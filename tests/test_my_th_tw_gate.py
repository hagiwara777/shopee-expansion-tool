"""DEC-0189 acceptance examples: synthetic JP facts only, never live product APIs."""
import json
from pathlib import Path

import pytest

from modules.asin_resolver import preview_candidates, verify_preview_rows
from modules.brand_monitoring import country_brand_names, load_brand_monitoring
from modules.guardrails import apply_guardrails
from modules.safety_policy import evaluate_policy, load_policy_rules
from modules.sora_markets import SORA_MARKETS
from modules.sora_run import evaluate_sora_run, prepare_sora_run, sora_exports
from modules.sp_api_catalog import JP_MARKETPLACE, normalize_catalog_item

ROOT = Path(__file__).resolve().parents[1]
ASIN = "B000000001"
FOOD = "食品・飲料・お酒 > 菓子 > キャンディ"


@pytest.fixture(autouse=True)
def no_live_requests(monkeypatch):
    monkeypatch.setattr("requests.Session.request", lambda *a, **kw: pytest.fail("Live API reached"))


def synthetic_run(market, title="ボールペン", category="文房具・オフィス用品", brand="試験ブランド", attributes=None):
    class CapturedClient:
        provider_name = "sp_api_catalog_2022_04_01"
        product_field_prefix = "spapi"
        verification_label = "SP_API_VERIFIED"

        def verify_products_by_asin(self, asins):
            return {asin: normalize_catalog_item({
                "asin": asin, "attributes": attributes or {},
                "summaries": [{"marketplaceId": JP_MARKETPLACE, "itemName": title, "brand": brand,
                               "browseClassification": {"displayName": category}}],
            }, fetched_at="2026-11-13T00:00:00+00:00") for asin in asins}
    verified = verify_preview_rows(preview_candidates(ASIN), CapturedClient())
    return prepare_sora_run(verified, marketplace=market, auth_calls=1, catalog_calls=1)


def attr(name, value):
    return {name: [{"value": value, "marketplace_id": JP_MARKETPLACE}]}


def package(length=30, width=20, height=10, weight=.5, length_unit="centimeters", weight_unit="kilograms"):
    return {
        "item_package_dimensions": [{
            key: {"value": value, "unit": length_unit}
            for key, value in (("length", length), ("width", width), ("height", height))
        }],
        "item_package_weight": [{"value": weight, "unit": weight_unit}],
    }


@pytest.mark.parametrize("market", ["MY", "TH", "TW"])
def test_sora_passes_and_exports_while_governance_stays_inactive(market):
    state = json.loads((ROOT / "governance/state.json").read_text(encoding="utf8"))
    assert state["markets"][market] == {"operation": "INACTIVE", "development_policy": "ALLOWED"}
    assert not any(key.startswith(market.lower() + ".") for key in state["capabilities"])
    assert SORA_MARKETS[market].ng_configured and not SORA_MARKETS[market].country_dictionaries
    run = synthetic_run(market)
    result = evaluate_sora_run(run)
    assert (result.eligible_count, result.review_count, result.exclude_count) == (1, 0, 0)
    output = sora_exports(run, result)
    assert output["通過ASIN.txt"] == (ASIN + "\n").encode()
    record = json.loads(output["実行記録.json"])
    assert record["国"] == market and record["SP-API呼び出し合計"] == 2
    assert record["重複照合"] == "重複照合は未実施"


@pytest.mark.parametrize("ingredient", ["豚肉", "ゼラチン", "みりん", "牛肉エキス", "チキンエキス", "ラード"])
@pytest.mark.parametrize("field", ["ingredients", "product_description", "bullet_point"])
def test_my_halal_food_looks_in_all_content_fields(ingredient, field):
    run = synthetic_run("MY", "フルーツキャンディ", FOOD, attributes=attr(field, ingredient))
    row = evaluate_sora_run(run).rows[0]
    assert row.final_eligibility == "EXCLUDE"
    assert "MY-HALAL-FOOD" in row.guardrail_note


def test_my_green_tea_passes_and_cosmetic_rice_bran_is_not_food():
    run = synthetic_run("MY", "緑茶", "食品・飲料・お酒 > 茶", attributes=attr("ingredients", "緑茶"))
    assert evaluate_sora_run(run).eligible_count == 1
    cosmetic = {"product_title": "米ぬか 化粧水", "category": "ビューティー > スキンケア",
                "ingredients": ["水、米ぬか、アルコール、牛脂"]}
    assert not [h for h in evaluate_policy(cosmetic, "MY") if h.rule_id in {"MY-HALAL-FOOD", "MY-SUGAR-RICE"}]
    assert apply_guardrails([{**cosmetic, "ingredients": ["水、米ぬか"]}], marketplace="MY")[0]["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("title", ["米 5kg", "白米 2kg", "無洗米 2kg", "国産無洗米 2kg", "新潟県産白米 5kg",
                                  "砂糖 1kg", "上白糖"])
def test_my_sugar_and_rice_are_food_items(title):
    hits = evaluate_policy({"product_title": title, "category": FOOD}, "MY")
    assert any(h.rule_id == "MY-SUGAR-RICE" and h.action == "BLOCK" for h in hits)


@pytest.mark.parametrize("title", ["米粉", "米ぬか化粧水", "米国産 緑茶", "玄米茶", "米菓", "玄米せんべい"])
def test_my_rice_boundary_does_not_turn_processed_or_other_meanings_into_rice(title):
    assert not [h for h in evaluate_policy({"product_title": title, "category": FOOD}, "MY")
                if h.rule_id == "MY-SUGAR-RICE"]


@pytest.mark.parametrize("title", ["米菓", "せんべい", "煎餅", "あられ", "おかき"])
def test_my_rice_snack_is_review(title):
    assert evaluate_sora_run(synthetic_run("MY", title, FOOD)).rows[0].final_eligibility == "REVIEW"


@pytest.mark.parametrize("title", ["メガネ拭き", "メガネケース", "眼鏡用クリーナー", "メガネクロス",
                                  "メガネチェーン", "メガネストラップ", "eyeglasses case"])
def test_my_eyewear_accessories_pass_even_with_an_eyewear_category(title):
    assert evaluate_sora_run(synthetic_run("MY", title, "ファッション > メガネ")).eligible_count == 1


@pytest.mark.parametrize("title", ["老眼鏡", "メガネ拭き と 老眼鏡セット"])
def test_my_eyewear_body_is_still_blocked(title):
    assert evaluate_sora_run(synthetic_run("MY", title, "ファッション")).exclude_count == 1


@pytest.mark.parametrize("market,title,category,expected,rule_id", [
    ("MY", "豚毛ブラシ", "ヘアブラシ", "REVIEW", "MY-PORK-OTHER"),
    ("MY", "kitchen knife", "キッチン", "EXCLUDE", "MY-KNIFE"),
    ("MY", "注射器型 ボールペン", "文具", "EXCLUDE", "MY-SYRINGE-SHAPE"),
    ("MY", "Quran", "本", "EXCLUDE", "MY-RELIGIOUS"),
    ("MY", "安全ヘルメット", "工具", "REVIEW", "MY-SAFETY-HELMET"),
    ("MY", "精力増強", "普通の商品", "EXCLUDE", "MY-APHRODISIAC"),
    ("TH", "乳液", "ビューティー > スキンケア", "EXCLUDE", "TH-TW-COSMETICS"),
    ("TH", "ヘアドライヤー AC100V", "普通の商品", "EXCLUDE", "TH-ELECTRIC"),
    ("TH", "車用ホルダー", "車&バイク > アクセサリ", "EXCLUDE", "TH-CAR-PARTS"),
    ("TH", "台所用洗剤", "ホーム&キッチン", "REVIEW", "TH-CHEMICAL"),
    ("TH", "仏像", "置物", "EXCLUDE", "TH-LICENSE-OTHER"),
    ("TW", "乳液", "ビューティー > スキンケア", "EXCLUDE", "TH-TW-COSMETICS"),
    ("TW", "普通の商品", "ドラッグストア > 衛生用品・ヘルスケア", "EXCLUDE", "TW-HEALTHCARE"),
    ("TW", "ベビーカー", "ベビー用品", "EXCLUDE", "TW-BABY"),
    ("TW", "ヘアアイロン", "ヘアケア", "EXCLUDE", "TW-HAIR-IRON"),
    ("TW", "サングラス", "ファッション", "EXCLUDE", "TW-SUNGLASSES"),
    ("TW", "玩具のパチンコ 投石器", "おもちゃ", "EXCLUDE", "TW-BLADE"),
    ("TW", "ハサミ", "文具", "REVIEW", "TW-BLADE-REVIEW"),
    ("TW", "ノミ取り", "ペット用品", "EXCLUDE", "TW-FLEA"),
    ("TW", "光美容器", "美容家電", "EXCLUDE", "TW-BEAUTY-DEVICE"),
    ("TW", "タンポン", "普通の商品", "EXCLUDE", "TW-TAMPON"),
    ("TW", "USBメモリ", "記録媒体", "EXCLUDE", "TW-LICENSE-ELECTRIC"),
    ("TW", "ヘルメット", "普通の商品", "EXCLUDE", "TW-SAFETY-HELMET"),
])
def test_market_specific_examples_reach_final_output(market, title, category, expected, rule_id):
    run = synthetic_run(market, title, category)
    row = evaluate_sora_run(run).rows[0]
    assert row.final_eligibility == expected, row.guardrail_note
    assert rule_id in row.guardrail_note
    outputs = sora_exports(run, evaluate_sora_run(run))
    assert ASIN in outputs["停止.csv" if expected == "EXCLUDE" else "要確認.csv"].decode("utf-8-sig")


@pytest.mark.parametrize("market", ["TH", "TW"])
def test_root_categories_are_exact_and_drugstore_is_only_review(market):
    for root in ("ビューティー", "ラグジュアリービューティー"):
        assert evaluate_sora_run(synthetic_run(market, "普通の商品", root + " > スキンケア")).exclude_count == 1
    assert evaluate_sora_run(synthetic_run(market, "普通の商品", "ドラッグストア > 雑貨")).review_count == 1
    # A later node and a stationery clip do not assert the forbidden root/product.
    assert evaluate_sora_run(synthetic_run(market, "クリップ付きボールペン", "文具 > ビューティー")).eligible_count == 1
    assert evaluate_sora_run(synthetic_run(market, "緑茶", "食品・飲料・お酒 > 茶")).exclude_count == 1


@pytest.mark.parametrize("root", ["家電&カメラ", "パソコン・周辺機器", "大型家電"])
def test_th_electric_root_category_is_blocked(root):
    assert evaluate_sora_run(synthetic_run("TH", "普通の商品", root + " > アクセサリ")).exclude_count == 1


def test_bounded_terms_and_th_toys_do_not_add_blanket_stops():
    assert evaluate_sora_run(synthetic_run("TH", "動物フィギュア", "おもちゃ")).eligible_count == 1
    assert evaluate_sora_run(synthetic_run("MY", "安全ヘルメット 自転車用", "自転車用品")).eligible_count == 1
    assert not [h for h in evaluate_policy({"product_title": "茶葉 10%増量", "category": FOOD}, "MY")
                if h.rule_id == "MY-WEIGHT-GAIN"]
    assert any(h.rule_id == "MY-WEIGHT-GAIN" for h in evaluate_policy({"product_title": "体重増加用 ビタミン 増量"}, "MY"))
    assert not [h for h in evaluate_policy({"product_title": "左官用コテ"}, "TW") if h.rule_id == "TW-HAIR-IRON"]
    assert any(h.rule_id == "TW-HAIR-IRON" for h in evaluate_policy({"product_title": "コテ ヘア用"}, "TW"))


@pytest.mark.parametrize("market", ["MY", "TH", "TW"])
@pytest.mark.parametrize("attributes,expected", [
    (attr("bullet_point", "医薬部外品"), "EXCLUDE"),
    ({"batteries_included": [{"value": True}]}, "EXCLUDE"),
    (attr("product_description", "エアゾール"), "REVIEW"),
])
def test_common_stops_prevent_pass_in_each_market(market, attributes, expected):
    assert evaluate_sora_run(synthetic_run(market, attributes=attributes)).rows[0].final_eligibility == expected


@pytest.mark.parametrize("market,title,rule_id", [
    (m, title, rule) for m in ("MY", "TH", "TW") for title, rule in (
        ("magnetic putty", "SG-MAGNETIC-PUTTY"), ("磁性粘土", "SG-MAGNETIC-CLAY"), ("無線機", "SG-RADIO"))
] + [(m, title, rule) for m in ("MY", "TW") for title, rule in (
    ("錠前破り", "SG-LOCK-PICKING"), ("ピッキングツール", "SG-PICKING-TOOL"),
    ("水鉄砲", "PH-TOY-WEAPON-DIRECT"), ("おもちゃのピストル", "PH-TOY-WEAPON-CONTEXT"),
    ("hidden camera", "MY-TW-SPY-CAMERA"))])
def test_only_specified_shared_rules_expand(market, title, rule_id):
    hits = evaluate_policy({"product_title": title}, market)
    assert any(h.rule_id == rule_id and h.action == "BLOCK" for h in hits)


def test_sg_only_terms_do_not_leak_and_th_precious_review_expands():
    for market in ("MY", "TH", "TW"):
        ids = {h.rule_id for h in evaluate_policy({"product_title": "護身用バトン プリペイドSIM"}, market)}
        assert "SG-SPECIFIC" not in ids
        assert not [h for h in evaluate_policy({"product_title": "錠前破り ピッキングツール"}, "TH")
                    if h.rule_id in {"SG-LOCK-PICKING", "SG-PICKING-TOOL"}]
    assert any(h.rule_id == "PH-PRECIOUS-REVIEW" and h.action == "REVIEW"
               for h in evaluate_policy({"product_title": "純銀"}, "TH"))


@pytest.mark.parametrize("market,brand", [("MY", "Hada Labo"), ("TW", "SHISEIDO"), ("TW", "資生堂")])
def test_country_counterfeit_brand_stops_reach_gate(market, brand):
    row = evaluate_sora_run(synthetic_run(market, brand=brand)).rows[0]
    assert row.final_eligibility == "EXCLUDE"
    assert f"公式監視ブランド（{market}）" in row.guardrail_note


def test_taiwan_bilingual_names_are_complete_names_and_children_are_not_inferred():
    assert country_brand_names("LOUIS VUITTON 路易威登", "TW") == ("LOUIS VUITTON", "路易威登")
    assert country_brand_names("Kose Cosmeport", "MY") == ("Kose Cosmeport",)
    tw = load_brand_monitoring("TW")
    assert tw.matches("ＳＨＩＳＥＩＤＯ") and tw.matches("資 生 堂") and tw.matches("SHISEIDO 資生堂")
    assert not tw.matches("資生堂風") and not tw.matches("エリクシール(資生堂)")
    my = load_brand_monitoring("MY")
    assert my.matches("Kose Cosmeport") and not my.matches("ソフティモ")
    assert evaluate_sora_run(synthetic_run("MY", brand="ソフティモ")).eligible_count == 1


@pytest.mark.parametrize("attributes,expected", [(package(), "REVIEW"), (package(10, 10, 5), "ELIGIBLE"),
                                                 (package(10, 10, 30), "ELIGIBLE"), ({}, "ELIGIBLE")])
def test_my_dimensional_weight_and_missing_sizes(attributes, expected):
    run = synthetic_run("MY", attributes=attributes)
    row = evaluate_sora_run(run).rows[0]
    assert row.final_eligibility == expected
    if expected == "REVIEW":
        assert "容積重量 1.0kg" in row.guardrail_note and "実重量 0.5kg" in row.guardrail_note
        assert "MY-VOLUMETRIC" in sora_exports(run, evaluate_sora_run(run))["要確認.csv"].decode("utf-8-sig")
    if not attributes:
        assert "サイズ情報なし" in row.guardrail_note
    assert (run.auth_calls, run.catalog_calls) == (1, 1)


@pytest.mark.parametrize("unit,values,weight_unit,weight", [
    ("millimeters", (300, 200, 100), "grams", 500),
    ("meters", (.3, .2, .1), "kilograms", .5),
    ("inches", (30/2.54, 20/2.54, 10/2.54), "pounds", .5/.45359237),
])
def test_volume_converts_units_and_falls_back_to_item_measurements(unit, values, weight_unit, weight):
    attributes = package(*values, weight, unit, weight_unit)
    attributes["item_dimensions"] = attributes.pop("item_package_dimensions")
    attributes["item_weight"] = attributes.pop("item_package_weight")
    row = evaluate_sora_run(synthetic_run("MY", attributes=attributes)).rows[0]
    assert row.final_eligibility == "REVIEW"
    assert "容積重量 1.0kg" in row.guardrail_note and "実重量 0.5kg" in row.guardrail_note
    assert "item_dimensions / item_weight" in row.guardrail_note


def test_package_measurements_take_precedence_and_cannot_clear_an_independent_block():
    attributes = package()
    small = package(1, 1, 1, 100)
    attributes["item_dimensions"] = small["item_package_dimensions"]
    attributes["item_weight"] = small["item_package_weight"]
    assert evaluate_sora_run(synthetic_run("MY", attributes=attributes)).review_count == 1
    attributes.update(attr("bullet_point", "医薬部外品"))
    assert evaluate_sora_run(synthetic_run("MY", attributes=attributes)).exclude_count == 1
    for market in ("TH", "TW", "PH", "SG"):
        row = evaluate_sora_run(synthetic_run(market, attributes=package())).rows[0]
        assert row.final_eligibility == "ELIGIBLE" and "MY-VOLUMETRIC" not in row.guardrail_note


def test_measurement_fallback_is_independent_and_conflicting_package_values_are_missing():
    attributes = package()
    attributes["item_weight"] = attributes.pop("item_package_weight")
    run = synthetic_run("MY", attributes=attributes)
    row = evaluate_sora_run(run).rows[0]
    assert row.final_eligibility == "REVIEW"
    assert "item_package_dimensions / item_weight" in row.guardrail_note
    attributes["item_package_dimensions"].append(package(10, 10, 5)["item_package_dimensions"][0])
    row = evaluate_sora_run(synthetic_run("MY", attributes=attributes)).rows[0]
    assert row.final_eligibility == "ELIGIBLE" and "サイズ情報なし" in row.guardrail_note


@pytest.mark.parametrize("bad", [
    {"item_package_weight": [{"value": .5, "unit": "kilograms"}]},
    {"item_package_dimensions": package()["item_package_dimensions"]},
    package(weight=-1), package(length=0), package(length_unit="unknown"), package(weight=True),
])
def test_incomplete_or_invalid_measurements_pass_with_note(bad):
    row = evaluate_sora_run(synthetic_run("MY", attributes=bad)).rows[0]
    assert row.final_eligibility == "ELIGIBLE" and "サイズ情報なし" in row.guardrail_note


def test_foreign_market_measurements_are_not_used():
    data = package()
    data["item_package_dimensions"][0]["marketplace_id"] = "ATVPDKIKX0DER"
    row = evaluate_sora_run(synthetic_run("MY", attributes=data)).rows[0]
    assert row.final_eligibility == "ELIGIBLE" and "サイズ情報なし" in row.guardrail_note


def test_all_rules_keep_required_scope_and_item_is_never_text_or_ingredients():
    rules = load_policy_rules()
    assert all(r["scope"] in {"item", "content"} for r in rules)
    assert all(not {"text", "ingredients"} & set(r["fields"]) for r in rules if r["scope"] == "item")


def test_new_item_rules_ignore_description_and_ingredient_mentions():
    for market in ("MY", "TH", "TW"):
        hits = evaluate_policy({
            "product_title": "ボールペン", "category": "文房具・オフィス用品",
            "description": ["サングラス ヘアアイロン 化粧水 メガネ 注射器型"],
            "ingredients": ["サングラス ヘアアイロン 化粧水 メガネ 注射器型"],
        }, market)
        assert not [h for h in hits if h.rule_id.startswith(("MY-", "TH-", "TW-"))]
