from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import pytest

from governance import engine, owner_evidence_preparation as preparation

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def packet(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Nonsecret preparation must not load any Anchor")

    monkeypatch.setattr(engine, "_load_anchor", forbidden)
    monkeypatch.setattr(engine, "_load_anchor_with_provenance", forbidden)
    task = {
        "schema_version": "2.0.0", "task_id": str(uuid.uuid4()), "repository_id": "1296080967",
        "profile_id": "formal-acceptance", "phase": "VALIDATION", "lifecycle": "OPEN",
        "scope": {"markets": ["PH", "SG"], "component_ids": ["governance"], "purpose": "Synthetic preparation"},
        "subject": {"type": "PR", "number": 999}, "additional_gate_ids": [],
        "additional_stop_condition_ids": [], "authorization_refs": ["owner-current-designation", "owner-current-permission"],
        "open_items": [],
    }
    path = tmp_path / "task context.json"
    key = tmp_path / "not opened key.dpapi"
    key.write_text("synthetic-secret-must-not-be-read", encoding="utf-8")
    original_read = Path.read_bytes

    def guarded_read(p):
        assert p != key, "Key reference must remain text only"
        return original_read(p)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)

    def run(**overrides):
        path.write_text(json.dumps(task), encoding="utf-8")
        args = dict(key_path=str(key), reference_source="owner-current-designation", authorization_ref="owner-current-permission")
        args.update(overrides)
        return preparation.inspect_preparation(path, **args)

    return task, path, key, run


def test_metadata_only_does_not_become_formal_readiness(packet):
    _, _, _, run = packet
    result = run()
    assert result["decision"] == "CONTINUE"
    assert result["formal_acceptance_ready"] is False
    assert result["key_checked"] is False
    assert result["requires_current_designation_review"] is True
    assert result["signing_state"] == "NOT_SIGNED"


def test_missing_conditions_are_aggregated_for_one_owner_request(packet):
    task, _, _, run = packet
    task["additional_gate_ids"] = ["protected.ph"]
    result = run(key_path="", reference_source="", authorization_ref="")
    assert result["decision"] == "HOLD"
    assert set(result["missing"]) == {
        "OWNER_KEY_REFERENCE_REQUIRED", "OWNER_KEY_REFERENCE_SOURCE_REQUIRED",
        "OWNER_KEY_USE_AUTHORIZATION_REQUIRED", "OWNER_ADDITIONAL_GATE_REASON_REQUIRED",
    }


@pytest.mark.parametrize("issue", ["closed", "checkout", "blocked", "old-source", "old-permission", "relative-key"])
def test_stale_or_unbound_metadata_stops_early(packet, issue):
    task, _, _, run = packet
    kwargs = {}
    if issue == "closed":
        task["lifecycle"] = "CLOSED"
    elif issue == "checkout":
        task["subject"] = "CHECKOUT"
    elif issue == "blocked":
        task["open_items"] = [{"id": "current-source", "blocking": True, "reason": "Unresolved current designation"}]
    elif issue == "old-source":
        kwargs["reference_source"] = "closed-task-script"
    elif issue == "old-permission":
        kwargs["authorization_ref"] = "closed-task-permission"
    else:
        kwargs["key_path"] = "old/key.dpapi"
    result = run(**kwargs)
    assert result["decision"] == "HOLD" and result["missing"]
    assert result["signing_state"] == "NOT_SIGNED"


def test_extra_gate_reason_is_indexed_without_weakening_gate(packet):
    task, _, _, run = packet
    task["additional_gate_ids"] = ["protected.ph", "protected.sg"]
    assert "OWNER_ADDITIONAL_GATE_REASON_REQUIRED" in run()["missing"]
    task["authorization_refs"].append("reviewed-extra-gate-risk-and-coverage")
    result = run(additional_gate_reason_ref="reviewed-extra-gate-risk-and-coverage")
    assert result["decision"] == "CONTINUE"
    assert result["additional_gate_ids"] == ["protected.ph", "protected.sg"]


def test_bad_json_does_not_echo_input_or_private_path(tmp_path):
    path = tmp_path / "private input.json"
    path.write_text("synthetic-password=do-not-echo invalid-json", encoding="utf-8")
    result = preparation.inspect_preparation(path)
    output = json.dumps(result)
    assert result["decision"] == "HARD_STOP"
    assert "synthetic-password" not in output and str(path) not in output


@pytest.mark.parametrize("shell_name", ["powershell", "pwsh"])
def test_native_preparation_captures_safe_json_and_preserves_context(packet, shell_name):
    shell = shutil.which(shell_name)
    if shell is None or sys.platform != "win32":
        pytest.skip("Windows shell unavailable")
    _, path, key, run = packet
    run()
    before = path.read_bytes()
    env = os.environ.copy()
    env.pop("GOVERNANCE_OWNER_EVIDENCE_PRIVATE_KEY", None)
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    command = [shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
               str(ROOT / "scripts/Test-OwnerEvidencePreparation.ps1"), "-TaskContext", str(path),
               "-PythonPath", sys.executable, "-KeyPath", str(key), "-ReferenceSource", "owner-current-designation",
               "-KeyUseAuthorizationRef", "owner-current-permission"]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["decision"] == "CONTINUE" and data["formal_acceptance_ready"] is False
    assert data["key_checked"] is False and path.read_bytes() == before


@pytest.mark.parametrize("shell_name", ["powershell", "pwsh"])
def test_provider_diagnostic_hold_survives_native_stop_semantics(tmp_path, shell_name):
    shell = shutil.which(shell_name)
    if shell is None or sys.platform != "win32":
        pytest.skip("Windows shell unavailable")
    script = tmp_path / "native diagnostic.ps1"
    script.write_text('''param([string]$PythonPath)
$ErrorActionPreference='Stop'
try {
 $lines=@(& $PythonPath -B -m governance.owner_comment_provider --diagnostic-json 2>&1)
 $code=$LASTEXITCODE
 $data=($lines -join "`n") | ConvertFrom-Json
 if($code -ne 10 -or $data.reason_code -ne 'OWNER_PROVIDER_ARGUMENTS_REQUIRED' -or $data.signing_state -ne 'NOT_SIGNED') { exit 1 }
 Write-Output ($data | ConvertTo-Json -Compress)
 exit 0
} catch { exit 1 }
''', encoding="utf-8-sig")
    env = os.environ.copy()
    for key in ["GOVERNANCE_OWNER_EVIDENCE_PRIVATE_KEY", "GOVERNANCE_TRUST_ANCHOR_JSON", "GOVERNANCE_TRUST_ANCHOR_SOURCE"]:
        env.pop(key, None)
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", LOCALAPPDATA=str(tmp_path / "empty-appdata"))
    process = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                              str(script), "-PythonPath", sys.executable], cwd=ROOT, env=env,
                             capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert process.returncode == 0, process.stdout + process.stderr
    result = json.loads(process.stdout)
    assert result["signing_state"] == "NOT_SIGNED"
    assert result["reason_code"] == "OWNER_PROVIDER_ARGUMENTS_REQUIRED"


@pytest.mark.parametrize("shell_name", ["powershell", "pwsh"])
@pytest.mark.parametrize("failure", ["missing", "noisy"])
def test_native_preparation_failure_is_safe_and_never_signs(packet, shell_name, failure):
    shell = shutil.which(shell_name)
    if shell is None or sys.platform != "win32":
        pytest.skip("Windows shell unavailable")
    _, path, key, run = packet
    run()
    interpreter = path.parent / "missing private interpreter.exe"
    marker = "SYNTHETIC_PRIVATE_MARKER_DO_NOT_ECHO"
    if failure == "noisy":
        interpreter = path.parent / "synthetic noisy interpreter.cmd"
        interpreter.write_text(f"@echo off\necho {marker} 1>&2\necho not-json\nexit /b 1\n", encoding="ascii")
    command = [shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
               str(ROOT / "scripts/Test-OwnerEvidencePreparation.ps1"), "-TaskContext", str(path),
               "-PythonPath", str(interpreter), "-KeyPath", str(key)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 10
    data = json.loads(result.stdout)
    assert data["reason_code"] == "OWNER_PREPARATION_LAUNCH_HOLD"
    assert data["signing_state"] == "NOT_SIGNED" and data["key_checked"] is False
    assert marker not in result.stdout + result.stderr
    assert str(interpreter) not in result.stdout + result.stderr
