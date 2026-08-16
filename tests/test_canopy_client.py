from urllib.parse import parse_qs, urlparse

import pytest

from modules.canopy_client import (
    CANOPY_EXPANSION_MAX_REQUESTS,
    CANOPY_NOT_FOUND,
    CANOPY_RESOLVER_MAX_ASINS,
    CANOPY_VERIFIED,
    CanopyDataError,
    CanopyNetworkError,
    CanopyTestClient,
)
from modules.cache import KeepaCache


def _product_payload(asin, *, brand="Acme", title=None):
    return {
        "data": {
            "amazonProduct": {
                "asin": asin,
                "title": title or f"Product {asin}",
                "brand": brand,
                "categories": [{"id": "ignored", "name": "Not mapped"}],
            }
        }
    }


def _search_payload(asins):
    return {
        "data": {
            "amazonProductSearchResults": {
                "productResults": {
                    "results": [{"asin": asin, "title": asin} for asin in asins],
                    "pageInfo": {"currentPage": 1, "hasNextPage": True},
                }
            }
        }
    }


class RecordingTransport:
    def __init__(self, *, brands=None, search_asins=None):
        self.brands = brands or {}
        self.search_asins = search_asins or []
        self.calls = []

    def __call__(self, url, headers, timeout):
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        self.calls.append((parsed.path, params, dict(headers), timeout))
        if parsed.path.endswith("/search"):
            return _search_payload(self.search_asins)
        asin = params["asin"][0]
        return _product_payload(asin, brand=self.brands.get(asin, "Acme"))


def test_canopy_resolver_verifies_at_most_ten_asins_with_one_request_each():
    transport = RecordingTransport()
    client = CanopyTestClient(api_key="secret", transport=transport)
    asins = [f"B{index:09d}" for index in range(1, CANOPY_RESOLVER_MAX_ASINS + 1)]

    products = client.verify_products_by_asin(asins)

    assert list(products) == asins
    assert len(transport.calls) == CANOPY_RESOLVER_MAX_ASINS
    assert all(call[1]["domain"] == ["JP"] for call in transport.calls)
    assert all(call[2]["API-KEY"] == "secret" for call in transport.calls)
    assert client.verification_label == CANOPY_VERIFIED
    assert client.not_found_label == CANOPY_NOT_FOUND


def test_canopy_resolver_rejects_more_than_ten_asins_before_any_request():
    transport = RecordingTransport()
    client = CanopyTestClient(api_key="secret", transport=transport)
    asins = [f"B{index:09d}" for index in range(1, CANOPY_RESOLVER_MAX_ASINS + 2)]

    with pytest.raises(CanopyDataError, match="at most 10"):
        client.verify_products_by_asin(asins)

    assert transport.calls == []


def test_canopy_expansion_uses_one_search_page_and_at_most_seven_requests():
    source_asin = "B000000001"
    candidates = [f"B{index:09d}" for index in range(2, 8)]
    transport = RecordingTransport(
        brands={candidates[1]: "Other", candidates[2]: "Ａｃｍｅ"},
        search_asins=[
            source_asin,
            "INVALID",
            candidates[0],
            candidates[0],
            *candidates[1:],
        ],
    )
    client = CanopyTestClient(api_key="secret", transport=transport)

    result = client.find_related_products(source_asin)

    assert result.request_count == CANOPY_EXPANSION_MAX_REQUESTS
    assert len(transport.calls) == CANOPY_EXPANSION_MAX_REQUESTS
    search_calls = [call for call in transport.calls if call[0].endswith("/search")]
    assert len(search_calls) == 1
    assert search_calls[0][1]["searchTerm"] == ["Acme"]
    assert search_calls[0][1]["domain"] == ["JP"]
    assert search_calls[0][1]["page"] == ["1"]
    assert result.self_excluded_count == 1
    assert result.invalid_excluded_count == 1
    assert result.duplicate_removed_count == 1
    assert result.brand_mismatch_excluded_count == 1
    assert result.final_display_count == 4
    assert len(result.rows) == 4
    assert all(row["source"] == "canopy_test_brand_search_exact" for row in result.rows)
    assert all(row["category"] == "" for row in result.rows)


def test_canopy_does_not_retry_or_fallback_after_transport_error():
    calls = []

    def failing_transport(url, headers, timeout):
        calls.append(url)
        raise OSError("synthetic failure")

    client = CanopyTestClient(api_key="secret", transport=failing_transport)

    with pytest.raises(CanopyNetworkError, match="without retry"):
        client.verify_products_by_asin(["B000000001"])

    assert len(calls) == 1


def test_canopy_expansion_never_initializes_or_writes_keepa_cache(monkeypatch):
    def forbidden_cache_operation(*args, **kwargs):
        raise AssertionError("Canopy must not use Keepa SQLite cache")

    monkeypatch.setattr(KeepaCache, "__init__", forbidden_cache_operation)
    monkeypatch.setattr(KeepaCache, "save_product", forbidden_cache_operation)
    monkeypatch.setattr(KeepaCache, "save_search", forbidden_cache_operation)
    transport = RecordingTransport(search_asins=["B000000002"])

    result = CanopyTestClient(api_key="secret", transport=transport).find_related_products(
        "B000000001"
    )

    assert result.final_display_count == 1
    assert result.request_count == 3


def test_canopy_rejects_malformed_response_instead_of_treating_it_as_verified():
    client = CanopyTestClient(
        api_key="secret",
        transport=lambda url, headers, timeout: {"data": {"amazonProduct": "bad"}},
    )

    with pytest.raises(CanopyDataError, match="malformed"):
        client.verify_products_by_asin(["B000000001"])
