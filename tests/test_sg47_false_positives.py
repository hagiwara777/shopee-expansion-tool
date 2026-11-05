"""Owner-reported SG47 wording, without ASIN-specific policy exceptions."""
import json
import shutil
import os

import pytest

from modules.brand_monitoring import CONFIG_DIR, BrandMonitoringError, load_brand_monitoring
from modules.guardrails import apply_guardrails


def guarded(market="SG", **facts):
    return apply_guardrails([{"product_title": "普通の化粧品", **facts}], marketplace=market)[0]


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("field", ["product_title", "category", "description", "features", "safetyWarning", "ingredients"])
@pytest.mark.parametrize("phrase", ["ホホバ種子油", "ブドウ種子エキス", "植物の種子オイル"])
def test_seed_derivatives_are_not_seeds(market, field, phrase):
    row = guarded(market, **{field: phrase})
    assert "種子" not in row["guardrail_matched_terms"].split("|")


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_seed_title_and_category_stop_but_description_does_not(market):
    assert guarded(market, product_title="園芸の種子")["guardrail_status"] == "BLOCK"
    assert guarded(market, category="園芸 > 種子")["guardrail_status"] == "BLOCK"
    assert guarded(market, description="種子")["guardrail_status"] == "SAFE"
    assert guarded(market, product_title="種子油と園芸の種子")["guardrail_status"] == "BLOCK"
    for term in ("園芸用土", "培養土", "生きた動物", "seeds", "gardening soil"):
        assert guarded(market, description=term)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("phrase", [
    "塩素系漂白剤のご使用はおやめください", "漂白剤を使わないでください",
    "塩素系漂白剤 のご使用はおやめください", "塩素系漂白剤　のご使用はおやめください",
    "漂白剤は使用しないでください",
])
def test_bleach_usage_prohibition_is_not_a_product_claim(market, phrase):
    assert guarded(market, safetyWarning=phrase)["guardrail_status"] == "SAFE"
    assert guarded(market, product_title="塩素系漂白剤", safetyWarning=phrase)["guardrail_status"] != "SAFE"
    assert guarded(market, safetyWarning=phrase + "。本品は漂白剤です。")["guardrail_status"] == "REVIEW"
    assert guarded(market, description=phrase)["guardrail_status"] == "REVIEW"


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("phrase", [
    "コンタクトレンズをはずしてからご使用ください", "コンタクトレンズを外してご使用ください",
    "コンタクトレンズ着用の方は外してください", "コンタクトレンズを装用している方は外してください",
])
def test_contact_lens_usage_caution_is_not_a_product_claim(market, phrase):
    assert guarded(market, safetyWarning=phrase)["guardrail_status"] == "SAFE"
    assert guarded(market, product_title="コンタクトレンズ", safetyWarning=phrase)["guardrail_status"] == "BLOCK"
    assert guarded(market, safetyWarning=phrase + "。コンタクトレンズ付きです。")["guardrail_status"] == "BLOCK"
    assert guarded(market, product_title="ヘアカラー", safetyWarning=phrase)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("name", ["ポケモン", "Pokemon", "ＰＯＫＥＭＯＮ"])
def test_title_ip_mismatch_is_sg_review_not_ph_review(name):
    assert guarded(product_title=f"エイトザタラソ 美容液オイル {name}", brand="エイトザタラソ")["guardrail_status"] == "REVIEW"
    assert guarded("PH", product_title=f"エイトザタラソ 美容液オイル {name}", brand="エイトザタラソ")["guardrail_status"] == "SAFE"
    assert guarded(product_title=f"{name} タオル", brand=name)["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("market", ["SG", "PH"])
def test_company_title_exclusion_does_not_release_exact_brand(market):
    assert guarded(market, product_title="メルト モイストシャンプー 花王", brand="melt(メルト)")["guardrail_status"] == "SAFE"
    assert guarded(market, product_title="Kao シャンプー", brand="melt")["guardrail_status"] == "SAFE"
    expected = "BLOCK" if market == "SG" else "SAFE"
    assert guarded(market, brand="花王")["guardrail_status"] == expected


@pytest.mark.parametrize("market", ["SG", "PH"])
@pytest.mark.parametrize("title", ["Supporter pouch", "simple hair finish", "organic shampoo", "happy apple scent", "alphabet HPplus", "JOYFUL タオル", "モカブラウン マスカラ", "シャンプー マイルド"])
def test_generic_english_and_substrings_do_not_flood_review(market, title):
    assert not load_brand_monitoring(market).title_matches(title)


def test_title_matching_preserves_word_boundaries_aliases_and_global_scope():
    for market in ("SG", "PH"):
        monitor = load_brand_monitoring(market)
        assert not monitor.title_matches("xxGillettezz タオル")
        assert monitor.title_matches("ギレット ジレット タオル")
        assert monitor.title_matches("(GILLETTE) タオル")
        assert monitor.title_matches("ブランド: Apple 用ポーチ")
        assert not monitor.title_matches("Tiffany pouch")  # Company-only block list is not the official list.


def test_title_exclusions_are_configurable_and_invalid_config_stops(tmp_path):
    for path in CONFIG_DIR.glob("*.json"):
        shutil.copyfile(path, tmp_path / path.name)
    config = json.loads((tmp_path / "title_review.json").read_text(encoding="utf-8"))
    config["company_names"] = []
    (tmp_path / "title_review.json").write_text(json.dumps(config), encoding="utf-8")
    assert load_brand_monitoring("SG", tmp_path).title_matches("花王 シャンプー")
    (tmp_path / "title_review.json").unlink()
    with pytest.raises(BrandMonitoringError):
        load_brand_monitoring("SG", tmp_path)


def test_reused_settings_are_immutable_and_current_content_still_fails_closed(tmp_path):
    for path in CONFIG_DIR.glob("*.json"):
        shutil.copyfile(path, tmp_path / path.name)
    first = load_brand_monitoring("SG", tmp_path)
    assert load_brand_monitoring("SG", tmp_path) is first
    with pytest.raises(TypeError):
        first.aliases["ポケモン"] = "not-an-official-brand"
    config = tmp_path / "title_review.json"
    valid, before = config.read_bytes(), config.stat()
    # Size and timestamp equality must not hide invalid current content.
    config.write_bytes(b"!" + valid[1:])
    os.utime(config, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(BrandMonitoringError):
        load_brand_monitoring("SG", tmp_path)
    config.write_bytes(valid)
    assert load_brand_monitoring("SG", tmp_path).matches("花王")
    assert not load_brand_monitoring("PH", tmp_path).matches("花王")
