from __future__ import annotations

from dataclasses import replace

import pytest

import modules.prelisting_gate as gate
from modules.guardrails import GuardrailDictionaryError
from modules.listing_inventory_parser import ListingEvidence, ListingInventoryFileResult
from modules.prelisting_candidate_csv import (
    EXPANSION_SOURCE_TYPE,
    RESOLVER_SOURCE_TYPE,
    PRELISTING_CANDIDATE_SCHEMA_VERSION,
    PrelistingCandidateFileResult,
    PrelistingCandidateRow,
)


def candidate(
    asin: str = "B000000001",
    *,
    source_type: str = EXPANSION_SOURCE_TYPE,
    source_asin: str = "B000000009",
    product_title: object = "Synthetic title",
    brand: object = "Synthetic brand",
    category: object = "Synthetic category",
    source_id: str = "",
) -> PrelistingCandidateRow:
    return PrelistingCandidateRow(
        schema_version=PRELISTING_CANDIDATE_SCHEMA_VERSION,
        source_type=source_type,
        source_id=source_id,
        source_asin=source_asin,
        candidate_asin=asin,
        input_title="Synthetic input title",
        product_title=product_title,
        brand=brand,
        category=category,
        amazon_url="",
        source_status="FOUND" if source_type == RESOLVER_SOURCE_TYPE else "",
        source_verification="KEEPA_VERIFIED" if source_type == RESOLVER_SOURCE_TYPE else "",
        source="synthetic",
        fetched_at="",
        source_note="",
    )


def candidate_file(
    rows: tuple[PrelistingCandidateRow, ...] | list[PrelistingCandidateRow],
    *,
    source_type: str = EXPANSION_SOURCE_TYPE,
) -> PrelistingCandidateFileResult:
    return PrelistingCandidateFileResult(
        schema_version=PRELISTING_CANDIDATE_SCHEMA_VERSION,
        source_type=source_type,
        source_file="synthetic-candidates.csv",
        data_row_count=len(rows),
        rows=tuple(rows),
    )


def evidence(
    asin: str,
    *,
    marketplace: str = "SG",
    shop_label: str = "Shop A",
    source_file: str = "shop-a.csv",
    source_row_number: int = 2,
    match_field: str = "Parent SKU",
    product_id: str = "P-1",
    stock: str = "1",
) -> ListingEvidence:
    return ListingEvidence(
        asin=asin,
        marketplace=marketplace,
        shop_label=shop_label,
        source_file=source_file,
        source_row_number=source_row_number,
        match_field=match_field,
        product_id=product_id,
        model_id="M-1",
        stock=stock,
        product_name="Synthetic inventory product",
        parent_sku=asin,
        sku=asin if match_field == "SKU" else "",
    )


def inventory(
    records: tuple[ListingEvidence, ...] | list[ListingEvidence] = (),
    *,
    marketplace: str = "SG",
    shop_label: str = "Shop A",
    source_file: str = "shop-a.csv",
    data_row_count: int = 1,
) -> ListingInventoryFileResult:
    records = tuple(records)
    return ListingInventoryFileResult(
        marketplace=marketplace,
        shop_label=shop_label,
        source_file=source_file,
        header_row_number=1,
        data_row_count=data_row_count,
        unique_asin_count=len({record.asin for record in records}),
        evidence_records=records,
    )


def set_guardrails(monkeypatch, statuses: list[str] | tuple[str, ...], *, mutate=None):
    captured: list[list[dict[str, object]]] = []

    def fake_apply_guardrails(rows, *, marketplace):
        inputs = list(rows)
        captured.append(inputs)
        output = []
        for input_row, status in zip(inputs, statuses):
            output.append(
                {
                    **input_row,
                    "guardrail_status": status,
                    "guardrail_risk_category": "synthetic_risk" if status != "SAFE" else "",
                    "guardrail_matched_terms": "synthetic_term" if status != "SAFE" else "",
                    "guardrail_source": "synthetic_source" if status != "SAFE" else "",
                    "guardrail_note": "synthetic note" if status != "SAFE" else "",
                }
            )
        return mutate(output) if mutate else output

    monkeypatch.setattr(gate, "apply_guardrails", fake_apply_guardrails)
    return captured


def evaluate(
    rows,
    inventories,
    *,
    source_type=EXPANSION_SOURCE_TYPE,
    marketplace=" SG ",
    expected_shop_count=None,
):
    inventory_rows = tuple(inventories)
    return gate.evaluate_prelisting_gate(
        candidate_file(rows, source_type=source_type),
        inventory_rows,
        marketplace=marketplace,
        expected_shop_count=(len(inventory_rows) if expected_shop_count is None else expected_shop_count),
    )


@pytest.mark.parametrize(
    ("status", "row", "expected"),
    [
        ("SAFE", candidate(), "ELIGIBLE"),
        ("REVIEW", candidate(), "REVIEW"),
        ("SAFE", candidate(product_title=""), "REVIEW"),
        ("BLOCK", candidate(), "EXCLUDE"),
    ],
)
def test_basic_guardrail_and_metadata_decisions(monkeypatch, status, row, expected):
    captured = set_guardrails(monkeypatch, [status])

    result = evaluate([row], [inventory([evidence("B000000099")])])

    assert result.rows[0].final_eligibility == expected
    assert result.candidate_count == result.eligible_count + result.review_count + result.exclude_count
    assert captured == [
        [
            {
                "gate_row_id": "G0001",
                "candidate_asin": "B000000001",
                "brand": row.brand,
                "product_title": row.product_title,
                "category": row.category,
            }
        ]
    ]


def test_ph_empty_inventory_uses_only_ph_guardrails_and_preserves_decisions():
    inventory_result = inventory(
        (),
        marketplace="PH",
        shop_label="PH Shop",
        source_file="Shopee 更新_PH.csv",
        data_row_count=0,
    )
    result = evaluate(
        [
            candidate("B000FQTRS0"),
            candidate("B000000002", product_title="medicated cleanser"),
            candidate("B000000003", product_title="ordinary storage box"),
            candidate("B000000004", product_title="electric kettle"),
        ],
        [inventory_result],
        marketplace=" ｐｈ ",
    )

    assert result.marketplace == "PH"
    assert [row.existing_listing_status for row in result.rows] == ["CLEAR"] * 4
    assert [row.final_eligibility for row in result.rows] == [
        "EXCLUDE",
        "REVIEW",
        "ELIGIBLE",
        "ELIGIBLE",
    ]
    assert [row.guardrail_status for row in result.rows] == ["BLOCK", "REVIEW", "SAFE", "SAFE"]


def test_sg_rule_does_not_leak_into_ph_guardrails():
    sg_inventory = inventory((), source_file="Shopee 更新_SG.csv", data_row_count=0)
    ph_inventory = inventory(
        (),
        marketplace="PH",
        shop_label="PH Shop",
        source_file="Shopee 更新_PH.csv",
        data_row_count=0,
    )

    sg_result = evaluate(
        [candidate(product_title="electric kettle")],
        [sg_inventory],
        marketplace="SG",
    )
    ph_result = evaluate(
        [candidate(product_title="electric kettle")],
        [ph_inventory],
        marketplace="PH",
    )
    sg_ph_only_result = evaluate(
        [candidate(product_title="medicated cleanser")],
        [sg_inventory],
        marketplace="SG",
    )
    ph_only_result = evaluate(
        [candidate(product_title="medicated cleanser")],
        [ph_inventory],
        marketplace="PH",
    )

    assert sg_result.rows[0].guardrail_status == "REVIEW"
    assert ph_result.rows[0].guardrail_status == "SAFE"
    assert sg_ph_only_result.rows[0].guardrail_status == "SAFE"
    assert ph_only_result.rows[0].guardrail_status == "REVIEW"


def test_empty_inventory_is_accepted_but_product_rows_without_evidence_fail_closed(monkeypatch):
    set_guardrails(monkeypatch, ["SAFE"])
    empty_result = evaluate(
        [candidate()],
        [inventory((), source_file="Shopee 更新_SG.csv", data_row_count=0)],
    )

    assert empty_result.rows[0].existing_listing_status == "CLEAR"
    assert empty_result.rows[0].final_eligibility == "ELIGIBLE"

    with pytest.raises(gate.PrelistingGateError, match="ASIN根拠"):
        evaluate([candidate()], [inventory((), data_row_count=1)])


def test_existing_parent_sku_sku_stock_zero_and_all_evidence_order(monkeypatch):
    set_guardrails(monkeypatch, ["SAFE"])
    target = "B000000001"
    first = inventory(
        [
            evidence(target, match_field="Parent SKU", stock="0", product_id="P-1"),
            evidence(target, match_field="SKU", stock="0", product_id="P-1"),
            evidence(target, match_field="Parent SKU", product_id="P-2", source_row_number=3),
        ]
    )
    second = inventory(
        [evidence(target, shop_label="Shop B", source_file="shop-b.csv", product_id="P-3")],
        shop_label="Shop B",
        source_file="shop-b.csv",
    )

    row = evaluate([candidate(target)], [first, second], expected_shop_count=2).rows[0]

    assert row.existing_listing_status == "EXISTING"
    assert row.final_eligibility == "EXCLUDE"
    assert [item.match_field for item in row.existing_evidence] == ["Parent SKU", "SKU", "Parent SKU", "Parent SKU"]
    assert [item.product_id for item in row.existing_evidence] == ["P-1", "P-1", "P-2", "P-3"]
    assert row.existing_evidence[0].stock == "0"


def test_duplicate_rows_keep_order_and_evaluate_every_state(monkeypatch):
    duplicate = candidate("B000000001")
    third = candidate("B000000001", product_title="  ")
    set_guardrails(monkeypatch, ["SAFE", "REVIEW", "BLOCK"])

    result = evaluate(
        [duplicate, duplicate, third],
        [inventory([evidence("B000000001")])],
    )

    assert [row.input_duplicate_status for row in result.rows] == ["UNIQUE", "DUPLICATE", "DUPLICATE"]
    assert [row.final_eligibility for row in result.rows] == ["EXCLUDE", "EXCLUDE", "EXCLUDE"]
    assert [row.candidate.product_title for row in result.rows] == ["Synthetic title", "Synthetic title", "  "]
    assert result.rows[1].reason_codes == ("EXISTING_ASIN", "INPUT_DUPLICATE", "GUARDRAIL_REVIEW")
    assert result.rows[2].reason_codes == (
        "GUARDRAIL_BLOCK",
        "EXISTING_ASIN",
        "INPUT_DUPLICATE",
        "METADATA_INCOMPLETE",
    )


def test_self_asin_and_resolver_source_status(monkeypatch):
    set_guardrails(monkeypatch, ["SAFE", "SAFE"])
    expansion = evaluate(
        [candidate("B000000001", source_asin="B000000001"), candidate("B000000002")],
        [inventory([evidence("B000000099")])],
    )
    set_guardrails(monkeypatch, ["SAFE"])
    resolver = evaluate(
        [candidate("B000000003", source_type=RESOLVER_SOURCE_TYPE, source_asin="")],
        [inventory([evidence("B000000099")])],
        source_type=RESOLVER_SOURCE_TYPE,
    )

    assert [row.source_asin_status for row in expansion.rows] == ["SELF_ASIN", "CLEAR"]
    assert expansion.rows[0].final_eligibility == "EXCLUDE"
    assert expansion.rows[1].final_eligibility == "ELIGIBLE"
    assert resolver.rows[0].source_asin_status == "CLEAR"
    assert resolver.rows[0].final_eligibility == "ELIGIBLE"


@pytest.mark.parametrize(
    ("field", "value", "expected_missing"),
    [
        ("product_title", "", ("product_title",)),
        ("brand", "   ", ("brand",)),
        ("category", None, ("category",)),
        ("product_title", "none", ("product_title",)),
        ("brand", "NULL", ("brand",)),
        ("category", "nan", ("category",)),
        ("product_title", "n/a", ("product_title",)),
        ("brand", "unknown", ("brand",)),
        ("category", "不明", ("category",)),
        ("product_title", "\uff2e\uff4f\uff4e\uff45", ("product_title",)),
    ],
)
def test_metadata_missing_values_are_review_without_mutating_candidate(
    monkeypatch, field, value, expected_missing
):
    set_guardrails(monkeypatch, ["SAFE"])
    original = candidate(**{field: value})

    row = evaluate([original], [inventory([evidence("B000000099")])]).rows[0]

    assert row.metadata_status == "INCOMPLETE"
    assert row.metadata_missing_fields == expected_missing
    assert row.final_eligibility == "REVIEW"
    assert getattr(row.candidate, field) == value


def test_metadata_multiple_missing_fields_have_fixed_order(monkeypatch):
    set_guardrails(monkeypatch, ["SAFE"])

    row = evaluate(
        [candidate(product_title="", brand="unknown", category="  ")],
        [inventory([evidence("B000000099")])],
    ).rows[0]

    assert row.metadata_missing_fields == ("product_title", "brand", "category")
    assert row.reason_codes == ("METADATA_INCOMPLETE",)


def test_exclude_retains_review_reasons_in_fixed_order(monkeypatch):
    set_guardrails(monkeypatch, ["REVIEW"])

    row = evaluate(
        [candidate("B000000001", category="unknown")],
        [inventory([evidence("B000000001")])],
    ).rows[0]

    assert row.final_eligibility == "EXCLUDE"
    assert row.reason_codes == ("EXISTING_ASIN", "GUARDRAIL_REVIEW", "METADATA_INCOMPLETE")


def test_formal_sg_penalty_asin_is_blocked_with_guardrail_metadata():
    row = evaluate(
        [candidate("B000FQTRS0")],
        [inventory([evidence("B000000099")])],
    ).rows[0]

    assert row.guardrail_status == "BLOCK"
    assert row.guardrail_risk_category == "own_penalty_product"
    assert row.guardrail_source == "own_penalty_case"
    assert row.final_eligibility == "EXCLUDE"
    assert row.reason_codes == ("GUARDRAIL_BLOCK",)


def test_guardrail_dictionary_error_stops_whole_evaluation(monkeypatch):
    def raise_dictionary_error(rows, *, marketplace):
        raise GuardrailDictionaryError("synthetic dictionary error")

    monkeypatch.setattr(gate, "apply_guardrails", raise_dictionary_error)

    with pytest.raises(gate.PrelistingGateError) as exc_info:
        evaluate([candidate()], [inventory([evidence("B000000099")])])

    assert isinstance(exc_info.value.__cause__, GuardrailDictionaryError)


def test_ph_guardrail_dictionary_error_stops_whole_evaluation(monkeypatch):
    def raise_dictionary_error(rows, *, marketplace):
        assert marketplace == "PH"
        raise GuardrailDictionaryError("synthetic PH dictionary error")

    monkeypatch.setattr(gate, "apply_guardrails", raise_dictionary_error)
    empty_ph = inventory(
        (),
        marketplace="PH",
        shop_label="PH Shop",
        source_file="Shopee 更新_PH.csv",
        data_row_count=0,
    )

    with pytest.raises(gate.PrelistingGateError) as exc_info:
        evaluate([candidate()], [empty_ph], marketplace="PH")

    assert isinstance(exc_info.value.__cause__, GuardrailDictionaryError)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda rows: rows[:-1],
        lambda rows: [{key: value for key, value in rows[0].items() if key != "guardrail_note"}],
        lambda rows: [{**rows[0], "guardrail_status": "MAYBE"}],
        lambda rows: [{**rows[0], "gate_row_id": "G9999"}],
        lambda rows: [{**rows[0], "candidate_asin": "B000000099"}],
        lambda rows: list(reversed(rows)),
    ],
)
def test_guardrail_output_contract_mismatches_fail_closed(monkeypatch, mutate):
    set_guardrails(monkeypatch, ["SAFE", "SAFE"], mutate=mutate)

    with pytest.raises(gate.PrelistingGateError):
        evaluate(
            [candidate("B000000001"), candidate("B000000002")],
            [inventory([evidence("B000000099")])],
        )


@pytest.mark.parametrize("marketplace", ["MY", "TH", "", None])
def test_unsupported_marketplace_is_rejected(monkeypatch, marketplace):
    set_guardrails(monkeypatch, ["SAFE"])

    with pytest.raises(gate.PrelistingGateError):
        gate.evaluate_prelisting_gate(
            candidate_file([candidate()]),
            [inventory([evidence("B000000099")])],
            marketplace=marketplace,
            expected_shop_count=1,
        )


@pytest.mark.parametrize("expected_shop_count", [None, True, False, 0, -1, "1", 1.0])
def test_expected_shop_count_is_a_positive_exact_int(monkeypatch, expected_shop_count):
    set_guardrails(monkeypatch, ["SAFE"])

    with pytest.raises(gate.PrelistingGateError):
        gate.evaluate_prelisting_gate(
            candidate_file([candidate()]),
            [inventory([evidence("B000000099")])],
            marketplace="SG",
            expected_shop_count=expected_shop_count,
        )


def test_inventory_file_count_and_identity_contracts_fail_closed(monkeypatch):
    set_guardrails(monkeypatch, ["SAFE"])
    valid = inventory([evidence("B000000099")])
    cases = [
        ((valid,), 2),
        ((valid, inventory([evidence("B000000098")], shop_label="Shop B", source_file="shop-b.csv")), 1),
        ((replace(valid, shop_label=""),), 1),
        ((valid, replace(valid, shop_label="\uff33\uff48\uff4f\uff50\u3000\uff21", source_file="shop-b.csv")), 2),
        ((replace(valid, source_file=""),), 1),
        ((valid, replace(valid, shop_label="Shop B", source_file="SHOP-A.CSV")), 2),
        ((replace(valid, marketplace="PH"),), 1),
    ]

    for inventories, expected_count in cases:
        with pytest.raises(gate.PrelistingGateError):
            evaluate([candidate()], inventories, expected_shop_count=expected_count)


def test_inventory_marketplace_mixing_and_filename_mismatch_fail_closed(monkeypatch):
    set_guardrails(monkeypatch, ["SAFE"])
    ph_evidence = evidence(
        "B000000099",
        marketplace="PH",
        shop_label="PH Shop",
        source_file="Shopee 更新_PH.csv",
    )
    ph_inventory = inventory(
        [ph_evidence],
        marketplace="PH",
        shop_label="PH Shop",
        source_file="Shopee 更新_PH.csv",
    )
    sg_inventory = inventory([evidence("B000000098", source_file="Shopee 更新_SG.csv")], source_file="Shopee 更新_SG.csv")

    with pytest.raises(gate.PrelistingGateError, match="marketplace"):
        evaluate([candidate()], [sg_inventory, ph_inventory], marketplace="PH", expected_shop_count=2)

    mismatched_source = "Shopee 更新_SG.csv"
    mismatched_evidence = evidence(
        "B000000099",
        marketplace="PH",
        shop_label="PH Shop",
        source_file=mismatched_source,
    )
    mismatched_inventory = inventory(
        [mismatched_evidence],
        marketplace="PH",
        shop_label="PH Shop",
        source_file=mismatched_source,
    )
    with pytest.raises(gate.PrelistingGateError, match="市場表記"):
        evaluate([candidate()], [mismatched_inventory], marketplace="PH")


@pytest.mark.parametrize(
    "bad_file",
    [
        candidate_file([], source_type=EXPANSION_SOURCE_TYPE),
        candidate_file([candidate()], source_type="OTHER"),
        candidate_file([candidate(source_type=RESOLVER_SOURCE_TYPE)], source_type=EXPANSION_SOURCE_TYPE),
        candidate_file([candidate("INVALID")]),
        candidate_file([candidate(source_asin="INVALID")]),
    ],
)
def test_candidate_input_contract_errors_fail_closed(monkeypatch, bad_file):
    set_guardrails(monkeypatch, ["SAFE"])

    with pytest.raises(gate.PrelistingGateError):
        gate.evaluate_prelisting_gate(
            bad_file,
            [inventory([evidence("B000000099")])],
            marketplace="SG",
            expected_shop_count=1,
        )


def test_empty_existing_asin_index_fails_closed(monkeypatch):
    set_guardrails(monkeypatch, ["SAFE"])

    with pytest.raises(gate.PrelistingGateError):
        evaluate([candidate()], [inventory()])


def test_casefolded_shop_label_duplicate_fails_closed(monkeypatch):
    set_guardrails(monkeypatch, ["SAFE"])
    first = inventory(
        [evidence("B000000099")],
        shop_label="SG_SHOP_1",
        source_file="shop-one.csv",
    )
    second = inventory(
        [evidence("B000000098", shop_label="sg_shop_1", source_file="shop-two.csv")],
        shop_label="sg_shop_1",
        source_file="shop-two.csv",
    )

    with pytest.raises(gate.PrelistingGateError):
        evaluate([candidate()], [first, second], expected_shop_count=2)


def test_summary_counts_are_asserted_individually(monkeypatch):
    set_guardrails(monkeypatch, ["SAFE", "REVIEW", "BLOCK"])

    result = evaluate(
        [
            candidate("B000000001"),
            candidate("B000000002"),
            candidate("B000000003"),
        ],
        [inventory([evidence("B000000099")])],
    )

    assert [row.final_eligibility for row in result.rows] == [
        "ELIGIBLE",
        "REVIEW",
        "EXCLUDE",
    ]
    assert result.candidate_count == 3
    assert result.eligible_count == 1
    assert result.review_count == 1
    assert result.exclude_count == 1
    assert result.candidate_count == (
        result.eligible_count + result.review_count + result.exclude_count
    )


def test_duplicate_guardrail_gate_row_id_fails_closed(monkeypatch):
    def duplicate_gate_row_id(rows):
        duplicate_rows = [dict(row) for row in rows]
        duplicate_rows[1]["gate_row_id"] = duplicate_rows[0]["gate_row_id"]
        assert [row["gate_row_id"] for row in duplicate_rows] == ["G0001", "G0001"]
        return duplicate_rows

    set_guardrails(
        monkeypatch,
        ["SAFE", "SAFE"],
        mutate=duplicate_gate_row_id,
    )

    with pytest.raises(gate.PrelistingGateError):
        evaluate(
            [candidate("B000000001"), candidate("B000000002")],
            [inventory([evidence("B000000099")])],
        )


def test_v12_dictionary_review_and_existing_block_propagate_to_gate_results():
    result = evaluate(
        [
            candidate(asin="B000000001", product_title="electric kettle"),
            candidate(asin="B000FQTRS0", product_title="薬用加美乃素S-II"),
        ],
        [inventory([evidence("B000000099")])],
    )

    review_row, block_row = result.rows
    assert review_row.guardrail_status == "REVIEW"
    assert review_row.guardrail_risk_category == "controlled_goods_unverified"
    assert review_row.guardrail_matched_terms == "electric kettle"
    assert review_row.guardrail_source == "shopee_policy"
    assert review_row.final_eligibility == "REVIEW"
    assert review_row.reason_codes == ("GUARDRAIL_REVIEW",)

    assert block_row.guardrail_status == "BLOCK"
    assert "own_penalty_product" in block_row.guardrail_risk_category.split("|")
    assert "medical_or_therapeutic" in block_row.guardrail_risk_category.split("|")
    assert block_row.final_eligibility == "EXCLUDE"
    assert block_row.reason_codes == ("GUARDRAIL_BLOCK",)
