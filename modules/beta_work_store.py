"""Long-lived market-bound business records, separate from API grants/ledgers/claims."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import re
from uuid import uuid4

from modules.sg_beta_facts import digest

STATES = ('WAITING', 'AWAITING_LISTING', 'LISTED', 'ERROR', 'RECHECK')
SCHEMA = 'PH_SG_BETA_WORK_V2'


class WorkStoreError(ValueError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


class BetaWorkStore:
    """Opening never initializes/repairs a file. Explicit create is new-file only."""

    SCHEMA = SCHEMA
    AUDIT_EVENTS = True

    @classmethod
    def create(cls, path, *, marketplace, shop_id):
        path = Path(path).resolve()
        if not isinstance(marketplace, str) or marketplace not in {'PH', 'SG'} or not isinstance(shop_id, str) or not shop_id.strip():
            raise WorkStoreError('Explicit PH/SG marketplace and shop required')
        path.parent.mkdir(parents=True, exist_ok=True)
        # O_EXCL also protects legacy databases and a concurrent creator.
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            with sqlite3.connect(path) as conn:
                conn.executescript(f'''
                    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE products (
                        asin TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                        state TEXT NOT NULL CHECK(state IN
                          ('WAITING','AWAITING_LISTING','LISTED','ERROR','RECHECK')),
                        payload TEXT NOT NULL, checksum TEXT NOT NULL);
                    CREATE TABLE events (
                        event_id INTEGER PRIMARY KEY, asin TEXT NOT NULL,
                        revision INTEGER NOT NULL, action TEXT NOT NULL,
                        created_at TEXT NOT NULL, payload TEXT NOT NULL{', checksum TEXT NOT NULL' if cls.AUDIT_EVENTS else ''});
                    CREATE TABLE copy_operations (
                        operation_id TEXT PRIMARY KEY, state TEXT NOT NULL,
                        payload TEXT NOT NULL, checksum TEXT NOT NULL);
                    CREATE TABLE copy_locks (
                        asin TEXT PRIMARY KEY REFERENCES products(asin),
                        operation_id TEXT NOT NULL REFERENCES copy_operations(operation_id));
                ''')
                identity = [('schema', cls.SCHEMA), ('marketplace', marketplace), ('shop_id', shop_id)]
                if cls.AUDIT_EVENTS:
                    identity.append(('store_id', uuid4().hex))
                conn.executemany('INSERT INTO meta VALUES (?,?)', identity)
        except Exception:
            # A failed creation stays visible for explicit recovery; never repair.
            raise WorkStoreError('Work database creation failed; do not reuse the partial file') from None
        return cls(path, marketplace=marketplace, shop_id=shop_id)

    def __init__(self, path, *, marketplace, shop_id):
        self.path = Path(path).resolve()
        if not isinstance(marketplace, str) or marketplace not in {'PH', 'SG'} or not isinstance(shop_id, str) or not shop_id.strip():
            raise WorkStoreError('Explicit PH/SG marketplace and shop required')
        self.marketplace, self.shop_id = marketplace, shop_id
        self.store_id = None
        with self.transaction() as conn:
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise WorkStoreError('Work database integrity failed')
            # Validate reads at open too; corrupted records cannot disappear.
            self.read_all(conn)

    @contextmanager
    def transaction(self):
        conn = None
        try:
            conn = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('BEGIN IMMEDIATE')
            if self.AUDIT_EVENTS:
                self.read_all(conn)
            yield conn
            if self.AUDIT_EVENTS:
                self.read_all(conn)
            conn.commit()
        except WorkStoreError:
            if conn is not None:
                conn.rollback()
            raise
        except (sqlite3.Error, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            if conn is not None:
                conn.rollback()
            raise WorkStoreError('Work records could not be saved/read; operation stopped') from exc
        except Exception:
            if conn is not None:
                conn.rollback()
            raise
        finally:
            if conn is not None:
                conn.close()

    def read_all(self, conn):
        meta = dict(conn.execute('SELECT key,value FROM meta'))
        expected = {'schema': self.SCHEMA, 'marketplace': self.marketplace, 'shop_id': self.shop_id}
        if self.AUDIT_EVENTS:
            store_id = meta.get('store_id')
            if not isinstance(store_id, str) or not re.fullmatch(r'[0-9a-f]{32}', store_id):
                raise WorkStoreError('Dedicated work database identity missing')
            expected['store_id'] = self.store_id or store_id
        if meta != expected:
            raise WorkStoreError('Work database identity changed')
        if self.AUDIT_EVENTS:
            self.store_id = expected['store_id']
        if self.AUDIT_EVENTS:
            self._validate_layout(conn)
        self._validate_operations(conn)
        values = {}
        for row in conn.execute('SELECT * FROM products ORDER BY asin'):
            value = json.loads(row['payload'])
            if self.AUDIT_EVENTS and (row['state'] not in STATES or type(row['revision']) is not int
                    or row['revision'] < 1 or not re.fullmatch(r'[A-Z0-9]{10}', row['asin'])
                    or value.get('marketplace') != self.marketplace or value.get('shop_id') != self.shop_id):
                raise WorkStoreError('Work product scope/state/revision invalid')
            if digest({'payload': value, 'state': row['state'], 'revision': row['revision']}) != row['checksum'] or value.get('asin') != row['asin']:
                raise WorkStoreError('Work record checksum/identity mismatch')
            values[row['asin']] = {**value, 'revision': row['revision'], 'state': row['state']}
        if self.AUDIT_EVENTS:
            self._validate_history(conn, values)
        return values

    def write(self, conn, value, *, action, expected_revision=None):
        if self.AUDIT_EVENTS and (type(expected_revision) is not int or expected_revision < 0):
            raise WorkStoreError('Explicit expected product revision required')
        value = dict(value)
        asin = value['asin']
        previous = conn.execute('SELECT revision FROM products WHERE asin=?', (asin,)).fetchone()
        revision = previous['revision'] if previous else 0
        if expected_revision is not None and revision != expected_revision:
            raise WorkStoreError('Product changed; reopen the selection before acting')
        state = value.pop('state')
        value.pop('revision', None)
        if state not in STATES:
            raise WorkStoreError('Invalid listing state')
        conn.execute('''INSERT INTO products VALUES (?,?,?,?,?)
                        ON CONFLICT(asin) DO UPDATE SET revision=excluded.revision,
                        state=excluded.state,payload=excluded.payload,checksum=excluded.checksum''',
                     (asin, revision + 1, state, encode(value),
                      digest({'payload': value, 'state': state, 'revision': revision + 1})))
        event = (asin, revision + 1, action, timestamp(), encode({**value, 'state': state}))
        if self.AUDIT_EVENTS:
            conn.execute('INSERT INTO events(asin,revision,action,created_at,payload,checksum) VALUES (?,?,?,?,?,?)',
                         (*event, digest(event)))
        else:
            conn.execute('INSERT INTO events(asin,revision,action,created_at,payload) VALUES (?,?,?,?,?)', event)

    def products(self):
        with self.transaction() as conn:
            return tuple(self.read_all(conn).values())

    def history(self, asin=None):
        with self.transaction() as conn:
            self.read_all(conn)
            rows = conn.execute('SELECT * FROM events WHERE (? IS NULL OR asin=?) ORDER BY event_id',
                                (asin, asin))
            return tuple(dict(row) for row in rows)

    def operations(self):
        with self.transaction() as conn:
            self._validate_operations(conn)
            result = []
            for row in conn.execute('SELECT * FROM copy_operations'):
                payload = json.loads(row['payload'])
                result.append({'operation_id': row['operation_id'], 'state': row['state'], **payload})
            return tuple(result)

    def _validate_operations(self, conn):
        expected = set()
        products = {r['asin'] for r in conn.execute('SELECT asin FROM products')}
        for row in conn.execute('SELECT * FROM copy_operations'):
            payload = json.loads(row['payload'])
            if (digest({'payload': payload, 'state': row['state']}) != row['checksum']
                    or row['state'] not in {'PENDING', 'UNKNOWN', 'SUCCESS', 'FAILED', 'CANCELLED'}):
                raise WorkStoreError('Copy operation record is damaged')
            asins = payload.get('asins')
            if (not isinstance(asins, list) or not asins or any(not isinstance(a, str) for a in asins)
                    or len(set(asins)) != len(asins) or not set(asins) <= products
                    or not isinstance(payload.get('basis'), dict) or set(payload['basis']) != set(asins)):
                raise WorkStoreError('Copy operation product binding invalid')
            if self.AUDIT_EVENTS and (payload.get('marketplace') != self.marketplace
                    or payload.get('shop_id') != self.shop_id
                    or not isinstance(payload.get('revisions'), dict)
                    or set(payload['revisions']) != set(asins)
                    or any(type(r) is not int or r < 1 for r in payload['revisions'].values())):
                raise WorkStoreError('Copy operation scope/revision invalid')
            if row['state'] in {'PENDING', 'UNKNOWN'}:
                expected.update((a, row['operation_id']) for a in payload['asins'])
        actual = {(r['asin'], r['operation_id']) for r in conn.execute('SELECT * FROM copy_locks')}
        if (actual != expected or len(expected) != len({a for a, _ in expected})
                or conn.execute('SELECT COUNT(*) FROM copy_locks').fetchone()[0] != len(actual)):
            raise WorkStoreError('Pending copy lock records are missing or inconsistent')

    def _validate_layout(self, conn):
        expected = {
            'meta': ('key', 'value'),
            'products': ('asin', 'revision', 'state', 'payload', 'checksum'),
            'events': ('event_id', 'asin', 'revision', 'action', 'created_at', 'payload', 'checksum'),
            'copy_operations': ('operation_id', 'state', 'payload', 'checksum'),
            'copy_locks': ('asin', 'operation_id'),
        }
        tables = {r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables != set(expected) or conn.execute('PRAGMA foreign_key_check').fetchone():
            raise WorkStoreError('Work database schema/integrity mismatch')
        for table, columns in expected.items():
            if tuple(r['name'] for r in conn.execute(f'PRAGMA table_info({table})')) != columns:
                raise WorkStoreError('Work database schema mismatch; migration prohibited')

    def _validate_history(self, conn, values):
        revisions, latest = {}, {}
        operations = {}
        for row in conn.execute('SELECT * FROM events ORDER BY event_id'):
            event = tuple(row[k] for k in ('asin', 'revision', 'action', 'created_at', 'payload'))
            if (row['checksum'] != digest(event) or row['asin'] not in values
                    or row['revision'] != revisions.get(row['asin'], 0) + 1):
                raise WorkStoreError('Work history damaged or missing')
            revisions[row['asin']] = row['revision']
            latest[row['asin']] = json.loads(row['payload'])
            if row['action'].startswith('COPY_'):
                note = latest[row['asin']]['notes'][-1]
                operation_id = note['operation_id']
                outcome = 'PENDING' if row['action'] == 'COPY_INTENT' else row['action'][5:]
                if note['kind'] != 'SUBMISSION' or note['result'] != outcome:
                    raise WorkStoreError('Submission history/result mismatch')
                operations.setdefault(operation_id, {})[row['asin']] = outcome
        for asin, value in values.items():
            if (revisions.get(asin) != value['revision']
                    or latest.get(asin) != {k: v for k, v in value.items() if k != 'revision'}):
                raise WorkStoreError('Work history/product mismatch')
        saved = {r['operation_id']: r for r in conn.execute('SELECT * FROM copy_operations')}
        if set(saved) != set(operations):
            raise WorkStoreError('Submission history/reservation missing')
        for operation_id, outcomes in operations.items():
            row = saved[operation_id]
            if (set(json.loads(row['payload'])['asins']) != set(outcomes)
                    or set(outcomes.values()) != {row['state']}):
                raise WorkStoreError('Submission history/reservation mismatch')
