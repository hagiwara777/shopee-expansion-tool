"""Read-only Shadow projection over current Gate inputs. No clients or storage.

Saved reports alone cannot establish current product identity. Replay V3 only
from explicitly supplied saved Facts matching the current Candidate/text.
"""
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json

from modules.prelisting_candidate_csv import parse_prelisting_candidate_csv
from modules.product_text_safety import (
    ProductTextSafetyError, parse_product_text_safety_sidecar,
    rows_to_product_text_safety_sidecar,
)
from modules.safety_shadow import (
    EVALUATOR_VERSION, FAMILY_RULES, FamilySignal, classify_product,
    fact_from_saved_product,
)

VERSION = "SAFETY_SHADOW_COMPARISON_V1"


@dataclass(frozen=True)
class ShadowComparisonRow:
    candidate_asin: str
    status: str
    reason: str
    signals: tuple[FamilySignal, ...] = ()
    category_basis: str = ""


@dataclass(frozen=True)
class ShadowComparison:
    marketplace: str
    context_sha256: str
    evidence_sha256: str
    rows: tuple[ShadowComparisonRow, ...]


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("INVALID_EVIDENCE")
        result[key] = value
    return result


def _invalid_number(value):
    raise ValueError("INVALID_EVIDENCE")


def comparison_context(candidates, candidate_content, product_text, gate_result, marketplace):
    """Bind every Candidate field, current market, Facts and displayed decision."""
    parsed = parse_prelisting_candidate_csv(candidate_content, filename="candidate.csv")
    if (marketplace not in {"PH", "SG"} or gate_result.marketplace != marketplace
            or any(row.marketplace != marketplace for row in gate_result.rows)
            or tuple(row.candidate for row in gate_result.rows) != candidates.rows
            or parsed.rows != candidates.rows or parsed.schema_version != candidates.schema_version
            or parsed.source_type != candidates.source_type):
        raise ValueError("CONTEXT_MISMATCH")
    return _hash({
        "version": VERSION, "evaluator": EVALUATOR_VERSION,
        "rules": [asdict(rule) for rule in FAMILY_RULES], "marketplace": marketplace,
        "candidate_sha256": hashlib.sha256(candidate_content).hexdigest(),
        "candidates": [asdict(row) for row in candidates.rows],
        "text": None if product_text is None else asdict(product_text),
        "gate": asdict(gate_result),
    })


def compare_saved_shadow(candidates, candidate_content, product_text, gate_result, *,
                         marketplace, evidence_content=None, source_format="keepa_response"):
    """Compute a fresh, separate comparison; never return a modified Gate result.

    NOT_COMPARABLE has no Safety meaning. No title/category substitution, report
    import, ASIN-only joins, or inference of provider timestamps is allowed.
    """
    rows = candidates.rows
    evidence_sha = hashlib.sha256(evidence_content or b"").hexdigest()
    context = ""

    def unavailable(reason):
        return ShadowComparison(marketplace, context, evidence_sha, tuple(
            ShadowComparisonRow(row.candidate_asin, "NOT_COMPARABLE", reason) for row in rows))

    try:
        context = comparison_context(candidates, candidate_content, product_text, gate_result, marketplace)
    except (ValueError, RuntimeError, TypeError, AttributeError):
        return unavailable("CONTEXT_MISMATCH")
    if evidence_content is None:
        return unavailable("MISSING_EVIDENCE")
    counts = Counter(row.candidate_asin for row in rows)
    if product_text is None:
        return unavailable("MISSING_CURRENT_TEXT_FACT")
    try:
        if (product_text.candidate_sha256 != hashlib.sha256(candidate_content).hexdigest()
                or len(product_text.rows) != len(product_text.facts_by_asin)
                or set(product_text.facts_by_asin) != set(counts)):
            return unavailable("CURRENT_TEXT_MISMATCH")
        # Reuse the established schema and field validation, with current bytes.
        encoded = rows_to_product_text_safety_sidecar(candidate_content, rows, product_text.rows)
        checked = parse_product_text_safety_sidecar(
            encoded, filename="text.csv", candidate_content=candidate_content, candidates=candidates)
        if checked != product_text:
            return unavailable("CURRENT_TEXT_MISMATCH")
    except (ProductTextSafetyError, ValueError, TypeError):
        return unavailable("CURRENT_TEXT_MISMATCH")
    try:
        if (not isinstance(evidence_content, bytes) or not evidence_content
                or len(evidence_content) > 10 * 1024 * 1024
                or source_format not in {"keepa_response", "cache_snapshot"}):
            raise ValueError
        payload = json.loads(evidence_content.decode("utf-8-sig"), object_pairs_hook=_unique_keys,
                             parse_constant=_invalid_number)
        if (not isinstance(payload, dict) or not isinstance(payload.get("products"), list)
                or not payload["products"]):
            raise ValueError
        products = {}
        for product in payload["products"]:
            if (not isinstance(product, dict) or not isinstance(product.get("asin"), str)
                    or product["asin"] in products):
                raise ValueError
            products[product["asin"]] = product
        captured = payload.get("fetched_at", "")
        if not isinstance(captured, str):
            raise ValueError
    except (ValueError, UnicodeError, RecursionError):
        return unavailable("INVALID_EVIDENCE")
    output = []
    for row in rows:
        reason, signals, basis = "", (), ""
        product = products.get(row.candidate_asin)
        if counts[row.candidate_asin] != 1:
            reason = "DUPLICATE_CANDIDATE_ASIN"
        elif product is None:
            reason = "MISSING_PRODUCT"
        else:
            try:
                # Cache paths can originate from a seed. Require explicit origin;
                # never inherit the offline adapter's default for a cache export.
                if source_format == "cache_snapshot" and "category_origin" not in product:
                    raise ValueError("CATEGORY_ORIGIN_UNVERIFIED")
                fact = fact_from_saved_product(product, source_format=source_format,
                                               evidence_ref="sha256:" + evidence_sha,
                                               fetched_at=captured)
                if (not fact.title.strip() or not fact.brand.strip() or not fact.fetched_at.strip()
                        or fact.title != row.product_title or fact.brand != row.brand
                        or fact.fetched_at != row.fetched_at):
                    reason = "PRODUCT_IDENTITY_MISMATCH"
                elif fact.text != product_text.facts_by_asin[row.candidate_asin]:
                    reason = "PRODUCT_TEXT_MISMATCH"
                elif fact.domain_id != 5:
                    reason = "PRODUCT_DOMAIN_UNVERIFIED"
                elif (fact.category_origin == "OWN_PRODUCT" and (
                        not fact.category_tree or " > ".join(name for _, name in fact.category_tree) != row.category)):
                    reason = "OWN_CATEGORY_MISMATCH"
                else:
                    basis = ("OWN_PRODUCT_JP" if fact.category_origin == "OWN_PRODUCT"
                             else "TITLE_TEXT_ONLY_" + fact.category_origin)
                    signals = classify_product(fact, include_categories=fact.category_origin == "OWN_PRODUCT")
            except (ValueError, ProductTextSafetyError, TypeError, AttributeError):
                reason = "INVALID_PRODUCT_FACT"
        output.append(ShadowComparisonRow(row.candidate_asin,
                      "NOT_COMPARABLE" if reason else "COMPARABLE", reason, signals, basis))
    return ShadowComparison(marketplace, context, evidence_sha, tuple(output))
