"""Isolated SG group confirmation and audit preview; listing exports stay closed."""

import csv
from dataclasses import replace
from io import StringIO

from modules.category_mapper_sg import SGMapperRecommendation, SGCategoryMapperError, refresh_sg_sls_results
from modules.category_mapper_store import CategoryMapperStore
from modules.sls_category_rules_sg import SgSlsCategoryResult
from modules.preparation_group_output import format_preparation_groups


def group_sg_confirmation_items(items):
    groups = {}
    for item in items:
        if item.marketplace != "SG" or item.input_safety_state != "GATE_ELIGIBLE":
            raise SGCategoryMapperError("SG groups require SG eligible input.")
        key = (item.keepa_category, item.keepa_brand)
        groups.setdefault(key, []).append(item)
    return tuple(tuple(members) for members in groups.values())


def confirm_sg_category_group(
    items: tuple[SGMapperRecommendation, ...], *, store: CategoryMapperStore,
    category_id: int, category_path: str, human_verified: bool,
) -> tuple[SGMapperRecommendation, ...]:
    if human_verified is not True or len(group_sg_confirmation_items(items)) != 1:
        raise SGCategoryMapperError("Confirm every product in one SG group explicitly.")
    store.save_sg_category_group(tuple(item.candidate_asin for item in items),
                                 category_id=category_id, category_path=category_path)
    updated = tuple(replace(
        item, category_recommendation_status="CONFIRMED", recommended_category_id=category_id,
        recommended_category_path=category_path, category_confidence="HIGH",
        category_recommendation_source="USER_CONFIRMED", category_verification_status="USER_CONFIRMED",
        category_is_confirmed=True, manual_review_required=False, manual_review_reason="",
        brand_status="UNRESOLVED", confirmed_brand_id=None, confirmed_brand_name="",
        brand_candidates=(), brand_current_valid=False,
        brand_review_reason="SG Brand requires current catalog and human confirmation.",
        sls_result=SgSlsCategoryResult(category_id=category_id),
    ) for item in items)
    return refresh_sg_sls_results(updated, store=store)


def build_sg_confirmation_audit_csv(items, *, store, session) -> bytes:
    """Revalidate immediately; never emit TRUE readiness or listing handoff rows."""
    from modules.category_mapper_sg import review_sg_brand
    items = tuple(items)
    if len({item.candidate_asin for item in items}) != len(items):
        raise SGCategoryMapperError("Duplicate SG audit product identity.")
    group_sg_confirmation_items(items)
    checked = refresh_sg_sls_results(items, store=store)
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=(
        "marketplace", "asin", "category_id", "category_path", "category_confirmed",
        "brand_id", "brand_name", "brand_status", "sls_action", "listing_ready", "output_scope",
    ), lineterminator="\n")
    writer.writeheader()
    for item in checked:
        current = review_sg_brand(item, store=store, session=session)
        category = (store.get_category("SG", item.recommended_category_id)
                    if type(item.recommended_category_id) is int else None)
        valid_category = (item.category_is_confirmed and item.category_verification_status == "USER_CONFIRMED"
                          and category is not None and bool(category["is_leaf"])
                          and category["category_path"] == item.recommended_category_path)
        writer.writerow({
            "marketplace": "SG", "asin": item.candidate_asin,
            "category_id": item.recommended_category_id if valid_category else "",
            "category_path": item.recommended_category_path if valid_category else "",
            "category_confirmed": "TRUE" if valid_category else "FALSE",
            "brand_id": "" if current.confirmed_brand_id is None else current.confirmed_brand_id,
            "brand_name": current.confirmed_brand_name, "brand_status": current.brand_status,
            "sls_action": item.sls_result.action or item.sls_result.check_state,
            "listing_ready": "FALSE", "output_scope": "DEVELOPMENT_AUDIT_ONLY",
        })
    return output.getvalue().encode("utf-8-sig")


def build_sg_preparation_candidate_files(items, *, workflow):
    """Offline preparation preview. Never change listing_ready or the real exit."""
    rows = _sg_preparation_rows(items, workflow=workflow)
    csv_output, text = format_preparation_groups(rows, extra_columns=("attribute_check_state", "output_scope"),
                                                unknown_attribute_text="未取得")
    banner = "開発検証用の出品準備候補です。出品用ファイルではありません。listing_ready=FALSE。"
    return csv_output, banner + ("\n\n" + text if text else ""), len(rows)


def build_sg_beta_preparation_files(items, *, workflow):
    """PH-style manual-preparation output, only after formal SG activation.

    Category/Brand/SLS/text/weapon checks use the same current assessment as
    the preview. This does not submit listings or confirm Seller Center input.
    """
    from modules.sg_beta_release import require_sg_beta_operation
    require_sg_beta_operation()
    rows = _sg_preparation_rows(items, workflow=workflow)
    rows = [{**row, "listing_ready": "TRUE", "output_scope": "SG_BETA_MANUAL_PREPARATION"}
            for row in rows]
    csv_output, text = format_preparation_groups(rows, extra_columns=("attribute_check_state", "output_scope"),
                                                unknown_attribute_text="未取得")
    require_sg_beta_operation()
    return csv_output, text, len(rows)


def _sg_preparation_rows(items, *, workflow):
    workflow.require_image_system_current()
    items = tuple(items)
    if len({item.candidate_asin for item in items}) != len(items):
        raise SGCategoryMapperError("Duplicate preparation candidate ASIN")
    group_sg_confirmation_items(items)
    checked = refresh_sg_sls_results(items, store=workflow.store)
    assessments = assess_sg_preparation(checked, workflow=workflow)
    ready = [assessment["item"] for assessment in assessments if assessment["preparation_complete"]]
    rows = []
    for item in ready:
        attributes = workflow.current_attributes(item)
        mandatory_count = (sum(attribute["is_mandatory"] for attribute in attributes.attributes)
                           if attributes is not None else None)
        rows.append({"marketplace": "SG", "asin": item.candidate_asin,
                     "group_key": f"SG|{item.recommended_category_id}|{item.confirmed_brand_id}",
                     "category_id": item.recommended_category_id, "category_path": item.recommended_category_path,
                     "brand_id": item.confirmed_brand_id, "brand_name": item.confirmed_brand_name,
                     "mandatory_attribute_count": mandatory_count, "verification_status": "USER_CONFIRMED",
                     "attribute_check_state": "FETCHED" if attributes is not None else "NOT_FETCHED",
                     "listing_ready": "FALSE", "output_scope": "DEVELOPMENT_PREPARATION_PREVIEW"})
    return rows


def assess_sg_preparation(items, *, workflow):
    """Current per-product completion and missing steps; never opens formal exit."""
    from modules.category_mapper_sg import review_sg_brand
    workflow.require_catalog_current()
    workflow.require_image_system_current()
    items=tuple(items)
    if len({item.candidate_asin for item in items})!=len(items):
        raise SGCategoryMapperError("Duplicate preparation ASIN")
    group_sg_confirmation_items(items)
    checked=refresh_sg_sls_results(items,store=workflow.store)
    assessments=[]
    for item in checked:
        if workflow._live_scope is not None:
            workflow._live_scope.require_product(item)
        current=review_sg_brand(item,store=workflow.store,session=workflow.session)
        missing=[]
        if not current.category_is_confirmed or current.category_verification_status!="USER_CONFIRMED":
            missing.append("カテゴリー確認")
        if not current.brand_current_valid or current.brand_status not in {"REAL_BRAND_CONFIRMED","NO_BRAND_CONFIRMED"}:
            missing.append("最新Brand一覧の取得・商品との照合")
        if item.sls_result.check_state!="EVALUATED" or item.sls_result.action!="CATEGORY_ALLOW":
            missing.append("発送条件（SLS）の確認")
        evidence=workflow.product_review.current(item)
        if evidence is not None:
            if evidence.guardrail_status!="SAFE":
                missing.append("商品Safetyの未解決事項")
        image_blocker = workflow.product_review.preparation_blocker(item)
        if image_blocker:
            missing.append(image_blocker)
        attributes=workflow.current_attributes(item)
        assessments.append({"item":current,"asin":item.candidate_asin,"preparation_complete":not missing,
            "missing_steps":tuple(missing),"attributes_fetched":attributes is not None,
            "mandatory_attribute_count":sum(a["is_mandatory"] for a in attributes.attributes) if attributes is not None else None,
            "listing_ready":False,"formal_output_enabled":False})
    return tuple(assessments)
