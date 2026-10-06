"""Live wiring tests are synthetic; they never execute an external API."""

from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from modules.category_mapper_sg_brand_workflow import SGBrandWorkflow
from modules.sg_live_validation import SGLiveValidationScope, OpenAIValidationBudget, BudgetedOpenAISession, LiveValidationStopped
from modules.weapon_image_inspection import BudgetedLiveWeaponImageInspector
from modules.ph_image_safety_api import RESPONSES_URL
from test_sg_brand_confirmation_ui import preview, workflow_preview
from test_product_review import evidence
from test_ph_image_safety_api import Session, Response, body


def payload(**changes):
    return {"model": "gpt-5.6-terra", "store": False, "max_output_tokens": 1200,
            "input": [{"role": "user", "content": [{"type": "input_image", "image_url": "data:image/png;base64,YQ=="}]}],
            **changes}


def test_budget_charges_before_calls_and_never_refunds_timeout(tmp_path):
    transport = Session(requests.Timeout())
    ledger = tmp_path / "budget.json"
    budget = OpenAIValidationBudget(ledger_path=ledger)
    session = BudgetedOpenAISession(budget, session=transport)
    with pytest.raises(requests.Timeout): session.post(RESPONSES_URL, json=payload())
    assert budget.request_count == 1 and budget.reserved_usd > 0
    saved = json.loads(ledger.read_text())
    assert saved["requests"] == 1 and "Authorization" not in ledger.read_text()
    with pytest.raises(LiveValidationStopped): OpenAIValidationBudget(ledger_path=ledger)


def test_budget_exhaustion_prevents_next_network_request():
    transport = Session(*(Response(data={}) for _ in range(30)))
    budget = OpenAIValidationBudget()
    session = BudgetedOpenAISession(budget, session=transport)
    with pytest.raises(LiveValidationStopped):
        for _ in range(30): session.post(RESPONSES_URL, json=payload())
    assert len(transport.calls) == budget.request_count and budget.request_count > 0
    assert 0 < budget.reserved_usd <= Decimal("1") and budget.stopped
    before = len(transport.calls)
    with pytest.raises(LiveValidationStopped): session.post(RESPONSES_URL, json=payload())
    assert len(transport.calls) == before


@pytest.mark.parametrize("change", [{"model": "unknown"}, {"store": True}, {"max_output_tokens": 1201},
    {"max_output_tokens": True}, {"stream": True}, {"tools": [{"type": "web_search"}]},
    {"input": [{"type": "input_image", "image_url": "https://unknown.invalid/image"}]},
    {"input": [{"type": "input_image", "image_url": "data:image/png;base64,YQ=="}] * 4},
    {"input": "x" * 280000}])
def test_unbounded_or_unknown_paid_profile_never_reaches_network(change):
    transport = Session()
    budget = OpenAIValidationBudget()
    with pytest.raises(LiveValidationStopped): BudgetedOpenAISession(budget, session=transport).post(RESPONSES_URL, json=payload(**change))
    assert not transport.calls and budget.request_count == 0


@pytest.mark.parametrize("amount", [0, -1, 2, "NaN", "Infinity"])
def test_owner_budget_cannot_be_increased(amount):
    with pytest.raises(ValueError): OpenAIValidationBudget(limit_usd=amount)


def test_session_pins_standard_tier_redirects_and_original_payload_is_unchanged():
    transport = Session(Response(data={}))
    original = payload(service_tier="auto")
    session = BudgetedOpenAISession(OpenAIValidationBudget(), session=transport)
    session.post(RESPONSES_URL, json=original)
    assert original["service_tier"] == "auto"
    assert transport.calls[0][1]["json"]["service_tier"] == "default"
    assert transport.calls[0][1]["allow_redirects"] is False
    with pytest.raises(ValueError): session.post("https://untrusted.invalid", json=payload())
    assert len(transport.calls) == 1


@pytest.mark.parametrize("asins", [(), ("B000000001",) * 2, tuple(f"B00000000{i}" for i in range(4)), ("bad",)])
def test_scope_enforces_three_unique_products(tmp_path, asins):
    with pytest.raises(ValueError): SGLiveValidationScope(asins, 22, tmp_path / "db.sqlite3")


def test_live_scope_refuses_normal_database(monkeypatch, tmp_path):
    import modules.sg_live_validation as validation
    normal = tmp_path / "normal.sqlite3"
    monkeypatch.setattr(validation, "default_category_mapper_db_path", lambda: normal)
    with pytest.raises(LiveValidationStopped):
        SGLiveValidationScope(("B000000001",), 22, normal)


@pytest.mark.parametrize("limit,categories", [(51, (11,)), (True, (11,)),
    (50, ()), (50, (True,)), (50, (11, 11)), (50, (11, 12, 13, 14))])
def test_extended_brand_grant_requires_bounded_category_allowlist(tmp_path, limit, categories):
    with pytest.raises(LiveValidationStopped):
        SGLiveValidationScope(("B000000001",), 22, tmp_path / "db.sqlite3",
                              brand_page_limit=limit, allowed_brand_category_ids=categories)


def test_extended_brand_grant_counts_repeated_requests_and_rejects_other_category(tmp_path):
    scope = SGLiveValidationScope(("B000000001",), 22, tmp_path / "db.sqlite3",
                                 brand_page_limit=50, allowed_brand_category_ids=(11, 12, 13))
    with pytest.raises(LiveValidationStopped):
        scope.reserve_brand_page(14)
    for category in (11, 12, 13):
        for _ in range(50):
            scope.reserve_brand_page(category)
        with pytest.raises(LiveValidationStopped):
            scope.reserve_brand_page(category)
    assert sum(scope._brand_page_counts.values()) == 150


def test_cli_bridge_failure_stops_before_keepa_or_paid_calls(monkeypatch, tmp_path, capsys):
    import dotenv
    import keepa
    from scripts import sg_live_smoke as smoke
    from modules.shopee_access_token_source import AccessTokenSourceError
    calls = []
    fixture = Path(__file__).parent / "fixtures/browser_e2e/sg_candidate/prelisting_gate_eligible_sg_expansion.csv"
    monkeypatch.setattr(smoke, "load_shopee_catalog_credentials", lambda **kwargs: SimpleNamespace(shop_id=22))
    monkeypatch.setattr(dotenv, "dotenv_values", lambda path: {})
    def unavailable(**kwargs):
        calls.append(kwargs)
        raise AccessTokenSourceError("Google Sheet Access Token Source is unavailable.")
    monkeypatch.setattr(smoke.ShopeeCatalogClient, "from_local_audit_env", unavailable)
    def never_keepa(*args, **kwargs):
        pytest.fail("Keepa must not run after Bridge failure")
    monkeypatch.setattr(keepa, "Keepa", never_keepa)
    monkeypatch.setattr(smoke.sys, "argv", ["sg_live_smoke", "--input", str(fixture),
        "--api-env", str(tmp_path / "unused.env"), "--output", str(tmp_path / "run"),
        "--bridge-spreadsheet-id", "synthetic-bridge", "--execute-live"])
    monkeypatch.setenv("SHOPEE_GOOGLE_SHEET_TOKEN_SOURCE_ENABLED", "0")
    monkeypatch.setenv("SHOPEE_GOOGLE_SHEET_BRIDGE_SPREADSHEET_ID", "previous")
    assert smoke.main() == 2
    assert calls == [{"marketplace": "SG"}]
    result = json.loads(capsys.readouterr().out)
    assert result == {"decision": "LIVE_VALIDATION_STOPPED", "error_type": "AccessTokenSourceError"}
    assert not (tmp_path / "run").exists()


def test_category_probe_diagnostics_exclude_reasoning_and_unstructured_provider_errors():
    from scripts.sg_live_smoke import category_transport_summary
    result = category_transport_summary(SimpleNamespace(status="FAILED", error_code="RESPONSE_INCOMPLETE",
                                                        api_call_count=2, traversal_steps=("private step",),
                                                        short_reason="private product or provider details"))
    assert result == {"check": "CATEGORY_AI", "status": "FAILED", "error_code": "RESPONSE_INCOMPLETE",
                      "api_call_count": 2, "completed_traversal_steps": 1}
    assert "private" not in json.dumps(result)
    result = category_transport_summary(SimpleNamespace(status="FAILED", error_code="private unexpected text",
                                                        api_call_count=1, traversal_steps=()))
    assert result["error_code"] == "UNCLASSIFIED_FAILURE"


@pytest.mark.parametrize("outcome,expected_counter,expected_code", [
    ("select", "category_ai_completed", ""),
    ("abstain", "category_ai_abstained", ""),
    ("timeout", "category_ai_failed", "TIMEOUT"),
])
@pytest.mark.parametrize("selection", ["TARGET_ROOT", "OTHER_ROOT"])
def test_probe_distinguishes_abstention_from_transport_failure(monkeypatch, tmp_path, outcome, expected_counter, expected_code, selection):
    from scripts import sg_live_smoke as smoke
    from modules.category_ai_core import FakeCategoryAIProvider, CategoryAIError, make_fake_select, make_fake_abstain
    from modules.shopee_catalog_client import ShopeeCatalogCredentials
    row = SimpleNamespace(candidate_asin="B000000001", source_asin="B000000000",
                          product_title="Synthetic item", keepa_brand="Maker", keepa_category="Category")
    source = SimpleNamespace(rows=(row,), source_type="EXPANSION")
    product = {"title": row.product_title, "brand": row.keepa_brand, "category": row.keepa_category,
               "ph_image_safety_fact": {}}
    # Only external transports are replaced; the real AI engine and report writer run.
    fake_outcome = {"select": make_fake_select(10), "abstain": make_fake_abstain(),
                    "timeout": CategoryAIError("TIMEOUT", api_call_count=1)}[outcome]
    provider = FakeCategoryAIProvider((fake_outcome,))
    monkeypatch.setattr(smoke, "OpenAIResponsesCategoryProvider", lambda *a, **k: provider)
    monkeypatch.setattr(smoke, "BudgetedLiveWeaponImageInspector", lambda **k: None)
    review = SimpleNamespace(image_selection=lambda *a: selection, supply=lambda *a, **k: None,
                             current=lambda *a: SimpleNamespace(guardrail_status="SAFE", binding="synthetic"))
    monkeypatch.setattr(smoke, "SGBrandWorkflow", lambda **k: SimpleNamespace(product_review=review,
                        inspect_product_images=lambda *a: SimpleNamespace(system_status="COMPLETED", ai_status="NO_SIGNAL")))
    credentials = ShopeeCatalogCredentials(1, "synthetic-key", 22, "synthetic-token")
    client = SimpleNamespace(marketplace="SG", credentials=credentials,
                get_categories=lambda *a: [{"category_id": 10, "parent_category_id": None,
                                           "category_name": "Leaf", "is_leaf": True}])
    report = smoke.probe(source=source, credentials=credentials, api_key="synthetic-key",
                         products={row.candidate_asin: product}, output_dir=tmp_path / "run", catalog_client=client)
    assert report[expected_counter] == 1
    assert report["image_not_target"] == int(selection == "OTHER_ROOT")
    assert report["image_completed"] == int(selection != "OTHER_ROOT")
    assert sum(report[k] for k in ("category_ai_completed", "category_ai_abstained", "category_ai_failed")) == 1
    assert report["decision"] == ("LIVE_TRANSPORT_CHECK_COMPLETE" if outcome == "select" else "LIVE_TRANSPORT_PARTIAL")
    saved = json.loads((tmp_path / "run" / "transport_results.json").read_text())[-1]
    assert saved["error_code"] == expected_code and saved["api_call_count"] == 1
    assert "short_reason" not in saved and "synthetic-token" not in json.dumps(saved)
    assert report["human_confirmations_created"] == report["listing_ready_true"] == 0


def test_live_scope_product_and_store_binding_and_offline_default_are_preserved(workflow_preview):
    app, previous, calls, _ = workflow_preview
    item = app.session_state["sg_category_mapper_recommendations"][0]
    scope = SGLiveValidationScope((item.candidate_asin,), previous._client.credentials.shop_id, previous.store.db_path)
    scope.require_client(previous._client, previous.store)
    with pytest.raises(ValueError): scope.require_product(replace(item, marketplace="PH"))
    with pytest.raises(ValueError): scope.require_product(replace(item, candidate_asin="B000000009"))
    from modules.shopee_catalog_client import ShopeeCatalogClient
    default = ShopeeCatalogClient(previous._client.credentials, marketplace="SG")
    with pytest.raises(ValueError): SGBrandWorkflow(store=previous.store, client=default)
    workflow = SGBrandWorkflow(store=previous.store, client=previous._client, live_validation_scope=scope)
    assert workflow.fetch(item).status == "SUCCESS" and len(calls) == 1
    with pytest.raises(ValueError): workflow.fetch(replace(item, candidate_asin="B000000009"))
    assert len(calls) == 1
    altered = replace(scope, shop_id=33)
    with pytest.raises(ValueError): altered.require_client(previous._client, previous.store)


def test_live_image_transport_needs_live_scope_and_shared_budget(workflow_preview):
    app, previous, _, _ = workflow_preview
    item = app.session_state["sg_category_mapper_recommendations"][0]
    api, images = Session(Response(data=body())), Session(Response())
    budget = OpenAIValidationBudget()
    adapter = BudgetedLiveWeaponImageInspector(api_key="synthetic-test", budget=budget,
                                               api_session=api, image_session=images)
    with pytest.raises(ValueError): SGBrandWorkflow(store=previous.store, client=previous._client, image_inspector=adapter)
    scope = SGLiveValidationScope((item.candidate_asin,), previous._client.credentials.shop_id, previous.store.db_path)
    workflow = SGBrandWorkflow(store=previous.store, client=previous._client, image_inspector=adapter, live_validation_scope=scope)
    text, image_fact = evidence(item)
    workflow.product_review.supply(item, text=text, images=image_fact)
    inspection = workflow.inspect_product_images(item)
    assert inspection.ai_status == "NO_SIGNAL" and budget.request_count == 1
    assert workflow.product_review.decision(item) is None
    assert not item.listing_ready
