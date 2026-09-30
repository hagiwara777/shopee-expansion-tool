"""Decision precedence and exact-ID/current-category binding."""
from dataclasses import replace
from types import MappingProxyType
import pytest
from modules.sls_category_assets import load_sg_context, SgSlsRule
from modules.sls_category_rules_sg import evaluate_sg_category


def evaluate(cid=100869, context=None, **changes):
    context = context or load_sg_context()
    path = " > ".join(context.names.get(cid, ("Unknown",)))
    args = dict(marketplace="SG", category_id=cid, category_confirmed=True,
                category_path=path, current_category_path=path, current_is_leaf=True,
                catalog_version="synthetic-content-digest", context=context)
    args.update(changes)
    return evaluate_sg_category(**args)


@pytest.mark.parametrize("status,quantity,action,reason", [
    ("YES", "No limit", "CATEGORY_ALLOW", "NO_CATEGORY_STOP"),
    ("NO", "No limit", "CATEGORY_EXCLUDE", "SLS_NOT_SHIPPABLE"),
    ("NO", "0", "CATEGORY_EXCLUDE", "SLS_NOT_SHIPPABLE"),
    ("Shopeeと要確認", "No limit", "CATEGORY_REVIEW", "SHOPEE_CHECK_REQUIRED"),
    ("YES", "2", "CATEGORY_REVIEW", "QUANTITY_LIMIT"),
    ("YES", "below 5kg", "CATEGORY_REVIEW", "WEIGHT_LIMIT"),
    ("YES", "0", "CATEGORY_REVIEW", "QUANTITY_LIMIT"),
    ("YES", "", "CATEGORY_REVIEW", "UNRESOLVED_RULE"),
    ("", "No limit", "CATEGORY_REVIEW", "UNRESOLVED_RULE"),
    ("UNKNOWN", "No limit", "CATEGORY_REVIEW", "UNRESOLVED_RULE"),
])
def test_conditions(status, quantity, action, reason):
    context = load_sg_context()
    rules = dict(context.rules)
    rules[100869] = replace(rules[100869], status=status, quantity=quantity)
    result = evaluate(context=replace(context, rules=MappingProxyType(rules)))
    assert result.action == action and result.reason_codes == (reason,)
    assert result.taxonomy_version == context.taxonomy_version
    assert result.market_asset_version == context.market_asset_version
    assert result.transform_version == context.transform_version
    assert result.catalog_version == "synthetic-content-digest"
    assert result.source_refs


@pytest.mark.parametrize("cid", [100906,100907,100908,100909,100910,100911,100912,100913,100914,100915])
def test_explicit_group_scope_only(cid):
    result = evaluate(cid)
    assert result.action == "CATEGORY_EXCLUDE"
    assert result.reason_codes == ("EXPLICIT_GROUP_NOTICE",)


@pytest.mark.parametrize("cid", [100044,100847,100848,102070,102178,None,True,0,-1,"100869",100869.0])
def test_missing_or_invalid_id_never_falls_back(cid):
    result = evaluate(cid)
    assert result.action == "CATEGORY_REVIEW"


def test_unconfirmed_and_market_rejection():
    assert evaluate(category_confirmed=False).check_state == "UNCHECKED"
    assert evaluate(category_confirmed=False).action is None
    with pytest.raises(ValueError, match="SG_ONLY"):
        evaluate(marketplace="PH")
    with pytest.raises(ValueError, match="SG_ONLY"):
        evaluate(context=replace(load_sg_context(), marketplace="PH"))


@pytest.mark.parametrize("changes", [dict(current_is_leaf=False), dict(current_category_path=None),
    dict(catalog_version=""), dict(category_path="Other"), dict(current_category_path="Other",category_path="Other")])
def test_current_catalog_and_identity_required(changes):
    assert evaluate(**changes).action == "CATEGORY_REVIEW"


def test_cosmetic_whitespace_after_exact_id_is_accepted():
    context = load_sg_context()
    path = " > ".join(context.names[102602])
    result = evaluate(102602, current_category_path=" ".join(path.split()), category_path=" ".join(path.split()))
    assert result.action == "CATEGORY_ALLOW"
    assert evaluate(999999, category_path=path, current_category_path=path).action == "CATEGORY_REVIEW"


def test_no_parent_or_name_rule_inheritance():
    context = load_sg_context()
    rules = dict(context.rules)
    del rules[100869]
    assert evaluate(context=replace(context,rules=MappingProxyType(rules))).reason_codes == ("MISSING_CATEGORY_RULE",)
