"""File-only adapter and separate CSV contract for Home Appliances sorting."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import csv
import io
import json
from pathlib import Path
import re

from modules.home_appliances_classifier import C, DETAIL_FIELDS, VERSION, Decision, classify_owned_text
from modules.sg_beta_facts import ProductFacts, facts_from_saved_keepa

SOURCE_FORMATS = ("keepa_response", "saved_fact", "cache_snapshot")
CSV_COLUMNS = ("ASIN", "商品名", "ブランド", "カテゴリ", "分類結果", "分類名",
               "判定理由コード", "判断根拠", "不足している情報", "分類ルールバージョン",
               "商品情報の出所", "取得時刻", "注意事項")
NOTICE = "候補仕分けのみ。Aは出品許可ではなく、Bは法律上の販売禁止ではありません。Cは未確認。"
MAX_BYTES = 50 * 1024 * 1024
MAX_PRODUCTS = 10000


class InputError(ValueError):
    """Stable reason code; never echo file contents or raw exceptions."""


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _invalid_constant(value):
    raise InputError("INVALID_JSON_NUMBER")


def _decode(text):
    try:
        return json.loads(text, object_pairs_hook=_unique_keys, parse_constant=_invalid_constant)
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("INVALID_JSON") from None


def _timestamp(value):
    if not isinstance(value, str):
        raise InputError("INVALID_FETCHED_AT")
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError
    except ValueError:
        raise InputError("INVALID_FETCHED_AT") from None
    return value


@dataclass(frozen=True)
class SavedInput:
    facts: ProductFacts
    source: str
    issue: str = ""


def _records(payload):
    if isinstance(payload, list):
        return payload, "", {}
    if not isinstance(payload, dict):
        raise InputError("INVALID_DOCUMENT_SHAPE")
    if "products" in payload:
        if payload.get("error") or not isinstance(payload["products"], list):
            raise InputError("INVALID_PRODUCT_RESPONSE")
        dated = payload.get("fetched_at", payload.get("research_fetched_at", ""))
        return payload["products"], _timestamp(dated), payload
    return [payload], "", {}


def _adapt(product, *, source_format, source, captured, envelope):
    if not isinstance(product, dict) or not isinstance(product.get("asin"), str):
        raise InputError("INVALID_PRODUCT_ASIN")
    asin = product["asin"]
    if not re.fullmatch(r"[A-Z0-9]{10}", asin):
        raise InputError("INVALID_PRODUCT_ASIN")
    issue = ""
    for obj in (envelope, product):
        if "domainId" in obj and (type(obj["domainId"]) is not int or obj["domainId"] != 5):
            issue = "PRODUCT_MARKET_MISMATCH"
        if "acquired_market" in obj and obj["acquired_market"] != "JP":
            issue = "PRODUCT_MARKET_MISMATCH"
    if source_format == "saved_fact":
        try:
            fact = ProductFacts.from_dict(product)
        except (ValueError, TypeError, AttributeError, KeyError):
            raise InputError("INVALID_SAVED_FACT") from None
        for field in fact.fields.values():
            _timestamp(field.fetched_at)
        return SavedInput(fact, source, issue)
    # Never infer JP from --source-format, filename, root category or cache defaults.
    if type(product.get("domainId")) is not int or product.get("domainId") != 5:
        issue = issue or "PRODUCT_MARKET_UNVERIFIED"
    for key in ("source_asin", "candidate_asin", "target_asin"):
        if key in product and product[key] != asin:
            issue = "PRODUCT_ASIN_MISMATCH"
    if "field_origins" in product and not isinstance(product["field_origins"], dict):
        raise InputError("INVALID_FIELD_ORIGINS")
    captured = _timestamp(product.get("fetched_at", captured))
    try:
        fact = facts_from_saved_keepa(product, evidence_ref=source, fetched_at=captured,
                                     source_format=source_format)
    except (ValueError, TypeError, AttributeError, KeyError):
        raise InputError("INVALID_PRODUCT_FACT") from None
    # Cache exports are comparison-only, even if a legacy file claims ownership.
    if source_format == "cache_snapshot":
        issue = "CACHE_FACT_NOT_VERIFIED"
    return SavedInput(fact, source, issue)


def load_inputs(paths, *, source_format):
    """Accept original responses, product arrays/objects, or JSONL records.

    Saved Fact records retain the existing {asin, fields} contract. An API's
    response timestamp/lastUpdate and filesystem dates are not fetched_at.
    """
    if source_format not in SOURCE_FORMATS:
        raise InputError("UNSUPPORTED_SOURCE_FORMAT")
    output, total = [], 0
    for input_number, path in enumerate(paths, 1):
        path = Path(path)
        try:
            if path.stat().st_size > MAX_BYTES:
                raise InputError("INPUT_SIZE_LIMIT")
            content = path.read_bytes()
        except OSError:
            raise InputError("INPUT_READ_FAILED") from None
        total += len(content)
        if total > MAX_BYTES:
            raise InputError("INPUT_SIZE_LIMIT")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeError:
            raise InputError("INPUT_NOT_UTF8") from None
        if not text.strip():
            raise InputError("EMPTY_INPUT")
        source = f"{source_format}:input-{input_number}:sha256:{sha256(content).hexdigest()}"
        payloads = [_decode(line) for line in text.splitlines() if line.strip()] if path.suffix.lower() == ".jsonl" else [_decode(text)]
        for payload in payloads:
            products, captured, envelope = _records(payload)
            if not products:
                raise InputError("EMPTY_PRODUCTS")
            for product in products:
                output.append(_adapt(product, source_format=source_format, source=source,
                                     captured=captured, envelope=envelope))
                if len(output) > MAX_PRODUCTS:
                    raise InputError("PRODUCT_COUNT_LIMIT")
    if not output:
        raise InputError("EMPTY_INPUT")
    if any(n > 1 for n in Counter(item.facts.asin for item in output).values()):
        raise InputError("DUPLICATE_ASIN_OR_CONFLICTING_SNAPSHOTS")
    return tuple(output)


def classify_input(item):
    facts = item.facts
    needed = ("title", "category_tree", "brand", "description", "features", "shortDescription", "itemHighlights")
    missing, invalid, row = [], [], {}
    for name in needed:
        field = facts.fields[name]
        empty = field.value in (None, "", [], ())
        # Raw response ownership is established by an explicitly selected format
        # and Product.domainId. Missing acquisition time is reported, not invented.
        owned = (field.origin == "OWN_PRODUCT" and field.source_asin == facts.asin
                 and field.acquired_market == "JP" and bool(field.evidence_ref)
                 and (item.source.startswith("keepa_response:") or field.owned_by(facts.asin)))
        if empty:
            missing.append(name)
        elif not owned:
            invalid.append(name)
            missing.append(name + ":対象ASIN自身のJP取得・出所証明")
        else:
            row["category" if name == "category_tree" else name] = (
                " > ".join(node["name"] for node in field.value) if name == "category_tree" else field.value)
    if not facts.fields["title"].fetched_at:
        missing.append("取得時刻（未記録）")
    if item.issue or invalid:
        decision = Decision(C, item.issue or "FACT_PROVENANCE_UNVERIFIED",
                            "ASIN・JP取得市場・項目の出所を確認できないため、候補の通過を保留。",
                            "対象ASIN・JP取得市場・Fact出所の整合した証拠")
    else:
        decision = classify_owned_text(row)
    missing.append(decision.missing_information)
    return Decision(decision.classification, decision.reason_code, decision.evidence,
                    "; ".join(x for x in missing if x))


def _safe_cell(value):
    text = str(value)
    # Preserve display text while preventing spreadsheet formula interpretation.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def csv_bytes(items):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for item in items:
        fact, decision = item.facts, classify_input(item)
        tree = fact.fields["category_tree"].value
        timestamps = sorted({fact.fields[k].fetched_at for k in ("title", "category_tree", *DETAIL_FIELDS)
                             if fact.fields[k].value and fact.fields[k].fetched_at})
        writer.writerow([_safe_cell(v) for v in (
            fact.asin, fact.fields["title"].value, fact.fields["brand"].value,
            " > ".join(n["name"] for n in tree), decision.letter, decision.classification,
            decision.reason_code, decision.evidence, decision.missing_information, VERSION,
            item.source, "; ".join(timestamps), NOTICE)])
    return stream.getvalue().encode("utf-8-sig")
