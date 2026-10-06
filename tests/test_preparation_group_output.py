"""Check PH output compatibility and isolated SG group/attribute semantics."""

import csv
from dataclasses import replace
from io import StringIO

from test_category_mapper import store, _gate_csv
from modules.category_mapper import parse_category_mapper_input, build_recommendations, apply_manual_brand, build_mapper_exports
from modules.category_mapper_sg import confirm_sg_brand
from modules.category_mapper_sg_brand_workflow import SGBrandWorkflow
from modules.category_mapper_sg_preparation import build_sg_preparation_candidate_files
from test_category_mapper_sg_brand import client_for, payload, raw_brand
from sls_category_sg_support import sg_item
from test_product_review import supply, allow, inspect


def test_ph_group_csv_and_txt_preserve_existing_order_and_format(store):
    source = parse_category_mapper_input(_gate_csv(), filename="eligible.csv")
    item = build_recommendations(source, resolver_titles=None, store=store)[0]
    first = apply_manual_brand(item, brand={"brand_id": 0, "brand_name": "No brand", "is_no_brand": True})
    second = replace(first, candidate_asin="B000000002")
    third = apply_manual_brand(replace(item, candidate_asin="B000000003"),
                               brand={"brand_id": 7, "brand_name": "Maker", "is_no_brand": False})
    result = build_mapper_exports((first, third, second))
    expected = (
        "marketplace,group_key,category_id,category_path,brand_id,brand_name,mandatory_attribute_count,verification_status,listing_ready,asin_count,asin\n"
        "PH,PH|100869|0,100869,Beauty > Hair Care > Shampoo,0,No brand,0,LISTING_TOOL_ACCEPTED,TRUE,2,B000000001\n"
        "PH,PH|100869|0,100869,Beauty > Hair Care > Shampoo,0,No brand,0,LISTING_TOOL_ACCEPTED,TRUE,2,B000000002\n"
        "PH,PH|100869|7,100869,Beauty > Hair Care > Shampoo,7,Maker,0,LISTING_TOOL_ACCEPTED,TRUE,1,B000000003\n"
    )
    assert result.groups_csv == expected.encode("utf-8-sig")
    assert result.listing_tool_text == (
        "［PH / Beauty > Hair Care > Shampoo / No brand］\nCategory ID: 100869\nBrand ID: 0\n"
        "Mandatory attributes: 0\nASIN count: 2\n\nB000000001\nB000000002\n\n"
        "［PH / Beauty > Hair Care > Shampoo / Maker］\nCategory ID: 100869\nBrand ID: 7\n"
        "Mandatory attributes: 0\nASIN count: 1\n\nB000000003"
    )


def prepared_sg(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.shopee_catalog_client.urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Live forbidden")))
    store, item = sg_item(tmp_path)
    store.initialize_sg_brand_acceptance()
    attribute_response = {"response": {"list": [{"category_id": item.recommended_category_id, "attribute_tree": [
        {"attribute_id": 1, "display_attribute_name": "Size", "is_mandatory": True},
        {"attribute_id": 2, "display_attribute_name": "Color", "is_mandatory": False},
    ]}]}}
    client, _ = client_for([payload([raw_brand(), raw_brand(8, "Other"), raw_brand(99, "No Brand")]), attribute_response])
    workflow = SGBrandWorkflow(store=store, client=client)
    catalog = workflow.fetch(item).catalog
    items = []
    for source, brand_id, name in ((item, 7, "Maker"),
                                   (replace(item, candidate_asin="B000000002"), 7, "Maker"),
                                   (replace(item, candidate_asin="B000000003", keepa_brand="Other"), 8, "Other")):
        confirmed = confirm_sg_brand(source, store=store, session=workflow.session, catalog=catalog,
                                     brand_id=brand_id, expected_brand_name=name,
                                     human_product_verified=True, human_option_selected=True)
        supply(workflow.product_review, confirmed)
        inspect(workflow.product_review, confirmed)
        allow(workflow.product_review, confirmed)
        items.append(confirmed)
    return workflow, tuple(items)


def test_sg_groups_by_market_category_and_real_brand_with_unknown_attributes(tmp_path, monkeypatch):
    workflow, items = prepared_sg(tmp_path, monkeypatch)
    data, text, count = build_sg_preparation_candidate_files((items[0], items[2], items[1]), workflow=workflow)
    rows = list(csv.DictReader(StringIO(data.decode("utf-8-sig"))))
    assert count == 3 and [row["asin"] for row in rows] == ["B000000001", "B000000002", "B000000003"]
    assert [row["asin_count"] for row in rows] == ["2", "2", "1"]
    assert [row["brand_id"] for row in rows] == ["7", "7", "8"]
    assert all(row["group_key"].startswith("SG|") and row["listing_ready"] == "FALSE" for row in rows)
    assert all(row["mandatory_attribute_count"] == "" and row["attribute_check_state"] == "NOT_FETCHED" for row in rows)
    assert "Mandatory attributes: 未取得" in text and "ASIN count: 2\n\nB000000001\nB000000002" in text
    assert all(item.listing_ready is False for item in items)


def test_sg_attribute_counts_are_current_and_exclusion_removes_only_its_asin(tmp_path, monkeypatch):
    workflow, items = prepared_sg(tmp_path, monkeypatch)
    workflow.fetch_attributes(items[0])
    workflow.product_review.record_weapon_decision(items[1], decision="EXCLUDE", reviewed_images=True, note="Synthetic weapon exclusion")
    data, text, count = build_sg_preparation_candidate_files(items, workflow=workflow)
    rows = list(csv.DictReader(StringIO(data.decode("utf-8-sig"))))
    assert count == 2 and [row["asin"] for row in rows] == ["B000000001", "B000000003"]
    assert all(row["mandatory_attribute_count"] == "1" and row["attribute_check_state"] == "FETCHED" for row in rows)
    assert "Mandatory attributes: 1" in text and "B000000002" not in text
    workflow.session.invalidate(items[0].recommended_category_id)
    assert build_sg_preparation_candidate_files(items, workflow=workflow)[2] == 0


def test_ph_formula_escape_is_preserved_in_shared_group_csv(store):
    source = parse_category_mapper_input(_gate_csv(), filename="eligible.csv")
    item = build_recommendations(source, resolver_titles=None, store=store)[0]
    confirmed = apply_manual_brand(item, brand={"brand_id": 7, "brand_name": "=Synthetic", "is_no_brand": False})
    data = build_mapper_exports((confirmed,)).groups_csv
    assert next(csv.DictReader(StringIO(data.decode("utf-8-sig"))))["brand_name"] == "'=Synthetic"


def test_sg_confirmed_zero_attributes_is_distinct_from_failed_acquisition(tmp_path, monkeypatch):
    workflow, items = prepared_sg(tmp_path, monkeypatch)
    monkeypatch.setattr(workflow._client, "get_attribute_tree", lambda *args: [])
    workflow.fetch_attributes(items[0])
    data, text, _ = build_sg_preparation_candidate_files(items, workflow=workflow)
    rows = list(csv.DictReader(StringIO(data.decode("utf-8-sig"))))
    assert all(row["mandatory_attribute_count"] == "0" and row["attribute_check_state"] == "FETCHED" for row in rows)
    assert "Mandatory attributes: 0" in text
    def fail(*args):
        raise ValueError("Synthetic attribute failure")
    monkeypatch.setattr(workflow._client, "get_attribute_tree", fail)
    import pytest
    with pytest.raises(ValueError):
        workflow.fetch_attributes(items[0])
    data, text, _ = build_sg_preparation_candidate_files(items, workflow=workflow)
    rows = list(csv.DictReader(StringIO(data.decode("utf-8-sig"))))
    assert all(row["mandatory_attribute_count"] == "" and row["attribute_check_state"] == "NOT_FETCHED" for row in rows)
    assert "Mandatory attributes: 未取得" in text
