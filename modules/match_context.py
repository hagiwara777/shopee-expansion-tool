"""Bounded, plain-text product evidence for displayed decision notes."""
import re


def excerpt_at(value: str, start: int, end: int, radius: int = 20) -> str:
    """Quote a match with at most ``radius`` source characters on each side."""
    left, right = max(0, start - radius), min(len(value), end + radius)
    snippet = re.sub(r"[\s\x00-\x1f\x7f]", " ", value[left:right]).replace("|", "｜")
    return ("…" if left else "") + snippet + ("…" if right < len(value) else "")
