"""DEC-0129 SG body confirmation, offline and limited to two product families.

Names create questions, never confirmed body Facts. Confirmations belong to
one whole Candidate and its supplied text Facts. Hashes detect accidental
mixups/edits; they do not authenticate the human or the source documents.
"""

from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import re
import unicodedata


VERSION = "SG_BODY_CONFIRMATION_V1"
POLICY = "DEC-0129"
BODY_REASON_CODES = ("SG_BODY_REVIEW", "SG_BODY_EXCLUDE")
FAMILIES = ("KNIFE", "CONTACT_LENS")
OUTCOMES = ("UNRESOLVED", "BODY_PRESENT", "ACCESSORY_ONLY")
_PATTERNS = {
    "KNIFE": re.compile(
        r"\b(?:kitchen|chef(?:['’]s)?|cook(?:['’]s)?|paring|bread|santoku|gyuto|nakiri|fruit)[\s-]+kn(?:ife|ives)\b"
        r"|\b(?:santoku|gyuto|nakiri)\b|包丁|庖丁|牛刀|三徳|柳刃|出刃|ペティナイフ"
    ),
    "CONTACT_LENS": re.compile(r"\bcontact[\s-]+lens(?:es)?\b|コンタクト[\s・]*レンズ|カラコン"),
}


class SGBodySafetyError(ValueError):
    """A confirmation cannot safely be associated with current inputs."""


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def body_suspicions(title, text=None):
    """Return family/matched-field evidence, without using seed category or AI."""
    fields = {"product_title": (title,)}
    if text is not None and text.capture_status == "CAPTURED":
        for field in ("description", "features", "short_description", "safety_warning", "item_highlights"):
            fields[field] = getattr(text, field)
    matches = {}
    for family, pattern in _PATTERNS.items():
        evidence = []
        for field, values in fields.items():
            for value in values:
                match = pattern.search(unicodedata.normalize("NFKC", "" if value is None else str(value)).casefold())
                if match:
                    evidence.append(f"{field}:{match.group()}")
        if evidence:
            matches[family] = tuple(evidence)
    return matches


def _context(candidates, product_text):
    facts = {} if product_text is None else product_text.facts_by_asin
    asins = [row.candidate_asin for row in candidates.rows]
    if product_text is not None and (set(facts) != set(asins) or len(product_text.rows) != len(facts)):
        raise SGBodySafetyError("商品文章とCandidateのASINが一致しません。")
    binding = _digest({
        "marketplace": "SG", "version": VERSION, "policy": POLICY,
        "candidate_schema": candidates.schema_version, "source_type": candidates.source_type,
        "candidates": [asdict(row) for row in candidates.rows],
        "product_text": None if product_text is None else asdict(product_text),
    })
    targets = {}
    for row in candidates.rows:
        for family, evidence in body_suspicions(row.product_title, facts.get(row.candidate_asin)).items():
            targets[(row.candidate_asin, family)] = evidence
    return binding, targets, len(asins) == len(set(asins))


def prepare_body_confirmations(candidates, product_text=None, confirmations=None):
    binding, targets, unique = _context(candidates, product_text)
    if confirmations is None:
        result = dict(schema=VERSION, policy=POLICY, marketplace="SG", context_sha256=binding, records=[])
        return _seal(result)
    result = deepcopy(confirmations)
    if (not isinstance(result, dict) or set(result) != {
            "schema", "policy", "marketplace", "context_sha256", "records", "integrity_sha256"}
            or result["schema"] != VERSION or result["policy"] != POLICY or result["marketplace"] != "SG"
            or result["context_sha256"] != binding or not isinstance(result["records"], list)
            or result["integrity_sha256"] != _digest({k: v for k, v in result.items() if k != "integrity_sha256"})):
        raise SGBodySafetyError("SG本体確認記録が現在のCandidate・商品文章・方針と一致しません。")
    seen = set()
    for record in result["records"]:
        if not isinstance(record, dict) or set(record) != {
                "candidate_asin", "family", "outcome", "evidence_reviewed", "note"}:
            raise SGBodySafetyError("SG本体確認記録の形式が不正です。")
        key = (record["candidate_asin"], record["family"])
        if (not unique or key not in targets or key in seen or record["outcome"] not in OUTCOMES
                or type(record["evidence_reviewed"]) is not bool
                or (record["outcome"] != "UNRESOLVED" and not record["evidence_reviewed"])
                or not isinstance(record["note"], str) or not record["note"].strip()
                or len(record["note"]) > 2000):
            raise SGBodySafetyError("対象商品と確認内容・根拠を確認してください。")
        seen.add(key)
    return result


def _seal(result):
    result["integrity_sha256"] = _digest({k: v for k, v in result.items() if k != "integrity_sha256"})
    return result


def record_body_confirmation(candidates, product_text, confirmations, *, asin, family,
                             outcome, evidence_reviewed, note):
    result = prepare_body_confirmations(candidates, product_text, confirmations)
    records = {(r["candidate_asin"], r["family"]): r for r in result["records"]}
    key = (asin, family)
    previous = records.get(key)
    if previous is not None and previous["outcome"] == "BODY_PRESENT" and outcome != "BODY_PRESENT":
        raise SGBodySafetyError("本体・実同梱の確認済み除外を、この操作で解除できません。")
    records[key] = dict(candidate_asin=asin, family=family, outcome=outcome,
                        evidence_reviewed=evidence_reviewed, note=note)
    result["records"] = [records[key] for key in sorted(records)]
    return prepare_body_confirmations(candidates, product_text, _seal(result))


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SGBodySafetyError("確認記録に重複した項目があります。")
        result[key] = value
    return result


def parse_body_confirmations(content, candidates, product_text=None):
    try:
        if not isinstance(content, bytes) or not content or len(content) > 10 * 1024 * 1024:
            raise ValueError
        value = json.loads(content.decode("utf-8-sig"), object_pairs_hook=_unique_keys)
        if not isinstance(value, dict):
            raise ValueError
        return prepare_body_confirmations(candidates, product_text, value)
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise SGBodySafetyError("SG本体確認記録を検証できません。現在の候補・商品文章との対応を確認してください。") from exc


def body_confirmation_bytes(confirmations):
    return json.dumps(confirmations, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def body_checks(candidates, product_text=None, confirmations=None):
    result = prepare_body_confirmations(candidates, product_text, confirmations)
    _, targets, _ = _context(candidates, product_text)
    records = {(r["candidate_asin"], r["family"]): r for r in result["records"]}
    return tuple(dict(candidate_asin=asin, family=family, evidence=evidence,
                      outcome=records.get((asin, family), {}).get("outcome", "UNRESOLVED"),
                      note=records.get((asin, family), {}).get("note", ""))
                 for (asin, family), evidence in targets.items())


def apply_sg_body_safety(base_result, candidates, product_text=None, confirmations=None):
    """Add stops to the current base result; accessory confirmation clears only ours."""
    if base_result.marketplace != "SG" or any(r.marketplace != "SG" for r in base_result.rows):
        raise SGBodySafetyError("本体確認はSGだけに適用できます。")
    if tuple(r.candidate for r in base_result.rows) != tuple(candidates.rows):
        raise SGBodySafetyError("本体確認のCandidateがGateと一致しません。")
    if any(set(r.reason_codes) & set(BODY_REASON_CODES) for r in base_result.rows):
        raise SGBodySafetyError("本体確認は元のGate結果へ適用してください。")
    checks = body_checks(candidates, product_text, confirmations)
    rows = []
    for base in base_result.rows:
        relevant = [check for check in checks if check["candidate_asin"] == base.candidate.candidate_asin]
        final, reasons, note = base.final_eligibility, base.reason_codes, base.guardrail_note
        outcomes = {check["outcome"] for check in relevant}
        if "BODY_PRESENT" in outcomes:
            final, reasons = "EXCLUDE", reasons + ("SG_BODY_EXCLUDE",)
        elif "UNRESOLVED" in outcomes:
            if final != "EXCLUDE":
                final = "REVIEW"
            reasons += ("SG_BODY_REVIEW",)
        if relevant:
            detail = "; ".join(f"{c['family']}:{c['outcome']} [{', '.join(c['evidence'])}] {c['note']}" for c in relevant)
            note = f"{note} | {POLICY} SG body: {detail}".strip(" |")
        rows.append(replace(base, final_eligibility=final, reason_codes=reasons, guardrail_note=note))
    return replace(base_result, rows=tuple(rows),
                   eligible_count=sum(r.final_eligibility == "ELIGIBLE" for r in rows),
                   review_count=sum(r.final_eligibility == "REVIEW" for r in rows),
                   exclude_count=sum(r.final_eligibility == "EXCLUDE" for r in rows))
