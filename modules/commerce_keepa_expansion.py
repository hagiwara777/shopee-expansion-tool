"""Opt-in Expansion adapter backed by commerce-api-core's public Keepa API."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from modules.amazon_data_provider import AmazonDataProviderConfigurationError
from modules.keepa_client import (
    KeepaDataError,
    KeepaExpansionClient,
    ProductFinderPage,
)


class _SettingsSecretRef:
    """Resolve the already-loaded Keepa setting only when a request starts."""

    __slots__ = ("_settings",)

    def __init__(self, settings: Any) -> None:
        self._settings = settings

    def resolve(self):
        from commerce_api.secrets import SecretValue

        return SecretValue(self._settings.keepa_api_key)

    def __repr__(self) -> str:
        return "SettingsKeepaSecretRef([REDACTED])"

    __str__ = __repr__


class _CapturingKeepaTransport:
    """Capture only public response metadata needed by the existing UI."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.tokens_left: int | None = None
        self.total_results: int | None = None

    def reset(self) -> None:
        self.total_results = None

    def get(self, request_type: str, params: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
        body = self._delegate.get(request_type, params, timeout)
        if isinstance(body, Mapping):
            tokens_left = body.get("tokensLeft")
            if type(tokens_left) is int and tokens_left >= 0:
                self.tokens_left = tokens_left
            total_results = body.get("totalResults") if request_type == "query" else None
            self.total_results = (
                total_results if type(total_results) is int and total_results >= 0 else None
            )
        return body


class _ExpansionKeepaAPI:
    """Expose only the Keepa API shape used by KeepaExpansionClient."""

    def __init__(self, client: Any, budget: Any, transport: _CapturingKeepaTransport,
                 domain: str) -> None:
        self._client = client
        self._budget = budget
        self._transport = transport
        self.domain = domain

    @property
    def tokens_left(self) -> int | None:
        return self._transport.tokens_left

    @property
    def last_total_results(self) -> int | None:
        return self._transport.total_results

    @property
    def stopped(self) -> bool:
        return bool(self._budget.core_keepa_stopped)

    def query(
        self,
        product_codes: str | Sequence[str],
        *,
        domain: str | None = None,
        history: bool = False,
        offers: Any = None,
        stock: bool = False,
        buybox: bool = False,
        rating: bool = False,
        progress_bar: bool = False,
        wait: bool = False,
        stats: int | None = None,
        **unsupported: Any,
    ) -> list[Mapping[str, Any]]:
        if (wait is not False or offers is not None or stock is not False or buybox is not False
                or progress_bar is not False or unsupported):
            raise ValueError("Core Keepa adapter does not support this request mode.")
        asins = (product_codes,) if isinstance(product_codes, str) else tuple(product_codes)
        selected_domain = domain or self.domain
        token_ceiling = len(asins) * (1 + int(rating))
        from commerce_api.budget import CallGrant

        with self._budget.core_keepa_call():
            result = self._client.get_products(
                asins,
                grant=CallGrant("keepa.product", {
                    "requests": 1,
                    "keepa_tokens": token_ceiling,
                }),
                token_grant=CallGrant("keepa.token", {
                    "requests": 1,
                    "keepa_tokens": 0,
                }),
                history=history,
                rating=rating,
                stats=stats,
            )
        return [dict(product) for product in result.products]

    def product_finder(
        self,
        selection: Mapping[str, Any],
        *,
        domain: str | None = None,
        n_products: int = 50,
        wait: bool = False,
    ) -> tuple[str, ...]:
        if wait is not False:
            raise ValueError("Core Keepa adapter requires non-waiting requests.")
        token_ceiling = 1 + (n_products + 4) // 5
        from commerce_api.budget import CallGrant

        self._transport.reset()
        with self._budget.core_keepa_call():
            return self._client.product_finder(
                selection,
                grant=CallGrant("keepa.finder", {
                    "requests": 1,
                    "keepa_tokens": token_ceiling,
                }),
                domain=domain or self.domain,
                n_products=n_products,
            )


class CommerceKeepaExpansionClient(KeepaExpansionClient):
    """Keep the established Expansion/cache contract over commerce-api-core."""

    provider_name = "keepa_core"

    def __init__(self, *, settings: Any, persistent_budget: Any, domain: str = "JP",
                 cache: Any | None = None, transport: Any | None = None) -> None:
        if persistent_budget is None or not callable(getattr(persistent_budget, "reserve", None)):
            raise AmazonDataProviderConfigurationError(
                "AMAZON_DATA_PROVIDER=keepa_core requires a persistent Keepa budget owner."
            )
        from modules.sg_continuous_runtime import SGContinuousLedger

        if (type(persistent_budget) is not SGContinuousLedger
                or not callable(getattr(persistent_budget, "core_keepa_call", None))):
            raise AmazonDataProviderConfigurationError(
                "Keepa Core requires the SG Continuous persistent request ledger."
            )
        try:
            from commerce_api.providers.keepa import KeepaClient, RequestsKeepaTransport
        except ImportError:
            raise AmazonDataProviderConfigurationError(
                "commerce-api-core and its pinned Keepa dependencies are required for keepa_core."
            ) from None

        delegate = transport or RequestsKeepaTransport()
        captured = _CapturingKeepaTransport(delegate)
        core_client = KeepaClient(
            api_key=_SettingsSecretRef(settings),
            budget=persistent_budget,
            domain=domain,
            transport=captured,
        )
        self._core_keepa_api = _ExpansionKeepaAPI(
            core_client, persistent_budget, captured, domain.upper(),
        )
        super().__init__(domain=domain, api=self._core_keepa_api, cache=cache)

    def _call_keepa(self, action: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        if "wait" in kwargs:
            kwargs["wait"] = False
        return super()._call_keepa(action, func, *args, **kwargs)

    def _token_status(self, *, wait: bool = True) -> str:
        return super()._token_status(wait=False)

    def _product_finder_page(self, action: str, params: dict[str, Any], *, wait: bool = True) -> ProductFinderPage:
        result = super()._product_finder_page(action, params, wait=False)
        return ProductFinderPage(
            asin_list=result.asin_list,
            total_results=self._core_keepa_api.last_total_results,
        )

    def _diagnose_and_fallback(self, source, original_error):
        # Finder diagnostics issue more product-finder requests. Core mode never
        # retries or widens a failed finite search after any transport outcome.
        if original_error is not None:
            raise original_error
        raise KeepaDataError("Core Keepa search stopped; an explicit new action is required.")
