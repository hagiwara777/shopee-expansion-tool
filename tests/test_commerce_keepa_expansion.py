from modules.amazon_data_provider import KEEPA_CORE_PROVIDER, create_amazon_data_client
from modules.cache import KeepaCache
from modules.config import Settings
from modules.keepa_client import KeepaClientError, KeepaExpansionClient
from modules.sg_continuous_runtime import SGContinuousLedger, SGContinuousPolicy

import pytest


SOURCE_ASIN = "B000000001"
CANDIDATE_ASIN = "B000000002"


def _policy():
    return SGContinuousPolicy(
        "synthetic-core-keepa", 22, "synthetic-bridge", 3, 0, 50, 5, 10, "0",
        "Synthetic offline authorization only",
    )


def _product(asin):
    current = [-1] * 37
    current[0], current[1], current[3], current[16], current[17] = 1000, 500, 9, 45, 9999
    return {
        "asin": asin,
        "domainId": 5,
        "title": "Synthetic item " + asin[-1],
        "brand": "Maker",
        "categoryTree": [{"catId": 123, "name": "Synthetic category"}],
        "stats": {"current": current},
        "availabilityAmazon": 0,
        "description": ["Synthetic description"],
        "features": ["Synthetic feature"],
    }


class OfflineKeepaTransport:
    def __init__(self, *, fail_finder=False):
        self.requests = []
        self.fail_finder = fail_finder

    def get(self, request_type, params, timeout):
        self.requests.append((request_type, dict(params)))
        if request_type == "token":
            return {"tokensLeft": 100, "refillRate": 5, "refillIn": 1200}
        if request_type == "query":
            if self.fail_finder:
                raise RuntimeError("synthetic offline transport failure")
            return {
                "asinList": [CANDIDATE_ASIN], "totalResults": 7,
                "tokensConsumed": 1, "tokensLeft": 99,
            }
        if request_type == "product":
            requested = params.get("asin", "")
            if isinstance(requested, (tuple, list)):
                asins = list(requested)
            else:
                asins = [part for part in str(requested).split(",") if part]
            return {
                "products": [_product(asin) for asin in asins],
                "tokensConsumed": len(asins), "tokensLeft": 99,
            }
        raise AssertionError("unexpected Keepa endpoint")


def _ledger(tmp_path):
    return SGContinuousLedger(
        tmp_path / "request-ledger.json", _policy(), initialize=True,
    )


def test_keepa_core_adapter_uses_real_core_and_preserves_expansion_result_offline(tmp_path):
    ledger = _ledger(tmp_path)
    transport = OfflineKeepaTransport()
    try:
        client = create_amazon_data_client(
            Settings(keepa_api_key="synthetic-key", amazon_data_provider=KEEPA_CORE_PROVIDER),
            persistent_budget=ledger,
            keepa_transport=transport,
            keepa_cache=KeepaCache(tmp_path / "cache.sqlite3"),
        )

        assert isinstance(client, KeepaExpansionClient)
        assert client.provider_name == KEEPA_CORE_PROVIDER
        result = client.find_related_products(SOURCE_ASIN, search_pages=1, search_mode="strict")

        assert result.source_asin == SOURCE_ASIN
        assert result.total_results == 7
        assert result.final_display_count == 1
        assert "指定した有限計画内で取得" in result.token_status
        assert result.rows[0]["candidate_asin"] == CANDIDATE_ASIN
        assert [kind for kind, _ in transport.requests] == [
            "token", "product", "query", "token", "product",
        ]
        assert ledger.data["keepa_requests"] == 5
        assert [row["state"] for row in ledger.data["keepa_core"]["reservations"]] == [
            "COMPLETE", "COMPLETE", "COMPLETE", "COMPLETE", "COMPLETE",
        ]
        assert all(row["actual_usage"] is not None for row in ledger.data["keepa_core"]["reservations"])
    finally:
        ledger.close()


def test_keepa_core_unknown_finder_usage_does_not_trigger_expansion_fallback(tmp_path):
    ledger = _ledger(tmp_path)
    transport = OfflineKeepaTransport(fail_finder=True)
    try:
        client = create_amazon_data_client(
            Settings(keepa_api_key="synthetic-key", amazon_data_provider=KEEPA_CORE_PROVIDER),
            persistent_budget=ledger,
            keepa_transport=transport,
            keepa_cache=KeepaCache(tmp_path / "cache.sqlite3"),
        )
        with pytest.raises(KeepaClientError):
            client.find_related_products(SOURCE_ASIN, search_pages=1, search_mode="standard")

        assert [kind for kind, _ in transport.requests] == ["token", "product", "query"]
        assert ledger.data["keepa_requests"] == 3
        assert [row["state"] for row in ledger.data["keepa_core"]["reservations"]] == [
            "COMPLETE", "COMPLETE", "UNKNOWN",
        ]
        assert ledger.core_keepa_stopped
    finally:
        ledger.close()
