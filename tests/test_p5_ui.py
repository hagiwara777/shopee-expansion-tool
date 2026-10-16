"""Same common PH/SG screen with synthetic P5 connections, no network."""
import pytest
from streamlit.testing.v1 import AppTest

from modules.p5_runtime import P5Runtime
from test_p5_runtime import scope_for, runtime_for, forbid_network
from test_expansion_gate_handoff import result, offline


@pytest.fixture(autouse=True)
def ui_offline(offline):
    pass


def entry(runtimes):
    from app_beta import render_beta
    render_beta(p5_runtimes=runtimes)


def app_for(runtime):
    app = AppTest.from_function(entry, args=({runtime.scope.marketplace: runtime},), default_timeout=30)
    app.session_state['beta_marketplace'] = runtime.scope.marketplace
    app.run()
    assert not app.exception
    return app


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_unapproved_settings_and_rerenders_have_no_side_effects(tmp_path, market, forbid_network, monkeypatch):
    runtime = P5Runtime(scope_for(tmp_path, market))
    monkeypatch.setattr('app.load_settings', lambda: pytest.fail('P5 reached legacy settings'))
    before = set(tmp_path.rglob('*'))
    app = app_for(runtime)
    assert app.button(key='p5_start').disabled
    app.run()
    assert not app.exception and runtime.ledger is None
    assert set(tmp_path.rglob('*')) == before
    assert not app.file_uploader


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_common_screen_uses_only_injected_client_and_filters_do_not_send(tmp_path, market, forbid_network, monkeypatch):
    runtime = runtime_for(tmp_path, market)
    calls = []
    def legacy(*a, **k):
        pytest.fail('P5 reached unbounded legacy API factory')
    monkeypatch.setattr('app.create_amazon_data_client', legacy)
    monkeypatch.setattr('app.load_settings', legacy)
    class Client:
        def find_related_products(self, **kwargs):
            calls.append(kwargs)
            return result()
    monkeypatch.setattr(runtime, 'amazon_client', lambda: Client())
    try:
        app = app_for(runtime)
        assert len(app.tabs) >= 4
        assert not calls and not any(w.key == 'p4_producer' for w in app.file_uploader)
        assert not any(w.key.endswith('replay') for w in app.file_uploader)
        app.text_input(key='f12_expansion_min').set_value('1000')
        app.selectbox(key='f12_expansion_rating').select('4.5以上')
        app.button(key='f12_expansion_apply').click().run()
        assert not calls and not app.exception
        next(w for w in app.text_input if w.label == 'ASIN').set_value('B000000000')
        next(w for w in app.button if w.label == '検索開始').click().run()
        assert not app.exception
        assert len(calls) == 1 and calls[0]['filter_criteria'].rating_min == 4.5
        app.run()
        assert len(calls) == 1
    finally:
        runtime.close()
