"""Shared synthetic inputs and validated asset copies for SLS tests."""
from dataclasses import replace
import json
from pathlib import Path
import shutil

from modules import sls_category_assets as assets
from modules.category_mapper import (CategoryMapperInput, CategoryMapperInputRow, GATE_ELIGIBLE,
                                     apply_manual_brand, build_recommendations)
from modules.category_mapper_store import CategoryMapperStore
from scripts.build_sls_category_assets import encode, digest


def ready_item(tmp_path):
    store = CategoryMapperStore(tmp_path / "mapper.sqlite3")
    source = CategoryMapperInput("PH", "EXPANSION", GATE_ELIGIBLE, (
        CategoryMapperInputRow("B000000000", "B000000001", "Shampoo", "ASIENCE",
                               "シャンプー", "EXPANSION", GATE_ELIGIBLE),))
    item = build_recommendations(source, resolver_titles=None, store=store)[0]
    return apply_manual_brand(item, brand={"brand_id": 0, "brand_name": "No brand", "is_no_brand": True})


def copy_assets(tmp_path, monkeypatch):
    root = tmp_path / "assets"
    shutil.copytree(assets.ASSET_ROOT, root)
    monkeypatch.setattr(assets, "ASSET_ROOT", root)
    return root


def rewrite_asset(root, name, change):
    path = root / (name + ".json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    change(payload)
    data = encode(payload)
    path.write_bytes(data)
    manifest_path = root / (name + ".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(sha256=digest(data), asset_version=digest(data), record_count=len(payload["records"]))
    manifest_path.write_bytes(encode(manifest))
    return digest(data)


def stop_shampoo(payload):
    row = next(row for row in payload["records"] if row["category_id"] == 100869)
    row.update(status="NO", action="CATEGORY_EXCLUDE", basis="SLS_NOT_SHIPPABLE")
