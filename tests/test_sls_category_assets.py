import json
from pathlib import Path
import pytest

from modules import sls_category_assets as assets
from sls_category_support import copy_assets, rewrite_asset


@pytest.mark.parametrize("name", ["canonical.json", "canonical.manifest.json", "markets/PH.json", "markets/PH.manifest.json"])
@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_active_asset_failure_closed(tmp_path, monkeypatch, name, failure):
    root = copy_assets(tmp_path, monkeypatch)
    path = root / name
    if failure == "missing":
        path.unlink()
    else:
        path.write_bytes(b"{broken")
    with pytest.raises(assets.SlsAssetError, match="UNAVAILABLE"):
        assets.load_ph_context()


def test_non_ph_corrupt_does_not_load_or_stop_ph(tmp_path, monkeypatch):
    root = copy_assets(tmp_path, monkeypatch)
    for market in ("BR", "SG", "MY", "TW", "VN", "TH"):
        (root / f"markets/{market}.json").write_bytes(b"broken")
    allowed = {root / name for name in ("canonical.json", "canonical.manifest.json", "markets/PH.json", "markets/PH.manifest.json")}
    read = Path.read_bytes
    def checked(path):
        assert path in allowed, f"PH loaded another asset: {path}"
        return read(path)
    monkeypatch.setattr(Path, "read_bytes", checked)
    assert assets.load_ph_context().rules[100869].action == "CATEGORY_ALLOW"


@pytest.mark.parametrize("kind", ["duplicate", "wrong_market", "wrong_taxonomy", "invalid_id", "bad_type"])
def test_valid_digest_does_not_bypass_structure(tmp_path, monkeypatch, kind):
    root = copy_assets(tmp_path, monkeypatch)
    def change(payload):
        if kind == "duplicate":
            payload["records"].append(payload["records"][0])
        elif kind == "wrong_market":
            payload["marketplace"] = "SG"
        elif kind == "wrong_taxonomy":
            payload["taxonomy_version"] = "0" * 64
        elif kind == "invalid_id":
            payload["records"][0]["category_id"] = True
        else:
            payload["records"][0]["status"] = []
    rewrite_asset(root, "markets/PH", change)
    with pytest.raises(assets.SlsAssetError):
        assets.load_ph_context()


def test_duplicate_json_keys_rejected():
    with pytest.raises(ValueError):
        assets._json(b'{"a": 1, "a": 2}')


def test_all_data_asset_digests_and_source_version_counts():
    for manifest_path in assets.ASSET_ROOT.rglob("*.manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        data = manifest_path.with_name(manifest_path.name.replace(".manifest", "")).read_bytes()
        assert assets.hashlib.sha256(data).hexdigest() == manifest["asset_version"] == manifest["sha256"]
        assert len(json.loads(data)["records"]) == manifest["record_count"]
