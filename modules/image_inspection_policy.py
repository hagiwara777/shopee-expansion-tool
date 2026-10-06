"""Common image target selection with explicit per-market Amazon root data.

MY/TH settings are initial development baselines, not operational activation.
Unknown roots are inspected; a skip never means a successful AI inspection.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re

POLICY_DIR = Path(__file__).resolve().parents[1] / "data" / "image_inspection"
MARKETS = frozenset({"PH", "SG", "MY", "TH"})


def normalize_root(value):
    if type(value) is int and 0 < value <= 2**63 - 1:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,19}", value.strip()):
        return normalize_root(int(value.strip()))
    return None


@dataclass(frozen=True)
class ImageInspectionPolicy:
    marketplace: str
    target_roots: frozenset[int]
    digest: str


def load_image_inspection_policy(marketplace):
    if marketplace not in MARKETS:
        raise ValueError("Unsupported image inspection marketplace")
    try:
        raw = (POLICY_DIR / f"{marketplace.lower()}.json").read_bytes()
        data = json.loads(raw)
        roots = data["target_root_category_ids"]
        if (set(data) != {"schema_version", "marketplace", "target_root_category_ids"}
                or type(data["schema_version"]) is not int or data["schema_version"] != 1
                or data["marketplace"] != marketplace or not isinstance(roots, list)
                or not roots or any(type(x) is not int or normalize_root(x) != x for x in roots)
                or len(set(roots)) != len(roots)):
            raise ValueError
        return ImageInspectionPolicy(marketplace, frozenset(roots), hashlib.sha256(raw).hexdigest())
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError("Image inspection country configuration unavailable or invalid") from None


def select_image_inspection(*, marketplace, root_category_id, provider, guardrail_status):
    policy = load_image_inspection_policy(marketplace)
    if guardrail_status not in {"SAFE", "REVIEW", "BLOCK"}:
        raise ValueError("Invalid existing Safety state")
    if provider not in {"keepa", "canopy_test"}:
        raise ValueError("Invalid image provider")
    if guardrail_status == "BLOCK":
        return "EXISTING_BLOCK"
    if provider == "canopy_test":
        return "PROVIDER_UNSUPPORTED"
    root = normalize_root(root_category_id)
    if root is None:
        return "ROOT_UNKNOWN"
    return "TARGET_ROOT" if root in policy.target_roots else "OTHER_ROOT"
