"""Contract tests for lightweight development policy v1."""

from __future__ import annotations

import subprocess
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
        (("Deploy",), 3, b"POLICY_DECISION: STOP"),
        (("LocalCommit", "-SecretToGit"), 3, b"POLICY_DECISION: STOP"),
        (("Push", "-Approved"), 0, b"POLICY_DECISION: PASS"),
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
