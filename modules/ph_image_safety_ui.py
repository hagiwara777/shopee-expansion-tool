"""Japanese PH image review controls; no requests on ordinary Streamlit reruns."""
import streamlit as st

from modules.ph_image_safety import (
    ImageSafetyError,
    SKIP_SELECTORS,
    clear_human_decision,
    image_sidecar_bytes,
    image_result_status,
    record_human_decision,
    run_image_safety,
)
from modules.ph_image_safety_api import OpenAIImageAnalyzer

_SELECTOR_LABELS = {
    "TARGET_ROOT": "対象カテゴリ",
    "ROOT_UNKNOWN": "カテゴリ不明のため対象",
    "OTHER_ROOT": "対象外カテゴリ・未実行",
    "EXISTING_BLOCK": "既存ルールで除外・未実行",
    "PROVIDER_UNSUPPORTED": "試験用取得元・未実行",
}
_STATE_LABELS = {
    "NOT_RUN": "未実行",
    "COMPLETED": "画像確認済み",
    "UNAVAILABLE": "画像なし・取得不能",
    "ERROR": "処理失敗",
    "PARTIAL": "一部画像を確認できず",
}
_AI_LABELS = {
    None: "有効なAI結果なし",
    "NO_SIGNAL": "確認画像で疑義なし",
    "REVIEW": "疑義あり・要確認",
    "INDETERMINATE": "判断できず・要確認",
}
_RESULT_LABELS = {
    None: "未実行",
    "NO_SIGNAL": "確認画像で疑義なし",
    "REVIEW": "疑義あり・要確認",
    "INDETERMINATE": "判断不能・要確認",
    "UNAVAILABLE": "画像なし・要確認",
    "ERROR": "処理失敗・要確認",
}
_HUMAN_LABELS = {"ALLOW_PREPARATION": "画像確認済み・準備継続", "EXCLUDE": "除外"}


def render_image_review(base_result, sidecar, candidate_content):
    st.subheader("PH画像の確認")
    st.caption("画像で見える武器・武器の形をした物の疑いを確認します。画像で疑義が見つからなくても、安全や出品承認を保証しません。")
    pending = [
        r
        for r in sidecar["rows"]
        if r["evaluation"]["selector"] not in SKIP_SELECTORS
        and r["evaluation"]["system_status"] == "NOT_RUN"
        and r["human"] is None
    ]
    if pending:
        pending_notice = st.empty()
        pending_notice.info(f"画像AI未実行: {len(pending)}商品。未確認の商品は要確認を継続します。")
        approved = st.checkbox(
            "対象商品の画像AI有料実行を許可する",
            key="ph_image_ai_approved_" + sidecar["candidate_sha256"],
        )
        if (
            st.button("対象商品の画像AIを実行", disabled=not approved, key="ph_image_ai_run")
            and approved is True
        ):
            with st.spinner("画像を確認しています..."):
                sidecar = run_image_safety(
                    base_result,
                    sidecar,
                    candidate_content,
                    analyzer=OpenAIImageAnalyzer.from_environment(),
                )
                pending_notice.success("対象商品の画像AI処理が終了しました。結果と要確認の商品を確認してください。")
    rows = sidecar["rows"]
    table_position = st.empty()
    target_rows = {
        r["fact"]["candidate_asin"]: r
        for r in rows
        if r["evaluation"]["selector"] not in SKIP_SELECTORS
    }
    if target_rows:
        asin = st.selectbox("人間が確認する商品", list(target_rows), key="ph_image_review_asin")
        if asin not in target_rows:
            raise ImageSafetyError("画像確認対象の商品が不正です。")
        row = target_rows[asin]
        st.text(
            next(
                r.candidate.product_title
                for r in base_result.rows
                if r.candidate.candidate_asin == asin
            )
        )
        for index, url in enumerate(row["fact"]["image_urls"], 1):
            st.link_button(f"商品画像{index}を開く", url)
        if not row["fact"]["image_urls"]:
            st.info("取得画像がありません。別経路でも十分な画像を確認できない場合は、要確認を継続してください。")
        st.caption("準備継続は画像由来の要確認だけを解除します。他の除外・要確認理由は残ります。")
        identity = row["evaluation"]["evaluation_id"]
        choice = st.selectbox(
            "画像確認後の判断",
            ["判断を選択", "画像確認済み・準備継続", "除外"],
            key="ph_image_choice_" + identity,
        )
        confirmed = st.checkbox("この商品の十分な画像を確認した", key="ph_image_confirmed_" + identity)
        note = st.text_area(
            "確認した画像・判断の根拠", key="ph_image_note_" + identity, max_chars=2000
        )
        if st.button("画像の人間判断を記録", key="ph_image_human_save"):
            decision = {"画像確認済み・準備継続": "ALLOW_PREPARATION", "除外": "EXCLUDE"}.get(choice)
            if decision is None:
                st.info("記録する判断を選んでください。現在の判断は変更していません。")
            elif not note.strip() or (
                decision == "ALLOW_PREPARATION" and confirmed is not True
            ):
                st.error("準備継続には十分な画像確認が必要です。確認した画像・判断の根拠も記入してください。")
            else:
                sidecar = record_human_decision(
                    base_result,
                    sidecar,
                    candidate_content,
                    asin=asin,
                    decision=decision,
                    reviewed_images=confirmed,
                    note=note,
                )
                st.success("画像の人間判断を記録しました。最終判定へ反映しました。")
        if row["human"] is not None and st.button(
            "この商品の人間判断を取り消す", key="ph_image_human_clear"
        ):
            sidecar = clear_human_decision(
                base_result, sidecar, candidate_content, asin=asin
            )
            st.success("人間判断を取り消しました。画像確認結果に基づく判定へ戻しました。")
    table_position.dataframe(
        [
            {
                "ASIN": r["fact"]["candidate_asin"],
                "画像確認対象": _SELECTOR_LABELS[r["evaluation"]["selector"]],
                "処理状況": _STATE_LABELS[r["evaluation"]["system_status"]],
                "画像確認結果": _RESULT_LABELS[image_result_status(r["evaluation"])],
                "取得画像のAI応答": _AI_LABELS[r["evaluation"]["ai_status"]],
                "判定メモ": r["evaluation"]["note"],
                "人間判断": _HUMAN_LABELS[r["human"]["decision"]] if r["human"] else "未記録",
            }
            for r in sidecar["rows"][:100]
        ],
        hide_index=True,
        width="stretch",
    )
    st.download_button(
        "画像確認記録をダウンロード",
        data=image_sidecar_bytes(sidecar),
        file_name="ph_image_safety_review.json",
        mime="application/json",
        key="ph-image-safety-download",
        on_click="ignore",
        width="stretch",
    )
    return sidecar
