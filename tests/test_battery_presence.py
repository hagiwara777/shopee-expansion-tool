import pytest

from modules.battery_presence import assess_battery_presence
from modules.guardrails import apply_guardrails, load_sls_shared_battery_rules


def product(title, **facts):
    return {
        "candidate_asin": "B000000001",
        "brand": "Independent example brand",
        "category": "Beauty",
        "product_title": title,
        **facts,
    }


@pytest.mark.parametrize("marketplace", ["SG", "PH"])
@pytest.mark.parametrize("title,facts", [
    ("髭剃り 替刃 10コ 電池付き", {}),
    ("Replacement blade with battery included", {}),
    ("電池内蔵シェーバー用替刃（電池付き）", {}),
    ("電池入り玩具", {}),
    ("Ordinary light", {"description": ["Includes a rechargeable battery."]}),
    ("充電式電池 4本", {}),
    ("モバイルバッテリー 10000mAh", {}),
    ("AA batteries 4 pack", {}),
    ("Replacement battery pack", {}),
    ("電池式ライト", {"description": ["電池を同梱しています。"]}),
])
def test_included_battery_is_blocked_in_each_runtime_market(marketplace, title, facts):
    guarded = apply_guardrails([product(title, **facts)], marketplace=marketplace)[0]
    assert guarded["guardrail_status"] == "BLOCK"
    assert "shipping_restricted" in guarded["guardrail_risk_category"].split("|")
    assert "Battery presence evidence:" in guarded["guardrail_note"]


@pytest.mark.parametrize("marketplace", ["SG", "PH"])
@pytest.mark.parametrize("title,facts", [
    ("髭剃り 電動 替刃 10個", {}),
    ("カミソリ 電動 ホルダー（本体＋刃３コ）", {}),
    ("髭剃り 電動 本体 替刃3個", {}),
    ("普通の照明", {"features": ["単3乾電池1本使用"]}),
    ("Ordinary light", {"itemHighlights": ["Uses 1 AA battery."]}),
    ("Battery-powered light", {}),
    ("電池式ライト 本体", {}),
    ("電動カミソリ本体用替刃", {}),
    ("電動カミソリ ホルダー対応 替刃", {}),
    ("電動歯ブラシ用 替えブラシ", {}),
    ("手動 カミソリ 本体", {"safetyWarning": [
        "振動が弱くなったら電池を入れ替えてください。長期間使用しない時は電池を取り外してください。"
    ]}),
    ("カミソリ 替刃 6コ", {"description": [
        "振動が弱くなったら乾いた場所で電池を入れ替えてください。"
    ]}),
    ("電動カミソリ 本体 電池別売", {}),
    ("電動カミソリ 本体 コード式", {}),
    ("充電式電池用ケース", {}),
    ("rechargeable battery charger", {}),
    ("Replacement blades for electric razor handle", {}),
    ("電池内蔵マウス専用ケース", {}),
    ("電池内蔵マウス用ケース", {}),
    ("電池内蔵シェーバー用替刃", {}),
    ("電池内蔵マウス用パッド", {}),
    ("Replacement blades for a shaver with a built-in battery", {}),
    ("Mouse pad for a mouse with a built-in battery", {}),
    ("Battery-powered light replacement cover", {}),
    ("AA battery holder", {}),
    ("電池が内蔵されていません", {}),
    ("電池付きではありません", {}),
    ("Ordinary light", {"features": ["Batteries not included."]}),
    ("Ordinary light", {"features": ["Does not include a battery."]}),
    ("Ordinary light", {"features": ["Not supplied with batteries."]}),
    ("Ordinary light", {"description": ["If batteries are included, remove them before disposal."]}),
    ("Ordinary accessory", {"safetyWarning": ["Avoid contact with battery fluid."]}),
    ("Ordinary accessory", {"safetyWarning": ["Contains battery acid: avoid contact."]}),
])
def test_uncertain_accessories_and_generic_warnings_stay_review(marketplace, title, facts):
    guarded = apply_guardrails([product(title, **facts)], marketplace=marketplace)[0]
    assert guarded["guardrail_status"] == "REVIEW"


@pytest.mark.parametrize("title,values", [
    ("電動カミソリ 本体", [("description", "電池は付属しません。")]),
    ("電池付き照明", [("description", "電池は別売です。")]),
    ("Electric razor body", [("features", "Batteries sold separately.")]),
])
def test_contradictory_or_no_battery_data_does_not_prove_inclusion(title, values):
    evidence = assess_battery_presence(title, [("product_title", title), *values])
    assert evidence is not None
    assert evidence.action == "REVIEW"


@pytest.mark.parametrize("field", [
    "description", "features", "shortDescription", "safetyWarning", "itemHighlights",
])
def test_direct_inclusion_uses_the_fact_field_for_audit(field):
    guarded = apply_guardrails(
        [product("普通の照明", **{field: ["電池付きです。"]})], marketplace="SG"
    )[0]
    assert guarded["guardrail_status"] == "BLOCK"
    assert f"fact_field={field}" in guarded["guardrail_note"]


@pytest.mark.parametrize("marketplace", ["SG", "PH"])
def test_battery_evidence_cannot_clear_an_existing_block(marketplace):
    guarded = apply_guardrails(
        [product("電動カミソリ 替刃", brand="LEGO")], marketplace=marketplace
    )[0]
    assert guarded["guardrail_status"] == "BLOCK"
    assert "electric_item_battery_presence_unknown" in guarded["guardrail_note"]


def test_normalization_and_unrelated_product_have_no_inclusion_inference():
    title = "髭剃り 電動 本体 替刃３個"
    evidence = assess_battery_presence(title, [("product_title", title)])
    assert evidence is not None and evidence.action == "REVIEW"
    assert assess_battery_presence("普通のコーム", [("product_title", "普通のコーム")]) is None


def test_battery_holder_has_no_inclusion_evidence_and_keeps_ph_existing_block():
    title = "モバイルバッテリー収納ホルダー"
    assert assess_battery_presence(title, [("product_title", title)]) is None
    assert apply_guardrails([product(title)], marketplace="SG")[0]["guardrail_status"] == "REVIEW"
    assert apply_guardrails([product(title)], marketplace="PH")[0]["guardrail_status"] == "BLOCK"


def test_original_sixteen_suspicion_rules_keep_their_ids_and_review_actions():
    rules = load_sls_shared_battery_rules()
    assert len(rules) == 16
    assert [rule.note.split(":", 1)[0] for rule in rules] == [
        f"SLS-BAT-{index:03d}" for index in range(1, 17)
    ]
    assert all(rule.action == "REVIEW" for rule in rules)
