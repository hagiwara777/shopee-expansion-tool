"""Short PH/SG protected invariants; detailed Mapper/UI tests run offline."""
from dataclasses import replace
import csv
from io import StringIO
import pytest

from modules.category_mapper import (apply_manual_brand, build_mapper_exports,
    refresh_sls_results, parse_category_mapper_input, CategoryMapperInputError)
from modules.sls_category_assets import load_ph_context
from modules.sls_category_rules import evaluate_ph_category, is_current_allow
from sls_category_support import ready_item, copy_assets, rewrite_asset, stop_shampoo
from test_prelisting_gate import candidate, inventory, evaluate


@pytest.mark.parametrize("action", ["CATEGORY_REVIEW", "CATEGORY_EXCLUDE"])
def test_stopped_rows_cannot_leak_or_be_released_by_brand(tmp_path, action):
    context = load_ph_context()
    cid = next(cid for cid, rule in context.rules.items() if rule.action == action)
    item = ready_item(tmp_path)
    # Deliberately leave the old ALLOW attached after changing the category.
    item = replace(item, recommended_category_id=cid)
    assert not item.listing_ready
    item = refresh_sls_results((item,), context=context)[0]
    for brand in ({"brand_id": 0, "is_no_brand": True}, {"brand_id": 123, "is_no_brand": False}):
        updated = apply_manual_brand(item, brand=brand)
        assert updated.sls_result == item.sls_result
        assert not updated.listing_ready
        bundle = build_mapper_exports((updated,))
        assert not list(csv.DictReader(StringIO(bundle.groups_csv.decode("utf-8-sig"))))
        assert not bundle.listing_tool_text


def test_direct_export_rechecks_new_asset_and_market_binding(tmp_path, monkeypatch):
    item = ready_item(tmp_path)
    root = copy_assets(tmp_path, monkeypatch)
    rewrite_asset(root, "markets/PH", stop_shampoo)
    current = load_ph_context()
    assert not is_current_allow(item.sls_result, marketplace="PH", category_id=100869,
                                category_confirmed=True, context=current)
    assert not build_mapper_exports((item,)).listing_tool_text
    assert not replace(item, marketplace="SG").listing_ready
    with pytest.raises(ValueError, match="PH_ONLY"):
        build_mapper_exports((replace(item, marketplace="SG"),))
    with pytest.raises(ValueError, match="PH_ONLY"):
        evaluate_ph_category(marketplace="SG", category_id=100869, category_confirmed=True, context=current)


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("title", ["Rechargeable desk light", "power bank"])
def test_battery_and_existing_safety_cannot_reach_mapper(market, title, tmp_path):
    result = evaluate([candidate(product_title=title)], [inventory((), marketplace=market,
                       shop_label=market, source_file=market + ".csv", data_row_count=0)], marketplace=market)
    assert result.rows[0].final_eligibility in {"REVIEW", "EXCLUDE"}
    # Category ALLOW must not make a non-eligible Recommendation ready either.
    item = ready_item(tmp_path)
    unsafe = replace(item, input_safety_state=result.rows[0].final_eligibility)
    assert not unsafe.listing_ready
    assert not build_mapper_exports((unsafe,)).listing_tool_text
