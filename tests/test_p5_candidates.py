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


def sdk(runtime, *, title='Synthetic wired headphone', brand='Synthetic Maker', found=None):
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
