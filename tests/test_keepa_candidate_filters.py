"""F04/F05/F07/F08 offline acquisition and cache contracts; no live API."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from modules.cache import KeepaCache, utc_now_iso
from modules.candidate_filters import FilterCriteria, MATCH, evaluate_product, extract_keepa_observation
from modules.keepa_client import (
    KeepaDataError, KeepaExpansionClient, KeepaTokenError, estimate_token_usage,
)


SEED = "B000000000"
FIRST = "B000000001"
SECOND = "B000000002"


@pytest.fixture
def keepa_raw_product():
    # Synthetic raw Product/Statistics fixture following official references:
    # https://keepa.com/api-docs/product.html (stats, rating, history)
    # https://keepa.com/api-docs/product-object.html (JP yen, type indices)
    # https://keepa.com/api-docs/statistics-object.html (current raw values)
    current = [-1] * 37
    current[0], current[1], current[3], current[16], current[17] = 1000, 500, 9, 45, 9999
    return {
        "asin": FIRST, "domainId": 5, "title": "Synthetic candidate", "brand": "Fixture",
        "categoryTree": [{"catId": 100, "name": "Fixture leaf"}],
        "stats": {"current": current}, "availabilityAmazon": 0,
        "description": ["Existing safety fact"],
    }


class FakeApi:
    def __init__(self, product, *, tokens=1000):
        self.product = deepcopy(product)
        self.tokens_left = tokens
        self.query_calls = []
        self.finder_calls = []

    def query(self, items, **kwargs):
        self.query_calls.append((items, kwargs))
        if items == SEED:
            return [{"asin": SEED, "brand": "Fixture", "categoryTree": [{"catId": 100, "name": "Leaf"}]}]
        return [deepcopy(self.product)]

    def product_finder(self, params, **kwargs):
        self.finder_calls.append((params, kwargs))
        return [FIRST]


def client_for(tmp_path, product, **kwargs):
    api = FakeApi(product, **kwargs)
    cache = KeepaCache(tmp_path / "cache.sqlite3")
    return KeepaExpansionClient(api=api, cache=cache), api, cache


@pytest.mark.parametrize("criteria,rating,stats", [
    (None, False, None), (FilterCriteria(), False, None),
    (FilterCriteria(price_min_jpy=1000), False, 1),
    (FilterCriteria(rating_min=4.5), True, 1),
])
def test_only_requested_acquisition_adds_stats_and_rating(tmp_path, keepa_raw_product, criteria, rating, stats):
    client, api, cache = client_for(tmp_path, keepa_raw_product)
    product = client.verify_products_by_asin([FIRST], filter_criteria=criteria)[FIRST]
    args = api.query_calls[0][1]
    assert args["rating"] is rating
    assert args.get("stats") == stats
    assert args["history"] is False and args["offers"] is None and args["buybox"] is False
    assert "update" not in args
    assert args["wait"] is (stats is None)
    if stats:
        assert product["candidate_observation"]["price_jpy"] == 1000
        assert cache.get_product(FIRST)["candidate_observation"] == product["candidate_observation"]
    else:
        assert "candidate_observation" not in product


def test_old_product_cache_is_unknown_without_automatic_refill(tmp_path, keepa_raw_product):
    client, api, cache = client_for(tmp_path, keepa_raw_product)
    cache.save_product({"asin": FIRST, "title": "Legacy", "brand": "Fixture"})
    criteria = FilterCriteria(price_min_jpy=1000, rating_min=4.5)
    products = client.verify_products_by_asin([FIRST, FIRST], filter_criteria=criteria)
    assert evaluate_product(products[FIRST], criteria).status == "UNKNOWN"
    assert api.query_calls == []
    plan = client.plan_candidate_observation_fetch([FIRST, FIRST], criteria)
    assert plan.count == 1 and plan.token_estimate == 2
    assert api.query_calls == []


def test_search_cache_reuses_candidates_and_hydrates_observation_without_api(tmp_path, keepa_raw_product):
    client, api, cache = client_for(tmp_path, keepa_raw_product)
    old = client.find_related_products(SEED, 1)
    count = len(api.query_calls), len(api.finder_calls)
    criteria = FilterCriteria(price_min_jpy=1000, rating_min=4.5)
    legacy = client.find_related_products(SEED, 1, filter_criteria=criteria)
    assert legacy.rows[0]["candidate_observation"] is None
    plan = client.plan_candidate_observation_fetch([FIRST], criteria)
    client.fetch_candidate_observations(plan, criteria, token_budget=2, max_products=1)
    after_refresh = len(api.query_calls), len(api.finder_calls)
    changed = client.find_related_products(SEED, 1, filter_criteria=FilterCriteria(price_max_jpy=5000))
    assert (len(api.query_calls), len(api.finder_calls)) == after_refresh
    assert after_refresh == (count[0] + 1, count[1])
    assert changed.cache_key_data == old.cache_key_data
    assert changed.rows[0]["candidate_asin"] == old.rows[0]["candidate_asin"]
    assert changed.rows[0]["product_text_safety_fact"] == old.rows[0]["product_text_safety_fact"]
    assert changed.rows[0]["candidate_observation"]["rating"] == 4.5


def test_expired_product_cache_uses_normal_finite_acquisition(tmp_path, keepa_raw_product):
    client, api, cache = client_for(tmp_path, keepa_raw_product)
    eight_days_ago = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    cache.save_product({"asin": FIRST, "fetched_at": eight_days_ago})
    criteria = FilterCriteria(rating_min=4.5)
    assert cache.get_product(FIRST) is None
    assert client.plan_candidate_observation_fetch([FIRST], criteria).count == 1
    product = client.verify_products_by_asin([FIRST], filter_criteria=criteria)[FIRST]
    assert evaluate_product(product, criteria).status == MATCH
    assert len(api.query_calls) == 1 and cache.ttl == timedelta(days=7)


@pytest.mark.parametrize("price,rating", [(-1, -1), (-2, -2), (0, 99)])
def test_captured_missing_no_offer_or_invalid_are_not_repeated_automatically(tmp_path, keepa_raw_product, price, rating):
    keepa_raw_product["stats"]["current"][0] = price
    keepa_raw_product["stats"]["current"][16] = rating
    client, api, _ = client_for(tmp_path, keepa_raw_product)
    criteria = FilterCriteria(price_min_jpy=1000, rating_min=4.5)
    client.verify_products_by_asin([FIRST], filter_criteria=criteria)
    plan = client.plan_candidate_observation_fetch([FIRST], criteria)
    assert plan.count == 0 and plan.token_estimate == 0
    products = client.fetch_candidate_observations(plan, criteria, token_budget=0, max_products=0)
    assert FIRST in products and len(api.query_calls) == 1


@pytest.mark.parametrize("tokens,max_products", [(1, 1), (2, 0)])
def test_explicit_refill_rejects_insufficient_declared_budget_before_send(tmp_path, keepa_raw_product, tokens, max_products):
    client, api, _ = client_for(tmp_path, keepa_raw_product)
    criteria = FilterCriteria(rating_min=4.5)
    plan = client.plan_candidate_observation_fetch([FIRST], criteria)
    with pytest.raises(KeepaTokenError):
        client.fetch_candidate_observations(plan, criteria, token_budget=tokens, max_products=max_products)
    assert api.query_calls == []


def test_known_token_shortage_stops_normal_and_manual_acquisition_before_send(tmp_path, keepa_raw_product):
    client, api, _ = client_for(tmp_path, keepa_raw_product, tokens=1)
    criteria = FilterCriteria(rating_min=4.5)
    with pytest.raises(KeepaTokenError):
        client.verify_products_by_asin([FIRST], filter_criteria=criteria)
    with pytest.raises(KeepaTokenError):
        client.find_related_products(SEED, 1, filter_criteria=criteria)
    plan = client.plan_candidate_observation_fetch([FIRST], criteria)
    with pytest.raises(KeepaTokenError):
        client.fetch_candidate_observations(plan, criteria, token_budget=2, max_products=1)
    assert api.query_calls == [] and api.finder_calls == []


def test_changed_refill_plan_stops_before_send(tmp_path, keepa_raw_product):
    client, api, cache = client_for(tmp_path, keepa_raw_product)
    criteria = FilterCriteria(rating_min=4.5)
    plan = client.plan_candidate_observation_fetch([FIRST], criteria)
    cache.save_product({"asin": FIRST, "candidate_observation": extract_keepa_observation(keepa_raw_product, captured_at=utc_now_iso())})
    with pytest.raises(KeepaDataError, match="取得対象"):
        client.fetch_candidate_observations(plan, criteria, token_budget=2, max_products=1)
    assert api.query_calls == []


def test_refill_preserves_safety_cache_age_and_previous_rating_timestamp(tmp_path, keepa_raw_product):
    client, api, cache = client_for(tmp_path, keepa_raw_product)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).replace(microsecond=0).isoformat()
    old_observation = extract_keepa_observation(keepa_raw_product, captured_at=yesterday, price_requested=False)
    old = {"asin": FIRST, "fetched_at": yesterday, "description": ["Original safety"],
           "classification_facts": {"unchanged": "original"}, "candidate_observation": old_observation}
    cache.save_product(old)
    criteria = FilterCriteria(price_min_jpy=1000)
    plan = client.plan_candidate_observation_fetch([FIRST], criteria)
    assert plan.count == plan.token_estimate == 1
    product = client.fetch_candidate_observations(plan, criteria, token_budget=1, max_products=1)[FIRST]
    assert product["description"] == old["description"]
    assert product["classification_facts"] == old["classification_facts"]
    assert product["fetched_at"] == yesterday
    assert product["candidate_observation"]["rating"] == 4.5
    assert product["candidate_observation"]["rating_captured_at"] == yesterday
    assert product["candidate_observation"]["rating_requested"] is True
    assert api.query_calls[0][1]["rating"] is False


def test_partial_or_wrong_refill_response_fails_without_replacing_existing_product(tmp_path, keepa_raw_product):
    client, api, cache = client_for(tmp_path, keepa_raw_product)
    cache.save_product({"asin": FIRST, "title": "Preserved original"})
    criteria = FilterCriteria(rating_min=4.5)
    plan = client.plan_candidate_observation_fetch([FIRST, SECOND], criteria)
    with pytest.raises(KeepaDataError, match="一部欠け"):
        client.fetch_candidate_observations(plan, criteria, token_budget=4, max_products=2)
    assert cache.get_product(FIRST)["title"] == "Preserved original"
    assert "candidate_observation" not in cache.get_product(FIRST)


def test_expansion_and_resolver_use_same_observation_and_no_finder_pushdown(tmp_path, keepa_raw_product):
    client, api, _ = client_for(tmp_path, keepa_raw_product)
    criteria = FilterCriteria(price_min_jpy=1000, price_max_jpy=5000, rating_min=4.5)
    expansion = client.find_related_products(SEED, 1, filter_criteria=criteria)
    resolver = client.verify_products_by_asin([FIRST], filter_criteria=criteria)[FIRST]
    assert evaluate_product(expansion.rows[0], criteria) == evaluate_product(resolver, criteria)
    assert evaluate_product(resolver, criteria).status == MATCH
    assert len(api.finder_calls) == 1
    assert not any("AMAZON" in key or "RATING" in key for key in api.finder_calls[0][0])
    assert estimate_token_usage(1) == 62
    assert estimate_token_usage(1, criteria) == 112
    assert estimate_token_usage(5, criteria) == 556


def test_installed_sdk_retains_raw_stats_and_jp_yen_is_not_stats_parsed(tmp_path, keepa_raw_product):
    keepa = pytest.importorskip("keepa")
    api = keepa.Keepa("synthetic", check_key=False)
    api.status.refillRate, api.status.refillIn, api.tokens_left = 5, 1000, 1000
    calls = []
    def request(endpoint, payload, **kwargs):
        calls.append((endpoint, payload, kwargs))
        return {"products": [deepcopy(keepa_raw_product)]}
    api._request = request
    # Exercise installed SDK parsing over an in-memory fixture only.
    parsed = api.query([FIRST], stats=1, rating=True, history=False, wait=False, progress_bar=False)[0]
    assert parsed["stats"]["current"][0] == 1000
    assert parsed["stats_parsed"]["current"]["AMAZON"] == 10.0
    client = KeepaExpansionClient(api=api, cache=KeepaCache(tmp_path / "cache.sqlite3"))
    result = client.verify_products_by_asin([FIRST], filter_criteria=FilterCriteria(rating_min=4.5))[FIRST]
    assert result["candidate_observation"]["price_jpy"] == 1000
    assert result["candidate_observation"]["rating"] == 4.5
    assert calls[-1][1]["stats"] == 1 and calls[-1][1]["rating"] == 1
    assert calls[-1][1]["history"] == 0 and calls[-1][2]["wait"] is False


def test_sg_existing_bounded_transport_reserves_actual_send(tmp_path, keepa_raw_product, monkeypatch):
    keepa = pytest.importorskip("keepa")
    from modules import keepa_bounded_transport
    calls = []
    class Budget:
        reserved = 0
        def reserve_keepa_request(self):
            self.reserved += 1
            if self.reserved > 1:
                raise ValueError("Finite ledger exhausted")
    def send(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status_code=200, json=lambda: {"products": [deepcopy(keepa_raw_product)], "tokensLeft": 998})
    monkeypatch.setattr(keepa_bounded_transport.requests, "get", send)
    api = keepa.Keepa("synthetic", check_key=False)
    api.status.refillRate, api.status.refillIn, api.tokens_left = 5, 1000, 1000
    budget = Budget()
    client = KeepaExpansionClient(api=api, cache=KeepaCache(tmp_path / "cache.sqlite3"), request_budget=budget)
    criteria = FilterCriteria(rating_min=4.5)
    assert client.verify_products_by_asin([FIRST], filter_criteria=criteria)[FIRST]["candidate_observation"]["rating"] == 4.5
    assert budget.reserved == 1 and len(calls) == 1 and calls[0]["allow_redirects"] is False
    with pytest.raises(KeepaDataError):
        client.verify_products_by_asin([SECOND], filter_criteria=criteria)
    assert budget.reserved == 2 and len(calls) == 1


def test_sdk_initial_zero_token_placeholder_is_checked_once_before_explicit_fetch(tmp_path, keepa_raw_product):
    keepa = pytest.importorskip("keepa")
    api = keepa.Keepa("synthetic", check_key=False)
    calls = []
    def request(endpoint, payload, **kwargs):
        calls.append((endpoint, kwargs))
        if endpoint == "token":
            api.tokens_left = 100
            api.status.refillRate, api.status.refillIn = 5, 1000
            return {"tokensLeft": 100, "refillRate": 5, "refillIn": 1000}
        return {"products": [deepcopy(keepa_raw_product)]}
    api._request = request
    client = KeepaExpansionClient(api=api, cache=KeepaCache(tmp_path / "cache.sqlite3"))
    criteria = FilterCriteria(rating_min=4.5)
    plan = client.plan_candidate_observation_fetch([FIRST], criteria)
    assert calls == []
    assert client.fetch_candidate_observations(plan, criteria, token_budget=2, max_products=1)
    assert [endpoint for endpoint, _ in calls] == ["token", "product"]
    assert all(kwargs["wait"] is False for _, kwargs in calls)


def test_active_finder_failure_does_not_spend_on_diagnostic_fallback(tmp_path, keepa_raw_product):
    client, api, _ = client_for(tmp_path, keepa_raw_product)
    def failure(params, **kwargs):
        api.finder_calls.append((params, kwargs))
        raise RuntimeError("429")
    api.product_finder = failure
    with pytest.raises(KeepaTokenError):
        client.find_related_products(SEED, 1, filter_criteria=FilterCriteria(rating_min=4.5))
    assert len(api.finder_calls) == 1
    assert len(api.query_calls) == 1


def test_active_finder_rejects_response_above_declared_page_ceiling(tmp_path, keepa_raw_product):
    client, api, _ = client_for(tmp_path, keepa_raw_product)
    api.product_finder = lambda params, **kwargs: [FIRST] * 51
    with pytest.raises(KeepaDataError, match="ページ上限"):
        client.find_related_products(SEED, 1, filter_criteria=FilterCriteria(price_min_jpy=1000))
    assert len(api.query_calls) == 1
