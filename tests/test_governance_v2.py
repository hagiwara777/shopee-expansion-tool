from __future__ import annotations

import copy
import base64
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import pytest

from governance import engine
from governance import owner_comment_provider
from governance import owner_acceptance_transport


ROOT = Path(__file__).resolve().parents[1]
ANCHOR = {
    "anchor_version": "1.0.0",
    "provider": "github",
    "host": "github.com",
    "repository_id": "1296080967",
    "repository_full_name": "hagiwara777/shopee-expansion-tool",
    "default_branch": "main",
    "owner_actor_id": "207869136",
    "bootstrap_formal_commit": "136958a1bf2493983b4413f7d231ee5adbd913bf",
}


def git(path: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


@pytest.fixture
def trusted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GOVERNANCE_TRUST_ANCHOR_JSON", json.dumps(ANCHOR))
    monkeypatch.setenv("GOVERNANCE_TRUST_ANCHOR_SOURCE", "ci-env-json")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "empty-appdata"))
    monkeypatch.delenv("APPDATA", raising=False)


def change(status: str, old: str | None = None, new: str | None = None) -> dict[str, object]:
    return {"status": status, "old_path": old, "new_path": new, "old_mode": None, "new_mode": None}


def task_context(task_id: str | None = None) -> dict[str, object]:
    return {
        "schema_version": "2.0.0",
        "task_id": task_id or str(uuid.uuid4()),
        "repository_id": "1296080967",
        "profile_id": "local-validation",
        "phase": "VALIDATION",
        "lifecycle": "OPEN",
        "scope": {"markets": [], "component_ids": ["governance"], "purpose": "Governance v2 validation"},
        "subject": "CHECKOUT",
        "additional_gate_ids": [],
        "additional_stop_condition_ids": [],
        "authorization_refs": [],
        "open_items": [],
    }


def test_gv2_config_001_machine_state_and_manifest_validate() -> None:
    bundle = engine.load_bundle(ROOT)
    assert bundle.state["markets"] == {
        "PH": {"operation": "ACTIVE", "development_policy": "ALLOWED"},
        "SG": {"operation": "ACTIVE", "development_policy": "ALLOWED"},
        "MY": {"operation": "INACTIVE", "development_policy": "NOT_STARTED"},
        "TH": {"operation": "INACTIVE", "development_policy": "NOT_STARTED"},
    }
    assert "active_task" not in bundle.state


def test_gv2_ci_workflow_emits_evidence_for_every_mandatory_check() -> None:
    generator = (ROOT / "scripts" / "Generate-GovernanceEvidence.ps1").read_text(
        encoding="utf-8"
    )
    workflow = (ROOT / ".github" / "workflows" / "governance-v2.yml").read_text(
        encoding="utf-8"
    )
    check_ids = {check["id"] for check in engine.load_bundle(ROOT).gates["checks"]}

    assert all(f'"{check_id}"' in generator for check_id in check_ids)
    assert all(f"-GateId {check_id} " in workflow for check_id in check_ids)
    assert "path: work/ci/commerce-api-core" in workflow
    assert "python -m pip install ./work/ci/commerce-api-core" in workflow
    assert git(ROOT, "check-ignore", "work/ci/commerce-api-core") == "work/ci/commerce-api-core"


@pytest.mark.parametrize(
    ("test_id", "changes", "expected"),
    [
        ("GV2-CLASS-GOVERNANCE", [change("M", new="governance/state.json")], "GOVERNANCE_ONLY"),
        ("GV2-CLASS-MARKET", [change("M", new="guardrails/risk_keywords_ph.csv")], "MARKET_LOCAL"),
        ("GV2-CLASS-SHARED", [change("M", new="modules/config.py")], "SHARED_CORE"),
        ("GV2-CLASS-UNKNOWN", [change("A", new="mystery/new.py")], "SHARED_CORE"),
        ("GV2-CLASS-RENAME", [change("R", old="guardrails/risk_keywords_ph.csv", new="mystery/rules.csv")], "SHARED_CORE"),
        ("GV2-CLASS-DELETE", [change("D", old="modules/guardrails.py")], "SHARED_CORE"),
        ("GV2-CLASS-MODE", [change("M", new="modules/guardrails.py")], "SHARED_CORE"),
    ],
    ids=lambda value: value if isinstance(value, str) and value.startswith("GV2-") else None,
)
def test_gv2_classification(test_id: str, changes: list[dict[str, object]], expected: str) -> None:
    assert test_id
    result = engine.classify_changes(changes, engine.load_bundle(ROOT).ownership)
    assert result["classification"] == expected


def test_gv2_protect_001_ph_and_sg_for_shared_core() -> None:
    bundle = engine.load_bundle(ROOT)
    classified = engine.classify_changes([change("M", new="modules/config.py")], bundle.ownership)
    assert engine._protected_capabilities(bundle, classified) == ["ph.beta.operation", "sg.safety.baseline"]


def test_gv2_sls_shared_asset_is_owned_and_requires_ph_and_sg_protection() -> None:
    bundle = engine.load_bundle(ROOT)
    classified = engine.classify_changes(
        [change("A", new="guardrails/sls_shared/battery_review_rules.csv")],
        bundle.ownership,
    )

    assert classified["classification"] == "SHARED_CORE"
    assert classified["components"] == ["safety.shared"]
    assert classified["unknown_paths"] == []
    assert engine._protected_capabilities(bundle, classified) == [
        "ph.beta.operation",
        "sg.safety.baseline",
    ]


def test_gv2_task_001_parallel_context_does_not_change_global_state(trusted: None, tmp_path: Path) -> None:
    state_before = (ROOT / "governance/state.json").read_bytes()
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps(task_context()), encoding="utf-8")
    second.write_text(json.dumps(task_context()), encoding="utf-8")
    bundle = engine.load_bundle(ROOT)
    assert engine._load_task_context(bundle, first, ANCHOR)["task_id"] != engine._load_task_context(bundle, second, ANCHOR)["task_id"]
    assert (ROOT / "governance/state.json").read_bytes() == state_before


def test_gv2_task_002_context_cannot_delete_mandatory_gate(trusted: None, tmp_path: Path) -> None:
    path = tmp_path / "task.json"
    value = task_context()
    value["remove_gate_ids"] = ["governance.validate"]
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(engine.GovernanceError, match="schema"):
        engine._load_task_context(engine.load_bundle(ROOT), path, ANCHOR)


def test_gv2_anchor_001_missing_is_hold(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GOVERNANCE_TRUST_ANCHOR_JSON", raising=False)
    monkeypatch.delenv("GOVERNANCE_TRUST_ANCHOR_SOURCE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    context = engine.generate_context(ROOT)
    result = engine.verify_context(ROOT, context, profile_id="read-only")
    assert result["decision"] == "HOLD"
    assert "TRUST_ANCHOR_MISSING" in result["blockers"]


def test_gv2_anchor_002_repo_fake_anchor_is_not_trusted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GOVERNANCE_TRUST_ANCHOR_JSON", raising=False)
    monkeypatch.delenv("GOVERNANCE_TRUST_ANCHOR_SOURCE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "outside"))
    fake = tmp_path / "repo" / "governance" / "trust-anchor.json"
    fake.parent.mkdir(parents=True)
    fake.write_text(json.dumps(ANCHOR), encoding="utf-8")
    assert engine._load_anchor() == (None, "TRUST_ANCHOR_MISSING")


def test_gv2_anchor_004_explicit_source_is_required(trusted: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOVERNANCE_TRUST_ANCHOR_SOURCE", raising=False)
    context = engine.generate_context(ROOT)
    result = engine.verify_context(ROOT, context, profile_id="read-only")
    assert result["decision"] == "HOLD"
    assert "TRUST_ANCHOR_SOURCE_UNSPECIFIED" in result["blockers"]


def test_gv2_anchor_005_dual_source_is_hard_stop(
    trusted: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    anchor_path = tmp_path / "ShopeeGovernance" / "trust" / "1296080967.json"
    anchor_path.parent.mkdir(parents=True)
    anchor_path.write_text(json.dumps(ANCHOR), encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with pytest.raises(engine.GovernanceError) as error:
        engine._load_anchor()
    assert error.value.reason_code == "TRUST_ANCHOR_SOURCE_CONFLICT"


@pytest.mark.parametrize("raw_anchor", ["not-json", "null", "NaN"])
def test_gv2_anchor_invalid_content_is_hard_stop(
    trusted: None, monkeypatch: pytest.MonkeyPatch, raw_anchor: str
) -> None:
    monkeypatch.setenv("GOVERNANCE_TRUST_ANCHOR_JSON", raw_anchor)
    with pytest.raises(engine.GovernanceError) as error:
        engine._load_anchor()
    assert error.value.reason_code == "TRUST_ANCHOR_INVALID"


def test_gv2_anchor_006_source_and_digest_are_recorded(trusted: None) -> None:
    context = engine.generate_context(ROOT)
    record = next(item for item in context["observations"]["records"] if item["id"] == "trust-anchor")
    assert record["value"] == {
        "source_method": "ci-env-json",
        "canonical_sha256": engine.sha256_bytes(engine.canonical_bytes(ANCHOR)),
    }


def test_gv2_verification_schema_allows_pre_migration_formal_writer(trusted: None) -> None:
    context = engine.generate_context(ROOT)
    verification = engine.verify_context(ROOT, context, profile_id="read-only")
    assert verification["verification_mode"] == "fresh"
    legacy_formal_result = dict(verification)
    legacy_formal_result.pop("verification_mode")
    engine._schema_validate(
        legacy_formal_result,
        engine.load_bundle(ROOT).schemas["schemas/verification.schema.json"],
        "verification",
    )


def test_gv2_anchor_007_current_digest_change_holds(
    trusted: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = engine.generate_context(ROOT)
    changed_anchor = dict(ANCHOR, owner_actor_id="different-owner")
    monkeypatch.setenv("GOVERNANCE_TRUST_ANCHOR_JSON", json.dumps(changed_anchor))
    result = engine.verify_context(ROOT, context, profile_id="read-only")
    assert result["decision"] == "HOLD"
    assert "TRUST_ANCHOR_DIGEST_CHANGED" in result["blockers"]


def test_gv2_old_snapshot_holds_when_current_anchor_source_disappears(
    trusted: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = engine.generate_context(ROOT)
    monkeypatch.delenv("GOVERNANCE_TRUST_ANCHOR_JSON", raising=False)
    result = engine.verify_context(ROOT, context, profile_id="read-only")
    assert result["verification_mode"] == "fresh"
    assert result["decision"] == "HOLD"
    assert "TRUST_ANCHOR_SELECTED_SOURCE_MISSING" in result["blockers"]


@pytest.mark.parametrize("revision", ["HEAD", "HEAD^{tree}"])
def test_gv2_fresh_001_head_or_tree_change_holds(
    trusted: None, monkeypatch: pytest.MonkeyPatch, revision: str
) -> None:
    context = engine.generate_context(ROOT)
    original = engine._run_git

    def changed_head(repository: Path, args: list[str], **kwargs: object) -> str | None:
        if args == ["rev-parse", revision]:
            return "f" * 40
        return original(repository, args, **kwargs)

    monkeypatch.setattr(engine, "_run_git", changed_head)
    result = engine.verify_context(ROOT, context, profile_id="read-only")
    assert result["decision"] == "HOLD"
    assert ("GIT_HEAD_CHANGED" if revision == "HEAD" else "GIT_TREE_CHANGED") in result["blockers"]


def test_gv2_fresh_002_worktree_change_holds(trusted: None, monkeypatch: pytest.MonkeyPatch) -> None:
    context = engine.generate_context(ROOT)
    monkeypatch.setattr(
        engine,
        "_working_tree_binding",
        lambda _repository: {"tracked_diff_sha256": "f" * 64, "has_untracked_files": False},
    )
    result = engine.verify_context(ROOT, context, profile_id="read-only")
    assert result["decision"] == "HOLD"
    assert "WORKING_TREE_CHANGED" in result["blockers"]


def test_gv2_worktree_binding_detects_untracked_dependency_checkout(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.name", "Governance Test")
    git(repository, "config", "user.email", "governance@example.invalid")
    shutil.copyfile(ROOT / ".gitignore", repository / ".gitignore")
    git(repository, "add", ".gitignore")
    git(repository, "commit", "-m", "fixture")
    assert engine._working_tree_binding(repository)["has_untracked_files"] is False

    dependency = repository / ".ci" / "dependency"
    dependency.mkdir(parents=True)
    git(dependency, "init", "-b", "main")
    git(dependency, "config", "user.name", "Governance Test")
    git(dependency, "config", "user.email", "governance@example.invalid")
    (dependency / "fixture.txt").write_text("synthetic dependency", encoding="utf-8")
    git(dependency, "add", "fixture.txt")
    git(dependency, "commit", "-m", "dependency fixture")
    assert engine._working_tree_binding(repository)["has_untracked_files"] is True

    ignored_parent = repository / "work" / "ci"
    ignored_parent.mkdir(parents=True)
    dependency.rename(ignored_parent / "dependency")
    assert engine._working_tree_binding(repository)["has_untracked_files"] is False


def test_gv2_fresh_003_config_hash_change_holds(trusted: None) -> None:
    context = engine.generate_context(ROOT)
    context = copy.deepcopy(context)
    context["canonical"]["config_hashes"]["changed"] = "f" * 64
    context["canonical_sha256"] = engine.sha256_bytes(engine.canonical_bytes(context["canonical"]))
    result = engine.verify_context(ROOT, context, profile_id="read-only")
    assert result["decision"] == "HOLD"
    assert "GOVERNANCE_CONFIG_CHANGED" in result["blockers"]


def test_gv2_fresh_004_task_context_current_content_required(
    trusted: None, tmp_path: Path
) -> None:
    path = tmp_path / "task-context.json"
    task = task_context()
    path.write_text(json.dumps(task), encoding="utf-8")
    context = engine.generate_context(ROOT, task_context_path=path)
    task["lifecycle"] = "CLOSED"
    path.write_text(json.dumps(task), encoding="utf-8")
    result = engine.verify_context(
        ROOT, context, profile_id="local-validation", task_context_path=path
    )
    assert result["decision"] == "HOLD"
    assert "TASK_CONTEXT_CHANGED" in result["blockers"]


def test_gv2_fresh_005_task_context_path_is_required_for_task_snapshot(
    trusted: None, tmp_path: Path
) -> None:
    path = tmp_path / "task-context.json"
    path.write_text(json.dumps(task_context()), encoding="utf-8")
    context = engine.generate_context(ROOT, task_context_path=path)
    result = engine.verify_context(ROOT, context, profile_id="read-only")
    assert result["decision"] == "HOLD"
    assert "TASK_CONTEXT_CURRENT_BINDING_REQUIRED" in result["blockers"]


def test_gv2_anchor_008_explicit_local_file_source_is_used(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    anchor_path = tmp_path / "ShopeeGovernance" / "trust" / "1296080967.json"
    anchor_path.parent.mkdir(parents=True)
    anchor_path.write_text(json.dumps(ANCHOR), encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("GOVERNANCE_TRUST_ANCHOR_SOURCE", "local-file")
    monkeypatch.delenv("GOVERNANCE_TRUST_ANCHOR_JSON", raising=False)
    anchor, reason = engine._load_anchor()
    assert anchor == ANCHOR
    assert reason == "TRUST_ANCHOR_LOADED"


def test_gv2_anchor_009_appdata_is_not_a_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    anchor_path = tmp_path / "ShopeeGovernance" / "trust" / "1296080967.json"
    anchor_path.parent.mkdir(parents=True)
    anchor_path.write_text(json.dumps(ANCHOR), encoding="utf-8")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("GOVERNANCE_TRUST_ANCHOR_SOURCE", "local-file")
    monkeypatch.delenv("GOVERNANCE_TRUST_ANCHOR_JSON", raising=False)
    anchor, reason = engine._load_anchor()
    assert anchor is None
    assert reason == "TRUST_ANCHOR_SELECTED_SOURCE_MISSING"


def test_gv2_anchor_003_remote_mismatch_hard_stop(trusted: None, monkeypatch: pytest.MonkeyPatch) -> None:
    context = engine.generate_context(ROOT)
    context = copy.deepcopy(context)
    for record in context["observations"]["records"]:
        if record["id"] == "repository-remote":
            record.update(observation="FAIL", reason_code="REPOSITORY_IDENTITY_MISMATCH", value=None)
    result = engine.verify_context(ROOT, context, profile_id="read-only")
    assert result["decision"] == "HARD_STOP"


def test_gv2_provider_001_absent_read_only_continues(trusted: None) -> None:
    context = engine.generate_context(ROOT)
    assert engine.verify_context(ROOT, context, profile_id="read-only")["decision"] == "CONTINUE"


def test_gv2_provider_002_absent_formal_holds(trusted: None) -> None:
    context = engine.generate_context(ROOT)
    result = engine.verify_context(ROOT, context, profile_id="formal-acceptance")
    assert result["decision"] == "HOLD"
    assert "PROVIDER_REPOSITORY_ID_REQUIRED" in result["blockers"]


def test_gv2_canonical_001_clock_is_volatile_only(trusted: None) -> None:
    one = engine.generate_context(ROOT, clock=datetime(2026, 1, 1, tzinfo=UTC))
    two = engine.generate_context(ROOT, clock=datetime(2026, 1, 2, tzinfo=UTC))
    assert engine.canonical_bytes(one["canonical"]) == engine.canonical_bytes(two["canonical"])
    assert one["canonical_sha256"] == two["canonical_sha256"]
    assert one["observations"]["volatile"] != two["observations"]["volatile"]


@pytest.mark.parametrize("unsafe", [r"C:\\Users\\alice\\secret.txt", "/home/alice/secret.txt", "file:///tmp/secret", "https://user:token@example.invalid/a"])
def test_gv2_share_001_rejects_private_output(unsafe: str) -> None:
    with pytest.raises(engine.GovernanceError):
        engine._assert_shareable({"value": unsafe})


def test_gv2_config_002_corruption_is_hard_stop(tmp_path: Path) -> None:
    checkout = tmp_path / "repo"
    (checkout / "governance").mkdir(parents=True)
    shutil.copytree(ROOT / "governance", checkout / "governance", dirs_exist_ok=True)
    (checkout / "governance" / "ownership.json").write_text("{}", encoding="utf-8")
    with pytest.raises(engine.GovernanceError) as error:
        engine.load_bundle(checkout)
    assert error.value.reason_code == "CONFIG_HASH_MISMATCH"


def make_evidence(
    bundle: engine.GovernanceBundle,
    context: dict[str, object],
    check_id: str,
    *,
    profile_id: str = "local-validation",
    tested_commit: str | None = None,
) -> dict[str, object]:
    check = next(item for item in bundle.gates["checks"] if item["id"] == check_id)
    profile = next(item for item in bundle.profiles["profiles"] if item["id"] == profile_id)
    return {
        "evidence_id": f"evidence-{check_id}", "schema_version": "2.0.0", "kind": "TEST",
        "repository_id": "1296080967", "object_format": "sha1",
        "tested_commit": tested_commit or context["observations"]["git_identity"]["head"],
        "tested_tree": context["observations"]["git_identity"]["tree"], "base_commit": None, "merge_base": None,
        "capability_ids": [], "component_ids": context["canonical"]["components"], "component_manifest": None,
        "state_schema_hash": context["canonical"]["config_hashes"]["schemas/state.schema.json"],
        "config_version": "2.0.0", "registry_hash": engine.sha256_bytes(engine.canonical_bytes(context["canonical"]["config_hashes"])),
        "gate_id": check_id, "gate_definition_hash": engine.sha256_bytes(engine.canonical_bytes(check)),
        "profile_hash": engine.sha256_bytes(engine.canonical_bytes(profile)),
        "test_plan_hash": engine.sha256_bytes(engine.canonical_bytes({"test_plan_id": check["test_plan_id"]})),
        "test_source_hash": "source", "fixture_hash": "fixture", "environment": {"os": "test"},
        "runner_version": "test", "observation": "PASS", "reason_codes": ["TEST_PASS"],
        "report_sha256": None, "provenance": "LOCAL", "executed_at": "2000-01-01T00:00:00Z",
        "external_validity": None, "source": {"type": "pytest"},
    }


def ci_environment(monkeypatch: pytest.MonkeyPatch, gate_id: str) -> None:
    bundle = engine.load_bundle(ROOT)
    check = next(item for item in bundle.gates["checks"] if item["id"] == gate_id)
    head = git(ROOT, "rev-parse", "HEAD")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY_ID", "1296080967")
    monkeypatch.setenv("GOVERNANCE_EVIDENCE_SHA", head)
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", f"owner/repo/{check['ci_identity']['workflow_path']}@refs/pull/74/head")
    monkeypatch.setenv("GITHUB_JOB", check["ci_identity"]["job_id"])
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("GITHUB_ACTOR_ID", "207869136")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("RUNNER_OS", "Windows")


def test_gv2_ci_evidence_001_generates_schema_valid_bound_record(
    trusted: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    ci_environment(monkeypatch, "governance.validate")
    digest, record = engine.generate_ci_evidence(ROOT, "governance.validate")
    assert digest == engine.evidence_digest(record)
    assert record["provenance"] == "CI"
    assert record["observation"] == "PASS"
    assert record["source"]["result"] == "SUCCESS"
    engine._schema_validate(record, engine.load_bundle(ROOT).schemas["schemas/evidence.schema.json"], "evidence")


@pytest.mark.parametrize("field", ["tested_commit", "tested_tree", "gate_definition_hash", "profile_hash"])
def test_gv2_ci_evidence_002_binding_mismatch_is_unknown(
    trusted: None, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    ci_environment(monkeypatch, "governance.validate")
    _, record = engine.generate_ci_evidence(ROOT, "governance.validate")
    record[field] = "0" * 40 if field in {"tested_commit", "tested_tree"} else "0" * 64
    context = engine.generate_context(ROOT)
    check = engine.load_bundle(ROOT).gates["checks"][0]
    observation, _, reason = engine._evidence_for_check(
        engine.load_bundle(ROOT), check, [record], context, "formal-acceptance"
    )
    assert (observation, reason) == ("UNKNOWN", "STALE_BINDING")


def test_gv2_ci_evidence_003_fabricated_ci_pass_is_rejected(trusted: None) -> None:
    context = engine.generate_context(ROOT)
    bundle = engine.load_bundle(ROOT)
    record = make_evidence(bundle, context, "governance.validate", profile_id="formal-acceptance")
    record["provenance"] = "CI"
    record["source"] = {"type": "forged", "result": "SUCCESS"}
    observation, _, reason = engine._evidence_for_check(
        bundle, bundle.gates["checks"][0], [record], context, "formal-acceptance"
    )
    assert (observation, reason) == ("UNKNOWN", "STALE_BINDING")


def test_gv2_ci_evidence_004_missing_actions_environment_is_rejected(
    trusted: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(engine.GovernanceError) as error:
        engine.generate_ci_evidence(ROOT, "governance.validate")
    assert error.value.reason_code == "CI_EVIDENCE_ENVIRONMENT_REQUIRED"


def test_gv2_evidence_001_old_date_binding_match_reuses(trusted: None) -> None:
    context = engine.generate_context(ROOT)
    bundle = engine.load_bundle(ROOT)
    evidence = make_evidence(bundle, context, "governance.validate")
    observation, ids, reason = engine._evidence_for_check(bundle, bundle.gates["checks"][0], [evidence], context, "local-validation")
    assert (observation, reason) == ("PASS", "EVIDENCE_BOUND")
    assert ids == [evidence["evidence_id"]]


def test_gv2_evidence_002_new_date_wrong_head_is_stale(trusted: None) -> None:
    context = engine.generate_context(ROOT)
    bundle = engine.load_bundle(ROOT)
    evidence = make_evidence(bundle, context, "governance.validate", tested_commit="0" * 40)
    evidence["executed_at"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    observation, _, reason = engine._evidence_for_check(bundle, bundle.gates["checks"][0], [evidence], context, "local-validation")
    assert (observation, reason) == ("UNKNOWN", "STALE_BINDING")


def test_gv2_evidence_003_content_address_detects_spoof(tmp_path: Path) -> None:
    bundle = engine.load_bundle(ROOT)
    record = {"not": "valid"}
    path = tmp_path / ("0" * 64 + ".json")
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(engine.GovernanceError):
        engine.load_evidence(bundle, [path])


def formal_context(tmp_path: Path, provider: dict[str, object]) -> dict[str, object]:
    path = tmp_path / "task-context.json"
    path.write_text(json.dumps(task_context()), encoding="utf-8")
    return engine.generate_context(ROOT, provider=provider, task_context_path=path)


def formal_evidence(bundle: engine.GovernanceBundle, context: dict[str, object]) -> list[dict[str, object]]:
    return [
        make_evidence(bundle, context, check["id"], profile_id="formal-acceptance")
        for check in engine._required_checks(bundle, context, "formal-acceptance")
    ]


@pytest.mark.parametrize(
    "branch_protection_checks",
    [None, {}, {"fabricated-check": "SUCCESS"}],
    ids=["absent", "empty", "fabricated-success"],
)
def test_gv2_ci_001_governance_checks_are_independent_of_branch_protection(
    trusted: None, tmp_path: Path, branch_protection_checks: dict[str, str] | None
) -> None:
    provider: dict[str, object] = {"repository_id": "1296080967"}
    if branch_protection_checks is not None:
        provider["branch_protection_checks"] = branch_protection_checks
    context = formal_context(tmp_path, provider)
    result = engine.verify_context(
        ROOT, context, profile_id="formal-acceptance", provider=provider,
        task_context_path=tmp_path / "task-context.json",
    )
    assert result["decision"] == "HOLD"
    assert "EVIDENCE_MISSING" in result["blockers"]
    assert "BRANCH_PROTECTION_UNKNOWN" not in result["blockers"]
    assert "BRANCH_PROTECTION_NOT_SATISFIED" not in result["blockers"]


def test_gv2_ci_002_formal_mandatory_evidence_failure_is_hard_stop(
    trusted: None, tmp_path: Path
) -> None:
    provider = {"repository_id": "1296080967"}
    context = formal_context(tmp_path, provider)
    bundle = engine.load_bundle(ROOT)
    evidence = make_evidence(bundle, context, "governance.validate", profile_id="formal-acceptance")
    evidence["observation"] = "FAIL"
    result = engine.verify_context(
        ROOT, context, profile_id="formal-acceptance", provider=provider, evidence=[evidence],
        task_context_path=tmp_path / "task-context.json",
    )
    assert result["decision"] == "HARD_STOP"
    assert "EVIDENCE_FAILURE" in result["blockers"]
    assert "BRANCH_PROTECTION_NOT_SATISFIED" not in result["blockers"]


def test_gv2_ci_003_owner_acceptance_remains_required_after_technical_readiness(
    trusted: None, tmp_path: Path
) -> None:
    provider = {"repository_id": "1296080967"}
    context = formal_context(tmp_path, provider)
    result = engine.verify_context(
        ROOT,
        context,
        profile_id="formal-acceptance",
        provider=provider,
        evidence=formal_evidence(engine.load_bundle(ROOT), context),
        task_context_path=tmp_path / "task-context.json",
    )
    assert result["decision"] == "HOLD"
    assert result["owner_acceptance_ready"] is True
    assert "OWNER_ACCEPTANCE_REQUIRED" in result["blockers"]
    assert all(requirement["observation"] == "PASS" for requirement in result["requirements"])


def test_gv2_provider_003_repository_identity_mismatch_is_hard_stop(
    trusted: None, tmp_path: Path
) -> None:
    provider = {"repository_id": "different-repository"}
    context = formal_context(tmp_path, provider)
    result = engine.verify_context(
        ROOT, context, profile_id="formal-acceptance", provider=provider,
        task_context_path=tmp_path / "task-context.json",
    )
    assert result["decision"] == "HARD_STOP"
    assert "REPOSITORY_IDENTITY_MISMATCH" in result["blockers"]


def test_gv2_owner_001_summary_requires_technical_readiness() -> None:
    with pytest.raises(engine.GovernanceError) as error:
        engine.build_owner_acceptance_summary({"decision": "HOLD", "owner_acceptance_ready": False}, {})
    assert error.value.exit_code == engine.EXIT_HOLD


def test_gv2_owner_002_summary_binding_changes_with_business_content() -> None:
    verification = {"verification_mode": "fresh", "decision": "CONTINUE", "owner_acceptance_ready": True, "verification_input_hash": "a" * 64}
    sections = {key: "事業向け説明" for key in ["acceptance_target", "change_scope", "non_targets", "existing_operations_impact", "major_risks", "verified_evidence", "known_limits", "meaning_after_acceptance", "rollback"]}
    first = engine.build_owner_acceptance_summary(verification, sections)
    sections["change_scope"] = "変更された説明"
    second = engine.build_owner_acceptance_summary(verification, sections)
    assert first["summary_binding"] != second["summary_binding"]


def test_gv2_git_001_fresh_clone_detached_head_no_local_main(trusted: None, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copytree(ROOT / "governance", source / "governance")
    git(source, "init", "-b", "main")
    git(source, "config", "user.name", "Governance Test")
    git(source, "config", "user.email", "governance@example.invalid")
    git(source, "add", "governance")
    git(source, "commit", "-m", "fixture")
    bare = tmp_path / "remote.git"
    git(tmp_path, "clone", "--bare", str(source), str(bare))
    clone = tmp_path / "clone"
    git(tmp_path, "clone", str(bare), str(clone))
    git(clone, "remote", "set-url", "origin", "https://github.com/hagiwara777/shopee-expansion-tool.git")
    head = git(clone, "rev-parse", "HEAD")
    git(clone, "checkout", "--detach", head)
    git(clone, "branch", "-D", "main")
    context = engine.generate_context(clone, base=head)
    assert context["observations"]["git_identity"]["branch"] is None
    assert engine.verify_context(clone, context, profile_id="read-only")["decision"] == "CONTINUE"


def test_gv2_rollback_001_target_is_pre_v2_formal_main() -> None:
    assert engine.load_bundle(ROOT).state["rollback_target"] == "136958a1bf2493983b4413f7d231ee5adbd913bf"

def test_gv2_baseline_001_mandatory_gate_deletion_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = engine.load_bundle(ROOT)
    baseline_gates = copy.deepcopy(bundle.gates)
    baseline_capabilities = copy.deepcopy(bundle.capabilities)

    def baseline(_root: Path, _ref: str, relative: str) -> dict[str, object] | None:
        if relative.endswith("gates.json"):
            return baseline_gates
        if relative.endswith("capabilities.json"):
            return baseline_capabilities
        return None

    monkeypatch.setattr(engine, "_git_json_at_ref", baseline)
    weakened = copy.deepcopy(bundle.gates)
    weakened["gates"] = [item for item in weakened["gates"] if item["id"] != "protected.sg"]
    with pytest.raises(engine.GovernanceError) as error:
        engine._enforce_baseline_policy(ROOT, weakened, bundle.capabilities)
    assert error.value.reason_code == "BASELINE_MANDATORY_GATE_REMOVED"


def test_gv2_task_003_required_profile_without_context_holds(trusted: None) -> None:
    context = engine.generate_context(ROOT)
    result = engine.verify_context(ROOT, context, profile_id="local-validation")
    assert result["decision"] == "HOLD"
    assert "TASK_CONTEXT_REQUIRED" in result["blockers"]


def test_gv2_git_002_porcelain_first_path_is_not_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        engine,
        "_run_git",
        lambda *_args, **_kwargs: " M AGENTS.md\n?? governance/state.json",
    )
    changes = engine._parse_status(ROOT, None, "head")
    assert changes[1]["new_path"] == "governance/state.json"
    assert changes[0]["new_path"] == "AGENTS.md"

def test_gv2_owner_003_github_owner_evidence_exact_binding() -> None:
    record = {
        "kind": "OWNER_ACCEPTANCE",
        "provenance": "GITHUB_OWNER",
        "observation": "PASS",
        "source": {
            "actor_id": "207869136",
            "verification_input_hash": "a" * 64,
            "summary_binding": "b" * 64,
        },
    }
    # A self-authored JSON record with the old fields has no trusted provider signature.
    anchor = dict(ANCHOR, anchor_version="1.1.0", owner_evidence_public_key=base64.b64encode(b"x" * 32).decode())
    assert engine._owner_evidence_matches([record], "a" * 64, anchor, "b" * 64, "d" * 40, 95) == (
        False,
        "OWNER_ACCEPTANCE_BINDING_MISMATCH",
    )


def _owner_comment_case():
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    anchor = dict(ANCHOR, anchor_version="1.1.0", owner_evidence_public_key=base64.b64encode(public).decode())
    head = "d" * 40
    verification_hash = "a" * 64
    sections = {key: "SG source identity docs-only" for key in (
        "acceptance_target", "change_scope", "non_targets", "existing_operations_impact",
        "major_risks", "verified_evidence", "known_limits", "meaning_after_acceptance", "rollback",
    )}
    binding = engine.sha256_bytes(engine.canonical_bytes({
        "verification_input_hash": verification_hash, "sections": sections,
    }))
    context = {"canonical": {"task": {"subject": {"type": "PR", "number": 95}}},
               "observations": {"git_identity": {"head": head}}}
    verification = {
        "verification_mode": "fresh",
        "verification_input_hash": verification_hash,
        "owner_acceptance_ready": True,
    }
    summary = {"schema_version": "2.0.0", "summary_binding": binding, "sections": sections}
    repository = {"id": 1296080967, "full_name": ANCHOR["repository_full_name"]}
    pull = {"number": 95, "head": {"sha": head}, "base": {"repo": {"id": 1296080967}}}
    body = ("OWNER_ACCEPTANCE: APPROVED\nPR: #95\nHEAD: " + head +
            "\nVERIFICATION_INPUT_HASH: " + verification_hash +
            "\nSUMMARY_BINDING: " + binding + "\nSCOPE: SG source identity docs-only")
    comments = [{"id": 77, "user": {"id": 207869136}, "body": body,
                 "created_at": "2026-09-27T12:00:00Z", "updated_at": "2026-09-27T12:00:00Z"}]
    now = datetime(2026, 9, 27, 12, 1, tzinfo=UTC)
    return key, anchor, context, verification, summary, repository, pull, comments, now


def _owner_provider_main_inputs(tmp_path: Path, case):
    _key, anchor, context, verification, summary, repository, pull, comments, _now = case
    paths = {}
    for name, value in (("context", context), ("verification", verification), ("summary", summary)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[name] = str(path)
    argv = ["owner-comment-provider"]
    for name in ("context", "verification", "summary"):
        argv.extend((f"--{name}", paths[name]))
    argv.extend(("--output-dir", str(tmp_path / "owner-evidence")))
    return anchor, repository, pull, comments, argv


def _owner_key_env_value(key: Ed25519PrivateKey) -> str:
    raw = key.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption(),
    )
    return base64.b64encode(raw).decode("ascii")


def test_owner_provider_gh_environment_filters_key_even_if_provider_env_has_it(monkeypatch) -> None:
    synthetic_key = "synthetic-signing-key-value"
    monkeypatch.setenv(owner_comment_provider.PRIVATE_KEY_ENV, synthetic_key)
    observed = {}

    def fake_run(args, **kwargs):
        assert args == ["gh", "api", "repos/example/repository"]
        observed.update(kwargs["env"])
        return subprocess.CompletedProcess(args, 0, stdout="{}", stderr="")

    monkeypatch.setattr(owner_comment_provider.subprocess, "run", fake_run)
    assert owner_comment_provider._github_api("repos/example/repository") == {}
    assert owner_comment_provider.PRIVATE_KEY_ENV not in observed
    assert os.environ[owner_comment_provider.PRIVATE_KEY_ENV] == synthetic_key


def test_owner_provider_removes_signing_key_and_excludes_it_from_gh(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(owner_comment_provider, "_require_formal_main_activation", lambda _root: None)
    case = _owner_comment_case()
    key, anchor, _context, verification, summary, repository, pull, comments, _now = case
    anchor, repository, pull, comments, argv = _owner_provider_main_inputs(tmp_path, case)
    encoded_key = _owner_key_env_value(key)
    monkeypatch.setenv(owner_comment_provider.PRIVATE_KEY_ENV, encoded_key)
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(engine, "_load_anchor", lambda: (anchor, "synthetic-anchor"))
    responses = iter((repository, pull, comments))
    child_environments = []
    real_run = subprocess.run

    def fake_run(args, **kwargs):
        if args[:2] != ["gh", "api"]:
            return real_run(args, **kwargs)
        assert args[:2] == ["gh", "api"]
        child_env = kwargs["env"]
        assert owner_comment_provider.PRIVATE_KEY_ENV not in child_env
        child_environments.append(child_env)
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(next(responses)), stderr="")

    monkeypatch.setattr(owner_comment_provider.subprocess, "run", fake_run)
    assert owner_comment_provider.main() == engine.EXIT_CONTINUE
    assert owner_comment_provider.PRIVATE_KEY_ENV not in os.environ
    assert len(child_environments) == 3
    captured = capsys.readouterr()
    assert encoded_key not in captured.out + captured.err
    records = [json.loads(path.read_text(encoding="utf-8"))
               for path in (tmp_path / "owner-evidence").glob("*.json")]
    assert len(records) == 1
    assert engine._owner_evidence_matches(
        records, verification["verification_input_hash"], anchor, summary["summary_binding"],
        "d" * 40, 95, datetime.now(UTC),
    ) == (True, "OWNER_ACCEPTANCE_BOUND")


@pytest.mark.parametrize("key_kind", ["invalid", "mismatch"])
def test_owner_provider_removes_key_and_holds_for_invalid_or_mismatched_key(
    tmp_path, monkeypatch, capsys, key_kind: str,
) -> None:
    monkeypatch.setattr(owner_comment_provider, "_require_formal_main_activation", lambda _root: None)
    case = _owner_comment_case()
    key, anchor, _context, _verification, _summary, _repository, _pull, _comments, _now = case
    anchor, _repository, _pull, _comments, argv = _owner_provider_main_inputs(tmp_path, case)
    encoded_key = "not-base64" if key_kind == "invalid" else _owner_key_env_value(key)
    if key_kind == "mismatch":
        anchor["owner_evidence_public_key"] = base64.b64encode(b"x" * 32).decode("ascii")
    monkeypatch.setenv(owner_comment_provider.PRIVATE_KEY_ENV, encoded_key)
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(engine, "_load_anchor", lambda: (anchor, "synthetic-anchor"))
    monkeypatch.setattr(
        owner_comment_provider.subprocess, "run",
        lambda *_args, **_kwargs: pytest.fail("GitHub must not be queried for an invalid signing key"),
    )
    assert owner_comment_provider.main() == engine.EXIT_HOLD
    assert owner_comment_provider.PRIVATE_KEY_ENV not in os.environ
    captured = capsys.readouterr()
    expected = "OWNER_PROVIDER_KEY_REQUIRED" if key_kind == "invalid" else "OWNER_PROVIDER_KEY_MISMATCH"
    assert expected in captured.err
    assert encoded_key not in captured.out + captured.err
    assert not (tmp_path / "owner-evidence").exists()


def test_owner_provider_api_failure_holds_without_leaking_signing_key(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(owner_comment_provider, "_require_formal_main_activation", lambda _root: None)
    case = _owner_comment_case()
    key, anchor, *_rest = case
    anchor, _repository, _pull, _comments, argv = _owner_provider_main_inputs(tmp_path, case)
    encoded_key = _owner_key_env_value(key)
    monkeypatch.setenv(owner_comment_provider.PRIVATE_KEY_ENV, encoded_key)
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(engine, "_load_anchor", lambda: (anchor, "synthetic-anchor"))

    def fail_api(args, **kwargs):
        assert owner_comment_provider.PRIVATE_KEY_ENV not in kwargs["env"]
        return subprocess.CompletedProcess(args, 1, stdout="", stderr=encoded_key)

    monkeypatch.setattr(owner_comment_provider.subprocess, "run", fail_api)
    assert owner_comment_provider.main() == engine.EXIT_HOLD
    assert owner_comment_provider.PRIVATE_KEY_ENV not in os.environ
    captured = capsys.readouterr()
    assert "GITHUB_OWNER_PROVIDER_UNAVAILABLE" in captured.err
    assert encoded_key not in captured.out + captured.err
    assert not (tmp_path / "owner-evidence").exists()


def test_owner_provider_github_spawn_error_is_safe_hold(monkeypatch) -> None:
    def fail_spawn(*_args, **_kwargs):
        raise OSError("synthetic spawn failure")

    monkeypatch.setattr(owner_comment_provider.subprocess, "run", fail_spawn)
    with pytest.raises(engine.GovernanceError) as exc:
        owner_comment_provider._github_api("repos/example/repository")
    assert exc.value.reason_code == "GITHUB_OWNER_PROVIDER_UNAVAILABLE"


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["LF", "CRLF"])
def test_gv2_owner_comment_provider_and_offline_verifier(newline: str) -> None:
    key, anchor, context, verification, summary, repository, pull, comments, now = _owner_comment_case()
    comments[0]["body"] = comments[0]["body"].replace("\n", newline)
    record = owner_comment_provider.build_evidence(context, verification, summary, anchor,
                                                    repository, pull, comments, key, observed_at=now)
    assert record["source"]["receipt"]["comment_body_sha256"] == engine.sha256_bytes(
        comments[0]["body"].encode("utf-8")
    )
    expected = (True, "OWNER_ACCEPTANCE_BOUND")
    assert engine._owner_evidence_matches([record], verification["verification_input_hash"],
                                          anchor, summary["summary_binding"], "d" * 40, 95, now) == expected
    assert engine._owner_evidence_matches([record], "b" * 64, anchor, summary["summary_binding"],
                                          "d" * 40, 95, now)[0] is False
    assert engine._owner_evidence_matches([record], verification["verification_input_hash"],
                                          anchor, "b" * 64, "d" * 40, 95, now)[0] is False
    assert engine._owner_evidence_matches([record], verification["verification_input_hash"],
                                          anchor, summary["summary_binding"], "e" * 40, 95, now)[0] is False
    assert engine._owner_evidence_matches([record], verification["verification_input_hash"],
                                          anchor, summary["summary_binding"], "d" * 40, 96, now)[0] is False
    assert engine._owner_evidence_matches([record], verification["verification_input_hash"],
                                          anchor, summary["summary_binding"], "d" * 40, 95,
                                          now + timedelta(minutes=6))[0] is False
    forged = copy.deepcopy(record)
    forged["source"]["receipt"]["scope"] = "wider approval"
    assert engine._owner_evidence_matches([forged], verification["verification_input_hash"],
                                          anchor, summary["summary_binding"], "d" * 40, 95, now)[0] is False
    forged_mirror = copy.deepcopy(record)
    forged_mirror["source"]["summary_binding"] = "b" * 64
    assert engine._owner_evidence_matches([forged_mirror], verification["verification_input_hash"],
                                          anchor, summary["summary_binding"], "d" * 40, 95, now)[0] is False


def test_gv2_owner_provider_rejects_non_fresh_verification() -> None:
    for verification in ({"verification_mode": "historical-replay"}, {}):
        with pytest.raises(engine.GovernanceError) as exc:
            owner_comment_provider.build_evidence({}, verification, {}, {}, {}, {}, [], None)
        assert exc.value.reason_code == "OWNER_VERIFICATION_NOT_FRESH"


def test_gv2_owner_provider_candidate_cannot_sign_before_formal_adoption(tmp_path: Path) -> None:
    with pytest.raises(engine.GovernanceError) as exc:
        owner_comment_provider._require_formal_main_activation(tmp_path)
    assert exc.value.reason_code == "OWNER_PROVIDER_NOT_FORMAL"


def test_gv2_owner_provider_requires_all_governance_files_to_match_formal_main(tmp_path: Path) -> None:
    root = tmp_path / "candidate"
    (root / "governance").mkdir(parents=True)
    (root / "governance" / "engine.py").write_text("formal verifier\n", encoding="utf-8")
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Governance Test")
    git(root, "config", "user.email", "governance@example.invalid")
    git(root, "add", "governance/engine.py")
    git(root, "commit", "-m", "formal verifier")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    assert owner_comment_provider._governance_matches_formal_main(root)

    (root / "governance" / "engine.py").write_text("candidate verifier\n", encoding="utf-8")
    assert not owner_comment_provider._governance_matches_formal_main(root)


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["LF", "CRLF"])
@pytest.mark.parametrize("mutation", ["repo", "pr", "head", "hash", "binding", "actor", "edit", "delete", "revoke", "scope"])
def test_gv2_owner_comment_provider_rejects_invalid_observation(mutation: str, newline: str) -> None:
    key, anchor, context, verification, summary, repository, pull, comments, now = _owner_comment_case()
    comments[0]["body"] = comments[0]["body"].replace("\n", newline)
    if mutation == "repo":
        repository["id"] += 1
    elif mutation == "pr":
        pull["number"] += 1
    elif mutation == "head":
        pull["head"]["sha"] = "e" * 40
    elif mutation == "hash":
        comments[0]["body"] = comments[0]["body"].replace("a" * 64, "b" * 64)
    elif mutation == "binding":
        comments[0]["body"] = comments[0]["body"].replace(summary["summary_binding"], "b" * 64)
    elif mutation == "actor":
        comments[0]["user"]["id"] += 1
    elif mutation == "edit":
        comments[0]["updated_at"] = "2026-09-27T12:00:01Z"
    elif mutation == "delete":
        comments.clear()
    elif mutation == "revoke":
        comments.append({"id": 78, "user": {"id": 207869136}, "body": "OWNER_ACCEPTANCE: REVOKED",
                         "created_at": "2026-09-27T12:00:01Z", "updated_at": "2026-09-27T12:00:01Z"})
    elif mutation == "scope":
        comments[0]["body"] = comments[0]["body"].replace("SCOPE: SG source identity docs-only", "SCOPE: ")
    with pytest.raises(engine.GovernanceError):
        owner_comment_provider.build_evidence(context, verification, summary, anchor,
                                              repository, pull, comments, key, observed_at=now)


@pytest.mark.parametrize("separator", ["\r", "\u2028"], ids=["bare-CR", "unicode-separator"])
def test_gv2_owner_comment_provider_rejects_other_line_separators(separator: str) -> None:
    key, anchor, context, verification, summary, repository, pull, comments, now = _owner_comment_case()
    comments[0]["body"] = comments[0]["body"].replace("\n", separator)
    with pytest.raises(engine.GovernanceError) as exc:
        owner_comment_provider.build_evidence(context, verification, summary, anchor,
                                              repository, pull, comments, key, observed_at=now)
    assert exc.value.reason_code == "OWNER_ACCEPTANCE_BINDING_MISMATCH"


def _owner_transport_case():
    _key, anchor, context, verification, summary, repository, pull, _comments, _now = _owner_comment_case()
    verification.update(profile_id="formal-acceptance", decision="HOLD", blockers=["OWNER_ACCEPTANCE_REQUIRED"])
    pull.update(state="open")
    pull["head"]["repo"] = {"id": 1296080967}
    pull["base"]["ref"] = "main"
    actor = {"id": 207869136}
    return anchor, context, verification, summary, repository, pull, actor


def test_gv2_owner_transport_formats_current_binding() -> None:
    anchor, context, verification, summary, repository, pull, actor = _owner_transport_case()
    body = owner_acceptance_transport.build_comment(
        context, verification, summary, anchor, repository, pull, actor, "SG source identity docs-only",
    )
    assert body == (
        "OWNER_ACCEPTANCE: APPROVED\nPR: #95\nHEAD: " + "d" * 40
        + "\nVERIFICATION_INPUT_HASH: " + "a" * 64
        + "\nSUMMARY_BINDING: " + summary["summary_binding"]
        + "\nSCOPE: SG source identity docs-only"
    )


@pytest.mark.parametrize("mutation", [
    "gates", "other_blocker", "historical", "legacy", "summary", "head", "repository", "actor", "scope", "base", "closed",
])
def test_gv2_owner_transport_fails_closed(mutation: str) -> None:
    anchor, context, verification, summary, repository, pull, actor = _owner_transport_case()
    scope = "SG source identity docs-only"
    if mutation == "gates":
        verification["owner_acceptance_ready"] = False
    elif mutation == "other_blocker":
        verification["blockers"].append("MANDATORY_CHECK_MISSING")
    elif mutation == "historical":
        verification["verification_mode"] = "historical-replay"
    elif mutation == "legacy":
        verification.pop("verification_mode")
    elif mutation == "summary":
        summary["sections"]["major_risks"] = "changed after approval"
    elif mutation == "head":
        pull["head"]["sha"] = "e" * 40
    elif mutation == "repository":
        repository["id"] += 1
    elif mutation == "actor":
        actor["id"] += 1
    elif mutation == "scope":
        scope = "wider\nscope"
    elif mutation == "base":
        pull["base"]["ref"] = "other"
    elif mutation == "closed":
        pull["state"] = "closed"
    with pytest.raises(engine.GovernanceError) as exc:
        owner_acceptance_transport.build_comment(
            context, verification, summary, anchor, repository, pull, actor, scope,
        )
    assert exc.value.exit_code == engine.EXIT_HOLD


def test_gv2_owner_transport_migration_pr_cannot_use_helper(tmp_path: Path) -> None:
    with pytest.raises(engine.GovernanceError) as exc:
        owner_acceptance_transport._require_formal_main_activation(tmp_path)
    assert exc.value.reason_code == "OWNER_TRANSPORT_NOT_FORMAL"


def test_gv2_owner_transport_post_reuses_only_unchanged_latest_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    body = "OWNER_ACCEPTANCE: APPROVED\nPR: #95"
    comments = [{"id": 77, "user": {"id": 207869136}, "body": body,
                 "created_at": "2026-09-27T12:00:00Z", "updated_at": "2026-09-27T12:00:00Z"}]
    monkeypatch.setattr(owner_comment_provider, "_comments", lambda *_args: comments)
    monkeypatch.setattr(owner_comment_provider, "_github_api", lambda *_args: {"id": 207869136})
    monkeypatch.setattr(owner_acceptance_transport.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("unexpected post"))
    assert owner_acceptance_transport.post_comment(body, "hagiwara777/shopee-expansion-tool", 95, "207869136") == 77
    comments[0]["updated_at"] = "2026-09-27T12:00:01Z"
    with pytest.raises(engine.GovernanceError) as exc:
        owner_acceptance_transport.post_comment(body, "hagiwara777/shopee-expansion-tool", 95, "207869136")
    assert exc.value.reason_code == "OWNER_TRANSPORT_COMMENT_EDITED"


def test_gv2_owner_transport_does_not_overwrite_latest_revocation(monkeypatch: pytest.MonkeyPatch) -> None:
    comments = [{"id": 79, "user": {"id": 207869136}, "body": "OWNER_ACCEPTANCE: REVOKED",
                 "created_at": "2026-09-27T12:01:00Z", "updated_at": "2026-09-27T12:01:00Z"}]
    monkeypatch.setattr(owner_comment_provider, "_comments", lambda *_args: comments)
    monkeypatch.setattr(owner_comment_provider, "_github_api", lambda *_args: {"id": 207869136})
    monkeypatch.setattr(
        owner_acceptance_transport.subprocess, "run",
        lambda *_args, **_kwargs: pytest.fail("revoked approval must not trigger a GitHub POST"),
    )
    with pytest.raises(engine.GovernanceError) as exc:
        owner_acceptance_transport.post_comment(
            "OWNER_ACCEPTANCE: APPROVED\nPR: #95", "hagiwara777/shopee-expansion-tool", 95, "207869136",
        )
    assert exc.value.reason_code == "OWNER_TRANSPORT_REVOKED"
    assert exc.value.exit_code == engine.EXIT_HOLD


def test_gv2_owner_transport_post_and_api_failure_hold(monkeypatch: pytest.MonkeyPatch) -> None:
    body = "OWNER_ACCEPTANCE: APPROVED\nPR: #95"
    monkeypatch.setattr(owner_comment_provider, "_comments", lambda *_args: [])
    monkeypatch.setattr(owner_comment_provider, "_github_api", lambda *_args: {"id": 207869136})
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, json.dumps({
            "id": 78, "body": body, "user": {"id": 207869136},
        }), "")

    monkeypatch.setattr(owner_acceptance_transport.subprocess, "run", fake_run)
    assert owner_acceptance_transport.post_comment(body, "hagiwara777/shopee-expansion-tool", 95, "207869136") == 78
    assert calls[0][-1] == f"body={body}"
    with pytest.raises(engine.GovernanceError) as exc:
        owner_acceptance_transport.post_comment(body, "hagiwara777/shopee-expansion-tool", 95, "other")
    assert exc.value.reason_code == "OWNER_TRANSPORT_TARGET_MISMATCH"
    monkeypatch.setattr(owner_acceptance_transport.subprocess, "run", lambda args, **_kwargs:
                        subprocess.CompletedProcess(args, 1, "", "failure"))
    with pytest.raises(engine.GovernanceError) as exc:
        owner_acceptance_transport.post_comment(body, "hagiwara777/shopee-expansion-tool", 95, "207869136")
    assert exc.value.reason_code == "OWNER_TRANSPORT_POST_FAILED"


def test_gv2_git_003_feature_branch_uses_merge_base(trusted: None, tmp_path: Path) -> None:
    source = tmp_path / "feature-repo"
    source.mkdir()
    shutil.copytree(ROOT / "governance", source / "governance")
    git(source, "init", "-b", "main")
    git(source, "config", "user.name", "Governance Test")
    git(source, "config", "user.email", "governance@example.invalid")
    git(source, "add", "governance")
    git(source, "commit", "-m", "baseline")
    base = git(source, "rev-parse", "HEAD")
    git(source, "switch", "-c", "feature/shared-change")
    (source / "modules").mkdir()
    (source / "modules" / "config.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(source, "add", "modules/config.py")
    git(source, "commit", "-m", "shared change")
    context = engine.generate_context(source, base=base)
    assert context["canonical"]["classification"] == "SHARED_CORE"
    assert context["canonical"]["protected_capabilities"] == [
        "ph.beta.operation",
        "sg.safety.baseline",
    ]


def test_gv2_evidence_004_fresh_clone_legacy_records_are_content_addressed() -> None:
    bundle = engine.load_bundle(ROOT)
    paths = sorted((ROOT / "governance" / "evidence").glob("*.json"))
    records = engine.load_evidence(bundle, paths)
    assert {record["kind"] for record in records} == {"LEGACY_ACCEPTANCE"}
    assert {record["capability_ids"][0] for record in records} == {
        "ph.beta.operation", "sg.safety.baseline"
    }

def test_gv2_evidence_005_explicit_external_expiry_uses_injected_clock(trusted: None) -> None:
    context = engine.generate_context(ROOT)
    bundle = engine.load_bundle(ROOT)
    record = make_evidence(bundle, context, "governance.validate")
    record["external_validity"] = {"not_after": "2025-01-01T00:00:00Z"}
    check = bundle.gates["checks"][0]
    result = engine._evidence_for_check(
        bundle, check, [record], context, "local-validation", datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert result[0] == "UNKNOWN"
    assert result[2] == "STALE_BINDING"


def test_gv2_override_001_exact_head_owner_binding_expires_on_change(trusted: None) -> None:
    context = engine.generate_context(ROOT)
    bundle = engine.load_bundle(ROOT)
    record = make_evidence(bundle, context, "governance.validate")
    record.update(kind="OVERRIDE", provenance="GITHUB_OWNER")
    record["source"] = {
        "authority": "repository-owner",
        "actor_id": "207869136",
        "head": context["observations"]["git_identity"]["head"],
    }
    check = bundle.gates["checks"][0]
    assert engine._evidence_for_check(bundle, check, [record], context, "local-validation")[0] == "PASS"
    stale = copy.deepcopy(record)
    stale["source"]["head"] = "0" * 40
    assert engine._evidence_for_check(bundle, check, [stale], context, "local-validation")[0] == "UNKNOWN"


@pytest.mark.parametrize("path", ["modules/sls_category_assets.py", "modules/sls_category_rules.py",
    "guardrails/sls_market_categories/markets/BR.json", "scripts/build_sls_category_assets.py",
    "tests/test_sls_category_protected.py", "tests/sls_category_support.py"])
def test_sls_category_assets_are_shared_core(path):
    bundle = engine.load_bundle(ROOT)
    classified = engine.classify_changes([change("A", new=path)], bundle.ownership)
    assert classified["classification"] == "SHARED_CORE"
    assert "safety.shared" in classified["components"]
