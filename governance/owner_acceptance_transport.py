"""Post the current Owner Acceptance binding after explicit Owner approval.

This transport cannot authenticate the human approval. The caller must first
show the nine-section Summary and receive an explicit final Owner decision.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from governance import engine, owner_comment_provider


HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _hold(code: str, message: str) -> None:
    raise engine.GovernanceError(code, message, engine.EXIT_HOLD)


def build_comment(
    context: dict[str, Any], verification: dict[str, Any], summary: dict[str, Any],
    anchor: dict[str, Any], repository: dict[str, Any], pull: dict[str, Any],
    actor: dict[str, Any], scope: str,
) -> str:
    """Validate the current machine binding and format the transport body."""
    subject = context.get("canonical", {}).get("task", {}).get("subject")
    number = subject.get("number") if isinstance(subject, dict) and subject.get("type") == "PR" else None
    head = context.get("observations", {}).get("git_identity", {}).get("head")
    verification_hash = verification.get("verification_input_hash")
    if not isinstance(number, int) or number < 1 or not isinstance(head, str) or not HEX40.fullmatch(head):
        _hold("OWNER_TRANSPORT_CONTEXT_INVALID", "PR対象またはheadが不正です。")
    if verification.get("profile_id") != "formal-acceptance" or not verification.get("owner_acceptance_ready"):
        _hold("OWNER_TRANSPORT_GATES_NOT_READY", "technical gatesが完了していません。")
    if verification.get("decision") != "HOLD" or set(verification.get("blockers", [])) != {"OWNER_ACCEPTANCE_REQUIRED"}:
        _hold("OWNER_TRANSPORT_VERIFICATION_INVALID", "Owner承認待ち以外の停止理由があります。")
    if not isinstance(verification_hash, str) or not HEX64.fullmatch(verification_hash):
        _hold("OWNER_TRANSPORT_VERIFICATION_INVALID", "verification inputが不正です。")
    binding = engine._expected_owner_summary_binding(summary, verification_hash)
    if binding is None:
        _hold("OWNER_TRANSPORT_SUMMARY_INVALID", "現在のSummary bindingが不正です。")
    if not isinstance(scope, str) or not scope or scope != scope.strip() or any(ch in scope for ch in "\r\n"):
        _hold("OWNER_TRANSPORT_SCOPE_INVALID", "承認scopeは空でない一行にしてください。")
    if not all(isinstance(item, dict) for item in (repository, pull, actor)):
        _hold("OWNER_TRANSPORT_TARGET_MISMATCH", "GitHubの対象応答が不正です。")
    head_info, base_info = pull.get("head"), pull.get("base")
    if not isinstance(head_info, dict) or not isinstance(base_info, dict):
        _hold("OWNER_TRANSPORT_TARGET_MISMATCH", "PRの対象応答が不正です。")
    if not isinstance(head_info.get("repo"), dict) or not isinstance(base_info.get("repo"), dict):
        _hold("OWNER_TRANSPORT_TARGET_MISMATCH", "PRの対象応答が不正です。")
    if (
        str(repository.get("id")) != str(anchor.get("repository_id"))
        or repository.get("full_name") != anchor.get("repository_full_name")
        or str(actor.get("id")) != str(anchor.get("owner_actor_id"))
        or pull.get("number") != number
        or pull.get("state") != "open"
        or pull.get("head", {}).get("sha") != head
        or str(pull.get("head", {}).get("repo", {}).get("id")) != str(repository.get("id"))
        or str(pull.get("base", {}).get("repo", {}).get("id")) != str(repository.get("id"))
        or pull.get("base", {}).get("ref") != anchor.get("default_branch")
    ):
        _hold("OWNER_TRANSPORT_TARGET_MISMATCH", "GitHubの対象またはOwner identityが一致しません。")
    return (
        f"OWNER_ACCEPTANCE: APPROVED\nPR: #{number}\nHEAD: {head}\n"
        f"VERIFICATION_INPUT_HASH: {verification_hash}\nSUMMARY_BINDING: {binding}\nSCOPE: {scope}"
    )


def _require_formal_main_activation(root: Path) -> None:
    """The migration PR must be accepted under the pre-migration procedure."""
    path = "governance/owner_acceptance_transport.py"
    expected = subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"refs/remotes/origin/main:{path}"],
        capture_output=True, text=True, check=False,
    )
    actual = subprocess.run(
        ["git", "-C", str(root), "hash-object", str(root / path)],
        capture_output=True, text=True, check=False,
    )
    if expected.returncode or actual.returncode or expected.stdout.strip() != actual.stdout.strip():
        _hold("OWNER_TRANSPORT_NOT_FORMAL", "このhelperはformal main採用後にだけ使用できます。")


def post_comment(body: str, full_name: str, number: int, expected_owner_id: str) -> int:
    """Post once; retry can reuse an unchanged latest Owner approval comment."""
    comments = owner_comment_provider._comments(full_name, number)
    current_actor = owner_comment_provider._github_api("user")
    if not isinstance(current_actor, dict) or "id" not in current_actor:
        _hold("OWNER_TRANSPORT_TARGET_MISMATCH", "Owner identityを確認できません。")
    owner_id = str(current_actor["id"])
    if owner_id != expected_owner_id:
        _hold("OWNER_TRANSPORT_TARGET_MISMATCH", "Owner identityが変わりました。")
    owner_comments = sorted(
        (item for item in comments if str(item.get("user", {}).get("id")) == owner_id
         and isinstance(item.get("body"), str) and item["body"].startswith("OWNER_ACCEPTANCE:")),
        key=lambda item: (item.get("created_at", ""), item.get("id", 0)),
    )
    if owner_comments and owner_comments[-1].get("body") == body:
        if owner_comments[-1].get("created_at") != owner_comments[-1].get("updated_at"):
            _hold("OWNER_TRANSPORT_COMMENT_EDITED", "既存コメントが編集されています。")
        return int(owner_comments[-1]["id"])
    result = subprocess.run(
        ["gh", "api", f"repos/{full_name}/issues/{number}/comments", "--method", "POST", "-f", f"body={body}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        _hold("OWNER_TRANSPORT_POST_FAILED", "GitHubコメント投稿に失敗しました。")
    try:
        posted = json.loads(result.stdout)
        if posted["body"] != body or str(posted["user"]["id"]) != owner_id:
            raise ValueError("posted comment mismatch")
        return int(posted["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        _hold("OWNER_TRANSPORT_POST_UNVERIFIED", "投稿結果を確認できません。")


def main() -> int:
    parser = argparse.ArgumentParser(prog="owner-acceptance-transport")
    parser.add_argument("--context", required=True)
    parser.add_argument("--verification", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--scope", required=True, help="Ownerが明示的に承認した一行の事業範囲")
    args = parser.parse_args()
    try:
        root = Path(__file__).resolve().parents[1]
        _require_formal_main_activation(root)
        anchor, _ = engine._load_anchor()
        if anchor is None:
            _hold("TRUST_ANCHOR_MISSING", "Trust Anchorがありません。")
        context = engine.load_json(Path(args.context))
        verification = engine.load_json(Path(args.verification))
        summary = engine.load_json(Path(args.summary))
        full_name = anchor["repository_full_name"]
        subject = context.get("canonical", {}).get("task", {}).get("subject", {})
        number = subject.get("number") if isinstance(subject, dict) else None
        if not isinstance(number, int) or number < 1:
            _hold("OWNER_TRANSPORT_CONTEXT_INVALID", "PR対象が不正です。")
        repository = owner_comment_provider._github_api(f"repos/{full_name}")
        pull = owner_comment_provider._github_api(f"repos/{full_name}/pulls/{number}")
        actor = owner_comment_provider._github_api("user")
        body = build_comment(context, verification, summary, anchor, repository, pull, actor, args.scope)
        comment_id = post_comment(body, full_name, number, str(anchor["owner_actor_id"]))
        print(f"PASS: Owner Acceptance binding comment posted or confirmed: {comment_id}")
        return engine.EXIT_CONTINUE
    except engine.GovernanceError as exc:
        print(f"{exc.reason_code}: {exc.safe_message}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
