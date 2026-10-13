"""Long-lived SG business records, separate from API grants/ledgers/claims."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3

from modules.sg_beta_facts import digest

STATES = ('WAITING', 'AWAITING_LISTING', 'LISTED', 'ERROR', 'RECHECK')
SCHEMA = 'SG_INITIAL_BETA_WORK_V1'


class SGWorkError(ValueError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


class SGWorkStore:
    """Opening never initializes/repairs a file. Explicit create is new-file only."""

    @classmethod
    def create(cls, path, *, shop_id):
        path = Path(path).resolve()
        if not isinstance(shop_id, str) or not shop_id.strip():
            raise SGWorkError('One explicit SG shop required')
        path.parent.mkdir(parents=True, exist_ok=True)
        # O_EXCL also protects legacy databases and a concurrent creator.
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            with sqlite3.connect(path) as conn:
                conn.executescript('''
                    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE products (
                        asin TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                        state TEXT NOT NULL CHECK(state IN
                          ('WAITING','AWAITING_LISTING','LISTED','ERROR','RECHECK')),
                        payload TEXT NOT NULL, checksum TEXT NOT NULL);
                    CREATE TABLE events (
                        event_id INTEGER PRIMARY KEY, asin TEXT NOT NULL,
                        revision INTEGER NOT NULL, action TEXT NOT NULL,
                        created_at TEXT NOT NULL, payload TEXT NOT NULL);
                    CREATE TABLE copy_operations (
                        operation_id TEXT PRIMARY KEY, state TEXT NOT NULL,
                        payload TEXT NOT NULL, checksum TEXT NOT NULL);
                    CREATE TABLE copy_locks (
                        asin TEXT PRIMARY KEY REFERENCES products(asin),
                        operation_id TEXT NOT NULL REFERENCES copy_operations(operation_id));
                ''')
                conn.executemany('INSERT INTO meta VALUES (?,?)',
                                 [('schema', SCHEMA), ('marketplace', 'SG'), ('shop_id', shop_id)])
        except Exception:
            # A failed creation stays visible for explicit recovery; never repair.
            raise SGWorkError('Work database creation failed; do not reuse the partial file') from None
        return cls(path, shop_id=shop_id)

    def __init__(self, path, *, shop_id):
        self.path = Path(path).resolve()
        self.shop_id = shop_id
        with self.transaction() as conn:
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise SGWorkError('Work database integrity failed')
            meta = dict(conn.execute('SELECT key,value FROM meta'))
            if meta != {'schema': SCHEMA, 'marketplace': 'SG', 'shop_id': shop_id}:
                raise SGWorkError('Dedicated SG work database/shop mismatch')
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
            yield conn
            conn.commit()
        except (sqlite3.Error, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            if conn is not None:
                conn.rollback()
            raise SGWorkError('SG work records could not be saved/read; operation stopped') from exc
        except Exception:
            if conn is not None:
                conn.rollback()
            raise
        finally:
            if conn is not None:
                conn.close()

    def read_all(self, conn):
        if dict(conn.execute('SELECT key,value FROM meta')) != {
                'schema': SCHEMA, 'marketplace': 'SG', 'shop_id': self.shop_id}:
            raise SGWorkError('Work database identity changed')
        self._validate_operations(conn)
        values = {}
        for row in conn.execute('SELECT * FROM products ORDER BY asin'):
            value = json.loads(row['payload'])
            if digest({'payload': value, 'state': row['state'], 'revision': row['revision']}) != row['checksum'] or value.get('asin') != row['asin']:
                raise SGWorkError('Work record checksum/identity mismatch')
            values[row['asin']] = {**value, 'revision': row['revision'], 'state': row['state']}
        return values

    def write(self, conn, value, *, action, expected_revision=None):
        value = dict(value)
        asin = value['asin']
        previous = conn.execute('SELECT revision FROM products WHERE asin=?', (asin,)).fetchone()
        revision = previous['revision'] if previous else 0
        if expected_revision is not None and revision != expected_revision:
            raise SGWorkError('Product changed; reopen the selection before acting')
        state = value.pop('state')
        value.pop('revision', None)
        if state not in STATES:
            raise SGWorkError('Invalid listing state')
        conn.execute('''INSERT INTO products VALUES (?,?,?,?,?)
                        ON CONFLICT(asin) DO UPDATE SET revision=excluded.revision,
                        state=excluded.state,payload=excluded.payload,checksum=excluded.checksum''',
                     (asin, revision + 1, state, encode(value),
                      digest({'payload': value, 'state': state, 'revision': revision + 1})))
        conn.execute('INSERT INTO events(asin,revision,action,created_at,payload) VALUES (?,?,?,?,?)',
                     (asin, revision + 1, action, timestamp(), encode({**value, 'state': state})))

    def products(self):
        with self.transaction() as conn:
            return tuple(self.read_all(conn).values())

    def history(self, asin=None):
        with self.transaction() as conn:
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
        for row in conn.execute('SELECT * FROM copy_operations'):
            payload = json.loads(row['payload'])
            if (digest({'payload': payload, 'state': row['state']}) != row['checksum']
                    or row['state'] not in {'PENDING', 'UNKNOWN', 'SUCCESS', 'FAILED', 'CANCELLED'}):
                raise SGWorkError('Copy operation record is damaged')
            if row['state'] in {'PENDING', 'UNKNOWN'}:
                expected.update((a, row['operation_id']) for a in payload['asins'])
        actual = {(r['asin'], r['operation_id']) for r in conn.execute('SELECT * FROM copy_locks')}
        if actual != expected:
            raise SGWorkError('Pending copy lock records are missing or inconsistent')
