"""Nonsecret preparation metadata check; never opens a key or Trust Anchor.

Exact reference membership is an index check, not proof of Owner intent.
The original current designation and permission still require source review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from governance import engine

ROOT = Path(__file__).resolve().parents[1]


def inspect_preparation(task_path: Path, *, key_path: str = "", reference_source: str = "",
                        authorization_ref: str = "", additional_gate_reason_ref: str = "") -> dict[str, object]:
    result: dict[str, object] = {
        "decision": "HOLD", "reason_code": "OWNER_PREPARATION_INCOMPLETE", "stage": "PREPARATION",
        "signing_state": "NOT_SIGNED", "key_checked": False, "formal_acceptance_ready": False,
        "requires_current_designation_review": True, "missing": [], "additional_gate_ids": [],
    }
    try:
        task = engine._load_task_context(engine.load_bundle(ROOT), task_path, None)
        missing: list[str] = []
        if task is None:
            missing.append("OWNER_TASK_REQUIRED")
        else:
            refs = task["authorization_refs"]
            result["additional_gate_ids"] = task["additional_gate_ids"]
            if task["lifecycle"] != "OPEN":
                missing.append("OWNER_TASK_NOT_OPEN")
            if not isinstance(task["subject"], dict) or task["subject"].get("type") != "PR":
                missing.append("OWNER_TARGET_PR_REQUIRED")
            if any(item["blocking"] for item in task["open_items"]):
                missing.append("OWNER_PREPARATION_BLOCKED")
            # key_path is text only; do not stat, read, resolve, search or decrypt.
            if not key_path or not Path(key_path).is_absolute():
                missing.append("OWNER_KEY_REFERENCE_REQUIRED")
            if not reference_source or reference_source not in refs:
                missing.append("OWNER_KEY_REFERENCE_SOURCE_REQUIRED")
            if not authorization_ref or authorization_ref not in refs:
                missing.append("OWNER_KEY_USE_AUTHORIZATION_REQUIRED")
            if task["additional_gate_ids"] and (not additional_gate_reason_ref or additional_gate_reason_ref not in refs):
                missing.append("OWNER_ADDITIONAL_GATE_REASON_REQUIRED")
        result["missing"] = missing
        if not missing:
            result.update(decision="CONTINUE", reason_code="OWNER_PREPARATION_METADATA_OK")
    except engine.GovernanceError as exc:
        result.update(decision="HARD_STOP" if exc.exit_code == engine.EXIT_HARD_STOP else "HOLD",
                      reason_code="OWNER_PREPARATION_CONTRACT_INVALID")
    except Exception:
        result["reason_code"] = "OWNER_PREPARATION_INPUT_HOLD"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(prog="owner-evidence-preparation")
    parser.add_argument("--task-context", required=True)
    parser.add_argument("--key-path", default="")
    parser.add_argument("--reference-source", default="")
    parser.add_argument("--key-use-authorization-ref", default="")
    parser.add_argument("--additional-gate-reason-ref", default="")
    args = parser.parse_args()
    result = inspect_preparation(Path(args.task_context), key_path=args.key_path,
                                 reference_source=args.reference_source, authorization_ref=args.key_use_authorization_ref,
                                 additional_gate_reason_ref=args.additional_gate_reason_ref)
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return {"CONTINUE": 0, "HOLD": 10, "HARD_STOP": 20}[str(result["decision"])]


if __name__ == "__main__":
    raise SystemExit(main())
