"""Deterministic, source-specific SLS transform. Raw CSVs stay outside Git.

Run with five explicit paths; --check compares bytes without writing. Source
identity is accepted through source-lock.json, never inferred from filenames.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path

TRANSFORM_VERSION = "SLS_SOURCE_TRANSFORM_V1"
SCHEMA = "SLS_CATEGORY_ASSET_V1"
ASSET_ROOT = Path(__file__).resolve().parents[1] / "guardrails/sls_market_categories"


def encode(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ph_decision(status: str, quantity: str) -> tuple[str, str]:
    if status.strip() == "NO":
        return "CATEGORY_EXCLUDE", "SLS_NOT_SHIPPABLE"
    if status.strip() == "Shopeeと要確認":
        return "CATEGORY_REVIEW", "SHOPEE_CHECK_REQUIRED"
    if status.strip() == "YES" and quantity.strip() == "No limit":
        return "CATEGORY_ALLOW", "NO_CATEGORY_STOP"
    if status.strip() == "YES" and quantity.strip().isdigit():
        return "CATEGORY_REVIEW", "QUANTITY_LIMIT"
    return "CATEGORY_REVIEW", "UNRESOLVED_RULE"


def transform(inputs: dict[str, bytes], lock: dict) -> dict[str, bytes]:
    """Pure transform, validating every source before producing any output."""
    records = {}
    outputs = {}
    sources = lock["sources"]
    if set(inputs) != {"master", "requirements", "vn", "th", "br"} or set(sources) != set(inputs):
        raise ValueError("SOURCE_SET_MISMATCH")
    for name, data in inputs.items():
        spec = sources[name]
        if digest(data) != spec["sha256"]:
            raise ValueError("SOURCE_IDENTITY_MISMATCH: " + name)
        rows = list(csv.reader(StringIO(data.decode("utf-8-sig"), newline=""), strict=True))
        if len(rows) != spec["logical_records"] or any(len(row) != spec["width"] for row in rows):
            raise ValueError("SOURCE_SHAPE_MISMATCH: " + name)
        records[name] = rows
        outputs[f"provenance/{name}.json"] = encode({
            "schema": SCHEMA, "transform_version": TRANSFORM_VERSION,
            "source": spec,
            "records": [{"logical_record": i, "raw_fields": row} for i, row in enumerate(rows, 1)],
        })

    def ref(name, n):
        return {"source_id": name, "sha256": sources[name]["sha256"], "logical_record": n}

    def category_id(value):
        if not value.isascii() or not value.isdigit() or int(value) <= 0:
            raise ValueError("INVALID_CATEGORY_ID")
        return int(value)

    def put(name, payload):
        data = encode({"schema": SCHEMA, "transform_version": TRANSFORM_VERSION, **payload})
        outputs[name + ".json"] = data
        outputs[name + ".manifest.json"] = encode({
            "schema": SCHEMA, "transform_version": TRANSFORM_VERSION,
            "asset_version": digest(data), "sha256": digest(data),
            "record_count": len(payload["records"]),
            "marketplace": payload.get("marketplace"),
            "source_hashes": {key: sources[key]["sha256"] for key in payload["source_ids"]},
        })

    master = records["master"]
    category_names = [f"L{i} Category Name" for i in range(1, 6)]
    expected_headers = {
        "master": (2, category_names + ["Unique Category ID", "（日本語）カテゴリー名"]
                   + ["発送可能？", "配送可能個数の上限"] * 4
                   + ["発送可能？"] * 3 + ["Cat. ID check"]),
        "vn": (5, category_names + ["Category ID", "whitelist required (O/X)",
               "Order amount less than 1,000,000", "Order amount over 1,000,000", "qty limit",
               "Duty & Tax % applied when importing from Vietnam", "VAT applied %", "Remarks"]),
        "th": (0, category_names + ["Unique Cat ID", "TH\n(can ship?)", "TH\n(Qty limit per order)",
               "Cat", "Probability of d&t exemption", "Min. duty rate", "Max. duty rate", "Average duty rate"]),
        "br": (0, ["Unique Cat ID", "L1 Category Name", "L2 Category Name", "L3 Category Name",
               "SAGAWA ", "JPBR", "JPBR\n(Qty limit)"]),
    }
    for name, (index, header) in expected_headers.items():
        if records[name][index] != header:
            raise ValueError("SOURCE_HEADER_MISMATCH: " + name)
    taxonomy = [{"category_id": category_id(row[5]), "names": row[:5], "name_ja": row[6], "source_refs": [ref("master", n)]} for n, row in enumerate(master[3:], 4)]
    ids = {row["category_id"] for row in taxonomy}
    if len(ids) != len(taxonomy) or len(ids) != lock["acceptance"]["canonical_count"]:
        raise ValueError("CANONICAL_ID_MISMATCH")
    put("canonical", {"source_ids": ["master"], "records": sorted(taxonomy, key=lambda r: r["category_id"])})
    taxonomy_version = digest(outputs["canonical.json"])
    markets = {}
    notice = lock["acceptance"]["sg_pet_food"]
    notice_row = master[notice["logical_record"] - 1]
    actual_scope = sorted(category_id(row[5]) for row in master[3:] if row[:2] == ["Pets", "Pet Food"])
    if actual_scope != notice["category_ids"] or "すべてのペットフード商品" not in notice_row[7] or "発送が禁止" not in notice_row[7]:
        raise ValueError("SG_NOTICE_SCOPE_MISMATCH")
    for market, offset in (("SG", 7), ("PH", 9), ("MY", 11), ("TW", 13)):
        rows = []
        for n, row in enumerate(master[3:], 4):
            cid = category_id(row[5])
            action, basis = ph_decision(row[offset], row[offset + 1]) if market == "PH" else (None, "DATA_ONLY_RUNTIME_NOT_EVALUATED")
            entry = {"category_id": cid, "status": row[offset], "quantity": row[offset + 1], "action": action, "basis": basis, "source_refs": [ref("master", n)], "anomalies": []}
            if market == "SG" and cid in notice["category_ids"]:
                entry["group_notice"] = {"scope_category_ids": notice["category_ids"], "source_ref": ref("master", notice["logical_record"]), "text": notice_row[7], "normalized_status": "NO"}
            rows.append(entry)
        markets[market] = (rows, ["master", "requirements"])

    vn = []
    for n, row in enumerate(records["vn"][6:], 7):
        vn.append({"category_id": category_id(row[5]), "under_1m": row[7], "over_1m": row[8], "whitelist": row[6], "quantity": row[9], "remarks": row[12], "action": None, "basis": "DATA_ONLY_RUNTIME_NOT_EVALUATED", "source_refs": [ref("vn", n)], "anomalies": []})
    markets["VN"] = (vn, ["vn", "requirements"])
    th = defaultdict(list)
    for n, row in enumerate(records["th"][1:], 2):
        th[category_id(row[5])].append((n, row))
    duplicate_ids = sorted(cid for cid, rows in th.items() if len(rows) != 1)
    if duplicate_ids != lock["acceptance"]["th_duplicate_ids"]:
        raise ValueError("TH_DUPLICATE_MISMATCH")
    th_rows = []
    for cid, rows in th.items():
        if len({tuple(row[6:8]) for _, row in rows}) != 1:
            raise ValueError("TH_OPERATIVE_CONFLICT")
        th_rows.append({"category_id": cid, "status": rows[0][1][6], "quantity": rows[0][1][7], "action": None, "basis": "DATA_ONLY_RUNTIME_NOT_EVALUATED", "source_refs": [ref("th", n) for n, _ in rows], "anomalies": ["DUPLICATE_ID_DIFFERENT_IDENTITY"] if len(rows) > 1 else []})
    markets["TH"] = (th_rows, ["th", "requirements"])
    br = []
    for n, row in enumerate(records["br"][1:], 2):
        br.append({"category_id": category_id(row[0]), "status": row[5], "quantity": row[6], "status_authority": "JPBR", "quantity_authority": "JPBR(Qty limit)", "sagawa_raw": row[4], "action": None, "basis": "DATA_ONLY_RUNTIME_NOT_EVALUATED", "source_refs": [ref("br", n)], "anomalies": []})
    markets["BR"] = (br, ["br", "requirements"])
    for market, (rows, source_ids) in markets.items():
        market_ids = {row["category_id"] for row in rows}
        if len(market_ids) != len(rows) or not market_ids <= ids or len(rows) != lock["acceptance"]["market_counts"][market]:
            raise ValueError("MARKET_ID_MISMATCH: " + market)
        put("markets/" + market, {"marketplace": market, "source_ids": source_ids, "taxonomy_version": taxonomy_version, "records": sorted(rows, key=lambda r: r["category_id"]), "missing_canonical_ids": sorted(ids - market_ids)})
    if dict(Counter(row["action"] for row in markets["PH"][0])) != lock["acceptance"]["ph_actions"]:
        raise ValueError("PH_ACCEPTANCE_COUNTS_MISMATCH")
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for source in ("master", "requirements", "vn", "th", "br"):
        parser.add_argument("--" + source, type=Path, required=True)
    parser.add_argument("--asset-root", type=Path, default=ASSET_ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    lock = json.loads((args.asset_root / "source-lock.json").read_text(encoding="utf-8"))
    outputs = transform({name: getattr(args, name).read_bytes() for name in lock["sources"]}, lock)
    for name, content in outputs.items():
        path = args.asset_root / name
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                raise ValueError("NORMALIZED_OUTPUT_MISMATCH: " + name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    print(f"PASS: {len(outputs)} deterministic assets; PH acceptance counts verified")


if __name__ == "__main__":
    main()
