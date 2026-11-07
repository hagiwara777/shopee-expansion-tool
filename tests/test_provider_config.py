"""Shared provider settings stay explicit and fail closed, without network."""
import pytest

import modules.config as config


def test_load_settings_defaults_to_keepa(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'current_beta_paths', lambda: None)
    monkeypatch.setattr(config, 'ENV_PATH', tmp_path / 'missing.env')
    monkeypatch.setenv('KEEPA_API_KEY', 'synthetic')
    monkeypatch.setenv('KEEPA_DOMAIN', 'JP')
    monkeypatch.delenv('AMAZON_DATA_PROVIDER', raising=False)
    assert config.load_settings().amazon_data_provider == 'keepa'


@pytest.mark.parametrize('provider', ['canopy_test', 'unknown'])
def test_load_settings_rejects_retired_or_unknown_provider(monkeypatch, tmp_path, provider):
    monkeypatch.setattr(config, 'current_beta_paths', lambda: None)
    monkeypatch.setattr(config, 'ENV_PATH', tmp_path / 'missing.env')
    monkeypatch.setenv('KEEPA_API_KEY', 'synthetic')
    monkeypatch.setenv('KEEPA_DOMAIN', 'JP')
    monkeypatch.setenv('AMAZON_DATA_PROVIDER', provider)
    with pytest.raises(config.AmazonDataProviderConfigurationError):
        config.load_settings()
