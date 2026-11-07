"""Shared P3 confirmation using an offline component AppTest."""
from streamlit.testing.v1 import AppTest

from test_classification_p3 import wf, ingest
from test_beta_workbench_p2 import product


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
