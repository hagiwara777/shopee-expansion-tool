"""Shared display of Category predictions; never changes confirmation state."""

import streamlit as st

from modules.category_mapper_ai import AICategorySuggestionBatch


def suggestion_status_label(status: str) -> str:
    return {
        "SUGGESTED": "候補あり", "ABSTAIN": "ABSTAIN（採用不可）",
        "FAILED": "FAILED（採用不可）", "CATALOG_MISMATCH": "catalog不整合（採用不可）",
        "SKIPPED_CONFIRMED": "確認済みCategoryのためスキップ",
    }.get(status, status)


def render_category_suggestion_batch(batch: AICategorySuggestionBatch) -> None:
    first, second, third = st.columns(3)
    first.metric("成功", batch.success_count)
    second.metric("失敗", batch.failure_count)
    third.metric("スキップ", batch.skip_count)
    st.dataframe([
        {"ASIN": item.candidate_asin, "AI状態": suggestion_status_label(item.status),
         "Category ID": item.predicted_category_id or "", "Category候補": item.predicted_category_path,
         "confidence": "" if item.confidence is None else f"{item.confidence:.3f}",
         "理由": item.short_reason, "error": item.error_code}
        for item in batch.suggestions
    ], hide_index=True)
