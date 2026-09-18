"""No private raw CSV dependency in CI; deterministic logical-record replay."""
import csv
from io import StringIO
import json
from pathlib import Path
import pytest

from scripts.build_sls_category_assets import ASSET_ROOT, transform, digest


def replay_inputs():
    lock = json.loads((ASSET_ROOT / "source-lock.json").read_text(encoding="utf-8"))
    inputs = {}
    for name in lock["sources"]:
        payload = json.loads((ASSET_ROOT / f"provenance/{name}.json").read_text(encoding="utf-8"))
        out = StringIO(newline="")
        csv.writer(out, lineterminator="\n").writerows(row["raw_fields"] for row in payload["records"])
        inputs[name] = out.getvalue().encode("utf-8")
        # Logical replay is a synthetic input, not a claim to recreate source bytes.
        lock["sources"][name]["sha256"] = digest(inputs[name])
    return inputs, lock


def test_deterministic_replay_preserves_every_raw_field_and_anomaly():
    inputs, lock = replay_inputs()
    first = transform(inputs, lock)
    assert first == transform(inputs, lock)
    for name in inputs:
        actual = json.loads(first[f"provenance/{name}.json"])["records"]
        original = json.loads((ASSET_ROOT / f"provenance/{name}.json").read_text(encoding="utf-8"))["records"]
        assert actual == original
    th = json.loads(first["markets/TH.json"])
    duplicate = next(r for r in th["records"] if r["category_id"] == 102009)
    assert [r["logical_record"] for r in duplicate["source_refs"]] == [293, 294]
    assert duplicate["status"] == "YES" and duplicate["quantity"] == "2"
    assert duplicate["anomalies"] == ["DUPLICATE_ID_DIFFERENT_IDENTITY"]
    assert 102010 in th["missing_canonical_ids"]
    sg = json.loads(first["markets/SG.json"])
    scoped = [r for r in sg["records"] if "group_notice" in r]
    assert [r["category_id"] for r in scoped] == list(range(100906, 100916))
    assert all(r["group_notice"]["source_ref"]["logical_record"] == 273 for r in scoped)
    vn = json.loads(first["markets/VN.json"])["records"]
    assert any(r["under_1m"] == "YES" and "further check" in r["remarks"] for r in vn)
    assert all({"under_1m", "over_1m", "whitelist", "quantity", "remarks"} <= set(r) for r in vn)
    br = json.loads(first["markets/BR.json"])["records"]
    assert any(r["sagawa_raw"] == "YES" and r["status"] == "NO" for r in br)
    assert all(r["status_authority"] == "JPBR" and r["quantity_authority"] == "JPBR(Qty limit)" for r in br)
    for market in ("SG", "MY", "TW", "VN", "TH", "BR"):
        assert all(r["action"] is None for r in json.loads(first[f"markets/{market}.json"])["records"])


def test_source_mismatch_stops_before_output():
    inputs, lock = replay_inputs()
    inputs["master"] += b"\n"
    with pytest.raises(ValueError, match="SOURCE_IDENTITY_MISMATCH"):
        transform(inputs, lock)


def test_duplicate_conflict_and_notice_scope_drift_stop():
    inputs, lock = replay_inputs()
    lock["acceptance"]["sg_pet_food"]["category_ids"] = [100906]
    with pytest.raises(ValueError, match="SG_NOTICE_SCOPE_MISMATCH"):
        transform(inputs, lock)
    inputs, lock = replay_inputs()
    rows = list(csv.reader(StringIO(inputs["th"].decode())))
    rows[293][6] = "NO"
    out = StringIO(newline="")
    csv.writer(out, lineterminator="\n").writerows(rows)
    inputs["th"] = out.getvalue().encode()
    lock["sources"]["th"]["sha256"] = digest(inputs["th"])
    with pytest.raises(ValueError, match="TH_OPERATIVE_CONFLICT"):
        transform(inputs, lock)


def test_committed_normalization_matches_deterministic_logical_replay():
    inputs, synthetic_lock = replay_inputs()
    outputs = transform(inputs, synthetic_lock)
    original_lock = json.loads((ASSET_ROOT / "source-lock.json").read_text(encoding="utf-8"))
    hashes = {original_lock["sources"][name]["sha256"]: spec["sha256"]
              for name, spec in synthetic_lock["sources"].items()}
    def rebind(value):
        if isinstance(value, str):
            return hashes.get(value, value)
        if isinstance(value, list):
            return [rebind(v) for v in value]
        if isinstance(value, dict):
            return {k: rebind(v) for k, v in value.items()}
        return value
    for name in ["canonical"] + ["markets/" + m for m in ("PH", "SG", "MY", "TW", "VN", "TH", "BR")]:
        committed = json.loads((ASSET_ROOT / (name + ".json")).read_text(encoding="utf-8"))
        replayed = json.loads(outputs[name + ".json"])
        assert rebind(committed["records"]) == replayed["records"]
        assert committed.get("missing_canonical_ids") == replayed.get("missing_canonical_ids")


def test_changed_br_authority_header_cannot_silently_swap_columns():
    inputs, lock = replay_inputs()
    inputs["br"] = inputs["br"].replace(b"SAGAWA ,JPBR,", b"JPBR,SAGAWA ,", 1)
    lock["sources"]["br"]["sha256"] = digest(inputs["br"])
    with pytest.raises(ValueError, match="SOURCE_HEADER_MISMATCH"):
        transform(inputs, lock)
