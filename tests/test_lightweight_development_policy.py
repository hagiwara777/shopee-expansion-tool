"""Contract tests for lightweight development policy v1."""

from __future__ import annotations

import subprocess
import os
import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_SCRIPT = PROJECT_ROOT / "scripts" / "Verify-LightweightDevelopmentPolicy.ps1"
COMPATIBILITY_SCRIPT = PROJECT_ROOT / "scripts" / "Verify-WorkBriefHandoff.ps1"


def _run(script: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        timeout=30,
    )


def test_policy_documents_and_internal_scenarios_are_consistent():
    completed = _run(POLICY_SCRIPT)

    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"PASS: lightweight development policy verification" in completed.stdout


@pytest.mark.parametrize(
    ("arguments", "expected_code", "expected_decision"),
    [
        (("ReadOnly",), 0, b"POLICY_DECISION: PASS"),
        (("LocalEdit",), 0, b"POLICY_DECISION: PASS"),
        (("LocalTest",), 0, b"POLICY_DECISION: PASS"),
        (("LocalCommit",), 0, b"POLICY_DECISION: PASS"),
        (("LocalEdit", "-DirtyOverwritesUserChanges"), 3, b"POLICY_DECISION: STOP"),
        (("PaidApi",), 3, b"POLICY_DECISION: STOP"),
        (("ExternalWrite",), 3, b"POLICY_DECISION: STOP"),
        (("IrrecoverableDelete",), 3, b"POLICY_DECISION: STOP"),
        (("MajorScopeChange",), 3, b"POLICY_DECISION: STOP"),
        (("MajorScopeChange", "-Approved"), 0, b"POLICY_DECISION: PASS"),
        (("Push",), 3, b"POLICY_DECISION: STOP"),
        (("DraftPr",), 3, b"POLICY_DECISION: STOP"),
        (("Merge",), 3, b"POLICY_DECISION: STOP"),
        (("Merge", "-Approved"), 3, b"POLICY_DECISION: STOP"),
        (("Deploy",), 3, b"POLICY_DECISION: STOP"),
        (("LocalCommit", "-SecretToGit"), 3, b"POLICY_DECISION: STOP"),
        (("Push", "-Approved"), 0, b"POLICY_DECISION: PASS"),
        (("DraftPr", "-Approved"), 0, b"POLICY_DECISION: PASS"),
    ],
)
def test_action_scenarios_return_expected_policy_decision(
    arguments: tuple[str, ...],
    expected_code: int,
    expected_decision: bytes,
):
    completed = _run(POLICY_SCRIPT, "-Scenario", *arguments)

    assert completed.returncode == expected_code, completed.stderr.decode(errors="replace")
    assert expected_decision in completed.stdout


def test_legacy_script_path_delegates_without_old_arguments():
    completed = _run(COMPATIBILITY_SCRIPT)

    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    combined = completed.stdout + completed.stderr
    assert b"PASS: lightweight development policy verification" in combined


def test_legacy_work_brief_arguments_fail_with_deprecation_message():
    completed = _run(COMPATIBILITY_SCRIPT, "-BriefPath", "obsolete.md")

    assert completed.returncode == 2
    combined = completed.stdout + completed.stderr
    assert b"Verify-LightweightDevelopmentPolicy.ps1" in combined


def test_historical_and_product_chatgpt_references_remain_allowed():
    decision_log = (PROJECT_ROOT / "docs" / "DECISION_LOG.md").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "FORMAL_WORK_UNIT_CLOSED" in decision_log
    assert "ChatGPT" in readme


def test_readonly_and_independent_local_work_do_not_require_formal_acceptance(tmp_path):
    # A synthetic missing-anchor environment, never the operator's real trust store.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GOVERNANCE_")}
    env["LOCALAPPDATA"] = str(tmp_path / "empty-appdata")
    env["APPDATA"] = str(tmp_path / "empty-roaming")
    env["GOVERNANCE_TRUST_ANCHOR_SOURCE"] = "local-file"
    output = tmp_path / "snapshot"
    for command in (
        ["git", "status", "--short"],
        ["git", "rev-parse", "--show-toplevel"],
        ["git", "log", "-1", "--oneline"],
        [sys.executable, "-m", "governance.engine", "validate", "--repository", str(PROJECT_ROOT)],
        [sys.executable, "-m", "governance.engine", "generate", "--repository", str(PROJECT_ROOT), "--output-dir", str(output)],
    ):
        result = subprocess.run(command, cwd=PROJECT_ROOT, env=env, capture_output=True, timeout=30)
        assert result.returncode == 0
    result = subprocess.run(
        [sys.executable, "-m", "governance.engine", "verify", "--repository", str(PROJECT_ROOT),
         "--context", str(output / "context.json"), "--profile", "formal-acceptance", "--output-dir", str(output)],
        cwd=PROJECT_ROOT, env=env, capture_output=True, timeout=30,
    )
    assert result.returncode == 10
    verification = json.loads((output / "verification.json").read_text(encoding="utf-8"))
    assert verification["decision"] == "HOLD"
    assert "TRUST_ANCHOR_SELECTED_SOURCE_MISSING" in verification["blockers"]
    assert not verification["owner_acceptance_ready"]
    for scenario, expected in (("ReadOnly", 0), ("LocalEdit", 0), ("LocalTest", 0), ("Merge", 3), ("PaidApi", 3)):
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-File", str(POLICY_SCRIPT), "-Scenario", scenario],
            cwd=PROJECT_ROOT, env=env, capture_output=True, timeout=30,
        )
        assert result.returncode == expected
    # Local policy results neither modify the formal decision nor confer authority.
    assert json.loads((output / "verification.json").read_text(encoding="utf-8")) == verification
