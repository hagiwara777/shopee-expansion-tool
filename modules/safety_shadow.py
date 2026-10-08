"""Offline product-role hypotheses. No sales decisions, clients, or persistence."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from modules.guardrails import normalize_text
from modules.product_text_safety import (
    ProductTextSafetyFact,
    extract_keepa_product_text_safety_fact,
    product_text_safety_fact_from_product_data,
)

EVALUATOR_VERSION = "SAFETY_SHADOW_V3"
ROLES = frozenset({"BODY_CANDIDATE", "ACCESSORY_CANDIDATE", "CONFLICT", "UNKNOWN"})
TEXT_FIELDS = ("description", "features", "shortDescription", "safetyWarning", "itemHighlights")


@dataclass(frozen=True)
class FamilyRule:
    family: str
    version: str
    related_terms: tuple[str, ...]
    body_terms: tuple[str, ...]
    accessory_terms: tuple[str, ...]
    bundle_terms: tuple[str, ...]
    absent_body_terms: tuple[str, ...]
    body_ids: tuple[int, ...] = ()
    accessory_ids: tuple[int, ...] = ()
    category_source: str = "UNVERIFIED_NO_CATEGORY_RULE"
    related_ids: tuple[int, ...] = ()


# Classification examples, not national prohibited-item dictionaries. IDs are JP
# only, supported by the saved knife metadata audit; no Shopee IDs are used.
FAMILY_RULES = (
    FamilyRule(
        "KNIFE", "KNIFE_JP_SHADOW_V1",
        ("knife", "knives", "包丁", "ナイフ", "牛刀", "三徳", "出刃", "砥石", "研ぎ器"),
        ("knife", "knives", "包丁", "ナイフ", "牛刀", "三徳", "出刃"),
        ("sharpener", "whetstone", "sheath", "knife case", "knife cover", "blade guard", "knife accessories", "包丁付属品",
         "storage holder", "包丁ケース", "包丁カバー", "包丁サヤ", "サヤケース", "ナイフカバー",
         "シャープナー", "研ぎ器", "砥石", "ブレードガード", "ブレードプロテクション", "布巻き"),
        ("knife included", "includes knife", "includes a knife", "包丁付き", "包丁付属"),
        ("knife not included", "knives not included", "no knife included", "without knife",
         "包丁は付属しません", "包丁は含まれません", "包丁別売", "包丁とサヤは付属しません"),
        (490276011, 13945771, 490275011), (13945801, 14617042051),
        "KNIFE_20_PRODUCT_METADATA_AUDIT_20261008", (13944721,),
    ),
    FamilyRule(
        "CONTACT_LENS", "CONTACT_LENS_JP_SHADOW_V2",
        ("contact lens", "contact lenses", "コンタクトレンズ", "カラコン"),
        ("contact lens", "contact lenses", "コンタクトレンズ", "カラコン"),
        ("lens case", "lenses case", "lens solution", "lenses solution", "lens cleaner",
         "lens care", "lens holder", "レンズケース", "レンズ用ケース", "レンズ洗浄", "洗浄液",
         "保存液", "レンズケア", "コンタクトケース", "コンタクト収納ケース", "コンタクトケア用品"),
        ("contact lenses included", "contact lens included", "includes contact lenses", "レンズ付き"),
        ("lenses not included", "lens not included", "no lenses included", "レンズは付属しません"),
        (2356869051,), (362602011, 362594011),
        "CONTACT_LENS_12_PRODUCT_METADATA_AUDIT_20261008",
    ),
)
NON_PRODUCT_TERMS = ("book", "poster", "illustration", "書籍", "図鑑", "柄のみ")
GUIDE_TERMS = ("buying guide", "instruction guide", "購入ガイド")
REFERENCE_TERMS = ("in the photographs", "in the photos", "in photographs only", "shown in photos",
                   "写真内", "写真に写る", "写真のみ")
NON_SUPPLY_TERMS = ("not supplied", "not included", "sold separately", "付属しません", "含まれません", "別売")
# Observed JP book root, independent of Keepa type. It provides non-product
# context, never a sales exemption or an ancestor-to-leaf role mapping.
NON_PRODUCT_ROOT_IDS = (465392,)


@dataclass(frozen=True)
class ProductFact:
    asin: str
    title: str
    brand: str
    category_tree: tuple[tuple[int, str], ...]
    categories: tuple[int, ...]
    domain_id: int | None
    category_origin: str
    text: ProductTextSafetyFact
    evidence_ref: str
    fetched_at: str
    last_update: int | None
    keepa_type: str  # Audit only; never used to classify.
    ingredient_values: tuple[tuple[str, tuple[str, ...]], ...]
    categories_capture_status: str

    def guardrail_input(self) -> dict[str, Any]:
        """Same factual fields for the unchanged facade; never a Shadow role."""
        row: dict[str, Any] = {
            "candidate_asin": self.asin, "product_title": self.title, "brand": self.brand,
            "category": " > ".join(name for _, name in self.category_tree)
            if self.category_origin == "OWN_PRODUCT" else "",
            **dict(self.ingredient_values),
        }
        for external, internal in zip(TEXT_FIELDS, (
            "description", "features", "short_description", "safety_warning", "item_highlights"
        )):
            row[external] = getattr(self.text, internal)
        return row


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return tuple(x for x in value if x.strip())
    raise ValueError("SHADOW_INVALID_TEXT")


def fact_from_saved_product(product: Mapping[str, Any], *, source_format: str,
                            evidence_ref: str, fetched_at: str = "") -> ProductFact:
    """Adapt explicit saved raw Keepa responses or cache exports, without fetching."""
    if source_format not in {"keepa_response", "cache_snapshot"}:
        raise ValueError("SHADOW_UNSUPPORTED_FORMAT")
    asin = product.get("asin")
    if not isinstance(asin, str) or not re.fullmatch(r"[A-Z0-9]{10}", asin):
        raise ValueError("SHADOW_INVALID_ASIN")
    if not evidence_ref:
        raise ValueError("SHADOW_MISSING_EVIDENCE_REF")
    captured = product.get("fetched_at")
    if captured is None or captured == "":
        captured = fetched_at
    if not isinstance(captured, str):
        raise ValueError("SHADOW_INVALID_CAPTURE_TIME")
    domain = product.get("domainId")
    if domain is not None and (type(domain) is not int or domain <= 0):
        raise ValueError("SHADOW_INVALID_DOMAIN")
    origin = product.get("category_origin", "OWN_PRODUCT")
    if origin not in {"OWN_PRODUCT", "SEED_FALLBACK", "MISSING"}:
        raise ValueError("SHADOW_INVALID_CATEGORY_ORIGIN")
    tree_key = "categoryTree" if source_format == "keepa_response" else "category_tree"
    tree = product.get(tree_key)
    categories = product.get("categories")
    tree = [] if tree is None else tree
    categories = [] if categories is None else categories
    if not isinstance(tree, list) or not isinstance(categories, list):
        raise ValueError("SHADOW_INVALID_CATEGORY_FACT")
    nodes = []
    for node in tree:
        if (not isinstance(node, dict) or type(node.get("catId")) is not int
                or node["catId"] <= 0 or not isinstance(node.get("name"), str)):
            raise ValueError("SHADOW_INVALID_CATEGORY_NODE")
        nodes.append((node["catId"], node["name"]))
    if any(type(cid) is not int or cid <= 0 for cid in categories):
        raise ValueError("SHADOW_INVALID_CATEGORY_ID")
    if not tree and not categories and origin == "OWN_PRODUCT":
        origin = "MISSING"
    if source_format == "keepa_response":
        # An absent capture time stays absent; never label the offline read as a
        # new provider fetch. Existing extractor needs a nonempty argument only.
        text = extract_keepa_product_text_safety_fact(
            product, candidate_asin=asin, fetched_at=captured or "UNKNOWN_NOT_RECORDED"
        )
    else:
        text = product_text_safety_fact_from_product_data(
            product, candidate_asin=asin, provider="keepa", fetched_at=captured
        )
    title, brand = product.get("title"), product.get("brand")
    title = "" if title is None else title
    brand = "" if brand is None else brand
    if not isinstance(title, str) or not isinstance(brand, str):
        raise ValueError("SHADOW_INVALID_IDENTITY_TEXT")
    update = product.get("lastUpdate")
    if update is not None and (type(update) is not int or update < 0):
        raise ValueError("SHADOW_INVALID_PROVIDER_TIMESTAMP")
    kind = product.get("type")
    kind = "" if kind is None else kind
    if not isinstance(kind, str):
        raise ValueError("SHADOW_INVALID_TYPE")
    return ProductFact(
        asin, title, brand, tuple(nodes), tuple(categories), domain, origin, text,
        evidence_ref, captured, update, kind,
        tuple((k, _strings(product.get(k))) for k in ("ingredients", "activeIngredients", "specialIngredients")),
        "NOT_CAPTURED" if "categories" not in product else "CAPTURED" if categories else "NOT_AVAILABLE",
    )


@dataclass(frozen=True)
class MatchedEvidence:
    field: str
    matched: str
    excerpt: str
    role: str
    evidence_source: str


@dataclass(frozen=True)
class FamilySignal:
    family: str
    classification: str
    bundle_candidate: bool
    matched_evidence: tuple[MatchedEvidence, ...]
    rule_version: str
    evaluator_version: str = EVALUATOR_VERSION


def _contains(value: str, term: str) -> bool:
    value, term = normalize_text(value), normalize_text(term)
    if re.fullmatch(r"[a-z0-9]+(?: [a-z0-9]+)*", term):
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", value) is not None
    return term in value


def _excerpt(value: str, term: str) -> str:
    normalized = normalize_text(value)
    start = max(0, normalized.find(normalize_text(term)) - 70)
    return normalized[start:start + 240]


def _clauses(value: str) -> tuple[str, ...]:
    # Keep decimal points intact. This is bounded phrase context, not a parser.
    return tuple(part for part in re.split(r"[\n;!?。]|\.(?=\s|$)|\s+but\s+", value, flags=re.I) if part.strip())


def _explicit_mixed_set(value: str, rule: FamilyRule) -> bool:
    if not any(_contains(value, marker) for marker in ("set", "セット")):
        return False
    parts = re.split(r"\s+(?:and|&|\+)\s+|と", normalize_text(value))
    if len(parts) < 2:
        return False
    body = any(any(_contains(part, term) for term in rule.body_terms)
               and not any(_contains(part, term) for term in rule.accessory_terms) for part in parts)
    accessory = any(any(_contains(part, term) for term in rule.accessory_terms) for part in parts)
    return body and accessory


def _non_product_context(value: str, rule: FamilyRule) -> bool:
    if any(_contains(value, term) for term in NON_PRODUCT_TERMS):
        return True
    normalized = normalize_text(value)
    for term in GUIDE_TERMS:
        if not _contains(value, term):
            continue
        prefix = normalized[:normalized.find(term)]
        # A physical product "with instruction guide" is not a guide product.
        before_with = re.split(r"\bwith\b", prefix)[0]
        physical_with_guide = _contains(prefix, "with") and any(
            _contains(before_with, body) for body in rule.body_terms)
        if not physical_with_guide:
            return True
    return False


def classify_product(fact: ProductFact, *, include_text: bool = True,
                     include_categories: bool = True) -> tuple[FamilySignal, ...]:
    """One evaluator for both families. Untargeted products emit no signal."""
    texts = [("title", fact.title)]
    if include_text:
        for field, internal in zip(TEXT_FIELDS, (
            "description", "features", "short_description", "safety_warning", "item_highlights"
        )):
            texts.extend((field, value) for value in getattr(fact.text, internal))
    result = []
    own_jp_categories = include_categories and fact.category_origin == "OWN_PRODUCT" and fact.domain_id == 5
    non_product_root = (fact.category_tree[0][0] if own_jp_categories and fact.category_tree else None)
    non_product_category = non_product_root in NON_PRODUCT_ROOT_IDS
    for rule in FAMILY_RULES:
        matches: list[MatchedEvidence] = []
        related = any(_contains(value, term) for _, value in texts for term in rule.related_terms)
        title_accessory = any(_contains(fact.title, term) for term in rule.accessory_terms)
        title_non_product = _non_product_context(fact.title, rule)
        clauses = [(field, part) for field, original in texts for part in _clauses(original)]
        for field, value in clauses:
            accessory = any(_contains(value, term) for term in rule.accessory_terms)
            explicit_bundle = _explicit_mixed_set(value, rule)
            bundle_phrase = any(_contains(value, term) for term in rule.bundle_terms)
            independent_body = any(_contains(value, term) for term in rule.body_terms) and not accessory
            non_supply = (independent_body or bundle_phrase or explicit_bundle) and any(
                _contains(value, term) for term in NON_SUPPLY_TERMS)
            absent = non_supply or any(_contains(value, term) for term in rule.absent_body_terms)
            reference = any(_contains(value, term) for term in REFERENCE_TERMS)
            non_product = non_product_category or title_non_product or _non_product_context(value, rule)
            for role, terms in (("ACCESSORY", rule.accessory_terms), ("BODY", rule.body_terms),
                                ("BUNDLE", rule.bundle_terms), ("BODY_ABSENT", rule.absent_body_terms)):
                for term in terms:
                    if not _contains(value, term):
                        continue
                    effective = role
                    if role == "ACCESSORY" and non_product:
                        effective = "ACCESSORY_MENTION"
                    if role == "BODY" and (accessory or absent or reference or non_product or
                                            (field != "title" and title_accessory)):
                        effective = "BODY_MENTION"
                    if role == "BUNDLE" and (absent or non_product):
                        effective = "BODY_MENTION"
                    elif role == "BUNDLE" and reference:
                        effective = "BUNDLE_REFERENCE"
                    if role == "BODY_ABSENT" and non_product:
                        effective = "BODY_MENTION"
                    matches.append(MatchedEvidence(field, term, _excerpt(value, term), effective, fact.evidence_ref))
            if non_supply and not non_product:
                for term in NON_SUPPLY_TERMS:
                    if _contains(value, term):
                        matches.append(MatchedEvidence(field, term, _excerpt(value, term), "BODY_ABSENT", fact.evidence_ref))
            if explicit_bundle and not absent and not non_product:
                marker = "set" if _contains(value, "set") else "セット"
                matches.append(MatchedEvidence(field, marker, _excerpt(value, marker),
                                               "BUNDLE_REFERENCE" if reference else "BUNDLE", fact.evidence_ref))
            for term in NON_PRODUCT_TERMS + GUIDE_TERMS:
                if _contains(value, term) and _non_product_context(value, rule):
                    matches.append(MatchedEvidence(field, term, _excerpt(value, term), "NON_PRODUCT_MENTION", fact.evidence_ref))
        if own_jp_categories:
            ids = [("categoryTree[-1]", fact.category_tree[-1][0])] if fact.category_tree else []
            ids.extend(("categories", cid) for cid in fact.categories)
            for field, cid in dict.fromkeys(ids):
                role = "BODY" if cid in rule.body_ids else "ACCESSORY" if cid in rule.accessory_ids else "FAMILY_ONLY" if cid in rule.related_ids else ""
                if role:
                    related = True
                    matches.append(MatchedEvidence(field, str(cid), str(cid), role,
                                                   f"{fact.evidence_ref};{rule.category_source}"))
            if non_product_category:
                matches.append(MatchedEvidence("categoryTree[0]", str(non_product_root), str(non_product_root),
                                               "NON_PRODUCT_CATEGORY", fact.evidence_ref))
        if not related:
            continue
        roles = {m.role for m in matches}
        title_roles = {m.role for m in matches if m.field == "title"}
        category_roles = {m.role for m in matches if m.field in {"categoryTree[-1]", "categories"}
                          and m.role in {"BODY", "ACCESSORY"}}
        bundle = "BUNDLE" in roles and "ACCESSORY" in roles
        contradictory = (
            ("BUNDLE_REFERENCE" in roles and "BODY_ABSENT" not in roles)
            or ("BODY_ABSENT" in roles and ("BODY" in category_roles or "BODY" in title_roles or "BUNDLE" in roles))
            or (non_product_category and bool(category_roles))
            or ("NON_PRODUCT_MENTION" in title_roles and bool(category_roles))
            or (not bundle and (category_roles == {"BODY", "ACCESSORY"}
                or ("BODY" in category_roles and "ACCESSORY" in title_roles)
                or ("ACCESSORY" in category_roles and "BODY" in title_roles)))
        )
        if contradictory:
            classification = "CONFLICT"
        elif bundle or "BODY" in title_roles or "BODY" in category_roles:
            classification = "BODY_CANDIDATE"
        elif "ACCESSORY" in roles:
            classification = "ACCESSORY_CANDIDATE"
        elif "BODY" in roles and "BODY_ABSENT" not in roles:
            classification = "BODY_CANDIDATE"
        else:
            classification = "UNKNOWN"
        result.append(FamilySignal(rule.family, classification, bundle, tuple(matches), rule.version))
    return tuple(result)
