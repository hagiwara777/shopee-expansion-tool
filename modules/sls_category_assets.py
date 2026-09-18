"""Explicit, market-local loading. Importing this module never reads assets."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping

ASSET_ROOT = Path(__file__).resolve().parents[1] / "guardrails/sls_market_categories"
SCHEMA = "SLS_CATEGORY_ASSET_V1"
TRANSFORM_VERSION = "SLS_SOURCE_TRANSFORM_V1"
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class SlsAssetError(RuntimeError):
    """No fallback: the PH SLS-dependent exits must stop."""


@dataclass(frozen=True)
class SlsSourceRef:
    source_id: str
    sha256: str
    logical_record: int


@dataclass(frozen=True)
class SlsRule:
    status: str
    quantity: str
    action: str
    basis: str
    source_refs: tuple[SlsSourceRef, ...]


@dataclass(frozen=True)
class SlsEvaluationContext:
    marketplace: str
    taxonomy_version: str
    market_asset_version: str
    transform_version: str
    category_ids: frozenset[int]
    rules: Mapping[int, SlsRule]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def _require(condition):
    if not condition:
        raise ValueError("invalid SLS asset")


def _read_asset(root, name, market):
    manifest_path = root / (name + ".manifest.json")
    manifest_bytes = manifest_path.read_bytes()
    manifest = _json(manifest_bytes)
    data = (root / (name + ".json")).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    _require(set(manifest) == {"schema", "transform_version", "sha256", "asset_version",
                               "record_count", "marketplace", "source_hashes"})
    _require(manifest["sha256"] == manifest["asset_version"] == digest)
    _require(manifest["schema"] == SCHEMA and manifest["transform_version"] == TRANSFORM_VERSION)
    _require(manifest["marketplace"] == market)
    payload = _json(data)
    expected_keys = {"schema", "transform_version", "source_ids", "records"}
    if market is not None:
        expected_keys |= {"marketplace", "taxonomy_version", "missing_canonical_ids"}
    _require(set(payload) == expected_keys)
    _require(payload["schema"] == SCHEMA and payload["transform_version"] == TRANSFORM_VERSION)
    _require(payload.get("marketplace") == market)
    _require(type(manifest["record_count"]) is int and manifest["record_count"] > 0)
    _require(type(payload["records"]) is list and len(payload["records"]) == manifest["record_count"])
    _require(set(payload["source_ids"]) == set(manifest["source_hashes"]))
    _require(all(type(v) is str and _HASH.fullmatch(v) for v in manifest["source_hashes"].values()))
    index = {}
    for record in payload["records"]:
        cid = record["category_id"]
        _require(type(cid) is int and cid > 0 and cid not in index)
        _require(type(record["source_refs"]) is list and bool(record["source_refs"]))
        for ref in record["source_refs"]:
            _require(ref["sha256"] == manifest["source_hashes"][ref["source_id"]])
            _require(type(ref["logical_record"]) is int and ref["logical_record"] > 0)
        index[cid] = record
    _require(list(index) == sorted(index))
    return payload, index, digest, manifest_path, manifest_bytes


def load_ph_context() -> SlsEvaluationContext:
    """Validate current bytes, reading only canonical and PH (four files).

    No mtime-only cache, eager all-market validation, raw CSV or provenance I/O.
    Deployment requires app stop/update/restart/new session; hot swap is unsupported.
    """
    try:
        canonical, taxonomy, taxonomy_version, cp, cb = _read_asset(ASSET_ROOT, "canonical", None)
        ph, records, version, pp, pb = _read_asset(ASSET_ROOT, "markets/PH", "PH")
        _require(canonical["source_ids"] == ["master"])
        _require(ph["source_ids"] == ["master", "requirements"])
        _require(ph["taxonomy_version"] == taxonomy_version)
        _require(set(records) <= set(taxonomy))
        _require(ph["missing_canonical_ids"] == sorted(set(taxonomy) - set(records)))
        for record in taxonomy.values():
            _require(set(record) == {"category_id", "names", "name_ja", "source_refs"})
            _require(type(record["names"]) is list and len(record["names"]) == 5)
            _require(all(type(name) is str for name in record["names"]))
            _require(type(record["name_ja"]) is str)
        rules = {}
        for cid, record in records.items():
            _require(set(record) == {"category_id", "status", "quantity", "action", "basis", "source_refs", "anomalies"})
            _require(record["source_refs"] == taxonomy[cid]["source_refs"])
            _require(all(type(record[k]) is str for k in ("status", "quantity", "action", "basis")))
            _require(record["action"] in {"CATEGORY_ALLOW", "CATEGORY_REVIEW", "CATEGORY_EXCLUDE"})
            _require(record["anomalies"] == [])
            rules[cid] = SlsRule(record["status"], record["quantity"], record["action"], record["basis"],
                                 tuple(SlsSourceRef(**ref) for ref in record["source_refs"]))
        _require(cp.read_bytes() == cb and pp.read_bytes() == pb)
        return SlsEvaluationContext("PH", taxonomy_version, version, TRANSFORM_VERSION,
                                    frozenset(taxonomy), MappingProxyType(rules))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise SlsAssetError("SLS_CATEGORY_DATA_UNAVAILABLE") from exc
