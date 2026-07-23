"""PH Category Mapper AI shadow-mode helpers.

This module is deliberately isolated from Category Mapper Ver0.1.  It builds
local Category DB candidates, asks a provider to rank only those candidates,
and records structured evaluation data.  It never mutates a Ver0.1
recommendation, mapping, brand decision, or export.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
import re
import time
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from modules.category_mapper import MapperRecommendation
from modules.category_mapper_store import (
    CategoryMapperStore,
    normalize_brand,
    normalize_mapping_key,
)


PH_MARKETPLACE = "PH"
PROMPT_VERSION = "CATEGORY_SHADOW_V1"
SCHEMA_VERSION = "CATEGORY_SHADOW_V1"
MAX_CANDIDATES = 20
MAX_RANKED_CANDIDATES = 3
MAX_GROUPS_PER_RUN = 20
MAX_REQUEST_SECONDS = 30
MAX_RUN_SECONDS = 180
MAX_OUTPUT_TOKENS = 600
_ACCEPTED_VERIFICATION_STATUSES = {
    "USER_CONFIRMED",
    "LISTING_TOOL_ACCEPTED",
    "SHOPEE_CORRECTED",
}
_RESCORE_TRUTH_STATUSES = {"USER_CONFIRMED", "LISTING_TOOL_ACCEPTED"}
_REGULATED_TERMS = (
    "health",
    "medicine",
    "medical",
    "food",
    "beverage",
    "supplement",
    "sexual wellness",
    "testing kit",
    "drug",
    "vitamin",
    "医薬",
    "医療",
    "食品",
    "サプリ",
)
_ACCESSORY_TERMS = (
    "case",
    "cover",
    "bag",
    "holder",
    "storage",
    "accessor",
    "ケース",
    "カバー",
    "収納",
)
_REPLACEMENT_TERMS = (
    "replacement",
    "spare part",
    "spare parts",
    "repair part",
    "refill part",
    "交換部品",
    "交換パーツ",
)
_SET_TERMS = (
    "bundle",
    " kit",
    " set",
    "& conditioner",
    "and conditioner",
    "セット",
    "トライアル",
    "2点",
)
_WORD = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class CategoryShadowError(RuntimeError):
    """Base error that never includes provider credentials or raw responses."""


class CategoryShadowConfigurationError(CategoryShadowError):
    """Raised when no safe local AI credential is configured."""


class CategoryShadowProviderError(CategoryShadowError):
    """Raised for an AI transport or provider failure using a safe error code."""


class CategoryShadowOutputError(CategoryShadowError):
    """Raised when a provider response cannot be accepted fail-closed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ShadowCategoryCandidate:
    """A verified local PH leaf Category eligible for an AI prompt."""

    category_id: int
    category_path: str
    source: str


@dataclass(frozen=True)
class CategoryShadowGroup:
    """A V1 UI group reduced to non-ASIN evidence for a shadow request."""

    marketplace: str
    group_key: str
    normalized_keepa_category: str
    normalized_keepa_brand: str
    canonical_product_type: str
    representative_titles: tuple[str, ...]
    resolver_titles: tuple[str, ...]
    asin_count: int
    is_main_product: bool
    is_set: bool
    is_accessory: bool
    is_replacement_part: bool
    selected_category_id: int | None
    selected_verification_status: str


@dataclass(frozen=True)
class CategoryShadowRequest:
    """Provider input containing only one group and local DB candidates."""

    group: CategoryShadowGroup
    candidates: tuple[ShadowCategoryCandidate, ...]
    prompt_version: str = PROMPT_VERSION


@dataclass(frozen=True)
class RankedCategory:
    category_id: int
    confidence: float
    short_reason: str


@dataclass(frozen=True)
class CategoryShadowResponse:
    schema_version: str
    canonical_product_type: str
    is_main_product: bool
    is_set: bool
    is_accessory: bool
    is_replacement_part: bool
    risk_flags: tuple[str, ...]
    abstain: bool
    abstain_reason: str
    ranked_candidates: tuple[RankedCategory, ...]
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    estimated_cost: float | None = None


@dataclass(frozen=True)
class ShadowPrediction:
    group: CategoryShadowGroup
    candidates: tuple[ShadowCategoryCandidate, ...]
    response: CategoryShadowResponse
    status: str
    latency_seconds: float
    cache_hit: bool

    @property
    def top1_category_id(self) -> int | None:
        return self.response.ranked_candidates[0].category_id if self.response.ranked_candidates else None

    @property
    def top3_category_ids(self) -> tuple[int, ...]:
        return tuple(candidate.category_id for candidate in self.response.ranked_candidates)

    @property
    def top1_match(self) -> bool | None:
        if self.group.selected_category_id is None:
            return None
        return self.top1_category_id == self.group.selected_category_id

    @property
    def top3_match(self) -> bool | None:
        if self.group.selected_category_id is None:
            return None
        return self.group.selected_category_id in self.top3_category_ids

    @property
    def prefilter_rank_of_selected(self) -> int | None:
        """Return the deterministic local-candidate rank for a confirmed Category."""

        selected = self.group.selected_category_id
        if selected is None:
            return None
        for rank, candidate in enumerate(self.candidates, start=1):
            if candidate.category_id == selected:
                return rank
        return None

    @property
    def ai_rank_of_selected(self) -> int | None:
        """Return the accepted AI rank for a confirmed Category, if present."""

        selected = self.group.selected_category_id
        if selected is None:
            return None
        for rank, category_id in enumerate(self.top3_category_ids, start=1):
            if category_id == selected:
                return rank
        return None

    @property
    def is_ai_request(self) -> bool:
        """Whether this run actually attempted one provider request for the group."""

        return self.status not in {"CACHED", "NO_CANDIDATE"}

    @property
    def has_valid_ai_response(self) -> bool:
        """Whether an actual request produced a locally validated structured response."""

        return self.status == "COMPLETED"


@dataclass(frozen=True)
class ShadowRunResult:
    run_id: str
    provider: str
    model: str
    prompt_version: str
    predictions: tuple[ShadowPrediction, ...]
    status: str
    started_at: str
    finished_at: str


@dataclass(frozen=True)
class ShadowRescoreResult:
    """Derived, no-provider evaluation of stored predictions against current truth."""

    evaluation_available_group_count: int
    unconfirmed_group_count: int
    evaluated_prediction_count: int
    metrics: Mapping[str, float | int | None]


class CategoryShadowProvider(Protocol):
    """Small provider boundary; the Mapper itself has no AI API dependency."""

    provider_name: str
    model: str

    def rank_categories(
        self, request: CategoryShadowRequest, *, timeout_seconds: float
    ) -> Mapping[str, Any]: ...


class FakeCategoryShadowProvider:
    """Deterministic test provider with no network or credential access."""

    provider_name = "fake"
    model = "fake-category-shadow-v1"

    def __init__(self, responses: Mapping[str, Mapping[str, Any] | Exception]) -> None:
        self.responses = dict(responses)
        self.calls: list[str] = []

    def rank_categories(
        self, request: CategoryShadowRequest, *, timeout_seconds: float
    ) -> Mapping[str, Any]:
        del timeout_seconds
        self.calls.append(request.group.group_key)
        response = self.responses.get(request.group.group_key)
        if isinstance(response, Exception):
            raise response
        if response is None:
            if not request.candidates:
                return _abstain_payload("NO_CANDIDATE")
            return _valid_payload(request.candidates[0].category_id)
        return response


class OpenAIResponsesCategoryShadowProvider:
    """One optional real provider using stdlib HTTP and the Responses API.

    Credentials live only in the process environment.  The request uses strict
    Structured Outputs and ``store: false``; no raw output is persisted locally.
    """

    provider_name = "openai_responses"

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self.model = model

    @classmethod
    def from_environment(cls) -> "OpenAIResponsesCategoryShadowProvider":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise CategoryShadowConfigurationError("OPENAI_API_KEY_MISSING")
        model = os.environ.get("OPENAI_CATEGORY_SHADOW_MODEL", "").strip() or "gpt-4o-mini"
        return cls(api_key=api_key, model=model)

    def rank_categories(
        self, request: CategoryShadowRequest, *, timeout_seconds: float
    ) -> Mapping[str, Any]:
        if not 0 < timeout_seconds <= MAX_REQUEST_SECONDS:
            raise CategoryShadowProviderError("INVALID_TIMEOUT")
        payload = {
            "model": self.model,
            "store": False,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "input": [
                {"role": "system", "content": _system_instruction()},
                {"role": "user", "content": _request_prompt(request)},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "category_shadow_rank",
                    "strict": True,
                    "schema": _response_schema(),
                }
            },
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        http_request = Request(
            "https://api.openai.com/v1/responses",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise CategoryShadowProviderError(f"HTTP_{exc.code}") from None
        except TimeoutError:
            raise CategoryShadowProviderError("TIMEOUT") from None
        except URLError:
            raise CategoryShadowProviderError("NETWORK_ERROR") from None
        except OSError:
            raise CategoryShadowProviderError("NETWORK_ERROR") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise CategoryShadowProviderError("INVALID_PROVIDER_RESPONSE") from None
        if not isinstance(decoded, Mapping):
            raise CategoryShadowProviderError("INVALID_PROVIDER_RESPONSE")
        output_text = _extract_output_text(decoded)
        try:
            structured = json.loads(output_text)
        except (TypeError, json.JSONDecodeError):
            raise CategoryShadowProviderError("INVALID_STRUCTURED_OUTPUT") from None
        if not isinstance(structured, Mapping):
            raise CategoryShadowProviderError("INVALID_STRUCTURED_OUTPUT")
        usage = decoded.get("usage") if isinstance(decoded, Mapping) else None
        result = dict(structured)
        if isinstance(usage, Mapping):
            input_details = usage.get("input_tokens_details")
            result["_usage"] = {
                "input_tokens": _nonnegative_int(usage.get("input_tokens")),
                "output_tokens": _nonnegative_int(usage.get("output_tokens")),
                "cached_tokens": _nonnegative_int(
                    input_details.get("cached_tokens") if isinstance(input_details, Mapping) else None
                ),
            }
        return result


def build_shadow_groups(
    recommendations: Sequence[MapperRecommendation],
) -> tuple[CategoryShadowGroup, ...]:
    """Create stable, product-group-only AI inputs without ASINs."""

    grouped: dict[tuple[str, str, str, str], list[MapperRecommendation]] = {}
    for item in recommendations:
        key = (
            item.marketplace,
            normalize_mapping_key(item.keepa_category),
            normalize_brand(item.keepa_brand),
            item.canonical_product_type or "UNCLASSIFIED",
        )
        grouped.setdefault(key, []).append(item)
    groups: list[CategoryShadowGroup] = []
    for (marketplace, keepa_category, keepa_brand, product_type), items in grouped.items():
        first = items[0]
        titles = _unique_text(item.product_title for item in items)[:3]
        resolver_titles = _unique_text(item.resolver_input_title for item in items)[:3]
        guard = _guard_flags(first.canonical_product_type, first.keepa_category, *titles, *resolver_titles)
        selected_id, selected_status = _selected_category(items)
        groups.append(
            CategoryShadowGroup(
                marketplace=marketplace,
                group_key=_shadow_group_key(marketplace, keepa_category, keepa_brand, product_type),
                normalized_keepa_category=keepa_category,
                normalized_keepa_brand=keepa_brand,
                canonical_product_type=first.canonical_product_type,
                representative_titles=titles,
                resolver_titles=resolver_titles,
                asin_count=len(items),
                is_main_product=guard["is_main_product"],
                is_set=guard["is_set"],
                is_accessory=guard["is_accessory"],
                is_replacement_part=guard["is_replacement_part"],
                selected_category_id=selected_id,
                selected_verification_status=selected_status,
            )
        )
    return tuple(groups)


def shadow_group_key_for_recommendation(recommendation: MapperRecommendation) -> str:
    """Return the stable non-ASIN group key used by persisted shadow predictions."""

    return _shadow_group_key(
        recommendation.marketplace,
        normalize_mapping_key(recommendation.keepa_category),
        normalize_brand(recommendation.keepa_brand),
        recommendation.canonical_product_type or "UNCLASSIFIED",
    )


def prefilter_category_candidates(
    group: CategoryShadowGroup,
    store: CategoryMapperStore,
    *,
    max_candidates: int = MAX_CANDIDATES,
) -> tuple[ShadowCategoryCandidate, ...]:
    """Rank only verified local PH leaf Categories before any AI request."""

    if group.marketplace != PH_MARKETPLACE or not 1 <= max_candidates <= MAX_CANDIDATES:
        return ()
    leaves = store.list_leaf_categories(PH_MARKETPLACE)
    by_id = {int(item["category_id"]): item for item in leaves}
    ranked: dict[int, tuple[int, set[str]]] = {}

    def add(category_id: Any, score: int, source: str) -> None:
        numeric_id = _positive_int(category_id)
        category = by_id.get(numeric_id or -1)
        if category is None or not _category_allowed_for_group(category, group):
            return
        prior_score, prior_sources = ranked.get(numeric_id, (0, set()))
        ranked[numeric_id] = (max(prior_score, score), {*prior_sources, source})

    # 1. Same-marketplace USER_CONFIRMED mapping for this normalized Keepa Category.
    for mapping in store.list_user_confirmed_category_mappings(PH_MARKETPLACE):
        if (
            str(mapping.get("mapping_key_type", "")).upper() == "KEEPA_CATEGORY"
            and str(mapping.get("mapping_key", "")) == group.normalized_keepa_category
        ):
            add(mapping.get("category_id"), 1000, "USER_CONFIRMED")
    # 2. Listing-tool accepted profile, then 3. matching confirmed product type mappings.
    profile = store.find_listing_profile(PH_MARKETPLACE, group.canonical_product_type)
    if profile is not None:
        add(profile.get("category_id"), 900, "LISTING_TOOL_ACCEPTED")
    for mapping in store.list_user_confirmed_category_mappings(PH_MARKETPLACE):
        if str(mapping.get("canonical_product_type", "")) == group.canonical_product_type:
            add(mapping.get("category_id"), 800, "CONFIRMED_PRODUCT_TYPE")

    evidence = " ".join(
        (
            group.normalized_keepa_category,
            *group.resolver_titles,
            *group.representative_titles,
        )
    )
    for category in leaves:
        text_score = _category_text_score(evidence, str(category.get("category_name", "")), str(category.get("category_path", "")))
        if text_score:
            add(category.get("category_id"), 300 + text_score, "LOCAL_TEXT_MATCH")

    # 7. Expand only inside roots already supported by a higher-priority local match.
    roots = {
        _root_name(str(by_id[category_id].get("category_path", "")))
        for category_id in ranked
        if category_id in by_id
    }
    if roots:
        for category in leaves:
            if _root_name(str(category.get("category_path", ""))) not in roots:
                continue
            proximity = _category_text_score(
                group.normalized_keepa_category,
                str(category.get("category_name", "")),
                str(category.get("category_path", "")),
            )
            if proximity:
                add(category.get("category_id"), 100 + proximity, "SAME_ROOT")

    ordinary: list[ShadowCategoryCandidate] = []
    others: list[ShadowCategoryCandidate] = []
    for category_id, (score, sources) in sorted(
        ranked.items(), key=lambda item: (-item[1][0], item[0])
    ):
        category = by_id[category_id]
        candidate = ShadowCategoryCandidate(
            category_id=category_id,
            category_path=str(category["category_path"]),
            source="+".join(sorted(sources)),
        )
        if bool(category.get("is_others")):
            if not _regulated_text(candidate.category_path) and not others:
                others.append(candidate)
        else:
            ordinary.append(candidate)
    return tuple((ordinary + others)[:max_candidates])


def validate_shadow_response(
    raw: Mapping[str, Any], *, candidate_ids: Sequence[int]
) -> CategoryShadowResponse:
    """Fail closed unless the structured response satisfies local safety rules."""

    if not isinstance(raw, Mapping):
        raise CategoryShadowOutputError("INVALID_AI_RESPONSE_TYPE")
    allowed = {int(value) for value in candidate_ids}
    required = {
        "schema_version",
        "canonical_product_type",
        "is_main_product",
        "is_set",
        "is_accessory",
        "is_replacement_part",
        "risk_flags",
        "abstain",
        "abstain_reason",
        "ranked_candidates",
    }
    if not required.issubset(raw) or any(key not in required | {"_usage"} for key in raw):
        raise CategoryShadowOutputError("INVALID_AI_SCHEMA")
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise CategoryShadowOutputError("INVALID_AI_SCHEMA_VERSION")
    bool_fields = ("is_main_product", "is_set", "is_accessory", "is_replacement_part", "abstain")
    if any(type(raw.get(field)) is not bool for field in bool_fields):
        raise CategoryShadowOutputError("INVALID_AI_BOOLEAN")
    canonical = _short_text(raw.get("canonical_product_type"), 80)
    abstain_reason = _short_text(raw.get("abstain_reason"), 280)
    risk_flags_raw = raw.get("risk_flags")
    if not isinstance(risk_flags_raw, list) or len(risk_flags_raw) > 10:
        raise CategoryShadowOutputError("INVALID_AI_RISK_FLAGS")
    risk_flags = tuple(_short_text(value, 80) for value in risk_flags_raw)
    if any(not value for value in risk_flags):
        raise CategoryShadowOutputError("INVALID_AI_RISK_FLAGS")
    ranked_raw = raw.get("ranked_candidates")
    if not isinstance(ranked_raw, list) or len(ranked_raw) > MAX_RANKED_CANDIDATES:
        raise CategoryShadowOutputError("INVALID_AI_RANKED_COUNT")
    ranked: list[RankedCategory] = []
    for item in ranked_raw:
        if not isinstance(item, Mapping) or set(item) != {"category_id", "confidence", "short_reason"}:
            raise CategoryShadowOutputError("INVALID_AI_RANKED_ITEM")
        category_id = _positive_int(item.get("category_id"))
        if category_id is None or category_id not in allowed:
            raise CategoryShadowOutputError("INVALID_AI_CATEGORY_ID")
        confidence = item.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            raise CategoryShadowOutputError("INVALID_AI_CONFIDENCE")
        reason = _short_text(item.get("short_reason"), 280)
        if not reason:
            raise CategoryShadowOutputError("INVALID_AI_REASON")
        ranked.append(RankedCategory(category_id, float(confidence), reason))
    if len({item.category_id for item in ranked}) != len(ranked):
        raise CategoryShadowOutputError("INVALID_AI_DUPLICATE_CATEGORY")
    if bool(raw["abstain"]) and ranked:
        raise CategoryShadowOutputError("INVALID_AI_ABSTAIN")
    if not bool(raw["abstain"]) and not ranked:
        raise CategoryShadowOutputError("INVALID_AI_EMPTY_RANKING")
    usage = raw.get("_usage") if isinstance(raw.get("_usage"), Mapping) else {}
    return CategoryShadowResponse(
        schema_version=SCHEMA_VERSION,
        canonical_product_type=canonical,
        is_main_product=bool(raw["is_main_product"]),
        is_set=bool(raw["is_set"]),
        is_accessory=bool(raw["is_accessory"]),
        is_replacement_part=bool(raw["is_replacement_part"]),
        risk_flags=risk_flags,
        abstain=bool(raw["abstain"]),
        abstain_reason=abstain_reason,
        ranked_candidates=tuple(ranked),
        input_tokens=_nonnegative_int(usage.get("input_tokens")),
        output_tokens=_nonnegative_int(usage.get("output_tokens")),
        cached_tokens=_nonnegative_int(usage.get("cached_tokens")),
    )


def run_category_shadow(
    *,
    recommendations: Sequence[MapperRecommendation],
    store: CategoryMapperStore,
    provider: CategoryShadowProvider,
    max_groups: int = MAX_GROUPS_PER_RUN,
    max_request_seconds: int = MAX_REQUEST_SECONDS,
    max_run_seconds: int = MAX_RUN_SECONDS,
) -> ShadowRunResult:
    """Run bounded group-level shadow ranking without touching Ver0.1 state."""

    if not 1 <= max_groups <= MAX_GROUPS_PER_RUN:
        raise ValueError("max_groups must be between 1 and 20")
    if not 1 <= max_request_seconds <= MAX_REQUEST_SECONDS:
        raise ValueError("max_request_seconds must be between 1 and 30")
    if not 1 <= max_run_seconds <= MAX_RUN_SECONDS:
        raise ValueError("max_run_seconds must be between 1 and 180")
    groups = build_shadow_groups(recommendations)[:max_groups]
    run_id = uuid4().hex
    started_at = _utc_now()
    started_clock = time.monotonic()
    store.save_ai_shadow_run(
        {
            "run_id": run_id,
            "marketplace": PH_MARKETPLACE,
            "provider": provider.provider_name,
            "model": provider.model,
            "prompt_version": PROMPT_VERSION,
            "started_at": started_at,
            "group_count": len(groups),
            "status": "RUNNING",
        }
    )
    predictions: list[ShadowPrediction] = []
    failed = False
    for group in groups:
        remaining = max_run_seconds - (time.monotonic() - started_clock)
        if remaining <= 0:
            failed = True
            break
        candidates = prefilter_category_candidates(group, store)
        candidate_ids = tuple(item.category_id for item in candidates)
        cache_key = _cache_key(group, candidate_ids, provider.provider_name, provider.model)
        cached = store.find_ai_shadow_prediction_cache(
            marketplace=PH_MARKETPLACE,
            cache_key=cache_key,
            prompt_version=PROMPT_VERSION,
            provider=provider.provider_name,
            model=provider.model,
        )
        started_group = time.monotonic()
        if cached is not None:
            try:
                response = _response_from_cached(cached, candidate_ids=candidate_ids)
            except CategoryShadowError:
                # A malformed historical cache must never prevent the normal
                # Ver0.1 workflow or a fresh bounded shadow evaluation.
                cached = None
            else:
                prediction = ShadowPrediction(group, candidates, response, "CACHED", 0.0, True)
        if cached is None and not candidates:
            response = _local_abstain_response(group, "NO_CANDIDATE", candidate_ids=())
            prediction = ShadowPrediction(group, candidates, response, "NO_CANDIDATE", 0.0, False)
        elif cached is None:
            try:
                raw = provider.rank_categories(
                    CategoryShadowRequest(group=group, candidates=candidates),
                    timeout_seconds=min(float(max_request_seconds), max(1.0, remaining)),
                )
                response = validate_shadow_response(raw, candidate_ids=candidate_ids)
                prediction = ShadowPrediction(
                    group,
                    candidates,
                    response,
                    "COMPLETED",
                    round(time.monotonic() - started_group, 3),
                    False,
                )
            except CategoryShadowOutputError as exc:
                response = _local_abstain_response(group, exc.code, candidate_ids=candidate_ids)
                prediction = ShadowPrediction(
                    group,
                    candidates,
                    response,
                    exc.code,
                    round(time.monotonic() - started_group, 3),
                    False,
                )
            except CategoryShadowProviderError as exc:
                response = _local_abstain_response(group, str(exc), candidate_ids=candidate_ids)
                prediction = ShadowPrediction(
                    group,
                    candidates,
                    response,
                    "FAILED",
                    round(time.monotonic() - started_group, 3),
                    False,
                )
                failed = True
            except Exception:
                # Provider and parsing failures must never break the existing
                # manual Category Mapper path or expose implementation details.
                response = _local_abstain_response(group, "UNEXPECTED_PROVIDER_ERROR", candidate_ids=candidate_ids)
                prediction = ShadowPrediction(
                    group,
                    candidates,
                    response,
                    "FAILED",
                    round(time.monotonic() - started_group, 3),
                    False,
                )
                failed = True
        predictions.append(prediction)
        store.save_ai_shadow_prediction(
            _prediction_record(
                run_id=run_id,
                prediction=prediction,
                provider=provider.provider_name,
                model=provider.model,
                cache_key=cache_key,
            )
        )
        if failed:
            break
    finished_at = _utc_now()
    completed = sum(item.status in {"COMPLETED", "CACHED", "NO_CANDIDATE"} for item in predictions)
    abstains = sum(item.response.abstain for item in predictions)
    ai_requests = [item for item in predictions if item.is_ai_request]
    ai_successes = [item for item in ai_requests if item.has_valid_ai_response]
    failures = len(ai_requests) - len(ai_successes)
    status = "COMPLETED" if len(predictions) == len(groups) and not failed else "PARTIAL"
    store.finish_ai_shadow_run(
        run_id,
        finished_at=finished_at,
        completed_count=completed,
        abstain_count=abstains,
        failed_count=failures,
        processed_group_count=len(predictions),
        ai_request_count=len(ai_requests),
        input_tokens=sum(item.response.input_tokens or 0 for item in ai_successes),
        output_tokens=sum(item.response.output_tokens or 0 for item in ai_successes),
        cached_tokens=sum(item.response.cached_tokens or 0 for item in ai_successes),
        estimated_cost=None,
        status=status,
    )
    return ShadowRunResult(
        run_id=run_id,
        provider=provider.provider_name,
        model=provider.model,
        prompt_version=PROMPT_VERSION,
        predictions=tuple(predictions),
        status=status,
        started_at=started_at,
        finished_at=finished_at,
    )


def shadow_kpis(predictions: Sequence[ShadowPrediction]) -> dict[str, float | int | bool | None]:
    """Return current-run-only metrics without treating local abstention as AI failure.

    The deterministic prefilter and the AI ranking are deliberately reported
    separately.  A local ``NO_CANDIDATE`` group never becomes an AI guard
    violation, an AI request, or an AI abstention.
    """

    count = len(predictions)
    confirmed = [item for item in predictions if item.group.selected_category_id is not None]
    prefilter_evaluated = [item for item in confirmed if item.prefilter_rank_of_selected is not None]
    ai_requests = [item for item in predictions if item.is_ai_request]
    ai_successes = [item for item in ai_requests if item.has_valid_ai_response]
    ai_evaluated = [item for item in ai_successes if item.group.selected_category_id is not None]
    common_evaluated = [
        item
        for item in ai_evaluated
        if item.prefilter_rank_of_selected is not None
    ]
    total_cost = [item.response.estimated_cost for item in ai_successes if item.response.estimated_cost is not None]
    latencies = [item.latency_seconds for item in ai_requests if item.latency_seconds > 0]
    no_candidate_count = sum(item.status == "NO_CANDIDATE" for item in predictions)
    ai_abstain_count = sum(item.response.abstain for item in ai_successes)
    ai_guard_violations = sum(_has_ai_guard_violation(item) for item in ai_successes)
    before_total = sum(len(item.candidates) for item in predictions)
    after_total = sum(len(item.response.ranked_candidates) for item in predictions)
    prefilter_top1 = _rate(
        sum(item.prefilter_rank_of_selected == 1 for item in prefilter_evaluated),
        len(prefilter_evaluated),
    )
    ai_top1 = _rate(sum(item.top1_match is True for item in ai_evaluated), len(ai_evaluated))
    ai_top3 = _rate(sum(item.top3_match is True for item in ai_evaluated), len(ai_evaluated))
    common_prefilter_top1 = _rate(
        sum(item.prefilter_rank_of_selected == 1 for item in common_evaluated),
        len(common_evaluated),
    )
    common_ai_top1 = _rate(
        sum(item.top1_match is True for item in common_evaluated),
        len(common_evaluated),
    )
    return {
        "processed_group_count": count,
        "evaluated_group_count": len(confirmed),
        "confirmed_group_count": len(confirmed),
        "confirmed_multi_candidate_group_count": sum(
            len(item.candidates) > 1 for item in confirmed
        ),
        "reference_data_sufficient": (
            len(confirmed) >= 10
            and sum(len(item.candidates) > 1 for item in confirmed) >= 5
        ),
        "single_candidate_group_count": sum(len(item.candidates) == 1 for item in predictions),
        "multi_candidate_group_count": sum(len(item.candidates) > 1 for item in predictions),
        "no_candidate_count": no_candidate_count,
        "local_abstain_count": no_candidate_count,
        "ai_request_count": len(ai_requests),
        "ai_success_count": len(ai_successes),
        "ai_failure_count": len(ai_requests) - len(ai_successes),
        "ai_abstain_count": ai_abstain_count,
        "prefilter_candidate_coverage": _rate(len(prefilter_evaluated), len(confirmed)),
        "prefilter_top1_accuracy": prefilter_top1,
        "ai_top1_accuracy": ai_top1,
        "ai_top3_accuracy": ai_top3,
        "top1_accuracy_lift": (
            common_ai_top1 - common_prefilter_top1
            if common_ai_top1 is not None and common_prefilter_top1 is not None
            else None
        ),
        "comparison_group_count": len(common_evaluated),
        "confirmed_category_rank_improvement_count": sum(
            item.ai_rank_of_selected is not None
            and item.prefilter_rank_of_selected is not None
            and item.ai_rank_of_selected < item.prefilter_rank_of_selected
            for item in common_evaluated
        ),
        "candidate_reduction_rate": ((before_total - after_total) / before_total) if before_total else None,
        "no_candidate_rate": _rate(no_candidate_count, count),
        "local_abstain_rate": _rate(no_candidate_count, count),
        "ai_abstain_rate": _rate(ai_abstain_count, len(ai_successes)),
        "ai_guard_violation_count": ai_guard_violations,
        "invalid_category_id_count": sum(item.status == "INVALID_AI_CATEGORY_ID" for item in predictions),
        "average_candidates_before_ai": (before_total / count) if count else 0.0,
        "average_candidates_after_ai": (after_total / count) if count else 0.0,
        "average_latency": (sum(latencies) / len(latencies)) if latencies else 0.0,
        "input_tokens": sum(item.response.input_tokens or 0 for item in ai_successes),
        "output_tokens": sum(item.response.output_tokens or 0 for item in ai_successes),
        "cached_tokens": sum(item.response.cached_tokens or 0 for item in ai_successes),
        "estimated_cost_per_100_groups": ((sum(total_cost) / len(ai_successes)) * 100) if total_cost and ai_successes else None,
        # Compatibility names used by the initial closed Ver0.2 UI.
        "candidate_coverage_rate": _rate(sum(bool(item.candidates) for item in predictions), count),
        "abstain_rate": _rate(sum(item.response.abstain for item in predictions), count),
        "top1_accuracy": ai_top1,
        "top3_accuracy": ai_top3,
        "set_or_accessory_guard_violation_count": ai_guard_violations,
    }


def rescore_saved_shadow_predictions(
    *,
    recommendations: Sequence[MapperRecommendation],
    store: CategoryMapperStore,
) -> ShadowRescoreResult:
    """Rescore stored ranks using current accepted group labels, without an AI request.

    Current recommendations contribute only explicit `USER_CONFIRMED` or
    `LISTING_TOOL_ACCEPTED` Category decisions.  The store persists those labels
    separately from a prediction, then derives idempotent evaluation records.
    """

    for group in build_shadow_groups(recommendations):
        if (
            group.selected_category_id is not None
            and group.selected_verification_status in _RESCORE_TRUTH_STATUSES
        ):
            store.save_ai_shadow_group_confirmation(
                marketplace=group.marketplace,
                group_key=group.group_key,
                category_id=group.selected_category_id,
                verification_status=group.selected_verification_status,
            )
    records = store.rescore_ai_shadow_predictions(PH_MARKETPLACE)
    availability = store.ai_shadow_rescore_availability(PH_MARKETPLACE)
    top1 = _rate(sum(record["top1_match"] is True for record in records), len(records))
    top3 = _rate(sum(record["top3_match"] is True for record in records), len(records))
    prefilter_ranked = [record for record in records if record["prefilter_rank"] is not None]
    return ShadowRescoreResult(
        evaluation_available_group_count=int(availability["evaluation_available_group_count"]),
        unconfirmed_group_count=int(availability["unconfirmed_group_count"]),
        evaluated_prediction_count=len(records),
        metrics={
            "top1_accuracy": top1,
            "top3_accuracy": top3,
            "prefilter_candidate_coverage": _rate(len(prefilter_ranked), len(records)),
            "prefilter_top1_accuracy": _rate(
                sum(record["prefilter_rank"] == 1 for record in prefilter_ranked),
                len(prefilter_ranked),
            ),
            "confirmed_category_rank_improvement_count": sum(
                record["ai_rank"] is not None
                and record["prefilter_rank"] is not None
                and int(record["ai_rank"]) < int(record["prefilter_rank"])
                for record in records
            ),
        },
    )


def _prediction_record(
    *,
    run_id: str,
    prediction: ShadowPrediction,
    provider: str,
    model: str,
    cache_key: str,
) -> dict[str, Any]:
    ranked = [
        {
            "category_id": candidate.category_id,
            "confidence": candidate.confidence,
            "short_reason": candidate.short_reason,
        }
        for candidate in prediction.response.ranked_candidates
    ]
    return {
        "run_id": run_id,
        "group_key": prediction.group.group_key,
        "marketplace": prediction.group.marketplace,
        "normalized_keepa_category": prediction.group.normalized_keepa_category,
        "normalized_keepa_brand": prediction.group.normalized_keepa_brand,
        "candidate_category_ids_json": _compact_json([item.category_id for item in prediction.candidates]),
        "ranked_candidates_json": _compact_json(ranked),
        "risk_flags_json": _compact_json(list(prediction.response.risk_flags)),
        "top1_category_id": prediction.top1_category_id,
        "top2_category_id": prediction.top3_category_ids[1] if len(prediction.top3_category_ids) > 1 else None,
        "top3_category_id": prediction.top3_category_ids[2] if len(prediction.top3_category_ids) > 2 else None,
        "top1_confidence": prediction.response.ranked_candidates[0].confidence if prediction.response.ranked_candidates else None,
        "abstain": int(prediction.response.abstain),
        "abstain_reason": prediction.response.abstain_reason,
        "selected_category_id": prediction.group.selected_category_id,
        "selected_verification_status": prediction.group.selected_verification_status,
        "top1_match": _nullable_bool(prediction.top1_match),
        "top3_match": _nullable_bool(prediction.top3_match),
        "evaluated_at": _utc_now(),
        "prompt_version": PROMPT_VERSION,
        "provider": provider,
        "model": model,
        "cache_key": cache_key,
        "status": prediction.status,
        "canonical_product_type": prediction.response.canonical_product_type,
        "is_main_product": int(prediction.response.is_main_product),
        "is_set": int(prediction.response.is_set),
        "is_accessory": int(prediction.response.is_accessory),
        "is_replacement_part": int(prediction.response.is_replacement_part),
        "latency_seconds": prediction.latency_seconds,
        "input_tokens": prediction.response.input_tokens or 0,
        "output_tokens": prediction.response.output_tokens or 0,
        "cached_tokens": prediction.response.cached_tokens or 0,
        "estimated_cost": prediction.response.estimated_cost,
    }


def _response_from_cached(
    cached: Mapping[str, Any], *, candidate_ids: Sequence[int]
) -> CategoryShadowResponse:
    try:
        ranked = json.loads(str(cached.get("ranked_candidates_json", "[]")))
        risks = json.loads(str(cached.get("risk_flags_json", "[]")))
    except json.JSONDecodeError as exc:
        raise CategoryShadowProviderError("INVALID_CACHE") from exc
    raw = {
        "schema_version": SCHEMA_VERSION,
        "canonical_product_type": str(cached.get("canonical_product_type", "")),
        "is_main_product": bool(cached.get("is_main_product")),
        "is_set": bool(cached.get("is_set")),
        "is_accessory": bool(cached.get("is_accessory")),
        "is_replacement_part": bool(cached.get("is_replacement_part")),
        "risk_flags": risks,
        "abstain": bool(cached.get("abstain")),
        "abstain_reason": str(cached.get("abstain_reason", "")),
        "ranked_candidates": ranked,
        "_usage": {
            "input_tokens": _nonnegative_int(cached.get("input_tokens")),
            "output_tokens": _nonnegative_int(cached.get("output_tokens")),
            "cached_tokens": _nonnegative_int(cached.get("cached_tokens")),
        },
    }
    return validate_shadow_response(raw, candidate_ids=candidate_ids)


def _category_allowed_for_group(category: Mapping[str, Any], group: CategoryShadowGroup) -> bool:
    if not bool(category.get("is_leaf")):
        return False
    path = str(category.get("category_path", ""))
    if _regulated_text(path) and (group.is_set or group.is_accessory or group.is_replacement_part):
        return False
    lower_path = path.casefold()
    has_accessory = any(term in lower_path for term in _ACCESSORY_TERMS)
    has_replacement = any(term in lower_path for term in _REPLACEMENT_TERMS)
    if group.is_accessory and not has_accessory:
        return False
    if group.is_replacement_part and not (has_replacement or has_accessory):
        return False
    if group.is_set and not any(term in lower_path for term in _SET_TERMS):
        return False
    if group.is_main_product and (has_accessory or has_replacement):
        return False
    return not (bool(category.get("is_others")) and _regulated_text(path))


def _category_text_score(evidence: str, category_name: str, category_path: str) -> int:
    evidence_normalized = _normalized_text(evidence)
    name_normalized = _normalized_text(category_name)
    path_normalized = _normalized_text(category_path)
    if not evidence_normalized or not name_normalized:
        return 0
    score = 0
    if name_normalized in evidence_normalized:
        score += 100
    if category_name.casefold() in evidence.casefold():
        score += 60
    evidence_words = set(_WORD.findall(evidence_normalized))
    category_words = set(_WORD.findall(name_normalized))
    score += min(40, 10 * len(evidence_words & category_words))
    for token in ("shampoo", "conditioner", "camera", "phone", "case", "toy", "shirt"):
        if token in evidence_normalized and token in path_normalized:
            score += 10
    return score


def _guard_flags(canonical_product_type: str, keepa_category: str, *texts: str) -> dict[str, bool]:
    evidence = _normalized_text(" ".join((canonical_product_type, keepa_category, *texts)))
    is_set = canonical_product_type == "SHAMPOO_CONDITIONER_SET" or any(term in evidence for term in _SET_TERMS)
    is_replacement = any(term in evidence for term in _REPLACEMENT_TERMS)
    is_accessory = not is_replacement and any(term in evidence for term in _ACCESSORY_TERMS)
    return {
        "is_main_product": not (is_set or is_accessory or is_replacement),
        "is_set": is_set,
        "is_accessory": is_accessory,
        "is_replacement_part": is_replacement,
    }


def _selected_category(items: Sequence[MapperRecommendation]) -> tuple[int | None, str]:
    ids = {
        item.recommended_category_id
        for item in items
        if item.category_is_confirmed
        and item.recommended_category_id is not None
        and item.category_verification_status in _ACCEPTED_VERIFICATION_STATUSES
    }
    statuses = {
        item.category_verification_status
        for item in items
        if item.category_is_confirmed
        and item.recommended_category_id is not None
        and item.category_verification_status in _ACCEPTED_VERIFICATION_STATUSES
    }
    if len(ids) != 1 or len(statuses) != 1:
        return None, ""
    return next(iter(ids)), next(iter(statuses))


def _system_instruction() -> str:
    return (
        "You rank only the supplied Shopee PH category candidates. Never invent, infer, or return "
        "a category ID outside the candidate list. Distinguish a main product from a case, accessory, "
        "replacement part, or set. Do not decide regulatory compliance. Do not choose Others to bypass "
        "a regulated category. If evidence is insufficient or the group is broad, abstain."
    )


def _request_prompt(request: CategoryShadowRequest) -> str:
    group = request.group
    payload = {
        "marketplace": group.marketplace,
        "normalized_keepa_category": group.normalized_keepa_category,
        "normalized_keepa_brand": group.normalized_keepa_brand,
        "representative_titles": list(group.representative_titles),
        "resolver_titles": list(group.resolver_titles),
        "canonical_product_type_candidate": group.canonical_product_type,
        "asin_count": group.asin_count,
        "flags": {
            "is_main_product": group.is_main_product,
            "is_set": group.is_set,
            "is_accessory": group.is_accessory,
            "is_replacement_part": group.is_replacement_part,
        },
        "previous_selected_category_id": group.selected_category_id,
        "previous_selected_verification_status": group.selected_verification_status,
        "candidates": [
            {"category_id": item.category_id, "category_path": item.category_path}
            for item in request.candidates
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _response_schema() -> dict[str, Any]:
    ranked_item = {
        "type": "object",
        "properties": {
            "category_id": {"type": "integer"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "short_reason": {"type": "string", "maxLength": 280},
        },
        "required": ["category_id", "confidence", "short_reason"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": [SCHEMA_VERSION]},
            "canonical_product_type": {"type": "string", "maxLength": 80},
            "is_main_product": {"type": "boolean"},
            "is_set": {"type": "boolean"},
            "is_accessory": {"type": "boolean"},
            "is_replacement_part": {"type": "boolean"},
            "risk_flags": {"type": "array", "items": {"type": "string", "maxLength": 80}, "maxItems": 10},
            "abstain": {"type": "boolean"},
            "abstain_reason": {"type": "string", "maxLength": 280},
            "ranked_candidates": {"type": "array", "items": ranked_item, "maxItems": MAX_RANKED_CANDIDATES},
        },
        "required": [
            "schema_version", "canonical_product_type", "is_main_product", "is_set",
            "is_accessory", "is_replacement_part", "risk_flags", "abstain",
            "abstain_reason", "ranked_candidates",
        ],
        "additionalProperties": False,
    }


def _extract_output_text(response: Mapping[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text
    output = response.get("output")
    if not isinstance(output, list):
        raise CategoryShadowProviderError("INVALID_PROVIDER_RESPONSE")
    for item in output:
        if not isinstance(item, Mapping):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, Mapping) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                return str(part["text"])
    raise CategoryShadowProviderError("MISSING_OUTPUT_TEXT")


def _cache_key(group: CategoryShadowGroup, candidate_ids: Sequence[int], provider: str, model: str) -> str:
    safe_input = {
        "marketplace": group.marketplace,
        "group_key": group.group_key,
        "titles": list(group.representative_titles),
        "resolver_titles": list(group.resolver_titles),
        "type": group.canonical_product_type,
        "flags": [group.is_main_product, group.is_set, group.is_accessory, group.is_replacement_part],
        "candidate_ids": sorted(int(value) for value in candidate_ids),
        "prompt_version": PROMPT_VERSION,
        "provider": provider,
        "model": model,
    }
    return sha256(_compact_json(safe_input).encode("utf-8")).hexdigest()


def _shadow_group_key(marketplace: str, category: str, brand: str, product_type: str) -> str:
    return "|".join((marketplace, category or "UNCATEGORIZED", brand or "UNBRANDED", product_type or "UNCLASSIFIED"))


def _local_abstain_response(
    group: CategoryShadowGroup, reason: str, *, candidate_ids: Sequence[int]
) -> CategoryShadowResponse:
    """Create a local fallback that preserves input-derived safety flags."""

    payload = _abstain_payload(reason)
    payload.update(
        {
            "canonical_product_type": group.canonical_product_type,
            "is_main_product": group.is_main_product,
            "is_set": group.is_set,
            "is_accessory": group.is_accessory,
            "is_replacement_part": group.is_replacement_part,
        }
    )
    return validate_shadow_response(payload, candidate_ids=candidate_ids)


def _has_ai_guard_violation(prediction: ShadowPrediction) -> bool:
    """Compare only a validated actual AI response against input-derived guards."""

    return any(
        (
            prediction.group.is_main_product != prediction.response.is_main_product,
            prediction.group.is_set != prediction.response.is_set,
            prediction.group.is_accessory != prediction.response.is_accessory,
            prediction.group.is_replacement_part != prediction.response.is_replacement_part,
        )
    )


def _abstain_payload(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "canonical_product_type": "",
        "is_main_product": False,
        "is_set": False,
        "is_accessory": False,
        "is_replacement_part": False,
        "risk_flags": [],
        "abstain": True,
        "abstain_reason": reason,
        "ranked_candidates": [],
    }


def _valid_payload(category_id: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "canonical_product_type": "",
        "is_main_product": True,
        "is_set": False,
        "is_accessory": False,
        "is_replacement_part": False,
        "risk_flags": [],
        "abstain": False,
        "abstain_reason": "",
        "ranked_candidates": [{"category_id": category_id, "confidence": 0.8, "short_reason": "Candidate matches supplied product evidence."}],
    }


def _unique_text(values: Sequence[str] | Any) -> tuple[str, ...]:
    collected: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in collected:
            collected.append(text)
    return tuple(collected)


def _normalized_text(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def _regulated_text(value: str) -> bool:
    normalized = _normalized_text(value)
    return any(term in normalized for term in _REGULATED_TERMS)


def _root_name(path: str) -> str:
    return path.split(">", 1)[0].strip()


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _short_text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _nullable_bool(value: bool | None) -> int | None:
    return None if value is None else int(value)


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
