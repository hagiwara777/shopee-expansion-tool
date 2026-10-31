import csv
from io import StringIO
from pathlib import Path
import shutil
import pytest

from modules.fromax_ng_export import build_fromax_ng_export


def test_sg_export_separates_otc_boundary_brands_and_asin_from_paste_list():
    bundle = build_fromax_ng_export("SG")
    caution_terms = {c.term.casefold() for c in bundle.cautions}
    assert "医薬品" in bundle.keywords
    assert "医薬部外品" not in bundle.keywords and "薬用" not in bundle.keywords
    assert "OTC" not in bundle.keywords and "otc" in caution_terms
    assert "otc" in "Hotcake".casefold()  # FROMAX would stop this unrelated product.
    assert "Adidas" not in bundle.keywords and "adidas" in caution_terms
    assert "B000FQTRS0" not in bundle.keywords and "b000fqtrs0" in caution_terms
    assert "medical device" not in {s.casefold() for s in bundle.keywords}
    assert "medical device" in caution_terms


def test_width_and_kana_variants_are_finite_but_not_kanji_synonyms():
    bundle = build_fromax_ng_export("SG")
    assert "ジフェンヒドラミン" in bundle.keywords
    assert "じふぇんひどらみん" in bundle.keywords
    assert "湿疹" not in bundle.keywords and "しっしん" not in bundle.keywords  # REVIEW, not BLOCK.
    assert len({v.casefold() for v in bundle.keywords}) == len(bundle.keywords)
    assert bundle.keywords_txt.decode("utf-8").splitlines() == list(bundle.keywords)
    assert not bundle.keywords_txt.startswith(b"\xef\xbb\xbf")


def test_market_specific_v2_and_community_blocks_are_not_mixed():
    sg, ph = build_fromax_ng_export("SG"), build_fromax_ng_export("PH")
    assert "ギャバ" in ph.keywords and "ギャバ" not in sg.keywords
    assert "gaba" in {c.term.casefold() for c in ph.cautions}
    assert "gaba" not in {c.term.casefold() for c in sg.cautions}
    assert "医療機器" in sg.keywords and "医療機器" in ph.keywords
    rows = list(csv.DictReader(StringIO(sg.cautions_csv.decode("utf-8-sig"))))
    assert rows and all(r["通常リストから分けた理由"] for r in rows)
    assert any("Community NG" in r["出典"] for r in rows)


def test_disabled_block_rule_does_not_reappear_as_an_ng_keyword(tmp_path):
    source = Path(__file__).resolve().parents[1] / "guardrails"
    for name in ("risk_keywords_sg.csv", "prohibited_brands_sg.csv", "deterministic_block_rules_v2.csv"):
        shutil.copyfile(source / name, tmp_path / name)
    with (tmp_path / "risk_keywords_sg.csv").open("a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(("架空の無効語", "BLOCK", "medical_or_therapeutic", "title", "contains", "internal_rule", "Synthetic disabled test", "FALSE"))
    bundle = build_fromax_ng_export("SG", dictionary_dir=tmp_path)
    assert "架空の無効語" not in bundle.keywords
    assert all(c.term != "架空の無効語" for c in bundle.cautions)


@pytest.mark.parametrize("market", ["MY", "TH", "", "sg"])
def test_inactive_or_implicit_market_is_not_exported(market):
    with pytest.raises(ValueError):
        build_fromax_ng_export(market)
