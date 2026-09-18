"""Pure PH-only SLS decisions. ALLOW never releases upstream Safety."""
from __future__ import annotations

from dataclasses import dataclass
from modules.sls_category_assets import SlsEvaluationContext, SlsSourceRef

CATEGORY_ALLOW = "CATEGORY_ALLOW"
CATEGORY_REVIEW = "CATEGORY_REVIEW"
CATEGORY_EXCLUDE = "CATEGORY_EXCLUDE"
EVALUATOR_VERSION = "PH_SLS_BETA_V1"


@dataclass(frozen=True)
class SlsCategoryResult:
    check_state: str = "UNCHECKED"
    action: str | None = None
    marketplace: str = ""
    category_id: int | None = None
    taxonomy_version: str = ""
    market_asset_version: str = ""
    evaluator_version: str = EVALUATOR_VERSION
    transform_version: str = ""
    reason_codes: tuple[str, ...] = ()
    source_refs: tuple[SlsSourceRef, ...] = ()


def evaluate_ph_category(*, marketplace: str, category_id: int | None,
                         category_confirmed: bool, context: SlsEvaluationContext) -> SlsCategoryResult:
    if marketplace != "PH" or context.marketplace != "PH":
        raise ValueError("SLS_RUNTIME_PH_ONLY")
    if not category_confirmed:
        return SlsCategoryResult(marketplace=marketplace, category_id=category_id)
    action, reason, refs = CATEGORY_REVIEW, "UNKNOWN_CATEGORY_ID", ()
    if type(category_id) is int and category_id in context.category_ids:
        rule = context.rules.get(category_id)
        reason = "MISSING_CATEGORY_RULE"
        if rule is not None:
            refs = rule.source_refs
            status, qty = rule.status.strip(), rule.quantity.strip()
            if status == "NO":
                action, reason = CATEGORY_EXCLUDE, "SLS_NOT_SHIPPABLE"
            elif status == "Shopeeと要確認":
                reason = "SHOPEE_CHECK_REQUIRED"
            elif status == "YES" and qty == "No limit":
                action, reason = CATEGORY_ALLOW, "NO_CATEGORY_STOP"
            elif status == "YES" and qty.isascii() and qty.isdigit():
                reason = "QUANTITY_LIMIT"
            else:
                reason = "UNRESOLVED_RULE"
            # NO remains dominant even if normalized metadata conflicts.
            if action != CATEGORY_EXCLUDE and (rule.action != action or rule.basis != reason):
                action, reason = CATEGORY_REVIEW, "UNRESOLVED_RULE"
    return SlsCategoryResult("EVALUATED", action, marketplace, category_id,
                             context.taxonomy_version, context.market_asset_version,
                             EVALUATOR_VERSION, context.transform_version, (reason,), refs)


def is_local_allow(result: SlsCategoryResult, *, marketplace: str, category_id: int | None,
                   category_confirmed: bool) -> bool:
    """Local binding only: no I/O and no claim about external asset freshness."""
    return (isinstance(result, SlsCategoryResult) and result.check_state == "EVALUATED"
            and result.action == CATEGORY_ALLOW and marketplace == result.marketplace == "PH"
            and category_confirmed and type(category_id) is int and category_id > 0
            and category_id == result.category_id and bool(result.taxonomy_version)
            and bool(result.market_asset_version) and bool(result.transform_version)
            and result.evaluator_version == EVALUATOR_VERSION)


def is_current_allow(result: SlsCategoryResult, *, marketplace: str, category_id: int | None,
                     category_confirmed: bool, context: SlsEvaluationContext) -> bool:
    return (is_local_allow(result, marketplace=marketplace, category_id=category_id,
                           category_confirmed=category_confirmed)
            and context.marketplace == marketplace
            and result.taxonomy_version == context.taxonomy_version
            and result.market_asset_version == context.market_asset_version
            and result.transform_version == context.transform_version)


_REASONS = {
    "NO_CATEGORY_STOP": "SLS Category条件による停止理由なし（商品全体のSafety保証ではありません）",
    "SLS_NOT_SHIPPABLE": "SLS Category上発送不可",
    "SHOPEE_CHECK_REQUIRED": "Shopee確認が必要",
    "QUANTITY_LIMIT": "数量制限あり（1注文の購入数を保証できないため確認が必要）",
    "UNKNOWN_CATEGORY_ID": "Category IDがSLS表にない、または不正",
    "MISSING_CATEGORY_RULE": "Category IDに対応するSLSルールがない",
    "UNRESOLVED_RULE": "SLS条件を自動判断できないため確認が必要",
}


def sls_reason_text(result: SlsCategoryResult) -> str:
    if result.check_state == "UNAVAILABLE":
        return "SLS Category dataを検証できないため出力停止"
    if result.check_state != "EVALUATED":
        return "Category確定後にSLS確認が必要"
    return " / ".join(_REASONS.get(code, "SLS条件の確認が必要") for code in result.reason_codes)
