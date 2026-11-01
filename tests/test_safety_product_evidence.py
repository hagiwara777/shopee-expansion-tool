"""DEC-0164 policy boundaries; synthetic facts only, no acquisition or API."""
import pytest

from modules.guardrails import apply_guardrails


def decide(market="SG", **facts):
    return apply_guardrails([{
        "candidate_asin": "B000000001", "brand": "Unlisted Sample",
        "product_title": "普通の洗顔料", "category": "", **facts,
    }], marketplace=market)[0]


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("field,text", [
    ("product_title", "薬用洗顔料"), ("features", "医薬部外品"),
    ("description", "quasi-drug cleanser"), ("shortDescription", "quasi drugs"),
    ("itemHighlights", "medicated cleanser"), ("safetyWarning", "有効成分を配合"),
    ("ingredients", "有効成分: 合成試験成分"),
    ("activeIngredients", "医薬部外品"), ("specialIngredients", "quasi-drugs"),
])
def test_quasi_drug_displays_block_in_all_captured_fact_types(market, field, text):
    result = decide(market, **{field: text if field == "product_title" else [text]})
    assert result["guardrail_status"] == "BLOCK"
    assert "DEC-0164" in result["guardrail_note"]


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("text", [
    "医薬品ではありません", "本品は医薬部外品ではない化粧品です。",
    "薬用ではありません", "有効成分は配合していません。",
    "有効成分なし", "not a quasi-drug", "non-medicated cleanser",
    "notquasi-drug nor unmedicated", "quasidrugstore",
])
def test_direct_negations_and_ascii_fragments_do_not_block(market, text):
    for field in ("product_title", "description", "ingredients"):
        result = decide(market, **{field: text if field == "product_title" else [text]})
        assert result["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_negation_never_clears_another_positive_fact_or_existing_block(market):
    result = decide(market, description=["医薬品ではありません。医薬部外品です。"])
    assert result["guardrail_status"] == "BLOCK"
    assert "医薬品" not in result["guardrail_matched_terms"].split("|")
    assert decide(market, product_title="薬用クリーム", description=["薬用ではありません"])["guardrail_status"] == "BLOCK"
    assert decide(market, product_title="医療機器", description=["医薬品ではありません"])["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("text", [
    "傷やはれもの、しっしん等、異常のある部位にはお使いにならないでください。",
    "傷、はれもの、しっしん等、異常のある部位には使用しないこと。",
    "しっしん、かぶれ、ただれなどの症状があるときにはお使いにならないでください。",
    "傷・はれもの・しっしん等異常のあるときは、お使いにならないでください。",
])
def test_eczema_cautions_are_not_efficacy_claims(text):
    assert decide(safetyWarning=[text])["guardrail_status"] == "SAFE"
    assert decide(description=["<br>" + text + "<br>"])["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("text", [
    "しっしんの改善に効果があります。",
    "しっしんを治す。異常のある部位には使用しないこと。",
    "しっしんに効果。しっしんのある部位には使用しないこと。",
    "しっしんのある部位には使用しないこと。しっしんを改善します。",
    "しっしん。使用しないこと。",  # Unclear context remains REVIEW.
])
def test_eczema_claim_or_unclear_context_still_requires_review(text):
    assert decide(description=[text])["guardrail_status"] == "REVIEW"


def test_caution_does_not_mask_forbidden_ingredient_or_add_kanji_rules():
    assert decide(description=["しっしんのある部位には使わない。塩酸ジフェンヒドラミン配合。"])["guardrail_status"] == "BLOCK"
    assert decide(product_title="湿疹・湿しん")["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("field,text", [
    ("product_title", "ドライシャンプー"), ("description", "スプレー缶"),
    ("features", "エアゾール"), ("shortDescription", "火気と高温に注意"),
    ("safetyWarning", "高圧ガス: 窒素ガス"), ("itemHighlights", "ヘアスプレー"),
    ("ingredients", "ＬＰＧ"), ("activeIngredients", "DME"),
    ("specialIngredients", "窒素ガス"), ("product_title", "電動ハンドル"),
    ("product_title", "白髪染め カラートリートメント 染毛剤"),
    ("description", "ヘアスタイリング スタイリング仕上げ ヘアセット剤 仕上げ剤"),
    ("shortDescription", "ジュレ状のまとめ髪スタイリングスティック"),
])
def test_transport_terms_review_title_ingredients_and_text(market, field, text):
    result = decide(market, **{field: text if field == "product_title" else [text]})
    assert result["guardrail_status"] == "REVIEW"
    assert "SLS輸送確認" in result["guardrail_note"]
    assert f"fact_field={field}" in result["guardrail_note"]


@pytest.mark.parametrize("text", [
    "ポンプ式スプレー 洗い流すトリートメント", "香水", "除光液 ネイルポリッシュ",
    "ヘアトニック 消毒液", "xxLPGxx ADMEx", "湿疹 湿しん",
])
def test_transport_does_not_expand_into_unapproved_terms_or_ascii_substrings(text):
    assert decide(product_title=text, description=[text], ingredients=[text])["guardrail_status"] == "SAFE"


def test_transport_review_never_downgrades_brand_battery_or_medical_blocks():
    for facts in ({"brand": "Gillette"}, {"description": ["電池付属"]}, {"features": ["医薬部外品"]}):
        result = decide(product_title="ドライシャンプー", **facts)
        assert result["guardrail_status"] == "BLOCK"
        assert "SLS輸送確認" in result["guardrail_note"]
