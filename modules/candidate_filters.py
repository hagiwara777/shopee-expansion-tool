"""Small, market-independent Amazon JP price/rating candidate selection.

Only raw Keepa ``stats.current`` observations are interpreted here. This module
does not fetch products, judge Safety, or change the Candidate CSV contract.
"""

from __future__ import annotations

import csv
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from io import StringIO
import json
import math
from numbers import Integral, Real
import re
from typing import Any, Iterable, Mapping


OBSERVATION_SCHEMA_VERSION = "CANDIDATE_OBSERVATION_V1"
FILTER_VERSION = "CANDIDATE_FILTERS_V1"
OBSERVATION_TTL = timedelta(days=7)
MATCH = "MATCH"
OUT_OF_RANGE = "OUT_OF_RANGE"
UNKNOWN = "UNKNOWN"
NOT_SPECIFIED = "NOT_SPECIFIED"
OBSERVED = "OBSERVED"
NOT_CAPTURED = "NOT_CAPTURED"
NO_AMAZON_OFFER = "NO_AMAZON_OFFER"
INVALID = "INVALID"
STALE = "STALE"
_ASIN = re.compile(r"^[A-Z0-9]{10}$")
_OBSERVATION_STATUSES = {OBSERVED, NOT_CAPTURED, NO_AMAZON_OFFER, INVALID}


@dataclass(frozen=True)
class FilterCriteria:
    price_min_jpy: int | None = None
    price_max_jpy: int | None = None
    rating_min: float | None = None

    def __post_init__(self) -> None:
        for field in ("price_min_jpy", "price_max_jpy"):
            value = getattr(self, field)
            if value is not None and (not _integer(value) or value < 0):
                raise ValueError("価格は0以上の整数（円）で指定してください。")
            if value is not None:
                object.__setattr__(self, field, int(value))
        if (
            self.price_min_jpy is not None
            and self.price_max_jpy is not None
            and self.price_min_jpy > self.price_max_jpy
        ):
            raise ValueError("価格下限は上限以下にしてください。")
        if self.rating_min is not None and (
            isinstance(self.rating_min, bool) or not isinstance(self.rating_min, Real)
            or self.rating_min not in (4.0, 4.5)
        ):
            raise ValueError("最低平均評価は指定なし・4.0・4.5から選択してください。")
        if self.rating_min is not None:
            object.__setattr__(self, "rating_min", float(self.rating_min))

    @property
    def price_active(self) -> bool:
        return self.price_min_jpy is not None or self.price_max_jpy is not None

    @property
    def rating_active(self) -> bool:
        return self.rating_min is not None

    @property
    def active(self) -> bool:
        return self.price_active or self.rating_active

    def to_dict(self) -> dict[str, int | float | None]:
        return {
            "price_min_jpy": self.price_min_jpy,
            "price_max_jpy": self.price_max_jpy,
            "rating_min": self.rating_min,
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint({"version": FILTER_VERSION, **self.to_dict()})


@dataclass(frozen=True)
class FilterEvaluation:
    status: str
    price_status: str
    rating_status: str
    price_reason: str
    rating_reason: str
    observation: Mapping[str, Any]
    observation_fingerprint: str
    fingerprint: str

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(
            reason
            for reason in (self.price_reason, self.rating_reason)
            if reason and reason != NOT_SPECIFIED
        )


@dataclass(frozen=True)
class RowFilterResult:
    row: Any
    asin: str
    evaluation: FilterEvaluation


@dataclass(frozen=True)
class PartitionResult:
    matched_rows: list[Any]
    out_of_range_rows: list[Any]
    unknown_rows: list[Any]
    evaluations: list[RowFilterResult]

    @property
    def counts(self) -> dict[str, int]:
        return {
            MATCH: len(self.matched_rows),
            OUT_OF_RANGE: len(self.out_of_range_rows),
            UNKNOWN: len(self.unknown_rows),
        }


def extract_keepa_observation(
    product: Mapping[str, Any],
    *,
    captured_at: str | datetime,
    price_requested: bool = True,
    rating_requested: bool = True,
) -> dict[str, Any]:
    """Capture current AMAZON yen/index 0 and RATING tenths/index 16.

    Keepa's JP smallest currency unit is one yen. SDK ``data`` arrays, NEW,
    Buy Box, historical last-known prices and review counts are never fallbacks.
    Missing requested data is retained as an observation, preventing automatic
    repeated fetching of an observed missing price or rating.
    """
    asin = _asin(product.get("asin"))
    capture = _parse_time(captured_at)
    domain = product.get("domainId")
    identity_valid = bool(asin) and _integer(domain) and domain == 5
    availability = product.get("availabilityAmazon")
    availability = int(availability) if _integer(availability) else None
    result: dict[str, Any] = {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "provider": "KEEPA",
        "asin": asin,
        "domain_id": int(domain) if _integer(domain) else None,
        "source_marketplace": "JP" if domain == 5 else "",
        "captured_at": _iso(capture) if capture else "",
        "availability_amazon": availability,
        "provider_updated_at": _keepa_time(product.get("lastUpdate")),
        "rating_updated_at": _keepa_time(product.get("lastRatingUpdate")),
    }
    for field, requested, index in (
        ("price", price_requested, 0), ("rating", rating_requested, 16)
    ):
        value_key = "price_jpy" if field == "price" else "rating"
        result[value_key] = None
        result[f"{field}_captured_at"] = result["captured_at"] if requested else ""
        status, reason = NOT_CAPTURED, NOT_CAPTURED
        if requested:
            if not identity_valid:
                status, reason = INVALID, "PRODUCT_IDENTITY_INVALID"
            elif capture is None:
                status, reason = INVALID, "CAPTURE_TIME_INVALID"
            else:
                value, malformed = _current_value(product, index)
                if malformed:
                    status, reason = INVALID, "CURRENT_VALUE_INVALID"
                elif field == "price":
                    if availability == -1 and value not in (None, -1, -2):
                        status, reason = INVALID, "AMAZON_AVAILABILITY_CONFLICT"
                    elif value == -1 or availability == -1:
                        status, reason = NO_AMAZON_OFFER, NO_AMAZON_OFFER
                    elif value is None or value == -2:
                        status, reason = NOT_CAPTURED, "AMAZON_PRICE_UNAVAILABLE"
                    elif not _integer(value) or value <= 0:
                        status, reason = INVALID, "AMAZON_PRICE_INVALID"
                    else:
                        result[value_key] = int(value)
                        status, reason = OBSERVED, ""
                elif value is None or value in (-1, -2):
                    status, reason = NOT_CAPTURED, "RATING_UNAVAILABLE"
                elif not _integer(value) or not 0 <= value <= 50:
                    status, reason = INVALID, "RATING_INVALID"
                else:
                    result[value_key] = int(value) / 10
                    status, reason = OBSERVED, ""
        result[f"{field}_status"] = status
        result[f"{field}_reason"] = reason
        result[f"{field}_requested"] = bool(requested)
    return result


def evaluate_product(
    product: Mapping[str, Any] | None,
    criteria: FilterCriteria,
    *,
    now: str | datetime | None = None,
) -> FilterEvaluation:
    """Evaluate the requested fields independently, then AND their results."""
    product = product or {}
    candidate = product.get("candidate_observation")
    observation = deepcopy(dict(candidate)) if isinstance(candidate, Mapping) else {}
    current_time = _now(now)
    price_status, price_reason = _evaluate_field(
        product, observation, "price", criteria.price_active, current_time
    )
    rating_status, rating_reason = _evaluate_field(
        product, observation, "rating", criteria.rating_active, current_time
    )
    if price_status == MATCH:
        price = observation["price_jpy"]
        if criteria.price_min_jpy is not None and price < criteria.price_min_jpy:
            price_status, price_reason = OUT_OF_RANGE, "BELOW_PRICE_MIN"
        elif criteria.price_max_jpy is not None and price > criteria.price_max_jpy:
            price_status, price_reason = OUT_OF_RANGE, "ABOVE_PRICE_MAX"
    if rating_status == MATCH and observation["rating"] < criteria.rating_min:
        rating_status, rating_reason = OUT_OF_RANGE, "BELOW_RATING_MIN"
    statuses = (price_status, rating_status)
    status = OUT_OF_RANGE if OUT_OF_RANGE in statuses else UNKNOWN if UNKNOWN in statuses else MATCH
    observation_hash = _fingerprint(observation)
    result_hash = _fingerprint({
        "version": FILTER_VERSION,
        "criteria": criteria.fingerprint,
        "observation": observation_hash,
        "status": status,
        "price_status": price_status,
        "rating_status": rating_status,
        "price_reason": price_reason,
        "rating_reason": rating_reason,
    })
    return FilterEvaluation(
        status, price_status, rating_status, price_reason, rating_reason,
        observation, observation_hash, result_hash,
    )


def observation_needs_capture(
    product: Mapping[str, Any] | None,
    criteria: FilterCriteria,
    *,
    now: str | datetime | None = None,
) -> bool:
    """Plan explicit refill only for uncaptured/expired requested observations.

    Captured missing values and invalid observations are shown for review. They
    do not cause a repeat fetch merely because they failed to match a filter.
    """
    if not criteria.active:
        return False
    product = product or {}
    observation = product.get("candidate_observation")
    if not isinstance(observation, Mapping) or not observation:
        return True
    evaluation = evaluate_product(product, criteria, now=now)
    for field, active, reason in (
        ("price", criteria.price_active, evaluation.price_reason),
        ("rating", criteria.rating_active, evaluation.rating_reason),
    ):
        if active and (
            reason == STALE
            or (observation.get(f"{field}_status") == NOT_CAPTURED
                and not observation.get(f"{field}_requested", False))
        ):
            return True
    return False


def partition_rows(
    rows: Iterable[Any],
    products_by_asin: Mapping[str, Mapping[str, Any]] | None,
    criteria: FilterCriteria,
    *,
    now: str | datetime | None = None,
) -> PartitionResult:
    """Keep original row order, source IDs and duplicate Resolver rows."""
    groups: dict[str, list[Any]] = {MATCH: [], OUT_OF_RANGE: [], UNKNOWN: []}
    evaluations = []
    for row in rows:
        values = _row_mapping(row)
        asin = _asin(values.get("candidate_asin") or values.get("asin"))
        product = dict(products_by_asin.get(asin, {})) if products_by_asin is not None else dict(values)
        # The row's ASIN is the binding target, even if the supplied product is wrong.
        product["asin"] = asin
        evaluation = evaluate_product(product, criteria, now=now)
        groups[evaluation.status].append(row)
        evaluations.append(RowFilterResult(row, asin, evaluation))
    return PartitionResult(groups[MATCH], groups[OUT_OF_RANGE], groups[UNKNOWN], evaluations)


def confirmation_csv_bytes(
    rows: Iterable[Any],
    criteria: FilterCriteria,
    candidate_content: bytes = b"",
    *,
    products_by_asin: Mapping[str, Mapping[str, Any]] | None = None,
    marketplace: str = "",
    now: str | datetime | None = None,
) -> bytes:
    """Build a separate UTF-8 BOM review CSV; this is never Gate/Safety input."""
    columns = (
        "schema_version", "marketplace", "source_id", "asin", "criteria_fingerprint",
        "observation_fingerprint", "result_fingerprint", "candidate_sha256",
        "price_min_jpy", "price_max_jpy", "rating_min", "result",
        "price_result", "price_reason", "rating_result", "rating_reason",
        "amazon_reference_price_jpy", "average_rating", "price_capture_status",
        "rating_capture_status", "captured_at", "price_captured_at", "rating_captured_at",
        "provider_updated_at", "rating_updated_at", "provider", "source_marketplace",
        "availability_amazon", "reference_only",
    )
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\r\n")
    writer.writeheader()
    candidate_sha = hashlib.sha256(candidate_content).hexdigest() if candidate_content else ""
    partition = partition_rows(rows, products_by_asin, criteria, now=now)
    for item in partition.evaluations:
        result, observation = item.evaluation, item.evaluation.observation
        writer.writerow({
            "schema_version": FILTER_VERSION,
            "marketplace": marketplace,
            "source_id": _row_mapping(item.row).get("source_id", ""),
            "asin": item.asin,
            "criteria_fingerprint": criteria.fingerprint,
            "observation_fingerprint": result.observation_fingerprint,
            "result_fingerprint": result.fingerprint,
            "candidate_sha256": candidate_sha,
            **criteria.to_dict(),
            "result": result.status,
            "price_result": result.price_status,
            "price_reason": result.price_reason,
            "rating_result": result.rating_status,
            "rating_reason": result.rating_reason,
            "amazon_reference_price_jpy": observation.get("price_jpy"),
            "average_rating": observation.get("rating"),
            "price_capture_status": observation.get("price_status", NOT_CAPTURED),
            "rating_capture_status": observation.get("rating_status", NOT_CAPTURED),
            **{key: observation.get(key, "") for key in (
                "captured_at", "price_captured_at", "rating_captured_at", "provider_updated_at",
                "rating_updated_at", "provider", "source_marketplace", "availability_amazon",
            )},
            "reference_only": "TRUE",
        })
    return stream.getvalue().encode("utf-8-sig")


def _evaluate_field(
    product: Mapping[str, Any], observation: Mapping[str, Any], field: str,
    active: bool, now: datetime,
) -> tuple[str, str]:
    if not active:
        return NOT_SPECIFIED, NOT_SPECIFIED
    if not observation:
        return UNKNOWN, NOT_CAPTURED
    if (
        observation.get("schema_version") != OBSERVATION_SCHEMA_VERSION
        or observation.get("provider") != "KEEPA"
        or observation.get("domain_id") != 5
        or observation.get("source_marketplace") != "JP"
        or not _asin(product.get("asin") or product.get("candidate_asin"))
        or observation.get("asin") != _asin(product.get("asin") or product.get("candidate_asin"))
    ):
        return UNKNOWN, "OBSERVATION_IDENTITY_INVALID"
    status = observation.get(f"{field}_status")
    if status not in _OBSERVATION_STATUSES or (field == "rating" and status == NO_AMAZON_OFFER):
        return UNKNOWN, INVALID
    captured = _parse_time(observation.get(f"{field}_captured_at", observation.get("captured_at")))
    if captured is None:
        return UNKNOWN, NOT_CAPTURED if status == NOT_CAPTURED else "CAPTURE_TIME_INVALID"
    if captured > now:
        return UNKNOWN, "CAPTURE_TIME_INVALID"
    if now - captured > OBSERVATION_TTL:
        return UNKNOWN, STALE
    if status != OBSERVED:
        return UNKNOWN, str(observation.get(f"{field}_reason") or status)
    value = observation.get("price_jpy" if field == "price" else "rating")
    if field == "price":
        if not _integer(value) or value <= 0 or observation.get("availability_amazon") == -1:
            return UNKNOWN, INVALID
    elif (
        isinstance(value, bool) or not isinstance(value, Real)
        or not math.isfinite(value) or not 0 <= value <= 5
        or round(value * 10) != value * 10
    ):
        return UNKNOWN, INVALID
    return MATCH, ""


def _current_value(product: Mapping[str, Any], index: int) -> tuple[Any, bool]:
    stats = product.get("stats")
    if stats is None:
        return None, False
    if not isinstance(stats, Mapping):
        return None, True
    values = stats.get("current")
    if values is None:
        return None, False
    if not isinstance(values, (list, tuple)):
        return None, True
    return (values[index], False) if len(values) > index else (None, False)


def _integer(value: Any) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _asin(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text if _ASIN.fullmatch(text) else ""


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str) and value:
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if result.tzinfo is None:
        return None
    return result.astimezone(timezone.utc)


def _now(value: str | datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    result = _parse_time(value)
    if result is None:
        raise ValueError("判定時刻はtimezone付きで指定してください。")
    return result


def _iso(value: datetime) -> str:
    return value.isoformat()


def _keepa_time(value: Any) -> str:
    if not _integer(value) or value <= 0:
        return ""
    try:
        return _iso(datetime(2011, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=int(value)))
    except OverflowError:
        return ""


def _row_mapping(row: Any) -> Mapping[str, Any]:
    return row if isinstance(row, Mapping) else vars(row)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    ).encode("utf-8")).hexdigest()
