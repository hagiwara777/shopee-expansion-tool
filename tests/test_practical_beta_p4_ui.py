"""A01-A06 synthetic PH/SG daily operations; no browser, server or real API."""
from dataclasses import replace
from io import StringIO
import csv
import json
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from modules.beta_work_store import BetaWorkStore, WorkStoreError
from modules.beta_workbench import BetaWorkBench
from modules.classification_workflow import ClassificationWorkflow
from modules.preparation_validity import PreparationSession
from test_classification_p3 import wf, ingest, human
from test_beta_workbench_p2 import product, selected
from test_sg_initial_beta import inventory
from test_expansion_gate_handoff import offline
from test_app_prelisting_gate import _run_gate_button

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT/'tests/fixtures/browser_e2e/ph_sg_practical_p4'


@pytest.fixture(autouse=True)
def network_forbidden(offline):
    pass


@pytest.fixture
def downloads(monkeypatch):
    captured = {}
    original = st.download_button
    def capture(label, data=None, **kwargs):
        if label.startswith('offline '):
            captured[label] = data
        return original(label, data, **kwargs)
    monkeypatch.setattr(st, 'download_button', capture)
    return captured


def upload(app, key, path):
    mime = 'application/json' if path.suffix == '.json' else 'text/csv'
    app.file_uploader(key=key).set_value((path.name, path.read_bytes(), mime))


def confirm_ui(app, key, asins):
    app.multiselect(key=key+'selected').set_value(asins)
    app.selectbox(key=key+'category').select(100578)
    app.text_input(key=key+'reviewer').set_value('Synthetic operator')
    app.text_area(key=key+'note').set_value('Synthetic current evidence, selected items only')
    app.run()
    app.checkbox(key=key+'human').check().run()
    app.button(key=key+'confirm_CATEGORY').click().run()
    assert not app.exception and not app.error, [e.value for e in app.error]
    app.selectbox(key=key+'brand').select(7).run()
    app.checkbox(key=key+'human').check().run()
    if 'workflow' in app.session_state:
        assert not app.button(key=key+'confirm_BRAND').disabled, json.dumps({
            'human': app.checkbox(key=key+'human').value, 'brand': app.selectbox(key=key+'brand').value,
            'records': [(r['revision'], r['assessment']['reasons'], r['assessment'].get('category_valid'))
                        for r in app.session_state['workflow'].bench.store.products()]})
    app.button(key=key+'confirm_BRAND').click().run()
    assert not app.exception


def action_ui(app, key, *, note='Synthetic human result'):
    app.text_area(key=key+'note').set_value(note).run()
    app.checkbox(key=key+'human').check().run()


def full_app(workspaces, market):
    script = f'from app_beta import render_beta\nrender_beta(practical_workspaces={workspaces!r})'
    app = AppTest.from_string(script, default_timeout=30)
    app.session_state['beta_marketplace'] = market
    app.run()
    assert not app.exception
    return app


def accept_batch(app, market, group):
    folder = FIXTURES/market
    upload(app, 'p4_producer', folder/(group+'_producer.json'))
    for field, suffix in [('candidate', 'candidate.csv'), ('product_text_safety', 'text.csv')]:
        upload(app, 'prelisting_gate_'+field+'_file', folder/(group+'_'+suffix))
    if market == 'PH':
        upload(app, 'prelisting_gate_image_safety_file', folder/(group+'_image.json'))
    app.file_uploader(key='prelisting_gate_inventory_files').set_value(
        [(market+'_inventory.csv', (folder/'inventory.csv').read_bytes(), 'text/csv')])
    app.run()
    assert not app.exception
    assert 'classification_current_batch' not in app.session_state
    _run_gate_button(app).click().run()
    assert not app.exception and 'classification_current_batch' in app.session_state
    key = 'p3_'+market+'_'
    app.text_input(key=key+'shop_0').set_value('synthetic-shop').run()
    app.checkbox(key=key+'current').check().run()
    app.button(key=key+'ingest').click().run()
    assert not app.exception and not app.error
    return app.session_state[key+'workflow']


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_a01_a03_a04_a05_a06_same_app_restart_a_then_resolver_b(market, tmp_path, downloads):
    workspaces = {m: {'db_path': str(tmp_path/(m+'.sqlite3')), 'shop_id':'synthetic-shop'} for m in ('PH','SG')}
    app = full_app(workspaces, market)
    assert next(b for b in app.button if b.label=='検索開始').disabled
    key = 'p3_'+market+'_'
    app.button(key=key+'create').click().run()
    upload(app, key+'catalog', ROOT/f'tests/fixtures/browser_e2e/ph_sg_classification_p3/{market}_context.json')
    app.run()
    current = accept_batch(app, market, 'A')
    assert len(current.bench.store.products()) == 10
    subset = ['B000000001','B000000002','B000000003']
    confirm_ui(app, key, subset)
    assert len(current.bench.prepared_pool()) == 3
    assert sum(r['category'] is None for r in current.bench.store.products()) == 7
    poolkey = key+'pool_'
    app.multiselect(key=poolkey+'selected').set_value(subset).run()
    app.button(key=poolkey+'output_False').click().run()
    assert not app.exception
    rows = list(csv.DictReader(StringIO(downloads['offline CSVを取得'].decode('utf-8-sig'))))
    assert {r['asin'] for r in rows} == set(subset)
    assert all(r['marketplace']==market and r['listing_ready']=='FALSE'
               and r['output_scope']=='PH_SG_P1_OFFLINE' for r in rows)
    assert all(r['group_key']==market+'|100578|7' for r in rows)
    assert downloads['offline TXTを取得'].startswith(b'\xef\xbb\xbf')
    assert all(a in downloads['offline TXTを取得'].decode('utf-8-sig') for a in subset)
    assert not current.bench.store.operations()
    assert all(r['listing_progress']=='WAITING' for r in current.bench.store.products())
    app.run()
    assert not any(e.key==poolkey+'csv' for e in app.get('download_button'))
    action_ui(app, poolkey)
    app.button(key=poolkey+'output_True').click().run()
    op = current.bench.store.operations()[0]
    opkey = key+'listing_'+op['operation_id']
    action_ui(app, opkey)
    app.button(key=opkey+'finish').click().run()
    assert current.bench.store.operations()[0]['state']=='UNKNOWN'
    assert not current.bench.prepared_pool()
    history = current.bench.store.history()
    # New Streamlit session: no old facts/confirmations or download authority.
    resumed = full_app(workspaces, market)
    new = resumed.session_state[key+'workflow']
    assert new.session.scope != current.session.scope
    assert not new.bench.prepared_pool()
    assert new.bench.store.operations()[0]['state']=='UNKNOWN'
    assert new.bench.store.history()[:len(history)] == history
    # Recovery is reachable even before current catalog/Gate material is loaded.
    resumed.selectbox(key=opkey+'outcome').select('CANCELLED').run()
    action_ui(resumed, opkey, note='Synthetic result checked; no actual submission')
    resumed.button(key=opkey+'finish').click().run()
    assert not resumed.exception and new.bench.store.operations()[0]['state']=='CANCELLED'
    upload(resumed, key+'catalog', ROOT/f'tests/fixtures/browser_e2e/ph_sg_classification_p3/{market}_context.json')
    resumed.run()
    new = accept_batch(resumed, market, 'B')
    assert len(new.bench.store.products()) == 12
    assert not new.bench.prepared_pool()
    confirm_ui(resumed, key, ['B000000011','B000000012'])
    assert len(new.bench.prepared_pool()) == 2
    assert new.bench.store.products()[-1]['batches'][0]['source_type']=='RESOLVER'
    # A requires current material and a fresh human decision, then shares B pool.
    accept_batch(resumed, market, 'A')
    assert len(new.bench.prepared_pool()) == 2
    confirm_ui(resumed, key, subset)
    assert len(new.bench.prepared_pool()) == 5
    resumed.button(key=key+'reload').click().run()
    assert not resumed.exception and not new.bench.prepared_pool()
    resumed.run()
    assert not new.bench.prepared_pool()  # Same-content new acquisition never revives decisions.
    assert any('要再確認' in ' '.join(map(str,d.value.to_numpy().ravel())) for d in resumed.dataframe)
    # Country switch drops all transient state and opens only that market's DB.
    before = new.bench.store.history()
    other = 'SG' if market=='PH' else 'PH'
    resumed.selectbox(key='beta_marketplace').select(other).run()
    assert not resumed.exception and 'p4_producer_rows' not in resumed.session_state
    assert new.bench.store.history()==before
    assert any(b.key=='p3_'+other+'_create' for b in resumed.button)


def controls(wf):
    app = AppTest.from_string("""
import streamlit as st
from modules.practical_beta_ui import render_practical_controls
render_practical_controls(st.session_state['workflow'], key='test_')
""", default_timeout=30)
    app.session_state['workflow'] = wf
    app.run()
    assert not app.exception
    return app


def test_disjoint_b_preserves_a_but_reacquired_same_a_needs_fresh_review(wf):
    ingest(wf)
    human(wf, ['B000000001'], 'CATEGORY', 100578)
    human(wf, ['B000000001'], 'BRAND', 7)
    market = wf.session.scope.marketplace
    app = AppTest.from_string(f"""
import streamlit as st
from modules.practical_beta_ui import render_source_settings
render_source_settings({market!r}, db_path='synthetic.sqlite3', shop_id='synthetic-shop')
""", default_timeout=30)
    app.session_state['p3_'+market+'_workflow'] = wf
    app.run()
    upload(app, 'p4_producer', FIXTURES/market/'B_producer.json')
    app.run()
    assert not app.exception and len(wf.bench.prepared_pool()) == 1
    upload(app, 'p4_producer', FIXTURES/market/'A_producer.json')
    app.run()
    assert not app.exception and not wf.bench.prepared_pool()
    ingest(wf)  # Same bytes, newly acquired target: old HUMAN must not revive.
    assert not wf.bench.prepared_pool()
    assert wf.bench.store.products()[0]['category'] is None
    assert any(json.loads(e['payload']).get('category') for e in wf.bench.store.history())


def test_a05_all_five_states_and_explicit_return(wf, downloads):
    ingest(wf)
    human(wf, ['B000000001'], 'CATEGORY',100578)
    human(wf, ['B000000001'], 'BRAND',7)
    app = controls(wf)
    app.multiselect(key='test_pool_selected').select('B000000001').run()
    action_ui(app, 'test_pool_')
    app.button(key='test_pool_output_True').click().run()
    operation = wf.bench.store.operations()[0]
    opkey = 'test_listing_'+operation['operation_id']
    app.selectbox(key=opkey+'outcome').select('SUCCESS').run()
    action_ui(app, opkey)
    app.button(key=opkey+'finish').click().run()
    assert wf.bench.store.products()[0]['state']=='AWAITING_LISTING'
    app.multiselect(key='test_listing_selected').select('B000000001')
    app.selectbox(key='test_listing_action').select('ERROR').run()
    action_ui(app,'test_listing_')
    app.button(key='test_listing_save').click().run()
    assert wf.bench.store.products()[0]['state']=='ERROR'
    app.selectbox(key='test_listing_action').select('RETURN').run()
    action_ui(app,'test_listing_')
    app.button(key='test_listing_save').click().run()
    assert wf.bench.store.products()[0]['state']=='WAITING'
    market = wf.session.scope.marketplace
    wf.supply_inventory((inventory('B000000001',marketplace=market,name=market+'_shop.csv'),), expected_shops=('synthetic-shop',),
                        reference='SYNTHETIC_CURRENT_MATCH', confirmed_current=True)
    app.run()
    assert not app.exception and wf.bench.store.products()[0]['state']=='LISTED'
    assert not wf.bench.prepared_pool()
    wf.session.begin_catalog_refresh()
    app.run()
    assert not app.exception and wf.bench.store.products()[0]['state']=='LISTED'
    assert wf.bench.store.products()[0]['preparation_state']=='RECHECK'


def test_a02_safety_hold_notes_auto_and_unknown_provenance_never_grant_output(wf):
    market = wf.session.scope.marketplace
    records = [product(market, title='Synthetic rechargeable battery'),
               product(market,'B000000002')]
    ingest(wf, records)
    for kind, option in [('CATEGORY',100578),('BRAND',7)]:
        human(wf, ['B000000001','B000000002'], kind,option)
    app = controls(wf)
    assert len(wf.bench.prepared_pool())==1
    app.selectbox(key='test_queue').select('Safety確認待ち').run()
    assert any('B000000001' in str(d.value) for d in app.dataframe)
    app.multiselect(key='test_listing_selected').select('B000000001')
    app.selectbox(key='test_listing_action').select('EVIDENCE_REVIEWED').run()
    action_ui(app,'test_listing_')
    app.button(key='test_listing_save').click().run()
    assert wf.bench.store.products()[0]['state']=='RECHECK'
    assert len(wf.bench.prepared_pool())==1
    app.selectbox(key='test_queue').select('全商品').run()
    app.multiselect(key='test_selected').set_value(['B000000002']).run()
    assert app.button(key='test_auto_CATEGORY').disabled  # Explicit action confirmation still required.
    app.text_input(key='test_reviewer').set_value('Synthetic rule operator')
    app.text_area(key='test_note').set_value('Synthetic positive rule evidence').run()
    app.checkbox(key='test_human').check().run()
    app.button(key='test_auto_CATEGORY').click().run()
    assert not app.exception
    assert wf.bench.store.products()[1]['category']['authority']=='AUTO_RULE'
    assert wf.bench.store.products()[1]['brand'] is None
    with pytest.raises(ValueError):
        wf.session.output([wf.bench.store.products()[1]], operational=True)


def test_a06_storage_failure_and_stale_reservation_fail_closed(wf, monkeypatch, downloads):
    ingest(wf)
    human(wf,['B000000001'],'CATEGORY',100578)
    human(wf,['B000000001'],'BRAND',7)
    app = controls(wf)
    app.multiselect(key='test_pool_selected').select('B000000001').run()
    original = wf.bench.store.write
    def fail(*a, **k):
        raise WorkStoreError('Synthetic commit failure')
    monkeypatch.setattr(wf.bench.store,'write',fail)
    app.button(key='test_pool_output_False').click().run()
    assert not app.exception and app.error and not downloads
    monkeypatch.setattr(wf.bench.store,'write',original)
    app.run()
    action_ui(app,'test_pool_')
    app.button(key='test_pool_output_True').click().run()
    operation = wf.bench.store.operations()[0]
    wf.session.begin_fact_refresh('B000000001')
    app.run()
    opkey = 'test_listing_'+operation['operation_id']
    app.selectbox(key=opkey+'outcome').select('SUCCESS').run()
    action_ui(app, opkey)
    app.button(key=opkey+'finish').click().run()
    assert not app.exception and app.error
    assert wf.bench.store.operations()[0]['state']=='PENDING'
    assert not wf.bench.prepared_pool()
    app.selectbox(key=opkey+'outcome').select('FAILED').run()
    action_ui(app,opkey)
    app.button(key=opkey+'finish').click().run()
    assert not app.exception and wf.bench.store.operations()[0]['state']=='FAILED'


@pytest.mark.parametrize('semantic', ['NO_SIGNAL','REVIEW'])
def test_a02_target_weapon_replay_human_review_deletion_and_wrong_market(wf, semantic):
    from modules.image_inspection_policy import load_image_inspection_policy
    from modules.product_review import WeaponImageReviewSession
    from modules.sg_beta_workbench import _sources, recommendation, capture_weapon_review
    from modules.practical_weapon_ui import weapon_source_binding
    from test_product_review import inspect
    market = wf.session.scope.marketplace
    r = product(market, root=min(load_image_inspection_policy(market).target_roots))
    _, text, _, _ = _sources(r)
    item = recommendation(r, marketplace=market)
    images = {**r['weapon']['images'], 'image_urls':['https://m.media-amazon.com/images/I/SYNTHETIC.jpg']}
    review = WeaponImageReviewSession(market)
    review.supply(item, text=text.facts_by_asin[r['asin']], images=images)
    r['weapon'] = capture_weapon_review(item, review, images=images)
    ingest(wf,[r])
    human(wf,[r['asin']],'CATEGORY',100578)
    human(wf,[r['asin']],'BRAND',7)
    assert not wf.bench.prepared_pool()
    inspect(review,item,semantic)
    bundle = dict(schema='PH_SG_P4_WEAPON_OFFLINE_V1',marketplace=market,asin=r['asin'],
        source_binding=weapon_source_binding(r,market),weapon=capture_weapon_review(item,review,images=images))
    app = controls(wf)
    key = 'test_weapon_'+r['asin']+'_'
    app.file_uploader(key=key+'replay').set_value(('mock.json',json.dumps(bundle).encode(),'application/json')).run()
    app.button(key=key+'load').click().run()
    assert not app.exception and not app.error
    if semantic=='REVIEW':
        assert not wf.bench.prepared_pool()
        app.text_area(key=key+'note').set_value('Synthetic weapon suspicion checked').run()
        app.checkbox(key=key+'human').check().run()
        app.button(key=key+'ALLOW_PREPARATION').click().run()
        assert not app.exception
    else:
        assert not any(c.key==key+'human' for c in app.checkbox)
    confirm_ui(app,'test_',[r['asin']])
    assert wf.bench.prepared_pool()
    app.file_uploader(key=key+'replay').set_value(None).run()
    assert not app.exception and not wf.bench.prepared_pool()
    # Other-market inspection and prior human decision cannot be copied in.
    bundle['marketplace'] = 'SG' if market=='PH' else 'PH'
    app.file_uploader(key=key+'replay').set_value(('wrong.json',json.dumps(bundle).encode(),'application/json')).run()
    app.button(key=key+'load').click().run()
    assert not app.exception and app.error and not wf.bench.prepared_pool()


def test_a06_same_country_shop_change_discards_transient_state(tmp_path):
    workspaces = {'PH': {'db_path':str(tmp_path/'shop-a.sqlite3'),'shop_id':'shop-a'}}
    BetaWorkStore.create(workspaces['PH']['db_path'],marketplace='PH',shop_id='shop-a')
    BetaWorkStore.create(tmp_path/'shop-b.sqlite3',marketplace='PH',shop_id='shop-b')
    app = AppTest.from_string("""
import streamlit as st
from app_beta import render_beta
render_beta(practical_workspaces=st.session_state['workspaces'])
""", default_timeout=30)
    app.session_state['workspaces'] = workspaces
    app.run()
    original = app.session_state['p3_PH_workflow']
    app.session_state['p4_producer_rows'] = ({'candidate_asin':'B000000001'},)
    # Configuration is supplied by the caller, not by an untrusted product row.
    app.session_state['workspaces'] = {'PH': {'db_path':str(tmp_path/'shop-b.sqlite3'),'shop_id':'shop-b'}}
    app.run()
    assert not app.exception and 'p4_producer_rows' not in app.session_state
    assert app.session_state['p3_PH_workflow'].session.scope.shop_id=='shop-b'
    assert original.bench.store.products()==()
