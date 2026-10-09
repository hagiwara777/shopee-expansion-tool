"""Optional read-only comparison. No persistence, decisions, or API factory."""
import streamlit as st

from modules.safety_shadow_comparison import compare_saved_shadow, comparison_context

REASONS = {
    "MISSING_EVIDENCE": "保存済みFactが未指定",
    "MISSING_CURRENT_TEXT_FACT": "対応するProduct Text Safety sidecarが未指定",
    "CURRENT_TEXT_MISMATCH": "現在の商品文章とCandidateが不一致",
    "CONTEXT_MISMATCH": "現在のCandidate・市場・Gate結果が不一致",
    "INVALID_EVIDENCE": "保存資料の形式不正・ASIN重複（旧report単独は利用不可）",
    "DUPLICATE_CANDIDATE_ASIN": "CandidateのASINが重複",
    "MISSING_PRODUCT": "対象ASINの保存Factなし",
    "PRODUCT_IDENTITY_MISMATCH": "商品名・ブランド・取得時刻が欠損または不一致",
    "PRODUCT_TEXT_MISMATCH": "商品文章Factが不一致",
    "PRODUCT_DOMAIN_UNVERIFIED": "JP商品資料として確認不能",
    "OWN_CATEGORY_MISMATCH": "商品自身のカテゴリpathが欠損または不一致",
    "INVALID_PRODUCT_FACT": "商品Factの形式・カテゴリ出所が確認不能",
}


def render_shadow_comparison(candidates, candidate_content, product_text, gate_result):
    with st.expander("Shadow V3との比較（任意）", expanded=False):
        st.caption("本体・付属品の候補と根拠を比較します。販売可否や既存の保安判定・除外は変更しません。")
        try:
            context = comparison_context(candidates, candidate_content, product_text,
                                         gate_result, gate_result.marketplace)
        except (ValueError, RuntimeError, TypeError, AttributeError):
            st.info("比較不能：現在の入力とGate結果を確認してください。")
            return
        source_format = st.selectbox("保存資料の形式", ("keepa_response", "cache_snapshot"),
                                     key="shadow_format_" + context)
        evidence = st.file_uploader("保存済み商品Fact JSON", type=["json"],
                                    key="shadow_evidence_" + context)
        comparison = compare_saved_shadow(
            candidates, candidate_content, product_text, gate_result, marketplace=gate_result.marketplace,
            evidence_content=None if evidence is None else evidence.getvalue(), source_format=source_format)
        displayed = []
        details = []
        for checked, current in zip(comparison.rows, gate_result.rows):
            roles = "; ".join(s.family + ": " + s.classification
                              + (" / 本体同梱候補" if s.bundle_candidate else "") for s in checked.signals)
            displayed.append({
                "市場": comparison.marketplace, "ASIN": checked.candidate_asin,
                "商品名": current.candidate.product_title, "既存Safety": current.guardrail_status,
                "既存Gate": current.final_eligibility, "既存停止根拠": current.guardrail_note,
                "比較": "比較可能" if checked.status == "COMPARABLE" else "比較不能",
                "分類候補": roles or ("対象familyのsignalなし（安全保証ではありません）"
                                  if checked.status == "COMPARABLE" else ""),
                "比較不能の理由": REASONS.get(checked.reason, checked.reason),
                "カテゴリ根拠": checked.category_basis,
            })
            for signal in checked.signals:
                for match in signal.matched_evidence:
                    details.append({"ASIN": checked.candidate_asin, "family": signal.family,
                                    "分類": signal.classification, "欄": match.field,
                                    "一致": match.matched, "抜粋": match.excerpt,
                                    "出所": match.evidence_source, "分類version": signal.rule_version,
                                    "Evaluator": signal.evaluator_version})
        st.dataframe(displayed, hide_index=True)
        if details:
            st.dataframe(details, hide_index=True)
        st.caption("seed fallbackは分類用カテゴリに使いません。比較不能は既存Safetyの変更や追加REVIEWを意味しません。")
