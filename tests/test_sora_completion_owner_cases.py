"""Offline regressions: synthetic facts based on the Owner's completion findings.

ASIN labels preserve traceability, but the facts below are constructed examples;
the SP-API payloads and complete descriptions were not saved.  These tests do not
claim to replay the actual products or to establish their real post-change outcome.
"""
import pytest

from modules.guardrails import apply_guardrails
from modules.safety_policy import evaluate_policy


def _facts(title, category="", **kwargs):
    return {"product_title": title, "category": category, **kwargs}


# Each product ID explicitly supplied by the Owner is represented.  Product
# data, including category paths, is synthetic and is not a captured response.
OWNER_CASES = (
    ("laundry-attack", "PH", ("B0GM6XJJST", "B0GM6SYX5M", "B0H2YN8M5Q", "B0GM6JWGHB", "B0GYRM1TJJ", "B0GM6R2W5Q"),
     _facts("アタックZERO 液体洗剤", "ドラッグストア > 洗濯用洗剤 > 液体洗剤"), "BLOCK"),
    ("laundry-delicate", "SG", ("B0CK254DBL",), _facts("NANOX 業務用おしゃれ着洗剤", "洗濯用洗剤 > 液体洗剤"), "BLOCK"),
    ("laundry-utamaro", "SG", ("B0088B5GLQ",), _facts("ウタマロリキッド", "洗濯用洗剤 > 液体洗剤"), "BLOCK"),
    ("laundry-fafa", "SG", ("B09BQNPG3N",), _facts("ファーファ 液体洗剤", "洗濯用洗剤 > 液体洗剤"), "BLOCK"),
    ("laundry-partial", "SG", ("B0012P1WRW",), _facts("NANOX エリそで用", "洗濯用洗剤 > 部分洗い"), "BLOCK"),
    ("laundry-soap", "SG", ("B08GCXR49B",), _facts("arau.ベビー 洗濯せっけん", "洗濯用洗剤 > ベビー用"), "BLOCK"),
    ("laundry-review", "SG", ("B0CFZSFBDS",), _facts("ヤシノミ 洗たく洗剤", "洗濯用洗剤 > 液体洗剤", features=["漂白剤"]), "BLOCK"),
    ("dish-soap", "SG", ("B09KVFTKD9", "B0DSKZKQ28", "B0CTCL695L"),
     _facts("食器用の液体洗剤", "ドラッグストア > 食器用洗剤 > 液体洗剤"), "SAFE"),
    ("supplement-fish", "SG", ("B003G90UTI",), _facts("深海ザメエキスカプセル", "健康食品 > フィッシュオイル"), "BLOCK"),
    ("supplement-diet", "SG", ("B005S9IYZ6", "B08TRW8Z41"), _facts("ガルシニア", "健康食品 > ダイエットサプリ"), "BLOCK"),
    ("supplement-foshu", "SG", ("B01LW54CP4",), _facts("チョコラBBリッチ・セラミド", "健康食品 > 機能性表示食品"), "BLOCK"),
    ("adult-category", "SG", ("B0FKRG2DZ2",), _facts("高貴な王女の白濁ローション", "アダルト > ローション > スタンダード"), "BLOCK"),
    ("scar-care", "PH", ("B01I74S9BC", "B08HDKVMKY", "B07DJDGQNY", "B01I74U2EE"),
     _facts("アトファイン 傷あとケアテープ", "衛生用品・ヘルスケア > 傷あとケア"), "BLOCK"),
    ("cologne", "SG", ("B0087WWXFS",), _facts("タクティクス アフターシェーブコロン", "ビューティー > コロン"), "BLOCK"),
    ("shampoo-fragrance", "SG", ("B08LW83L8M",),
     _facts("LUX シャンプー", "ヘアケア > シャンプー", description="まるで香水のような香り立ち"), "SAFE"),
    ("lotion-ethanol-middle", "SG", ("B097T3ML15", "B097T5L9BJ"),
     _facts("アクアレーベル化粧水", "化粧水", ingredients=["水、グリセリン、エタノール、香料"]), "SAFE"),
    ("corporation", "PH", ("B0H8DJ97P2", "B0H8DLYGQZ", "B0H8DKRHHL", "B0H8DW3L7V", "B0H8DRKLJJ", "B0H8DN79NH"),
     _facts("ぷっくりシール", "おもちゃ > シール", features=["株式会社サンリオ"]), "SAFE"),
    ("gavan", "SG", ("B0GGNFZ99L", "B0GR32PH7R", "B0GR3BMSX5"),
     _facts("超宇宙刑事ギャバン", "おもちゃ > フィギュア", features=["電池を使用（同梱有無は未確認）"]), "REVIEW"),
    ("toy-toothbrush", "PH", ("B01AR9XOL0", "B08VX5LNF1"),
     _facts("人形のおせわセット", "おもちゃ > 人形・ドール > ままごと", features=["歯ブラシ ハブラシ"]), "SAFE"),
    ("toy-coin", "PH", ("B06XD17BJJ",), _facts("人形のじどうはんばいき", "おもちゃ > ままごと", features=["コイン"]), "SAFE"),
    ("toy-milk", "PH", ("B0B62M21XH",), _facts("人形のレンジとれいぞうこセット", "おもちゃ > ままごと", features=["牛乳"]), "SAFE"),
    ("nail-tools", "SG", ("B07QDWVSL3", "B018RTMDEQ"), _facts("爪切り", "ビューティー > ネイル > ネイル道具・ケアツール > 爪切り"), "SAFE"),
    ("plant-extract", "SG", ("B01MTDET4L",), _facts("和漢植物 洗顔", "ビューティー > スキンケア > 洗顔料"), "SAFE"),
    ("softener-fragrance", "SG", ("B0FMWQSW3G",), _facts("ファインフレグランス 柔軟剤", "洗濯用品 > 柔軟剤"), "SAFE"),
    ("haircolor-lasting", "SG", ("B0DSGWF4HV",), _facts("UV ヘアカラーラスティング&スタイリング バーム", "ビューティー > スタイリング"), "SAFE"),
    ("dishwasher-detergent", "SG", ("B0GKNHS61H",), _facts("食洗機用洗剤", "台所用品 > 食器用洗剤"), "SAFE"),
    ("bath-fertilizer-grade", "PH", ("B00C1CACNU",),
     _facts("エプソムソルト 入浴剤", "バス用品 > 入浴剤", features=["食添→特号→肥料"]), "SAFE"),
)


@pytest.mark.parametrize("case,market,asin,facts,expected", [
    pytest.param(case, market, asin, facts, expected, id=f"{case}-{market}-{asin}")
    for case, market, asins, facts, expected in OWNER_CASES for asin in asins
])
def test_owner_cases_with_explicitly_synthetic_facts(case, market, asin, facts, expected):
    row = {"candidate_asin": asin, **facts}
    assert apply_guardrails([row], marketplace=market)[0]["guardrail_status"] == expected


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("category", ["洗濯用洗剤 > 液体洗剤", "サプリメント > フィッシュオイル",
                                      "アダルト > ローション", "衛生用品 > 術後ケア"])
def test_unsafe_parent_category_is_a_shared_stop_signal(market, category):
    assert apply_guardrails([_facts("普通の商品", category)], marketplace=market)[0]["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("title", ["衣料用液体洗剤", "洗濯用粉末洗剤", "洗濯用ジェルボール", "おしゃれ着用液体洗剤"])
def test_specific_clothing_detergent_forms_are_stopped(market, title):
    assert apply_guardrails([_facts(title)], marketplace=market)[0]["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("title", ["食器用洗剤", "柔軟剤", "普通のばんそうこう", "非医療用テープ"])
def test_specific_safe_neighbours_are_not_swept_up(market, title):
    assert apply_guardrails([_facts(title)], marketplace=market)[0]["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["PH", "SG"])
def test_wound_care_direct_negation_does_not_hide_a_separate_positive(market):
    assert apply_guardrails([_facts("普通のばんそうこう", description="術後ケアではありません")],
                            marketplace=market)[0]["guardrail_status"] == "SAFE"
    assert apply_guardrails([_facts("傷あとケアテープ", description="術後ケアではありません")],
                            marketplace=market)[0]["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["PH", "SG"])
def test_softener_survives_a_laundry_parent_and_a_separate_detergent_still_stops(market):
    softener = _facts("香りの柔軟剤", "洗濯用洗剤 > 柔軟剤", description="洗濯用洗剤と併用")
    assert apply_guardrails([softener], marketplace=market)[0]["guardrail_status"] == "SAFE"
    combined = _facts("柔軟剤入り洗濯用洗剤", "洗濯用洗剤 > 柔軟剤")
    assert apply_guardrails([combined], marketplace=market)[0]["guardrail_status"] == "BLOCK"
    for included in ("洗濯用洗剤", "衣料用液体洗剤", "洗濯用ジェルボール", "洗濯せっけん"):
        bundle = _facts("柔軟剤", "柔軟剤", description=included + "を同梱")
        assert apply_guardrails([bundle], marketplace=market)[0]["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("phrase", ["コロン", "オーデコロン", "オードコロン", "cologne", "eau de cologne",
                                    "アフターシェーブコロン", "アフターシャワーコロン", "ボディコロン", "ヘアコロン"])
@pytest.mark.parametrize("field", ["product_title", "description", "category"])
def test_cologne_is_blocked_in_each_requested_field(market, phrase, field):
    assert any(h.action == "BLOCK" and h.rule_id == "COMMON-SLS-PERFUME"
               for h in evaluate_policy({field: phrase}, market))


@pytest.mark.parametrize("phrase", ["コロンビア", "Columbia", "コロンとした形", "ころんとした形", "セミコロン", "コロン記号"])
def test_cologne_exclusions_do_not_hide_a_real_cologne(phrase):
    assert not any(h.rule_id == "COMMON-SLS-PERFUME" for h in evaluate_policy({"product_title": phrase}, "SG"))
    assert any(h.rule_id == "COMMON-SLS-PERFUME" for h in evaluate_policy({"product_title": phrase + " コロン"}, "SG"))


def test_cologne_inside_a_category_node_is_detected_without_matching_colombia():
    assert any(h.rule_id == "COMMON-SLS-PERFUME" for h in evaluate_policy({"category": "ビューティー > メンズコロン"}, "SG"))
    assert not any(h.rule_id == "COMMON-SLS-PERFUME" for h in evaluate_policy({"category": "ブランド > コロンビア"}, "SG"))


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("ingredients,expected", [
    (["エタノール、水、香料"], "BLOCK"), (["水、エタノール、香料"], "BLOCK"),
    (["水、グリセリン、エタノール"], "SAFE"), (["水", "グリセリン", "エタノール"], "SAFE"),
    (["水", "エタノール", "香料"], "BLOCK"),
])
def test_ethanol_requires_first_or_second_position_in_full_ingredients(market, ingredients, expected):
    assert apply_guardrails([_facts("普通の化粧水", ingredients=ingredients)], marketplace=market)[0]["guardrail_status"] == expected


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("description,should_block", [
    ("全成分：エタノール、水、香料", True),
    ("【全成分】水、エタノール、香料", True),
    ("全成分：水、グリセリン、エタノール", False),
    ("水、エタノール、香料", False),  # No heading: position is not established.
    ("エタノールを含む化粧水です", False),
])
def test_ethanol_text_position_needs_a_confirmed_ingredient_list(market, description, should_block):
    hits = evaluate_policy(_facts("化粧水", description=description), market)
    assert any(h.rule_id == "COMMON-TRANSPORT-ETHANOL-LEADING" for h in hits) is should_block


def test_adult_use_statement_is_a_stop_without_assuming_a_missing_ancestor():
    hits = evaluate_policy(_facts("ローション", description="自慰用"), "SG")
    assert any(h.rule_id == "COMMON-ADULT-TOY" and h.action == "BLOCK" for h in hits)


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("phrase", ["アダルト用品", "アダルト商品", "性玩具", "adult product"])
def test_clear_adult_product_description_is_a_block(market, phrase):
    hits = evaluate_policy(_facts("普通の商品", description=phrase), market)
    assert any(h.rule_id == "COMMON-ADULT-TOY" and h.action == "BLOCK" for h in hits)


def test_scent_exclusion_does_not_release_a_perfume_named_as_a_fragrance():
    assert apply_guardrails([_facts("フレグランス", "シャンプー")], marketplace="SG")[0]["guardrail_status"] == "BLOCK"
    assert apply_guardrails([_facts("シャンプー", "シャンプー", description="香水のような香り。香水を同梱")],
                            marketplace="SG")[0]["guardrail_status"] == "BLOCK"
    for title in ("フレグランスとシャンプーのセット", "シャンプーとフレグランスのセット", "フレグランス＋柔軟剤"):
        assert apply_guardrails([_facts(title, "ビューティー")], marketplace="SG")[0]["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("title", [
    "フレグランス 30mL + シャンプー 300mL セット",
    "シャンプー 300mL と フレグランス 30mL セット",
    "柔軟剤 500mL ＆ フレグランス 30mL",
    "フレグランス 30mL・ボディソープ",
    "フレグランス 30mL シャンプー 300mL セット",
    "フレグランス 30mL + LUX シャンプー 300mL セット",
    "シャンプー 300mL と ギフト用フレグランス 30mL セット",
])
def test_scent_exclusion_keeps_separate_sized_fragrance_in_bundle(market, title):
    result = apply_guardrails([_facts(title, "ビューティー")], marketplace=market)[0]
    assert result["guardrail_status"] == "BLOCK"
    assert "COMMON-SLS-PERFUME" in result["guardrail_note"]


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("title", [
    "ファインフレグランス 500mL 柔軟剤",
    "シャンプー 300mL と トリートメントのフレグランス",
])
def test_scent_wording_in_wash_products_is_not_a_separate_perfume(market, title):
    result = apply_guardrails([_facts(title, "ビューティー")], marketplace=market)[0]
    assert result["guardrail_status"] == "SAFE"


def test_perfume_smell_comparison_may_include_a_bounded_adjective():
    safe = _facts("シャンプー", "シャンプー", description="まるで香水のような華やかな香り")
    actual = _facts("シャンプー", "シャンプー", description="香水のような商品です")
    assert apply_guardrails([safe], marketplace="SG")[0]["guardrail_status"] == "SAFE"
    assert apply_guardrails([actual], marketplace="SG")[0]["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("title", ["フレグランス ボディソープ", "フレグランス コンディショナー", "フレグランス 洗顔"])
def test_fragrance_wording_in_identifiable_wash_products_does_not_become_perfume(title):
    assert apply_guardrails([_facts(title, "ビューティー")], marketplace="SG")[0]["guardrail_status"] == "SAFE"
    assert apply_guardrails([_facts(title + " 香水付き", "ビューティー")], marketplace="SG")[0]["guardrail_status"] == "BLOCK"


def test_gavan_exclusion_keeps_a_separate_gaba_match_and_its_context():
    result = apply_guardrails([_facts("ギャバンとギャバ")], marketplace="SG")[0]
    assert result["guardrail_status"] == "BLOCK"
    assert "PH-V2-INGREDIENT-GABA-006" in result["guardrail_note"]


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("company", ["株式会社", "(株)", "㈱"])
def test_company_forms_do_not_match_finance_but_real_shares_still_do(market, company):
    assert not any(h.rule_id == "COMMON-FINANCE" for h in evaluate_policy({"features": [company + "サンリオ"]}, market))
    assert any(h.rule_id == "COMMON-FINANCE" for h in evaluate_policy({"features": [company + "の株式"]}, market))


def test_fertilizer_grade_exclusion_is_bounded_to_bath_product_and_one_occurrence():
    bath = _facts("エプソムソルト", "入浴剤", features=["原料等級 食添→特号→肥料"])
    other = _facts("原料", "雑貨", features=["原料等級 食添→特号→肥料"])
    separate = _facts("入浴剤と肥料", "入浴剤", features=["食添→特号→肥料"])
    assert not any(h.rule_id == "PH-SLS" and h.term == "肥料" for h in evaluate_policy(bath, "PH"))
    assert any(h.rule_id == "PH-SLS" and h.term == "肥料" for h in evaluate_policy(other, "PH"))
    assert any(h.rule_id == "PH-SLS" and h.term == "肥料" for h in evaluate_policy(separate, "PH"))


@pytest.mark.parametrize("warning", ["火気注意", "火気厳禁", "引火性"])
def test_flammable_warning_blocks_identifiable_liquid_but_not_general_aerosol(warning):
    liquid = _facts("化粧水", "ビューティー > 化粧水", safetyWarning=warning)
    aerosol = _facts("ヘアスプレー", "ヘアスプレー", safetyWarning=warning)
    assert any(h.rule_id == "COMMON-TRANSPORT-FLAMMABLE-LIQUID" and h.action == "BLOCK" for h in evaluate_policy(liquid, "SG"))
    assert not any(h.rule_id == "COMMON-TRANSPORT-FLAMMABLE-LIQUID" for h in evaluate_policy(aerosol, "SG"))


def test_aerosol_does_not_become_a_liquid_merely_by_comparing_itself_to_lotion():
    aerosol = _facts("ヘアスプレー", "ヘアスプレー", description="化粧水のような潤い。火気厳禁")
    assert not any(h.rule_id == "COMMON-TRANSPORT-FLAMMABLE-LIQUID" for h in evaluate_policy(aerosol, "SG"))


def test_explicit_liquid_category_or_own_product_statement_supports_a_stop():
    for row in (_facts("普通の品", "引火性の液体"),
                _facts("普通の品", "雑貨", description="本品は液体です。火気注意")):
        assert any(h.rule_id == "COMMON-TRANSPORT-FLAMMABLE-LIQUID" for h in evaluate_policy(row, "SG"))


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("title", ["香水", "オードトワレ", "オードパルファム", "フレグランス", "ワイン", "日本酒", "マッチ", "ライター",
                                   "ヘアカラー", "ジェルネイル", "マニキュア", "観葉植物", "医薬部外品", "レチノール"])
def test_existing_positive_stops_remain(market, title):
    assert apply_guardrails([_facts(title)], marketplace=market)[0]["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["PH", "SG"])
def test_masking_an_occurrence_never_hides_an_independent_real_hit(market):
    examples = [
        _facts("普通の品", description="株式会社サンリオ。株式を販売"),
        _facts("超宇宙刑事ギャバン GABA配合"),
        _facts("爪切りとジェルネイルのセット", "ネイル > 爪切り"),
        _facts("和漢植物の洗顔と観葉植物", "ビューティー > スキンケア"),
        _facts("観葉和漢植物", "ビューティー > スキンケア"),
        _facts("和漢植物の本体と洗顔", "ビューティー > スキンケア"),
        _facts("柔軟剤と香水のセット", "柔軟剤"),
        _facts("ヘアカラーラスティング バームと染毛剤", "ビューティー"),
        _facts("食洗機用洗剤と食洗機本体", "台所用品"),
        _facts("食洗機用本体と洗剤", "台所用品"),
    ]
    for row in examples:
        assert apply_guardrails([row], marketplace=market)[0]["guardrail_status"] == "BLOCK", row


def test_ph_oral_and_other_non_toy_products_still_stop():
    for row in (_facts("歯ブラシ", "オーラルケア"), _facts("牛乳", "食品 > 飲料"), _facts("コイン", "貨幣")):
        assert apply_guardrails([row], marketplace="PH")[0]["guardrail_status"] == "BLOCK"
    assert apply_guardrails([_facts("歯ブラシ", "オーラルケア")], marketplace="SG")[0]["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["PH", "SG"])
def test_battery_and_brand_stops_are_independent_of_toy_exclusions(market):
    toy = _facts("人形の歯ブラシ", "おもちゃ > 人形", features=["電池付属"])
    assert apply_guardrails([toy], marketplace=market)[0]["guardrail_status"] == "BLOCK"
    assert apply_guardrails([_facts("普通の品", brand="Biore")], marketplace=market)[0]["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("title", ["アリエール 洗濯洗剤", "ナノックス 洗濯洗剤", "エマール おしゃれ着洗剤",
                                   "ボールド 洗濯洗剤", "ディアナチュラ サプリメント", "Nature Made サプリメント",
                                   "ザバス 牛乳", "コンドーム", "不織布マスク", "ドライヤー", "ヘアアイロン",
                                   "プリオール 医薬部外品", "レチノール", "香水", "電池付属 おもちゃ"])
def test_owner_previously_blocked_product_types_stay_blocked(market, title):
    assert apply_guardrails([_facts(title)], marketplace=market)[0]["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("brand", ["Biore", "Maybelline", "Nivea", "Curel", "Ariel", "Eisai", "エーザイ"])
def test_owner_named_brand_stops_remain_or_gain_the_requested_exact_alias(market, brand):
    assert apply_guardrails([_facts("普通の品", brand=brand)], marketplace=market)[0]["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("brand", ["Kao", "Kewpie"])
def test_sg_brand_scope_is_preserved(brand):
    assert apply_guardrails([_facts("普通の品", brand=brand)], marketplace="SG")[0]["guardrail_status"] == "BLOCK"
    assert apply_guardrails([_facts("普通の品", brand=brand)], marketplace="PH")[0]["guardrail_status"] == "SAFE"


def test_new_brand_alias_is_not_a_substring_or_an_ipr_claim():
    row = apply_guardrails([_facts("普通の品", brand="Eisai")], marketplace="SG")[0]
    assert "PH-SG-COMMUNITY-EISAI-ALIAS" in row["guardrail_note"]
    assert apply_guardrails([_facts("普通の品", brand="Eisai関連")], marketplace="SG")[0]["guardrail_status"] == "SAFE"


def test_existing_aerosol_review_is_not_released_or_reclassified_as_liquid_block():
    result = apply_guardrails([_facts("黒ばら ヘアスプレー", category="ヘアスプレー")], marketplace="SG")[0]
    assert result["guardrail_status"] == "REVIEW"


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("parent,leaf", [("洗濯用洗剤", "液体洗剤"), ("サプリメント", "フィッシュオイル"),
                                        ("アダルト", "ローション"), ("衛生用品", "術後ケア")])
def test_sp_api_ancestor_reaches_the_real_sora_gate_without_a_network_call(market, parent, leaf):
    from modules.asin_resolver import preview_candidates, verify_preview_rows
    from modules.sora_run import evaluate_sora_run, prepare_sora_run
    from modules.sp_api_catalog import JP_MARKETPLACE, normalize_catalog_item

    class Client:
        provider_name = "sp_api_catalog_2022_04_01"
        product_field_prefix = "spapi"
        verification_label = "SP_API_VERIFIED"

        def verify_products_by_asin(self, asins):
            return {asin: normalize_catalog_item({
                "asin": asin, "attributes": {},
                "summaries": [{"marketplaceId": JP_MARKETPLACE, "itemName": "普通の商品", "brand": "試験ブランド"}],
                "classifications": [{"marketplaceId": JP_MARKETPLACE, "classifications": [
                    {"displayName": leaf, "parent": {"displayName": parent}}]}],
            }, fetched_at="2026-11-01T09:00:00+00:00") for asin in asins}

    verified = verify_preview_rows(preview_candidates("B000000001"), Client())
    run = prepare_sora_run(verified, marketplace=market, auth_calls=0, catalog_calls=0, input_files=("synthetic.txt",))
    assert evaluate_sora_run(run).rows[0].final_eligibility == "EXCLUDE"


@pytest.mark.parametrize("ingredients,expected", [
    ("水、エタノール、香料", "EXCLUDE"),
    ("水、グリセリン、エタノール", "ELIGIBLE"),
])
def test_structured_sp_api_ingredients_reach_the_sora_gate_offline(ingredients, expected):
    from modules.asin_resolver import preview_candidates, verify_preview_rows
    from modules.sora_run import evaluate_sora_run, prepare_sora_run
    from modules.sp_api_catalog import JP_MARKETPLACE, normalize_catalog_item

    class Client:
        provider_name = "sp_api_catalog_2022_04_01"
        product_field_prefix = "spapi"
        verification_label = "SP_API_VERIFIED"

        def verify_products_by_asin(self, asins):
            return {asin: normalize_catalog_item({
                "asin": asin, "attributes": {"ingredients": [{"value": ingredients}]},
                "summaries": [{"marketplaceId": JP_MARKETPLACE, "itemName": "普通の化粧水", "brand": "試験ブランド",
                               "browseClassification": {"displayName": "化粧水"}}],
            }, fetched_at="2026-11-01T09:00:00+00:00") for asin in asins}

    verified = verify_preview_rows(preview_candidates("B000000001"), Client())
    run = prepare_sora_run(verified, marketplace="SG", auth_calls=0, catalog_calls=0, input_files=("synthetic.txt",))
    assert evaluate_sora_run(run).rows[0].final_eligibility == expected
