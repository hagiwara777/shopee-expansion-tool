"""Start Sora after an optional, guarded fast-forward of its own checkout."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import webbrowser


OFFICIAL_REMOTE_URLS = frozenset({
    'https://github.com/hagiwara777/shopee-expansion-tool',
    'https://github.com/hagiwara777/shopee-expansion-tool.git',
})
PORT = 8510
URL = 'http://localhost:8510'


class GitError(Exception):
    pass


class GitTimeout(GitError):
    pass


class LockBusy(Exception):
    pass


class PortProbeError(Exception):
    pass


@dataclass(frozen=True)
class UpdateResult:
    before: str | None
    after: str | None
    reason: str
    start_allowed: bool = True


@dataclass(frozen=True)
class TcpOwner:
    family: int
    address: bytes
    scope: int
    owner: int


def noncredential_environment() -> dict[str, str]:
    """Do not pass app credentials to Git or process-inspection helpers."""
    excluded_prefixes = ('SP_API_', 'SORA_SP_API_', 'AWS_', 'AMAZON_', 'OPENAI_', 'KEEPA_')
    excluded_names = {'GH_TOKEN', 'GITHUB_TOKEN'}
    return {key: os.environ[key] for key in os.environ
            if not key.upper().startswith(excluded_prefixes) and key.upper() not in excluded_names}


class _Tcp4Row(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in
                ('state', 'local_address', 'local_port', 'remote_address', 'remote_port', 'owner')]


class _Tcp6Row(ctypes.Structure):
    _fields_ = [('local_address', ctypes.c_ubyte * 16), ('local_scope', ctypes.c_uint32),
                ('local_port', ctypes.c_uint32), ('remote_address', ctypes.c_ubyte * 16),
                ('remote_scope', ctypes.c_uint32), ('remote_port', ctypes.c_uint32),
                ('state', ctypes.c_uint32), ('owner', ctypes.c_uint32)]


def tcp_owners(port: int, table_class: int) -> set[TcpOwner]:
    """Read both TCP families; use the OS listener table, not its optional state labels."""
    if os.name != 'nt':
        raise PortProbeError('Windows required')
    api = ctypes.WinDLL('iphlpapi', use_last_error=True).GetExtendedTcpTable
    api.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_int,
                    ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    api.restype = ctypes.c_uint32
    owners = set()
    for family, row_type in ((socket.AF_INET, _Tcp4Row), (socket.AF_INET6, _Tcp6Row)):
        size = ctypes.c_uint32()
        if api(None, ctypes.byref(size), 0, family, table_class, 0) != 122 or size.value < 4:
            raise PortProbeError('TCP table size unavailable')
        # Other applications can open sockets between the size query and read.
        size.value += max(4096, size.value // 4)
        buffer = ctypes.create_string_buffer(size.value)
        if api(buffer, ctypes.byref(size), 0, family, table_class, 0) != 0:
            raise PortProbeError('TCP table unavailable')
        class Table(ctypes.Structure):
            _fields_ = [('count', ctypes.c_uint32), ('rows', row_type * 1)]
        count = ctypes.c_uint32.from_buffer(buffer).value
        offset = Table.rows.offset
        if count > (ctypes.sizeof(buffer) - offset) // ctypes.sizeof(row_type):
            raise PortProbeError('Invalid TCP table')
        rows = (row_type * count).from_buffer(buffer, offset)
        for row in rows:
            if socket.ntohs(row.local_port & 0xffff) != port:
                continue
            if family == socket.AF_INET:
                address = int(row.local_address).to_bytes(4, byteorder=sys.byteorder)
                scope = 0
            else:
                address, scope = bytes(row.local_address), int(row.local_scope)
            owners.add(TcpOwner(int(family), address, scope, int(row.owner)))
    return owners


def port_can_bind(port: int) -> bool:
    """Guard against a missing or incomplete OS table; never retain the sockets."""
    opened = []
    try:
        for family, address in ((socket.AF_INET, '0.0.0.0'), (socket.AF_INET6, '::')):
            connection = socket.socket(family, socket.SOCK_STREAM)
            opened.append(connection)
            connection.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            if family == socket.AF_INET6:
                connection.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            connection.bind((address, port))
        return True
    except OSError:
        return False
    finally:
        for connection in opened:
            connection.close()


class Git:
    def __init__(self, repository: Path):
        self.repository = repository

    def run(self, *args: str, timeout: int = 15, check: bool = True):
        # The formal repository is public. Do not ask for, read, or send Git credentials.
        command = [
            'git', '-c', 'credential.helper=', '-c', 'credential.interactive=never',
            '-c', 'core.askPass=', '-c', 'http.extraHeader=',
            '-c', 'http.https://github.com/.extraHeader=', '-C', str(self.repository), *args,
        ]
        environment = noncredential_environment()
        environment['GIT_TERMINAL_PROMPT'] = '0'
        environment['GCM_INTERACTIVE'] = 'Never'
        environment['GIT_ASKPASS'] = ''
        environment['SSH_ASKPASS'] = ''
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, encoding='utf-8',
                                    errors='replace', env=environment, timeout=timeout,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired as exc:
            raise GitTimeout('git timed out') from exc
        except OSError as exc:
            raise GitError('git unavailable') from exc
        if check and result.returncode:
            # stderr may contain private paths or URLs; do not display or record it.
            raise GitError('git failed')
        return result

    def head(self) -> str | None:
        try:
            value = self.run('rev-parse', '--verify', 'HEAD^{commit}').stdout.strip().lower()
        except GitError:
            return None
        return value if re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', value) else None

    def official_remote(self) -> bool:
        values = self.run('remote', 'get-url', '--all', 'origin').stdout.splitlines()
        allowed = {value.casefold() for value in OFFICIAL_REMOTE_URLS}
        return len(values) == 1 and values[0].strip().casefold() in allowed

    def on_main(self) -> bool:
        result = self.run('symbolic-ref', '--quiet', '--short', 'HEAD', check=False)
        return result.returncode == 0 and result.stdout.strip() == 'main'

    def clean(self) -> bool:
        return not self.run('status', '--porcelain=v1', '--untracked-files=all', '-z').stdout


def update_checkout(repository: Path, port_state) -> UpdateResult:
    """Never force, reset, remove or stash; retain the current checkout on precheck failure."""
    git = Git(repository)
    before = git.head()
    if before is None:
        return UpdateResult(None, None, '現在の版を確認できないため更新しません')
    merge_started = False
    try:
        root = Path(git.run('rev-parse', '--show-toplevel').stdout.strip()).resolve()
        if root != repository.resolve():
            return UpdateResult(before, before, '正式版フォルダを確認できないため更新しません')
        if not git.official_remote():
            return UpdateResult(before, before, 'originが正式repositoryでないため更新しません')
        try:
            git.run('fetch', '--no-tags', '--no-recurse-submodules', 'origin',
                    'refs/heads/main:refs/remotes/origin/main', timeout=30)
        except GitError:
            return UpdateResult(before, git.head(), 'mainの取得に失敗したため更新しません')
        if not git.on_main():
            return UpdateResult(before, git.head(), 'mainブランチでないため更新しません')
        if not git.clean():
            return UpdateResult(before, git.head(), '変更または未追跡ファイルがあるため更新しません')
        target = git.run('rev-parse', '--verify', 'refs/remotes/origin/main^{commit}').stdout.strip().lower()
        if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', target):
            return UpdateResult(before, git.head(), '更新先を確認できないため更新しません')
        ancestor = git.run('merge-base', '--is-ancestor', before, target, check=False)
        if ancestor.returncode != 0:
            return UpdateResult(before, git.head(), '現在の版から安全に進められないため更新しません')
        if target == before:
            after = git.head()
            if after != before:
                return UpdateResult(before, after, '更新前の状態が変わったため更新しません')
            return UpdateResult(before, after, 'すでに最新のため更新しません')
        if port_state() != 'FREE':
            return UpdateResult(before, git.head(), '8510の状態が変わったため更新しません')
        if git.head() != before or not git.on_main() or not git.clean() or not git.official_remote():
            return UpdateResult(before, git.head(), '更新前の状態が変わったため更新しません')
        try:
            merge_started = True
            git.run('merge', '--ff-only', '--no-overwrite-ignore', target, timeout=60)
        except GitTimeout:
            return UpdateResult(before, git.head(), '更新が時間切れとなり状態を確認できません', start_allowed=False)
        except GitError:
            after = git.head()
            try:
                unchanged = after == before and git.on_main() and git.clean()
            except GitError:
                unchanged = False
            return UpdateResult(before, after, '更新に失敗しました', start_allowed=unchanged)
        after = git.head()
        if after != target or not git.on_main() or not git.clean():
            return UpdateResult(before, after, '更新後の状態を確認できません', start_allowed=False)
        return UpdateResult(before, after, '最新mainへ更新しました')
    except (GitError, OSError, ValueError):
        return UpdateResult(before, git.head(), '更新条件を確認できません', start_allowed=not merge_started)


class Journal:
    def __init__(self, directory: Path, repository: Path):
        self.directory = directory.resolve()
        if self.directory == repository.resolve() or repository.resolve() in self.directory.parents:
            raise OSError('log directory must be outside the checkout')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'startup.jsonl'

    def append(self, result: UpdateResult) -> bool:
        record = {'time': datetime.now().astimezone().isoformat(timespec='seconds'),
                  'before': result.before, 'after': result.after, 'reason': result.reason}
        try:
            with self.path.open('a', encoding='utf-8', newline='\n') as output:
                output.write(json.dumps(record, ensure_ascii=False) + '\n')
                output.flush()
            return True
        except OSError:
            print('起動記録を書き込めません。')
            return False


@contextmanager
def launch_lock(directory: Path):
    """One launcher may update/start at a time; keep the lock while Sora is running."""
    handle = (directory / 'startup.lock').open('a+b')
    acquired = False
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b'\0')
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise LockBusy from exc
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise LockBusy from exc
        acquired = True
        yield
    finally:
        if acquired:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


class WindowsRuntime:
    def __init__(self, repository: Path):
        self.repository = repository

    def _processes_state(self, process_ids: set[int]) -> str:
        system_root = os.environ.get('SystemRoot')
        if not system_root:
            return 'ERROR'
        powershell = Path(system_root) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        script = self.repository / 'scripts/Test-SoraProcess.ps1'
        try:
            result = subprocess.run([str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive',
                                     '-ExecutionPolicy', 'Bypass', '-File', str(script),
                                     '-AppPath', str(self.repository / 'app.py'),
                                     '-OwnerIds', ','.join(str(value) for value in sorted(process_ids)),
                                     '-Port', str(PORT)],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding='utf-8', errors='replace', timeout=20,
                                    env=noncredential_environment(),
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, subprocess.TimeoutExpired):
            return 'ERROR'
        state = result.stdout.strip()
        return state if result.returncode == 0 and state in {'SORA', 'UNKNOWN'} else 'ERROR'

    def port_state(self) -> str:
        try:
            # TCP_TABLE_OWNER_PID_LISTENER=3 and TCP_TABLE_OWNER_PID_ALL=5.
            listeners = tcp_owners(PORT, 3)
            all_rows = tcp_owners(PORT, 5)
            if not listeners:
                if all_rows or not port_can_bind(PORT):
                    return 'UNKNOWN'
                return 'FREE'
            if not listeners.issubset(all_rows) or any(row.owner <= 0 for row in listeners):
                return 'UNKNOWN'
            state = self._processes_state({row.owner for row in listeners})
            if state != 'SORA':
                return state
            # The port may have changed while the process command was being inspected.
            return 'SORA' if tcp_owners(PORT, 3) == listeners else 'UNKNOWN'
        except (OSError, PortProbeError, ValueError, AttributeError):
            return 'ERROR'

    def open_existing(self):
        try:
            return webbrowser.open(URL)
        except Exception:
            return False

    def start(self, env_reference: str | None) -> int:
        previous_reference = os.environ.get('SORA_SP_API_ENV')
        if env_reference:
            # This is only the existing file reference; never open or log its contents.
            os.environ['SORA_SP_API_ENV'] = env_reference
        try:
            return subprocess.call([sys.executable, '-m', 'streamlit', 'run',
                                    str(self.repository / 'app.py'), '--server.port', str(PORT),
                                    '--server.headless', 'false', '--server.showEmailPrompt', 'false',
                                    '--browser.gatherUsageStats', 'false'],
                                   cwd=self.repository)
        except OSError:
            print('Soraを起動できませんでした。Python環境を確認してください。')
            return 1
        finally:
            if env_reference:
                if previous_reference is None:
                    os.environ.pop('SORA_SP_API_ENV', None)
                else:
                    os.environ['SORA_SP_API_ENV'] = previous_reference


def handle_busy(state: str, journal: Journal, before: str | None, runtime) -> int:
    if state == 'SORA':
        journal.append(UpdateResult(before, before, 'Soraがすでに起動中のため更新しません'))
        print('Soraはすでに起動中です。ブラウザで画面を開きます。')
        if not runtime.open_existing():
            print('ブラウザを開けませんでした。http://localhost:8510 を開いてください。')
            return 1
        return 0
    reason = '8510の使用状況を確認できないため、更新・起動しません'
    journal.append(UpdateResult(before, before, reason))
    print(reason + '。ほかのアプリは停止しません。')
    return 1


def run_launcher(repository: Path, journal_directory: Path, env_reference: str | None, runtime) -> int:
    try:
        journal = Journal(journal_directory, repository)
    except OSError:
        print('正式版フォルダ外の起動記録を用意できないため、更新・起動しません。')
        return 1
    git = Git(repository)
    before = git.head()
    state = runtime.port_state()
    if state != 'FREE':
        return handle_busy(state, journal, before, runtime)
    if not env_reference and not os.environ.get('SORA_SP_API_ENV'):
        reason = 'Sora専用の設定ファイル参照がないため、更新・起動しません'
        journal.append(UpdateResult(before, before, reason))
        print(reason + '。')
        return 1
    try:
        with launch_lock(journal.directory):
            # Recheck after obtaining the lock; a second double-click cannot update a running app.
            state = runtime.port_state()
            if state != 'FREE':
                return handle_busy(state, journal, git.head(), runtime)
            before = git.head()
            if journal.append(UpdateResult(before, before, '更新前の確認を開始')):
                result = update_checkout(repository, runtime.port_state)
                if not journal.append(result):
                    print('更新の結果を記録できませんでした。')
            else:
                result = UpdateResult(before, before, '記録できないため更新しません')
            print(result.reason + '。')
            if not result.start_allowed:
                print('更新後の状態が不明なため、Soraを起動しません。')
                return 1
            state = runtime.port_state()
            if state != 'FREE':
                return handle_busy(state, journal, git.head(), runtime)
            print('現在の版でSoraを起動します。')
            return runtime.start(env_reference)
    except LockBusy:
        state = runtime.port_state()
        if state == 'SORA':
            return handle_busy(state, journal, git.head(), runtime)
        journal.append(UpdateResult(before, git.head(), '別の起動処理が進行中のため更新しません'))
        print('別のSora起動処理が進行中です。終了するまでお待ちください。')
        return 1
    except OSError:
        print('起動処理の同時実行を確認できないため、更新・起動しません。')
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description='Soraを起動します。')
    parser.add_argument('--sp-api-env', help='既存の設定ファイル参照（内容は読みません）')
    arguments = parser.parse_args()
    local_data = os.environ.get('LOCALAPPDATA')
    if not local_data:
        print('起動記録の保存先が分からないため、更新・起動しません。')
        return 1
    repository = Path(__file__).resolve().parent.parent
    return run_launcher(repository, Path(local_data) / 'Sora', arguments.sp_api_env,
                        WindowsRuntime(repository))


if __name__ == '__main__':
    raise SystemExit(main())
