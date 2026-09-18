from collections import Counter
from dataclasses import replace
from types import MappingProxyType
import pytest

from modules import category_mapper as mapper
from modules.sls_category_assets import load_ph_context, SlsRule
from modules.sls_category_rules import evaluate_ph_category, is_current_allow, SlsCategoryResult
from sls_category_support import ready_item


@pytest.mark.parametrize("status,qty,action,reason", [
    ("NO", "0", "CATEGORY_EXCLUDE", "SLS_NOT_SHIPPABLE"),
    ("NO", "No limit", "CATEGORY_EXCLUDE", "SLS_NOT_SHIPPABLE"),
    ("Shopeeと要確認", "No limit", "CATEGORY_REVIEW", "SHOPEE_CHECK_REQUIRED"),
    ("YES", "No limit", "CATEGORY_ALLOW", "NO_CATEGORY_STOP"),
    ("YES", "1", "CATEGORY_REVIEW", "QUANTITY_LIMIT"),
    ("YES", "2", "CATEGORY_REVIEW", "QUANTITY_LIMIT"),
    ("YES", "below 5kg", "CATEGORY_REVIEW", "UNRESOLVED_RULE"),
    ("?", "", "CATEGORY_REVIEW", "UNRESOLVED_RULE"),
])
def test_ph_semantics(status, qty, action, reason):
    ctx = load_ph_context()
    ctx = replace(ctx, rules=MappingProxyType({100869: SlsRule(status, qty, action, reason, ())}))
    result = evaluate_ph_category(marketplace="PH", category_id=100869, category_confirmed=True, context=ctx)
    assert result.action == action and result.reason_codes == (reason,)


def test_source_version_acceptance_counts_and_missing():
    ctx = load_ph_context()
    results = [evaluate_ph_category(marketplace="PH", category_id=cid, category_confirmed=True, context=ctx) for cid in ctx.category_ids]
    assert Counter(r.action for r in results) == {"CATEGORY_ALLOW": 1964, "CATEGORY_EXCLUDE": 174, "CATEGORY_REVIEW": 24}
    for cid in (None, True, "100869", 999999999):
        assert evaluate_ph_category(marketplace="PH", category_id=cid, category_confirmed=True, context=ctx).action == "CATEGORY_REVIEW"
    assert evaluate_ph_category(marketplace="PH", category_id=100869, category_confirmed=False, context=ctx).check_state == "UNCHECKED"
    missing = replace(ctx, rules=MappingProxyType({}))
    assert evaluate_ph_category(marketplace="PH", category_id=100869, category_confirmed=True, context=missing).reason_codes == ("MISSING_CATEGORY_RULE",)


def test_property_pure_and_local_binding(tmp_path, monkeypatch):
    item = ready_item(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("I/O in pure property")
    monkeypatch.setattr(mapper, "load_ph_context", forbidden)
    from pathlib import Path
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    assert item.listing_ready and item.group_key
    for result in (SlsCategoryResult(), replace(item.sls_result, check_state="UNAVAILABLE"),
                   replace(item.sls_result, marketplace="SG"), replace(item.sls_result, category_id=100661)):
        assert not replace(item, sls_result=result).listing_ready


def test_taxonomy_version_and_category_change_invalidate(tmp_path):
    item = ready_item(tmp_path)
    ctx = load_ph_context()
    assert not is_current_allow(item.sls_result, marketplace="PH", category_id=100869,
                                category_confirmed=True, context=replace(ctx, taxonomy_version="new"))
    changed = mapper.apply_manual_category(item, category={"category_id": 100661, "category_path": "Perfumes"},
                                          mandatory_attribute_count=0, no_brand_available=True)
    assert changed.sls_result.action == "CATEGORY_EXCLUDE"
    assert changed.sls_result.category_id == 100661
    assert not changed.brand_is_confirmed and not changed.no_brand_selected_by_user
    assert not changed.listing_ready
