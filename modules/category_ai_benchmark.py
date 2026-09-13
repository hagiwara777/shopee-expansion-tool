"""CSV/config adapters and post-prediction benchmark evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
from io import StringIO
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from modules.category_ai_core import (
    BenchmarkRequestProfile,
    CategoryCatalog,
    CategoryNode,
    Prediction,
    ProductEvidence,
    TokenUsage,
    assert_profiles_comparable,
    canonical_json,
    content_hash,
)


SOURCE_REQUIRED_COLUMNS = frozenset({"case_id", "product_title"})
SOURCE_OPTIONAL_COLUMNS = frozenset(
    {"marketplace", "asin", "keepa_category", "keepa_brand", "resolver_title"}
)
CATALOG_COLUMNS = frozenset(
    {"category_id", "parent_category_id", "category_name", "category_path", "is_leaf"}
)
GOLD_COLUMNS = frozenset(
    {
        "case_id",
        "asin",
        "expected_category_id",
        "expected_category_path",
        "truth_status",
    }
)
GOLD_CONFIRMED = "CONFIRMED"
GOLD_ABSTAIN_REQUIRED = "ABSTAIN_REQUIRED"
SUPPORTED_GOLD_STATUSES = frozenset({GOLD_CONFIRMED, GOLD_ABSTAIN_REQUIRED})
SCORING_OUTCOMES = frozenset(
    {
        "CORRECT_SELECT",
        "CORRECT_ABSTAIN",
        "WRONG_CATEGORY",
        "FALSE_ABSTAIN",
        "OVERCONFIDENT_SELECT",
        "FAILED",
    }
)
PREDICTION_BATCH_HASH_VERSION = "CATEGORY_AI_PREDICTION_BATCH_V1"


def _decode_csv(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8") from exc


def _rows(content: bytes, required: frozenset[str]) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(_decode_csv(content), newline=""))
    fields = set(reader.fieldnames or ())
    if not required.issubset(fields):
        missing = ", ".join(sorted(required - fields))
        raise ValueError(f"missing CSV columns: {missing}")
    return [
        {str(key): str(value or "").strip() for key, value in row.items() if key is not None}
        for row in reader
    ]


def parse_source_csv(content: bytes, *, marketplace: str) -> tuple[ProductEvidence, ...]:
    market = marketplace.strip().upper()
    rows = _rows(content, SOURCE_REQUIRED_COLUMNS)
    products: list[ProductEvidence] = []
    seen: set[str] = set()
    for row in rows:
        case_id = row.get("case_id", "")
        if case_id in seen:
            raise ValueError("duplicate case_id")
        seen.add(case_id)
        row_market = row.get("marketplace", "").upper()
        if row_market and row_market != market:
            raise ValueError("source marketplace differs from selected marketplace")
        products.append(
            ProductEvidence(
                marketplace=market,
                case_id=case_id,
                asin=row.get("asin", ""),
                product_title=row.get("product_title", ""),
                keepa_category=row.get("keepa_category", ""),
                keepa_brand=row.get("keepa_brand", ""),
                resolver_title=row.get("resolver_title", ""),
            )
        )
    if not products:
        raise ValueError("source CSV has no products")
    return tuple(products)


def parse_catalog_csv(
    content: bytes,
    *,
    marketplace: str,
    catalog_version: str,
) -> CategoryCatalog:
    rows = _rows(content, CATALOG_COLUMNS)
    nodes = []
    for row in rows:
        category_id = _positive_int(row["category_id"], "category_id")
        parent_text = row["parent_category_id"]
        parent_id = (
            None
            if parent_text.lower() in {"", "0", "null", "none"}
            else _positive_int(parent_text, "parent_category_id")
        )
        leaf_text = row["is_leaf"].lower()
        if leaf_text not in {"true", "false", "1", "0"}:
            raise ValueError("is_leaf must be true or false")
        nodes.append(
            CategoryNode(
                category_id=category_id,
                parent_category_id=parent_id,
                category_name=row["category_name"],
                category_path=row["category_path"],
                is_leaf=leaf_text in {"true", "1"},
            )
        )
    return CategoryCatalog(
        marketplace=marketplace,
        catalog_version=catalog_version,
        nodes=tuple(nodes),
    )


@dataclass(frozen=True)
class GoldTruth:
    case_id: str
    asin: str
    truth_status: str
    expected_category_id: int | None
    expected_category_path: str


def parse_gold_csv(
    content: bytes,
    *,
    products: Sequence[ProductEvidence],
    catalog: CategoryCatalog,
) -> dict[str, GoldTruth]:
    """Load formal Gold only after Source and Catalog have been fixed."""

    rows = _rows(content, GOLD_COLUMNS)
    source_by_case: dict[str, ProductEvidence] = {}
    source_asins: set[str] = set()
    for product in products:
        case_id = product.case_id.strip()
        asin = product.asin.strip()
        if not case_id or case_id in source_by_case:
            raise ValueError("source case_id must be non-empty and unique")
        if not asin or asin in source_asins:
            raise ValueError("source ASIN must be non-empty and unique")
        source_by_case[case_id] = product
        source_asins.add(asin)

    gold: dict[str, GoldTruth] = {}
    gold_asins: set[str] = set()
    for row in rows:
        case_id = row["case_id"]
        if not case_id or case_id in gold:
            raise ValueError("gold case_id must be non-empty and unique")
        asin = row["asin"]
        if not asin or asin in gold_asins:
            raise ValueError("gold ASIN must be non-empty and unique")
        gold_asins.add(asin)
        truth_status = row["truth_status"]
        if truth_status not in SUPPORTED_GOLD_STATUSES:
            raise ValueError("unsupported gold truth_status")
        expected_id_text = row["expected_category_id"]
        expected_path = row["expected_category_path"]
        expected_id: int | None = None
        if truth_status == GOLD_CONFIRMED:
            if not expected_id_text or not expected_path:
                raise ValueError("CONFIRMED gold requires expected Category ID and path")
            expected_id = _positive_int(expected_id_text, "expected_category_id")
            node = catalog.get(expected_id)
            if node is None or not node.is_leaf:
                raise ValueError("CONFIRMED expected_category_id must be a catalog leaf")
            if node.category_path != expected_path:
                raise ValueError("CONFIRMED expected Category ID and path differ")
        elif expected_id_text or expected_path:
            raise ValueError("ABSTAIN_REQUIRED expected Category ID and path must be blank")
        gold[case_id] = GoldTruth(
            case_id=case_id,
            asin=asin,
            truth_status=truth_status,
            expected_category_id=expected_id,
            expected_category_path=expected_path,
        )

    if set(gold) != set(source_by_case):
        raise ValueError("Source and Gold case_id sets differ")
    if len(gold) != len(products):
        raise ValueError("Source and Gold row counts differ")
    for case_id, truth in gold.items():
        if truth.asin != source_by_case[case_id].asin:
            raise ValueError("Source and Gold ASIN mapping differs")
    return gold


def _positive_int(value: str, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} must be positive")
    return parsed


@dataclass(frozen=True)
class ModelPrice:
    input_per_million_usd: float
    cached_input_per_million_usd: float
    cache_write_multiplier: float
    output_per_million_usd: float


@dataclass(frozen=True)
class PriceBook:
    version: str
    updated_at: str
    service_tier: str
    models: Mapping[str, ModelPrice]

    @classmethod
    def from_path(cls, path: Path) -> "PriceBook":
        data = json.loads(path.read_text(encoding="utf-8"))
        required = {"version", "updated_at", "service_tier", "models"}
        if set(data) != required or not isinstance(data["models"], dict):
            raise ValueError("invalid price config")
        models = {
            model: ModelPrice(
                input_per_million_usd=float(values["input_per_million_usd"]),
                cached_input_per_million_usd=float(
                    values["cached_input_per_million_usd"]
                ),
                cache_write_multiplier=float(values["cache_write_multiplier"]),
                output_per_million_usd=float(values["output_per_million_usd"]),
            )
            for model, values in data["models"].items()
        }
        return cls(
            version=str(data["version"]),
            updated_at=str(data["updated_at"]),
            service_tier=str(data["service_tier"]),
            models=models,
        )

    def estimate(self, profile: BenchmarkRequestProfile, usage: TokenUsage) -> float:
        if profile.service_tier != self.service_tier:
            raise ValueError("price config does not cover selected service tier")
        price = self.models.get(profile.model)
        if price is None:
            raise ValueError("price config does not cover selected model")
        regular = usage.input_tokens - usage.cached_tokens - usage.cache_write_tokens
        cost = (
            regular * price.input_per_million_usd
            + usage.cached_tokens * price.cached_input_per_million_usd
            + usage.cache_write_tokens
            * price.input_per_million_usd
            * price.cache_write_multiplier
            + usage.output_tokens * price.output_per_million_usd
        ) / 1_000_000
        return round(cost, 12)


def load_request_profiles(path: Path) -> tuple[BenchmarkRequestProfile, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != {"config_version", "profiles"} or not isinstance(
        data["profiles"], list
    ):
        raise ValueError("invalid request profile config")
    if data["config_version"] != "CATEGORY_AI_BENCHMARK_REQUEST_PROFILES_V1":
        raise ValueError("unsupported request profile config version")
    profiles = tuple(BenchmarkRequestProfile(**item) for item in data["profiles"])
    assert_profiles_comparable(profiles)
    if len({profile.model for profile in profiles}) != len(profiles):
        raise ValueError("duplicate model request profile")
    return profiles


@dataclass(frozen=True)
class GoldEvaluation:
    case_id: str
    asin: str
    model: str
    prediction_hash: str
    truth_status: str
    expected_category_id: int | None
    expected_category_path: str
    prediction_decision: str
    scoring_outcome: str

    @property
    def exact_match(self) -> bool:
        return self.scoring_outcome == "CORRECT_SELECT"

    @property
    def wrong_category(self) -> bool:
        return self.scoring_outcome == "WRONG_CATEGORY"


def prediction_batch_hash(predictions: Sequence[Prediction]) -> str:
    """Fix a complete, deterministic batch before Gold is loaded."""

    if not predictions:
        raise ValueError("prediction batch must not be empty")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for prediction in predictions:
        if (
            not prediction.prediction_hash
            or prediction.with_hash().prediction_hash != prediction.prediction_hash
        ):
            raise ValueError("prediction must be fixed before batch hashing")
        identity = (prediction.model, prediction.case_id)
        if identity in seen:
            raise ValueError("duplicate model and case_id in prediction batch")
        seen.add(identity)
        records.append(
            {
                "model": prediction.model,
                "case_id": prediction.case_id,
                "asin": prediction.asin,
                "prediction_hash": prediction.prediction_hash,
            }
        )
    return content_hash(
        {
            "version": PREDICTION_BATCH_HASH_VERSION,
            "predictions": sorted(
                records, key=lambda item: (item["model"], item["case_id"])
            ),
        }
    )


def evaluate_predictions(
    predictions: Sequence[Prediction],
    gold: Mapping[str, GoldTruth],
    *,
    fixed_prediction_batch_hash: str,
) -> dict[str, GoldEvaluation]:
    """Compare only already-fixed predictions; gold never enters the engine/provider."""

    if prediction_batch_hash(predictions) != fixed_prediction_batch_hash:
        raise ValueError("prediction batch hash differs from the fixed pre-Gold hash")

    by_model: dict[str, list[Prediction]] = {}
    for prediction in predictions:
        by_model.setdefault(prediction.model, []).append(prediction)
    gold_cases = set(gold)
    for items in by_model.values():
        cases = [item.case_id for item in items]
        if len(cases) != len(set(cases)) or set(cases) != gold_cases:
            raise ValueError("each model prediction batch must match every Gold case_id")

    evaluation: dict[str, GoldEvaluation] = {}
    for prediction in predictions:
        truth = gold[prediction.case_id]
        if prediction.asin != truth.asin:
            raise ValueError("Prediction and Gold ASIN mapping differs")
        if prediction.status == "FAILED":
            decision = "FAILED"
            outcome = "FAILED"
        elif (
            prediction.status == "ABSTAIN"
            and prediction.abstain
            and prediction.predicted_category_id is None
        ):
            decision = "ABSTAIN"
            outcome = (
                "CORRECT_ABSTAIN"
                if truth.truth_status == GOLD_ABSTAIN_REQUIRED
                else "FALSE_ABSTAIN"
            )
        elif (
            prediction.status == "COMPLETED"
            and not prediction.abstain
            and prediction.predicted_category_id is not None
        ):
            decision = "SELECT"
            if truth.truth_status == GOLD_ABSTAIN_REQUIRED:
                outcome = "OVERCONFIDENT_SELECT"
            elif prediction.predicted_category_id == truth.expected_category_id:
                outcome = "CORRECT_SELECT"
            else:
                outcome = "WRONG_CATEGORY"
        else:
            decision = "FAILED"
            outcome = "FAILED"
        if outcome not in SCORING_OUTCOMES:
            raise AssertionError("unreachable scoring outcome")
        evaluation[prediction.prediction_hash] = GoldEvaluation(
            case_id=prediction.case_id,
            asin=prediction.asin,
            model=prediction.model,
            prediction_hash=prediction.prediction_hash,
            truth_status=truth.truth_status,
            expected_category_id=truth.expected_category_id,
            expected_category_path=truth.expected_category_path,
            prediction_decision=decision,
            scoring_outcome=outcome,
        )
    return evaluation


def prediction_rows(
    predictions: Sequence[Prediction],
    evaluations: Mapping[str, GoldEvaluation] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for prediction in predictions:
        row = asdict(prediction)
        row["confidence"] = prediction.prediction_confidence
        row["benchmark_request_profile"] = canonical_json(
            prediction.benchmark_request_profile
        )
        row["traversal_steps"] = canonical_json(
            [asdict(step) for step in prediction.traversal_steps]
        )
        evaluation = (evaluations or {}).get(prediction.prediction_hash)
        row.update(
            {
                "exact_match": evaluation.exact_match if evaluation else "",
                "wrong_category": evaluation.wrong_category if evaluation else "",
                "gold_truth_status": evaluation.truth_status if evaluation else "",
                "prediction_decision": (
                    evaluation.prediction_decision if evaluation else ""
                ),
                "scoring_outcome": evaluation.scoring_outcome if evaluation else "",
                "expected_category_id": (
                    evaluation.expected_category_id if evaluation else ""
                ),
                "expected_category_path": (
                    evaluation.expected_category_path if evaluation else ""
                ),
            }
        )
        rows.append(row)
    return rows


def rows_to_csv(rows: Sequence[Mapping[str, Any]]) -> bytes:
    if not rows:
        return b""
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def aggregate_by_model(
    predictions: Sequence[Prediction],
    evaluations: Mapping[str, GoldEvaluation] | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Prediction]] = {}
    for prediction in predictions:
        grouped.setdefault(prediction.model, []).append(prediction)
    summaries: list[dict[str, Any]] = []
    for model, items in sorted(grouped.items()):
        matched = [
            (evaluations or {}).get(item.prediction_hash)
            for item in items
            if (evaluations or {}).get(item.prediction_hash) is not None
        ]
        outcome_counts = {
            outcome: sum(
                bool(item and item.scoring_outcome == outcome) for item in matched
            )
            for outcome in SCORING_OUTCOMES
        }
        success_count = (
            outcome_counts["CORRECT_SELECT"] + outcome_counts["CORRECT_ABSTAIN"]
        )
        confirmed_count = sum(
            bool(item and item.truth_status == GOLD_CONFIRMED) for item in matched
        )
        abstain_required_count = sum(
            bool(item and item.truth_status == GOLD_ABSTAIN_REQUIRED) for item in matched
        )
        select_count = (
            outcome_counts["CORRECT_SELECT"]
            + outcome_counts["WRONG_CATEGORY"]
            + outcome_counts["OVERCONFIDENT_SELECT"]
        )
        completed_decision_count = len(matched) - outcome_counts["FAILED"]
        known_costs = [item.estimated_cost_usd for item in items if item.estimated_cost_usd is not None]
        total_cost = sum(known_costs) if len(known_costs) == len(items) else None
        summaries.append(
            {
                "model": model,
                "total_products": len(items),
                "evaluated_products": len(matched),
                "correct_select_count": outcome_counts["CORRECT_SELECT"],
                "correct_abstain_count": outcome_counts["CORRECT_ABSTAIN"],
                "wrong_category_count": outcome_counts["WRONG_CATEGORY"],
                "false_abstain_count": outcome_counts["FALSE_ABSTAIN"],
                "overconfident_select_count": outcome_counts[
                    "OVERCONFIDENT_SELECT"
                ],
                "failed_count": outcome_counts["FAILED"],
                "overall_success_count": success_count,
                "overall_success_rate": (
                    success_count / len(items) if items and matched else None
                ),
                "confirmed_exact_accuracy": (
                    outcome_counts["CORRECT_SELECT"] / confirmed_count
                    if confirmed_count
                    else None
                ),
                "abstain_accuracy": (
                    outcome_counts["CORRECT_ABSTAIN"] / abstain_required_count
                    if abstain_required_count
                    else None
                ),
                "select_precision": (
                    outcome_counts["CORRECT_SELECT"] / select_count
                    if select_count
                    else None
                ),
                "completed_decision_count": completed_decision_count,
                "completed_decision_success_count": success_count,
                "completed_decision_success_rate": (
                    success_count / completed_decision_count
                    if completed_decision_count
                    else None
                ),
                "total_input_tokens": sum(item.input_tokens for item in items),
                "total_cached_tokens": sum(item.cached_tokens for item in items),
                "total_output_tokens": sum(item.output_tokens for item in items),
                "api_call_count": sum(item.api_call_count for item in items),
                "total_cost_usd": total_cost,
                "average_cost_per_product_usd": total_cost / len(items) if total_cost is not None else None,
                "average_latency_seconds": sum(item.latency_seconds for item in items) / len(items),
            }
        )
    return summaries
