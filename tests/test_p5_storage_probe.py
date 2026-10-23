"""Offline probe cleanup fixtures; no P5 roots, ACLs, credentials or live I/O."""
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from modules.p5_runtime import P5Stopped
from modules.p5_windows import WindowsStorage


@pytest.fixture
def probe(tmp_path, monkeypatch):
    locked = False

    def locking(fd, action, size):
        nonlocal locked
        if action == 2:
            if locked:
                raise OSError('SYNTHETIC_LOCKED')
            locked = True
        else:
            locked = False

    monkeypatch.setitem(sys.modules, 'msvcrt', SimpleNamespace(
        locking=locking, LK_NBLCK=2, LK_UNLCK=0))
    # OS preflight is synthetic here. The real API0 Windows probe is separate.
    checks = []
    fixture = SimpleNamespace(setup=lambda: SimpleNamespace(check=checks.append))
    return lambda: WindowsStorage.probe(fixture, tmp_path), checks


def instrument_connection(monkeypatch, *, fail_insert=False, on_close=lambda: None):
    original = sqlite3.connect
    connections = []
    closed = []

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if fail_insert and sql.startswith('INSERT'):
                raise sqlite3.OperationalError('SYNTHETIC_TRANSACTION_FAILURE')
            return super().execute(sql, *args, **kwargs)

        def close(self):
            super().close()
            closed.append(self)
            on_close()

    def connect(*args, **kwargs):
        conn = original(*args, factory=ObservedConnection, **kwargs)
        connections.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, 'connect', connect)
    return connections, closed


def test_success_closes_sqlite_before_unlink_and_removes_only_own_probe(tmp_path, monkeypatch, probe):
    connections, closed = instrument_connection(monkeypatch)
    original_unlink = Path.unlink
    deleted = []

    def unlink(path, *args, **kwargs):
        assert closed == connections and len(closed) == 1
        deleted.append(path.name)
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'unlink', unlink)
    run, checks = probe
    assert run() == dict.fromkeys(('create', 'read', 'fsync', 'rename', 'exclusive_lock', 'sqlite_transaction'), True)
    assert checks == [tmp_path]
    assert deleted == ['second', 'probe.sqlite3']
    assert list(tmp_path.iterdir()) == []


def test_transaction_failure_closes_db_and_retains_probe_files(tmp_path, monkeypatch, probe):
    connections, closed = instrument_connection(monkeypatch, fail_insert=True)
    run, _ = probe
    with pytest.raises(P5Stopped, match='P5_STORAGE_PROBE_FAILED'):
        run()
    assert closed == connections and len(closed) == 1
    directory, = tmp_path.iterdir()
    assert {p.name for p in directory.iterdir()} == {'second', 'probe.sqlite3'}
    with pytest.raises(sqlite3.ProgrammingError):
        connections[0].execute('SELECT 1')


@pytest.mark.parametrize('change', ['extra', 'replacement', 'directory'])
def test_uncertain_residue_is_preserved_before_any_unlink(tmp_path, monkeypatch, probe, change):
    def change_after_close():
        directory, = tmp_path.glob('probe*')
        if change == 'extra':
            (directory / 'unexpected').write_bytes(b'SYNTHETIC_RETAIN')
        elif change == 'replacement':
            replacement = tmp_path / 'replacement'
            replacement.write_bytes(b'SYNTHETIC_RETAIN')
            replacement.replace(directory / 'second')
        else:
            directory.rename(tmp_path / 'retained')
            directory.mkdir()

    instrument_connection(monkeypatch, on_close=change_after_close)
    monkeypatch.setattr(Path, 'unlink', lambda *args, **kwargs: pytest.fail('uncertain residue deleted'))
    run, _ = probe
    with pytest.raises(P5Stopped, match='P5_STORAGE_PROBE_FAILED'):
        run()
    if change == 'directory':
        assert {p.name for p in (tmp_path / 'retained').iterdir()} == {'second', 'probe.sqlite3'}
    else:
        directory, = tmp_path.glob('probe*')
        assert (directory / 'probe.sqlite3').exists() and (directory / 'second').exists()
        if change == 'extra':
            assert (directory / 'unexpected').read_bytes() == b'SYNTHETIC_RETAIN'
        else:
            assert (directory / 'second').read_bytes() == b'SYNTHETIC_RETAIN'


def test_cleanup_failure_stops_and_retains_remaining_files(tmp_path, monkeypatch, probe):
    instrument_connection(monkeypatch)
    original_unlink = Path.unlink
    attempts = []

    def unlink(path, *args, **kwargs):
        attempts.append(path.name)
        if path.name == 'probe.sqlite3':
            raise PermissionError('SYNTHETIC_CLEANUP_FAILURE')
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'unlink', unlink)
    run, _ = probe
    with pytest.raises(P5Stopped, match='P5_STORAGE_PROBE_FAILED'):
        run()
    assert attempts == ['second', 'probe.sqlite3']
    directory, = tmp_path.iterdir()
    assert {p.name for p in directory.iterdir()} == {'probe.sqlite3'}
