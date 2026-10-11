"""Deployment checks use synthetic files and mocked Git; external I/O forbidden."""
from dataclasses import replace, asdict
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from modules import sg_beta_environment as environment
from modules import sg_live_runtime as runtime
from test_sg_live_runtime import grant, factory, isolated_claims
from test_sg_beta_release import activation


@pytest.fixture
def profile(tmp_path, monkeypatch, grant):
    repo = tmp_path/'release'; repo.mkdir()
    monkeypatch.setattr(environment, 'ROOT', repo)
    monkeypatch.setattr(environment, 'require_sg_beta_operation', lambda: None)
    calls=[]
    def git(*args):
        calls.append(args)
        return 'a'*40 if args == ('rev-parse','HEAD') else ''
    monkeypatch.setattr(environment, '_git', git)
    inputs=tmp_path/'inputs'; inputs.mkdir()
    fixtures=Path(__file__).parent/'fixtures/browser_e2e/sg_candidate'
    gate='prelisting_gate_eligible_sg_expansion.csv'
    for name,source in [('candidate.csv','candidate.csv'),('product_text.csv','product_text.csv'),
                        ('raw_images.json','raw_images.json'),(gate,gate)]:
        shutil.copyfile(fixtures/source,inputs/name)
    grant_path=tmp_path/'grant.json'; grant_path.write_text(json.dumps(asdict(grant)))
    for name in ('python.exe','api.env','google-reader.json'): (tmp_path/name).touch()
    config=dict(schema_version=1,marketplace='SG',release_commit='a'*40,repository_path=str(repo),
        python_path=str(tmp_path/'python.exe'),api_env_path=str(tmp_path/'api.env'),
        google_credentials_path=str(tmp_path/'google-reader.json'),grant_path=str(grant_path),
        data_root=str(tmp_path/'persistent'),inputs_dir=str(inputs),gate_filename=gate,port=8502,
        input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()})
    path=tmp_path/'deployment.json'; path.write_text(json.dumps(config))
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:pytest.fail('External I/O forbidden'))
    return path,config,calls


def test_preflight_validates_without_creating_runtime_data(profile):
    path,config,calls=profile
    assert environment.preflight(path)==config
    assert ('merge-base','--is-ancestor','a'*40,'refs/remotes/origin/main') in calls
    assert not Path(config['data_root']).exists()


@pytest.mark.parametrize('change',['dirty','not-formal','wrong-head','wrong-market','changed-input','bad-sidecar','wrong-asins','wrong-repo','ph-port'])
def test_preflight_stops_invalid_deployment(profile,monkeypatch,change):
    path,c,_=profile
    if change in {'dirty','not-formal','wrong-head'}:
        def git(*args):
            if change=='not-formal' and args[0]=='merge-base':
                raise subprocess.CalledProcessError(1,'git')
            if args[0]=='rev-parse': return 'b'*40 if change=='wrong-head' else 'a'*40
            return ' M app_sg_beta.py' if change=='dirty' else ''
        monkeypatch.setattr(environment,'_git',git)
    elif change=='wrong-market': c['marketplace']='PH'
    elif change=='wrong-repo': c['repository_path']=str(path.parent)
    elif change=='ph-port': c['port']=8501
    elif change in {'changed-input','bad-sidecar'}:
        asset=Path(c['inputs_dir'])/('candidate.csv' if change=='changed-input' else 'raw_images.json')
        asset.write_bytes(b'broken')
        if change=='bad-sidecar': c['input_sha256'][asset.name]=hashlib.sha256(asset.read_bytes()).hexdigest()
    else:
        grant_path=Path(c['grant_path']); data=json.loads(grant_path.read_text())
        data['allowed_asins']=['B000000002']; grant_path.write_text(json.dumps(data))
    path.write_text(json.dumps(c))
    with pytest.raises(environment.SGBetaEnvironmentError): environment.preflight(path)
    assert not Path(c['data_root']).exists()


def test_persistent_claim_and_spend_survive_code_release_change(tmp_path,grant,monkeypatch):
    run=tmp_path/'persistent/run'; claims=tmp_path/'persistent/claims'
    r=runtime.SGLiveRuntime(grant=grant,run_path=run,claim_dir=claims,fresh_client_factory=factory([]))
    r.refresh_catalog(); r.close()
    monkeypatch.setattr(runtime,'CLAIM_DIR',tmp_path/'new-code-release/claims')
    r=runtime.SGLiveRuntime(grant=grant,run_path=run,claim_dir=claims,fresh_client_factory=factory([]))
    assert r.ledger.data['catalog_requests']==1
    r.close()
    with pytest.raises(runtime.LiveValidationStopped):
        runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/'reset-run',claim_dir=claims)


def test_beta_entry_forwards_persistent_root(activation,monkeypatch,tmp_path):
    from app_sg_beta import render_sg_beta
    import app_sg_beta
    calls=[]
    monkeypatch.setattr(app_sg_beta,'render_sg_live_candidate',lambda *a,**k:calls.append(k))
    render_sg_beta(tmp_path/'grant.json',runtime_root=tmp_path/'data')
    assert calls[0]['runtime_root']==tmp_path/'data' and calls[0]['beta_output'] is True


@pytest.fixture
def continuous_profile(profile, tmp_path, monkeypatch):
    from modules.sg_continuous_runtime import SGContinuousPolicy, initialize_continuous_operation
    path, old, calls = profile
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'appdata'))
    policy = SGContinuousPolicy('offline-preflight', 22, 'synthetic-bridge', 2, 0, 50, 4, 3, '0',
                                'Synthetic offline authorization only')
    policy_path = tmp_path/'policy.json'
    policy_path.write_text(json.dumps(asdict(policy)))
    config = {key: old[key] for key in ('marketplace', 'release_commit', 'repository_path',
              'python_path', 'api_env_path', 'google_credentials_path', 'data_root', 'port')}
    config.update(schema_version=2, mode='continuous', policy_path=str(policy_path))
    run = Path(config['data_root'])/'continuous'
    initialize_continuous_operation(policy, run)
    path.write_text(json.dumps(config))
    return path, config, calls, run


def test_continuous_preflight_has_no_fixed_input_contract(continuous_profile):
    path, config, calls, run = continuous_profile
    before = {p: p.read_bytes() for p in run.iterdir() if p.is_file()}
    assert environment.preflight(path) == config
    # The legacy input directory is irrelevant to normal admission in the UI.
    for p in (path.parent/'inputs').iterdir():
        p.write_bytes(b'different batch, to be validated at admission')
    assert environment.preflight(path) == config
    assert before == {p: p.read_bytes() for p in run.iterdir() if p.is_file()}
    assert ('merge-base', '--is-ancestor', 'a'*40, 'refs/remotes/origin/main') in calls


@pytest.mark.parametrize('change', ['dirty', 'not-formal', 'mode', 'market', 'ph-port', 'old-grant',
                                  'policy', 'ledger', 'db-schema', 'db-corrupt', 'binding', 'missing-db'])
def test_continuous_preflight_stops_without_repair(continuous_profile, monkeypatch, change):
    import sqlite3
    path, config, calls, run = continuous_profile
    if change in {'dirty', 'not-formal'}:
        def git(*args):
            if change == 'not-formal' and args[0] == 'merge-base':
                raise subprocess.CalledProcessError(1, 'git')
            if args[0] == 'rev-parse': return 'a'*40
            return ' M app.py' if change == 'dirty' else ''
        monkeypatch.setattr(environment, '_git', git)
    elif change == 'mode': config['mode'] = 'limited'
    elif change == 'market': config['marketplace'] = 'PH'
    elif change == 'ph-port': config['port'] = 8501
    elif change == 'old-grant': config['grant_path'] = str(path.parent/'grant.json')
    elif change == 'policy':
        p = Path(config['policy_path']); data = json.loads(p.read_text())
        data['keepa_request_limit'] += 1; p.write_text(json.dumps(data))
    elif change == 'db-schema':
        with sqlite3.connect(run/'validation.sqlite3') as db:
            db.execute('DROP TABLE catalog_categories')
    elif change == 'db-corrupt':
        import gc
        gc.collect()
        (run/'validation.sqlite3').write_bytes(b'not a database')
    elif change == 'missing-db':
        import gc
        gc.collect()  # Existing sqlite transaction contexts release on collection.
        (run/'validation.sqlite3').unlink()
    else: (run/('request-ledger.json' if change == 'ledger' else 'run-binding.json')).write_text('{}')
    path.write_text(json.dumps(config))
    before = {p: p.read_bytes() for p in run.iterdir() if p.is_file()}
    with pytest.raises(environment.SGBetaEnvironmentError): environment.preflight(path)
    assert before == {p: p.read_bytes() for p in run.iterdir() if p.is_file()}
