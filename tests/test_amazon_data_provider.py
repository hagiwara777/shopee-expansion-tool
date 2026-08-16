from dataclasses import replace

import pytest

from modules.amazon_data_provider import (
    AmazonDataProviderConfigurationError,
    CANOPY_TEST_PROVIDER,
    KEEPA_PROVIDER,
    create_amazon_data_client,
    normalize_amazon_data_provider,
)
from modules.canopy_client import CanopyTestClient
from modules.config import Settings
from modules.keepa_client import KeepaExpansionClient


class NoopCache:
    pass


def _settings(**overrides):
    settings = Settings(keepa_api_key="keepa-secret")
    return replace(settings, **overrides)


def test_provider_defaults_to_keepa_only_for_empty_configuration():
    assert normalize_amazon_data_provider(None) == KEEPA_PROVIDER
    assert normalize_amazon_data_provider("") == KEEPA_PROVIDER


def test_provider_accepts_explicit_canopy_test_and_rejects_unknown_value():
    assert normalize_amazon_data_provider(" canopy_test ") == CANOPY_TEST_PROVIDER
    with pytest.raises(AmazonDataProviderConfigurationError, match="keepa or canopy_test"):
        normalize_amazon_data_provider("rainforest")


def test_factory_keeps_existing_keepa_client_as_default():
    client = create_amazon_data_client(
        _settings(),
        keepa_api=object(),
        keepa_cache=NoopCache(),
    )

    assert isinstance(client, KeepaExpansionClient)
    assert client.provider_name == KEEPA_PROVIDER


def test_factory_creates_canopy_only_when_explicitly_selected():
    client = create_amazon_data_client(
        _settings(
            amazon_data_provider=CANOPY_TEST_PROVIDER,
            canopy_api_key="canopy-secret",
        ),
        canopy_transport=lambda url, headers, timeout: {},
    )

    assert isinstance(client, CanopyTestClient)
    assert client.provider_name == CANOPY_TEST_PROVIDER


@pytest.mark.parametrize(
    "settings",
    [
        _settings(keepa_api_key=""),
        _settings(
            amazon_data_provider=CANOPY_TEST_PROVIDER,
            canopy_api_key="",
        ),
    ],
)
def test_factory_fails_closed_when_selected_provider_credential_is_missing(settings):
    with pytest.raises(AmazonDataProviderConfigurationError):
        create_amazon_data_client(settings)
