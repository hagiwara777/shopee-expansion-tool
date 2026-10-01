"""Offline contract for the CURRENT_WORK restart guide only."""
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
TRANSIENT_MARKERS = (
    r"WAITING_APPROVAL",
    r"OWNER_ACCEPTANCE_REQUIRED",
    r"Owner\s*Acceptance\s*待ち",
    r"Owner\s*承認待ち",
    r"Owner\s*最終承認を待",
    r"未マージ",
    r"Draft\s+PR",
)


def assert_post_merge_stable_restart_guide(text: str) -> None:
    """Catch explicit volatile state; semantic merge review remains mandatory."""
    found = [marker for marker in TRANSIENT_MARKERS if re.search(marker, text, re.IGNORECASE)]
    assert not found, f"POST_MERGE_STABILITY_FAIL: transient CURRENT_WORK state: {found}"


def test_current_work_is_post_merge_stable() -> None:
    assert_post_merge_stable_restart_guide(
        (ROOT / "docs" / "CURRENT_WORK.md").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("marker", [
    "WAITING_APPROVAL", "OWNER_ACCEPTANCE_REQUIRED", "Owner Acceptance待ち",
    "Owner承認待ち", "Owner最終承認を待つ", "未マージ", "Draft PR",
    "draft pr", "Owner Acceptance 待ち", "Owner 承認待ち",
])
@pytest.mark.parametrize("section", ["現在の単一作業", "現在の正式状態", "次の独立工程"])
def test_transient_current_state_fails(marker: str, section: str) -> None:
    text = f"# CURRENT WORK\n\n## {section}\n\nこのPRは{marker}。\n"
    with pytest.raises(AssertionError, match="POST_MERGE_STABILITY_FAIL"):
        assert_post_merge_stable_restart_guide(text)


@pytest.mark.parametrize("text", [
    "PR #111は正式採用済み。accepted headと確定merge commitはGitHubで確認できる。",
    "Step 8 CLOSED。次の独立工程Step 9は未承認・未着手。別Owner承認が必要。",
    "AI候補を人間が確認する。現在のhead / PR / checksはGit / GitHubを参照する。",
])
def test_stable_history_and_independent_approval_boundary_pass(text: str) -> None:
    assert_post_merge_stable_restart_guide(text)
