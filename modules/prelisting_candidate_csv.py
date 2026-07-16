"""Convert and validate the shared pre-listing candidate CSV contract."""

from __future__ import annotations

import csv
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
)


class PrelistingCandidateCsvError(RuntimeError):
    """Raised when a pre-listing candidate CSV cannot be trusted."""


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
    """Convert only FOUND and KEEPA_VERIFIED Resolver rows without API access."""

    materialized_rows = list(rows)
    output_rows: list[PrelistingCandidateRow] = []
    for row_number, row in enumerate(materialized_rows, 1):
        values = _mapping_values(row, f"Resolver入力 {row_number}行目")
        status = values["status"].strip().upper()
        verification = values["verification"].strip().upper()
        if status != RESOLVER_FOUND_STATUS or verification != RESOLVER_VERIFICATION:
            continue

        output_rows.append(
            _canonicalize_row(
                PrelistingCandidateRow(
                    schema_version=PRELISTING_CANDIDATE_SCHEMA_VERSION,
                    source_type=RESOLVER_SOURCE_TYPE,
                    source_id=values["source_id"],
                    source_asin="",
                    candidate_asin=values["asin"],
                    input_title=values["input_title"],
                    product_title=values["keepa_title"],
                    brand=values["keepa_brand"],
                    category=values["keepa_category"],
                    amazon_url=values["amazon_url"],
                    source_status=RESOLVER_FOUND_STATUS,
                    source_verification=RESOLVER_VERIFICATION,
                    source=RESOLVER_SOURCE,
                    fetched_at=values["keepa_fetched_at"],
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
        if values["source_verification"] != RESOLVER_VERIFICATION:
            raise PrelistingCandidateCsvError(
                f"{context}: Resolverのsource_verificationはKEEPA_VERIFIEDである必要があります。"
            )
        if source != RESOLVER_SOURCE:
            raise PrelistingCandidateCsvError(
                f"{context}: Resolverのsourceは{RESOLVER_SOURCE}である必要があります。"
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
