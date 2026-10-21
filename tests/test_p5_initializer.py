"""Synthetic records/OS plus real app_beta script; no live authorization proof."""
from dataclasses import asdict, replace
from datetime import timedelta
import importlib
import json
from pathlib import Path
import sys

import pytest
from streamlit.testing.v1 import AppTest

from modules import p5_initializer, p5_operator
from modules.p5_initializer import initialize_and_run
from modules.p5_operator import (OriginalOwnerRecord, P5OwnerAuthority,
    P5Checkpoint, P5Operator, configured_runtime, register_operator)
from modules.p5_live_adapter import P5CodeIdentity, P5ServiceCredentials, P5KeepaReference
from modules.p5_runtime import P5Stopped, initialize_p5_ledger
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


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_real_script_config_alone_and_import_cannot_authorize(tmp_path, monkeypatch, market):
    scope = scope_for(tmp_path, market)
    config = scope_file(tmp_path, scope)
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    block_secrets(monkeypatch)
    importlib.reload(p5_initializer)
    monkeypatch.setenv('P5_OPERATOR', 'APPROVED')
    monkeypatch.setenv('P5_INITIALIZER', 'APPROVED')
    monkeypatch.setattr(sys, 'argv', ['app_beta.py', '--p5-config', str(config), '--APPROVED'])
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app_beta.py', default_timeout=30).run()
    app.selectbox(key='beta_marketplace').select(market).run()
    app.run()
    assert not app.exception and app.button(key='p5_start').disabled
    pending = app.session_state['p5_runtime']
    with pytest.raises(P5Stopped, match='P5_TRUSTED_OPERATOR_REQUIRED'):
        pending.start()
    assert pending.runtime.permit is None
    assert p5_operator._installed_operator is None
    assert before == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


@pytest.mark.parametrize('bad', [None, 'APPROVED', {'APPROVED': True}, lambda: None, object(),
    object.__new__(type('SyntheticSubclass', (P5Operator,), {}))])
def test_registration_rejects_untyped_values(bad):
    with pytest.raises(P5Stopped, match='P5_TRUSTED_OPERATOR_REQUIRED'):
        register_operator(bad)
    assert p5_operator._installed_operator is None


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_initializer_to_actual_entrypoint_start_and_rerun(tmp_path, monkeypatch, market):
    scope, values, source, code = components(tmp_path, monkeypatch, market)
    initialize_p5_ledger(scope)  # synthetic installation is a separate test step
    config = scope_file(tmp_path, scope)
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    block_secrets(monkeypatch)
    shutdown = []
    def render(*a, **kwargs):
        if shutdown:
            kwargs['p5_runtime'].close()
    monkeypatch.setattr('app.render_application', render)
    entry = Path(__file__).resolve().parents[1] / 'app_beta.py'
    monkeypatch.setattr('modules.p5_windows._command_arguments',
        lambda command: ['python', 'synthetic_trusted_process.py', 'run', str(entry)])
    # _windows/_command_arguments are synthetic OS seams; all other code,
    # including the new initializer and actual entrypoint, is checked directly.
    monkeypatch.setattr(P5CodeIdentity, '_require_loaded_source',
        lambda module, path: None if module.__name__ == 'modules.p5_windows'
        else LOADED_SOURCE_CHECK(module, path))
    def observe_code(self):
        main = sys.modules['__main__']
        assert Path(main.__file__).resolve() == entry
        LOADED_SOURCE_CHECK(main, entry)
        return code
    monkeypatch.setattr(P5CodeIdentity, 'observe', observe_code)
    from streamlit.web import bootstrap
    launches = []
    def run(entrypoint, is_hello, args, flags):
        launches.append(entrypoint)
        assert Path(entrypoint).name == 'app_beta.py' and not is_hello
        assert flags['server_address'] == '127.0.0.1' and flags['server_port'] == 8511
        assert type(p5_operator._installed_operator) is P5Operator
        monkeypatch.setattr(sys, 'argv', [entrypoint, *args])
        app = AppTest.from_file(entrypoint, default_timeout=30).run()
        app.selectbox(key='beta_marketplace').select(market).run()
        installed = p5_operator._installed_operator
        app.selectbox(key='beta_marketplace').select('SG' if market == 'PH' else 'PH').run()
        assert not app.exception and not app.button
        app.selectbox(key='beta_marketplace').select(market).run()
        assert p5_operator._installed_operator is installed
        pending = app.session_state['p5_runtime']
        app.run()
        assert not app.exception and pending.runtime.permit is None
        assert before == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
        app.button(key='p5_start').click().run()
        assert not app.exception and not app.error
        active = app.session_state['p5_runtime']
        assert active is pending and active.runtime.permit is not None
        assert active.workflow is not None and not active.ledger.data['reservations']
        app.run()
        assert app.session_state['p5_runtime'] is active and not app.error
        assert not active.runtime._service_credentials and not active.ledger.data['reservations']
        # Revocation is rechecked after registration and successful start.
        original = source['record']
        source['record'] = replace(original, approval=replace(original.approval, revoked=True))
        app.run()
        assert app.error and not app.exception
        source['record'] = original
        shutdown.append(True)
        app.run()  # close/checkpoint while the real app_beta entrypoint is active
        assert not app.error and not app.exception and active.ledger is None
        assert len(list((scope.directory / 'backups').glob('*/manifest.json'))) == 1
    monkeypatch.setattr(bootstrap, 'run', run)  # only server/socket boundary replaced
    initialize_and_run(**values, scope_config=config)
    assert len(launches) == 1


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
