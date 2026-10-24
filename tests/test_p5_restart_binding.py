
"""Restart compatibility with synthetic stores, authorities and OS observations only."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from modules.beta_work_store import BetaWorkStore
from modules.p5_runtime import P5Stopped, initialize_p5_ledger
from modules.p5_windows import (EXECUTION_PROFILE_PREFIX, execution_profile_target,
    plan_execution_target)
from modules.sg_continuous_runtime import _digest
from test_p5_composition import observer_fixture
from test_p5_runtime import scope_for, forbid_network


def profile(tmp_path, **changes):
    values = dict(machine='SYNTHETIC_HOST', operator_sid='SYNTHETIC_SID',
        interpreter=sys.executable, host_interpreter=sys.executable,
        entrypoint=str(tmp_path / 'app_beta.py'), port=8515)
    values.update(changes)
    return execution_profile_target(**values)


@pytest.mark.parametrize('field,value', [
    ('machine', ''), ('operator_sid', ''), ('interpreter', 'relative.exe'),
    ('host_interpreter', 'relative.exe'), ('entrypoint', 'app_beta.py'), ('entrypoint', '/other.py'),
    ('port', 0), ('port', 65536), ('port', True)])
def test_profile_rejects_incomplete_or_invalid_installation_target(tmp_path, field, value):
    with pytest.raises(P5Stopped, match='PROFILE_INVALID'):
        profile(tmp_path, **{field: value})


@pytest.mark.parametrize('field,value', [
    ('machine', 'OTHER_HOST'), ('operator_sid', 'OTHER_SID'),
    ('interpreter', 'other-interpreter'), ('host_interpreter', 'other-host'), ('entrypoint', 'other-code'), ('port', 8516)])
def test_profile_pins_every_stable_execution_boundary(tmp_path, field, value):
    if field in {'interpreter', 'host_interpreter'}:
        value = str(tmp_path / 'other-python.exe')
    elif field == 'entrypoint':
        value = str(tmp_path / 'other-release' / 'app_beta.py')
    assert profile(tmp_path) != profile(tmp_path, **{field: value})


def test_profile_can_be_planned_before_store_or_listener_exists(tmp_path, monkeypatch):
    calls = []
    def host(action, **kwargs):
        calls.append((action, kwargs))
        return dict(machine='SYNTHETIC_HOST', sid='SYNTHETIC_SID', executable=sys.executable)
    monkeypatch.setattr('modules.p5_windows._windows', host)
    result = plan_execution_target(operator_sid='SYNTHETIC_SID',
        interpreter=sys.executable, entrypoint=str(tmp_path / 'app_beta.py'), port=8515)
    assert result == profile(tmp_path)
    assert calls == [('Host', {})]
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr('modules.p5_windows._windows',
        lambda *a, **k: dict(machine='SYNTHETIC_HOST', sid='OTHER_SID', executable=sys.executable))
    with pytest.raises(P5Stopped, match='PROFILE_UNVERIFIED'):
        plan_execution_target(operator_sid='SYNTHETIC_SID',
            interpreter=sys.executable, entrypoint=str(tmp_path / 'app_beta.py'), port=8515)


def profile_observer(tmp_path, monkeypatch):
    scope, observer, process, code = observer_fixture(tmp_path, monkeypatch)
    entrypoint = str(tmp_path / 'app_beta.py')
    monkeypatch.setattr(sys.modules['__main__'], '__file__', entrypoint)
    scope = replace(scope, execution_target=execution_profile_target(machine=process['machine'],
        operator_sid=process['sid'], interpreter=sys.executable,
        host_interpreter=process['executable'], entrypoint=entrypoint,
        port=observer.port))
    return scope, observer, process, code


def test_profile_keeps_scope_stable_but_stales_old_process_review(tmp_path, monkeypatch):
    scope, observer, process, _ = profile_observer(tmp_path, monkeypatch)
    first = observer.observe(scope)
    process['started'] = 'SYNTHETIC_NEXT_PROCESS_START'
    second = observer.observe(scope)
    assert first['execution_target'] == second['execution_target'] == scope.execution_target
    assert _digest(first) != _digest(second)
    assert first['machine'] != second['machine']
    assert asdict(scope) == second['plan']


@pytest.mark.parametrize('change', ['machine', 'sid', 'executable', 'entrypoint', 'port', 'pid',
    'no-listener', 'wildcard', 'other-listener', 'empty-start'])
def test_profile_mode_preserves_actual_os_and_code_target_guards(tmp_path, monkeypatch, change):
    scope, observer, process, _ = profile_observer(tmp_path, monkeypatch)
    if change == 'entrypoint':
        monkeypatch.setattr(sys.modules['__main__'], '__file__', str(tmp_path / 'elsewhere' / 'app_beta.py'))
    elif change == 'port':
        observer.port = 8516
        process['listeners'][0]['port'] = 8516
    elif change == 'pid':
        process['pid'] += 1
    elif change == 'no-listener':
        process['listeners'] = []
    elif change == 'wildcard':
        process['listeners'][0]['address'] = '0.0.0.0'
    elif change == 'other-listener':
        process['listeners'][0]['pid'] += 1
    elif change == 'empty-start':
        process['started'] = ''
    else:
        process[change] = {'machine': 'OTHER_HOST', 'sid': 'OTHER_SID',
            'executable': str(tmp_path / 'other-python.exe')}[change]
    with pytest.raises(P5Stopped):
        observer.observe(scope)


def test_unknown_profile_version_is_not_a_legacy_fallback(tmp_path, monkeypatch):
    scope, observer, _, _ = profile_observer(tmp_path, monkeypatch)
    with pytest.raises(P5Stopped, match='PROFILE_UNSUPPORTED'):
        observer.observe(replace(scope, execution_target='p5-profile-v99:' + '0' * 64))


def test_profile_pins_venv_entry_and_distinct_os_python_image(tmp_path, monkeypatch):
    scope, observer, process, _ = profile_observer(tmp_path, monkeypatch)
    process['executable'] = str(tmp_path / 'base-python.exe')
    scope = replace(scope, execution_target=execution_profile_target(machine=process['machine'],
        operator_sid=process['sid'], interpreter=sys.executable,
        host_interpreter=process['executable'], entrypoint=str(tmp_path / 'app_beta.py'),
        port=observer.port))
    assert observer.observe(scope)['execution_target'] == scope.execution_target
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'other-venv-python.exe'))
    with pytest.raises(P5Stopped, match='PROFILE_MISMATCH'):
        observer.observe(scope)


def test_planning_refuses_a_different_interpreter_than_the_running_venv(tmp_path, monkeypatch):
    monkeypatch.setattr('modules.p5_windows._windows',
        lambda *a, **k: dict(machine='SYNTHETIC_HOST', sid='SYNTHETIC_SID',
            executable=str(tmp_path / 'base-python.exe')))
    with pytest.raises(P5Stopped, match='PROFILE_UNVERIFIED'):
        plan_execution_target(operator_sid='SYNTHETIC_SID',
            interpreter=str(tmp_path / 'other-venv.exe'),
            entrypoint=str(tmp_path / 'app_beta.py'), port=8515)
    assert list(tmp_path.iterdir()) == []


# Actual separate Python processes use the real P5 runtime, store, authority and
# ledger. OS/code observations and original Owner evidence are SYNTHETIC. No
# Streamlit listener, secret source, live transport, migration or setup is used.
CHILD = r'''
import json, os, pathlib, socket, sys, urllib.request
from datetime import datetime, timezone
from dataclasses import replace
import pytest
root, tests, plan_path, action = sys.argv[1:]
sys.path[:0] = [root, tests]
from modules.p5_runtime import P5Scope, initialize_p5_ledger, P5Stopped
from modules.p5_windows import WindowsP5Observer
from modules.p5_live_adapter import P5CodeIdentity, P5ServiceCredentials, P5CredentialResolver, P5KeepaReference
from modules.p5_operator import OriginalOwnerRecord, P5OwnerAuthority, P5Operator, P5Checkpoint
from modules.sg_continuous_runtime import _digest
from test_p5_runtime import trusted_adapter, synthetic_setup
from test_p5_production_connection import credential_reference
import requests

def deny(*a, **k):
    raise AssertionError('SYNTHETIC_RESTART_NETWORK_OR_SECRET_REFUSED')
requests.sessions.Session.request = deny
urllib.request.OpenerDirector.open = deny
socket.socket.connect = deny
socket.socket.bind = deny
socket.getaddrinfo = deny
values = json.loads(pathlib.Path(plan_path).read_text())
for key in ('asins', 'category_ids', 'finder_queries', 'openai_models', 'resolver_inputs'):
    values[key] = tuple(values[key])
scope = P5Scope(**values)
credentials = P5ServiceCredentials(
    shopee=P5CredentialResolver(credential_reference(scope, pathlib.Path(plan_path).parent)),
    keepa=P5KeepaReference(scope.credential_ref, scope.marketplace, scope.shop_id, 'SYNTHETIC_NO_KEY'))
setup = synthetic_setup()
from types import SimpleNamespace
storage = SimpleNamespace(operator='SYNTHETIC_SID', setup=lambda: setup, inspect=setup.inspect)
process = dict(pid=os.getpid(), started=datetime.now(timezone.utc).isoformat(),
    machine='SYNTHETIC_HOST', sid='SYNTHETIC_SID', executable=sys.executable,
    command='SYNTHETIC_COMMAND', listeners=[dict(pid=os.getpid(), address='127.0.0.1', port=8515)])
import modules.p5_windows as windows
windows._windows = lambda *a, **k: process
windows._command_arguments = lambda command: ['python', 'run', __file__]
P5CodeIdentity.observe = lambda self: dict(release=scope.release,
    source_digest='SYNTHETIC_SOURCE', entrypoint='app_beta.py')
P5CodeIdentity._require_loaded_source = staticmethod(lambda *a: None)
operations = frozenset({'keepa.token'})
observer = WindowsP5Observer(storage=storage, port=8515, credentials=credentials,
    operations=operations, primary_sources={'keepa.token':dict(verified=True,
        body_digest='SYNTHETIC_SPEC', version='SYNTHETIC')}, pricing={}, required_bytes=1000)
_, _, _, approval = trusted_adapter(scope)
ticket = dict(scope=scope.digest, operations=sorted(operations), version='SYNTHETIC_ONLY')
approval = replace(approval, operations=operations, ticket_digest=_digest(ticket),
    observations_digest=_digest(observer.observe(scope)))
record = OriginalOwnerRecord(approval.original_instruction_ref, approval.owner_ref,
    'SYNTHETIC original instruction; not actual Owner authority', approval.approved_at, approval)
authority = P5OwnerAuthority(read_original=lambda ref:record, read_ticket=lambda:ticket,
    reviewed_record=record, reviewed_ticket=ticket)
operator = P5Operator(authority=authority, observer=observer, credentials=credentials,
    checkpoint=P5Checkpoint(setup, required_bytes=1024**2), approval_reference=record.reference)
runtime = operator.compose(scope)
try:
    runtime.start()
except P5Stopped as exc:
    if str(exc) != 'P5_UNRESOLVED_CONSUMPTION':
        raise
    print(json.dumps(dict(result='BLOCKED_UNKNOWN', machine=process['pid'],
        scope=scope.digest, observed_digest=approval.observations_digest)))
else:
    if action in {'consume', 'unknown'}:
        rid = runtime.ledger.reserve('keepa')
        runtime.ledger.finish(rid, success=action == 'consume')
    print(json.dumps(dict(result='STARTED', pid=os.getpid(), scope=scope.digest,
        observed_digest=approval.observations_digest, ledger=runtime.ledger.data,
        history=runtime._store.history(), products=runtime._store.products())))
# Deliberate process termination releases the actual OS lease. Do not run a
# session-end backup in this process-death/restart fixture.
'''


@pytest.mark.parametrize('market', ['PH', 'SG'])
@pytest.mark.parametrize('first_action', ['consume', 'unknown'])
def test_two_real_processes_keep_same_store_budget_history_and_unknown_stop(tmp_path, market, first_action):
    child = tmp_path / 'app_beta.py'
    child.write_text(CHILD, encoding='utf-8')
    target = profile(tmp_path)
    scope = scope_for(tmp_path, market, bridge_spreadsheet_id='synthetic-sheet',
        execution_target=target, preparation_limit=2, keepa_requests=2, keepa_products=0,
        keepa_tokens=0, shopee_requests=0, bridge_requests=0, auth_requests=0,
        image_requests=0, openai_requests=0, openai_usd='0', openai_models=(),
        openai_input_bound=0, openai_output_tokens=0, openai_images=0)
    initialize_p5_ledger(scope, material_updates=True)
    store = BetaWorkStore(scope.db_path, marketplace=market, shop_id=scope.shop_id)
    with store.transaction() as conn:
        store.write(conn, dict(asin='B000000001', marketplace=market, shop_id=scope.shop_id,
            state='WAITING', fixture='SYNTHETIC_RESTART_HISTORY'),
            action='SYNTHETIC_INTAKE', expected_revision=0)
    expected_history, expected_products = store.history(), store.products()
    plan = tmp_path / 'synthetic-plan.json'
    plan.write_text(json.dumps(asdict(scope)), encoding='utf-8')
    repository = Path(__file__).resolve().parents[1]
    # No inherited application API/credential variables are passed to a child.
    env = {k: v for k, v in os.environ.items() if k.upper() in
        {'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP', 'COMSPEC', 'PATHEXT'}}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHON_DOTENV_DISABLED='1')
    def run(action):
        result = subprocess.run([sys.executable, '-B', '-I', str(child), str(repository),
            str(repository / 'tests'), str(plan), action],
            env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout.strip())
    first = run(first_action)
    assert first['result'] == 'STARTED'
    baseline = {name:(scope.directory / name).read_bytes()
        for name in ('work.sqlite3', 'keepa.sqlite3', 'ledger.json', 'claim.json')}
    second = run('resume')
    assert second['scope'] == first['scope'] == scope.digest
    assert second['observed_digest'] != first['observed_digest']
    assert second['result'] == ('STARTED' if first_action == 'consume' else 'BLOCKED_UNKNOWN')
    assert baseline == {name:(scope.directory / name).read_bytes() for name in baseline}
    assert store.history() == expected_history
    assert store.products() == expected_products
    ledger = json.loads(baseline['ledger.json'])
    assert len(ledger['reservations']) == 1
    assert ledger['reservations'][0]['state'] == ('COMPLETE' if first_action == 'consume' else 'UNKNOWN')
    assert ledger['material_updates'] == {'version':1, 'intents':[]}
    assert set(ledger['candidates']) == {'requests','finder','proposals','batches','selections'}




def test_previous_process_approval_is_rejected_even_with_same_profile(tmp_path, monkeypatch):
    from modules.p5_live_adapter import P5CodeIdentity
    from test_p5_runtime import trusted_adapter
    scope, observer, process, _ = profile_observer(tmp_path, monkeypatch)
    scope = replace(scope, keepa_requests=2, keepa_products=0, keepa_tokens=0,
        shopee_requests=0, bridge_requests=0, auth_requests=0, image_requests=0,
        openai_requests=0, openai_usd='0', openai_models=(), openai_input_bound=0,
        openai_output_tokens=0, openai_images=0)
    adapter, authority, _, approval = trusted_adapter(scope)
    adapter.synthetic = False
    adapter.code_identity = P5CodeIdentity()
    adapter.observe = observer.observe
    adapter.resolve_secrets = observer.credentials
    approval = replace(approval, operations=frozenset({'keepa.token'}),
        observations_digest=_digest(observer.observe(scope)))
    authority.verify_original = lambda ref: approval
    adapter._check(scope, 'SYNTHETIC_ONLY')
    process['started'] = 'SYNTHETIC_NEW_PROCESS'
    with pytest.raises(P5Stopped, match='EXECUTION_OBSERVATION_MISMATCH'):
        adapter.compose(scope, approval_reference='SYNTHETIC_ONLY')


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows read-only Host action')
def test_native_profile_planning_needs_no_store_or_application_listener(tmp_path):
    from modules.p5_windows import _windows
    # Host metadata only: no keys, tokens, user credential source or App access.
    host = _windows('Host')
    target = plan_execution_target(operator_sid=host['sid'], interpreter=sys.executable,
        entrypoint=str(tmp_path / 'app_beta.py'), port=8515)
    assert target == execution_profile_target(machine=host['machine'], operator_sid=host['sid'],
        interpreter=sys.executable, host_interpreter=host['executable'], entrypoint=str(tmp_path / 'app_beta.py'), port=8515)
    assert target.startswith(EXECUTION_PROFILE_PREFIX)
    assert list(tmp_path.iterdir()) == []
