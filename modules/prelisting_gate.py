"""Evaluate validated pre-listing candidates without UI, CSV output, or API calls."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata
from typing import Any, Iterable, Mapping

from modules.guardrails import GuardrailDictionaryError, apply_guardrails
from modules.keepa_client import normalize_asin
from modules.listing_inventory_parser import (
    ListingEvidence,
    ListingInventoryFileResult,
    ListingInventoryParseError,
    build_existing_asin_index,
    normalize_marketplace,
    validate_inventory_filename_marketplace,
)
from modules.prelisting_candidate_csv import (
    EXPANSION_SOURCE_TYPE,
    RESOLVER_SOURCE_TYPE,
    PrelistingCandidateFileResult,
    PrelistingCandidateRow,
)


SG_MARKETPLACE = "SG"
PH_MARKETPLACE = "PH"
ALLOWED_SOURCE_TYPES = {EXPANSION_SOURCE_TYPE, RESOLVER_SOURCE_TYPE}
GUARDRAIL_COLUMNS = (
    "guardrail_status",
    "guardrail_risk_category",
    "guardrail_matched_terms",
    "guardrail_source",
    "guardrail_note",
)
GUARDRAIL_STATUSES = {"SAFE", "REVIEW", "BLOCK"}
METADATA_FIELDS = ("product_title", "brand", "category")
MISSING_METADATA_VALUES = {"", "none", "null", "nan", "n/a", "unknown", "不明"}
REASON_CODE_ORDER = (
    "GUARDRAIL_BLOCK",
    "EXISTING_ASIN",
    "INPUT_DUPLICATE",
    "SELF_ASIN",
    "GUARDRAIL_REVIEW",
    "METADATA_INCOMPLETE",
)


class PrelistingGateError(RuntimeError):
    """Raised when the pre-listing gate cannot safely produce a result."""


@dataclass(frozen=True)
class PrelistingGateRow:
    """One fully evaluated candidate, preserving source data and all evidence."""

    candidate: PrelistingCandidateRow
    marketplace: str
    guardrail_status: str
    guardrail_risk_category: str
    guardrail_matched_terms: str
    guardrail_source: str
    guardrail_note: str
    existing_listing_status: str
    existing_evidence: tuple[ListingEvidence, ...]
    input_duplicate_status: str
    source_asin_status: str
    metadata_status: str
    metadata_missing_fields: tuple[str, ...]
    final_eligibility: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class PrelistingGateResult:
    """The ordered decision result for one supported-market pre-listing file."""

    marketplace: str
    candidate_count: int
    eligible_count: int
    review_count: int
    exclude_count: int
    rows: tuple[PrelistingGateRow, ...]


@dataclass(frozen=True)
class _ValidatedCandidate:
    candidate: PrelistingCandidateRow
    candidate_asin: str
    source_asin: str


def evaluate_prelisting_gate(
    candidates: PrelistingCandidateFileResult,
    inventories: Iterable[ListingInventoryFileResult],
    *,
    marketplace: str,
    expected_shop_count: int,
) -> PrelistingGateResult:
    """Return final eligibility for validated SG or PH candidates and inventory evidence.

    This function is intentionally fail-closed: an invalid input contract or a
    Guardrail contract error raises ``PrelistingGateError`` instead of returning
    an empty or partially trusted result.
    """

    try:
        normalized_marketplace = _normalize_supported_marketplace(marketplace, "marketplace")
        _validate_expected_shop_count(expected_shop_count)
        candidate_rows = _validate_candidates(candidates)
        inventory_results = tuple(inventories)
        _validate_inventories(
            inventory_results,
            marketplace=normalized_marketplace,
            expected_shop_count=expected_shop_count,
        )
        existing_index = _build_existing_index(inventory_results)
        guarded_rows = _apply_and_validate_guardrails(
            candidate_rows,
            marketplace=normalized_marketplace,
        )
        result_rows = _evaluate_rows(
            candidate_rows,
            guarded_rows,
            existing_index,
            marketplace=normalized_marketplace,
        )
        return _build_result(normalized_marketplace, result_rows)
    except PrelistingGateError:
        raise
    except Exception as exc:
        raise PrelistingGateError("出品前保安ゲートの内部処理に失敗しました。") from exc


def _validate_expected_shop_count(expected_shop_count: int) -> None:
    if type(expected_shop_count) is not int or expected_shop_count < 1:
        raise PrelistingGateError("expected_shop_countはbool以外の1以上のintで指定してください。")


def _validate_candidates(
    candidates: PrelistingCandidateFileResult,
) -> tuple[_ValidatedCandidate, ...]:
    if not isinstance(candidates, PrelistingCandidateFileResult):
        raise PrelistingGateError("candidatesはPrelistingCandidateFileResultである必要があります。")
    if candidates.source_type not in ALLOWED_SOURCE_TYPES:
        raise PrelistingGateError("候補ファイルのsource_typeが不正です。")

    try:
        rows = tuple(candidates.rows)
    except TypeError as exc:
        raise PrelistingGateError("候補行を反復できません。") from exc
    if not rows:
        raise PrelistingGateError("候補行が0件です。")

    validated_rows: list[_ValidatedCandidate] = []
    for row_number, candidate in enumerate(rows, 1):
        if not isinstance(candidate, PrelistingCandidateRow):
            raise PrelistingGateError(f"候補 {row_number}行目の型が不正です。")
        if candidate.source_type != candidates.source_type:
            raise PrelistingGateError(f"候補 {row_number}行目のsource_typeがファイルと一致しません。")
        if candidate.source_type not in ALLOWED_SOURCE_TYPES:
            raise PrelistingGateError(f"候補 {row_number}行目のsource_typeが不正です。")

        candidate_asin = _normalize_required_asin(
            candidate.candidate_asin,
            f"候補 {row_number}行目のcandidate_asin",
        )
        source_asin = ""
        if candidate.source_type == EXPANSION_SOURCE_TYPE:
            source_asin = _normalize_required_asin(
                candidate.source_asin,
                f"候補 {row_number}行目のsource_asin",
            )
        elif _normalized_text(candidate.source_asin):
            source_asin = _normalize_required_asin(
                candidate.source_asin,
                f"候補 {row_number}行目のsource_asin",
            )

        validated_rows.append(
            _ValidatedCandidate(
                candidate=candidate,
                candidate_asin=candidate_asin,
                source_asin=source_asin,
            )
        )
    return tuple(validated_rows)


def _validate_inventories(
    inventories: tuple[ListingInventoryFileResult, ...],
    *,
    marketplace: str,
    expected_shop_count: int,
) -> None:
    if len(inventories) != expected_shop_count:
        raise PrelistingGateError(
            "既出品ファイル数がexpected_shop_countと一致しません。"
        )

    shop_labels: set[str] = set()
    source_files: set[str] = set()
    for file_number, inventory in enumerate(inventories, 1):
        if not isinstance(inventory, ListingInventoryFileResult):
            raise PrelistingGateError(f"既出品ファイル {file_number}件目の型が不正です。")
        if _normalize_supported_marketplace(
            inventory.marketplace,
            f"既出品ファイル {file_number}件目のmarketplace",
        ) != marketplace:
            raise PrelistingGateError("既出品ファイルのmarketplaceが判定対象と一致しません。")

        shop_label = _normalized_identity(inventory.shop_label)
        source_file = _normalized_identity(inventory.source_file)
        if not shop_label:
            raise PrelistingGateError(f"既出品ファイル {file_number}件目のshop_labelが空です。")
        if not source_file:
            raise PrelistingGateError(f"既出品ファイル {file_number}件目のsource_fileが空です。")
        try:
            validate_inventory_filename_marketplace(inventory.source_file, marketplace)
        except ListingInventoryParseError as exc:
            raise PrelistingGateError(
                f"既出品ファイル {file_number}件目のsource_fileの市場表記が不正です。"
            ) from exc
        if shop_label in shop_labels:
            raise PrelistingGateError("既出品ファイルのshop_labelが重複しています。")
        if source_file in source_files:
            raise PrelistingGateError("既出品ファイルのsource_fileが重複しています。")
        shop_labels.add(shop_label)
        source_files.add(source_file)
        _validate_inventory_contents(inventory, file_number, marketplace)


def _validate_inventory_contents(
    inventory: ListingInventoryFileResult,
    file_number: int,
    marketplace: str,
) -> None:
    if type(inventory.data_row_count) is not int or inventory.data_row_count < 0:
        raise PrelistingGateError(f"既出品ファイル {file_number}件目のdata_row_countが不正です。")
    if type(inventory.unique_asin_count) is not int or inventory.unique_asin_count < 0:
        raise PrelistingGateError(f"既出品ファイル {file_number}件目のunique_asin_countが不正です。")
    if not isinstance(inventory.evidence_records, tuple):
        raise PrelistingGateError(f"既出品ファイル {file_number}件目のevidence_recordsが不正です。")

    if inventory.data_row_count == 0:
        if inventory.unique_asin_count or inventory.evidence_records:
            raise PrelistingGateError(
                f"既出品ファイル {file_number}件目の0件inventory契約が不正です。"
            )
        return

    if not inventory.evidence_records:
        raise PrelistingGateError(
            f"既出品ファイル {file_number}件目は商品行があるのに有効なASIN根拠がありません。"
        )

    unique_asins: set[str] = set()
    for evidence_number, evidence in enumerate(inventory.evidence_records, 1):
        if not isinstance(evidence, ListingEvidence):
            raise PrelistingGateError(
                f"既出品ファイル {file_number}件目の証跡 {evidence_number}件目の型が不正です。"
            )
        if _normalize_supported_marketplace(
            evidence.marketplace,
            f"既出品ファイル {file_number}件目の証跡 {evidence_number}件目のmarketplace",
        ) != marketplace:
            raise PrelistingGateError("既出品証跡のmarketplaceが判定対象と一致しません。")
        if _normalized_identity(evidence.shop_label) != _normalized_identity(inventory.shop_label):
            raise PrelistingGateError("既出品証跡のshop_labelが既出品ファイルと一致しません。")
        if _normalized_identity(evidence.source_file) != _normalized_identity(inventory.source_file):
            raise PrelistingGateError("既出品証跡のsource_fileが既出品ファイルと一致しません。")
        unique_asins.add(
            _normalize_required_asin(
                evidence.asin,
                f"既出品ファイル {file_number}件目の証跡 {evidence_number}件目のASIN",
            )
        )
    if not unique_asins or inventory.unique_asin_count != len(unique_asins):
        raise PrelistingGateError(f"既出品ファイル {file_number}件目のASIN集計が不正です。")


def _build_existing_index(
    inventories: tuple[ListingInventoryFileResult, ...],
) -> dict[str, list[ListingEvidence]]:
    try:
        return build_existing_asin_index(inventories)
    except ListingInventoryParseError as exc:
        raise PrelistingGateError("既出品ASINインデックスを構築できません。") from exc


def _apply_and_validate_guardrails(
    candidate_rows: tuple[_ValidatedCandidate, ...],
    *,
    marketplace: str,
) -> tuple[dict[str, str], ...]:
    guardrail_inputs = [
        {
            "gate_row_id": f"G{row_number:04d}",
            "candidate_asin": row.candidate_asin,
            "brand": row.candidate.brand,
            "product_title": row.candidate.product_title,
            "category": row.candidate.category,
        }
        for row_number, row in enumerate(candidate_rows, 1)
    ]
    try:
        guarded_rows = tuple(apply_guardrails(guardrail_inputs, marketplace=marketplace))
    except GuardrailDictionaryError as exc:
        raise PrelistingGateError("Guardrail辞書を読み込めません。") from exc

    if len(guarded_rows) != len(candidate_rows):
        raise PrelistingGateError("Guardrail出力件数が候補件数と一致しません。")

    validated_rows: list[dict[str, str]] = []
    for row_number, (candidate, guarded_row) in enumerate(
        zip(candidate_rows, guarded_rows), 1
    ):
        if not isinstance(guarded_row, Mapping):
            raise PrelistingGateError(f"Guardrail出力 {row_number}行目の型が不正です。")
        expected_gate_row_id = f"G{row_number:04d}"
        if guarded_row.get("gate_row_id") != expected_gate_row_id:
            raise PrelistingGateError(f"Guardrail出力 {row_number}行目のgate_row_idが不正です。")
        if guarded_row.get("candidate_asin") != candidate.candidate_asin:
            raise PrelistingGateError(f"Guardrail出力 {row_number}行目のcandidate_asinが不一致です。")
        missing_columns = [column for column in GUARDRAIL_COLUMNS if column not in guarded_row]
        if missing_columns:
            raise PrelistingGateError(
                f"Guardrail出力 {row_number}行目の必須列が不足しています: "
                f"{', '.join(missing_columns)}"
            )
        status = _normalized_text(guarded_row["guardrail_status"]).upper()
        if status not in GUARDRAIL_STATUSES:
            raise PrelistingGateError(f"Guardrail出力 {row_number}行目のstatusが不正です。")
        validated_rows.append(
            {
                "guardrail_status": status,
                "guardrail_risk_category": _text(guarded_row["guardrail_risk_category"]),
                "guardrail_matched_terms": _text(guarded_row["guardrail_matched_terms"]),
                "guardrail_source": _text(guarded_row["guardrail_source"]),
                "guardrail_note": _text(guarded_row["guardrail_note"]),
            }
        )
    return tuple(validated_rows)


def _evaluate_rows(
    candidate_rows: tuple[_ValidatedCandidate, ...],
    guarded_rows: tuple[dict[str, str], ...],
    existing_index: Mapping[str, list[ListingEvidence]],
    *,
    marketplace: str,
) -> tuple[PrelistingGateRow, ...]:
    seen_asins: set[str] = set()
    result_rows: list[PrelistingGateRow] = []

    for candidate, guarded_row in zip(candidate_rows, guarded_rows):
        input_duplicate_status = "DUPLICATE" if candidate.candidate_asin in seen_asins else "UNIQUE"
        seen_asins.add(candidate.candidate_asin)

        source_asin_status = (
            "SELF_ASIN"
            if candidate.candidate.source_type == EXPANSION_SOURCE_TYPE
            and candidate.candidate_asin == candidate.source_asin
            else "CLEAR"
        )
        existing_evidence = tuple(existing_index.get(candidate.candidate_asin, []))
        existing_listing_status = "EXISTING" if existing_evidence else "CLEAR"
        metadata_missing_fields = _metadata_missing_fields(candidate.candidate)
        metadata_status = "INCOMPLETE" if metadata_missing_fields else "COMPLETE"
        reason_codes = _reason_codes(
            guardrail_status=guarded_row["guardrail_status"],
            existing_listing_status=existing_listing_status,
            input_duplicate_status=input_duplicate_status,
            source_asin_status=source_asin_status,
            metadata_status=metadata_status,
        )
        final_eligibility = _final_eligibility(
            guardrail_status=guarded_row["guardrail_status"],
            existing_listing_status=existing_listing_status,
            input_duplicate_status=input_duplicate_status,
            source_asin_status=source_asin_status,
            metadata_status=metadata_status,
        )
        result_rows.append(
            PrelistingGateRow(
                candidate=candidate.candidate,
                marketplace=marketplace,
                guardrail_status=guarded_row["guardrail_status"],
                guardrail_risk_category=guarded_row["guardrail_risk_category"],
                guardrail_matched_terms=guarded_row["guardrail_matched_terms"],
                guardrail_source=guarded_row["guardrail_source"],
                guardrail_note=guarded_row["guardrail_note"],
                existing_listing_status=existing_listing_status,
                existing_evidence=existing_evidence,
                input_duplicate_status=input_duplicate_status,
                source_asin_status=source_asin_status,
                metadata_status=metadata_status,
                metadata_missing_fields=metadata_missing_fields,
                final_eligibility=final_eligibility,
                reason_codes=reason_codes,
            )
        )
    return tuple(result_rows)


def _metadata_missing_fields(candidate: PrelistingCandidateRow) -> tuple[str, ...]:
    return tuple(
        field
        for field in METADATA_FIELDS
        if _normalized_metadata_value(getattr(candidate, field)) in MISSING_METADATA_VALUES
    )


def _reason_codes(
    *,
    guardrail_status: str,
    existing_listing_status: str,
    input_duplicate_status: str,
    source_asin_status: str,
    metadata_status: str,
) -> tuple[str, ...]:
    active_codes = {
        "GUARDRAIL_BLOCK": guardrail_status == "BLOCK",
        "EXISTING_ASIN": existing_listing_status == "EXISTING",
        "INPUT_DUPLICATE": input_duplicate_status == "DUPLICATE",
        "SELF_ASIN": source_asin_status == "SELF_ASIN",
        "GUARDRAIL_REVIEW": guardrail_status == "REVIEW",
        "METADATA_INCOMPLETE": metadata_status == "INCOMPLETE",
    }
    return tuple(code for code in REASON_CODE_ORDER if active_codes[code])


def _final_eligibility(
    *,
    guardrail_status: str,
    existing_listing_status: str,
    input_duplicate_status: str,
    source_asin_status: str,
    metadata_status: str,
) -> str:
    if (
        guardrail_status == "BLOCK"
        or existing_listing_status == "EXISTING"
        or input_duplicate_status == "DUPLICATE"
        or source_asin_status == "SELF_ASIN"
    ):
        return "EXCLUDE"
    if guardrail_status == "REVIEW" or metadata_status == "INCOMPLETE":
        return "REVIEW"
    if (
        guardrail_status == "SAFE"
        and existing_listing_status == "CLEAR"
        and input_duplicate_status == "UNIQUE"
        and source_asin_status == "CLEAR"
        and metadata_status == "COMPLETE"
    ):
        return "ELIGIBLE"
    raise PrelistingGateError("最終適格性を安全に決定できません。")


def _build_result(
    marketplace: str,
    rows: tuple[PrelistingGateRow, ...],
) -> PrelistingGateResult:
    eligible_count = sum(row.final_eligibility == "ELIGIBLE" for row in rows)
    review_count = sum(row.final_eligibility == "REVIEW" for row in rows)
    exclude_count = sum(row.final_eligibility == "EXCLUDE" for row in rows)
    if len(rows) != eligible_count + review_count + exclude_count:
        raise PrelistingGateError("判定サマリーの件数が候補件数と一致しません。")
    return PrelistingGateResult(
        marketplace=marketplace,
        candidate_count=len(rows),
        eligible_count=eligible_count,
        review_count=review_count,
        exclude_count=exclude_count,
        rows=rows,
    )


def _normalize_supported_marketplace(value: Any, context: str) -> str:
    try:
        return normalize_marketplace(value, context=context)
    except ListingInventoryParseError as exc:
        raise PrelistingGateError(f"{context}が不正です。") from exc


def _normalize_required_asin(value: Any, context: str) -> str:
    candidate = _normalized_text(value).upper()
    if not candidate:
        raise PrelistingGateError(f"{context}が空です。")
    try:
        return normalize_asin(candidate)
    except ValueError as exc:
        raise PrelistingGateError(f"{context}のASIN形式が不正です。") from exc


def _normalized_identity(value: Any) -> str:
    return _normalized_text(value).casefold()


def _normalized_metadata_value(value: Any) -> str:
    return _normalized_text(value).casefold()


def _normalized_text(value: Any) -> str:
    if value is None:
        return ""
    return unicodedata.normalize("NFKC", str(value)).strip()


def _text(value: Any) -> str:
    return "" if value is None else str(value)
