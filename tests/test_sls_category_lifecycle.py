from dataclasses import replace
import sqlite3
import pytest

from modules.category_mapper import (CategoryMapperInput, CategoryMapperInputRow, GATE_ELIGIBLE,
    RAW_EXPANSION, build_recommendations, build_mapper_exports, refresh_sls_results)
from modules.category_mapper_store import CategoryMapperStore
from modules.category_mapper_ui import replace_from_group
from modules.sls_category_assets import load_ph_context
from sls_category_support import ready_item, copy_assets, rewrite_asset, stop_shampoo


def source(category):
    return CategoryMapperInput("PH", "EXPANSION", GATE_ELIGIBLE, (
        CategoryMapperInputRow("B000000000", "B000000001", "Item", "ASIENCE", category,
                               "EXPANSION", GATE_ELIGIBLE),))


@pytest.mark.parametrize("path", ["profile", "mapping"])
def test_saved_confirmations_get_current_sls_without_db_migration(tmp_path, monkeypatch, path):
    store = CategoryMapperStore(tmp_path / "saved.sqlite3")
    category = "シャンプー" if path == "profile" else "saved category"
    cid = 100869
    if path == "mapping":
        store.save_category_mapping(marketplace="PH", mapping_key_type="KEEPA_CATEGORY",
            mapping_key=category, canonical_product_type="", category_id=cid, category_path="Shampoo")
    store.save_brand_policy(marketplace="PH", keepa_category=category, keepa_brand="ASIENCE",
                            category_id=cid, brand_policy="NO_BRAND_SELECTED", brand_id=0)
    with sqlite3.connect(store.db_path) as conn:
        schema = conn.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name").fetchall()
    before = build_recommendations(source(category), resolver_titles=None, store=store)[0]
    assert before.listing_ready
    root = copy_assets(tmp_path, monkeypatch)
    rewrite_asset(root, "markets/PH", stop_shampoo)
    reopened = CategoryMapperStore(store.db_path)
    after = build_recommendations(source(category), resolver_titles=None, store=reopened)[0]
    assert after.category_is_confirmed and after.no_brand_selected_by_user
    assert after.sls_result.action == "CATEGORY_EXCLUDE" and not after.listing_ready
    assert not build_mapper_exports((before,)).listing_tool_text
    with sqlite3.connect(store.db_path) as conn:
        assert conn.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name").fetchall() == schema


def test_group_copy_preserves_member_safety_market_and_invalidates_sls(tmp_path):
    ready = ready_item(tmp_path)
    member = replace(ready, candidate_asin="B000000002", input_safety_state=RAW_EXPANSION)
    copied = replace_from_group(member, ready)
    assert copied.input_safety_state == RAW_EXPANSION
    assert copied.candidate_asin == "B000000002"
    assert copied.sls_result.check_state == "UNCHECKED" and not copied.listing_ready
    refreshed = refresh_sls_results((copied,), context=load_ph_context())[0]
    assert refreshed.sls_result.action == "CATEGORY_ALLOW" and not refreshed.listing_ready
    sg = replace_from_group(replace(member, marketplace="SG"), ready)
    assert sg.marketplace == "SG" and not sg.listing_ready
    with pytest.raises(ValueError, match="PH_ONLY"):
        refresh_sls_results((sg,), context=load_ph_context())
