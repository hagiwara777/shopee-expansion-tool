"""DEC-0191: Owner-supplied names, offline facts, and bounded overstop controls."""
from dataclasses import replace

import pytest

from modules.guardrails import _find_home_appliance_matches, apply_guardrails
from modules.safety_policy import evaluate_policy
from modules.sora_run import evaluate_sora_run
from modules.sora_volumetric import PackageMeasurements, apply_my_volumetric
from tests.test_my_th_tw_gate import package, synthetic_run


FOOD = "食品・飲料・お酒 > カテゴリー別 > コーヒー・紅茶・お茶・粉末ドリンク > コーヒー > インスタントコーヒー"
TOY = "おもちゃ > カテゴリー別 > ままごと・ごっこ遊び > ままごと用キッチン・食べ物 > セット"
NOTE_A = "; 商品名の語が使い方・複合名のため要確認（その物そのものかを確認）"
NOTE_B = "; 説明文だけの記載のため要確認（商品名・カテゴリには無し）"
NOTE_C = "; 食品の成分表記のため要確認（化粧品成分ルール）"
MISSING = "MY-VOLUMETRIC: サイズ情報なし（FROMAXが実重量だけで送料を計算するため要確認）"
MARKETS = ("MY", "SG", "PH", "TH", "TW")


@pytest.fixture(autouse=True)
def no_live_requests(monkeypatch):
    monkeypatch.setattr("requests.Session.request", lambda *a, **kw: pytest.fail("Live API reached"))


def guarded(facts, market="MY"):
    return apply_guardrails([facts], marketplace=market)[0]


@pytest.mark.parametrize("facts,note", [
    ({"product_title": "AGF ブレンディ スティック 冷たい牛乳でつくるクリーミーカフェオレ 7本 【 スティックコーヒー 】", "category": FOOD}, NOTE_A),
    ({"product_title": "AGF ブレンディ スティック まろやか豆乳カフェオレ 6本 【スティックコーヒー】【 ソイ 】【 豆乳 】", "category": FOOD}, NOTE_A),
    ({"product_title": "AGF ブレンディ スティック ミルクティー", "features": ["香り高い紅茶と濃厚なミルク感がマッチした、やさしい甘さのロイヤルミルクティー"]}, NOTE_B),
    ({"product_title": "inゼリー マルチビタミン 180g ×36個", "category": "食品・飲料・お酒 > カテゴリー別 > ドリンク > ゼリー飲料", "features": ["配合栄養素: ビタミンA、ビタミンB1、ビタミンB2"]}, NOTE_C),
])
def test_owner_food_and_drink_examples_review_with_japanese_reason(facts, note):
    row = guarded(facts)
    assert row["guardrail_status"] == "REVIEW"
    assert note in row["guardrail_note"]


def test_owner_detergent_is_not_an_appliance_body():
    facts = {"product_title": "食器洗い乾燥機専用 キュキュットクリア除菌 スティックタイプ 大容量100本入り",
             "category": "ドラッグストア > カテゴリー別 > 日用品 > 食器洗い機用洗剤"}
    assert not _find_home_appliance_matches(facts)
    assert "home_appliance_policy" not in guarded(facts)["guardrail_risk_category"]


def test_owner_pretend_ramen_is_not_halal_food():
    facts = {"product_title": "パイロット メルちゃん おせわパーツ おしょくじラーメン 3歳以上", "category": TOY,
             "features": ["セット内容:ラーメン(めん、チャーシュー、たまご、キャベツ)、スプーン、フォーク"]}
    assert not [h for h in evaluate_policy(facts, "MY") if h.rule_id == "MY-HALAL-FOOD"]
    assert guarded(facts)["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("title", ["牛乳で作る", "牛乳で割る", "牛乳に溶かす", "牛乳と混ぜる", "豆乳カフェオレ", "卵スープ"])
def test_food_name_usage_and_compound_occurrences_review(title):
    assert guarded({"product_title": title, "category": FOOD})["guardrail_status"] == "REVIEW"


@pytest.mark.parametrize("title,expected", [
    ("豆乳カフェオレ【豆乳】", "REVIEW"), ("[豆乳]豆乳カフェオレ", "REVIEW"),
    ("カフェオレ【豆乳】", "BLOCK"), ("豆乳カフェオレ 牛乳 1000ml", "BLOCK"),
    ("牛乳で作るカフェオレ 牛乳 1000ml", "BLOCK"), ("豆乳 カフェオレ", "BLOCK"),
])
def test_search_tags_and_independent_food_bodies(title, expected):
    assert guarded({"product_title": title, "category": FOOD})["guardrail_status"] == expected


@pytest.mark.parametrize("facts", [
    {"product_title": "明治 おいしい牛乳 1000ml", "category": FOOD},
    {"product_title": "キッコーマン 調製豆乳 200ml×18本", "category": FOOD},
    {"product_title": "卵 10個 Mサイズ", "category": FOOD},
    {"product_title": "一蘭 とんこつラーメン 5食", "category": FOOD},
    {"product_title": "ラーメン", "category": FOOD, "features": ["チャーシュー、ポークエキス"]},
    {"product_title": "ジッポー ライター"},
    {"product_title": "美容クリーム", "category": "ビューティー", "description": "レチノール配合"},
    {"product_title": "食洗機 本体", "category": "家電"},
    {"product_title": "食玩 ポークカレー お菓子付き", "category": "おもちゃ > 食玩"},
])
def test_independent_bodies_and_food_content_still_block(facts):
    assert guarded(facts)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("kind", ["食玩", "知育菓子", "菓子", "ガム", "キャンディ", "ラムネ"])
def test_edible_toys_keep_food_rules(kind):
    assert any(h.rule_id == "MY-HALAL-FOOD" and h.action == "BLOCK" for h in evaluate_policy(
        {"product_title": kind + " ポークカレー", "category": "おもちゃ"}, "MY"))


@pytest.mark.parametrize("field", ["description", "features", "shortDescription", "safetyWarning", "itemHighlights"])
def test_fuel_text_review_preserves_identity_and_other_blocks(field):
    facts = {"product_title": "普通の商品", field: "マッチした"}
    assert guarded(facts)["guardrail_status"] == "REVIEW"
    assert NOTE_B in guarded(facts)["guardrail_note"]
    for identity in ({"product_title": "ライター"}, {"category": "着火剤"}):
        assert guarded({**facts, **identity})["guardrail_status"] == "BLOCK"
        assert NOTE_B not in guarded({**facts, **identity})["guardrail_note"]
    assert guarded({**facts, "product_title": "スタンガン"})["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", MARKETS)
def test_fuel_identity_in_category_alone_stays_block(market):
    facts = {"product_title": "普通の商品", "category": "アウトドア > ライター"}
    assert any(h.rule_id == "COMMON-FIRE-FUEL" and h.action == "BLOCK" and h.field == "category"
               for h in evaluate_policy(facts, market))


@pytest.mark.parametrize("market", MARKETS)
def test_food_ingredient_review_is_bounded_by_root_and_field(market):
    facts = {"product_title": "普通の食品", "category": FOOD, "description": "レチノール配合"}
    hits = [h for h in evaluate_policy(facts, market) if h.rule_id == "COMMON-COSMETIC-INGREDIENT"]
    assert hits and all(h.action == "REVIEW" for h in hits)
    for other in ({"category": "ビューティー > 食品"}, {"product_title": "レチノール"}):
        assert any(h.action == "BLOCK" for h in evaluate_policy({**facts, **other}, market)
                   if h.rule_id == "COMMON-COSMETIC-INGREDIENT")


@pytest.mark.parametrize("suffix", ["専用", "用", "対応"])
def test_detergent_destination_occurrences_do_not_hide_another_body(suffix):
    facts = {"product_title": "食洗機" + suffix + " 試験商品", "category": "日用品 > クリーナー"}
    assert not _find_home_appliance_matches(facts)
    assert _find_home_appliance_matches({**facts, "product_title": facts["product_title"] + " 食洗機本体付き"})[0].rule.action == "BLOCK"
    for body in ("本体", " の本体"):
        assert _find_home_appliance_matches({**facts, "product_title": "食洗機" + suffix + body + " 洗剤付き"})[0].rule.action == "BLOCK"


@pytest.mark.parametrize("weight,volume", [(.03, .041), (1.93, 5.10)])
def test_my_excess_volume_changes_only_the_note(weight, volume):
    base = evaluate_sora_run(synthetic_run("MY", attributes=package(10, 10, 5)))
    assert base.rows[0].final_eligibility == "ELIGIBLE"
    fact = PackageMeasurements(base.rows[0].candidate.candidate_asin, (volume * 6000, 1, 1), weight, "package", "package")
    result = apply_my_volumetric(base, (fact,))
    assert result.eligible_count == 1 and result.rows[0].final_eligibility == "ELIGIBLE"
    assert replace(result.rows[0], guardrail_note=base.rows[0].guardrail_note) == base.rows[0]
    assert f"容積重量 {volume}kg ＞ 実重量 {weight}kg" in result.rows[0].guardrail_note


@pytest.mark.parametrize("dimensions,weight", [(None, 1), ((10, 10, 10), None), ((1e308, 1e308, 1e308), 1)])
def test_my_missing_or_uncalculable_sizes_review(dimensions, weight):
    run = synthetic_run("MY", attributes=package(10, 10, 5))
    result = evaluate_sora_run(run)
    assert result.rows[0].final_eligibility == "ELIGIBLE"
    fact = PackageMeasurements(result.rows[0].candidate.candidate_asin, dimensions, weight, "package", "package")
    row = apply_my_volumetric(result, (fact,)).rows[0]
    assert row.final_eligibility == "REVIEW" and row.guardrail_status == "REVIEW"
    assert "MY-VOLUMETRIC" in row.guardrail_matched_terms.split("|")
    assert "GUARDRAIL_REVIEW" in row.reason_codes and MISSING in row.guardrail_note


def test_missing_measurements_cannot_clear_a_block_or_exclusion():
    blocked = evaluate_sora_run(synthetic_run("MY", title="スタンガン"))
    row = apply_my_volumetric(blocked, ()).rows[0]
    assert row.guardrail_status == "BLOCK" and row.final_eligibility == "EXCLUDE"
    assert MISSING in row.guardrail_note
    base = evaluate_sora_run(synthetic_run("MY", attributes=package(10, 10, 5)))
    excluded = replace(base.rows[0], final_eligibility="EXCLUDE", reason_codes=("EXISTING_LISTING",))
    row = apply_my_volumetric(replace(base, rows=(excluded,)), ()).rows[0]
    assert row.final_eligibility == "EXCLUDE" and "EXISTING_LISTING" in row.reason_codes
    assert row.guardrail_status == "REVIEW" and "GUARDRAIL_REVIEW" in row.reason_codes
