import json
import shutil

import pytest

from modules.brand_monitoring import (
    CONFIG_DIR, BrandMonitoringError, load_brand_monitoring, normalize_brand,
)
from modules.guardrails import apply_guardrails, GuardrailDictionaryError


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("brand", ["Gillette", "ｇｉｌｌｅｔｔｅ", "La Roche-Posay(ラロッシュポゼ)", "Bioré"])
def test_official_ipr_exact_width_case_parentheses_and_latin_accent(market, brand):
    row = apply_guardrails([{"brand": brand, "product_title": "Synthetic ordinary item"}], marketplace=market)[0]
    assert row["guardrail_status"] == "BLOCK"
    assert "shopee_brand_list" in row["guardrail_source"]
    assert "公式監視ブランド（ALL）" in row["guardrail_note"]


@pytest.mark.parametrize("brand", ["KATE", "KATE(カネボウ)", "Kate Spade extra", "ELIXIR", "エリクシール(ELIXIR)"])
def test_no_substring_or_parent_company_inference(brand):
    for market in ("SG", "PH"):
        assert not load_brand_monitoring(market).matches(brand)


def test_kana_dakuten_is_not_removed_as_latin_accent():
    assert normalize_brand("ビオレ") != normalize_brand("ヒオレ")
    assert normalize_brand("Bioré") == normalize_brand("Biore")


def test_country_columns_do_not_leak_and_global_stays_global():
    sg, ph = load_brand_monitoring("SG"), load_brand_monitoring("PH")
    assert sg.matches("Starhub") and not ph.matches("Starhub")
    assert ph.matches("Brilliant Skin Essentials") and not sg.matches("Brilliant Skin Essentials")
    assert sg.matches("HP") and ph.matches("HP")
    assert not sg.matches("HP Plus")


@pytest.mark.parametrize("brand", ["PURITO", "PURITO (퓨리토)", "Fear Of God", "Fear Of God (Essential)"])
def test_official_parenthetical_notes_and_amazon_primary_name(brand):
    assert load_brand_monitoring("SG").matches(brand)


def test_explicit_alias_only_and_outer_brand_is_primary(tmp_path):
    for path in CONFIG_DIR.glob("*.json"):
        shutil.copyfile(path, tmp_path / path.name)
    (tmp_path / "aliases.json").write_text(json.dumps({"aliases": [
        {"alias": "ジレット", "canonical": "Gillette"},
        {"alias": "カネボウ", "canonical": "Kanebo"},
    ]}, ensure_ascii=False), encoding="utf-8")
    # This fixture intentionally replaces the alias inventory with only two
    # entries, so its company exclusion references the canonical name alone.
    title_config = json.loads((tmp_path / "title_review.json").read_text(encoding="utf-8"))
    title_config["company_names"] = ["Kao"]
    (tmp_path / "title_review.json").write_text(json.dumps(title_config), encoding="utf-8")
    data = load_brand_monitoring("SG", tmp_path)
    assert data.matches("ジレット")
    assert data.matches("カネボウ(Kanebo)")
    assert not data.matches("KATE(カネボウ)")
    assert not data.matches("ジレット風")


def test_missing_or_invalid_configuration_stops_instead_of_empty_list(tmp_path, monkeypatch):
    with pytest.raises(BrandMonitoringError):
        load_brand_monitoring("SG", tmp_path)
    monkeypatch.setattr("modules.guardrails.load_brand_monitoring",
                        lambda market: (_ for _ in ()).throw(BrandMonitoringError("invalid")))
    with pytest.raises(GuardrailDictionaryError):
        apply_guardrails([{"brand": "Gillette"}])


def test_corrupt_aliases_fail_closed(tmp_path):
    for path in CONFIG_DIR.glob("*.json"):
        shutil.copyfile(path, tmp_path / path.name)
    (tmp_path / "aliases.json").write_text('{"aliases":[{"alias":"X"}]}', encoding="utf-8")
    with pytest.raises(BrandMonitoringError):
        load_brand_monitoring("PH", tmp_path)


def test_alias_canonical_typo_fails_closed(tmp_path):
    for path in CONFIG_DIR.glob("*.json"):
        shutil.copyfile(path, tmp_path / path.name)
    (tmp_path / "aliases.json").write_text(json.dumps({"aliases":[
        {"alias":"ジレット", "canonical":"Gillete"}]}), encoding="utf-8")
    with pytest.raises(BrandMonitoringError, match="参照先"):
        load_brand_monitoring("SG", tmp_path)




@pytest.mark.parametrize('market', ['SG', 'PH'])
def test_exact_brand_and_conditional_battery_keep_their_gate_behavior(market):
    rows = apply_guardrails([
        {'brand': 'HP', 'product_title': 'ordinary storage box'},
        {'brand': 'HP Plus', 'product_title': 'ordinary storage box'},
        {'brand': 'Synthetic Brand', 'product_title': '電池付きの時計'},
        {'brand': 'Synthetic Brand', 'product_title': '電池を使用しません'},
    ], marketplace=market)
    assert [row['guardrail_status'] for row in rows] == ['BLOCK', 'SAFE', 'BLOCK', 'REVIEW']
    assert rows[0]['guardrail_matched_terms'] == 'HP'


@pytest.mark.parametrize("brand", [
    "メイベリン", "キュレル", "ニベア", "ジレット", "ラ・ロッシュ ポゼ",
    "ｸﾚ･ﾄﾞ･ﾎﾟｰ ﾎﾞｰﾃ", "クレドポーボーテ", "シュウ・ウエムラ",
    "オ―ラルＢ", "オｰラルB", "エスケーツー", "ディオール", "ヴィックス",
])
@pytest.mark.parametrize("market", ["SG", "PH"])
def test_approved_aliases_reach_guardrail_block_with_normalized_spelling(brand, market):
    row = apply_guardrails([{"brand": brand, "product_title": "Synthetic ordinary item"}], marketplace=market)[0]
    assert row["guardrail_status"] == "BLOCK"
    assert "brand_ip" in row["guardrail_risk_category"].split("|")


@pytest.mark.parametrize("brand", [
    "KATE(カネボウ)", "エリクシール(資生堂)", "メイベリン風", "ニベア関連",
    "アリエル", "オラルB", "セラヴィ", "セラ・ヴィ",
])
def test_normalization_does_not_infer_child_brands_substrings_or_ambiguous_aliases(brand):
    assert not load_brand_monitoring("SG").matches(brand)
    assert not load_brand_monitoring("PH").matches(brand)


def test_long_vowel_glyphs_are_equivalent_but_presence_remains_meaningful():
    assert normalize_brand("オーラルB") == normalize_brand("オ―ラルＢ") == normalize_brand("オｰラル B")
    assert normalize_brand("アリエール") != normalize_brand("アリエル")
    assert load_brand_monitoring("SG").matches("アリエール")
    assert normalize_brand("ビオレ") != normalize_brand("ヒオレ")


def test_kao_alias_obeys_country_lists_including_taiwan():
    sg, ph = load_brand_monitoring("SG"), load_brand_monitoring("PH")
    assert sg.matches("花 王") and sg.matches("Kao")
    assert not ph.matches("花王") and not ph.matches("Kao")
    for brand in ("花王", "Kao"):
        assert apply_guardrails([{"brand": brand, "product_title": "Synthetic item"}], marketplace="SG")[0]["guardrail_status"] == "BLOCK"
        assert apply_guardrails([{"brand": brand, "product_title": "Synthetic item"}], marketplace="PH")[0]["guardrail_status"] == "SAFE"
    records = json.loads((CONFIG_DIR / "aliases.json").read_text(encoding="utf-8"))["aliases"]
    assert next(r for r in records if r["canonical"] == "Kao")["markets"] == ["SG", "TW"]
    tw = load_brand_monitoring("TW")
    assert tw.matches("花王") and tw.matches("Kao")


def test_approved_alias_inventory_excludes_competing_name_and_resolves_official_references():
    records = json.loads((CONFIG_DIR / "aliases.json").read_text(encoding="utf-8"))["aliases"]
    assert len(records) == 77
    assert not any(r["alias"] == "セラヴィ" for r in records)
    for market in ("SG", "PH"):
        data = load_brand_monitoring(market)
        for record in records:
            if market in record.get("markets", ["SG", "PH"]) and data.matches(record["canonical"]):
                assert data.matches(record["alias"]), record["alias"]
    assert load_brand_monitoring("PH").matches("CeraVe")  # Canonical BLOCK remains.


@pytest.mark.parametrize("markets", [[], ["SG", "SG"], ["ZZ"], "SG", [123]])
def test_invalid_alias_market_scope_stops(tmp_path, markets):
    for path in CONFIG_DIR.glob("*.json"):
        shutil.copyfile(path, tmp_path / path.name)
    (tmp_path / "aliases.json").write_text(json.dumps({"aliases": [
        {"alias": "花王", "canonical": "Kao", "markets": markets}]}), encoding="utf-8")
    with pytest.raises(BrandMonitoringError, match="対象市場"):
        load_brand_monitoring("SG", tmp_path)


def test_alias_collision_after_space_and_dot_normalization_stops(tmp_path):
    for path in CONFIG_DIR.glob("*.json"):
        shutil.copyfile(path, tmp_path / path.name)
    (tmp_path / "aliases.json").write_text(json.dumps({"aliases": [
        {"alias": "ジレット", "canonical": "Gillette"},
        {"alias": "ジ・レ ット", "canonical": "Nivea"}]}), encoding="utf-8")
    with pytest.raises(BrandMonitoringError, match="重複"):
        load_brand_monitoring("SG", tmp_path)
