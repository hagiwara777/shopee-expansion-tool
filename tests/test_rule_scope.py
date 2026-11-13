"""DEC-0188: synthetic item/content boundaries; no SP-API or captured payloads."""
import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest

from modules.guardrails import apply_guardrails
from modules.safety_policy import (
    INGREDIENT_FIELDS, TEXT_FIELDS, SafetyPolicyError, evaluate_policy, load_policy_rules,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("facts", [
    {"product_title": "ラーメン", "features": ["アレルギー物質 小麦、卵、乳成分"]},
    {"product_title": "ハウス北海道シチュー", "ingredients": ["食用油脂"]},
    {"product_title": "乳液", "features": ["マスクにつきにくい"]},
    {"product_title": "日焼け止め", "description": "漂白剤不使用"},
    {"product_title": "ヘアスティック", "features": ["ヘアカラーした髪にも"]},
    {"product_title": "アリミノ メン フリーズキープグリース", "category": "ビューティー > ヘアケア > スタイリング"},
    {"product_title": "夕張メロンハイチュウ", "category": "食品・飲料・お酒 > 菓子 > キャンディ"},
    {"product_title": "泡洗顔", "features": ["チルド"]},
    {"product_title": "豆乳イソフラボン 洗顔"},
])
def test_ingredient_or_usage_mentions_do_not_turn_into_item_stops(market, facts):
    assert apply_guardrails([facts], marketplace=market)[0]["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("title,rule_id,action", [
    ("日清キャノーラ油", "COMMON-SLS-FOOD", "BLOCK"),
    ("明治おいしい牛乳", "COMMON-SLS-FOOD", "BLOCK"),
    ("たまご 10個", "COMMON-SLS-FOOD", "BLOCK"),
    ("ヘアカラー", "COMMON-SLS-HAIRCOLOR", "BLOCK"),
    ("白髪染め", "COMMON-SLS-HAIRCOLOR", "BLOCK"),
    ("不織布マスク", "COMMON-MASK", "BLOCK"),
    ("エンジンオイル", "COMMON-SLS-CAROIL", "BLOCK"),
    ("シャーシグリース", "COMMON-SLS-CAROIL", "BLOCK"),
    ("キッチンハイター", "COMMON-TRANSPORT-OXIDIZER", "REVIEW"),
    ("酸素系漂白剤", "COMMON-TRANSPORT-OXIDIZER", "REVIEW"),
    ("納豆", "COMMON-COLD-FOOD", "REVIEW"),
])
def test_actual_item_names_still_stop(market, title, rule_id, action):
    hits = evaluate_policy({"product_title": title}, market)
    assert any(hit.rule_id == rule_id and hit.action == action for hit in hits)
    assert apply_guardrails([{"product_title": title}], marketplace=market)[0]["guardrail_status"] == action


@pytest.mark.parametrize("marker", ["ヘア", "髪", "整髪", "スタイリング", "ワックス", "Hair", "Styling"])
@pytest.mark.parametrize("field", ["product_title", "category"])
@pytest.mark.parametrize("term", ["グリス", "グリース", "grease"])
def test_only_grease_terms_have_the_title_or_category_hair_exception(marker, field, term):
    row = {"product_title": "商品 " + term, field: marker + " " + term}
    hits = evaluate_policy(row, "PH")
    assert not any(hit.rule_id == "COMMON-SLS-CAROIL" for hit in hits)
    row["product_title"] += " エンジンオイル"
    assert any(hit.rule_id == "COMMON-SLS-CAROIL" and hit.term == "エンジンオイル"
               for hit in evaluate_policy(row, "PH"))


def test_description_cannot_grant_the_hair_grease_exception():
    hits = evaluate_policy({"product_title": "シャーシグリース", "description": "Hair Styling"}, "PH")
    assert any(hit.rule_id == "COMMON-SLS-CAROIL" for hit in hits)


def test_chair_is_not_the_english_hair_word():
    hits = evaluate_policy({"product_title": "Chair grease"}, "PH")
    assert any(hit.rule_id == "COMMON-SLS-CAROIL" and hit.action == "BLOCK" for hit in hits)


@pytest.mark.parametrize("category,stops", [
    ("食品・飲料・お酒", False),
    ("お酒", False),
    ("食品・飲料・お酒 > 菓子 > キャンディ", False),
    ("食品・飲料・お酒 > お酒 > リキュール", True),
    ("食品・飲料・お酒 > お酒・リキュール", True),
    ("食品・飲料 > 飲料 > お酒のセット", True),
])
def test_alcohol_category_requires_a_later_node_containing_osake(category, stops):
    hits = evaluate_policy({"product_title": "商品", "category": category}, "SG")
    assert any(hit.rule_id == "COMMON-ALCOHOL-CATEGORY" and hit.action == "BLOCK" for hit in hits) == stops


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("facts,rule_id,action", [
    ({"description": "過酸化水素"}, "COMMON-TRANSPORT-OXIDIZER-INGREDIENT", "REVIEW"),
    ({"description": "要冷蔵"}, "COMMON-COLD-FOOD-LABEL", "REVIEW"),
    ({"description": "レチノール"}, "COMMON-COSMETIC-INGREDIENT", "BLOCK"),
    ({"ingredients": ["医薬部外品"]}, "COMMON-QUASI-FACT", "BLOCK"),
])
def test_content_rules_keep_their_text_and_ingredient_stops(market, facts, rule_id, action):
    row = {"product_title": "食品" if rule_id == "COMMON-COLD-FOOD-LABEL" else "商品", **facts}
    assert any(hit.rule_id == rule_id and hit.action == action for hit in evaluate_policy(row, market))
    assert apply_guardrails([row], marketplace=market)[0]["guardrail_status"] == action


def test_sg_lard_in_a_description_ingredient_list_still_blocks():
    row = {"product_title": "加工食品", "description": "原材料：小麦粉、ラード、食塩"}
    assert any(hit.rule_id == "SG-ANIMAL-FAT" and hit.action == "BLOCK" for hit in evaluate_policy(row, "SG"))
    assert not any(hit.rule_id == "SG-ANIMAL-FAT" for hit in evaluate_policy(row, "PH"))


@pytest.mark.parametrize("field", INGREDIENT_FIELDS)
def test_sg_fat_in_ingredient_columns_requires_food_evidence(field):
    food = {"product_title": "加工食品", field: ["ラード"]}
    assert any(hit.rule_id == "SG-ANIMAL-FAT" and hit.action == "BLOCK" for hit in evaluate_policy(food, "SG"))
    assert apply_guardrails([food], marketplace="SG")[0]["guardrail_status"] == "BLOCK"
    soap = {"product_title": "牛乳石鹸", "category": "ビューティー > ボディケア", field: ["牛脂"]}
    assert not any(hit.rule_id == "SG-ANIMAL-FAT" for hit in evaluate_policy(soap, "SG"))
    assert apply_guardrails([soap], marketplace="SG")[0]["guardrail_status"] == "SAFE"
    unknown = {"product_title": "商品", field: ["ラード"]}
    assert not any(hit.rule_id == "SG-ANIMAL-FAT" for hit in evaluate_policy(unknown, "SG"))


@pytest.mark.parametrize("field", ["product_title", "description"])
def test_sg_fat_title_and_description_keep_their_always_condition(field):
    row = {"product_title": "石けん", field: "牛脂"}
    assert any(hit.rule_id == "SG-ANIMAL-FAT" and hit.action == "BLOCK" for hit in evaluate_policy(row, "SG"))


@pytest.mark.parametrize("field", INGREDIENT_FIELDS)
def test_sg_mushroom_ingredient_in_processed_food_stops(field):
    row = {"product_title": "加工食品", field: ["しいたけエキス"]}
    assert any(hit.rule_id == "SG-MUSHROOM" and hit.action == "BLOCK" for hit in evaluate_policy(row, "SG"))
    assert apply_guardrails([row], marketplace="SG")[0]["guardrail_status"] == "BLOCK"
    assert not any(hit.rule_id == "SG-MUSHROOM" for hit in evaluate_policy(row, "PH"))


def test_every_rule_declares_scope_and_item_rules_have_no_text_or_ingredients():
    rules = load_policy_rules()
    assert all(rule["scope"] in {"item", "content"} for rule in rules)
    assert all(not ({"text", "ingredients"} & set(rule["fields"])) for rule in rules if rule["scope"] == "item")
    by_id = {rule["id"]: rule for rule in rules}
    for rule in rules:
        if rule["id"].startswith("COMMON-GENERAL-TEXT-"):
            assert rule["scope"] == "content"
    for rule_id in ("SG-MEAT", "SG-ANIMAL-FAT", "SG-MUSHROOM", "SG-FOOD"):
        assert by_id[rule_id]["scope"] == "content"
    for rule_id in ("COMMON-COLD-FOOD-LABEL", "COMMON-TRANSPORT-OXIDIZER-INGREDIENT"):
        assert by_id[rule_id]["scope"] == "content"


@pytest.mark.parametrize("scope", [None, "", "ITEM", "unknown", []])
def test_missing_or_invalid_scope_fails_closed(tmp_path, scope):
    data = json.loads((ROOT / "guardrails/policy/rules.json").read_text(encoding="utf-8"))
    if scope is None:
        data["rules"][0].pop("scope")
    else:
        data["rules"][0]["scope"] = scope
    (tmp_path / "rules.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SafetyPolicyError):
        load_policy_rules(tmp_path)
    with pytest.raises(SafetyPolicyError):
        evaluate_policy({}, "PH", data["rules"])


@pytest.mark.parametrize("field", ["text", "ingredients"])
def test_item_scope_rejects_text_and_ingredients_at_load_and_evaluation(tmp_path, field):
    data = json.loads((ROOT / "guardrails/policy/rules.json").read_text(encoding="utf-8"))
    rule = next(rule for rule in data["rules"] if rule["id"] == "COMMON-SLS-FOOD")
    rule["fields"].append(field)
    (tmp_path / "rules.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SafetyPolicyError):
        load_policy_rules(tmp_path)
    with pytest.raises(SafetyPolicyError):
        evaluate_policy({}, "PH", [rule])


class ItemOnlyRow(dict):
    def get(self, key, default=None):
        if key in TEXT_FIELDS + INGREDIENT_FIELDS:
            raise AssertionError("An item rule attempted to read product text or ingredients")
        return super().get(key, default)


def test_item_rules_cannot_read_text_even_through_condition_helpers():
    rules = [rule for rule in load_policy_rules() if rule["scope"] == "item"]
    row = ItemOnlyRow(product_title="商品", description="本品は液体。卵、ヘアカラー、マスク", ingredients=["食用油脂"])
    assert not evaluate_policy(row, "PH", rules)
    # Exercise a helper that reads text for content rules. Item scope must
    # still prevent that description from establishing the liquid condition.
    rule = deepcopy(next(rule for rule in rules if rule["id"] == "COMMON-SLS-FOOD"))
    rule.update(id="TEST-ITEM-CONDITION", terms=["火気注意"], condition="flammable_liquid")
    row["product_title"] = "火気注意"
    assert not evaluate_policy(row, "PH", [rule])


def test_ledger_carries_the_declared_policy_scope():
    with (ROOT / "NG/ledger.csv").open(encoding="utf-8", newline="") as handle:
        rows = {row["id"]: row for row in csv.DictReader(handle) if row["group"] == "保安ルール"}
    for rule in load_policy_rules():
        assert rows[rule["id"]]["scope"] == rule["scope"]
    markdown = (ROOT / "NG/LEDGER.md").read_text(encoding="utf-8")
    assert "| scope |" in markdown
