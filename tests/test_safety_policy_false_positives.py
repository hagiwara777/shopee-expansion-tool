"""Owner-reported wording regressions, with synthetic product facts only."""

import pytest

from modules.guardrails import apply_guardrails


def guarded(title="普通のシャンプー", *, market="SG", **facts):
    return apply_guardrails([{"product_title": title, **facts}], marketplace=market)[0]


@pytest.mark.parametrize("field", ["description", "features", "shortDescription", "safetyWarning", "itemHighlights"])
@pytest.mark.parametrize("phrase", ["ご使用方法をお守りください", "使用上の注意をお守り下さい"])
def test_sg_amulet_does_not_match_usage_instructions(field, phrase):
    assert guarded(**{field: phrase})["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("phrase", ["ご使用方法をお守りください", "お守り下さい"])
@pytest.mark.parametrize("field", ["product_title", "category"])
def test_sg_amulet_instruction_exclusion_also_applies_in_scanned_fields(field, phrase):
    assert guarded(**{field: phrase})["guardrail_status"] == "SAFE"


def test_sg_amulet_scope_does_not_release_a_separate_product_or_other_sg_stop():
    assert guarded(description="お守り")["guardrail_status"] == "SAFE"
    assert guarded("交通安全のお守り")["guardrail_status"] == "BLOCK"
    assert guarded(category="お守り")["guardrail_status"] == "BLOCK"
    assert guarded("お守りください。交通安全のお守り")["guardrail_status"] == "BLOCK"
    assert guarded(safetyWarning="お守りください", category="お守り")["guardrail_status"] == "BLOCK"
    assert guarded(description="護身用ペン")["guardrail_status"] == "BLOCK"
    assert guarded("交通安全のお守り", market="PH")["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("field", ["description", "features", "safetyWarning", "itemHighlights"])
def test_plant_product_rule_does_not_use_product_text(field, market):
    assert guarded(market=market, **{field: "植物由来の天然成分"})["guardrail_status"] == "SAFE"
    assert guarded(market=market, **{field: "観葉植物"})["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("phrase", ["植物由来", "植物性", "植物エキス", "植物オイル", "植物アロマ"])
@pytest.mark.parametrize("field", ["product_title", "category"])
def test_plant_ingredient_expressions_are_not_live_plants(field, phrase):
    assert guarded(**{field: phrase})["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_plant_exclusions_do_not_cancel_a_separate_plant_product(market):
    assert guarded("観葉植物", market=market)["guardrail_status"] == "BLOCK"
    assert guarded(market=market, category="植物")["guardrail_status"] == "BLOCK"
    assert guarded(market=market, category="園芸 > 観葉植物")["guardrail_status"] == "BLOCK"
    assert guarded(market=market, category="植物性 > 植物")["guardrail_status"] == "BLOCK"
    assert guarded("植物由来の鉢と観葉植物", market=market)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("term", ["園芸用土", "生きた動物"])
def test_plant_scope_correction_does_not_change_other_shipping_terms(term):
    assert guarded(description=term)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("phrase", ["セテアリルアルコール", "ステアリルアルコール", "ｾﾃｱﾘﾙｱﾙｺｰﾙ"])
def test_katakana_compound_alcohol_is_not_standalone_alcohol(market, phrase):
    assert guarded(phrase, market=market)["guardrail_status"] == "SAFE"
    assert guarded(market=market, features=[phrase])["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_standalone_alcohol_remains_a_stop_after_harmless_occurrences(market):
    assert guarded("アルコール", market=market)["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description="アルコール度数 12%")["guardrail_status"] == "REVIEW"
    assert guarded(market=market, description="セテアリルアルコール。アルコール度数 12%")["guardrail_status"] == "REVIEW"
    assert guarded(market=market, description="アルコールフリー。アルコール度数 12%")["guardrail_status"] == "REVIEW"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("field", ["features", "itemHighlights"])
@pytest.mark.parametrize("label", ["全成分：", "【成分】", "原材料:"])
def test_bullet_ingredient_section_is_review_instead_of_block(market, field, label):
    row = guarded(market=market, **{field: [label + "水、サリチル酸、ナイアシンアミド"]})
    assert row["guardrail_status"] == "REVIEW"
    assert "サリチル酸" in row["guardrail_matched_terms"]
    assert "ナイアシンアミド" in row["guardrail_matched_terms"]


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_ingredient_header_inside_bullet_splits_only_the_suffix(market):
    assert guarded(market=market, features=["使い方：適量を塗布。全成分：水、サリチル酸"])["guardrail_status"] == "REVIEW"
    assert guarded(market=market, features=["サリチル酸配合。全成分：水"])["guardrail_status"] == "BLOCK"
    assert guarded(market=market, features=["保湿成分としてナイアシンアミドを配合"])["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_ingredient_review_does_not_lower_a_positive_elsewhere(market):
    section = ["全成分：水、サリチル酸"]
    assert guarded("サリチル酸配合美容液", market=market, features=section)["guardrail_status"] == "BLOCK"
    assert guarded(market=market, features=section, description="サリチル酸配合美容液")["guardrail_status"] == "BLOCK"
    assert guarded(market=market, features=section + ["ナイアシンアミド配合美容液"])["guardrail_status"] == "BLOCK"
    assert guarded(market=market, features=["全成分", "サリチル酸配合美容液"])["guardrail_status"] == "BLOCK"
    assert guarded(market=market, features=section, itemHighlights=["サリチル酸配合美容液"])["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_ingredient_section_does_not_lower_independent_medical_or_brand_stops(market):
    assert guarded(market=market, features=["全成分：サリチル酸、ジフェンヒドラミン"])["guardrail_status"] == "BLOCK"
    assert guarded(market=market, features=["全成分：サリチル酸。医薬部外品"])["guardrail_status"] == "BLOCK"
    assert guarded(market=market, brand="Adidas", features=["全成分：サリチル酸"])["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_structured_new_ingredient_fields_keep_the_existing_contract(market):
    row = guarded(market=market, ingredients=["サリチル酸"], activeIngredients=["ナイアシンアミド"])
    assert row["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("title", ["e-cigarettes", "e-juices", "two-way radios", "Kaminomoto S-II100ml"])
def test_existing_hyphenated_stops_keep_their_substring_matching(title):
    assert guarded(title)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("title,category,field,excerpt", [
    ("クリーミータッチライナー 08 マッチャカーキ", "ビューティー > メイクアップ > アイライナー", "description", ""),
    ("リップモンスター 口紅 04 パンプキンワイン", "ビューティー > メイクアップ > 口紅", "description", ""),
    ("リップモンスター 口紅 04 パンプキンワイン 5個", "ビューティー > メイクアップ > 口紅", "description", ""),
    ("クレンズオイル 無香タイプ", "ビューティー > スキンケア > クレンジングオイル", "description",
     "香りに敏感な方や、お手持ちのスキンケア・香水の香りを邪魔したくない方にも使いやすい仕"),
    ("ボディミルク 無香料 450ml", "ビューティー > ボディケア > ボディローション", "features",
     "で他の香りを邪魔しない】無香料・無着色。香水や他のフレグランスを使用する方、また強い"),
    ("ボディミルク 無香料 250ml", "ビューティー > ボディケア > ボディローション", "features",
     "で他の香りを邪魔しない】無香料・無着色。香水や他のフレグランスを使用する方、また強い"),
])
def test_owner_six_contexts_are_not_a_stop_in_either_market(market, title, category, field, excerpt):
    assert guarded(title, market=market, category=category, **{field: excerpt})["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("term", ["マッチャカーキ", "抹茶", "ﾏｯﾁｬ"])
def test_matcha_is_not_a_match_but_a_separate_match_still_blocks(market, term):
    assert guarded(term, market=market)["guardrail_status"] == "SAFE"
    assert guarded(term + " とマッチ", market=market)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("term", ["パンプキンワイン", "ワインレッド", "ワイン色"])
def test_makeup_wine_color_is_not_a_drink(market, term):
    category = "ビューティー > メイクアップ > 口紅"
    assert guarded("口紅 " + term, market=market, category=category)["guardrail_status"] == "SAFE"
    assert guarded("口紅", market=market, category=category, description="色: " + term)["guardrail_status"] == "SAFE"
    assert guarded("口紅 " + term, market=market, category=category, description="ワインを含む")["guardrail_status"] == "BLOCK"
    assert guarded("口紅 " + term + " とワイン", market=market, category=category)["guardrail_status"] == "BLOCK"
    assert guarded("口紅 " + term + "入り", market=market, category=category)["guardrail_status"] == "BLOCK"
    assert guarded("口紅 " + term + "を含む", market=market, category=category)["guardrail_status"] == "BLOCK"
    assert guarded(term, market=market, category="食品・飲料 > ワイン")["guardrail_status"] == "BLOCK"
    assert guarded(term, market=market, category="スポーツ > グリップ")["guardrail_status"] == "BLOCK"
    assert guarded(term, market=market)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("phrase", [
    "お手持ちの香水に合います",
    "お手持ちのスキンケア・香水の香りを邪魔したくない方にも使いやすい",
    "香水や他のフレグランスを使用する方におすすめ",
    "香水の香りを邪魔しない",
])
def test_only_a_reference_to_the_users_other_perfume_is_excluded(market, phrase):
    assert guarded(market=market, description=phrase)["guardrail_status"] == "SAFE"
    assert guarded("香水", market=market, description=phrase)["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description=phrase + "。この商品は香水です")["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description=phrase + "。本品は香水タイプです")["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description=phrase + "。オードパルファム入り")["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("title", ["香水", "オードトワレ", "オードパルファム", "フレグランス", "perfume", "fragrance", "ワイン", "日本酒", "マッチ", "ライター"])
def test_actual_restricted_products_remain_blocked(market, title):
    assert guarded(title, market=market)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("category", ["香水", "フレグランス", "香水・フレグランス", "オードトワレ", "perfume", "fragrance"])
def test_perfume_product_category_is_blocked_even_with_an_other_perfume_reference(market, category):
    assert guarded(market=market, category="ビューティー > " + category,
                   description="お手持ちの香水に合います")["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_perfume_mentions_without_confirmed_other_product_context_still_block(market):
    assert guarded(market=market, description="香水を同梱しています")["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description="無香料。香水を同梱しています")["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description="お手持ちの香水を同梱しています")["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description="香水のような商品です")["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description="本品はフレグランスです")["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description="This product is a perfume")["guardrail_status"] == "BLOCK"
    assert guarded("フレグランスフリーの乳液", market=market)["guardrail_status"] == "SAFE"
    assert guarded("fragrance-free lotion", market=market)["guardrail_status"] == "SAFE"
