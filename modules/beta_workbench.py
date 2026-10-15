"""P2 offline PH/SG persistence using the P1 current-evidence contract.

No API, credential lookup, legacy migration, UI or external listing execution.
The store holds history; only the supplied in-memory P1 session grants preparation.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import copy
import csv
from io import StringIO
import json
from uuid import uuid4

from modules.beta_work_store import BetaWorkStore, WorkStoreError, encode, timestamp
from modules.listing_inventory_parser import build_existing_asin_index
from modules.preparation_validity import PreparationSession, PreparationError
from modules.sg_beta_facts import ProductFacts, digest
from modules.sg_beta_workbench import _sources


class BetaWorkBench:
    """Fresh session required on every restart or market/shop switch.

    All selections bind ASIN to revision. Reopening does not accept facts,
    catalogs, classification decisions or official receipts from the database.
    """

    def __init__(self, store: BetaWorkStore, session: PreparationSession):
        if not isinstance(store, BetaWorkStore) or store.SCHEMA != BetaWorkStore.SCHEMA:
            raise WorkStoreError('P2 requires a new dedicated work store; migration prohibited')
        if not isinstance(session, PreparationSession):
            raise WorkStoreError('Current P1 preparation session required')
        self.store, self.session, self.scope = store, session, session.scope
        self._require_scope()
        self.refresh()

    def _require_scope(self):
        if (self.session.scope != self.scope or self.store.marketplace != self.scope.marketplace
                or self.store.shop_id != self.scope.shop_id):
            raise WorkStoreError('Work store/preparation marketplace/shop/session mismatch')

    @contextmanager
    def _transaction(self, *, evidence_revision=None):
        self._require_scope()
        revision = self.session.evidence_revision
        if evidence_revision is not None and evidence_revision != revision:
            raise WorkStoreError('Preparation evidence changed after selection')
        with self.store.transaction() as conn:
            yield conn
            self._require_scope()
            if revision != self.session.evidence_revision:
                raise WorkStoreError('Preparation evidence changed during operation')

    def _matches(self):
        try:
            evidence = self.session.current_inventory()
        except PreparationError:
            return {}, None
        return build_existing_asin_index(evidence.inventories), evidence

    def _assess(self, value):
        result = copy.deepcopy(self.session.assess(value))
        result.setdefault('category_valid', False)
        result.setdefault('brand_valid', False)
        # A missing current context cannot erase previously known Safety stops.
        # They remain recheck reasons, never preparation authority.
        result.setdefault('safety_reasons', copy.deepcopy(value.get('assessment', {}).get('safety_reasons', [])))
        result['reasons'].extend(result['safety_reasons'])
        if value.get('review_pending'):
            result['reasons'].append('HUMAN_REVIEW_UNRESOLVED')
        if value.get('manual_exclude'):
            result['reasons'].append('HUMAN_EXCLUDE')
        if value.get('body_excluded'):
            result['reasons'].append('SG_BODY_EXCLUDE_HISTORY')
        result['reasons'] = list(dict.fromkeys(result['reasons']))
        result['valid'] = not result['reasons']
        result['basis'] = digest({'p1': result.get('basis'), 'pending': value.get('review_pending', False),
                                  'manual_exclude': value.get('manual_exclude', False),
                                  'body_excluded': value.get('body_excluded', False)})
        return result

    @staticmethod
    def _update_assessment(value, result):
        value['assessment'] = result
        value['preparation_state'] = 'READY' if result['valid'] else 'RECHECK'
        progress = value['listing_progress']
        value['state'] = (progress if progress in {'LISTED', 'ERROR'} or result['valid'] else 'RECHECK')

    @staticmethod
    def _note(value, kind, result, note, **extra):
        value['notes'].append({'kind': kind, 'result': result, 'note': note.strip(), 'at': timestamp(), **extra})

    @staticmethod
    def _human(human_confirmed, note):
        if human_confirmed is not True or not isinstance(note, str) or not note.strip():
            raise WorkStoreError('Explicit human confirmation and reason required')

    def _selection(self, conn, expected):
        if not isinstance(expected, dict) or not expected:
            raise WorkStoreError('Select products and their current revisions explicitly')
        values = self.store.read_all(conn)
        selected = []
        for asin, revision in expected.items():
            value = values.get(asin)
            if type(revision) is not int or value is None or value['revision'] != revision:
                raise WorkStoreError('Stale product selection; refresh first')
            selected.append(value)
        return selected

    def ingest(self, records, *, batch_ref, require_review_asins=()):
        """Append a group, preserving other groups and same-product history.

        Input decisions/valid flags are never adopted. An unchanged record in
        this same session may retain its existing confirmation, after P1 checks.
        A changed/new/reopened product needs explicit Category and Brand review.
        """
        records = copy.deepcopy(tuple(records))
        require_review_asins = frozenset(require_review_asins)
        if (not isinstance(batch_ref, str) or not batch_ref.strip() or not records
                or any(not isinstance(r, dict) for r in records)
                or len({r.get('asin') for r in records}) != len(records)):
            raise WorkStoreError('Explicit batch reference and unique nonempty products required')
        if not require_review_asins <= {r.get('asin') for r in records}:
            raise WorkStoreError('Recheck must be limited to incoming products')
        with self._transaction() as conn:
            old = self.store.read_all(conn)
            for record in records:
                scope = record.get('preparation_scope')
                if scope is not None and scope != asdict(self.scope):
                    raise WorkStoreError('Intake marketplace/shop/session mismatch')
                for name, expected in (('marketplace', self.scope.marketplace), ('shop_id', self.scope.shop_id)):
                    if name in record and record[name] != expected:
                        raise WorkStoreError('Intake marketplace/shop mismatch')
                facts = ProductFacts.from_dict(record['facts'])
                candidates, _, _, body = _sources(record)
                if self.scope.marketplace == 'PH' and body:
                    raise WorkStoreError('SG body confirmation cannot be imported into PH')
                rows = [c for c in candidates.rows if c.candidate_asin == facts.asin]
                if (record.get('asin') != facts.asin or len(rows) != 1
                        or facts.fields['title'].value != rows[0].product_title
                        or facts.fields['brand'].value != rows[0].brand):
                    raise WorkStoreError('Intake product/Fact/source mismatch')
                previous = old.get(facts.asin)
                value = {k: copy.deepcopy(record.get(k)) for k in ('asin', 'facts', 'source', 'weapon')}
                value.update(marketplace=self.scope.marketplace, shop_id=self.scope.shop_id,
                    category=None, brand=None, preparation_scope=asdict(self.scope),
                    first_seen_at=previous['first_seen_at'] if previous else timestamp(),
                    amazon_url=rows[0].amazon_url or f'https://www.amazon.co.jp/dp/{facts.asin}',
                    listing_progress=previous['listing_progress'] if previous else 'WAITING',
                    notes=copy.deepcopy(previous['notes']) if previous else [],
                    batches=copy.deepcopy(previous['batches']) if previous else [],
                    revoked=copy.deepcopy(previous['revoked']) if previous else [],
                    review_pending=previous.get('review_pending', False) if previous else False,
                    manual_exclude=previous.get('manual_exclude', False) if previous else False,
                    body_excluded=previous.get('body_excluded', False) if previous else False)
                if self.scope.marketplace == 'SG' and body:
                    value['body_excluded'] |= any(r.get('candidate_asin') == facts.asin
                        and r.get('outcome') == 'BODY_PRESENT' for r in body.get('records', []))
                unchanged = previous and all(previous.get(k) == value.get(k) for k in ('facts', 'source', 'weapon'))
                if (unchanged and previous.get('preparation_scope') == asdict(self.scope)
                        and facts.asin not in require_review_asins):
                    value['category'], value['brand'] = previous['category'], previous['brand']
                elif previous and facts.asin in require_review_asins:
                    self._note(value, 'CLASSIFICATION', 'INVALIDATED', 'Current target Fact must be reviewed again')
                value['batches'].append({'reference': batch_ref.strip(), 'at': timestamp(),
                    'source_type': rows[0].source_type, 'source_id': rows[0].source_id,
                    'source_asin': rows[0].source_asin, 'source_binding': digest(value['source'])})
                self._update_assessment(value, self._assess(value))
                self.store.write(conn, value, action='INGEST', expected_revision=previous['revision'] if previous else 0)
        return self.store.products()

    def refresh(self):
        with self._transaction() as conn:
            matches, evidence = self._matches()
            for value in self.store.read_all(conn).values():
                before = copy.deepcopy(value)
                result = self._assess(value)
                if value['asin'] in matches:
                    value['listing_progress'] = 'LISTED'
                    value['listing_match'] = {'reference': evidence.reference,
                        'scope': asdict(evidence.scope), 'inventory_binding': digest(asdict(evidence)),
                        'matches': [asdict(e) for e in matches[value['asin']]]}
                self._update_assessment(value, result)
                if value != before:
                    self.store.write(conn, value, action='REVALIDATE', expected_revision=value['revision'])
        return self.store.products()

    def prepared_pool(self):
        self.refresh()
        with self._transaction() as conn:
            locks = {r['asin'] for r in conn.execute('SELECT asin FROM copy_locks')}
            current = self.store.read_all(conn)
            return tuple(v for v in current.values() if v['state'] == 'WAITING'
                         and v['asin'] not in locks and self._assess(v)['valid'])

    def confirm(self, expected, *, kind, option_id, human_verified, note, reviewer='operator',
                evidence_revision=None):
        self._human(human_verified, note)
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise WorkStoreError('Reviewer required')
        if kind not in {'CATEGORY', 'BRAND'}:
            raise WorkStoreError('Category or Brand confirmation required')
        with self._transaction(evidence_revision=evidence_revision) as conn:
            for value in self._selection(conn, expected):
                if value.get('preparation_scope') != asdict(self.scope):
                    # Preserve old decisions in history, never rebind them as current.
                    value = self.session.bind_product({k: v for k, v in value.items() if k != 'preparation_scope'})
                if kind == 'CATEGORY':
                    value = self.session.confirm_category(value, option_id, human_verified=True)
                else:
                    value = self.session.confirm_brand(value, option_id, human_verified=True)
                ctx = self.session.classification_context()
                self._note(value, kind, 'CONFIRMED', note, reviewer=reviewer.strip(), authority='HUMAN',
                    catalog_version=ctx.catalog.catalog_version,
                    rule_alias_revision=ctx.classification.revision, catalog_binding=ctx.catalog_binding)
                self._update_assessment(value, self._assess(value))
                self.store.write(conn, value, action='HUMAN_' + kind, expected_revision=value['revision'])

    def revoke(self, expected, *, kind, note, evidence_revision=None):
        self._human(True, note)
        if kind not in {'CATEGORY', 'BRAND'}:
            raise WorkStoreError('Category or Brand cancellation required')
        with self._transaction(evidence_revision=evidence_revision) as conn:
            for value in self._selection(conn, expected):
                value['revoked'].append({'kind': kind, 'decision': copy.deepcopy(value.get(kind.lower())),
                                         'at': timestamp(), 'note': note.strip()})
                value[kind.lower()] = None
                if kind == 'CATEGORY':
                    value['brand'] = None
                self._note(value, kind, 'REVOKED', note)
                self._update_assessment(value, self._assess(value))
                self.store.write(conn, value, action='REVOKE_' + kind, expected_revision=value['revision'])

    def record_review(self, expected, *, result, note, human_confirmed):
        self._human(human_confirmed, note)
        if result not in {'UNRESOLVED', 'EVIDENCE_REVIEWED', 'EXCLUDE'}:
            raise WorkStoreError('Explicit review result required')
        with self._transaction() as conn:
            for value in self._selection(conn, expected):
                value['review_pending'] = result == 'UNRESOLVED'
                if result == 'EXCLUDE':
                    value['manual_exclude'] = True
                self._note(value, 'SAFETY', result, note)
                self._update_assessment(value, self._assess(value))
                self.store.write(conn, value, action='SAFETY_REVIEW', expected_revision=value['revision'])

    def _ready(self, conn, expected):
        values = self._selection(conn, expected)
        bindings = {}
        for value in values:
            current = self._assess(value)
            locked = conn.execute('SELECT 1 FROM copy_locks WHERE asin=?', (value['asin'],)).fetchone()
            if (not current['valid'] or value['state'] != 'WAITING'
                    or value['listing_progress'] != 'WAITING' or locked):
                raise WorkStoreError('Product requires recheck, is listed or has unresolved submission')
            bindings[value['asin']] = current['basis']
        return values, bindings

    def _check_bindings(self, values, bindings):
        self._require_scope()
        for value in values:
            current = self._assess(value)
            if not current['valid'] or current['basis'] != bindings[value['asin']]:
                raise WorkStoreError('Preparation changed before delivering output')

    def output(self, expected, *, reserve_copy=False):
        """Commit output history/reservation before returning offline CSV/TXT.

        A download alone does not confirm submission. reserve_copy must be used
        before a human attempts external submission; UNKNOWN retains the lock.
        """
        if type(reserve_copy) is not bool:
            raise WorkStoreError('Explicit reservation choice required')
        with self._transaction() as conn:
            values, bindings = self._ready(conn, expected)
            csv_bytes, txt_bytes = self.session.output(values)
            self._check_bindings(values, bindings)
            operation_id = uuid4().hex if reserve_copy else None
            if reserve_copy:
                payload = {'asins': list(expected), 'basis': bindings,
                    'revisions': {v['asin']: v['revision'] + 1 for v in values},
                    'marketplace': self.scope.marketplace, 'shop_id': self.scope.shop_id,
                    'session_id': self.scope.session_id, 'created_at': timestamp(), 'note': ''}
                conn.execute('INSERT INTO copy_operations VALUES (?,?,?,?)',
                    (operation_id, 'PENDING', encode(payload), digest({'payload': payload, 'state': 'PENDING'})))
                conn.executemany('INSERT INTO copy_locks VALUES (?,?)', [(a, operation_id) for a in expected])
            for value in values:
                if reserve_copy:
                    self._note(value, 'SUBMISSION', 'PENDING', 'Submission reserved', operation_id=operation_id)
                self.store.write(conn, value, action='COPY_INTENT' if reserve_copy else 'EXPORT',
                                 expected_revision=value['revision'])
            self._check_bindings(values, bindings)
        self._check_bindings(values, bindings)
        return csv_bytes, txt_bytes, operation_id

    def finish_copy(self, operation_id, expected, *, outcome, note, human_confirmed):
        self._human(human_confirmed, note)
        if outcome not in {'SUCCESS', 'UNKNOWN', 'FAILED', 'CANCELLED'}:
            raise WorkStoreError('Explicit submission outcome required')
        with self._transaction() as conn:
            values = self._selection(conn, expected)
            row = conn.execute('SELECT * FROM copy_operations WHERE operation_id=?', (operation_id,)).fetchone()
            if row is None or row['state'] not in {'PENDING', 'UNKNOWN'}:
                raise WorkStoreError('Submission already closed or missing')
            payload = json.loads(row['payload'])
            if set(expected) != set(payload['asins']):
                raise WorkStoreError('Resolve the complete reservation together')
            for value in values:
                if outcome == 'SUCCESS':
                    current = self._assess(value)
                    if (not current['valid'] or current['basis'] != payload['basis'][value['asin']]
                            or payload['session_id'] != self.scope.session_id
                            or payload['revisions'][value['asin']] != value['revision']
                            or value['listing_progress'] != 'WAITING'):
                        raise WorkStoreError('Reserved preparation changed; resolve the unknown result explicitly')
                    value['listing_progress'] = 'AWAITING_LISTING'
                self._note(value, 'SUBMISSION', outcome, note, operation_id=operation_id)
                self._update_assessment(value, self._assess(value))
                self.store.write(conn, value, action='COPY_' + outcome, expected_revision=value['revision'])
                payload['revisions'][value['asin']] = value['revision'] + 1
            payload['note'] = note.strip()
            conn.execute('UPDATE copy_operations SET state=?,payload=?,checksum=? WHERE operation_id=?',
                (outcome, encode(payload), digest({'payload': payload, 'state': outcome}), operation_id))
            if outcome != 'UNKNOWN':
                conn.execute('DELETE FROM copy_locks WHERE operation_id=?', (operation_id,))

    def listing_action(self, expected, *, action, human_confirmed, note):
        self._human(human_confirmed, note)
        if action not in {'ERROR', 'RETURN'}:
            raise WorkStoreError('Explicit error or return action required')
        with self._transaction() as conn:
            for value in self._selection(conn, expected):
                if conn.execute('SELECT 1 FROM copy_locks WHERE asin=?', (value['asin'],)).fetchone():
                    raise WorkStoreError('Resolve the pending submission first')
                if action == 'ERROR':
                    if value['listing_progress'] != 'AWAITING_LISTING':
                        raise WorkStoreError('Only a confirmed submission can have a listing error')
                    value['listing_progress'] = 'ERROR'
                else:
                    if value['state'] not in {'AWAITING_LISTING', 'ERROR', 'RECHECK'} or value['listing_progress'] == 'LISTED':
                        raise WorkStoreError('Product cannot return from this state')
                    if not self._assess(value)['valid']:
                        raise WorkStoreError('Current preparation must be valid before returning')
                    value['listing_progress'] = 'WAITING'
                self._note(value, 'LISTING', action, note)
                self._update_assessment(value, self._assess(value))
                self.store.write(conn, value, action='LISTING_' + action, expected_revision=value['revision'])

    def queue_csv(self, *, queue='SAFETY'):
        if queue not in {'SAFETY', 'CATEGORY', 'BRAND', 'ALL'}:
            raise WorkStoreError('Unknown confirmation queue')
        values = self.refresh()
        stream = StringIO(newline='')
        fields = ('marketplace', 'shop_id', 'asin', 'queue', 'reasons', 'notes', 'state', 'revision')
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for value in values:
            result = value['assessment']
            chosen = (queue == 'ALL' or queue == 'SAFETY' and (result['safety_reasons'] or value['review_pending']
                      or value['manual_exclude'] or value['body_excluded'])
                      or queue == 'CATEGORY' and not result['category_valid']
                      or queue == 'BRAND' and not result['brand_valid'])
            if chosen:
                row = {k: value[k] for k in ('marketplace', 'shop_id', 'asin', 'state', 'revision')}
                row.update(queue=queue, reasons=' | '.join(result['reasons']), notes=encode(value['notes']))
                writer.writerow({k: "'" + str(v) if str(v).startswith(('=', '+', '-', '@')) else v for k, v in row.items()})
        return stream.getvalue().encode('utf-8-sig')
