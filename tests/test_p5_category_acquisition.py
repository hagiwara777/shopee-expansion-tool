"""Leaf bootstrap through existing P5 gates; synthetic storage/HTTP only."""
from dataclasses import replace
from pathlib import Path
import json
from types import SimpleNamespace

import pytest

from modules.beta_work_store import BetaWorkStore
from modules.p5_live_adapter import BUDGETS
from modules.p5_runtime import (P5Scope, P5Runtime, P5ExecutionPermit, P5Stopped,
    P5_CATEGORY_ACQUISITION_OPERATIONS)
from modules.p5_transport import make_catalog_client
from modules.sg_continuous_runtime import _digest
from test_p5_runtime import synthetic_setup, trusted_adapter, secrets, catalog_response, forbid_network


def template_for(tmp_path, market='PH', **changes):
    values = dict(run_id='synthetic-category', marketplace=market, shop_id='22',
        credential_ref='synthetic-ref', release='0'*40, execution_target='synthetic-process',
        root=str(tmp_path), store_id=None, asins=('B000000000',), category_ids=(), finder_queries=(),
        **dict.fromkeys(BUDGETS, 0), openai_models=(), openai_input_bound=0,
        openai_output_tokens=0, openai_images=0, bridge_spreadsheet_id='synthetic-sheet')
    values.update(openai_usd='0', shopee_requests=1, bridge_requests=1, auth_requests=1)
    values.update(changes)
    return P5Scope(**values)


def installed_runtime(tmp_path, market='PH'):
    template = template_for(tmp_path, market)
    scope = synthetic_setup().install(template, required_bytes=1000)
    rt = P5Runtime(scope, permit=P5ExecutionPermit(scope.digest, 'SYNTHETIC_ONLY',
        offline_test=True, operations=P5_CATEGORY_ACQUISITION_OPERATIONS))
    rt.start()
    return template, rt


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_unbound_leaf_install_does_not_grant_execution_or_product_operations(tmp_path, market):
    template = template_for(tmp_path, market)
    template.validate_new_install()
    assert not template.directory.exists()
    scope = synthetic_setup().install(template, required_bytes=1000)
    assert scope.store_id == BetaWorkStore(scope.db_path, marketplace=market, shop_id='22').store_id
    before = {p: p.read_bytes() for p in scope.directory.iterdir() if p.is_file()}
    with pytest.raises(P5Stopped, match='EXECUTION_NOT_APPROVED'):
        P5Runtime(scope).start()
    assert all(p.read_bytes() == data for p, data in before.items())
    for operations in (None, frozenset({'shopee.category'}),
                       P5_CATEGORY_ACQUISITION_OPERATIONS | {'p2.save'}):
        with pytest.raises(P5Stopped, match='CATEGORY_ACQUISITION_ONLY'):
            P5Runtime(scope, permit=P5ExecutionPermit(scope.digest, 'SYNTHETIC_ONLY',
                offline_test=True, operations=operations)).start()
    assert all(p.read_bytes() == data for p, data in before.items())
    with pytest.raises(FileExistsError):
        synthetic_setup().install(template, required_bytes=1000)


@pytest.mark.parametrize('changes', [
    {'keepa_requests': 1}, {'keepa_products': 1}, {'keepa_tokens': 1}, {'image_requests': 1},
    {'openai_requests': 1}, {'openai_usd': '0.01'}, {'openai_models': ('gpt-5.6-luna',)},
    {'openai_input_bound': 1}, {'openai_output_tokens': 1}, {'openai_images': 1},
    {'preparation_limit': 1}, {'finder_queries': ('{"page":0,"perPage":1}',)},
    {'shopee_requests': 0}, {'shopee_requests': 2}, {'bridge_requests': 0}, {'bridge_requests': 2},
    {'auth_requests': 0}, {'auth_requests': 2},
    {'bridge_spreadsheet_id': ''},
])
def test_empty_leaf_cannot_expand_scope_or_create_storage(tmp_path, changes):
    template = template_for(tmp_path, **changes)
    with pytest.raises(P5Stopped, match='SCOPE_BINDING_INVALID'):
        synthetic_setup().install(template, required_bytes=1000)
    assert not template.directory.exists()


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_strict_catalog_acquisition_and_one_send_keep_p2_unchanged(tmp_path, market):
    _, rt = installed_runtime(tmp_path, market)
    before_db = rt.scope.db_path.read_bytes()
    calls = []
    def response(*args):
        calls.append(args[0].rsplit('/', 1)[-1])
        return catalog_response(*args)
    try:
        client = make_catalog_client(rt, secrets(rt), request_json=response)
        catalog = rt.acquire_catalog(client)
        assert catalog.marketplace == market and any(n.is_leaf for n in catalog.nodes)
        assert rt.category_receipt['catalog'] == catalog and rt.category_receipt['official'] is False
        assert rt.scope.category_ids == () and not rt.ledger.data.get('candidates')
        assert 'material_updates' not in rt.ledger.data
        assert rt.scope.db_path.read_bytes() == before_db
        assert not rt.workflow.bench.store.products() and not rt.workflow.bench.store.history()
        for operation in ('shopee.brand', 'keepa.product', 'material.update', 'p2.save', 'output'):
            with pytest.raises(P5Stopped, match='OPERATION_NOT_APPROVED'):
                rt.require_operation(operation)
        with pytest.raises(P5Stopped):
            rt.acquire_catalog(client)
        assert calls == ['get_category']
        assert len(rt.ledger.data['reservations']) == 1
    finally:
        rt.close()


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_real_google_request_adapter_trace_is_bounded_and_synthetic(tmp_path, monkeypatch, market):
    scope = synthetic_setup().install(template_for(tmp_path, market), required_bytes=1000)
    adapter, authority, observed, approval = trusted_adapter(scope)
    approval = replace(approval, operations=P5_CATEGORY_ACQUISITION_OPERATIONS)
    observed['primary_sources'].pop('brand')
    observed['primary_sources'].pop('attribute')
    observed['pricing'] = {}
    authority.verify_original = lambda ref: replace(approval, observations_digest=_digest(observed))
    rt = adapter.compose(scope, approval_reference='SYNTHETIC_ONLY')
    path = tmp_path / 'synthetic-google.json'
    path.write_text('{"type":"authorized_user"}')
    rt._credentials = replace(secrets(rt), google_credential_file=str(path))
    reads = []
    original_read = Path.read_text
    def read_text(file, *args, **kwargs):
        if file == path:
            reads.append('synthetic-google')
        return original_read(file, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read_text)
    calls = []
    class Session:
        def mount(self, *args): pass
        def request(self, method, url, **kwargs):
            assert kwargs['allow_redirects'] is False
            calls.append('auth' if url.endswith('/token') else 'bridge')
            body = {'access_token': 'SYNTHETIC_ONLY', 'expires_in': 300} if url.endswith('/token') else {
                'values': [['marketplace', 'shop_id', 'access_token'], [market, '22', 'SYNTHETIC_ONLY']]}
            return SimpleNamespace(status_code=200, content=json.dumps(body).encode(), headers={}, json=lambda: body)
    class Credentials:
        def before_request(self, request, method, url, headers):
            request('https://oauth2.googleapis.com/token', method='POST', body=b'SYNTHETIC')
    monkeypatch.setattr('requests.Session', Session)
    monkeypatch.setattr('google.auth.load_credentials_from_dict', lambda *a, **k: (Credentials(), None))
    def response(*args):
        calls.append('shopee')
        return catalog_response(*args)
    rt.start()
    try:
        client = make_catalog_client(rt, rt.secrets('shopee'), request_json=response)
        rt.acquire_catalog(client)
        assert calls == ['auth', 'bridge', 'shopee']
        assert [r['kind'] for r in rt.ledger.data['reservations']] == calls
        assert all(r['state'] == 'COMPLETE' for r in rt.ledger.data['reservations'])
        with pytest.raises(P5Stopped):
            rt.acquire_catalog(client)
        with pytest.raises(P5Stopped):
            rt.refresh_access_token()
        assert calls == ['auth', 'bridge', 'shopee']
        assert reads == ['synthetic-google']
    finally:
        rt.close()


@pytest.mark.parametrize('failure', ['timeout', 'invalid-hierarchy', 'wrong-market'])
def test_failure_never_retries_or_upgrades_partial_results(tmp_path, failure):
    _, rt = installed_runtime(tmp_path)
    calls = []
    def response(*args):
        calls.append('shopee')
        if failure == 'timeout':
            raise TimeoutError('SYNTHETIC')
        return {'response': {'category_list': [dict(category_id=2, parent_category_id=1,
            category_name='Synthetic orphan', is_leaf=True)]}}
    try:
        client = make_catalog_client(rt, secrets(rt), request_json=response)
        if failure == 'wrong-market':
            client.marketplace = 'SG'
        with pytest.raises((ValueError, RuntimeError)):
            rt.acquire_catalog(client)
        saved = json.loads(rt.ledger.path.read_text())
        assert rt.category_receipt is None
        with pytest.raises((ValueError, RuntimeError)):
            rt.acquire_catalog(client)
        assert calls == ([] if failure == 'wrong-market' else ['shopee'])
        assert json.loads(rt.ledger.path.read_text()) == saved
        if failure == 'timeout':
            assert saved['stopped'] and saved['reservations'][0]['state'] == 'UNKNOWN'
    finally:
        rt.close()


def test_category_scope_cannot_be_rebound_into_product_scope(tmp_path):
    _, rt = installed_runtime(tmp_path)
    scope = rt.scope
    before = {name: (scope.directory / name).read_bytes() for name in ('claim.json', 'ledger.json')}
    rt.close()
    product_scope = replace(scope, category_ids=(100578,))
    with pytest.raises(P5Stopped, match='INSTALLATION_REQUIRED'):
        P5Runtime(product_scope, permit=P5ExecutionPermit(product_scope.digest, 'SYNTHETIC_ONLY',
            offline_test=True, operations=P5_CATEGORY_ACQUISITION_OPERATIONS)).start()
    assert all((scope.directory / name).read_bytes() == value for name, value in before.items())


def test_missing_primary_category_spec_still_stops_before_start(tmp_path):
    scope = synthetic_setup().install(template_for(tmp_path), required_bytes=1000)
    before = {p: p.read_bytes() for p in scope.directory.iterdir() if p.is_file()}
    with pytest.raises(P5Stopped, match='PRIMARY_SOURCE_UNVERIFIED'):
        P5Runtime(scope, permit=P5ExecutionPermit(scope.digest, 'NOT_A_LIVE_APPROVAL',
            operations=P5_CATEGORY_ACQUISITION_OPERATIONS), execution_identity=lambda: None).start()
    assert all(p.read_bytes() == value for p, value in before.items())


def category_app(runtime):
    from app_beta import render_beta
    render_beta(p5_runtimes={runtime.scope.marketplace: runtime})


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_category_only_ui_replays_without_send_or_product_controls(tmp_path, monkeypatch, market):
    from streamlit.testing.v1 import AppTest
    _, rt = installed_runtime(tmp_path, market)
    calls = []
    def response(*args):
        calls.append('category')
        return catalog_response(*args)
    client = make_catalog_client(rt, secrets(rt), request_json=response)
    monkeypatch.setattr(rt, 'catalog_client', lambda: client)
    monkeypatch.setattr('app_beta.render_application', lambda *a, **k: pytest.fail('product UI reached'))
    try:
        app = AppTest.from_function(category_app, args=(rt,), default_timeout=30)
        app.session_state['beta_marketplace'] = market
        app.run()
        assert not app.exception and not calls and not app.tabs
        assert {button.key for button in app.button} == {'p5_start', 'p5_catalog'}
        app.button(key='p5_catalog').click().run()
        app.run()
        assert not app.exception and calls == ['category'] and len(app.dataframe) == 1
        assert app.button(key='p5_catalog').disabled and not app.get('download_button')
        app.run()
        assert calls == ['category'] and not rt.workflow.bench.store.products()
    finally:
        rt.close()
