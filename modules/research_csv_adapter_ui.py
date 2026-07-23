"""Streamlit UI for the isolated Shopee research CSV import adapter."""

from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from modules.research_csv_adapter import ResearchCsvInput, import_research_csvs


_RESULT_KEY = "research_csv_adapter_result"
_FINGERPRINT_KEY = "research_csv_adapter_input_fingerprint"


def render_research_csv_adapter_tab() -> None:
    """Render import, preview, and local download controls without external calls."""

    st.subheader("Shopee調査CSV取込")
    st.caption(
        "複数のShopee調査CSVから PH / Japan 完全一致の商品だけを抽出し、"
        "ASIN Resolver用TSVと追跡用CSVをローカルで作成します。外部APIは呼び出しません。"
    )
    uploaded_files = st.file_uploader(
        "Shopee調査CSV（複数選択可）",
        type=["csv"],
        accept_multiple_files=True,
        key="research_csv_adapter_files",
    )
    uploads = tuple(
        ResearchCsvInput(filename=uploaded_file.name, content=uploaded_file.getvalue())
        for uploaded_file in uploaded_files
    )
    fingerprint = _input_fingerprint(uploads)
    if st.session_state.get(_FINGERPRINT_KEY) not in {None, fingerprint}:
        st.session_state.pop(_RESULT_KEY, None)
        st.info("入力が変わったため、前回の取込結果を削除しました。")

    if st.button(
        "取込内容を確認",
        type="primary",
        icon=":material/fact_check:",
        key="research_csv_adapter_import",
    ):
        if not uploads:
            st.session_state.pop(_RESULT_KEY, None)
            st.warning("Shopee調査CSVを1件以上選択してください。")
        else:
            st.session_state[_RESULT_KEY] = import_research_csvs(uploads)
            st.session_state[_FINGERPRINT_KEY] = fingerprint

    result = st.session_state.get(_RESULT_KEY)
    if result is None or st.session_state.get(_FINGERPRINT_KEY) != fingerprint:
        return

    _render_summary(result.summary)
    st.caption(f"Batch ID: {result.batch_id}")
    _render_previews(result)
    st.subheader("ダウンロード")
    with st.container(horizontal=True):
        st.download_button(
            "Resolver用TSVをダウンロード",
            data=result.resolver_tsv(),
            file_name="shopee_research_resolver_input_ph_japan.tsv",
            mime="text/tab-separated-values",
            icon=":material/download:",
            key="research_csv_adapter_download_resolver",
        )
        st.download_button(
            "追跡用Manifest CSVをダウンロード",
            data=result.manifest_csv(),
            file_name="shopee_research_manifest_ph_japan.csv",
            mime="text/csv",
            icon=":material/download:",
            key="research_csv_adapter_download_manifest",
        )
        st.download_button(
            "保留・除外CSVをダウンロード",
            data=result.deferred_csv(),
            file_name="shopee_research_deferred_ph_japan.csv",
            mime="text/csv",
            icon=":material/download:",
            key="research_csv_adapter_download_deferred",
        )


def _render_summary(summary: object) -> None:
    values = dict(summary) if isinstance(summary, dict) else {}
    metric_rows = (
        (
            ("入力ファイル数", values.get("input_file_count", 0)),
            ("総行数", values.get("total_rows", 0)),
            ("PH / Japan対象行", values.get("ph_japan_rows", 0)),
            ("Japan以外", values.get("location_not_japan_rows", 0)),
        ),
        (
            ("一意listing数", values.get("unique_listing_count", 0)),
            ("重複除外数", values.get("duplicate_superseded_count", 0)),
            ("Resolver投入可能数", values.get("resolver_ready_count", 0)),
            ("TITLE_REVIEW数", values.get("title_review_count", 0)),
        ),
    )
    for metrics in metric_rows:
        columns = st.columns(4)
        for column, (label, value) in zip(columns, metrics):
            column.metric(label, value)
    st.caption(f"URL / schemaエラー数: {values.get('url_or_schema_error_count', 0)}")


def _render_previews(result: object) -> None:
    resolver_rows = tuple(getattr(result, "resolver_rows", ()))
    deferred_rows = tuple(getattr(result, "deferred_rows", ()))
    st.subheader("Resolver投入対象")
    if resolver_rows:
        manifest_by_source_id = {
            row["source_id"]: row for row in getattr(result, "manifest_rows", ())
        }
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "source_id": row["source_id"],
                        "cleaned_title": row["input_title"],
                        "product_url": manifest_by_source_id[row["source_id"]]["product_url"],
                        "search_date": manifest_by_source_id[row["source_id"]]["search_date"],
                    }
                    for row in resolver_rows
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("Resolver投入対象はありません。保留・除外の理由を確認してください。")

    st.subheader("保留・除外")
    if deferred_rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "raw_title": row["raw_title"],
                        "reason": row["exclusion_reason"],
                        "source_file": row["source_file"],
                    }
                    for row in deferred_rows
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.success("保留・除外行はありません。")


def _input_fingerprint(uploads: tuple[ResearchCsvInput, ...]) -> str:
    digest = hashlib.sha256()
    for upload in uploads:
        digest.update(upload.filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(upload.content)
        digest.update(b"\0")
    return digest.hexdigest()
