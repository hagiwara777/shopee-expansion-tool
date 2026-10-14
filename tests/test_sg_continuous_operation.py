"""Synthetic batches and fake transports only; production/API access forbidden."""
from dataclasses import replace
import hashlib
import json
import logging
import gc
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from modules.sg_continuous_runtime import (SGContinuousPolicy, SGContinuousRuntime,
    initialize_continuous_operation, ContinuousOpenAIBudget)
from modules.category_mapper_sg import (parse_sg_category_mapper_input, build_sg_recommendations,
    confirm_sg_category, confirm_sg_brand, review_sg_brand, build_sg_category_catalog_csv)
from modules.category_mapper_sg_preparation import build_sg_beta_preparation_files
from modules.product_review_transport import SGProductEvidenceLoader
from modules.product_text_safety import rows_to_product_text_safety_sidecar, parse_product_text_safety_sidecar
from modules.ph_image_safety import create_image_sidecar
from modules.prelisting_candidate_csv import rows_to_prelisting_candidate_csv, parse_prelisting_candidate_csv
from modules.prelisting_gate import evaluate_prelisting_gate
from modules.prelisting_gate_csv import build_prelisting_gate_exports
from modules.listing_inventory_parser import ListingInventoryFileResult
from modules.shopee_catalog_client import ShopeeCatalogClient, ShopeeCatalogCredentials
from modules.sls_category_assets import load_sg_context
from test_product_text_safety import candidate, fact
from test_ph_image_safety import fact as image_fact
from test_category_mapper_sg_brand import raw_brand, payload
from test_sg_live_validation import payload as paid_payload
from test_ingredient_safety import fact as ingredient_fact
from modules.ingredient_safety import rows_to_ingredient_safety_sidecar


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail('Business network is forbidden')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('modules.shopee_catalog_client.urlopen', forbidden)
    monkeypatch.setattr('modules.shopee_access_token_source.GoogleSheetAccessTokenSource.get_access_token', forbidden)
    def warning(self, message, *a, **kw):
        if self.isEnabledFor(logging.WARNING): self._log(logging.WARNING, message, a, **kw)
    monkeypatch.setattr(logging.Logger, 'warning', warning)


@pytest.fixture
def policy():
    return SGContinuousPolicy('synthetic-operation', 22, 'synthetic-bridge', 3, 0, 50, 5, 3, '0',
                              'Synthetic offline authorization only')


def fake_factory(calls, *, fail=False, pages=None):
    names = load_sg_context().names[100869]
    categories = [dict(category_id=100869 if i == len(names)-1 else 9000000+i,
                       parent_category_id=0 if i == 0 else 9000000+i-1,
                       display_category_name=name, has_children=i != len(names)-1)
                  for i, name in enumerate(names)]
    def fresh():
        client = ShopeeCatalogClient(ShopeeCatalogCredentials(1, 'synthetic', 22, 'synthetic'), marketplace='SG')
        def get(path, params):
            calls.append(path)
            if fail: raise RuntimeError('synthetic transport failure')
            if path.endswith('get_category'): return {'response': {'category_list': categories}}
            return pages.pop(0) if pages else payload([raw_brand()])
        client._get = get
        return client
    return fresh


def open_runtime(tmp_path, policy, calls=None, **kwargs):
    run, claims = tmp_path/'continuous', tmp_path/'claims'
    if not run.exists(): initialize_continuous_operation(policy, run, claim_dir=claims)
    return SGContinuousRuntime(policy=policy, run_path=run, claim_dir=claims,
        fresh_client_factory=fake_factory(calls if calls is not None else [], **kwargs))


def bundle(count=4, start=1, title='Synthetic storage box', *, root=999999):
    rows = tuple(replace(candidate(f'B{i:09d}'), source_asin='B999999999', product_title=title,
                         brand='Maker', category='Synthetic category') for i in range(start, start+count))
    raw = rows_to_prelisting_candidate_csv(rows)
    parsed = parse_prelisting_candidate_csv(raw, filename='candidate.csv')
    text = rows_to_product_text_safety_sidecar(raw, rows, tuple(fact(r.candidate_asin) for r in rows))
    facts = parse_product_text_safety_sidecar(text, filename='text.csv', candidate_content=raw, candidates=parsed)
    inventory = ListingInventoryFileResult('SG', 'synthetic', 'inventory.csv', 5, 0, 0, ())
    gate = evaluate_prelisting_gate(parsed, [inventory], marketplace='SG', expected_shop_count=1,
                                   product_text_safety=facts)
    output = build_prelisting_gate_exports(gate)
    assert output.eligible_count == count
    return dict(candidate_content=raw, text_content=text,
                ingredient_content=rows_to_ingredient_safety_sidecar(raw, rows,
                    tuple(ingredient_fact(r.candidate_asin, ingredients=()) for r in rows)),
                image_content=create_image_sidecar(raw, rows, [{'candidate_asin': r.candidate_asin,
                   'ph_image_safety_fact': image_fact(r.candidate_asin, root=root)} for r in rows]),
                gate_content=output.eligible_csv, gate_filename='prelisting_gate_eligible_sg_expansion.csv')


def admit(runtime, files):
    w = runtime.workflow
    runtime._p1_test_files = files
    fingerprint = hashlib.sha256(b''.join(v for v in files.values() if isinstance(v, bytes))).hexdigest()
    w.bind_input(fingerprint)
    w.bind_product_evidence_files(fingerprint)
    w.install_product_evidence_loader(SGProductEvidenceLoader(**files))
    source = parse_sg_category_mapper_input(files['gate_content'], filename=files['gate_filename'])
    return build_sg_recommendations(source, resolver_titles={}, store=runtime.store, reuse_confirmations=False)


def complete(runtime, item):
    category = runtime.store.get_category('SG', 100869)
    item = confirm_sg_category(item, store=runtime.store, category_id=100869,
                               expected_category_path=category['category_path'])
    catalog = runtime.workflow.fetch(item).catalog
    item = confirm_sg_brand(item, store=runtime.store, session=runtime.workflow.session, catalog=catalog,
                            brand_id=7, expected_brand_name='Maker', human_product_verified=True,
                            human_option_selected=True)
    runtime.workflow.load_product_evidence(item)
    from preparation_validity_support import bound_preparation
    runtime.workflow.preparation_session, runtime.workflow.preparation_records = bound_preparation(
        (item,), product_review=runtime.workflow.product_review, source_bundle=runtime._p1_test_files)
    return item


@pytest.mark.parametrize('count', [4, 150])
def test_two_batches_all_rows_partial_output_and_fresh_confirmation(tmp_path, policy, count):
    r = open_runtime(tmp_path, policy)
    try:
        r.refresh_catalog()
        a = admit(r, bundle(count))
        assert len(a) == count and all(not item.category_is_confirmed for item in a)
        first = complete(r, a[0])
        csv, text, ready = build_sg_beta_preparation_files((first, *a[1:]), workflow=r.workflow)
        assert ready == 1 and first.candidate_asin in text and a[1].candidate_asin not in text
        assert b'TRUE' in csv
        old_p1, old_record = r.workflow.preparation_session, r.workflow.preparation_records[first.candidate_asin]
        b = admit(r, bundle(count, start=count+1))
        assert not old_p1.assess(old_record)['valid']
        assert r.workflow.preparation_session is None and not r.workflow.preparation_records
        assert len(b) == count and not r.workflow.session._current and not r.workflow.session._product_confirmations
        assert r.workflow.product_review.current(first) is None
        assert build_sg_beta_preparation_files(b, workflow=r.workflow)[2] == 0
        with pytest.raises(ValueError): r.scope.require_product(first)
        second = complete(r, b[0])
        assert build_sg_beta_preparation_files((second, *b[1:]), workflow=r.workflow)[2] == 1
        # Same ASIN, changed product: saved Category/Brand are not adopted.
        changed = admit(r, bundle(1, title='Changed synthetic storage box'))[0]
        assert not changed.category_is_confirmed and changed.confirmed_brand_id is None
        changed = confirm_sg_category(changed, store=r.store, category_id=100869,
                                      expected_category_path=first.recommended_category_path)
        r.workflow.fetch(changed)
        assert review_sg_brand(changed, store=r.store, session=r.workflow.session).confirmed_brand_id is None
    finally: r.close()


def test_no_automatic_setup_and_operation_cannot_move_or_change(tmp_path, policy):
    with pytest.raises((ValueError, OSError)):
        SGContinuousRuntime(policy=policy, run_path=tmp_path/'absent', claim_dir=tmp_path/'claims')
    assert not (tmp_path/'absent').exists()
    r = open_runtime(tmp_path, policy); r.close()
    with pytest.raises((ValueError, OSError)):
        initialize_continuous_operation(policy, tmp_path/'other', claim_dir=tmp_path/'claims')
    with pytest.raises(ValueError): open_runtime(tmp_path, replace(policy, catalog_request_limit=4))


@pytest.mark.parametrize('damage', ['missing', 'corrupt', 'changed-counter', 'db', 'binding', 'claim'])
def test_restart_refuses_damaged_persistence(tmp_path, policy, damage):
    r = open_runtime(tmp_path, policy); r.refresh_catalog(); r.close()
    path = tmp_path/'continuous/request-ledger.json'
    if damage == 'missing': path.unlink()
    elif damage == 'corrupt': path.write_text('broken')
    elif damage == 'changed-counter':
        data = json.loads(path.read_text()); data['catalog_requests'] = 0; path.write_text(json.dumps(data))
    else:
        target = {'db': tmp_path/'continuous/validation.sqlite3',
                  'binding': tmp_path/'continuous/run-binding.json',
                  'claim': next((tmp_path/'claims').glob('*.json'))}[damage]
        gc.collect()
        target.unlink()
    with pytest.raises((ValueError, OSError)): open_runtime(tmp_path, policy)


def test_failure_and_limit_survive_restart_and_batch_change(tmp_path, policy):
    p = replace(policy, catalog_request_limit=1)
    calls = []
    r = open_runtime(tmp_path, p, calls, fail=True)
    with pytest.raises(RuntimeError): r.refresh_catalog()
    assert r.ledger.data['catalog_requests'] == 1 and r.client.catalog_refresh_failed
    r.close()
    r = open_runtime(tmp_path, p, calls)
    try:
        with pytest.raises(ValueError): r.refresh_catalog()
        assert len(calls) == 1
        with pytest.raises(ValueError): r.workflow.require_catalog_current()
    finally: r.close()


def test_parallel_runtime_and_damaged_open_record_stop_before_send(tmp_path, policy):
    calls = []; r = open_runtime(tmp_path, policy, calls)
    try:
        with pytest.raises((ValueError, OSError)): open_runtime(tmp_path, policy)
        (tmp_path/'continuous/request-ledger.json').write_text('broken')
        with pytest.raises(ValueError): r.refresh_catalog()
        assert not calls
    finally: r.close()


def test_zero_limits_send_nothing(tmp_path, policy):
    calls = []; p = replace(policy, catalog_request_limit=0, brand_total_page_limit=0, keepa_request_limit=0)
    r = open_runtime(tmp_path, p, calls)
    try:
        with pytest.raises(ValueError): r.refresh_catalog()
        with pytest.raises(ValueError): r.ledger.reserve_keepa_request()
        assert not calls and r.category_engine is None and not r.workflow.can_inspect_images
    finally: r.close()


def test_brand_total_limit_and_partial_failure_do_not_commit(tmp_path, policy):
    pages = [payload([raw_brand()], next_offset=100, has_next_page=True)]
    r = open_runtime(tmp_path, replace(policy, brand_total_page_limit=1), pages=pages)
    try:
        r.refresh_catalog(); item = admit(r, bundle(1))[0]
        cat = r.store.get_category('SG', 100869)
        item = confirm_sg_category(item, store=r.store, category_id=100869, expected_category_path=cat['category_path'])
        with pytest.raises(RuntimeError): r.workflow.fetch(item)
        assert r.ledger.data['brand_page_counts'] == {'100869': 1}
        assert not r.workflow.session._current and not r.store.list_brands('SG', 100869)
    finally: r.close()


def test_paid_consumption_survives_restart(tmp_path, policy):
    p = replace(policy, openai_limit_usd='1')
    run = tmp_path/'continuous'; claims = tmp_path/'claims'
    initialize_continuous_operation(p, run, claim_dir=claims)
    def runtime(): return SGContinuousRuntime(policy=p, run_path=run, claim_dir=claims,
                                               fresh_client_factory=fake_factory([]), api_key='synthetic')
    r = runtime(); budget = ContinuousOpenAIBudget(r.ledger); budget.reserve(paid_payload()); saved = budget.summary(); r.close()
    r = runtime()
    try: assert ContinuousOpenAIBudget(r.ledger).summary() == saved
    finally: r.close()


def test_receipt_save_failure_sends_nothing(tmp_path, policy, monkeypatch):
    calls=[]; r=open_runtime(tmp_path, policy, calls)
    original=Path.replace
    def fail(self, target):
        if self.name == 'request-ledger.pending': raise OSError('synthetic write failure')
        return original(self, target)
    monkeypatch.setattr(Path, 'replace', fail)
    try:
        with pytest.raises(ValueError): r.refresh_catalog()
        assert not calls
        with pytest.raises(ValueError): r.ledger.reserve_keepa_request()
    finally: r.close()


def test_keepa_real_sdk_transport_counts_each_send_without_retry(tmp_path, policy):
    import keepa
    from modules.keepa_bounded_transport import install_bounded_keepa_transport
    r=open_runtime(tmp_path, replace(policy, keepa_request_limit=1)); calls=[]
    def send(*a, **kw):
        calls.append(kw); return SimpleNamespace(status_code=429)
    api=install_bounded_keepa_transport(keepa.Keepa('synthetic', check_key=False), r.ledger, transport=send)
    try:
        with pytest.raises(RuntimeError): api._request('product', {}, wait=True)
        with pytest.raises(RuntimeError): api._request('product', {}, wait=True)
        assert len(calls)==1 and calls[0]['allow_redirects'] is False
        assert r.ledger.data['keepa_requests']==1
    finally: r.close()


def test_same_screen_processes_next_batch_without_settings_or_stale_controls(tmp_path, policy):
    r = open_runtime(tmp_path, policy)
    r.refresh_catalog()
    app = AppTest.from_string("""
import streamlit as st
from modules.category_mapper_sg_ui import render_sg_category_mapper
render_sg_category_mapper(brand_workflow=st.session_state['test_runtime'].workflow, beta_output=True)
""", default_timeout=30)
    app.session_state['test_runtime'] = r

    def upload(files):
        r._p1_test_files = files
        for key, name, content, mime in (
            ('sg_category_mapper_source_csv', files['gate_filename'], files['gate_content'], 'text/csv'),
            ('sg_review_candidate_csv', 'candidate.csv', files['candidate_content'], 'text/csv'),
            ('sg_review_text_csv', 'text.csv', files['text_content'], 'text/csv'),
            ('sg_review_image_json', 'raw.json', files['image_content'], 'application/json')):
            app.file_uploader(key=key).set_value((name, content, mime)).run()
            assert not app.exception
        app.file_uploader(key='sg_review_ingredient_csv').set_value(('ingredient.csv', files['ingredient_content'], 'text/csv')).run()
        app.button(key='sg_review_load_files').click().run()
        app.button(key='sg_category_mapper_build').click().run()
        assert not app.exception

    def finish_first():
        app.number_input(key='sg_category_mapper_manual_category_0').set_value(100869).run()
        app.button(key='sg_category_mapper_confirm_manual_0').click().run()
        app.button(key='sg_category_mapper_fetch_brands_0').click().run()
        brand = next(box for box in app.selectbox if box.label == '確認するShopee Brand')
        brand.select('7 | Maker').run()
        verified = next(box for box in app.checkbox if box.label == '商品情報とBrand / No Brandの選択が一致することを確認しました')
        assert not verified.value
        verified.check().run()
        app.button(key='sg_category_mapper_apply_brand_0').click().run()
        app.button(key='sg_category_mapper_fetch_product_evidence_0').click().run()
        assert not app.exception
        from preparation_validity_support import bound_preparation
        current_items = tuple(app.session_state['sg_category_mapper_recommendations'])
        r.workflow.preparation_session, r.workflow.preparation_records = bound_preparation(
            (current_items[0],), product_review=r.workflow.product_review, source_bundle=r._p1_test_files)
        app.run()
        assert any(c.value == '出品準備対象: 1件' for c in app.caption)

    try:
        app.run(); upload(bundle(4)); finish_first()
        old = app.session_state['sg_category_mapper_recommendations'][0]
        app.number_input(key='sg_category_mapper_group_category_0').set_value(100869).run()
        group_check = next(box for box in app.checkbox if box.label == 'このグループの全商品のCategoryを確認しました')
        group_check.check().run()
        upload(bundle(4, start=5))
        assert len(app.session_state['sg_category_mapper_recommendations']) == 4
        assert all(not i.category_is_confirmed and i.confirmed_brand_id is None
                   for i in app.session_state['sg_category_mapper_recommendations'])
        assert app.number_input(key='sg_category_mapper_manual_category_0').value == 0
        assert not any(box.value for box in app.checkbox)
        assert r.workflow.product_review.current(old) is None
        assert not any(c.value == '出品準備対象: 1件' for c in app.caption)
        finish_first()
    finally: r.close()


@pytest.mark.parametrize('change', ['gate-market', 'gate-review', 'text-sha', 'image-sha',
                                   'missing-ingredients', 'changed-safety'])
def test_invalid_batch_replaces_no_confirmations_and_does_not_send(tmp_path, policy, change):
    calls=[]; r=open_runtime(tmp_path, policy, calls)
    try:
        r.refresh_catalog(); a=admit(r, bundle(1)); first=complete(r, a[0]); before=len(calls)
        files=bundle(1, start=2)
        if change=='gate-market': files['gate_content']=files['gate_content'].replace(b',SG,', b',PH,')
        elif change=='gate-review': files['gate_content']=files['gate_content'].replace(b',ELIGIBLE,', b',REVIEW,')
        elif change=='text-sha': files['text_content']=files['text_content'].replace(hashlib.sha256(files['candidate_content']).hexdigest().encode(), b'0'*64)
        elif change=='image-sha':
            data=json.loads(files['image_content']); data['candidate_sha256']='0'*64
            files['image_content']=json.dumps(data).encode()
        elif change=='missing-ingredients': files.pop('ingredient_content')
        else: files['text_content']=files['text_content'].replace(b'ordinary description', b'rechargeable battery')
        with pytest.raises((ValueError, RuntimeError)): admit(r, files)
        assert not r.scope.allowed_asins and not r.workflow.can_load_product_evidence
        assert r.workflow.product_review.current(first) is None and len(calls)==before
        with pytest.raises(ValueError): build_sg_beta_preparation_files((first,), workflow=r.workflow)
    finally: r.close()


def test_zero_paid_budget_keeps_weapon_target_stopped(tmp_path, policy):
    r=open_runtime(tmp_path, policy)
    try:
        r.refresh_catalog(); item=complete(r, admit(r, bundle(1, root=13299531))[0])
        assert not r.workflow.can_inspect_images
        assert build_sg_beta_preparation_files((item,), workflow=r.workflow)[2]==0
    finally: r.close()


def test_process_lease_blocks_a_second_process(tmp_path, policy):
    import subprocess, sys
    r=open_runtime(tmp_path, policy)
    source="""
import sys
from modules.sg_continuous_runtime import SGContinuousPolicy, SGContinuousLedger
p=SGContinuousPolicy(**__import__('json').loads(sys.argv[1]))
try:
    SGContinuousLedger(sys.argv[2],p)
except (OSError, ValueError):
    print('SAFE_STOP'); sys.exit(0)
sys.exit(1)
"""
    try:
        result=subprocess.run([sys.executable, '-c', source, json.dumps(policy.__dict__),
                              str(r.ledger.path)], capture_output=True, text=True, timeout=30)
        assert result.returncode==0 and 'SAFE_STOP' in result.stdout
    finally: r.close()


def test_closed_runtime_budget_cannot_spend_after_reopening(tmp_path, policy):
    old = open_runtime(tmp_path, policy)
    old.ledger.reserve_keepa_request()
    old.close()
    current = open_runtime(tmp_path, policy)
    try:
        with pytest.raises((ValueError, RuntimeError)):
            old.ledger.reserve_keepa_request()
        assert current.ledger.data['keepa_requests'] == 1
        current.ledger.reserve_keepa_request()
        assert current.ledger.data['keepa_requests'] == 2
    finally: current.close()


@pytest.mark.parametrize('amount', ['1.05', '01.050'])
def test_continuous_paid_ceiling_is_finite_owner_policy_not_legacy_one_dollar(tmp_path, policy, amount):
    from modules.sg_live_validation import OpenAIValidationBudget
    policy = replace(policy, openai_limit_usd=amount)
    run, claims = tmp_path/'continuous', tmp_path/'claims'
    initialize_continuous_operation(policy, run, claim_dir=claims)
    def reopen():
        return SGContinuousRuntime(policy=policy, run_path=run, claim_dir=claims,
            api_key='synthetic-not-a-key', fresh_client_factory=fake_factory([]))
    r = reopen()
    try:
        budget = ContinuousOpenAIBudget(r.ledger)
        while budget.reserved_usd + budget.ceiling(paid_payload()) <= budget.limit_usd:
            budget.reserve(paid_payload())
        assert budget.reserved_usd > 1
        saved = budget.reserved_usd
        with pytest.raises(ValueError): budget.reserve(paid_payload())
    finally: r.close()
    r = reopen()
    try:
        budget = ContinuousOpenAIBudget(r.ledger)
        assert budget.reserved_usd == saved and budget.stopped
        with pytest.raises(ValueError): budget.reserve(paid_payload())
    finally: r.close()
    with pytest.raises(ValueError): OpenAIValidationBudget(limit_usd='1.05')


@pytest.mark.parametrize('amount', ['Infinity', 'NaN', '-1'])
def test_continuous_policy_rejects_nonfinite_or_negative_paid_budget(tmp_path, policy, amount):
    with pytest.raises(ValueError):
        replace(policy, openai_limit_usd=amount).validate(tmp_path/'sg.sqlite3')
