"""P5-only write-ahead material intent in the original leased budget ledger.

There is no distributed transaction: unfinished intent always requires explicit
offline recovery, never automatic resend, commit, refund or old-ready fallback.
"""
import copy
from dataclasses import asdict
from threading import get_ident
from uuid import uuid4

from modules.sg_continuous_runtime import _digest
from modules.sg_beta_facts import ProductFacts
from modules.p5_runtime import P5Stopped


def journal(runtime):
    return runtime.ledger.data.get('material_updates', {}).get('intents', [])


def validate_journal(ledger):
    value = ledger.data['material_updates']
    if (not ledger.grant.preparation_limit or set(value) != {'version', 'intents'}
            or type(value['version']) is not int or value['version'] != 1
            or not isinstance(value['intents'], list)):
        raise P5Stopped('P5_MATERIAL_JOURNAL_INVALID')
    selected = ledger.data['candidates']['selections']
    generations, ids = {}, set()
    for item in value['intents']:
        bid = item.get('batch')
        if (bid not in selected or not item.get('id') or item['id'] in ids
                or item.get('scope') != ledger.grant.digest
                or item.get('selection') != _digest(selected[bid])
                or item.get('state') not in {'BEGIN', 'INVALIDATED', 'VALIDATED', 'COMMITTED'}
                or not isinstance(item.get('targets'), list) or not item['targets']
                or len(set(item['targets'])) != len(item['targets'])
                or not set(item['targets']) <= set(selected[bid]['asins'])
                or not item.get('reviewer') or not item.get('note')
                or set(item.get('expected', {})) != set(item['targets'])
                or set(item.get('parent', {})) != set(item['targets'])
                or any(type(r) is not int or r < 1 for r in item['expected'].values())):
            raise P5Stopped('P5_MATERIAL_INTENT_INVALID')
        ids.add(item['id'])
        for asin in item['targets']:
            if item['parent'][asin] != generations.get(asin, 0):
                raise P5Stopped('P5_MATERIAL_PARENT_MISMATCH')
        if item['state'] in {'VALIDATED', 'COMMITTED'}:
            if (_digest(item.get('rows')) != item.get('rows_sha')
                    or {r.get('candidate_asin') or r.get('asin') for r in item['rows']} != set(item['targets'])
                    or len(item['rows']) != len(item['targets'])):
                raise P5Stopped('P5_MATERIAL_SHA_MISMATCH')
        if item['state'] == 'COMMITTED':
            if (set(item.get('result', {})) != set(item['targets'])
                    or any(item['result'][a] != item['invalidated'][a] + 1 for a in item['targets'])):
                raise P5Stopped('P5_MATERIAL_REVISION_MISMATCH')
            for asin in item['targets']:
                generations[asin] = item['parent'][asin] + 1


def _internal(runtime):
    return runtime._material_action is not None and runtime._material_action['thread'] == get_ident()


def _latest(runtime, asin):
    return next((i for i in reversed(journal(runtime)) if asin in i['targets']), None)


def marker(item, asin):
    return {'intent': item['id'], 'generation': item['parent'][asin] + 1,
            'rows_sha': item['rows_sha'], 'packet_sha': item['packet_sha']}


def require_journal_current(runtime):
    items = journal(runtime)
    if any(i['state'] != 'COMMITTED' for i in items) and not _internal(runtime):
        raise P5Stopped('P5_MATERIAL_RECOVERY_REQUIRED')
    if _internal(runtime):
        return
    store = runtime._store
    if store is None:
        return
    # Read-only check is safe inside P2's write transaction. Monotonic revisions
    # after material adoption may record HUMAN confirmation/5-state operations.
    import sqlite3
    import json
    with sqlite3.connect(store.path.as_uri() + '?mode=ro', uri=True) as conn:
        products = {a: (r, json.loads(p)) for a, r, p in conn.execute('SELECT asin,revision,payload FROM products')}
        for asin in {a for i in items for a in i['targets']}:
            item = _latest(runtime, asin)
            revision, product = products.get(asin, (0, {}))
            if (item['state'] != 'COMMITTED' or revision < item['result'][asin]
                    or product.get('source', {}).get('p5_material') != marker(item, asin)
                    or not conn.execute('SELECT 1 FROM events WHERE asin=? AND revision=? AND action=?',
                        (asin, item['result'][asin], 'P5_MATERIAL_COMMIT')).fetchone()):
                raise P5Stopped('P5_MATERIAL_P2_MISMATCH')
        # Dropping the journal must not make a persisted new-format product old.
        for asin, (_, product) in products.items():
            if product.get('source', {}).get('p5_material') and _latest(runtime, asin) is None:
                raise P5Stopped('P5_MATERIAL_JOURNAL_MISSING')


def require_record_generation(runtime, record):
    item = _latest(runtime, record['asin'])
    supplied = record.get('source', {}).get('p5_material')
    if item is None:
        if supplied:
            raise P5Stopped('P5_MATERIAL_JOURNAL_MISSING')
        return
    staged = _internal(runtime) and runtime._material_action.get('committing')
    if ((item['state'] != 'COMMITTED' and not staged)
            or supplied != marker(item, record['asin'])):
        raise P5Stopped('P5_MATERIAL_GENERATION_MISMATCH')
    if not staged and item.get('filters', {}).get(record['asin'], 'MATCH') != 'MATCH':
        raise P5Stopped('P5_MATERIAL_FILTER_RECHECK_REQUIRED')


def current_rows(runtime, bid, rows):
    result = {r.get('candidate_asin') or r.get('asin'): r for r in rows}
    for item in journal(runtime):
        if item['batch'] != bid:
            continue
        staged = _internal(runtime) and runtime._material_action.get('committing')
        if item['state'] != 'COMMITTED' and not staged:
            raise P5Stopped('P5_MATERIAL_RECOVERY_REQUIRED')
        result.update({r.get('candidate_asin') or r.get('asin'): r for r in item['rows']})
    return list(result.values())


def require_update_send(runtime, operation):
    action = runtime._material_action
    if (_internal(runtime) and operation == 'p2.save' and
            (action['item']['state'] == 'BEGIN' or
             (action.get('committing') and action['item']['state'] == 'VALIDATED'))):
        return
    if (not _internal(runtime) or action.get('committing')
            or operation not in {'keepa.token', 'keepa.product'}
            or action['item']['state'] != 'INVALIDATED'):
        raise P5Stopped('P5_MATERIAL_SEND_BEFORE_INVALIDATION')
    item = action['item']
    products = {p['asin']: p for p in runtime._store.products()}
    if any(products[a]['revision'] != item['invalidated'][a]
           or products[a]['source'].get('p5_material_pending') != item['id']
           or products[a]['category'] is not None or products[a]['brand'] is not None
           or products[a]['preparation_state'] == 'READY' for a in item['targets']):
        raise P5Stopped('P5_MATERIAL_P2_INVALIDATION_REQUIRED')


def update_material(runtime, expected, *, reviewer, note, identity=None, fetch=None):
    runtime.require_operation('material.update')
    runtime.require_operation('p2.save')
    runtime.candidates._human(True, reviewer, note)
    if 'material_updates' not in runtime.ledger.data:
        raise P5Stopped('P5_LEGACY_MATERIAL_UPDATE_UNAVAILABLE')
    if fetch is not None and not runtime.permit.offline_test:
        raise P5Stopped('P5_SYNTHETIC_FETCH_REFUSED')
    with runtime.ledger._lock:
        runtime.require_current()
        if runtime._material_action is not None:
            raise P5Stopped('P5_MATERIAL_UPDATE_IN_PROGRESS')
        targets = set(expected)
        candidates = runtime.candidates.data
        bids = [b for b, s in candidates['selections'].items() if targets and targets <= set(s['asins'])]
        if len(bids) != 1:
            raise P5Stopped('P5_MATERIAL_SELECTION_REQUIRED')
        bid = bids[0]
        bench = runtime.workflow.bench
        with bench.store.transaction() as conn:
            old = bench._selection(conn, expected)
            if any(conn.execute('SELECT 1 FROM copy_locks WHERE asin=?', (a,)).fetchone() for a in targets):
                raise P5Stopped('P5_MATERIAL_PENDING_COPY_LOCK')
        old_rows = current_rows(runtime, bid, candidates['batches'][bid]['rows'])
        old_rows = [r for r in old_rows if (r.get('candidate_asin') or r.get('asin')) in targets]
        runtime.checkpoint('material-update')
        item = {'id': uuid4().hex, 'scope': runtime.scope.digest, 'batch': bid,
            'selection': _digest(candidates['selections'][bid]), 'targets': sorted(targets),
            'parent': {a: (_latest(runtime, a)['parent'][a] + 1 if _latest(runtime, a) else 0) for a in targets},
            'expected': dict(expected), 'state': 'BEGIN', 'reviewer': reviewer.strip(), 'note': note.strip(),
            'session': asdict(bench.session.scope), 'old_sha': _digest(old_rows),
            'reservations_before': [r['id'] for r in runtime.ledger.data['reservations']]}
        journal(runtime).append(item)
        runtime._material_action = {'thread': get_ident(), 'item': item, 'committing': False}
        try:
            runtime.ledger.persist()  # write-ahead, before P2 and before any send
            for asin in targets:
                bench.session.begin_fact_refresh(asin)
                runtime.weapon_receipts.pop(asin, None)
            with bench._transaction() as conn:
                for product in bench._selection(conn, expected):
                    product.update(category=None, brand=None)
                    product['source']['p5_material_pending'] = item['id']
                    bench._update_assessment(product, bench._assess(product))
                    bench._note(product, 'MATERIAL', 'BEGIN', note, intent=item['id'])
                    bench.store.write(conn, product, action='P5_MATERIAL_BEGIN', expected_revision=product['revision'])
            item['invalidated'] = {p['asin']: p['revision'] for p in bench.store.products() if p['asin'] in targets}
            item['state'] = 'INVALIDATED'
            runtime.ledger.persist()
            require_update_send(runtime, 'keepa.product')
            rows = (fetch(copy.deepcopy(old_rows)) if fetch is not None else
                    runtime.amazon_client().fresh_selected_products(copy.deepcopy(old_rows)))
            rows = copy.deepcopy(list(rows))
            if len(rows) != len(targets) or {r.get('candidate_asin') or r.get('asin') for r in rows} != targets:
                raise P5Stopped('P5_MATERIAL_RESPONSE_TARGET_MISMATCH')
            item['response_rows'] = rows
            item['response_sha'] = _digest(rows)
            runtime.ledger.persist()  # retained even if later comparison fails
            by_asin = {r.get('candidate_asin') or r.get('asin'): r for r in old_rows}
            comparisons = {}
            for row in rows:
                asin = row.get('candidate_asin') or row.get('asin')
                before = by_asin[asin]
                for key in ('seed_asin', 'candidate_asin', 'asin', 'source', 'source_id', 'input_title', 'origin'):
                    if row.get(key) != before.get(key):
                        raise P5Stopped('P5_MATERIAL_SOURCE_CHANGED')
                facts = ProductFacts.from_dict(row['classification_facts'])
                if facts.asin != asin or any(not f.owned_by(asin)
                    for f in facts.fields.values() if f.value not in (None, '', [], ())):
                    raise P5Stopped('P5_MATERIAL_FACT_INVALID')
                prior = ProductFacts.from_dict(before['classification_facts'])
                changed = any(facts.fields[k].value != prior.fields[k].value for k in facts.fields)
                if candidates['batches'][bid]['source_type'] == 'RESOLVER' and changed:
                    comparison = (identity or {}).get(asin, {})
                    if (not isinstance(comparison, dict) or comparison.get('state') != 'CONFIRMED'
                            or comparison.get('new_facts_sha') != facts.binding
                            or comparison.get('old_facts_sha') != prior.binding
                            or not comparison.get('reviewer') or not comparison.get('note')):
                        raise P5Stopped('P5_RESOLVER_IDENTITY_UNRESOLVED')
                comparisons[asin] = {'changed': changed, 'identity': (identity or {}).get(asin, 'UNCHANGED'),
                                     'reviewer': reviewer, 'note': note}
            packet = runtime.candidates.handoff(bid, rows_override=rows)
            from modules.classification_workflow import records_from_producer
            records = records_from_producer(marketplace=runtime.scope.marketplace, **packet)
            from modules.candidate_filters import FilterCriteria, partition_rows
            criteria = FilterCriteria(**candidates['batches'][bid].get('filter_criteria', {}))
            filters = {r.asin: r.evaluation.status for r in partition_rows(rows, None, criteria).evaluations}
            item.update(rows=rows, rows_sha=_digest(rows), comparisons=comparisons,
                filters=filters,
                packet_sha=_digest({k: v.hex() for k, v in packet.items() if isinstance(v, bytes)}),
                reservations=[r['id'] for r in runtime.ledger.data['reservations']
                              if r['id'] not in item['reservations_before']], state='VALIDATED')
            runtime.ledger.persist()
            runtime._material_action['committing'] = True
            for record in records:
                record['source']['p5_material'] = marker(item, record['asin'])
                record['source']['p5_selection'] = runtime.candidates.require_record(record)
            # P1/P2 current validation still owns Safety, all-shop and HUMAN
            # Category→Brand. A download response never creates readiness.
            for record in records:
                bench.session.accept_facts(ProductFacts.from_dict(record['facts']))
            with bench._transaction() as conn:
                previous = {p['asin']: p for p in bench._selection(conn, item['invalidated'])}
                for record in records:
                    product = previous[record['asin']]
                    for key in ('facts', 'source', 'weapon'):
                        product[key] = copy.deepcopy(record.get(key))
                    product.update(category=None, brand=None, preparation_scope=asdict(bench.session.scope))
                    bench._update_assessment(product, bench._assess(product))
                    bench._note(product, 'MATERIAL', 'RECONFIRM_REQUIRED', note, intent=item['id'])
                    bench.store.write(conn, product, action='P5_MATERIAL_COMMIT', expected_revision=product['revision'])
            item['result'] = {p['asin']: p['revision'] for p in bench.store.products() if p['asin'] in targets}
            item['state'] = 'COMMITTED'
            runtime.ledger.persist()
        finally:
            runtime._material_action = None
        runtime.require_current()
        return copy.deepcopy(item)
