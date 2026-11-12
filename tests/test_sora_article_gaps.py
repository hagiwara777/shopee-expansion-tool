"""DEC-0182: SG/PH gaps found by comparing Shopee's own prohibited-item articles with the gate.

Synthetic representative product names only; not complete product records, a full audit of
the official lists, or live acceptance.
"""
import pytest

from modules.guardrails import apply_guardrails
from modules.safety_policy import evaluate_policy


def status(market, title="普通の商品", **facts):
    return apply_guardrails([{"product_title": title, **facts}], marketplace=market)[0]["guardrail_status"]


def rule_ids(market, title="普通の商品", **facts):
    return {hit.rule_id for hit in evaluate_policy({"product_title": title, **facts}, market)}


BOTH = ["PH", "SG"]


@pytest.mark.parametrize("market", BOTH)
@pytest.mark.parametrize("title", [
    "アース ブラックキャップ ゴキブリ 駆除剤 12個",
    "アース渦巻香 蚊取り線香 30巻",
    "金鳥 蚊取線香 大型 50巻",
    "バルサン 燻煙剤 6-8畳用",
    "殺鼠剤 ネズミ 駆除",
    "ロート 目薬 ビタミン配合 12ml",
    "点眼液 コンタクト対応 15ml",
    "ケアリーヴ 絆創膏 救急ばんそうこう 80枚",
    "ハクゾウ 滅菌ガーゼ 医療用 10枚入",
    "アルミ 松葉杖 身長調節 軽量",
    "JTB旅行券 ナイスギフト 1万円分",
    "Amazonギフトカード Eメールタイプ 5000円",
    "QUOカード 1000円分",
    "図書カード NEXT 500円",
])
def test_requested_items_stop_in_both_markets(market, title):
    assert status(market, title) == "BLOCK"


@pytest.mark.parametrize("market", BOTH)
@pytest.mark.parametrize("title", [
    "イワタニ カセットガス 3本パック",
    "ヘアムース ふわふわ 泡 整髪料 185g",
    "アサヒペン アクリルスプレー 黒 300ml",
    "ラッカースプレー つや消し 420ml",
    "エアダスター 無水 PC掃除",
    "キャンプ ガス缶 OD缶 500g",
    "納豆 国産大豆 冷蔵 40g×3",
    "キムチ 白菜 400g チルド",
])
def test_can_gas_and_chilled_items_need_confirmation_in_both_markets(market, title):
    assert status(market, title) == "REVIEW"


def test_sg_only_items_stop_or_need_confirmation():
    assert status("SG", "いなば ちゅ〜る 猫用おやつ まぐろ 14g×50", category="ペット用品 > キャット > おやつ") == "BLOCK"
    assert status("SG", "ささみ 無添加", category="ペット用品 > 猫 > おやつ") == "BLOCK"
    assert status("SG", "成犬用 ドライ", category="ペット用品 > 犬 > フード・おやつ > ドッグフード") == "BLOCK"
    assert status("SG", "使い捨て 防護服 医療用 ガウン") == "BLOCK"
    assert status("SG", "医療用手袋 パウダーフリー 100枚") == "BLOCK"
    assert status("SG", "ニトリル手袋 100枚 使い捨て パウダーフリー") == "REVIEW"
    assert status("SG", "ビーフカレー レトルト 中辛 5食") == "REVIEW"
    assert status("SG", "冷凍 餃子 焼き 30個") in {"REVIEW", "BLOCK"}
    # The existing explicit SG meat BLOCK is not weakened by the new confirmation rule.
    assert status("SG", "ビーフジャーキー 60g") == "BLOCK"


def test_ph_outdoor_knife_blocks_and_does_not_apply_to_sg_rule_id():
    assert status("PH", "アウトドアナイフ フォールディング 折りたたみ") == "BLOCK"
    assert status("PH", "Survival knife with sheath") == "BLOCK"
    assert "PH-OUTDOOR-KNIFE" in rule_ids("PH", "サバイバルナイフ")
    # SG keeps stopping every knife through its own rule.
    assert status("SG", "サバイバルナイフ") == "BLOCK"
    assert "PH-OUTDOOR-KNIFE" not in rule_ids("SG", "サバイバルナイフ")


def test_sg_and_ph_specific_rules_stay_in_their_market():
    cases = [
        ("SG-PETFOOD-CATEGORY", {"product_title": "犬 おやつ", "category": "ペット用品 > 犬 > おやつ"}, "SG", "PH"),
        ("SG-MEDICAL-PROTECTIVE", {"product_title": "防護服"}, "SG", "PH"),
        ("SG-DISPOSABLE-GLOVE", {"product_title": "ニトリル手袋"}, "SG", "PH"),
        ("SG-MEAT-PROCESSED", {"product_title": "ビーフカレー"}, "SG", "PH"),
        ("PH-OUTDOOR-KNIFE", {"product_title": "サバイバルナイフ"}, "PH", "SG"),
    ]
    for rule_id, row, intended, other in cases:
        assert any(h.rule_id == rule_id for h in evaluate_policy(row, intended))
        assert not any(h.rule_id == rule_id for h in evaluate_policy(row, other))


@pytest.mark.parametrize("market", BOTH)
@pytest.mark.parametrize("title", [
    "目薬ケース 携帯用",
    "絆創膏ケース 携帯 ポーチ",
    "蚊取り線香ホルダー 陶器",
    "蚊取り線香 用 スタンド 皿",
    "チルドレンズ ブック 絵本",
    "ボンベイ サファイア 風 トレイ",
    "ギフトボックス ラッピング",
    "ギフトカード 封筒 メッセージ",
    "ヨーグルトメーカー 家庭用",
    "キュキュット 食器用洗剤 本体 240ml",
    "ムシューダ 防虫剤 引き出し用 24個",  # Owner decision 2026-11-12: clothing moth repellent keeps passing.
    "食器用 ゴム手袋 キッチン",
    "バターナイフ ステンレス",
    "ナイフ 研ぎ器 シャープナー",
])
def test_overstop_controls_remain_safe(market, title):
    assert status(market, title) == "SAFE"


@pytest.mark.parametrize("market", BOTH)
def test_pet_supplies_other_than_food_and_ph_pet_food_scope(market):
    # The top-level pet node alone is not a food.
    assert status(market, "犬用 リード 散歩", category="ペット用品 > 犬 > リード・首輪") == "SAFE"
    assert status(market, "猫 ねこじゃらし", category="ペット用品 > 猫 > おもちゃ") == "SAFE"
    if market == "PH":
        # DEC-0182 limits the new pet-food category stop to SG; PH keeps its existing COMMON-PETFOOD terms.
        assert status("PH", "猫 ささみ 無添加", category="ペット用品 > 猫 > おやつ") == "SAFE"


def test_sharpener_for_ph_outdoor_knife_does_not_hide_a_knife():
    assert status("PH", "サバイバルナイフ 研ぎ器 砥石") == "SAFE"
    assert status("PH", "サバイバルナイフ と ナイフ 研ぎ器 セット") == "BLOCK"


def test_ph_does_not_gain_the_sg_meat_confirmation():
    assert status("PH", "ビーフカレー レトルト 中辛 5食") == "SAFE"
    assert status("PH", "チキンラーメン 5食 袋麺") == "SAFE"


@pytest.mark.parametrize("market", BOTH)
def test_negated_medical_items_are_not_stopped_by_a_bare_mention(market):
    assert status(market, "絆創膏ではありません 柄 ステッカー") == "SAFE"
