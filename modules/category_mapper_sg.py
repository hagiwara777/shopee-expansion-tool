"""SG Category Mapper Minimum Beta with product-level human confirmation only."""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from hashlib import sha256
from io import StringIO
from typing import Mapping, Sequence

from modules.category_ai_core import BenchmarkRequestProfile, CategoryCatalog, CategoryNode
from modules.category_mapper_ai import (
    AICategorySuggestionBatch,
    CategoryPredictionEngine,
    build_category_ai_catalog,
    generate_ai_category_suggestions,
)
from modules.category_mapper_store import CategoryMapperStore
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

    @property
    def listing_ready(self) -> bool:
        """SG Category completion never opens Brand/SLS/listing handoff."""

        return False

    @property
    def group_key(self) -> str:
        return ""


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
        nodes.append(
            CategoryNode(
                category_id=category_id,
                parent_category_id=parent_category_id,
                category_name=category_name,
                category_path=category_path,
                is_leaf=leaf_text == "TRUE",
            )
        )
    try:
        return CategoryCatalog(
            marketplace=SG_MARKETPLACE,
            catalog_version=(
                f"{SG_CATALOG_VERSION_PREFIX}:{sha256(content).hexdigest()}"
            ),
            nodes=tuple(nodes),
        )
    except ValueError as exc:
        raise SGCategoryMapperError(f"SG Category catalog validation failed: {exc}") from exc


def replace_sg_category_catalog(
    store: CategoryMapperStore,
    catalog: CategoryCatalog,
    *,
    synced_at: str | None = None,
) -> int:
    """Replace SG only after CategoryCatalog has validated every row."""

    if catalog.marketplace != SG_MARKETPLACE:
        raise SGCategoryMapperError("Only a validated SG catalog can be replaced.")
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
    return tuple(recommendations)


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
    return replace(
        recommendation,
        category_recommendation_status="CONFIRMED",
        recommended_category_id=int(current["category_id"]),
        recommended_category_path=_text(current["category_path"]),
        category_confidence="HIGH",
        category_recommendation_source="USER_CONFIRMED",
        category_verification_status="USER_CONFIRMED",
        category_is_confirmed=True,
        manual_review_required=False,
        manual_review_reason="",
    )


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
