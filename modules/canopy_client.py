"""Minimal test-only Canopy REST adapter for Resolver and Expansion."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import unicodedata

from modules.amazon_data_provider import AmazonDataProviderError, CANOPY_TEST_PROVIDER
from modules.cache import utc_now_iso
from modules.keepa_client import normalize_asin


CANOPY_BASE_URL = "https://rest.canopyapi.co"
CANOPY_PRODUCT_PATH = "/api/amazon/product"
CANOPY_SEARCH_PATH = "/api/amazon/search"
CANOPY_RESOLVER_MAX_ASINS = 10
CANOPY_EXPANSION_MAX_CANDIDATES = 5
CANOPY_EXPANSION_MAX_REQUESTS = 7
CANOPY_SEARCH_RESULT_LIMIT = 20
CANOPY_VERIFIED = "CANOPY_VERIFIED"
CANOPY_NOT_FOUND = "CANOPY_NOT_FOUND"
CANOPY_EXPANSION_SOURCE = "canopy_test_brand_search_exact"

Transport = Callable[[str, Mapping[str, str], float], Mapping[str, Any]]


class CanopyClientError(AmazonDataProviderError):
    """Base error for Canopy test-provider operations."""


class CanopyConfigurationError(CanopyClientError):
    pass


class CanopyDataError(CanopyClientError):
    pass


class CanopyNetworkError(CanopyClientError):
    pass


class CanopyNotFoundError(CanopyClientError):
    pass


@dataclass(frozen=True)
class CanopyExpansionResult:
    source_asin: str
    brand: str
    rows: list[dict[str, str]]
    raw_candidate_count: int
    detail_success_count: int
    detail_failed_count: int
    duplicate_removed_count: int
    self_excluded_count: int
    invalid_excluded_count: int
    brand_mismatch_excluded_count: int
    final_display_count: int
    request_count: int
    fetched_at: str
    provider: str = CANOPY_TEST_PROVIDER


class CanopyTestClient:
    """Canopy adapter with no retry, no fallback, pagination, or cache writes."""

    verification_label = CANOPY_VERIFIED
    not_found_label = CANOPY_NOT_FOUND
    product_field_prefix = "canopy"
    provider_name = CANOPY_TEST_PROVIDER

    def __init__(
        self,
        api_key: str | None = None,
        domain: str = "JP",
        *,
        transport: Transport | None = None,
        timeout_seconds: float = 20.0,
    ):
        if domain != "JP":
            raise CanopyConfigurationError("Canopy test provider supports JP only.")
        if not (api_key or "").strip() and transport is None:
            raise CanopyConfigurationError("CANOPY_API_KEY is required.")
        self.api_key = (api_key or "").strip()
        self.domain = domain
        self.transport = transport or self._default_transport
        self.timeout_seconds = timeout_seconds
        self.request_count = 0

    def verify_products_by_asin(self, asins: Iterable[str]) -> dict[str, dict[str, Any]]:
        normalized_asins = _unique_normalized_asins(asins)
        if len(normalized_asins) > CANOPY_RESOLVER_MAX_ASINS:
            raise CanopyDataError(
                f"Canopy Resolver accepts at most {CANOPY_RESOLVER_MAX_ASINS} ASINs per run."
            )

        products: dict[str, dict[str, Any]] = {}
        for asin in normalized_asins:
            try:
                product = self._get_product(asin)
            except CanopyNotFoundError:
                continue
            products[asin] = product
        return products

    def find_related_products(self, source_asin: str) -> CanopyExpansionResult:
        self.request_count = 0
        normalized_source_asin = normalize_asin(source_asin)
        source = self._get_product(normalized_source_asin)
        source_brand = _required_text(source.get("brand"), "source product brand")

        search_payload = self._request_json(
            CANOPY_SEARCH_PATH,
            {
                "searchTerm": source_brand,
                "domain": self.domain,
                "page": "1",
                "limit": str(CANOPY_SEARCH_RESULT_LIMIT),
            },
        )
        search_results = _extract_search_results(search_payload)
        raw_candidate_count = len(search_results)
        candidate_asins, duplicate_count, self_count, invalid_count = _candidate_asins(
            search_results,
            source_asin=normalized_source_asin,
            limit=CANOPY_EXPANSION_MAX_CANDIDATES,
        )

        fetched_at = utc_now_iso()
        rows: list[dict[str, str]] = []
        detail_failed_count = 0
        brand_mismatch_count = 0
        for asin in candidate_asins:
            try:
                product = self._get_product(asin)
            except CanopyNotFoundError:
                detail_failed_count += 1
                continue
            if not _brand_exact(source_brand, product.get("brand")):
                brand_mismatch_count += 1
                continue
            rows.append(
                {
                    "seed_asin": normalized_source_asin,
                    "candidate_asin": asin,
                    "product_title": _text(product.get("title")),
                    "brand": _text(product.get("brand")),
                    "category": "",
                    "source": CANOPY_EXPANSION_SOURCE,
                    "fetched_at": _text(product.get("fetched_at")) or fetched_at,
                    "note": "Canopy TEST brand exact match; category mapping not applied",
                }
            )

        if self.request_count > CANOPY_EXPANSION_MAX_REQUESTS:
            raise CanopyDataError("Canopy Expansion request limit exceeded.")

        return CanopyExpansionResult(
            source_asin=normalized_source_asin,
            brand=source_brand,
            rows=rows,
            raw_candidate_count=raw_candidate_count,
            detail_success_count=len(candidate_asins) - detail_failed_count,
            detail_failed_count=detail_failed_count,
            duplicate_removed_count=duplicate_count,
            self_excluded_count=self_count,
            invalid_excluded_count=invalid_count,
            brand_mismatch_excluded_count=brand_mismatch_count,
            final_display_count=len(rows),
            request_count=self.request_count,
            fetched_at=fetched_at,
        )

    def _get_product(self, asin: str) -> dict[str, Any]:
        payload = self._request_json(
            CANOPY_PRODUCT_PATH,
            {"asin": normalize_asin(asin), "domain": self.domain},
        )
        product = _extract_product(payload)
        returned_asin = normalize_asin(_required_text(product.get("asin"), "product ASIN"))
        if returned_asin != asin:
            raise CanopyDataError("Canopy returned a different ASIN than requested.")
        return {
            "asin": returned_asin,
            "title": _text(product.get("title")),
            "brand": _text(product.get("brand")),
            "category": "",
            "fetched_at": utc_now_iso(),
        }

    def _request_json(self, path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        query = urlencode(params)
        url = f"{CANOPY_BASE_URL}{path}?{query}"
        headers = {"API-KEY": self.api_key, "Accept": "application/json"}
        self.request_count += 1
        try:
            payload = self.transport(url, headers, self.timeout_seconds)
        except CanopyNotFoundError:
            raise
        except CanopyClientError:
            raise
        except Exception as exc:
            raise CanopyNetworkError("Canopy request failed without retry.") from exc
        if not isinstance(payload, Mapping):
            raise CanopyDataError("Canopy response must be a JSON object.")
        return payload

    @staticmethod
    def _default_transport(
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                raw = response.read()
        except HTTPError as exc:
            if exc.code == 404:
                raise CanopyNotFoundError("Canopy product was not found.") from exc
            raise CanopyNetworkError(f"Canopy HTTP error: {exc.code}.") from exc
        except URLError as exc:
            raise CanopyNetworkError("Canopy network request failed.") from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CanopyDataError("Canopy returned invalid JSON.") from exc
        if not isinstance(payload, Mapping):
            raise CanopyDataError("Canopy response must be a JSON object.")
        return payload


def _extract_product(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = payload.get("data")
    product = data.get("amazonProduct") if isinstance(data, Mapping) else None
    if product is None:
        raise CanopyNotFoundError("Canopy did not return product data.")
    if not isinstance(product, Mapping):
        raise CanopyDataError("Canopy product response is malformed.")
    return product


def _extract_search_results(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    data = payload.get("data")
    search = data.get("amazonProductSearchResults") if isinstance(data, Mapping) else None
    product_results = search.get("productResults") if isinstance(search, Mapping) else None
    results = product_results.get("results") if isinstance(product_results, Mapping) else None
    if not isinstance(results, list):
        raise CanopyDataError("Canopy search response is malformed.")
    return [item for item in results if isinstance(item, Mapping)]


def _candidate_asins(
    search_results: Iterable[Mapping[str, Any]],
    *,
    source_asin: str,
    limit: int,
) -> tuple[list[str], int, int, int]:
    candidates: list[str] = []
    seen: set[str] = set()
    duplicate_count = 0
    self_count = 0
    invalid_count = 0
    for result in search_results:
        try:
            asin = normalize_asin(_text(result.get("asin")))
        except ValueError:
            invalid_count += 1
            continue
        if asin == source_asin:
            self_count += 1
            continue
        if asin in seen:
            duplicate_count += 1
            continue
        seen.add(asin)
        candidates.append(asin)
        if len(candidates) == limit:
            break
    return candidates, duplicate_count, self_count, invalid_count


def _unique_normalized_asins(asins: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in asins:
        asin = normalize_asin(value)
        if asin not in seen:
            seen.add(asin)
            unique.append(asin)
    return unique


def _brand_exact(expected: str, actual: Any) -> bool:
    return _normalize_brand(expected) == _normalize_brand(_text(actual))


def _normalize_brand(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _required_text(value: Any, label: str) -> str:
    text = _text(value).strip()
    if not text:
        raise CanopyDataError(f"Canopy {label} is missing.")
    return text


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()
