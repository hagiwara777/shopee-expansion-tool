"""Streamlit adapter for the isolated SG Category Mapper Minimum Beta."""

from __future__ import annotations

import hashlib

import streamlit as st

from modules.category_mapper import parse_resolver_title_csv
from modules.category_mapper_sg import (
    SGCategoryMapperError,
    SGMapperRecommendation,
    build_sg_category_ai_catalog,
    build_sg_recommendations,
    confirm_sg_category,
    parse_sg_category_catalog,
    parse_sg_category_mapper_input,
    replace_sg_category_catalog,
)
from modules.category_mapper_store import CategoryMapperStore


_SG_RESULT_KEY = "sg_category_mapper_recommendations"
_SG_FINGERPRINT_KEY = "sg_category_mapper_input_fingerprint"
_SG_SOURCE_TYPE_KEY = "sg_category_mapper_source_type"
_SG_STATE_KEYS = (
    _SG_RESULT_KEY,
    _SG_FINGERPRINT_KEY,
    _SG_SOURCE_TYPE_KEY,
)


def render_sg_category_mapper() -> None:
    """Render SG mapping without Brand, SLS, ready exports, or automatic confirmation."""

    st.divider()
    st.subheader("SG Category Mapper Minimum Beta")
    st.caption(
        "SG Gate ELIGIBLE商品を商品単位の人間確認でCategoryだけ保存します。"
        "Category確定後も listing_ready=false のまま停止します。"
    )
    st.info(
        "SG AI Category候補のlive実行は未承認です。現在は検証済みSG catalogからの"
        "手動Category確認だけを利用できます。"
    )
    store = CategoryMapperStore()
    _render_catalog_import(store)

    source_file = st.file_uploader(
        "SG Prelisting Gate eligible CSV",
        type=["csv"],
        key="sg_category_mapper_source_csv",
    )
    resolver_file = st.file_uploader(
        "Resolver補助CSV（任意・SG）",
        type=["csv"],
        key="sg_category_mapper_resolver_csv",
    )
    source_content = source_file.getvalue() if source_file is not None else None
    resolver_content = resolver_file.getvalue() if resolver_file is not None else None
    fingerprint = _input_fingerprint(source_content, resolver_content, store)
    if st.session_state.get(_SG_FINGERPRINT_KEY) not in {None, fingerprint}:
        clear_sg_category_mapper_result(st.session_state)
        st.info("SG入力またはcatalogが変わったため、前回の表示結果を削除しました。")

    if source_file is not None and st.button(
        "SG Category確認を開始",
        type="primary",
        icon=":material/playlist_add_check:",
        key="sg_category_mapper_build",
    ):
        try:
            build_sg_category_ai_catalog(store)
            source = parse_sg_category_mapper_input(
                source_content or b"",
                filename=source_file.name,
            )
            resolver_titles = (
                {}
                if resolver_file is None
                else parse_resolver_title_csv(
                    resolver_content or b"",
                    filename=resolver_file.name,
                )
            )
            recommendations = build_sg_recommendations(
                source,
                resolver_titles=resolver_titles,
                store=store,
            )
        except SGCategoryMapperError as exc:
            clear_sg_category_mapper_result(st.session_state)
            st.error(str(exc))
        except Exception:
            clear_sg_category_mapper_result(st.session_state)
            st.error("SG Category確認を開始できませんでした。入力と現在catalogを確認してください。")
        else:
            st.session_state[_SG_RESULT_KEY] = recommendations
            st.session_state[_SG_FINGERPRINT_KEY] = fingerprint
            st.session_state[_SG_SOURCE_TYPE_KEY] = source.source_type

    recommendations = st.session_state.get(_SG_RESULT_KEY)
    if not recommendations or st.session_state.get(_SG_FINGERPRINT_KEY) != fingerprint:
        return
    recommendations = tuple(recommendations)
    _render_products(recommendations, store)


def clear_sg_category_mapper_result(state) -> None:
    for key in _SG_STATE_KEYS:
        state.pop(key, None)


def _render_catalog_import(store: CategoryMapperStore) -> None:
    status = store.catalog_status("SG")
    with st.container(border=True):
        first, second, third = st.columns(3)
        first.metric("SG Category件数", status["category_count"])
        second.metric("最終replace", status["last_synced_at"] or "未取込")
        third.metric("状態", status["api_status"] or "未取込")
        catalog_file = st.file_uploader(
            "出所確認済みSG Category catalog CSV",
            type=["csv"],
            key="sg_category_mapper_catalog_csv",
        )
        if catalog_file is not None and st.button(
            "検証してSG catalogを全件replace",
            icon=":material/database_upload:",
            key="sg_category_mapper_replace_catalog",
        ):
            try:
                catalog = parse_sg_category_catalog(
                    catalog_file.getvalue(),
                    filename=catalog_file.name,
                )
                count = replace_sg_category_catalog(store, catalog)
            except SGCategoryMapperError as exc:
                st.error(str(exc))
            except Exception:
                st.error("SG Category catalogを検証できないため、既存catalogを変更しませんでした。")
            else:
                clear_sg_category_mapper_result(st.session_state)
                st.success(f"検証済みSG Category catalog {count}件へ置換しました。")
                st.rerun()


def _render_products(
    recommendations: tuple[SGMapperRecommendation, ...],
    store: CategoryMapperStore,
) -> None:
    st.subheader("商品単位のCategory確認")
    confirmed_count = sum(item.category_is_confirmed for item in recommendations)
    st.caption(
        f"Category確認済み: {confirmed_count}/{len(recommendations)}件 / "
        "SG listing_ready: 0件 / export: 停止"
    )

    for index, recommendation in enumerate(recommendations):
        with st.expander(f"{recommendation.candidate_asin} / {recommendation.product_title}"):
            st.dataframe(
                [
                    {
                        "ASIN": recommendation.candidate_asin,
                        "商品名": recommendation.product_title,
                        "Keepa category": recommendation.keepa_category,
                        "Keepa brand": recommendation.keepa_brand,
                        "Resolver title": recommendation.resolver_input_title,
                    }
                ],
                hide_index=True,
            )
            if recommendation.category_is_confirmed:
                st.success("SG Category：人間確認済み")
                st.write(recommendation.recommended_category_path)
                st.caption(
                    f"ID {recommendation.recommended_category_id} / listing_ready=false / STOP"
                )
                continue
            _render_manual_selection(index, recommendation, store)


def _render_manual_selection(
    index: int,
    recommendation: SGMapperRecommendation,
    store: CategoryMapperStore,
) -> None:
    st.markdown("##### 検証済みSG catalogから手動選択")
    query = st.text_input(
        "Categoryを検索",
        key=f"sg_category_mapper_search_{index}",
        placeholder="Category名、Path、またはID",
    )
    results = (
        store.search_categories("SG", query=query, leaf_only=True, limit=100)
        if query.strip()
        else []
    )
    if results:
        st.dataframe(
            [
                {"Category ID": item["category_id"], "Category path": item["category_path"]}
                for item in results
            ],
            hide_index=True,
        )
    category_id = st.number_input(
        "確認するSG Category ID",
        min_value=0,
        value=0,
        step=1,
        key=f"sg_category_mapper_manual_category_{index}",
    )
    if st.button(
        "このCategoryを商品単位で確定",
        key=f"sg_category_mapper_confirm_manual_{index}",
    ):
        category = store.get_category("SG", int(category_id))
        if category is None or not bool(category.get("is_leaf")):
            st.error("現在の検証済みSG catalogにあるleaf Categoryを選択してください。")
            return
        try:
            updated = confirm_sg_category(
                recommendation,
                store=store,
                category_id=int(category["category_id"]),
                expected_category_path=str(category["category_path"]),
            )
        except SGCategoryMapperError as exc:
            st.error(str(exc))
        else:
            _replace_one(updated)
            st.rerun()


def _replace_one(updated: SGMapperRecommendation) -> None:
    current = tuple(st.session_state.get(_SG_RESULT_KEY) or ())
    st.session_state[_SG_RESULT_KEY] = tuple(
        updated if item.candidate_asin == updated.candidate_asin else item
        for item in current
    )


def _input_fingerprint(
    source_content: bytes | None,
    resolver_content: bytes | None,
    store: CategoryMapperStore,
) -> str | None:
    if source_content is None:
        return None
    status = store.catalog_status("SG")
    digest = hashlib.sha256()
    digest.update(source_content)
    digest.update(b"\0")
    digest.update(resolver_content or b"")
    digest.update(b"\0")
    digest.update(str(status["last_synced_at"]).encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(status["category_count"]).encode("ascii"))
    return digest.hexdigest()
