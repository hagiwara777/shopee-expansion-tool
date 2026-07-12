import pandas as pd
import streamlit as st

from modules.asin_resolver import (
    build_ai_prompt,
    clean_ai_response,
    preview_candidates,
    rows_to_resolver_csv,
    summarize_preview,
    summarize_statuses,
    verify_preview_rows,
)
from modules.config import load_settings
from modules.export_csv import rows_to_csv
from modules.guardrails import (
    GuardrailDictionaryError,
    apply_guardrails,
    filter_safe_rows,
    summarize_guardrails,
)
from modules.keepa_client import (
    KeepaClientError,
    KeepaConfigurationError,
    KeepaDataError,
    KeepaExpansionClient,
    SEARCH_MODE_LABELS,
    SEARCH_MODE_NOTES,
    estimate_token_usage,
    normalize_asin,
    planned_candidate_count,
)


PAGE_OPTIONS = [1, 3, 5]
SEARCH_MODE_OPTIONS = ["strict", "standard", "broad", "category_research"]


st.set_page_config(page_title="Shopee Expansion Tool Ver1", layout="centered")

st.title("Shopee Expansion Tool Ver1")

expansion_tab, resolver_tab = st.tabs(["派生ASIN取得", "起点ASIN取得"])

with expansion_tab:
    with st.form("search_form", clear_on_submit=False):
        asin_input = st.text_input("ASIN", placeholder="B07TSC47PH")
        search_mode = st.selectbox(
            "検索モード",
            SEARCH_MODE_OPTIONS,
            index=0,
            format_func=lambda value: SEARCH_MODE_LABELS[value],
        )
        st.caption(SEARCH_MODE_NOTES[search_mode])
        search_pages = st.selectbox(
            "検索ページ数",
            PAGE_OPTIONS,
            index=0,
            format_func=lambda value: f"{value}ページ",
        )
        st.caption(
            f"取得予定候補数: {planned_candidate_count(search_pages)}件 / "
            f"推定消費トークン: 約{estimate_token_usage(search_pages)} tokens"
        )
        search_clicked = st.form_submit_button(
            "検索開始",
            type="primary",
            width="stretch",
        )

    if search_clicked:
        st.session_state["result"] = None

        settings = load_settings()

        if not settings.keepa_api_key:
            st.error(
                "APIキーが未設定です。プロジェクト直下の .env に KEEPA_API_KEY を設定してください。"
            )
            st.stop()

        try:
            source_asin = normalize_asin(asin_input)
            client = KeepaExpansionClient(
                api_key=settings.keepa_api_key,
                domain=settings.keepa_domain,
            )

            with st.spinner("Keepa APIから候補ASINを取得しています。トークン不足時は自動で回復待ちします..."):
                result = client.find_related_products(
                    source_asin=source_asin,
                    search_pages=search_pages,
                    search_mode=search_mode,
                )

        except ValueError as exc:
            st.error(str(exc))
        except (KeepaConfigurationError, KeepaDataError, KeepaClientError) as exc:
            st.error(str(exc))
        except Exception:
            st.error(
                "想定外のエラーが発生しました。アプリを再起動し、同じASINで再実行してください。"
            )
        else:
            st.session_state["result"] = result

    result = st.session_state.get("result")

    if result:
        try:
            guarded_rows = apply_guardrails(result.rows)
        except GuardrailDictionaryError as exc:
            st.error(f"Guardrail辞書を読み込めませんでした。{exc}")
            st.warning(
                "アカウント保護のため、Guardrail判定が完了するまで候補一覧とCSVダウンロードは表示しません。"
            )
            st.stop()

        guardrail_summary = summarize_guardrails(guarded_rows)
        safe_rows = filter_safe_rows(guarded_rows)

        if result.final_display_count:
            st.success(f"{result.final_display_count}件の候補ASINを取得しました。")
        else:
            st.warning("候補ASINは0件でした。検索条件をstandardまたはbroadに広げて再検索してください。")

        st.write(f"取得したbrand: {result.brand}")
        st.write(f"取得したcategory: {result.category}")
        st.write(f"検索モード: {SEARCH_MODE_LABELS.get(result.search_mode, result.search_mode)}")
        st.write(f"検索モードの注意: {result.search_mode_note}")
        st.write(f"利用カテゴリ条件: {result.category_filter_note}")
        st.write(f"検索ページ数: {result.search_pages}ページ")
        st.write(f"取得予定候補数: {result.planned_candidates}件")
        st.write(f"推定消費トークン: 約{result.token_estimate} tokens")
        if result.total_results is not None:
            st.write(f"Product Finder totalResults: {result.total_results}件")
        st.write(f"Product Finder returned ASIN count: {result.raw_candidate_count}件")
        st.write(f"詳細取得成功数: {result.detail_success_count}件")
        st.write(f"詳細取得失敗数: {result.detail_failed_count}件")
        st.write(f"重複除外数: {result.duplicate_removed_count}件")
        st.write(f"自己ASIN除外数: {result.self_excluded_count}件")
        st.write(f"既出品除外: {result.existing_listing_exclusion_status}")
        st.write(f"削除済みASIN除外: {result.deleted_asin_exclusion_status}")
        st.write(f"最終表示件数: {result.final_display_count}件")
        st.write(f"キャッシュ利用: {'あり' if result.cache_hit else 'なし'}")
        st.write("ガードレール適用有無: 適用済み（SG辞書）")
        st.write(f"SAFE件数: {guardrail_summary['SAFE']}件")
        st.write(f"REVIEW件数: {guardrail_summary['REVIEW']}件")
        st.write(f"BLOCK件数: {guardrail_summary['BLOCK']}件")
        st.write(f"出品候補CSV件数: {guardrail_summary['safe_csv_count']}件（SAFEのみ）")
        st.write(f"監査用CSV件数: {guardrail_summary['audit_csv_count']}件（全件）")
        st.warning(
            "SAFEは出品安全を保証するものではありません。現時点のSG辞書ルールに一致しなかった、という意味です。"
        )
        if guardrail_summary["BLOCK"]:
            st.warning("BLOCK候補はアカウント保護のため出品候補CSVから除外されます。")
        if guardrail_summary["REVIEW"]:
            st.warning(
                "REVIEW候補は人間確認が必要なため、通常の出品候補CSVには含めていません。"
            )
        if result.total_results_note:
            st.info(result.total_results_note)
        if result.strict_low_count_suggestion:
            st.warning(result.strict_low_count_suggestion)
        st.info(result.token_status)

        if result.note:
            st.warning(result.note)

        if result.diagnostics:
            with st.expander("Product Finder診断結果"):
                for diagnostic in result.diagnostics:
                    st.write(diagnostic)

        st.download_button(
            label="出品候補CSVダウンロード（SAFEのみ）",
            data=rows_to_csv(safe_rows),
            file_name=f"keepa_safe_candidates_{result.source_asin}.csv",
            mime="text/csv",
            width="stretch",
        )
        st.download_button(
            label="監査用CSVダウンロード（SAFE / REVIEW / BLOCK 全件）",
            data=rows_to_csv(guarded_rows),
            file_name=f"keepa_guardrail_audit_{result.source_asin}.csv",
            mime="text/csv",
            width="stretch",
        )
        st.dataframe(pd.DataFrame(guarded_rows), width="stretch", hide_index=True)

with resolver_tab:
    st.subheader("ASIN Resolver Tool Ver0.2")
    prompt_tab, verify_tab = st.tabs(["商品名 → AI用プロンプト", "AI返答 → ASIN確認"])

    with prompt_tab:
        st.info(
            "商品名は1行1商品で貼り付けてください。"
            "このタブではAmazon検索を行わず、外部AIへ貼るためのプロンプトを生成します。"
        )
        with st.form("asin_resolver_prompt_form", clear_on_submit=False):
            product_names_text = st.text_area(
                "商品名リスト",
                placeholder=(
                    "Anua Heartleaf 77 Toner 250ml\n"
                    "HAKUBA Camera Case Plus Shell City 04 Camera Pouch M Black"
                ),
                height=180,
            )
            prompt_clicked = st.form_submit_button(
                "AI用プロンプト生成",
                type="primary",
                width="stretch",
            )

        if prompt_clicked:
            if not product_names_text.strip():
                st.warning("商品名リストを入力してください。")
            else:
                generated_prompt = build_ai_prompt(product_names_text)
                st.session_state["asin_resolver_prompt"] = generated_prompt
                st.session_state["asin_resolver_prompt_display"] = generated_prompt

        st.text_area(
            "生成されたプロンプト",
            height=320,
            key="asin_resolver_prompt_display",
        )

    with verify_tab:
        st.info(
            "商品名だけではAmazon検索は行いません。"
            "Amazon.co.jp URLまたはASINを含むAI返答を貼り付けてください。"
        )
        with st.form("asin_resolver_verify_form", clear_on_submit=False):
            ai_response_text = st.text_area(
                "ChatGPT / Geminiの返答",
                placeholder=(
                    "input_title\tamazon_url\n"
                    "Anua Heartleaf 77 Toner 250ml\thttps://www.amazon.co.jp/dp/B08C4Z1XF4\n"
                    "Unknown Product\t不明"
                ),
                height=220,
            )
            parse_clicked = st.form_submit_button(
                "AI返答を解析",
                type="primary",
                width="stretch",
            )

        if parse_clicked:
            st.session_state["asin_resolver_preview_rows"] = []
            st.session_state["asin_resolver_rows"] = []
            st.session_state["asin_resolver_input_line_count"] = 0

            if not ai_response_text.strip():
                st.warning("ChatGPT / Geminiの返答を入力してください。")
            else:
                preview_rows = preview_candidates(ai_response_text)
                st.session_state["asin_resolver_preview_rows"] = preview_rows
                st.session_state["asin_resolver_input_line_count"] = len(
                    clean_ai_response(ai_response_text).splitlines()
                )
                if preview_rows:
                    st.success(f"{len(preview_rows)}件の候補行を解析しました。")
                else:
                    st.warning("確認対象または候補として残す行はありませんでした。")

        preview_rows = st.session_state.get("asin_resolver_preview_rows", [])
        if preview_rows:
            preview_summary = summarize_preview(preview_rows)
            input_line_count = st.session_state.get("asin_resolver_input_line_count", 0)
            st.caption(
                f"解析対象入力行数: {input_line_count}件（空行・コードブロックを除く）。"
                f"Keepa API確認対象ASIN数: {preview_summary['unique_asins']}件"
                "（重複を除いたKeepa確認対象ASIN数）。"
                "プレビューではKeepa APIを呼びません。"
                "AI返答を変更した場合は、もう一度解析してください。"
            )
            preview_cols = st.columns(3)
            preview_cols[0].metric("抽出ASIN行数", preview_summary["extracted_asin_rows"])
            preview_cols[1].metric("Keepa確認対象数", preview_summary["unique_asins"])
            preview_cols[2].metric("NOT_CHECKED件数", preview_summary["not_checked"])
            preview_detail_cols = st.columns(2)
            preview_detail_cols[0].metric("対象外URL件数", preview_summary["non_jp_url"])
            preview_detail_cols[1].metric("抽出不可行数", preview_summary["unresolved"])
            st.dataframe(pd.DataFrame(preview_rows), width="stretch", hide_index=True)

            verify_clicked = st.button(
                "抽出ASINをKeepaで確認",
                type="primary",
                width="stretch",
                disabled=preview_summary["unique_asins"] == 0,
            )

            if verify_clicked:
                st.session_state["asin_resolver_rows"] = []
                settings = load_settings()
                if not settings.keepa_api_key:
                    st.error(
                        "Keepa APIキーが未設定です。プロジェクト直下の .env の KEEPA_API_KEY を確認してください。"
                    )
                else:
                    try:
                        client = KeepaExpansionClient(
                            api_key=settings.keepa_api_key,
                            domain="JP",
                        )
                        with st.spinner("Keepa APIでASINの実在確認をしています..."):
                            st.session_state["asin_resolver_rows"] = verify_preview_rows(
                                preview_rows,
                                client,
                            )
                    except (KeepaConfigurationError, KeepaDataError, KeepaClientError) as exc:
                        st.error(str(exc))
                    except Exception:
                        st.error(
                            "想定外のエラーが発生しました。アプリを再起動し、同じ内容で再実行してください。"
                        )

        resolver_rows = st.session_state.get("asin_resolver_rows", [])
        if resolver_rows:
            summary = summarize_statuses(resolver_rows)
            st.success(f"{len(resolver_rows)}件のKeepa確認を完了しました。")
            st.write(f"FOUND: {summary['FOUND']}件")
            st.write(f"UNKNOWN: {summary['UNKNOWN']}件")
            st.write(f"ERROR: {summary['ERROR']}件")
            st.download_button(
                label="起点ASIN候補CSVダウンロード",
                data=rows_to_resolver_csv(resolver_rows),
                file_name="asin_resolver_candidates.csv",
                mime="text/csv",
                width="stretch",
            )
            st.dataframe(pd.DataFrame(resolver_rows), width="stretch", hide_index=True)
