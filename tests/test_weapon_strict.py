"""DEC-0190: synthetic weapon names and harmless controls, with no live API."""
import pytest

from modules.guardrails import apply_guardrails
from modules.safety_policy import evaluate_policy, load_policy_rules


MARKETS = ("MY", "SG", "PH", "TH", "TW")
STRICT_TITLES = (
    "モデルガン", "模造銃", "レプリカ銃", "拳銃", "ピストル", "リボルバー", "ライフル", "ショットガン",
    "マシンガン", "機関銃", "鉄砲", "ゴム鉄砲", "輪ゴム銃",
    "模造刀", "模擬刀", "居合刀", "日本刀", "木刀", "刀剣", "太刀", "脇差", "短刀", "小太刀", "薙刀",
    "日輪刀", "ライトセーバー", "刀", "剣", "ヌンチャク", "トンファー", "メリケンサック", "ナックルダスター",
    "警棒", "特殊警棒", "伸縮警棒", "手裏剣", "苦無", "クナイ", "鉄扇", "吹き矢", "弓矢", "クロスボウ",
    "ボウガン", "スリングショット", "唐辛子スプレー", "replica gun", "toy gun", "pistol", "revolver",
    "rifle", "nunchaku", "brass knuckles", "baton", "shuriken", "crossbow", "slingshot", "blowgun",
    "ピストル型 キーホルダー", "鬼滅の刃 日輪刀 おもちゃ", "刀 フィギュア",
)
HARMLESS_TITLES = (
    "ガンダム プラモデル", "グルーガン", "ヒートガン", "エアダスターガン", "剣山（生け花）",
    "真剣ゼミ", "刀削麺", "剣菱", "爪切り", "けん玉", "防犯ブザー", "鬼滅の刃 フィギュア",
)
PART_TERMS = ("武器パーツ付属", "武器付属", "剣付属", "銃付属", "ライフル付属", "ソードが付属", "武器セット")


@pytest.fixture(autouse=True)
def no_live_requests(monkeypatch):
    monkeypatch.setattr("requests.Session.request", lambda *a, **kw: pytest.fail("Live API reached"))


def status(market, title="キャラクター フィギュア", **facts):
    return apply_guardrails([{"product_title": title, **facts}], marketplace=market)[0]["guardrail_status"]


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("title", STRICT_TITLES)
def test_weapons_and_owner_reported_misses_block_in_every_market(market, title):
    assert status(market, title) == "BLOCK"


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("title", HARMLESS_TITLES)
def test_harmless_names_remain_safe_without_other_product_facts(market, title):
    assert status(market, title) == "SAFE"


@pytest.mark.parametrize("market", MARKETS)
def test_office_scissors_keep_taiwan_review_without_an_office_exception(market):
    assert status(market, "ハサミ 事務用") == ("REVIEW" if market == "TW" else "SAFE")


@pytest.mark.parametrize("market", MARKETS)
def test_sharpeners_do_not_match_the_new_weapon_rules(market):
    # Other country knife rules remain independent; this exclusion is not a
    # general permission for sharpening tools in every market.
    assert not any(h.rule_id in {"COMMON-WEAPON-STRICT", "COMMON-WEAPON-SHAPED-ACCESSORY"}
                   for h in evaluate_policy({"product_title": "包丁研ぎ器"}, market))


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("weapon", ("銃", "ピストル", "拳銃", "刀", "剣", "ナイフ"))
@pytest.mark.parametrize("accessory", ("キーホルダー", "キーチェーン", "ペンダント", "ネックレス", "ストラップ", "チャーム", "フィギュア"))
def test_weapon_and_accessory_must_coexist_in_the_title(market, weapon, accessory):
    assert status(market, weapon + " " + accessory) == "BLOCK"
    assert status(market, weapon + accessory) == "BLOCK"
    assert status(market, accessory + weapon) == "BLOCK"
    assert status(market, "ハート " + accessory) == "SAFE"


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("title", ("防弾チョッキ", "防弾ベスト", "防刃ベスト", "スチールヘルメット", "軍服",
                                    "軍装備", "警察 制服", "警察 バッジ", "勲章"))
def test_military_and_police_gear_blocks_everywhere(market, title):
    assert status(market, title) == "BLOCK"


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("category", ("おもちゃ", "ホビー > フィギュア", "プラモデル", "フィギュア"))
@pytest.mark.parametrize("text", PART_TERMS)
def test_hobby_accessory_mentions_in_description_need_review(market, category, text):
    assert status(market, category=category, description=text) == "REVIEW"


@pytest.mark.parametrize("market", MARKETS)
def test_accessory_review_keeps_other_blocks_and_requires_real_category(market):
    facts = {"category": "ホビー > フィギュア", "description": "武器パーツ付属"}
    assert status(market, "刀 フィギュア", **facts) == "BLOCK"
    assert status(market, **{**facts, "description": "武器パーツ付属。スタンガン同梱"}) == "BLOCK"
    for category in ("", "文具", "ホビー風雑貨"):
        assert not any(h.rule_id == "COMMON-WEAPON-ACCESSORY-REVIEW"
                       for h in evaluate_policy({"product_title": "フィギュア", "description": "武器パーツ付属",
                                                 "category": category}, market))


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("title", ("剣道 竹刀", "竹刀", "剣道", "ダーツ セット", "アーチェリー", "弓（スポーツ用）"))
def test_sport_equipment_needs_review_but_taiwan_darts_still_block(market, title):
    assert status(market, title) == ("BLOCK" if market == "TW" and title == "ダーツ セット" else "REVIEW")


@pytest.mark.parametrize("market", MARKETS)
def test_exclusions_preserve_an_independent_weapon_occurrence(market):
    for title in ("剣山、刀", "真剣ゼミ、剣 フィギュア", "水鉄砲、鉄砲", "グルーガンとピストル"):
        assert status(market, title) == "BLOCK"
    for title in ("replica gun case", "PISTOL", "木刀ケース"):
        assert status(market, title) == "BLOCK"
    assert status(market, "pistolsleeve") == "SAFE"


def test_water_gun_preserves_existing_country_handling_and_protected_fixture():
    # The real SG default currently has no literal 水鉄砲 entry; its protected
    # dictionary fixture supplies REVIEW. Neither may become a strict BLOCK.
    for market in MARKETS:
        assert not any(h.rule_id == "COMMON-WEAPON-STRICT"
                       for h in evaluate_policy({"product_title": "水鉄砲"}, market))
    assert status("PH", "水鉄砲") == "BLOCK"
    assert status("SG", "ウォーターガン") == "REVIEW"


@pytest.mark.parametrize("market", MARKETS)
def test_new_item_rules_never_read_product_description_or_ingredients(market):
    rules = [r for r in load_policy_rules() if r["id"] in {
        "COMMON-WEAPON-STRICT", "COMMON-WEAPON-SHAPED-ACCESSORY", "COMMON-MILITARY-POLICE-GEAR",
        "COMMON-SPORT-WEAPON-REVIEW"}]
    assert len(rules) == 4 and all(r["scope"] == "item" and r["markets"] == ["ALL"] for r in rules)
    assert not evaluate_policy({"product_title": "普通の雑貨", "description": "木刀 警棒 防弾ベスト ダーツ",
                                "ingredients": ["日本刀"]}, market, rules=rules)
    assert any(h.rule_id == "COMMON-WEAPON-STRICT" and h.field == "category"
               for h in evaluate_policy({"product_title": "セット", "category": "ホビー > 木刀"}, market, rules=rules))


BORROWED_TITLES = (
    "ピストル型 シャワーヘッド", "ピストル型 散水ノズル", "ライフル スコープ カバー",
    "銃型 シャワーヘッド", "刀風 傘", "剣形 雑貨", "ナイフ型 雑貨", "ナイフ柄の飾り", "ソード風 雑貨",
    "pistol-shaped showerhead", "rifle scope cover", "knife-shaped decoration", "sword-shaped decoration",
    "ライフル用 未知の道具", "cover for rifle", "サバイバルナイフ型",
)


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("title", BORROWED_TITLES)
def test_borrowed_shapes_and_parts_are_review_without_product_exceptions(market, title):
    assert status(market, title) == "REVIEW"


@pytest.mark.parametrize("market", MARKETS)
def test_borrowed_part_review_does_not_release_separate_th_license_stop(market):
    assert status(market, "Kitchen knife case") == ("BLOCK" if market == "TH" else "REVIEW")
    if market == "TH":
        assert any(h.rule_id == "TH-LICENSE-OTHER" and h.action == "BLOCK"
                   for h in evaluate_policy({"product_title": "Kitchen knife case"}, market))


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("word", ("ピストル", "ライフル", "銃", "刀", "剣", "ナイフ", "ソード", "pistol", "rifle", "sword", "knife"))
def test_borrowable_names_block_as_bodies_and_review_as_unknown_product_shapes(market, word):
    assert status(market, word) == "BLOCK"
    for suffix in ("型", "風", "形"):
        assert status(market, word + suffix + " 未知の道具") == "REVIEW"


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("kind", ("おもちゃ", "玩具", "トイ", "キーホルダー", "キーチェーン", "ペンダント", "ネックレス",
                                  "ストラップ", "チャーム", "フィギュア", "レプリカ", "コスプレ", "模型"))
def test_toy_and_decoration_kinds_block_even_when_the_weapon_is_a_shape_modifier(market, kind):
    assert status(market, "ライフル型 " + kind) == "BLOCK"


@pytest.mark.parametrize("market", MARKETS)
def test_real_weapons_and_other_blocks_cannot_be_hidden_by_a_borrowed_occurrence(market):
    for title in ("エアソフト ピストル", "おもちゃ ピストル", "ピストル型道具、ピストル本体",
                  "ライフル スコープ カバー、ライフル付属", "ライフルとカバー",
                  "ライフル ケース付き", "rifle case included", "ライフル 型番123",
                  "ピストル型道具 スタンガン同梱", "模造刀型の未知の道具", "モデルガン用ケース"):
        assert status(market, title) == "BLOCK"
    assert status(market, "gun") == "SAFE"
    assert status(market, "銃型") == "REVIEW"
    assert status(market, "ピストル型 トイレットペーパーホルダー") == "REVIEW"


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("field", ("features", "description"))
@pytest.mark.parametrize("text", ("ビームライフル、シールドが付属", "日輪刀が付属します", "武器パーツ同梱",
                                  "武器パーツ付き", "剣と盾のセット", "ブレードと槍が付属", "弓が同梱",
                                  "ピストルが付属", "ナイフが付属", "ソードが付属", "銃が付属"))
def test_realistic_hobby_attachment_sentences_review_in_each_description_field(market, field, text):
    value = [text] if field == "features" else text
    assert status(market, "ガンダム プラモデル", category="ホビー > プラモデル", **{field: value}) == "REVIEW"


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("facts", (
    {"description": "台座が付属"}, {"description": "ソード"},
    {"description": "ライフルを構える。台座が付属"},
    {"description": "ライフルを構える\n台座が付属"},
    {"description": "ライフルを構える</p><p>台座が付属"},
    {"features": ["ライフルを構える", "台座が付属"]},
    {"description": "ライフルを構える", "features": ["台座が付属"]},
    {"description": "剣山と台座が付属。真剣に作成"},
))
def test_hobby_review_does_not_cross_sentences_feature_values_or_fields(market, facts):
    assert status(market, "ガンダム プラモデル", category="ホビー > プラモデル", **facts) == "SAFE"


@pytest.mark.parametrize("market", MARKETS)
def test_hobby_attachment_review_preserves_title_and_other_weapon_blocks(market):
    facts = {"category": "おもちゃ", "features": ["ビームライフル、シールドが付属"]}
    assert status(market, "モデルガン", **facts) == "BLOCK"
    assert status(market, "日輪刀 おもちゃ", **facts) == "BLOCK"
    assert status(market, "ガンダム プラモデル", **{**facts, "description": "スタンガン同梱"}) == "BLOCK"
