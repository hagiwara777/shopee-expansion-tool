"""Marketplace-neutral hierarchical category prediction core."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import json
from time import perf_counter
from typing import Any, Callable, Mapping, Protocol, Sequence

from modules.category_ai_prompts import (
    PROMPT_VERSION,
    RESPONSE_SCHEMA_VERSION,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_SHA256,
)


TRAVERSAL_VERSION = "HIERARCHICAL_TRAVERSAL_V1"
REQUEST_PROFILE_VERSION = "CATEGORY_AI_BENCHMARK_REQUEST_PROFILE_V1"
SUPPORTED_MARKETPLACES = frozenset({"PH", "SG", "MY", "TH"})
PROHIBITED_AI_INPUT_KEYS = frozenset(
    {
        "recommended_category",
        "canonical_product_type",
        "domain",
        "previous_selected_category_id",
        "expected_category_id",
        "gold_truth",
        "exact_match",
        "wrong_category",
    }
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _mapping_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.add(str(key).lower())
            keys.update(_mapping_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            keys.update(_mapping_keys(child))
    return keys


class CategoryAIError(RuntimeError):
    """Safe, non-secret error with a stable machine code."""

    def __init__(
        self,
        code: str,
        *,
        api_call_count: int = 0,
        latency_seconds: float = 0.0,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.api_call_count = api_call_count
        self.latency_seconds = latency_seconds


@dataclass(frozen=True)
class ProductEvidence:
    marketplace: str
    case_id: str
    product_title: str
    asin: str = ""
    keepa_category: str = ""
    keepa_brand: str = ""
    resolver_title: str = ""

    def __post_init__(self) -> None:
        market = self.marketplace.strip().upper()
        if market not in SUPPORTED_MARKETPLACES:
            raise ValueError("unsupported marketplace")
        if not self.case_id.strip() or not self.product_title.strip():
            raise ValueError("case_id and product_title are required")
        object.__setattr__(self, "marketplace", market)

    def api_product(self) -> dict[str, str]:
        return {
            "product_title": self.product_title,
            "keepa_category": self.keepa_category,
            "keepa_brand": self.keepa_brand,
            "resolver_title": self.resolver_title,
        }


@dataclass(frozen=True)
class CategoryNode:
    category_id: int
    parent_category_id: int | None
    category_name: str
    category_path: str
    is_leaf: bool

    def __post_init__(self) -> None:
        if isinstance(self.category_id, bool) or self.category_id <= 0:
            raise ValueError("category_id must be a positive integer")
        if not self.category_name.strip() or not self.category_path.strip():
            raise ValueError("category name and path are required")
        if self.parent_category_id == self.category_id:
            raise ValueError("category cannot be its own parent")

    def candidate_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "category_name": self.category_name,
            "category_path": self.category_path,
            "is_leaf": self.is_leaf,
        }


@dataclass(frozen=True)
class CategoryCatalog:
    marketplace: str
    catalog_version: str
    nodes: tuple[CategoryNode, ...]
    catalog_hash: str = field(init=False)
    _by_id: Mapping[int, CategoryNode] = field(init=False, repr=False)
    _children: Mapping[int | None, tuple[CategoryNode, ...]] = field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        market = self.marketplace.strip().upper()
        if market not in SUPPORTED_MARKETPLACES:
            raise ValueError("unsupported marketplace")
        if not self.catalog_version.strip() or not self.nodes:
            raise ValueError("catalog version and nodes are required")
        by_id: dict[int, CategoryNode] = {}
        children: dict[int | None, list[CategoryNode]] = {}
        for node in self.nodes:
            if node.category_id in by_id:
                raise ValueError("duplicate category_id")
            by_id[node.category_id] = node
            children.setdefault(node.parent_category_id, []).append(node)
        if not children.get(None):
            raise ValueError("catalog must contain root categories")
        for node in self.nodes:
            if node.parent_category_id is not None and node.parent_category_id not in by_id:
                raise ValueError("category references a missing parent")
            if node.category_path.split(" > ")[-1] != node.category_name:
                raise ValueError("category path does not end with category name")
            if node.parent_category_id is not None:
                parent = by_id[node.parent_category_id]
                if not node.category_path.startswith(parent.category_path + " > "):
                    raise ValueError("category path contradicts parent")
            actual_leaf = not children.get(node.category_id)
            if node.is_leaf != actual_leaf:
                raise ValueError("is_leaf contradicts catalog structure")
            visited: set[int] = set()
            current = node
            while current.parent_category_id is not None:
                if current.category_id in visited:
                    raise ValueError("catalog contains a cycle")
                visited.add(current.category_id)
                current = by_id[current.parent_category_id]
        ordered_nodes = tuple(sorted(self.nodes, key=lambda item: item.category_id))
        normalized_children = {
            parent: tuple(sorted(items, key=lambda item: item.category_id))
            for parent, items in children.items()
        }
        normalized = {
            "marketplace": market,
            "catalog_version": self.catalog_version,
            "nodes": [asdict(node) for node in ordered_nodes],
        }
        object.__setattr__(self, "marketplace", market)
        object.__setattr__(self, "nodes", ordered_nodes)
        object.__setattr__(self, "_by_id", by_id)
        object.__setattr__(self, "_children", normalized_children)
        object.__setattr__(self, "catalog_hash", content_hash(normalized))

    def children_of(self, parent_category_id: int | None) -> tuple[CategoryNode, ...]:
        return self._children.get(parent_category_id, ())

    def get(self, category_id: int) -> CategoryNode | None:
        return self._by_id.get(category_id)


@dataclass(frozen=True)
class BenchmarkRequestProfile:
    model: str
    reasoning_effort: str
    text_verbosity: str
    max_output_tokens: int
    service_tier: str
    timeout_seconds: float
    provider: str = "openai_responses"
    endpoint_path: str = "/v1/responses"
    stream: bool = False
    truncation: str = "disabled"
    tool_choice: str = "none"
    parallel_tool_calls: bool = False
    profile_version: str = REQUEST_PROFILE_VERSION
    prompt_version: str = PROMPT_VERSION
    prompt_sha256: str = SYSTEM_PROMPT_SHA256
    response_schema_version: str = RESPONSE_SCHEMA_VERSION
    traversal_version: str = TRAVERSAL_VERSION
    store: bool = False

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("exact model ID is required")
        if self.reasoning_effort not in {"none", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("unsupported reasoning_effort")
        if self.text_verbosity not in {"low", "medium", "high"}:
            raise ValueError("unsupported text verbosity")
        if self.max_output_tokens <= 0 or self.timeout_seconds <= 0:
            raise ValueError("token and timeout limits must be positive")
        if self.service_tier not in {"default", "flex", "priority"}:
            raise ValueError("unsupported service tier")
        if self.store is not False:
            raise ValueError("benchmark responses must use store=false")
        if (
            self.provider != "openai_responses"
            or self.endpoint_path != "/v1/responses"
            or self.stream is not False
            or self.truncation != "disabled"
            or self.tool_choice != "none"
            or self.parallel_tool_calls is not False
        ):
            raise ValueError("unsupported Responses request contract")
        if (
            self.profile_version != REQUEST_PROFILE_VERSION
            or self.prompt_version != PROMPT_VERSION
            or self.prompt_sha256 != SYSTEM_PROMPT_SHA256
            or self.response_schema_version != RESPONSE_SCHEMA_VERSION
            or self.traversal_version != TRAVERSAL_VERSION
        ):
            raise ValueError("unsupported benchmark contract version")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def profile_hash(self) -> str:
        return content_hash(self.to_dict())

    @property
    def comparison_contract_hash(self) -> str:
        settings = self.to_dict()
        settings.pop("model")
        return content_hash(settings)


def assert_profiles_comparable(profiles: Sequence[BenchmarkRequestProfile]) -> None:
    """Allow model ID to differ; every other request condition must be identical."""

    if not profiles:
        raise ValueError("at least one benchmark request profile is required")
    hashes = {profile.comparison_contract_hash for profile in profiles}
    if len(hashes) != 1:
        raise ValueError("model comparison request settings changed")


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0

    def __post_init__(self) -> None:
        values = (
            self.input_tokens,
            self.cached_tokens,
            self.cache_write_tokens,
            self.output_tokens,
        )
        if any(isinstance(value, bool) or value < 0 for value in values):
            raise ValueError("token usage must contain non-negative integers")
        if self.cached_tokens + self.cache_write_tokens > self.input_tokens:
            raise ValueError("input token details exceed input tokens")

    def plus(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            self.input_tokens + other.input_tokens,
            self.cached_tokens + other.cached_tokens,
            self.cache_write_tokens + other.cache_write_tokens,
            self.output_tokens + other.output_tokens,
        )


@dataclass(frozen=True)
class StepRequest:
    product: ProductEvidence
    parent_category_id: int | None
    current_category_path: str
    candidates: tuple[CategoryNode, ...]

    def user_input(self) -> dict[str, Any]:
        payload = {
            "prompt_version": PROMPT_VERSION,
            "marketplace": self.product.marketplace,
            "product": self.product.api_product(),
            "category_context": {
                "current_category_path": self.current_category_path,
                "candidates": [candidate.candidate_dict() for candidate in self.candidates],
            },
        }
        if _mapping_keys(payload) & PROHIBITED_AI_INPUT_KEYS:
            raise CategoryAIError("PROHIBITED_AI_INPUT")
        return payload


@dataclass(frozen=True)
class StepResult:
    product_type_summary: str
    decision: str
    selected_category_id: int | None
    confidence: float
    short_reason: str
    usage: TokenUsage = TokenUsage()
    api_call_count: int = 1
    latency_seconds: float = 0.0
    served_service_tier: str = ""


@dataclass(frozen=True)
class TraversalStep:
    step_index: int
    parent_category_id: int | None
    parent_category_path: str
    candidate_count: int
    decision: str
    selected_category_id: int | None
    selected_category_name: str
    selected_category_path: str
    selected_is_leaf: bool | None
    confidence: float
    short_reason: str
    product_type_summary: str
    input_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    output_tokens: int
    api_call_count: int
    latency_seconds: float
    served_service_tier: str


class CategoryAIProvider(Protocol):
    name: str

    def select(self, request: StepRequest, profile: BenchmarkRequestProfile) -> StepResult:
        ...


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def parse_step_result(
    value: str | Mapping[str, Any],
    *,
    allowed_category_ids: set[int],
    usage: TokenUsage | None = None,
    api_call_count: int = 1,
    latency_seconds: float = 0.0,
    served_service_tier: str = "",
) -> StepResult:
    try:
        data = (
            json.loads(value, object_pairs_hook=_reject_duplicate_keys)
            if isinstance(value, str)
            else dict(value)
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CategoryAIError("INVALID_JSON", api_call_count=api_call_count) from exc
    required = {
        "prompt_version",
        "product_type_summary",
        "decision",
        "selected_category_id",
        "confidence",
        "short_reason",
    }
    if set(data) != required:
        raise CategoryAIError("SCHEMA_VIOLATION", api_call_count=api_call_count)
    if data["prompt_version"] != PROMPT_VERSION:
        raise CategoryAIError("PROMPT_VERSION_MISMATCH", api_call_count=api_call_count)
    if not isinstance(data["product_type_summary"], str) or not data["product_type_summary"].strip():
        raise CategoryAIError("SCHEMA_VIOLATION", api_call_count=api_call_count)
    if not isinstance(data["short_reason"], str) or not data["short_reason"].strip():
        raise CategoryAIError("SCHEMA_VIOLATION", api_call_count=api_call_count)
    confidence = data["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise CategoryAIError("SCHEMA_VIOLATION", api_call_count=api_call_count)
    decision = data["decision"]
    selected = data["selected_category_id"]
    if decision == "SELECT":
        if isinstance(selected, bool) or not isinstance(selected, int):
            raise CategoryAIError("SCHEMA_VIOLATION", api_call_count=api_call_count)
        if selected not in allowed_category_ids:
            raise CategoryAIError("CANDIDATE_OUTSIDE_ALLOWLIST", api_call_count=api_call_count)
    elif decision == "ABSTAIN":
        if selected is not None:
            raise CategoryAIError("SCHEMA_VIOLATION", api_call_count=api_call_count)
    else:
        raise CategoryAIError("SCHEMA_VIOLATION", api_call_count=api_call_count)
    return StepResult(
        product_type_summary=data["product_type_summary"].strip(),
        decision=decision,
        selected_category_id=selected,
        confidence=float(confidence),
        short_reason=data["short_reason"].strip(),
        usage=usage or TokenUsage(),
        api_call_count=api_call_count,
        latency_seconds=latency_seconds,
        served_service_tier=served_service_tier,
    )


@dataclass(frozen=True)
class Prediction:
    marketplace: str
    case_id: str
    asin: str
    product_title: str
    model: str
    provider: str
    prompt_version: str
    catalog_hash: str
    catalog_version: str
    benchmark_request_profile: Mapping[str, Any]
    benchmark_request_profile_hash: str
    comparison_contract_hash: str
    traversal_version: str
    status: str
    predicted_category_id: int | None
    predicted_category_path: str
    abstain: bool
    prediction_confidence: float | None
    short_reason: str
    input_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    output_tokens: int
    api_call_count: int
    latency_seconds: float
    estimated_cost_usd: float | None
    price_config_version: str
    traversal_steps: tuple[TraversalStep, ...]
    error_code: str
    prediction_hash: str = ""

    def hash_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("prediction_hash")
        return payload

    def with_hash(self) -> "Prediction":
        return replace(self, prediction_hash=content_hash(self.hash_payload()))


@dataclass(frozen=True)
class FakeProviderOutcome:
    value: str | Mapping[str, Any]
    usage: TokenUsage = TokenUsage()
    api_call_count: int = 1
    latency_seconds: float = 0.0
    served_service_tier: str = "default"


class FakeCategoryAIProvider:
    """Scripted contract fake. It intentionally performs no semantic inference."""

    name = "fake"

    def __init__(
        self,
        outcomes: Sequence[str | Mapping[str, Any] | FakeProviderOutcome | Exception],
    ) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[tuple[StepRequest, BenchmarkRequestProfile, dict[str, Any]]] = []

    def select(self, request: StepRequest, profile: BenchmarkRequestProfile) -> StepResult:
        payload = request.user_input()
        self.requests.append((request, profile, payload))
        if not self._outcomes:
            raise CategoryAIError("FAKE_OUTCOME_EXHAUSTED")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            if isinstance(outcome, CategoryAIError):
                raise outcome
            raise CategoryAIError("FAKE_PROVIDER_ERROR") from outcome
        if isinstance(outcome, FakeProviderOutcome):
            return parse_step_result(
                outcome.value,
                allowed_category_ids={candidate.category_id for candidate in request.candidates},
                usage=outcome.usage,
                api_call_count=outcome.api_call_count,
                latency_seconds=outcome.latency_seconds,
                served_service_tier=outcome.served_service_tier,
            )
        return parse_step_result(
            outcome,
            allowed_category_ids={candidate.category_id for candidate in request.candidates},
        )


CostEstimator = Callable[[BenchmarkRequestProfile, TokenUsage], float | None]


class CategoryAIEngine:
    """Traverse one catalog independently for one product and fail closed."""

    def __init__(
        self,
        provider: CategoryAIProvider,
        *,
        cost_estimator: CostEstimator | None = None,
        price_config_version: str = "",
    ) -> None:
        self.provider = provider
        self.cost_estimator = cost_estimator
        self.price_config_version = price_config_version

    def predict(
        self,
        product: ProductEvidence,
        catalog: CategoryCatalog,
        profile: BenchmarkRequestProfile,
    ) -> Prediction:
        if product.marketplace != catalog.marketplace:
            raise ValueError("product and catalog marketplace differ")
        steps: list[TraversalStep] = []
        usage = TokenUsage()
        calls = 0
        latency = 0.0
        parent_id: int | None = None
        parent_path = "ROOT"
        failure_code = ""
        final_node: CategoryNode | None = None
        final_reason = ""
        status = "FAILED"
        abstain = True

        while True:
            candidates = catalog.children_of(parent_id)
            if not candidates:
                failure_code = "CATALOG_TRAVERSAL_INCONSISTENCY"
                final_reason = failure_code
                break
            request = StepRequest(
                product=product,
                parent_category_id=parent_id,
                current_category_path=parent_path,
                candidates=candidates,
            )
            started = perf_counter()
            try:
                result = self.provider.select(request, profile)
            except CategoryAIError as exc:
                elapsed = max(exc.latency_seconds, perf_counter() - started)
                calls += exc.api_call_count
                latency += elapsed
                failure_code = exc.code
                final_reason = exc.code
                break
            calls += result.api_call_count
            latency += result.latency_seconds or (perf_counter() - started)
            usage = usage.plus(result.usage)
            selected_node = (
                catalog.get(result.selected_category_id)
                if result.selected_category_id is not None
                else None
            )
            if result.decision == "SELECT" and (
                selected_node is None or selected_node not in candidates
            ):
                failure_code = "CATALOG_SELECTION_INCONSISTENCY"
                final_reason = failure_code
                break
            steps.append(
                TraversalStep(
                    step_index=len(steps) + 1,
                    parent_category_id=parent_id,
                    parent_category_path=parent_path,
                    candidate_count=len(candidates),
                    decision=result.decision,
                    selected_category_id=result.selected_category_id,
                    selected_category_name=selected_node.category_name if selected_node else "",
                    selected_category_path=selected_node.category_path if selected_node else "",
                    selected_is_leaf=selected_node.is_leaf if selected_node else None,
                    confidence=result.confidence,
                    short_reason=result.short_reason,
                    product_type_summary=result.product_type_summary,
                    input_tokens=result.usage.input_tokens,
                    cached_tokens=result.usage.cached_tokens,
                    cache_write_tokens=result.usage.cache_write_tokens,
                    output_tokens=result.usage.output_tokens,
                    api_call_count=result.api_call_count,
                    latency_seconds=result.latency_seconds,
                    served_service_tier=result.served_service_tier,
                )
            )
            final_reason = result.short_reason
            if result.decision == "ABSTAIN":
                status = "ABSTAIN"
                break
            assert selected_node is not None
            if selected_node.is_leaf:
                final_node = selected_node
                status = "COMPLETED"
                abstain = False
                break
            parent_id = selected_node.category_id
            parent_path = selected_node.category_path
            if len(steps) > len(catalog.nodes):
                failure_code = "CATALOG_TRAVERSAL_LIMIT"
                final_reason = failure_code
                status = "FAILED"
                abstain = True
                break

        selected_confidences = [
            step.confidence for step in steps if step.decision == "SELECT"
        ]
        prediction_confidence = min(selected_confidences) if selected_confidences else None
        estimated_cost = (
            self.cost_estimator(profile, usage) if self.cost_estimator is not None else None
        )
        prediction = Prediction(
            marketplace=product.marketplace,
            case_id=product.case_id,
            asin=product.asin,
            product_title=product.product_title,
            model=profile.model,
            provider=self.provider.name,
            prompt_version=PROMPT_VERSION,
            catalog_hash=catalog.catalog_hash,
            catalog_version=catalog.catalog_version,
            benchmark_request_profile=profile.to_dict(),
            benchmark_request_profile_hash=profile.profile_hash,
            comparison_contract_hash=profile.comparison_contract_hash,
            traversal_version=TRAVERSAL_VERSION,
            status=status,
            predicted_category_id=final_node.category_id if final_node else None,
            predicted_category_path=final_node.category_path if final_node else "",
            abstain=abstain,
            prediction_confidence=prediction_confidence,
            short_reason=final_reason,
            input_tokens=usage.input_tokens,
            cached_tokens=usage.cached_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            output_tokens=usage.output_tokens,
            api_call_count=calls,
            latency_seconds=latency,
            estimated_cost_usd=estimated_cost,
            price_config_version=self.price_config_version,
            traversal_steps=tuple(steps),
            error_code=failure_code,
        )
        return prediction.with_hash()


def make_fake_select(
    category_id: int,
    *,
    confidence: float = 0.8,
    reason: str = "synthetic contract selection",
    summary: str = "synthetic product",
) -> dict[str, Any]:
    return {
        "prompt_version": PROMPT_VERSION,
        "product_type_summary": summary,
        "decision": "SELECT",
        "selected_category_id": category_id,
        "confidence": confidence,
        "short_reason": reason,
    }


def make_fake_abstain(
    *,
    confidence: float = 0.2,
    reason: str = "synthetic ambiguity",
    summary: str = "ambiguous synthetic product",
) -> dict[str, Any]:
    return {
        "prompt_version": PROMPT_VERSION,
        "product_type_summary": summary,
        "decision": "ABSTAIN",
        "selected_category_id": None,
        "confidence": confidence,
        "short_reason": reason,
    }
