from __future__ import annotations

import hashlib
import json

import pytest

from modules.asin_resolver_evidence import (
    APPROVED_FORMAL_MAIN_COMMIT_ENV,
    EvidenceValidationError,
    complete_batch,
    create_evidence_batch,
    load_and_validate_batch,
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
)


FORMAL_MAIN_COMMIT = "1c5a16a843a10140c75df9214744fe1c692da101"


@pytest.fixture(autouse=True)
def _approved_formal_commit(monkeypatch):
    monkeypatch.setenv(APPROVED_FORMAL_MAIN_COMMIT_ENV, FORMAL_MAIN_COMMIT)


def _write_manifest(manifest_path, manifest):
    raw = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    manifest_path.write_bytes(raw)
    manifest_path.with_name("evidence_manifest.sha256").write_text(
        f"{hashlib.sha256(raw).hexdigest()}  evidence_manifest.json\n",
        encoding="ascii",
    )


def test_synthetic_batch_can_resume_and_stops_for_tampering_or_foreign_artifact(tmp_path):
    runtime_root = tmp_path / "runs"
    manifest_path = create_evidence_batch(
        runtime_root,
        batch_id="PH-ASIN-integration-0001",
        formal_main_commit=FORMAL_MAIN_COMMIT,
        resolver_version="0.4.3",
    )

    # 1-6: source input/map, initial prompt/response, parse export/candidate CSV.
    persist_source_input_and_source_map(
        manifest_path,
        "JPH-A\tSynthetic alpha\nJPH-B\tSynthetic beta\n",
    )
    record_initial_prompt(manifest_path, "initial synthetic prompt")
    record_initial_response(manifest_path, "initial synthetic response")
    record_initial_parse(
        manifest_path,
        [{"source_id": "R0001", "status": "UNKNOWN"}],
        b"source_id,status\nR0001,UNKNOWN\n",
    )

    # 7-10: Retry selection, prompt, response, parse/candidate, final export.
    prepare_retry(manifest_path, [{"source_id": "R0001", "selected": True}])
    record_retry_prompt(manifest_path, "retry synthetic prompt")
    record_retry_response(manifest_path, "retry synthetic response")
    record_retry_parse(
        manifest_path,
        [{"source_id": "R0001", "status": "FOUND"}],
        b"source_id,status\nR0001,FOUND\n",
    )
    record_resolver_export(
        manifest_path,
        b"source_id,status\nR0001,FOUND\n",
        source_phase="retry",
    )

    # 11-13: application-equivalent state restoration and next checkpoint recovery.
    manifest = load_and_validate_batch(manifest_path)
    restored = restore_batch_state(manifest_path)
    assert manifest["last_completed_checkpoint"] == "EXPORT_SAVED"
    assert restored["source_entries"][1]["resolver_source_id"] == "R0002"
    assert restored["retry_parse_rows"] == [{"source_id": "R0001", "status": "FOUND"}]

    # 14-15: one artifact mutation prevents any resume.
    (manifest_path.parent / "retry_candidates.csv").write_bytes(b"modified\n")
    with pytest.raises(EvidenceValidationError, match="SHA-256 mismatch"):
        restore_batch_state(manifest_path)

    # A fresh synthetic package demonstrates a foreign artifact record hard stop.
    clean_manifest_path = create_evidence_batch(
        runtime_root,
        batch_id="PH-ASIN-integration-0002",
        formal_main_commit=FORMAL_MAIN_COMMIT,
        resolver_version="0.4.3",
    )
    persist_source_input_and_source_map(clean_manifest_path, "JPH-C\tSynthetic gamma\n")
    foreign = json.loads(clean_manifest_path.read_text(encoding="utf-8"))
    foreign["artifacts"][0]["batch_id"] = "PH-ASIN-integration-0001"
    _write_manifest(clean_manifest_path, foreign)
    with pytest.raises(EvidenceValidationError, match="batch_id does not match"):
        load_and_validate_batch(clean_manifest_path)

    # Completion is only possible after a valid export package.
    with pytest.raises(EvidenceValidationError):
        complete_batch(manifest_path)
