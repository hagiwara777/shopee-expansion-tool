"""Regressions using only strings provided by the Owner.

The category and product-text fragments below are not complete captured product
records.  These tests verify the cited evidence and policy terms in isolation;
they do not claim an ASIN's complete, final live outcome.
"""
import pytest

from modules.guardrails import apply_guardrails
from modules.safety_policy import evaluate_policy


OBSERVED_LAUNDRY_CATEGORY = "ドラッグストア > カテゴリー別 > 日用品 > 洗濯・仕上げ剤 > 液体洗剤"
OBSERVED_ALLIE_TEXT = "紫外線をカットし、ヘアカラーの色落ちを防ぐ"
OBSERVED_ALLIE_TITLE = "ALLIE クロノビューティ UV ヘアカラーラスティング&スタイリング バーム"


@pytest.mark.parametrize("market", ["PH", "SG"])
def test_observed_laundry_category_stops_as_an_ancestor(market):
    hits = evaluate_policy({"category": OBSERVED_LAUNDRY_CATEGORY}, market)
    assert any(hit.rule_id == "COMMON-SLS-LAUNDRY-CATEGORY" and hit.action == "BLOCK" for hit in hits)


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("term", ["柔軟剤", "柔軟仕上げ剤", "fabric softener"])
@pytest.mark.parametrize("field", ["product_title", "description", "features", "shortDescription", "safetyWarning", "itemHighlights", "category"])
def test_softener_item_scope_stops_only_title_or_category(market, term, field):
    hits = evaluate_policy({field: term}, market)
    assert any(hit.rule_id == "COMMON-SLS-LAUNDRY" and hit.action == "BLOCK" for hit in hits) == (field in {"product_title", "category"})


@pytest.mark.parametrize("market", ["PH", "SG"])
def test_owner_softener_fragrance_fragment_is_blocked_as_softener(market):
    hits = evaluate_policy({"product_title": "ファインフレグランス 柔軟剤"}, market)
    assert any(hit.rule_id == "COMMON-SLS-LAUNDRY" and hit.action == "BLOCK" for hit in hits)
    assert not any(hit.rule_id == "COMMON-SLS-PERFUME" for hit in hits)


@pytest.mark.parametrize("market", ["PH", "SG"])
def test_observed_dish_detergent_category_does_not_match_laundry(market):
    for node in ("食器用洗剤", "液体洗剤"):
        hits = evaluate_policy({"category": node}, market)
        assert not any(hit.rule_id in {"COMMON-SLS-LAUNDRY", "COMMON-SLS-LAUNDRY-CATEGORY"} for hit in hits)


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("fragment", ["ギャバン", "ギャバリオン"])
@pytest.mark.parametrize("field", ["product_title", "ingredients"])
def test_gaba_fragments_remain_blocked_and_explained(market, fragment, field):
    # A verified fragment, not a claim that it is the complete Amazon title.
    result = apply_guardrails([{field: fragment}], marketplace=market)[0]
    assert result["guardrail_status"] == "BLOCK"
    assert "PH-V2-INGREDIENT-GABA-006" in result["guardrail_note"]
    assert fragment in result["guardrail_note"]


@pytest.mark.parametrize("market", ["PH", "SG"])
def test_observed_allie_text_does_not_match_haircolor(market):
    for text in (OBSERVED_ALLIE_TEXT, "カラーリング後"):
        hits = evaluate_policy({"description": text}, market)
        assert not any(hit.rule_id == "COMMON-SLS-HAIRCOLOR" for hit in hits)
    hits = evaluate_policy({"product_title": OBSERVED_ALLIE_TITLE, "description": OBSERVED_ALLIE_TEXT}, market)
    assert not any(hit.rule_id == "COMMON-SLS-HAIRCOLOR" for hit in hits)


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("term", ["ヘアカラー", "染毛剤", "白髪染め"])
def test_actual_haircolor_product_terms_still_block(market, term):
    hits = evaluate_policy({"product_title": term}, market)
    assert any(hit.rule_id == "COMMON-SLS-HAIRCOLOR" and hit.action == "BLOCK" for hit in hits)
    # A combination of Owner-supplied fragments, not a reconstructed product.
    hits = evaluate_policy({"product_title": term, "description": OBSERVED_ALLIE_TEXT}, market)
    assert any(hit.rule_id == "COMMON-SLS-HAIRCOLOR" and hit.action == "BLOCK" for hit in hits)


@pytest.mark.parametrize("market", ["PH", "SG"])
def test_cologne_product_term_still_blocks(market):
    hits = evaluate_policy({"product_title": "アフターシェーブコロン"}, market)
    assert any(hit.rule_id == "COMMON-SLS-PERFUME" and hit.action == "BLOCK" for hit in hits)


@pytest.mark.parametrize("market", ["PH", "SG"])
def test_ingredient_token_alone_is_not_a_new_block(market):
    # This is the provided term in isolation, not a reconstructed ASIN record.
    hits = evaluate_policy({"ingredients": ["エタノール"]}, market)
    assert not any(hit.action == "BLOCK" for hit in hits)
