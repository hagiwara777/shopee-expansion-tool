"""P5 two-stage PH/SG flow, actual SDK with synthetic responses; no live I/O."""
import copy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from modules.classification_workflow import records_from_producer
from modules.p5_runtime import P5Runtime, P5Stopped
from modules.p5_transport import P5KeepaBudget, make_keepa_client, make_catalog_client
from modules.prelisting_candidate_csv import parse_prelisting_candidate_csv
from modules.prelisting_gate import evaluate_prelisting_gate
from modules.product_text_safety import parse_product_text_safety_sidecar
from test_p5_runtime import runtime_for, secrets, catalog_response, forbid_network
from test_sg_initial_beta import raw, inventory
from test_keepa_candidate_filters import keepa_raw_product


ASINS = ['B000000001', 'B000000002', 'B000000003']
SOURCE = {'source_id': 'R0001', 'input_title': 'Synthetic wired headphone', 'origin': 'SYNTHETIC_SHOPEE_REFERENCE'}
QUERY = {'brand': ['Synthetic Maker'], 'categories_include': [3210981], 'page': 0,
         'perPage': 50, 'sort': [['current_SALES', 'asc']]}


@pytest.fixture(params=['PH', 'SG'])
def flow(request, tmp_path, forbid_network):
    rt = runtime_for(tmp_path, request.param, asins=('B000000000',),
        preparation_limit=4, finder_queries=(json.dumps(QUERY),), resolver_inputs=(json.dumps(SOURCE),))
    yield rt
    rt.close()


def sdk(runtime, *, title='Synthetic wired headphone', brand='Synthetic Maker', found=None, stats=None):
    calls = []
    def send(url, **kwargs):
        calls.append((url, kwargs))
        body = {'tokensLeft': 500, 'tokensConsumed': 0, 'refillRate': 5, 'refillIn': 60000}
        if '/query/' in url:
            body.update(tokensConsumed=2, asinList=ASINS if found is None else found, totalResults=3)
        elif '/product/' in url:
            products = []
            for asin in kwargs['params']['asin'].split(','):
                p = raw(asin, title, 'Synthetic Maker' if asin == 'B000000000' else brand)
                p['categoryTree'][0]['catId'] = 3210981
                if stats is not None:
                    p.update(stats={'current':stats}, availabilityAmazon=0)
                products.append(p)
            body.update(tokensConsumed=len(products), products=products)
        return SimpleNamespace(status_code=200, json=lambda: body)
    return make_keepa_client(runtime, secrets(runtime), transport=send), calls


def discover(runtime, **kwargs):
    client, calls = sdk(runtime, **kwargs)
    result = client.find_related_products('B000000000', 1)
    return client, result, calls


def fix(runtime, rows, source_type='EXPANSION', asins=None, identity='UNKNOWN'):
    bid = runtime.candidates.offer(source_type, rows)
    runtime.candidates.select(bid, asins or [rows[0].get('candidate_asin') or rows[0]['asin']],
        human_confirmed=True, reviewer='SYNTHETIC_OPERATOR', note='Synthetic selection/specification comparison', identity=identity)
    return bid


def current_material(runtime, inventories=None):
    client = make_catalog_client(runtime, secrets(runtime), request_json=catalog_response)
    runtime.acquire_catalog(client)
    runtime.acquire_brand(client, 100578)
    market = runtime.scope.marketplace
    runtime.workflow.supply_inventory(inventories or (inventory(shop='22', marketplace=market, name=market+'_shop.csv'),),
        expected_shops=('22',), reference='SYNTHETIC_CURRENT_INVENTORY', confirmed_current=True)


def ingest(runtime, bid):
    material = runtime.candidates.handoff(bid)
    records = records_from_producer(marketplace=runtime.scope.marketplace, **material)
    runtime.workflow.ingest(records, scope=runtime.workflow.session.scope, batch_ref=bid)
    return records


def confirm(runtime, asin):
    for kind, option in [('CATEGORY', 100578), ('BRAND', 7)]:
        runtime.workflow.confirm(runtime.workflow.select([asin]), kind=kind, option_id=option,
            reviewer='SYNTHETIC_OPERATOR', note='Synthetic classification', human_verified=True)


@pytest.fixture(params=['PH', 'SG'])
def updating_flow(request, tmp_path, forbid_network):
    rt = runtime_for(tmp_path, request.param, material_updates=True, asins=('B000000000',),
        preparation_limit=4, finder_queries=(json.dumps(QUERY),), resolver_inputs=(json.dumps(SOURCE),))
    _, result, _ = discover(rt)
    bid = fix(rt, result.rows, asins=ASINS[:2])
    current_material(rt)
    ingest(rt, bid)
    for asin in ASINS[:2]:
        confirm(rt, asin)
    rt._test_bid = bid
    yield rt
    rt.close()


def update_one(rt, *, fetch=None):
    row = next(p for p in rt.workflow.bench.store.products() if p['asin'] == ASINS[0])
    return rt.update_material({ASINS[0]: row['revision']}, reviewer='SYNTHETIC',
        note='Synthetic current material comparison', fetch=fetch or (lambda rows: rows))


def test_t03_t04_same_content_generation_preserves_selection_history_and_other_product(updating_flow):
    rt = updating_flow
    bench = rt.workflow.bench
    original = copy.deepcopy(rt.candidates.data)
    digest = rt.scope.digest
    other = next(p for p in bench.store.products() if p['asin'] == ASINS[1])
    history = bench.store.history()
    update = update_one(rt)
    assert update['state'] == 'COMMITTED'
    assert rt.candidates.data == original and rt.scope.digest == digest
    assert next(p for p in bench.store.products() if p['asin'] == ASINS[1]) == other
    assert bench.store.history()[:len(history)] == history
    target = next(p for p in bench.store.products() if p['asin'] == ASINS[0])
    assert target['category'] is None and target['brand'] is None and target['preparation_state'] == 'RECHECK'
    confirm(rt, ASINS[0])
    assert len(bench.prepared_pool()) == 2
    update_one(rt)
    assert len(rt.ledger.data['material_updates']['intents']) == 2
    rt.close()
    rt.start()
    assert not rt.workflow.bench.prepared_pool()
    current_material(rt)
    ingest(rt, rt._test_bid)
    confirm(rt, ASINS[0])
    assert rt.workflow.bench.prepared_pool()


def test_t03_legacy_update_requires_new_installation_and_selected_subset(tmp_path, updating_flow):
    from modules.p5_runtime import initialize_p5_ledger
    with pytest.raises(ValueError, match='NEW_INSTALLATION'):
        initialize_p5_ledger(updating_flow.scope, material_updates=True)
    legacy = runtime_for(tmp_path / 'legacy', updating_flow.scope.marketplace)
    try:
        with pytest.raises(P5Stopped, match='LEGACY'):
            legacy.update_material({ASINS[0]: 1}, reviewer='fixture', note='fixture', fetch=lambda rows: rows)
    finally:
        legacy.close()
    with pytest.raises(P5Stopped, match='SELECTION'):
        updating_flow.update_material({ASINS[2]: 1}, reviewer='fixture', note='fixture', fetch=lambda rows: rows)


@pytest.mark.parametrize('boundary', ['BEGIN', 'INVALIDATED', 'VALIDATED', 'COMMITTED', 'P2_BEGIN', 'P2_COMMIT'])
def test_t05_crash_each_boundary_never_revives_ready_or_resends(updating_flow, monkeypatch, boundary):
    rt = updating_flow
    ledger, store = rt.ledger, rt.workflow.bench.store
    persist, write = ledger.persist, store.write
    calls = []
    reservations = copy.deepcopy(ledger.data['reservations'])
    def crash_persist():
        state = ledger.data['material_updates']['intents'][-1]['state']
        if state == boundary:
            raise OSError('Synthetic crash')
        persist()
    def crash_write(conn, value, *, action, expected_revision):
        if action == {'P2_BEGIN': 'P5_MATERIAL_BEGIN', 'P2_COMMIT': 'P5_MATERIAL_COMMIT'}.get(boundary):
            raise OSError('Synthetic P2 crash')
        write(conn, value, action=action, expected_revision=expected_revision)
    monkeypatch.setattr(ledger, 'persist', crash_persist)
    monkeypatch.setattr(store, 'write', crash_write)
    with pytest.raises((ValueError, RuntimeError, OSError)):
        update_one(rt, fetch=lambda rows: (calls.append(True), rows)[1])
    assert len(calls) == (boundary in {'VALIDATED', 'COMMITTED', 'P2_COMMIT'})
    assert ledger.data['reservations'] == reservations
    with pytest.raises((ValueError, RuntimeError)):
        rt.require_current()
    rt.close()
    if boundary != 'BEGIN':
        with pytest.raises((ValueError, RuntimeError)):
            rt.start()


def test_t02_t05_send_requires_both_invalidations_and_charges_same_ledger(updating_flow):
    rt = updating_flow
    before = len(rt.ledger.data['reservations'])
    def fetch(rows):
        products = {p['asin']:p for p in rt.workflow.bench.store.products()}
        assert products[ASINS[0]]['category'] is None
        budget = P5KeepaBudget(rt)
        budget.balance = 100
        rid = budget.reserve_keepa_call('product', {'domain':5,'asin':ASINS[0]})
        budget.complete_keepa_call(rid, {'tokensLeft':99, 'tokensConsumed':1}, 200)
        return rows
    update_one(rt, fetch=fetch)
    assert len(rt.ledger.data['reservations']) == before + 1
    assert rt.ledger.data['material_updates']['intents'][-1]['reservations']


def test_t05_pending_copy_and_stale_revision_stop_before_begin(updating_flow):
    rt = updating_flow
    before = copy.deepcopy(rt.ledger.data)
    with pytest.raises(ValueError):
        rt.update_material({ASINS[0]:0}, reviewer='fixture', note='fixture', fetch=lambda rows: rows)
    assert rt.ledger.data == before
    bench = rt.workflow.bench
    row = next(p for p in bench.store.products() if p['asin'] == ASINS[0])
    bench.output({ASINS[0]:row['revision']}, reserve_copy=True)
    with pytest.raises(ValueError):
        update_one(rt)
    assert rt.ledger.data == before


def test_t04_fresh_bypasses_fresh_cache_and_rebuilds_safety(updating_flow, monkeypatch):
    rt = updating_flow
    client, calls = sdk(rt, title='Synthetic rechargeable battery')
    monkeypatch.setattr(rt, 'amazon_client', lambda: client)
    # Discovery populated the same 7-day cache. This explicit update must send.
    target = next(p for p in rt.workflow.bench.store.products() if p['asin'] == ASINS[0])
    original = copy.deepcopy(rt.candidates.data)
    rt.update_material({ASINS[0]:target['revision']}, reviewer='fixture', note='fresh response')
    assert any('/product/' in url for url, _ in calls)
    assert all('/query/' not in url for url, _ in calls)
    assert rt.candidates.data['batches'] == original['batches']
    with pytest.raises(ValueError):
        confirm(rt, ASINS[0])  # Battery REVIEW still stops classification/output.
    assert next(p for p in rt.workflow.bench.store.products() if p['asin'] == ASINS[0])['preparation_state'] == 'RECHECK'


def test_t04_fresh_captures_both_price_and_rating(updating_flow, monkeypatch, keepa_raw_product):
    rt = updating_flow
    client, calls = sdk(rt, stats=keepa_raw_product['stats']['current'])
    monkeypatch.setattr(rt, 'amazon_client', lambda: client)
    target = next(p for p in rt.workflow.bench.store.products() if p['asin'] == ASINS[0])
    update = rt.update_material({ASINS[0]:target['revision']}, reviewer='fixture', note='price and rating')
    observed = update['rows'][0]['candidate_observation']
    assert observed['price_jpy'] == 1000 and observed['rating'] == 4.5
    assert observed['price_status'] == observed['rating_status'] == 'OBSERVED'
    assert len(calls) == 2  # token and selected Product; Finder was not rerun


@pytest.mark.parametrize('change', ['title','brand','model','category_tree','features','ingredients'])
def test_t04_changed_fact_keeps_old_confirmation_invalid(updating_flow, change):
    rt = updating_flow
    def changed(rows):
        fact = rows[0]['classification_facts']['fields'][change]
        if change == 'category_tree':
            fact['value'][-1]['name'] = 'Changed fixture category'
        elif isinstance(fact['value'], list):
            fact['value'] = ['Changed fixture content']
        else:
            fact['value'] = 'Changed fixture content'
        return rows
    # Inconsistent producer/sidecar fields are allowed to STOP, never old ready.
    try:
        update_one(rt, fetch=changed)
    except (ValueError, RuntimeError):
        with pytest.raises(ValueError): rt.require_current()
    else:
        assert next(p for p in rt.workflow.bench.store.products() if p['asin']==ASINS[0])['category'] is None


def test_t05_missing_journal_never_downgrades_to_old_mode(updating_flow):
    rt = updating_flow
    update_one(rt)
    del rt.ledger.data['material_updates']
    rt.ledger.persist()
    with pytest.raises(ValueError, match='JOURNAL_MISSING'):
        rt.require_current()
    rt.close()
    with pytest.raises(ValueError):
        rt.start()


def test_t05_concurrent_update_and_output_fail_closed(updating_flow):
    from threading import Event, Thread
    rt = updating_flow
    entered, release = Event(), Event()
    errors = []
    def fetch(rows):
        entered.set()
        assert release.wait(10)
        return rows
    def work():
        try: update_one(rt, fetch=fetch)
        except Exception as exc: errors.append(exc)
    worker = Thread(target=work)
    worker.start()
    try:
        assert entered.wait(10)
        with pytest.raises(ValueError):
            rt.require_current()
        with pytest.raises(ValueError):
            rt.workflow.bench.output({ASINS[0]:1})
    finally:
        release.set()
        worker.join(10)
    assert not worker.is_alive() and not errors


@pytest.mark.parametrize('sidecar', ['ingredients', 'image'])
def test_t04_all_safety_material_remains_bound_to_generation(updating_flow, sidecar):
    rt = updating_flow
    update_one(rt)
    row = copy.deepcopy(next(p for p in rt.workflow.bench.store.products() if p['asin']==ASINS[0]))
    if sidecar == 'ingredients':
        row['source']['ingredients'] = row['source']['ingredients'].replace('keepa', 'canopy_test')
    else:
        row['weapon']['images']['root_category_id'] = 999999
    with pytest.raises((ValueError, RuntimeError)):
        rt.require_preparation_target(row)


@pytest.mark.parametrize('market', ['PH','SG'])
def test_t04_filter_reassessment_retains_selection_but_blocks_pool(tmp_path, market, keepa_raw_product):
    from modules.candidate_filters import FilterCriteria, extract_keepa_observation
    from modules.cache import utc_now_iso
    rt = runtime_for(tmp_path, market, material_updates=True, asins=('B000000000',),
        preparation_limit=4, finder_queries=(json.dumps(QUERY),))
    try:
        _, result, _ = discover(rt)
        rows = [copy.deepcopy(result.rows[0])]
        rows[0]['candidate_observation'] = extract_keepa_observation(keepa_raw_product, captured_at=utc_now_iso())
        bid = rt.candidates.offer('EXPANSION', rows, filter_criteria=FilterCriteria(rating_min=4.5))
        rt.candidates.select(bid, [ASINS[0]], human_confirmed=True, reviewer='fixture', note='fixture')
        current_material(rt)
        ingest(rt, bid)
        confirm(rt, ASINS[0])
        def changed(selected_rows):
            selected_rows[0]['candidate_observation']['rating'] = 4.0
            return selected_rows
        update_one(rt, fetch=changed)
        assert rt.candidates.data['selections'][bid]['asins'] == [ASINS[0]]
        assert not rt.workflow.bench.prepared_pool()
        with pytest.raises(ValueError): confirm(rt, ASINS[0])
    finally:
        rt.close()


@pytest.mark.parametrize('market', ['PH','SG'])
def test_t04_changed_resolver_requires_new_exact_comparison(tmp_path, market):
    from modules.asin_resolver import verify_selected_rows
    rt = runtime_for(tmp_path, market, material_updates=True, asins=('B000000000',),
        preparation_limit=4, finder_queries=(json.dumps(QUERY),), resolver_inputs=(json.dumps(SOURCE),))
    try:
        client, _ = sdk(rt)
        proposed = [{'selected':True, 'source_id':SOURCE['source_id'], 'input_title':SOURCE['input_title'],
                     'asin':'B000000004', 'parse_status':'CANDIDATE'}]
        rt.candidates.propose_resolver(proposed, human_confirmed=True, reviewer='fixture', note='fixture')
        rows = verify_selected_rows(proposed, client)
        bid = fix(rt, rows, 'RESOLVER', asins=['B000000004'], identity='CONFIRMED')
        current_material(rt)
        ingest(rt, bid)
        def changed(selected_rows):
            facts = selected_rows[0]['classification_facts']['fields']
            facts['model'] = {**facts['title'], 'value':'Changed synthetic model'}
            return selected_rows
        product = rt.workflow.bench.store.products()[0]
        with pytest.raises(ValueError, match='IDENTITY_UNRESOLVED'):
            rt.update_material({product['asin']:product['revision']}, reviewer='fixture', note='comparison needed',
                identity={product['asin']:'CONFIRMED'}, fetch=changed)
        assert rt.ledger.data['material_updates']['intents'][-1]['response_rows']
        assert rt.ledger.data['candidates']['selections'][bid]['identity'] == 'CONFIRMED'
        with pytest.raises(ValueError): rt.require_current()
    finally:
        rt.close()


def test_finder_selection_safety_classification_save_restart(flow):
    rt = flow
    client, result, calls = discover(rt)
    digest = rt.scope.digest
    bid = rt.candidates.offer('EXPANSION', result.rows)
    with pytest.raises(P5Stopped, match='EXPLICIT_SELECTION'):
        rt.candidates.handoff(bid)
    bid = fix(rt, result.rows)
    current_material(rt)
    records = ingest(rt, bid)
    assert [r['asin'] for r in records] == [ASINS[0]]
    handoff = rt.candidates.handoff(bid)
    parsed = parse_prelisting_candidate_csv(handoff['candidate_content'], filename=handoff['filename'])
    text = parse_product_text_safety_sidecar(handoff['text_content'], filename='text.csv', candidate_content=handoff['candidate_content'], candidates=parsed)
    gate = evaluate_prelisting_gate(parsed, rt.workflow.session.current_inventory().inventories,
        marketplace=rt.scope.marketplace, expected_shop_count=1, product_text_safety=text)
    assert gate.rows[0].final_eligibility == 'ELIGIBLE'
    confirm(rt, ASINS[0])
    bench = rt.workflow.bench
    assert [r['asin'] for r in bench.prepared_pool()] == [ASINS[0]]
    chosen = {r['asin']: r['revision'] for r in bench.store.products()}
    csv_bytes, _, _ = bench.output(chosen)
    assert b'FALSE' in csv_bytes and b'PH_SG_P1_OFFLINE' in csv_bytes
    with pytest.raises(P5Stopped, match='SYNTHETIC_IS_NOT_OFFICIAL'):
        rt.output(chosen)
    # Unselected targets are rejected even through direct lower-level intake.
    unselected = copy.deepcopy(records[0])
    unselected['asin'] = ASINS[1]
    with pytest.raises((ValueError, RuntimeError)):
        bench.ingest([unselected], batch_ref='UNSELECTED')
    with pytest.raises(P5Stopped, match='ALREADY_FIXED'):
        rt.candidates.select(bid, ASINS[:2], human_confirmed=True, reviewer='operator', note='attempted addition')
    history = bench.store.history()
    reservations = copy.deepcopy(rt.ledger.data['reservations'])
    scope, permit = rt.scope, rt.permit
    rt.close()
    rt.start()
    assert rt.scope.digest == digest and rt.scope.asins == ('B000000000',)
    assert rt.ledger.data['reservations'] == reservations
    assert rt.workflow.bench.store.history()[:len(history)] == history
    assert rt.candidates.handoff(bid) == handoff
    assert not rt.workflow.bench.prepared_pool()  # No old current authority.
    current_material(rt)
    ingest(rt, bid)
    confirm(rt, ASINS[0])
    assert len(rt.workflow.bench.prepared_pool()) == 1
    assert len(calls) == 4  # token, seed, strict query, detail; no restart API.
    # Re-instantiating the adapter cannot widen targets or repeat the query.
    fresh = P5KeepaBudget(rt)
    fresh.balance = 500
    with pytest.raises(P5Stopped, match='ALREADY_EXECUTED'):
        fresh.reserve_keepa_call('query', {'key':'SYNTHETIC', 'domain':5, 'selection':json.dumps(QUERY)})
    assert rt.scope == scope and rt.permit == permit


def test_resolver_origin_identity_and_source_survive_to_store(flow):
    from modules.asin_resolver import verify_selected_rows
    client, _ = sdk(flow)
    proposed = [{'selected': True, 'source_id': SOURCE['source_id'], 'input_title': SOURCE['input_title'],
                 'asin': 'B000000004', 'parse_status': 'CANDIDATE'}]
    with pytest.raises(P5Stopped, match='OUTSIDE_SCOPE'):
        client.verify_products_by_asin(['B000000004'])
    flow.candidates.propose_resolver(proposed, human_confirmed=True, reviewer='operator', note='source checked')
    rows = verify_selected_rows(proposed, client)
    assert rows[0]['verification'] == 'KEEPA_VERIFIED'
    bid = flow.candidates.offer('RESOLVER', rows)
    for identity in ('UNKNOWN', 'MISMATCH'):
        with pytest.raises(P5Stopped, match='IDENTITY_UNRESOLVED'):
            flow.candidates.select(bid, ['B000000004'], human_confirmed=True, reviewer='operator', note='not identical', identity=identity)
    bid = fix(flow, rows, 'RESOLVER', identity='CONFIRMED')
    current_material(flow)
    ingest(flow, bid)
    confirm(flow, 'B000000004')
    stored = flow.workflow.bench.store.products()[0]
    assert stored['batches'][-1]['source_type'] == 'RESOLVER'
    assert stored['batches'][-1]['source_id'] == 'R0001'
    assert SOURCE['input_title'] in stored['source']['candidate']
    assert stored['source']['p5_selection']['origin'] == SOURCE['origin']
    assert stored['source']['p5_selection']['identity'] == 'CONFIRMED'
    assert flow.candidates.data['proposals'][0]['origin'] == SOURCE['origin']
    assert flow.candidates.data['selections'][bid]['identity'] == 'CONFIRMED'
    for field, value in [('status','UNKNOWN'), ('identity_status','MISMATCH'), ('source_id','R9999')]:
        bad = [{**rows[0], field: value}]
        with pytest.raises(P5Stopped):
            flow.candidates.offer('RESOLVER', bad)


@pytest.mark.parametrize('kind', ['BLOCK', 'REVIEW', 'EXCLUDE'])
def test_safety_stops_cannot_be_overridden_by_classification(flow, kind):
    title = ('prescription drug' if flow.scope.marketplace == 'PH' else '薬用 lotion') if kind == 'BLOCK' else (
        'Synthetic rechargeable battery' if kind == 'REVIEW' else 'Synthetic wired headphone')
    _, result, _ = discover(flow, title=title)
    bid = fix(flow, result.rows)
    current_material(flow)
    ingest(flow, bid)
    bench = flow.workflow.bench
    if kind == 'EXCLUDE':
        bench.record_review({r['asin']:r['revision'] for r in bench.store.products()},
            result='EXCLUDE', note='Synthetic exclusion', human_confirmed=True)
    with pytest.raises((ValueError, RuntimeError)):
        confirm(flow, ASINS[0])
    assert not bench.prepared_pool()
    assert bench.store.products()[0]['category'] is None


def test_scope_change_budget_excess_and_response_size_stop_without_reset(flow):
    budget = P5KeepaBudget(flow)
    budget.balance = 500
    before = copy.deepcopy(flow.ledger.data)
    with pytest.raises(P5Stopped, match='BUDGET_EXHAUSTED'):
        flow.ledger.reserve('keepa', tokens=flow.scope.keepa_tokens+1)
    assert flow.ledger.data == before
    with pytest.raises(P5Stopped, match='NOT_APPROVED'):
        P5Runtime(replace(flow.scope, preparation_limit=5), permit=flow.permit).start()
    rid = budget.reserve_keepa_call('query', {'key':'SYNTHETIC', 'domain':5, 'selection':json.dumps(QUERY)})
    with pytest.raises(P5Stopped, match='RESPONSE_INVALID'):
        budget.complete_keepa_call(rid, {'tokensLeft':500, 'tokensConsumed':1, 'asinList':ASINS*20}, 200)
    budget.fail_keepa_call(rid)
    flow.close()
    with pytest.raises(P5Stopped, match='UNRESOLVED'):
        flow.start()


def test_rebatching_and_preparation_limit_cannot_expand_fixed_targets(flow):
    _, result, _ = discover(flow)
    bid = fix(flow, result.rows)
    other = flow.candidates.offer('EXPANSION', result.rows[1:])
    with pytest.raises(P5Stopped, match='ALREADY_FIXED'):
        flow.candidates.select(other, [ASINS[1]], human_confirmed=True, reviewer='operator', note='rebatching')
    assert set(flow.candidates.data['selections']) == {bid}
    with pytest.raises(P5Stopped, match='OUTSIDE_BATCH'):
        flow.candidates.select(bid, ['B000000099'], human_confirmed=True, reviewer='operator', note='outside scope')


def test_new_mode_budget_and_candidate_history_missing_on_disk_stop(flow):
    _, result, _ = discover(flow)
    fix(flow, result.rows)
    path = flow.ledger.path
    before = json.loads(path.read_text('utf-8'))
    flow.close()
    damaged = copy.deepcopy(before)
    damaged['candidates']['selections'] = {}
    path.write_text(json.dumps(damaged), encoding='utf-8')
    with pytest.raises((ValueError, RuntimeError)):
        flow.start()
    # Do not initialize/recover the run or erase its charged reservations.
    assert json.loads(path.read_text('utf-8'))['reservations'] == before['reservations']


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_preparation_limit_and_parallel_fix_are_atomic(tmp_path, market, forbid_network):
    from concurrent.futures import ThreadPoolExecutor
    rt = runtime_for(tmp_path, market, asins=('B000000000',), preparation_limit=1,
                     finder_queries=(json.dumps(QUERY),))
    try:
        _, result, _ = discover(rt)
        bid = rt.candidates.offer('EXPANSION', result.rows)
        before = rt.ledger.path.read_bytes()
        with pytest.raises(P5Stopped, match='LIMIT_EXCEEDED'):
            rt.candidates.select(bid, ASINS[:2], human_confirmed=True, reviewer='operator', note='too many')
        assert rt.ledger.path.read_bytes() == before
        def choose(asin):
            try:
                rt.candidates.select(bid, [asin], human_confirmed=True, reviewer='operator', note='parallel explicit selection')
                return True
            except P5Stopped:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sum(pool.map(choose, ASINS[:2])) == 1
        assert len(rt.candidates.data['selections'][bid]['asins']) == 1
    finally:
        rt.close()


def test_parallel_finder_adapters_reserve_one_approved_page(flow):
    from concurrent.futures import ThreadPoolExecutor
    def reserve(_):
        budget = P5KeepaBudget(flow)
        budget.balance = 500
        try:
            return budget.reserve_keepa_call('query', {'key':'SYNTHETIC','domain':5,'selection':json.dumps(QUERY)})
        except P5Stopped:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = [r for r in pool.map(reserve, range(2)) if r is not None]
    assert len(receipts) == 1
    assert len(flow.ledger.data['reservations']) == 1
    # No physical send occurred; retain the reserved run for explicit recovery.


def test_market_shop_and_candidate_tampering_cannot_reuse_selection(flow):
    _, result, _ = discover(flow)
    bid = fix(flow, result.rows)
    current_material(flow)
    record = ingest(flow, bid)[0]
    changed = copy.deepcopy(record)
    changed['facts']['fields']['description']['value'] = ['changed evidence']
    with pytest.raises((ValueError, RuntimeError)):
        flow.workflow.bench.ingest([changed], batch_ref='tampered')
    other = inventory(shop='99', marketplace=flow.scope.marketplace, name='other.csv')
    with pytest.raises((ValueError, RuntimeError)):
        current_material(flow, (other,))
    assert not flow.workflow.bench.prepared_pool()


def test_existing_listing_stops_preparation_in_this_market_and_shop(flow):
    _, result, _ = discover(flow)
    bid = fix(flow, result.rows)
    inv = inventory(ASINS[0], shop='22', marketplace=flow.scope.marketplace, name='listed.csv')
    current_material(flow, (inv,))
    ingest(flow, bid)
    with pytest.raises((ValueError, RuntimeError)):
        confirm(flow, ASINS[0])
    record = flow.workflow.bench.store.products()[0]
    assert record['listing_progress'] == 'LISTED'
    assert not flow.workflow.bench.prepared_pool()
