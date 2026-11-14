"""Owner acceptance examples. No external calls or captured product payloads."""
import json
from pathlib import Path

import pytest

from modules.guardrails import apply_guardrails, evaluate_deterministic_blocks_v2, load_deterministic_block_rules_v2
from modules.safety_policy import SafetyPolicyError, evaluate_policy, load_policy_rules
from modules.brand_monitoring import load_brand_monitoring


def guarded(title="普通の雑貨", *, market="SG", **facts):
    return apply_guardrails([{"product_title": title, **facts}], marketplace=market)[0]


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("phrase", ["アルコールフリー", "ノンアルコール", "alcohol-free", "fake lashes", "つけまつげ"])
@pytest.mark.parametrize("field", ["product_title", "description", "features", "safetyWarning"])
def test_owner_harmless_expressions_produce_neither_block_nor_review(market, phrase, field):
    assert guarded(market=market, **{field: phrase})["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("phrase", ["アルコールフリー", "ノンアルコール", "alcohol-free", "fake lashes", "つけまつげ"])
def test_exclusions_do_not_hide_another_positive_statement(market, phrase):
    row = guarded(market=market, description=[phrase, "医療機器"])
    assert row["guardrail_status"] == "BLOCK"
    row = guarded(market=market, description=[phrase, "アルコール配合"])
    assert row["guardrail_status"] == "REVIEW"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("term", ["偽物", "fake", "replica", "コピー品", "医薬品", "medicine", "処方箋",
    "prescription", "タバコ", "cigarette", "アルコール", "武器", "weapon", "弾薬", "アダルト",
    "adult only", "R18", "18禁", "違法", "illegal", "脱税", "盗品"])
def test_general_words_are_title_block_and_description_review(market, term):
    assert guarded(term, market=market)["guardrail_status"] == "BLOCK"
    # DEC-0181 treats the specific tobacco product term as BLOCK in text too.
    expected = "BLOCK" if term == "タバコ" else "REVIEW"
    assert guarded(market=market, description=term)["guardrail_status"] == expected


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("term", ["第1類医薬品", "第2類医薬品", "第3類医薬品", "指定医薬部外品", "医療機器", "処方薬"])
def test_clear_medical_classifications_block_in_description(market, term):
    assert guarded(market=market, description=term)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("term", ["医薬品ではありません", "医薬部外品ではありません", "not a medicine", "not a medical device"])
def test_direct_medical_negation_is_not_a_positive_classification(term):
    assert guarded(description=term)["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("term", ["アゼライン酸", "ハイドロキノン", "ヒドロキノン", "レチノール", "ナイアシンアミド",
    "アルブチン", "トランサミン", "トラネキサム酸", "AHA", "グリコール酸", "サリチル酸", "コウジ酸",
    "ビタミンA", "ビタミンB3", "ボトックス", "ボツリヌス", "トレチノイン", "レチノイン酸"])
def test_new_ingredient_policy_does_not_read_ingredient_columns(market, term):
    assert guarded(term + " 美容液", market=market)["guardrail_status"] == "BLOCK"
    assert guarded(market=market, description=term)["guardrail_status"] == "BLOCK"
    for field in ("ingredients", "activeIngredients", "specialIngredients"):
        assert guarded(market=market, **{field: [term]})["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("field", ["product_title", "description", "ingredients", "activeIngredients", "specialIngredients"])
def test_diphenhydramine_remains_a_fact_block_including_ph(market, field):
    assert guarded(market=market, **{field: "ジフェンヒドラミン塩酸塩"})["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("term", ["CBD", "大麻", "マリファナ", "ヘンプ", "Hemp", "ガンビル", "Gambir",
    "Sativa", "Cannabis", "アヘン", "コカイン", "ケタミン", "ブフォテニン", "hemp-free", "龍角散"])
@pytest.mark.parametrize("market", ["SG", "PH"])
def test_shared_drug_policy_reads_text_and_ingredients(term, market):
    for field in ("product_title", "description", "ingredients"):
        assert guarded(market=market, **{field: term})["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("title", ["AHAVA soap", "ビタミンABC", "ビタミンB30", "notdiphenhydramine"])
def test_short_latin_terms_have_boundaries(title):
    assert guarded(title)["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_saved_lebel_examples_as_synthetic_current_facts(market):
    assert guarded("普通のシャンプー", market=market, itemHighlights=["ヘアスタイリング"])["guardrail_status"] == "SAFE"
    assert guarded("普通のシャンプー", market=market, ingredients=["LPG", "DME"])["guardrail_status"] == "REVIEW"
    assert guarded("ヘアスタイリング スプレー", market=market)["guardrail_status"] == "REVIEW"
    assert guarded("カラートリートメント", market=market)["guardrail_status"] == "BLOCK"
    assert guarded("普通のシャンプー", market=market, category="ビューティー > ヘアケア・カラー・スタイリング > シャンプー")["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("title,expected", [
    ("不織布マスク", "BLOCK"), ("立体マスク", "BLOCK"), ("N95 マスク", "BLOCK"),
    ("防塵マスク", "BLOCK"), ("ヘアマスク", "SAFE"), ("美容用シートマスク", "SAFE"),
    ("フェイスパック", "SAFE"), ("マスク", "REVIEW"),
    ("剣付きフィギュア", "BLOCK"), ("銃型キーホルダー", "BLOCK"),
    ("剣の模型が付属するペンダント", "BLOCK"), ("武器を使うキャラクターのフィギュア", "REVIEW"),
    ("レーザーポインター 5mW", "BLOCK"), ("レーザーポインター 1mW", "SAFE"),
    ("レーザーポインター", "REVIEW"), ("ハイライター 化粧品", "SAFE"),
    ("マスカラ トップコート", "SAFE"), ("ネイル トップコート", "BLOCK"),
    ("エッグプロテイン配合シャンプー", "SAFE"), ("牛乳 1L", "BLOCK"),
    ("普通の食品のつめかえ用", "SAFE"), ("商品の小分け", "REVIEW"),
    ("サンプル", "REVIEW"), ("試供品", "REVIEW"), ("sample", "REVIEW"),
])
def test_owner_context_examples(title, expected):
    assert guarded(title)["guardrail_status"] == expected


@pytest.mark.parametrize("title", ["サンプル", "試供品", "小分け"])
def test_samples_are_shared_even_for_config_only_future_markets(title):
    for market in ("SG", "PH", "MY", "TH", "TW"):
        hits = evaluate_policy({"product_title": title}, market)
        assert [h.action for h in hits] == ["REVIEW"]


@pytest.mark.parametrize("title,sg,ph", [
    ("チューイングガム", "BLOCK", "SAFE"), ("ビーフジャーキー", "BLOCK", "SAFE"),
    ("トランシーバー", "BLOCK", "REVIEW"), ("歯ブラシ", "SAFE", "BLOCK"),
    ("デンタルフロス", "SAFE", "BLOCK"), ("トランプ", "SAFE", "BLOCK"),
    ("ダーマローラー", "SAFE", "BLOCK"), ("肥料", "SAFE", "BLOCK"),
    ("ペットフード", "BLOCK", "BLOCK"), ("サプリメント", "BLOCK", "BLOCK"),
    ("kitchen knife", "BLOCK", "BLOCK"), ("包丁", "BLOCK", "BLOCK"),
    ("モバイルバッテリー", "BLOCK", "BLOCK"),
])
def test_market_differences_are_data_not_input_origin(title, sg, ph):
    assert guarded(title, market="SG")["guardrail_status"] == sg
    assert guarded(title, market="PH")["guardrail_status"] == ph


@pytest.mark.parametrize("title", ["Kitchen knife case", "Kitchen knife sharpener", "包丁研ぎ器"])
def test_sg_knife_accessory_is_not_mistaken_for_a_body(title):
    # The separate SG body gate still requires a reviewed confirmation.
    # DEC-0190: a case gets shared REVIEW; existing sharpening exclusions stay.
    expected = "REVIEW" if title == "Kitchen knife case" else "SAFE"
    assert guarded(title, market="SG")["guardrail_status"] == expected


@pytest.mark.parametrize("description", ["Includes a kitchen knife", "Contains a knife"])
def test_sg_accessory_with_explicit_knife_body_stays_blocked(description):
    assert guarded("Kitchen knife case", market="SG", description=description)["guardrail_status"] == "BLOCK"


def test_ph_contact_lens_body_and_accessory_are_distinct():
    assert guarded("Contact lens", market="PH")["guardrail_status"] == "BLOCK"
    assert guarded("Contact lens case", market="PH")["guardrail_status"] == "SAFE"
    assert guarded("Contact lens case", market="PH", description="Contains a contact lens")["guardrail_status"] == "BLOCK"
    # Existing plural-term stops, including accessories, cannot be relaxed.
    assert guarded("Contact lenses case", market="PH")["guardrail_status"] == "BLOCK"


def test_future_market_common_rules_and_my_country_brands():
    assert evaluate_policy({"product_title": "ナイアシンアミド 美容液"}, "MY")[0].action == "BLOCK"
    assert evaluate_deterministic_blocks_v2({"ingredients": ["GABA"]}, load_deterministic_block_rules_v2(), marketplace="MY")
    assert not evaluate_policy({"product_title": "普通の食品"}, "MY")
    assert evaluate_policy({"product_title": "普通の食品"}, "TH")[0].action == "BLOCK"
    assert load_brand_monitoring("MY").matches("Hada Labo")


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("brand", ["Louis Vuitton", "Gucci", "Chanel", "Hermès", "Prada", "Rolex", "Cartier", "Tiffany", "Burberry", "Dior"])
def test_ten_company_brands_are_shared_exact_matches(market, brand):
    assert guarded(market=market, brand=brand)["guardrail_status"] == "BLOCK"
    assert guarded(market=market, brand=brand + "風")["guardrail_status"] == "SAFE"


def test_approved_milbon_and_pokemon_aliases_do_not_infer_subbrands():
    assert load_brand_monitoring("SG").matches("ミルボン(MILBON)")
    assert load_brand_monitoring("SG").matches("ポケモン")
    assert not load_brand_monitoring("PH").matches("ミルボン(MILBON)")
    for brand in ("インテグレート(資生堂)", "KATE(カネボウ)", "エリクシール(資生堂)"):
        assert not load_brand_monitoring("SG").matches(brand)


@pytest.mark.parametrize("contents", ["{}", '{"schema":"bad"}', "[]", "null"])
def test_policy_damage_fails_closed(tmp_path, contents):
    (tmp_path / "rules.json").write_text(contents, encoding="utf-8")
    with pytest.raises(SafetyPolicyError):
        load_policy_rules(tmp_path)


def test_all_source_no_categories_have_a_stop_signal_without_assigning_categories():
    base = Path(__file__).resolve().parents[1] / "guardrails/sls_market_categories"
    canonical = {r["category_id"]: " > ".join(filter(None, r["names"])) for r in json.loads((base / "canonical.json").read_text(encoding="utf-8"))["records"]}
    rules = load_policy_rules()
    for market, count in (("SG", 171), ("PH", 174)):
        rows = json.loads((base / f"markets/{market}.json").read_text(encoding="utf-8"))["records"]
        prohibited = [r for r in rows if r["status"] == "NO"]
        assert len(prohibited) == count
        for row in prohibited:
            path = canonical[row["category_id"]]
            hits = evaluate_policy({"category": path}, market, rules)
            assert hits, (market, path)
            expected = "REVIEW" if path in {"Health > Others", "Health > Personal Care > Others", "Health > Sexual Wellness > Others"} else "BLOCK"
            assert expected in {h.action for h in hits}, (market, path)
            assert all(h.action != "ALLOW" for h in hits)
    assert not evaluate_policy({"category": "Others"}, "SG", rules)
    assert not evaluate_policy({"category": "Beauty > Hair Care"}, "SG", rules)
