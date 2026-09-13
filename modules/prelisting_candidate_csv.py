"""Convert and validate the shared pre-listing candidate CSV contract."""

from __future__ import annotations

import csv
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
from typing import Any, Iterable, Mapping
import unicodedata

from modules.keepa_client import normalize_asin


PRELISTING_CANDIDATE_SCHEMA_VERSION = "PRELISTING_CANDIDATE_V1"
PRELISTING_CANDIDATE_COLUMNS = (
    "schema_version",
    "source_type",
    "source_id",
    "source_asin",
    "candidate_asin",
    "input_title",
    "product_title",
    "brand",
    "category",
    "amazon_url",
    "source_status",
    "source_verification",
    "source",
    "fetched_at",
    "source_note",
)

EXPANSION_SOURCE_TYPE = "EXPANSION"
RESOLVER_SOURCE_TYPE = "RESOLVER"
ALLOWED_SOURCE_TYPES = {EXPANSION_SOURCE_TYPE, RESOLVER_SOURCE_TYPE}
RESOLVER_SOURCE = "asin_resolver_keepa_verified"
RESOLVER_FOUND_STATUS = "FOUND"
RESOLVER_VERIFICATION = "KEEPA_VERIFIED"
CANOPY_RESOLVER_SOURCE = "asin_resolver_canopy_verified"
CANOPY_RESOLVER_VERIFICATION = "CANOPY_VERIFIED"
RESOLVER_SOURCE_BY_VERIFICATION = {
    RESOLVER_VERIFICATION: RESOLVER_SOURCE,
    CANOPY_RESOLVER_VERIFICATION: CANOPY_RESOLVER_SOURCE,
}
_INPUT_ROW_KEYS = (
    "seed_asin",
    "candidate_asin",
    "product_title",
    "brand",
    "category",
    "source",
    "fetched_at",
    "note",
    "source_id",
    "asin",
    "input_title",
    "keepa_title",
    "keepa_brand",
    "keepa_category",
    "amazon_url",
    "status",
    "verification",
    "keepa_fetched_at",
    "canopy_title",
    "canopy_brand",
    "canopy_category",
    "canopy_fetched_at",
    "product_title",
    "product_brand",
    "product_category",
    "product_fetched_at",
)


class PrelistingCandidateCsvError(RuntimeError):
    """Raised when a pre-listing candidate CSV cannot be trusted."""


class ResolverGateHandoffError(PrelistingCandidateCsvError):
    """Raised when duplicate Resolver evidence cannot be safely consolidated."""


@dataclass(frozen=True)
class PrelistingCandidateRow:
    """One validated candidate row in the shared pre-listing CSV contract."""

    schema_version: str
    source_type: str
    source_id: str
    source_asin: str
    candidate_asin: str
    input_title: str
    product_title: str
    brand: str
    category: str
    amazon_url: str
    source_status: str
    source_verification: str
    source: str
    fetched_at: str
    source_note: str


@dataclass(frozen=True)
class ResolverCandidateConversionResult:
    """Resolver conversion rows and the source-row eligibility counts."""

    output_rows: tuple[PrelistingCandidateRow, ...]
    input_row_count: int
    eligible_row_count: int
    excluded_row_count: int


@dataclass(frozen=True)
class ResolverGateHandoffNormalizationResult:
    """Unique product rows used only at the Resolver-to-Gate handoff boundary."""

    candidate_rows: tuple[PrelistingCandidateRow, ...]
    source_rows: tuple[dict[str, Any], ...]
    verified_row_count: int
    unique_candidate_count: int
    consolidated_row_count: int


@dataclass(frozen=True)
class PrelistingCandidateFileResult:
    """The validated contents of one shared pre-listing candidate CSV."""

    schema_version: str
    source_type: str
    source_file: str
    data_row_count: int
    rows: tuple[PrelistingCandidateRow, ...]


def expansion_rows_to_prelisting_candidates(
    rows: Iterable[Mapping[str, Any]],
) -> list[PrelistingCandidateRow]:
    """Convert Guardrail-pre-application Expansion rows without deduplication."""

    output_rows: list[PrelistingCandidateRow] = []
    for row_number, row in enumerate(rows, 1):
        values = _mapping_values(row, f"Expansion入力 {row_number}行目")
        output_rows.append(
            _canonicalize_row(
                PrelistingCandidateRow(
                    schema_version=PRELISTING_CANDIDATE_SCHEMA_VERSION,
                    source_type=EXPANSION_SOURCE_TYPE,
                    source_id="",
                    source_asin=values["seed_asin"],
                    candidate_asin=values["candidate_asin"],
                    input_title="",
                    product_title=values["product_title"],
                    brand=values["brand"],
                    category=values["category"],
                    amazon_url="",
                    source_status="",
                    source_verification="",
                    source=values["source"],
                    fetched_at=values["fetched_at"],
                    source_note=values["note"],
                ),
                f"Expansion入力 {row_number}行目",
            )
        )
    return output_rows


def resolver_rows_to_prelisting_candidates(
    rows: Iterable[Mapping[str, Any]],
) -> ResolverCandidateConversionResult:
    """Convert only provider-verified FOUND Resolver rows without API access."""

    materialized_rows = list(rows)
    output_rows: list[PrelistingCandidateRow] = []
    for row_number, row in enumerate(materialized_rows, 1):
        values = _mapping_values(row, f"Resolver入力 {row_number}行目")
        status = values["status"].strip().upper()
        verification = values["verification"].strip().upper()
        if status != RESOLVER_FOUND_STATUS or verification not in RESOLVER_SOURCE_BY_VERIFICATION:
            continue

        prefix = "keepa" if verification == RESOLVER_VERIFICATION else "canopy"
        product_title = values["product_title"] or values[f"{prefix}_title"]
        product_brand = values["product_brand"] or values[f"{prefix}_brand"]
        product_category = values["product_category"] or values[f"{prefix}_category"]
        product_fetched_at = values["product_fetched_at"] or values[f"{prefix}_fetched_at"]

        output_rows.append(
            _canonicalize_row(
                PrelistingCandidateRow(
                    schema_version=PRELISTING_CANDIDATE_SCHEMA_VERSION,
                    source_type=RESOLVER_SOURCE_TYPE,
                    source_id=values["source_id"],
                    source_asin="",
                    candidate_asin=values["asin"],
                    input_title=values["input_title"],
                    product_title=product_title,
                    brand=product_brand,
                    category=product_category,
                    amazon_url=values["amazon_url"],
                    source_status=RESOLVER_FOUND_STATUS,
                    source_verification=verification,
                    source=RESOLVER_SOURCE_BY_VERIFICATION[verification],
                    fetched_at=product_fetched_at,
                    source_note=values["note"],
                ),
                f"Resolver入力 {row_number}行目",
            )
        )

    return ResolverCandidateConversionResult(
        output_rows=tuple(output_rows),
        input_row_count=len(materialized_rows),
        eligible_row_count=len(output_rows),
        excluded_row_count=len(materialized_rows) - len(output_rows),
    )


def normalize_resolver_gate_handoff(
    candidate_rows: Iterable[PrelistingCandidateRow],
    source_rows: Iterable[Mapping[str, Any]],
) -> ResolverGateHandoffNormalizationResult:
    """Consolidate duplicate ASINs only for the Resolver-to-Gate handoff.

    Resolver evidence remains row-oriented. Gate candidates and all Safety
    sidecars are product-oriented and therefore require one row per ASIN.
    """

    candidates = tuple(
        _canonicalize_row(row, f"Resolver Gate handoff {row_number}行目")
        for row_number, row in enumerate(candidate_rows, 1)
    )
    eligible_sources: list[Mapping[str, Any]] = []
    for row_number, source in enumerate(source_rows, 1):
        values = _mapping_values(source, f"Resolver Gate source {row_number}行目")
        if (
            values["status"].strip().upper() == RESOLVER_FOUND_STATUS
            and values["verification"].strip().upper() in RESOLVER_SOURCE_BY_VERIFICATION
        ):
            eligible_sources.append(source)

    if len(candidates) != len(eligible_sources):
        raise ResolverGateHandoffError(
            "Resolver Gate handoff candidate/source row counts do not match"
        )

    unique_candidates: list[PrelistingCandidateRow] = []
    unique_sources: list[dict[str, Any]] = []
    index_by_asin: dict[str, int] = {}
    for row_number, (candidate, source) in enumerate(
        zip(candidates, eligible_sources), 1
    ):
        source_asin = _normalize_required_asin(
            _text(source.get("candidate_asin") or source.get("asin")),
            f"Resolver Gate source {row_number}行目: candidate_asin",
        )
        if source_asin != candidate.candidate_asin:
            raise ResolverGateHandoffError(
                f"{candidate.candidate_asin}: Resolver candidate/source ASIN mismatch"
            )

        source_verification = _text(source.get("verification")).strip().upper()
        if source_verification != candidate.source_verification:
            raise ResolverGateHandoffError(
                f"{candidate.candidate_asin}: duplicate Resolver rows contain "
                "conflicting provider/verification evidence"
            )

        existing_index = index_by_asin.get(candidate.candidate_asin)
        if existing_index is None:
            index_by_asin[candidate.candidate_asin] = len(unique_candidates)
            unique_candidates.append(candidate)
            unique_sources.append(deepcopy(dict(source)))
            continue

        unique_candidates[existing_index] = _merge_candidate_product_evidence(
            unique_candidates[existing_index], candidate
        )
        unique_sources[existing_index] = _merge_resolver_safety_evidence(
            unique_sources[existing_index], source, candidate.candidate_asin
        )

    return ResolverGateHandoffNormalizationResult(
        candidate_rows=tuple(unique_candidates),
        source_rows=tuple(unique_sources),
        verified_row_count=len(candidates),
        unique_candidate_count=len(unique_candidates),
        consolidated_row_count=len(candidates) - len(unique_candidates),
    )


def rows_to_prelisting_candidate_csv(
    rows: Iterable[PrelistingCandidateRow],
) -> bytes:
    """Serialize one source type of validated candidate rows as UTF-8 BOM CSV."""

    canonical_rows = tuple(
        _canonicalize_row(row, f"CSV出力 {row_number}行目")
        for row_number, row in enumerate(rows, 1)
    )
    if not canonical_rows:
        raise PrelistingCandidateCsvError("出品前保安ゲート用CSVのデータ行が0件です。")

    source_types = {row.source_type for row in canonical_rows}
    if len(source_types) > 1:
        raise PrelistingCandidateCsvError(
            "出品前保安ゲート用CSVにEXPANSIONとRESOLVERを混在させられません。"
        )

    buffer = StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=PRELISTING_CANDIDATE_COLUMNS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in canonical_rows:
        writer.writerow(_row_to_dict(row))
    return buffer.getvalue().encode("utf-8-sig")


def parse_prelisting_candidate_csv(
    content: bytes,
    *,
    filename: str,
) -> PrelistingCandidateFileResult:
    """Parse one fixed-schema pre-listing candidate CSV without filtering rows."""

    text = _decode_utf8_content(content, filename)
    csv_rows = _read_csv_rows(text, filename)
    if not csv_rows:
        raise PrelistingCandidateCsvError(f"{filename}: CSV内容が空です。")

    header_row_number, header = csv_rows[0]
    if header != list(PRELISTING_CANDIDATE_COLUMNS):
        raise PrelistingCandidateCsvError(
            f"{filename} のCSV {header_row_number}行目: "
            "ヘッダーが出品前保安ゲート用CSVの固定15列と一致しません。"
        )

    raw_rows: list[tuple[int, PrelistingCandidateRow]] = []
    for source_row_number, values in csv_rows[1:]:
        if _is_blank_row(values):
            continue
        if len(values) != len(PRELISTING_CANDIDATE_COLUMNS):
            raise PrelistingCandidateCsvError(
                f"{filename} のCSV {source_row_number}行目: "
                f"列数が不正です。期待値={len(PRELISTING_CANDIDATE_COLUMNS)}、実値={len(values)}"
            )
        raw_rows.append(
            (
                source_row_number,
                PrelistingCandidateRow(**dict(zip(PRELISTING_CANDIDATE_COLUMNS, values))),
            )
        )

    if not raw_rows:
        raise PrelistingCandidateCsvError(
            f"{filename}: ヘッダー行の後に出品前保安ゲート候補行がありません。"
        )

    schema_versions = {row.schema_version for _, row in raw_rows}
    if len(schema_versions) > 1:
        raise PrelistingCandidateCsvError(
            f"{filename}: schema_versionが複数混在しています。"
        )
    if schema_versions != {PRELISTING_CANDIDATE_SCHEMA_VERSION}:
        raise PrelistingCandidateCsvError(
            f"{filename}: 未対応のschema_versionです。"
        )

    source_types = {row.source_type for _, row in raw_rows}
    invalid_source_types = source_types - ALLOWED_SOURCE_TYPES
    if invalid_source_types:
        raise PrelistingCandidateCsvError(
            f"{filename}: 不正なsource_typeです。"
        )
    if len(source_types) > 1:
        raise PrelistingCandidateCsvError(
            f"{filename}: EXPANSIONとRESOLVERが同一CSVに混在しています。"
        )

    canonical_rows = tuple(
        _canonicalize_row(row, f"{filename} のCSV {source_row_number}行目")
        for source_row_number, row in raw_rows
    )
    return PrelistingCandidateFileResult(
        schema_version=PRELISTING_CANDIDATE_SCHEMA_VERSION,
        source_type=canonical_rows[0].source_type,
        source_file=filename,
        data_row_count=len(canonical_rows),
        rows=canonical_rows,
    )


def _mapping_values(row: Mapping[str, Any], context: str) -> dict[str, str]:
    if not isinstance(row, Mapping):
        raise PrelistingCandidateCsvError(f"{context}: 入力行が辞書ではありません。")
    return {key: _text(row.get(key)) for key in _INPUT_ROW_KEYS}


def _merge_candidate_product_evidence(
    first: PrelistingCandidateRow, duplicate: PrelistingCandidateRow
) -> PrelistingCandidateRow:
    asin = first.candidate_asin
    if duplicate.candidate_asin != asin:
        raise ResolverGateHandoffError(
            f"{asin}: Resolver duplicate consolidation ASIN mismatch"
        )
    merged = first.__dict__.copy()
    for field, label in (
        ("source_verification", "provider/verification"),
        ("source", "provider/verification"),
        ("product_title", "product title"),
        ("brand", "brand"),
        ("category", "category"),
        ("fetched_at", "product fetch timestamp"),
    ):
        existing = _text(merged[field])
        incoming = _text(getattr(duplicate, field))
        if existing and incoming and existing != incoming:
            raise ResolverGateHandoffError(
                f"{asin}: duplicate Resolver rows contain conflicting {label} evidence"
            )
        if not existing and incoming:
            merged[field] = incoming
    return PrelistingCandidateRow(**merged)


def _merge_resolver_safety_evidence(
    first: dict[str, Any], duplicate: Mapping[str, Any], asin: str
) -> dict[str, Any]:
    merged = deepcopy(first)
    for field, label in (
        ("ingredient_safety_fact", "Ingredient Safety"),
        ("product_text_safety_fact", "Product Text Safety"),
        ("ph_image_safety_fact", "PH Image Safety"),
    ):
        existing = merged.get(field)
        incoming = duplicate.get(field)
        if existing is None:
            if incoming is not None:
                merged[field] = deepcopy(incoming)
            continue
        if incoming is None or existing == incoming:
            continue
        raise ResolverGateHandoffError(
            f"{asin}: duplicate Resolver rows contain conflicting {label} evidence"
        )
    return merged


def _canonicalize_row(row: PrelistingCandidateRow, context: str) -> PrelistingCandidateRow:
    if not isinstance(row, PrelistingCandidateRow):
        raise PrelistingCandidateCsvError(f"{context}: CSV行の型が不正です。")

    values = {column: _text(getattr(row, column)) for column in PRELISTING_CANDIDATE_COLUMNS}
    if values["schema_version"] != PRELISTING_CANDIDATE_SCHEMA_VERSION:
        raise PrelistingCandidateCsvError(f"{context}: 未対応のschema_versionです。")
    if values["source_type"] not in ALLOWED_SOURCE_TYPES:
        raise PrelistingCandidateCsvError(f"{context}: 不正なsource_typeです。")

    candidate_asin = _normalize_required_asin(
        values["candidate_asin"],
        f"{context}: candidate_asin",
    )
    source_asin = values["source_asin"]
    source = values["source"]

    if values["source_type"] == EXPANSION_SOURCE_TYPE:
        source_asin = _normalize_required_asin(
            source_asin,
            f"{context}: source_asin",
        )
        if not source.strip():
            raise PrelistingCandidateCsvError(f"{context}: sourceが空です。")
    else:
        if values["source_status"] != RESOLVER_FOUND_STATUS:
            raise PrelistingCandidateCsvError(f"{context}: Resolverのsource_statusはFOUNDである必要があります。")
        verification = values["source_verification"]
        if verification not in RESOLVER_SOURCE_BY_VERIFICATION:
            raise PrelistingCandidateCsvError(
                f"{context}: Resolverのsource_verificationが未対応です。"
            )
        expected_source = RESOLVER_SOURCE_BY_VERIFICATION[verification]
        if source != expected_source:
            raise PrelistingCandidateCsvError(
                f"{context}: Resolverのsourceは{expected_source}である必要があります。"
            )

    return PrelistingCandidateRow(
        schema_version=PRELISTING_CANDIDATE_SCHEMA_VERSION,
        source_type=values["source_type"],
        source_id=values["source_id"],
        source_asin=source_asin,
        candidate_asin=candidate_asin,
        input_title=values["input_title"],
        product_title=values["product_title"],
        brand=values["brand"],
        category=values["category"],
        amazon_url=values["amazon_url"],
        source_status=values["source_status"],
        source_verification=values["source_verification"],
        source=source,
        fetched_at=values["fetched_at"],
        source_note=values["source_note"],
    )


def _normalize_required_asin(value: str, context: str) -> str:
    candidate = unicodedata.normalize("NFKC", _text(value)).strip().upper()
    if not candidate:
        raise PrelistingCandidateCsvError(f"{context}が空です。")
    try:
        return normalize_asin(candidate)
    except ValueError as exc:
        raise PrelistingCandidateCsvError(f"{context}のASIN形式が不正です: {exc}") from exc


def _decode_utf8_content(content: bytes, filename: str) -> str:
    if not isinstance(content, bytes):
        raise PrelistingCandidateCsvError(f"{filename}: CSV内容がbytesではありません。")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PrelistingCandidateCsvError(
            f"{filename}: UTF-8として読み込めません。"
        ) from exc
    if not text.strip():
        raise PrelistingCandidateCsvError(f"{filename}: CSV内容が空です。")
    return text


def _read_csv_rows(text: str, filename: str) -> list[tuple[int, list[str]]]:
    reader = csv.reader(StringIO(text, newline=""), strict=True)
    rows: list[tuple[int, list[str]]] = []
    try:
        for row in reader:
            rows.append((reader.line_num, row))
    except csv.Error as exc:
        raise PrelistingCandidateCsvError(
            f"{filename}: CSVとして解析できません: {exc}"
        ) from exc
    return rows


def _row_to_dict(row: PrelistingCandidateRow) -> dict[str, str]:
    return {column: getattr(row, column) for column in PRELISTING_CANDIDATE_COLUMNS}


def _is_blank_row(row: list[str]) -> bool:
    return not any(value.strip() for value in row)


def _text(value: Any) -> str:
    return "" if value is None else str(value)
