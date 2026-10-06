"""Category-only SG diagnostic using saved input/catalog; dry run by default.

Paid execution requires a separate owner grant for this run, up to USD 0.10.
It does not reuse/reset the previous three-product live probe's budget.
"""

import argparse
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.category_ai_core import CategoryAIEngine, ProductEvidence
from modules.category_ai_openai import OpenAIResponsesCategoryProvider
from modules.category_mapper_ai import load_luna_request_profile
from modules.category_mapper_sg import parse_sg_category_catalog, parse_sg_category_mapper_input
from modules.sg_live_validation import OpenAIValidationBudget, BudgetedOpenAISession, LiveValidationStopped
from scripts.sg_live_smoke import category_transport_summary


def remaining_budget(prior_dir, source, catalog):
    """Allocate the remaining grant once; never reset a previous ledger."""
    prior_dir = Path(prior_dir)
    report = json.loads((prior_dir / "diagnostic.json").read_text(encoding="utf-8"))
    ledger = json.loads((prior_dir / "budget.json").read_text(encoding="utf-8"))
    expected = [hashlib.sha256(r.candidate_asin.encode()).hexdigest() for r in source.rows]
    if (report.get("scope") != "SG_CATEGORY_ONLY_DIAGNOSTIC"
            or report.get("catalog_hash") != catalog.catalog_hash
            or [r.get("asin_binding") for r in report.get("results", [])] != expected
            or report.get("budget") != ledger or ledger.get("stopped") is not False
            or ledger.get("limit_usd") != "0.10"
            or type(ledger.get("requests")) is not int or ledger["requests"] < 0):
        raise LiveValidationStopped("Previous diagnostic binding/budget invalid")
    spent = Decimal(ledger["reserved_upper_bound_usd"])
    if not spent.is_finite() or not Decimal("0") <= spent < Decimal("0.10"):
        raise LiveValidationStopped("Previous diagnostic budget unavailable")
    remaining = Decimal("0.10") - spent
    # An exclusive claim prevents multiple fresh child runs using the same remainder.
    with (prior_dir / "remaining-budget-claimed.json").open("x", encoding="utf-8") as file:
        json.dump({"allocated_remaining_usd": str(remaining), "prior_reserved_usd": str(spent)}, file)
    return remaining, spent


def classification_trace(prediction, catalog):
    """Private brief classification answers, not raw responses or hidden reasoning."""
    return [{"parent_category_id": step.parent_category_id,
             "current_path": step.parent_category_path, "decision": step.decision,
             "selected_category_id": step.selected_category_id,
             "selected_path": step.selected_category_path,
             "candidates": [node.candidate_dict() for node in catalog.children_of(step.parent_category_id)],
             "brief_classification_explanation": step.short_reason[:600]}
            for step in prediction.traversal_steps]


def prepare(input_path, catalog_path):
    source = parse_sg_category_mapper_input(input_path.read_bytes(), filename=input_path.name)
    asins = tuple(row.candidate_asin for row in source.rows)
    if not 1 <= len(asins) <= 3 or len(set(asins)) != len(asins):
        raise LiveValidationStopped("Diagnostic requires one to three unique products")
    # The accepted SG parser validates the entire saved tree without a DB write.
    catalog = parse_sg_category_catalog(catalog_path.read_bytes(), filename=catalog_path.name)
    return source, catalog


def execute(source, catalog, output_dir, api_key, *, session=None, prior_dir=None, leaf_search=False):
    asins = tuple(row.candidate_asin for row in source.rows)
    if catalog.marketplace != "SG" or not 1 <= len(asins) <= 3 or len(set(asins)) != len(asins):
        raise LiveValidationStopped("Invalid SG diagnostic scope")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    limit, prior_reserved = remaining_budget(prior_dir, source, catalog) if prior_dir else (Decimal("0.10"), Decimal("0"))
    budget = OpenAIValidationBudget(limit_usd=limit, ledger_path=output_dir / "budget.json")
    transport = BudgetedOpenAISession(budget, session=session)
    if leaf_search:
        from modules.category_ai_leaf_search import LeafSearchEngine, LeafSearchProvider
        engine = LeafSearchEngine(LeafSearchProvider(api_key, session=transport))
    else:
        engine = CategoryAIEngine(OpenAIResponsesCategoryProvider(api_key, session=transport))
    results = []
    try:
        for row in source.rows:
            prediction = engine.predict(ProductEvidence("SG", row.candidate_asin, row.product_title,
                asin=row.candidate_asin, keepa_category=row.keepa_category, keepa_brand=row.keepa_brand),
                catalog, load_luna_request_profile())
            results.append({"asin_binding": hashlib.sha256(row.candidate_asin.encode()).hexdigest(),
                            **category_transport_summary(prediction),
                            "predicted_category_id": prediction.predicted_category_id,
                            "predicted_category_path": prediction.predicted_category_path,
                            "classification_trace": engine.last_trace if leaf_search else classification_trace(prediction, catalog)})
    except LiveValidationStopped:
        # Preserve earlier safe diagnostics and the charged ledger on budget stop.
        budget.stopped = True
    report = {"scope": "SG_CATEGORY_ONLY_DIAGNOSTIC", "selected_products": len(source.rows),
              "results": results, "budget": budget.summary(), "budget_stopped": budget.stopped,
              "input_basis": "SAVED_PREVIOUS_PROBE_INPUT_AND_CATALOG",
              "catalog_hash": catalog.catalog_hash,
              "algorithm": "CATEGORY_LEAF_SEARCH_V2" if leaf_search else "HIERARCHICAL_TRAVERSAL_V1",
              "grant_cumulative_reserved_usd": str(prior_reserved + budget.reserved_usd),
              "human_confirmations_created": 0, "normal_environment_modified": False}
    (output_dir / "diagnostic.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--api-env", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prior-diagnostic", type=Path, help="Claim unspent portion of a previous USD0.10 grant once")
    parser.add_argument("--leaf-search", action="store_true", help="Explicit isolated V2 leaf-first candidate search")
    parser.add_argument("--execute-live", action="store_true")
    args = parser.parse_args()
    try:
        source, catalog = prepare(args.input, args.catalog)
        if not args.execute_live:
            print(json.dumps({"decision": "OFFLINE_INPUT_AND_CATALOG_VALID", "selected_products": len(source.rows),
                              "catalog_nodes": len(catalog.nodes), "external_api_calls": 0,
                              "paid_run_ceiling_usd": "0.10"}))
            return 0
        if args.output is None or args.api_env is None or args.output.exists():
            raise LiveValidationStopped("Fresh output and existing API settings required")
        from dotenv import dotenv_values
        key = os.getenv("OPENAI_API_KEY") or dotenv_values(args.api_env).get("OPENAI_API_KEY") or ""
        report = execute(source, catalog, args.output, key, prior_dir=args.prior_diagnostic, leaf_search=args.leaf_search)
        # Detailed category paths and brief answers stay in the private artifact.
        print(json.dumps({**report, "results": [{k:v for k,v in r.items() if k != "classification_trace"}
                                                for r in report["results"]]}))
        return 2 if report["budget_stopped"] or any(r["status"] == "FAILED" for r in report["results"]) else 0
    except Exception as exc:
        print(json.dumps({"decision": "DIAGNOSTIC_STOPPED", "error_type": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
