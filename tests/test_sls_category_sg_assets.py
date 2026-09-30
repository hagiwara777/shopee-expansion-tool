"""SG loader contracts, market isolation and data-only metadata validation."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import json
import pytest
from modules import sls_category_assets as assets
from sls_category_support import copy_assets, rewrite_asset


def test_valid_context_and_only_four_files(monkeypatch):
    read = Path.read_bytes
    seen = []
    def track(path):
        seen.append(path.relative_to(assets.ASSET_ROOT).as_posix())
        return read(path)
    monkeypatch.setattr(Path, "read_bytes", track)
    context = assets.load_sg_context()
    assert set(seen) == {"canonical.json", "canonical.manifest.json", "markets/SG.json", "markets/SG.manifest.json"}
    assert len(context.names) == 2162 and len(context.rules) == 2162
    assert context.marketplace == "SG"
    assert sum(rule.group_notice for rule in context.rules.values()) == 10
    with pytest.raises(TypeError):
        context.rules[1] = None
    with pytest.raises(FrozenInstanceError):
        context.marketplace = "PH"


@pytest.mark.parametrize("name", ["canonical.json", "canonical.manifest.json", "markets/SG.json", "markets/SG.manifest.json"])
@pytest.mark.parametrize("fault", ["missing", "corrupt"])
def test_required_file_failure(tmp_path, monkeypatch, name, fault):
    root = copy_assets(tmp_path, monkeypatch)
    path = root / name
    if fault == "missing":
        path.unlink()
    else:
        path.write_bytes(b"invalid")
    with pytest.raises(assets.SlsAssetError):
        assets.load_sg_context()


@pytest.mark.parametrize("change", [
    lambda p: p.update(marketplace="PH"),
    lambda p: p.update(taxonomy_version="0" * 64),
    lambda p: p.update(transform_version="invalid"),
    lambda p: p["records"][0].update(category_id=True),
    lambda p: p["records"][0].update(category_id=0),
    lambda p: p["records"][0].update(category_id="100001"),
    lambda p: p["records"][1].update(category_id=p["records"][0]["category_id"]),
    lambda p: p["records"][0].update(action="CATEGORY_ALLOW"),
    lambda p: p["records"][0].update(basis="NO_CATEGORY_STOP"),
    lambda p: p["records"][0].update(anomalies=["contradiction"]),
    lambda p: p["records"][0]["source_refs"][0].update(sha256="0" * 64),
    lambda p: p["records"][0]["source_refs"][0].update(logical_record=True),
    lambda p: next(r for r in p["records"] if r.get("group_notice"))["group_notice"].update(normalized_status="YES"),
    lambda p: next(r for r in p["records"] if r.get("group_notice"))["group_notice"]["scope_category_ids"].append(999999),
    lambda p: next(r for r in p["records"] if r.get("group_notice"))["group_notice"].update(text="other"),
    lambda p: next(r for r in p["records"] if r.get("group_notice")).pop("group_notice"),
])
def test_recomputed_manifest_does_not_release_invalid_contract(tmp_path, monkeypatch, change):
    root = copy_assets(tmp_path, monkeypatch)
    rewrite_asset(root, "markets/SG", change)
    with pytest.raises(assets.SlsAssetError):
        assets.load_sg_context()


def test_other_markets_and_raw_provenance_are_not_runtime_dependencies(tmp_path, monkeypatch):
    root = copy_assets(tmp_path, monkeypatch)
    for path in (root / "markets").glob("*"):
        if not path.name.startswith("SG."):
            path.write_bytes(b"corrupt other market")
    for path in (root / "provenance").rglob("*"):
        if not path.is_file():
            continue
        path.write_bytes(b"corrupt raw provenance")
    assert assets.load_sg_context().marketplace == "SG"


def test_sg_corruption_does_not_affect_ph(tmp_path, monkeypatch):
    root = copy_assets(tmp_path, monkeypatch)
    (root / "markets/SG.json").write_bytes(b"bad")
    assert assets.load_ph_context().marketplace == "PH"


@pytest.mark.parametrize("name", ["canonical","markets/SG"])
def test_valid_json_digest_mismatch_is_rejected(tmp_path,monkeypatch,name):
    root=copy_assets(tmp_path,monkeypatch)
    path=root/(name+".json")
    path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises(assets.SlsAssetError):
        assets.load_sg_context()


def test_duplicate_json_key_is_rejected(tmp_path,monkeypatch):
    root=copy_assets(tmp_path,monkeypatch)
    path=root/"markets/SG.manifest.json"
    original=path.read_text(encoding="utf-8")
    path.write_text(original.replace('"marketplace": "SG"','"marketplace": "SG", "marketplace": "SG"'),encoding="utf-8")
    with pytest.raises(assets.SlsAssetError):
        assets.load_sg_context()
