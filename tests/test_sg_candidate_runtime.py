"""Exercise separately launched SG review without network/production data."""

from base64 import b64encode
from dataclasses import replace
import json
import logging
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from modules.category_ai_core import content_hash, StepRequest, ProductEvidence, CategoryNode, make_fake_select
from modules.category_mapper_ai import load_luna_request_profile
from modules.category_mapper_sg import build_sg_category_catalog_csv, parse_sg_category_catalog
from modules.sg_candidate_runtime import SGReplayBundle, create_sg_candidate_workflow
from modules.weapon_image_inspection import OfflineWeaponImageInspector
from test_ph_image_safety_api import Session, Response, body, png
from test_product_review_transport import files, upload_files
from test_product_review import allow, evidence, inspect
from test_sg_brand_confirmation_ui import preview, workflow_preview, select_brand
from sls_category_sg_support import sg_item


def replay_data():
    return dict(schema="SG_OFFLINE_REPLAY_V1", marketplace="SG", shop_id=22,
                catalog_responses={}, category_predictions={}, images={}, image_predictions={})


def bundle(data):
    return SGReplayBundle(json.dumps(data).encode())


def add_image_response(data, urls):
    from types import SimpleNamespace
    api = Session(Response(data=body()))
    adapter = OfflineWeaponImageInspector(api_key="synthetic-replay", api_session=api,
        image_session=Session(*(Response() for url in urls)), sleep=lambda delay: None)
    adapter.inspect(SimpleNamespace(binding="synthetic", image_urls=tuple(urls), image_capture_error=False,
                                   image_provider="keepa", guardrail_status="SAFE"))
    data["images"].update({url: b64encode(png()).decode() for url in urls})
    data["image_predictions"][content_hash(api.calls[0][1]["json"])] = body()


@pytest.mark.parametrize("change", ["PH", "zero_shop", "bool_shop", "extra", "invalid_image"])
def test_replay_rejects_wrong_binding_or_malformed_data(change):
    data = replay_data()
    if change == "PH": data["marketplace"] = "PH"
    if change == "zero_shop": data["shop_id"] = 0
    if change == "bool_shop": data["shop_id"] = True
    if change == "extra": data["access_token"] = "unsupported"
    if change == "invalid_image": data["images"] = {"https://untrusted.invalid/x": "YQ=="}
    with pytest.raises(ValueError): bundle(data)


def test_duplicate_bundle_keys_are_rejected():
    with pytest.raises(ValueError): SGReplayBundle(b'{"schema":1,"schema":2}')


def test_replay_never_reuses_existing_or_production_database(tmp_path, monkeypatch):
    path = tmp_path / "normal.sqlite3"
    path.write_bytes(b"production-marker")
    import modules.sg_candidate_runtime as runtime
    monkeypatch.setattr(runtime, "default_category_mapper_db_path", lambda: path)
    with pytest.raises(ValueError): create_sg_candidate_workflow(bundle(replay_data()), db_path=path)
    assert path.read_bytes() == b"production-marker"
    other = tmp_path / "existing.sqlite3"
    other.write_bytes(b"another-marker")
    with pytest.raises(ValueError): create_sg_candidate_workflow(bundle(replay_data()), db_path=other)
    assert other.read_bytes() == b"another-marker"


def test_catalog_replay_binds_shop_and_exact_category_offset(tmp_path):
    data = replay_data()
    data["catalog_responses"]["brand:11:0"] = {"response": {"brand_list": [], "has_next_page": False, "next_offset": 0}}
    replay = bundle(data)
    url = "https://partner.shopeemobile.com/api/v2/product/get_brand_list"
    query = dict(shop_id="22", category_id="11", offset="0")
    result = replay.catalog_request(url, query, 10)
    result.clear()
    assert replay.catalog_request(url, query, 10)["response"]["brand_list"] == []
    for change in (dict(shop_id="33"), dict(category_id="12"), dict(offset="100")):
        with pytest.raises((ValueError, KeyError)): replay.catalog_request(url, {**query, **change}, 10)


def test_category_replay_is_bound_to_product_catalog_and_profile():
    from modules.category_ai_core import CategoryAIError
    request = StepRequest(ProductEvidence("SG", "one", "Synthetic product"), None, "",
                          (CategoryNode(11, None, "Root", "Root", True),))
    profile = load_luna_request_profile()
    data = replay_data()
    data["category_predictions"][content_hash([request.user_input(), profile.to_dict()])] = make_fake_select(11)
    engine = bundle(data).category_engine()
    assert engine.provider.select(request, profile).selected_category_id == 11
    changed = replace(request, product=replace(request.product, product_title="Different product"))
    with pytest.raises(CategoryAIError): engine.provider.select(changed, profile)
    changed = replace(request, candidates=(CategoryNode(12, None, "Other", "Other", True),))
    with pytest.raises(CategoryAIError): engine.provider.select(changed, profile)


def test_replayed_image_uses_existing_transport_and_refuses_different_image(workflow_preview):
    app, workflow, _, _ = workflow_preview
    item = app.session_state["sg_category_mapper_recommendations"][0]
    text, images = evidence(item)
    workflow.product_review.supply(item, text=text, images=images)
    data = replay_data()
    add_image_response(data, images["image_urls"])
    adapter = bundle(data).image_inspector()
    result = adapter.inspect(workflow.product_review.current(item))
    assert result.system_status == "COMPLETED" and result.ai_status == "NO_SIGNAL"
    assert workflow.product_review.decision(item) is None
    images["image_urls"] = ["https://m.media-amazon.com/images/I/missing.png"]
    workflow.product_review.supply(item, text=text, images=images)
    result = adapter.inspect(workflow.product_review.current(item))
    assert result.system_status == "UNAVAILABLE" and result.ai_status is None


def test_sg_batch_uses_country_root_selection(workflow_preview):
    app, workflow, _, _ = workflow_preview
    first = app.session_state["sg_category_mapper_recommendations"][0]
    second = replace(first, candidate_asin="B000000002")
    for item in (first, second):
        text, images = evidence(item)
        workflow.product_review.supply(item, text=text, images={**images, "root_category_id": 13299531 if item == first else 999999})
    assert workflow.image_inspection_targets((first, second)) == (first,)
    with pytest.raises(ValueError): workflow.image_inspection_targets((first, first))
    with pytest.raises(ValueError): workflow.image_inspection_targets((replace(first, marketplace="PH"),))
    text, images = evidence(first, "Rechargeable battery included")
    workflow.product_review.supply(first, text=text, images=images)
    assert workflow.image_inspection_targets((first, second)) == ()


def test_failed_batch_invalidates_unprocessed_old_reviews(workflow_preview):
    app, workflow, _, _ = workflow_preview
    first = app.session_state["sg_category_mapper_recommendations"][0]
    second = replace(first, candidate_asin="B000000002")
    for item in (first, second):
        text, images = evidence(item)
        workflow.product_review.supply(item, text=text, images=images)
        inspect(workflow.product_review, item)
        allow(workflow.product_review, item)
    workflow._image_inspector = OfflineWeaponImageInspector(api_key="synthetic-replay",
        api_session=Session(Response(status=401, data={})), image_session=Session(Response()), sleep=lambda delay: None)
    with pytest.raises(RuntimeError): workflow.inspect_image_batch((first, second))
    assert all(workflow.product_review.decision(item) is None for item in (first, second))
    with pytest.raises(ValueError): workflow.require_image_system_current()


def test_candidate_entry_from_files_to_group_downloads(tmp_path, monkeypatch):
    def warning(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.WARNING): self._log(logging.WARNING, message, args, **kwargs)
    monkeypatch.setattr(logging.Logger, "warning", warning)
    import modules.sg_candidate_runtime as runtime
    original_factory = runtime.create_sg_candidate_workflow
    serial = iter(range(20))
    monkeypatch.setattr(runtime, "create_sg_candidate_workflow",
        lambda replay, db_path: original_factory(replay, db_path=tmp_path / f"candidate-{next(serial)}.sqlite3"))
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("No external I/O allowed"))
    fixture = Path(__file__).parent / "fixtures" / "browser_e2e" / "sg_candidate"
    material = dict(candidate_content=(fixture / "candidate.csv").read_bytes(),
                    text_content=(fixture / "product_text.csv").read_bytes(),
                    image_content=(fixture / "raw_images.json").read_bytes(),
                    gate_content=(fixture / "prelisting_gate_eligible_sg_expansion.csv").read_bytes(),
                    gate_filename="prelisting_gate_eligible_sg_expansion.csv")
    data = json.loads((fixture / "replay.json").read_bytes())
    catalog = (fixture / "catalog.csv").read_bytes()
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app_sg_candidate.py"), default_timeout=15).run()
    assert not app.exception
    app.file_uploader(key="sg_candidate_bundle").set_value(("replay.json", json.dumps(data).encode(), "application/json")).run()
    assert "sg_candidate_workflow" not in app.session_state
    app.button(key="sg_candidate_initialize").click().run()
    assert not app.exception
    app.file_uploader(key="sg_category_mapper_catalog_csv").set_value(("catalog.csv", catalog, "text/csv")).run()
    app.button(key="sg_category_mapper_replace_catalog").click().run()
    app.file_uploader(key="sg_category_mapper_source_csv").set_value((material["gate_filename"], material["gate_content"], "text/csv")).run()
    upload_files(app, material)
    app.button(key="sg_review_load_files").click().run()
    assert not app.error
    assert app.session_state["sg_candidate_workflow"].can_load_product_evidence
    app.button(key="sg_category_mapper_build").click().run()
    app.button(key="sg_category_mapper_build_ai_suggestions").click().run()
    assert app.session_state["sg_category_mapper_ai_suggestions"].suggestions[0].predicted_category_id == 100869
    assert not app.session_state["sg_category_mapper_recommendations"][0].category_is_confirmed
    app.button(key="sg_category_mapper_apply_ai_0").click().run()
    app.button(key="sg_category_mapper_fetch_brands_0").click().run()
    select_brand(app, "7 | Example Brand")
    app.button(key="sg_category_mapper_fetch_attributes_0").click().run()
    app.button(key="sg_review_load_all").click().run()
    app.button(key="sg_review_inspect_all").click().run()
    assert not app.exception
    assert not any("sg_weapon_review_" in checkbox.key for checkbox in app.checkbox)
    assert not any(button.label == "商品確認結果を保存" for button in app.button)
    assert not app.exception
    labels = [button.label for button in app.get("download_button")]
    assert "開発検証：出品準備候補CSV" in labels and "開発検証：出品準備候補TXT" in labels
    workflow = app.session_state["sg_candidate_workflow"]
    item = app.session_state["sg_category_mapper_recommendations"][0]
    assert workflow.product_review.decision(item) is None and not item.listing_ready
    assert workflow.product_review.preparation_blocker(item) is None
    app.run()
    assert workflow.product_review.preparation_blocker(item) is None
    app.file_uploader(key="sg_candidate_bundle").set_value(None).run()
    assert "sg_candidate_workflow" not in app.session_state
    assert workflow.product_review.decision(item) is None
    assert not app.get("download_button")
