"""Fresh content/assets and independent SG result lifecycle."""
from dataclasses import replace
import sqlite3
import pytest
from modules.category_mapper_sg import refresh_sg_sls_results, confirm_sg_category, SGCategoryMapperError
from sls_category_sg_support import sg_item
from sls_category_support import copy_assets, rewrite_asset


def test_refresh_changes_only_sls_state(tmp_path):
    store,item = sg_item(tmp_path)
    assert item.sls_result.action == "CATEGORY_ALLOW"
    updated = refresh_sg_sls_results((item,),store=store)[0]
    assert replace(updated,sls_result=item.sls_result) == item
    assert not updated.listing_ready and updated.group_key == ""


@pytest.mark.parametrize("column,value", [("category_path","Changed"),("category_name","Changed"),
    ("is_leaf",0),("parent_category_id",1234567)])
def test_same_timestamp_and_count_content_drift_stops(tmp_path,column,value):
    store,item=sg_item(tmp_path)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute(f"UPDATE catalog_categories SET {column}=? WHERE marketplace='SG' AND category_id=?",(value,100869))
    current=refresh_sg_sls_results((item,),store=store)[0]
    assert current.sls_result.action != "CATEGORY_ALLOW"
    assert current.category_is_confirmed == item.category_is_confirmed
    assert current.manual_review_required == item.manual_review_required


def test_asset_change_invalidates_old_allow(tmp_path,monkeypatch):
    store,item=sg_item(tmp_path)
    root=copy_assets(tmp_path,monkeypatch)
    def stop(payload):
        next(r for r in payload['records'] if r['category_id']==100869).update(status="NO",quantity="No limit")
    rewrite_asset(root,"markets/SG",stop)
    current=refresh_sg_sls_results((item,),store=store)[0]
    assert current.sls_result.action == "CATEGORY_EXCLUDE"
    assert current.sls_result.market_asset_version != item.sls_result.market_asset_version
    assert replace(current,sls_result=item.sls_result) == item
    (root/'markets/SG.json').unlink()
    assert refresh_sg_sls_results((current,),store=store)[0].sls_result.check_state == "UNAVAILABLE"


def test_category_change_and_unconfirmation_invalidate(tmp_path):
    store,item=sg_item(tmp_path)
    altered=replace(item,recommended_category_id=999999)
    assert refresh_sg_sls_results((altered,),store=store)[0].sls_result.action == "CATEGORY_REVIEW"
    for altered in (replace(item,category_is_confirmed=False),replace(item,category_verification_status="AI_SUGGESTED")):
        assert refresh_sg_sls_results((altered,),store=store)[0].sls_result.check_state == "UNCHECKED"
    confirmed=confirm_sg_category(item,store=store,category_id=100869,expected_category_path=item.recommended_category_path)
    assert confirmed.sls_result.action == "CATEGORY_ALLOW"
    assert confirmed.brand_status == "UNRESOLVED" and not confirmed.listing_ready


@pytest.mark.parametrize("state", ["REVIEW","EXCLUDE","BLOCK"])
def test_upstream_stop_is_preserved(tmp_path,state):
    store,item=sg_item(tmp_path)
    stopped=replace(item,input_safety_state=state)
    refreshed=refresh_sg_sls_results((stopped,),store=store)[0]
    assert refreshed.input_safety_state == state
    assert refreshed.sls_result.action == "CATEGORY_REVIEW" and not refreshed.listing_ready
    with pytest.raises(SGCategoryMapperError):
        confirm_sg_category(stopped,store=store,category_id=100869,expected_category_path=item.recommended_category_path)


def test_catalog_version_is_refreshed_even_when_action_remains_allow(tmp_path):
    store,item=sg_item(tmp_path)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("UPDATE catalog_categories SET synced_at='NEW' WHERE marketplace='SG'")
    refreshed=refresh_sg_sls_results((item,),store=store)[0]
    assert refreshed.sls_result.action == "CATEGORY_ALLOW"
    assert refreshed.sls_result.catalog_version != item.sls_result.catalog_version


def test_invalid_persisted_leaf_type_and_db_read_failure_stop(tmp_path):
    store,item=sg_item(tmp_path)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("UPDATE catalog_categories SET is_leaf=2 WHERE marketplace='SG' AND category_id=100869")
    assert refresh_sg_sls_results((item,),store=store)[0].sls_result.check_state == "UNAVAILABLE"
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("DROP TABLE catalog_categories")
    assert refresh_sg_sls_results((item,),store=store)[0].sls_result.check_state == "UNAVAILABLE"


def test_valid_unrelated_catalog_content_change_rebinds_same_allow(tmp_path):
    store,item=sg_item(tmp_path)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("INSERT INTO catalog_categories(marketplace,category_id,parent_category_id,category_name,category_path,is_leaf,is_others,synced_at,api_version) SELECT marketplace,9999999,NULL,'Other','Other',1,0,synced_at,api_version FROM catalog_categories WHERE marketplace='SG' AND category_id=100869")
    refreshed=refresh_sg_sls_results((item,),store=store)[0]
    assert refreshed.sls_result.action == "CATEGORY_ALLOW"
    assert refreshed.sls_result.catalog_version != item.sls_result.catalog_version
