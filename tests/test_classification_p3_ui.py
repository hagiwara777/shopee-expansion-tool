"""Normal app -> Gate material -> shared P3 confirmation, offline AppTest."""
from dataclasses import asdict
import json

import pytest
from streamlit.testing.v1 import AppTest

from modules.product_text_safety import product_text_safety_fact_to_payload, parse_product_text_safety_sidecar
from modules.prelisting_candidate_csv import parse_prelisting_candidate_csv
from test_classification_p3 import wf, ingest, human
from test_beta_workbench_p2 import product
from test_expansion_gate_handoff import offline, result, inventory
from test_app_prelisting_gate import _run_gate_button


def test_shared_ui_three_selected_products_and_evidence_change(wf):
    market, shop = wf.session.scope.marketplace, wf.session.scope.shop_id
    ingest(wf,[product(market,f'B{i:09d}') for i in range(1,11)])
    script = """
import streamlit as st
from modules.classification_workflow_ui import render_classification_controls
render_classification_controls(st.session_state['workflow'])
"""
    app = AppTest.from_string(script,default_timeout=30)
    app.session_state['workflow'] = wf
    app.run()
    app.multiselect(key='p3_selected').set_value(['B000000001','B000000002','B000000003']).run()
    app.selectbox(key='p3_category').select(100578).run()
    app.text_input(key='p3_reviewer').set_value('Synthetic human').run()
    app.text_area(key='p3_note').set_value('Current product-specific evidence').run()
    app.checkbox(key='p3_human').check().run()
    app.button(key='p3_confirm_CATEGORY').click().run()
    assert not app.exception and not wf.bench.prepared_pool()
    assert len([r for r in wf.bench.store.products() if r['category']]) == 3
    assert not app.checkbox(key='p3_human').value
    app.selectbox(key='p3_brand').select(7).run()
    app.checkbox(key='p3_human').check().run()
    app.button(key='p3_confirm_BRAND').click().run()
    assert not app.exception and len(wf.bench.prepared_pool()) == 3
    wf.session.begin_fact_refresh('B000000001')
    app.run()
    assert not app.exception and not app.checkbox(key='p3_human').value
    assert app.button(key='p3_confirm_BRAND').disabled
    assert len(wf.bench.prepared_pool()) == 2


def test_actual_normal_gate_connects_to_p1_p2_and_changed_material_stops(wf, offline):
    market, shop = wf.session.scope.marketplace, wf.session.scope.shop_id
    r = product(market)
    source = r['source']
    candidate = source['candidate'].encode('utf-8')
    parsed = parse_prelisting_candidate_csv(candidate,filename='candidate.csv')
    text = parse_product_text_safety_sidecar(source['text'].encode('utf-8'),filename='text.csv',
        candidate_content=candidate,candidates=parsed).facts_by_asin[r['asin']]
    generated = result(title=r['facts']['fields']['title']['value'],root=3210981)
    generated.rows[0].update(brand='Synthetic Maker',category='Headphones',
        fetched_at=r['facts']['fields']['title']['fetched_at'],classification_facts=r['facts'],
        product_text_safety_fact=product_text_safety_fact_to_payload(text),
        ph_image_safety_fact=r['weapon']['images'])
    ctx = wf.session.classification_context()
    bundle = dict(schema='PH_SG_P3_OFFLINE_V1',marketplace=market,version=ctx.catalog.catalog_version,
        revision=ctx.classification.revision,nodes=[asdict(n) for n in ctx.catalog.nodes],
        rules=[asdict(n) for n in ctx.rules],aliases=[asdict(n) for n in ctx.aliases],
        brands=[asdict(n) for n in ctx.brands.values()])
    script = f"from app_beta import render_beta\nrender_beta(classification_workspaces={{{market!r}:{{'db_path':{str(wf.bench.store.path)!r},'shop_id':{shop!r}}}}})"
    app = AppTest.from_string(script,default_timeout=30)
    app.session_state['beta_marketplace'] = market
    app.session_state['result'] = generated
    app.run()
    assert not app.exception
    app.file_uploader(key='p3_'+market+'_catalog').set_value(('catalog.json',json.dumps(bundle).encode(),'application/json')).run()
    inventory(app,market)
    app.button(key='expansion_gate_use').click().run()
    _run_gate_button(app).click().run()
    assert not app.exception and 'classification_current_batch' in app.session_state
    key='p3_'+market+'_'
    app.text_input(key=key+'shop_0').set_value(shop).run()
    app.checkbox(key=key+'current').check().run()
    app.button(key=key+'ingest').click().run()
    assert not app.exception and not app.error
    current = app.session_state[key+'workflow']
    assert current.bench.store.products()[0]['facts'] == r['facts']
    app.multiselect(key=key+'selected').select(r['asin']).run()
    app.selectbox(key=key+'category').select(100578).run()
    app.text_input(key=key+'reviewer').set_value('Synthetic human').run()
    app.text_area(key=key+'note').set_value('Current product evidence').run()
    app.checkbox(key=key+'human').check().run()
    app.button(key=key+'confirm_CATEGORY').click().run()
    app.selectbox(key=key+'brand').select(7).run()
    app.checkbox(key=key+'human').check().run()
    app.button(key=key+'confirm_BRAND').click().run()
    assert not app.exception and len(current.bench.prepared_pool()) == 1
    # A Fact absent from the CSV still invalidates an old selection immediately.
    generated.rows[0]['classification_facts']['fields']['model']['value'] = 'Changed model'
    app.run()
    assert not app.exception and not current.bench.prepared_pool()
    assert not app.checkbox(key=key+'human').value
    # Removing current Gate material immediately revokes current inventory proof.
    app.file_uploader(key='prelisting_gate_inventory_files').set_value([]).run()
    assert not app.exception and 'classification_current_batch' not in app.session_state
    assert not current.bench.prepared_pool()
