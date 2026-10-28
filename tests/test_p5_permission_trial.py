"""One designated PH shop's permission trial; all records, files and HTTP are synthetic."""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from modules.p5_live_adapter import BUDGETS, OperatorApproval, P5CategoryPermissionTrial
from modules.p5_operator import OriginalOwnerRecord, P5OwnerAuthority
from modules.p5_runtime import P5Stopped, P5_OPERATIONS, P5_CATEGORY_ACQUISITION_OPERATIONS
from modules.p5_transport import make_catalog_client
from modules.sg_continuous_runtime import _digest
from test_p5_category_acquisition import template_for
from test_p5_operation_preflight import production
from test_p5_runtime import synthetic_setup, trusted_adapter, secrets, catalog_response, forbid_network


def trial_for(tmp_path, market='PH'):
    scope = synthetic_setup().install(template_for(tmp_path, market), required_bytes=1000)
    adapter, authority, observed, approval = trusted_adapter(scope)
    source = observed['primary_sources']['category']
    source.update(verified=False, spec_verified=True, app_shop_permission='',
                  app_shop_permission_status='UNVERIFIED')
    observed['primary_sources'] = {'category': source}
    observed['pricing'] = {}
    trial = P5CategoryPermissionTrial('SYNTHETIC_EXISTING_SHOP_DESIGNATION', market,
                                      scope.shop_id, scope.credential_ref)
    approval = replace(approval, operations=P5_CATEGORY_ACQUISITION_OPERATIONS,
                       category_permission_trial=trial)
    state = SimpleNamespace(scope=scope, adapter=adapter, authority=authority,
                            observed=observed, approval=approval)
    bind(state)
    return state


def bind(state):
    state.approval = replace(state.approval, observations_digest=_digest(state.observed))
    state.authority.verify_original = lambda ref: state.approval


@pytest.mark.parametrize('prod', [False, True])
def test_designated_trial_starts_without_promoting_permission_or_doing_io(tmp_path, monkeypatch, prod):
    state = trial_for(tmp_path)
    if prod:
        production(state.adapter, state.observed, state.scope, tmp_path, monkeypatch)
        state.adapter.checkpoint = lambda *args: None  # Synthetic checkpoint, not real backup evidence.
        bind(state)
    original = deepcopy(state.observed['primary_sources'])
    rt = state.adapter.compose(state.scope, approval_reference='SYNTHETIC')
    try:
        rt.start()
        rt.start()
        rt.require_operation('shopee.category')
        assert rt.permit.operations == P5_CATEGORY_ACQUISITION_OPERATIONS
        assert state.observed['primary_sources'] == original
        assert rt._credentials is None and not rt.ledger.data['reservations']
        for operation in P5_OPERATIONS - P5_CATEGORY_ACQUISITION_OPERATIONS:
            with pytest.raises(P5Stopped, match='OPERATION_NOT_APPROVED'):
                rt.require_operation(operation)
        assert rt._credentials is None and not rt.ledger.data['reservations']
    finally:
        rt.close()


@pytest.mark.parametrize('change', ['missing-approval', 'dict-approval', 'bool-approval',
    'designation', 'shop', 'credential', 'market', 'product-scope', 'two-allocations',
    'larger-total', 'larger-send', 'extra-operation'])
def test_trial_cannot_expand_or_be_enabled_by_a_flag(tmp_path, change):
    state = trial_for(tmp_path)
    trial = state.approval.category_permission_trial
    if change in {'missing-approval', 'dict-approval', 'bool-approval'}:
        value = {'missing-approval': None, 'dict-approval': asdict(trial), 'bool-approval': True}[change]
        state.approval = replace(state.approval, category_permission_trial=value)
        state.observed['primary_sources']['category']['permission_trial'] = True  # Config alone is inert.
    elif change in {'designation', 'shop', 'credential', 'market'}:
        fields = {'designation': {'owner_designation_ref': ''}, 'shop': {'shop_id': '99'},
                  'credential': {'credential_ref': 'other-ref'}, 'market': {'marketplace': 'SG'}}
        state.approval = replace(state.approval, category_permission_trial=replace(trial, **fields[change]))
    elif change == 'two-allocations':
        state.approval = replace(state.approval, allocations=(state.scope, replace(state.scope, marketplace='SG')))
        state.approval = replace(state.approval, total_limits=tuple(
            (key, str(float(value) * 2)) for key, value in state.approval.total_limits))
    elif change == 'larger-total':
        state.approval = replace(state.approval, total_limits=tuple(
            (key, 2 if key == 'shopee_requests' else value) for key, value in state.approval.total_limits))
    elif change == 'extra-operation':
        state.approval = replace(state.approval, operations=state.approval.operations | {'shopee.brand'})
    else:
        state.scope = replace(state.scope, **({'category_ids': (100578,)} if change == 'product-scope'
                                             else {'shopee_requests': 2}))
        state.approval = replace(state.approval, scope_digest=state.scope.digest, allocations=(state.scope,))
        state.observed['plan'] = asdict(state.scope)
    bind(state)
    with pytest.raises(P5Stopped):
        state.adapter.compose(state.scope, approval_reference='SYNTHETIC')
    assert not json.loads((state.scope.directory / 'ledger.json').read_text())['reservations']


def test_sg_cannot_use_the_unknown_permission_exception(tmp_path):
    state = trial_for(tmp_path, 'SG')
    with pytest.raises(P5Stopped, match='CATEGORY_PERMISSION_TRIAL_INVALID'):
        state.adapter.compose(state.scope, approval_reference='SYNTHETIC')


@pytest.mark.parametrize('field,value', [('body_digest', ''), ('version', ''), ('paging', ''),
    ('request_response', ''), ('rate_limit', ''), ('spec_verified', False),
    ('app_shop_permission_status', ''), ('app_shop_permission', 'claimed verified'), ('verified', True)])
def test_trial_does_not_waive_spec_checks_or_accept_false_verification(tmp_path, field, value):
    state = trial_for(tmp_path)
    state.observed['primary_sources']['category'][field] = value
    bind(state)
    with pytest.raises(P5Stopped, match='PRIMARY_SOURCE_UNVERIFIED'):
        state.adapter.compose(state.scope, approval_reference='SYNTHETIC')


def test_unknown_marker_cannot_be_promoted_in_an_ordinary_approval(tmp_path):
    state = trial_for(tmp_path)
    state.approval = replace(state.approval, category_permission_trial=None)
    state.observed['primary_sources']['category'].update(verified=True, app_shop_permission='claimed')
    bind(state)
    with pytest.raises(P5Stopped, match='PRIMARY_SOURCE_UNVERIFIED'):
        state.adapter.compose(state.scope, approval_reference='SYNTHETIC')


@pytest.mark.parametrize('outcome', ['success', '403', '429', 'timeout', 'hierarchy', 'wrong-shop'])
def test_bounded_sdk_trace_and_failure_preservation(tmp_path, monkeypatch, outcome):
    state = trial_for(tmp_path)
    rt = state.adapter.compose(state.scope, approval_reference='SYNTHETIC')
    path = tmp_path / 'synthetic-google.json'
    path.write_text('{"type":"authorized_user"}')
    rt._credentials = replace(secrets(rt), google_credential_file=str(path))
    calls = []
    class Session:
        def mount(self, *args): pass
        def request(self, method, url, **kwargs):
            assert kwargs['allow_redirects'] is False
            calls.append('auth' if url.endswith('/token') else 'bridge')
            body = {'access_token': 'SYNTHETIC_ONLY', 'expires_in': 300} if url.endswith('/token') else {
                'values': [['marketplace', 'shop_id', 'access_token'],
                           ['PH', '99' if outcome == 'wrong-shop' else '22', 'SYNTHETIC_ONLY']]}
            return SimpleNamespace(status_code=200, content=json.dumps(body).encode(), headers={}, json=lambda: body)
    class Credentials:
        def before_request(self, request, method, url, headers):
            request('https://oauth2.googleapis.com/token', method='POST', body=b'synthetic')
            headers['authorization'] = 'SYNTHETIC_ONLY'
    monkeypatch.setattr('requests.Session', Session)
    monkeypatch.setattr('google.auth.load_credentials_from_dict', lambda *a, **k: (Credentials(), None))
    def response(*args):
        calls.append('shopee')
        if outcome in {'403', '429'}:
            raise HTTPError('https://partner.shopeemobile.com/api/v2/product/get_category',
                            int(outcome), 'SYNTHETIC', None, None)
        if outcome == 'timeout':
            raise TimeoutError('SYNTHETIC')
        if outcome == 'hierarchy':
            return {'response': {'category_list': [dict(category_id=2, parent_category_id=1,
                category_name='Synthetic orphan', is_leaf=True)]}}
        return catalog_response(*args)
    rt.start()
    try:
        client = make_catalog_client(rt, rt.secrets('shopee'), request_json=response)
        if outcome == 'success':
            assert rt.acquire_catalog(client).marketplace == 'PH'
            assert rt.category_receipt['official'] is False
        else:
            with pytest.raises((ValueError, RuntimeError)):
                rt.acquire_catalog(client)
            assert rt.category_receipt is None
        expected = ['auth', 'bridge'] if outcome == 'wrong-shop' else ['auth', 'bridge', 'shopee']
        assert calls == expected
        saved = deepcopy(rt.ledger.data['reservations'])
        with pytest.raises((ValueError, RuntimeError)):
            rt.acquire_catalog(client)
        assert calls == expected and rt.ledger.data['reservations'] == saved
        assert state.observed['primary_sources']['category']['verified'] is False
        assert state.observed['primary_sources']['category']['app_shop_permission_status'] == 'UNVERIFIED'
        assert not rt.workflow.bench.store.products()
    finally:
        rt.close()


@pytest.mark.parametrize('change', ['designation', 'revoked', 'expired', 'ticket'])
def test_trial_is_bound_to_original_review_and_rechecked_before_operations(tmp_path, change):
    state = trial_for(tmp_path)
    ticket = {'scope': state.scope.digest, 'purpose': 'SYNTHETIC_PERMISSION_TRIAL'}
    state.approval = replace(state.approval, ticket_digest=_digest(ticket))
    record = OriginalOwnerRecord(state.approval.original_instruction_ref, state.approval.owner_ref,
        'SYNTHETIC ONLY: review existing PH shop designation and one permission trial',
        state.approval.approved_at, state.approval)
    current = {'record': record}
    state.adapter.authority = P5OwnerAuthority(read_original=lambda ref: current['record'],
        read_ticket=lambda: ticket, reviewed_record=record, reviewed_ticket=ticket)
    rt = state.adapter.compose(state.scope, approval_reference=record.reference)
    try:
        rt.start()
        if change == 'ticket':
            ticket['purpose'] = 'CHANGED_SYNTHETIC_TICKET'
        else:
            fields = {'designation': {'category_permission_trial': replace(
                record.approval.category_permission_trial, shop_id='99')},
                'revoked': {'revoked': True}, 'expired': {'expires_at': record.approval.approved_at}}
            current['record'] = replace(record, approval=replace(record.approval, **fields[change]))
        with pytest.raises(P5Stopped, match='OWNER_APPROVAL_UNVERIFIED'):
            rt.require_operation('shopee.category')
        assert rt._credentials is None and not rt.ledger.data['reservations']
    finally:
        rt.close()


def test_absent_trial_preserves_the_prechange_original_record_digest():
    now = datetime(2026, 10, 28, tzinfo=timezone.utc)
    approval = OperatorApproval('SYNTHETIC_OWNER', 'SYNTHETIC_ORIGINAL', now, now+timedelta(hours=1),
        'synthetic-end', '2'*64, '0'*64, '1'*64, P5_CATEGORY_ACQUISITION_OPERATIONS, (),
        tuple((key, '0' if key == 'openai_usd' else 0) for key in BUDGETS))
    record = OriginalOwnerRecord('SYNTHETIC_ORIGINAL', 'SYNTHETIC_OWNER',
                                'Synthetic legacy Owner record', now, approval)
    assert record.digest == '2bc7e4195b3ec8785c2e4b1c519f805b9d9e1df45adda1e8f0e5bb0007105523'
