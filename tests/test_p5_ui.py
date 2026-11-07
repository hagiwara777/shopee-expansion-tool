"""Individual P5 components with synthetic connections, no network."""
import pytest
from streamlit.testing.v1 import AppTest

from modules.p5_runtime import P5Runtime
from test_p5_runtime import scope_for, forbid_network
from test_expansion_gate_handoff import offline
from test_p5_candidates import flow, sdk, SOURCE
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
    from modules.p5_ui import render_p5_start, render_p5_workspace
    runtime = next(iter(runtimes.values()))
    if render_p5_start(runtime):
        render_p5_workspace(runtime)


def app_for(runtime):
    app = AppTest.from_function(entry, args=({runtime.scope.marketplace: runtime},), default_timeout=30)
    app.session_state['beta_marketplace'] = runtime.scope.marketplace
    app.run()
    assert not app.exception
    return app


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_unapproved_settings_and_rerenders_have_no_side_effects(tmp_path, market, forbid_network, monkeypatch):
    runtime = P5Runtime(scope_for(tmp_path, market))
    monkeypatch.setattr('modules.config.load_settings', lambda: pytest.fail('P5 reached legacy settings'))
    before = set(tmp_path.rglob('*'))
    app = app_for(runtime)
    assert app.button(key='p5_start').disabled
    app.run()
    assert not app.exception and runtime.ledger is None
    assert set(tmp_path.rglob('*')) == before
    assert not app.file_uploader






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
