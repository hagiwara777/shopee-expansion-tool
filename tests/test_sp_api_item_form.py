"""DEC-0192: synthetic Amazon item-form facts reach the existing safety gate."""

import pytest

from modules.asin_resolver import preview_candidates, verify_preview_rows
from modules.sora_run import evaluate_sora_run, prepare_sora_run, sora_exports
from modules.sp_api_catalog import JP_MARKETPLACE, normalize_catalog_item


ASIN = "B000000001"
TITLE = "Dr.Scholl 靴専用 【消臭・抗菌靴スプレー 大型サイズ300ml×2個】"


@pytest.fixture(autouse=True)
def no_live_requests(monkeypatch):
    monkeypatch.setattr("requests.Session.request", lambda *a, **kw: pytest.fail("Live API reached"))


def catalog_item(item_form, **attributes):
    return {
        "asin": ASIN,
        "attributes": {
            "item_form": item_form,
            "item_package_dimensions": [{
                axis: {"value": 10, "unit": "centimeters"}
                for axis in ("length", "width", "height")
            }],
            "item_package_weight": [{"value": 1, "unit": "kilograms"}],
            **attributes,
        },
        "summaries": [{
            "marketplaceId": JP_MARKETPLACE, "itemName": TITLE, "brand": "試験ブランド",
            "browseClassification": {"displayName": "ドラッグストア"},
        }],
    }


def run_from_normalized_product(product, marketplace):
    class CapturedClient:
        provider_name = "sp_api_catalog_2022_04_01"
        product_field_prefix = "spapi"
        verification_label = "SP_API_VERIFIED"

        def verify_products_by_asin(self, asins):
            return {asin: product for asin in asins}

    verified = verify_preview_rows(preview_candidates(ASIN), CapturedClient())
    return prepare_sora_run(verified, marketplace=marketplace, auth_calls=0, catalog_calls=0)


@pytest.mark.parametrize("marketplace", ["SG", "PH", "MY", "TH", "TW"])
def test_jp_item_form_aerosol_reaches_sora_review_and_cannot_pass(marketplace):
    product = normalize_catalog_item(catalog_item([
        {"value": "エアゾール", "marketplace_id": JP_MARKETPLACE},
    ]), fetched_at="2026-11-14T00:00:00+00:00")
    assert product["product_text_safety_fact"]["itemHighlights"] == ["エアゾール"]

    run = run_from_normalized_product(product, marketplace)
    result = evaluate_sora_run(run)
    row = result.rows[0]
    assert row.guardrail_status == "REVIEW" and row.final_eligibility == "REVIEW"
    assert "エアゾール" in row.guardrail_matched_terms
    assert "COMMON-AEROSOL" in row.guardrail_note
    assert "MY-VOLUMETRIC" not in row.guardrail_matched_terms
    assert sora_exports(run, result)["通過ASIN.txt"] == b""


def test_foreign_item_form_is_not_japanese_product_evidence():
    product = normalize_catalog_item(catalog_item([
        {"value": "エアゾール", "marketplace_id": "ATVPDKIKX0DER"},
    ]), fetched_at="2026-11-14T00:00:00+00:00")
    assert product["product_text_safety_fact"]["itemHighlights"] == []
    result = evaluate_sora_run(run_from_normalized_product(product, "SG"))
    assert result.rows[0].guardrail_status == "SAFE"
    assert result.rows[0].final_eligibility == "ELIGIBLE"


def test_item_form_keeps_existing_highlights_and_deduplicates_values():
    attributes = {
        name: [{"value": value, "marketplace_id": JP_MARKETPLACE}]
        for name, value in (
            ("special_feature", "エアゾール"), ("included_components", "本体"),
            ("directions", "靴に使用"), ("power_source", "手動"),
        )
    }
    product = normalize_catalog_item(catalog_item([
        {"value": "エアゾール", "marketplace_id": JP_MARKETPLACE},
        {"value": "液体", "marketplace_id": JP_MARKETPLACE},
    ], **attributes), fetched_at="2026-11-14T00:00:00+00:00")
    assert product["product_text_safety_fact"]["itemHighlights"] == [
        "エアゾール", "本体", "靴に使用", "手動", "液体",
    ]
