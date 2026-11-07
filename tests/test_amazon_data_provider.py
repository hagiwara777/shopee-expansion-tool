from contextlib import nullcontext
from dataclasses import replace

import pytest

from modules.amazon_data_provider import (
    AmazonDataProviderConfigurationError,
    CANOPY_TEST_PROVIDER,
    KEEPA_CORE_PROVIDER,
    KEEPA_PROVIDER,
    create_amazon_data_client,
    normalize_amazon_data_provider,
)
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


@pytest.mark.parametrize('provider', [CANOPY_TEST_PROVIDER, 'rainforest'])
def test_retired_and_unknown_provider_are_rejected_without_fallback(provider):
    with pytest.raises(AmazonDataProviderConfigurationError, match="keepa or keepa_core"):
        normalize_amazon_data_provider(provider)


def test_factory_keeps_existing_keepa_client_as_default():
    client = create_amazon_data_client(
        _settings(),
        keepa_api=object(),
        keepa_cache=NoopCache(),
    )

    assert isinstance(client, KeepaExpansionClient)
    assert client.provider_name == KEEPA_PROVIDER


def test_core_provider_requires_a_persistent_budget_before_construction():
    with pytest.raises(AmazonDataProviderConfigurationError, match="persistent Keepa budget owner"):
        create_amazon_data_client(_settings(amazon_data_provider=KEEPA_CORE_PROVIDER))


def test_core_provider_rejects_non_sg_and_in_memory_budget_owners():
    class VolatileBudget:
        reserve = staticmethod(lambda *args, **kwargs: "reservation")
        core_keepa_call = staticmethod(nullcontext)

    with pytest.raises(AmazonDataProviderConfigurationError, match="SG Continuous persistent request ledger"):
        create_amazon_data_client(
            _settings(amazon_data_provider=KEEPA_CORE_PROVIDER),
            persistent_budget=VolatileBudget(),
        )


def test_provider_factory_keeps_legacy_and_persistent_budget_ports_separate(monkeypatch):
    seen = []
    class FakeClient:
        def __init__(self, **kwargs):
            seen.append(kwargs)
    monkeypatch.setattr('modules.keepa_client.KeepaExpansionClient', FakeClient)
    monkeypatch.setattr('modules.commerce_keepa_expansion.CommerceKeepaExpansionClient', FakeClient)
    ledger = object()
    create_amazon_data_client(_settings(amazon_data_provider=KEEPA_PROVIDER), request_budget=ledger)
    create_amazon_data_client(_settings(amazon_data_provider=KEEPA_CORE_PROVIDER), persistent_budget=ledger)
    assert seen[0]['request_budget'] is ledger and 'persistent_budget' not in seen[0]
    assert seen[1]['persistent_budget'] is ledger and 'request_budget' not in seen[1]
    with pytest.raises(AmazonDataProviderConfigurationError):
        create_amazon_data_client(_settings(amazon_data_provider=KEEPA_CORE_PROVIDER), request_budget=ledger)
    with pytest.raises(AmazonDataProviderConfigurationError):
        create_amazon_data_client(_settings(amazon_data_provider=KEEPA_PROVIDER), persistent_budget=ledger)




def test_factory_never_falls_back_when_retired_canopy_is_selected(monkeypatch):
    monkeypatch.setattr('modules.keepa_client.KeepaExpansionClient',
                        lambda *a, **kw: pytest.fail('Keepa fallback'))
    with pytest.raises(AmazonDataProviderConfigurationError):
        create_amazon_data_client(_settings(amazon_data_provider=CANOPY_TEST_PROVIDER))


@pytest.mark.parametrize(
    "settings",
    [
        _settings(keepa_api_key=""),
    ],
)
def test_factory_fails_closed_when_selected_provider_credential_is_missing(settings):
    with pytest.raises(AmazonDataProviderConfigurationError):
        create_amazon_data_client(settings)
