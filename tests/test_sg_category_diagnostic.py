"""Offline diagnostics tests: paid calls replaced with scripted Responses."""

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from modules.category_ai_core import CategoryCatalog, CategoryNode, make_fake_select, make_fake_abstain
from scripts import sg_category_diagnostic as diagnostic
from test_category_ai_openai import Response, Session, response_body


def inputs():
    row = SimpleNamespace(candidate_asin="B000000001", product_title="Synthetic item",
                          keepa_brand="Maker", keepa_category="Category")
    return SimpleNamespace(rows=(row,)), CategoryCatalog("SG", "synthetic", (CategoryNode(10, None, "Leaf", "Leaf", True),))


@pytest.mark.parametrize("outcome,status,code", [
    (make_fake_select(10), "COMPLETED", ""),
    (make_fake_abstain(), "ABSTAIN", ""),
    ({"not": "valid"}, "FAILED", "SCHEMA_VIOLATION"),
])
def test_category_only_diagnostic_records_status_without_product_text(tmp_path, outcome, status, code):
    source, catalog = inputs()
    session = Session(Response(body=response_body(output_text=json.dumps(outcome), model="gpt-5.6-luna")))
    report = diagnostic.execute(source, catalog, tmp_path / "run", "synthetic-key", session=session)
    assert report["results"][0]["status"] == status
    assert report["results"][0]["error_code"] == code
    assert len(session.calls) == 1
    assert report["budget"]["limit_usd"] == "0.10" and report["budget"]["requests"] == 1
    saved = (tmp_path / "run" / "diagnostic.json").read_text()
    assert "Synthetic item" not in saved and "synthetic-key" not in saved and "short_reason" not in saved
    assert report["human_confirmations_created"] == 0 and not report["normal_environment_modified"]
    with pytest.raises(FileExistsError):
        diagnostic.execute(source, catalog, tmp_path / "run", "synthetic-key", session=session)
    assert len(session.calls) == 1


def test_default_cli_is_offline(monkeypatch, capsys):
    source, catalog = inputs()
    monkeypatch.setattr(diagnostic, "prepare", lambda *a: (source, catalog))
    monkeypatch.setattr(diagnostic, "execute", lambda *a, **k: pytest.fail("Offline default reached paid execution"))
    monkeypatch.setattr("sys.argv", ["diagnostic", "--input", "synthetic.csv", "--catalog", "catalog.csv"])
    assert diagnostic.main() == 0
    assert json.loads(capsys.readouterr().out)["external_api_calls"] == 0


def test_scope_rejects_extra_products_before_creating_output(tmp_path):
    source, catalog = inputs()
    source.rows = source.rows * 4
    with pytest.raises(ValueError):
        diagnostic.execute(source, catalog, tmp_path / "run", "synthetic-key")
    assert not (tmp_path / "run").exists()


def test_remaining_budget_carries_previous_reservation_and_cannot_be_claimed_twice(tmp_path):
    source, catalog = inputs()
    session = Session(Response(body=response_body(output_text=json.dumps(make_fake_abstain()), model="gpt-5.6-luna")))
    prior = diagnostic.execute(source, catalog, tmp_path / "prior", "synthetic-key", session=session)
    child = diagnostic.execute(source, catalog, tmp_path / "child", "synthetic-key", session=session, prior_dir=tmp_path / "prior")
    assert Decimal(child["budget"]["limit_usd"]) == Decimal("0.10") - Decimal(prior["budget"]["reserved_upper_bound_usd"])
    assert Decimal(child["grant_cumulative_reserved_usd"]) == Decimal(prior["budget"]["reserved_upper_bound_usd"]) + Decimal(child["budget"]["reserved_upper_bound_usd"])
    assert child["results"][0]["classification_trace"][0]["decision"] == "ABSTAIN"
    assert child["results"][0]["classification_trace"][0]["candidates"][0]["category_id"] == 10
    with pytest.raises(FileExistsError):
        diagnostic.execute(source, catalog, tmp_path / "duplicate-child", "synthetic-key", session=session, prior_dir=tmp_path / "prior")
    assert len(session.calls) == 2
    assert json.loads((tmp_path / "prior" / "budget.json").read_text()) == prior["budget"]


def test_prior_catalog_mismatch_blocks_before_network(tmp_path):
    source, catalog = inputs()
    session = Session(Response(body=response_body(output_text=json.dumps(make_fake_abstain()), model="gpt-5.6-luna")))
    diagnostic.execute(source, catalog, tmp_path / "prior", "synthetic-key", session=session)
    changed = CategoryCatalog("SG", "changed", catalog.nodes)
    with pytest.raises(ValueError):
        diagnostic.execute(source, changed, tmp_path / "child", "synthetic-key", session=session, prior_dir=tmp_path / "prior")
    assert len(session.calls) == 1
    assert not (tmp_path / "prior" / "remaining-budget-claimed.json").exists()


def test_trace_identifies_actual_abstention_branch_and_candidates():
    from modules.category_ai_core import CategoryAIEngine, FakeCategoryAIProvider, ProductEvidence
    catalog = CategoryCatalog("SG", "synthetic", (
        CategoryNode(10, None, "Root", "Root", False),
        CategoryNode(11, 10, "Leaf", "Root > Leaf", True),
    ))
    engine = CategoryAIEngine(FakeCategoryAIProvider((make_fake_select(10), make_fake_abstain(reason="No appropriate dedicated category"))))
    prediction = engine.predict(ProductEvidence("SG", "synthetic", "Synthetic item"), catalog, diagnostic.load_luna_request_profile())
    trace = diagnostic.classification_trace(prediction, catalog)
    assert trace[0]["selected_category_id"] == 10
    assert trace[1]["parent_category_id"] == 10 and trace[1]["decision"] == "ABSTAIN"
    assert [x["category_id"] for x in trace[1]["candidates"]] == [11]
    assert trace[1]["brief_classification_explanation"] == "No appropriate dedicated category"
