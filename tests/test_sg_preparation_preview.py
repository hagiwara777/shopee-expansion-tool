import csv
import sqlite3
from dataclasses import replace
from io import StringIO

import pytest

from test_sg_brand_confirmation_ui import preview, workflow_preview, select_brand
from modules.category_mapper_sg_preparation import confirm_sg_category_group, build_sg_confirmation_audit_csv
from modules.category_mapper_sg import SGCategoryMapperError


def group_items(app):
    first = app.session_state["sg_category_mapper_recommendations"][0]
    return first, replace(first, candidate_asin="B000000002", product_title="Other synthetic item")


def test_group_category_confirmation_saves_each_asin_without_confirming_brand(preview):
    app, store, _ = preview
    result = confirm_sg_category_group(group_items(app), store=store, category_id=11,
                                      category_path="Root > Leaf", human_verified=True)
    assert len(result) == 2
    for item in result:
        assert store.find_confirmed_category_mapping("SG", "ASIN", item.candidate_asin)["category_id"] == 11
        assert item.category_is_confirmed and item.confirmed_brand_id is None and not item.listing_ready


def test_group_save_rolls_back_every_product_on_failure(preview):
    app, store, _ = preview
    with store._connect() as connection:
        connection.execute("""CREATE TRIGGER fail_second BEFORE INSERT ON category_mappings
            WHEN NEW.mapping_key='b000000002' BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        confirm_sg_category_group(group_items(app), store=store, category_id=11,
                                  category_path="Root > Leaf", human_verified=True)
    for item in group_items(app):
        assert store.find_confirmed_category_mapping("SG", "ASIN", item.candidate_asin) is None


@pytest.mark.parametrize("change", [{"marketplace": "PH"}, {"keepa_brand": "Other"}, {"input_safety_state": "REVIEW"}])
def test_group_rejects_mixed_market_brand_or_noneligible(preview, change):
    app, store, _ = preview
    first, second = group_items(app)
    with pytest.raises(SGCategoryMapperError):
        confirm_sg_category_group((first, replace(second, **change)), store=store,
                                  category_id=11, category_path="Root > Leaf", human_verified=True)
    assert store.find_confirmed_category_mapping("SG", "ASIN", first.candidate_asin) is None


def test_attributes_are_sg_bound_and_failure_discards_old_result(workflow_preview):
    app, workflow, calls, responses = workflow_preview
    responses.append({"response": {"list": [{"category_id": 11, "attribute_tree": [
        {"attribute_id": 1, "display_attribute_name": "Size", "is_mandatory": True},
    ]}]}})
    app.button(key="sg_category_mapper_fetch_attributes_0").click().run()
    assert not app.exception
    assert "category_id_list" in calls[-1]
    item = app.session_state["sg_category_mapper_recommendations"][0]
    assert workflow.current_attributes(item).attributes[0]["attribute_name"] == "Size"
    assert any("必須属性: 1件" in text.value for text in app.caption)
    app.run()
    assert len(calls) == 1
    responses.append(RuntimeError("PRIVATE_ATTRIBUTE_MARKER"))
    app.button(key="sg_category_mapper_fetch_attributes_0").click().run()
    assert not app.exception
    assert workflow.current_attributes(item) is None
    assert "PRIVATE_ATTRIBUTE_MARKER" not in str(app)


def test_audit_revalidates_stale_brand_and_never_exports_ready_true(workflow_preview):
    app, workflow, _, _ = workflow_preview
    app.button(key="sg_category_mapper_fetch_brands_0").click().run()
    item = select_brand(app, "99 | No Brand")
    workflow.session.invalidate(11)
    data = build_sg_confirmation_audit_csv((item,), store=workflow.store, session=workflow.session)
    row = next(csv.DictReader(StringIO(data.decode("utf-8-sig"))))
    assert row["brand_id"] == "" and row["brand_status"] == "REVIEW"
    assert row["listing_ready"] == "FALSE" and row["output_scope"] == "DEVELOPMENT_AUDIT_ONLY"


def test_group_ui_requires_explicit_product_confirmation(workflow_preview):
    app, _, _, _ = workflow_preview
    app.session_state["sg_category_mapper_recommendations"] = group_items(app)
    app.run()
    app.number_input(key="sg_category_mapper_group_category_0").set_value(11).run()
    assert app.button(key="sg_category_mapper_group_confirm_0").disabled
    group_checkbox = next(box for box in app.checkbox if "全商品のCategory" in box.label)
    group_checkbox.check().run()
    app.button(key="sg_category_mapper_group_confirm_0").click().run()
    assert not app.exception
    assert all(item.category_is_confirmed for item in app.session_state["sg_category_mapper_recommendations"])


def test_preparation_assessment_lists_missing_steps_and_closes_exit(workflow_preview):
    from modules.category_mapper_sg_preparation import assess_sg_preparation
    app,workflow,_,_=workflow_preview
    item=app.session_state["sg_category_mapper_recommendations"][0]
    result=assess_sg_preparation((item,),workflow=workflow)[0]
    assert not result["preparation_complete"] and not result["listing_ready"] and not result["formal_output_enabled"]
    assert "最新Brand一覧の取得・商品との照合" in result["missing_steps"]
    assert "武器画像検査の対象判定資料" in result["missing_steps"]
    assert "商品説明・画像の人間確認" not in result["missing_steps"]


def test_failed_catalog_refresh_closes_all_preparation(workflow_preview):
    from modules.category_mapper_sg_preparation import assess_sg_preparation,build_sg_preparation_candidate_files
    app,workflow,_,_=workflow_preview; item=app.session_state["sg_category_mapper_recommendations"][0]
    workflow._client.catalog_refresh_failed=True
    with pytest.raises(ValueError): assess_sg_preparation((item,),workflow=workflow)
    with pytest.raises(ValueError): build_sg_preparation_candidate_files((item,),workflow=workflow)
