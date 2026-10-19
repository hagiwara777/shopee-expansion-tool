"""Windows P5 observations and explicit installer callbacks. Import is inert.

No API, credential, installation, ACL change or probe occurs in constructors.
OS observations are fresh; expected values are operator-bound, never inferred
from the execution ticket being verified.
"""
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from uuid import uuid4

from modules.p5_runtime import P5Stopped
from modules.p5_setup import P5Setup, StorageObservation
from modules.sg_continuous_runtime import _digest


def _windows(action, path=None, operator=None, port=None):
    if sys.platform != 'win32':
        raise P5Stopped('P5_WINDOWS_OBSERVATION_REQUIRED')
    command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
               str(Path(__file__).with_suffix('.ps1')), '-Action', action]
    for name, value in (('Target', path), ('OperatorSid', operator), ('Port', port)):
        if value is not None:
            command.extend(['-' + name, str(value)])
    try:
        result = subprocess.run(command, check=True, capture_output=True, timeout=30)
        return json.loads(result.stdout.decode('utf-8-sig'))
    except Exception:
        raise P5Stopped('P5_WINDOWS_OBSERVATION_FAILED') from None


class WindowsStorage:
    def __init__(self, *, installation_root, protected_paths, operator_sid, expected_volume):
        self.root = Path(installation_root)
        self.protected = tuple(Path(p) for p in protected_paths)
        self.operator = operator_sid
        self.expected_volume = expected_volume

    def _paths(self, path):
        path = Path(path)
        if (not path.is_absolute() or not self.root.is_absolute() or not self.protected
                or not path.is_relative_to(self.root) or any(not p.is_absolute() for p in self.protected)
                or path.drive.upper() != 'D:'):
            raise P5Stopped('P5_STORAGE_PATH_REFUSED')
        canonical = path.resolve()
        identities = []
        # Inspect raw ancestors before resolve can hide a junction/symlink.
        for parent in reversed((path, *path.parents)):
            if parent.exists() or parent.is_symlink():
                stat = parent.lstat()
                if parent.is_symlink() or getattr(stat, 'st_file_attributes', 0) & 0x400:
                    raise P5Stopped('P5_STORAGE_ALIAS_REFUSED')
                identities.append((stat.st_dev, stat.st_ino))
        if len(identities) != len(set(identities)) or not identities:
            raise P5Stopped('P5_STORAGE_IDENTITY_ACL_UNVERIFIED')
        for protected in self.protected:
            other = protected.resolve()
            if canonical.is_relative_to(other) or other.is_relative_to(canonical):
                raise P5Stopped('P5_STORAGE_OVERLAP_REFUSED')
            if other.exists() and (other.stat().st_dev, other.stat().st_ino) in identities:
                raise P5Stopped('P5_STORAGE_OVERLAP_REFUSED')
        return canonical, tuple(identities)

    def inspect(self, path):
        try:
            canonical, identities = self._paths(path)
            data = _windows('Storage', path=path, operator=self.operator)
            # Subtree aliases/hardlinks cannot hide under the canonical root.
            total = 0
            if Path(path).exists():
                for current, directories, files in os.walk(path, followlinks=False):
                    for name in directories + files:
                        item = Path(current) / name
                        stat = item.lstat()
                        if item.is_symlink() or getattr(stat, 'st_file_attributes', 0) & 0x400 or stat.st_nlink > 1 and item.is_file():
                            raise ValueError()
                        total += stat.st_size if item.is_file() else 0
            return StorageObservation(str(canonical), data['volume'], data['filesystem'],
                data['fixed'], data['unaliased'], True, identities,
                frozenset(data['principals']) if data['acl_valid'] else frozenset(),
                data['inheritance_disabled'], data['free_bytes'], data['c_free_bytes'], total)
        except P5Stopped:
            raise
        except Exception:
            raise P5Stopped('P5_STORAGE_IDENTITY_ACL_UNVERIFIED') from None

    def set_acl(self, path):
        self._paths(path)
        if _windows('SetAcl', path=path, operator=self.operator) != {'applied': True}:
            raise P5Stopped('P5_STORAGE_ACL_FAILED')

    def probe(self, path):
        """Explicit install-only create/read/fsync/rename/lock/SQLite probe."""
        import msvcrt
        self.setup().check(path)
        directory = Path(path) / ('probe' + uuid4().hex)
        directory.mkdir(exist_ok=False)
        try:
            first, second = directory / 'first', directory / 'second'
            with first.open('xb') as stream:
                stream.write(b'P5 storage probe')
                stream.flush()
                os.fsync(stream.fileno())
            if first.read_bytes() != b'P5 storage probe':
                raise ValueError()
            first.rename(second)
            with second.open('r+b') as lock:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                try:
                    with second.open('r+b') as other:
                        try:
                            msvcrt.locking(other.fileno(), msvcrt.LK_NBLCK, 1)
                        except OSError:
                            pass
                        else:
                            raise ValueError()
                finally:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            with sqlite3.connect(directory / 'probe.sqlite3') as conn:
                conn.execute('CREATE TABLE probe (value INTEGER)')
                conn.execute('INSERT INTO probe VALUES (1)')
                conn.commit()
                if conn.execute('SELECT value FROM probe').fetchall() != [(1,)]:
                    raise ValueError()
            return dict.fromkeys(('create', 'read', 'fsync', 'rename', 'exclusive_lock', 'sqlite_transaction'), True)
        except Exception:
            raise P5Stopped('P5_STORAGE_PROBE_FAILED') from None
        finally:
            # Only this newly-created probe directory; never recurse/delete data.
            for item in directory.iterdir():
                item.unlink()
            directory.rmdir()

    def setup(self):
        return P5Setup(inspect=self.inspect, set_acl=self.set_acl, probe=self.probe,
                       expected_volume=self.expected_volume, operator=self.operator)


def _command_arguments(command):
    import ctypes
    from ctypes import wintypes
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(wintypes.LPWSTR)
    count = ctypes.c_int()
    args = parse(command, ctypes.byref(count))
    if not args:
        raise ValueError()
    try:
        return [args[i] for i in range(count.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(args, ctypes.c_void_p))


class WindowsP5Observer:
    def __init__(self, *, storage, port, credentials, operations, primary_sources,
                 pricing, required_bytes):
        self.storage, self.port, self.credentials = storage, port, credentials
        self.operations, self.sources, self.pricing = operations, primary_sources, pricing
        self.required_bytes = required_bytes

    def observe(self, scope):
        from modules.p5_live_adapter import P5CodeIdentity
        try:
            process = _windows('Process', port=self.port)
            args = _command_arguments(process['command'])
            # The listener must belong to this exact interpreter/entrypoint.
            if (process['pid'] != os.getpid() or not process['started'] or not process['machine']
                    or process['sid'] != self.storage.operator
                    or Path(process['executable']).resolve() != Path(sys.executable).resolve()
                    or not process['listeners']
                    or any(row['pid'] != os.getpid() or row['address'] not in {'127.0.0.1', '::1'}
                           or row['port'] != self.port for row in process['listeners'])
                    or 'run' not in args
                    or Path(args[args.index('run') + 1]).resolve() != Path(sys.modules['__main__'].__file__).resolve()):
                raise ValueError()
            machine = {k: process[k] for k in ('machine', 'pid', 'started')}
            for name in ('p5_operator', 'p5_windows', 'p5_setup'):
                module = sys.modules['modules.' + name]
                source = Path(__file__).parent / (name + '.py')
                if Path(module.__file__).resolve() != source.resolve():
                    raise ValueError()
                P5CodeIdentity._require_loaded_source(module, source)
            code = P5CodeIdentity().observe()
            self.storage.setup().check(Path(scope.root), required_bytes=self.required_bytes)
            self.storage.setup().check(scope.directory, required_bytes=self.required_bytes)
            observed = self.storage.inspect(scope.directory)
            # Store identity is read from the actual P2 DB, never just scope.
            # Guards also run inside P2's active write transaction. Observation
            # must not acquire a second writer or initialize/repair the store.
            from modules.beta_work_store import BetaWorkStore
            with sqlite3.connect(scope.db_path.as_uri() + '?mode=ro', uri=True) as conn:
                if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError()
                meta = dict(conn.execute('SELECT key,value FROM meta'))
            if any(meta.get(k) != v for k, v in dict(schema=BetaWorkStore.SCHEMA,
                    marketplace=scope.marketplace, shop_id=scope.shop_id, store_id=scope.store_id).items()):
                raise ValueError()
            if self.operations & {'keepa.token', 'keepa.product', 'keepa.query'}:
                token_spec = self.sources.get('keepa.token', {})
                if token_spec.get('verified') is not True or not token_spec.get('body_digest') or not token_spec.get('version'):
                    raise P5Stopped('PRIMARY_SOURCE_UNVERIFIED')
            return dict(repository='1296080967', **code, machine=machine, port=self.port,
                loopback=True, execution_target=_digest(machine | {'port': self.port}),
                storage=dict(root=str(scope.directory), store_id=meta['store_id'], volume=observed.volume,
                    acl=_digest(sorted(observed.acl_principals)), identities=observed.identities, capacity_ok=True),
                credential=self.credentials.describe(scope, self.operations),
                primary_sources=self.sources, pricing=self.pricing, plan=asdict(scope))
        except P5Stopped:
            raise
        except Exception:
            raise P5Stopped('P5_PROCESS_OBSERVATION_MISMATCH') from None
