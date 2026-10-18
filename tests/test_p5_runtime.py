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
    material_updates = limits.pop('material_updates', False)
    scope = scope_for(tmp_path, market, **limits)
    initialize_p5_ledger(scope, material_updates=material_updates)
    runtime = P5Runtime(scope, permit=P5ExecutionPermit(scope.digest, 'SYNTHETIC_ONLY', offline_test=True))
    runtime.start()
    return runtime


def trusted_adapter(scope):
    from dataclasses import asdict
    from datetime import datetime, timedelta, timezone
    from modules.p5_live_adapter import P5TrustedAdapter, OperatorApproval, OPERATIONS, BUDGETS
    from modules.sg_continuous_runtime import _digest
    now = datetime.now(timezone.utc)
    source = dict(verified=True, body_digest='SYNTHETIC', version='fixture',
        app_shop_permission='fixture', paging='fixture', request_response='fixture', rate_limit='fixture')
    observed = dict(repository='1296080967', release=scope.release, source_digest='fixture-tree',
        execution_target=scope.execution_target,
        entrypoint='app_beta.py', machine='fixture-host', port=8511, loopback=True,
        storage=dict(root=str(scope.directory), store_id=scope.store_id, volume='fixture-volume',
                     acl='fixture-acl', identities='fixture-identities', capacity_ok=True),
        credential=dict(reference=scope.credential_ref, marketplace=scope.marketplace, shop=scope.shop_id),
        primary_sources={k: dict(source) for k in ('category', 'brand', 'attribute')},
        pricing=dict(verified=True, reference='SYNTHETIC_PRICE', body_digest='SYNTHETIC_PRICE'), plan=asdict(scope))
    approval = OperatorApproval('SYNTHETIC_OWNER', 'SYNTHETIC_ORIGINAL', now-timedelta(minutes=1),
        now+timedelta(minutes=5), 'fixture-end', 'fixture-ticket', scope.digest, _digest(observed),
        OPERATIONS, (scope,), tuple((k, getattr(scope, k)) for k in BUDGETS))
    authority = SimpleNamespace(verify_original=lambda reference: approval)
    adapter = P5TrustedAdapter(authority=authority, observe=lambda s: observed,
        resolve_secrets=lambda s: pytest.fail('Unexpected credential resolution'), synthetic=True)
    return adapter, authority, observed, approval


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_t01_trusted_composition_rechecks_original_observations_and_operations(tmp_path, market):
    from datetime import timedelta
    scope = scope_for(tmp_path, market)
    initialize_p5_ledger(scope)
    adapter, authority, observed, approval = trusted_adapter(scope)
    rt = adapter.compose(scope, approval_reference='SYNTHETIC')
    rt.start()
    try:
        for bad in ({'APPROVED': True}, replace(approval, revoked=True),
                    replace(approval, expires_at=approval.approved_at-timedelta(seconds=1)),
                    replace(approval, scope_digest='wrong'), replace(approval, original_instruction_ref='')):
            authority.verify_original = lambda ref, bad=bad: bad
            with pytest.raises((ValueError, RuntimeError)):
                rt.require_operation('keepa.product')
        authority.verify_original = lambda ref: approval
        for key in observed:
            original = observed[key]
            observed[key] = 'CHANGED'
            with pytest.raises(ValueError):
                rt.require_current()
            observed[key] = original
        authority.verify_original = lambda ref: replace(approval, operations=frozenset({'output'}))
        with pytest.raises(ValueError, match='OPERATION'):
            rt.require_operation('keepa.product')
        assert not rt.ledger.data['reservations']
    finally:
        rt.close()


def test_t02_trusted_market_fixed_allocation_cannot_exceed_total(tmp_path):
    scope = scope_for(tmp_path)
    adapter, authority, _, approval = trusted_adapter(scope)
    authority.verify_original = lambda ref: replace(approval,
        total_limits=tuple((k, 0 if k == 'keepa_tokens' else v) for k, v in approval.total_limits))
    with pytest.raises(ValueError, match='ALLOCATION_EXCEEDED'):
        adapter.compose(scope, approval_reference='SYNTHETIC')


def synthetic_setup():
    from modules.p5_setup import P5Setup, StorageObservation, GiB
    def inspect(path):
        return StorageObservation(str(path.resolve()), 'FIXTURE_VOLUME', 'NTFS', True, True, True,
            (str(path),), frozenset({'fixture-operator', 'SYSTEM', 'Administrators'}), True,
            40*GiB, 4*GiB, 0)
    return P5Setup(inspect=inspect, set_acl=lambda p: None,
        probe=lambda p: dict.fromkeys(('create','read','fsync','rename','exclusive_lock','sqlite_transaction'), True),
        expected_volume='FIXTURE_VOLUME', operator='fixture-operator')


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_t06_new_only_setup_checkpoint_and_disconnected_recovery(tmp_path, market):
    from modules.p5_setup import checkpoint, restore_isolated
    template = replace(scope_for(tmp_path / 'template', market), root=str(tmp_path / 'new'),
        preparation_limit=2, store_id='UNOBSERVED')
    setup = synthetic_setup()
    scope = setup.install(template, required_bytes=1000)
    assert scope.store_id != 'UNOBSERVED'
    assert scope.digest != template.digest
    before = {p: p.read_bytes() for p in scope.directory.iterdir() if p.is_file()}
    with pytest.raises(FileExistsError):
        setup.install(template, required_bytes=1000)
    assert all(p.read_bytes() == content for p, content in before.items())
    rt = P5Runtime(scope, permit=P5ExecutionPermit(scope.digest, 'SYNTHETIC', offline_test=True))
    rt.start()
    try:
        target = checkpoint(rt, setup=setup, checkpoint_id='fixture1', required_bytes=1024**2)
        result = restore_isolated(target, tmp_path / 'recovered', latest_ledger=rt.ledger.path,
            setup=setup, required_bytes=1000)
        assert result['live_resume_allowed'] is False
        rid = rt.ledger.reserve('auth')
        rt.ledger.finish(rid, success=False)
        with pytest.raises(ValueError, match='BUDGET_ROLLBACK'):
            restore_isolated(target, tmp_path / 'stale', latest_ledger=rt.ledger.path,
                setup=setup, required_bytes=1000)
        assert not (tmp_path / 'stale').exists()
        unknown = checkpoint(rt, setup=setup, checkpoint_id='unknown', required_bytes=1024**2)
        recovery = restore_isolated(unknown, tmp_path / 'unknown-recovered', latest_ledger=rt.ledger.path,
            setup=setup, required_bytes=1000)
        assert recovery['unresolved_preserved']
    finally:
        rt.close()


@pytest.mark.parametrize('field,value', [('volume','OTHER'), ('filesystem','FAT32'), ('fixed',False),
    ('ancestors_unaliased',False), ('isolated',False), ('identities',()),
    ('acl_principals',frozenset({'Everyone'})), ('acl_inheritance_disabled',False),
    ('free_bytes',None), ('free_bytes',9*1024**3), ('c_free_bytes',1024**3), ('run_bytes',10*1024**3)])
def test_t06_unknown_alias_acl_and_capacity_rejected_before_creation(tmp_path, field, value):
    setup = synthetic_setup()
    inspect = setup.inspect
    setup.inspect = lambda p: replace(inspect(p), **{field:value})
    path = tmp_path / 'new'
    with pytest.raises(ValueError):
        setup.check(path, required_bytes=0)
    assert not path.exists()


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_t06_partial_install_retained_and_never_reinitialized(tmp_path, market):
    template = replace(scope_for(tmp_path / 'template', market), root=str(tmp_path / 'partial'), preparation_limit=2)
    setup = synthetic_setup()
    setup.probe = lambda p: {'create':True}
    with pytest.raises(ValueError, match='PROBE_FAILED'):
        setup.install(template, required_bytes=1000)
    assert template.directory.exists()
    assert not (template.directory / 'ledger.json').exists()
    with pytest.raises(FileExistsError):
        setup.install(template, required_bytes=1000)


def test_t02_each_physical_brand_page_reads_bridge_before_signing(runtime, monkeypatch):
    rt = runtime
    rt._credentials = secrets(rt)
    rt.authorization_guard = lambda operation=None: None
    events = []
    def bridge():
        rid = rt.ledger.reserve('bridge')
        rt.ledger.finish(rid, success=True)
        rt._credentials = replace(rt._credentials, shopee_credentials=replace(
            rt._credentials.shopee_credentials, access_token='SYNTHETIC_' + str(len(events))))
        events.append('bridge')
    monkeypatch.setattr(rt, 'refresh_access_token', bridge)
    def response(url, params, timeout):
        events.append('send')
        assert params['access_token'].startswith('SYNTHETIC_')
        if url.endswith('get_category'):
            return catalog_response(url, params)
        offset = int(params['offset'])
        body = catalog_response(url, params)
        body['response']['brand_list'][0]['brand_id'] += offset
        body['response'].update(has_next_page=offset == 0, next_offset=1)
        return body
    client = make_catalog_client(rt, rt._credentials, request_json=response)
    rt.acquire_catalog(client)
    rt.acquire_brand(client, 100578)
    assert events == ['bridge','send'] * 3
    assert len([r for r in rt.ledger.data['reservations'] if r['kind']=='bridge']) == 3
    assert len([r for r in rt.ledger.data['reservations'] if r['kind']=='shopee']) == 3


def test_t01_lower_p2_write_and_download_cannot_bypass_operation_allowlist(runtime):
    rt = runtime
    prepare(rt)
    def guard(operation=None):
        if operation in {'p2.save','output'}:
            raise P5Stopped('P5_OPERATION_NOT_APPROVED')
    rt.authorization_guard = guard
    before = rt.workflow.bench.store.history()
    for operation in (rt.workflow.bench.refresh,
                      lambda: rt.workflow.bench.output({'B000000000':1})):
        with pytest.raises(ValueError, match='NOT_APPROVED'):
            operation()
    assert rt.workflow.bench.store.history() == before


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
    monkeypatch.setattr('google.auth.load_credentials_from_dict', lambda *a, **k: (Credentials(), None))
    credential_file = tmp_path / 'synthetic-google.json'
    credential_file.write_text('{"type":"authorized_user"}')
    bridge = P5BridgeTransport(runtime, credential_file=credential_file, spreadsheet_id='synthetic-sheet')
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


@pytest.mark.parametrize('finder_status', [200, 503])
def test_empty_finder_never_runs_legacy_diagnostics_or_resends_query(runtime, keepa_raw_product, finder_status):
    calls = []
    def send(url, **kwargs):
        calls.append(url)
        body = {'tokensLeft': 500, 'tokensConsumed': 0, 'refillRate': 5, 'refillIn': 60000}
        if '/product/' in url:
            body.update(tokensConsumed=1, products=[dict(keepa_raw_product, asin='B000000000')])
        elif '/query/' in url:
            body.update(tokensConsumed=1, asinList=[], totalResults=0)
        return SimpleNamespace(status_code=finder_status if '/query/' in url else 200, json=lambda: body)
    client = make_keepa_client(runtime, secrets(runtime), transport=send)
    if finder_status == 200:
        result = client.find_related_products('B000000000', 1)
        assert not result.rows
    else:
        from modules.keepa_client import KeepaClientError
        with pytest.raises(KeepaClientError, match='P5'):
            client.find_related_products('B000000000', 1)
    assert sum('/query/' in url for url in calls) == 1
    assert len(calls) == 3  # token, seed, one approved Finder page only.


@pytest.mark.parametrize('kind', ['external_account', 'impersonated_service_account', 'other'])
def test_google_external_credential_adapters_are_refused_before_loading(tmp_path, monkeypatch, kind):
    from modules.p5_transport import P5BridgeTransport
    runtime = runtime_for(tmp_path, bridge_spreadsheet_id='synthetic-sheet')
    path = tmp_path / 'synthetic-google.json'
    path.write_text(json.dumps({'type': kind}))
    monkeypatch.setattr('google.auth.load_credentials_from_dict', lambda *a, **k: pytest.fail('unapproved credential adapter loaded'))
    try:
        bridge = P5BridgeTransport(runtime, credential_file=path, spreadsheet_id='synthetic-sheet')
        with pytest.raises(P5Stopped, match='CREDENTIAL_TYPE_REFUSED'):
            bridge.read_values('synthetic-sheet', 'A:C')
        assert not runtime.ledger.data['reservations']
    finally:
        runtime.close()
