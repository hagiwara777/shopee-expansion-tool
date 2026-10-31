"""Manual download only; does not edit FROMAX or the app's dictionaries."""
import streamlit as st
from modules.fromax_ng_export import build_fromax_ng_export
from modules.guardrails import GuardrailDictionaryError
from modules.community_ng import CommunityNgDataError


def render_fromax_ng_export(marketplace: str) -> None:
    with st.expander("FROMAX用NGキーワードの手動出力", expanded=False):
        st.caption("有効なBLOCK語句だけを国別に出します。要確認の語句は含めません。FROMAXへの自動登録は行いません。")
        if not st.checkbox("NG語句のプレビューを開く", key=f"fromax-ng-preview-{marketplace}"):
            return
        try:
            bundle = build_fromax_ng_export(marketplace)
        except (GuardrailDictionaryError, CommunityNgDataError, ValueError):
            st.error("NG辞書を確認できないため出力を停止しました。")
            return
        st.write(f"{marketplace}：貼付用 {len(bundle.keywords)}語／注意リスト {len(bundle.cautions)}行")
        st.warning("FROMAXは単語の区切りを見ません。短い英語・ブランド・ASIN指定などは注意リストへ分けています。注意リストは一括貼付しないでください。")
        st.caption("元表記・全半角の正規化表記・ひらがな／カタカナ表記を含みます。漢字との言い換えは生成しません。貼付用の語句でも否定文や付属品に反応する場合があります。")
        st.code("\n".join(bundle.keywords), language=None)
        st.download_button("貼付用NGキーワードTXT", data=bundle.keywords_txt,
            file_name=f"fromax_ng_keywords_{marketplace.lower()}.txt", mime="text/plain",
            key=f"fromax-ng-keywords-{marketplace}", on_click="ignore", width="stretch")
        st.download_button("注意リストCSV（そのまま貼付しない）", data=bundle.cautions_csv,
            file_name=f"fromax_ng_cautions_{marketplace.lower()}.csv", mime="text/csv",
            key=f"fromax-ng-cautions-{marketplace}", on_click="ignore", width="stretch")
        st.caption("FROMAXリサーチ画面のNGは商品名・ブランドを見るため、説明文・成分の確認は本ツールの保安ゲートで続けてください。NGブランドの既存設定はこのTXTで置き換えません。")
