"""DEC-0187: Shopee sales-restriction guide items (SG p4 / PH p9) whose representative names passed."""
import pytest

from modules.guardrails import apply_guardrails


def status(market, title, category=""):
    return apply_guardrails([{"product_title": title, "category": category}], marketplace=market)[0]["guardrail_status"]


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize(("title", "expected"), [
    ("警察手帳 レプリカ ポリス バッジ", "BLOCK"),
    ("警察 バッジ レプリカ", "BLOCK"),
    ("運転免許証 レプリカ 身分証", "BLOCK"),
    ("パチスロ実機 家庭用", "BLOCK"),
    ("トヨタ 中古車 自動車本体", "BLOCK"),
    ("肩こり改善 血行促進 磁気ネックレス", "BLOCK"),
    ("スーパーコピー 腕時計", "BLOCK"),
    ("自衛隊 迷彩服 制服", "REVIEW"),
    ("軍用 暗視スコープ ナイトビジョン", "REVIEW"),
])
def test_guide_items_stop_or_need_confirmation(market, title, expected):
    assert status(market, title) == expected


def test_ph_only_guide_items():
    assert status("PH", "ICC ステッカー 認証シール") == "BLOCK"
    assert status("PH", "【中古】 ブラジャー") == "BLOCK"
    assert status("PH", "テロリスト フィギュア") == "BLOCK"
    assert status("SG", "テロリスト フィギュア") == "SAFE"
    assert status("PH", "ワイヤレス ブラジャー 新品") == "SAFE"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("title", [
    "運転免許証ケース 本革",
    "運転免許証 入れ カードケース",
    "迷彩柄 Tシャツ メンズ",
    "スロット 収納ボックス",
    "ネックレス チェーン シルバー",
    "コピー用紙 A4 500枚",
])
def test_overstop_controls_remain_safe(market, title):
    assert status(market, title) == "SAFE"
