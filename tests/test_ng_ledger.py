"""DEC-0185: the NG ledger is a complete, up-to-date, read-only view of the NG sources."""
import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_ng_ledger", ROOT / "scripts" / "build_ng_ledger.py")
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)


def test_committed_ledger_matches_the_sources():
    rows, unclaimed = ledger.build()
    assert unclaimed == []
    assert (ROOT / "NG" / "LEDGER.md").read_text(encoding="utf-8") == ledger.render_markdown(rows)
    assert (ROOT / "NG" / "ledger.csv").read_text(encoding="utf-8") == ledger.render_csv(rows)


def test_every_guardrail_file_is_placed_in_the_ledger():
    # A file that no reader claims must be reported, not silently ignored.
    assert ledger.build()[1] == []
    assert "policy/rules.json" in ledger.unclaimed_files(set())
    assert "sls_market_categories/README.md" not in ledger.unclaimed_files(set())


def test_ledger_rows_are_well_formed_and_cover_every_policy_rule():
    import json
    rows = list(csv.DictReader((ROOT / "NG" / "ledger.csv").open(encoding="utf-8", newline="")))
    assert rows and set(rows[0]) == set(ledger.COLUMNS)
    assert len({(r["group"], r["id"]) for r in rows}) == len(rows)
    assert {r["action"] for r in rows} <= {"BLOCK", "REVIEW", ""}
    assert all(r["markets"] and r["source_file"] and (ROOT / r["source_file"]).is_file() for r in rows)
    policy_ids = {r["id"] for r in json.loads(
        (ROOT / "guardrails/policy/rules.json").read_text(encoding="utf-8"))["rules"]}
    assert policy_ids == {r["id"] for r in rows if r["group"] == "保安ルール"}


def test_building_the_ledger_does_not_touch_the_sources():
    before = {p: p.read_bytes() for p in (ROOT / "guardrails").rglob("*") if p.is_file()}
    ledger.build()
    assert before == {p: p.read_bytes() for p in (ROOT / "guardrails").rglob("*") if p.is_file()}


def test_ledger_csv_carries_every_policy_term_for_research_filters():
    # Research skills pre-filter with ledger.csv, so no policy term may be cut off there.
    import json
    rows = {r["id"]: r for r in csv.DictReader((ROOT / "NG" / "ledger.csv").open(encoding="utf-8", newline=""))
            if r["group"] == "保安ルール"}
    for rule in json.loads((ROOT / "guardrails/policy/rules.json").read_text(encoding="utf-8"))["rules"]:
        assert all(ledger.TERM_SEPARATOR not in term for term in rule["terms"])
        assert rows[rule["id"]]["target"].split(ledger.TERM_SEPARATOR) == rule["terms"]


def test_no_new_word_is_written_in_two_places():
    # DEC-0187: one NG decision lives in one place. Intended overlaps are listed by hand.
    rows, _ = ledger.build()
    assert sorted(set(ledger.overlaps(rows)) - ledger.accepted_overlaps()) == []
    assert (ROOT / "NG" / "overlaps.csv").read_text(encoding="utf-8") == ledger.render_overlaps(ledger.overlaps(rows))


def test_overlap_detection_finds_a_word_added_to_two_rules():
    rows, _ = ledger.build()
    extra = dict(rows[0], id="TEST-DUPLICATE", target="テスト専用の重複語")
    twin = dict(extra, id="TEST-DUPLICATE-2")
    found = ledger.overlaps(rows + [extra, twin])
    assert "テスト専用の重複語" in found
    # Different markets do not overlap.
    sg, ph = dict(extra, markets="SG"), dict(twin, markets="PH")
    assert "テスト専用の重複語" not in ledger.overlaps(rows + [sg, ph])


def test_my_th_tw_lists_and_sls_are_listed_and_taiwan_names_match_runtime():
    import json
    from modules.brand_monitoring import country_brand_names
    rows, _ = ledger.build()
    for market in ("MY", "TH", "TW"):
        name = f"counterfeit_{market.lower()}.json"
        assert "brand_monitoring/" + name not in ledger.SUPPORT_FILES
        data = json.loads((ROOT / "guardrails/brand_monitoring" / name).read_text(encoding="utf8"))
        expected = {name for brand in data["brands"] for name in country_brand_names(brand, market)}
        assert expected == {r["target"] for r in rows if r["source_file"].endswith("/" + name)}
        assert any(r["group"] == "SLS発送可否（カテゴリ）" and r["markets"] == market for r in rows)
    assert {"SHISEIDO", "資生堂"} <= {r["target"] for r in rows if r["markets"] == "TW"}
