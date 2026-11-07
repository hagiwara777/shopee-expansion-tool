"""Synthetic PH/SG shared controls; no browser, server or real API."""
import json
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from modules.beta_work_store import WorkStoreError
from test_classification_p3 import wf, ingest, human
from test_beta_workbench_p2 import product
from test_sg_initial_beta import inventory
from test_expansion_gate_handoff import offline

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
