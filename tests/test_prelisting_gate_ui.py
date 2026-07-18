import pytest

from modules.listing_inventory_parser import ListingEvidence, ListingInventoryFileResult
from modules.prelisting_candidate_csv import PrelistingCandidateRow
from modules.prelisting_gate import PrelistingGateResult, PrelistingGateRow
from modules.prelisting_gate_ui import (
    PRELISTING_GATE_RESULT_STATE_KEYS,
    PRELISTING_GATE_PREVIEW_COLUMNS,
    build_prelisting_gate_preview_rows,
    build_prelisting_gate_fingerprint,
    clear_prelisting_gate_result,
    prelisting_gate_download_source_type,
    safe_prelisting_gate_error_summary,
    shop_label_widget_key,
    summarize_prelisting_inventory,
    validate_inventory_file_duplicates,
    validate_shop_labels,
)


def _fingerprint(
    *,
    marketplace: str = "SG",
    expected_shop_count: int = 2,
    candidate_filename: str = "candidates.csv",
    candidate_content: bytes = b"candidate-content",
    inventory_files: tuple[tuple[str, bytes, str], ...] = (
        ("shop-1.csv", b"inventory-one", "SG_SHOP_1"),
        ("shop-2.csv", b"inventory-two", "SG_SHOP_2"),
    ),
) -> str:
    return build_prelisting_gate_fingerprint(
        marketplace=marketplace,
        expected_shop_count=expected_shop_count,
        candidate_filename=candidate_filename,
        candidate_content=candidate_content,
        inventory_files=inventory_files,
    )


def _evidence(asin: str, shop_label: str) -> ListingEvidence:
    return ListingEvidence(
        asin=asin,
        marketplace="SG",
        shop_label=shop_label,
        source_file="synthetic.csv",
        source_row_number=2,
        match_field="Parent SKU",
        product_id="synthetic-product-id",
        model_id="synthetic-model-id",
        stock="1",
        product_name="Synthetic product",
        parent_sku=asin,
        sku="",
    )


def _inventory_result(
    *,
    shop_label: str,
    data_row_count: int,
    asins: tuple[str, ...],
) -> ListingInventoryFileResult:
    evidence_records = tuple(_evidence(asin, shop_label) for asin in asins)
    return ListingInventoryFileResult(
        marketplace="SG",
        shop_label=shop_label,
        source_file=f"{shop_label}.csv",
        header_row_number=1,
        data_row_count=data_row_count,
        unique_asin_count=len(set(asins)),
        evidence_records=evidence_records,
    )


def _gate_result(
    rows: tuple[tuple[str, str], ...],
) -> PrelistingGateResult:
    gate_rows = []
    for index, (final_eligibility, candidate_asin) in enumerate(rows, start=1):
        candidate = PrelistingCandidateRow(
            schema_version="PRELISTING_CANDIDATE_V1",
            source_type="EXPANSION",
            source_id=f"S{index:04d}",
            source_asin="B000000999",
            candidate_asin=candidate_asin,
            input_title=f"Synthetic input {index}",
            product_title=f"Synthetic title {index}",
            brand=f"Synthetic brand {index}",
            category=f"Synthetic category {index}",
            amazon_url=f"https://example.invalid/{index}",
            source_status="FOUND",
            source_verification="KEEPA_VERIFIED",
            source="synthetic",
            fetched_at="2026-07-17T00:00:00+00:00",
            source_note="",
        )
        guardrail_status = {
            "ELIGIBLE": "SAFE",
            "REVIEW": "REVIEW",
            "EXCLUDE": "BLOCK",
        }[final_eligibility]
        reason_codes = {
            "ELIGIBLE": (),
            "REVIEW": ("GUARDRAIL_REVIEW",),
            "EXCLUDE": ("GUARDRAIL_BLOCK",),
        }[final_eligibility]
        evidence = (_evidence(candidate_asin, "SG_SHOP_1"),) if index == 2 else ()
        gate_rows.append(
            PrelistingGateRow(
                candidate=candidate,
                marketplace="SG",
                guardrail_status=guardrail_status,
                guardrail_risk_category="",
                guardrail_matched_terms="",
                guardrail_source="synthetic",
                guardrail_note="",
                existing_listing_status="EXISTING" if evidence else "CLEAR",
                existing_evidence=evidence,
                input_duplicate_status="UNIQUE",
                source_asin_status="CLEAR",
                metadata_status="COMPLETE",
                metadata_missing_fields=(),
                final_eligibility=final_eligibility,
                reason_codes=reason_codes,
            )
        )

    result_rows = tuple(gate_rows)
    return PrelistingGateResult(
        marketplace="SG",
        candidate_count=len(result_rows),
        eligible_count=sum(row.final_eligibility == "ELIGIBLE" for row in result_rows),
        review_count=sum(row.final_eligibility == "REVIEW" for row in result_rows),
        exclude_count=sum(row.final_eligibility == "EXCLUDE" for row in result_rows),
        rows=result_rows,
    )


def test_fingerprint_is_deterministic_and_never_contains_uploaded_bytes():
    first = _fingerprint()

    assert first == _fingerprint()
    assert first != _fingerprint(candidate_filename="renamed.csv")
    assert first != _fingerprint(candidate_content=b"candidate-content-changed")
    assert first != _fingerprint(
        inventory_files=(
            ("renamed.csv", b"inventory-one", "SG_SHOP_1"),
            ("shop-2.csv", b"inventory-two", "SG_SHOP_2"),
        )
    )
    assert first != _fingerprint(
        inventory_files=(
            ("shop-1.csv", b"inventory-one-changed", "SG_SHOP_1"),
            ("shop-2.csv", b"inventory-two", "SG_SHOP_2"),
        )
    )
    assert first != _fingerprint(
        inventory_files=(
            ("shop-2.csv", b"inventory-two", "SG_SHOP_2"),
            ("shop-1.csv", b"inventory-one", "SG_SHOP_1"),
        )
    )
    assert first != _fingerprint(expected_shop_count=3)
    assert first != _fingerprint(
        inventory_files=(
            ("shop-1.csv", b"inventory-one", "SG_SHOP_CHANGED"),
            ("shop-2.csv", b"inventory-two", "SG_SHOP_2"),
        )
    )
    assert first != _fingerprint(marketplace="PH")
    assert "candidate-content" not in first
    assert "inventory-one" not in first


def test_shop_label_validation_rejects_blank_casefold_and_nfkc_duplicates():
    blank = validate_shop_labels(["  "])
    casefold_duplicate = validate_shop_labels(["SG_SHOP_1", "sg_shop_1"])
    nfkc_duplicate = validate_shop_labels(["ＳＧ＿ＳＨＯＰ＿１", "SG_SHOP_1"])

    assert not blank.is_valid
    assert "shop_labelが空欄です。" in blank.errors
    assert not casefold_duplicate.is_valid
    assert "shop_labelが重複しています。" in casefold_duplicate.errors
    assert not nfkc_duplicate.is_valid
    assert "shop_labelが重複しています。" in nfkc_duplicate.errors
    assert nfkc_duplicate.display_labels[0] == "ＳＧ＿ＳＨＯＰ＿１"
    assert nfkc_duplicate.normalized_labels[0] == "SG_SHOP_1"


def test_inventory_file_validation_rejects_duplicate_names_and_contents():
    duplicate_names = validate_inventory_file_duplicates(
        [("same.csv", b"first"), ("same.csv", b"second")]
    )
    duplicate_contents = validate_inventory_file_duplicates(
        [("first.csv", b"same-content"), ("second.csv", b"same-content")]
    )

    assert not duplicate_names.is_valid
    assert "既出品CSVのファイル名が重複しています。" in duplicate_names.errors
    assert not duplicate_contents.is_valid
    assert "既出品CSVの内容が重複しています。" in duplicate_contents.errors
    assert shop_label_widget_key("shop.csv", b"one") != shop_label_widget_key(
        "shop.csv", b"two"
    )


def test_safe_error_summaries_never_include_source_values():
    raw_source_value = "RAW-PRODUCT-ID-DO-NOT-DISPLAY"
    candidate = safe_prelisting_gate_error_summary("candidate")
    inventory = safe_prelisting_gate_error_summary("inventory")
    configuration = safe_prelisting_gate_error_summary("configuration")
    gate = safe_prelisting_gate_error_summary("gate")
    export = safe_prelisting_gate_error_summary("export")
    unexpected = safe_prelisting_gate_error_summary("unexpected")

    assert candidate == (
        "候補CSVを解析できません。\n"
        "出品前保安ゲート用の固定15列CSVか、schema versionと候補行を確認してください。"
    )
    assert inventory == (
        "既出品CSVを解析できません。\n"
        "必須ヘッダー、空ファイル、Parent SKU／SKUのASIN形式を確認してください。"
    )
    assert configuration == (
        "入力条件が揃っていません。\n"
        "全ショップ数、アップロード数、ファイル名、shop_labelを確認してください。"
    )
    assert gate == (
        "出品前チェックを完了できませんでした。\n"
        "対象国、全ショップ数、ファイル名、shop_label、Guardrail辞書を確認してください。"
    )
    assert export == (
        "判定結果CSVを作成できませんでした。\n"
        "判定結果の整合性を確認してください。"
    )
    assert all(
        raw_source_value not in summary
        for summary in (candidate, inventory, configuration, gate, export, unexpected)
    )


def test_preflight_summary_aggregates_only_non_sensitive_counts():
    summary = summarize_prelisting_inventory(
        [
            _inventory_result(
                shop_label="SG_SHOP_1",
                data_row_count=2,
                asins=("B000000001", "B000000002"),
            ),
            _inventory_result(
                shop_label="SG_SHOP_2",
                data_row_count=1,
                asins=("B000000002", "B000000003"),
            ),
        ],
        expected_shop_count=2,
        uploaded_file_count=2,
    )

    assert summary.expected_shop_count == 2
    assert summary.uploaded_file_count == 2
    assert summary.parsed_file_count == 2
    assert summary.existing_listing_row_count == 3
    assert summary.unique_existing_asin_count == 3
    assert summary.evidence_count == 4


def test_clear_prelisting_gate_result_removes_only_its_own_state_keys():
    state = {
        "unrelated": "keep",
        **{key: "remove" for key in PRELISTING_GATE_RESULT_STATE_KEYS},
    }

    clear_prelisting_gate_result(state)

    assert state == {"unrelated": "keep"}


def test_preview_rows_filter_each_eligibility_in_input_order_and_keep_duplicates():
    result = _gate_result(
        (
            ("ELIGIBLE", "B000000001"),
            ("REVIEW", "B000000002"),
            ("EXCLUDE", "B000000003"),
            ("ELIGIBLE", "B000000001"),
        )
    )

    eligible = build_prelisting_gate_preview_rows(result, final_eligibility="ELIGIBLE")
    review = build_prelisting_gate_preview_rows(result, final_eligibility="REVIEW")
    exclude = build_prelisting_gate_preview_rows(result, final_eligibility="EXCLUDE")

    assert [row["candidate_asin"] for row in eligible] == ["B000000001", "B000000001"]
    assert [row["candidate_asin"] for row in review] == ["B000000002"]
    assert [row["candidate_asin"] for row in exclude] == ["B000000003"]


def test_preview_rows_are_fixed_to_ten_safe_columns_without_mutating_result():
    result = _gate_result((("REVIEW", "B000000002"),))
    original_rows = result.rows

    preview = build_prelisting_gate_preview_rows(result, final_eligibility="REVIEW")

    assert tuple(preview[0]) == PRELISTING_GATE_PREVIEW_COLUMNS
    assert len(preview[0]) == 10
    assert preview[0]["reason_codes"] == "GUARDRAIL_REVIEW"
    assert preview[0]["existing_evidence_count"] == 0
    assert not {"existing_evidence_json", "product_id", "model_id", "source_file"} & set(
        preview[0]
    )
    assert result.rows == original_rows


def test_preview_rows_limit_to_first_hundred_records():
    result = _gate_result(
        tuple(("ELIGIBLE", f"B{index:09d}") for index in range(1, 102))
    )

    preview = build_prelisting_gate_preview_rows(result, final_eligibility="ELIGIBLE")

    assert len(preview) == 100
    assert preview[0]["candidate_asin"] == "B000000001"
    assert preview[-1]["candidate_asin"] == "B000000100"


@pytest.mark.parametrize("final_eligibility", ["SAFE", "", None])
def test_preview_rows_reject_invalid_final_eligibility(final_eligibility):
    result = _gate_result((("ELIGIBLE", "B000000001"),))

    with pytest.raises(ValueError):
        build_prelisting_gate_preview_rows(
            result,
            final_eligibility=final_eligibility,
        )


@pytest.mark.parametrize("limit", [0, -1, 101, True, "100"])
def test_preview_rows_reject_invalid_limit(limit):
    result = _gate_result((("ELIGIBLE", "B000000001"),))

    with pytest.raises(ValueError):
        build_prelisting_gate_preview_rows(
            result,
            final_eligibility="ELIGIBLE",
            limit=limit,
        )


def test_download_source_type_uses_only_the_formal_source_types():
    assert prelisting_gate_download_source_type("EXPANSION") == "expansion"
    assert prelisting_gate_download_source_type("RESOLVER") == "resolver"
    with pytest.raises(ValueError):
        prelisting_gate_download_source_type("UNKNOWN")
