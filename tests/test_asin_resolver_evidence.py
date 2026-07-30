from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from modules.asin_resolver_evidence import (
    APPROVED_FORMAL_MAIN_COMMIT_ENV,
    COMPLETED,
    INITIAL_PARSE_SAVED,
    RUNTIME_ACCEPTANCE_STATUS,
    EvidenceValidationError,
    complete_batch,
    create_evidence_batch,
    load_and_validate_batch,
    load_source_map_from_input,
    parse_source_input,
    persist_source_input_and_source_map,
    prepare_retry,
    record_initial_parse,
    record_initial_prompt,
    record_initial_response,
    record_resolver_export,
    record_retry_parse,
    record_retry_prompt,
    record_retry_response,
    restore_batch_state,
    source_map_from_tsv,
    source_map_tsv,
)
import modules.asin_resolver_evidence as evidence


FORMAL_MAIN_COMMIT = "1c5a16a843a10140c75df9214744fe1c692da101"


@pytest.fixture(autouse=True)
def _approved_formal_commit(monkeypatch):
    monkeypatch.setenv(APPROVED_FORMAL_MAIN_COMMIT_ENV, FORMAL_MAIN_COMMIT)


def _create_batch(tmp_path: Path, batch_id: str = "PH-ASIN-test-0001") -> Path:
    return create_evidence_batch(
        tmp_path / "runs",
        batch_id=batch_id,
        formal_main_commit=FORMAL_MAIN_COMMIT,
        resolver_version="0.4.3",
    )


def _initial_parse(manifest_path: Path) -> None:
    persist_source_input_and_source_map(
        manifest_path,
        "JPH-001\tOriginal one\nJPH-002\tOriginal two\n",
        search_title_builder=lambda title: f"search:{title}",
    )
    record_initial_prompt(manifest_path, "initial prompt")
    record_initial_response(manifest_path, "initial response")
    record_initial_parse(
        manifest_path,
        [{"source_id": "R0001", "status": "UNKNOWN"}],
        b"source_id,status\nR0001,UNKNOWN\n",
    )


def _rewrite_manifest(manifest_path: Path, mutate) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(manifest)
    raw = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    manifest_path.write_bytes(raw)
    manifest_path.with_name("evidence_manifest.sha256").write_text(
        f"{hashlib.sha256(raw).hexdigest()}  evidence_manifest.json\n",
        encoding="ascii",
    )


def test_two_column_and_legacy_inputs_have_deterministic_source_maps():
    tsv_entries = parse_source_input("JPH-1\tOne\r\nJPH-2\tTwo\r\n")
    legacy_entries = parse_source_input("One\n\nTwo\n")

    assert [(entry.upstream_source_id, entry.resolver_source_id) for entry in tsv_entries] == [
        ("JPH-1", "R0001"),
        ("JPH-2", "R0002"),
    ]
    assert [(entry.upstream_source_id, entry.resolver_source_id) for entry in legacy_entries] == [
        ("", "R0001"),
        ("", "R0002"),
    ]
    assert source_map_from_tsv(source_map_tsv(tsv_entries)) == tsv_entries


@pytest.mark.parametrize(
    "source_input",
    ["JPH-1\tOne\nJPH-1\tTwo\n", "JPH-1\tOne\tExtra\n"],
)
def test_source_input_rejects_duplicate_ids_and_extra_columns(source_input):
    with pytest.raises(EvidenceValidationError):
        parse_source_input(source_input)


def test_batch_requires_environment_approved_formal_main_commit(tmp_path, monkeypatch):
    with pytest.raises(EvidenceValidationError, match="allowed formal commit"):
        create_evidence_batch(
            tmp_path,
            batch_id="PH-ASIN-test-0002",
            formal_main_commit="a" * 40,
            resolver_version="0.4.3",
        )


def test_approved_formal_commit_rejects_invalid_and_mismatched_values(tmp_path, monkeypatch):
    monkeypatch.setenv(APPROVED_FORMAL_MAIN_COMMIT_ENV, "not-a-sha")
    with pytest.raises(EvidenceValidationError, match=APPROVED_FORMAL_MAIN_COMMIT_ENV):
        _create_batch(tmp_path)
    monkeypatch.setenv(APPROVED_FORMAL_MAIN_COMMIT_ENV, "b" * 40)
    with pytest.raises(EvidenceValidationError, match="does not match"):
        _create_batch(tmp_path)
    with pytest.raises(EvidenceValidationError, match="40-character SHA"):
        create_evidence_batch(
            tmp_path,
            batch_id="PH-ASIN-test-0003",
            formal_main_commit="",
            resolver_version="0.4.3",
        )
    monkeypatch.delenv(APPROVED_FORMAL_MAIN_COMMIT_ENV)
    with pytest.raises(EvidenceValidationError, match=APPROVED_FORMAL_MAIN_COMMIT_ENV):
        create_evidence_batch(
            tmp_path,
            batch_id="PH-ASIN-test-0004",
            formal_main_commit=FORMAL_MAIN_COMMIT,
            resolver_version="0.4.3",
        )


@pytest.mark.parametrize(
    "source_input",
    ["JPH-1\tOne\r\n\r\nJPH-2\tTwo\r\n", "One\r\n\r\nTwo\r\n"],
)
def test_source_input_is_saved_before_and_regenerates_the_same_source_map(tmp_path, source_input):
    manifest_path = _create_batch(tmp_path)
    entries = persist_source_input_and_source_map(
        manifest_path,
        source_input,
        search_title_builder=lambda title: f"query {title}",
    )
    manifest = load_and_validate_batch(manifest_path)
    package_dir = manifest_path.parent
    source_input_record = next(item for item in manifest["artifacts"] if item["artifact_type"] == "source_input")

    assert (package_dir / source_input_record["filename"]).read_bytes() == source_input.replace("\r\n", "\n").encode("utf-8")
    assert load_source_map_from_input(
        package_dir / source_input_record["filename"], search_title_builder=lambda title: f"query {title}"
    ) == entries
    assert manifest["last_completed_checkpoint"] == "SOURCE_MAP_SAVED"


def test_retry_free_transition_graph_and_completed_batch_is_immutable(tmp_path):
    manifest_path = _create_batch(tmp_path)
    _initial_parse(manifest_path)
    record_resolver_export(manifest_path, b"source_id,status\nR0001,FOUND\n", source_phase="initial")
    completed = complete_batch(manifest_path)

    assert completed["last_completed_checkpoint"] == COMPLETED
    assert completed["batch_status"] == "COMPLETED"
    with pytest.raises(EvidenceValidationError, match="completed batch"):
        record_initial_prompt(manifest_path, "must not write")


def test_retry_transition_graph_requires_every_retry_checkpoint(tmp_path):
    manifest_path = _create_batch(tmp_path)
    _initial_parse(manifest_path)
    prepare_retry(manifest_path, [{"source_id": "R0001", "selected": True}])
    record_retry_prompt(manifest_path, "retry prompt")
    record_retry_response(manifest_path, "retry response")
    record_retry_parse(
        manifest_path,
        [{"source_id": "R0001", "status": "FOUND"}],
        b"source_id,status\nR0001,FOUND\n",
    )
    record_resolver_export(manifest_path, b"source_id,status\nR0001,FOUND\n", source_phase="retry")
    manifest = load_and_validate_batch(manifest_path)

    assert manifest["last_completed_checkpoint"] == "EXPORT_SAVED"
    assert {item["artifact_type"] for item in manifest["artifacts"]} >= {
        "retry_selection",
        "retry_prompt",
        "retry_ai_response",
        "retry_parse_export",
        "retry_candidate_csv",
    }
    export = next(item for item in manifest["artifacts"] if item["artifact_type"] == "resolver_export")
    assert [
        next(item for item in manifest["artifacts"] if item["artifact_id"] == parent)["artifact_type"]
        for parent in export["parent_artifact_ids"]
    ] == ["initial_parse_export", "retry_parse_export"]


def test_illegal_jumps_and_retry_artifacts_without_retry_path_stop(tmp_path):
    manifest_path = _create_batch(tmp_path)
    with pytest.raises(EvidenceValidationError, match="expected checkpoint"):
        record_initial_prompt(manifest_path, "too early")

    _initial_parse(manifest_path)
    prepare_retry(manifest_path, [{"source_id": "R0001", "selected": True}])
    with pytest.raises(EvidenceValidationError, match="expected checkpoint"):
        record_resolver_export(manifest_path, b"source_id\nR0001\n", source_phase="initial")

    _rewrite_manifest(
        manifest_path,
        lambda manifest: manifest.update(
            {
                "last_completed_checkpoint": INITIAL_PARSE_SAVED,
                "resume_from_checkpoint": "RETRY_PREPARED_OR_EXPORT_SAVED",
            }
        ),
    )
    with pytest.raises(EvidenceValidationError, match="legal transition path"):
        load_and_validate_batch(manifest_path)


@pytest.mark.parametrize("field", ["acceptance_status", "producer", "storage_alias"])
def test_invalid_runtime_artifact_metadata_stops_validation(tmp_path, field):
    manifest_path = _create_batch(tmp_path)
    persist_source_input_and_source_map(manifest_path, "One\n")

    def mutate(manifest):
        artifact = manifest["artifacts"][0]
        artifact[field] = "" if field != "acceptance_status" else "UNDEFINED"

    _rewrite_manifest(manifest_path, mutate)
    with pytest.raises(EvidenceValidationError):
        load_and_validate_batch(manifest_path)


def test_sha_mismatch_stops_without_overwrite(tmp_path):
    manifest_path = _create_batch(tmp_path)
    _initial_parse(manifest_path)
    package_dir = manifest_path.parent
    candidate_path = package_dir / "initial_candidates.csv"
    candidate_path.write_bytes(b"tampered\n")
    before = manifest_path.read_bytes()
    with pytest.raises(EvidenceValidationError, match="SHA-256 mismatch"):
        load_and_validate_batch(manifest_path)
    assert manifest_path.read_bytes() == before


def test_source_map_mismatch_and_missing_parent_stop_validation(tmp_path):
    manifest_path = _create_batch(tmp_path)
    persist_source_input_and_source_map(
        manifest_path,
        "JPH-001\tOriginal one\n",
        search_title_builder=lambda title: f"search:{title}",
    )
    package_dir = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_map = next(item for item in manifest["artifacts"] if item["artifact_type"] == "source_map")
    source_map_path = package_dir / source_map["filename"]
    source_map_path.write_text(
        "upstream_source_id\tresolver_source_id\tinput_order\toriginal_title\tinitial_search_title\n"
        "JPH-001\tR0001\t1\tUnexpected title\tsearch:Unexpected title\n",
        encoding="utf-8",
        newline="\n",
    )
    source_map["sha256"] = hashlib.sha256(source_map_path.read_bytes()).hexdigest()
    _rewrite_manifest(manifest_path, lambda rewritten: rewritten.update({"artifacts": manifest["artifacts"]}))

    with pytest.raises(EvidenceValidationError, match="source_input"):
        load_and_validate_batch(manifest_path)

    parent_manifest_path = _create_batch(tmp_path, batch_id="PH-ASIN-test-0004")
    _initial_parse(parent_manifest_path)
    _rewrite_manifest(
        parent_manifest_path,
        lambda rewritten: rewritten["artifacts"][-1].update({"parent_artifact_ids": ["ART-MISSING"]}),
    )
    with pytest.raises(EvidenceValidationError, match="parent artifact"):
        load_and_validate_batch(parent_manifest_path)


def test_restore_batch_state_reconstructs_saved_inputs_and_retry_state(tmp_path):
    manifest_path = _create_batch(tmp_path)
    _initial_parse(manifest_path)
    prepare_retry(manifest_path, [{"source_id": "R0001", "selected": True}])
    record_retry_prompt(manifest_path, "retry prompt")
    state = restore_batch_state(manifest_path)

    assert state["source_entries"][0]["upstream_source_id"] == "JPH-001"
    assert state["initial_prompt"] == "initial prompt"
    assert state["retry_rows"] == [{"selected": True, "source_id": "R0001"}]
    assert state["manifest"]["artifacts"][0]["acceptance_status"] == RUNTIME_ACCEPTANCE_STATUS
    assert state["next_action"] == "enter_retry_response"


def test_every_checkpoint_restores_the_correct_next_action_and_export_rows(tmp_path):
    manifest_path = _create_batch(tmp_path)
    expected_actions = [
        ("BATCH_CREATED", "save_source_input_and_source_map"),
        ("SOURCE_MAP_SAVED", "generate_initial_prompt"),
        ("INITIAL_PROMPT_SAVED", "enter_initial_response"),
        ("INITIAL_RESPONSE_SAVED", "parse_saved_initial_response"),
        ("INITIAL_PARSE_SAVED", "prepare_retry_or_export"),
        ("RETRY_PREPARED", "generate_retry_prompt"),
        ("RETRY_PROMPT_SAVED", "enter_retry_response"),
        ("RETRY_RESPONSE_SAVED", "parse_saved_retry_response"),
        ("RETRY_PARSE_SAVED", "export"),
        ("EXPORT_SAVED", "complete_or_view"),
        ("COMPLETED", "view_only"),
    ]

    def assert_next(expected_checkpoint, expected_action):
        state = restore_batch_state(manifest_path)
        assert state["manifest"]["last_completed_checkpoint"] == expected_checkpoint
        assert state["next_action"] == expected_action
        return state

    assert_next(*expected_actions[0])
    persist_source_input_and_source_map(manifest_path, "JPH-001\tOriginal one\n")
    assert_next(*expected_actions[1])
    record_initial_prompt(manifest_path, "initial prompt")
    assert_next(*expected_actions[2])
    record_initial_response(manifest_path, "initial response")
    assert_next(*expected_actions[3])
    record_initial_parse(
        manifest_path,
        [{"source_id": "R0001", "status": "UNKNOWN"}],
        b"source_id,status\nR0001,UNKNOWN\n",
    )
    assert_next(*expected_actions[4])
    prepare_retry(manifest_path, [{"source_id": "R0001", "selected": True}])
    assert_next(*expected_actions[5])
    record_retry_prompt(manifest_path, "retry prompt")
    assert_next(*expected_actions[6])
    record_retry_response(manifest_path, "retry response")
    assert_next(*expected_actions[7])
    record_retry_parse(
        manifest_path,
        [{"source_id": "R0001", "status": "FOUND"}],
        b"source_id,status\nR0001,FOUND\n",
    )
    assert_next(*expected_actions[8])
    record_resolver_export(
        manifest_path,
        b"source_id,status,verification\nR0001,FOUND,KEEPA_VERIFIED\n",
        source_phase="retry",
    )
    export_state = assert_next(*expected_actions[9])
    assert export_state["resolver_rows"] == [
        {"source_id": "R0001", "status": "FOUND", "verification": "KEEPA_VERIFIED"}
    ]
    assert export_state["resolver_export_phase"] == "retry"
    complete_batch(manifest_path)
    assert_next(*expected_actions[10])


@pytest.mark.parametrize(
    "field,value",
    [
        ("marketplace", "SG"),
        ("module", "Wrong module"),
        ("resolver_version", ""),
        ("created_at", "2026-07-29T00:00:00"),
    ],
)
def test_manifest_schema_rejects_required_metadata_mismatches(tmp_path, field, value):
    manifest_path = _create_batch(tmp_path)
    _rewrite_manifest(manifest_path, lambda manifest: manifest.update({field: value}))
    with pytest.raises(EvidenceValidationError):
        load_and_validate_batch(manifest_path)


def test_stage_write_failure_rolls_back_new_files_and_keeps_prior_checkpoint(tmp_path, monkeypatch):
    manifest_path = _create_batch(tmp_path)
    original_write_manifest = evidence._write_manifest_atomic

    def fail_after_artifacts(*args, **kwargs):
        raise OSError("injected manifest failure")

    monkeypatch.setattr(evidence, "_write_manifest_atomic", fail_after_artifacts)
    with pytest.raises(OSError, match="injected"):
        persist_source_input_and_source_map(manifest_path, "One\n")
    monkeypatch.setattr(evidence, "_write_manifest_atomic", original_write_manifest)

    manifest = load_and_validate_batch(manifest_path)
    assert manifest["last_completed_checkpoint"] == "BATCH_CREATED"
    assert not (manifest_path.parent / "source_input.txt").exists()
    assert not (manifest_path.parent / "source_map.tsv").exists()


def test_parse_stage_write_failure_rolls_back_both_new_files(tmp_path, monkeypatch):
    manifest_path = _create_batch(tmp_path)
    persist_source_input_and_source_map(manifest_path, "One\n")
    record_initial_prompt(manifest_path, "initial prompt")
    record_initial_response(manifest_path, "initial response")
    original_write_manifest = evidence._write_manifest_atomic

    monkeypatch.setattr(
        evidence,
        "_write_manifest_atomic",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("injected parse failure")),
    )
    with pytest.raises(OSError, match="injected parse failure"):
        record_initial_parse(
            manifest_path,
            [{"source_id": "R0001", "status": "UNKNOWN"}],
            b"source_id,status\nR0001,UNKNOWN\n",
        )
    monkeypatch.setattr(evidence, "_write_manifest_atomic", original_write_manifest)

    manifest = load_and_validate_batch(manifest_path)
    assert manifest["last_completed_checkpoint"] == "INITIAL_RESPONSE_SAVED"
    assert not (manifest_path.parent / "initial_parse.json").exists()
    assert not (manifest_path.parent / "initial_candidates.csv").exists()


def test_manifest_sidecar_failure_restores_the_prior_valid_pair(tmp_path, monkeypatch):
    manifest_path = _create_batch(tmp_path)
    persist_source_input_and_source_map(manifest_path, "One\n")
    before_manifest = manifest_path.read_bytes()
    before_sidecar = manifest_path.with_name("evidence_manifest.sha256").read_bytes()
    original_replace = evidence.os.replace

    def fail_sidecar_promotion(source, target):
        if Path(target).name == "evidence_manifest.sha256":
            raise OSError("injected sidecar promotion failure")
        return original_replace(source, target)

    monkeypatch.setattr(evidence.os, "replace", fail_sidecar_promotion)
    with pytest.raises(OSError, match="injected sidecar promotion failure"):
        record_initial_prompt(manifest_path, "initial prompt")
    monkeypatch.setattr(evidence.os, "replace", original_replace)

    assert manifest_path.read_bytes() == before_manifest
    assert manifest_path.with_name("evidence_manifest.sha256").read_bytes() == before_sidecar
    assert not (manifest_path.parent / "initial_prompt.txt").exists()
    assert load_and_validate_batch(manifest_path)["last_completed_checkpoint"] == "SOURCE_MAP_SAVED"


def test_atomic_manifest_updates_leave_no_temporary_files(tmp_path):
    manifest_path = _create_batch(tmp_path)
    _initial_parse(manifest_path)

    assert not [path for path in manifest_path.parent.iterdir() if path.name.startswith(".")]
