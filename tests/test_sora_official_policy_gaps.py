"""Synthetic representative names, not complete product records or live acceptance."""
import pytest

from modules.guardrails import apply_guardrails
from modules.safety_policy import evaluate_policy


def status(market, title="普通の商品", **facts):
    return apply_guardrails([{"product_title": title, **facts}], marketplace=market)[0]["guardrail_status"]


TOBACCO = ["タバコ", "たばこ", "煙草", "葉巻", "シガー", "シガリロ", "刻みたばこ",
           "キセル", "喫煙具", "喫煙パイプ", "シガレットケース"]
DRINKS = ["梅酒", "焼酎", "ウイスキー", "ウィスキー", "ブランデー", "ウォッカ", "リキュール",
          "果実酒", "洋酒", "清酒", "紹興酒", "泡盛", "チューハイ", "酎ハイ", "ハイボール", "シャンパン"]
PESTICIDES = ["殺虫剤", "農薬", "除草剤", "insecticide", "insecticides", "pesticide", "pesticides"]
TEST_KITS = ["HIV", "抗原検査キット", "PCR検査キット", "PCR 検査キット", "新型コロナ 検査キット"]


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("term", TOBACCO + DRINKS + PESTICIDES + ["べっ甲", "鼈甲"] + TEST_KITS)
def test_shared_requested_terms_block_in_title_and_description(market, term):
    assert status(market, term) == "BLOCK"
    assert status(market, description=term) == "BLOCK"


@pytest.mark.parametrize("market", ["PH", "SG"])
def test_shared_category_and_alcohol_strength(market):
    assert status(market, category="食品・飲料 > お酒 > 果実酒") == "BLOCK"
    assert status(market, "炭酸飲料", description="アルコール分 5%") == "BLOCK"
    assert status(market, "炭酸飲料", description="アルコール分 0%とアルコール分 5%をセット") == "BLOCK"
    assert status(market, "炭酸飲料", description="アルコール分 ０．００％") == "BLOCK"
    assert status(market, "化粧水", description="アルコール分 5%") == "REVIEW"
    assert status(market, "キャンディ", category="食品・飲料・お酒 > 菓子") == "SAFE"


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("title", ["シガーソケット", "タバコ臭を消す消臭剤", "たばこのにおいを消す消臭剤",
                                  "ウイスキーグラス", "焼酎グラス", "梅酒用の瓶", "梅酒用容器", "甘酒",
                                  "農作業用手袋", "琥珀のアクセサリー", "水質検査キット", "土壌検査キット"])
def test_shared_exclusions_remain_safe(market, title):
    assert status(market, title) == "SAFE"


@pytest.mark.parametrize("market", ["PH", "SG"])
def test_excluded_shared_occurrence_does_not_hide_another_positive(market):
    assert status(market, "消臭剤", description="タバコ臭やタバコのにおいを消す") == "SAFE"
    assert status(market, "タバコ臭を消す消臭剤と葉巻") == "BLOCK"
    assert status(market, "ウイスキーグラスとウイスキー") == "BLOCK"
    assert status(market, "消臭剤", description="タバコのにおいを消す。葉巻を同梱") == "BLOCK"
    for term in ("毒物", "劇物"):
        hits = evaluate_policy({"product_title": term}, market)
        assert any(h.rule_id == "COMMON-TRANSPORT-TOXIC" and h.action == "REVIEW" for h in hits)


SG_TERMS = [
    "ナイフ", "サバイバルナイフ", "アウトドアナイフ", "フォールディングナイフ", "knife",
    "ガム", "キシリトールガム", "モデルガン", "模造刀", "居合刀", "ガスガン", "電動ガン",
    "ガスブローバック", "エアガン用マガジン", "銃用マガジン", "銃の弾倉", "特殊警棒", "警棒",
    "タクティカルペン", "ピッキングツール", "電動キックボード", "電動アシスト自転車", "e-bike",
    "ドッグフード", "キャットフード", "ペットフード", "ラード", "牛脂", "ヘット",
    "マグネットパテ", "磁石スライム", "magnetic putty", "レーダー探知機", "スクランブラー",
    "人毛", "人毛ウィッグ", "人毛エクステ", "human hair",
]
MUSHROOMS = ["しいたけ", "椎茸", "きのこ", "キノコ", "まいたけ", "舞茸", "しめじ", "なめこ", "えのき", "きくらげ", "マッシュルーム", "トリュフ"]


@pytest.mark.parametrize("term", SG_TERMS)
def test_sg_requested_terms_block(term):
    assert status("SG", term) == "BLOCK"


@pytest.mark.parametrize("term", MUSHROOMS)
def test_sg_mushrooms_block_in_food_context(term):
    assert status("SG", term, category="食品 > 食材") == "BLOCK"


def test_sg_requested_categories_block():
    for category in ("食品 > ガム", "ペット用品 > ペットフード"):
        assert status("SG", category=category) == "BLOCK"


@pytest.mark.parametrize("text", ["アウトドアナイフ", "キシリトールガム", "モデルガン", "電動キックボード",
                                  "ドッグフード", "ラード", "マグネットパテ", "レーダー探知機", "人毛ウィッグ"])
def test_sg_requested_terms_also_block_in_product_text(text):
    assert status("SG", description=text) == "BLOCK"


@pytest.mark.parametrize("title,category", [
    ("バターナイフ", ""), ("ナイフ型の飾り", ""), ("ナイフ柄の飾り", ""),
    ("Kitchen knife case", ""), ("ガムテープ", ""), ("ガムシロップ", ""), ("アラビアガム", ""),
    ("マガジンラック", ""), ("雑誌", ""), ("キックボード", ""), ("ラード不使用", ""),
    ("普通の粘土", ""), ("時計", ""), ("人工毛ウィッグ", ""),
    ("きのこの山", "食品 > 菓子"), ("きのこの山と菓子", "食品 > 菓子"), ("きのこ形のおもちゃ", "おもちゃ"),
    ("きのこ型の雑貨", "生活雑貨"),
])
def test_sg_exclusions_remain_safe(title, category):
    assert status("SG", title, category=category) == "SAFE"


def test_sg_exclusions_do_not_hide_other_positive_occurrences():
    assert status("SG", "普通の雑貨", description="ナイフ柄の飾り") == "SAFE"
    assert status("SG", "バターナイフとサバイバルナイフ") == "BLOCK"
    assert status("SG", "サバイバルナイフ型") == "BLOCK"
    assert status("SG", "ガムテープとキシリトールガム") == "BLOCK"
    assert status("SG", "ラード不使用、牛脂入り") == "BLOCK"
    assert status("SG", "きのこの山と干ししいたけ", category="食品 > 食材") == "BLOCK"
    assert status("SG", "きのこ形の食品", category="食品") == "BLOCK"
    assert status("SG", "きのこの山盛り", category="食品") == "BLOCK"
    # The pre-existing rule for an explicitly weapon-shaped keychain remains.
    assert status("SG", "ナイフ型キーホルダー") == "BLOCK"


PH_TERMS = ["水鉄砲", "BB弾", "舌クリーナー", "舌ブラシ", "歯間ブラシ", "タフトブラシ", "入れ歯洗浄剤",
            "タトゥーマシン", "タトゥー針", "アートメイク", "刺青", "ペット用ノミ駆除", "犬のダニ駆除",
            "猫用駆虫薬", "フェイスマスク", "シートマスク", "フェイスパック", "シートパック"]


@pytest.mark.parametrize("term", PH_TERMS)
def test_ph_requested_terms_block(term):
    assert status("PH", term) == "BLOCK"


@pytest.mark.parametrize("term", ["銃", "ピストル", "ライフル", "ガン"])
def test_ph_generic_weapon_terms_require_toy_context(term):
    assert status("PH", "おもちゃの" + term) == "BLOCK"
    assert status("PH", term, category="おもちゃ > なりきり") == "BLOCK"


@pytest.mark.parametrize("title,category", [
    ("グルーガン", ""), ("ヒートガン", ""), ("マッサージガン", ""),
    ("スプレーガン", ""), ("エアダスターガン", ""), ("グルーガン", "おもちゃ"),
    ("ヘアブラシ", ""), ("タトゥーシール", ""), ("ノミダニ用ブラシ", ""), ("ヘアマスク", ""),
])
def test_ph_exclusions_remain_safe(title, category):
    assert status("PH", title, category=category) == "SAFE"


def test_ph_toy_exclusions_do_not_hide_an_independent_weapon():
    assert status("PH", "おもちゃのグルーガンとピストル") == "BLOCK"


@pytest.mark.parametrize("text", ["水鉄砲", "おもちゃのピストル", "舌クリーナー", "タトゥー針",
                                  "犬のノミ・ダニ駆除", "フェイスマスク"])
def test_ph_requested_terms_also_block_in_product_text(text):
    assert status("PH", description=text) == "BLOCK"


def test_ph_pet_category_provides_animal_context_and_oral_category_is_read():
    assert status("PH", "ノミ・ダニ駆除", category="ペット用品") == "BLOCK"
    assert status("PH", category="オーラルケア > 舌クリーナー") == "BLOCK"
    assert status("PH", "carpet ダニ駆除") == "SAFE"


def test_new_market_specific_rules_stay_in_their_market():
    cases = [
        ("SG-GENERAL-KNIFE", "アウトドアナイフ", "SG", "PH"),
        ("SG-GUM", "キシリトールガム", "SG", "PH"),
        ("SG-ANIMAL-FAT", "ラード", "SG", "PH"),
        ("SG-WEAPON-ADDITIONAL", "モデルガン", "SG", "PH"),
        ("SG-WEAPON-PART", "銃用マガジン", "SG", "PH"),
        ("SG-ELECTRIC-VEHICLE", "電動キックボード", "SG", "PH"),
        ("SG-PETFOOD", "ドッグフード", "SG", "PH"),
        ("SG-MAGNETIC-PUTTY", "マグネットパテ", "SG", "PH"),
        ("SG-RESTRICTED-ELECTRONICS", "レーダー探知機", "SG", "PH"),
        ("SG-HUMAN-HAIR", "人毛", "SG", "PH"),
        ("SG-MUSHROOM", "干ししいたけ", "SG", "PH"),
        ("PH-TOY-WEAPON-DIRECT", "水鉄砲", "PH", "SG"),
        ("PH-TOY-WEAPON-CONTEXT", "おもちゃのピストル", "PH", "SG"),
        ("PH-ORAL", "舌クリーナー", "PH", "SG"),
        ("PH-TATTOO", "タトゥーマシン", "PH", "SG"),
        ("PH-PET-DRUG", "犬のダニ駆除", "PH", "SG"),
        ("PH-COSMETIC-MASK", "シートパック", "PH", "SG"),
    ]
    for rule_id, term, intended, other in cases:
        assert any(h.rule_id == rule_id and h.action == "BLOCK" for h in evaluate_policy({"product_title": term}, intended))
        assert not any(h.rule_id == rule_id for h in evaluate_policy({"product_title": term}, other))
