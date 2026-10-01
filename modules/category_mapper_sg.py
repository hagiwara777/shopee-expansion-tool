"""SG Category Mapper Minimum Beta with product-level human confirmation only."""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass, field, replace
from hashlib import sha256
from io import StringIO
from typing import Mapping, Sequence
from uuid import uuid4

from modules.category_ai_core import BenchmarkRequestProfile, CategoryCatalog, CategoryNode
from modules.category_mapper_ai import (
    AICategorySuggestionBatch,
    CategoryPredictionEngine,
    build_category_ai_catalog,
    generate_ai_category_suggestions,
)
from modules.sls_category_assets import SlsAssetError, load_sg_context
from modules.sls_category_rules_sg import SgSlsCategoryResult, evaluate_sg_category
from modules.category_mapper_store import CategoryMapperStore, normalize_brand
from modules.shopee_catalog_client import ShopeeCatalogClient, ShopeeCatalogError, BRAND_STATUS_NORMAL
from modules.keepa_client import normalize_asin
from modules.prelisting_candidate_csv import (
    ALLOWED_SOURCE_TYPES,
    PRELISTING_CANDIDATE_SCHEMA_VERSION,
)
from modules.prelisting_gate_csv import (
    GATE_RESULT_SCHEMA_VERSION,
    PRELISTING_GATE_RESULT_COLUMNS,
    build_prelisting_gate_export_filenames,
)


SG_MARKETPLACE = "SG"
GATE_ELIGIBLE = "GATE_ELIGIBLE"
SG_CATEGORY_CATALOG_COLUMNS = (
    "marketplace",
    "category_id",
    "parent_category_id",
    "category_name",
    "category_path",
    "is_leaf",
)
SG_CATALOG_VERSION_PREFIX = "SG_CATEGORY_CATALOG_OFFLINE_V1"
SG_ASIN_MAPPING_KEY_TYPE = "ASIN"


class SGCategoryMapperError(RuntimeError):
    """Raised when SG Mapper input or catalog cannot be trusted."""


@dataclass(frozen=True)
class SGCategoryMapperInputRow:
    source_asin: str
    candidate_asin: str
    product_title: str
    keepa_brand: str
    keepa_category: str
    source_type: str
    input_title: str = ""


@dataclass(frozen=True)
class SGCategoryMapperInput:
    marketplace: str
    source_type: str
    input_safety_state: str
    rows: tuple[SGCategoryMapperInputRow, ...]


@dataclass(frozen=True)
class SGMapperRecommendation:
    marketplace: str
    source_type: str
    source_asin: str
    candidate_asin: str
    product_title: str
    keepa_brand: str
    keepa_category: str
    resolver_input_title: str
    input_safety_state: str
    category_recommendation_status: str = "UNMAPPED"
    recommended_category_id: int | None = None
    recommended_category_path: str = ""
    category_confidence: str = "NONE"
    category_recommendation_source: str = "NONE"
    category_verification_status: str = "UNCONFIRMED"
    category_is_confirmed: bool = False
    manual_review_required: bool = True
    manual_review_reason: str = "SG Category requires product-level human confirmation."
    brand_status: str = "UNRESOLVED"
    confirmed_brand_id: int | None = None
    confirmed_brand_name: str = ""
    brand_candidates: tuple[tuple[int, str], ...] = ()
    brand_review_reason: str = "SG Brand requires current catalog and human confirmation."
    brand_current_valid: bool = False
    sls_result: SgSlsCategoryResult = field(default_factory=SgSlsCategoryResult)

    @property
    def listing_ready(self) -> bool:
        """SG Category completion never opens Brand/SLS/listing handoff."""

        return False

    @property
    def group_key(self) -> str:
        return ""


def build_sg_category_catalog_csv(
    categories: Sequence[Mapping[str, object]], *, marketplace: str
) -> bytes:
    """Convert a complete normalized SG response without API or database access.

    The client has no marketplace field per Category, so callers must explicitly
    bind the response to SG. Source paths and other extra fields are ignored.
    """

    if marketplace != SG_MARKETPLACE:
        raise SGCategoryMapperError("Normalized Category response must be bound to SG.")
    by_id: dict[int, dict[str, object]] = {}
    for category in categories:
        if not isinstance(category, Mapping) or not {
            "category_id", "parent_category_id", "category_name", "is_leaf"
        } <= category.keys():
            raise SGCategoryMapperError("Normalized Category fields are missing.")
        if category.get("marketplace", SG_MARKETPLACE) != SG_MARKETPLACE:
            raise SGCategoryMapperError("Normalized Category marketplace mismatch.")
        category_id = category["category_id"]
        if type(category_id) is not int or category_id <= 0:
            raise SGCategoryMapperError("Normalized category_id must be a positive integer.")
        if category_id in by_id:
            raise SGCategoryMapperError("Duplicate normalized category_id.")
        parent = category["parent_category_id"]
        if parent is not None and (type(parent) is not int or parent < 0):
            raise SGCategoryMapperError("Normalized parent_category_id is invalid.")
        name = category["category_name"]
        if not isinstance(name, str) or not name.strip():
            raise SGCategoryMapperError("Normalized category_name is missing.")
        if type(category["is_leaf"]) is not bool:
            raise SGCategoryMapperError("Normalized is_leaf must be boolean.")
        by_id[category_id] = {
            "marketplace": SG_MARKETPLACE,
            "category_id": category_id,
            "parent_category_id": None if parent is None or parent == 0 else parent,
            "category_name": name.strip(),
            "is_leaf": category["is_leaf"],
        }
    if not by_id or not any(row["parent_category_id"] is None for row in by_id.values()):
        raise SGCategoryMapperError("SG catalog must contain root categories.")
    if not any(row["is_leaf"] for row in by_id.values()):
        raise SGCategoryMapperError("SG catalog must contain leaf categories.")
    paths: dict[int, str] = {}
    for category_id in sorted(by_id):
        chain: list[int] = []
        visited: set[int] = set()
        current = category_id
        while current is not None and current not in paths:
            if current not in by_id:
                raise SGCategoryMapperError("SG catalog references a missing parent.")
            if current in visited:
                raise SGCategoryMapperError("SG catalog contains a cycle.")
            visited.add(current)
            chain.append(current)
            current = by_id[current]["parent_category_id"]
        prefix = paths.get(current, "")
        for ancestor in reversed(chain):
            name = by_id[ancestor]["category_name"]
            prefix = f"{prefix} > {name}" if prefix else name
            paths[ancestor] = prefix
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=SG_CATEGORY_CATALOG_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for category_id in sorted(by_id):
        row = by_id[category_id]
        writer.writerow({
            **row,
            "parent_category_id": row["parent_category_id"] or "",
            "category_path": paths[category_id],
            "is_leaf": "TRUE" if row["is_leaf"] else "FALSE",
        })
    content = output.getvalue().encode("utf-8-sig")
    parse_sg_category_catalog(content, filename="sg_category_catalog.csv")
    return content


def _validate_sg_catalog_paths(catalog: CategoryCatalog) -> None:
    """Require exact parent/name paths, beyond the shared prefix contract."""

    for node in catalog.nodes:
        parent = catalog.get(node.parent_category_id) if node.parent_category_id is not None else None
        expected = f"{parent.category_path} > {node.category_name}" if parent else node.category_name
        if node.category_path != expected:
            raise SGCategoryMapperError("SG Category path does not exactly match hierarchy.")


def parse_sg_category_catalog(content: bytes, *, filename: str) -> CategoryCatalog:
    """Parse one complete offline SG catalog and validate the entire hierarchy."""

    rows = _csv_dict_rows(content, filename, SG_CATEGORY_CATALOG_COLUMNS)
    nodes: list[CategoryNode] = []
    for row_number, row in enumerate(rows, start=2):
        if _text(row.get("marketplace")).upper() != SG_MARKETPLACE:
            raise SGCategoryMapperError(f"SG catalog marketplace mismatch at row {row_number}.")
        category_id = _strict_positive_int(row.get("category_id"), "category_id", row_number)
        parent_text = _text(row.get("parent_category_id"))
        parent_category_id = (
            None
            if not parent_text
            else _strict_positive_int(parent_text, "parent_category_id", row_number)
        )
        category_name = _text(row.get("category_name"))
        category_path = _text(row.get("category_path"))
        if not category_name or not category_path:
            raise SGCategoryMapperError(f"SG catalog name/path is missing at row {row_number}.")
        leaf_text = _text(row.get("is_leaf")).upper()
        if leaf_text not in {"TRUE", "FALSE"}:
            raise SGCategoryMapperError(f"SG catalog is_leaf is invalid at row {row_number}.")
        try:
            node = CategoryNode(
                category_id=category_id,
                parent_category_id=parent_category_id,
                category_name=category_name,
                category_path=category_path,
                is_leaf=leaf_text == "TRUE",
            )
        except ValueError as exc:
            raise SGCategoryMapperError(f"SG Category node validation failed: {exc}") from exc
        nodes.append(node)
    try:
        catalog = CategoryCatalog(
            marketplace=SG_MARKETPLACE,
            catalog_version=(
                f"{SG_CATALOG_VERSION_PREFIX}:{sha256(content).hexdigest()}"
            ),
            nodes=tuple(nodes),
        )
    except ValueError as exc:
        raise SGCategoryMapperError(f"SG Category catalog validation failed: {exc}") from exc
    _validate_sg_catalog_paths(catalog)
    return catalog


def replace_sg_category_catalog(
    store: CategoryMapperStore,
    catalog: CategoryCatalog,
    *,
    synced_at: str | None = None,
) -> int:
    """Replace SG only after CategoryCatalog has validated every row."""

    if catalog.marketplace != SG_MARKETPLACE:
        raise SGCategoryMapperError("Only a validated SG catalog can be replaced.")
    _validate_sg_catalog_paths(catalog)
    return store.replace_sg_category_catalog(catalog, synced_at=synced_at)


def parse_sg_category_mapper_input(content: bytes, *, filename: str) -> SGCategoryMapperInput:
    """Accept only a formal all-ELIGIBLE SG Gate CSV for one source type."""

    lowered_filename = filename.strip().casefold()
    if "audit" in lowered_filename or "review" in lowered_filename:
        raise SGCategoryMapperError("Gate audit and review CSV files are not accepted.")
    rows = _csv_dict_rows(content, filename, PRELISTING_GATE_RESULT_COLUMNS)
    source_types = {_text(row.get("source_type")).upper() for row in rows}
    if len(source_types) != 1 or not source_types <= ALLOWED_SOURCE_TYPES:
        raise SGCategoryMapperError("SG Gate CSV source_type must be one non-mixed allowed type.")
    source_type = next(iter(source_types))
    expected_filename = build_prelisting_gate_export_filenames(
        marketplace=SG_MARKETPLACE,
        source_type=source_type,
    )["eligible"]
    if lowered_filename != expected_filename.casefold():
        raise SGCategoryMapperError("Only the formal SG Gate eligible CSV filename is accepted.")

    mapped_rows: list[SGCategoryMapperInputRow] = []
    seen_asins: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        if _text(row.get("gate_schema_version")) != GATE_RESULT_SCHEMA_VERSION:
            raise SGCategoryMapperError(f"Gate schema version is invalid at row {row_number}.")
        if _text(row.get("candidate_schema_version")) != PRELISTING_CANDIDATE_SCHEMA_VERSION:
            raise SGCategoryMapperError(f"Candidate schema version is invalid at row {row_number}.")
        if _text(row.get("marketplace")).upper() != SG_MARKETPLACE:
            raise SGCategoryMapperError(f"Gate marketplace is not SG at row {row_number}.")
        if _text(row.get("final_eligibility")).upper() != "ELIGIBLE":
            raise SGCategoryMapperError("REVIEW and EXCLUDE rows are not accepted.")
        if _text(row.get("source_type")).upper() != source_type:
            raise SGCategoryMapperError("Mixed source_type rows are not accepted.")
        required_states = {
            "guardrail_status": "SAFE",
            "existing_listing_status": "CLEAR",
            "input_duplicate_status": "UNIQUE",
            "source_asin_status": "CLEAR",
            "metadata_status": "COMPLETE",
        }
        if any(_text(row.get(key)).upper() != expected for key, expected in required_states.items()):
            raise SGCategoryMapperError("Gate row is not a complete formal ELIGIBLE decision.")
        try:
            candidate_asin = normalize_asin(_text(row.get("candidate_asin")))
        except ValueError as exc:
            raise SGCategoryMapperError(f"Candidate ASIN is invalid at row {row_number}.") from exc
        if candidate_asin in seen_asins:
            raise SGCategoryMapperError("Duplicate candidate ASIN is not accepted.")
        seen_asins.add(candidate_asin)
        product_title = _text(row.get("product_title"))
        if not product_title:
            raise SGCategoryMapperError(f"Product title is missing at row {row_number}.")
        mapped_rows.append(
            SGCategoryMapperInputRow(
                source_asin=_text(row.get("source_asin")),
                candidate_asin=candidate_asin,
                product_title=product_title,
                keepa_brand=_text(row.get("brand")),
                keepa_category=_text(row.get("category")),
                source_type=source_type,
                input_title=_text(row.get("input_title")),
            )
        )
    return SGCategoryMapperInput(
        marketplace=SG_MARKETPLACE,
        source_type=source_type,
        input_safety_state=GATE_ELIGIBLE,
        rows=tuple(mapped_rows),
    )


def build_sg_recommendations(
    source: SGCategoryMapperInput,
    *,
    resolver_titles: Mapping[str, str] | None,
    store: CategoryMapperStore,
) -> tuple[SGMapperRecommendation, ...]:
    """Build SG rows and reuse only current-catalog-valid ASIN confirmations."""

    if source.marketplace != SG_MARKETPLACE or source.input_safety_state != GATE_ELIGIBLE:
        raise SGCategoryMapperError("Only SG GATE_ELIGIBLE input can reach SG Category Mapper.")
    resolver_titles = resolver_titles or {}
    recommendations: list[SGMapperRecommendation] = []
    for row in source.rows:
        resolver_title = _text(resolver_titles.get(row.candidate_asin) or row.input_title)
        recommendation = SGMapperRecommendation(
            marketplace=SG_MARKETPLACE,
            source_type=row.source_type,
            source_asin=row.source_asin,
            candidate_asin=row.candidate_asin,
            product_title=row.product_title,
            keepa_brand=row.keepa_brand,
            keepa_category=row.keepa_category,
            resolver_input_title=resolver_title,
            input_safety_state=GATE_ELIGIBLE,
        )
        saved = store.find_confirmed_category_mapping(
            SG_MARKETPLACE,
            SG_ASIN_MAPPING_KEY_TYPE,
            row.candidate_asin,
        )
        if saved is not None:
            current = store.get_category(SG_MARKETPLACE, saved.get("category_id"))
            if (
                current is not None
                and bool(current.get("is_leaf"))
                and _text(current.get("category_path")) == _text(saved.get("category_path"))
            ):
                recommendation = replace(
                    recommendation,
                    category_recommendation_status="CONFIRMED",
                    recommended_category_id=int(current["category_id"]),
                    recommended_category_path=_text(current["category_path"]),
                    category_confidence="HIGH",
                    category_recommendation_source="USER_CONFIRMED_REUSE",
                    category_verification_status="USER_CONFIRMED",
                    category_is_confirmed=True,
                    manual_review_required=False,
                    manual_review_reason="",
                )
        recommendations.append(recommendation)
    return refresh_sg_sls_results(tuple(recommendations), store=store)


def build_sg_category_ai_catalog(store: CategoryMapperStore) -> CategoryCatalog:
    """Build a fail-closed SG AI catalog from the current validated SG tree."""

    try:
        return build_category_ai_catalog(store, marketplace=SG_MARKETPLACE)
    except ValueError as exc:
        raise SGCategoryMapperError("Current SG Category catalog is unavailable or invalid.") from exc


def generate_sg_ai_category_suggestions(
    recommendations: Sequence[SGMapperRecommendation],
    *,
    store: CategoryMapperStore,
    engine: CategoryPredictionEngine,
    catalog: CategoryCatalog,
    profile: BenchmarkRequestProfile,
) -> AICategorySuggestionBatch:
    """Reuse Category AI Core for candidate display without confirming any row."""

    if catalog.marketplace != SG_MARKETPLACE:
        raise SGCategoryMapperError("SG AI suggestions require the current SG catalog.")
    if any(
        item.marketplace != SG_MARKETPLACE or item.input_safety_state != GATE_ELIGIBLE
        for item in recommendations
    ):
        raise SGCategoryMapperError("Only SG GATE_ELIGIBLE rows can receive AI suggestions.")
    return generate_ai_category_suggestions(
        recommendations,
        store=store,
        engine=engine,
        catalog=catalog,
        profile=profile,
    )


def confirm_sg_category(
    recommendation: SGMapperRecommendation,
    *,
    store: CategoryMapperStore,
    category_id: int,
    expected_category_path: str,
) -> SGMapperRecommendation:
    """Confirm one product after revalidating ID/path/leaf against the current SG catalog."""

    if (
        recommendation.marketplace != SG_MARKETPLACE
        or recommendation.input_safety_state != GATE_ELIGIBLE
    ):
        raise SGCategoryMapperError("Only an SG GATE_ELIGIBLE product can be confirmed.")
    if type(category_id) is not int or category_id <= 0:
        raise SGCategoryMapperError("Selected Category ID must be a positive integer.")
    current = store.get_category(SG_MARKETPLACE, category_id)
    if (
        current is None
        or not bool(current.get("is_leaf"))
        or _text(current.get("category_path")) != _text(expected_category_path)
    ):
        raise SGCategoryMapperError("Selected Category is not the current SG catalog leaf/path.")
    store.save_category_mapping(
        marketplace=SG_MARKETPLACE,
        mapping_key_type=SG_ASIN_MAPPING_KEY_TYPE,
        mapping_key=recommendation.candidate_asin,
        canonical_product_type="",
        category_id=int(current["category_id"]),
        category_path=_text(current["category_path"]),
        note="SG Category Mapper Minimum Beta product confirmation",
    )
    updated = replace(
        recommendation,
        sls_result=SgSlsCategoryResult(category_id=category_id),
        category_recommendation_status="CONFIRMED",
        recommended_category_id=int(current["category_id"]),
        recommended_category_path=_text(current["category_path"]),
        category_confidence="HIGH",
        category_recommendation_source="USER_CONFIRMED",
        category_verification_status="USER_CONFIRMED",
        category_is_confirmed=True,
        manual_review_required=False,
        manual_review_reason="",
        brand_status="UNRESOLVED",
        confirmed_brand_id=None,
        confirmed_brand_name="",
        brand_candidates=(),
        brand_review_reason="SG Brand requires current catalog and human confirmation.",
        brand_current_valid=False,
    )
    return refresh_sg_sls_results((updated,), store=store)[0]


@dataclass(frozen=True)
class SGBrandCatalog:
    """Session-only provenance, never reconstructed from persisted SUCCESS."""

    marketplace: str
    shop_id: int
    category_id: int
    session_id: str
    digest: str
    # Immutable ID / API display name / No Brand classification.
    brands: tuple[tuple[int, str, bool], ...]


@dataclass(frozen=True)
class SGBrandSyncResult:
    status: str
    pages: int
    catalog: SGBrandCatalog | None = None
    review_reason: str = ""


def sg_brand_catalog_digest(brands: Sequence[Mapping[str, object]]) -> str:
    if any(type(row["brand_id"]) is not int or row["brand_id"] < 0
           or not isinstance(row["brand_name"], str) or not row["brand_name"].strip()
           or row["is_no_brand"] not in (0, 1) for row in brands):
        raise SGCategoryMapperError("SG Brand persisted catalog is invalid.")
    rows = sorted((int(row["brand_id"]), str(row["brand_name"]), bool(row["is_no_brand"])) for row in brands)
    return "SG_BRAND_CATALOG_V1:" + sha256(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class SGBrandSession:
    """One SG shop session, with independently current catalogs per Category."""

    def __init__(self, *, marketplace: str, shop_id: int) -> None:
        if marketplace != SG_MARKETPLACE or type(shop_id) is not int or shop_id <= 0:
            raise SGCategoryMapperError("SG Brand session binding is invalid.")
        self._binding = (marketplace, shop_id, str(uuid4()))
        self._current: dict[int, SGBrandCatalog] = {}

    @property
    def marketplace(self) -> str:
        return self._binding[0]

    @property
    def shop_id(self) -> int:
        return self._binding[1]

    def invalidate(self, category_id: int) -> None:
        self._current.pop(category_id, None)

    def _check_binding(self, catalog: SGBrandCatalog, category_id: int) -> None:
        if (catalog.marketplace != self.marketplace or catalog.shop_id != self.shop_id
                or catalog.category_id != category_id or catalog.session_id != self._binding[2]):
            raise SGCategoryMapperError("SG Brand catalog/session binding mismatch.")

    def _bind_committed(self, catalog: SGBrandCatalog, *, category_id: int, store: CategoryMapperStore) -> None:
        self._check_binding(catalog, category_id)
        if sg_brand_catalog_digest(store.list_brands("SG", category_id)) != catalog.digest:
            raise SGCategoryMapperError("SG Brand catalog commit digest mismatch.")
        self._current[category_id] = catalog

    def require_current(
        self, category_id: int, *, store: CategoryMapperStore, catalog: SGBrandCatalog | None = None,
    ) -> SGBrandCatalog:
        current = self._current.get(category_id)
        if current is None:
            raise SGCategoryMapperError("SG Brand catalog is not current in this session.")
        if catalog is not None and catalog is not current:
            raise SGCategoryMapperError("SG Brand result does not belong to this current session/Category.")
        self._check_binding(current, category_id)
        if sg_brand_catalog_digest(store.list_brands("SG", category_id)) != current.digest:
            self.invalidate(category_id)
            raise SGCategoryMapperError("SG Brand catalog changed since session commit.")
        return current


def sync_sg_brand_catalog_offline(
    *, client: ShopeeCatalogClient, session: SGBrandSession, store: CategoryMapperStore,
    confirmed_category_id: int,
) -> SGBrandSyncResult:
    """Explicit lazy offline run; no factory, credential lookup, rerun, or retry.

    The injected transport must be an offline fake. The default network transport
    is refused. Response identity echoes are neither required nor invented.
    """
    category_id = confirmed_category_id
    session.invalidate(category_id)
    if type(category_id) is not int or category_id <= 0:
        raise SGCategoryMapperError("SG Brand run Category is invalid.")
    store._require_sg_brand_acceptance()

    def check_run() -> None:
        if (session.marketplace != "SG" or client.marketplace != "SG"
                or client.credentials.shop_id != session.shop_id or client.uses_default_transport):
            raise SGCategoryMapperError("SG Brand offline client/run binding is invalid.")
        client._require_marketplace("SG")

    check_run()
    current_category = store.get_category("SG", category_id)
    if current_category is None or not current_category["is_leaf"]:
        raise SGCategoryMapperError("SG Brand run requires a current leaf Category.")
    brands: dict[int, dict[str, object]] = {}
    page_signatures = set()
    offsets = set()
    offset = 0
    for page_number in range(1, 11):
        check_run()
        if offset in offsets:
            raise SGCategoryMapperError("SG Brand pagination cycle.")
        offsets.add(offset)
        try:
            page = client.get_brand_list("SG", category_id, offset=offset,
                                         page_size=100, status=BRAND_STATUS_NORMAL, strict=True)
        except (ShopeeCatalogError, ValueError):
            raise SGCategoryMapperError("SG Brand raw contract/acquisition failed; catalog is not current.") from None
        check_run()
        signature = tuple(sorted((b["brand_id"], b["brand_name"], b["original_brand_name"], b["is_no_brand"])
                                 for b in page.brands))
        if signature and signature in page_signatures:
            raise SGCategoryMapperError("SG Brand page repeated abnormally.")
        page_signatures.add(signature)
        for brand in page.brands:
            old = brands.get(brand["brand_id"])
            if old is not None and old != brand:
                raise SGCategoryMapperError("SG Brand conflicting duplicate across pages.")
            brands[brand["brand_id"]] = dict(brand)
        if page.is_complete:
            ordered = tuple(brands[key] for key in sorted(brands))
            store.replace_sg_brand_catalog(category_id, ordered)
            catalog = SGBrandCatalog("SG", session.shop_id, category_id, session._binding[2],
                                     sg_brand_catalog_digest(ordered),
                                     tuple((b["brand_id"], b["brand_name"], b["is_no_brand"]) for b in ordered))
            session._bind_committed(catalog, category_id=category_id, store=store)
            return SGBrandSyncResult("SUCCESS", page_number, catalog)
        if page.next_offset <= offset or page.next_offset in offsets:
            raise SGCategoryMapperError("SG Brand pagination did not advance.")
        offset = page.next_offset
    return SGBrandSyncResult("INCOMPLETE", 10, review_reason="Brand page budget exhausted; Category requires REVIEW.")


def sg_no_brand_evidence_digest(item: SGMapperRecommendation) -> str:
    """Only equality of the seven recorded Evidence fields, not product truth."""
    fields = {
        "candidate_asin": item.candidate_asin, "product_title": item.product_title,
        "keepa_brand": item.keepa_brand, "keepa_category": item.keepa_category,
        "resolver_input_title": item.resolver_input_title, "source_type": item.source_type,
        "source_asin": item.source_asin,
    }
    canonical = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
    return "SG_NO_BRAND_EVIDENCE_V1:" + sha256(canonical.encode("utf-8")).hexdigest()


def _require_sg_brand_product(item: SGMapperRecommendation, store: CategoryMapperStore) -> int:
    if (item.marketplace != "SG" or item.input_safety_state != GATE_ELIGIBLE
            or not item.category_is_confirmed or item.category_verification_status != "USER_CONFIRMED"):
        raise SGCategoryMapperError("SG Brand requires eligible input and human-confirmed Category.")
    category_id = item.recommended_category_id
    if type(category_id) is not int or normalize_asin(item.candidate_asin) != item.candidate_asin:
        raise SGCategoryMapperError("SG Brand product identity is invalid.")
    current = store.get_category("SG", category_id)
    if (current is None or not current["is_leaf"]
            or current["category_path"] != item.recommended_category_path):
        raise SGCategoryMapperError("SG Brand requires current Category ID/path/leaf.")
    return category_id


def _sg_brand_review(item: SGMapperRecommendation, reason: str, *, current: bool = False,
                     candidates: tuple[tuple[int, str], ...] = ()) -> SGMapperRecommendation:
    return replace(item, brand_status="CANDIDATE" if candidates else "REVIEW",
                   confirmed_brand_id=None, confirmed_brand_name="", brand_candidates=candidates,
                   brand_review_reason=reason, brand_current_valid=current,
                   manual_review_required=True, manual_review_reason=reason)


def review_sg_brand(
    item: SGMapperRecommendation, *, store: CategoryMapperStore, session: SGBrandSession,
    catalog: SGBrandCatalog | None = None,
) -> SGMapperRecommendation:
    """Saved No Brand has precedence and never silently falls back to an alias."""
    try:
        category_id = _require_sg_brand_product(item, store)
        current = session.require_current(category_id, store=store, catalog=catalog)
    except (SGCategoryMapperError, ValueError):
        return _sg_brand_review(item, "Current SG Category/Brand session validation required.")
    options = {b[0]: (b[1], b[2]) for b in current.brands}
    saved = store.find_sg_no_brand_confirmation(item.candidate_asin, category_id)
    if saved is not None:
        option = options.get(saved["no_brand_id"])
        valid = (saved["marketplace"] == "SG" and saved["candidate_asin"] == item.candidate_asin
                 and saved["confirmed_category_id"] == category_id and saved["user_confirmed"] == 1
                 and saved["product_evidence_digest"] == sg_no_brand_evidence_digest(item)
                 and saved["source_brand"] == item.keepa_brand
                 and option == (saved["no_brand_name"], True))
        if not valid:
            return _sg_brand_review(item, "Saved product No Brand confirmation is stale; human REVIEW required.", current=True)
        return _sg_brand_confirmed(item, saved["no_brand_id"], saved["no_brand_name"], True)
    if store.has_sg_no_brand_confirmation(item.candidate_asin):
        return _sg_brand_review(item, "Product No Brand Category changed; human REVIEW required.", current=True)
    alias = store.find_sg_brand_alias(item.keepa_brand, category_id)
    if alias is not None:
        valid = (bool(item.keepa_brand.strip()) and alias["canonical_brand"] == item.keepa_brand
                 and alias["source_brand"] == normalize_brand(item.keepa_brand)
                 and alias["user_confirmed"] == 1 and alias["verification_status"] == "USER_CONFIRMED"
                 and options.get(alias["brand_id"]) == (alias["shopee_brand_name"], False))
        if not valid:
            return _sg_brand_review(item, "Saved real Brand alias is stale/ambiguous; human REVIEW required.", current=True)
        return _sg_brand_confirmed(item, alias["brand_id"], alias["shopee_brand_name"], False)
    if not item.keepa_brand.strip() or not normalize_brand(item.keepa_brand):
        return _sg_brand_review(item, "Source Brand missing/ambiguous; human REVIEW required.", current=True)
    candidates = tuple((brand_id, name) for brand_id, name, no_brand in current.brands
                       if not no_brand and normalize_brand(name) == normalize_brand(item.keepa_brand))
    if not candidates:
        title = f" {normalize_brand(item.product_title + ' ' + item.resolver_input_title)} "
        candidates = tuple((brand_id, name) for brand_id, name, no_brand in current.brands
                           if not no_brand and f" {normalize_brand(name)} " in title)
    return _sg_brand_review(item, "Brand candidates require human confirmation." if candidates
                            else "Source Brand not registered; No Brand is not an automatic fallback.",
                            current=True, candidates=candidates)


def _sg_brand_confirmed(item: SGMapperRecommendation, brand_id: int, name: str, no_brand: bool) -> SGMapperRecommendation:
    return replace(item, brand_status="NO_BRAND_CONFIRMED" if no_brand else "REAL_BRAND_CONFIRMED",
                   confirmed_brand_id=brand_id, confirmed_brand_name=name, brand_candidates=(),
                   brand_review_reason="", brand_current_valid=True,
                   manual_review_required=False, manual_review_reason="")


def confirm_sg_brand(
    item: SGMapperRecommendation, *, store: CategoryMapperStore, session: SGBrandSession,
    catalog: SGBrandCatalog, brand_id: int, expected_brand_name: str,
    human_product_verified: bool, human_option_selected: bool,
) -> SGMapperRecommendation:
    """Explicit per-product human selection; no Brand/No Brand auto-confirm."""
    if human_product_verified is not True or human_option_selected is not True:
        raise SGCategoryMapperError("Explicit human product verification and option selection are required.")
    category_id = _require_sg_brand_product(item, store)
    current = session.require_current(category_id, store=store, catalog=catalog)
    if type(brand_id) is not int:
        raise SGCategoryMapperError("Selected SG Brand ID is invalid.")
    option = next((b for b in current.brands if b[0] == brand_id), None)
    if option is None or option[1] != expected_brand_name:
        raise SGCategoryMapperError("Selected SG Brand is not the current ID/name option.")
    store.save_sg_brand_confirmation(candidate_asin=item.candidate_asin, category_id=category_id,
        brand={"brand_id": option[0], "brand_name": option[1], "is_no_brand": option[2]},
        source_brand=item.keepa_brand, product_evidence_digest=sg_no_brand_evidence_digest(item),
        expected_brands=current.brands, expected_category_path=item.recommended_category_path)
    return _sg_brand_confirmed(item, option[0], option[1], option[2])


def _csv_dict_rows(
    content: bytes,
    filename: str,
    expected_header: Sequence[str],
) -> list[dict[str, str]]:
    if not content:
        raise SGCategoryMapperError(f"{filename} is empty.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SGCategoryMapperError(f"{filename} must be UTF-8.") from exc
    try:
        reader = csv.reader(StringIO(text, newline=""))
        header = next(reader, None)
        if header != list(expected_header):
            raise SGCategoryMapperError(f"{filename} has an unsupported header.")
        rows: list[dict[str, str]] = []
        for values in reader:
            if not values or all(not _text(value) for value in values):
                continue
            if len(values) != len(expected_header):
                raise SGCategoryMapperError(f"{filename} has an invalid column count.")
            rows.append(dict(zip(expected_header, values)))
    except csv.Error as exc:
        raise SGCategoryMapperError(f"{filename} could not be read.") from exc
    if not rows:
        raise SGCategoryMapperError(f"{filename} contains no rows.")
    return rows


def _strict_positive_int(value: object, field: str, row_number: int) -> int:
    text = _text(value)
    if not text.isdecimal():
        raise SGCategoryMapperError(f"SG catalog {field} is invalid at row {row_number}.")
    result = int(text)
    if result <= 0:
        raise SGCategoryMapperError(f"SG catalog {field} is invalid at row {row_number}.")
    return result


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def refresh_sg_sls_results(recommendations: Sequence[SGMapperRecommendation], *,
                           store: CategoryMapperStore) -> tuple[SGMapperRecommendation, ...]:
    """Re-read current bytes/content; replace only the independent SLS result."""
    if any(item.marketplace != "SG" for item in recommendations):
        raise SGCategoryMapperError("SG SLS refresh requires SG recommendations.")
    try:
        context = load_sg_context()
        current_rows = store.list_categories_for_category_ai_catalog("SG")
        if not current_rows or any(
            type(row["category_id"]) is not int or row["category_id"] <= 0
            or (row["parent_category_id"] is not None and
                (type(row["parent_category_id"]) is not int or row["parent_category_id"] <= 0))
            or type(row["is_leaf"]) is not int or row["is_leaf"] not in (0, 1)
            or any(type(row[key]) is not str for key in ("category_name", "category_path", "synced_at"))
            for row in current_rows
        ):
            raise SGCategoryMapperError("Current SG SLS catalog is invalid.")
        catalog = CategoryCatalog("SG", "SG_SLS_CURRENT_V1:" + max(row["synced_at"] for row in current_rows),
            tuple(CategoryNode(row["category_id"], row["parent_category_id"], row["category_name"],
                               row["category_path"], bool(row["is_leaf"])) for row in current_rows))
        _validate_sg_catalog_paths(catalog)
        rows = sorted((node.category_id, node.parent_category_id, node.category_name,
                       node.category_path, node.is_leaf) for node in catalog.nodes)
        digest = sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        version = catalog.catalog_version + ":" + digest
        by_id = {node.category_id: node for node in catalog.nodes}
    except (SlsAssetError, SGCategoryMapperError, ValueError, TypeError, KeyError, OSError, sqlite3.Error):
        return tuple(replace(item, sls_result=SgSlsCategoryResult(
            check_state="UNAVAILABLE" if item.category_is_confirmed else "UNCHECKED",
            category_id=item.recommended_category_id, reason_codes=("SLS_CATEGORY_DATA_UNAVAILABLE",),
        )) for item in recommendations)
    results = []
    for item in recommendations:
        cid = item.recommended_category_id
        current = by_id.get(cid) if type(cid) is int and cid > 0 else None
        result = evaluate_sg_category(
            marketplace=item.marketplace, category_id=cid,
            category_confirmed=item.category_is_confirmed and item.category_verification_status == "USER_CONFIRMED",
            category_path=item.recommended_category_path,
            current_category_path=current.category_path if current else None,
            current_is_leaf=current.is_leaf if current else False,
            catalog_version=version, context=context,
        )
        if item.input_safety_state != GATE_ELIGIBLE:
            result = replace(result, check_state="EVALUATED", action="CATEGORY_REVIEW", reason_codes=("UPSTREAM_SAFETY_STOP",))
        results.append(replace(item, sls_result=result))
    return tuple(results)
