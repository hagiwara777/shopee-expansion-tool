"""Thin Category AI adapter for the PH Category Mapper Minimum Beta."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from modules.category_ai_benchmark import load_request_profiles
from modules.category_ai_core import (
    BenchmarkRequestProfile,
    CategoryAIError,
    CategoryCatalog,
    CategoryNode,
    Prediction,
    ProductEvidence,
)
from modules.category_mapper import MapperRecommendation
from modules.category_mapper_store import CategoryMapperStore


LUNA_MODEL = "gpt-5.6-luna"
AI_SUGGESTED = "SUGGESTED"
AI_ABSTAIN = "ABSTAIN"
AI_FAILED = "FAILED"
AI_CATALOG_MISMATCH = "CATALOG_MISMATCH"
AI_SKIPPED_CONFIRMED = "SKIPPED_CONFIRMED"
HOBBIES_ROOT = "Hobbies & Collections"
_PROFILE_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "category_ai_benchmark_request_profiles.json"
)


class CategoryPredictionEngine(Protocol):
    def predict(
        self,
        product: ProductEvidence,
        catalog: CategoryCatalog,
        profile: BenchmarkRequestProfile,
    ) -> Prediction: ...


@dataclass(frozen=True)
class AICategorySuggestion:
    candidate_asin: str
    status: str
    predicted_category_id: int | None = None
    predicted_category_path: str = ""
    confidence: float | None = None
    short_reason: str = ""
    error_code: str = ""
    prediction: Prediction | None = None

    @property
    def is_adoptable(self) -> bool:
        return (
            self.status == AI_SUGGESTED
            and self.predicted_category_id is not None
            and bool(self.predicted_category_path)
        )

    @property
    def requires_hobbies_warning(self) -> bool:
        root = self.predicted_category_path.split(" > ", 1)[0].strip()
        return root.casefold() == HOBBIES_ROOT.casefold()


@dataclass(frozen=True)
class AICategorySuggestionBatch:
    suggestions: tuple[AICategorySuggestion, ...]

    @property
    def success_count(self) -> int:
        return sum(item.status == AI_SUGGESTED for item in self.suggestions)

    @property
    def failure_count(self) -> int:
        return sum(
            item.status in {AI_FAILED, AI_CATALOG_MISMATCH}
            for item in self.suggestions
        )

    @property
    def skip_count(self) -> int:
        return sum(
            item.status in {AI_ABSTAIN, AI_SKIPPED_CONFIRMED}
            for item in self.suggestions
        )

    def by_asin(self) -> dict[str, AICategorySuggestion]:
        return {item.candidate_asin: item for item in self.suggestions}

    def without_asins(self, asins: set[str]) -> "AICategorySuggestionBatch":
        return AICategorySuggestionBatch(
            tuple(item for item in self.suggestions if item.candidate_asin not in asins)
        )


def load_luna_request_profile(
    path: Path = _PROFILE_PATH,
) -> BenchmarkRequestProfile:
    """Load the fixed Benchmark V1 request profile selected for Minimum Beta."""

    matches = [profile for profile in load_request_profiles(path) if profile.model == LUNA_MODEL]
    if len(matches) != 1:
        raise ValueError("The fixed Luna request profile is unavailable.")
    return matches[0]


def build_category_ai_catalog(
    store: CategoryMapperStore,
    *,
    marketplace: str = "PH",
) -> CategoryCatalog:
    """Build the AI Core catalog from the Mapper's current local Category tree."""

    rows = store.list_categories_for_category_ai_catalog(marketplace)
    if not rows:
        raise ValueError("The local Category catalog is empty.")
    last_synced_at = max((str(row.get("synced_at") or "") for row in rows), default="")
    return CategoryCatalog(
        marketplace=marketplace,
        catalog_version=f"CATEGORY_MAPPER_LOCAL_V1:{last_synced_at or 'INITIAL'}",
        nodes=tuple(
            CategoryNode(
                category_id=int(row["category_id"]),
                parent_category_id=(
                    None
                    if row.get("parent_category_id") is None
                    else int(row["parent_category_id"])
                ),
                category_name=str(row["category_name"]),
                category_path=str(row["category_path"]),
                is_leaf=bool(row["is_leaf"]),
            )
            for row in rows
        ),
    )


def generate_ai_category_suggestions(
    recommendations: Sequence[MapperRecommendation],
    *,
    store: CategoryMapperStore,
    engine: CategoryPredictionEngine,
    catalog: CategoryCatalog,
    profile: BenchmarkRequestProfile,
) -> AICategorySuggestionBatch:
    """Predict only unconfirmed rows without mutating Mapper recommendations."""

    if profile.model != LUNA_MODEL:
        raise ValueError("Category Mapper Minimum Beta requires gpt-5.6-luna.")
    if catalog.marketplace != "PH":
        raise ValueError("Category Mapper Minimum Beta requires the PH catalog.")

    suggestions: list[AICategorySuggestion] = []
    for recommendation in recommendations:
        if recommendation.category_is_confirmed:
            suggestions.append(
                AICategorySuggestion(
                    candidate_asin=recommendation.candidate_asin,
                    status=AI_SKIPPED_CONFIRMED,
                )
            )
            continue
        product = ProductEvidence(
            marketplace="PH",
            case_id=recommendation.candidate_asin,
            asin=recommendation.candidate_asin,
            product_title=recommendation.product_title,
            keepa_category=recommendation.keepa_category,
            keepa_brand=recommendation.keepa_brand,
            resolver_title=recommendation.resolver_input_title,
        )
        try:
            prediction = engine.predict(product, catalog, profile)
        except CategoryAIError as exc:
            suggestions.append(
                AICategorySuggestion(
                    candidate_asin=recommendation.candidate_asin,
                    status=AI_FAILED,
                    error_code=exc.code,
                )
            )
            continue
        except Exception:
            suggestions.append(
                AICategorySuggestion(
                    candidate_asin=recommendation.candidate_asin,
                    status=AI_FAILED,
                    error_code="UNEXPECTED_PREDICTION_ERROR",
                )
            )
            continue
        suggestions.append(
            _validated_suggestion(
                recommendation.candidate_asin,
                prediction=prediction,
                catalog=catalog,
                store=store,
            )
        )
    return AICategorySuggestionBatch(tuple(suggestions))


def group_consensus_suggestion(
    member_asins: Sequence[str],
    suggestions: Sequence[AICategorySuggestion],
) -> AICategorySuggestion | None:
    """Return one candidate only when every group member has the same valid leaf."""

    by_asin = {item.candidate_asin: item for item in suggestions}
    if not member_asins or len(set(member_asins)) != len(member_asins):
        return None
    members = [by_asin.get(asin) for asin in member_asins]
    if any(item is None or not item.is_adoptable for item in members):
        return None
    valid_members = [item for item in members if item is not None]
    category_ids = {item.predicted_category_id for item in valid_members}
    category_paths = {item.predicted_category_path for item in valid_members}
    if len(category_ids) != 1 or len(category_paths) != 1:
        return None
    return valid_members[0]


def _validated_suggestion(
    candidate_asin: str,
    *,
    prediction: Prediction,
    catalog: CategoryCatalog,
    store: CategoryMapperStore,
) -> AICategorySuggestion:
    if prediction.status == AI_ABSTAIN or (
        prediction.abstain and not prediction.error_code
    ):
        return AICategorySuggestion(
            candidate_asin=candidate_asin,
            status=AI_ABSTAIN,
            confidence=prediction.prediction_confidence,
            short_reason=prediction.short_reason,
            prediction=prediction,
        )
    if prediction.status != "COMPLETED" or prediction.abstain:
        return AICategorySuggestion(
            candidate_asin=candidate_asin,
            status=AI_FAILED,
            confidence=prediction.prediction_confidence,
            short_reason=prediction.short_reason,
            error_code=prediction.error_code or "PREDICTION_FAILED",
            prediction=prediction,
        )
    category_id = prediction.predicted_category_id
    core_node = catalog.get(category_id) if category_id is not None else None
    mapper_node = store.get_category("PH", category_id)
    if (
        core_node is None
        or not core_node.is_leaf
        or mapper_node is None
        or not bool(mapper_node.get("is_leaf"))
        or str(mapper_node.get("category_path") or "") != prediction.predicted_category_path
        or core_node.category_path != prediction.predicted_category_path
    ):
        return AICategorySuggestion(
            candidate_asin=candidate_asin,
            status=AI_CATALOG_MISMATCH,
            confidence=prediction.prediction_confidence,
            short_reason=prediction.short_reason,
            error_code="PREDICTION_CATEGORY_NOT_SELECTABLE",
            prediction=prediction,
        )
    return AICategorySuggestion(
        candidate_asin=candidate_asin,
        status=AI_SUGGESTED,
        predicted_category_id=category_id,
        predicted_category_path=prediction.predicted_category_path,
        confidence=prediction.prediction_confidence,
        short_reason=prediction.short_reason,
        prediction=prediction,
    )
