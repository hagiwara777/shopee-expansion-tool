"""Offline regressions for the TH spot-check findings in DEC-0192."""

import pytest

from modules.guardrails import apply_guardrails
from modules.safety_policy import evaluate_policy


MARKETS = ("SG", "PH", "MY", "TH", "TW")
SOFT_BULLET_TITLE = (
    "友愛玩具(Yuuai Gangu) ソフトバレット タクティカルスター "
    "電池不要 全長約81㎝ TY-1163"
)


def guarded(title, market="SG", **facts):
    return apply_guardrails([{"product_title": title, **facts}], marketplace=market)[0]


def test_owner_microtorch_is_blocked_in_thailand():
    title = (
        "新富士バーナー(Shinfuji Burner) マイクロトーチ アクティブ ブラック RZ-522BK"
        "【小型強力耐風バーナー 】【線香/ロープ切断/ハンダ付など】【ガス充てん式】"
    )
    row = guarded(title, "TH", category="産業・研究開発用品")
    assert row["guardrail_status"] == "BLOCK"
    assert "COMMON-GAS-TORCH" in row["guardrail_note"]


@pytest.mark.parametrize("market", MARKETS)
def test_gas_burner_is_blocked_in_every_market(market):
    row = guarded("ガスバーナー 本体 キャンプ", market)
    assert row["guardrail_status"] == "BLOCK"
    assert "ガスバーナー" in row["guardrail_matched_terms"].split("|")


@pytest.mark.parametrize("title", ["トーチライト LED", "新富士バーナー", "バーナー", "トーチ"])
def test_torch_and_burner_words_alone_do_not_block(title):
    assert guarded(title)["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("field", ["category", "description"])
def test_gas_torch_rule_reads_only_the_title(field):
    hits = evaluate_policy({"product_title": "普通の商品", field: "ガスバーナー"}, "SG")
    assert not [hit for hit in hits if hit.rule_id == "COMMON-GAS-TORCH"]


@pytest.mark.parametrize("market", MARKETS)
def test_owner_soft_bullet_toy_is_a_weapon_without_battery_match(market):
    row = guarded(SOFT_BULLET_TITLE, market, category="おもちゃ")
    assert row["guardrail_status"] == "BLOCK"
    assert "ソフトバレット" in row["guardrail_matched_terms"].split("|")
    assert "電池" not in row["guardrail_matched_terms"].split("|")
    assert "COMMON-WEAPON-STRICT" in row["guardrail_note"]


@pytest.mark.parametrize("phrase", [
    "電池不要", "電池は不要", "電池なし", "電池はなし",
    "電池無し", "電池は無し", "電池不使用", "電池は不使用",
])
def test_explicit_no_battery_statements_do_not_match_shared_battery_word(phrase):
    row = guarded(f"LEDライト {phrase} ソーラー")
    assert row["guardrail_status"] == "SAFE"
    assert "電池" not in row["guardrail_matched_terms"].split("|")


def test_no_battery_statement_in_highlights_does_not_match_shared_battery_word():
    assert guarded("LEDライト ソーラー", itemHighlights=["電池不要"])["guardrail_status"] == "SAFE"


def test_owner_aa_battery_light_stays_blocked():
    row = guarded("LEDライト 単3電池 2本使用")
    assert row["guardrail_status"] == "BLOCK"
    assert "電池" in row["guardrail_matched_terms"].split("|")


def test_no_battery_statement_does_not_mask_a_separate_battery_fact():
    row = guarded("普通の商品", features=["電池不要", "単3電池 2本使用"])
    assert row["guardrail_status"] == "REVIEW"
    assert "電池" in row["guardrail_matched_terms"].split("|")


@pytest.mark.parametrize("market", ["TH", "TW"])
@pytest.mark.parametrize("title,expected", [
    ("グリップ", "SAFE"), ("ゼムクリップ", "SAFE"),
    ("リップクリーム", "BLOCK"), ("薬用リップ", "BLOCK"),
])
def test_lip_pattern_distinguishes_katakana_compounds(market, title, expected):
    row = guarded(title, market)
    assert row["guardrail_status"] == expected
    hits = [hit for hit in evaluate_policy({"product_title": title}, market)
            if hit.rule_id == "TH-TW-COSMETICS" and hit.term == "リップ"]
    assert bool(hits) == (expected == "BLOCK")


def test_owner_grip_scissors_are_safe_in_thailand():
    title = "プラス はさみ フィットカットカーブ フッ素コート 低反発グリップ SC-175SF"
    assert guarded(title, "TH", category="文房具・オフィス用品")["guardrail_status"] == "SAFE"
