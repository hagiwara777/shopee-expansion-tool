"""Pure Category Mapper parsing, recommendation, and export logic."""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from io import StringIO
import re
from typing import Any, Iterable, Mapping, Protocol, Sequence
import unicodedata

from modules.asin_resolver import RESOLVER_CSV_COLUMNS
from modules.category_mapper_store import CategoryMapperStore, normalize_brand
from modules.keepa_client import normalize_asin
from modules.prelisting_candidate_csv import (
    EXPANSION_SOURCE_TYPE,
    PRELISTING_CANDIDATE_COLUMNS,
    PrelistingCandidateCsvError,
    parse_prelisting_candidate_csv,
)
from modules.prelisting_gate_csv import PRELISTING_GATE_RESULT_COLUMNS
from modules.shopee_catalog_client import BrandPage, ShopeeCatalogError, ShopeeRateLimitError


PH_MARKETPLACE = "PH"
GATE_ELIGIBLE = "GATE_ELIGIBLE"
RAW_EXPANSION = "RAW_EXPANSION"
CONDITIONER = "CONDITIONER"
SHAMPOO_CONDITIONER_SET = "SHAMPOO_CONDITIONER_SET"
UNMAPPED = "UNMAPPED"
SUGGESTED = "SUGGESTED"
CONFIRMED = "CONFIRMED"
LISTING_TOOL_ACCEPTED = "LISTING_TOOL_ACCEPTED"
USER_CONFIRMED = "USER_CONFIRMED"
API_CATEGORY_PRESENT = "API_CATEGORY_PRESENT"
ATTRIBUTES_CONFIRMED = "ATTRIBUTES_CONFIRMED"
BRAND_LIST_CONFIRMED = "BRAND_LIST_CONFIRMED"
UNKNOWN = "UNKNOWN"

RECOMMENDATION_COLUMNS = (
    "marketplace",
    "source_type",
    "source_asin",
    "candidate_asin",
    "product_title",
    "keepa_brand",
    "keepa_category",
    "resolver_input_title",
    "input_safety_state",
    "listing_ready",
    "canonical_product_type",
    "category_recommendation_status",
    "recommended_category_id",
    "recommended_category_path",
    "category_confidence",
    "category_recommendation_source",
    "category_verification_status",
    "mandatory_attribute_count",
    "no_brand_available",
    "canonical_brand_candidate",
    "brand_match_status",
    "recommended_brand_id",
    "recommended_brand_name",
    "brand_confidence",
    "brand_recommendation_source",
    "brand_accuracy_warning",
    "group_key",
    "manual_review_required",
    "manual_review_reason",
)
GROUP_COLUMNS = (
    "marketplace",
    "group_key",
    "category_id",
    "category_path",
    "brand_id",
    "brand_name",
    "mandatory_attribute_count",
    "verification_status",
    "listing_ready",
    "asin_count",
    "asin",
)
_SHAMPOO_EXCLUSIONS = (
    "収納ケース",
    "case for",
    "cover for",
    "holder for",
    "replacement part",
    "accessory",
    "対応収納",
    "用ケース",
    "空ボトル",
    "ディスペンサー単体",
)
_SET_MARKERS = (
    "シャンプー・コンディショナーセット",
    "シャンプー&コンディショナー",
    "シャンプー＆コンディショナー",
    "シャンプーとコンディショナー",
    "シャンプー コンディショナー セット",
    "シャンプーコンディショナーセット",
    "2点セット",
    "トライアルセット",
    "shampoo and conditioner",
    "shampoo & conditioner",
    "shampoo conditioner set",
    "hair care set",
)
_SET_WORDS = ("bundle", "kit", "set")
_ASCII_WORD = re.compile(r"(?<![a-z0-9]){word}(?![a-z0-9])", re.IGNORECASE)
_CONDITIONER_KEEPA_CATEGORY = "リンス・コンディショナー"
_CONDITIONER_CATEGORY_NAME = "Hair and Scalp Conditioner"
_CONDITIONER_CATEGORY_PATH_PREFIX = "Beauty > Hair Care >"


class CategoryMapperInputError(RuntimeError):
    """Raised when input cannot safely be treated as Mapper source data."""


@dataclass(frozen=True)
class CategoryMapperInputRow:
    source_asin: str
    candidate_asin: str
    product_title: str
    keepa_brand: str
    keepa_category: str
    source_type: str
    input_safety_state: str
    input_title: str = ""


@dataclass(frozen=True)
class CategoryMapperInput:
    marketplace: str
    source_type: str
    input_safety_state: str
    rows: tuple[CategoryMapperInputRow, ...]


@dataclass(frozen=True)
class AttributeFlattenResult:
    attributes: tuple[dict[str, Any], ...]
    group_node_count: int
    skipped_node_count: int
    depth_limited: bool


@dataclass(frozen=True)
class MapperRecommendation:
    marketplace: str
    source_type: str
    source_asin: str
    candidate_asin: str
    product_title: str
    keepa_brand: str
    keepa_category: str
    resolver_input_title: str
    input_safety_state: str
    canonical_product_type: str
    category_recommendation_status: str
    recommended_category_id: int | None
    recommended_category_path: str
    category_confidence: str
    category_recommendation_source: str
    category_verification_status: str
    mandatory_attribute_count: int | None
    no_brand_available: bool
    canonical_brand_candidate: str
    brand_match_status: str
    recommended_brand_id: int | None
    recommended_brand_name: str
    brand_confidence: str
    brand_recommendation_source: str
    brand_accuracy_warning: str
    category_is_confirmed: bool
    brand_is_confirmed: bool
    no_brand_selected_by_user: bool
    manual_review_required: bool
    manual_review_reason: str

    @property
    def listing_ready(self) -> bool:
        return (
            self.input_safety_state == GATE_ELIGIBLE
            and self.category_is_confirmed
            and (self.brand_is_confirmed or self.no_brand_selected_by_user)
            and not self.manual_review_required
        )

    @property
    def group_key(self) -> str:
        if not self.listing_ready or self.recommended_category_id is None:
            return ""
        brand_id = self.recommended_brand_id
        if brand_id is None:
            return ""
        return f"{self.marketplace}|{self.recommended_category_id}|{brand_id}"


@dataclass(frozen=True)
class MapperExportBundle:
    recommendations_csv: bytes
    groups_csv: bytes
    listing_tool_text: str


class BrandCatalogClient(Protocol):
    def get_brand_list(
        self,
        marketplace: str,
        category_id: int,
        *,
        offset: int = 0,
        page_size: int = 100,
    ) -> BrandPage: ...


def parse_category_mapper_input(content: bytes, *, filename: str) -> CategoryMapperInput:
    """Accept only raw Expansion or all-ELIGIBLE PH Gate CSV contracts."""

    header = _csv_header(content, filename)
    if header == list(PRELISTING_CANDIDATE_COLUMNS):
        return _parse_expansion_input(content, filename)
    if header == list(PRELISTING_GATE_RESULT_COLUMNS):
        return _parse_gate_eligible_input(content, filename)
    raise CategoryMapperInputError(
        "Category Mapper input must be an Expansion candidate or PH Gate eligible CSV."
    )


def parse_resolver_title_csv(content: bytes, *, filename: str) -> dict[str, str]:
    """Read Resolver output only as optional title evidence, never product authority."""

    rows = _csv_dict_rows(content, filename, expected_header=RESOLVER_CSV_COLUMNS)
    titles: dict[str, str] = {}
    for row in rows:
        asin_value = _text(row.get("asin"))
        if not asin_value:
            continue
        try:
            asin = normalize_asin(asin_value)
        except ValueError:
            continue
        title = _text(row.get("input_title"))
        if title and asin not in titles:
            titles[asin] = title
    return titles


def build_recommendations(
    source: CategoryMapperInput,
    *,
    resolver_titles: Mapping[str, str] | None,
    store: CategoryMapperStore,
) -> tuple[MapperRecommendation, ...]:
    """Build conservative recommendations from local data only; no API call occurs."""

    _require_ph(source.marketplace)
    resolver_titles = resolver_titles or {}
    recommendations = []
    for row in source.rows:
        resolver_title = _text(resolver_titles.get(row.candidate_asin) or row.input_title)
        product_type = classify_product_type(
            keepa_category=row.keepa_category,
            product_title=row.product_title,
            resolver_input_title=resolver_title,
        )
        category = _recommend_category(
            row,
            resolver_title=resolver_title,
            canonical_product_type=product_type,
            store=store,
        )
        brands = (
            store.list_brands(source.marketplace, category["category_id"])
            if category["category_id"] is not None
            else []
        )
        brand = recommend_brand(
            marketplace=source.marketplace,
            category_id=category["category_id"],
            keepa_brand=row.keepa_brand,
            resolver_input_title=resolver_title,
            brands=brands,
            confirmed_brand_policy=(
                None
                if category["category_id"] is None
                else store.find_confirmed_brand_policy(
                    source.marketplace,
                    row.keepa_category,
                    row.keepa_brand,
                    category["category_id"],
                )
            ),
            confirmed_alias=(
                None
                if category["category_id"] is None
                else store.find_confirmed_brand_alias(
                    source.marketplace, category["category_id"], row.keepa_brand
                )
            ),
        )
        brand["no_brand_available"] = bool(brand.get("no_brand_available")) or any(
            bool(candidate.get("is_no_brand")) for candidate in brands
        )
        recommendations.append(
            _build_recommendation(
                row,
                resolver_title=resolver_title,
                canonical_product_type=product_type,
                category=category,
                brand=brand,
            )
        )
    return tuple(recommendations)


def classify_product_type(
    *,
    keepa_category: str,
    product_title: str,
    resolver_input_title: str,
) -> str:
    """Return only a high-confidence canonical type; unknown stays unmapped."""

    category = _normalize_type(keepa_category)
    combined = _normalize_type(" ".join((product_title, resolver_input_title)))
    all_text = f"{category} {combined}"
    if any(exclusion.casefold() in combined for exclusion in _SHAMPOO_EXCLUSIONS):
        return ""
    if _is_shampoo_conditioner_set(all_text):
        return SHAMPOO_CONDITIONER_SET
    if category == _normalize_type(_CONDITIONER_KEEPA_CATEGORY):
        return CONDITIONER
    if category == "シャンプー":
        return "SHAMPOO"
    if "シャンプー" in combined or _contains_ascii_word(combined, "shampoo"):
        return "SHAMPOO"
    return ""


def recommend_brand(
    *,
    marketplace: str,
    category_id: int | None,
    keepa_brand: str,
    resolver_input_title: str,
    brands: Sequence[Mapping[str, Any]],
    confirmed_brand_policy: Mapping[str, Any] | None = None,
    confirmed_alias: Mapping[str, Any] | None = None,
    manufacturer_name: str = "",
) -> dict[str, Any]:
    """Recommend a brand only when an explicit match rule supports it."""

    _require_ph(marketplace)
    actual_brand = _text(keepa_brand)
    no_brand = next((brand for brand in brands if bool(brand.get("is_no_brand"))), None)
    real_brands = [brand for brand in brands if not bool(brand.get("is_no_brand"))]
    if confirmed_alias is not None and (_nonnegative_int(confirmed_alias.get("brand_id")) or -1) > 0:
        return _brand_result(
            confirmed_alias,
            status="CONFIRMED_ALIAS_MATCH",
            confidence="HIGH",
            source="CONFIRMED_BRAND_ALIAS",
            canonical_brand=_text(confirmed_alias.get("canonical_brand")) or actual_brand,
            confirmed=True,
            no_brand_available=no_brand is not None,
            no_brand_selected_by_user=False,
        )
    if (
        confirmed_brand_policy is not None
        and _text(confirmed_brand_policy.get("brand_policy")).upper() == "NO_BRAND_SELECTED"
        and _nonnegative_int(confirmed_brand_policy.get("brand_id")) == 0
    ):
        return _brand_result(
            no_brand or {"brand_id": 0, "brand_name": "No brand", "is_no_brand": True},
            status="NO_BRAND_SELECTED",
            confidence="HIGH",
            source="CONFIRMED_NO_BRAND_POLICY",
            canonical_brand=actual_brand,
            confirmed=False,
            no_brand_available=True,
            no_brand_selected_by_user=True,
        )
    if actual_brand and actual_brand.isascii():
        exact = [brand for brand in real_brands if _text(brand.get("brand_name")) == actual_brand]
        if len(exact) == 1:
            return _brand_result(
                exact[0],
                status="EXACT_MATCH",
                confidence="HIGH",
                source="ASCII_EXACT_KEEPA_BRAND",
                canonical_brand=actual_brand,
            )
    normalized_actual = normalize_brand(actual_brand)
    if normalized_actual:
        normalized = [
            brand
            for brand in real_brands
            if normalize_brand(brand.get("brand_name")) == normalized_actual
        ]
        if len(normalized) == 1:
            return _brand_result(
                normalized[0],
                status="NORMALIZED_MATCH",
                confidence="MEDIUM",
                source="NORMALIZED_KEEPA_BRAND",
                canonical_brand=actual_brand,
            )
        if len(normalized) > 1:
            return _multiple_brand_result(actual_brand)
    title_matches = [
        brand
        for brand in real_brands
        if _title_contains_brand(resolver_input_title, _text(brand.get("brand_name")))
    ]
    if len(title_matches) == 1:
        return _brand_result(
            title_matches[0],
            status="RESOLVER_TITLE_EXACT_MATCH",
            confidence="MEDIUM",
            source="RESOLVER_TITLE_EXACT",
            canonical_brand=actual_brand,
        )
    if len(title_matches) > 1:
        return _multiple_brand_result(actual_brand)
    if manufacturer_name and normalize_brand(manufacturer_name) != normalized_actual:
        manufacturer_matches = [
            brand
            for brand in real_brands
            if normalize_brand(brand.get("brand_name")) == normalize_brand(manufacturer_name)
        ]
        if manufacturer_matches:
            return {
                **_unresolved_brand_result(actual_brand, no_brand),
                "status": "MANUFACTURER_ONLY",
                "warning": "Manufacturer name was not treated as the product brand.",
            }
    return _unresolved_brand_result(actual_brand, no_brand)


def flatten_attribute_tree(root: Any, *, max_depth: int = 40) -> AttributeFlattenResult:
    """Flatten arbitrary attribute trees without recursion loops or null failures."""

    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")
    merged: dict[str, dict[str, Any]] = {}
    visited: set[int] = set()
    group_nodes = 0
    skipped_nodes = 0
    depth_limited = False

    def visit(node: Any, depth: int) -> None:
        nonlocal group_nodes, skipped_nodes, depth_limited
        if depth > max_depth:
            depth_limited = True
            return
        if isinstance(node, (list, tuple)):
            for child in node:
                visit(child, depth)
            return
        if not isinstance(node, Mapping):
            skipped_nodes += 1
            return
        identity = id(node)
        if identity in visited:
            return
        visited.add(identity)
        attribute_id = _text(node.get("attribute_id"))
        if attribute_id:
            candidate = {
                "attribute_id": attribute_id,
                "attribute_name": _first_text(
                    node, "display_attribute_name", "original_attribute_name", "attribute_name", "name"
                ),
                "is_mandatory": bool(node.get("is_mandatory", node.get("mandatory"))),
                "input_type": _first_text(node, "input_type"),
                "validation_type": _first_text(node, "validation_type"),
                "value_count": _list_count(node, "attribute_value_list", "values", "value_list"),
                "unit_count": _list_count(node, "unit_list", "units"),
                "multi_select_max": _int_or_zero(
                    node.get("max_input_value_number")
                    or node.get("max_selected_count")
                    or node.get("max_value_count")
                ),
            }
            if attribute_id in merged:
                merged[attribute_id] = _merge_attribute(merged[attribute_id], candidate)
            else:
                merged[attribute_id] = candidate
        else:
            group_nodes += 1
        children = node.get("children", [])
        if children is None:
            children = []
        if isinstance(children, (list, tuple)):
            for child in children:
                visit(child, depth + 1)
        elif children:
            skipped_nodes += 1

    visit(root, 0)
    return AttributeFlattenResult(
        attributes=tuple(sorted(merged.values(), key=lambda item: item["attribute_id"])),
        group_node_count=group_nodes,
        skipped_node_count=skipped_nodes,
        depth_limited=depth_limited,
    )


def sync_brand_pages(
    *,
    store: CategoryMapperStore,
    client: BrandCatalogClient,
    marketplace: str,
    category_id: int,
    matching_terms: Iterable[str],
    max_pages: int = 10,
) -> dict[str, Any]:
    """Fetch at most ten lazy brand pages, retaining cache on any non-429 error."""

    _require_ph(marketplace)
    if not 1 <= max_pages <= 10:
        raise ValueError("max_pages must be between 1 and 10")
    current_brands = store.list_brands(marketplace, category_id)
    terms = tuple(term for term in (_text(term) for term in matching_terms) if term)
    if _cached_brand_match_exists(current_brands, terms):
        return {"api_pages": 0, "used_cache": True, "failed": False, "brands": current_brands}
    state = store.brand_sync_state(marketplace, category_id)
    if state["is_complete"]:
        return {"api_pages": 0, "used_cache": bool(current_brands), "failed": False, "brands": current_brands}
    offset = state["next_offset"]
    pages = 0
    try:
        while pages < max_pages:
            page = client.get_brand_list(
                marketplace,
                category_id,
                offset=offset,
                page_size=100,
            )
            store.save_brand_page(
                marketplace,
                category_id,
                page.brands,
                next_offset=page.next_offset,
                is_complete=page.is_complete,
            )
            pages += 1
            current_brands = store.list_brands(marketplace, category_id)
            if _cached_brand_match_exists(current_brands, terms) or page.is_complete:
                break
            offset = page.next_offset
    except ShopeeRateLimitError:
        store.record_brand_sync_failure(marketplace, category_id)
        raise
    except ShopeeCatalogError:
        store.record_brand_sync_failure(marketplace, category_id)
        return {
            "api_pages": pages,
            "used_cache": bool(current_brands),
            "failed": True,
            "brands": current_brands,
        }
    return {
        "api_pages": pages,
        "used_cache": pages == 0 and bool(current_brands),
        "failed": False,
        "brands": current_brands,
    }


def apply_manual_category(
    recommendation: MapperRecommendation,
    *,
    category: Mapping[str, Any],
    mandatory_attribute_count: int | None,
    no_brand_available: bool,
) -> MapperRecommendation:
    """Apply a user-confirmed Category selected from the local catalog."""

    category_id = _positive_int(category.get("category_id"))
    if category_id is None:
        raise ValueError("A catalog Category ID is required.")
    updated = replace(
        recommendation,
        category_recommendation_status=CONFIRMED,
        recommended_category_id=category_id,
        recommended_category_path=_text(category.get("category_path")),
        category_confidence="HIGH",
        category_recommendation_source="USER_CONFIRMED",
        category_verification_status=USER_CONFIRMED,
        mandatory_attribute_count=mandatory_attribute_count,
        no_brand_available=no_brand_available,
        category_is_confirmed=True,
        canonical_brand_candidate="",
        brand_match_status="NO_BRAND_AVAILABLE" if no_brand_available else "NOT_FOUND",
        recommended_brand_id=None,
        recommended_brand_name="No brand" if no_brand_available else "",
        brand_confidence="NONE",
        brand_recommendation_source=(
            "API_CONFIRMED_NO_BRAND" if no_brand_available else "BRAND_UNRESOLVED"
        ),
        brand_accuracy_warning=(
            "No brand is available but must be selected explicitly by the user."
            if no_brand_available
            else "No verified Shopee brand match was found."
        ),
        brand_is_confirmed=False,
        no_brand_selected_by_user=False,
    )
    return _with_manual_review_state(updated)


def apply_manual_brand(
    recommendation: MapperRecommendation,
    *,
    brand: Mapping[str, Any],
) -> MapperRecommendation:
    """Apply an explicit user brand choice, including a catalog-confirmed No brand."""

    brand_id = _nonnegative_int(brand.get("brand_id"))
    if brand_id is None:
        raise ValueError("A catalog Brand ID is required.")
    is_no_brand = bool(brand.get("is_no_brand"))
    if is_no_brand:
        updated = replace(
            recommendation,
            no_brand_available=True,
            brand_match_status="NO_BRAND_SELECTED",
            recommended_brand_id=brand_id,
            recommended_brand_name=_text(brand.get("brand_name")) or "No brand",
            brand_confidence="HIGH",
            brand_recommendation_source="USER_NO_BRAND_SELECTION",
            brand_accuracy_warning=(
                "Actual Keepa brand is retained; No brand was explicitly selected by the user."
                if recommendation.keepa_brand
                else ""
            ),
            brand_is_confirmed=False,
            no_brand_selected_by_user=True,
        )
    else:
        updated = replace(
            recommendation,
            brand_match_status="MANUAL_REVIEW",
            recommended_brand_id=brand_id,
            recommended_brand_name=_text(brand.get("brand_name")),
            brand_confidence="HIGH",
            brand_recommendation_source="USER_CONFIRMED",
            brand_accuracy_warning="",
            brand_is_confirmed=True,
            no_brand_selected_by_user=False,
        )
    return _with_manual_review_state(updated)


def build_mapper_exports(recommendations: Iterable[MapperRecommendation]) -> MapperExportBundle:
    """Serialize detailed audit data, ready-only groups, and paste-ready text."""

    ordered = tuple(recommendations)
    recommendation_rows = [_recommendation_row(item) for item in ordered]
    ready = [item for item in ordered if item.listing_ready]
    grouped: dict[str, list[MapperRecommendation]] = {}
    for item in ready:
        grouped.setdefault(item.group_key, []).append(item)
    group_rows: list[dict[str, Any]] = []
    text_blocks: list[str] = []
    for group_key, items in grouped.items():
        first = items[0]
        verification_status = (
            first.category_verification_status
            if first.category_verification_status == USER_CONFIRMED
            else LISTING_TOOL_ACCEPTED
        )
        for item in items:
            group_rows.append(
                {
                    "marketplace": item.marketplace,
                    "group_key": group_key,
                    "category_id": item.recommended_category_id,
                    "category_path": item.recommended_category_path,
                    "brand_id": item.recommended_brand_id,
                    "brand_name": item.recommended_brand_name,
                    "mandatory_attribute_count": item.mandatory_attribute_count,
                    "verification_status": verification_status,
                    "listing_ready": "TRUE",
                    "asin_count": len(items),
                    "asin": item.candidate_asin,
                }
            )
        header = (
            f"［{first.marketplace} / {first.recommended_category_path} / "
            f"{first.recommended_brand_name}］"
        )
        lines = [
            header,
            f"Category ID: {first.recommended_category_id}",
            f"Brand ID: {first.recommended_brand_id}",
            f"Mandatory attributes: {first.mandatory_attribute_count or 0}",
            f"ASIN count: {len(items)}",
            "",
            *(item.candidate_asin for item in items),
        ]
        text_blocks.append("\n".join(lines))
    return MapperExportBundle(
        recommendations_csv=_rows_to_csv(RECOMMENDATION_COLUMNS, recommendation_rows),
        groups_csv=_rows_to_csv(GROUP_COLUMNS, group_rows),
        listing_tool_text="\n\n".join(text_blocks),
    )


def summarize_output_blockers(
    recommendations: Iterable[MapperRecommendation],
) -> dict[str, tuple[MapperRecommendation, ...]]:
    """Return overlapping readiness blockers without weakening export requirements."""

    ordered = tuple(recommendations)
    return {
        "category_unconfirmed": tuple(item for item in ordered if not item.category_is_confirmed),
        "brand_unconfirmed": tuple(
            item
            for item in ordered
            if not item.brand_is_confirmed and not item.no_brand_selected_by_user
        ),
        "manual_review_required": tuple(item for item in ordered if item.manual_review_required),
        "ready": tuple(item for item in ordered if item.listing_ready),
    }


def group_recommendations(
    recommendations: Iterable[MapperRecommendation],
) -> tuple[dict[str, Any], ...]:
    """Summarize UI rows by normalized source Category/Brand/recommendation."""

    grouped: dict[tuple[str, str, str, str], list[MapperRecommendation]] = {}
    for recommendation in recommendations:
        key = (
            recommendation.marketplace,
            normalize_brand(recommendation.keepa_category),
            normalize_brand(recommendation.keepa_brand),
            recommendation.canonical_product_type,
        )
        grouped.setdefault(key, []).append(recommendation)
    summaries = []
    for items in grouped.values():
        first = items[0]
        summaries.append(
            {
                "member_asins": tuple(item.candidate_asin for item in items),
                "asin_count": len(items),
                "keepa_category": first.keepa_category,
                "keepa_brand": first.keepa_brand,
                "canonical_product_type": first.canonical_product_type,
                "category_id": _single_value(item.recommended_category_id for item in items),
                "category_path": _single_value(item.recommended_category_path for item in items) or "",
                "category_status": _single_value(
                    item.category_recommendation_status for item in items
                )
                or "MIXED",
                "brand_status": _single_value(item.brand_match_status for item in items)
                or "MIXED",
                "listing_ready_count": sum(item.listing_ready for item in items),
            }
        )
    return tuple(summaries)


def _parse_expansion_input(content: bytes, filename: str) -> CategoryMapperInput:
    try:
        parsed = parse_prelisting_candidate_csv(content, filename=filename)
    except PrelistingCandidateCsvError as exc:
        raise CategoryMapperInputError("Expansion CSV could not be validated.") from exc
    if parsed.source_type != EXPANSION_SOURCE_TYPE:
        raise CategoryMapperInputError("Only Expansion candidate CSV is accepted in this input mode.")
    rows = tuple(
        CategoryMapperInputRow(
            source_asin=row.source_asin,
            candidate_asin=row.candidate_asin,
            product_title=row.product_title,
            keepa_brand=row.brand,
            keepa_category=row.category,
            source_type=row.source_type,
            input_safety_state=RAW_EXPANSION,
            input_title=row.input_title,
        )
        for row in parsed.rows
    )
    _validate_mapper_rows(rows)
    return CategoryMapperInput(
        marketplace=PH_MARKETPLACE,
        source_type=EXPANSION_SOURCE_TYPE,
        input_safety_state=RAW_EXPANSION,
        rows=rows,
    )


def _parse_gate_eligible_input(content: bytes, filename: str) -> CategoryMapperInput:
    rows = _csv_dict_rows(content, filename, expected_header=PRELISTING_GATE_RESULT_COLUMNS)
    if not rows:
        raise CategoryMapperInputError("Eligible Gate CSV contains no rows.")
    source_types = {_text(row.get("source_type")).upper() for row in rows}
    if not source_types <= {"EXPANSION", "RESOLVER"} or len(source_types) != 1:
        raise CategoryMapperInputError("Eligible Gate CSV source type is invalid.")
    mapped_rows: list[CategoryMapperInputRow] = []
    for row in rows:
        if _text(row.get("marketplace")).upper() != PH_MARKETPLACE:
            raise CategoryMapperInputError("Category Mapper supports PH Gate eligible CSV only.")
        if _text(row.get("final_eligibility")).upper() != "ELIGIBLE":
            raise CategoryMapperInputError("Gate audit, REVIEW, and EXCLUDE CSV are not accepted.")
        mapped_rows.append(
            CategoryMapperInputRow(
                source_asin=_text(row.get("source_asin")),
                candidate_asin=_text(row.get("candidate_asin")),
                product_title=_text(row.get("product_title")),
                keepa_brand=_text(row.get("brand")),
                keepa_category=_text(row.get("category")),
                source_type=next(iter(source_types)),
                input_safety_state=GATE_ELIGIBLE,
                input_title=_text(row.get("input_title")),
            )
        )
    _validate_mapper_rows(mapped_rows)
    source_type = next(iter(source_types))
    return CategoryMapperInput(
        marketplace=PH_MARKETPLACE,
        source_type=source_type,
        input_safety_state=GATE_ELIGIBLE,
        rows=tuple(mapped_rows),
    )


def _recommend_category(
    row: CategoryMapperInputRow,
    *,
    resolver_title: str,
    canonical_product_type: str,
    store: CategoryMapperStore,
) -> dict[str, Any]:
    marketplace = PH_MARKETPLACE
    if canonical_product_type:
        profile = store.find_listing_profile(marketplace, canonical_product_type)
        if profile and profile["verification_status"] == LISTING_TOOL_ACCEPTED:
            return _category_result(
                category_id=int(profile["category_id"]),
                category_path=_text(profile["category_path"]),
                status=CONFIRMED,
                confidence="HIGH",
                source="LISTING_TOOL_ACCEPTED_PROFILE",
                verification=LISTING_TOOL_ACCEPTED,
                mandatory_attribute_count=int(profile["mandatory_attribute_count"]),
                confirmed=True,
            )
    mapping = store.find_confirmed_category_mapping(
        marketplace,
        "KEEPA_CATEGORY",
        row.keepa_category,
    )
    if mapping is not None:
        mapped_category = store.get_category(marketplace, int(mapping["category_id"]))
        if mapped_category is not None:
            category_id = int(mapped_category["category_id"])
            return _category_result(
                category_id=category_id,
                category_path=_text(mapped_category["category_path"]),
                status=CONFIRMED,
                confidence="HIGH",
                source="USER_CONFIRMED_MAPPING",
                verification=USER_CONFIRMED,
                mandatory_attribute_count=store.mandatory_attribute_count(marketplace, category_id),
                confirmed=True,
            )
    if canonical_product_type == CONDITIONER:
        candidates = _find_conditioner_leaf_candidates(store, marketplace)
        if len(candidates) == 1:
            candidate = candidates[0]
            category_id = int(candidate["category_id"])
            return _category_result(
                category_id=category_id,
                category_path=_text(candidate["category_path"]),
                status=SUGGESTED,
                confidence="MEDIUM",
                source="PH_CATEGORY_TREE_CONDITIONER_LEAF",
                verification=API_CATEGORY_PRESENT,
                mandatory_attribute_count=store.mandatory_attribute_count(marketplace, category_id),
                confirmed=False,
            )
        return _category_result(
            category_id=None,
            category_path="",
            status=UNMAPPED,
            confidence="NONE",
            source="CONDITIONER_CANDIDATE_UNAVAILABLE",
            verification=UNKNOWN,
            mandatory_attribute_count=None,
            confirmed=False,
        )
    if canonical_product_type == SHAMPOO_CONDITIONER_SET:
        return _category_result(
            category_id=None,
            category_path="",
            status=UNMAPPED,
            confidence="NONE",
            source="SHAMPOO_CONDITIONER_SET_REQUIRES_USER_CONFIRMATION",
            verification=UNKNOWN,
            mandatory_attribute_count=None,
            confirmed=False,
        )
    matches = _find_leaf_title_matches(store, marketplace, resolver_title)
    if len(matches) == 1:
        matched = matches[0]
        category_id = int(matched["category_id"])
        return _category_result(
            category_id=category_id,
            category_path=_text(matched["category_path"]),
            status=SUGGESTED,
            confidence="MEDIUM",
            source="RESOLVER_TITLE_LEAF_EXACT",
            verification=API_CATEGORY_PRESENT,
            mandatory_attribute_count=store.mandatory_attribute_count(marketplace, category_id),
            confirmed=False,
        )
    return _category_result(
        category_id=None,
        category_path="",
        status=UNMAPPED,
        confidence="NONE",
        source="UNMAPPED",
        verification=UNKNOWN,
        mandatory_attribute_count=None,
        confirmed=False,
    )


def _find_leaf_title_matches(
    store: CategoryMapperStore, marketplace: str, resolver_title: str
) -> list[dict[str, Any]]:
    words = re.findall(r"[A-Za-z0-9]+|[^\sA-Za-z0-9]+", resolver_title)
    candidates: dict[int, dict[str, Any]] = {}
    for word in words:
        if len(word.strip()) < 3:
            continue
        for category in store.search_categories(
            marketplace,
            query=word,
            leaf_only=True,
            limit=100,
        ):
            name = _text(category.get("category_name"))
            if name and _title_contains_brand(resolver_title, name):
                candidates[int(category["category_id"])] = category
    return list(candidates.values())


def _find_conditioner_leaf_candidates(
    store: CategoryMapperStore, marketplace: str
) -> list[dict[str, Any]]:
    """Find only the exact PH Hair Care conditioner leaf from the local tree."""

    candidates = []
    for category in store.search_categories(
        marketplace,
        query="conditioner",
        leaf_only=True,
        limit=100,
    ):
        if bool(category.get("is_others")):
            continue
        if _normalize_type(_text(category.get("category_name"))) != _normalize_type(
            _CONDITIONER_CATEGORY_NAME
        ):
            continue
        category_path = _text(category.get("category_path"))
        if not category_path.casefold().startswith(_CONDITIONER_CATEGORY_PATH_PREFIX.casefold()):
            continue
        candidates.append(category)
    return candidates


def _category_result(
    *,
    category_id: int | None,
    category_path: str,
    status: str,
    confidence: str,
    source: str,
    verification: str,
    mandatory_attribute_count: int | None,
    confirmed: bool,
) -> dict[str, Any]:
    return {
        "category_id": category_id,
        "category_path": category_path,
        "status": status,
        "confidence": confidence,
        "source": source,
        "verification": verification,
        "mandatory_attribute_count": mandatory_attribute_count,
        "confirmed": confirmed,
    }


def _build_recommendation(
    row: CategoryMapperInputRow,
    *,
    resolver_title: str,
    canonical_product_type: str,
    category: Mapping[str, Any],
    brand: Mapping[str, Any],
) -> MapperRecommendation:
    no_brand_available = bool(brand.get("no_brand_available"))
    initial = MapperRecommendation(
        marketplace=PH_MARKETPLACE,
        source_type=row.source_type,
        source_asin=row.source_asin,
        candidate_asin=row.candidate_asin,
        product_title=row.product_title,
        keepa_brand=row.keepa_brand,
        keepa_category=row.keepa_category,
        resolver_input_title=resolver_title,
        input_safety_state=row.input_safety_state,
        canonical_product_type=canonical_product_type,
        category_recommendation_status=_text(category["status"]),
        recommended_category_id=category["category_id"],
        recommended_category_path=_text(category["category_path"]),
        category_confidence=_text(category["confidence"]),
        category_recommendation_source=_text(category["source"]),
        category_verification_status=_text(category["verification"]),
        mandatory_attribute_count=category["mandatory_attribute_count"],
        no_brand_available=no_brand_available,
        canonical_brand_candidate=_text(brand.get("canonical_brand")),
        brand_match_status=_text(brand.get("status")),
        recommended_brand_id=brand.get("brand_id"),
        recommended_brand_name=_text(brand.get("brand_name")),
        brand_confidence=_text(brand.get("confidence")),
        brand_recommendation_source=_text(brand.get("source")),
        brand_accuracy_warning=_text(brand.get("warning")),
        category_is_confirmed=bool(category["confirmed"]),
        brand_is_confirmed=bool(brand.get("confirmed")),
        no_brand_selected_by_user=bool(brand.get("no_brand_selected_by_user")),
        manual_review_required=False,
        manual_review_reason="",
    )
    return _with_manual_review_state(initial)


def _with_manual_review_state(recommendation: MapperRecommendation) -> MapperRecommendation:
    reasons = []
    if not recommendation.category_is_confirmed:
        reasons.append("Category requires user confirmation.")
    if not recommendation.brand_is_confirmed and not recommendation.no_brand_selected_by_user:
        if recommendation.no_brand_available:
            reasons.append("Select a real brand or explicitly select No brand.")
        else:
            reasons.append("Brand requires user confirmation.")
    return replace(
        recommendation,
        manual_review_required=bool(reasons),
        manual_review_reason=" ".join(reasons),
    )


def _brand_result(
    brand: Mapping[str, Any],
    *,
    status: str,
    confidence: str,
    source: str,
    canonical_brand: str,
    confirmed: bool = False,
    no_brand_available: bool | None = None,
    no_brand_selected_by_user: bool = False,
) -> dict[str, Any]:
    is_no_brand = bool(brand.get("is_no_brand")) or _nonnegative_int(brand.get("brand_id")) == 0
    return {
        "status": status,
        "brand_id": _nonnegative_int(brand.get("brand_id")),
        "brand_name": _text(brand.get("shopee_brand_name") or brand.get("brand_name")),
        "confidence": confidence,
        "source": source,
        "canonical_brand": canonical_brand,
        "warning": "" if confirmed else "Brand recommendation requires user confirmation.",
        "confirmed": confirmed,
        "no_brand_available": is_no_brand if no_brand_available is None else no_brand_available,
        "no_brand_selected_by_user": no_brand_selected_by_user,
    }


def _multiple_brand_result(actual_brand: str) -> dict[str, Any]:
    return {
        "status": "MULTIPLE_MATCHES",
        "brand_id": None,
        "brand_name": "",
        "confidence": "NONE",
        "source": "MULTIPLE_BRAND_CANDIDATES",
        "canonical_brand": actual_brand,
        "warning": "Multiple Shopee brand candidates require user selection.",
        "confirmed": False,
        "no_brand_available": False,
    }


def _unresolved_brand_result(
    actual_brand: str, no_brand: Mapping[str, Any] | None
) -> dict[str, Any]:
    if no_brand is not None:
        return {
            "status": "NO_BRAND_AVAILABLE",
            "brand_id": None,
            "brand_name": _text(no_brand.get("brand_name")) or "No brand",
            "confidence": "NONE",
            "source": "API_CONFIRMED_NO_BRAND",
            "canonical_brand": actual_brand,
            "warning": "No brand is available but must be selected explicitly by the user.",
            "confirmed": False,
            "no_brand_available": True,
        }
    return {
        "status": "NOT_FOUND",
        "brand_id": None,
        "brand_name": "",
        "confidence": "NONE",
        "source": "BRAND_UNRESOLVED",
        "canonical_brand": actual_brand,
        "warning": "No verified Shopee brand match was found.",
        "confirmed": False,
        "no_brand_available": False,
    }


def _cached_brand_match_exists(brands: Sequence[Mapping[str, Any]], terms: Sequence[str]) -> bool:
    for term in terms:
        normalized = normalize_brand(term)
        if not normalized:
            continue
        if any(normalize_brand(brand.get("brand_name")) == normalized for brand in brands):
            return True
        if any(_title_contains_brand(term, _text(brand.get("brand_name"))) for brand in brands):
            return True
    return False


def _is_shampoo_conditioner_set(text: str) -> bool:
    normalized = _normalize_type(text)
    compact = re.sub(r"\s+", "", normalized)
    markers = tuple(_normalize_type(marker) for marker in _SET_MARKERS)
    if any(marker in normalized or re.sub(r"\s+", "", marker) in compact for marker in markers):
        return _has_hair_care_context(normalized)
    has_japanese_pair = "シャンプー" in normalized and "コンディショナー" in normalized
    if has_japanese_pair and any(separator in normalized for separator in ("&", "＆", "と", "・")):
        return True
    has_english_pair = _contains_ascii_word(normalized, "shampoo") and _contains_ascii_word(
        normalized, "conditioner"
    )
    if has_english_pair and (
        " & " in normalized
        or " and " in normalized
        or any(_contains_ascii_word(normalized, word) for word in _SET_WORDS)
    ):
        return True
    return _has_hair_care_context(normalized) and any(
        _contains_ascii_word(normalized, word) for word in _SET_WORDS
    )


def _has_hair_care_context(text: str) -> bool:
    return any(
        marker in text
        for marker in ("シャンプー", "コンディショナー", "ヘアケア", "hair care")
    ) or any(_contains_ascii_word(text, word) for word in ("shampoo", "conditioner"))


def _single_value(values: Iterable[Any]) -> Any:
    sentinel = object()
    selected: Any = sentinel
    for value in values:
        if selected is sentinel:
            selected = value
        elif value != selected:
            return None
    return None if selected is sentinel else selected


def _recommendation_row(item: MapperRecommendation) -> dict[str, Any]:
    return {
        "marketplace": item.marketplace,
        "source_type": item.source_type,
        "source_asin": item.source_asin,
        "candidate_asin": item.candidate_asin,
        "product_title": item.product_title,
        "keepa_brand": item.keepa_brand,
        "keepa_category": item.keepa_category,
        "resolver_input_title": item.resolver_input_title,
        "input_safety_state": item.input_safety_state,
        "listing_ready": _bool_text(item.listing_ready),
        "canonical_product_type": item.canonical_product_type,
        "category_recommendation_status": item.category_recommendation_status,
        "recommended_category_id": item.recommended_category_id or "",
        "recommended_category_path": item.recommended_category_path,
        "category_confidence": item.category_confidence,
        "category_recommendation_source": item.category_recommendation_source,
        "category_verification_status": item.category_verification_status,
        "mandatory_attribute_count": (
            "" if item.mandatory_attribute_count is None else item.mandatory_attribute_count
        ),
        "no_brand_available": _bool_text(item.no_brand_available),
        "canonical_brand_candidate": item.canonical_brand_candidate,
        "brand_match_status": item.brand_match_status,
        "recommended_brand_id": item.recommended_brand_id if item.recommended_brand_id is not None else "",
        "recommended_brand_name": item.recommended_brand_name,
        "brand_confidence": item.brand_confidence,
        "brand_recommendation_source": item.brand_recommendation_source,
        "brand_accuracy_warning": item.brand_accuracy_warning,
        "group_key": item.group_key,
        "manual_review_required": _bool_text(item.manual_review_required),
        "manual_review_reason": item.manual_review_reason,
    }


def _rows_to_csv(columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> bytes:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: _csv_safe(row.get(column, "")) for column in columns})
    return buffer.getvalue().encode("utf-8-sig")


def _csv_header(content: bytes, filename: str) -> list[str]:
    text = _decode_csv(content, filename)
    try:
        reader = csv.reader(StringIO(text, newline=""))
        return next(reader)
    except (csv.Error, StopIteration) as exc:
        raise CategoryMapperInputError("CSV could not be read.") from exc


def _csv_dict_rows(
    content: bytes, filename: str, *, expected_header: Sequence[str]
) -> list[dict[str, str]]:
    text = _decode_csv(content, filename)
    try:
        reader = csv.reader(StringIO(text, newline=""))
        header = next(reader)
        if header != list(expected_header):
            raise CategoryMapperInputError("CSV header does not match the required contract.")
        rows: list[dict[str, str]] = []
        for values in reader:
            if not any(value.strip() for value in values):
                continue
            if len(values) != len(expected_header):
                raise CategoryMapperInputError("CSV row column count is invalid.")
            rows.append(dict(zip(expected_header, values)))
    except csv.Error as exc:
        raise CategoryMapperInputError("CSV could not be read.") from exc
    return rows


def _decode_csv(content: bytes, filename: str) -> str:
    if not content:
        raise CategoryMapperInputError("CSV is empty.")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CategoryMapperInputError("CSV must be UTF-8.") from exc


def _validate_mapper_rows(rows: Iterable[CategoryMapperInputRow]) -> None:
    seen: set[str] = set()
    materialized = tuple(rows)
    if not materialized:
        raise CategoryMapperInputError("CSV contains no candidate rows.")
    for row in materialized:
        try:
            normalized = normalize_asin(row.candidate_asin)
        except ValueError as exc:
            raise CategoryMapperInputError("Candidate ASIN format is invalid.") from exc
        if normalized in seen:
            raise CategoryMapperInputError("Duplicate candidate ASIN is not accepted.")
        seen.add(normalized)


def _merge_attribute(existing: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        key: (
            bool(existing[key] or candidate[key])
            if key == "is_mandatory"
            else max(int(existing[key]), int(candidate[key]))
            if key in {"value_count", "unit_count", "multi_select_max"}
            else existing[key] or candidate[key]
        )
        for key in existing
    }


def _list_count(node: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        value = node.get(key)
        if isinstance(value, (list, tuple)):
            return len(value)
    return 0


def _title_contains_brand(title: str, brand_name: str) -> bool:
    normalized_title = unicodedata.normalize("NFKC", _text(title))
    normalized_brand = unicodedata.normalize("NFKC", _text(brand_name))
    if not normalized_title or not normalized_brand:
        return False
    if normalized_brand.isascii() and re.search(r"[A-Za-z0-9]", normalized_brand):
        return _contains_ascii_word(normalized_title, normalized_brand)
    return normalized_brand.casefold() in normalized_title.casefold()


def _contains_ascii_word(text: str, word: str) -> bool:
    return _ASCII_WORD.pattern and re.search(
        _ASCII_WORD.pattern.format(word=re.escape(word)), text, re.IGNORECASE
    ) is not None


def _normalize_type(value: str) -> str:
    return unicodedata.normalize("NFKC", _text(value)).casefold()


def _first_text(payload: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return _text(value)
    return ""


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _positive_int(value: object) -> int | None:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _nonnegative_int(value: object) -> int | None:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _int_or_zero(value: object) -> int:
    parsed = _nonnegative_int(value)
    return 0 if parsed is None else parsed


def _bool_text(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def _csv_safe(value: object) -> object:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


def _require_ph(marketplace: str) -> None:
    if _text(marketplace).upper() != PH_MARKETPLACE:
        raise ValueError("Category Mapper supports PH only.")
