"""One irreversible JP product attempt, independent of operational caches/budgets.

Import and --help are offline. Execution requires separate Owner authorization.
The SDK's private raw contract is deliberately pinned and tested for 1.5.0.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path

import keepa
import requests

from modules.keepa_bounded_transport import install_bounded_keepa_transport

ASIN = "B00HVLUR18"
DOMAIN = "JP"
DOMAIN_ID = 5
RUNNER_VERSION = "KEEPA_JP_SINGLE_FACT_V1"
ENDPOINT = "https://api.keepa.com/product/?"
TEXT_FIELDS = ("title", "brand", "model", "manufacturer", "description", "features",
               "shortDescription", "safetyWarning", "itemHighlights", "ingredients",
               "activeIngredients", "specialIngredients", "imagesCSV")
REQUEST_OPTIONS = dict(domain=DOMAIN, history=False, offers=None, stock=False,
                       buybox=False, rating=False, videos=False, aplus=False,
                       update=-1, only_live_offers=None, days=None, stats=None,
                       wait=False, raw=True)


class FactRunStopped(RuntimeError):
    """Only stable reason codes cross the CLI boundary; no raw exceptions/keys."""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       indent=2) + "\n").encode("utf-8")


def _write_new(path, content):
    # Exclusive creation leaves even partial files in place after failed fsync.
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _outside_git(path):
    path = Path(path).absolute()
    # Reject links/junctions, including ancestors, before resolving destinations.
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or ancestor.is_junction():
            raise FactRunStopped("LINKED_STORAGE_FORBIDDEN")
        if (ancestor / ".git").exists() or ancestor.name.casefold() == ".git":
            raise FactRunStopped("GIT_STORAGE_FORBIDDEN")
    return path.resolve()


class _Attempt:
    def __init__(self, root, evidence_dir, authorization_ref):
        self.root = root
        self.evidence_dir = evidence_dir
        self.authorization_ref = authorization_ref
        self.reserved = 0

    def reserve_keepa_request(self):
        if self.reserved:
            raise FactRunStopped("HTTP_SEND_LIMIT")
        # The independent directory is a permanent one-shot tombstone. It is
        # never removed, even if record writing or evidence setup fails.
        self.root.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.root.mkdir()
        except FileExistsError:
            raise FactRunStopped("ATTEMPT_ALREADY_EXISTS") from None
        self.reserved = 1
        record = dict(runner_version=RUNNER_VERSION, asin=ASIN, domain=DOMAIN,
                      domain_id=DOMAIN_ID, reserved_http_sends=1,
                      state="RESERVED_RESULT_UNKNOWN", reserved_at=_now(),
                      authorization_ref=self.authorization_ref,
                      evidence_destination_sha256=hashlib.sha256(
                          str(self.evidence_dir).encode("utf-8")).hexdigest())
        _write_new(self.root / "attempt.json", _json_bytes(record))
        if (self.root / "attempt.json").read_bytes() != _json_bytes(record):
            raise FactRunStopped("ATTEMPT_READBACK_FAILED")

    def finish(self, state, sends, reason_code):
        _write_new(self.root / "outcome.json", _json_bytes(dict(
            state=state, reason_code=reason_code, finished_at=_now(), http_send_attempts=sends,
            automatic_resend_allowed=False)))


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("non-JSON constant")

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=reject_constant)
    except (ValueError, UnicodeError):
        raise FactRunStopped("INVALID_JSON") from None
    if type(data) is not dict:
        raise FactRunStopped("INVALID_RESPONSE")
    return data


def _validate_product(data):
    if "error" in data:
        raise FactRunStopped("API_ERROR")
    products = data.get("products")
    if type(products) is not list or len(products) != 1 or type(products[0]) is not dict:
        raise FactRunStopped("PRODUCT_COUNT_OR_SHAPE")
    product = products[0]
    if product.get("asin") != ASIN:
        raise FactRunStopped("ASIN_MISMATCH")
    if type(product.get("domainId")) is not int or product["domainId"] != DOMAIN_ID:
        raise FactRunStopped("DOMAIN_MISMATCH")
    if "domainId" in data and (type(data["domainId"]) is not int or data["domainId"] != DOMAIN_ID):
        raise FactRunStopped("DOMAIN_MISMATCH")
    tree = product.get("categoryTree")
    if tree is not None:
        if type(tree) is not list:
            raise FactRunStopped("INVALID_CATEGORY_TREE")
        ids = []
        for node in tree:
            if (type(node) is not dict or type(node.get("catId")) is not int
                    or node["catId"] <= 0 or type(node.get("name")) is not str
                    or not node["name"].strip()):
                raise FactRunStopped("INVALID_CATEGORY_TREE")
            ids.append(node["catId"])
        if len(ids) != len(set(ids)):
            raise FactRunStopped("INVALID_CATEGORY_TREE")
    root = product.get("rootCategory")
    if root is not None:
        if type(root) is not int or (root <= 0 and root != -1):
            raise FactRunStopped("INVALID_ROOT_CATEGORY")
        if tree and root > 0 and tree[0]["catId"] != root:
            raise FactRunStopped("CATEGORY_ROOT_MISMATCH")
    categories = product.get("categories")
    if categories is not None and (type(categories) is not list or any(
            type(item) is not int or item <= 0 for item in categories)):
        raise FactRunStopped("INVALID_CATEGORIES")
    for field in TEXT_FIELDS:
        value = product.get(field)
        if value is None:
            continue
        valid = type(value) is str
        if field not in {"title", "brand", "model", "manufacturer", "imagesCSV"}:
            valid = valid or (type(value) is list and all(type(v) is str for v in value))
        if not valid:
            raise FactRunStopped("INVALID_FACT_FIELD")
    return product


def _facts(product, fetched_at, digest):
    facts = {}
    for field in (*TEXT_FIELDS, "categoryTree", "rootCategory", "categories"):
        value = product.get(field)
        if field not in product:
            status = "MISSING"
        elif value is None or value == [] or value == -1 or (
                type(value) is str and not value.strip()) or (
                type(value) is list and all(type(v) is str and not v.strip() for v in value)):
            status = "UNKNOWN"
        else:
            status = "PRESENT"
        facts[field] = dict(value=value, status=status,
                            authority="OWN_PRODUCT" if status == "PRESENT" else status,
                            asin=ASIN, acquisition_marketplace=DOMAIN, domain_id=DOMAIN_ID,
                            fetched_at=fetched_at, raw_sha256=digest,
                            evidence_ref=f"raw-response.json#/products/0/{field}")
    tree_fact = facts["categoryTree"]
    tree = product.get("categoryTree")
    for field, value in (("category_path", " > ".join(node["name"] for node in tree) if tree else None),
                         ("leaf_category_id", tree[-1]["catId"] if tree else None)):
        facts[field] = dict(tree_fact, value=value, derivation="ORDERED_OWN_PRODUCT_CATEGORY_TREE")
    return dict(runner_version=RUNNER_VERSION, asin=ASIN, facts=facts)


def _execute_once(*, api_key, evidence_dir, attempt_root, authorization_ref, transport=None):
    """Internal injection seam for offline tests; CLI never overrides attempt root."""
    if version("keepa") != "1.5.0":
        raise FactRunStopped("SDK_VERSION_MISMATCH")
    if (not api_key or not authorization_ref or len(authorization_ref) > 500
            or api_key in authorization_ref):
        raise FactRunStopped("EXPLICIT_AUTHORIZATION_AND_KEY_REQUIRED")
    evidence_dir = _outside_git(evidence_dir)
    attempt_root = _outside_git(attempt_root)
    if (evidence_dir == attempt_root or evidence_dir.is_relative_to(attempt_root)
            or attempt_root.is_relative_to(evidence_dir)):
        raise FactRunStopped("INDEPENDENT_STORAGE_REQUIRED")
    if evidence_dir.exists() or not evidence_dir.parent.is_dir():
        raise FactRunStopped("NEW_DEDICATED_EVIDENCE_DIRECTORY_REQUIRED")
    if attempt_root.exists():
        raise FactRunStopped("ATTEMPT_ALREADY_EXISTS")
    attempt = _Attempt(attempt_root, evidence_dir, authorization_ref)
    sends = 0
    captured = {}
    state = "RESULT_UNKNOWN"
    reason_code = "ACQUISITION_STOPPED"
    api = keepa.Keepa(api_key, check_key=False, timeout=10, logging_level="CRITICAL")
    expected_payload = dict(asin=ASIN, domain=DOMAIN_ID, key=api_key,
                            history=0, stock=0, buybox=0, rating=0, videos=0, aplus=0,
                            update=-1)
    session = requests.Session()
    session.trust_env = False
    session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
    send = session.get if transport is None else transport

    def capture(url, **kwargs):
        nonlocal sends, state
        if sends or url != ENDPOINT or kwargs["params"] != expected_payload:
            raise FactRunStopped("HTTP_SEND_LIMIT_OR_SCOPE")
        # Bounded transport has already persisted the independent reservation.
        state = "SAVE_FAILED"
        evidence_dir.mkdir()
        sends += 1
        state = "RESULT_UNKNOWN"
        response = send(url, **kwargs)
        if api_key.encode("utf-8") in response.content:
            state = "RESPONSE_REJECTED"
            raise FactRunStopped("SECRET_IN_RESPONSE")
        captured.update(status=response.status_code, fetched_at=_now(), raw=response.content)
        state = "SAVE_FAILED"
        _write_new(evidence_dir / "raw-response.json", response.content)
        digest = hashlib.sha256(response.content).hexdigest()
        captured["sha256"] = digest
        _write_new(evidence_dir / "raw-response.sha256", (digest + "\n").encode("ascii"))
        state = "RESPONSE_REJECTED"
        return response

    install_bounded_keepa_transport(api, attempt, transport=capture)
    bounded_request = api._request

    def product_only(request_type, payload, **kwargs):
        if (request_type != "product" or payload != expected_payload
                or kwargs != dict(wait=False, raw_response=True)):
            raise FactRunStopped("REQUEST_SCOPE_MISMATCH")
        return bounded_request(request_type, payload, **kwargs)

    api._request = product_only
    try:
        response = api._product_query([ASIN], **REQUEST_OPTIONS)
        product = _validate_product(_strict_json(response.content))
        state = "SAVE_FAILED"
        facts_bytes = _json_bytes(_facts(product, captured["fetched_at"], captured["sha256"]))
        _write_new(evidence_dir / "facts.json", facts_bytes)
        state = "SUCCESS"
        reason_code = "VALIDATED_AND_SAVED"
    except Exception as exc:
        # Errors can contain a credential-bearing request URL; retain codes only.
        if not attempt.reserved:
            raise FactRunStopped("PRE_SEND_STOP") from None
        if state == "SUCCESS":
            state = "SAVE_FAILED"
        if isinstance(exc, FactRunStopped):
            reason_code = str(exc)
        raise FactRunStopped(state) from None
    finally:
        session.close()
        if attempt.reserved:
            try:
                manifest = dict(runner_version=RUNNER_VERSION, sdk_version="1.5.0",
                                asin=ASIN, domain=DOMAIN, domain_id=DOMAIN_ID,
                                endpoint="product", history=False, update=-1,
                                reserved_http_sends=1, http_send_attempts=sends,
                                max_http_sends=1, automatic_resend_allowed=False,
                                state=state, reason_code=reason_code,
                                http_status=captured.get("status"),
                                fetched_at=captured.get("fetched_at"),
                                raw_sha256=captured.get("sha256"),
                                raw_ref="raw-response.json" if "sha256" in captured else None,
                                facts_ref="facts.json" if state == "SUCCESS" else None,
                                finished_at=_now())
                if state == "SUCCESS":
                    manifest["facts_sha256"] = hashlib.sha256(facts_bytes).hexdigest()
                if evidence_dir.is_dir():
                    _write_new(evidence_dir / "manifest.json", _json_bytes(manifest))
                attempt.finish(state, sends, reason_code)
            except Exception:
                # The original reservation/tombstone survives all save failures.
                raise FactRunStopped("SAVE_FAILED") from None
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=f"Owner-authorized one-shot {ASIN} JP Fact acquisition")
    parser.add_argument("--execute", action="store_true", help="Use only after explicit live API approval")
    parser.add_argument("--authorization-ref", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Execution requires separate Owner approval and --execute")
    appdata = os.environ.get("LOCALAPPDATA")
    if not appdata:
        raise FactRunStopped("PERSISTENT_ATTEMPT_ROOT_REQUIRED")
    return _execute_once(api_key=os.environ.get("KEEPA_API_KEY", ""),
                         authorization_ref=args.authorization_ref,
                         evidence_dir=args.evidence_dir,
                         attempt_root=Path(appdata) / "ShopeeKeepaJPFact" / ASIN)


if __name__ == "__main__":
    try:
        result = main()
        print(result["state"])
    except FactRunStopped as exc:
        print(str(exc))
        raise SystemExit(1) from None
