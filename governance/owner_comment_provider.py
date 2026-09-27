"""Fetch GitHub Owner PR comments and issue short-lived signed acceptance evidence.

This is deliberately separate from the offline Governance generator and verifier.
The signing key belongs to a trusted provider runtime, never to the repository.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from governance import engine


APPROVAL = re.compile(
    r"\AOWNER_ACCEPTANCE: APPROVED\nPR: #(\d+)\nHEAD: ([0-9a-f]{40})\n"
    r"VERIFICATION_INPUT_HASH: ([0-9a-f]{64})\nSUMMARY_BINDING: ([0-9a-f]{64})\n"
    r"SCOPE: ([^\r\n]+)\s*\Z"
)
REVOKED = re.compile(r"\AOWNER_ACCEPTANCE: REVOKED\b")


def _github_api(path: str) -> Any:
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    if result.returncode:
        raise engine.GovernanceError("GITHUB_OWNER_PROVIDER_UNAVAILABLE", "GitHub観測に失敗しました。", engine.EXIT_HOLD)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise engine.GovernanceError("GITHUB_OWNER_PROVIDER_INVALID", "GitHub応答が不正です。", engine.EXIT_HOLD) from exc


def _comments(full_name: str, pr_number: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    page = 1
    while True:
        items = _github_api(f"repos/{full_name}/issues/{pr_number}/comments?per_page=100&page={page}")
        if not isinstance(items, list):
            raise engine.GovernanceError("GITHUB_OWNER_PROVIDER_INVALID", "コメント応答が不正です。", engine.EXIT_HOLD)
        result.extend(items)
        if len(items) < 100:
            return result
        page += 1


def build_evidence(
    context: dict[str, Any], verification: dict[str, Any], summary: dict[str, Any],
    anchor: dict[str, Any], repository: dict[str, Any], pull: dict[str, Any],
    comments: list[dict[str, Any]], private_key: Ed25519PrivateKey,
    *, observed_at: datetime | None = None,
) -> dict[str, Any]:
    if anchor.get("anchor_version") != "1.1.0":
        raise engine.GovernanceError("OWNER_EVIDENCE_TRUST_KEY_REQUIRED", "Owner Evidence公開鍵が未設定です。", engine.EXIT_HOLD)
    if (
        str(repository.get("id")) != str(anchor["repository_id"])
        or repository.get("full_name") != anchor["repository_full_name"]
        or pull.get("base", {}).get("repo", {}).get("id") != repository.get("id")
    ):
        raise engine.GovernanceError("OWNER_REPOSITORY_MISMATCH", "repository identityが一致しません。", engine.EXIT_HARD_STOP)
    subject = context["canonical"].get("task", {}).get("subject")
    if not isinstance(subject, dict) or subject.get("type") != "PR":
        raise engine.GovernanceError("OWNER_PR_MISMATCH", "Task ContextにPR対象がありません。", engine.EXIT_HOLD)
    number = subject["number"]
    head = context["observations"]["git_identity"]["head"]
    if pull.get("number") != number or pull.get("head", {}).get("sha") != head:
        raise engine.GovernanceError("OWNER_HEAD_MISMATCH", "PR番号またはheadが一致しません。", engine.EXIT_HOLD)
    binding = engine._expected_owner_summary_binding(summary, verification["verification_input_hash"])
    if binding is None or not verification.get("owner_acceptance_ready"):
        raise engine.GovernanceError("OWNER_SUMMARY_MISMATCH", "Summaryのbindingが不正です。", engine.EXIT_HOLD)
    owner_comments = sorted(
        (item for item in comments if str(item.get("user", {}).get("id")) == str(anchor["owner_actor_id"])
         and isinstance(item.get("body"), str) and item["body"].startswith("OWNER_ACCEPTANCE:")),
        key=lambda item: (item.get("created_at", ""), item.get("id", 0)),
    )
    if not owner_comments or REVOKED.match(owner_comments[-1]["body"]):
        raise engine.GovernanceError("OWNER_ACCEPTANCE_REQUIRED", "Owner承認コメントがありません。", engine.EXIT_HOLD)
    comment = owner_comments[-1]
    if comment.get("created_at") != comment.get("updated_at"):
        raise engine.GovernanceError("OWNER_COMMENT_EDITED", "Owner承認コメントが編集されています。", engine.EXIT_HOLD)
    match = APPROVAL.fullmatch(comment["body"])
    if not match or (int(match[1]), match[2], match[3], match[4]) != (
        number, head, verification["verification_input_hash"], binding,
    ):
        raise engine.GovernanceError("OWNER_ACCEPTANCE_BINDING_MISMATCH", "Owner承認対象が一致しません。", engine.EXIT_HOLD)
    receipt = {
        "repository_id": str(repository["id"]),
        "repository_full_name": repository["full_name"],
        "pr_number": number,
        "actor_id": str(comment["user"]["id"]),
        "comment_id": comment["id"],
        "comment_created_at": comment["created_at"],
        "comment_body_sha256": engine.sha256_bytes(comment["body"].encode("utf-8")),
        "head": head,
        "verification_input_hash": verification["verification_input_hash"],
        "summary_binding": binding,
        "decision": "APPROVED",
        "scope": match[5].strip(),
        "observed_at": (observed_at or datetime.now(UTC)).astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }
    signature = base64.b64encode(private_key.sign(engine.canonical_bytes(receipt))).decode("ascii")
    record = {
        "evidence_id": f"owner-pr-{number}-comment-{comment['id']}", "schema_version": engine.SCHEMA_VERSION,
        "kind": "OWNER_ACCEPTANCE", "repository_id": str(repository["id"]),
        "object_format": "sha1", "tested_commit": head, "tested_tree": None,
        "base_commit": None, "merge_base": None, "capability_ids": [], "component_ids": [],
        "component_manifest": None, "state_schema_hash": None, "config_version": engine.SCHEMA_VERSION,
        "registry_hash": None, "gate_id": None, "gate_definition_hash": None,
        "profile_hash": None, "test_plan_hash": None, "test_source_hash": None,
        "fixture_hash": None, "environment": None, "runner_version": None,
        "observation": "PASS", "reason_codes": ["GITHUB_OWNER_COMMENT_VERIFIED"],
        "report_sha256": None, "provenance": "GITHUB_OWNER", "executed_at": receipt["observed_at"],
        "external_validity": None,
        "source": {
            "type": "GITHUB_PR_COMMENT", "receipt": receipt, "signature": signature,
            "actor_id": receipt["actor_id"],
            "verification_input_hash": receipt["verification_input_hash"],
            "summary_binding": receipt["summary_binding"],
        },
    }
    engine._schema_validate(record, engine.load_bundle(Path(__file__).resolve().parents[1]).schemas["schemas/evidence.schema.json"], "evidence")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(prog="owner-comment-provider")
    parser.add_argument("--context", required=True)
    parser.add_argument("--verification", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        anchor, _ = engine._load_anchor()
        if anchor is None:
            raise engine.GovernanceError("TRUST_ANCHOR_MISSING", "Trust Anchorがありません。", engine.EXIT_HOLD)
        raw_key = os.environ.get("GOVERNANCE_OWNER_EVIDENCE_PRIVATE_KEY", "")
        try:
            private_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(raw_key, validate=True))
        except (ValueError, TypeError) as exc:
            raise engine.GovernanceError("OWNER_PROVIDER_KEY_REQUIRED", "Provider署名鍵がありません。", engine.EXIT_HOLD) from exc
        public_key = private_key.public_key().public_bytes_raw()
        if base64.b64encode(public_key).decode("ascii") != anchor.get("owner_evidence_public_key"):
            raise engine.GovernanceError("OWNER_PROVIDER_KEY_MISMATCH", "Provider署名鍵がTrust Anchorと一致しません。", engine.EXIT_HOLD)
        context = engine.load_json(Path(args.context))
        verification = engine.load_json(Path(args.verification))
        summary = engine.load_json(Path(args.summary))
        subject = context["canonical"]["task"]["subject"]
        full_name = anchor["repository_full_name"]
        repository = _github_api(f"repos/{full_name}")
        pull = _github_api(f"repos/{full_name}/pulls/{subject['number']}")
        record = build_evidence(context, verification, summary, anchor, repository, pull,
                                _comments(full_name, subject["number"]), private_key)
        digest = engine.evidence_digest(record)
        output = Path(args.output_dir) / f"{digest}.json"
        engine._write_output(output, engine.canonical_bytes(record))
        print(f"PASS: GitHub Owner comment evidence generated: {output.name}")
        return engine.EXIT_CONTINUE
    except engine.GovernanceError as exc:
        print(f"{exc.reason_code}: {exc.safe_message}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
