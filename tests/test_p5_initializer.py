"""Synthetic P5 initializer and OS records; no live authorization proof."""
from dataclasses import asdict, replace
from datetime import timedelta
import json
from pathlib import Path

import pytest

from modules import p5_initializer, p5_operator
from modules.p5_initializer import initialize_and_run
from modules.p5_operator import (OriginalOwnerRecord, P5OwnerAuthority,
    P5Checkpoint, P5Operator, configured_runtime, register_operator)
from modules.p5_live_adapter import P5CodeIdentity, P5ServiceCredentials, P5KeepaReference
from modules.p5_runtime import P5Stopped
from modules.sg_continuous_runtime import _digest
from test_p5_composition import observer_fixture
from test_p5_runtime import scope_for, trusted_adapter, forbid_network
from test_expansion_gate_handoff import offline

LOADED_SOURCE_CHECK = P5CodeIdentity._require_loaded_source


@pytest.fixture(autouse=True)
def isolated_registration(monkeypatch):
    monkeypatch.setattr(p5_operator, '_installed_operator', None)


def components(tmp_path, monkeypatch, market='PH'):
    scope, observer, process, code = observer_fixture(tmp_path, monkeypatch)
    if market == 'SG':
        scope = scope_for(tmp_path, market, bridge_spreadsheet_id='synthetic-sheet')
    scope = replace(scope, image_requests=0, openai_requests=0, openai_usd='0',
        execution_target=_digest({k: process[k] for k in ('machine', 'pid', 'started')} | {'port': 8511}))
    observer.credentials = P5ServiceCredentials(keepa=P5KeepaReference(
        scope.credential_ref, market, scope.shop_id, 'SYNTHETIC_UNUSED_KEY'))
    # Keepa-only acquisition: unused services receive no budget or permission.
    scope = replace(scope, shopee_requests=0, bridge_requests=0, auth_requests=0)
    operations = frozenset({'keepa.token', 'keepa.product', 'keepa.query'})
    observer.operations = operations
    _, _, _, approval = trusted_adapter(scope)
    ticket = {'version': 'SYNTHETIC', 'scope': scope.digest, 'operations': sorted(operations)}
    approval = replace(approval, operations=operations, ticket_digest=_digest(ticket),
        observations_digest=_digest(observer.observe(scope)))
    record = OriginalOwnerRecord(approval.original_instruction_ref, approval.owner_ref,
        'SYNTHETIC ONLY: reviewed fixture, never an actual Owner authorization', approval.approved_at, approval)
    source = {'record': record, 'ticket': ticket}
    authority = P5OwnerAuthority(read_original=lambda ref: source['record'],
        read_ticket=lambda: source['ticket'], reviewed_record=record, reviewed_ticket=ticket)
    values = dict(authority=authority, observer=observer, credentials=observer.credentials,
        checkpoint=P5Checkpoint(observer.storage.setup(), required_bytes=1024**2),
        approval_reference=record.reference)
    return scope, values, source, code


def scope_file(tmp_path, scope):
    path = tmp_path / 'synthetic-scopes.json'
    path.write_text(json.dumps([asdict(scope)]), encoding='utf-8')
    return path


def block_secrets(monkeypatch):
    def refuse(*a, **k):
        pytest.fail('credential body read in initializer/display/start')
    monkeypatch.setattr(P5ServiceCredentials, 'resolve', refuse)
    monkeypatch.setattr('modules.shopee_catalog_client.load_shopee_catalog_credentials', refuse)




@pytest.mark.parametrize('bad', [None, 'APPROVED', {'APPROVED': True}, lambda: None, object(),
    object.__new__(type('SyntheticSubclass', (P5Operator,), {}))])
def test_registration_rejects_untyped_values(bad):
    with pytest.raises(P5Stopped, match='P5_TRUSTED_OPERATOR_REQUIRED'):
        register_operator(bad)
    assert p5_operator._installed_operator is None




@pytest.mark.parametrize('change', ['missing', 'body', 'revoked', 'expired', 'ticket',
    'scope', 'shop', 'release', 'code', 'market'])
def test_registered_connection_rejects_mismatch_before_io(tmp_path, monkeypatch, change):
    scope, values, source, code = components(tmp_path, monkeypatch)
    block_secrets(monkeypatch)
    from streamlit.web import bootstrap
    monkeypatch.setattr(bootstrap, 'run', lambda *a: None)
    initialize_and_run(**values, scope_config=tmp_path / 'unused.json')
    if change == 'missing':
        source['record'] = None
    elif change == 'body':
        source['record'] = replace(source['record'], body='SYNTHETIC_CHANGED')
    elif change in {'revoked', 'expired'}:
        record = source['record']
        update = {'revoked': True} if change == 'revoked' else {'expires_at': record.approval.approved_at-timedelta(seconds=1)}
        source['record'] = replace(record, approval=replace(record.approval, **update))
    elif change == 'ticket':
        source['ticket']['version'] = 'CHANGED'
    elif change == 'code':
        code['release'] = 'f' * 40
    else:
        scope = replace(scope, **{'scope': {'run_id': 'other'}, 'shop': {'shop_id': '99'},
            'release': {'release': 'f'*40}, 'market': {'marketplace': 'SG'}}[change])
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    pending = configured_runtime(scope)
    with pytest.raises(P5Stopped, match='P5_(OWNER_APPROVAL_UNVERIFIED|EXECUTION_.*)'):
        pending.start()
    assert pending.runtime.permit is None
    assert before == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_initializer_cannot_replace_operator_or_accept_fake_authority(tmp_path, monkeypatch):
    scope, values, _, _ = components(tmp_path, monkeypatch)
    from streamlit.web import bootstrap
    monkeypatch.setattr(bootstrap, 'run', lambda *a: None)
    with pytest.raises(P5Stopped, match='TRUSTED_OPERATOR_REQUIRED'):
        initialize_and_run(**(values | {'authority': type('Fake', (), {'verify_original': lambda *a: 'APPROVED'})()}),
            scope_config=tmp_path / 'unused.json')
    assert p5_operator._installed_operator is None
    initialize_and_run(**values, scope_config=tmp_path / 'unused.json')
    installed = p5_operator._installed_operator
    register_operator(installed)  # same-object registration remains idempotent
    with pytest.raises(P5Stopped, match='ALREADY_REGISTERED'):
        initialize_and_run(**values, scope_config=tmp_path / 'unused.json')
    assert p5_operator._installed_operator is installed


@pytest.mark.parametrize('change', ['loaded', 'source', 'origin'])
def test_windows_observer_checks_initializer_loaded_code_and_source(tmp_path, monkeypatch, change):
    scope, observer, _, _ = observer_fixture(tmp_path, monkeypatch)
    # Restore the real function: this test must not inherit the fixture's stub.
    original = Path(p5_initializer.__file__)
    check = LOADED_SOURCE_CHECK
    def verify(module, path):
        if module is p5_initializer:
            check(module, path)
    monkeypatch.setattr(P5CodeIdentity, '_require_loaded_source', verify)
    if change == 'loaded':
        monkeypatch.setattr(p5_initializer, 'initialize_and_run', lambda **kw: None)
    elif change == 'source':
        altered = tmp_path / 'altered.py'
        altered.write_bytes(original.read_bytes().replace(b'127.0.0.1', b'0.0.0.0'))
        monkeypatch.setattr(P5CodeIdentity, '_require_loaded_source',
            lambda module, path: check(module, altered) if module is p5_initializer else None)
    else:
        monkeypatch.setattr(p5_initializer, '__file__', str(tmp_path / 'other.py'))
    with pytest.raises(P5Stopped, match='PROCESS_OBSERVATION_MISMATCH'):
        observer.observe(scope)
