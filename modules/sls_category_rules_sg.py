"""Pure SG-only SLS evaluation; ALLOW is a category candidate, never readiness."""
from __future__ import annotations

from dataclasses import dataclass
from modules.sls_category_assets import SgSlsEvaluationContext, SlsSourceRef

EVALUATOR_VERSION = "SG_SLS_MINIMUM_BETA_V1"


@dataclass(frozen=True)
class SgSlsCategoryResult:
    check_state: str = "UNCHECKED"
    action: str | None = None
    marketplace: str = "SG"
    category_id: int | None = None
    taxonomy_version: str = ""
    market_asset_version: str = ""
    evaluator_version: str = EVALUATOR_VERSION
    transform_version: str = ""
    catalog_version: str = ""
    reason_codes: tuple[str, ...] = ()
    source_refs: tuple[SlsSourceRef, ...] = ()


def _path_parts(path: str) -> tuple[str, ...]:
    # Cosmetic whitespace is accepted only after exact ID membership.
    return tuple(" ".join(part.split()) for part in path.split(">"))


def evaluate_sg_category(*, marketplace: str, category_id: int | None,
                         category_confirmed: bool, category_path: str,
                         current_category_path: str | None, current_is_leaf: bool,
                         catalog_version: str, context: SgSlsEvaluationContext) -> SgSlsCategoryResult:
    if marketplace != "SG" or context.marketplace != "SG":
        raise ValueError("SLS_RUNTIME_SG_ONLY")
    if not category_confirmed:
        return SgSlsCategoryResult(category_id=category_id)
    action, reason, refs = "CATEGORY_REVIEW", "UNKNOWN_CATEGORY_ID", ()
    valid_id = type(category_id) is int and category_id > 0
    if not valid_id or current_category_path is None or not current_is_leaf or not catalog_version:
        reason = "CURRENT_CATEGORY_INVALID"
    elif _path_parts(category_path) != _path_parts(current_category_path):
        reason = "CURRENT_CATEGORY_CHANGED"
    elif category_id not in context.names:
        reason = "UNKNOWN_CATEGORY_ID"
    elif _path_parts(current_category_path) != tuple(" ".join(x.split()) for x in context.names[category_id]):
        reason = "CATEGORY_IDENTITY_DRIFT"
    else:
        rule = context.rules.get(category_id)
        reason = "MISSING_CATEGORY_RULE"
        if rule is not None:
            refs = rule.source_refs
            status, qty = rule.status.strip(), rule.quantity.strip()
            if rule.group_notice:
                action, reason = "CATEGORY_EXCLUDE", "EXPLICIT_GROUP_NOTICE"
            elif status == "NO":
                action, reason = "CATEGORY_EXCLUDE", "SLS_NOT_SHIPPABLE"
            elif status == "Shopeeと要確認":
                reason = "SHOPEE_CHECK_REQUIRED"
            elif status == "YES" and qty == "No limit":
                action, reason = "CATEGORY_ALLOW", "NO_CATEGORY_STOP"
            elif status == "YES" and qty.isascii() and qty.isdigit():
                reason = "QUANTITY_LIMIT"
            elif status == "YES" and qty == "below 5kg":
                reason = "WEIGHT_LIMIT"
            else:
                reason = "UNRESOLVED_RULE"
    return SgSlsCategoryResult("EVALUATED", action, marketplace, category_id,
                               context.taxonomy_version, context.market_asset_version,
                               EVALUATOR_VERSION, context.transform_version, catalog_version, (reason,), refs)


_REASONS = {
    "NO_CATEGORY_STOP": "SLS Category条件による停止理由なし（ALLOW候補）",
    "SLS_NOT_SHIPPABLE": "SLS Category上発送不可",
    "EXPLICIT_GROUP_NOTICE": "SLS表の明示的なPet Food発送禁止notice",
    "SHOPEE_CHECK_REQUIRED": "Shopee確認が必要",
    "QUANTITY_LIMIT": "数量制限の確認が必要",
    "WEIGHT_LIMIT": "5kg未満の重量条件の確認が必要",
    "UNKNOWN_CATEGORY_ID": "Category IDがSLS表にない、または不正",
    "MISSING_CATEGORY_RULE": "Category IDのSG SLSルールがない",
    "CURRENT_CATEGORY_INVALID": "現在catalogのleaf Categoryを確認できない",
    "CURRENT_CATEGORY_CHANGED": "確認済みCategoryと現在catalogが一致しない",
    "CATEGORY_IDENTITY_DRIFT": "同一IDのCategory pathがSLS taxonomyと一致しない",
    "UNRESOLVED_RULE": "SLS条件を自動判断できないため確認が必要",
}


def sg_sls_reason_text(result: SgSlsCategoryResult) -> str:
    if result.check_state == "UNAVAILABLE":
        return "SG SLS資産または現在catalogを検証できません"
    if result.check_state == "UNCHECKED":
        return "Categoryを人間確認した後にSLS確認が必要"
    return " / ".join(_REASONS.get(code, "SG SLS確認が必要") for code in result.reason_codes)
