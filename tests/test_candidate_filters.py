"""Offline F01-F03, cache-age and F08 review-CSV contracts."""

from copy import deepcopy
import csv
from datetime import datetime, timedelta, timezone
import hashlib
from io import StringIO

import pytest

from modules.candidate_filters import (
    FilterCriteria,
    INVALID,
    MATCH,
    NO_AMAZON_OFFER,
    NOT_CAPTURED,
    NOT_SPECIFIED,
    OUT_OF_RANGE,
    STALE,
    UNKNOWN,
    confirmation_csv_bytes,
    evaluate_product,
    extract_keepa_observation,
    observation_needs_capture,
    partition_rows,
)


ASIN = "B000000001"
NOW = datetime(2026, 10, 15, 3, 0, tzinfo=timezone.utc)


def raw_product(price=1000, rating=45):
    # Synthetic raw/SDK stats.current contract: AMAZON=0, SALES=3,
    # RATING=16 (tenths). SDK converted data deliberately disagrees.
    current = [-1] * 34
    current[0], current[1], current[3], current[16], current[17], current[18] = (
        price, 200, 999999, rating, 45000, 800
    )
    return {
        "asin": ASIN,
        "domainId": 5,
        "stats": {"current": current, "avg": [99900] * 34},
        "csv": [[100, 99900]],
        "data": {"AMAZON": [999.0], "RATING": [1.0]},
        "availabilityAmazon": 0,
        "lastUpdate": 8300000,
        "lastRatingUpdate": 8299999,
    }


def observed(price=1000, rating=45, *, captured_at=NOW, **flags):
    raw = raw_product(price, rating)
    return {
        "asin": ASIN,
        "candidate_observation": extract_keepa_observation(
            raw, captured_at=captured_at, **flags
        ),
    }


@pytest.mark.parametrize(
    "price,criteria,expected",
    [
        (999, FilterCriteria(price_min_jpy=1000), OUT_OF_RANGE),
        (1000, FilterCriteria(price_min_jpy=1000), MATCH),
        (5000, FilterCriteria(price_max_jpy=5000), MATCH),
        (5001, FilterCriteria(price_max_jpy=5000), OUT_OF_RANGE),
        (999, FilterCriteria(1000, 5000), OUT_OF_RANGE),
        (1000, FilterCriteria(1000, 5000), MATCH),
        (5000, FilterCriteria(1000, 5000), MATCH),
        (5001, FilterCriteria(1000, 5000), OUT_OF_RANGE),
        (100000, FilterCriteria(), MATCH),
    ],
)
def test_f01_price_bounds_are_inclusive_and_optional(price, criteria, expected):
    result = evaluate_product(observed(price), criteria, now=NOW)
    assert result.status == expected
    assert result.observation["price_jpy"] == price


@pytest.mark.parametrize(
    "kwargs",
    [
        {"price_min_jpy": -1}, {"price_max_jpy": -1},
        {"price_min_jpy": 1000, "price_max_jpy": 999},
        {"price_min_jpy": 1.5}, {"price_max_jpy": True},
        {"rating_min": 3.9}, {"rating_min": 5.0},
        {"rating_min": True}, {"rating_min": float("nan")},
        {"rating_min": complex(4, 0)},
    ],
)
def test_f01_invalid_criteria_are_rejected_before_any_acquisition(kwargs):
    with pytest.raises(ValueError):
        FilterCriteria(**kwargs)


@pytest.mark.parametrize(
    "raw_rating,minimum,expected",
    [(39, 4.0, OUT_OF_RANGE), (40, 4.0, MATCH), (44, 4.5, OUT_OF_RANGE),
     (45, 4.5, MATCH), (50, 4.5, MATCH), (0, 4.0, OUT_OF_RANGE)],
)
def test_f02_rating_tenths_and_thresholds(raw_rating, minimum, expected):
    product = observed(rating=raw_rating)
    result = evaluate_product(product, FilterCriteria(rating_min=minimum), now=NOW)
    assert result.status == expected
    assert result.observation["rating"] == raw_rating / 10


@pytest.mark.parametrize("rating", [None, -1, -2, -3, 51, 4.5, True, "45", float("nan")])
def test_f02_missing_sentinel_or_invalid_rating_never_matches(rating):
    result = evaluate_product(observed(rating=rating), FilterCriteria(rating_min=4), now=NOW)
    assert result.status == UNKNOWN
    assert result.rating_reason
    assert result.observation["rating"] is None


def test_f01_f02_uses_raw_current_only_without_price_or_rank_fallbacks():
    raw = raw_product(price=-2, rating=-1)
    raw["availabilityAmazon"] = 2
    raw["rating"] = 5
    raw["buyBoxPrice"] = 1000
    raw["reviews"] = {"rating": 5}
    observation = extract_keepa_observation(raw, captured_at=NOW)
    result = evaluate_product(
        {"asin": ASIN, "candidate_observation": observation}, FilterCriteria(1000, 5000, 4.5), now=NOW
    )
    assert result.status == UNKNOWN
    assert observation["price_jpy"] is None
    assert observation["rating"] is None


@pytest.mark.parametrize("current", [[], [1000], [-1] * 16, None])
def test_f02_absent_rating_array_index_is_unknown(current):
    raw = raw_product()
    raw["stats"]["current"] = current
    observation = extract_keepa_observation(raw, captured_at=NOW)
    result = evaluate_product(
        {"asin": ASIN, "candidate_observation": observation}, FilterCriteria(rating_min=4.5), now=NOW
    )
    assert result.status == UNKNOWN


@pytest.mark.parametrize("stats", ["invalid", {"current": "1000"}, {"current": {"0": 1000}}])
def test_malformed_stats_do_not_match(stats):
    raw = raw_product()
    raw["stats"] = stats
    observation = extract_keepa_observation(raw, captured_at=NOW)
    assert observation["price_status"] == INVALID
    assert observation["rating_status"] == INVALID


def test_f03_amazon_no_offer_is_distinct_from_missing_and_outside():
    no_offer = observed(price=-1)
    missing = observed(price=None)
    outside = observed(price=999)
    criteria = FilterCriteria(price_min_jpy=1000)
    results = [evaluate_product(product, criteria, now=NOW) for product in (no_offer, missing, outside)]
    assert [(result.status, result.price_reason) for result in results] == [
        (UNKNOWN, NO_AMAZON_OFFER), (UNKNOWN, "AMAZON_PRICE_UNAVAILABLE"),
        (OUT_OF_RANGE, "BELOW_PRICE_MIN"),
    ]


def test_f03_availability_without_price_proves_no_offer_only_when_explicit():
    raw = raw_product(price=None)
    raw["availabilityAmazon"] = -1
    assert extract_keepa_observation(raw, captured_at=NOW)["price_status"] == NO_AMAZON_OFFER
    raw["availabilityAmazon"] = 2
    assert extract_keepa_observation(raw, captured_at=NOW)["price_status"] == NOT_CAPTURED
    raw["availabilityAmazon"] = -1
    raw["stats"]["current"][0] = 1000
    assert extract_keepa_observation(raw, captured_at=NOW)["price_status"] == INVALID


def test_contradictory_cached_observation_is_not_promoted_to_match():
    product = observed()
    product["candidate_observation"]["availability_amazon"] = -1
    result = evaluate_product(product, FilterCriteria(price_min_jpy=1000), now=NOW)
    assert result.status == UNKNOWN
    assert result.price_reason == INVALID


@pytest.mark.parametrize("price", [0, -3, 1000.5, True, "1000", float("inf")])
def test_invalid_price_never_matches(price):
    result = evaluate_product(observed(price), FilterCriteria(price_max_jpy=5000), now=NOW)
    assert result.status == UNKNOWN
    assert result.observation["price_status"] == INVALID


@pytest.mark.parametrize(
    "price,rating,criteria,expected",
    [(1000, 45, FilterCriteria(1000, 5000, 4.5), MATCH),
     (1000, None, FilterCriteria(1000, 5000, 4.5), UNKNOWN),
     (None, 45, FilterCriteria(1000, 5000, 4.5), UNKNOWN),
     (None, 39, FilterCriteria(1000, 5000, 4.0), OUT_OF_RANGE),
     (5001, None, FilterCriteria(1000, 5000, 4.0), OUT_OF_RANGE),
     (None, None, FilterCriteria(1000, 5000, 4.0), UNKNOWN),
     (1000, None, FilterCriteria(1000, 5000), MATCH),
     (None, 45, FilterCriteria(rating_min=4.5), MATCH)],
)
def test_f03_and_with_outside_priority_and_independent_unspecified_fields(price, rating, criteria, expected):
    assert evaluate_product(observed(price, rating), criteria, now=NOW).status == expected


def test_outside_priority_retains_both_field_reasons():
    result = evaluate_product(observed(price=-1, rating=39), FilterCriteria(1000, 5000, 4), now=NOW)
    assert result.status == OUT_OF_RANGE
    assert result.price_status == UNKNOWN
    assert result.rating_status == OUT_OF_RANGE
    assert result.reasons == (NO_AMAZON_OFFER, "BELOW_RATING_MIN")


def test_no_conditions_preserves_even_legacy_or_bad_observations():
    for product in ({}, {"asin": ASIN}, {"candidate_observation": {"bad": "legacy"}}):
        result = evaluate_product(product, FilterCriteria(), now=NOW)
        assert result.status == MATCH
        assert result.price_status == result.rating_status == NOT_SPECIFIED
        assert not observation_needs_capture(product, FilterCriteria(), now=NOW)


@pytest.mark.parametrize("domain", [None, 1, "5", True])
def test_wrong_or_unknown_jp_source_is_unknown(domain):
    raw = raw_product()
    raw["domainId"] = domain
    observation = extract_keepa_observation(raw, captured_at=NOW)
    result = evaluate_product(
        {"asin": ASIN, "candidate_observation": observation}, FilterCriteria(1000, 5000, 4), now=NOW
    )
    assert result.status == UNKNOWN


def test_other_product_observation_is_never_borrowed():
    product = observed()
    product["asin"] = "B000000002"
    result = evaluate_product(product, FilterCriteria(price_min_jpy=1000), now=NOW)
    assert result.status == UNKNOWN
    assert result.price_reason == "OBSERVATION_IDENTITY_INVALID"


def test_f04_seven_day_cache_age_boundary_and_per_field_capture_age():
    at_boundary = observed(captured_at=NOW - timedelta(days=7))
    criteria = FilterCriteria(1000, 5000, 4.5)
    assert evaluate_product(at_boundary, criteria, now=NOW).status == MATCH
    after = NOW + timedelta(microseconds=1)
    result = evaluate_product(at_boundary, criteria, now=after)
    assert result.status == UNKNOWN
    assert result.price_reason == result.rating_reason == STALE
    assert observation_needs_capture(at_boundary, criteria, now=after)
    mixed_age = observed()
    mixed_age["candidate_observation"]["rating_captured_at"] = (NOW - timedelta(days=8)).isoformat()
    assert evaluate_product(mixed_age, FilterCriteria(1000, 5000), now=NOW).status == MATCH
    assert evaluate_product(mixed_age, criteria, now=NOW).rating_reason == STALE


@pytest.mark.parametrize("timestamp", ["", "invalid", "2026-10-15T03:00:00", NOW + timedelta(days=1)])
def test_f08_unknown_invalid_future_capture_time_never_matches(timestamp):
    product = observed(captured_at=timestamp)
    assert evaluate_product(product, FilterCriteria(1000, 5000), now=NOW).status == UNKNOWN


def test_f04_refill_distinguishes_uncaptured_and_captured_absence():
    criteria = FilterCriteria(1000, 5000, 4.5)
    assert observation_needs_capture({"asin": ASIN}, criteria, now=NOW)
    assert observation_needs_capture({"asin": ASIN, "candidate_observation": {}}, criteria, now=NOW)
    assert observation_needs_capture(observed(rating_requested=False), criteria, now=NOW)
    assert not observation_needs_capture(observed(price=-1, rating=None), criteria, now=NOW)
    assert not observation_needs_capture(observed(price=0, rating=99), criteria, now=NOW)


def test_equivalent_criteria_have_the_same_result_identity():
    assert FilterCriteria(rating_min=4).fingerprint == FilterCriteria(rating_min=4.0).fingerprint


def test_f04_conditions_reuse_observation_without_mutating_it():
    product = observed()
    before = deepcopy(product)
    first = evaluate_product(product, FilterCriteria(1000, 5000, 4.0), now=NOW)
    second = evaluate_product(product, FilterCriteria(1001, 5000, 4.5), now=NOW)
    assert first.status == MATCH and second.status == OUT_OF_RANGE
    assert first.observation_fingerprint == second.observation_fingerprint
    assert first.fingerprint != second.fingerprint
    assert product == before


def test_f06_partition_keeps_resolver_source_ids_duplicate_rows_and_order():
    rows = [
        {"source_id": "row-2", "asin": ASIN},
        {"source_id": "row-1", "asin": ASIN},
        {"source_id": "row-3", "asin": "B000000003"},
    ]
    partition = partition_rows(rows, {ASIN: observed()}, FilterCriteria(1000, 5000, 4.5), now=NOW)
    assert partition.matched_rows == rows[:2]
    assert partition.matched_rows[0] is rows[0]
    assert partition.unknown_rows == rows[2:]
    assert partition.counts == {MATCH: 2, OUT_OF_RANGE: 0, UNKNOWN: 1}
    assert [item.row["source_id"] for item in partition.evaluations] == ["row-2", "row-1", "row-3"]


def test_f06_row_observations_never_borrow_freshness_from_a_duplicate_asin():
    legacy = {"source_id": "old", "asin": ASIN}
    current = {**observed(), "source_id": "current"}
    partition = partition_rows([legacy, current], None, FilterCriteria(price_min_jpy=1000), now=NOW)
    assert partition.matched_rows == [current]
    assert partition.unknown_rows == [legacy]


def test_f08_confirmation_csv_bom_identity_values_reasons_times_and_market_separation():
    rows = [
        {"source_id": "入力1", "asin": ASIN},
        {"source_id": "入力2", "asin": ASIN},
        {"source_id": "入力3", "asin": "B000000003"},
    ]
    candidate = b"exact current fifteen column Candidate bytes"
    criteria = FilterCriteria(1000, 5000, 4.5)
    content = confirmation_csv_bytes(
        rows, criteria, candidate, products_by_asin={ASIN: observed()}, marketplace="SG", now=NOW
    )
    assert content.startswith(b"\xef\xbb\xbf")
    records = list(csv.DictReader(StringIO(content.decode("utf-8-sig"))))
    assert [record["source_id"] for record in records] == ["入力1", "入力2", "入力3"]
    first = records[0]
    assert first["candidate_sha256"] == hashlib.sha256(candidate).hexdigest()
    assert first["criteria_fingerprint"] == criteria.fingerprint
    assert first["marketplace"] == "SG" and first["source_marketplace"] == "JP"
    assert first["amazon_reference_price_jpy"] == "1000"
    assert first["average_rating"] == "4.5"
    assert first["captured_at"] == NOW.isoformat()
    assert first["provider_updated_at"] and first["rating_updated_at"]
    assert first["reference_only"] == "TRUE"
    assert records[2]["result"] == UNKNOWN
    assert records[2]["price_reason"] == NOT_CAPTURED
    assert records[2]["amazon_reference_price_jpy"] == ""


def test_f08_zero_matches_does_not_claim_old_candidate_sha():
    content = confirmation_csv_bytes(
        [observed(price=999)], FilterCriteria(price_min_jpy=1000), now=NOW
    )
    records = list(csv.DictReader(StringIO(content.decode("utf-8-sig"))))
    assert records[0]["result"] == OUT_OF_RANGE
    assert records[0]["candidate_sha256"] == ""
