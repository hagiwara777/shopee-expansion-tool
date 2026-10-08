"""Targeted SG body questions in the existing Gate; no general review system."""

import streamlit as st

from modules.prelisting_sg_body_safety import (
    SGBodySafetyError, body_checks, body_confirmation_bytes, prepare_body_confirmations, record_body_confirmation,
)


def render_sg_body_review(candidates, product_text, confirmations):
    result = prepare_body_confirmations(candidates, product_text, confirmations)
    checks = body_checks(candidates, product_text, result)
    if not checks:
        return result
    st.subheader("SG 本体・実同梱の確認")
    st.caption("レンズ本体は販売除外、一般台所用包丁本体は当社の暫定除外です。"
               "本体を含むセットも除外します。付属品確認で既存の別理由による停止は解除されません。")
    titles = {row.candidate_asin: row.product_title for row in candidates.rows}
    choices = {
        "不明・確認を継続": "UNRESOLVED",
        "本体あり・本体を含むセット": "BODY_PRESENT",
        "本体なし・付属品／ケア用品のみ": "ACCESSORY_ONLY",
    }
    for check in checks:
        asin, family = check["candidate_asin"], check["family"]
        key = f"sg_body_{result['context_sha256']}_{asin}_{family}"
        with st.container(border=True):
            st.write(f"{asin} — {titles[asin]}")
            subject = "一般台所用包丁" if family == "KNIFE" else "コンタクトレンズ"
            st.write(f"{subject}本体が商品またはセットに実際に含まれますか？")
            st.caption("疑義の根拠: " + "; ".join(check["evidence"]))
            st.caption(f"保存済み確認: {check['outcome']}" + (f" / {check['note']}" if check["note"] else ""))
            if check["outcome"] == "BODY_PRESENT":
                st.warning("本体・実同梱を確認済みのため除外します。")
                continue
            choice = st.selectbox("本体・同梱の確認結果", tuple(choices), key=key + "_outcome")
            reviewed = st.checkbox("名称だけで決めず、商品内容・同梱内容の根拠を確認した", key=key + "_reviewed")
            note = st.text_area("確認した資料・内容と判断根拠", key=key + "_note", max_chars=2000)
            if st.button("本体確認結果を反映", key=key + "_save"):
                try:
                    result = record_body_confirmation(candidates, product_text, result, asin=asin, family=family,
                                                      outcome=choices[choice], evidence_reviewed=reviewed, note=note)
                except SGBodySafetyError:
                    st.warning("対象・確認結果・商品内容の確認と判断根拠を確認してください。停止を維持します。")
                else:
                    st.success("確認結果を反映しました。再開用の確認記録も保存してください。")
    st.download_button("SG本体確認記録を保存", data=body_confirmation_bytes(result),
                       file_name="sg_body_confirmations.json", mime="application/json", key="sg_body_download")
    st.caption("同じ入力での再実行には確認を保持します。画面を閉じて再開するときは、この記録を読み込んでください。")
    return result
