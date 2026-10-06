"""Streamlit adapter for the isolated SG Category Mapper Minimum Beta."""

from __future__ import annotations

import hashlib

import streamlit as st

from modules.brand_confirmation import brand_option_label, search_brand_options
from modules.category_suggestion_ui import render_category_suggestion_batch
from modules.category_mapper_ai import AICategorySuggestionBatch, CategoryPredictionEngine, load_luna_request_profile
from modules.category_mapper import parse_resolver_title_csv
from modules.category_mapper_sg import (
    SGCategoryMapperError,
    SGMapperRecommendation,
    SGBrandSession,
    build_sg_category_ai_catalog,
    build_sg_recommendations,
    generate_sg_ai_category_suggestions,
    confirm_sg_category,
    confirm_sg_brand,
    review_sg_brand,
    sg_no_brand_evidence_digest,
    parse_sg_category_catalog,
    parse_sg_category_mapper_input,
    replace_sg_category_catalog,
    refresh_sg_sls_results,
)
from modules.sls_category_rules_sg import sg_sls_reason_text
from modules.category_mapper_store import CategoryMapperStore
from modules.category_mapper_sg_brand_workflow import SGBrandWorkflow
from modules.product_review_transport import SGProductEvidenceLoader
from modules.category_mapper_sg_preparation import (
    group_sg_confirmation_items, confirm_sg_category_group, build_sg_confirmation_audit_csv,
    build_sg_preparation_candidate_files, build_sg_beta_preparation_files, assess_sg_preparation,
)


_SG_RESULT_KEY = "sg_category_mapper_recommendations"
_SG_FINGERPRINT_KEY = "sg_category_mapper_input_fingerprint"
_SG_SOURCE_TYPE_KEY = "sg_category_mapper_source_type"
_SG_AI_RESULT_KEY = "sg_category_mapper_ai_suggestions"
_SG_STATE_KEYS = (
    _SG_RESULT_KEY,
    _SG_FINGERPRINT_KEY,
    _SG_SOURCE_TYPE_KEY,
    _SG_AI_RESULT_KEY,
)


def render_sg_category_mapper(
    *, brand_workflow: SGBrandWorkflow | None = None,
    ai_engine: CategoryPredictionEngine | None = None,
    beta_output: bool = False,
) -> None:
    """Render SG mapping with offline SLS status and closed ready exports."""

    if beta_output:
        from modules.sg_beta_release import require_sg_beta_operation
        require_sg_beta_operation()
        if brand_workflow is None:
            raise ValueError("SG beta requires its bound workflow.")
    st.caption("SGの商品を確認し、出品準備CSV / TXTへまとめます。" if beta_output else (
        "SG Gate ELIGIBLE商品を商品単位の人間確認でCategoryを保存し、offline SLSを確認します。"
        "Category確定後も listing_ready=false のまま停止します。"
    ))
    if ai_engine is None:
        st.session_state.pop(_SG_AI_RESULT_KEY, None)
        st.info(
            "SG AI Category候補のlive実行は未承認です。現在は検証済みSG catalogからの"
            "手動Category確認だけを利用できます。"
        )
    elif brand_workflow is None:
        raise ValueError("Offline AI UI requires an explicitly injected isolated development workflow.")
    store = CategoryMapperStore() if brand_workflow is None else brand_workflow.store
    if brand_workflow is not None:
        st.info("SGのCategory・Brand・発送条件を確認します。" if beta_output else
                "SG Brand確認の開発検証画面です。候補取得は隔離DB・offline接続で行います。")
    with st.expander("設定：Category catalog（通常は変更不要）"):
        if brand_workflow is None or brand_workflow._live_scope is None:
            _render_catalog_import(store)
        else:
            st.caption("実接続確認では、画面上部のボタンから最新SGカテゴリーを取得します。")

    st.subheader("1. 商品CSVを読み込む")
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
    if brand_workflow is not None:
        brand_workflow.bind_input(fingerprint)
        _render_sg_evidence_import(brand_workflow, source_content, source_file.name if source_file else "")
    if st.session_state.get(_SG_FINGERPRINT_KEY) not in {None, fingerprint}:
        clear_sg_category_mapper_result(st.session_state)
        st.info("SG入力またはcatalogが変わったため、前回の表示結果を削除しました。")

    if source_file is not None and st.button(
        "Category確認を開始",
        type="primary",
        icon=":material/playlist_add_check:",
        key="sg_category_mapper_build",
    ):
        st.session_state.pop(_SG_AI_RESULT_KEY, None)
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
            if brand_workflow is not None and brand_workflow._live_scope is not None:
                if any(row.candidate_asin not in brand_workflow._live_scope.allowed_asins for row in source.rows):
                    raise SGCategoryMapperError("承認されたSG対象商品以外が含まれています。")
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
    recommendations = refresh_sg_sls_results(tuple(recommendations), store=store)
    st.session_state[_SG_RESULT_KEY] = recommendations
    if ai_engine is not None:
        _render_sg_ai_action(recommendations, store=store, engine=ai_engine)
    if brand_workflow is not None:
        _render_sg_batch_review(recommendations, brand_workflow)
    _render_products(recommendations, store, brand_workflow=brand_workflow, beta_output=beta_output)


def _render_sg_batch_review(recommendations, workflow):
    with st.expander("武器・武器形状の画像検査（開発検証）"):
        if st.button("武器画像検査の対象を判定", key="sg_review_load_all",
                     disabled=not workflow.can_load_product_evidence):
            # Clear first: a failure midway must not leave old reviews usable.
            workflow.product_review.clear()
            try:
                for item in recommendations:
                    workflow.load_product_evidence(item)
            except Exception:
                workflow.product_review.clear()
                st.warning("確認資料を読み込めませんでした。以前の確認を無効にしました。")
        try:
            targets = workflow.image_inspection_targets(recommendations)
        except Exception:
            workflow.product_review.clear_review_results()
            targets = ()
            st.warning("現在の安全情報を確認できません。商品確認を停止します。")
        st.caption(f"SG画像疑義確認の対象: {len(targets)}件。国別の対象カテゴリー設定で選びます。対象外はAI未実行です。")
        if st.button("対象商品の画像疑義をまとめて確認", key="sg_review_inspect_all",
                     disabled=not workflow.can_inspect_images or not targets):
            try:
                with st.spinner("対象商品の画像を確認しています…"):
                    workflow.inspect_image_batch(recommendations)
            except Exception:
                st.warning("画像確認を完了できません。以前の確認を無効にし、準備候補の出力を停止しました。")
            else:
                st.success("武器画像検査を実行しました。疑義あり・判断不能の商品だけ画像を確認してください。")


def clear_sg_category_mapper_result(state) -> None:
    for key in _SG_STATE_KEYS:
        state.pop(key, None)


def _render_sg_evidence_import(workflow, gate_content, gate_filename):
    with st.expander("安全判定・武器画像検査の入力資料（開発検証）"):
        st.caption("説明は既存の安全判定、画像情報は武器画像検査の対象判定に使います。商品内容の人間確認は要求しません。外部APIには問い合わせません。")
        candidate = st.file_uploader("商品候補の元CSV", type=["csv"], key="sg_review_candidate_csv")
        text = st.file_uploader("商品説明ファイル", type=["csv"], key="sg_review_text_csv")
        images = st.file_uploader("画像情報ファイル（未評価）", type=["json"], key="sg_review_image_json")
        files = (candidate, text, images)
        contents = tuple(file.getvalue() if file is not None else None for file in files)
        digest = hashlib.sha256()
        for content in (gate_content, *contents):
            digest.update(b"missing" if content is None else hashlib.sha256(content).digest())
        digest.update(gate_filename.encode("utf-8"))
        workflow.bind_product_evidence_files(digest.hexdigest() if any(file is not None for file in files) else None)
        if st.button("確認資料を読み込む", key="sg_review_load_files",
                     disabled=gate_content is None or any(file is None for file in files)):
            # Failed reload must discard both old evidence and its review first.
            workflow.clear_product_evidence_loader()
            try:
                loader = SGProductEvidenceLoader(candidate_content=contents[0], text_content=contents[1],
                                                 image_content=contents[2], gate_content=gate_content,
                                                 gate_filename=gate_filename)
                workflow.install_product_evidence_loader(loader)
            except Exception:
                st.error("確認資料を読み込めません。元CSVとの対応、説明・画像ファイル、SG入力を確認してください。")
            else:
                st.success("入力資料を読み込みました。武器画像検査の対象判定へ進めます。")


def _render_sg_ai_action(
    recommendations: tuple[SGMapperRecommendation, ...], *,
    store: CategoryMapperStore, engine: CategoryPredictionEngine,
) -> None:
    st.subheader("AI Category候補")
    st.caption("開発検証用の候補提示です。AIだけではCategoryや出品準備を確定しません。")
    if st.button(
        "AI Category候補を作成（Luna）", icon=":material/psychology:",
        key="sg_category_mapper_build_ai_suggestions",
        disabled=all(item.category_is_confirmed for item in recommendations),
    ):
        st.session_state.pop(_SG_AI_RESULT_KEY, None)
        try:
            batch = generate_sg_ai_category_suggestions(
                recommendations, store=store, engine=engine,
                catalog=build_sg_category_ai_catalog(store), profile=load_luna_request_profile(),
            )
        except Exception:
            st.warning("AI候補を作成できませんでした。手動Category確認を利用できます。")
        else:
            st.session_state[_SG_AI_RESULT_KEY] = batch
    batch = st.session_state.get(_SG_AI_RESULT_KEY)
    if isinstance(batch, AICategorySuggestionBatch):
        render_category_suggestion_batch(batch)


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
    *, brand_session: SGBrandSession | None = None,
    brand_workflow: SGBrandWorkflow | None = None,
    beta_output: bool = False,
) -> None:
    st.subheader("確認する商品")
    if brand_workflow is not None:
        _render_sg_groups(recommendations, store=store)
    st.caption("SGは商品ごとに確認します。Categoryの検索・採用操作はPHと共通です。")
    confirmed_count = sum(item.category_is_confirmed for item in recommendations)
    st.caption(
        f"Category確認済み: {confirmed_count}/{len(recommendations)}件 / " +
        ("出品準備情報を下で確認してください。" if beta_output else "SG listing_ready: 0件 / export: 停止")
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
            st.markdown("##### 2. Categoryを確認")
            if recommendation.category_is_confirmed:
                st.success("SG Category：人間確認済み")
                st.write(recommendation.recommended_category_path)
                st.caption(
                    f"ID {recommendation.recommended_category_id}" + ("" if beta_output else " / listing_ready=false / STOP")
                )
            else:
                if brand_workflow is not None:
                    _render_sg_ai_candidate(index, recommendation, store=store)
                _render_manual_selection(index, recommendation, store)
            st.markdown("##### 3. Brand / No Brandを確認")
            if brand_workflow is not None:
                _render_sg_brand_acquisition(index, recommendation, workflow=brand_workflow)
            elif brand_session is None:
                st.info("SGのBrand / No Brand確認はSeller Centerで行います。この画面では確認結果を保存しません。")
            else:
                render_sg_brand_confirmation(index, recommendation, store=store, session=brand_session)
            st.markdown("##### 4. 発送条件（SLS）を確認")
            _render_sls(recommendation)
            if brand_workflow is not None:
                _render_sg_attributes(index, recommendation, workflow=brand_workflow)
                _render_sg_weapon_review(index, recommendation, workflow=brand_workflow)
    st.subheader("5. 出品準備情報")
    if beta_output:
        current_items = tuple(st.session_state.get(_SG_RESULT_KEY) or recommendations)
        try:
            assessments = assess_sg_preparation(current_items, workflow=brand_workflow)
            for assessment in assessments:
                remaining = " / ".join(assessment["missing_steps"]) or "出品準備対象"
                st.caption(f"{assessment['asin']}：{remaining}")
            data, text, count = build_sg_beta_preparation_files(current_items, workflow=brand_workflow)
        except Exception:
            st.warning("現在の確認結果を検証できないため、出力を停止しました。")
        else:
            st.caption(f"出品準備対象: {count}件")
            st.caption("Category・Brandごとの入力補助資料です。Seller Centerの必須属性・商品固有の発送条件を確認して手動で出品してください。")
            if count:
                st.download_button("出品準備CSV", data, file_name="sg_listing_groups.csv", mime="text/csv")
                st.download_button("出品準備TXT", text, file_name="sg_listing_tool_input.txt", mime="text/plain")
        return
    st.info("SGの出品準備CSV / TXT出力は未提供です。実運用開始には別途承認が必要です。")
    if brand_workflow is not None:
        current_items = tuple(st.session_state.get(_SG_RESULT_KEY) or recommendations)
        try:
            audit = build_sg_confirmation_audit_csv(current_items, store=store, session=brand_workflow.session)
        except Exception:
            st.warning("確認状況を再検証できないため、開発用CSVの出力を停止しました。")
        else:
            st.download_button("開発検証：確認状況CSV", data=audit,
                               file_name="sg_confirmation_development_audit.csv", mime="text/csv",
                               key="sg_category_mapper_download_development_audit")
            st.caption("確認状況の記録です。出品用ファイルではなく、listing_readyは全件FALSEです。")
        try:
            assessments=assess_sg_preparation(current_items,workflow=brand_workflow)
            for assessment in assessments:
                remaining=" / ".join(assessment["missing_steps"]) or "開発用準備の確認完了（正式採用待ち）"
                st.caption(f"{assessment['asin']}：{remaining}")
            csv_preview, text_preview, count = build_sg_preparation_candidate_files(current_items, workflow=brand_workflow)
        except Exception:
            st.warning("出品準備候補を再検証できないため、開発用出力を停止しました。")
        else:
            st.caption(f"開発用の出品準備候補: {count}件（通常環境の出品準備完了ではありません）")
            if count:
                st.download_button("開発検証：出品準備候補CSV", csv_preview,
                                   file_name="sg_preparation_development_preview.csv", mime="text/csv")
                st.download_button("開発検証：出品準備候補TXT", text_preview,
                                   file_name="sg_preparation_development_preview.txt", mime="text/plain")


def _render_sg_weapon_review(index, recommendation, *, workflow):
    st.markdown("##### 武器・武器形状の画像検査")
    if st.button("武器画像検査の対象を判定", disabled=not workflow.can_load_product_evidence,
                 key=f"sg_category_mapper_fetch_product_evidence_{index}"):
        try:
            workflow.load_product_evidence(recommendation)
        except Exception:
            st.warning("武器画像検査の対象を判定できませんでした。")
    try:
        evidence = workflow.product_review.current(recommendation)
    except Exception:
        st.warning("安全情報を再検証できないため、商品確認を停止しました。")
        return
    if evidence is None:
        st.caption("武器画像検査の対象は未判定です。")
        return
    inspection = workflow.product_review.current_image_inspection(recommendation)
    selection = workflow.product_review.image_selection(recommendation)
    if selection == "OTHER_ROOT":
        st.caption("武器画像検査: 国別設定で対象外（未実行）。画像確認は不要です。")
        return
    if selection not in {"TARGET_ROOT", "ROOT_UNKNOWN"} or evidence.guardrail_status != "SAFE":
        st.warning("既存の安全判定または画像providerの未解決事項があります。")
        return
    if workflow.can_inspect_images and selection in {"TARGET_ROOT", "ROOT_UNKNOWN"}:
        if st.button("この商品の画像疑義を確認（開発検証）", key=f"sg_image_inspection_run_{index}",
                     disabled=evidence.guardrail_status != "SAFE" or evidence.image_provider != "keepa"):
            try:
                inspection = workflow.inspect_product_images(recommendation)
            except Exception:
                st.warning("画像確認を完了できません。以前の確認を無効化し、開発用準備候補の出力を停止しました。")
                inspection = None
    if inspection is None:
        st.info("対象商品の武器画像検査は未実行です。")
        return
    state_label = {"COMPLETED": "画像確認済み", "PARTIAL": "一部画像を確認できず",
                   "UNAVAILABLE": "画像なし・取得不能", "ERROR": "処理失敗"}[inspection.system_status]
    candidate_label = {"NO_SIGNAL": "確認画像で疑義なし", "REVIEW": "疑義あり・要確認",
                       "INDETERMINATE": "判断不能・要確認", None: "有効なAI候補なし"}[inspection.ai_status]
    st.caption(f"画像処理: {state_label} / 画像AI候補: {candidate_label}")
    st.text(inspection.note)
    st.caption("画像上の武器・武器形状物の疑義確認です。AI候補は国別の出品可否判定や安全保証ではありません。")
    if inspection.system_status == "COMPLETED" and inspection.ai_status == "NO_SIGNAL":
        st.caption("確認画像で武器疑義なし。追加の人間確認は不要です。")
        return
    for number, url in enumerate(evidence.image_urls, 1):
        st.link_button(f"武器疑義を確認する画像 {number}", url)
    prefix = f"sg_weapon_review_{index}_{evidence.binding}_{workflow.product_review.policy_binding(recommendation)[0]}_{inspection.evaluation_id}"
    images_checked = st.checkbox("武器疑義について十分な画像を確認しました", key=prefix + "_images")
    note = st.text_input("確認した画像・判断の根拠", key=prefix + "_note", max_chars=2000)
    if st.button("画像の人間判断を記録", key=prefix + "_save"):
        try:
            workflow.product_review.record_weapon_decision(recommendation, decision="ALLOW_PREPARATION",
                                           reviewed_images=images_checked, note=note)
        except Exception:
            st.warning("確認資料の不足またはSafety停止があります。確認済みにできません。")
    if st.button("武器画像の確認で除外", key=prefix + "_exclude"):
        try:
            workflow.product_review.record_weapon_decision(recommendation, decision="EXCLUDE",
                                           reviewed_images=images_checked, note=note)
        except Exception:
            st.warning("除外する理由を記入してください。")
    try:
        decision = workflow.product_review.decision(recommendation)
    except Exception:
        st.warning("安全情報を再検証できないため、商品確認を停止しました。")
        return
    if decision == "ALLOW_PREPARATION":
        st.success("武器画像の人間判断：準備継続")
    elif decision == "EXCLUDE":
        st.warning("この商品は出品準備候補から除外します。")


def _render_sg_groups(recommendations, *, store):
    for index, members in enumerate(group_sg_confirmation_items(recommendations)):
        if len(members) < 2:
            continue
        with st.expander(f"グループ確認：{members[0].keepa_category} / {members[0].keepa_brand}（{len(members)}件）"):
            st.dataframe([{"ASIN": item.candidate_asin, "商品名": item.product_title} for item in members], hide_index=True)
            category_id = st.number_input("グループで確認するCategory ID", min_value=0, step=1,
                                          key=f"sg_category_mapper_group_category_{index}")
            category = store.get_category("SG", int(category_id)) if category_id > 0 else None
            category_path = "" if category is None else str(category["category_path"])
            if category is not None:
                st.write(f"確認するCategory: {category_path}（ID {category_id}）")
            binding = hashlib.sha256((str(category_id) + category_path + "".join(sg_no_brand_evidence_digest(item) for item in members)).encode()).hexdigest()
            verified = st.checkbox("このグループの全商品のCategoryを確認しました",
                                   key=f"sg_category_mapper_group_verified_{binding}")
            if st.button("このCategoryをグループに採用", disabled=not verified or category is None or not category["is_leaf"],
                         key=f"sg_category_mapper_group_confirm_{index}"):
                try:
                    category = store.get_category("SG", int(category_id))
                    if category is None:
                        raise SGCategoryMapperError("Category unavailable")
                    updated = confirm_sg_category_group(tuple(members), store=store, category_id=int(category_id),
                                                        category_path=category["category_path"], human_verified=verified)
                except Exception:
                    st.warning("グループを確定できませんでした。現在のCategoryと商品を再確認してください。")
                else:
                    for item in updated:
                        _replace_one(item)
                    st.rerun()


def _render_sg_attributes(index, recommendation, *, workflow):
    st.markdown("##### 必須属性を確認")
    if not recommendation.category_is_confirmed:
        st.caption("Category採用後に属性を確認できます。")
        return
    if st.button("Category attributesを取得", key=f"sg_category_mapper_fetch_attributes_{index}"):
        try:
            workflow.fetch_attributes(recommendation)
        except Exception:
            st.warning("属性を取得・検証できませんでした。未確認のまま停止します。")
    result = workflow.current_attributes(recommendation)
    if result is None:
        st.caption("属性は未取得です。必須属性0件として扱いません。")
        return
    mandatory = [item for item in result.attributes if item["is_mandatory"]]
    st.caption(f"必須属性: {len(mandatory)}件（SG現在カテゴリの取得結果）")
    st.dataframe(list(result.attributes), hide_index=True)
    st.caption("属性の表示は入力完了や出品可能の確認を意味しません。")


def _render_sg_ai_candidate(
    index: int, recommendation: SGMapperRecommendation, *, store: CategoryMapperStore,
) -> None:
    batch = st.session_state.get(_SG_AI_RESULT_KEY)
    if not isinstance(batch, AICategorySuggestionBatch):
        return
    suggestion = batch.by_asin().get(recommendation.candidate_asin)
    if suggestion is None or not suggestion.is_adoptable:
        return
    st.write(f"AI候補: {suggestion.predicted_category_path}（ID {suggestion.predicted_category_id}）")
    if suggestion.requires_hobbies_warning:
        st.warning("Hobbies & Collectionsは既知の弱点があります。Categoryを手動確認してください。")
    if st.button("AI候補のCategoryを採用", key=f"sg_category_mapper_apply_ai_{index}"):
        try:
            updated = confirm_sg_category(
                recommendation, store=store, category_id=suggestion.predicted_category_id,
                expected_category_path=suggestion.predicted_category_path,
            )
        except (SGCategoryMapperError, ValueError):
            st.warning("AI候補が現在catalogと一致しません。Categoryを再確認してください。")
            st.session_state.pop(_SG_AI_RESULT_KEY, None)
        else:
            _replace_one(updated)
            st.session_state.pop(_SG_AI_RESULT_KEY, None)
            st.rerun()


def _render_sg_brand_acquisition(
    index: int, recommendation: SGMapperRecommendation, *, workflow: SGBrandWorkflow,
) -> None:
    if not recommendation.category_is_confirmed:
        st.info("Brand確認はCategoryを採用した後に表示します。")
        return
    if st.button(
        "このCategoryのBrand候補を取得", icon=":material/brand_awareness:",
        key=f"sg_category_mapper_fetch_brands_{index}",
    ):
        try:
            result = workflow.fetch(recommendation)
        except Exception:
            # Never include a transport exception: it may contain credentials.
            st.warning("Brand取得に失敗しました。古い候補を使わず、未確定のまま停止します。")
        else:
            if result.status != "SUCCESS":
                st.warning("Brand候補の取得が完了していません。未確定のまま停止します。")
            else:
                st.success("Brand候補を全件取得・検証しました。")
    render_sg_brand_confirmation(
        index, recommendation, store=workflow.store, session=workflow.session,
    )


def render_sg_brand_confirmation(
    index: int, recommendation: SGMapperRecommendation, *,
    store: CategoryMapperStore, session: SGBrandSession,
) -> None:
    """Offline development adapter; callers supply an initialized isolated DB/session.

    No credential lookup, network client, DB initialization or production route.
    Every rerun revalidates saved selections against this session's current catalog.
    """
    try:
        store._require_sg_brand_acceptance()
    except ValueError:
        st.warning("SG Brandの確認は初期化済みの隔離検証DBで行ってください。")
        return
    current = review_sg_brand(recommendation, store=store, session=session)
    _replace_one(current)
    if not current.category_is_confirmed:
        st.info("Brand確認はCategoryを採用した後に表示します。")
        return
    if not current.brand_current_valid:
        st.warning("現在のCategoryに対応するBrand候補の取得・検証が必要です。")
        return
    if current.brand_status in {"REAL_BRAND_CONFIRMED", "NO_BRAND_CONFIRMED"}:
        st.success("Brand：確認済み", icon=":material/check_circle:")
        st.write(f"{current.confirmed_brand_name}（ID {current.confirmed_brand_id}）")
        return
    catalog = session.require_current(current.recommended_category_id, store=store)
    brands = [
        {"brand_id": brand_id, "brand_name": name, "is_no_brand": no_brand}
        for brand_id, name, no_brand in catalog.brands
    ]
    st.caption(f"Keepa brand: {current.keepa_brand or '未設定'}")
    query = st.text_input(
        "Brand候補を検索", placeholder="Brand名またはBrand ID",
        key=f"sg_category_mapper_brand_search_{index}_{catalog.digest}",
    )
    options = search_brand_options(brands, query)
    if not options:
        st.info("一致するBrand候補はありません。未確定のまま保留できます。")
        return
    # Bind widgets to product Evidence and catalog, so confirmation never carries
    # over to another item/catalog after a rerun or input replacement.
    binding = f"{index}_{sg_no_brand_evidence_digest(current)}_{catalog.digest}"
    selected_label = st.selectbox(
        "確認するShopee Brand", [brand_option_label(brand) for brand in options],
        index=None, placeholder="確認したBrandを選択してください",
        key=f"sg_category_mapper_manual_brand_{binding}",
    )
    selected = next((brand for brand in options if brand_option_label(brand) == selected_label), None)
    verified = st.checkbox(
        "商品情報とBrand / No Brandの選択が一致することを確認しました",
        key=f"sg_category_mapper_brand_verified_{binding}_{selected_label}",
    )
    if st.button(
        "このBrandを採用", icon=":material/fact_check:",
        disabled=selected is None or not verified,
        key=f"sg_category_mapper_apply_brand_{index}",
    ):
        try:
            if selected is None:
                raise SGCategoryMapperError("Explicit Brand selection required.")
            updated = confirm_sg_brand(
                current, store=store, session=session, catalog=catalog,
                brand_id=int(selected["brand_id"]), expected_brand_name=str(selected["brand_name"]),
                human_product_verified=verified, human_option_selected=selected is not None,
            )
        except (SGCategoryMapperError, ValueError):
            st.warning("Brand候補または商品情報が変わりました。再確認してください。")
        else:
            _replace_one(updated)
            st.rerun()


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
        "確認するCategory ID",
        min_value=0,
        value=0,
        step=1,
        key=f"sg_category_mapper_manual_category_{index}",
    )
    if st.button(
        "このCategoryを採用",
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


def _render_sls(recommendation: SGMapperRecommendation) -> None:
    result = recommendation.sls_result
    label = {"CATEGORY_ALLOW": "ALLOW候補", "CATEGORY_REVIEW": "REVIEW",
             "CATEGORY_EXCLUDE": "EXCLUDE"}.get(result.action, result.check_state)
    message = "SG SLS: " + label + " / " + sg_sls_reason_text(result)
    if result.check_state == "UNAVAILABLE" or result.action == "CATEGORY_EXCLUDE":
        st.error(message)
    elif result.action == "CATEGORY_REVIEW":
        st.warning(message)
    else:
        st.info(message)
    st.caption("SLSはCategory条件の確認です。商品全体のSafety判定・listing_ready・exportは解除しません。")
