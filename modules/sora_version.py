"""Capture the checkout version once, so reruns do not relabel loaded code."""
from pathlib import Path
import re
import subprocess


def _running_version():
    root = Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root,
                                capture_output=True, text=True, timeout=2, check=True)
        commit = result.stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            return "確認できません"
        dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=root,
                               capture_output=True, timeout=2).returncode
        return commit[:7] + ("（変更あり）" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "確認できません"


RUNNING_VERSION = _running_version()
