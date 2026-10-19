"""Same common PH/SG screen with synthetic P5 connections, no network."""
import pytest
from streamlit.testing.v1 import AppTest

from modules.p5_runtime import P5Runtime
from test_p5_runtime import scope_for, runtime_for, forbid_network
from test_expansion_gate_handoff import result, offline
from test_p5_candidates import flow, sdk, current_material, SOURCE
from test_p5_candidates import updating_flow


def update_entry(runtime):
    from modules.p5_ui import render_material_update
    render_material_update(runtime)


def test_t07_update_display_rerenders_zero_send(updating_flow, monkeypatch):
    rt = updating_flow
    before = list(rt.ledger.data['reservations'])
    monkeypatch.setattr(rt, 'amazon_client', lambda: pytest.fail('rerender attempted send'))
    app = AppTest.from_function(update_entry, args=(rt,), default_timeout=30).run()
    assert not app.exception and app.button(key='p5_update').disabled
    app.multiselect(key='p5_update_asins').select('B000000001').run()
    app.run()
    assert not app.exception and rt.ledger.data['reservations'] == before


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


def test_two_stage_expansion_ui_through_safety_and_saved_classification(flow, monkeypatch):
    from test_app_prelisting_gate import _run_gate_button, _empty_inventory_csv
    from test_practical_beta_p4_ui import confirm_ui
    client, calls = sdk(flow)
    monkeypatch.setattr(flow, 'amazon_client', lambda: client)
    current_material(flow)
    app = app_for(flow)
    next(w for w in app.text_input if w.label == 'ASIN').set_value('B000000000')
    next(w for w in app.button if w.label == '検索開始').click().run()
    assert not app.exception and len(calls) == 4
    assert not flow.candidates.data['selections']
    key = 'p5_select_EXPANSION_'
    app.multiselect(key=key+'asins').set_value(['B000000001'])
    app.text_input(key=key+'reviewer').set_value('Synthetic operator')
    app.text_input(key=key+'note').set_value('Selected synthetic passive product').run()
    app.checkbox(key=key+'human').check().run()
    app.button(key=key+'fix').click().run()
    assert not app.exception and len(flow.candidates.data['selections']) == 1
    assert 'classification_current_batch' not in app.session_state
    market = flow.scope.marketplace
    app.file_uploader(key='prelisting_gate_inventory_files').set_value(
        [(market+'_inventory.csv', _empty_inventory_csv(market), 'text/csv')]).run()
    _run_gate_button(app).click().run()
    assert not app.exception and 'classification_current_batch' in app.session_state
    app.text_input(key='p5_intake_shop_0').set_value('22').run()
    app.checkbox(key='p5_intake_current').check().run()
    app.button(key='p5_intake_ingest').click().run()
    assert not app.exception and not app.error, [e.value for e in app.error]
    confirm_ui(app, 'p5_work_', ['B000000001'])
    assert [r['asin'] for r in flow.workflow.bench.prepared_pool()] == ['B000000001']
    assert len(calls) == 4
    before = flow.ledger.path.read_bytes()
    app.run()
    assert flow.ledger.path.read_bytes() == before


def test_resolver_identity_widget_never_selects_unknown_or_mismatch(flow):
    from modules.asin_resolver import verify_selected_rows
    from streamlit.testing.v1 import AppTest
    client, _ = sdk(flow)
    proposed = [{'source_id':SOURCE['source_id'], 'input_title':SOURCE['input_title'],
                 'asin':'B000000004', 'selected':True}]
    flow.candidates.propose_resolver(proposed, human_confirmed=True, reviewer='operator', note='source checked')
    rows = verify_selected_rows(proposed, client)
    def selection_entry(runtime, rows):
        from modules.p5_ui import render_p5_selection
        render_p5_selection(runtime, 'RESOLVER', rows)
    app = AppTest.from_function(selection_entry, args=(flow, rows), default_timeout=30).run()
    key = 'p5_select_RESOLVER_'
    app.multiselect(key=key+'asins').set_value(['B000000004'])
    app.text_input(key=key+'reviewer').set_value('operator')
    app.text_input(key=key+'note').set_value('Synthetic specification checked').run()
    app.checkbox(key=key+'human').check().run()
    assert app.button(key=key+'fix').disabled
    app.selectbox(key=key+'identity').select('MISMATCH').run()
    app.checkbox(key=key+'human').check().run()
    assert app.button(key=key+'fix').disabled and not flow.candidates.data['selections']
    app.selectbox(key=key+'identity').select('CONFIRMED').run()
    app.checkbox(key=key+'human').check().run()
    app.button(key=key+'fix').click().run()
    assert not app.exception and len(flow.candidates.data['selections']) == 1


def test_country_switch_reopens_same_budget_and_preserves_other_market(flow):
    from pathlib import Path
    market = flow.scope.marketplace
    other_market = 'SG' if market == 'PH' else 'PH'
    other = runtime_for(Path(flow.scope.root), other_market, preparation_limit=4)
    charged = flow.ledger.reserve('keepa', units=1, tokens=2)
    flow.ledger.finish(charged, success=True, actual_tokens=1)
    app = AppTest.from_function(entry, args=({market:flow, other_market:other},), default_timeout=30)
    app.session_state['beta_marketplace'] = market
    try:
        app.run()
        app.selectbox(key='beta_marketplace').select(other_market).run()
        assert not app.exception and not other.ledger.data['reservations']
        assert flow.ledger is None
        app.selectbox(key='beta_marketplace').select(market).run()
        app.button(key='p5_start').click().run()
        assert not app.exception and len(flow.ledger.data['reservations']) == 1
        assert flow.ledger.data['reservations'][0]['tokens'] == 2
        assert other.ledger is None
    finally:
        other.close()


def test_json_scope_loads_resolver_plan_without_creating_permit(flow):
    from dataclasses import asdict
    import json
    from pathlib import Path
    config = Path(flow.scope.root) / 'synthetic-scope.json'
    config.write_text(json.dumps([asdict(flow.scope)]), encoding='utf-8')
    before = flow.ledger.path.read_bytes()
    source = ('import runpy, sys\n'
              'previous = sys.argv\n'
              f"sys.argv = ['app_beta.py', '--p5-config', {str(config)!r}]\n"
              "try:\n    runpy.run_path('app_beta.py', run_name='__main__')\n"
              'finally:\n    sys.argv = previous\n')
    app = AppTest.from_string(source, default_timeout=30)
    app.session_state['beta_marketplace'] = flow.scope.marketplace
    app.run()
    assert not app.exception
    assert app.button(key='p5_start').disabled
    assert flow.ledger.path.read_bytes() == before

@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_production_attribute_button_is_disabled_and_rerender_reads_no_credentials(tmp_path, monkeypatch, market):
    from test_p5_operation_preflight import scoped, production
    scope, adapter, observed, bind = scoped(tmp_path, market)
    production(adapter, observed, scope, tmp_path, monkeypatch)
    bind()
    rt = adapter.compose(scope, approval_reference='SYNTHETIC')
    rt.checkpoint_hook = lambda *a: None
    rt.start()
    try:
        monkeypatch.setattr(rt, 'secrets', lambda *a: pytest.fail('credential read during render'))
        # Catalog presence cannot enable the production Attribute button.
        rt.category_receipt = {'fixture':True}
        app = app_for(rt)
        assert app.button(key='p5_attribute').disabled
        assert any('取得専用の承認' in c.value for c in app.caption)
        assert any('属性値の一致は保証しません' in c.value for c in app.caption)
        app.run()
        assert not app.exception and app.button(key='p5_attribute').disabled
        assert not rt.ledger.data['reservations']
    finally:
        rt.close()
