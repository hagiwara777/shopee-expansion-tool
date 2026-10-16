"""Synthetic P5 connections only. No credential lookup or external transport."""
from dataclasses import replace
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

from modules.beta_work_store import BetaWorkStore
from modules.cache import KeepaCache
from modules.p5_runtime import P5Scope, P5Runtime, P5ExecutionPermit, P5Stopped, initialize_p5_ledger
from modules.p5_transport import (P5KeepaBudget, P5HTTP, P5OpenAIBudget, P5Secrets,
    make_catalog_client, make_keepa_client)
from modules.shopee_catalog_client import ShopeeCatalogCredentials
from modules.preparation_validity import InventoryEvidence
from test_sg_initial_beta import inventory, catalog
from test_beta_workbench_p2 import product, intake, selected
from test_keepa_candidate_filters import keepa_raw_product


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def refuse(*a, **k):
        pytest.fail('Unexpected external transport in P5 offline tests')
    monkeypatch.setattr('requests.sessions.Session.request', refuse)
    monkeypatch.setattr('urllib.request.OpenerDirector.open', refuse)
    monkeypatch.setattr('modules.shopee_catalog_client.urlopen', refuse)


def scope_for(tmp_path, market='PH', **limits):
    directory = tmp_path / 'synthetic-run' / market / '22'
    store = BetaWorkStore.create(directory / 'work.sqlite3', marketplace=market, shop_id='22')
    KeepaCache(directory / 'keepa.sqlite3')
    values = dict(run_id='synthetic-run', marketplace=market, shop_id='22', credential_ref='synthetic-ref',
        release='0'*40, execution_target='synthetic-process', root=str(tmp_path), store_id=store.store_id,
        asins=('B000000000', 'B000000001', 'B000000002'), category_ids=(100578,),
        finder_queries=(json.dumps({'brand': ['Fixture'], 'categories_include': [100], 'page': 0,
                                    'perPage': 50, 'sort': [['current_SALES', 'asc']]}),),
        keepa_requests=20, keepa_products=70, keepa_tokens=175, shopee_requests=69,
        bridge_requests=5, auth_requests=5, image_requests=6, openai_requests=26, openai_usd='0.50',
        openai_models=('gpt-5.6-luna', 'gpt-5.6-terra'), openai_input_bound=124384,
        openai_output_tokens=1200, openai_images=3)
    values.update(limits)
    return P5Scope(**values)


def runtime_for(tmp_path, market='PH', **limits):
    scope = scope_for(tmp_path, market, **limits)
    initialize_p5_ledger(scope)
    runtime = P5Runtime(scope, permit=P5ExecutionPermit(scope.digest, 'SYNTHETIC_ONLY', offline_test=True))
    runtime.start()
    return runtime


@pytest.fixture(params=['PH', 'SG'])
def runtime(request, tmp_path):
    runtime = runtime_for(tmp_path, request.param)
    yield runtime
    runtime.close()


def secrets(runtime):
    return P5Secrets('synthetic-ref', runtime.scope.marketplace, '22',
        ShopeeCatalogCredentials(1, 'SYNTHETIC_KEY', 22, 'SYNTHETIC_TOKEN'), keepa_key='SYNTHETIC_ONLY')


def catalog_response(*args):
    url = args[0]
    if url.endswith('get_category'):
        return {'response': {'category_list': [dict(category_id=n.category_id,
            parent_category_id=n.parent_category_id or 0, category_name=n.category_name, is_leaf=n.is_leaf)
            for n in catalog().nodes]}}
    if url.endswith('get_attribute_tree'):
        return {'response': {'list': [{'category_id': 100578, 'attribute_tree': []}]}}
    return {'response': {'brand_list': [{'brand_id': 7, 'display_brand_name': 'Synthetic Maker',
        'original_brand_name': 'Synthetic Maker'}], 'has_next_page': False, 'next_offset': 1}}


def prepare(runtime):
    client = make_catalog_client(runtime, secrets(runtime), request_json=catalog_response)
    runtime.acquire_catalog(client)
    runtime.acquire_brand(client, 100578)
    s = runtime.workflow.session
    inv = inventory(shop='22', marketplace=runtime.scope.marketplace, name=runtime.scope.marketplace+'_shop.csv')
    s.accept_inventory(InventoryEvidence(s.scope, (inv,), ('22',), 'SYNTHETIC_INVENTORY', True))
    intake(runtime.workflow.bench)
    return client


def test_configuration_is_not_execution_or_installation(tmp_path):
    scope = scope_for(tmp_path)
    before = set(tmp_path.rglob('*'))
    runtime = P5Runtime(scope)
    for action in (runtime.start, runtime.amazon_client, runtime.catalog_client, runtime.require_current):
        with pytest.raises(P5Stopped, match='NOT_APPROVED'):
            action()
    assert set(tmp_path.rglob('*')) == before


def test_live_permit_without_verified_primary_sources_stops_before_io(tmp_path):
    scope = scope_for(tmp_path)
    runtime = P5Runtime(scope, permit=P5ExecutionPermit(scope.digest, 'NOT_A_LIVE_APPROVAL'))
    with pytest.raises(P5Stopped, match='PRIMARY_SOURCE_UNVERIFIED'):
        runtime.start()
    assert not (scope.directory / 'runtime.lock').exists()


def test_scope_and_credential_market_shop_are_exact(runtime):
    with pytest.raises(P5Stopped):
        make_catalog_client(runtime, replace(secrets(runtime), marketplace='SG' if runtime.scope.marketplace == 'PH' else 'PH'))
    with pytest.raises(P5Stopped):
        make_catalog_client(runtime, replace(secrets(runtime), shop_id='99'))
    assert not runtime.ledger.data['reservations']


def test_category_brand_attribute_currentness_and_mock_never_operational(runtime):
    assert runtime.attribute_status(100578)['state'] == 'NOT_FETCHED'
    client = prepare(runtime)
    result = runtime.acquire_attributes(client, 100578)
    assert result['state'] == 'FETCHED' and result['tree_count'] == 0
    assert 'mandatory_attribute_count' not in result
    assert not runtime.category_receipt['official']
    assert runtime.workflow.session._brands[100578].source == 'OFFLINE_MOCK'
    bench = runtime.workflow.bench
    csv_bytes, _, _ = bench.output(selected(bench))
    assert b'FALSE' in csv_bytes and b'PH_SG_P1_OFFLINE' in csv_bytes
    with pytest.raises(P5Stopped, match='SYNTHETIC_IS_NOT_OFFICIAL'):
        runtime.output(selected(bench))
    runtime.invalidate_catalog()
    assert runtime.category_receipt is None and runtime.attribute_status(100578)['state'] == 'NOT_FETCHED'
    assert not bench.prepared_pool()


@pytest.mark.parametrize('bad', [None, {}, {'category_id': True},
    {'category_id': 99, 'parent_category_id': 0, 'category_name': 'Bad', 'is_leaf': 'false'},
    {'category_id': 99, 'parent_category_id': 100578, 'category_name': 'Bad', 'is_leaf': True}])
def test_invalid_category_raw_is_not_silently_discarded(runtime, bad):
    client = prepare(runtime)
    def malformed(*a):
        response = catalog_response('get_category')
        response['response']['category_list'].append(bad)
        return response
    client._request_json = malformed
    with pytest.raises((ValueError, RuntimeError)):
        runtime.acquire_catalog(client)
    assert runtime.category_receipt is None
    assert not runtime.workflow.bench.prepared_pool()


def test_catalog_scope_and_request_limit_stop_before_send(tmp_path):
    runtime = runtime_for(tmp_path, shopee_requests=1)
    calls = []
    client = make_catalog_client(runtime, secrets(runtime), request_json=lambda *a: (calls.append(a), catalog_response(*a))[1])
    runtime.acquire_catalog(client)
    with pytest.raises(P5Stopped):
        client.get_brand_list(runtime.scope.marketplace, 99, strict=True)
    with pytest.raises(P5Stopped, match='BUDGET_EXHAUSTED'):
        runtime.acquire_brand(client, 100578)
    assert len(calls) == 1
    runtime.close()


def test_maximum_keepa_tokens_reserved_and_actual_recorded(runtime):
    budget = P5KeepaBudget(runtime)
    with pytest.raises(P5Stopped, match='BALANCE'):
        budget.reserve_keepa_call('product', {'domain': 5, 'asin': 'B000000001', 'rating': 1})
    token = budget.reserve_keepa_call('token', {'key': 'SYNTHETIC'})
    budget.complete_keepa_call(token, {'tokensLeft': 100, 'tokensConsumed': 0}, 200)
    receipt = budget.reserve_keepa_call('product', {'domain': 5, 'asin': 'B000000001', 'rating': 1})
    assert runtime.ledger.data['reservations'][-1]['tokens'] == 2
    budget.complete_keepa_call(receipt, {'tokensLeft': 99, 'tokensConsumed': 1}, 200)
    row = runtime.ledger.data['reservations'][-1]
    assert row['tokens'] == 2 and row['actual_tokens'] == 1


@pytest.mark.parametrize('payload', [{}, {'tokensConsumed': True, 'tokensLeft': 100},
    {'tokensConsumed': -1, 'tokensLeft': 100}, {'tokensConsumed': 0}, {'tokensConsumed': 5, 'tokensLeft': 100}])
def test_keepa_missing_invalid_consumption_retains_reservation_across_restart(tmp_path, payload):
    runtime = runtime_for(tmp_path)
    scope, permit = runtime.scope, runtime.permit
    budget = P5KeepaBudget(runtime)
    reservation = budget.reserve_keepa_call('token', {'key': 'SYNTHETIC'})
    with pytest.raises(P5Stopped):
        budget.complete_keepa_call(reservation, payload, 200)
    budget.fail_keepa_call(reservation)
    runtime.close()
    reopened = P5Runtime(scope, permit=permit)
    with pytest.raises(P5Stopped, match='UNRESOLVED'):
        reopened.start()
    data = json.loads((scope.directory / 'ledger.json').read_text())
    assert len(data['reservations']) == 1 and data['reservations'][0]['state'] == 'UNKNOWN'


def test_parallel_open_and_budget_do_not_reset(runtime):
    other = P5Runtime(runtime.scope, permit=runtime.permit)
    with pytest.raises((OSError, RuntimeError)):
        other.start()
    row = runtime.ledger.reserve('bridge')
    runtime.ledger.finish(row, success=True)
    runtime.close()
    other.start()
    assert len(other.ledger.data['reservations']) == 1
    other.close()


def test_failed_persistence_sends_nothing(runtime, monkeypatch):
    calls = []
    session = SimpleNamespace(request=lambda *a, **k: calls.append(a))
    def fail(*a):
        raise OSError('synthetic disk failure')
    monkeypatch.setattr('modules.sg_continuous_runtime.os.fsync', fail)
    with pytest.raises(P5Stopped):
        P5HTTP(runtime, 'bridge', session=session).get('https://sheets.googleapis.com/v4/spreadsheets/synthetic/values/A:C')
    assert calls == []


@pytest.mark.parametrize('kind,url', [('bridge', 'https://sheets.googleapis.com/v4/spreadsheets/synthetic'),
    ('auth', 'https://oauth2.googleapis.com/token'), ('image', 'https://m.media-amazon.com/images/I/synthetic.jpg'),
    ('openai', 'https://api.openai.com/v1/responses')])
def test_timeout_does_not_retry_and_paid_reservation_survives(runtime, kind, url):
    calls = []
    def timeout(*a, **k):
        calls.append(k)
        raise TimeoutError('synthetic timeout')
    session = SimpleNamespace(request=timeout)
    transport = P5HTTP(runtime, kind, session=session)
    kwargs = {'json': {'model': 'gpt-5.6-luna', 'store': False, 'max_output_tokens': 100, 'input': 'synthetic'}} if kind == 'openai' else {}
    method = transport.post if kind in {'auth', 'openai'} else transport.get
    with pytest.raises(P5Stopped): method(url, **kwargs)
    with pytest.raises(P5Stopped): method(url, **kwargs)
    assert len(calls) == 1 and calls[0]['allow_redirects'] is False
    assert runtime.ledger.data['reservations'][0]['state'] == 'UNKNOWN'
    if kind == 'openai': assert Decimal(runtime.ledger.data['reservations'][0]['usd']) > 0


@pytest.mark.parametrize('payload', [{'model': 'other', 'store': False, 'max_output_tokens': 10},
    {'model': 'gpt-5.6-luna', 'store': False, 'max_output_tokens': 1201},
    {'model': 'gpt-5.6-luna', 'store': True, 'max_output_tokens': 10}])
def test_openai_invalid_profile_is_rejected_before_send(runtime, payload):
    with pytest.raises(ValueError): P5OpenAIBudget.check_payload(runtime.scope, payload)
    assert not runtime.ledger.data['reservations']


def test_claim_or_store_replacement_cannot_create_new_budget(runtime):
    before = (runtime.scope.directory / 'ledger.json').read_bytes()
    (runtime.scope.directory / 'claim.json').write_text('{}')
    with pytest.raises(P5Stopped): runtime.require_current()
    assert (runtime.scope.directory / 'ledger.json').read_bytes() == before
    with pytest.raises(FileExistsError): initialize_p5_ledger(runtime.scope)


def test_actual_sdk_transport_records_f1_f2_consumption_without_network(runtime, keepa_raw_product):
    from modules.candidate_filters import FilterCriteria
    calls = []
    def send(url, **kwargs):
        calls.append((url, kwargs))
        body = {'tokensLeft': 100, 'tokensConsumed': 0, 'refillRate': 5, 'refillIn': 60000}
        if '/product/' in url:
            assert kwargs['params']['stats'] == 1 and kwargs['params']['rating'] == 1
            assert kwargs['params']['domain'] == 5
            body.update(tokensConsumed=2, tokensLeft=98, products=[keepa_raw_product])
        return SimpleNamespace(status_code=200, json=lambda: body)
    client = make_keepa_client(runtime, secrets(runtime), transport=send)
    assert calls == []  # SDK constructor and cache open do not send.
    with pytest.raises(P5Stopped): client.find_related_products('B000000000', 3)
    assert calls == []
    result = client.verify_products_by_asin(['B000000001'], filter_criteria=FilterCriteria(price_min_jpy=100, rating_min=4.5))
    assert result['B000000001']['candidate_observation']['price_jpy'] == 1000
    assert result['B000000001']['candidate_observation']['rating'] == 4.5
    assert len(calls) == 2
    assert sum(r['tokens'] for r in runtime.ledger.data['reservations']) == 2
    assert sum(r['actual_tokens'] for r in runtime.ledger.data['reservations']) == 2


def test_primary_source_and_default_transport_contract_is_synthetic_not_live(tmp_path, monkeypatch):
    # As in P1 exit tests, patch the default HTTP function to exercise the
    # production branch. These assertions are not an official/live receipt.
    scope = scope_for(tmp_path)
    initialize_p5_ledger(scope)
    permit = P5ExecutionPermit(scope.digest, 'SYNTHETIC_CONTRACT_ONLY', ('fixture-category', 'fixture-brand', 'fixture-attribute'))
    runtime = P5Runtime(scope, permit=permit, execution_identity=lambda: (scope.release, scope.execution_target))
    runtime.start()
    monkeypatch.setattr('modules.shopee_catalog_client._urlopen_json', lambda *a, **k: catalog_response(*a))
    client = make_catalog_client(runtime, secrets(runtime))
    runtime.acquire_catalog(client)
    runtime.acquire_brand(client, 100578)
    s = runtime.workflow.session
    inv = inventory(shop='22', marketplace='PH', name='PH_shop.csv')
    s.accept_inventory(InventoryEvidence(s.scope, (inv,), ('22',), 'SYNTHETIC_ONLY', True))
    intake(runtime.workflow.bench)
    csv_bytes, _, _ = runtime.output(selected(runtime.workflow.bench))
    assert b'TRUE' in csv_bytes and b'PH_SG_MANUAL_PREPARATION' in csv_bytes
    # A fabricated reference or matching catalog cannot recreate acquisition.
    runtime.category_receipt = None
    with pytest.raises(ValueError): runtime.output(selected(runtime.workflow.bench))
    runtime.close()


def test_expansion_and_resolver_share_bounded_sdk_and_filter_observations(runtime, keepa_raw_product):
    from modules.candidate_filters import FilterCriteria
    calls = []
    def send(url, **kwargs):
        calls.append(url)
        body = {'tokensLeft': 500, 'tokensConsumed': 0, 'refillRate': 5, 'refillIn': 60000}
        if '/query/' in url:
            body.update(tokensConsumed=2, asinList=['B000000001'], totalResults=1)
        elif '/product/' in url:
            p = dict(keepa_raw_product)
            p['asin'] = kwargs['params']['asin']
            body.update(tokensConsumed=1 if p['asin'] == 'B000000000' else 2, products=[p])
        return SimpleNamespace(status_code=200, json=lambda: body)
    client = make_keepa_client(runtime, secrets(runtime), transport=send)
    criteria = FilterCriteria(price_min_jpy=100, rating_min=4.5)
    expanded = client.find_related_products('B000000000', 1, filter_criteria=criteria)
    assert expanded.rows[0]['candidate_asin'] == 'B000000001'
    assert expanded.rows[0]['candidate_observation']['rating'] == 4.5
    before = len(calls)
    resolved = client.verify_products_by_asin(['B000000001'], filter_criteria=criteria)
    assert resolved['B000000001']['candidate_observation']['price_jpy'] == 1000
    assert len(calls) == before  # Existing cache reuse is not a second API call.
    assert sum(r['tokens'] for r in runtime.ledger.data['reservations']) == 14


@pytest.mark.parametrize('kind', ['bridge', 'auth', 'image', 'openai'])
def test_each_http_counter_is_independent_and_zero_limit_sends_nothing(tmp_path, kind):
    runtime = runtime_for(tmp_path, **{kind+'_requests': 0})
    calls = []
    transport = P5HTTP(runtime, kind, session=SimpleNamespace(request=lambda *a, **k: calls.append(a)))
    urls = {'bridge': 'https://sheets.googleapis.com/v4/spreadsheets/synthetic',
        'auth': 'https://oauth2.googleapis.com/token', 'image': 'https://m.media-amazon.com/a.jpg',
        'openai': 'https://api.openai.com/v1/responses'}
    kwargs = {'json': {'model': 'gpt-5.6-luna', 'store': False, 'max_output_tokens': 100}} if kind == 'openai' else {}
    with pytest.raises(P5Stopped):
        transport.request('POST' if kind in {'auth', 'openai'} else 'GET', urls[kind], **kwargs)
    assert not calls and not runtime.ledger.data['reservations']
    runtime.close()


def test_unknown_image_stream_retains_reservation_and_prevents_second_get(runtime):
    calls = []
    def chunks(**kwargs):
        yield b'partial'
        raise TimeoutError('synthetic partial stream')
    response = SimpleNamespace(status_code=200, iter_content=chunks, close=lambda: None)
    transport = P5HTTP(runtime, 'image', session=SimpleNamespace(request=lambda *a, **k: (calls.append(a), response)[1]))
    result = transport.get('https://m.media-amazon.com/a.jpg', stream=True)
    with pytest.raises(P5Stopped): list(result.iter_content(chunk_size=64))
    result.close()
    with pytest.raises(P5Stopped): transport.get('https://m.media-amazon.com/a.jpg', stream=True)
    assert len(calls) == 1 and runtime.ledger.data['reservations'][0]['state'] == 'UNKNOWN'


def test_finite_keepa_tokens_stop_before_second_send(tmp_path):
    runtime = runtime_for(tmp_path, keepa_tokens=1)
    budget = P5KeepaBudget(runtime)
    budget.balance = 500
    reservation = budget.reserve_keepa_call('product', {'domain': 5, 'asin': 'B000000001'})
    budget.complete_keepa_call(reservation, {'tokensLeft': 499, 'tokensConsumed': 1}, 200)
    with pytest.raises(P5Stopped, match='BUDGET_EXHAUSTED'):
        budget.reserve_keepa_call('product', {'domain': 5, 'asin': 'B000000001'})
    assert len(runtime.ledger.data['reservations']) == 1
    runtime.close()


def test_bridge_and_google_auth_use_separate_finite_transports(tmp_path, monkeypatch):
    from modules.p5_transport import P5BridgeTransport
    from modules.shopee_access_token_source import GoogleSheetAccessTokenSource
    runtime = runtime_for(tmp_path, bridge_spreadsheet_id='synthetic-sheet')
    calls = []
    class Session:
        def mount(self, *a): pass
        def request(self, method, url, **kwargs):
            calls.append((method, url))
            if 'oauth2' in url:
                body = {'access_token': 'SYNTHETIC_ONLY', 'expires_in': 300}
            else:
                body = {'values': [['marketplace', 'shop_id', 'access_token'], ['PH', '22', 'SYNTHETIC_ONLY']]}
            return SimpleNamespace(status_code=200, content=json.dumps(body).encode(),
                headers={}, json=lambda: body)
    class Credentials:
        def before_request(self, request, method, url, headers):
            request('https://oauth2.googleapis.com/token', method='POST', body=b'SYNTHETIC_ONLY')
    monkeypatch.setattr('requests.Session', Session)
    monkeypatch.setattr('google.auth.load_credentials_from_file', lambda *a, **k: (Credentials(), None))
    bridge = P5BridgeTransport(runtime, credential_file='SYNTHETIC_NOT_READ', spreadsheet_id='synthetic-sheet')
    source = GoogleSheetAccessTokenSource('synthetic-sheet', transport=bridge)
    assert source.get_access_token('PH', 22).value == 'SYNTHETIC_ONLY'
    assert len(calls) == 2
    assert [r['kind'] for r in runtime.ledger.data['reservations']] == ['auth', 'bridge']
    with pytest.raises((ValueError, RuntimeError)):
        GoogleSheetAccessTokenSource('synthetic-sheet', transport=bridge).get_access_token('SG', 99)
    runtime.close()


@pytest.mark.parametrize('url', ['http://m.media-amazon.com/a.jpg', 'https://example.invalid/a.jpg',
    'https://m.media-amazon.com:444/a.jpg', 'https://other@ m.media-amazon.com/a.jpg'])
def test_image_destination_allowlist_sends_nothing(runtime, url):
    calls = []
    transport = P5HTTP(runtime, 'image', session=SimpleNamespace(request=lambda *a, **k: calls.append(a)))
    with pytest.raises((ValueError, RuntimeError)): transport.get(url, stream=True)
    assert not calls and not runtime.ledger.data['reservations']


def test_partial_http_category_response_stops_without_official_receipt(tmp_path, monkeypatch):
    from modules.shopee_catalog_client import _urlopen_json
    from contextlib import nullcontext
    calls = []
    response = SimpleNamespace(status=206, read=lambda: json.dumps(catalog_response('get_category')).encode())
    monkeypatch.setattr('urllib.request.build_opener', lambda *a: SimpleNamespace(
        open=lambda *a, **k: (calls.append(1), nullcontext(response))[1]))
    with pytest.raises(RuntimeError, match='complete response'):
        _urlopen_json('https://partner.shopeemobile.com/api/v2/product/get_category', {}, 10, allow_redirects=False)
    assert len(calls) == 1


def test_existing_weapon_inspector_uses_only_p5_image_and_paid_transports(runtime):
    from modules.image_inspection_policy import load_image_inspection_policy
    from modules.practical_weapon_ui import _session
    from modules.p5_transport import make_image_inspector
    from test_ph_image_safety_api import Response, body, URL
    record = product(runtime.scope.marketplace,
        root=min(load_image_inspection_policy(runtime.scope.marketplace).target_roots))
    record['weapon']['images']['image_urls'] = [URL]
    item, review = _session(record, runtime.scope.marketplace)
    image_calls, api_calls = [], []
    images = SimpleNamespace(request=lambda *a, **k: (image_calls.append(a), Response())[1])
    api = SimpleNamespace(request=lambda *a, **k: (api_calls.append(k), Response(data=body()))[1])
    inspector = make_image_inspector(runtime, replace(secrets(runtime), openai_key='SYNTHETIC_ONLY'),
        api_session=api, image_session=images)
    inspected = inspector.inspect(review.current(item))
    assert inspected.system_status == 'COMPLETED' and inspected.ai_status == 'NO_SIGNAL'
    assert len(image_calls) == len(api_calls) == 1
    assert [r['kind'] for r in runtime.ledger.data['reservations']] == ['image', 'openai']
    assert Decimal(runtime.ledger.data['reservations'][-1]['usd']) > 0


def test_mock_object_cannot_borrow_default_transport_provenance(runtime):
    from modules.p5_transport import P5CatalogPolicy
    calls = []
    counterfeit = SimpleNamespace(request_policy=P5CatalogPolicy(runtime), uses_default_transport=True,
        get_categories=lambda *a, **k: calls.append(1))
    with pytest.raises(P5Stopped, match='APPROVED_CATALOG_ROUTE'):
        runtime.acquire_catalog(counterfeit)
    assert not calls and runtime.category_receipt is None and not runtime.ledger.data['reservations']
