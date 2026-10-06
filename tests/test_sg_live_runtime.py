from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import pytest
from modules import sg_live_runtime as runtime
from modules.shopee_catalog_client import ShopeeCatalogClient,ShopeeCatalogCredentials
from modules.sg_live_validation import LiveValidationStopped
from test_sg_live_validation import payload

@pytest.fixture(autouse=True)
def isolated_claims(tmp_path,monkeypatch):
    monkeypatch.setattr(runtime,"CLAIM_DIR",tmp_path/"claims")

@pytest.fixture
def grant():
    return runtime.SGLiveRunGrant(("B000000001",),22,"synthetic-bridge",(11,),3,3,3,"0","Synthetic owner test authorization")


def factory(calls, *, fail=False, shop=22):
    def fresh():
        calls.append("fresh token")
        client=ShopeeCatalogClient(ShopeeCatalogCredentials(1,"synthetic",shop,"synthetic-token"),marketplace="SG")
        def get(path,params):
            if fail: raise RuntimeError("PRIVATE_TRANSPORT_MARKER")
            calls.append(path)
            if path.endswith("get_category"):
                return {"response":{"category_list":[{"category_id":11,"parent_category_id":0,"display_category_name":"Synthetic Leaf","has_children":False}]}}
            if path.endswith("get_attribute_tree"):
                return {"response":{"list":[{"category_id":11,"attribute_tree":[]}]}}
            return {"response":{"brand_list":[],"has_next_page":False,"next_offset":0}}
        client._get=get
        return client
    return fresh


def test_runtime_creation_and_rerun_are_local_only(tmp_path,grant):
    calls=[]; r=runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/"run",fresh_client_factory=factory(calls))
    assert calls==[] and r.category_engine is None and not r.workflow.can_inspect_images
    assert callable(r.workflow.product_review.image_inspection_required)
    assert r.refresh_catalog()==1
    assert calls==["fresh token","/api/v2/product/get_category"]
    r.close()
    r=runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/"run",fresh_client_factory=factory(calls))
    assert r.ledger.data["catalog_requests"]==1
    with pytest.raises(ValueError): r.workflow.require_catalog_current()
    r.refresh_catalog(); assert calls.count("fresh token")==2
    r.close()


def test_new_location_or_changed_grant_cannot_reset_existing_run(tmp_path,grant):
    r=runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/"run",fresh_client_factory=factory([])); r.close()
    with pytest.raises(ValueError): runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/"another",fresh_client_factory=factory([]))
    with pytest.raises(ValueError): runtime.SGLiveRuntime(grant=replace(grant,catalog_request_limit=4),run_path=tmp_path/"run",fresh_client_factory=factory([]))


def test_missing_ledger_refuses_reset(tmp_path,grant):
    r=runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/"run",fresh_client_factory=factory([])); r.close()
    (tmp_path/"run"/"request-ledger.json").unlink()
    with pytest.raises(ValueError): runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/"run",fresh_client_factory=factory([]))


def test_concurrent_runtime_cannot_spend_same_grant(tmp_path,grant):
    r=runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/"run",fresh_client_factory=factory([]))
    try:
        with pytest.raises((ValueError,OSError)): runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/"run",fresh_client_factory=factory([]))
    finally: r.close()


def test_failed_requests_and_restart_keep_consumption(tmp_path,grant):
    calls=[]; r=runtime.SGLiveRuntime(grant=replace(grant,catalog_request_limit=1),run_path=tmp_path/"run",fresh_client_factory=factory(calls,fail=True))
    with pytest.raises(RuntimeError): r.refresh_catalog()
    assert r.client.catalog_refresh_failed
    assert r.ledger.data["catalog_requests"]==1
    r.close()
    r=runtime.SGLiveRuntime(grant=replace(grant,catalog_request_limit=1),run_path=tmp_path/"run",fresh_client_factory=factory(calls))
    with pytest.raises(ValueError): r.refresh_catalog()
    assert calls==["fresh token"]
    r.close()


def test_each_endpoint_gets_fresh_bound_token_and_stops_out_of_scope(tmp_path,grant):
    calls=[]; r=runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/"run",fresh_client_factory=factory(calls))
    r.refresh_catalog(); r.client.get_attribute_tree("SG",11); r.client.get_brand_list("SG",11)
    assert calls.count("fresh token")==3
    assert r.ledger.data["attribute_requests"]==1 and r.ledger.data["brand_page_counts"]=={"11":1}
    before=list(calls)
    with pytest.raises(ValueError): r.client.get_brand_list("SG",12)
    with pytest.raises(ValueError): r.client.get_attribute_tree("SG",12)
    with pytest.raises(ValueError): r.client.get_categories("PH")
    assert calls==before
    r.close()


def test_wrong_shop_stops_before_catalog_endpoint(tmp_path,grant):
    calls=[]; r=runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/"run",fresh_client_factory=factory(calls,shop=23))
    with pytest.raises(ValueError): r.refresh_catalog()
    assert calls==["fresh token"]
    r.close()


def test_paid_reservation_and_failure_survive_restart(tmp_path,grant):
    g=replace(grant,openai_limit_usd="1")
    r=runtime.SGLiveRuntime(grant=g,run_path=tmp_path/"run",fresh_client_factory=factory([]),api_key="synthetic")
    b=runtime.PersistentSGOpenAIBudget(r.ledger); b.reserve(payload()); before=b.summary(); r.close()
    r=runtime.SGLiveRuntime(grant=g,run_path=tmp_path/"run",fresh_client_factory=factory([]),api_key="synthetic")
    b=runtime.PersistentSGOpenAIBudget(r.ledger); assert b.summary()==before
    with pytest.raises(ValueError): b.reserve(payload(model="unknown"))
    r.close()
    r=runtime.SGLiveRuntime(grant=g,run_path=tmp_path/"run",fresh_client_factory=factory([]),api_key="synthetic")
    b=runtime.PersistentSGOpenAIBudget(r.ledger); assert b.stopped
    with pytest.raises(ValueError): b.reserve(payload())
    r.close()


@pytest.mark.parametrize("changes", [{"openai_limit_usd":"2"},{"openai_limit_usd":"NaN"},{"brand_category_ids":()},{"catalog_request_limit":True},{"authorization_ref":""}])
def test_invalid_grant_has_no_requests(tmp_path,grant,changes):
    calls=[]
    with pytest.raises(ValueError): runtime.SGLiveRuntime(grant=replace(grant,**changes),run_path=tmp_path/"run",fresh_client_factory=factory(calls))
    assert not calls


def test_corrupt_ledger_fails_closed(tmp_path,grant):
    r=runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/"run",fresh_client_factory=factory([])); r.close()
    ledger=tmp_path/"run"/"request-ledger.json"; data=json.loads(ledger.read_text()); data["brand_page_counts"]["11"]=-1; ledger.write_text(json.dumps(data))
    with pytest.raises(ValueError): runtime.SGLiveRuntime(grant=grant,run_path=tmp_path/"run",fresh_client_factory=factory([]))


def test_real_factory_reads_latest_bridge_without_changing_environment(grant,monkeypatch):
    import os
    from modules.shopee_access_token_source import AccessToken
    observed=[]; values=iter(("synthetic-token-a","synthetic-token-b"))
    monkeypatch.setattr(runtime,"load_shopee_catalog_credentials",lambda *a,**kw: ShopeeCatalogCredentials(1,"synthetic",22,"old-token"))
    class Source:
        def __init__(self,bridge): assert bridge==grant.bridge_spreadsheet_id
        def get_access_token(self,market,shop):
            observed.append((market,shop)); return AccessToken(next(values))
    monkeypatch.setattr(runtime,"GoogleSheetAccessTokenSource",Source)
    before=dict(os.environ); fresh=runtime.existing_sg_client_factory(grant)
    assert fresh().credentials.access_token=="synthetic-token-a"
    assert fresh().credentials.access_token=="synthetic-token-b"
    assert observed==[("SG",22),("SG",22)] and dict(os.environ)==before


def test_paid_ai_rejects_other_product_before_any_transport(tmp_path,grant):
    from modules.category_ai_core import ProductEvidence
    from test_ph_image_safety_api import Session
    api=Session(); g=replace(grant,openai_limit_usd="1")
    r=runtime.SGLiveRuntime(grant=g,run_path=tmp_path/"run",fresh_client_factory=factory([]),api_key="synthetic",api_session=api)
    r.refresh_catalog()
    with pytest.raises(ValueError): r.category_engine.predict(ProductEvidence("SG","case","Product",asin="B000000002"),None,None)
    assert not api.calls and r.ledger.data["openai"]["requests"]==0
    r.close()
