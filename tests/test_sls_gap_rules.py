"""DEC-0186: product groups in SLS 'NO' (not shippable) Shopee categories that word rules missed.

Synthetic representative titles; category numbers are never inferred from Amazon data.
"""
import pytest

from modules.guardrails import apply_guardrails


def status(market, title, category=""):
    return apply_guardrails([{"product_title": title, "category": category}], marketplace=market)[0]["guardrail_status"]


BOTH = ["SG", "PH"]


@pytest.mark.parametrize("market", BOTH)
@pytest.mark.parametrize("title", [
    "アロマオイル 精油 6本セット",
    "ミニトマト 種 固定種 20粒",
    "チューリップ 球根 10球",
    "グリススプレー シリコングリス 100g",
    "メイクキープミスト 80ml",
    "大人のおもちゃ セット",
    "カメラ用 互換バッテリー NP-FW50",
    "バイク用バッテリー 12V YTX7L-BS",
    "ノートパソコン用 交換バッテリー",
    "腕時計用 時計用電池 SR626SW",
])
def test_sls_not_shippable_groups_stop_in_both_markets(market, title):
    assert status(market, title) == "BLOCK"


@pytest.mark.parametrize("market", BOTH)
@pytest.mark.parametrize("title", ["キッコーマン 豆乳 無調整 1000ml", "アーモンドミルク 砂糖不使用 1L"])
def test_non_dairy_milk_stops_as_food_and_needs_confirmation_without_food_context(market, title):
    assert status(market, title, "食品・飲料 > 飲料") == "BLOCK"
    # Without a food category the existing food rule asks for confirmation instead of passing.
    assert status(market, title) == "REVIEW"


@pytest.mark.parametrize("market", BOTH)
@pytest.mark.parametrize("title", ["カーワックス 固形 300g", "ガラコ 撥水剤 フロントガラス", "タイヤチェーン 非金属"])
def test_sls_check_with_shopee_car_care_needs_confirmation(market, title):
    assert status(market, title) == "REVIEW"


def test_market_specific_sls_groups():
    assert status("SG", "水鉄砲 大容量") == "BLOCK"
    assert status("SG", "鼻うがい 洗浄器 ハナクリーン") == "BLOCK"
    assert status("SG", "バッテリー充電器 車用 12V") == "BLOCK"
    assert status("PH", "潤滑ゼリー ローション 100ml") == "BLOCK"
    assert status("PH", "純銀 インゴット 100g") == "BLOCK"
    assert status("PH", "マフラーカッター オーバル ステンレス") == "BLOCK"
    assert status("PH", "純銀 ネックレス") == "REVIEW"
    # Market-specific additions stay in their market.
    assert status("PH", "鼻うがい 洗浄器 ハナクリーン") == "SAFE"
    assert status("SG", "マフラーカッター オーバル ステンレス") == "SAFE"
    assert status("SG", "純銀 ネックレス") == "SAFE"


@pytest.mark.parametrize("market", BOTH)
@pytest.mark.parametrize(("title", "category"), [
    ("豆乳イソフラボン 化粧水 しっとり 200ml", "ビューティー > スキンケア > 化粧水"),
    ("なめらか本舗 豆乳ローション", "ビューティー > スキンケア"),
    ("ラベンダー精油配合 ハンドクリーム", "ビューティー > ハンドケア"),
    ("天然精油の香り ボディソープ", "ビューティー > ボディケア"),
    ("CPUグリス 熱伝導 4g", "パソコン > パーツ"),
    ("洗車ブラシ 柄付き", "カー&バイク用品 > 洗車用品"),
    ("ピストン式 ボールペン", "文房具"),
    ("ミニカー タイヤ付き", "おもちゃ"),
    ("ブラスターズ フィギュア", "おもちゃ"),
    ("グリーンベル 爪切り", "ビューティー > ネイルケア"),
    ("撥水 傘 折りたたみ", "ファッション > 傘"),
    ("伊藤園 お～いお茶 ティーバッグ", "食品 > 飲料"),
])
def test_overstop_controls_remain_safe(market, title, category):
    assert status(market, title, category) == "SAFE"
