"""Synthetic release-state tests; never adopt or run the normal environment."""

import csv
import json
from io import StringIO
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from modules.category_mapper_sg import confirm_sg_brand
from modules.category_mapper_sg_brand_workflow import SGBrandWorkflow
from modules.category_mapper_sg_preparation import build_sg_beta_preparation_files, build_sg_preparation_candidate_files
from modules import sg_beta_release as release
from sls_category_sg_support import sg_item
from test_category_mapper_sg_brand import client_for, payload, raw_brand
from test_product_review import evidence, supply, inspect
from test_sg_brand_confirmation_ui import preview


@pytest.fixture
def activation(tmp_path, monkeypatch):
    root = tmp_path / 'release'
    directory = root / 'governance'
    (directory / 'schemas').mkdir(parents=True)
    state = json.loads((release.ROOT / 'governance/state.json').read_text(encoding='utf-8'))
    state['markets']['SG']['operation'] = 'ACTIVE'
    schema = (release.ROOT / 'governance/schemas/state.schema.json').read_bytes()
    (directory / 'schemas/state.schema.json').write_bytes(schema)
    path = directory / 'state.json'
    path.write_text(json.dumps(state), encoding='utf-8')
    monkeypatch.setattr(release, 'ROOT', root)
    return path, state


@pytest.fixture
def ready(tmp_path):
    store, item = sg_item(tmp_path)
    store.initialize_sg_brand_acceptance()
    client, _ = client_for([payload([raw_brand()])])
    workflow = SGBrandWorkflow(store=store, client=client)
    catalog = workflow.fetch(item).catalog
    item = confirm_sg_brand(item, store=store, session=workflow.session, catalog=catalog,
        brand_id=7, expected_brand_name='Maker', human_product_verified=True, human_option_selected=True)
    text, images = evidence(item)
    workflow.product_review.supply(item, text=text, images={**images, 'root_category_id':999999, 'image_urls':[]})
    return workflow, item


def test_inactive_state_blocks_before_workflow_access(activation):
    path, state = activation
    state['markets']['SG']['operation'] = 'INACTIVE'
    path.write_text(json.dumps(state), encoding='utf-8')
    with pytest.raises(release.SGBetaNotAdopted):
        build_sg_beta_preparation_files((), workflow=None)


@pytest.mark.parametrize('change', ['inactive', 'paused', 'capability', 'blocking', 'corrupt', 'missing'])
def test_unaccepted_or_broken_state_closes_beta(activation, change):
    path, state = activation
    if change == 'inactive': state['markets']['SG']['operation'] = 'INACTIVE'
    if change == 'paused': state['markets']['SG']['development_policy'] = 'PAUSED'
    if change == 'capability': state['capabilities']['sg.safety.baseline']['lifecycle'] = 'REGISTERED'
    if change == 'blocking': state['open_items'] = [dict(id='stop', blocking=True, reason='x', impact='x', revisit_when='x')]
    path.write_text('broken' if change == 'corrupt' else json.dumps(state), encoding='utf-8')
    if change == 'missing': path.unlink()
    with pytest.raises(release.SGBetaNotAdopted): release.require_sg_beta_operation()


def test_beta_and_preview_outputs_have_separate_meanings(activation, ready):
    workflow, item = ready
    data, text, count = build_sg_beta_preparation_files((item,), workflow=workflow)
    row = next(csv.DictReader(StringIO(data.decode('utf-8-sig'))))
    assert count == 1 and row['listing_ready'] == 'TRUE'
    assert row['output_scope'] == 'SG_BETA_MANUAL_PREPARATION'
    assert row['attribute_check_state'] == 'NOT_FETCHED'
    assert 'Brand ID: 7' in text and item.candidate_asin in text
    assert workflow.product_review.decision(item) is None
    preview, _, count = build_sg_preparation_candidate_files((item,), workflow=workflow)
    row = next(csv.DictReader(StringIO(preview.decode('utf-8-sig'))))
    assert count == 1 and row['listing_ready'] == 'FALSE'
    assert row['output_scope'] == 'DEVELOPMENT_PREPARATION_PREVIEW'
    assert not item.listing_ready  # Category confirmation alone stays closed.


@pytest.mark.parametrize('stop', ['brand', 'battery', 'weapon', 'catalog', 'sls'])
def test_beta_does_not_release_existing_stops(activation, ready, stop):
    workflow, item = ready
    if stop == 'brand': workflow.session.invalidate(item.recommended_category_id)
    if stop == 'battery': supply(workflow.product_review, item, 'Rechargeable battery included')
    if stop == 'weapon':
        supply(workflow.product_review, item)
        inspect(workflow.product_review, item, 'REVIEW')
    if stop == 'sls':
        with workflow.store._connect() as connection:
            connection.execute("UPDATE catalog_categories SET category_path='Changed' WHERE marketplace='SG'")
    if stop == 'catalog':
        workflow._client.catalog_refresh_failed = True
        with pytest.raises(ValueError): build_sg_beta_preparation_files((item,), workflow=workflow)
    else:
        assert build_sg_beta_preparation_files((item,), workflow=workflow)[2] == 0


@pytest.mark.parametrize('term', ['充電ケース', 'charging case', '完全ワイヤレス', 'ワイヤレスイヤホン', 'ワイヤレスヘッドホン'])
def test_beta_rechecks_new_battery_signals_despite_old_gate_and_category_allow(activation, ready, term):
    from modules.category_mapper_sg_preparation import assess_sg_preparation
    workflow, item = ready
    assert item.input_safety_state == 'GATE_ELIGIBLE'
    assert item.sls_result.action == 'CATEGORY_ALLOW'
    supply(workflow.product_review, item, f'Includes {term}')
    assessment = assess_sg_preparation((item,), workflow=workflow)[0]
    assert workflow.product_review.current(item).guardrail_status == 'REVIEW'
    assert '商品Safetyの未解決事項' in assessment['missing_steps']
    assert not assessment['preparation_complete']
    data, text, count = build_sg_beta_preparation_files((item,), workflow=workflow)
    assert count == 0
    assert not list(csv.DictReader(StringIO(data.decode('utf-8-sig'))))
    assert item.candidate_asin not in text


def test_activation_change_during_build_closes_output(activation, ready, monkeypatch):
    workflow, item = ready
    path, state = activation
    from modules import category_mapper_sg_preparation as output
    original = output.format_preparation_groups
    def revoked(*args, **kwargs):
        state['markets']['SG']['operation'] = 'INACTIVE'
        path.write_text(json.dumps(state), encoding='utf-8')
        return original(*args, **kwargs)
    monkeypatch.setattr(output, 'format_preparation_groups', revoked)
    with pytest.raises(release.SGBetaNotAdopted): build_sg_beta_preparation_files((item,), workflow=workflow)


def test_beta_entry_before_adoption_never_opens_a_runtime(activation, preview, monkeypatch):
    path, state = activation
    state['markets']['SG']['operation'] = 'INACTIVE'
    path.write_text(json.dumps(state), encoding='utf-8')
    monkeypatch.setattr('modules.sg_live_runtime.SGLiveRuntime',
                        lambda **kwargs: pytest.fail('Runtime must not open before adoption'))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app_sg_beta.py')).run()
    assert not app.exception
    assert any('正式採用' in text.value for text in app.info)
    assert not app.button and not app.file_uploader and not app.get('download_button')


def test_beta_ui_outputs_and_revocation(activation, ready, preview):
    workflow, item = ready
    app = AppTest.from_string('''
import streamlit as st
from modules.category_mapper_sg_ui import _render_products
_render_products(tuple(st.session_state.sg_category_mapper_recommendations),
                 st.session_state.workflow.store, brand_workflow=st.session_state.workflow, beta_output=True)
''')
    app.session_state['sg_category_mapper_recommendations'] = (item,)
    app.session_state['workflow'] = workflow
    app.run()
    assert not app.exception
    assert [button.label for button in app.get('download_button')] == ['出品準備CSV', '出品準備TXT']
    assert not any('商品確認結果を保存' == button.label for button in app.button)
    path, state = activation
    state['markets']['SG']['operation'] = 'INACTIVE'
    path.write_text(json.dumps(state), encoding='utf-8')
    app.run()
    assert not app.exception and not app.get('download_button')
