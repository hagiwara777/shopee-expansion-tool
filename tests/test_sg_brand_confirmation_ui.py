"""Exercise human Brand selection and stale-state handling without live APIs."""

from dataclasses import replace
import logging

import pytest
from streamlit.testing.v1 import AppTest

from modules.category_mapper_sg import (
    SGBrandSession, SGMapperRecommendation, build_sg_category_catalog_csv,
    parse_sg_category_catalog, sync_sg_brand_catalog_offline,
)
from modules.category_mapper_store import CategoryMapperStore
from modules.shopee_catalog_client import ShopeeCatalogClient, ShopeeCatalogCredentials
from modules.sls_category_rules_sg import SgSlsCategoryResult
from modules.category_mapper_sg_brand_workflow import SGBrandWorkflow
from test_app_category_mapper_sg import _sg_gate_csv
from modules.category_ai_core import CategoryAIEngine, FakeCategoryAIProvider, make_fake_select, make_fake_abstain


APP = '''
import streamlit as st
from modules.category_mapper_sg_ui import render_sg_brand_confirmation
render_sg_brand_confirmation(
    0, st.session_state.sg_category_mapper_recommendations[0],
    store=st.session_state.preview_store, session=st.session_state.preview_session,
)
'''


@pytest.fixture
def preview(tmp_path, monkeypatch):
    # Match existing AppTest fixtures: this host's logging.warning is modified.
    def standard_warning(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.WARNING):
            self._log(logging.WARNING, message, args, **kwargs)
    monkeypatch.setattr(logging.Logger, "warning", standard_warning)
    def forbid(*args, **kwargs):
        raise AssertionError("Live API forbidden in offline UI test")
    monkeypatch.setattr("modules.shopee_catalog_client.urlopen", forbid)
    monkeypatch.setattr("modules.shopee_access_token_source.GoogleSheetAccessTokenSource.get_access_token", forbid)
    store = CategoryMapperStore(tmp_path / "isolated.sqlite3")
    store.replace_sg_category_catalog(parse_sg_category_catalog(build_sg_category_catalog_csv([
        {"category_id": 10, "parent_category_id": None, "category_name": "Root", "is_leaf": False},
        {"category_id": 11, "parent_category_id": 10, "category_name": "Leaf", "is_leaf": True},
    ], marketplace="SG"), filename="sg.csv"))
    store.initialize_sg_brand_acceptance()
    session = SGBrandSession(marketplace="SG", shop_id=22)
    client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "FAKE_KEY", 22, "FAKE_TOKEN"), marketplace="SG",
        request_json=lambda *args: {"response": {"brand_list": [
            {"brand_id": 7, "display_brand_name": "Maker", "original_brand_name": "Maker"},
            {"brand_id": 99, "display_brand_name": "No Brand", "original_brand_name": "No Brand"},
        ], "next_offset": 0, "has_next_page": False}},
    )
    sync_sg_brand_catalog_offline(client=client, session=session, store=store, confirmed_category_id=11)
    item = SGMapperRecommendation(
        "SG", "EXPANSION", "B000000000", "B000000001", "Synthetic item", "Maker", "Category", "",
        "GATE_ELIGIBLE", category_recommendation_status="CONFIRMED", recommended_category_id=11,
        recommended_category_path="Root > Leaf", category_verification_status="USER_CONFIRMED",
        category_is_confirmed=True, sls_result=SgSlsCategoryResult(action="CATEGORY_REVIEW"),
    )
    app = AppTest.from_string(APP, default_timeout=10)
    app.session_state["preview_store"] = store
    app.session_state["preview_session"] = session
    app.session_state["sg_category_mapper_recommendations"] = (item,)
    app.run()
    assert not app.exception
    return app, store, session


def select_brand(app, label):
    app.selectbox[0].select(label).run()
    app.checkbox[0].check().run()
    app.button(key="sg_category_mapper_apply_brand_0").click().run()
    assert not app.exception
    return app.session_state["sg_category_mapper_recommendations"][0]


def test_requires_selection_and_product_confirmation(preview):
    app, store, _ = preview
    assert app.selectbox[0].value is None
    assert app.button(key="sg_category_mapper_apply_brand_0").disabled
    app.selectbox[0].select("7 | Maker").run()
    assert app.button(key="sg_category_mapper_apply_brand_0").disabled
    assert store.find_sg_brand_alias("Maker", 11) is None


@pytest.mark.parametrize("label,status", [("7 | Maker", "REAL_BRAND_CONFIRMED"), ("99 | No Brand", "NO_BRAND_CONFIRMED")])
def test_saves_explicit_brand_and_keeps_shipping_stop(preview, label, status):
    app, store, _ = preview
    result = select_brand(app, label)
    assert result.brand_status == status
    assert result.sls_result.action == "CATEGORY_REVIEW"
    assert result.listing_ready is False
    assert any("Brand：確認済み" in text.value for text in app.success)
    assert not app.get("download_button")
    if status == "NO_BRAND_CONFIRMED":
        saved = store.find_sg_no_brand_confirmation(result.candidate_asin, 11)
        assert saved["no_brand_id"] == 99
        # A No Brand decision belongs to this product, not to every Maker item.
        assert store.find_sg_no_brand_confirmation("B000000002", 11) is None


def test_catalog_change_revokes_confirmed_display(preview):
    app, store, _ = preview
    select_brand(app, "7 | Maker")
    store.replace_sg_brand_catalog(11, [{"brand_id": 8, "brand_name": "Changed", "is_no_brand": False}])
    app.run()
    assert not app.exception
    assert not app.success
    assert app.session_state["sg_category_mapper_recommendations"][0].confirmed_brand_id is None
    assert not app.get("selectbox")


def test_product_change_clears_checkbox_and_no_brand_confirmation(preview):
    app, _, _ = preview
    app.selectbox[0].select("99 | No Brand").run()
    app.checkbox[0].check().run()
    item = app.session_state["sg_category_mapper_recommendations"][0]
    app.session_state["sg_category_mapper_recommendations"] = (replace(item, product_title="Other product"),)
    app.run()
    assert not app.exception
    assert app.selectbox[0].value is None
    assert not app.checkbox[0].value
    assert app.button(key="sg_category_mapper_apply_brand_0").disabled


def test_session_change_requires_current_catalog(preview):
    app, _, _ = preview
    select_brand(app, "99 | No Brand")
    app.session_state["preview_session"] = SGBrandSession(marketplace="SG", shop_id=22)
    app.run()
    assert not app.exception
    assert not app.success
    assert app.session_state["sg_category_mapper_recommendations"][0].brand_status == "REVIEW"


def test_saved_no_brand_is_stale_after_product_change(preview):
    app, _, _ = preview
    item = select_brand(app, "99 | No Brand")
    app.session_state["sg_category_mapper_recommendations"] = (replace(item, product_title="Changed Evidence"),)
    app.run()
    assert not app.exception
    assert not app.success
    assert app.session_state["sg_category_mapper_recommendations"][0].brand_status == "REVIEW"
    assert app.button(key="sg_category_mapper_apply_brand_0").disabled


def test_uninitialized_database_cannot_confirm(preview, tmp_path):
    app, _, _ = preview
    uninitialized = CategoryMapperStore(tmp_path / "uninitialized.sqlite3")
    app.session_state["preview_store"] = uninitialized
    app.run()
    assert not app.exception
    assert not app.get("selectbox")
    assert any("隔離検証DB" in text.value for text in app.warning)
    with uninitialized._connect() as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='product_no_brand_confirmations'").fetchone() is None


@pytest.fixture
def workflow_preview(preview):
    _, store, _ = preview
    calls = []
    responses = []

    def request(url, query, timeout):
        calls.append(dict(query))
        if responses:
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return {"response": {"brand_list": [
            {"brand_id": 7, "display_brand_name": "Maker", "original_brand_name": "Maker"},
            {"brand_id": 99, "display_brand_name": "No Brand", "original_brand_name": "No Brand"},
        ], "next_offset": 0, "has_next_page": False}}

    workflow = SGBrandWorkflow(store=store, client=ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "FAKE_KEY", 22, "FAKE_TOKEN"),
        marketplace="SG", request_json=request,
    ))
    app = AppTest.from_string('''
import streamlit as st
from modules.category_mapper_sg_ui import render_sg_category_mapper
render_sg_category_mapper(
    brand_workflow=st.session_state.workflow, ai_engine=st.session_state.get("fake_engine"),
)
''', default_timeout=10)
    app.session_state["workflow"] = workflow
    app.run()
    app.file_uploader(key="sg_category_mapper_source_csv").set_value((
        "prelisting_gate_eligible_sg_expansion.csv", _sg_gate_csv(), "text/csv",
    )).run()
    app.button(key="sg_category_mapper_build").click().run()
    app.number_input(key="sg_category_mapper_manual_category_0").set_value(11).run()
    app.button(key="sg_category_mapper_confirm_manual_0").click().run()
    assert not app.exception
    assert calls == []
    return app, workflow, calls, responses


def test_full_sg_flow_fetch_confirm_save_and_rerun_without_requests(workflow_preview):
    app, workflow, calls, _ = workflow_preview
    app.button(key="sg_category_mapper_fetch_brands_0").click().run()
    assert not app.exception
    assert len(calls) == 1
    assert calls[0]["shop_id"] == "22" and calls[0]["category_id"] == "11"
    item = select_brand(app, "99 | No Brand")
    assert item.brand_status == "NO_BRAND_CONFIRMED"
    assert item.listing_ready is False
    assert workflow.store.find_sg_no_brand_confirmation(item.candidate_asin, 11)["no_brand_id"] == 99
    app.run()
    assert len(calls) == 1
    assert [button.label for button in app.get("download_button")] == ["開発検証：確認状況CSV"]


def test_refetch_failure_does_not_reuse_saved_brand_or_leak_exception(workflow_preview):
    app, _, calls, responses = workflow_preview
    app.button(key="sg_category_mapper_fetch_brands_0").click().run()
    select_brand(app, "99 | No Brand")
    responses.append(RuntimeError("PRIVATE_TEST_MARKER"))
    app.button(key="sg_category_mapper_fetch_brands_0").click().run()
    assert not app.exception
    assert len(calls) == 2
    item = app.session_state["sg_category_mapper_recommendations"][0]
    assert item.brand_status == "REVIEW" and item.confirmed_brand_id is None
    assert not any("Brand：確認済み" in text.value for text in app.success)
    assert "PRIVATE_TEST_MARKER" not in str(app)
    assert not app.get("selectbox")


def test_input_replacement_requires_new_brand_acquisition(workflow_preview):
    app, _, calls, _ = workflow_preview
    app.button(key="sg_category_mapper_fetch_brands_0").click().run()
    select_brand(app, "99 | No Brand")
    changed = _sg_gate_csv().replace(b"Example personal care item", b"Changed product title")
    app.file_uploader(key="sg_category_mapper_source_csv").set_value((
        "prelisting_gate_eligible_sg_expansion.csv", changed, "text/csv",
    )).run()
    app.button(key="sg_category_mapper_build").click().run()
    assert not app.exception
    assert len(calls) == 1
    assert not any("Brand：確認済み" in text.value for text in app.success)
    assert not app.get("selectbox")


@pytest.mark.parametrize("market,default_transport", [("PH", False), ("SG", True)])
def test_workflow_rejects_other_market_or_default_network(preview, market, default_transport):
    _, store, _ = preview
    kwargs = {} if default_transport else {"request_json": lambda *args: {}}
    client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "FAKE_KEY", 22, "FAKE_TOKEN"), marketplace=market, **kwargs,
    )
    with pytest.raises(ValueError):
        SGBrandWorkflow(store=store, client=client)


def enable_ai_preview(app, outcomes):
    item = app.session_state["sg_category_mapper_recommendations"][0]
    app.session_state["sg_category_mapper_recommendations"] = (replace(
        item, category_is_confirmed=False, category_verification_status="UNRESOLVED",
        recommended_category_id=None, recommended_category_path="",
    ),)
    provider = FakeCategoryAIProvider(outcomes)
    app.session_state["fake_engine"] = CategoryAIEngine(provider)
    app.run()
    app.button(key="sg_category_mapper_build_ai_suggestions").click().run()
    assert not app.exception
    return provider


def test_ai_only_suggests_until_human_adoption(workflow_preview):
    app, _, calls, _ = workflow_preview
    provider = enable_ai_preview(app, [make_fake_select(10, confidence=1.0), make_fake_select(11, confidence=1.0)])
    item = app.session_state["sg_category_mapper_recommendations"][0]
    assert item.category_is_confirmed is False and item.listing_ready is False
    assert provider.requests[0][0].product.marketplace == "SG"
    app.button(key="sg_category_mapper_apply_ai_0").click().run()
    assert not app.exception
    confirmed = app.session_state["sg_category_mapper_recommendations"][0]
    assert confirmed.category_is_confirmed and confirmed.recommended_category_id == 11
    assert confirmed.listing_ready is False and confirmed.confirmed_brand_id is None
    assert calls == []


def test_ai_abstain_keeps_manual_category_path(workflow_preview):
    app, _, _, _ = workflow_preview
    enable_ai_preview(app, [make_fake_abstain()])
    assert not any(button.key == "sg_category_mapper_apply_ai_0" for button in app.button)
    assert app.number_input(key="sg_category_mapper_manual_category_0")
    assert not app.session_state["sg_category_mapper_recommendations"][0].category_is_confirmed


def test_ai_adoption_rechecks_current_category_path(workflow_preview):
    app, workflow, _, _ = workflow_preview
    enable_ai_preview(app, [make_fake_select(10), make_fake_select(11)])
    with workflow.store._connect() as connection:
        connection.execute("UPDATE catalog_categories SET category_path='Root > Changed' WHERE marketplace='SG' AND category_id=11")
    app.button(key="sg_category_mapper_apply_ai_0").click().run()
    assert not app.exception
    assert not app.session_state["sg_category_mapper_recommendations"][0].category_is_confirmed
    assert any("現在catalog" in text.value for text in app.warning)


def test_same_brand_name_different_market_ids_stay_separate(workflow_preview):
    app, workflow, _, _ = workflow_preview
    workflow.store.save_brand_page("PH", 11, [
        {"brand_id": 404, "brand_name": "Maker", "is_no_brand": False},
    ], next_offset=0, is_complete=True)
    before = workflow.store.list_brands("PH", 11)
    app.button(key="sg_category_mapper_fetch_brands_0").click().run()
    result = select_brand(app, "7 | Maker")
    assert result.confirmed_brand_id == 7 and result.marketplace == "SG"
    assert workflow.store.list_brands("PH", 11) == before
    assert before[0]["brand_id"] == 404
