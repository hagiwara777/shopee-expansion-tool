from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Iterable, Mapping
import uuid


EVIDENCE_SCHEMA_VERSION = "1.0"
RUNTIME_ACCEPTANCE_STATUS = "RUNTIME_PRODUCED_PENDING_HUMAN_ACCEPTANCE"
ALLOWED_ACCEPTANCE_STATUSES = frozenset({RUNTIME_ACCEPTANCE_STATUS})
BATCH_STATUSES = frozenset({"IN_PROGRESS", "PAUSED", "COMPLETED", "BLOCKED"})
ARTIFACT_TYPES = frozenset(
    {
        "source_input",
        "source_map",
        "initial_prompt",
        "initial_ai_response",
        "initial_parse_export",
        "initial_candidate_csv",
        "retry_selection",
        "retry_prompt",
        "retry_ai_response",
        "retry_parse_export",
        "retry_candidate_csv",
        "resolver_export",
    }
)

BATCH_CREATED = "BATCH_CREATED"
SOURCE_MAP_SAVED = "SOURCE_MAP_SAVED"
INITIAL_PROMPT_SAVED = "INITIAL_PROMPT_SAVED"
INITIAL_RESPONSE_SAVED = "INITIAL_RESPONSE_SAVED"
INITIAL_PARSE_SAVED = "INITIAL_PARSE_SAVED"
RETRY_PREPARED = "RETRY_PREPARED"
RETRY_PROMPT_SAVED = "RETRY_PROMPT_SAVED"
RETRY_RESPONSE_SAVED = "RETRY_RESPONSE_SAVED"
RETRY_PARSE_SAVED = "RETRY_PARSE_SAVED"
EXPORT_SAVED = "EXPORT_SAVED"
COMPLETED = "COMPLETED"

LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    BATCH_CREATED: frozenset({SOURCE_MAP_SAVED}),
    SOURCE_MAP_SAVED: frozenset({INITIAL_PROMPT_SAVED}),
    INITIAL_PROMPT_SAVED: frozenset({INITIAL_RESPONSE_SAVED}),
    INITIAL_RESPONSE_SAVED: frozenset({INITIAL_PARSE_SAVED}),
    INITIAL_PARSE_SAVED: frozenset({RETRY_PREPARED, EXPORT_SAVED}),
    RETRY_PREPARED: frozenset({RETRY_PROMPT_SAVED}),
    RETRY_PROMPT_SAVED: frozenset({RETRY_RESPONSE_SAVED}),
    RETRY_RESPONSE_SAVED: frozenset({RETRY_PARSE_SAVED}),
    RETRY_PARSE_SAVED: frozenset({EXPORT_SAVED}),
    EXPORT_SAVED: frozenset({COMPLETED}),
    COMPLETED: frozenset(),
}
CHECKPOINTS = frozenset(LEGAL_TRANSITIONS)
NEXT_CHECKPOINT = {
    BATCH_CREATED: SOURCE_MAP_SAVED,
    SOURCE_MAP_SAVED: INITIAL_PROMPT_SAVED,
    INITIAL_PROMPT_SAVED: INITIAL_RESPONSE_SAVED,
    INITIAL_RESPONSE_SAVED: INITIAL_PARSE_SAVED,
    INITIAL_PARSE_SAVED: "RETRY_PREPARED_OR_EXPORT_SAVED",
    RETRY_PREPARED: RETRY_PROMPT_SAVED,
    RETRY_PROMPT_SAVED: RETRY_RESPONSE_SAVED,
    RETRY_RESPONSE_SAVED: RETRY_PARSE_SAVED,
    RETRY_PARSE_SAVED: EXPORT_SAVED,
    EXPORT_SAVED: COMPLETED,
    COMPLETED: COMPLETED,
}
FORMAL_MAIN_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
BATCH_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$")
APPROVED_FORMAL_MAIN_COMMIT_ENV = "ASIN_RESOLVER_APPROVED_FORMAL_MAIN_COMMIT"
EXPECTED_MARKETPLACE = "PH"
EXPECTED_MODULE = "ASIN Resolver"


class EvidenceValidationError(ValueError):
    """Raised when a batch package cannot be trusted or advanced safely."""


@dataclass(frozen=True)
class SourceMapEntry:
    upstream_source_id: str
    resolver_source_id: str
    input_order: int
    original_title: str
    initial_search_title: str

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def canonicalize_source_input(source_input: str) -> str:
    """Persist pasted input as UTF-8 text using LF and one final newline."""
    if not isinstance(source_input, str):
        raise EvidenceValidationError("source input must be text")
    if "\x00" in source_input:
        raise EvidenceValidationError("source input contains a NUL character")
    normalized = source_input.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.rstrip("\n") + "\n" if normalized.strip() else ""


def parse_source_input(
    source_input: str,
    *,
    search_title_builder: Callable[[str], str] | None = None,
) -> list[SourceMapEntry]:
    """Build a source map from canonical TSV or legacy one-title-per-line input."""
    normalized = canonicalize_source_input(source_input)
    if not normalized:
        raise EvidenceValidationError("source input has no product rows")

    build_search_title = search_title_builder or (lambda title: title)
    entries: list[SourceMapEntry] = []
    upstream_ids: set[str] = set()
    for physical_line, raw_line in enumerate(normalized.splitlines(), 1):
        if not raw_line.strip():
            continue
        if "\t" in raw_line:
            fields = raw_line.split("\t")
            if len(fields) != 2:
                raise EvidenceValidationError(
                    f"line {physical_line} must be legacy text or exactly two TSV columns"
                )
            upstream_source_id = fields[0].strip()
            original_title = fields[1].strip()
        else:
            upstream_source_id = ""
            original_title = raw_line.strip()
        if not original_title:
            raise EvidenceValidationError(f"line {physical_line} has no input_title")
        if upstream_source_id:
            if upstream_source_id in upstream_ids:
                raise EvidenceValidationError(
                    f"duplicate upstream_source_id: {upstream_source_id}"
                )
            upstream_ids.add(upstream_source_id)
        input_order = len(entries) + 1
        resolver_source_id = f"R{input_order:04d}"
        entries.append(
            SourceMapEntry(
                upstream_source_id=upstream_source_id,
                resolver_source_id=resolver_source_id,
                input_order=input_order,
                original_title=original_title,
                initial_search_title=build_search_title(original_title),
            )
        )

    resolver_ids = [entry.resolver_source_id for entry in entries]
    if len(resolver_ids) != len(set(resolver_ids)):
        raise EvidenceValidationError("duplicate resolver_source_id")
    if not entries:
        raise EvidenceValidationError("source input has no product rows")
    return entries


def source_map_tsv(entries: Iterable[SourceMapEntry]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "upstream_source_id",
            "resolver_source_id",
            "input_order",
            "original_title",
            "initial_search_title",
        ],
        delimiter="\t",
        lineterminator="\n",
    )
    writer.writeheader()
    for entry in entries:
        writer.writerow(entry.to_record())
    return buffer.getvalue().encode("utf-8")


def load_source_map_from_input(
    source_input_path: Path,
    *,
    search_title_builder: Callable[[str], str] | None = None,
) -> list[SourceMapEntry]:
    try:
        saved_input = source_input_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceValidationError("source_input is not UTF-8") from exc
    return parse_source_input(saved_input, search_title_builder=search_title_builder)


def source_map_from_tsv(data: bytes) -> list[SourceMapEntry]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceValidationError("source_map is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    expected = [
        "upstream_source_id",
        "resolver_source_id",
        "input_order",
        "original_title",
        "initial_search_title",
    ]
    if reader.fieldnames != expected:
        raise EvidenceValidationError("source_map columns do not match schema")
    entries: list[SourceMapEntry] = []
    for row in reader:
        try:
            entries.append(
                SourceMapEntry(
                    upstream_source_id=str(row["upstream_source_id"] or ""),
                    resolver_source_id=str(row["resolver_source_id"] or ""),
                    input_order=int(str(row["input_order"] or "")),
                    original_title=str(row["original_title"] or ""),
                    initial_search_title=str(row["initial_search_title"] or ""),
                )
            )
        except (KeyError, ValueError) as exc:
            raise EvidenceValidationError("source_map row is invalid") from exc
    _validate_source_map_entries(entries)
    return entries


def generate_batch_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"PH-ASIN-{timestamp}-{uuid.uuid4().hex[:8]}"


def get_approved_formal_main_commit() -> str:
    """Read the FORMAL Brief approval from its independent environment channel."""
    value = os.environ.get(APPROVED_FORMAL_MAIN_COMMIT_ENV)
    if not isinstance(value, str) or not FORMAL_MAIN_COMMIT_PATTERN.fullmatch(value.lower()):
        raise EvidenceValidationError(
            f"{APPROVED_FORMAL_MAIN_COMMIT_ENV} must be a 40-character SHA"
        )
    return value.lower()


def create_evidence_batch(
    runtime_root: Path,
    *,
    batch_id: str,
    formal_main_commit: str,
    resolver_version: str,
    marketplace: str = "PH",
    module: str = "ASIN Resolver",
) -> Path:
    _validate_batch_id(batch_id)
    _validate_formal_main_commit(formal_main_commit, get_approved_formal_main_commit())
    if marketplace != EXPECTED_MARKETPLACE or module != EXPECTED_MODULE:
        raise EvidenceValidationError("batch marketplace/module must be PH / ASIN Resolver")
    if not isinstance(resolver_version, str) or not resolver_version.strip():
        raise EvidenceValidationError("resolver metadata must not be empty")

    package_dir = Path(runtime_root) / batch_id
    try:
        package_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise EvidenceValidationError(f"batch package already exists: {batch_id}") from exc

    now = _now()
    manifest = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "batch_id": batch_id,
        "marketplace": marketplace,
        "module": module,
        "formal_main_commit": formal_main_commit.lower(),
        "resolver_version": resolver_version,
        "batch_status": "IN_PROGRESS",
        "last_completed_checkpoint": BATCH_CREATED,
        "resume_from_checkpoint": SOURCE_MAP_SAVED,
        "created_at": now,
        "updated_at": now,
        "source_map_artifact_id": None,
        "artifacts": [],
    }
    _write_manifest_atomic(package_dir, manifest)
    return package_dir / "evidence_manifest.json"


def persist_source_input_and_source_map(
    manifest_path: Path,
    source_input: str,
    *,
    search_title_builder: Callable[[str], str] | None = None,
) -> list[SourceMapEntry]:
    package_dir, manifest = _load_mutable_manifest(manifest_path)
    _require_checkpoint(manifest, BATCH_CREATED)
    canonical_input = canonicalize_source_input(source_input)
    entries = parse_source_input(canonical_input, search_title_builder=search_title_builder)
    input_bytes = canonical_input.encode("utf-8")
    map_bytes = source_map_tsv(entries)
    paths = _commit_new_stage_files(
        package_dir,
        {"source_input.txt": input_bytes, "source_map.tsv": map_bytes},
    )
    regenerated = load_source_map_from_input(
        paths["source_input.txt"], search_title_builder=search_title_builder
    )
    if regenerated != entries:
        _rollback_new_files(paths.values())
        raise EvidenceValidationError("saved source_input did not regenerate the source map")
    loaded_map = source_map_from_tsv(paths["source_map.tsv"].read_bytes())
    if loaded_map != entries or len(loaded_map) != len(entries):
        _rollback_new_files(paths.values())
        raise EvidenceValidationError("source_input and source_map do not agree")

    input_record = _artifact_record(
        manifest,
        artifact_type="source_input",
        filename="source_input.txt",
        data=input_bytes,
        parent_artifact_ids=[],
    )
    map_record = _artifact_record(
        manifest,
        artifact_type="source_map",
        filename="source_map.tsv",
        data=map_bytes,
        parent_artifact_ids=[input_record["artifact_id"]],
        source_ids=[entry.resolver_source_id for entry in entries],
    )
    try:
        manifest["artifacts"].extend([input_record, map_record])
        manifest["source_map_artifact_id"] = map_record["artifact_id"]
        _advance_manifest(manifest, SOURCE_MAP_SAVED)
        _write_manifest_atomic(package_dir, manifest)
    except Exception:
        _rollback_new_files(paths.values())
        raise
    return entries


def record_initial_prompt(manifest_path: Path, prompt: str) -> dict[str, Any]:
    return _record_one_artifact_stage(
        manifest_path,
        expected_checkpoint=SOURCE_MAP_SAVED,
        next_checkpoint=INITIAL_PROMPT_SAVED,
        artifact_type="initial_prompt",
        filename="initial_prompt.txt",
        data=_text_bytes(prompt, "initial prompt"),
        parent_types=("source_map",),
    )


def record_initial_response(manifest_path: Path, response: str) -> dict[str, Any]:
    return _record_one_artifact_stage(
        manifest_path,
        expected_checkpoint=INITIAL_PROMPT_SAVED,
        next_checkpoint=INITIAL_RESPONSE_SAVED,
        artifact_type="initial_ai_response",
        filename="initial_ai_response.txt",
        data=_text_bytes(response, "initial AI response"),
        parent_types=("initial_prompt",),
    )


def record_initial_parse(
    manifest_path: Path,
    parsed_rows: Iterable[Mapping[str, Any]],
    candidate_csv: bytes,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return _record_parse_stage(
        manifest_path,
        expected_checkpoint=INITIAL_RESPONSE_SAVED,
        next_checkpoint=INITIAL_PARSE_SAVED,
        parse_type="initial_parse_export",
        parse_filename="initial_parse.json",
        candidate_type="initial_candidate_csv",
        candidate_filename="initial_candidates.csv",
        parsed_rows=parsed_rows,
        candidate_csv=candidate_csv,
        response_parent_type="initial_ai_response",
    )


def prepare_retry(manifest_path: Path, retry_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    payload = _json_bytes({"rows": [dict(row) for row in retry_rows]})
    return _record_one_artifact_stage(
        manifest_path,
        expected_checkpoint=INITIAL_PARSE_SAVED,
        next_checkpoint=RETRY_PREPARED,
        artifact_type="retry_selection",
        filename="retry_selection.json",
        data=payload,
        parent_types=("initial_parse_export",),
    )


def record_retry_prompt(manifest_path: Path, prompt: str) -> dict[str, Any]:
    return _record_one_artifact_stage(
        manifest_path,
        expected_checkpoint=RETRY_PREPARED,
        next_checkpoint=RETRY_PROMPT_SAVED,
        artifact_type="retry_prompt",
        filename="retry_prompt.txt",
        data=_text_bytes(prompt, "retry prompt"),
        parent_types=("retry_selection",),
    )


def record_retry_response(manifest_path: Path, response: str) -> dict[str, Any]:
    return _record_one_artifact_stage(
        manifest_path,
        expected_checkpoint=RETRY_PROMPT_SAVED,
        next_checkpoint=RETRY_RESPONSE_SAVED,
        artifact_type="retry_ai_response",
        filename="retry_ai_response.txt",
        data=_text_bytes(response, "retry AI response"),
        parent_types=("retry_prompt",),
    )


def record_retry_parse(
    manifest_path: Path,
    parsed_rows: Iterable[Mapping[str, Any]],
    candidate_csv: bytes,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return _record_parse_stage(
        manifest_path,
        expected_checkpoint=RETRY_RESPONSE_SAVED,
        next_checkpoint=RETRY_PARSE_SAVED,
        parse_type="retry_parse_export",
        parse_filename="retry_parse.json",
        candidate_type="retry_candidate_csv",
        candidate_filename="retry_candidates.csv",
        parsed_rows=parsed_rows,
        candidate_csv=candidate_csv,
        response_parent_type="retry_ai_response",
    )


def record_resolver_export(
    manifest_path: Path,
    export_csv: bytes,
    *,
    source_phase: str,
) -> dict[str, Any]:
    package_dir, manifest = _load_mutable_manifest(manifest_path)
    expected = {
        "initial": (INITIAL_PARSE_SAVED, ("initial_parse_export",), "resolver_export_initial.csv"),
        "retry": (
            RETRY_PARSE_SAVED,
            ("initial_parse_export", "retry_parse_export"),
            "resolver_export_retry.csv",
        ),
    }.get(source_phase)
    if expected is None:
        raise EvidenceValidationError("resolver export source_phase must be initial or retry")
    expected_checkpoint, parent_types, filename = expected
    _require_checkpoint(manifest, expected_checkpoint)
    if not export_csv:
        raise EvidenceValidationError("resolver export must not be empty")
    parents = [_latest_artifact(manifest, parent_type)["artifact_id"] for parent_type in parent_types]
    paths = _commit_new_stage_files(package_dir, {filename: export_csv})
    record = _artifact_record(
        manifest,
        artifact_type="resolver_export",
        filename=filename,
        data=export_csv,
        parent_artifact_ids=parents,
    )
    try:
        manifest["artifacts"].append(record)
        _advance_manifest(manifest, EXPORT_SAVED)
        _write_manifest_atomic(package_dir, manifest)
    except Exception:
        _rollback_new_files(paths.values())
        raise
    return record


def complete_batch(manifest_path: Path) -> dict[str, Any]:
    package_dir, manifest = _load_mutable_manifest(manifest_path)
    _require_checkpoint(manifest, EXPORT_SAVED)
    _advance_manifest(manifest, COMPLETED)
    manifest["batch_status"] = "COMPLETED"
    _write_manifest_atomic(package_dir, manifest)
    return manifest


def pause_batch(manifest_path: Path) -> dict[str, Any]:
    package_dir, manifest = _load_mutable_manifest(manifest_path)
    if manifest["last_completed_checkpoint"] == COMPLETED:
        raise EvidenceValidationError("completed batch cannot be paused")
    manifest["batch_status"] = "PAUSED"
    manifest["updated_at"] = _now()
    _write_manifest_atomic(package_dir, manifest)
    return manifest


def resume_batch(manifest_path: Path) -> dict[str, Any]:
    package_dir, manifest = _load_mutable_manifest(manifest_path)
    if manifest["batch_status"] == "COMPLETED":
        raise EvidenceValidationError("completed batch cannot be resumed")
    if manifest["batch_status"] == "BLOCKED":
        raise EvidenceValidationError("blocked batch must not be changed")
    manifest["batch_status"] = "IN_PROGRESS"
    manifest["updated_at"] = _now()
    _write_manifest_atomic(package_dir, manifest)
    return manifest


def load_and_validate_batch(
    manifest_path: Path,
) -> dict[str, Any]:
    package_dir = Path(manifest_path).resolve().parent
    if Path(manifest_path).name != "evidence_manifest.json":
        raise EvidenceValidationError("manifest filename must be evidence_manifest.json")
    try:
        raw = Path(manifest_path).read_bytes()
    except FileNotFoundError as exc:
        raise EvidenceValidationError("evidence manifest is missing") from exc
    _validate_manifest_sidecar(package_dir, raw)
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceValidationError("evidence manifest is not valid UTF-8 JSON") from exc
    _validate_manifest(
        manifest,
        package_dir,
        allowed_formal_main_commit=get_approved_formal_main_commit(),
    )
    return manifest


def restore_batch_state(manifest_path: Path) -> dict[str, Any]:
    manifest = load_and_validate_batch(manifest_path)
    package_dir = Path(manifest_path).resolve().parent
    state: dict[str, Any] = {"manifest": manifest, "source_entries": []}
    source_input = _artifact_or_none(manifest, "source_input")
    source_map = _artifact_or_none(manifest, "source_map")
    if source_input and source_map:
        entries = source_map_from_tsv((package_dir / source_map["filename"]).read_bytes())
        state["source_entries"] = [entry.to_record() for entry in entries]
        state["source_input"] = (package_dir / source_input["filename"]).read_text(encoding="utf-8")
    for artifact_type, state_key in (
        ("initial_prompt", "initial_prompt"),
        ("initial_ai_response", "initial_ai_response"),
        ("retry_prompt", "retry_prompt"),
        ("retry_ai_response", "retry_ai_response"),
    ):
        artifact = _artifact_or_none(manifest, artifact_type)
        if artifact:
            state[state_key] = (package_dir / artifact["filename"]).read_text(encoding="utf-8")
    for artifact_type, state_key in (
        ("initial_parse_export", "initial_parse_rows"),
        ("retry_parse_export", "retry_parse_rows"),
        ("retry_selection", "retry_rows"),
    ):
        artifact = _artifact_or_none(manifest, artifact_type)
        if artifact:
            payload = json.loads((package_dir / artifact["filename"]).read_text(encoding="utf-8"))
            state[state_key] = payload.get("rows", [])
    resolver_export = _artifact_or_none(manifest, "resolver_export")
    if resolver_export:
        export_text = (package_dir / resolver_export["filename"]).read_text(encoding="utf-8")
        reader = csv.DictReader(io.StringIO(export_text))
        if not reader.fieldnames:
            raise EvidenceValidationError("resolver_export CSV has no header")
        state["resolver_rows"] = [
            {str(key): str(value or "") for key, value in row.items() if key is not None}
            for row in reader
        ]
        parent_types = {
            artifact["artifact_type"]
            for artifact in manifest["artifacts"]
            if artifact["artifact_id"] in resolver_export["parent_artifact_ids"]
        }
        state["resolver_export_phase"] = (
            "retry" if "retry_parse_export" in parent_types else "initial"
        )
    state["next_action"] = _next_action_for_checkpoint(manifest["last_completed_checkpoint"])
    return state


def _record_parse_stage(
    manifest_path: Path,
    *,
    expected_checkpoint: str,
    next_checkpoint: str,
    parse_type: str,
    parse_filename: str,
    candidate_type: str,
    candidate_filename: str,
    parsed_rows: Iterable[Mapping[str, Any]],
    candidate_csv: bytes,
    response_parent_type: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    package_dir, manifest = _load_mutable_manifest(manifest_path)
    _require_checkpoint(manifest, expected_checkpoint)
    rows = [dict(row) for row in parsed_rows]
    parse_data = _json_bytes({"rows": rows})
    if not candidate_csv:
        raise EvidenceValidationError("candidate CSV must not be empty")
    response_parent = _latest_artifact(manifest, response_parent_type)
    paths = _commit_new_stage_files(
        package_dir,
        {parse_filename: parse_data, candidate_filename: candidate_csv},
    )
    parse_record = _artifact_record(
        manifest,
        artifact_type=parse_type,
        filename=parse_filename,
        data=parse_data,
        parent_artifact_ids=[response_parent["artifact_id"]],
    )
    candidate_record = _artifact_record(
        manifest,
        artifact_type=candidate_type,
        filename=candidate_filename,
        data=candidate_csv,
        parent_artifact_ids=[parse_record["artifact_id"]],
    )
    try:
        manifest["artifacts"].extend([parse_record, candidate_record])
        _advance_manifest(manifest, next_checkpoint)
        _write_manifest_atomic(package_dir, manifest)
    except Exception:
        _rollback_new_files(paths.values())
        raise
    return parse_record, candidate_record


def _record_one_artifact_stage(
    manifest_path: Path,
    *,
    expected_checkpoint: str,
    next_checkpoint: str,
    artifact_type: str,
    filename: str,
    data: bytes,
    parent_types: tuple[str, ...],
) -> dict[str, Any]:
    package_dir, manifest = _load_mutable_manifest(manifest_path)
    _require_checkpoint(manifest, expected_checkpoint)
    parents = [_latest_artifact(manifest, artifact_type)["artifact_id"] for artifact_type in parent_types]
    paths = _commit_new_stage_files(package_dir, {filename: data})
    record = _artifact_record(
        manifest,
        artifact_type=artifact_type,
        filename=filename,
        data=data,
        parent_artifact_ids=parents,
    )
    try:
        manifest["artifacts"].append(record)
        _advance_manifest(manifest, next_checkpoint)
        _write_manifest_atomic(package_dir, manifest)
    except Exception:
        _rollback_new_files(paths.values())
        raise
    return record


def _load_mutable_manifest(manifest_path: Path) -> tuple[Path, dict[str, Any]]:
    manifest = load_and_validate_batch(manifest_path)
    if manifest["last_completed_checkpoint"] == COMPLETED:
        raise EvidenceValidationError("completed batch cannot be modified")
    if manifest["batch_status"] != "IN_PROGRESS":
        raise EvidenceValidationError("batch is not in progress")
    return Path(manifest_path).resolve().parent, manifest


def _artifact_record(
    manifest: Mapping[str, Any],
    *,
    artifact_type: str,
    filename: str,
    data: bytes,
    parent_artifact_ids: list[str],
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    if artifact_type not in ARTIFACT_TYPES:
        raise EvidenceValidationError(f"unsupported artifact type: {artifact_type}")
    if not filename or Path(filename).name != filename:
        raise EvidenceValidationError("artifact filename must be a basename")
    artifact_id = f"ART-{manifest['batch_id']}-{artifact_type}-{len(manifest['artifacts']) + 1:04d}"
    now = _now()
    record: dict[str, Any] = {
        "artifact_id": artifact_id,
        "batch_id": manifest["batch_id"],
        "artifact_type": artifact_type,
        "filename": filename,
        "sha256": _sha256(data),
        "producer": "ASIN Resolver Evidence Persistence",
        "acceptance_status": RUNTIME_ACCEPTANCE_STATUS,
        "storage_alias": f"outputs/asin_resolver_runs/{manifest['batch_id']}/{filename}",
        "parent_artifact_ids": parent_artifact_ids,
        "created_at": now,
        "updated_at": now,
    }
    if source_ids:
        record["source_ids"] = source_ids
    return record


def _advance_manifest(manifest: dict[str, Any], target_checkpoint: str) -> None:
    current = manifest["last_completed_checkpoint"]
    if target_checkpoint not in LEGAL_TRANSITIONS.get(current, frozenset()):
        raise EvidenceValidationError(f"illegal checkpoint transition: {current} -> {target_checkpoint}")
    manifest["last_completed_checkpoint"] = target_checkpoint
    manifest["resume_from_checkpoint"] = NEXT_CHECKPOINT[target_checkpoint]
    manifest["updated_at"] = _now()


def _require_checkpoint(manifest: Mapping[str, Any], expected: str) -> None:
    if manifest["last_completed_checkpoint"] != expected:
        raise EvidenceValidationError(
            f"expected checkpoint {expected}, found {manifest['last_completed_checkpoint']}"
        )


def _next_action_for_checkpoint(checkpoint: str) -> str:
    actions = {
        BATCH_CREATED: "save_source_input_and_source_map",
        SOURCE_MAP_SAVED: "generate_initial_prompt",
        INITIAL_PROMPT_SAVED: "enter_initial_response",
        INITIAL_RESPONSE_SAVED: "parse_saved_initial_response",
        INITIAL_PARSE_SAVED: "prepare_retry_or_export",
        RETRY_PREPARED: "generate_retry_prompt",
        RETRY_PROMPT_SAVED: "enter_retry_response",
        RETRY_RESPONSE_SAVED: "parse_saved_retry_response",
        RETRY_PARSE_SAVED: "export",
        EXPORT_SAVED: "complete_or_view",
        COMPLETED: "view_only",
    }
    return actions[checkpoint]


def _validate_manifest(
    manifest: Any,
    package_dir: Path,
    *,
    allowed_formal_main_commit: str | None,
) -> None:
    if not isinstance(manifest, dict):
        raise EvidenceValidationError("manifest must be an object")
    required = {
        "schema_version",
        "batch_id",
        "marketplace",
        "module",
        "formal_main_commit",
        "resolver_version",
        "batch_status",
        "last_completed_checkpoint",
        "resume_from_checkpoint",
        "created_at",
        "updated_at",
        "source_map_artifact_id",
        "artifacts",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise EvidenceValidationError(f"manifest missing fields: {', '.join(missing)}")
    if manifest["schema_version"] != EVIDENCE_SCHEMA_VERSION:
        raise EvidenceValidationError("unsupported manifest schema version")
    _validate_batch_id(manifest["batch_id"])
    _validate_formal_main_commit(manifest["formal_main_commit"], allowed_formal_main_commit)
    if manifest["marketplace"] != EXPECTED_MARKETPLACE:
        raise EvidenceValidationError("manifest marketplace must be PH")
    if manifest["module"] != EXPECTED_MODULE:
        raise EvidenceValidationError("manifest module must be ASIN Resolver")
    if not isinstance(manifest["resolver_version"], str) or not manifest["resolver_version"].strip():
        raise EvidenceValidationError("manifest resolver_version must not be empty")
    _validate_timestamp(manifest["created_at"], "manifest created_at")
    _validate_timestamp(manifest["updated_at"], "manifest updated_at")
    if manifest["batch_status"] not in BATCH_STATUSES:
        raise EvidenceValidationError("invalid batch status")
    checkpoint = manifest["last_completed_checkpoint"]
    if checkpoint not in CHECKPOINTS:
        raise EvidenceValidationError("invalid checkpoint")
    if manifest["resume_from_checkpoint"] != NEXT_CHECKPOINT[checkpoint]:
        raise EvidenceValidationError("resume checkpoint does not match last checkpoint")
    if checkpoint == COMPLETED and manifest["batch_status"] != "COMPLETED":
        raise EvidenceValidationError("completed checkpoint requires COMPLETED status")
    if checkpoint != COMPLETED and manifest["batch_status"] == "COMPLETED":
        raise EvidenceValidationError("COMPLETED status requires completed checkpoint")
    if not isinstance(manifest["artifacts"], list):
        raise EvidenceValidationError("artifacts must be a list")

    artifact_by_id: dict[str, dict[str, Any]] = {}
    filenames: set[str] = set()
    for artifact in manifest["artifacts"]:
        _validate_artifact_record(artifact, manifest["batch_id"], package_dir)
        artifact_id = artifact["artifact_id"]
        if artifact_id in artifact_by_id:
            raise EvidenceValidationError("duplicate artifact ID")
        if artifact["filename"] in filenames:
            raise EvidenceValidationError("duplicate artifact filename")
        artifact_by_id[artifact_id] = artifact
        filenames.add(artifact["filename"])

    for artifact in artifact_by_id.values():
        for parent_id in artifact["parent_artifact_ids"]:
            if parent_id not in artifact_by_id:
                raise EvidenceValidationError("parent artifact is missing from manifest")
            if artifact_by_id[parent_id]["batch_id"] != manifest["batch_id"]:
                raise EvidenceValidationError("parent artifact belongs to another batch")
        _validate_expected_parent_types(artifact, artifact_by_id)

    _validate_checkpoint_artifacts(manifest, artifact_by_id)
    _validate_source_input_map_correspondence(package_dir, artifact_by_id)
    _validate_artifact_source_ids(package_dir, artifact_by_id)
    _validate_package_file_set(package_dir, filenames)


def _validate_artifact_record(artifact: Any, batch_id: str, package_dir: Path) -> None:
    if not isinstance(artifact, dict):
        raise EvidenceValidationError("artifact record must be an object")
    required = {
        "artifact_id",
        "batch_id",
        "artifact_type",
        "filename",
        "sha256",
        "producer",
        "acceptance_status",
        "storage_alias",
        "parent_artifact_ids",
        "created_at",
        "updated_at",
    }
    if required - set(artifact):
        raise EvidenceValidationError("artifact record is missing required fields")
    if artifact["batch_id"] != batch_id:
        raise EvidenceValidationError("artifact batch_id does not match manifest")
    if artifact["artifact_type"] not in ARTIFACT_TYPES:
        raise EvidenceValidationError("unsupported artifact type")
    filename = artifact["filename"]
    if not isinstance(filename, str) or not filename or Path(filename).name != filename:
        raise EvidenceValidationError("unsafe artifact filename")
    if not isinstance(artifact["producer"], str) or not artifact["producer"].strip():
        raise EvidenceValidationError("artifact producer must not be empty")
    if artifact["acceptance_status"] not in ALLOWED_ACCEPTANCE_STATUSES:
        raise EvidenceValidationError("unsupported acceptance status")
    if not isinstance(artifact["storage_alias"], str) or not artifact["storage_alias"].strip():
        raise EvidenceValidationError("artifact storage alias must not be empty")
    if not isinstance(artifact["parent_artifact_ids"], list):
        raise EvidenceValidationError("parent_artifact_ids must be a list")
    if not isinstance(artifact["sha256"], str) or not SHA256_PATTERN.fullmatch(artifact["sha256"]):
        raise EvidenceValidationError("artifact SHA-256 must be 64 lowercase hex characters")
    _validate_timestamp(artifact["created_at"], "artifact created_at")
    _validate_timestamp(artifact["updated_at"], "artifact updated_at")
    if "source_ids" in artifact and (
        not isinstance(artifact["source_ids"], list)
        or not all(isinstance(source_id, str) for source_id in artifact["source_ids"])
    ):
        raise EvidenceValidationError("artifact source_ids must be a list of strings")
    expected_alias = f"outputs/asin_resolver_runs/{batch_id}/{filename}"
    if artifact["storage_alias"] != expected_alias:
        raise EvidenceValidationError("artifact storage alias is not canonical")
    path = (package_dir / filename).resolve()
    if path.parent != package_dir.resolve() or not path.is_file():
        raise EvidenceValidationError("artifact file is missing or outside its package")
    if _sha256(path.read_bytes()) != artifact["sha256"]:
        raise EvidenceValidationError("artifact SHA-256 mismatch")


def _validate_expected_parent_types(
    artifact: Mapping[str, Any], artifact_by_id: Mapping[str, Mapping[str, Any]]
) -> None:
    expected_parent_types: dict[str, tuple[str, ...] | None] = {
        "source_input": (),
        "source_map": ("source_input",),
        "initial_prompt": ("source_map",),
        "initial_ai_response": ("initial_prompt",),
        "initial_parse_export": ("initial_ai_response",),
        "initial_candidate_csv": ("initial_parse_export",),
        "retry_selection": ("initial_parse_export",),
        "retry_prompt": ("retry_selection",),
        "retry_ai_response": ("retry_prompt",),
        "retry_parse_export": ("retry_ai_response",),
        "retry_candidate_csv": ("retry_parse_export",),
        "resolver_export": None,
    }
    parent_ids = artifact["parent_artifact_ids"]
    parent_types = tuple(artifact_by_id[parent_id]["artifact_type"] for parent_id in parent_ids)
    expected = expected_parent_types[artifact["artifact_type"]]
    if artifact["artifact_type"] == "resolver_export":
        allowed = {
            ("initial_parse_export",),
            ("initial_parse_export", "retry_parse_export"),
        }
        if parent_types not in allowed:
            raise EvidenceValidationError("resolver export must parent a parse export")
    elif parent_types != expected:
        raise EvidenceValidationError("artifact parent types are invalid")


def _validate_checkpoint_artifacts(
    manifest: Mapping[str, Any], artifact_by_id: Mapping[str, Mapping[str, Any]]
) -> None:
    types = {artifact["artifact_type"] for artifact in artifact_by_id.values()}
    checkpoint = manifest["last_completed_checkpoint"]
    required_by_checkpoint = {
        BATCH_CREATED: set(),
        SOURCE_MAP_SAVED: {"source_input", "source_map"},
        INITIAL_PROMPT_SAVED: {"source_input", "source_map", "initial_prompt"},
        INITIAL_RESPONSE_SAVED: {
            "source_input", "source_map", "initial_prompt", "initial_ai_response"
        },
        INITIAL_PARSE_SAVED: {
            "source_input",
            "source_map",
            "initial_prompt",
            "initial_ai_response",
            "initial_parse_export",
            "initial_candidate_csv",
        },
        RETRY_PREPARED: {
            "source_input",
            "source_map",
            "initial_prompt",
            "initial_ai_response",
            "initial_parse_export",
            "initial_candidate_csv",
            "retry_selection",
        },
        RETRY_PROMPT_SAVED: {
            "source_input",
            "source_map",
            "initial_prompt",
            "initial_ai_response",
            "initial_parse_export",
            "initial_candidate_csv",
            "retry_selection",
            "retry_prompt",
        },
        RETRY_RESPONSE_SAVED: {
            "source_input",
            "source_map",
            "initial_prompt",
            "initial_ai_response",
            "initial_parse_export",
            "initial_candidate_csv",
            "retry_selection",
            "retry_prompt",
            "retry_ai_response",
        },
        RETRY_PARSE_SAVED: {
            "source_input",
            "source_map",
            "initial_prompt",
            "initial_ai_response",
            "initial_parse_export",
            "initial_candidate_csv",
            "retry_selection",
            "retry_prompt",
            "retry_ai_response",
            "retry_parse_export",
            "retry_candidate_csv",
        },
    }
    if checkpoint in {EXPORT_SAVED, COMPLETED}:
        base = required_by_checkpoint[INITIAL_PARSE_SAVED]
        retry_types = {
            "retry_selection",
            "retry_prompt",
            "retry_ai_response",
            "retry_parse_export",
            "retry_candidate_csv",
        }
        if types & retry_types:
            base = required_by_checkpoint[RETRY_PARSE_SAVED]
        required = base | {"resolver_export"}
    else:
        required = required_by_checkpoint[checkpoint]
    if types != required:
        raise EvidenceValidationError("checkpoint artifacts do not match a legal transition path")
    source_map_ids = [
        artifact_id
        for artifact_id, artifact in artifact_by_id.items()
        if artifact["artifact_type"] == "source_map"
    ]
    if checkpoint == BATCH_CREATED:
        if manifest["source_map_artifact_id"] is not None:
            raise EvidenceValidationError("new batch must not have a source map artifact ID")
    elif len(source_map_ids) != 1 or manifest["source_map_artifact_id"] != source_map_ids[0]:
        raise EvidenceValidationError("source_map_artifact_id does not identify the source map")


def _validate_source_input_map_correspondence(
    package_dir: Path, artifact_by_id: Mapping[str, Mapping[str, Any]]
) -> None:
    source_input = next(
        (artifact for artifact in artifact_by_id.values() if artifact["artifact_type"] == "source_input"),
        None,
    )
    source_map = next(
        (artifact for artifact in artifact_by_id.values() if artifact["artifact_type"] == "source_map"),
        None,
    )
    if source_input is None and source_map is None:
        return
    if source_input is None or source_map is None:
        raise EvidenceValidationError("source_input and source_map must be saved together")
    input_entries = parse_source_input(
        (package_dir / source_input["filename"]).read_text(encoding="utf-8")
    )
    map_entries = source_map_from_tsv((package_dir / source_map["filename"]).read_bytes())
    input_identity = [
        (entry.upstream_source_id, entry.resolver_source_id, entry.input_order, entry.original_title)
        for entry in input_entries
    ]
    map_identity = [
        (entry.upstream_source_id, entry.resolver_source_id, entry.input_order, entry.original_title)
        for entry in map_entries
    ]
    if input_identity != map_identity:
        raise EvidenceValidationError("source_input and source_map rows do not correspond")


def _validate_artifact_source_ids(
    package_dir: Path, artifact_by_id: Mapping[str, Mapping[str, Any]]
) -> None:
    source_map = next(
        (artifact for artifact in artifact_by_id.values() if artifact["artifact_type"] == "source_map"),
        None,
    )
    known_ids: set[str] = set()
    if source_map is not None:
        known_ids = {
            entry.resolver_source_id
            for entry in source_map_from_tsv((package_dir / source_map["filename"]).read_bytes())
        }
    for artifact in artifact_by_id.values():
        for source_id in artifact.get("source_ids", []):
            if source_id not in known_ids:
                raise EvidenceValidationError("artifact source_ids contain an unknown resolver source ID")


def _validate_timestamp(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise EvidenceValidationError(f"{label} must be an ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise EvidenceValidationError(f"{label} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidenceValidationError(f"{label} must include a timezone")


def _validate_package_file_set(package_dir: Path, artifact_filenames: set[str]) -> None:
    allowed = artifact_filenames | {"evidence_manifest.json", "evidence_manifest.sha256"}
    files = {path.name for path in package_dir.iterdir() if path.is_file()}
    if files != allowed:
        raise EvidenceValidationError("batch package contains unregistered or missing files")


def _validate_manifest_sidecar(package_dir: Path, manifest_bytes: bytes) -> None:
    sidecar = package_dir / "evidence_manifest.sha256"
    if not sidecar.is_file():
        raise EvidenceValidationError("manifest SHA sidecar is missing")
    expected = f"{_sha256(manifest_bytes)}  evidence_manifest.json\n"
    if sidecar.read_text(encoding="ascii") != expected:
        raise EvidenceValidationError("manifest SHA sidecar mismatch")


def _write_manifest_atomic(package_dir: Path, manifest: Mapping[str, Any]) -> None:
    serialized = _json_bytes(manifest)
    _replace_file_pair_atomically(
        package_dir,
        {
            "evidence_manifest.json": serialized,
            "evidence_manifest.sha256": f"{_sha256(serialized)}  evidence_manifest.json\n".encode("ascii"),
        },
    )


def _atomic_write(destination: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=destination.parent, prefix=f".{destination.name}.", delete=False
    ) as temporary:
        temporary.write(data)
        temporary.flush()
        temporary_name = Path(temporary.name)
    temporary_name.replace(destination)


def _write_new_artifact_file(package_dir: Path, filename: str, data: bytes) -> Path:
    path = package_dir / filename
    if path.exists():
        raise EvidenceValidationError(f"artifact filename already exists: {filename}")
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except FileExistsError as exc:
        raise EvidenceValidationError(f"artifact filename already exists: {filename}") from exc
    return path


def _commit_new_stage_files(package_dir: Path, files: Mapping[str, bytes]) -> dict[str, Path]:
    """Promote a new multi-file stage together or remove only its new files on failure."""
    for filename in files:
        if Path(filename).name != filename or (package_dir / filename).exists():
            raise EvidenceValidationError(f"artifact filename already exists: {filename}")
    temporary_paths: dict[str, Path] = {}
    promoted: dict[str, Path] = {}
    try:
        for filename, data in files.items():
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=package_dir, prefix=f".{filename}.", delete=False
            ) as temporary:
                temporary.write(data)
                temporary.flush()
                temporary_paths[filename] = Path(temporary.name)
        for filename, temporary_path in temporary_paths.items():
            destination = package_dir / filename
            temporary_path.replace(destination)
            promoted[filename] = destination
        return promoted
    except Exception:
        _rollback_new_files(promoted.values())
        _rollback_new_files(temporary_paths.values())
        raise


def _rollback_new_files(paths: Iterable[Path]) -> None:
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass


def _replace_file_pair_atomically(package_dir: Path, files: Mapping[str, bytes]) -> None:
    """Replace manifest and sidecar while restoring their former bytes on a write failure."""
    originals = {
        filename: (package_dir / filename).read_bytes() if (package_dir / filename).exists() else None
        for filename in files
    }
    temporary_paths: dict[str, Path] = {}
    replaced: list[str] = []
    try:
        for filename, data in files.items():
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=package_dir, prefix=f".{filename}.", delete=False
            ) as temporary:
                temporary.write(data)
                temporary.flush()
                temporary_paths[filename] = Path(temporary.name)
        for filename, temporary_path in temporary_paths.items():
            temporary_path.replace(package_dir / filename)
            replaced.append(filename)
    except Exception:
        for filename in reversed(replaced):
            original = originals[filename]
            destination = package_dir / filename
            if original is None:
                _rollback_new_files([destination])
            else:
                _atomic_write(destination, original)
        raise
    finally:
        _rollback_new_files(temporary_paths.values())


def _latest_artifact(manifest: Mapping[str, Any], artifact_type: str) -> Mapping[str, Any]:
    matches = [artifact for artifact in manifest["artifacts"] if artifact["artifact_type"] == artifact_type]
    if len(matches) != 1:
        raise EvidenceValidationError(f"expected one {artifact_type} artifact")
    return matches[0]


def _artifact_or_none(manifest: Mapping[str, Any], artifact_type: str) -> Mapping[str, Any] | None:
    matches = [artifact for artifact in manifest["artifacts"] if artifact["artifact_type"] == artifact_type]
    if len(matches) > 1:
        raise EvidenceValidationError(f"multiple {artifact_type} artifacts are not supported")
    return matches[0] if matches else None


def _validate_source_map_entries(entries: Iterable[SourceMapEntry]) -> None:
    materialized = list(entries)
    if not materialized:
        raise EvidenceValidationError("source_map has no rows")
    resolver_ids = [entry.resolver_source_id for entry in materialized]
    if len(resolver_ids) != len(set(resolver_ids)):
        raise EvidenceValidationError("duplicate resolver_source_id")
    upstream_ids = [entry.upstream_source_id for entry in materialized if entry.upstream_source_id]
    if len(upstream_ids) != len(set(upstream_ids)):
        raise EvidenceValidationError("duplicate upstream_source_id")
    for expected_order, entry in enumerate(materialized, 1):
        if entry.input_order != expected_order or entry.resolver_source_id != f"R{expected_order:04d}":
            raise EvidenceValidationError("source_map input order does not match resolver IDs")
        if not entry.original_title or not entry.initial_search_title:
            raise EvidenceValidationError("source_map title fields must not be empty")


def _validate_formal_main_commit(value: Any, allowed_value: str | None) -> None:
    if not isinstance(value, str) or not FORMAL_MAIN_COMMIT_PATTERN.fullmatch(value.lower()):
        raise EvidenceValidationError("formal_main_commit must be a 40-character SHA")
    if allowed_value is not None:
        if not isinstance(allowed_value, str) or not FORMAL_MAIN_COMMIT_PATTERN.fullmatch(
            allowed_value.lower()
        ):
            raise EvidenceValidationError("allowed formal main commit must be a 40-character SHA")
        if value.lower() != allowed_value.lower():
            raise EvidenceValidationError("formal_main_commit does not match the allowed formal commit")


def _validate_batch_id(value: Any) -> None:
    if not isinstance(value, str) or not BATCH_ID_PATTERN.fullmatch(value):
        raise EvidenceValidationError("batch_id is invalid")


def _text_bytes(value: str, label: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise EvidenceValidationError(f"{label} must not be empty")
    return value.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
