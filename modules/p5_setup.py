"""P5-only explicit setup/checkpoint/isolated recovery; no default OS paths.

Platform inspection and ACL/probe execution are injected by a trusted installer.
Unknown observations fail closed. Constructors/imports do not touch storage.
Synthetic tests exercise this contract without operational installation.
"""
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3

from modules.beta_work_store import BetaWorkStore
from modules.cache import KeepaCache
from modules.p5_runtime import P5Stopped, initialize_p5_ledger
from modules.sg_continuous_runtime import _digest


GiB = 1024 ** 3


@dataclass(frozen=True)
class StorageObservation:
    canonical: str
    volume: str
    filesystem: str
    fixed: bool
    ancestors_unaliased: bool  # includes reparse/junction/UNC/SUBST inspection
    isolated: bool  # canonical + volume/file identities against protected roots
    identities: tuple
    acl_principals: frozenset
    acl_inheritance_disabled: bool
    free_bytes: int
    c_free_bytes: int
    run_bytes: int


def preflight(path, observation, *, expected_volume, operator, required_bytes, require_acl=True):
    target = Path(path)
    allowed = frozenset({operator, 'SYSTEM', 'Administrators'})
    o = observation
    if (type(o) is not StorageObservation or not target.is_absolute()
            or str(target.resolve()) != o.canonical or not expected_volume or o.volume != expected_volume
            or o.filesystem != 'NTFS' or o.fixed is not True
            or o.ancestors_unaliased is not True or o.isolated is not True
            or not o.identities or len(set(o.identities)) != len(o.identities)
            or not operator or (require_acl and
                (o.acl_principals != allowed or o.acl_inheritance_disabled is not True))):
        raise P5Stopped('P5_STORAGE_IDENTITY_ACL_UNVERIFIED')
    if (any(type(v) is not int or v < 0 for v in (o.free_bytes, o.c_free_bytes, o.run_bytes, required_bytes))
            or o.free_bytes < 10 * GiB or o.c_free_bytes < 2 * GiB or o.run_bytes >= 10 * GiB
            or o.free_bytes <= required_bytes):
        raise P5Stopped('P5_STORAGE_CAPACITY_STOP')
    return {'warning': o.free_bytes < 20 * GiB or o.run_bytes >= 5 * GiB,
            'same_volume_backup_is_media_protection': False}


class P5Setup:
    def __init__(self, *, inspect, set_acl, probe, expected_volume, operator):
        self.inspect, self.set_acl, self.probe = inspect, set_acl, probe
        self.expected_volume, self.operator = expected_volume, operator

    def check(self, path, *, required_bytes=0):
        return preflight(path, self.inspect(Path(path)), expected_volume=self.expected_volume,
                         operator=self.operator, required_bytes=required_bytes)

    def check_new(self, path, *, required_bytes):
        # No target ACL exists yet. Volume/ancestors/isolation/capacity are
        # mandatory here; the full ACL check follows exclusive creation.
        path = Path(path)
        if path.exists() or path.is_symlink():
            raise FileExistsError('P5_NEW_STORAGE_REQUIRED')
        return preflight(path, self.inspect(path), expected_volume=self.expected_volume,
            operator=self.operator, required_bytes=required_bytes, require_acl=False)

    def create_new(self, path, *, required_bytes):
        self.check_new(path, required_bytes=required_bytes)
        missing = []
        parent = Path(path)
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        # Never adopt a directory concurrently created by another installer.
        for directory in reversed(missing):
            self.check_new(directory, required_bytes=required_bytes)
            directory.mkdir(exist_ok=False)
            self.set_acl(directory)
            self.check(directory, required_bytes=required_bytes)

    def install(self, template, *, required_bytes):
        template.validate_new_install()
        if not template.preparation_limit:
            raise P5Stopped('P5_TWO_STAGE_SCOPE_REQUIRED')
        directory = template.directory
        self.create_new(directory, required_bytes=required_bytes)
        result = self.probe(directory)
        if (not isinstance(result, dict) or set(result) !=
                {'create', 'read', 'fsync', 'rename', 'exclusive_lock', 'sqlite_transaction'}
                or any(v is not True for v in result.values())):
            raise P5Stopped('P5_STORAGE_PROBE_FAILED')
        store = BetaWorkStore.create(directory / 'work.sqlite3',
                                     marketplace=template.marketplace, shop_id=template.shop_id)
        scope = replace(template, store_id=store.store_id)
        scope.validate()
        KeepaCache(directory / 'keepa.sqlite3')
        initialize_p5_ledger(scope, material_updates=True)
        for name in ('inputs', 'evidence', 'exports', 'backups'):
            (directory / name).mkdir()
        self.check(directory, required_bytes=required_bytes)
        return scope  # installation creates no permit/credential/runtime


def _write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as file:
        json.dump(value, file, sort_keys=True)
        file.flush()
        os.fsync(file.fileno())


def _hash(path):
    h = sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _db_summary(path):
    with sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True) as conn:
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise P5Stopped('P5_BACKUP_INTEGRITY_FAILED')
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {t: conn.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
                  for t in ('products', 'events', 'copy_operations', 'copy_locks') if t in tables}
        return {'counts': counts, 'meta': dict(conn.execute('SELECT key,value FROM meta')) if 'meta' in tables else {}}


def checkpoint(runtime, *, setup, checkpoint_id, required_bytes):
    if (not checkpoint_id or not checkpoint_id.isalnum() or runtime._material_action is not None):
        raise P5Stopped('P5_CHECKPOINT_QUIESCENCE_REQUIRED')
    with runtime.ledger._lock:
        runtime.ledger.require_current()
        if any(r['state'] == 'RESERVED' for r in runtime.ledger.data['reservations']):
            raise P5Stopped('P5_CHECKPOINT_INFLIGHT_SEND')
        footprint = sum((runtime.scope.directory / n).stat().st_size for n in
                        ('work.sqlite3', 'keepa.sqlite3', 'ledger.json', 'claim.json'))
        if required_bytes < footprint * 3:
            raise P5Stopped('P5_CHECKPOINT_CAPACITY_PLAN_INSUFFICIENT')
        setup.check(runtime.scope.directory, required_bytes=required_bytes)
        target = runtime.scope.directory / 'backups' / checkpoint_id
        if target.resolve().parent != (runtime.scope.directory / 'backups').resolve():
            raise P5Stopped('P5_BACKUP_PATH_REFUSED')
        # Inspector must allow intended same-shop backup and reject aliases.
        setup.create_new(target, required_bytes=required_bytes)
        with runtime._store.transaction():
            for name in ('work.sqlite3', 'keepa.sqlite3'):
                source_path = runtime.scope.directory / name
                output_path = target / name
                with output_path.open('xb'):
                    pass
                with sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True) as source:
                    with sqlite3.connect(output_path) as destination:
                        source.backup(destination)
            for name in ('ledger.json', 'claim.json'):
                with (target / name).open('xb') as output:
                    output.write((runtime.scope.directory / name).read_bytes())
                    output.flush()
                    os.fsync(output.fileno())
            summaries = {name: _db_summary(target / name) for name in ('work.sqlite3', 'keepa.sqlite3')}
            manifest = {'version': 1, 'scope': runtime.scope.digest, 'store_id': runtime.scope.store_id,
                'marketplace': runtime.scope.marketplace, 'shop_id': runtime.scope.shop_id,
                'files': {p.name: _hash(p) for p in target.iterdir()}, 'databases': summaries,
                'reservations': runtime.ledger.data['reservations'],
                'material_updates': runtime.ledger.data.get('material_updates'),
                'media_failure_protected': False}
            _write_new(target / 'manifest.json', {**manifest, 'checksum': _digest(manifest)})
        return target


def restore_isolated(backup, destination, *, latest_ledger, setup, required_bytes):
    backup, destination = Path(backup), Path(destination)
    setup.check(backup, required_bytes=required_bytes)
    setup.check_new(destination, required_bytes=required_bytes)
    manifest = json.loads((backup / 'manifest.json').read_text('utf-8'))
    payload = {k: v for k, v in manifest.items() if k != 'checksum'}
    if manifest.get('checksum') != _digest(payload) or set(manifest['files']) != {
            'work.sqlite3', 'keepa.sqlite3', 'ledger.json', 'claim.json'}:
        raise P5Stopped('P5_BACKUP_MANIFEST_INVALID')
    for name, expected in manifest['files'].items():
        if _hash(backup / name) != expected:
            raise P5Stopped('P5_BACKUP_SHA_MISMATCH')
    saved = json.loads((backup / 'ledger.json').read_text('utf-8'))
    current = json.loads(Path(latest_ledger).read_text('utf-8'))
    if current != saved:
        raise P5Stopped('P5_BACKUP_BUDGET_ROLLBACK_OR_UNKNOWN')
    if (saved['checksum'] != _digest({k:v for k,v in saved.items() if k != 'checksum'})
            or saved['grant_digest'] != manifest['scope']
            or json.loads((backup / 'claim.json').read_text('utf-8')) != {'scope_digest': manifest['scope']}):
        raise P5Stopped('P5_BACKUP_SCOPE_MISMATCH')
    for name, expected in manifest['databases'].items():
        if _db_summary(backup / name) != expected:
            raise P5Stopped('P5_BACKUP_HISTORY_MISMATCH')
    meta = manifest['databases']['work.sqlite3']['meta']
    if any(meta.get(k) != manifest[k] for k in ('store_id', 'marketplace', 'shop_id')):
        raise P5Stopped('P5_BACKUP_STORE_MISMATCH')
    setup.create_new(destination, required_bytes=required_bytes)
    for name in manifest['files']:
        with (destination / name).open('xb') as output:
            output.write((backup / name).read_bytes())
            output.flush()
            os.fsync(output.fileno())
        if _hash(destination / name) != manifest['files'][name]:
            raise P5Stopped('P5_RESTORE_SHA_MISMATCH')
    for name, expected in manifest['databases'].items():
        if _db_summary(destination / name) != expected:
            raise P5Stopped('P5_RESTORE_INTEGRITY_FAILED')
    # claim remains bound to the original root. Recovery never creates a live
    # runtime, new scope, new budget or permission to swap the original files.
    return {'live_resume_allowed': False, 'scope': manifest['scope'],
            'unresolved_preserved': any(r['state'] != 'COMPLETE' for r in saved['reservations'])}
