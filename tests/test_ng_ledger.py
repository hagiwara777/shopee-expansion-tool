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
