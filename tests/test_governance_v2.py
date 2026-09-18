from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from governance import engine


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
        "SG": {"operation": "INACTIVE", "development_policy": "PAUSED"},
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
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    context = engine.generate_context(ROOT)
    result = engine.verify_context(ROOT, context, profile_id="read-only")
    assert result["decision"] == "HOLD"
    assert "TRUST_ANCHOR_MISSING" in result["blockers"]


def test_gv2_anchor_002_repo_fake_anchor_is_not_trusted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GOVERNANCE_TRUST_ANCHOR_JSON", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "outside"))
    fake = tmp_path / "repo" / "governance" / "trust-anchor.json"
    fake.parent.mkdir(parents=True)
    fake.write_text(json.dumps(ANCHOR), encoding="utf-8")
    assert engine._load_anchor() == (None, "TRUST_ANCHOR_MISSING")


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
    result = engine.verify_context(ROOT, context, profile_id="formal-acceptance", provider=provider)
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
        ROOT, context, profile_id="formal-acceptance", provider=provider, evidence=[evidence]
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
    result = engine.verify_context(ROOT, context, profile_id="formal-acceptance", provider=provider)
    assert result["decision"] == "HARD_STOP"
    assert "REPOSITORY_IDENTITY_MISMATCH" in result["blockers"]


def test_gv2_owner_001_summary_requires_technical_readiness() -> None:
    with pytest.raises(engine.GovernanceError) as error:
        engine.build_owner_acceptance_summary({"decision": "HOLD", "owner_acceptance_ready": False}, {})
    assert error.value.exit_code == engine.EXIT_HOLD


def test_gv2_owner_002_summary_binding_changes_with_business_content() -> None:
    verification = {"decision": "CONTINUE", "owner_acceptance_ready": True, "verification_input_hash": "a" * 64}
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
    assert engine._owner_evidence_matches([record], "a" * 64, "207869136") == (
        True,
        "OWNER_ACCEPTANCE_BOUND",
    )
    assert engine._owner_evidence_matches([record], "c" * 64, "207869136") == (
        False,
        "OWNER_ACCEPTANCE_BINDING_MISMATCH",
    )


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
