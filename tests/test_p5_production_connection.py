"""Synthetic authority/files/HTTP only. No production approval or live proof."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from modules.p5_live_adapter import P5CodeIdentity, P5CredentialReference, P5CredentialResolver
from modules.p5_runtime import P5Stopped, initialize_p5_ledger
from modules.p5_transport import P5BridgeTransport, P5HTTP
from modules.sg_continuous_runtime import _digest
from test_p5_runtime import (scope_for, runtime_for, trusted_adapter, secrets,
                             forbid_network)


@pytest.mark.parametrize('factory,key', [('make_keepa_client', 'keepa_key'),
    ('make_image_inspector', 'openai_key'), ('make_category_provider', 'openai_key')])
def test_unconnected_paid_credential_references_stop_before_client_or_send(tmp_path, monkeypatch, factory, key):
    from modules import p5_transport
    rt = runtime_for(tmp_path)
    monkeypatch.setattr('requests.Session', lambda: pytest.fail('client constructed without approved key'))
    try:
        with pytest.raises(P5Stopped, match='CREDENTIAL_REQUIRED'):
            getattr(p5_transport, factory)(rt, replace(secrets(rt), **{key: ''}))
        assert not rt.ledger.data['reservations']
    finally:
        rt.close()


def credential_reference(scope, tmp_path):
    return P5CredentialReference(scope.credential_ref, scope.marketplace, scope.shop_id,
        str(tmp_path / 'synthetic-audit.env'), str(tmp_path / 'synthetic-google.json'),
        scope.bridge_spreadsheet_id)


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_reference_is_lazy_bound_and_uses_existing_reader_without_legacy_token(tmp_path, monkeypatch, market):
    scope = scope_for(tmp_path, market, bridge_spreadsheet_id='synthetic-sheet')
    initialize_p5_ledger(scope)
    reference = credential_reference(scope, tmp_path)
    resolver = P5CredentialResolver(reference)
    calls = []
    from modules.shopee_catalog_client import load_shopee_catalog_credentials
    def read(*args, **kwargs):
        calls.append((args, kwargs))
        return load_shopee_catalog_credentials(*args, **kwargs)
    monkeypatch.setattr('modules.shopee_catalog_client.load_shopee_catalog_credentials', read)
    adapter, authority, _, approval = trusted_adapter(scope)
    adapter.resolve_secrets = resolver
    authority.verify_original = lambda ref: None
    with pytest.raises(P5Stopped, match='OWNER_APPROVAL'):
        adapter.compose(scope, approval_reference='SYNTHETIC')
    assert not calls
    authority.verify_original = lambda ref: approval
    runtime = adapter.compose(scope, approval_reference='SYNTHETIC')
    runtime.start()
    runtime.start()  # rerender/repeated start does not resolve credentials
    assert not calls and not runtime.ledger.data['reservations']
    Path(reference.audit_env).write_text(
        f'SHOPEE_PARTNER_ID=1\nSHOPEE_PARTNER_KEY=SYNTHETIC_ONLY\n'
        f'SHOPEE_{market}_SHOP_ID=22\nSHOPEE_{market}_ACCESS_TOKEN=SYNTHETIC_LEGACY\n',
        encoding='utf-8')
    try:
        resolved = runtime.secrets()
        assert resolved.shopee_credentials.shop_id == 22
        assert resolved.shopee_credentials.access_token == ''
        assert resolved.google_credential_file == reference.google_credential_file
        assert len(calls) == 1
        assert calls[0][1] == dict(marketplace=market, require_access_token=False)
        assert 'SYNTHETIC_LEGACY' not in repr(resolved)
        authority.verify_original = lambda ref: replace(approval, revoked=True)
        with pytest.raises(P5Stopped, match='OWNER_APPROVAL'):
            runtime.secrets()  # cached credentials do not bypass current approval
    finally:
        runtime.close()


@pytest.mark.parametrize('field,value', [('reference', 'other'), ('marketplace', 'SG'),
    ('shop_id', '99'), ('audit_env', ''), ('google_credential_file', 'relative.json'),
    ('bridge_spreadsheet_id', 'other')])
def test_reference_mismatch_fails_before_secret_read(tmp_path, monkeypatch, field, value):
    scope = scope_for(tmp_path, bridge_spreadsheet_id='synthetic-sheet')
    reference = replace(credential_reference(scope, tmp_path), **{field: value})
    monkeypatch.setattr('modules.shopee_catalog_client.load_shopee_catalog_credentials',
                        lambda *a, **k: pytest.fail('secret read before reference validation'))
    with pytest.raises(P5Stopped, match='CREDENTIAL_REFERENCE'):
        P5CredentialResolver(reference)(scope)


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_resolved_underlying_shop_and_missing_reference_stop(tmp_path, monkeypatch, market):
    rt = runtime_for(tmp_path, market)
    try:
        rt._credentials = replace(secrets(rt), shopee_credentials=replace(
            secrets(rt).shopee_credentials, shop_id=99))
        with pytest.raises(P5Stopped, match='CREDENTIAL_ADAPTER'):
            rt.secrets()
        with pytest.raises(P5Stopped, match='CREDENTIAL_REFERENCE'):
            P5CredentialResolver(None)(rt.scope)
        reference = credential_reference(replace(rt.scope, bridge_spreadsheet_id='synthetic'), tmp_path)
        monkeypatch.setattr('modules.shopee_catalog_client.load_shopee_catalog_credentials',
            lambda *a, **k: rt._credentials.shopee_credentials)
        with pytest.raises(P5Stopped, match='RESOLUTION_STOPPED'):
            P5CredentialResolver(reference)(replace(rt.scope, bridge_spreadsheet_id='synthetic'))
    finally:
        rt.close()


def code_checkout(tmp_path, monkeypatch):
    root = tmp_path / 'synthetic-code'
    (root / 'modules').mkdir(parents=True)
    entry = root / 'app_beta.py'
    entry.write_text('# Synthetic entrypoint\n')
    for name in ('p5_live_adapter', 'p5_runtime', 'p5_transport', 'shopee_catalog_client'):
        path = root / 'modules' / (name + '.py')
        path.write_bytes(Path(sys.modules['modules.' + name].__file__).read_bytes())
        monkeypatch.setattr(sys.modules['modules.' + name], '__file__', str(path))
    monkeypatch.setattr(sys.modules['__main__'], '__file__', str(entry))
    def git(*args):
        return subprocess.run(['git', '-C', str(root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()
    git('init', '-b', 'main')
    git('remote', 'add', 'origin', 'https://github.com/hagiwara777/shopee-expansion-tool.git')
    git('add', '.')
    git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-m', 'Synthetic fixture')
    return root, git


def test_code_observation_uses_running_imports_and_git_not_release_config(tmp_path, monkeypatch):
    root, git = code_checkout(tmp_path, monkeypatch)
    observer = P5CodeIdentity()
    value = observer.observe()
    assert value['release'] == git('rev-parse', 'HEAD')
    assert value['entrypoint'] == 'app_beta.py' and len(value['source_digest']) == 64
    path = root / 'modules/p5_runtime.py'
    path.write_text('# Modified source without release change\n')
    with pytest.raises(P5Stopped, match='CODE_UNVERIFIED'):
        observer.observe()


def test_clean_checkout_cannot_hide_changed_loaded_code(tmp_path, monkeypatch):
    code_checkout(tmp_path, monkeypatch)
    from modules.p5_runtime import P5Runtime
    monkeypatch.setattr(P5Runtime, 'require_current', lambda self: None)
    with pytest.raises(P5Stopped, match='CODE_UNVERIFIED'):
        P5CodeIdentity().observe()


@pytest.mark.parametrize('mismatch', ['import', 'entrypoint', 'remote', 'untracked'])
def test_code_mismatch_fails_closed(tmp_path, monkeypatch, mismatch):
    root, git = code_checkout(tmp_path, monkeypatch)
    if mismatch == 'import':
        monkeypatch.setattr(sys.modules['modules.p5_transport'], '__file__', str(tmp_path / 'other.py'))
    elif mismatch == 'entrypoint':
        monkeypatch.setattr(sys.modules['__main__'], '__file__', str(tmp_path / 'app_beta.py'))
    elif mismatch == 'remote':
        git('remote', 'set-url', 'origin', 'https://example.invalid/other.git')
    else:
        (root / 'extra.py').write_text('# Unknown code\n')
    with pytest.raises(P5Stopped, match='CODE_UNVERIFIED'):
        P5CodeIdentity().observe()


def test_production_checks_code_references_and_unresolved_sources(tmp_path, monkeypatch):
    scope = scope_for(tmp_path, bridge_spreadsheet_id='synthetic-sheet')
    adapter, authority, observed, approval = trusted_adapter(scope)
    adapter.synthetic = False
    with pytest.raises(P5Stopped, match='CODE_UNVERIFIED'):
        adapter.compose(scope, approval_reference='SYNTHETIC')
    adapter.code_identity = P5CodeIdentity()
    resolver = P5CredentialResolver(credential_reference(scope, tmp_path))
    adapter.resolve_secrets = resolver
    observed['credential'] = resolver.describe(scope)
    code = {k: observed[k] for k in ('release', 'source_digest', 'entrypoint')}
    # Synthetic observer only: this does not claim production observation.
    monkeypatch.setattr(P5CodeIdentity, 'observe', lambda self: code)
    def bind():
        authority.verify_original = lambda ref: replace(approval, observations_digest=_digest(observed))
    bind()
    code['release'] = '1' * 40
    with pytest.raises(P5Stopped, match='CODE_MISMATCH'):
        adapter.compose(scope, approval_reference='SYNTHETIC')
    code['release'] = scope.release
    observed['primary_sources']['attribute']['verified'] = False
    bind()  # Even an approved digest cannot turn an unresolved source verified.
    with pytest.raises(P5Stopped, match='PRIMARY_SOURCE_UNVERIFIED'):
        adapter.compose(scope, approval_reference='SYNTHETIC')
    observed['primary_sources']['attribute']['verified'] = True
    bind()
    with pytest.raises(P5Stopped, match='ATTRIBUTE_LIVE_NOT_ENABLED'):
        adapter.compose(scope, approval_reference='SYNTHETIC')
    assert not Path(resolver.reference.audit_env).exists()


@pytest.mark.parametrize('authority', [None, 'APPROVED', {'APPROVED': True}])
def test_missing_original_authority_is_a_safe_stop(tmp_path, authority):
    scope = scope_for(tmp_path)
    adapter, _, _, _ = trusted_adapter(scope)
    adapter.authority = authority
    with pytest.raises(P5Stopped, match='OWNER_APPROVAL_UNVERIFIED'):
        adapter.compose(scope, approval_reference='APPROVED')


def test_bridge_permission_precedes_google_body_read(tmp_path, monkeypatch):
    rt = runtime_for(tmp_path, bridge_spreadsheet_id='synthetic-sheet')
    rt.authorization_guard = lambda operation=None: (
        (_ for _ in ()).throw(P5Stopped('SYNTHETIC_OPERATION_REFUSED')) if operation == 'auth' else None)
    read_text = Path.read_text
    def read(path, *args, **kwargs):
        if str(path) == 'unread':
            pytest.fail('unauthorized secret read')
        return read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    try:
        with pytest.raises(P5Stopped, match='OPERATION_REFUSED'):
            P5BridgeTransport(rt, credential_file='unread', spreadsheet_id='synthetic-sheet').read_values(
                'synthetic-sheet', 'A:C')
    finally:
        rt.close()


def test_bridge_other_sheet_or_range_is_refused_before_send(tmp_path):
    rt = runtime_for(tmp_path, bridge_spreadsheet_id='synthetic-sheet')
    calls = []
    http = P5HTTP(rt, 'bridge', session=SimpleNamespace(request=lambda *a, **k: calls.append(a)))
    try:
        for suffix in ('other/values/A%3AC', 'synthetic-sheet/values/A%3AD'):
            with pytest.raises(P5Stopped, match='BRIDGE_BINDING'):
                http.get('https://sheets.googleapis.com/v4/spreadsheets/' + suffix,
                         params={'majorDimension': 'ROWS'})
        assert not calls and not rt.ledger.data['reservations']
    finally:
        rt.close()


@pytest.mark.parametrize('failure', ['extra-auth', 'timeout', 'redirect', 'bad-body'])
def test_google_failure_cannot_retry_or_replenish_reservations(tmp_path, monkeypatch, failure):
    rt = runtime_for(tmp_path, bridge_spreadsheet_id='synthetic-sheet')
    path = tmp_path / 'synthetic-google.json'
    path.write_text('{"type":"authorized_user"}')
    calls = []
    class Session:
        def mount(self, *args): pass
        def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            assert kwargs['allow_redirects'] is False
            if failure == 'timeout':
                raise TimeoutError('SYNTHETIC')
            body = {'access_token': 'SYNTHETIC_ONLY', 'expires_in': 300}
            return SimpleNamespace(status_code=302 if failure == 'redirect' else 200,
                content=json.dumps(body).encode(), headers={}, json=lambda: body)
    class Credentials:
        def before_request(self, request, method, url, headers):
            request('https://oauth2.googleapis.com/token', method='POST', body=b'SYNTHETIC')
            if failure == 'bad-body':
                raise ValueError('SYNTHETIC parser failure after consumed response')
            request('https://oauth2.googleapis.com/token', method='POST', body=b'SYNTHETIC')
    monkeypatch.setattr('requests.Session', Session)
    monkeypatch.setattr('google.auth.load_credentials_from_dict', lambda *a, **k: (Credentials(), None))
    bridge = P5BridgeTransport(rt, credential_file=path, spreadsheet_id='synthetic-sheet')
    try:
        with pytest.raises(P5Stopped): bridge.read_values('synthetic-sheet', 'A:C')
        saved = json.loads(rt.ledger.path.read_text())
        with pytest.raises(P5Stopped): bridge.read_values('synthetic-sheet', 'A:C')
        assert len(calls) == 1
        assert len(saved['reservations']) == 1 and saved['stopped'] is True
        if failure in {'timeout', 'redirect'}:
            assert saved['reservations'][0]['state'] == 'UNKNOWN'
        assert json.loads(rt.ledger.path.read_text()) == saved
    finally:
        rt.close()
