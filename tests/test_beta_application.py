"""Preserved beta path and preflight contracts with synthetic data."""
import json
import logging
import os
from pathlib import Path

import pytest

from modules.beta_runtime_paths import beta_runtime_paths, current_beta_paths
from test_sg_live_runtime import grant
from test_sg_beta_environment import profile


@pytest.fixture(autouse=True)
def isolate_app(monkeypatch, tmp_path):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'appdata'))
    for name in ('OPENAI_API_KEY', 'KEEPA_API_KEY', 'PH_IMAGE_SAFETY_API_ENABLED'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr('modules.config.ENV_PATH', tmp_path / 'missing.env')
    def warning(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.WARNING):
            self._log(logging.WARNING, message, args, **kwargs)
    monkeypatch.setattr(logging.Logger, 'warning', warning)
    monkeypatch.setattr('requests.sessions.Session.request', lambda *a, **k: pytest.fail('External API forbidden'))
    monkeypatch.setattr('modules.shopee_catalog_client.urlopen', lambda *a, **k: pytest.fail('External API forbidden'))










def test_explicit_ph_paths_reuse_cache_and_do_not_leak_settings(tmp_path, monkeypatch):
    from modules.cache import KeepaCache
    from modules.config import load_settings
    from modules.category_ai_openai import OpenAIResponsesCategoryProvider
    from modules.ph_image_safety_api import OpenAIImageAnalyzer
    ph = tmp_path / 'ph'; ph.mkdir()
    env = tmp_path / 'ph.env'
    env.write_text('KEEPA_API_KEY=synthetic-ph\nOPENAI_API_KEY=synthetic-openai\nPH_IMAGE_SAFETY_API_ENABLED=1\n', encoding='utf-8')
    original = dict(os.environ)
    with beta_runtime_paths(ph, env):
        assert load_settings().keepa_api_key == 'synthetic-ph'
        cache = KeepaCache()
        assert cache.db_path == ph / 'cache' / 'keepa_cache.sqlite3'
        assert OpenAIResponsesCategoryProvider.from_environment()._api_key == 'synthetic-openai'
        assert OpenAIImageAnalyzer.from_environment()._enabled is True
    assert current_beta_paths() is None
    changed_names = [name for name in set(original) | set(os.environ)
                     if original.get(name) != os.environ.get(name)]
    assert not changed_names  # Never dump environment values on test failure.


def test_unified_preflight_reuses_strict_sg_preflight(profile, tmp_path):
    from modules.beta_environment import preflight
    sg_path, sg_config, _ = profile
    ph = tmp_path / 'ph'; (ph / 'cache').mkdir(parents=True)
    (ph / 'cache' / 'keepa_cache.sqlite3').touch()
    env = tmp_path / 'ph.env'; env.touch()
    c = dict(schema_version=1, repository_path=sg_config['repository_path'], release_commit='a'*40,
             python_path=sg_config['python_path'], sg_config_path=str(sg_path),
             ph_runtime_root=str(ph), ph_api_env_path=str(env),
             server_data_root=str(tmp_path / 'server'), port=8503)
    path = tmp_path / 'beta.json'; path.write_text(json.dumps(c))
    assert preflight(path) == c
    assert not Path(c['server_data_root']).exists()
    # A unified UI must not relax strict SG dirty/input/identity checks.
    sg_config['input_sha256']['candidate.csv'] = '0'*64
    sg_path.write_text(json.dumps(sg_config))
    from modules.beta_environment import BetaEnvironmentError
    with pytest.raises(BetaEnvironmentError):
        preflight(path)


@pytest.mark.parametrize('change', ['ph-port', 'sg-port', 'missing-ph-cache', 'overlap-sg', 'wrong-release', 'wrong-python'])
def test_unified_preflight_stops_wrong_or_overlapping_paths(profile, tmp_path, change):
    from modules.beta_environment import preflight, BetaEnvironmentError
    sg_path, sg_config, _ = profile
    ph = tmp_path / 'ph'; (ph / 'cache').mkdir(parents=True)
    cache = ph / 'cache' / 'keepa_cache.sqlite3'; cache.touch()
    env = tmp_path / 'ph.env'; env.touch()
    c = dict(schema_version=1, repository_path=sg_config['repository_path'], release_commit='a'*40,
             python_path=sg_config['python_path'], sg_config_path=str(sg_path),
             ph_runtime_root=str(ph), ph_api_env_path=str(env), server_data_root=str(tmp_path / 'server'), port=8503)
    if change in {'ph-port', 'sg-port'}: c['port'] = 8501 if change == 'ph-port' else 8502
    elif change == 'missing-ph-cache': cache.unlink()
    elif change == 'overlap-sg': c['server_data_root'] = sg_config['data_root']
    elif change == 'wrong-release': c['release_commit'] = 'b'*40
    else: c['python_path'] = str(tmp_path / 'other-python.exe')
    path = tmp_path / 'beta.json'; path.write_text(json.dumps(c))
    with pytest.raises(BetaEnvironmentError): preflight(path)
