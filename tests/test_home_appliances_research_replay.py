"""Optional local replay of the original research ZIP, never product fixtures in Git.

Set HOME_APPLIANCES_RESEARCH_ZIP to run. This is known-product regression,
not unknown-product validation or evidence of production classification accuracy.
"""
from collections import Counter
import csv
import io
import json
import os
from pathlib import Path
import zipfile

import pytest

from modules.home_appliances_classifier import A, B, C, classify_owned_text
from modules.home_appliances_files import load_inputs, classify_input


def test_known_72_products_73_snapshots(tmp_path):
    source = os.environ.get("HOME_APPLIANCES_RESEARCH_ZIP")
    if not source:
        pytest.skip("Local research ZIP not supplied; no fresh accuracy claim")
    with zipfile.ZipFile(source) as archive:
        references = list(csv.DictReader(io.StringIO(archive.read("classification_results.csv").decode("utf-8-sig"))))
        snapshots = {r["case_id"]: r for r in map(json.loads, archive.read("evidence/keepa_product_fields.jsonl").decode().splitlines())}
    assert len(references) == len(snapshots) == 73
    assert len({r["asin"] for r in references}) == 72
    assert all(r["v3_evaluation_role"] == "REPLAY_ONLY_NO_FRESH_VALIDATION" for r in references)
    counts, changes = Counter(), []
    for ref in references:
        snapshot = snapshots[ref["case_id"]]
        assert snapshot["asin"] == ref["asin"] and snapshot["domainId"] == 5
        raw = snapshot["raw_fields"]
        row = dict(raw, title=raw.get("title", raw.get("product_title", "")))
        row["category"] = " > ".join(n["name"] for n in raw.get("categoryTree", [])) or raw.get("keepa_category", "")
        decision = classify_owned_text(row)
        counts[decision.classification] += 1
        if decision.classification != ref["v3_full_information_class"]:
            changes.append(ref["case_id"])
        # Regression target only; historical title-only records are tested at
        # rule level, not relabeled as complete native product Facts.
        assert decision.classification == ref["reference_class"]
        if raw.get("domainId") == 5:
            path = tmp_path / "original-product.json"
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            item = load_inputs([path], source_format="keepa_response")[0]
            assert classify_input(item).classification == decision.classification
    assert counts == {A: 27, B: 45, C: 1}
    assert set(changes) == {"DEV-B0CPL68SZN", "HOLD-B0FP8YN3CP"}


def test_original_response_files(tmp_path):
    source = os.environ.get("HOME_APPLIANCES_RESEARCH_ZIP")
    if not source:
        pytest.skip("Local saved responses not supplied")
    root = Path(source).parent
    # Original acquisition records can be input together without preprocessing.
    paths = [root / "acquisition" / f"send-{n:02}.response.json" for n in (5, 6, 8, 9)]
    items = load_inputs(paths, source_format="keepa_response")
    assert len(items) == 63
    assert len({item.facts.asin for item in items}) == 63
    assert all(item.facts.fields["title"].fetched_at for item in items)
    assert Counter(classify_input(item).letter for item in items) == {"A": 27, "B": 22, "C": 14}
