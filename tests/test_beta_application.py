"""Single-app country routing with synthetic data and no external calls."""
from dataclasses import asdict
import json
import logging
import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from modules.beta_runtime_paths import beta_runtime_paths, current_beta_paths
from test_sg_live_runtime import grant, factory
from test_sg_beta_release import activation
from test_sg_beta_environment import profile

ROOT = Path(__file__).resolve().parents[1]


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


def test_one_selector_routes_shared_tabs_and_clears_transient_country_state(monkeypatch):
    app = AppTest.from_file(str(ROOT / 'app_beta.py'), default_timeout=15).run()
    assert not app.exception
    assert {'ASIN Expansion', 'ASIN Resolver', '出品前保安ゲート', 'Category Mapper'} <= {t.label for t in app.tabs}
    assert [s.label for s in app.selectbox].count('対象国') == 1
    assert not any(s.label in {'対象市場', 'Marketplace'} for s in app.selectbox)
    assert any('対象国: PH' in m.value for m in app.markdown)
    app.session_state['category_mapper_recommendations'] = ('PH_PRIVATE_CONFIRMATION',)
    app.session_state['prelisting_gate_exports'] = 'PH_PRIVATE_EXPORT'
    app.session_state['category_mapper_temporary_access_token'] = 'synthetic-ph-token'
    app.selectbox(key='beta_marketplace').select('SG').run()
    assert not app.exception
    assert any('対象国: SG' in m.value for m in app.markdown)
    assert 'category_mapper_recommendations' not in app.session_state
    assert 'prelisting_gate_exports' not in app.session_state
    assert 'category_mapper_temporary_access_token' not in app.session_state
    assert any('SGの利用設定' in i.value for i in app.info)
    app.selectbox(key='beta_marketplace').select('PH').run()
    assert not app.exception
    assert any('対象国: PH' in m.value for m in app.markdown)


def test_country_change_without_widget_callback_still_clears_old_state():
    app = AppTest.from_file(str(ROOT / 'app_beta.py'), default_timeout=15).run()
    app.session_state['prelisting_gate_exports'] = 'synthetic-ph-export'
    app.session_state['beta_marketplace'] = 'SG'
    app.run()
    assert not app.exception and 'prelisting_gate_exports' not in app.session_state


def test_invalid_market_never_renders_workflow():
    app = AppTest.from_file(str(ROOT / 'app_beta.py'))
    app.session_state['beta_marketplace'] = 'MY'
    app.run()
    assert not app.exception and app.error
    assert not app.tabs


def test_sg_switch_close_and_reopen_preserve_actual_persistent_budget(tmp_path, grant, activation, monkeypatch):
    from modules import sg_live_runtime, sg_beta_environment
    path = tmp_path / 'grant.json'
    path.write_text(json.dumps(asdict(grant)), encoding='utf-8')
    data = tmp_path / 'sg-data'
    c = {'grant_path': str(path), 'api_env_path': None, 'data_root': str(data)}
    monkeypatch.setattr(sg_beta_environment, 'preflight', lambda p: c)
    actual_runtime = sg_live_runtime.SGLiveRuntime
    calls = []
    def local_runtime(**kwargs):
        return actual_runtime(**kwargs, fresh_client_factory=factory(calls))
    monkeypatch.setattr(sg_live_runtime, 'SGLiveRuntime', local_runtime)
    source = f"from app_beta import render_beta\nrender_beta(sg_config_path={str(tmp_path / 'synthetic.json')!r})"
    # This exercises all four real work tabs with a cold Windows CI runner.
    # Use the same bounded wait as the installed-beta UI verification; retain
    # every routing, lock, claim and spend assertion below.
    app = AppTest.from_string(source, default_timeout=60).run()
    app.selectbox(key='beta_marketplace').select('SG').run()
    assert not app.exception and not calls
    app.button(key='sg_live_open').click().run()
    assert not app.exception and not app.error and not calls
    first = app.session_state['sg_live_runtime']
    app.button(key='sg_live_refresh_catalog').click().run()
    assert not app.exception and first.ledger.data['catalog_requests'] == 1
    ledger = data / grant.digest / 'request-ledger.json'
    claim = data / 'claims' / f'{grant.digest}.json'
    previous_ledger, previous_claim = ledger.read_bytes(), claim.read_bytes()
    app.selectbox(key='beta_marketplace').select('PH').run()
    assert not app.exception and 'sg_live_runtime' not in app.session_state
    # The old process lock must be released, rather than silently reinitializing.
    app.selectbox(key='beta_marketplace').select('SG').run()
    app.button(key='sg_live_open').click().run()
    second = app.session_state['sg_live_runtime']
    try:
        assert not app.exception and not app.error
        assert second is not first
        assert second.ledger.data['catalog_requests'] == 1
        assert ledger.read_bytes() == previous_ledger and claim.read_bytes() == previous_claim
        assert calls == ['fresh token', '/api/v2/product/get_category']
        assert second.ledger.data['openai']['requests'] == 0
    finally:
        second.close()


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
