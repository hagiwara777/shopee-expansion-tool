"""P5 production wiring with synthetic records, OS and HTTP. Never live I/O."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from modules.p5_live_adapter import (P5CredentialResolver, P5KeepaReference,
    P5ServiceCredentials, P5CodeIdentity)
from modules.p5_operator import (OriginalOwnerRecord, P5OwnerAuthority, P5Checkpoint,
    PendingP5Runtime, P5Operator, configured_runtime)
from modules.p5_runtime import P5Stopped, initialize_p5_ledger
from modules.p5_windows import WindowsP5Observer, WindowsStorage
from modules.sg_continuous_runtime import _digest
from test_p5_runtime import (scope_for, trusted_adapter, runtime_for, synthetic_setup,
    forbid_network, secrets)
from test_p5_production_connection import credential_reference
from test_expansion_gate_handoff import offline


def owner_fixture(tmp_path):
    scope = scope_for(tmp_path)
    adapter, _, observed, approval = trusted_adapter(scope)
    ticket = {'version': 'SYNTHETIC1', 'scope': scope.digest, 'operations': sorted(approval.operations)}
    approval = replace(approval, ticket_digest=_digest(ticket))
    record = OriginalOwnerRecord(approval.original_instruction_ref, approval.owner_ref,
        'SYNTHETIC original instruction reviewed by trusted human operator',
        approval.approved_at, approval)
    source = {'record': record, 'ticket': ticket}
    authority = P5OwnerAuthority(read_original=lambda ref: source['record'],
        read_ticket=lambda: source['ticket'], reviewed_record=record, reviewed_ticket=ticket)
    adapter.authority = authority
    return scope, adapter, source, record


@pytest.mark.parametrize('change', ['missing', 'json', 'body', 'owner', 'reference', 'time',
    'expired', 'future', 'revoked', 'operations', 'scope', 'ticket', 'end'])
def test_original_record_rechecked_on_start_and_operations(tmp_path, change):
    scope, adapter, source, original = owner_fixture(tmp_path)
    initialize_p5_ledger(scope)
    runtime = adapter.compose(scope, approval_reference=original.reference)
    runtime.start()
    if change == 'missing':
        source['record'] = None
    elif change == 'json':
        source['record'] = {'APPROVED': True}
    elif change in {'body', 'owner', 'reference', 'time'}:
        key = {'owner': 'owner_ref', 'time': 'recorded_at'}.get(change, change)
        source['record'] = replace(original, **{key: datetime.now(timezone.utc) if change == 'time' else 'changed'})
    elif change == 'ticket':
        source['ticket'] = dict(source['ticket'], version='changed')
    else:
        updates = {'expired': {'expires_at': original.approval.approved_at},
            'future': {'approved_at': datetime.now(timezone.utc) + timedelta(days=1)},
            'revoked': {'revoked': True}, 'operations': {'operations': frozenset({'output'})},
            'scope': {'scope_digest': 'changed'}, 'end': {'end_condition_ref': ''}}[change]
        source['record'] = replace(original, approval=replace(original.approval, **updates))
    try:
        with pytest.raises(P5Stopped, match='OWNER_APPROVAL'):
            runtime.require_operation('keepa.product')
        with pytest.raises(P5Stopped, match='OWNER_APPROVAL'):
            adapter.compose(scope, approval_reference=original.reference)
        assert not runtime.ledger.data['reservations']
    finally:
        runtime.close()


def test_review_digest_does_not_share_mutable_approval_state(tmp_path):
    _, adapter, source, original = owner_fixture(tmp_path)
    limits = list(original.approval.total_limits)
    record = replace(original, approval=replace(original.approval, total_limits=limits))
    source['record'] = record
    authority = P5OwnerAuthority(read_original=lambda ref: source['record'], read_ticket=lambda: source['ticket'],
        reviewed_record=record, reviewed_ticket=source['ticket'])
    authority.verify_original(record.reference)
    limits[0] = (limits[0][0], 999999)
    with pytest.raises(P5Stopped, match='OWNER_APPROVAL'):
        authority.verify_original(record.reference)


@pytest.mark.parametrize('order', [('keepa', 'bridge', 'shopee'), ('bridge', 'shopee', 'keepa')])
def test_credentials_are_service_lazy_in_both_orders(tmp_path, monkeypatch, order):
    scope = scope_for(tmp_path, bridge_spreadsheet_id='synthetic-sheet')
    initialize_p5_ledger(scope)
    credentials = P5ServiceCredentials(shopee=P5CredentialResolver(credential_reference(scope, tmp_path)),
        keepa=P5KeepaReference(scope.credential_ref, scope.marketplace, scope.shop_id, 'SYNTHETIC_KEEPA_KEY'))
    adapter, authority, observed, approval = trusted_adapter(scope)
    observed['credential'] = credentials.describe(scope, approval.operations)
    adapter.resolve_secrets = credentials
    authority.verify_original = lambda ref: replace(approval, observations_digest=_digest(observed))
    calls = []
    monkeypatch.setenv('SYNTHETIC_KEEPA_KEY', 'SYNTHETIC_ONLY')
    monkeypatch.setenv('OPENAI_API_KEY', 'UNUSED_SYNTHETIC')
    def shopee(*a, **k):
        calls.append('shopee')
        return secrets(SimpleNamespace(scope=scope)).shopee_credentials
    monkeypatch.setattr('modules.shopee_catalog_client.load_shopee_catalog_credentials', shopee)
    runtime = adapter.compose(scope, approval_reference='SYNTHETIC')
    runtime.start()
    assert not calls and not runtime._service_credentials
    try:
        for service in order:
            value = runtime.secrets(service)
            assert bool(value.keepa_key) == (service == 'keepa')
            assert bool(value.google_credential_file) == (service == 'bridge')
            assert bool(value.shopee_credentials) == (service == 'shopee')
            assert value.openai_key == ''
            if service == 'shopee':
                assert value.shopee_credentials.access_token == ''
        assert calls == ['shopee']
        for service in order:
            runtime.secrets(service)
        assert calls == ['shopee']
        runtime._bridge_token = 'SYNTHETIC_BRIDGE_TOKEN'
        assert runtime.secrets('shopee').shopee_credentials.access_token == 'SYNTHETIC_BRIDGE_TOKEN'
        assert runtime.secrets('keepa').keepa_key == 'SYNTHETIC_ONLY'
        assert not runtime.ledger.data['reservations']
    finally:
        runtime.close()
    assert not runtime._service_credentials


def test_unapproved_service_does_not_read_key_even_after_other_service(tmp_path, monkeypatch):
    # Use an explicit operation permit; no resolver is reached before guards.
    runtime = runtime_for(tmp_path)
    runtime.permit = replace(runtime.permit, operations=frozenset({'bridge', 'auth'}))
    calls = []
    runtime.credential_resolver = lambda service: calls.append(service) or secrets(runtime)
    try:
        runtime.secrets('bridge')
        for service in ('keepa', 'shopee', 'openai', 'unknown'):
            with pytest.raises(P5Stopped, match='OPERATION'):
                runtime.secrets(service)
        assert calls == ['bridge']
    finally:
        runtime.close()


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_actual_sdk_cold_trace_four_sends_and_112_reserved_tokens(tmp_path, market):
    from modules.candidate_filters import FilterCriteria
    from test_p5_candidates import QUERY, sdk
    runtime = runtime_for(tmp_path, market, asins=('B000000000',), preparation_limit=1,
        finder_queries=(json.dumps(QUERY),), keepa_requests=4, keepa_products=51, keepa_tokens=112)
    found = [f'B{n:09d}' for n in range(1, 51)]
    stats = [1000] + [-1] * 15 + [45]
    client, calls = sdk(runtime, found=found, stats=stats)
    assert not calls  # Keepa(check_key=False) construction has no hidden request
    try:
        result = client.find_related_products('B000000000', 1,
            filter_criteria=FilterCriteria(price_min_jpy=0, rating_min=4.0))
        assert len(result.rows) == 50
        assert [url.split('/')[-2] for url, _ in calls] == ['token', 'product', 'query', 'product']
        assert all(options['allow_redirects'] is False for _, options in calls)
        reservations = runtime.ledger.data['reservations']
        assert [r['tokens'] for r in reservations] == [0, 1, 11, 100]
        assert sum(r['units'] for r in reservations) == 51
        # Same cache action and new SDK share the finite ledger, no extra send.
        client.find_related_products('B000000000', 1,
            filter_criteria=FilterCriteria(price_min_jpy=0, rating_min=4.0))
        assert len(calls) == 4
        other, other_calls = sdk(runtime, found=found, stats=stats)
        cached = other.find_related_products('B000000000', 1,
            filter_criteria=FilterCriteria(price_min_jpy=0, rating_min=4.0))
        assert cached.cache_hit and not other_calls
        with pytest.raises((ValueError, RuntimeError)):
            other.api._request('token', {'key': 'SYNTHETIC_ONLY'}, wait=False)
        assert not other_calls and len(reservations) == 4
    finally:
        runtime.close()


def observer_fixture(tmp_path, monkeypatch):
    scope = scope_for(tmp_path, bridge_spreadsheet_id='synthetic-sheet')
    credentials = P5ServiceCredentials(shopee=P5CredentialResolver(credential_reference(scope, tmp_path)),
        keepa=P5KeepaReference(scope.credential_ref, scope.marketplace, scope.shop_id, 'SYNTHETIC_KEEPA_KEY'))
    setup = synthetic_setup()
    storage = SimpleNamespace(operator='SYNTHETIC_SID', setup=lambda: setup, inspect=setup.inspect)
    code = dict(release=scope.release, source_digest='SYNTHETIC_TREE', entrypoint='app_beta.py')
    process = dict(pid=os.getpid(), sid=storage.operator, started='SYNTHETIC_START', machine='SYNTHETIC_MACHINE',
        executable=sys.executable, command='SYNTHETIC_COMMAND',
        listeners=[dict(pid=os.getpid(), address='127.0.0.1', port=8511)])
    monkeypatch.setattr('modules.p5_windows._windows', lambda *a, **k: process)
    monkeypatch.setattr('modules.p5_windows._command_arguments', lambda command:
        ['python', '-m', 'streamlit', 'run', sys.modules['__main__'].__file__])
    monkeypatch.setattr(P5CodeIdentity, 'observe', lambda self: code)
    monkeypatch.setattr(P5CodeIdentity, '_require_loaded_source', lambda *a: None)
    observer = WindowsP5Observer(storage=storage, port=8511, credentials=credentials,
        operations=frozenset({'keepa.token'}), primary_sources={'keepa.token':
            dict(verified=True, body_digest='SYNTHETIC_SPEC', version='SYNTHETIC')},
        pricing={}, required_bytes=1000)
    return scope, observer, process, code


@pytest.mark.parametrize('change', ['pid', 'sid', 'started', 'machine', 'executable',
    'no-listener', 'wildcard', 'other-listener', 'port', 'entrypoint', 'storage', 'token-spec'])
def test_windows_observation_rejects_mismatches(tmp_path, monkeypatch, change):
    scope, observer, process, _ = observer_fixture(tmp_path, monkeypatch)
    if change in {'pid', 'sid', 'started', 'machine', 'executable'}:
        process[change] = {'pid': os.getpid() + 1, 'sid': 'OTHER', 'started': '',
            'machine': '', 'executable': str(tmp_path / 'other.exe')}[change]
    elif change == 'no-listener':
        process['listeners'] = []
    elif change in {'wildcard', 'other-listener', 'port'}:
        process['listeners'][0].update({'wildcard': {'address': '0.0.0.0'},
            'other-listener': {'pid': os.getpid()+1}, 'port': {'port': 8512}}[change])
    elif change == 'entrypoint':
        monkeypatch.setattr('modules.p5_windows._command_arguments', lambda command: ['python', 'run', 'other.py'])
    elif change == 'storage':
        observer.storage.setup().check = lambda *a, **k: (_ for _ in ()).throw(P5Stopped('P5_STORAGE_IDENTITY_ACL_UNVERIFIED'))
    else:
        observer.sources['keepa.token']['verified'] = False
    with pytest.raises(P5Stopped):
        observer.observe(scope)


def test_observation_binds_process_identity_not_ticket_label(tmp_path, monkeypatch):
    scope, observer, process, _ = observer_fixture(tmp_path, monkeypatch)
    first = observer.observe(scope)
    process['started'] = 'SYNTHETIC_NEW_START'
    second = observer.observe(scope)
    assert first['execution_target'] != scope.execution_target
    assert first['execution_target'] != second['execution_target']
    assert first['machine']['pid'] == os.getpid()


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_observation_can_recheck_inside_existing_p2_write_transaction(tmp_path, monkeypatch, market):
    from modules.beta_work_store import BetaWorkStore
    scope, observer, _, _ = observer_fixture(tmp_path, monkeypatch)
    if market == 'SG':
        scope = scope_for(tmp_path, market, bridge_spreadsheet_id='synthetic-sheet')
        observer.credentials = P5ServiceCredentials(
            shopee=P5CredentialResolver(credential_reference(scope, tmp_path)),
            keepa=P5KeepaReference(scope.credential_ref, scope.marketplace, scope.shop_id, 'SYNTHETIC_KEEPA_KEY'))
    store = BetaWorkStore(scope.db_path, marketplace=scope.marketplace, shop_id=scope.shop_id)
    history = store.history()
    with store.transaction() as conn:
        changes = conn.total_changes
        observed = observer.observe(scope)
        assert observed['storage']['store_id'] == store.store_id
        assert conn.total_changes == changes
    assert store.history() == history


@pytest.mark.parametrize('change', ['store_id', 'marketplace', 'shop_id', 'schema', 'missing'])
def test_observation_rejects_actual_store_identity_changes_without_repair(tmp_path, monkeypatch, change):
    import sqlite3
    scope, observer, _, _ = observer_fixture(tmp_path, monkeypatch)
    if change == 'missing':
        scope = replace(scope, run_id='synthetic-missing')
    else:
        with sqlite3.connect(scope.db_path) as conn:
            conn.execute('UPDATE meta SET value=? WHERE key=?', ('SYNTHETIC_CHANGED', change))
    with pytest.raises(P5Stopped, match='PROCESS_OBSERVATION_MISMATCH'):
        observer.observe(scope)
    assert scope.db_path.exists() is (change != 'missing')


def test_full_operator_composition_uses_original_os_references_and_real_checkpoint(tmp_path, monkeypatch):
    scope, observer, process, _ = observer_fixture(tmp_path, monkeypatch)
    scope = replace(scope, image_requests=0, openai_requests=0, openai_usd='0',
        execution_target=_digest({k: process[k] for k in ('machine', 'pid', 'started')} | {'port': 8511}))
    operations = frozenset({'keepa.token', 'keepa.product', 'keepa.query', 'shopee.category',
        'shopee.brand', 'bridge', 'auth', 'p2.save', 'output'})
    observer.operations = operations
    _, _, old_observed, approval = trusted_adapter(scope)
    observer.sources.update({k: old_observed['primary_sources'][k] for k in ('category', 'brand')})
    ticket = {'scope': scope.digest, 'operations': sorted(operations), 'version': 'SYNTHETIC'}
    approval = replace(approval, operations=operations, ticket_digest=_digest(ticket),
        observations_digest=_digest(observer.observe(scope)))
    record = OriginalOwnerRecord(approval.original_instruction_ref, approval.owner_ref,
        'SYNTHETIC reviewed original, never an actual production authorization', approval.approved_at, approval)
    source = {'record': record}
    authority = P5OwnerAuthority(read_original=lambda ref: source['record'], read_ticket=lambda: ticket,
        reviewed_record=record, reviewed_ticket=ticket)
    operator = P5Operator(authority=authority, observer=observer, credentials=observer.credentials,
        checkpoint=P5Checkpoint(observer.storage.setup(), required_bytes=1024**2), approval_reference=record.reference)
    initialize_p5_ledger(scope)
    monkeypatch.setenv('SYNTHETIC_KEEPA_KEY', 'SYNTHETIC_ONLY')
    runtime = operator.compose(scope)
    assert runtime.permit.offline_test is False  # production branch, synthetic observations only
    assert not runtime._service_credentials and runtime.ledger is None
    runtime.start()
    try:
        assert runtime.secrets('keepa').keepa_key == 'SYNTHETIC_ONLY'
        assert not runtime.secrets('bridge').keepa_key
        with pytest.raises(P5Stopped, match='OPERATION'):
            runtime.secrets('openai')
        with pytest.raises(P5Stopped, match='OPERATION'):
            runtime.require_operation('shopee.attribute')
        runtime.checkpoint('output')
        assert len(list((scope.directory / 'backups').glob('*/manifest.json'))) == 1
        source['record'] = replace(record, body='SYNTHETIC_CHANGED')
        with pytest.raises(P5Stopped, match='OWNER_APPROVAL'):
            runtime.require_current()
        source['record'] = record
    finally:
        runtime.close()
    assert len(list((scope.directory / 'backups').glob('*/manifest.json'))) == 2


def test_precreation_ignores_only_nonexistent_target_acl_then_requires_full_acl(tmp_path):
    setup = synthetic_setup()
    original = setup.inspect
    calls = []
    setup.inspect = lambda path: replace(original(path), acl_principals=frozenset({'Everyone'}),
        acl_inheritance_disabled=False) if not path.exists() else original(path)
    setup.set_acl = lambda path: calls.append(path)
    target = tmp_path / 'new' / 'shop'
    setup.create_new(target, required_bytes=1000)
    assert calls == [target.parent, target]
    assert target.is_dir()
    with pytest.raises(FileExistsError):
        setup.create_new(target, required_bytes=1000)
    setup.inspect = lambda path: replace(original(path), acl_principals=frozenset({'Everyone'}))
    blocked = tmp_path / 'blocked'
    with pytest.raises(P5Stopped, match='ACL_UNVERIFIED'):
        setup.create_new(blocked, required_bytes=1000)
    assert blocked.is_dir() and not list(blocked.iterdir())


@pytest.mark.parametrize('change,value', [('volume','OTHER'), ('ancestors_unaliased',False),
    ('isolated',False), ('identities',()), ('free_bytes',0)])
def test_precreation_never_relaxes_identity_and_capacity(tmp_path, change, value):
    setup = synthetic_setup()
    original = setup.inspect
    setup.inspect = lambda path: replace(original(path), **{change: value})
    setup.set_acl = lambda path: pytest.fail('ACL mutation before preflight')
    target = tmp_path / 'blocked'
    with pytest.raises(P5Stopped):
        setup.create_new(target, required_bytes=1000)
    assert not target.exists()


def test_unapproved_missing_parent_is_rejected_before_any_creation(tmp_path):
    setup = synthetic_setup()
    original = setup.inspect
    parent = tmp_path / 'outside-approved-install-root'
    target = parent / 'shop'
    def inspect(path):
        if path == parent:
            raise P5Stopped('P5_STORAGE_PATH_REFUSED')
        return original(path)
    setup.inspect = inspect
    with pytest.raises(P5Stopped, match='PATH_REFUSED'):
        setup.create_new(target, required_bytes=1000)
    assert not parent.exists()


@pytest.mark.parametrize('reason', ['output', 'session-end'])
def test_checkpoint_failure_stops_without_releasing_unknown(tmp_path, reason):
    runtime = runtime_for(tmp_path)
    reservation = runtime.ledger.reserve('auth')
    runtime.ledger.finish(reservation, success=False)
    before = json.loads(runtime.ledger.path.read_text())['reservations']
    runtime.checkpoint_hook = lambda *a: (_ for _ in ()).throw(OSError('SYNTHETIC_FAILURE'))
    with pytest.raises(P5Stopped, match='CHECKPOINT_FAILED'):
        runtime.checkpoint(reason)
    saved = json.loads(runtime.ledger.path.read_text())
    assert saved['stopped'] and saved['reservations'] == before
    runtime.checkpoint_hook = None
    runtime.close()


def test_missing_production_checkpoint_closes_output(tmp_path):
    runtime = runtime_for(tmp_path)
    runtime.permit = replace(runtime.permit, offline_test=False)
    runtime.authorization_guard = lambda op=None: None
    with pytest.raises(P5Stopped, match='CHECKPOINT_FAILED'):
        runtime.checkpoint('output')
    assert runtime.ledger.data['stopped']
    runtime.authorization_guard = None
    runtime.close()


def test_partial_backup_failure_keeps_files_claim_history_and_stops_output(tmp_path, monkeypatch):
    runtime = runtime_for(tmp_path)
    reservation = runtime.ledger.reserve('auth')
    runtime.ledger.finish(reservation, success=True)
    before = list(runtime.ledger.data['reservations'])
    claim = (runtime.scope.directory / 'claim.json').read_bytes()
    history = runtime.workflow.bench.store.history()
    runtime.checkpoint_hook = P5Checkpoint(synthetic_setup(), required_bytes=1024**2)
    monkeypatch.setattr('modules.p5_setup._write_new', lambda *a: (_ for _ in ()).throw(OSError('SYNTHETIC_MANIFEST_FAILURE')))
    try:
        with pytest.raises(P5Stopped, match='CHECKPOINT_FAILED'):
            runtime.workflow.bench.output({}, operational=True)
        partial = list((runtime.scope.directory / 'backups').iterdir())
        assert len(partial) == 1 and not (partial[0] / 'manifest.json').exists()
        assert {p.name for p in partial[0].iterdir()} == {'work.sqlite3', 'keepa.sqlite3', 'ledger.json', 'claim.json'}
        assert runtime.ledger.data['stopped'] and runtime.ledger.data['reservations'] == before
        assert (runtime.scope.directory / 'claim.json').read_bytes() == claim
        assert runtime.workflow.bench.store.history() == history
        with pytest.raises(P5Stopped):
            runtime.require_current()
    finally:
        runtime.checkpoint_hook = None
        runtime.close()


def test_configured_runtime_and_windows_constructors_are_inert(tmp_path, monkeypatch):
    scope = scope_for(tmp_path)
    before = set(tmp_path.rglob('*'))
    monkeypatch.setattr('modules.p5_windows._windows', lambda *a, **k: pytest.fail('OS I/O before explicit start'))
    storage = WindowsStorage(installation_root='D:/SYNTHETIC', protected_paths=(tmp_path,),
        operator_sid='SYNTHETIC', expected_volume='SYNTHETIC')
    P5Checkpoint(storage.setup(), required_bytes=1000)
    pending = configured_runtime(scope)
    assert pending.runtime.permit is None and not pending.can_request_start()
    with pytest.raises(P5Stopped):
        pending.start()
    assert set(tmp_path.rglob('*')) == before


def test_windows_storage_maps_readonly_metadata_without_secret_or_acl_io(tmp_path, monkeypatch):
    from modules.p5_setup import GiB
    storage = WindowsStorage(installation_root=tmp_path, protected_paths=(tmp_path / 'protected',),
        operator_sid='SYNTHETIC_SID', expected_volume='SYNTHETIC_VOLUME')
    monkeypatch.setattr(storage, '_paths', lambda path: (path.resolve(), ((1, 101),)))
    (tmp_path / 'synthetic.txt').write_bytes(b'SYNTHETIC')
    calls = []
    def read(action, **kwargs):
        assert action == 'Storage'  # never SetAcl or Process during storage inspection
        calls.append(action)
        return dict(volume='SYNTHETIC_VOLUME', filesystem='NTFS', fixed=True, unaliased=True,
            principals=['SYNTHETIC_SID', 'SYSTEM', 'Administrators'], acl_valid=True,
            inheritance_disabled=True, free_bytes=40*GiB, c_free_bytes=4*GiB)
    monkeypatch.setattr('modules.p5_windows._windows', read)
    monkeypatch.setattr(Path, 'open', lambda *a, **k: pytest.fail('inspection opened a file body'))
    observed = storage.inspect(tmp_path)
    assert observed.run_bytes == len(b'SYNTHETIC') and observed.identities == ((1, 101),)
    assert storage.setup().check(tmp_path)['warning'] is False
    assert calls == ['Storage', 'Storage']


def test_windows_storage_rejects_incomplete_os_metadata_without_mutation(tmp_path, monkeypatch):
    storage = WindowsStorage(installation_root=tmp_path, protected_paths=(tmp_path / 'protected',),
        operator_sid='SYNTHETIC_SID', expected_volume='SYNTHETIC_VOLUME')
    monkeypatch.setattr(storage, '_paths', lambda path: (path.resolve(), ((1, 101),)))
    monkeypatch.setattr('modules.p5_windows._windows', lambda action, **kwargs: {'volume': 'SYNTHETIC_VOLUME'})
    with pytest.raises(P5Stopped, match='STORAGE_IDENTITY_ACL_UNVERIFIED'):
        storage.inspect(tmp_path)
    assert not list(tmp_path.iterdir())


def pending_entry(runtime):
    from app_beta import render_beta
    render_beta(p5_runtimes={runtime.scope.marketplace: runtime})


def test_pending_operator_composes_only_at_start_and_rerenders_do_not_send(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    runtime = runtime_for(tmp_path)
    runtime.close()
    calls = []
    operator = object.__new__(P5Operator)
    monkeypatch.setattr(P5Operator, 'compose', lambda self, scope: calls.append('compose') or runtime)
    pending = PendingP5Runtime(runtime.scope, operator)
    monkeypatch.setattr('app_beta.render_application', lambda *a, **k: None)
    app = AppTest.from_function(pending_entry, args=(pending,), default_timeout=30).run()
    app.run()
    assert not app.exception and not calls and pending.runtime.permit is None
    assert not app.button(key='p5_start').disabled
    app.button(key='p5_start').click().run()
    app.run()
    assert not app.exception and calls == ['compose']
    assert not runtime.ledger.data['reservations']
    runtime.close()
