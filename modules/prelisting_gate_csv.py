"""Serialize validated pre-listing gate decisions as auditable CSV bytes."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
import json
from typing import Any

from modules.listing_inventory_parser import ListingEvidence
from modules.prelisting_candidate_csv import (
    PRELISTING_CANDIDATE_COLUMNS,
    PrelistingCandidateRow,
)
from modules.prelisting_gate import (
    METADATA_FIELDS,
    REASON_CODE_ORDER,
    SG_MARKETPLACE,
    PrelistingGateResult,
    PrelistingGateRow,
)


GATE_RESULT_SCHEMA_VERSION = "PRELISTING_GATE_RESULT_V1"
PRELISTING_GATE_RESULT_COLUMNS = (
    "gate_schema_version",
    "candidate_asin",
    "final_eligibility",
    "reason_codes",
    "marketplace",
    "candidate_schema_version",
    "source_type",
    "source_id",
    "source_asin",
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
    "guardrail_status",
    "guardrail_risk_category",
    "guardrail_matched_terms",
    "guardrail_source",
    "guardrail_note",
    "existing_listing_status",
    "existing_evidence_count",
    "existing_match_fields",
    "existing_shop_labels",
    "existing_source_files",
    "existing_source_row_numbers",
    "existing_product_ids",
    "existing_model_ids",
    "existing_stocks",
    "existing_product_names",
    "existing_evidence_json",
    "input_duplicate_status",
    "source_asin_status",
    "metadata_status",
    "metadata_missing_fields",
)

_FINAL_ELIGIBILITIES = {"ELIGIBLE", "REVIEW", "EXCLUDE"}
_GUARDRAIL_STATUSES = {"SAFE", "REVIEW", "BLOCK"}
_EXISTING_LISTING_STATUSES = {"CLEAR", "EXISTING"}
_INPUT_DUPLICATE_STATUSES = {"UNIQUE", "DUPLICATE"}
_SOURCE_ASIN_STATUSES = {"CLEAR", "SELF_ASIN"}
_METADATA_STATUSES = {"COMPLETE", "INCOMPLETE"}
_EVIDENCE_JSON_KEYS = (
    "asin",
    "marketplace",
    "shop_label",
    "source_file",
    "source_row_number",
    "match_field",
    "product_id",
    "model_id",
    "stock",
    "product_name",
    "parent_sku",
    "sku",
)
_EVIDENCE_STRING_FIELDS = tuple(
    field for field in _EVIDENCE_JSON_KEYS if field != "source_row_number"
)
_FORMULA_SAFE_COLUMNS = {
    "source_id",
    "input_title",
    "product_title",
    "brand",
    "category",
    "amazon_url",
    "source",
    "fetched_at",
    "source_note",
    "guardrail_risk_category",
    "guardrail_matched_terms",
    "guardrail_source",
    "guardrail_note",
    "existing_match_fields",
    "existing_shop_labels",
    "existing_source_files",
    "existing_product_ids",
    "existing_model_ids",
    "existing_stocks",
    "existing_product_names",
}


class PrelistingGateCsvError(RuntimeError):
    """Raised when a gate result cannot safely be serialized as CSV."""


@dataclass(frozen=True)
class PrelistingGateExportBundle:
    """All ordered CSV outputs derived from one validated gate result."""

    eligible_count: int
    review_count: int
    exclude_count: int
    audit_count: int
    eligible_csv: bytes | None
    review_csv: bytes | None
    audit_csv: bytes


def build_prelisting_gate_exports(
    result: PrelistingGateResult,
) -> PrelistingGateExportBundle:
    """Build eligible, review, and complete-audit CSV bytes in one call.

    This function validates the output contract of Phase 3A but intentionally
    does not rerun Guardrail, existing-listing matching, or eligibility logic.
    """

    try:
        rows = _validate_result(result)
        rendered_rows = tuple(_export_row(row) for row in rows)
        eligible_rows = tuple(
            rendered
            for source, rendered in zip(rows, rendered_rows)
            if source.final_eligibility == "ELIGIBLE"
        )
        review_rows = tuple(
            rendered
            for source, rendered in zip(rows, rendered_rows)
            if source.final_eligibility == "REVIEW"
        )
        return PrelistingGateExportBundle(
            eligible_count=result.eligible_count,
            review_count=result.review_count,
            exclude_count=result.exclude_count,
            audit_count=len(rows),
            eligible_csv=_serialize_csv(eligible_rows) if eligible_rows else None,
            review_csv=_serialize_csv(review_rows) if review_rows else None,
            audit_csv=_serialize_csv(rendered_rows),
        )
    except PrelistingGateCsvError:
        raise
    except (TypeError, ValueError) as exc:
        raise PrelistingGateCsvError("出品前保安ゲートCSVを安全に生成できません。") from exc


def _validate_result(result: PrelistingGateResult) -> tuple[PrelistingGateRow, ...]:
    if not isinstance(result, PrelistingGateResult):
        raise PrelistingGateCsvError("resultはPrelistingGateResultである必要があります。")
    if result.marketplace != SG_MARKETPLACE:
        raise PrelistingGateCsvError("resultのmarketplaceはSGである必要があります。")

    _require_exact_int(result.candidate_count, "candidate_count", minimum=1)
    _require_exact_int(result.eligible_count, "eligible_count", minimum=0)
    _require_exact_int(result.review_count, "review_count", minimum=0)
    _require_exact_int(result.exclude_count, "exclude_count", minimum=0)
    if not isinstance(result.rows, tuple):
        raise PrelistingGateCsvError("result.rowsはtupleである必要があります。")
    if len(result.rows) != result.candidate_count:
        raise PrelistingGateCsvError("result.rows数とcandidate_countが一致しません。")
    if (
        result.eligible_count + result.review_count + result.exclude_count
        != result.candidate_count
    ):
        raise PrelistingGateCsvError("resultの集計値合計とcandidate_countが一致しません。")

    rows: list[PrelistingGateRow] = []
    actual_counts = {status: 0 for status in _FINAL_ELIGIBILITIES}
    for row_number, row in enumerate(result.rows, 1):
        _validate_row(row, result.marketplace, row_number)
        actual_counts[row.final_eligibility] += 1
        rows.append(row)

    if (
        actual_counts["ELIGIBLE"] != result.eligible_count
        or actual_counts["REVIEW"] != result.review_count
        or actual_counts["EXCLUDE"] != result.exclude_count
    ):
        raise PrelistingGateCsvError("resultの集計値が実際の行判定と一致しません。")
    return tuple(rows)


def _validate_row(
    row: PrelistingGateRow,
    marketplace: str,
    row_number: int,
) -> None:
    if not isinstance(row, PrelistingGateRow):
        raise PrelistingGateCsvError(f"結果 {row_number}行目の型が不正です。")
    if row.marketplace != marketplace:
        raise PrelistingGateCsvError(f"結果 {row_number}行目のmarketplaceが不一致です。")
    _require_choice(row.final_eligibility, _FINAL_ELIGIBILITIES, "final_eligibility", row_number)
    _require_choice(row.guardrail_status, _GUARDRAIL_STATUSES, "guardrail_status", row_number)
    _require_choice(
        row.existing_listing_status,
        _EXISTING_LISTING_STATUSES,
        "existing_listing_status",
        row_number,
    )
    _require_choice(
        row.input_duplicate_status,
        _INPUT_DUPLICATE_STATUSES,
        "input_duplicate_status",
        row_number,
    )
    _require_choice(
        row.source_asin_status,
        _SOURCE_ASIN_STATUSES,
        "source_asin_status",
        row_number,
    )
    _require_choice(row.metadata_status, _METADATA_STATUSES, "metadata_status", row_number)
    _validate_candidate(row.candidate, row_number)
    _validate_string_fields(
        row,
        (
            "guardrail_risk_category",
            "guardrail_matched_terms",
            "guardrail_source",
            "guardrail_note",
        ),
        row_number,
    )
    _validate_ordered_tuple(
        row.reason_codes,
        REASON_CODE_ORDER,
        "reason_codes",
        row_number,
    )
    if row.final_eligibility == "ELIGIBLE" and row.reason_codes:
        raise PrelistingGateCsvError("ELIGIBLE行のreason_codesは空tupleである必要があります。")
    _validate_ordered_tuple(
        row.metadata_missing_fields,
        METADATA_FIELDS,
        "metadata_missing_fields",
        row_number,
    )
    if row.metadata_status == "COMPLETE" and row.metadata_missing_fields:
        raise PrelistingGateCsvError("COMPLETE行のmetadata_missing_fieldsは空tupleである必要があります。")
    if row.metadata_status == "INCOMPLETE" and not row.metadata_missing_fields:
        raise PrelistingGateCsvError("INCOMPLETE行のmetadata_missing_fieldsは1件以上必要です。")
    _validate_evidence(row, row_number)


def _validate_candidate(candidate: PrelistingCandidateRow, row_number: int) -> None:
    if not isinstance(candidate, PrelistingCandidateRow):
        raise PrelistingGateCsvError(f"結果 {row_number}行目のcandidate型が不正です。")
    _validate_string_fields(candidate, PRELISTING_CANDIDATE_COLUMNS, row_number)
    if not candidate.candidate_asin:
        raise PrelistingGateCsvError(f"結果 {row_number}行目のcandidate_asinが空です。")


def _validate_evidence(row: PrelistingGateRow, row_number: int) -> None:
    if not isinstance(row.existing_evidence, tuple):
        raise PrelistingGateCsvError(f"結果 {row_number}行目のexisting_evidenceはtupleである必要があります。")
    if row.existing_listing_status == "CLEAR" and row.existing_evidence:
        raise PrelistingGateCsvError("CLEAR行に既出品証跡を含められません。")
    if row.existing_listing_status == "EXISTING" and not row.existing_evidence:
        raise PrelistingGateCsvError("EXISTING行には既出品証跡が1件以上必要です。")

    for evidence_number, evidence in enumerate(row.existing_evidence, 1):
        if not isinstance(evidence, ListingEvidence):
            raise PrelistingGateCsvError(
                f"結果 {row_number}行目の既出品証跡 {evidence_number}件目の型が不正です。"
            )
        _validate_string_fields(evidence, _EVIDENCE_STRING_FIELDS, row_number)
        _require_exact_int(
            evidence.source_row_number,
            f"結果 {row_number}行目のsource_row_number",
            minimum=1,
        )
        if evidence.asin != row.candidate.candidate_asin:
            raise PrelistingGateCsvError("既出品証跡のASINがcandidate_asinと一致しません。")
        if evidence.marketplace != row.marketplace:
            raise PrelistingGateCsvError("既出品証跡のmarketplaceが行marketplaceと一致しません。")


def _require_exact_int(value: Any, label: str, *, minimum: int) -> None:
    if type(value) is not int or value < minimum:
        raise PrelistingGateCsvError(f"{label}はbool以外の{minimum}以上のintである必要があります。")


def _require_choice(value: Any, allowed: set[str], label: str, row_number: int) -> None:
    if not isinstance(value, str) or value not in allowed:
        raise PrelistingGateCsvError(f"結果 {row_number}行目の{label}が不正です。")


def _validate_string_fields(value: Any, fields: tuple[str, ...], row_number: int) -> None:
    for field in fields:
        if not isinstance(getattr(value, field), str):
            raise PrelistingGateCsvError(f"結果 {row_number}行目の{field}は文字列である必要があります。")


def _validate_ordered_tuple(
    values: Any,
    allowed_order: tuple[str, ...],
    label: str,
    row_number: int,
) -> None:
    if not isinstance(values, tuple) or any(not isinstance(value, str) for value in values):
        raise PrelistingGateCsvError(f"結果 {row_number}行目の{label}は文字列tupleである必要があります。")
    if len(values) != len(set(values)):
        raise PrelistingGateCsvError(f"結果 {row_number}行目の{label}に重複があります。")
    if any(value not in allowed_order for value in values):
        raise PrelistingGateCsvError(f"結果 {row_number}行目の{label}に許可されない値があります。")
    expected = tuple(value for value in allowed_order if value in values)
    if values != expected:
        raise PrelistingGateCsvError(f"結果 {row_number}行目の{label}の順序が不正です。")


def _export_row(row: PrelistingGateRow) -> dict[str, str]:
    candidate = row.candidate
    evidence = row.existing_evidence
    values = {
        "gate_schema_version": GATE_RESULT_SCHEMA_VERSION,
        "candidate_asin": candidate.candidate_asin,
        "final_eligibility": row.final_eligibility,
        "reason_codes": "|".join(row.reason_codes),
        "marketplace": row.marketplace,
        "candidate_schema_version": candidate.schema_version,
        "source_type": candidate.source_type,
        "source_id": candidate.source_id,
        "source_asin": candidate.source_asin,
        "input_title": candidate.input_title,
        "product_title": candidate.product_title,
        "brand": candidate.brand,
        "category": candidate.category,
        "amazon_url": candidate.amazon_url,
        "source_status": candidate.source_status,
        "source_verification": candidate.source_verification,
        "source": candidate.source,
        "fetched_at": candidate.fetched_at,
        "source_note": candidate.source_note,
        "guardrail_status": row.guardrail_status,
        "guardrail_risk_category": row.guardrail_risk_category,
        "guardrail_matched_terms": row.guardrail_matched_terms,
        "guardrail_source": row.guardrail_source,
        "guardrail_note": row.guardrail_note,
        "existing_listing_status": row.existing_listing_status,
        "existing_evidence_count": str(len(evidence)),
        "existing_match_fields": _aggregate_evidence(evidence, "match_field"),
        "existing_shop_labels": _aggregate_evidence(evidence, "shop_label"),
        "existing_source_files": _aggregate_evidence(evidence, "source_file"),
        "existing_source_row_numbers": _aggregate_evidence(evidence, "source_row_number"),
        "existing_product_ids": _aggregate_evidence(evidence, "product_id"),
        "existing_model_ids": _aggregate_evidence(evidence, "model_id"),
        "existing_stocks": _aggregate_evidence(evidence, "stock"),
        "existing_product_names": _aggregate_evidence(evidence, "product_name"),
        "existing_evidence_json": _evidence_json(evidence),
        "input_duplicate_status": row.input_duplicate_status,
        "source_asin_status": row.source_asin_status,
        "metadata_status": row.metadata_status,
        "metadata_missing_fields": "|".join(row.metadata_missing_fields),
    }
    return {
        column: _safe_formula_cell(values[column]) if column in _FORMULA_SAFE_COLUMNS else values[column]
        for column in PRELISTING_GATE_RESULT_COLUMNS
    }


def _aggregate_evidence(evidence: tuple[ListingEvidence, ...], field: str) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        text = str(getattr(item, field))
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
    return "|".join(values)


def _evidence_json(evidence: tuple[ListingEvidence, ...]) -> str:
    evidence_rows = [
        {key: getattr(item, key) for key in _EVIDENCE_JSON_KEYS}
        for item in evidence
    ]
    return json.dumps(evidence_rows, ensure_ascii=False, separators=(",", ":"))


def _safe_formula_cell(value: str) -> str:
    if not value:
        return value
    if value[0] in {"\t", "\r", "\n"}:
        return "'" + value
    for character in value:
        if character.isspace():
            continue
        return "'" + value if character in {"=", "+", "-", "@"} else value
    return value


def _serialize_csv(rows: tuple[dict[str, str], ...]) -> bytes:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=PRELISTING_GATE_RESULT_COLUMNS,
        extrasaction="raise",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")
