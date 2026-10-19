"""Operation-scoped contracts with synthetic authority/HTTP only; never live proof."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from modules.p5_live_adapter import BUDGETS, P5CodeIdentity, P5CredentialResolver
from modules.p5_runtime import P5ExecutionPermit, P5Runtime, P5Stopped, initialize_p5_ledger
from modules.p5_transport import P5HTTP, P5KeepaBudget, make_catalog_client, make_category_provider
from modules.sg_continuous_runtime import _digest
from test_p5_runtime import scope_for, trusted_adapter, secrets, catalog_response, forbid_network
from test_p5_production_connection import credential_reference


def scoped(tmp_path, market='PH', operations=frozenset({'shopee.category', 'bridge', 'auth'}), **limits):
    budgets = dict.fromkeys(BUDGETS, 0)
    budgets['openai_usd'] = '0'
    if operations & {'shopee.category', 'shopee.brand', 'shopee.attribute'}:
        budgets.update(shopee_requests=2)
    for op in ('bridge', 'auth', 'image'):
        if op in operations:
            budgets[op + '_requests'] = 2
    if operations & {'keepa.token', 'keepa.product', 'keepa.query'}:
        budgets.update(keepa_requests=3)
    if 'keepa.product' in operations:
        budgets.update(keepa_products=2)
    if operations & {'keepa.product', 'keepa.query'}:
        budgets.update(keepa_tokens=4)
    if 'openai' in operations:
        budgets.update(openai_requests=2, openai_usd='0.5')
    budgets.update(limits)
    scope = scope_for(tmp_path, market, bridge_spreadsheet_id='synthetic-sheet', **budgets)
    initialize_p5_ledger(scope)
    adapter, authority, observed, approval = trusted_adapter(scope)
    observed['primary_sources'].pop('attribute')
    observed['pricing'] = {} if 'openai' not in operations else observed['pricing']
    approval = replace(approval, operations=operations)
    def bind():
        authority.verify_original = lambda ref: replace(approval, observations_digest=_digest(observed))
    bind()
    return scope, adapter, observed, bind


def production(adapter, observed, scope, tmp_path, monkeypatch):
    # Exercise production branches with explicitly synthetic observations. No secret file exists.
    adapter.synthetic = False
    adapter.code_identity = P5CodeIdentity()
    adapter.resolve_secrets = P5CredentialResolver(credential_reference(scope, tmp_path))
    observed['credential'] = adapter.resolve_secrets.describe(scope)
    code = {k: observed[k] for k in ('release', 'source_digest', 'entrypoint')}
    monkeypatch.setattr(P5CodeIdentity, 'observe', lambda self: code)


@pytest.mark.parametrize('market', ['PH', 'SG'])
@pytest.mark.parametrize('prod', [False, True])
def test_category_preflight_without_attribute_or_openai_is_zero_io(tmp_path, monkeypatch, market, prod):
    scope, adapter, observed, bind = scoped(tmp_path, market)
    observed['primary_sources'].pop('brand')
    if prod:
        production(adapter, observed, scope, tmp_path, monkeypatch)
    bind()
    rt = adapter.compose(scope, approval_reference='SYNTHETIC')
    try:
        rt.start()
        rt.start()
        rt.require_operation('shopee.category')
        assert rt.permit.primary_source_refs == ('category:SYNTHETIC',)
        assert rt.permit.openai_pricing_ref == '' and not rt.ledger.data['reservations']
        assert rt._credentials is None
        for service in ('keepa', 'openai'):
            with pytest.raises(P5Stopped, match='OPERATION_NOT_APPROVED'):
                rt.secrets(service)
        assert rt._credentials is None
    finally:
        rt.checkpoint_hook = lambda *a: None
        rt.close()


@pytest.mark.parametrize('missing', ['category', 'brand'])
def test_brand_requires_both_specs(tmp_path, missing):
    scope, adapter, observed, bind = scoped(tmp_path, operations=frozenset({'shopee.brand', 'bridge', 'auth'}))
    observed['primary_sources'][missing]['verified'] = False
    bind()
    with pytest.raises(P5Stopped, match='PRIMARY_SOURCE_UNVERIFIED'):
        adapter.compose(scope, approval_reference='SYNTHETIC')
    observed['primary_sources'][missing]['verified'] = True
    bind()
    rt = adapter.compose(scope, approval_reference='SYNTHETIC')
    try:
        rt.start()
        assert len(rt.permit.primary_source_refs) == 2
        client = make_catalog_client(rt, secrets(rt), request_json=catalog_response)
        with pytest.raises(P5Stopped, match='CURRENT_CATALOG_ROUTE'):
            rt.acquire_brand(client, 100578)
        assert not rt.ledger.data['reservations']
    finally:
        rt.close()


@pytest.mark.parametrize('op', ['p2.save', 'output'])
@pytest.mark.parametrize('missing', ['category', 'brand'])
def test_preparation_requires_current_category_and_brand_specs_without_network_grants(tmp_path, op, missing):
    scope, adapter, observed, bind = scoped(tmp_path, operations=frozenset({op, 'p2.save'}))
    observed['primary_sources'][missing]['verified'] = False
    bind()
    with pytest.raises(P5Stopped, match='PRIMARY_SOURCE_UNVERIFIED'):
        adapter.compose(scope, approval_reference='SYNTHETIC')
    observed['primary_sources'][missing]['verified'] = True
    bind()
    rt = adapter.compose(scope, approval_reference='SYNTHETIC')
    try:
        rt.start()
        rt.require_operation(op)
        with pytest.raises(P5Stopped, match='OPERATION_NOT_APPROVED'):
            rt.catalog_client()
        assert rt._credentials is None and not rt.ledger.data['reservations']
    finally:
        rt.close()


@pytest.mark.parametrize('field', ['verified', 'reference', 'body_digest'])
def test_openai_needs_current_price(tmp_path, field):
    scope, adapter, observed, bind = scoped(tmp_path, operations=frozenset({'openai'}))
    observed['primary_sources'] = {}
    observed['pricing'][field] = False if field == 'verified' else ''
    bind()
    with pytest.raises(P5Stopped, match='CURRENT_OPENAI_PRICING_UNVERIFIED'):
        adapter.compose(scope, approval_reference='SYNTHETIC')


@pytest.mark.parametrize('limit,value', [('openai_requests', 0), ('openai_usd', '0'),
    ('openai_models', ()), ('openai_input_bound', 0), ('openai_output_tokens', 0)])
def test_openai_requires_model_and_finite_positive_approved_limits(tmp_path, limit, value):
    scope, adapter, _, _ = scoped(tmp_path, operations=frozenset({'openai'}), **{limit:value})
    with pytest.raises(P5Stopped):
        adapter.compose(scope, approval_reference='SYNTHETIC')


def test_openai_without_shopee_needs_own_key_before_client_construction(tmp_path, monkeypatch):
    scope, adapter, observed, bind = scoped(tmp_path, operations=frozenset({'openai'}))
    observed['primary_sources'] = {}
    bind()
    rt = adapter.compose(scope, approval_reference='SYNTHETIC')
    try:
        rt.start()
        monkeypatch.setattr('requests.Session', lambda: pytest.fail('constructed without key'))
        with pytest.raises(P5Stopped, match='OPENAI_CREDENTIAL_REQUIRED'):
            make_category_provider(rt, replace(secrets(rt), shopee_credentials=None, openai_key=''))
        assert not rt.ledger.data['reservations']
    finally:
        rt.close()


@pytest.mark.parametrize('operation', ['shopee.attribute', 'shopee.brand', 'keepa.product', 'openai', 'output'])
def test_unapproved_operations_stop_before_secret_or_send(tmp_path, operation):
    scope, adapter, _, _ = scoped(tmp_path)
    rt = adapter.compose(scope, approval_reference='SYNTHETIC')
    try:
        rt.start()
        with pytest.raises(P5Stopped, match='OPERATION_NOT_APPROVED'):
            rt.require_operation(operation)
        with pytest.raises(P5Stopped):
            rt.acquire_attributes(None, 100578)
        assert rt.attribute_status(100578)['state'] == 'NOT_FETCHED'
        assert not rt.ledger.data['reservations'] and rt._credentials is None
    finally:
        rt.close()


@pytest.mark.parametrize('missing', ['bridge', 'auth'])
def test_shopee_dependencies_cannot_be_removed_or_zeroed(tmp_path, missing):
    ops = frozenset({'shopee.category', 'bridge', 'auth'} - {missing})
    scope, adapter, _, _ = scoped(tmp_path, operations=ops)
    with pytest.raises(P5Stopped, match='DEPENDENCY_NOT_APPROVED'):
        adapter.compose(scope, approval_reference='SYNTHETIC')


@pytest.mark.parametrize('budget', ['shopee_requests', 'bridge_requests', 'auth_requests'])
def test_related_shopee_sends_need_positive_individual_budgets(tmp_path, budget):
    scope, adapter, _, _ = scoped(tmp_path, **{budget:0})
    with pytest.raises(P5Stopped, match='OPERATION_BUDGET_MISMATCH'):
        adapter.compose(scope, approval_reference='SYNTHETIC')


def test_unused_budget_cannot_be_spent_and_zero_is_required(tmp_path):
    scope, adapter, _, _ = scoped(tmp_path, openai_usd='0.01')
    with pytest.raises(P5Stopped, match='OPERATION_BUDGET_MISMATCH'):
        adapter.compose(scope, approval_reference='SYNTHETIC')


def test_production_attribute_rejected_even_with_legacy_permit_and_no_guard(tmp_path):
    scope = scope_for(tmp_path)
    initialize_p5_ledger(scope)
    rt = P5Runtime(scope, permit=P5ExecutionPermit(scope.digest, 'SYNTHETIC', ('C','B','A')),
        execution_identity=lambda: (scope.release, scope.execution_target))
    rt.start()
    try:
        client = make_catalog_client(rt, secrets(rt))
        with pytest.raises(P5Stopped, match='ATTRIBUTE_LIVE_NOT_ENABLED'):
            client.get_attribute_trees(scope.marketplace, (100578,))
        with pytest.raises(P5Stopped, match='ATTRIBUTE_LIVE_NOT_ENABLED'):
            rt.acquire_attributes(client, 100578)
        assert not rt.ledger.data['reservations']
        assert rt.attribute_status(100578)['state'] == 'NOT_FETCHED'
    finally:
        rt.close()


@pytest.mark.parametrize('failure', ['shop', 'release', 'source', 'pricing', 'unknown', 'budget'])
def test_scoped_runtime_rechecks_binding_and_sticky_consumption(tmp_path, failure):
    scope, adapter, observed, bind = scoped(tmp_path)
    rt = adapter.compose(scope, approval_reference='SYNTHETIC')
    rt.start()
    try:
        if failure == 'shop':
            observed['credential']['shop'] = '99'
            bind()
        elif failure == 'release':
            observed['release'] = '1'*40
            bind()
        elif failure == 'source':
            observed['primary_sources']['category']['verified'] = False
            bind()
        elif failure == 'pricing':
            # Unused pricing remains irrelevant even if unverified, but changing
            # the approved observation still invalidates the original binding.
            observed['pricing'] = {'verified':False}
        else:
            for _ in range(2):
                rid = rt.ledger.reserve('auth')
                rt.ledger.finish(rid, success=failure != 'unknown')
                if failure == 'unknown':
                    break
        with pytest.raises(P5Stopped):
            if failure == 'budget':
                P5HTTP(rt, 'auth', session=SimpleNamespace(request=lambda *a, **k: pytest.fail('over-budget send'))).post(
                    'https://oauth2.googleapis.com/token')
            else:
                rt.require_operation('shopee.category')
        if failure == 'unknown':
            assert rt.ledger.data['reservations'][0]['state'] == 'UNKNOWN'
        assert rt._credentials is None
    finally:
        rt.close()

@pytest.mark.parametrize('market', ['PH', 'SG'])
@pytest.mark.parametrize('partial', [False, True])
def test_brand_only_current_route_and_complete_paging_remain_required(tmp_path, monkeypatch, market, partial):
    from test_sg_initial_beta import catalog
    scope, adapter, _, _ = scoped(tmp_path, market,
        operations=frozenset({'shopee.brand', 'bridge', 'auth'}), shopee_requests=12)
    rt = adapter.compose(scope, approval_reference='SYNTHETIC')
    rt.start()
    calls = []
    try:
        rt.workflow.supply_catalog(replace(catalog(), marketplace=market), reference='SYNTHETIC', revision='fixture')
        def response(*args):
            calls.append(args)
            body = catalog_response(*args)
            if partial:
                body['response']['has_next_page'] = True
                body['response']['next_offset'] = len(calls)
            return body
        client = make_catalog_client(rt, secrets(rt), request_json=response)
        rt.category_receipt = dict(session=rt.workflow.session.scope,
            binding=rt.workflow.session.current_classification_binding(), client=client, official=False)
        # Simulated token supply only. Physical Bridge/auth counters are tested
        # separately; no real Google file or transport is reached here.
        monkeypatch.setattr(rt, 'refresh_access_token', lambda: None)
        rt._credentials = secrets(rt)
        if partial:
            with pytest.raises(ValueError):
                rt.acquire_brand(client, 100578)
            assert 1 <= len(calls) <= 10
            assert 100578 not in rt.workflow.session._brands
        else:
            result = rt.acquire_brand(client, 100578)
            assert result.complete and result.current and len(calls) == 1
            assert not rt.workflow.bench.prepared_pool()  # no implicit P2 permission
        with pytest.raises(P5Stopped, match='OPERATION_NOT_APPROVED'):
            rt.acquire_catalog(client)
        assert all(r['kind'] == 'shopee' for r in rt.ledger.data['reservations'])
    finally:
        rt.close()


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_keepa_only_needs_no_catalog_price_or_shopee_credential(tmp_path, market):
    scope, adapter, observed, bind = scoped(tmp_path, market,
        operations=frozenset({'keepa.token', 'keepa.product'}))
    observed['primary_sources'] = {}
    bind()
    rt = adapter.compose(scope, approval_reference='SYNTHETIC')
    rt.start()
    try:
        rt._credentials = replace(secrets(rt), shopee_credentials=None)
        assert rt.secrets('keepa').keepa_key
        budget = P5KeepaBudget(rt)
        token = budget.reserve_keepa_call('token', {'key':'SYNTHETIC_ONLY'})
        budget.complete_keepa_call(token, {'tokensConsumed':0, 'tokensLeft':5}, 200)
        product = budget.reserve_keepa_call('product', {'key':'SYNTHETIC_ONLY', 'domain':5, 'asin':scope.asins[0]})
        budget.complete_keepa_call(product, {'tokensConsumed':1, 'tokensLeft':4}, 200)
        with pytest.raises(P5Stopped, match='OUTSIDE_SCOPE'):
            budget.reserve_keepa_call('product', {'key':'SYNTHETIC_ONLY', 'domain':5, 'asin':'B999999999'})
        assert len(rt.ledger.data['reservations']) == 2
        assert not rt.permit.primary_source_refs and rt.permit.openai_pricing_ref == ''
    finally:
        rt.close()


@pytest.mark.parametrize('field', ['verified', 'body_digest', 'version', 'app_shop_permission',
                                  'paging', 'request_response', 'rate_limit'])
def test_category_spec_fields_cannot_be_omitted(tmp_path, field):
    scope, adapter, observed, bind = scoped(tmp_path)
    observed['primary_sources']['category'].pop(field)
    bind()
    with pytest.raises(P5Stopped, match='PRIMARY_SOURCE_UNVERIFIED'):
        adapter.compose(scope, approval_reference='SYNTHETIC')

@pytest.mark.parametrize('service,operations', [('keepa', frozenset({'keepa.token','keepa.product'})),
                                               ('openai', frozenset({'openai'}))])
def test_production_paid_scope_does_not_read_shopee_or_google_body(tmp_path, monkeypatch, service, operations):
    scope, adapter, observed, bind = scoped(tmp_path, operations=operations)
    observed['primary_sources'] = {}
    adapter.synthetic = False
    adapter.code_identity = P5CodeIdentity()
    monkeypatch.setattr(P5CodeIdentity, 'observe', lambda self:
        {k: observed[k] for k in ('release', 'source_digest', 'entrypoint')})
    monkeypatch.setattr('modules.shopee_catalog_client.load_shopee_catalog_credentials',
                        lambda *a, **k: pytest.fail('unused Shopee credential read'))
    bind()
    rt = adapter.compose(scope, approval_reference='SYNTHETIC')
    rt.checkpoint_hook = lambda *a: None
    rt.start()
    try:
        with pytest.raises(P5Stopped, match=service.upper() + '_CREDENTIAL_REQUIRED'):
            rt.secrets(service)
        with pytest.raises(P5Stopped):
            rt.refresh_access_token()
        assert rt._credentials is None and not rt.ledger.data['reservations']
    finally:
        rt.close()

@pytest.mark.parametrize('missing', ['scope', 'authorization', 'sources', 'wrong-source', 'pricing', 'operation'])
def test_scoped_permit_itself_rejects_missing_requirements_without_adapter_guard(tmp_path, missing):
    scope = scope_for(tmp_path)
    permit = P5ExecutionPermit(scope.digest, 'SYNTHETIC', ('category:SYNTHETIC',),
        operations=frozenset({'shopee.category'}))
    kwargs = {}
    if missing == 'scope':
        permit = replace(permit, scope_digest='different')
    elif missing == 'authorization':
        permit = replace(permit, authorization_ref='')
    elif missing == 'sources':
        permit = replace(permit, primary_source_refs=())
    elif missing == 'wrong-source':
        permit = replace(permit, primary_source_refs=('attribute:SYNTHETIC',))
    elif missing == 'pricing':
        permit = replace(permit, operations=frozenset({'openai'}), primary_source_refs=())
    else:
        kwargs['operational'] = True
    with pytest.raises(P5Stopped):
        permit.require(scope, **kwargs)
