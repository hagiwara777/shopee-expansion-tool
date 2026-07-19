"""Contract checks for the repository-local change verification loop."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = PROJECT_ROOT / "scripts" / "verify_change.ps1"
PYTHON_SYNTAX_SCRIPT = PROJECT_ROOT / "scripts" / "check_python_syntax.py"
DOCUMENTATION = PROJECT_ROOT / "docs" / "testing" / "change_verification_loop.md"


def _run_dry_run(tmp_path: Path, mode: str) -> tuple[subprocess.CompletedProcess[bytes], Path]:
    report_path = tmp_path / f"{mode.lower()}-report.md"
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(VERIFY_SCRIPT),
            "-Mode",
            mode,
            "-DryRun",
            "-ReportPath",
            str(report_path),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        timeout=20,
    )
    return completed, report_path


def test_quick_and_full_dry_runs_finish_without_browser_wait(tmp_path: Path):
    quick, quick_report = _run_dry_run(tmp_path, "Quick")
    full, full_report = _run_dry_run(tmp_path, "Full")

    assert quick.returncode == 0, quick.stderr.decode(errors="replace")
    assert full.returncode == 0, full.stderr.decode(errors="replace")
    assert "CONDITIONAL_PASS" in quick_report.read_text(encoding="utf-8")
    assert "CONDITIONAL_PASS" in full_report.read_text(encoding="utf-8")


def test_verification_script_has_bounded_stages_and_browser_handoff_contract():
    source = VERIFY_SCRIPT.read_text(encoding="utf-8-sig")

    assert 'ValidateSet("Quick", "Full", "Browser")' in source
    assert 'ValidateSet("Auto", "Prepare", "Verify")' in source
    assert "function Invoke-ProcessStage" in source
    assert "WaitForExit" in source
    assert '"TIMEOUT"' in source
    assert "Stop-Process -Id $process.Id -Force" in source
    assert "Streamlit停止・PIDポート清掃" in source
    assert "FULL_NONINTERACTIVE" in source
    assert "BROWSER_READY" in source
    assert "BROWSER_UNAVAILABLE" in source
    assert "prepare_browser_e2e.ps1" in source
    assert "start_streamlit_e2e.ps1" in source
    assert "stop_streamlit_e2e.ps1" in source
    assert "verify_browser_downloads.ps1" in source
    assert "computer-use-client" not in source
    assert "Read-Host" not in source
    assert "Wait-Process" not in source
    assert "Wait-Job" not in source
    assert "Receive-Job" not in source
    for required_stage in (
        "対象テスト",
        "全回帰",
        "Python構文検査",
        "PowerShell構文検査",
        "git diff --check",
        "変更ファイル",
        "セキュリティ監査",
        "Streamlit AppTest",
        "E2E fixture契約",
        "Streamlit起動",
        "health HTTP確認",
        "root HTTP確認",
        "Streamlit停止・PIDポート清掃",
    ):
        assert required_stage in source
    assert not re.search(r"(?i)[a-z]:\\", source)


def test_python_syntax_helper_parses_in_memory_without_creating_pyc(tmp_path: Path):
    source_file = tmp_path / "valid_source.py"
    source_file.write_text("answer = 42\n", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(PYTHON_SYNTAX_SCRIPT), str(source_file)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "PASS: Python syntax check (1 file(s))" in completed.stdout
    assert not list(tmp_path.rglob("*.pyc"))


def test_documentation_describes_noninteractive_full_and_agent_browser_handoff():
    documentation = DOCUMENTATION.read_text(encoding="utf-8")

    assert "自動テストの結果と、実商品・事業上の妥当性を混同しない" in documentation
    assert "PowerShell は Computer Use を実行しません" in documentation
    assert "BROWSER_UNAVAILABLE" in documentation
    assert "-BrowserStage Prepare" in documentation
    assert "-BrowserStage Verify" in documentation
