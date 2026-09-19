"""Streamlit UI adapter for the isolated Category Mapper workflow."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from typing import Any, Iterable, Mapping

import streamlit as st

from modules.category_mapper_sg_ui import render_sg_category_mapper
from modules.category_ai_core import CategoryAIEngine
from modules.category_ai_openai import OpenAIResponsesCategoryProvider
from modules.category_mapper import (
    CategoryMapperInputError,
    MapperRecommendation,
    apply_manual_brand,
    apply_manual_category,
    build_mapper_exports,
    build_recommendations,
    flatten_attribute_tree,
    group_recommendations,
    parse_category_mapper_input,
    parse_resolver_title_csv,
    summarize_output_blockers,
    refresh_sls_results,
)
from modules.category_mapper_ai import (
    AI_ABSTAIN,
    AI_CATALOG_MISMATCH,
    AI_FAILED,
    AI_SKIPPED_CONFIRMED,
    AI_SUGGESTED,
    AICategorySuggestionBatch,
    build_category_ai_catalog,
    generate_ai_category_suggestions,
    group_consensus_suggestion,
    load_luna_request_profile,
)
from modules.sls_category_assets import SlsAssetError, load_ph_context
from modules.sls_category_rules import SlsCategoryResult, is_current_allow, sls_reason_text
from modules.category_mapper_store import CategoryMapperStore
from modules.shopee_catalog_client import (
    ShopeeCatalogClient,
    ShopeeCatalogConfigurationError,
    ShopeeCatalogError,
    ShopeeRateLimitError,
)


_RESULT_KEY = "category_mapper_recommendations"
_FINGERPRINT_KEY = "category_mapper_input_fingerprint"
_SOURCE_TYPE_KEY = "category_mapper_source_type"
_AI_RESULT_KEY = "category_mapper_ai_suggestions"
_ACCESS_TOKEN_KEY = "category_mapper_temporary_access_token"
_STATE_KEYS = (_RESULT_KEY, _FINGERPRINT_KEY, _SOURCE_TYPE_KEY, _AI_RESULT_KEY)
CATALOG_ADMIN_UI_ENABLED_ENV = "CATEGORY_MAPPER_CATALOG_ADMIN_UI_ENABLED"


def render_category_mapper_tab() -> None:
    """Keep SLS failure local to Mapper; never retain successful output on error."""
    area = st.empty()
    try:
        with area.container():
            load_ph_context()  # Validate before creating/opening DB or new Brand actions.
            _render_category_mapper_body()
    except SlsAssetError:
        previous = tuple(st.session_state.get(_RESULT_KEY) or ())
        st.session_state[_RESULT_KEY] = tuple(
            replace(item, sls_result=SlsCategoryResult(check_state="UNAVAILABLE"))
            for item in previous
        )
        area.empty()
        with area.container():
            st.error("SLS Category dataを検証できないため出力停止")
            st.metric("出品グループ対象", 0)
    render_sg_category_mapper()


def _render_category_mapper_body() -> None:
    """Render PH-only mapping without executing catalog calls unless requested."""

    st.subheader("Category Mapper Ver0.1")
    st.caption(
        "Category / Brand を推測だけで確定せず、確認済みプロファイルとユーザー確認を優先します。"
    )
    marketplace = st.selectbox("Marketplace", ("PH",), disabled=True, key="category_mapper_marketplace")
    st.caption("SG / MY / TH は未検証・未対応のため、この画面から内部APIへ渡しません。")
    st.text_input(
        "Shopee ACCESS_TOKEN（一時利用）",
        type="password",
        key=_ACCESS_TOKEN_KEY,
        help="このブラウザの利用中だけ使用します。空欄の場合は既存の認証設定を使用します。",
    )
    store = CategoryMapperStore()
    if os.environ.get(CATALOG_ADMIN_UI_ENABLED_ENV) == "1":
        _render_catalog_status(store, marketplace)

    source_file = st.file_uploader(
        "Expansion候補CSV または Prelisting Gate eligible CSV",
        type=["csv"],
        key="category_mapper_source_csv",
    )
    resolver_file = st.file_uploader(
        "Resolver補助CSV（任意）",
        type=["csv"],
        key="category_mapper_resolver_csv",
    )
    source_content = source_file.getvalue() if source_file is not None else None
    resolver_content = resolver_file.getvalue() if resolver_file is not None else None
    fingerprint = _input_fingerprint(source_content, resolver_content)
    if st.session_state.get(_FINGERPRINT_KEY) not in {None, fingerprint}:
        clear_category_mapper_result(st.session_state)
        st.info("入力が変わったため、前回の推薦結果を削除しました。")

    if source_file is not None and st.button(
        "推薦を作成",
        type="primary",
        icon=":material/playlist_add_check:",
        key="category_mapper_build",
    ):
        st.session_state.pop(_AI_RESULT_KEY, None)
        try:
            source = parse_category_mapper_input(source_content or b"", filename=source_file.name)
            resolver_titles = (
                {}
                if resolver_file is None
                else parse_resolver_title_csv(resolver_content or b"", filename=resolver_file.name)
            )
            recommendations = build_recommendations(
                source,
                resolver_titles=resolver_titles,
                store=store,
            )
        except SlsAssetError:
            raise
        except CategoryMapperInputError:
            clear_category_mapper_result(st.session_state)
            st.error(
                "CSVを検証できませんでした。Expansion候補CSVまたはPH Gate eligible CSVの"
                "固定ヘッダー、ASIN、対象市場を確認してください。"
            )
        except Exception:
            clear_category_mapper_result(st.session_state)
            st.error("推薦を作成できませんでした。入力内容を確認してから再実行してください。")
        else:
            st.session_state[_RESULT_KEY] = recommendations
            st.session_state[_FINGERPRINT_KEY] = fingerprint
            st.session_state[_SOURCE_TYPE_KEY] = source.source_type.casefold()

    recommendations = st.session_state.get(_RESULT_KEY)
    if not recommendations or st.session_state.get(_FINGERPRINT_KEY) != fingerprint:
        return
    recommendations = refresh_sls_results(recommendations, context=load_ph_context())
    st.session_state[_RESULT_KEY] = recommendations
    _render_ai_suggestion_action(tuple(recommendations), store)
    _render_recommendations(
        tuple(recommendations),
        store=store,
        source_type=str(st.session_state.get(_SOURCE_TYPE_KEY) or "expansion"),
    )


def clear_category_mapper_result(state: Mapping[str, object] | dict[str, object]) -> None:
    """Clear only stale Mapper session state."""

    for key in _STATE_KEYS:
        state.pop(key, None)  # type: ignore[attr-defined]


def _catalog_client() -> ShopeeCatalogClient:
    temporary_token = str(st.session_state.get(_ACCESS_TOKEN_KEY) or "").strip()
    if temporary_token:
        return ShopeeCatalogClient.from_local_audit_env(access_token_override=temporary_token)
    return ShopeeCatalogClient.from_local_audit_env()


def _category_ai_engine() -> CategoryAIEngine:
    """Create the paid provider only after the explicit AI action is clicked."""

    provider = OpenAIResponsesCategoryProvider.from_environment()
    return CategoryAIEngine(provider)


def _render_ai_suggestion_action(
    recommendations: tuple[MapperRecommendation, ...], store: CategoryMapperStore
) -> None:
    st.subheader("AI Category候補")
    st.caption(
        "gpt-5.6-lunaは候補提示だけを行います。候補だけではCategoryを確定せず、"
        "出品準備完了にもなりません。"
    )
    eligible_count = sum(not item.category_is_confirmed for item in recommendations)
    if st.button(
        "AI Category候補を作成（Luna）",
        icon=":material/psychology:",
        key="category_mapper_build_ai_suggestions",
        disabled=eligible_count == 0,
    ):
        st.session_state.pop(_AI_RESULT_KEY, None)
        try:
            catalog = build_category_ai_catalog(store)
            profile = load_luna_request_profile()
            engine = _category_ai_engine()
            batch = generate_ai_category_suggestions(
                recommendations,
                store=store,
                engine=engine,
                catalog=catalog,
                profile=profile,
            )
        except Exception:
            st.error(
                "AI Category候補を作成できませんでした。OpenAI設定とPH Category Treeを"
                "確認してください。既存の手動Category経路はそのまま利用できます。"
            )
        else:
            st.session_state[_AI_RESULT_KEY] = batch

    batch = st.session_state.get(_AI_RESULT_KEY)
    if not isinstance(batch, AICategorySuggestionBatch):
        return
    first, second, third = st.columns(3)
    first.metric("成功", batch.success_count)
    second.metric("失敗", batch.failure_count)
    third.metric("スキップ", batch.skip_count)
    st.dataframe(
        [
            {
                "ASIN": item.candidate_asin,
                "AI状態": _ai_status_label(item.status),
                "Category ID": item.predicted_category_id or "",
                "Category候補": item.predicted_category_path,
                "confidence": "" if item.confidence is None else f"{item.confidence:.3f}",
                "理由": item.short_reason,
                "error": item.error_code,
            }
            for item in batch.suggestions
        ],
        hide_index=True,
    )


def _render_catalog_status(store: CategoryMapperStore, marketplace: str) -> None:
    status = store.catalog_status(marketplace)
    with st.container(border=True):
        st.caption("PH catalog sync status")
        first, second, third, fourth = st.columns(4)
        first.metric("Category最終同期", status["last_synced_at"] or "未同期")
        second.metric("Category件数", status["category_count"])
        third.metric("キャッシュ", "使用中" if status["using_cache"] else "なし")
        fourth.metric("API状態", status["api_status"] or "未実行")
        st.caption("API更新に失敗した場合も、既存キャッシュがあればそのまま利用します。")
        if st.button(
            "PH Category Treeを同期",
            icon=":material/sync:",
            key="category_mapper_sync_categories",
        ):
            try:
                client = _catalog_client()
                categories = client.get_categories(marketplace)
                store.save_categories(marketplace, categories)
            except ShopeeCatalogConfigurationError:
                st.warning("Shopee catalog認証情報が利用できないため、ローカルキャッシュを使用します。")
            except ShopeeRateLimitError:
                store.record_category_sync_failure(marketplace)
                st.error("Shopee catalog APIのレート制限を検知したため、同期を停止しました。")
            except ShopeeCatalogError:
                store.record_category_sync_failure(marketplace)
                st.warning("Category同期に失敗したため、前回キャッシュを使用します。")
            else:
                st.success("PH Category Treeを同期しました。")
                st.rerun()


def _render_recommendations(
    recommendations: tuple[MapperRecommendation, ...],
    *,
    store: CategoryMapperStore,
    source_type: str,
) -> None:
    exports = build_mapper_exports(recommendations)
    recommendations = exports.evaluated_recommendations
    st.session_state[_RESULT_KEY] = recommendations
    summaries = group_recommendations(recommendations)
    st.subheader("商品グループ一覧")
    st.dataframe(
        [
            {
                "ASIN数": summary["asin_count"],
                "Keepa category": summary["keepa_category"],
                "Keepa brand": summary["keepa_brand"],
                "Category": _category_status_label(str(summary["category_status"])),
                "Brand": _brand_status_label(str(summary["brand_status"])),
                "状態": _readiness_label(int(summary["asin_count"]), int(summary["listing_ready_count"])),
            }
            for summary in summaries
        ],
        hide_index=True,
    )
    for index, summary in enumerate(summaries):
        member_asins = tuple(summary["member_asins"])
        members = tuple(item for item in recommendations if item.candidate_asin in member_asins)
        _render_group_controls(index, members, store)

    current = tuple(st.session_state.get(_RESULT_KEY) or recommendations)
    exports = build_mapper_exports(current)
    current = exports.evaluated_recommendations
    st.session_state[_RESULT_KEY] = current
    blockers = summarize_output_blockers(current)
    st.subheader("SLS Category確認")
    st.dataframe([{"ASIN": item.candidate_asin,
                   "Shopee Category ID": item.recommended_category_id,
                   "SLS Category action": item.sls_result.action or item.sls_result.check_state,
                   "理由": sls_reason_text(item.sls_result)} for item in current], hide_index=True)
    ready = blockers["ready"]
    st.subheader("出力")
    st.download_button(
        "詳細推薦CSVをダウンロード",
        data=exports.recommendations_csv,
        file_name=f"category_mapper_recommendations_ph_{source_type}.csv",
        mime="text/csv",
        icon=":material/download:",
        key="category_mapper_download_recommendations",
    )
    if not ready:
        st.info("出力対象がありません。これは安全条件による正常状態です。")
        st.dataframe(
            [
                {"阻害条件": "Category未確定", "件数": len(blockers["category_unconfirmed"])},
                {"阻害条件": "Brand未確定", "件数": len(blockers["brand_unconfirmed"])},
                {"阻害条件": "手動確認必要", "件数": len(blockers["manual_review_required"])},
                {"阻害条件": "出品グループ対象", "件数": 0},
            ],
            hide_index=True,
        )
        blocker_rows = []
        for label, items in (
            ("Category未確定", blockers["category_unconfirmed"]),
            ("Brand未確定", blockers["brand_unconfirmed"]),
            ("手動確認必要", blockers["manual_review_required"]),
        ):
            blocker_rows.extend(
                {
                    "阻害条件": label,
                    "ASIN": item.candidate_asin,
                    "Keepa category": item.keepa_category,
                    "Keepa brand": item.keepa_brand,
                    "理由": item.manual_review_reason,
                }
                for item in items
            )
        with st.expander("阻害条件の対象行を確認"):
            st.dataframe(blocker_rows, hide_index=True)
        return
    group_count = len({item.group_key for item in ready})
    st.success(f"出品グループ対象: {len(ready)} ASIN / {group_count} グループ")
    st.download_button(
        "出品グループCSVをダウンロード",
        data=exports.groups_csv,
        file_name=f"category_mapper_groups_ph_{source_type}.csv",
        mime="text/csv",
        icon=":material/download:",
        key="category_mapper_download_groups",
    )
    st.download_button(
        "出品ツール貼付用TXTをダウンロード",
        data=exports.listing_tool_text.encode("utf-8"),
        file_name=f"category_mapper_groups_ph_{source_type}.txt",
        mime="text/plain",
        icon=":material/content_copy:",
        key="category_mapper_download_txt",
    )


def _render_group_controls(
    index: int,
    members: tuple[MapperRecommendation, ...],
    store: CategoryMapperStore,
) -> None:
    first = members[0]
    title = (
        f"{first.keepa_category or 'カテゴリ未設定'} / "
        f"{first.keepa_brand or 'Brand未設定'}（{len(members)}件）"
    )
    with st.expander(title):
        st.caption(_group_progress_label(first, len(members)))
        _render_category_controls(index, members, store)
        current = tuple(st.session_state.get(_RESULT_KEY) or members)
        refreshed = next(
            (item for item in current if item.candidate_asin == first.candidate_asin), first
        )
        if refreshed.category_is_confirmed:
            _render_brand_controls(index, members, store, refreshed)
        else:
            st.info("Brand確認はCategoryを採用した後に表示します。", icon=":material/info:")
        _render_group_details(index, refreshed, store)


def _render_category_controls(
    index: int,
    members: tuple[MapperRecommendation, ...],
    store: CategoryMapperStore,
) -> None:
    first = members[0]
    st.markdown("##### 1. Category")
    if first.category_is_confirmed and first.recommended_category_id:
        st.success("Category：確認済み", icon=":material/check_circle:")
        st.write(first.recommended_category_path)
        st.caption(f"ID {first.recommended_category_id}")
        _render_attribute_summary(first, store)
        return

    batch = st.session_state.get(_AI_RESULT_KEY)
    if isinstance(batch, AICategorySuggestionBatch):
        _render_ai_group_suggestion(index, members, store, batch)

    if first.category_recommendation_status == "SUGGESTED" and first.recommended_category_id:
        candidate = store.get_category("PH", first.recommended_category_id)
        if candidate is not None:
            st.info("推奨候補", icon=":material/lightbulb:")
            st.write(candidate["category_path"])
            st.caption(
                f"ID {candidate['category_id']} / 必須属性: {_mandatory_count_label(first.mandatory_attribute_count)}"
            )
            _render_attribute_summary(first, store)
            with st.container(horizontal=True):
                if st.button(
                    "このCategoryを採用",
                    type="primary",
                    icon=":material/check_circle:",
                    key=f"category_mapper_apply_suggested_category_{index}",
                ):
                    if _apply_category_choice(first, members, store, int(candidate["category_id"])):
                        st.rerun()
                if st.button(
                    "別のCategoryを探す",
                    icon=":material/search:",
                    key=f"category_mapper_show_category_search_{index}",
                ):
                    st.session_state[f"category_mapper_category_search_open_{index}"] = True

    search_open = bool(st.session_state.get(f"category_mapper_category_search_open_{index}"))
    if (
        first.category_recommendation_status != "SUGGESTED"
        or not first.recommended_category_id
        or search_open
    ):
        if not first.recommended_category_id:
            st.warning("Categoryを選んでください。", icon=":material/warning:")
        _render_category_search(index, members, store)


def _render_category_search(
    index: int,
    members: tuple[MapperRecommendation, ...],
    store: CategoryMapperStore,
) -> None:
    first = members[0]
    query = st.text_input(
        "Categoryを検索",
        key=f"category_mapper_category_search_{index}",
        placeholder="Category名、Path、またはID",
    )
    leaf_only = st.checkbox("leafのみ", value=True, key=f"category_mapper_leaf_only_{index}")
    others_only = st.checkbox("Othersのみ", key=f"category_mapper_others_only_{index}")
    search_results = (
        store.search_categories("PH", query=query, leaf_only=leaf_only, others_only=others_only)
        if query.strip()
        else []
    )
    if search_results:
        st.dataframe(
            [
                {
                    "Category ID": item["category_id"],
                    "Path": item["category_path"],
                    "leaf": bool(item["is_leaf"]),
                    "Others": bool(item["is_others"]),
                    "verification": (
                        "LISTING_TOOL_ACCEPTED"
                        if item["api_version"] == "INITIAL_PROFILE"
                        else "API_CATEGORY_PRESENT"
                    ),
                }
                for item in search_results
            ],
            hide_index=True,
        )
    category_value = st.number_input(
        "確認するCategory ID",
        min_value=0,
        value=int(first.recommended_category_id or 0),
        step=1,
        key=f"category_mapper_manual_category_{index}",
    )
    if st.button(
        "このCategoryを採用",
        icon=":material/fact_check:",
        key=f"category_mapper_apply_category_{index}",
    ):
        if _apply_category_choice(first, members, store, int(category_value)):
            st.rerun()


def _apply_category_choice(
    first: MapperRecommendation,
    members: tuple[MapperRecommendation, ...],
    store: CategoryMapperStore,
    category_id: int,
) -> bool:
    category = store.get_category("PH", category_id)
    if category is None:
        st.error("Category IDを確認できません。同期または検索後に、表示されたCategory IDを選択してください。")
        return False
    mandatory_count = store.mandatory_attribute_count("PH", int(category["category_id"]))
    no_brand_available = store.no_brand_available("PH", int(category["category_id"]))
    updated = apply_manual_category(
        first,
        category=category,
        mandatory_attribute_count=mandatory_count,
        no_brand_available=no_brand_available,
    )
    _replace_group(members, updated)
    if first.keepa_category:
        store.save_category_mapping(
            marketplace="PH",
            mapping_key_type="KEEPA_CATEGORY",
            mapping_key=first.keepa_category,
            canonical_product_type=first.canonical_product_type,
            category_id=int(category["category_id"]),
            category_path=str(category["category_path"]),
        )
        st.caption(f"次回以降、PHの「{first.keepa_category}」商品へ再利用します。")
    _discard_ai_suggestions(members)
    return True


def _render_ai_group_suggestion(
    index: int,
    members: tuple[MapperRecommendation, ...],
    store: CategoryMapperStore,
    batch: AICategorySuggestionBatch,
) -> None:
    by_asin = batch.by_asin()
    group_suggestions = tuple(
        by_asin[item.candidate_asin]
        for item in members
        if item.candidate_asin in by_asin
    )
    if not group_suggestions:
        return
    st.markdown("###### AI候補（未確定）")
    if any(item.requires_hobbies_warning for item in group_suggestions):
        st.warning(
            "Benchmark弱点カテゴリのため特に手動確認が必要です：Hobbies & Collections"
        )
    consensus = group_consensus_suggestion(
        tuple(item.candidate_asin for item in members),
        group_suggestions,
    )
    if consensus is None:
        st.info(
            "全memberが同じ有効leaf Categoryへ一致していないため、AI候補をGroup採用できません。"
            "既存の手動Category経路を使用してください。"
        )
        return
    category = store.get_category("PH", consensus.predicted_category_id)
    if (
        category is None
        or not bool(category.get("is_leaf"))
        or str(category.get("category_path") or "") != consensus.predicted_category_path
    ):
        st.warning("AI候補が現在のPH catalogと一致しないため採用できません。")
        return
    st.write(consensus.predicted_category_path)
    st.caption(
        f"ID {consensus.predicted_category_id} / confidence "
        f"{consensus.confidence if consensus.confidence is not None else '未取得'}"
    )
    if st.button(
        "AI候補のCategoryを採用",
        type="primary",
        icon=":material/fact_check:",
        key=f"category_mapper_apply_ai_category_{index}",
    ):
        if _apply_category_choice(
            members[0], members, store, int(consensus.predicted_category_id)
        ):
            st.rerun()


def _render_attribute_summary(
    recommendation: MapperRecommendation, store: CategoryMapperStore
) -> None:
    if recommendation.recommended_category_id is None:
        return
    attributes = store.list_attributes("PH", recommendation.recommended_category_id)
    mandatory = [item for item in attributes if bool(item["is_mandatory"])]
    count = (
        len(mandatory)
        if attributes
        else recommendation.mandatory_attribute_count
        if recommendation.mandatory_attribute_count is not None
        else None
    )
    if count == 0:
        st.caption("追加必須項目はありません。")
    elif mandatory:
        st.caption("必須属性: " + "、".join(str(item["attribute_name"]) for item in mandatory))
    elif count is not None:
        st.caption(f"必須属性: {count}件")
    else:
        st.caption("必須属性は未取得です。必要な場合は詳細情報から取得できます。")


def _render_attribute_controls(
    index: int, recommendation: MapperRecommendation, store: CategoryMapperStore
) -> None:
    if recommendation.recommended_category_id is None:
        return
    st.markdown("##### 詳細属性")
    category_id = recommendation.recommended_category_id
    attributes = store.list_attributes("PH", category_id)
    if attributes:
        st.dataframe(
            [
                {
                    "attribute_id": item["attribute_id"],
                    "attribute_name": item["attribute_name"],
                    "mandatory": bool(item["is_mandatory"]),
                    "input_type": item["input_type"],
                    "validation_type": item["validation_type"],
                    "value_count": item["value_count"],
                    "unit_count": item["unit_count"],
                    "multi_select_max": item["multi_select_max"],
                    "synced_at": item["synced_at"],
                }
                for item in attributes
            ],
            hide_index=True,
        )
    if store.has_attribute_cache("PH", category_id):
        st.caption("Category attributesはローカルキャッシュで確認済みです。")
    elif st.button(
        "Category attributesを取得",
        icon=":material/account_tree:",
        key=f"category_mapper_fetch_attributes_{index}",
    ):
        try:
            _fetch_attributes(category_id, store)
        except ShopeeCatalogConfigurationError:
            st.warning("Shopee catalog認証情報が利用できないため、属性を取得できません。")
        except ShopeeRateLimitError:
            st.error("Shopee catalog APIのレート制限を検知したため、属性取得を停止しました。")
        except ShopeeCatalogError:
            st.warning("属性取得に失敗しました。既存キャッシュを確認してください。")
        else:
            st.success("属性を更新しました。")
            st.rerun()


def _fetch_attributes(category_id: int, store: CategoryMapperStore) -> None:
    client = _catalog_client()
    tree = client.get_attribute_tree("PH", category_id)
    flattened = flatten_attribute_tree(tree)
    store.save_attributes("PH", category_id, flattened.attributes)


def _render_brand_controls(
    index: int,
    members: tuple[MapperRecommendation, ...],
    store: CategoryMapperStore,
    recommendation: MapperRecommendation,
) -> None:
    context = load_ph_context()
    recommendation = refresh_sls_results((recommendation,), context=context)[0]
    if not is_current_allow(recommendation.sls_result, marketplace=recommendation.marketplace,
                            category_id=recommendation.recommended_category_id,
                            category_confirmed=recommendation.category_is_confirmed, context=context):
        st.warning(sls_reason_text(recommendation.sls_result))
        return
    if recommendation.recommended_category_id is None:
        st.info("Brand候補はCategoryを採用した後に表示します。")
        return
    st.markdown("##### 2. Brand")
    category_id = recommendation.recommended_category_id
    if recommendation.no_brand_selected_by_user or recommendation.brand_is_confirmed:
        st.success("Brand：確認済み", icon=":material/check_circle:")
        if recommendation.recommended_brand_id == 0:
            st.write("No brand（ID 0）")
        else:
            st.write(f"{recommendation.recommended_brand_name}（ID {recommendation.recommended_brand_id}）")
        return
    st.caption(f"Keepa brand: {recommendation.keepa_brand or '未設定'}")
    if recommendation.resolver_input_title:
        st.caption(f"Resolver英語候補: {recommendation.resolver_input_title}")
    if store.has_brand_cache("PH", category_id):
        st.caption("Brand候補は確認済みです。")
    elif st.button(
        "このCategoryのBrand候補を取得",
        icon=":material/brand_awareness:",
        key=f"category_mapper_fetch_brands_{index}",
    ):
        try:
            client = _catalog_client()
            page = client.get_brand_list(
                "PH",
                category_id,
                offset=0,
                page_size=100,
            )
            store.save_brand_page(
                "PH",
                category_id,
                page.brands,
                next_offset=page.next_offset,
                is_complete=page.is_complete,
            )
        except ShopeeCatalogConfigurationError:
            st.warning("Shopee catalog認証情報が利用できないため、Brand候補を取得できません。")
        except ShopeeRateLimitError:
            st.error("Shopee catalog APIのレート制限を検知したため、Brand取得を停止しました。")
        except ShopeeCatalogError:
            store.record_brand_sync_failure("PH", category_id)
            st.warning("Brand取得に失敗しました。Brand未確定のまま停止します。")
        else:
            st.success("Brand候補の先頭ページを更新しました。")
            st.rerun()
    brands = store.list_brands("PH", category_id)
    if not brands:
        st.caption("Brand Listは未取得です。Brand IDを推測せず、先に候補を取得してください。")
        return
    no_brand = next((brand for brand in brands if bool(brand["is_no_brand"])), None)
    if no_brand is not None:
        st.write("No brand：利用可能")
        if st.button(
            "No brandで確定",
            type="primary",
            icon=":material/check_circle:",
            key=f"category_mapper_apply_no_brand_{index}",
        ):
            updated = apply_manual_brand(recommendation, brand=no_brand)
            _replace_group(members, updated)
            store.save_brand_policy(
                marketplace="PH",
                keepa_category=recommendation.keepa_category,
                keepa_brand=recommendation.keepa_brand,
                category_id=category_id,
                brand_policy="NO_BRAND_SELECTED",
                brand_id=0,
            )
            st.rerun()
    with st.container(horizontal=True):
        if st.button(
            "別のBrandを探す",
            icon=":material/search:",
            key=f"category_mapper_show_brand_search_{index}",
        ):
            st.session_state[f"category_mapper_brand_search_open_{index}"] = True
        st.button("保留", icon=":material/pending:", key=f"category_mapper_hold_brand_{index}")
    if not st.session_state.get(f"category_mapper_brand_search_open_{index}"):
        return
    query = st.text_input(
        "Brand候補を検索",
        key=f"category_mapper_brand_search_{index}",
        placeholder="Brand名またはBrand ID",
    )
    filtered_brands = [
        brand
        for brand in brands
        if not query.strip()
        or query.casefold() in str(brand["brand_name"]).casefold()
        or query.strip() in str(brand["brand_id"])
    ]
    if not filtered_brands:
        st.info("一致するBrand候補はありません。未確定のまま保留できます。")
        return
    real_filtered = [brand for brand in filtered_brands if not bool(brand["is_no_brand"])]
    if not real_filtered:
        st.info("一致する実Brand候補はありません。No brandで確定するか、保留してください。")
        return
    options = [f"{brand['brand_id']} | {brand['brand_name']}" for brand in real_filtered]
    selected = st.selectbox(
        "確認するShopee Brand",
        options,
        key=f"category_mapper_manual_brand_{index}",
    )
    selected_brand = real_filtered[options.index(selected)]
    if st.button(
        "このBrandを採用",
        icon=":material/fact_check:",
        key=f"category_mapper_apply_brand_{index}",
    ):
        updated = apply_manual_brand(recommendation, brand=selected_brand)
        _replace_group(members, updated)
        if recommendation.keepa_brand:
            store.save_brand_alias(
                source_brand=recommendation.keepa_brand,
                canonical_brand=recommendation.keepa_brand,
                marketplace="PH",
                category_id=category_id,
                shopee_brand_name=str(selected_brand["brand_name"]),
                brand_id=int(selected_brand["brand_id"]),
            )
        st.rerun()


def _render_group_details(
    index: int, recommendation: MapperRecommendation, store: CategoryMapperStore
) -> None:
    with st.expander("詳細情報を表示", icon=":material/visibility:"):
        st.dataframe(
            [
                {
                    "項目": "Category source",
                    "値": recommendation.category_recommendation_source,
                },
                {"項目": "Category confidence", "値": recommendation.category_confidence},
                {
                    "項目": "Category verification",
                    "値": recommendation.category_verification_status,
                },
                {"項目": "Brand source", "値": recommendation.brand_recommendation_source},
                {"項目": "Brand confidence", "値": recommendation.brand_confidence},
                {"項目": "確認理由", "値": recommendation.manual_review_reason},
            ],
            hide_index=True,
        )
        _render_attribute_controls(index, recommendation, store)
        if recommendation.recommended_category_id is not None:
            state = store.brand_sync_state("PH", recommendation.recommended_category_id)
            st.caption(
                "Brand List: "
                f"next_offset={state['next_offset']} / "
                f"is_complete={state['is_complete']} / "
                f"api_status={state['api_status'] or '未実行'}"
            )


def _replace_group(
    members: Iterable[MapperRecommendation], updated: MapperRecommendation
) -> None:
    member_asins = {member.candidate_asin for member in members}
    previous = tuple(st.session_state.get(_RESULT_KEY) or ())
    replacements = []
    for item in previous:
        if item.candidate_asin in member_asins:
            replacements.append(
                replace_from_group(item, updated)
                if item.candidate_asin != updated.candidate_asin
                else updated
            )
        else:
            replacements.append(item)
    st.session_state[_RESULT_KEY] = refresh_sls_results(replacements, context=load_ph_context())


def _discard_ai_suggestions(members: Iterable[MapperRecommendation]) -> None:
    batch = st.session_state.get(_AI_RESULT_KEY)
    if not isinstance(batch, AICategorySuggestionBatch):
        return
    remaining = batch.without_asins({item.candidate_asin for item in members})
    if remaining.suggestions:
        st.session_state[_AI_RESULT_KEY] = remaining
    else:
        st.session_state.pop(_AI_RESULT_KEY, None)


def replace_from_group(
    item: MapperRecommendation, updated: MapperRecommendation
) -> MapperRecommendation:
    """Reuse a confirmed group choice while preserving each source row's audit evidence."""

    fields = (
        'category_recommendation_status',
        'recommended_category_id',
        'recommended_category_path',
        'category_confidence',
        'category_recommendation_source',
        'category_verification_status',
        'mandatory_attribute_count',
        'no_brand_available',
        'canonical_brand_candidate',
        'brand_match_status',
        'recommended_brand_id',
        'recommended_brand_name',
        'brand_confidence',
        'brand_recommendation_source',
        'brand_accuracy_warning',
        'category_is_confirmed',
        'brand_is_confirmed',
        'no_brand_selected_by_user',
        'manual_review_required',
        'manual_review_reason',
    )
    updated_item = replace(item, **{key: getattr(updated, key) for key in fields},
                           sls_result=SlsCategoryResult())
    return updated_item  # The group boundary evaluates each member with one context.


def _input_fingerprint(source_content: bytes | None, resolver_content: bytes | None) -> str | None:
    if source_content is None:
        return None
    digest = hashlib.sha256()
    digest.update(source_content)
    digest.update(b"\x00")
    digest.update(resolver_content or b"")
    return digest.hexdigest()


def _category_status_label(status: str) -> str:
    return {
        "SUGGESTED": "推奨候補",
        "CONFIRMED": "確認済み",
        "UNMAPPED": "Category未選択",
        "MIXED": "確認状態が混在",
    }.get(status, status or "未確認")


def _ai_status_label(status: str) -> str:
    return {
        AI_SUGGESTED: "候補あり",
        AI_ABSTAIN: "ABSTAIN（採用不可）",
        AI_FAILED: "FAILED（採用不可）",
        AI_CATALOG_MISMATCH: "catalog不整合（採用不可）",
        AI_SKIPPED_CONFIRMED: "確認済みCategoryのためスキップ",
    }.get(status, status)


def _brand_status_label(status: str) -> str:
    return {
        "NO_BRAND_AVAILABLE": "No brandを選択可能",
        "NO_BRAND_SELECTED": "No brand確認済み",
        "CONFIRMED_ALIAS_MATCH": "実Brand確認済み",
        "EXACT_MATCH": "実Brand候補あり",
        "NORMALIZED_MATCH": "実Brand候補あり",
        "NOT_FOUND": "Brand未確認",
        "MANUAL_REVIEW": "実Brand確認済み",
        "MIXED": "確認状態が混在",
        "MULTIPLE_MATCHES": "Brand候補を選択してください",
    }.get(status, status or "未確認")


def _readiness_label(asin_count: int, ready_count: int) -> str:
    if ready_count == asin_count and asin_count > 0:
        return "出品準備完了"
    return f"一部完了: {ready_count}/{asin_count}" if ready_count else "未完了"


def _group_progress_label(recommendation: MapperRecommendation, asin_count: int) -> str:
    if recommendation.listing_ready:
        return f"出品準備完了: {asin_count}件"
    if recommendation.sls_result.action in {"CATEGORY_REVIEW", "CATEGORY_EXCLUDE"} or (
        recommendation.sls_result.check_state == "UNAVAILABLE"
    ):
        return f"SLS Category確認で停止: {asin_count}件"
    missing = int(not recommendation.category_is_confirmed) + int(
        not recommendation.brand_is_confirmed and not recommendation.no_brand_selected_by_user
    )
    return f"状態: あと{missing}項目" if missing else "状態: 出力条件未完了"


def _mandatory_count_label(count: int | None) -> str:
    if count is None:
        return "未確認"
    return "0件" if count == 0 else f"{count}件"
