"""Operational-contract simulations; these are NOT live/Owner acceptance."""
from dataclasses import replace
import sqlite3

import pytest

from modules.p5_runtime import P5Runtime, P5ExecutionPermit, initialize_p5_ledger
from modules.p5_transport import make_catalog_client
from modules.preparation_validity import InventoryEvidence
from modules.beta_work_store import WorkStoreError
from test_p5_runtime import scope_for, secrets, catalog_response, forbid_network
from test_beta_workbench_p2 import intake, selected
from test_sg_initial_beta import inventory


@pytest.fixture(params=['PH', 'SG'])
def contract_runtime(tmp_path, request, monkeypatch, forbid_network):
    scope = scope_for(tmp_path, request.param)
    initialize_p5_ledger(scope)
    permit = P5ExecutionPermit(scope.digest, 'SYNTHETIC_CONTRACT', ('fixture-C', 'fixture-B', 'fixture-A'))
    runtime = P5Runtime(scope, permit=permit, execution_identity=lambda: (scope.release, scope.execution_target))
    runtime.start()
    monkeypatch.setattr('modules.shopee_catalog_client._urlopen_json', lambda *a, **k: catalog_response(*a))
    client = make_catalog_client(runtime, secrets(runtime))
    runtime.acquire_catalog(client)
    runtime.acquire_brand(client, 100578)
    s = runtime.workflow.session
    inv = inventory(shop='22', marketplace=scope.marketplace, name=scope.marketplace+'_shop.csv')
    s.accept_inventory(InventoryEvidence(s.scope, (inv,), ('22',), 'SYNTHETIC_ONLY', True))
    intake(runtime.workflow.bench)
    yield runtime
    runtime.close()


def test_operational_download_is_not_submission(contract_runtime):
    runtime = contract_runtime
    bench = runtime.workflow.bench
    content, _, operation = runtime.output(selected(bench))
    assert b'TRUE' in content and operation is None
    assert not bench.store.operations()
    assert bench.store.products()[0]['listing_progress'] == 'WAITING'


def test_t07_attribute_refresh_during_formatting_rejects_old_bytes(contract_runtime, monkeypatch):
    rt = contract_runtime
    from modules.preparation_validity import format_preparation_groups
    original = format_preparation_groups
    def refresh(*args, **kwargs):
        result = original(*args, **kwargs)
        rt.acquire_attributes(rt.category_receipt['client'], 100578)
        return result
    monkeypatch.setattr('modules.preparation_validity.format_preparation_groups', refresh)
    with pytest.raises(ValueError):
        rt.output(selected(rt.workflow.bench), reserve_copy=True)
    assert not rt.workflow.bench.store.operations()


def test_operational_permission_revoked_during_formatting_rolls_back(contract_runtime, monkeypatch):
    runtime = contract_runtime
    from modules.preparation_validity import format_preparation_groups
    def invalidate(*a, **k):
        result = format_preparation_groups(*a, **k)
        runtime.permit = None
        return result
    monkeypatch.setattr('modules.preparation_validity.format_preparation_groups', invalidate)
    bench = runtime.workflow.bench
    before = bench.store.history()
    with pytest.raises(ValueError): runtime.output(selected(bench), reserve_copy=True)
    assert bench.store.history() == before and bench.store.operations() == ()


def test_revocation_after_commit_never_returns_bytes_and_preserves_lock(contract_runtime, monkeypatch):
    runtime = contract_runtime
    connect = sqlite3.connect
    class RevokeAfterCommit:
        def __init__(self, *a, **k): object.__setattr__(self, 'conn', connect(*a, **k))
        def __getattr__(self, name): return getattr(self.conn, name)
        def __setattr__(self, name, value): setattr(self.conn, name, value)
        def commit(self):
            changed = self.conn.total_changes
            self.conn.commit()
            if changed: runtime.permit = None
    monkeypatch.setattr('modules.beta_work_store.sqlite3.connect', RevokeAfterCommit)
    bench = runtime.workflow.bench
    # P5's read-only identity check needs the connection context manager too.
    RevokeAfterCommit.__enter__ = lambda self: self.conn.__enter__()
    RevokeAfterCommit.__exit__ = lambda self, *a: self.conn.__exit__(*a)
    with pytest.raises(ValueError): runtime.output(selected(bench), reserve_copy=True)
    assert bench.store.operations()[0]['state'] == 'PENDING'
    assert not bench.prepared_pool()


def test_mock_category_replacement_cannot_borrow_official_brand_receipt(contract_runtime):
    runtime = contract_runtime
    session = runtime.workflow.session
    catalog = session.classification_context().catalog
    runtime.workflow.supply_catalog(catalog, reference='FAKE_OFFICIAL_STRING', revision='SELF_DECLARED')
    record = runtime.workflow.bench.store.products()[0]
    with pytest.raises(ValueError): runtime.require_output_proof(record)


def test_initial_p5_never_accepts_auto_rule_or_replayed_weapon(contract_runtime):
    runtime = contract_runtime
    record = runtime.workflow.bench.store.products()[0]
    record['category']['authority'] = 'AUTO_RULE'
    with pytest.raises(ValueError, match='HUMAN_ONLY'): runtime.require_output_proof(record)
    record['category']['authority'] = 'HUMAN'
    from modules.image_inspection_policy import load_image_inspection_policy
    record['weapon']['images']['root_category_id'] = min(load_image_inspection_policy(runtime.scope.marketplace).target_roots)
    with pytest.raises(ValueError, match='IMAGE_ACQUISITION'): runtime.require_output_proof(record)
    from modules.sg_beta_facts import digest
    # Acquisition-proof contract only: P1's separate Safety validation still
    # owns whether REVIEW may prepare. An ID cannot authorize altered content.
    record['weapon']['inspection'] = {'evaluation_id': 'SYNTHETIC_ONLY', 'ai_status': 'REVIEW'}
    runtime.weapon_receipts[record['asin']] = (
        digest([record['facts'], record['source'], record['weapon']['images']]), digest(record['weapon']['inspection']))
    runtime.require_output_proof(record)
    record['weapon']['inspection']['ai_status'] = 'NO_SIGNAL'
    with pytest.raises(ValueError, match='IMAGE_ACQUISITION'): runtime.require_output_proof(record)


def test_sg_formal_gate_still_rechecks_after_output_commit(contract_runtime, monkeypatch):
    runtime = contract_runtime
    if runtime.scope.marketplace != 'SG':
        return
    calls = []
    def require(): calls.append(1)
    monkeypatch.setattr('modules.sg_beta_release.require_sg_beta_operation', require)
    runtime.output(selected(runtime.workflow.bench))
    assert len(calls) >= 5
