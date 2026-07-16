from __future__ import annotations

import csv
from dataclasses import replace
from io import StringIO
import json

import pytest

import modules.prelisting_gate_csv as gate_csv
from modules.listing_inventory_parser import ListingEvidence
from modules.prelisting_candidate_csv import (
    EXPANSION_SOURCE_TYPE,
    PRELISTING_CANDIDATE_SCHEMA_VERSION,
    PrelistingCandidateRow,
)
from modules.prelisting_gate import PrelistingGateResult, PrelistingGateRow


EXPECTED_COLUMNS = (
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
FORMULA_SAFE_COLUMNS = {
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


def candidate(asin: str = "B000000001", **overrides: str) -> PrelistingCandidateRow:
    values = {
        "schema_version": PRELISTING_CANDIDATE_SCHEMA_VERSION,
        "source_type": EXPANSION_SOURCE_TYPE,
        "source_id": "synthetic-source-id",
        "source_asin": "B000000099",
        "candidate_asin": asin,
        "input_title": "Synthetic input title",
        "product_title": "Synthetic product title",
        "brand": "Synthetic brand",
        "category": "Synthetic category",
        "amazon_url": "",
        "source_status": "",
        "source_verification": "",
        "source": "synthetic-source",
        "fetched_at": "2026-07-16T00:00:00+00:00",
        "source_note": "Synthetic note",
    }
    values.update(overrides)
    return PrelistingCandidateRow(**values)


def evidence(asin: str, **overrides: object) -> ListingEvidence:
    values = {
        "asin": asin,
        "marketplace": "SG",
        "shop_label": "Shop A",
        "source_file": "shop-a.csv",
        "source_row_number": 2,
        "match_field": "Parent SKU",
        "product_id": "P-001",
        "model_id": "M-001",
        "stock": "1",
        "product_name": "Synthetic inventory product",
        "parent_sku": asin,
        "sku": "",
    }
    values.update(overrides)
    return ListingEvidence(**values)


def gate_row(
    asin: str = "B000000001",
    *,
    candidate_row: PrelistingCandidateRow | None = None,
    final_eligibility: str = "ELIGIBLE",
    guardrail_status: str = "SAFE",
    existing_listing_status: str = "CLEAR",
    evidence_records: tuple[ListingEvidence, ...] = (),
    input_duplicate_status: str = "UNIQUE",
    source_asin_status: str = "CLEAR",
    metadata_status: str = "COMPLETE",
    metadata_missing_fields: tuple[str, ...] = (),
    reason_codes: tuple[str, ...] = (),
    **overrides: object,
) -> PrelistingGateRow:
    values = {
        "candidate": candidate_row or candidate(asin),
        "marketplace": "SG",
        "guardrail_status": guardrail_status,
        "guardrail_risk_category": "",
        "guardrail_matched_terms": "",
        "guardrail_source": "",
        "guardrail_note": "Synthetic guardrail note",
        "existing_listing_status": existing_listing_status,
        "existing_evidence": evidence_records,
        "input_duplicate_status": input_duplicate_status,
        "source_asin_status": source_asin_status,
        "metadata_status": metadata_status,
        "metadata_missing_fields": metadata_missing_fields,
        "final_eligibility": final_eligibility,
        "reason_codes": reason_codes,
    }
    values.update(overrides)
    return PrelistingGateRow(**values)


def gate_result(
    rows: tuple[PrelistingGateRow, ...] | list[PrelistingGateRow],
    **overrides: object,
) -> PrelistingGateResult:
    rows = tuple(rows)
    values = {
        "marketplace": "SG",
        "candidate_count": len(rows),
        "eligible_count": sum(row.final_eligibility == "ELIGIBLE" for row in rows),
        "review_count": sum(row.final_eligibility == "REVIEW" for row in rows),
        "exclude_count": sum(row.final_eligibility == "EXCLUDE" for row in rows),
        "rows": rows,
    }
    values.update(overrides)
    return PrelistingGateResult(**values)


def csv_rows(content: bytes) -> list[dict[str, str]]:
    assert content.startswith(b"\xef\xbb\xbf")
    return list(csv.DictReader(StringIO(content.decode("utf-8-sig"))))


def csv_header(content: bytes) -> list[str]:
    return content.decode("utf-8-sig").splitlines()[0].split(",")


def existing_result() -> PrelistingGateResult:
    asin = "B000000001"
    row = gate_row(
        asin,
        final_eligibility="EXCLUDE",
        existing_listing_status="EXISTING",
        evidence_records=(evidence(asin),),
        reason_codes=("EXISTING_ASIN",),
    )
    return gate_result([row])


def test_builds_all_exports_with_fixed_header_order_and_duplicate_asins():
    rows = (
        gate_row("B000000001"),
        gate_row(
            "B000000001",
            final_eligibility="REVIEW",
            guardrail_status="REVIEW",
            input_duplicate_status="DUPLICATE",
            reason_codes=("GUARDRAIL_REVIEW",),
        ),
        gate_row(
            "B000000003",
            final_eligibility="EXCLUDE",
            guardrail_status="BLOCK",
            reason_codes=("GUARDRAIL_BLOCK",),
        ),
    )

    bundle = gate_csv.build_prelisting_gate_exports(gate_result(rows))

    assert bundle.eligible_count == 1
    assert bundle.review_count == 1
    assert bundle.exclude_count == 1
    assert bundle.audit_count == 3
    assert bundle.eligible_csv is not None
    assert bundle.review_csv is not None
    assert not hasattr(bundle, "exclude_csv")
    assert gate_csv.PRELISTING_GATE_RESULT_COLUMNS == EXPECTED_COLUMNS
    assert csv_header(bundle.audit_csv) == list(EXPECTED_COLUMNS)
    assert len(csv_header(bundle.audit_csv)) == 39
    assert csv_header(bundle.eligible_csv) == csv_header(bundle.audit_csv)
    assert csv_header(bundle.review_csv) == csv_header(bundle.audit_csv)
    assert [row["candidate_asin"] for row in csv_rows(bundle.audit_csv)] == [
        "B000000001",
        "B000000001",
        "B000000003",
    ]
    assert [row["final_eligibility"] for row in csv_rows(bundle.eligible_csv)] == ["ELIGIBLE"]
    assert [row["final_eligibility"] for row in csv_rows(bundle.review_csv)] == ["REVIEW"]


def test_empty_eligible_or_review_export_is_none_while_audit_is_generated():
    no_eligible = gate_result(
        [
            gate_row(
                "B000000001",
                final_eligibility="REVIEW",
                guardrail_status="REVIEW",
                reason_codes=("GUARDRAIL_REVIEW",),
            ),
            gate_row(
                "B000000002",
                final_eligibility="EXCLUDE",
                guardrail_status="BLOCK",
                reason_codes=("GUARDRAIL_BLOCK",),
            ),
        ]
    )
    no_review = gate_result(
        [
            gate_row("B000000003"),
            gate_row(
                "B000000004",
                final_eligibility="EXCLUDE",
                guardrail_status="BLOCK",
                reason_codes=("GUARDRAIL_BLOCK",),
            ),
        ]
    )

    no_eligible_bundle = gate_csv.build_prelisting_gate_exports(no_eligible)
    no_review_bundle = gate_csv.build_prelisting_gate_exports(no_review)

    assert no_eligible_bundle.eligible_csv is None
    assert len(csv_rows(no_eligible_bundle.audit_csv)) == 2
    assert no_review_bundle.review_csv is None
    assert len(csv_rows(no_review_bundle.audit_csv)) == 2


def test_csv_contract_round_trips_special_characters_empty_cells_and_lf():
    special_candidate = candidate(
        "B000000001",
        source_id="",
        input_title='日本語, "引用符"\n改行',
        product_title='商品, "引用符"\n改行',
        brand="日本語ブランド",
        category="",
        source_note='メモ, "引用符"\n改行',
    )
    bundle = gate_csv.build_prelisting_gate_exports(
        gate_result([gate_row(candidate_row=special_candidate)])
    )

    assert bundle.eligible_csv is not None
    assert b"\r\n" not in bundle.eligible_csv
    row = csv_rows(bundle.eligible_csv)[0]
    assert row["input_title"] == '日本語, "引用符"\n改行'
    assert row["product_title"] == '商品, "引用符"\n改行'
    assert row["source_note"] == 'メモ, "引用符"\n改行'
    assert row["source_id"] == ""
    assert row["category"] == ""
    assert row["gate_schema_version"] == "PRELISTING_GATE_RESULT_V1"


def test_reason_and_metadata_tuples_keep_order_and_empty_tuples_are_blank():
    asin = "B000000001"
    excluded = gate_row(
        asin,
        final_eligibility="EXCLUDE",
        existing_listing_status="EXISTING",
        evidence_records=(evidence(asin),),
        metadata_status="INCOMPLETE",
        metadata_missing_fields=("product_title", "category"),
        reason_codes=("EXISTING_ASIN", "METADATA_INCOMPLETE"),
    )
    bundle = gate_csv.build_prelisting_gate_exports(gate_result([excluded]))
    row = csv_rows(bundle.audit_csv)[0]

    assert row["reason_codes"] == "EXISTING_ASIN|METADATA_INCOMPLETE"
    assert row["metadata_missing_fields"] == "product_title|category"

    empty_row = csv_rows(
        gate_csv.build_prelisting_gate_exports(gate_result([gate_row()])).audit_csv
    )[0]
    assert empty_row["reason_codes"] == ""
    assert empty_row["metadata_missing_fields"] == ""


def test_zero_and_one_evidence_are_exported_without_loss():
    zero_row = csv_rows(
        gate_csv.build_prelisting_gate_exports(gate_result([gate_row()])).audit_csv
    )[0]
    assert zero_row["existing_evidence_count"] == "0"
    assert zero_row["existing_evidence_json"] == "[]"
    assert zero_row["existing_match_fields"] == ""

    asin = "B000000002"
    one_evidence = evidence(asin, stock="0", product_id="0001", model_id="0002")
    one_row = gate_row(
        asin,
        final_eligibility="EXCLUDE",
        existing_listing_status="EXISTING",
        evidence_records=(one_evidence,),
        reason_codes=("EXISTING_ASIN",),
    )
    exported = csv_rows(
        gate_csv.build_prelisting_gate_exports(gate_result([one_row])).audit_csv
    )[0]
    evidence_json = json.loads(exported["existing_evidence_json"])

    assert exported["existing_evidence_count"] == "1"
    assert evidence_json[0]["stock"] == "0"
    assert evidence_json[0]["product_id"] == "0001"
    assert evidence_json[0]["model_id"] == "0002"


def test_multiple_evidence_json_and_aggregate_columns_preserve_order_and_values():
    asin = "B000000001"
    records = (
        evidence(
            asin,
            shop_label="Shop A",
            source_file="shop-a.csv",
            source_row_number=7,
            match_field="Parent SKU",
            product_id="001",
            model_id="M-1",
            stock="0",
            product_name='日本語, "引用符"\n改行',
            parent_sku=asin,
            sku="",
        ),
        evidence(
            asin,
            shop_label="Shop A",
            source_file="shop-a.csv",
            source_row_number=7,
            match_field="SKU",
            product_id="001",
            model_id="",
            stock="0",
            product_name='日本語, "引用符"\n改行',
            parent_sku=asin,
            sku=asin,
        ),
        evidence(
            asin,
            shop_label="Shop B",
            source_file="shop-b.csv",
            source_row_number=8,
            match_field="Parent SKU",
            product_id="002",
            model_id="M-2",
            stock="5",
            product_name="Second product",
            parent_sku=asin,
            sku="",
        ),
    )
    row = gate_row(
        asin,
        final_eligibility="EXCLUDE",
        existing_listing_status="EXISTING",
        evidence_records=records,
        reason_codes=("EXISTING_ASIN",),
    )
    exported = csv_rows(
        gate_csv.build_prelisting_gate_exports(gate_result([row])).audit_csv
    )[0]
    evidence_json = json.loads(exported["existing_evidence_json"])

    assert exported["existing_evidence_count"] == "3"
    assert exported["existing_match_fields"] == "Parent SKU|SKU"
    assert exported["existing_shop_labels"] == "Shop A|Shop B"
    assert exported["existing_source_files"] == "shop-a.csv|shop-b.csv"
    assert exported["existing_source_row_numbers"] == "7|8"
    assert exported["existing_product_ids"] == "001|002"
    assert exported["existing_model_ids"] == "M-1|M-2"
    assert exported["existing_stocks"] == "0|5"
    assert exported["existing_product_names"] == '日本語, "引用符"\n改行|Second product'
    assert len(evidence_json) == 3
    assert list(evidence_json[0]) == [
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
    ]
    assert [item["match_field"] for item in evidence_json] == ["Parent SKU", "SKU", "Parent SKU"]
    assert evidence_json[0]["parent_sku"] == asin
    assert evidence_json[1]["sku"] == asin
    assert evidence_json[0]["product_name"] == '日本語, "引用符"\n改行'
    assert isinstance(evidence_json[0]["source_row_number"], int)
    assert all(isinstance(item["product_id"], str) for item in evidence_json)
    assert all(isinstance(item["model_id"], str) for item in evidence_json)
    assert all(isinstance(item["stock"], str) for item in evidence_json)


@pytest.mark.parametrize(
    "dangerous",
    ["=SUM(1,2)", "+CMD", "-CMD", "@CMD", "  +CMD", "\tCMD", "\rCMD", "\nCMD"],
)
def test_formula_safety_prefixes_dangerous_free_text_cells(dangerous):
    row = gate_row(candidate_row=candidate(source_id=dangerous))
    exported = csv_rows(
        gate_csv.build_prelisting_gate_exports(gate_result([row])).audit_csv
    )[0]

    assert exported["source_id"] == "'" + dangerous


def test_formula_safety_applies_to_all_target_columns_without_mutating_json_or_models():
    asin = "B000000001"
    source_candidate = candidate(
        asin,
        source_id="=source-id",
        input_title="+input",
        product_title="-title",
        brand="@brand",
        category="  +category",
        amazon_url="\turl",
        source="\rsource",
        fetched_at="\nfetched",
        source_note="normal note",
    )
    source_evidence = evidence(
        asin,
        match_field="=match",
        shop_label="+shop",
        source_file="-file",
        product_id="@product",
        model_id="  +model",
        stock="\tstock",
        product_name="\nname",
    )
    source_row = gate_row(
        asin,
        candidate_row=source_candidate,
        final_eligibility="EXCLUDE",
        existing_listing_status="EXISTING",
        evidence_records=(source_evidence,),
        reason_codes=("EXISTING_ASIN",),
        guardrail_risk_category="=risk",
        guardrail_matched_terms="+terms",
        guardrail_source="-guardrail-source",
        guardrail_note="@guardrail-note",
    )
    original_candidate = source_candidate
    original_evidence = source_evidence

    exported = csv_rows(
        gate_csv.build_prelisting_gate_exports(gate_result([source_row])).audit_csv
    )[0]
    evidence_json = json.loads(exported["existing_evidence_json"])

    assert gate_csv._FORMULA_SAFE_COLUMNS == FORMULA_SAFE_COLUMNS
    for column in FORMULA_SAFE_COLUMNS:
        if column == "source_note":
            assert exported[column] == "normal note"
        else:
            assert exported[column].startswith("'")
    assert exported["candidate_asin"] == asin
    assert exported["existing_evidence_json"].startswith("[")
    assert evidence_json[0]["match_field"] == "=match"
    assert evidence_json[0]["stock"] == "\tstock"
    assert source_candidate == original_candidate
    assert source_evidence == original_evidence


@pytest.mark.parametrize(
    "mutate",
    [
        lambda base: "not-a-result",
        lambda base: replace(base, marketplace="PH"),
        lambda base: replace(base, candidate_count=True),
        lambda base: replace(base, candidate_count=0),
        lambda base: replace(base, rows=list(base.rows)),
        lambda base: replace(base, candidate_count=2, eligible_count=2),
        lambda base: replace(base, eligible_count=0, review_count=1),
        lambda base: replace(base, rows=("not-a-row",)),
        lambda base: replace(base, rows=(replace(base.rows[0], marketplace="PH"),)),
        lambda base: replace(base, rows=(replace(base.rows[0], final_eligibility="OTHER"),)),
        lambda base: replace(base, rows=(replace(base.rows[0], guardrail_status="OTHER"),)),
        lambda base: replace(base, rows=(replace(base.rows[0], existing_listing_status="OTHER"),)),
        lambda base: replace(base, rows=(replace(base.rows[0], input_duplicate_status="OTHER"),)),
        lambda base: replace(base, rows=(replace(base.rows[0], source_asin_status="OTHER"),)),
        lambda base: replace(base, rows=(replace(base.rows[0], metadata_status="OTHER"),)),
        lambda base: replace(base, rows=(replace(base.rows[0], reason_codes=[]),)),
        lambda base: replace(base, rows=(replace(base.rows[0], reason_codes=("OTHER",)),)),
        lambda base: replace(
            base,
            rows=(replace(base.rows[0], reason_codes=("EXISTING_ASIN", "EXISTING_ASIN")),),
        ),
        lambda base: replace(
            base,
            rows=(replace(base.rows[0], reason_codes=("METADATA_INCOMPLETE", "EXISTING_ASIN")),),
        ),
        lambda base: replace(base, rows=(replace(base.rows[0], reason_codes=("EXISTING_ASIN",)),)),
        lambda base: replace(base, rows=(replace(base.rows[0], metadata_missing_fields=[]),)),
        lambda base: replace(base, rows=(replace(base.rows[0], metadata_missing_fields=("OTHER",)),)),
        lambda base: replace(
            base,
            rows=(replace(base.rows[0], metadata_missing_fields=("brand", "brand")),),
        ),
        lambda base: replace(
            base,
            rows=(replace(base.rows[0], metadata_missing_fields=("category", "brand")),),
        ),
        lambda base: replace(
            base,
            rows=(replace(base.rows[0], metadata_missing_fields=("brand",)),),
        ),
        lambda base: replace(
            base,
            rows=(replace(base.rows[0], metadata_status="INCOMPLETE"),),
        ),
        lambda base: replace(base, rows=(replace(base.rows[0], existing_evidence=[]),)),
        lambda base: replace(
            base,
            rows=(replace(base.rows[0], existing_evidence=(evidence("B000000001"),)),),
        ),
        lambda base: replace(
            base,
            rows=(replace(base.rows[0], existing_listing_status="EXISTING"),),
        ),
        lambda base: replace(
            existing_result(),
            rows=(replace(existing_result().rows[0], existing_evidence=("not-evidence",)),),
        ),
        lambda base: replace(
            existing_result(),
            rows=(
                replace(
                    existing_result().rows[0],
                    existing_evidence=(evidence("B000000099"),),
                ),
            ),
        ),
        lambda base: replace(
            existing_result(),
            rows=(
                replace(
                    existing_result().rows[0],
                    existing_evidence=(evidence("B000000001", marketplace="PH"),),
                ),
            ),
        ),
        lambda base: replace(
            existing_result(),
            rows=(
                replace(
                    existing_result().rows[0],
                    existing_evidence=(evidence("B000000001", source_row_number=True),),
                ),
            ),
        ),
        lambda base: replace(
            existing_result(),
            rows=(
                replace(
                    existing_result().rows[0],
                    existing_evidence=(evidence("B000000001", source_row_number=0),),
                ),
            ),
        ),
        lambda base: replace(
            existing_result(),
            rows=(
                replace(
                    existing_result().rows[0],
                    existing_evidence=(evidence("B000000001", source_row_number=-1),),
                ),
            ),
        ),
    ],
)
def test_invalid_result_contracts_fail_closed(mutate):
    with pytest.raises(gate_csv.PrelistingGateCsvError):
        gate_csv.build_prelisting_gate_exports(mutate(gate_result([gate_row()])))
