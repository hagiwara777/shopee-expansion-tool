"""Owner-authorized SG read-only probe. Explicit CLI only; no ordinary UI link."""

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.category_ai_core import CategoryAIEngine
from modules.category_ai_openai import OpenAIResponsesCategoryProvider
from modules.category_mapper_ai import load_luna_request_profile
from modules.category_mapper_sg import (
    SGMapperRecommendation, parse_sg_category_mapper_input,
    build_sg_category_catalog_csv, parse_sg_category_catalog, build_sg_category_ai_catalog,
)
from modules.category_mapper_sg_brand_workflow import SGBrandWorkflow
from modules.category_mapper_store import CategoryMapperStore
from modules.product_text_safety import product_text_safety_fact_from_product_data
from modules.sg_live_validation import SGLiveValidationScope, OpenAIValidationBudget, BudgetedOpenAISession
from modules.shopee_catalog_client import ShopeeCatalogClient, load_shopee_catalog_credentials
from modules.weapon_image_inspection import BudgetedLiveWeaponImageInspector


def category_transport_summary(prediction):
    """Persist machine status only, never model reasoning or request contents."""
    code = prediction.error_code
    if prediction.status == "FAILED" and (not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code)):
        code = "UNCLASSIFIED_FAILURE"
    return {"check": "CATEGORY_AI", "status": prediction.status,
            "error_code": code if prediction.status == "FAILED" else "",
            "api_call_count": prediction.api_call_count,
            "completed_traversal_steps": len(prediction.traversal_steps)}


def probe(*, source, credentials, api_key, products, output_dir, catalog_client=None, budget=None):
    """Products have already been retrieved with at most one three-ASIN query.

    No human adoption or listing output is performed. Configuration failures in
    Shopee do not prevent the independent explanation/image transport probe.
    """
    asins = tuple(row.candidate_asin for row in source.rows)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    db_path = output_dir / "validation.sqlite3"
    scope = SGLiveValidationScope(asins, credentials.shop_id, db_path)
    if set(products) != set(asins):
        raise ValueError("Keepa product set does not match selected SG input")
    store = CategoryMapperStore(db_path)
    store.initialize_sg_brand_acceptance()
    client = catalog_client or ShopeeCatalogClient(credentials, marketplace="SG")
    scope.require_client(client, store)
    budget = budget or OpenAIValidationBudget(ledger_path=output_dir / "budget.json")
    inspector = BudgetedLiveWeaponImageInspector(api_key=api_key, budget=budget)
    workflow = SGBrandWorkflow(store=store, client=client, image_inspector=inspector, live_validation_scope=scope)
    report = {"scope": "SG_ISOLATED_READ_ONLY_LIVE_PROBE", "selected_products": len(asins),
              "shopee_catalog": "NOT_RUN", "category_ai_completed": 0, "category_ai_abstained": 0, "category_ai_failed": 0,
              "image_completed": 0, "image_not_target": 0, "image_indeterminate_or_unavailable": 0,
              "evidence_drift": 0, "existing_safety_stop": 0, "image_system_failure": False,
              "human_confirmations_created": 0, "listing_ready_true": 0,
              "formal_listing_files": 0, "normal_environment_modified": False}
    if not credentials.access_token:
        report["shopee_catalog"] = "BLOCKED_SG_ACCESS_TOKEN_MISSING"
    else:
        try:
            catalog_bytes = build_sg_category_catalog_csv(client.get_categories("SG"), marketplace="SG")
            store.replace_sg_category_catalog(parse_sg_category_catalog(catalog_bytes, filename="sg_catalog.csv"))
            (output_dir / "sg_catalog.csv").write_bytes(catalog_bytes)
            report["shopee_catalog"] = "SUCCESS"
        except Exception:
            report["shopee_catalog"] = "FAILED"
    details = []
    for row in source.rows:
        product = products[row.candidate_asin]
        item = SGMapperRecommendation("SG", source.source_type, row.source_asin, row.candidate_asin,
            row.product_title, row.keepa_brand, row.keepa_category, "", "GATE_ELIGIBLE")
        # A live fact change is not silently promoted to the old Gate identity.
        if (product.get("title") != row.product_title or product.get("brand") != row.keepa_brand
                or product.get("category") != row.keepa_category):
            report["evidence_drift"] += 1
            continue
        try:
            text = product_text_safety_fact_from_product_data(product, candidate_asin=item.candidate_asin, provider="keepa")
            workflow.product_review.supply(item, text=text, images=product["ph_image_safety_fact"])
            evidence = workflow.product_review.current(item)
            if evidence.guardrail_status != "SAFE":
                report["existing_safety_stop"] += 1
                continue
            selection=workflow.product_review.image_selection(item)
            if selection=="OTHER_ROOT":
                report["image_not_target"]+=1
                details.append({"asin_binding":hashlib.sha256(item.candidate_asin.encode()).hexdigest(),
                                "image_selection":selection,"system_status":"NOT_RUN"})
            else:
                inspection = workflow.inspect_product_images(item)
                report["image_completed" if inspection.system_status == "COMPLETED" else "image_indeterminate_or_unavailable"] += 1
                details.append({"asin_binding": hashlib.sha256(item.candidate_asin.encode()).hexdigest(),
                                "system_status": inspection.system_status, "ai_status": inspection.ai_status,
                                "evidence_binding": evidence.binding})
        except Exception:
            report["image_system_failure"] = True
            break  # Authentication/contract/budget failures do not trigger more paid calls.
        if report["shopee_catalog"] == "SUCCESS":
            from modules.category_ai_core import ProductEvidence
            engine = CategoryAIEngine(OpenAIResponsesCategoryProvider(api_key, session=BudgetedOpenAISession(budget)))
            prediction = engine.predict(ProductEvidence("SG", item.candidate_asin, item.product_title,
                asin=item.candidate_asin, keepa_category=item.keepa_category, keepa_brand=item.keepa_brand),
                build_sg_category_ai_catalog(store), load_luna_request_profile())
            counter = {"COMPLETED": "category_ai_completed", "ABSTAIN": "category_ai_abstained",
                       "FAILED": "category_ai_failed"}[prediction.status]
            report[counter] += 1
            details.append({"asin_binding": hashlib.sha256(item.candidate_asin.encode()).hexdigest(),
                            **category_transport_summary(prediction)})
            if budget.stopped:
                break
    report["budget"] = budget.summary()
    report["decision"] = ("LIVE_TRANSPORT_PARTIAL" if report["shopee_catalog"] != "SUCCESS"
                          or report["image_system_failure"] or report["evidence_drift"] or report["existing_safety_stop"]
                          or report["category_ai_failed"] or report["image_indeterminate_or_unavailable"]
                          or report["image_completed"] + report["image_not_target"] != len(asins) or report["category_ai_completed"] != len(asins)
                          else "LIVE_TRANSPORT_CHECK_COMPLETE")
    (output_dir / "transport_results.json").write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--api-env", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bridge-spreadsheet-id", help="Explicit existing Bridge selection for this isolated process only")
    parser.add_argument("--execute-live", action="store_true")
    args = parser.parse_args()
    if not args.execute_live:
        parser.error("Explicit --execute-live and prior owner authorization required")
    try:
        from dotenv import dotenv_values
        import keepa
        from modules.keepa_client import _product_to_cache_data
        source = parse_sg_category_mapper_input(args.input.read_bytes(), filename=args.input.name)
        asins = tuple(row.candidate_asin for row in source.rows)
        # Validate before constructing API clients (the Keepa constructor also performs I/O).
        credentials = load_shopee_catalog_credentials(marketplace="SG", require_access_token=False)
        SGLiveValidationScope(asins, credentials.shop_id, args.output / "validation.sqlite3")
        if args.output.exists():
            raise ValueError("Existing live run cannot be repeated/reset")
        values = dotenv_values(args.api_env)
        import os
        if args.bridge_spreadsheet_id:
            os.environ["SHOPEE_GOOGLE_SHEET_TOKEN_SOURCE_ENABLED"] = "1"
            os.environ["SHOPEE_GOOGLE_SHEET_BRIDGE_SPREADSHEET_ID"] = args.bridge_spreadsheet_id
        # Reuse the accepted source priority/fail-closed contract. Never bypass
        # an enabled Bridge by constructing a client from legacy credentials.
        catalog_client = ShopeeCatalogClient.from_local_audit_env(marketplace="SG")
        credentials = catalog_client.credentials
        openai_key = os.getenv("OPENAI_API_KEY") or values.get("OPENAI_API_KEY") or ""
        keepa_key = os.getenv("KEEPA_API_KEY") or values.get("KEEPA_API_KEY") or ""
        if not openai_key or not keepa_key:
            raise ValueError("Existing API settings unavailable")
        api = keepa.Keepa(keepa_key)
        raw_products = api.query(list(asins), domain="JP", history=False, offers=None, stock=False,
                                 buybox=False, rating=False, progress_bar=False, wait=False)
        normalized = [_product_to_cache_data(raw) for raw in raw_products]
        products = {product["asin"]: product for product in normalized}
        report = probe(source=source, credentials=credentials, api_key=openai_key, products=products,
                       output_dir=args.output, catalog_client=catalog_client)
        print(json.dumps(report))
        return 0 if report["decision"] == "LIVE_TRANSPORT_CHECK_COMPLETE" else 2
    except Exception as exc:
        # No raw exceptions, product text, request URLs or credentials in output.
        print(json.dumps({"decision": "LIVE_VALIDATION_STOPPED", "error_type": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
