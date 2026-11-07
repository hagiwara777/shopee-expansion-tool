"""Offline launcher tests: local synthetic Git repositories and fake Sora processes."""
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from scripts import sora_launcher as launcher


def git(directory, *args):
    result = subprocess.run(['git', '-C', str(directory), *args], check=False,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding='utf-8', errors='replace')
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def repositories(tmp_path, monkeypatch):
    # Each test uses a local synthetic remote. Nothing points at the formal checkout.
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', str(tmp_path / 'empty-gitconfig'))
    remote, writer, installed = (tmp_path / name for name in ('remote.git', 'writer', 'installed'))
    subprocess.run(['git', 'init', '--bare', '-b', 'main', str(remote)], check=True, capture_output=True)
    subprocess.run(['git', 'init', '-b', 'main', str(writer)], check=True, capture_output=True)
    git(writer, 'config', 'user.name', 'Synthetic Test')
    git(writer, 'config', 'user.email', 'synthetic@example.invalid')
    (writer / 'app.py').write_text('synthetic old version\n', encoding='utf-8')
    (writer / '.gitignore').write_text('private.txt\n', encoding='utf-8')
    git(writer, 'add', 'app.py', '.gitignore')
    git(writer, 'commit', '-m', 'initial')
    git(writer, 'remote', 'add', 'origin', str(remote))
    git(writer, 'push', '-u', 'origin', 'main')
    subprocess.run(['git', 'clone', '--branch', 'main', str(remote), str(installed)],
                   check=True, capture_output=True)
    git(installed, 'config', 'user.name', 'Synthetic Test')
    git(installed, 'config', 'user.email', 'synthetic@example.invalid')
    monkeypatch.setattr(launcher, 'OFFICIAL_REMOTE_URLS', frozenset({git(installed, 'remote', 'get-url', 'origin')}))
    return remote, writer, installed


def advance(writer, text='synthetic new version\n'):
    (writer / 'app.py').write_text(text, encoding='utf-8')
    git(writer, 'add', 'app.py')
    git(writer, 'commit', '-m', 'next')
    git(writer, 'push', 'origin', 'main')
    return git(writer, 'rev-parse', 'HEAD')


class FakeRuntime:
    def __init__(self, states=()):
        self.states = list(states)
        self.last_state = 'FREE'
        self.started = []
        self.opened = 0

    def port_state(self):
        if self.states:
            self.last_state = self.states.pop(0)
        return self.last_state

    def open_existing(self):
        self.opened += 1
        return True

    def start(self, env_reference):
        self.started.append(env_reference)
        return 0


def records(directory):
    return [json.loads(line) for line in (directory / 'startup.jsonl').read_text(encoding='utf-8').splitlines()]


def test_clean_main_fast_forwards_once_and_starts_with_audit(repositories, tmp_path, monkeypatch):
    _, writer, installed = repositories
    before, target = git(installed, 'rev-parse', 'HEAD'), advance(writer)
    commands, original = [], launcher.Git.run
    def observed(self, *args, **kwargs):
        commands.append(args)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(launcher.Git, 'run', observed)
    runtime, journal = FakeRuntime(), tmp_path / 'outside-log'
    assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == 0
    assert git(installed, 'rev-parse', 'HEAD') == target
    assert runtime.started == ['synthetic-reference'] and runtime.opened == 0
    merges = [args for args in commands if args and args[0] == 'merge']
    assert merges == [('merge', '--ff-only', '--no-overwrite-ignore', target)]
    assert records(journal)[-1]['before'] == before
    assert records(journal)[-1]['after'] == target
    assert '更新しました' in records(journal)[-1]['reason']
    assert 'synthetic-reference' not in (journal / 'startup.jsonl').read_text(encoding='utf-8')


def test_fetch_failure_starts_unchanged_version(repositories, tmp_path, monkeypatch):
    _, _, installed = repositories
    missing = str(tmp_path / 'missing-remote')
    git(installed, 'remote', 'set-url', 'origin', missing)
    monkeypatch.setattr(launcher, 'OFFICIAL_REMOTE_URLS', frozenset({missing}))
    before, runtime = git(installed, 'rev-parse', 'HEAD'), FakeRuntime()
    journal = tmp_path / 'outside-log'
    assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == 0
    assert git(installed, 'rev-parse', 'HEAD') == before and len(runtime.started) == 1
    assert '取得に失敗' in records(journal)[-1]['reason']


def test_already_latest_starts_without_merging(repositories, tmp_path, monkeypatch):
    _, _, installed = repositories
    original = launcher.Git.run
    def no_merge(self, *args, **kwargs):
        assert not args or args[0] != 'merge'
        return original(self, *args, **kwargs)
    monkeypatch.setattr(launcher.Git, 'run', no_merge)
    before, runtime = git(installed, 'rev-parse', 'HEAD'), FakeRuntime()
    journal = tmp_path / 'outside-log'
    assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == 0
    assert len(runtime.started) == 1 and git(installed, 'rev-parse', 'HEAD') == before
    assert records(journal)[-1]['before'] == records(journal)[-1]['after'] == before
    assert 'すでに最新' in records(journal)[-1]['reason']


def test_head_change_during_latest_check_is_recorded(repositories, monkeypatch):
    _, _, installed = repositories
    before = git(installed, 'rev-parse', 'HEAD')
    changed = 'b' * len(before)
    heads = iter([before, changed])
    monkeypatch.setattr(launcher.Git, 'head', lambda self: next(heads))
    result = launcher.update_checkout(installed, lambda: 'FREE')
    assert result.before == before and result.after == changed
    assert '状態が変わった' in result.reason


@pytest.mark.parametrize('change', ['tracked', 'untracked'])
def test_dirty_checkout_is_preserved_and_current_version_starts(repositories, tmp_path, change):
    _, writer, installed = repositories
    before = git(installed, 'rev-parse', 'HEAD')
    advance(writer)
    changed = installed / ('app.py' if change == 'tracked' else 'untracked.txt')
    changed.write_text('local work\n', encoding='utf-8')
    runtime, journal = FakeRuntime(), tmp_path / 'outside-log'
    assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == 0
    assert git(installed, 'rev-parse', 'HEAD') == before
    assert changed.read_text(encoding='utf-8') == 'local work\n'
    assert len(runtime.started) == 1 and '未追跡' in records(journal)[-1]['reason']


def test_diverged_main_is_not_merged_and_current_version_starts(repositories, tmp_path):
    _, writer, installed = repositories
    advance(writer)
    (installed / 'app.py').write_text('local commit\n', encoding='utf-8')
    git(installed, 'add', 'app.py')
    git(installed, 'commit', '-m', 'diverged')
    before, runtime = git(installed, 'rev-parse', 'HEAD'), FakeRuntime()
    journal = tmp_path / 'outside-log'
    assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == 0
    assert git(installed, 'rev-parse', 'HEAD') == before and len(runtime.started) == 1
    assert '安全に進められない' in records(journal)[-1]['reason']


def test_detached_checkout_stays_on_the_previous_commit(repositories, tmp_path):
    _, writer, installed = repositories
    before = git(installed, 'rev-parse', 'HEAD')
    git(installed, 'switch', '--detach', before)
    advance(writer)
    runtime, journal = FakeRuntime(), tmp_path / 'outside-log'
    assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == 0
    assert git(installed, 'rev-parse', 'HEAD') == before and len(runtime.started) == 1
    assert 'mainブランチでない' in records(journal)[-1]['reason']


@pytest.mark.parametrize(('state', 'exit_code', 'opened'), [('SORA', 0, 1), ('UNKNOWN', 1, 0), ('ERROR', 1, 0)])
def test_occupied_or_unverified_port_never_fetches_or_starts(repositories, tmp_path, monkeypatch,
                                                            state, exit_code, opened):
    _, _, installed = repositories
    original = launcher.Git.run
    def no_fetch(self, *args, **kwargs):
        assert not args or args[0] != 'fetch'
        return original(self, *args, **kwargs)
    monkeypatch.setattr(launcher.Git, 'run', no_fetch)
    runtime, journal = FakeRuntime([state]), tmp_path / 'outside-log'
    before = git(installed, 'rev-parse', 'HEAD')
    assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == exit_code
    assert runtime.opened == opened and runtime.started == []
    assert records(journal)[-1]['before'] == records(journal)[-1]['after'] == before


def test_port_becoming_busy_during_fetch_prevents_merge(repositories, tmp_path):
    _, writer, installed = repositories
    before = git(installed, 'rev-parse', 'HEAD')
    advance(writer)
    runtime, journal = FakeRuntime(['FREE', 'FREE', 'SORA', 'SORA']), tmp_path / 'outside-log'
    assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == 0
    assert git(installed, 'rev-parse', 'HEAD') == before
    assert runtime.opened == 1 and runtime.started == []


def test_foreign_remote_is_not_fetched(repositories, tmp_path, monkeypatch):
    _, _, installed = repositories
    git(installed, 'remote', 'set-url', 'origin', 'https://example.invalid/not-formal.git')
    original = launcher.Git.run
    def no_fetch(self, *args, **kwargs):
        assert not args or args[0] != 'fetch'
        return original(self, *args, **kwargs)
    monkeypatch.setattr(launcher.Git, 'run', no_fetch)
    runtime, journal = FakeRuntime(), tmp_path / 'outside-log'
    assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == 0
    assert len(runtime.started) == 1 and '正式repositoryでない' in records(journal)[-1]['reason']


def test_existing_sora_opens_even_when_no_config_reference_is_inherited(repositories, tmp_path, monkeypatch):
    _, _, installed = repositories
    monkeypatch.delenv('SORA_SP_API_ENV', raising=False)
    runtime = FakeRuntime(['SORA'])
    assert launcher.run_launcher(installed, tmp_path / 'outside-log', None, runtime) == 0
    assert runtime.opened == 1 and runtime.started == []


def test_missing_config_reference_prevents_new_start_and_update(repositories, tmp_path, monkeypatch):
    _, writer, installed = repositories
    monkeypatch.delenv('SORA_SP_API_ENV', raising=False)
    before = git(installed, 'rev-parse', 'HEAD')
    advance(writer)
    runtime, journal = FakeRuntime(), tmp_path / 'outside-log'
    assert launcher.run_launcher(installed, journal, None, runtime) == 1
    assert git(installed, 'rev-parse', 'HEAD') == before and runtime.started == []
    assert '設定ファイル参照がない' in records(journal)[-1]['reason']


def test_ignored_file_collision_is_not_overwritten(repositories, tmp_path):
    _, writer, installed = repositories
    before = git(installed, 'rev-parse', 'HEAD')
    (installed / 'private.txt').write_text('local ignored content', encoding='utf-8')
    (writer / '.gitignore').write_text('', encoding='utf-8')
    (writer / 'private.txt').write_text('upstream content', encoding='utf-8')
    git(writer, 'add', '.gitignore', 'private.txt')
    git(writer, 'commit', '-m', 'add tracked file')
    git(writer, 'push', 'origin', 'main')
    runtime, journal = FakeRuntime(), tmp_path / 'outside-log'
    assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == 0
    assert git(installed, 'rev-parse', 'HEAD') == before
    assert (installed / 'private.txt').read_text(encoding='utf-8') == 'local ignored content'
    assert len(runtime.started) == 1 and '更新に失敗' in records(journal)[-1]['reason']


def test_log_location_inside_checkout_is_rejected(repositories):
    _, _, installed = repositories
    runtime = FakeRuntime()
    assert launcher.run_launcher(installed, installed / 'logs', 'synthetic-reference', runtime) == 1
    assert runtime.started == [] and not (installed / 'logs').exists()


def test_unwritable_log_prevents_update_but_starts_current_version(repositories, tmp_path, monkeypatch):
    _, writer, installed = repositories
    before = git(installed, 'rev-parse', 'HEAD')
    advance(writer)
    monkeypatch.setattr(launcher.Journal, 'append', lambda self, result: False)
    runtime = FakeRuntime()
    assert launcher.run_launcher(installed, tmp_path / 'outside-log', 'synthetic-reference', runtime) == 0
    assert git(installed, 'rev-parse', 'HEAD') == before and len(runtime.started) == 1


def test_another_launcher_prevents_a_second_update_or_start(repositories, tmp_path):
    _, writer, installed = repositories
    before = git(installed, 'rev-parse', 'HEAD')
    advance(writer)
    runtime, journal = FakeRuntime(), tmp_path / 'outside-log'
    journal.mkdir()
    with launcher.launch_lock(journal):
        assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == 1
    assert git(installed, 'rev-parse', 'HEAD') == before and runtime.started == []
    assert '起動処理が進行中' in records(journal)[-1]['reason']


def test_unverified_post_merge_state_never_starts_sora(repositories, tmp_path, monkeypatch):
    _, writer, installed = repositories
    target = advance(writer)
    original, merged = launcher.Git.clean, []
    original_run = launcher.Git.run
    def observed_run(self, *args, **kwargs):
        result = original_run(self, *args, **kwargs)
        if args and args[0] == 'merge':
            merged.append(True)
        return result
    def fail_after_merge(self):
        if merged:
            raise launcher.GitError('synthetic post-update check failure')
        return original(self)
    monkeypatch.setattr(launcher.Git, 'run', observed_run)
    monkeypatch.setattr(launcher.Git, 'clean', fail_after_merge)
    runtime, journal = FakeRuntime(), tmp_path / 'outside-log'
    assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == 1
    assert git(installed, 'rev-parse', 'HEAD') == target and runtime.started == []
    assert '確認できません' in records(journal)[-1]['reason']


def test_update_timeout_does_not_start_even_if_head_appears_unchanged(repositories, tmp_path, monkeypatch):
    _, writer, installed = repositories
    before = git(installed, 'rev-parse', 'HEAD')
    advance(writer)
    original = launcher.Git.run
    def timed_out_merge(self, *args, **kwargs):
        if args and args[0] == 'merge':
            raise launcher.GitTimeout('synthetic timeout')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(launcher.Git, 'run', timed_out_merge)
    runtime, journal = FakeRuntime(), tmp_path / 'outside-log'
    assert launcher.run_launcher(installed, journal, 'synthetic-reference', runtime) == 1
    assert git(installed, 'rev-parse', 'HEAD') == before and runtime.started == []
    assert '時間切れ' in records(journal)[-1]['reason']


def test_streamlit_command_uses_current_python_and_only_passes_the_reference(tmp_path, monkeypatch):
    captured = []
    monkeypatch.setenv('SORA_SP_API_ENV', 'previous-reference')
    def fake_call(command, *, cwd):
        captured.append((command, cwd, os.environ['SORA_SP_API_ENV']))
        return 0
    monkeypatch.setattr(launcher.subprocess, 'call', fake_call)
    assert launcher.WindowsRuntime(tmp_path).start('synthetic-reference') == 0
    command, cwd, reference = captured[0]
    assert command[:5] == [sys.executable, '-m', 'streamlit', 'run', str(tmp_path / 'app.py')]
    assert command[5:7] == ['--server.port', '8510'] and cwd == tmp_path
    assert reference == 'synthetic-reference' and reference not in command
    assert os.environ['SORA_SP_API_ENV'] == 'previous-reference'


def test_git_does_not_receive_application_credentials_or_askpass(tmp_path, monkeypatch):
    monkeypatch.setenv('SORA_SP_API_ENV', 'synthetic-reference')
    monkeypatch.setenv('SP_API_CLIENT_SECRET', 'synthetic-value')
    monkeypatch.setenv('GITHUB_TOKEN', 'synthetic-value')
    monkeypatch.setenv('GIT_ASKPASS', 'synthetic-askpass')
    captured = []
    def fake_run(command, **kwargs):
        captured.append(kwargs['env'])
        return subprocess.CompletedProcess(command, 0, '', '')
    monkeypatch.setattr(launcher.subprocess, 'run', fake_run)
    launcher.Git(tmp_path).run('status')
    environment = captured[0]
    assert 'SORA_SP_API_ENV' not in environment and 'SP_API_CLIENT_SECRET' not in environment
    assert 'GITHUB_TOKEN' not in environment and environment['GIT_ASKPASS'] == ''
    assert environment['GIT_TERMINAL_PROMPT'] == '0'


def test_desktop_example_calls_the_managed_cmd_only():
    example = Path(launcher.__file__).with_name('Sora-Start.cmd.example').read_text(encoding='ascii')
    lines = [line.strip() for line in example.splitlines() if line.strip() and line.strip().lower() != '@echo off']
    assert len(lines) == 1 and lines[0].lower().startswith('call ')
    assert '\\scripts\\Start-Sora.cmd' in lines[0]


def test_managed_cmd_passes_existing_python_and_reference(tmp_path):
    scripts = tmp_path / 'formal folder with spaces' / 'scripts'
    scripts.mkdir(parents=True)
    managed = Path(launcher.__file__).with_name('Start-Sora.cmd')
    (scripts / managed.name).write_bytes(managed.read_bytes())
    (scripts / 'sora_launcher.py').write_text(
        'import json, sys\nfrom pathlib import Path\n'
        'Path(__file__).with_name("args.json").write_text(json.dumps(sys.argv[1:]))\n', encoding='ascii')
    desktop = tmp_path / 'desktop.cmd'
    desktop.write_text(f'@echo off\ncall "{scripts / managed.name}" "{sys.executable}" "synthetic reference"\n',
                       encoding='ascii')
    result = subprocess.run(['cmd.exe', '/d', '/c', str(desktop)], input='\n',
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads((scripts / 'args.json').read_text()) == ['--sp-api-env', 'synthetic reference']


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@pytest.mark.parametrize(('process_ids', 'name', 'command', 'expected'), [
    ([], '', '', 'UNKNOWN'),
    ([123], 'python.exe', '"C:\\Python\\python.exe" -m streamlit run "C:\\Sora Folder\\app.py" --server.port 8510', 'SORA'),
    ([123], 'python.exe', '"C:\\Python\\python.exe" -m streamlit run "C:\\Other\\app.py" --server.port 8510', 'UNKNOWN'),
    ([123], 'python.exe', '"C:\\Python\\python.exe" -c "-m streamlit run C:\\Sora Folder\\app.py --server.port 8510"', 'UNKNOWN'),
    ([123], 'other.exe', '"C:\\Python\\python.exe" -m streamlit run "C:\\Sora Folder\\app.py" --server.port 8510', 'UNKNOWN'),
    ([0], '', '', 'UNKNOWN'),
])
def test_windows_process_probe_distinguishes_only_the_expected_sora(process_ids, name, command, expected):
    script = Path(launcher.__file__).parent / 'Test-SoraProcess.ps1'
    owners = ','.join(str(value) for value in process_ids)
    source = f"""
. {ps_quote(script)}
function Get-CimInstance {{ param($ClassName, $Filter, $ErrorAction) [pscustomobject]@{{Name={ps_quote(name)}; CommandLine={ps_quote(command)}}} }}
Test-SoraProcesses -ExpectedAppPath 'C:\\Sora Folder\\app.py' -ProcessIds @({owners}) -ExpectedPort 8510
"""
    encoded = base64.b64encode(source.encode('utf-16le')).decode('ascii')
    completed = subprocess.run(['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive',
                                '-EncodedCommand', encoded], capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == expected


def test_missing_port_rows_never_override_a_failed_bind(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, 'tcp_owners', lambda port, kind: set())
    monkeypatch.setattr(launcher, 'port_can_bind', lambda port: False)
    assert launcher.WindowsRuntime(tmp_path).port_state() == 'UNKNOWN'
    monkeypatch.setattr(launcher, 'port_can_bind', lambda port: True)
    assert launcher.WindowsRuntime(tmp_path).port_state() == 'FREE'


def test_port_owner_changes_during_identity_check_are_not_accepted(tmp_path, monkeypatch):
    first = launcher.TcpOwner(socket.AF_INET, b'\0' * 4, 0, 100)
    second = launcher.TcpOwner(socket.AF_INET, b'\0' * 4, 0, 200)
    tables = iter([{first}, {first}, {second}])
    monkeypatch.setattr(launcher, 'tcp_owners', lambda port, kind: next(tables))
    runtime = launcher.WindowsRuntime(tmp_path)
    monkeypatch.setattr(runtime, '_processes_state', lambda owners: 'SORA')
    assert runtime.port_state() == 'UNKNOWN'


def test_windows_port_probe_recognizes_a_free_ephemeral_port(tmp_path, monkeypatch):
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1', 0))
        port = reserve.getsockname()[1]
    monkeypatch.setattr(launcher, 'PORT', port)
    assert launcher.WindowsRuntime(tmp_path).port_state() == 'FREE'


@pytest.mark.parametrize(('same_entry', 'expected'), [(True, 'SORA'), (False, 'UNKNOWN')])
def test_windows_port_probe_identifies_a_synthetic_listener(tmp_path, monkeypatch, same_entry, expected):
    # Start only a test-owned local socket, on an ephemeral port; no Sora or API is run.
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1', 0))
        port = reserve.getsockname()[1]
    package = tmp_path / 'streamlit'
    package.mkdir()
    (package / '__init__.py').write_text('', encoding='utf-8')
    (package / '__main__.py').write_text(
        'import os, socket, sys, time\n'
        'from pathlib import Path\n'
        's = socket.socket()\n'
        's.bind(("127.0.0.1", int(sys.argv[-1])))\n'
        's.listen()\n'
        'Path(os.environ["SORA_SYNTHETIC_READY"]).write_text("ready")\n'
        'time.sleep(60)\n', encoding='utf-8')
    app = tmp_path / 'app.py'
    app.write_text('# synthetic fixture\n', encoding='utf-8')
    actual_entry = app if same_entry else tmp_path / 'other.py'
    if not same_entry:
        actual_entry.write_text('# different synthetic fixture\n', encoding='utf-8')
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    helper = Path(launcher.__file__).parent / 'Test-SoraProcess.ps1'
    (scripts / helper.name).write_bytes(helper.read_bytes())
    monkeypatch.setattr(launcher, 'PORT', port)
    ready = tmp_path / 'ready.txt'
    env = dict(os.environ, PYTHONPATH=str(tmp_path), SORA_SYNTHETIC_READY=str(ready))
    process = subprocess.Popen([getattr(sys, '_base_executable', sys.executable), '-m', 'streamlit',
                                'run', str(actual_entry), '--server.port', str(port)], cwd=tmp_path, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists(), 'synthetic listener did not start'
        state = launcher.WindowsRuntime(tmp_path).port_state()
        assert state == expected, f'synthetic listener state was {state}'
    finally:
        process.terminate()
        process.wait(timeout=10)
