"""Select the Amazon data provider without implicit fallback."""

from __future__ import annotations

from typing import Any


KEEPA_PROVIDER = "keepa"
CANOPY_TEST_PROVIDER = "canopy_test"
SUPPORTED_AMAZON_DATA_PROVIDERS = {KEEPA_PROVIDER, CANOPY_TEST_PROVIDER}


class AmazonDataProviderError(RuntimeError):
    """Base error for provider selection and provider-backed requests."""


class AmazonDataProviderConfigurationError(AmazonDataProviderError):
    """Raised when provider configuration is missing or unsupported."""


def normalize_amazon_data_provider(value: str | None) -> str:
    """Return a supported provider name, defaulting only an empty value to Keepa."""

    provider = (value or KEEPA_PROVIDER).strip().casefold() or KEEPA_PROVIDER
    if provider not in SUPPORTED_AMAZON_DATA_PROVIDERS:
        raise AmazonDataProviderConfigurationError(
            "AMAZON_DATA_PROVIDER must be keepa or canopy_test."
        )
    return provider


def create_amazon_data_client(
    settings: Any,
    *,
    keepa_api: Any | None = None,
    keepa_cache: Any | None = None,
    canopy_transport: Any | None = None,
) -> Any:
    """Create only the explicitly configured provider client."""

    provider = normalize_amazon_data_provider(settings.amazon_data_provider)
    if provider == KEEPA_PROVIDER:
        if not settings.keepa_api_key and keepa_api is None:
            raise AmazonDataProviderConfigurationError(
                "KEEPA_API_KEY is required when AMAZON_DATA_PROVIDER=keepa."
            )
        from modules.keepa_client import KeepaExpansionClient

        kwargs: dict[str, Any] = {
            "api_key": settings.keepa_api_key,
            "domain": settings.keepa_domain,
        }
        if keepa_api is not None:
            kwargs["api"] = keepa_api
        if keepa_cache is not None:
            kwargs["cache"] = keepa_cache
        return KeepaExpansionClient(**kwargs)

    if not settings.canopy_api_key and canopy_transport is None:
        raise AmazonDataProviderConfigurationError(
            "CANOPY_API_KEY is required when AMAZON_DATA_PROVIDER=canopy_test."
        )
    from modules.canopy_client import CanopyTestClient

    return CanopyTestClient(
        api_key=settings.canopy_api_key,
        domain="JP",
        transport=canopy_transport,
    )
