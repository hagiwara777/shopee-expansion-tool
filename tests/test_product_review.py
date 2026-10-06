from dataclasses import replace
import csv
from io import StringIO

import pytest

from test_sg_brand_confirmation_ui import preview, workflow_preview
from modules.product_review import WeaponImageReviewSession
from modules.product_text_safety import ProductTextSafetyFact
from modules.category_mapper_sg_preparation import build_sg_preparation_candidate_files
from modules.category_mapper_sg_brand_workflow import SGBrandWorkflow
from modules.category_mapper_sg import confirm_sg_brand, review_sg_brand
from test_category_mapper_sg_brand import client_for, payload, raw_brand
from sls_category_sg_support import sg_item


def evidence(item, description="Synthetic description"):
    return ProductTextSafetyFact(item.candidate_asin, "keepa", "CAPTURED", (description,), (), (), (), (),
                                 "2026-10-04T00:00:00+00:00"), {
        "candidate_asin": item.candidate_asin, "provider": "keepa", "capture_error": False,
        "image_urls": ["https://m.media-amazon.com/images/I/TEST.jpg"],
    }


def supply(session, item, description="Synthetic description"):
    text, images = evidence(item, description)
    session.supply(item, text=text, images=images)


def allow(session, item):
    session.record_weapon_decision(item, decision="ALLOW_PREPARATION", reviewed_images=True,
                   note="Reviewed synthetic image for weapon suspicion")


def inspect(session, item, semantic="REVIEW"):
    from test_ph_image_safety_api import Session, Response, body
    from modules.weapon_image_inspection import OfflineWeaponImageInspector
    adapter = OfflineWeaponImageInspector(api_key="synthetic", api_session=Session(Response(data=body(semantic))),
        image_session=Session(*(Response() for _ in session.current(item).image_urls)), sleep=lambda _: None)
    evidence = session.begin_image_inspection(item)
    result = adapter.inspect(evidence)
    session.finish_image_inspection(item, evidence_binding=evidence.binding, inspection=result)
    return result


def test_review_requires_evidence_and_explicit_confirmation(preview):
    app, _, _ = preview
    item = app.session_state["sg_category_mapper_recommendations"][0]
    session = WeaponImageReviewSession("SG")
    with pytest.raises(ValueError):
        allow(session, item)
    supply(session, item)
    with pytest.raises(ValueError):
        allow(session, item)
    inspect(session, item)
    with pytest.raises(ValueError):
        session.record_weapon_decision(item, decision="ALLOW_PREPARATION", reviewed_images=False, note="Checked")
    allow(session, item)
    assert session.decision(item) == "ALLOW_PREPARATION"
    assert session.decision(replace(item, product_title="Changed")) is None
    supply(session, item, "Changed description")
    assert session.decision(item) is None


def test_description_battery_signal_cannot_be_overridden_by_review(preview):
    app, _, _ = preview
    item = app.session_state["sg_category_mapper_recommendations"][0]
    session = WeaponImageReviewSession("SG")
    supply(session, item, "Contains a rechargeable battery")
    assert session.current(item).guardrail_status == "REVIEW"
    with pytest.raises(ValueError):
        allow(session, item)


@pytest.mark.parametrize("change", [{"capture_error": True}, {"image_urls": []}, {"provider": "canopy_test"}])
def test_incomplete_or_test_provider_image_cannot_pass(preview, change):
    app, _, _ = preview
    item = app.session_state["sg_category_mapper_recommendations"][0]
    text, images = evidence(item)
    session = WeaponImageReviewSession("SG")
    session.supply(item, text=text, images={**images, **change})
    with pytest.raises(ValueError):
        allow(session, item)


def test_review_rejects_market_or_asin_mismatch(preview):
    app, _, _ = preview
    item = app.session_state["sg_category_mapper_recommendations"][0]
    session = WeaponImageReviewSession("SG")
    with pytest.raises(ValueError):
        supply(session, replace(item, marketplace="PH"))
    text, images = evidence(item)
    with pytest.raises(ValueError):
        session.supply(item, text=replace(text, candidate_asin="B000000002"), images=images)


def test_preview_requires_safety_brand_and_current_shipping_allow(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.shopee_catalog_client.urlopen", lambda *a, **k: pytest.fail("Live forbidden"))
    store, item = sg_item(tmp_path)
    store.initialize_sg_brand_acceptance()
    client, _ = client_for([payload([raw_brand(), raw_brand(99, "No Brand")])])
    workflow = SGBrandWorkflow(store=store, client=client)
    acquired = workflow.fetch(item)
    confirmed = confirm_sg_brand(item, store=store, session=workflow.session, catalog=acquired.catalog,
                                 brand_id=7, expected_brand_name="Maker", human_product_verified=True, human_option_selected=True)
    assert item.sls_result.action == "CATEGORY_ALLOW"
    assert build_sg_preparation_candidate_files((confirmed,), workflow=workflow)[2] == 0
    supply(workflow.product_review, confirmed)
    inspect(workflow.product_review, confirmed)
    allow(workflow.product_review, confirmed)
    csv_data, text, count = build_sg_preparation_candidate_files((confirmed,), workflow=workflow)
    assert count == 1
    row = next(csv.DictReader(StringIO(csv_data.decode("utf-8-sig"))))
    assert row["listing_ready"] == "FALSE" and row["brand_id"] == "7"
    assert "出品用ファイルではありません" in text
    workflow.session.invalidate(item.recommended_category_id)
    assert build_sg_preparation_candidate_files((confirmed,), workflow=workflow)[2] == 0


def test_general_description_image_review_widgets_are_removed(workflow_preview):
    app, workflow, _, _ = workflow_preview
    workflow._product_evidence_loader = evidence
    app.run()
    app.button(key="sg_category_mapper_fetch_product_evidence_0").click().run()
    assert not app.exception
    assert not any("商品説明・特徴" in box.label for box in app.checkbox)
    assert not any(button.label == "商品確認結果を保存" for button in app.button)
    assert not hasattr(workflow.product_review, "record")
    assert not hasattr(workflow.product_review, "require_image_inspection")
    def fail(item):
        raise RuntimeError("PRIVATE_TEST_MARKER")
    workflow._product_evidence_loader = fail
    app.button(key="sg_category_mapper_fetch_product_evidence_0").click().run()
    assert not app.exception
    assert workflow.product_review.current(app.session_state["sg_category_mapper_recommendations"][0]) is None
    assert "PRIVATE_TEST_MARKER" not in str(app)


@pytest.mark.parametrize("missing_images", [False, True])
def test_non_target_exports_without_image_fetch_or_human_confirmation(tmp_path, missing_images):
    store, item = sg_item(tmp_path)
    store.initialize_sg_brand_acceptance()
    client, calls = client_for([payload([raw_brand()])])
    workflow = SGBrandWorkflow(store=store, client=client)
    catalog = workflow.fetch(item).catalog
    item = confirm_sg_brand(item, store=store, session=workflow.session, catalog=catalog,
        brand_id=7, expected_brand_name="Maker", human_product_verified=True, human_option_selected=True)
    text, images = evidence(item)
    images.update(root_category_id=3210981, image_urls=[] if missing_images else images["image_urls"],
                  capture_error=missing_images)
    workflow.product_review.supply(item, text=text, images=images)
    assert workflow.product_review.decision(item) is None
    assert workflow.product_review.current_image_inspection(item) is None
    assert not workflow.can_inspect_images
    data, _, count = build_sg_preparation_candidate_files((item,), workflow=workflow)
    assert count == 1 and len(calls) == 1
    assert next(csv.DictReader(StringIO(data.decode("utf-8-sig"))))["listing_ready"] == "FALSE"
    supply(workflow.product_review, item, "Rechargeable battery included")
    assert build_sg_preparation_candidate_files((item,), workflow=workflow)[2] == 0


@pytest.mark.parametrize("semantic,expected", [("NO_SIGNAL", 1), ("REVIEW", 0), ("INDETERMINATE", 0)])
def test_weapon_inspection_outcome_controls_preparation_without_general_review(tmp_path, semantic, expected):
    store, item = sg_item(tmp_path)
    store.initialize_sg_brand_acceptance()
    client, _ = client_for([payload([raw_brand()])])
    workflow = SGBrandWorkflow(store=store, client=client)
    catalog = workflow.fetch(item).catalog
    item = confirm_sg_brand(item, store=store, session=workflow.session, catalog=catalog,
        brand_id=7, expected_brand_name="Maker", human_product_verified=True, human_option_selected=True)
    supply(workflow.product_review, item)
    assert build_sg_preparation_candidate_files((item,), workflow=workflow)[2] == 0
    inspect(workflow.product_review, item, semantic)
    assert build_sg_preparation_candidate_files((item,), workflow=workflow)[2] == expected
    assert workflow.product_review.decision(item) is None
    if semantic != "NO_SIGNAL":
        allow(workflow.product_review, item)
        assert build_sg_preparation_candidate_files((item,), workflow=workflow)[2] == 1
        workflow.product_review.record_weapon_decision(item, decision="EXCLUDE",
            reviewed_images=True, note="Synthetic weapon exclusion")
        assert build_sg_preparation_candidate_files((item,), workflow=workflow)[2] == 0
