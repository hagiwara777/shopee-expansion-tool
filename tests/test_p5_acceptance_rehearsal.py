"""P5 acceptance rehearsal: synthetic authority/OS/HTTP, never live evidence.

Exercise the real operator, two-stage selection ledger, P1/P2, checkpoint and
three fresh sessions together. Credential resolution and Bridge reads are
synthetic seams; their physical transport coverage remains in existing tests.
"""
import copy
import csv
from io import StringIO
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from modules.asin_resolver import verify_selected_rows
from modules.beta_work_store import WorkStoreError
from modules.p5_live_adapter import P5CredentialResolver, P5ServiceCredentials, P5KeepaReference
from modules.p5_operator import OriginalOwnerRecord, P5OwnerAuthority, P5Operator, P5Checkpoint
from modules.p5_runtime import P5Runtime, P5ExecutionPermit, P5Stopped, initialize_p5_ledger
from modules.p5_transport import P5BridgeTransport
from modules.p5_windows import execution_profile_target
from modules.sg_continuous_runtime import _digest
from test_p5_candidates import QUERY, SOURCE, discover, fix, ingest, confirm
from test_p5_composition import observer_fixture
from test_p5_production_connection import credential_reference
from test_p5_runtime import scope_for, trusted_adapter, secrets, catalog_response, forbid_network
from test_beta_workbench_p2 import selected
from test_sg_initial_beta import inventory


@pytest.fixture(params=['PH', 'SG'])
def rehearsal(tmp_path, monkeypatch, request, forbid_network):
    scope, observer, process, _ = observer_fixture(tmp_path, monkeypatch)
    if request.param == 'SG':
        scope = scope_for(tmp_path, 'SG', bridge_spreadsheet_id='synthetic-sheet')
    import sys
    entry = str(tmp_path / 'app_beta.py')
    monkeypatch.setattr(sys.modules['__main__'], '__file__', entry)
    scope = replace(scope, asins=('B000000000',), preparation_limit=3,
        finder_queries=(json.dumps(QUERY),), resolver_inputs=(json.dumps(SOURCE),),
        image_requests=0, openai_requests=0, openai_usd='0',
        bridge_requests=10, auth_requests=10,
        execution_target=execution_profile_target(machine=process['machine'],
            operator_sid=process['sid'], interpreter=sys.executable,
            host_interpreter=process['executable'], entrypoint=entry, port=observer.port))
    initialize_p5_ledger(scope, material_updates=True)
    # Prepare A/B via actual SDK parsing and selection with synthetic HTTP.
    seed = P5Runtime(scope, permit=P5ExecutionPermit(scope.digest, 'SYNTHETIC', offline_test=True))
    seed.start()
    try:
        client, found, _ = discover(seed)
        a = fix(seed, found.rows, asins=['B000000001', 'B000000002'])
        proposed = [dict(selected=True, source_id=SOURCE['source_id'], input_title=SOURCE['input_title'],
                         asin='B000000004', parse_status='CANDIDATE')]
        seed.candidates.propose_resolver(proposed, human_confirmed=True, reviewer='SYNTHETIC', note='Synthetic input')
        b = fix(seed, verify_selected_rows(proposed, client), 'RESOLVER', identity='CONFIRMED')
        initial = copy.deepcopy(seed.ledger.data)
    finally:
        seed.close()
    observer.credentials = P5ServiceCredentials(
        shopee=P5CredentialResolver(credential_reference(scope, tmp_path)),
        keepa=P5KeepaReference(scope.credential_ref, scope.marketplace, scope.shop_id, 'SYNTHETIC_UNUSED'))
    operations = frozenset({'keepa.token', 'keepa.product', 'keepa.query', 'shopee.category',
                           'shopee.brand', 'bridge', 'auth', 'p2.save', 'output'})
    observer.operations = operations
    _, _, observed, approval = trusted_adapter(scope)
    observer.sources.update({k: observed['primary_sources'][k] for k in ('category', 'brand')})
    ticket = dict(version='SYNTHETIC_ONLY', scope=scope.digest, operations=sorted(operations))
    reads, sends = [], []

    def resolve(_self, current, service):
        reads.append(service)
        return replace(secrets(SimpleNamespace(scope=current)), google_credential_file='SYNTHETIC_UNUSED_FILE')

    def bridge(transport, spreadsheet_id, cell_range):
        transport.runtime.require_operation('bridge')
        transport.runtime.require_operation('auth')
        assert spreadsheet_id == scope.bridge_spreadsheet_id and cell_range == 'A:C'
        return {'values': [['marketplace', 'shop_id', 'access_token'],
                           [scope.marketplace, scope.shop_id, 'SYNTHETIC_ONLY']]}

    def send(*args, **kwargs):
        sends.append(args[0].rsplit('/', 1)[-1])
        return catalog_response(*args)

    monkeypatch.setattr(P5ServiceCredentials, 'resolve', resolve)
    monkeypatch.setattr(P5BridgeTransport, 'read_values', bridge)
    monkeypatch.setattr('modules.shopee_catalog_client._urlopen_json', send)
    active = []

    def start(number):
        process['started'] = 'SYNTHETIC_START_' + str(number)
        reviewed = replace(approval, operations=operations, ticket_digest=_digest(ticket),
                           observations_digest=_digest(observer.observe(scope)))
        record = OriginalOwnerRecord(reviewed.original_instruction_ref, reviewed.owner_ref,
            'SYNTHETIC original instruction, not real Owner authorization', reviewed.approved_at, reviewed)
        source = {'record': record}
        authority = P5OwnerAuthority(read_original=lambda ref: source['record'], read_ticket=lambda: ticket,
                                    reviewed_record=record, reviewed_ticket=ticket)
        operator = P5Operator(authority=authority, observer=observer, credentials=observer.credentials,
            checkpoint=P5Checkpoint(observer.storage.setup(), required_bytes=64 * 1024**2),
            approval_reference=record.reference)
        before = (len(reads), len(sends))
        rt = operator.compose(scope)
        rt.start()
        active.append(rt)
        assert (len(reads), len(sends)) == before
        return rt, source

    yield SimpleNamespace(start=start, scope=scope, batches=(a, b), initial=initial,
                          sends=sends, reads=reads, process=process)
    for runtime in active:
        runtime.close()


def current(runtime):
    client = runtime.catalog_client()
    runtime.acquire_catalog(client)
    runtime.acquire_brand(client, 100578)
    market = runtime.scope.marketplace
    runtime.workflow.supply_inventory((inventory(shop='22', marketplace=market, name=market+'_shop.csv'),),
        expected_shops=('22',), reference='SYNTHETIC_CURRENT', confirmed_current=True)


def test_three_sessions_preserve_selection_consumption_and_require_current_confirmation(rehearsal):
    r = rehearsal
    previous_history = ()
    previous_reservations = r.initial['reservations']
    sessions = set()
    for number in range(3):
        rt, _ = r.start(number)
        bench = rt.workflow.bench
        sessions.add(rt.workflow.session.scope.session_id)
        assert not bench.prepared_pool() and rt.category_receipt is None
        assert bench.store.history()[:len(previous_history)] == previous_history
        assert rt.candidates.data == r.initial['candidates']
        assert rt.ledger.data['reservations'] == previous_reservations
        current(rt)
        ingest(rt, r.batches[0])
        confirm(rt, 'B000000001')  # A's other product stays pending.
        if number:
            ingest(rt, r.batches[1])
            confirm(rt, 'B000000004')
        expected = ['B000000001'] + (['B000000004'] if number else [])
        assert {p['asin'] for p in bench.prepared_pool()} == set(expected)
        content, text, operation = rt.output(selected(bench, *expected))
        assert content.startswith(b'\xef\xbb\xbf') and operation is None
        rows = list(csv.DictReader(StringIO(content.decode('utf-8-sig'))))
        assert {row['asin'] for row in rows} == set(expected) and len(rows) == len(expected)
        assert all(row['marketplace'] == r.scope.marketplace
                   and row['listing_ready'] == 'TRUE'
                   and row['output_scope'] == 'PH_SG_MANUAL_PREPARATION'
                   and row['group_key'] == f"{r.scope.marketplace}|100578|7" for row in rows)
        assert b'B000000002' not in text
        for asin in expected:
            assert asin.encode() in text
        assert not bench.store.operations()
        assert all(p['listing_progress'] == 'WAITING' for p in bench.store.products())
        previous_history = bench.store.history()
        previous_reservations = copy.deepcopy(rt.ledger.data['reservations'])
        rt.close()
    assert len(sessions) == 3
    assert r.sends == ['get_category', 'get_brand_list'] * 3
    assert len(list((r.scope.directory / 'backups').glob('*/manifest.json'))) == 6


def test_revoked_original_stops_output_without_spending_or_erasing_history(rehearsal):
    rt, source = rehearsal.start(0)
    current(rt)
    ingest(rt, rehearsal.batches[0])
    confirm(rt, 'B000000001')
    history = rt.workflow.bench.store.history()
    ledger = copy.deepcopy(rt.ledger.data)
    sends = list(rehearsal.sends)
    record = source['record']
    source['record'] = replace(record, approval=replace(record.approval, revoked=True))
    with pytest.raises(P5Stopped, match='OWNER_APPROVAL'):
        rt.output(selected(rt.workflow.bench, 'B000000001'))
    assert rt.workflow.bench.store.history() == history
    assert rt.ledger.data == ledger and rehearsal.sends == sends
    assert not rt.workflow.bench.prepared_pool()


def test_unknown_submission_survives_restart_and_blocks_duplicate_output(rehearsal):
    rt, _ = rehearsal.start(0)
    current(rt)
    ingest(rt, rehearsal.batches[0])
    confirm(rt, 'B000000001')
    bench = rt.workflow.bench
    _, _, operation = rt.output(selected(bench, 'B000000001'), reserve_copy=True)
    bench.finish_copy(operation, selected(bench, 'B000000001'), outcome='UNKNOWN',
                      note='SYNTHETIC uncertainty; no actual external submission', human_confirmed=True)
    rt.close()
    rt, _ = rehearsal.start(1)
    current(rt)
    ingest(rt, rehearsal.batches[0])
    confirm(rt, 'B000000001')
    bench = rt.workflow.bench
    assert bench.session.assess(bench.store.products()[0])['valid']
    history = bench.store.history()
    ledger = copy.deepcopy(rt.ledger.data)
    sends = list(rehearsal.sends)
    with pytest.raises(WorkStoreError, match='unresolved submission'):
        rt.output(selected(bench, 'B000000001'), reserve_copy=True)
    assert bench.store.history() == history
    assert rt.ledger.data == ledger and rehearsal.sends == sends
    assert len(bench.store.operations()) == 1
    assert bench.store.operations()[0]['state'] == 'UNKNOWN'
    assert all(p['listing_progress'] == 'WAITING' for p in bench.store.products())
