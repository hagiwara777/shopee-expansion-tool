"""SG image development UI uses PH HTTP/image code with synthetic transports."""

from dataclasses import replace

import pytest
import requests

from modules.category_mapper_sg_brand_workflow import SGBrandWorkflow
from modules.category_mapper_sg_preparation import build_sg_preparation_candidate_files
from modules.weapon_image_inspection import OfflineWeaponImageInspector
from test_ph_image_safety_api import Session, Response, body
from test_sg_brand_confirmation_ui import preview, workflow_preview
from test_product_review import evidence, allow, supply


def inspector(*responses, images=None):
    api = Session(*(responses or [Response(data=body())]))
    image = Session(*(images if images is not None else [Response()]))
    adapter = OfflineWeaponImageInspector(api_key="synthetic-test-credential", api_session=api,
                                         image_session=image, sleep=lambda delay: None)
    return adapter, api, image


def image_workflow(workflow_preview, adapter):
    app, previous, _, _ = workflow_preview
    workflow = SGBrandWorkflow(store=previous.store, client=previous._client,
                               product_evidence_loader=evidence, image_inspector=adapter)
    app.session_state["workflow"] = workflow
    app.run()
    return app, workflow


@pytest.mark.parametrize("semantic", ["NO_SIGNAL", "REVIEW", "INDETERMINATE"])
def test_only_weapon_suspicion_or_indeterminate_needs_human_review(workflow_preview, semantic):
    adapter, api, images = inspector(Response(data=body(semantic)))
    app, workflow = image_workflow(workflow_preview, adapter)
    item = app.session_state["sg_category_mapper_recommendations"][0]
    workflow.load_product_evidence(item)
    with pytest.raises(ValueError):
        allow(workflow.product_review, item)
    assert not api.calls and not images.calls
    result = workflow.inspect_product_images(item)
    assert result.ai_status == semantic and result.system_status == "COMPLETED"
    assert workflow.product_review.decision(item) is None and not item.listing_ready
    assert len(api.calls) == len(images.calls) == 1
    assert "Do not assess legality" in api.calls[0][1]["json"]["instructions"]
    if semantic == "NO_SIGNAL":
        assert workflow.product_review.preparation_blocker(item) is None
        assert workflow.product_review.decision(item) is None
    else:
        assert workflow.product_review.preparation_blocker(item) == "武器疑義・画像判断不能の確認"
        allow(workflow.product_review, item)
        assert workflow.product_review.decision(item) == "ALLOW_PREPARATION"
    supply(workflow.product_review, item, "Changed evidence")
    assert workflow.product_review.current_image_inspection(item) is None
    assert workflow.product_review.decision(item) is None


def test_partial_images_are_indeterminate_and_cannot_be_no_signal(workflow_preview):
    adapter, _, _ = inspector(images=[Response(), Response(status=404)])
    app, workflow = image_workflow(workflow_preview, adapter)
    item = app.session_state["sg_category_mapper_recommendations"][0]
    text, image = evidence(item)
    image["image_urls"].append("https://m.media-amazon.com/images/I/OTHER.png")
    workflow.product_review.supply(item, text=text, images=image)
    result = workflow.inspect_product_images(item)
    assert result.system_status == "PARTIAL" and result.ai_status == "INDETERMINATE"
    assert workflow.product_review.decision(item) is None


def test_missing_images_never_call_transport_or_allow_preparation(workflow_preview):
    adapter, api, images = inspector()
    app, workflow = image_workflow(workflow_preview, adapter)
    item = app.session_state["sg_category_mapper_recommendations"][0]
    text, image = evidence(item)
    image["image_urls"] = []
    workflow.product_review.supply(item, text=text, images=image)
    result = workflow.inspect_product_images(item)
    assert result.system_status == "UNAVAILABLE" and result.ai_status is None
    assert not api.calls and not images.calls
    with pytest.raises(ValueError):
        allow(workflow.product_review, item)


def test_existing_safety_stop_and_other_market_never_call_ai(workflow_preview):
    adapter, api, images = inspector()
    app, workflow = image_workflow(workflow_preview, adapter)
    item = app.session_state["sg_category_mapper_recommendations"][0]
    supply(workflow.product_review, item, "Rechargeable battery included")
    with pytest.raises(ValueError):
        workflow.inspect_product_images(item)
    with pytest.raises(ValueError):
        workflow.load_product_evidence(replace(item, marketplace="PH"))
    assert not api.calls and not images.calls


def test_auth_failure_invalidates_all_previous_review_and_closes_preview_until_recheck(workflow_preview):
    adapter, api, images = inspector(Response(data=body()), Response(status=401, data={"error": {"code": "invalid_api_key"}}),
                                     Response(data=body()), images=[Response(), Response(), Response()])
    app, workflow = image_workflow(workflow_preview, adapter)
    item = app.session_state["sg_category_mapper_recommendations"][0]
    workflow.load_product_evidence(item)
    workflow.inspect_product_images(item)
    allow(workflow.product_review, item)
    with pytest.raises(RuntimeError):
        workflow.inspect_product_images(item)
    assert workflow.product_review.decision(item) is None
    assert workflow.product_review.current_image_inspection(item) is None
    with pytest.raises(ValueError):
        build_sg_preparation_candidate_files((item,), workflow=workflow)
    workflow.inspect_product_images(item)
    workflow.require_image_system_current()
    assert workflow.product_review.decision(item) is None
    assert len(api.calls) == len(images.calls) == 3


def test_image_reinspection_resets_ui_checkboxes_and_never_runs_on_rerun(workflow_preview):
    adapter, api, images = inspector(Response(data=body("REVIEW")), Response(data=body("INDETERMINATE")), images=[Response(), Response()])
    app, workflow = image_workflow(workflow_preview, adapter)
    app.button(key="sg_category_mapper_fetch_product_evidence_0").click().run()
    assert not app.exception and not api.calls
    app.button(key="sg_image_inspection_run_0").click().run()
    assert not app.exception and len(api.calls) == 1
    assert not any("商品説明・特徴" in box.label for box in app.checkbox)
    next(box for box in app.checkbox if "武器疑義について" in box.label).check().run()
    next(text for text in app.text_input if text.label == "確認した画像・判断の根拠").set_value("Synthetic weapon review").run()
    next(button for button in app.button if button.label == "画像の人間判断を記録").click().run()
    assert not app.exception and any("武器画像の人間判断：準備継続" in text.value for text in app.success)
    app.run()
    assert len(api.calls) == len(images.calls) == 1
    app.button(key="sg_image_inspection_run_0").click().run()
    assert not app.exception and len(api.calls) == 2
    assert not next(box for box in app.checkbox if "武器疑義について" in box.label).value
    assert not any("武器画像の人間判断：準備継続" in text.value for text in app.success)


@pytest.mark.parametrize("api_session,image_session", [(None, Session()), (Session(), None), (requests.Session(), Session()), (Session(), requests.Session())])
def test_adapter_rejects_missing_or_network_sessions(api_session, image_session):
    with pytest.raises(ValueError):
        OfflineWeaponImageInspector(api_key="synthetic", api_session=api_session, image_session=image_session)


def test_sg_workflow_rejects_unvalidated_inspector(workflow_preview):
    _, workflow, _, _ = workflow_preview
    with pytest.raises(ValueError):
        SGBrandWorkflow(store=workflow.store, client=workflow._client, image_inspector=object())


def test_image_result_cannot_move_between_products_and_new_evaluation_invalidates_decision(workflow_preview):
    adapter, _, _ = inspector(Response(data=body()), Response(data=body()), images=[Response(), Response()])
    app, workflow = image_workflow(workflow_preview, adapter)
    item = app.session_state["sg_category_mapper_recommendations"][0]
    workflow.load_product_evidence(item)
    result = workflow.inspect_product_images(item)
    allow(workflow.product_review, item)
    other = replace(item, candidate_asin="B000000002")
    supply(workflow.product_review, other)
    with pytest.raises(ValueError):
        workflow.product_review.finish_image_inspection(other,
            evidence_binding=workflow.product_review.current(other).binding, inspection=result)
    assert workflow.product_review.current_image_inspection(other) is None
    # Even a direct replacement cannot reuse the old human confirmation.
    newer = adapter.inspect(workflow.product_review.current(item))
    assert newer.image_digests and newer.evaluation_id != result.evaluation_id
    workflow.product_review.finish_image_inspection(item,
        evidence_binding=workflow.product_review.current(item).binding, inspection=newer)
    assert workflow.product_review.decision(item) is None


@pytest.mark.parametrize("change", ["safe_claim", "missing_image", "unknown_digest", "zero_attempts", "false_complete"])
def test_invalid_result_is_system_failure_and_never_becomes_human_confirmation(workflow_preview, monkeypatch, change):
    adapter, api, images = inspector()
    app, workflow = image_workflow(workflow_preview, adapter)
    item = app.session_state["sg_category_mapper_recommendations"][0]
    workflow.load_product_evidence(item)
    current = workflow.product_review.current(item)
    response = dict(system_status="COMPLETED", ai_status="NO_SIGNAL", note="Synthetic prediction", attempts=1,
                    images=[dict(url=current.image_urls[0], status="LOADED", sha256="a" * 64, mime="image/png")])
    if change == "safe_claim":
        response["ai_status"] = "SAFE"
    elif change == "missing_image":
        response["images"] = []
    elif change == "unknown_digest":
        response["images"][0]["sha256"] = ""
    elif change == "zero_attempts":
        response["attempts"] = 0
    else:
        response["images"][0].update(status="UNAVAILABLE", sha256="", mime="")
    monkeypatch.setattr(adapter._analyzer, "analyze", lambda *a, **k: response)
    with pytest.raises(ValueError):
        workflow.inspect_product_images(item)
    assert workflow.product_review.current_image_inspection(item) is None
    with pytest.raises(ValueError):
        allow(workflow.product_review, item)
    with pytest.raises(ValueError):
        workflow.require_image_system_current()
    assert not api.calls and not images.calls


def test_non_target_sg_product_needs_no_image_or_human_review(workflow_preview):
    adapter, api, images = inspector()
    app, workflow = image_workflow(workflow_preview, adapter)
    item = app.session_state["sg_category_mapper_recommendations"][0]
    text, raw = evidence(item)
    raw["root_category_id"] = 3210981
    workflow.product_review.supply(item, text=text, images=raw)
    assert workflow.image_inspection_targets((item,)) == ()
    assert workflow.product_review.decision(item) is None
    with pytest.raises(ValueError):
        workflow.inspect_product_images(item)
    assert not api.calls and not images.calls
    with pytest.raises(ValueError):
        allow(workflow.product_review, item)
    assert workflow.product_review.preparation_blocker(item) is None
    assert workflow.product_review.current_image_inspection(item) is None
    app.run()
    assert not app.exception
    assert any("国別設定で対象外" in x.value for x in app.caption)
    assert not any(x.key == "sg_image_inspection_run_0" for x in app.button)
    assert not any(x.key.startswith("sg_weapon_review_") for x in app.checkbox)
    assert not app.get("link_button")


def test_non_target_missing_images_does_not_block_preparation(workflow_preview):
    adapter, api, images = inspector()
    app, workflow = image_workflow(workflow_preview, adapter)
    item = app.session_state["sg_category_mapper_recommendations"][0]
    text, raw = evidence(item)
    raw.update(root_category_id=3210981, image_urls=[])
    workflow.product_review.supply(item, text=text, images=raw)
    assert workflow.image_inspection_targets((item,)) == ()
    with pytest.raises(ValueError):
        allow(workflow.product_review, item)
    assert workflow.product_review.preparation_blocker(item) is None
    assert not api.calls and not images.calls
