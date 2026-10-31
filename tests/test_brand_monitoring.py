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


def test_fromax_keeps_monitoring_and_conditional_battery_out_of_paste_list():
    from modules.fromax_ng_export import build_fromax_ng_export
    result = build_fromax_ng_export("SG")
    assert "HP" not in result.keywords
    assert "電池入り商品" not in result.keywords
    assert any(c.term == "HP" and "完全一致" in c.reason for c in result.cautions)
    assert any(c.term == "電池入り商品" and "条件付き" in c.reason for c in result.cautions)
