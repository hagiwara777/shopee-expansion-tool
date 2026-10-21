from contextlib import nullcontext
from dataclasses import replace
from types import SimpleNamespace

import pytest

from modules.amazon_data_provider import (
    AmazonDataProviderConfigurationError,
    CANOPY_TEST_PROVIDER,
    KEEPA_CORE_PROVIDER,
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
    with pytest.raises(AmazonDataProviderConfigurationError, match="keepa, keepa_core, or canopy_test"):
        normalize_amazon_data_provider("rainforest")


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


def test_sg_continuous_routes_core_and_legacy_providers_to_their_budget_ports(monkeypatch, tmp_path):
    import app
    import modules.sg_beta_environment as beta_environment
    import modules.sg_continuous_runtime as continuous_runtime

    class FakeRuntime:
        def __init__(self):
            self.grant = SimpleNamespace(digest="synthetic-policy")
            self.run_path = (tmp_path / "continuous").resolve()
            self.ledger = SimpleNamespace(require_current=lambda: None)

    class FakePolicy:
        @classmethod
        def from_file(cls, path):
            return SimpleNamespace(digest="synthetic-policy")

    runtime = FakeRuntime()
    monkeypatch.setattr(app, "st", SimpleNamespace(session_state={"sg_live_runtime": runtime}))
    monkeypatch.setattr(beta_environment, "preflight", lambda path: {
        "mode": "continuous", "policy_path": "synthetic-policy.json",
        "data_root": str(tmp_path),
    })
    monkeypatch.setattr(continuous_runtime, "SGContinuousRuntime", FakeRuntime)
    monkeypatch.setattr(continuous_runtime, "SGContinuousPolicy", FakePolicy)

    core = app._continuous_amazon_budget("SG", "synthetic-config.json", KEEPA_CORE_PROVIDER)
    legacy = app._continuous_amazon_budget("SG", "synthetic-config.json", KEEPA_PROVIDER)
    assert core == {"persistent_budget": runtime.ledger}
    assert legacy == {"request_budget": runtime.ledger}
    assert app._continuous_amazon_budget("PH", "synthetic-config.json", KEEPA_CORE_PROVIDER) == {}


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
