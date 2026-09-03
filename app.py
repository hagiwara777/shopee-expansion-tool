import os

import pandas as pd
import streamlit as st
from pathlib import Path

from modules.asin_resolver import (
    build_ai_prompt,
    build_retry_prompt,
    build_retry_rows,
    build_search_title,
    build_source_map,
    clean_ai_response,
    preview_candidates,
    retry_rows_fingerprint,
    rows_to_resolver_csv,
    summarize_preview,
    summarize_retry_rows,
    summarize_statuses,
    verify_selected_rows,
)
from modules.asin_resolver_evidence import (
    EvidenceValidationError,
    complete_batch,
    create_evidence_batch,
    generate_batch_id,
    load_and_validate_batch,
    pause_batch,
    persist_source_input_and_source_map,
    prepare_retry,
    record_initial_parse,
    record_initial_prompt,
    record_initial_response,
    record_resolver_export,
    record_retry_parse,
    record_retry_prompt,
    record_retry_response,
    restore_batch_state,
    resume_batch,
)
from modules.category_mapper_ui import render_category_mapper_tab
from modules.amazon_data_provider import (
    AmazonDataProviderConfigurationError,
    AmazonDataProviderError,
    CANOPY_TEST_PROVIDER,
    KEEPA_PROVIDER,
    create_amazon_data_client,
)
from modules.config import load_settings
from modules.direct_chat_assist import build_copy_button_html, is_valid_chatgpt_project_url
from modules.keepa_client import (
    SEARCH_MODE_LABELS,
    SEARCH_MODE_NOTES,
    estimate_token_usage,
    normalize_asin,
    planned_candidate_count,
)
from modules.listing_inventory_parser import (
    ListingInventoryParseError,
    parse_listing_inventory_csv,
)
from modules.ingredient_safety import (
    IngredientSafetyError,
    facts_for_candidate_rows,
    parse_ingredient_safety_sidecar,
    rows_to_ingredient_safety_sidecar,
    summarize_capture_statuses,
)
from modules.product_text_safety import (
    ProductTextSafetyError,
    facts_for_candidate_rows as product_text_facts_for_candidate_rows,
    parse_product_text_safety_sidecar,
    rows_to_product_text_safety_sidecar,
    summarize_capture_statuses as summarize_product_text_capture_statuses,
)
from modules.prelisting_candidate_csv import (
    PrelistingCandidateCsvError,
    expansion_rows_to_prelisting_candidates,
    parse_prelisting_candidate_csv,
    resolver_rows_to_prelisting_candidates,
    rows_to_prelisting_candidate_csv,
)
from modules.ph_image_safety import (
    ImageSafetyError, apply_image_safety, create_image_sidecar,
    parse_image_sidecar, prepare_image_safety,
)
from modules.ph_image_safety_ui import render_image_review
from modules.prelisting_gate import PrelistingGateError, evaluate_prelisting_gate
from modules.prelisting_gate_csv import (
    PrelistingGateCsvError,
    build_prelisting_gate_export_filenames,
    build_prelisting_gate_exports,
)
from modules.prelisting_gate_ui import (
    build_internal_shop_labels,
    build_prelisting_gate_preview_rows,
    build_prelisting_gate_fingerprint,
    clear_prelisting_gate_result,
    localize_prelisting_gate_preview_rows,
    safe_prelisting_gate_error_summary,
    summarize_prelisting_inventory,
    validate_inventory_file_duplicates,
    validate_shop_labels,
)
from modules.research_csv_adapter_ui import render_research_csv_adapter_tab


PAGE_OPTIONS = [1, 3, 5]
SEARCH_MODE_OPTIONS = ["strict", "standard", "broad", "category_research"]
RETRY_SESSION_KEYS = (
    "asin_resolver_retry_rows",
    "asin_resolver_retry_editor",
    "asin_resolver_retry_prompt",
    "asin_resolver_retry_prompt_display",
    "asin_resolver_retry_prompt_fingerprint",
)
EVIDENCE_SESSION_KEYS = (
    "asin_resolver_evidence_manifest_path",
    "asin_resolver_evidence_response_phase",
    "asin_resolver_evidence_source_entries",
)
EVIDENCE_RESTORABLE_SESSION_KEYS = (
    "asin_resolver_source_map",
    "asin_resolver_prompt",
    "asin_resolver_prompt_display",
    "asin_resolver_preview_rows",
    "asin_resolver_rows",
    "asin_resolver_input_line_count",
    "asin_resolver_selection_editor",
    "asin_resolver_product_names_input",
    "asin_resolver_evidence_source_input",
    "asin_resolver_evidence_next_action",
)
EVIDENCE_RUNTIME_ROOT = Path(__file__).resolve().parent / "outputs" / "asin_resolver_runs"
ASIN_RESOLVER_VERSION = "0.4.3"
PRELISTING_GATE_MARKETPLACES = ("SG", "PH")


def _clear_retry_state() -> None:
    for key in RETRY_SESSION_KEYS:
        st.session_state.pop(key, None)


def _clear_evidence_state() -> None:
    for key in EVIDENCE_SESSION_KEYS:
        st.session_state.pop(key, None)
    for key in EVIDENCE_RESTORABLE_SESSION_KEYS:
        st.session_state.pop(key, None)
    _clear_retry_state()


def _active_evidence_manifest_path() -> Path | None:
    value = st.session_state.get("asin_resolver_evidence_manifest_path")
    if not isinstance(value, str) or not value:
        return None
    return Path(value)


def _restore_evidence_session(manifest_path: Path) -> dict:
    state = restore_batch_state(manifest_path)
    _clear_evidence_state()
    st.session_state["asin_resolver_evidence_manifest_path"] = str(manifest_path)
    st.session_state["asin_resolver_evidence_source_entries"] = state["source_entries"]
    st.session_state["asin_resolver_evidence_next_action"] = state["next_action"]
    if "source_input" in state:
        st.session_state["asin_resolver_evidence_source_input"] = state["source_input"]
    st.session_state["asin_resolver_source_map"] = {
        entry["resolver_source_id"]: entry["original_title"]
        for entry in state["source_entries"]
    }
    if "initial_prompt" in state:
        st.session_state["asin_resolver_prompt"] = state["initial_prompt"]
        st.session_state["asin_resolver_prompt_display"] = state["initial_prompt"]
    checkpoint = state["manifest"]["last_completed_checkpoint"]
    if checkpoint in {"INITIAL_PROMPT_SAVED", "INITIAL_RESPONSE_SAVED", "INITIAL_PARSE_SAVED"}:
        st.session_state["asin_resolver_evidence_response_phase"] = "initial"
    if "retry_rows" in state:
        st.session_state["asin_resolver_retry_rows"] = state["retry_rows"]
    if "retry_prompt" in state:
        st.session_state["asin_resolver_retry_prompt"] = state["retry_prompt"]
        st.session_state["asin_resolver_retry_prompt_display"] = state["retry_prompt"]
    if checkpoint in {"RETRY_PROMPT_SAVED", "RETRY_RESPONSE_SAVED", "RETRY_PARSE_SAVED"}:
        st.session_state["asin_resolver_evidence_response_phase"] = "retry"
    if "retry_parse_rows" in state:
        st.session_state["asin_resolver_preview_rows"] = state["retry_parse_rows"]
        st.session_state["asin_resolver_evidence_response_phase"] = "retry"
    elif "initial_parse_rows" in state:
        st.session_state["asin_resolver_preview_rows"] = state["initial_parse_rows"]
        st.session_state["asin_resolver_evidence_response_phase"] = "initial"
    if "resolver_rows" in state:
        st.session_state["asin_resolver_rows"] = state["resolver_rows"]
        st.session_state["asin_resolver_evidence_response_phase"] = state[
            "resolver_export_phase"
        ]
    return state


def _render_direct_chat_assist(prompt_state_key: str, dom_id: str) -> None:
    prompt = st.session_state.get(prompt_state_key)
    if not isinstance(prompt, str) or not prompt:
        return

    settings = load_settings()
    project_url = settings.amazon_search_project_url
    project_url_is_valid = is_valid_chatgpt_project_url(project_url)

    st.caption(
        "1. 「ChatGPTへ貼るプロンプトをコピー」  2. コピーした全文をChatGPTの新規チャットへそのまま貼り付けて送信  "
        "3. 返答本文だけを「AI返答 → ASIN確認」へ貼り付け"
    )
    copy_column, project_column = st.columns(2)
    with copy_column:
        st.html(build_copy_button_html(prompt, dom_id), unsafe_allow_javascript=True)
    with project_column:
        if project_url_is_valid:
            st.link_button(
                "Amazon URL検索プロジェクトを開く",
                project_url,
                key=f"{dom_id}-project-link",
                icon=":material/open_in_new:",
                on_click="ignore",
                width="content",
            )
        else:
            st.button(
                "Amazon URL検索プロジェクトを開く",
                key=f"{dom_id}-project-link-disabled",
                icon=":material/open_in_new:",
                disabled=True,
                width="content",
            )
            st.caption("AMAZON_SEARCH_PROJECT_URLを正式フォルダの.envに設定してください。")


def _render_prelisting_gate_result(result, exports, *, source_type: str) -> None:
    """Render one current gate result without exposing audit-only evidence."""

    export_filenames = build_prelisting_gate_export_filenames(
        marketplace=result.marketplace,
        source_type=source_type,
    )

    st.caption(f"判定市場: {result.marketplace}")
    summary_columns = st.columns(4)
    summary_columns[0].metric("候補総数", result.candidate_count)
    summary_columns[1].metric("出品候補", result.eligible_count)
    summary_columns[2].metric("要確認", result.review_count)
    summary_columns[3].metric("除外", result.exclude_count)
    st.caption("出品候補: 現時点のルールで除外・要確認理由が見つからなかった商品")
    st.caption("要確認: 人間による確認が必要な商品")
    st.caption("除外: 出品候補から除外する商品")
    st.warning(
        "出品候補は安全・出品承認を保証するものではありません。"
        "現時点のルールで除外・要確認理由が見つからなかった商品です。"
    )

    result_tabs = st.tabs(["出品候補", "要確認", "除外"])
    result_counts = (
        ("ELIGIBLE", result.eligible_count),
        ("REVIEW", result.review_count),
        ("EXCLUDE", result.exclude_count),
    )
    for result_tab, (final_eligibility, count) in zip(result_tabs, result_counts):
        with result_tab:
            st.caption(f"{count}件")
            preview_rows = build_prelisting_gate_preview_rows(
                result,
                final_eligibility=final_eligibility,
            )
            if not preview_rows:
                st.info("該当商品はありません")
            else:
                st.dataframe(
                    localize_prelisting_gate_preview_rows(preview_rows),
                    hide_index=True,
                    width="stretch",
                )
                if count > len(preview_rows):
                    st.caption("先頭100件のみ表示。全件はCSVで確認してください")

    st.subheader("判定結果CSV")
    st.caption(
        "この出品可能CSVは保安ゲート判定結果です。\n"
        "外部出品ツールへの直接投入形式は未確認です。"
    )
    st.caption(
        "出品候補は安全・出品承認を保証するものではありません。\n"
        "現時点のルールで除外・要確認理由が見つからなかった商品です。"
    )
    if exports.eligible_csv is not None:
        st.download_button(
            label="出品可能CSVをダウンロード",
            data=exports.eligible_csv,
            file_name=export_filenames["eligible"],
            mime="text/csv",
            key="prelisting-gate-eligible-download",
            on_click="ignore",
            width="stretch",
        )
    if exports.review_csv is not None:
        st.download_button(
            label="要確認CSVをダウンロード",
            data=exports.review_csv,
            file_name=export_filenames["review"],
            mime="text/csv",
            key="prelisting-gate-review-download",
            on_click="ignore",
            width="stretch",
        )
    st.download_button(
        label="全件監査CSVをダウンロード",
        data=exports.audit_csv,
        file_name=export_filenames["audit"],
        mime="text/csv",
        key="prelisting-gate-audit-download",
        on_click="ignore",
        width="stretch",
    )


def _render_prelisting_gate_input_tab() -> None:
    """Render input parsing, gate execution, and current result presentation."""

    st.subheader("出品前保安ゲート")
    marketplace = st.selectbox(
        "対象市場",
        PRELISTING_GATE_MARKETPLACES,
        key="prelisting_gate_marketplace",
    )
    st.write(f"対象国: {marketplace}")

    expected_shop_count = st.number_input(
        f"{marketplace}で現在運用している全ショップ数",
        min_value=1,
        value=1,
        step=1,
        key="prelisting_gate_expected_shop_count",
    )
    st.caption(
        f"{marketplace}で現在運用している全ショップの既出品CSVを入力してください。"
        "不足すると既出品重複を見逃す可能性があります。"
    )

    candidate_file = st.file_uploader(
        "出品前保安ゲート用の候補CSV",
        type=["csv"],
        accept_multiple_files=False,
        key="prelisting_gate_candidate_file",
    )
    candidate_bytes = candidate_file.getvalue() if candidate_file is not None else None

    ingredient_safety_file = st.file_uploader(
        "Ingredient Safety Fact sidecar（任意）",
        type=["csv"],
        accept_multiple_files=False,
        key="prelisting_gate_ingredient_safety_file",
    )
    ingredient_safety_bytes = (
        ingredient_safety_file.getvalue() if ingredient_safety_file is not None else None
    )
    st.caption(
        "sidecar未指定でも従来どおり判定できます。Fact欠損はSafety PASSや成分不存在を意味しません。"
    )

    product_text_safety_file = st.file_uploader(
        "Product Text Safety Fact sidecar（PHでは必須）",
        type=["csv"],
        accept_multiple_files=False,
        key="prelisting_gate_product_text_safety_file",
    )
    product_text_safety_bytes = (
        product_text_safety_file.getvalue()
        if product_text_safety_file is not None
        else None
    )
    st.caption(
        "PHでsidecar未指定の場合は実行を停止します。sidecar内のNOT_CAPTURED / "
        "NOT_AVAILABLE / PROVIDER_UNSUPPORTEDは、それ自体ではBLOCKやREVIEWにしません。"
    )

    image_safety_file = None
    image_safety_bytes = None
    if marketplace == "PH":
        image_safety_file = st.file_uploader(
            "PH画像確認ファイル（必須）", type=["json"], accept_multiple_files=False,
            key="prelisting_gate_image_safety_file",
        )
        image_safety_bytes = image_safety_file.getvalue() if image_safety_file is not None else None
        st.caption("候補と一緒にダウンロードした画像確認ファイル、または同じ候補の画像確認記録を指定してください。")

    uploaded_inventory_files = st.file_uploader(
        f"{marketplace}全ショップの既出品CSV",
        type=["csv"],
        accept_multiple_files=True,
        key="prelisting_gate_inventory_files",
    )
    inventory_uploads = tuple(uploaded_inventory_files or ())
    inventory_files = tuple(
        (uploaded_file.name, uploaded_file.getvalue())
        for uploaded_file in inventory_uploads
    )

    configuration_errors: list[str] = []
    expected_shop_count_is_valid = (
        type(expected_shop_count) is int and expected_shop_count >= 1
    )
    if not expected_shop_count_is_valid:
        configuration_errors.append("全ショップ数は1以上の整数で入力してください。")

    file_validation = validate_inventory_file_duplicates(inventory_files)
    configuration_errors.extend(file_validation.errors)
    labels = build_internal_shop_labels(marketplace, len(inventory_files))
    label_validation = validate_shop_labels(labels)
    if not label_validation.is_valid:
        configuration_errors.extend(label_validation.errors)

    fingerprint_shop_count = expected_shop_count if expected_shop_count_is_valid else 0
    current_fingerprint = build_prelisting_gate_fingerprint(
        marketplace=marketplace,
        expected_shop_count=fingerprint_shop_count,
        candidate_filename=candidate_file.name if candidate_file is not None else None,
        candidate_content=candidate_bytes,
        ingredient_safety_filename=(
            ingredient_safety_file.name if ingredient_safety_file is not None else None
        ),
        ingredient_safety_content=ingredient_safety_bytes,
        product_text_safety_filename=(
            product_text_safety_file.name if product_text_safety_file is not None else None
        ),
        product_text_safety_content=product_text_safety_bytes,
        image_safety_content=image_safety_bytes,
        inventory_files=(
            (filename, content, label)
            for (filename, content), label in zip(inventory_files, labels, strict=True)
        ),
    )
    saved_fingerprint = st.session_state.get("prelisting_gate_fingerprint")
    if saved_fingerprint is not None and saved_fingerprint != current_fingerprint:
        clear_prelisting_gate_result(st.session_state)

    if len(inventory_files) != expected_shop_count:
        configuration_errors.append(
            "既出品CSVの数が全ショップ数と一致していません。"
        )
    if marketplace == "PH" and product_text_safety_file is None:
        configuration_errors.append(
            "PHではCandidate CSVと対応するProduct Text Safety sidecarが必要です。"
        )

    if marketplace == "PH" and image_safety_file is None:
        configuration_errors.append("PHでは候補CSVに対応する画像確認ファイルが必要です。")

    candidate_result = None
    candidate_parse_error = False
    if candidate_file is None:
        configuration_errors.append("候補CSVをアップロードしてください。")
    else:
        try:
            candidate_result = parse_prelisting_candidate_csv(
                candidate_bytes,
                filename=candidate_file.name,
            )
        except PrelistingCandidateCsvError:
            candidate_parse_error = True

    ingredient_safety_result = None
    ingredient_safety_parse_error = False
    if ingredient_safety_file is not None and candidate_result is not None:
        try:
            ingredient_safety_result = parse_ingredient_safety_sidecar(
                ingredient_safety_bytes,
                filename=ingredient_safety_file.name,
                candidate_content=candidate_bytes,
                candidates=candidate_result,
            )
        except IngredientSafetyError:
            ingredient_safety_parse_error = True
    elif ingredient_safety_file is not None:
        ingredient_safety_parse_error = True

    product_text_safety_result = None
    product_text_safety_parse_error = False
    if product_text_safety_file is not None and candidate_result is not None:
        try:
            product_text_safety_result = parse_product_text_safety_sidecar(
                product_text_safety_bytes,
                filename=product_text_safety_file.name,
                candidate_content=candidate_bytes,
                candidates=candidate_result,
            )
        except (ProductTextSafetyError, ImageSafetyError):
            product_text_safety_parse_error = True
    elif product_text_safety_file is not None:
        product_text_safety_parse_error = True

    image_safety_result = None
    image_safety_parse_error = False
    if image_safety_file is not None and candidate_result is not None:
        try:
            image_safety_result = parse_image_sidecar(
                image_safety_bytes, candidate_content=candidate_bytes, candidates=candidate_result,
            )
        except (ImageSafetyError, TypeError, ValueError):
            image_safety_parse_error = True
    elif image_safety_file is not None:
        image_safety_parse_error = True

    inventory_results = []
    inventory_parse_error = False
    if inventory_files and file_validation.is_valid and label_validation.is_valid:
        for (filename, content), shop_label in zip(
            inventory_files,
            label_validation.display_labels,
            strict=True,
        ):
            try:
                inventory_results.append(
                    parse_listing_inventory_csv(
                        content,
                        filename=filename,
                        marketplace=marketplace,
                        shop_label=shop_label,
                    )
                )
            except ListingInventoryParseError:
                inventory_parse_error = True
                break

    preflight_ready = (
        not configuration_errors
        and not candidate_parse_error
        and not inventory_parse_error
        and not ingredient_safety_parse_error
        and not product_text_safety_parse_error
        and not image_safety_parse_error
        and candidate_result is not None
        and len(inventory_results) == len(inventory_files)
        and len(inventory_files) == expected_shop_count
    )
    if not preflight_ready:
        clear_prelisting_gate_result(st.session_state)

    if configuration_errors:
        st.warning(safe_prelisting_gate_error_summary("configuration"))
        for error in dict.fromkeys(configuration_errors):
            st.caption(error)
    if candidate_parse_error:
        st.error(safe_prelisting_gate_error_summary("candidate"))
    if inventory_parse_error:
        st.error(safe_prelisting_gate_error_summary("inventory"))
    if ingredient_safety_parse_error:
        st.error(
            "Ingredient Safety sidecarを検証できません。Candidate SHA、ASIN集合、schema、JSONを確認してください。"
        )
    if product_text_safety_parse_error:
        st.error(
            "Product Text Safety sidecarを検証できません。Candidate SHA、ASIN集合、schema、JSONを確認してください。"
        )

    if image_safety_parse_error:
        st.error("画像確認ファイルを検証できません。候補との対応、画像情報、判断記録を確認してください。")

    input_ready = preflight_ready
    if input_ready:
        preflight_summary = summarize_prelisting_inventory(
            inventory_results,
            expected_shop_count=expected_shop_count,
            uploaded_file_count=len(inventory_files),
        )
        candidate_summary = st.columns(3)
        candidate_summary[0].metric("候補CSV行数", candidate_result.data_row_count)
        candidate_summary[1].metric("候補CSV schema version", candidate_result.schema_version)
        candidate_summary[2].metric("候補CSV source type", candidate_result.source_type)

        inventory_summary = st.columns(3)
        inventory_summary[0].metric("対象ショップ数", preflight_summary.expected_shop_count)
        inventory_summary[1].metric("解析済み既出品CSV数", preflight_summary.parsed_file_count)
        inventory_summary[2].metric(
            "既出品ユニークASIN数",
            preflight_summary.unique_existing_asin_count,
        )
        st.caption(
            "既出品行数: "
            f"{preflight_summary.existing_listing_row_count} / "
            f"根拠レコード数: {preflight_summary.evidence_count}"
        )
        st.success(
            "入力準備が完了しました。\n"
            "出品前チェックを実行できます。"
        )
        if ingredient_safety_result is None:
            st.info("Ingredient Safety sidecar: 未指定（legacy互換判定）")
        else:
            capture_summary = summarize_capture_statuses(ingredient_safety_result)
            st.caption(
                "Ingredient Safety sidecar: "
                f"CAPTURED {capture_summary['CAPTURED']} / "
                f"NOT_CAPTURED {capture_summary['NOT_CAPTURED']} / "
                f"PROVIDER_UNSUPPORTED {capture_summary['PROVIDER_UNSUPPORTED']}"
            )
        if product_text_safety_result is None:
            st.info("Product Text Safety sidecar: 未指定（SG legacy互換判定）")
        else:
            product_text_summary = summarize_product_text_capture_statuses(
                product_text_safety_result
            )
            st.caption(
                "Product Text Safety sidecar: "
                f"CAPTURED {product_text_summary['CAPTURED']} / "
                f"NOT_CAPTURED {product_text_summary['NOT_CAPTURED']} / "
                f"NOT_AVAILABLE {product_text_summary['NOT_AVAILABLE']} / "
                f"PROVIDER_UNSUPPORTED {product_text_summary['PROVIDER_UNSUPPORTED']}"
            )

    run_gate_clicked = st.button(
        "出品前チェックを実行",
        disabled=not input_ready,
        type="primary",
        width="stretch",
    )
    if run_gate_clicked:
        clear_prelisting_gate_result(st.session_state)
        try:
            with st.spinner("出品前保安ゲートを判定しています..."):
                gate_result = evaluate_prelisting_gate(
                    candidate_result,
                    inventory_results,
                    marketplace=marketplace,
                    expected_shop_count=expected_shop_count,
                    ingredient_safety=ingredient_safety_result,
                    product_text_safety=product_text_safety_result,
                )
                base_result = gate_result
                if marketplace == "PH":
                    image_safety_result = prepare_image_safety(base_result, image_safety_result, candidate_bytes)
                    gate_result = apply_image_safety(base_result, image_safety_result, candidate_bytes)
                exports = build_prelisting_gate_exports(gate_result)
        except PrelistingGateError:
            clear_prelisting_gate_result(st.session_state)
            st.error(safe_prelisting_gate_error_summary("gate"))
        except PrelistingGateCsvError:
            clear_prelisting_gate_result(st.session_state)
            st.error(safe_prelisting_gate_error_summary("export"))
        except ImageSafetyError:
            clear_prelisting_gate_result(st.session_state)
            st.error("画像確認を続行できません。画像確認ファイル、API認証・契約・設定を確認してください。Gateを停止しました。")
        except Exception:
            clear_prelisting_gate_result(st.session_state)
            st.error(safe_prelisting_gate_error_summary("unexpected"))
        else:
            st.session_state["prelisting_gate_base_result"] = base_result
            st.session_state["prelisting_gate_image_sidecar"] = image_safety_result
            st.session_state["prelisting_gate_result"] = gate_result
            st.session_state["prelisting_gate_exports"] = exports
            st.session_state["prelisting_gate_fingerprint"] = current_fingerprint

    saved_result = st.session_state.get("prelisting_gate_result")
    saved_exports = st.session_state.get("prelisting_gate_exports")
    saved_fingerprint = st.session_state.get("prelisting_gate_fingerprint")
    if saved_result is not None and saved_result.marketplace != marketplace:
        clear_prelisting_gate_result(st.session_state)
        saved_result = None
        saved_exports = None
        saved_fingerprint = None
    result_is_current = (
        input_ready
        and saved_result is not None
        and saved_exports is not None
        and saved_fingerprint == current_fingerprint
        and saved_result.marketplace == marketplace
    )
    if result_is_current:
        try:
            if marketplace == "PH":
                base_result = st.session_state["prelisting_gate_base_result"]
                image_sidecar = st.session_state["prelisting_gate_image_sidecar"]
                image_sidecar = prepare_image_safety(base_result, image_sidecar, candidate_bytes)
                image_sidecar = render_image_review(base_result, image_sidecar, candidate_bytes)
                saved_result = apply_image_safety(base_result, image_sidecar, candidate_bytes)
                saved_exports = build_prelisting_gate_exports(saved_result)
                st.session_state["prelisting_gate_image_sidecar"] = image_sidecar
                st.session_state["prelisting_gate_result"] = saved_result
                st.session_state["prelisting_gate_exports"] = saved_exports
            _render_prelisting_gate_result(
                saved_result,
                saved_exports,
                source_type=candidate_result.source_type,
            )
        except ImageSafetyError:
            clear_prelisting_gate_result(st.session_state)
            st.error("画像確認を続行できません。画像確認ファイル、API認証・契約・設定を確認してください。Gateを停止しました。")
        except Exception:
            clear_prelisting_gate_result(st.session_state)
            st.error(safe_prelisting_gate_error_summary("unexpected"))


st.set_page_config(page_title="Shopee Expansion Tool Ver1", layout="centered")

st.title("Shopee Expansion Tool Ver1")

try:
    amazon_settings = load_settings()
except AmazonDataProviderConfigurationError as exc:
    st.error(str(exc))
    st.stop()

previous_provider = st.session_state.get("active_amazon_data_provider")
if previous_provider and previous_provider != amazon_settings.amazon_data_provider:
    st.session_state.pop("result", None)
    st.session_state.pop("asin_resolver_rows", None)
st.session_state["active_amazon_data_provider"] = amazon_settings.amazon_data_provider

if amazon_settings.amazon_data_provider == CANOPY_TEST_PROVIDER:
    st.warning("Amazon data provider: Canopy TEST")

expansion_tab, resolver_tab, prelisting_gate_tab, category_mapper_tab = st.tabs(
    ["ASIN Expansion", "ASIN Resolver", "出品前保安ゲート", "Category Mapper"]
)

with expansion_tab:
    with st.form("search_form", clear_on_submit=False):
        asin_input = st.text_input("ASIN", placeholder="B07TSC47PH")
        if amazon_settings.amazon_data_provider == KEEPA_PROVIDER:
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
        else:
            search_mode = "canopy_test"
            search_pages = 1
            st.caption(
                "Canopy TEST: 起点商品のbrandでJP検索し、1ページだけから"
                "brand完全一致候補を最大5件確認します（最大7 requests、retryなし）。"
            )
        search_clicked = st.form_submit_button(
            "検索開始",
            type="primary",
            width="stretch",
        )

    if search_clicked:
        st.session_state["result"] = None

        try:
            source_asin = normalize_asin(asin_input)
            client = create_amazon_data_client(amazon_settings)

            if amazon_settings.amazon_data_provider == KEEPA_PROVIDER:
                with st.spinner(
                    "Keepa APIから候補ASINを取得しています。"
                    "トークン不足時は自動で回復待ちします..."
                ):
                    result = client.find_related_products(
                        source_asin=source_asin,
                        search_pages=search_pages,
                        search_mode=search_mode,
                    )
            else:
                with st.spinner("Canopy TESTで候補ASINを確認しています（retryなし）..."):
                    result = client.find_related_products(source_asin=source_asin)

        except ValueError as exc:
            st.error(str(exc))
        except AmazonDataProviderError as exc:
            st.error(str(exc))
        except Exception:
            st.error(
                "想定外のエラーが発生しました。アプリを再起動し、同じASINで再実行してください。"
            )
        else:
            st.session_state["result"] = result

    result = st.session_state.get("result")

    if result:
        if result.final_display_count:
            st.success(f"{result.final_display_count}件の候補ASINを取得しました。")
        elif amazon_settings.amazon_data_provider == CANOPY_TEST_PROVIDER:
            st.warning("候補ASINは0件でした。Canopy TESTのbrand完全一致候補はありません。")
        else:
            st.warning("候補ASINは0件でした。検索条件をstandardまたはbroadに広げて再検索してください。")

        st.write(f"取得したbrand: {result.brand}")
        if amazon_settings.amazon_data_provider == KEEPA_PROVIDER:
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
        else:
            st.write(f"JP検索結果ASIN数: {result.raw_candidate_count}件")
            st.write(f"詳細取得失敗数: {result.detail_failed_count}件")
            st.write(f"brand不一致除外数: {result.brand_mismatch_excluded_count}件")
            st.write(f"重複除外数: {result.duplicate_removed_count}件")
            st.write(f"自己ASIN除外数: {result.self_excluded_count}件")
            st.write(f"不正ASIN除外数: {result.invalid_excluded_count}件")
            st.write(f"最終表示件数: {result.final_display_count}件")
            st.write(f"request数: {result.request_count} / 7")
            st.caption("Canopy結果はKeepa SQLite cacheへ保存しません。")

        try:
            expansion_prelisting_rows = expansion_rows_to_prelisting_candidates(result.rows)
            expansion_prelisting_csv = rows_to_prelisting_candidate_csv(expansion_prelisting_rows)
            expansion_safety_facts = facts_for_candidate_rows(
                expansion_prelisting_rows,
                result.rows,
            )
            expansion_safety_sidecar = rows_to_ingredient_safety_sidecar(
                expansion_prelisting_csv,
                expansion_prelisting_rows,
                expansion_safety_facts,
            )
            expansion_product_text_facts = product_text_facts_for_candidate_rows(
                expansion_prelisting_rows,
                result.rows,
            )
            expansion_product_text_sidecar = rows_to_product_text_safety_sidecar(
                expansion_prelisting_csv,
                expansion_prelisting_rows,
                expansion_product_text_facts,
            )
            expansion_image_sidecar = create_image_sidecar(
                expansion_prelisting_csv, expansion_prelisting_rows, result.rows,
            )
        except PrelistingCandidateCsvError:
            st.error(
                "出品前保安ゲート用CSVを生成できませんでした。候補データを確認してください。"
            )
        except IngredientSafetyError:
            st.error(
                "出品前保安ゲート用CSVを生成できませんでした。候補データを確認してください。"
            )
        except (ProductTextSafetyError, ImageSafetyError):
            st.error(
                "出品前保安ゲート用CSVを生成できませんでした。候補データを確認してください。"
            )
        else:
            st.caption(
                "このCSVは外部出品ツールへ直接渡さず、対象市場（SG／PH）を選んだ出品前保安ゲートの候補CSVとして使用してください。"
            )
            st.download_button(
                label="出品前保安ゲート用CSVダウンロード",
                data=expansion_prelisting_csv,
                file_name=f"prelisting_candidates_expansion_{result.source_asin}.csv",
                mime="text/csv",
                key="prelisting-expansion-download",
                width="stretch",
            )
            st.download_button(
                label="Ingredient Safety Fact sidecarダウンロード",
                data=expansion_safety_sidecar,
                file_name=f"ingredient_safety_facts_expansion_{result.source_asin}.csv",
                mime="text/csv",
                key="ingredient-safety-expansion-download",
                width="stretch",
            )
            st.download_button(
                label="Product Text Safety Fact sidecarダウンロード",
                data=expansion_product_text_sidecar,
                file_name=f"product_text_safety_facts_expansion_{result.source_asin}.csv",
                mime="text/csv",
                key="product-text-safety-expansion-download",
                width="stretch",
            )
            st.download_button(
                label="PH画像確認ファイルをダウンロード", data=expansion_image_sidecar,
                file_name=f"ph_image_safety_expansion_{result.source_asin}.json",
                mime="application/json", key="ph-image-safety-expansion-download", width="stretch",
            )
        st.dataframe(pd.DataFrame(result.rows), width="stretch", hide_index=True)

with resolver_tab:
    st.subheader("ASIN Resolver Tool Ver0.4.3")
    if os.environ.get("ASIN_RESOLVER_EVIDENCE_UI_ENABLED") == "1":
        with st.expander("Evidence Batch（PH固定30件基準実行用）", expanded=True):
            active_manifest_path = _active_evidence_manifest_path()
            if active_manifest_path is None:
                st.warning(
                    "現在はlegacy／非証跡モードです。Evidence Manifest、source map、再開保証を"
                    "持たないため、formalな固定30件基準実行には使用できません。"
                )
            else:
                st.success(f"Evidence Batch: {active_manifest_path.parent.name}")

            with st.form("asin_resolver_evidence_batch_form", clear_on_submit=False):
                recorded_formal_commit = st.text_input(
                    "記録する formal main commit（40桁SHA、必須）",
                    key="asin_resolver_recorded_formal_commit",
                )
                st.caption(
                    "承認値は環境変数 ASIN_RESOLVER_APPROVED_FORMAL_MAIN_COMMIT からのみ取得します。"
                )
                create_batch_clicked = st.form_submit_button("新規 Evidence Batchを作成")

            if create_batch_clicked:
                try:
                    manifest_path = create_evidence_batch(
                        EVIDENCE_RUNTIME_ROOT,
                        batch_id=generate_batch_id(),
                        formal_main_commit=recorded_formal_commit,
                        resolver_version=ASIN_RESOLVER_VERSION,
                    )
                    _clear_evidence_state()
                    _restore_evidence_session(manifest_path)
                    st.success(f"Evidence Batchを作成しました: {manifest_path.parent.name}")
                except EvidenceValidationError as exc:
                    st.error(f"Evidence Batchを作成せず停止しました: {exc}")

            resume_path_text = st.text_input(
                "既存 Evidence Manifest のローカルパス",
                key="asin_resolver_evidence_resume_path",
                placeholder=".../outputs/asin_resolver_runs/<batch_id>/evidence_manifest.json",
            )
            if st.button("Evidence Manifestを検証して再開", width="stretch"):
                try:
                    manifest_path = Path(resume_path_text)
                    manifest = load_and_validate_batch(manifest_path)
                    if manifest["batch_status"] == "PAUSED":
                        resume_batch(manifest_path)
                    _restore_evidence_session(manifest_path)
                    st.success(
                        "Evidence Manifestを検証しました。"
                        f"次のcheckpoint: {manifest['resume_from_checkpoint']}"
                    )
                except (EvidenceValidationError, OSError) as exc:
                    st.error(f"Evidence Manifestを変更せず停止しました: {exc}")

            active_manifest_path = _active_evidence_manifest_path()
            if active_manifest_path is not None:
                try:
                    active_manifest = load_and_validate_batch(active_manifest_path)
                except (EvidenceValidationError, OSError) as exc:
                    st.error(f"Evidence Batchを変更せず停止しました: {exc}")
                    _clear_evidence_state()
                else:
                    status_columns = st.columns(3)
                    status_columns[0].metric("batch status", active_manifest["batch_status"])
                    status_columns[1].metric(
                        "last checkpoint", active_manifest["last_completed_checkpoint"]
                    )
                    status_columns[2].metric(
                        "resume checkpoint", active_manifest["resume_from_checkpoint"]
                    )
                    artifact_rows = [
                        {
                            "artifact_id": artifact["artifact_id"],
                            "filename": artifact["filename"],
                            "sha256": artifact["sha256"],
                            "producer": artifact["producer"],
                            "acceptance_status": artifact["acceptance_status"],
                            "storage_alias": artifact["storage_alias"],
                            "parent_artifact_ids": "; ".join(artifact["parent_artifact_ids"]),
                        }
                        for artifact in active_manifest["artifacts"]
                    ]
                    if artifact_rows:
                        st.dataframe(pd.DataFrame(artifact_rows), hide_index=True, width="stretch")
                    action_columns = st.columns(2)
                    if action_columns[0].button(
                        "Evidence Batchを一時停止",
                        width="stretch",
                        disabled=active_manifest["last_completed_checkpoint"] == "COMPLETED",
                    ):
                        try:
                            pause_batch(active_manifest_path)
                            st.info("Evidence BatchをPAUSEDとして保存しました。")
                        except EvidenceValidationError as exc:
                            st.error(f"Evidence Batchを変更せず停止しました: {exc}")
                    if action_columns[1].button(
                        "Evidence Batchを完了", width="stretch", disabled=active_manifest[
                            "last_completed_checkpoint"
                        ] != "EXPORT_SAVED"
                    ):
                        try:
                            complete_batch(active_manifest_path)
                            st.session_state["asin_resolver_evidence_next_action"] = "view_only"
                            st.success("Evidence BatchをCOMPLETEDとして保存しました。")
                        except EvidenceValidationError as exc:
                            st.error(f"Evidence Batchを変更せず停止しました: {exc}")

    active_evidence_path = _active_evidence_manifest_path()
    evidence_next_action = st.session_state.get("asin_resolver_evidence_next_action")
    evidence_prompt_action_allowed = active_evidence_path is None or evidence_next_action in {
        "save_source_input_and_source_map",
        "generate_initial_prompt",
    }
    evidence_response_action_allowed = active_evidence_path is None or evidence_next_action in {
        "enter_initial_response",
        "parse_saved_initial_response",
        "enter_retry_response",
        "parse_saved_retry_response",
    }
    evidence_retry_action_allowed = active_evidence_path is None or evidence_next_action in {
        "prepare_retry_or_export",
        "generate_retry_prompt",
    }
    evidence_export_action_allowed = active_evidence_path is None or evidence_next_action in {
        "prepare_retry_or_export",
        "export",
    }

    if active_evidence_path is not None and isinstance(evidence_next_action, str):
        st.info(f"Evidence Batch再開ガイド: 次の操作は `{evidence_next_action}` です。")

    prompt_tab, verify_tab, retry_tab, research_csv_adapter_tab = st.tabs(
        [
            "商品名 → AI用プロンプト",
            "AI返答 → ASIN確認",
            "不明商品 → 再検索プロンプト",
            "Shopee調査CSV取込",
        ]
    )

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
                key="asin_resolver_product_names_input",
            )
            prompt_clicked = st.form_submit_button(
                "AI用プロンプト生成",
                type="primary",
                width="stretch",
                disabled=not evidence_prompt_action_allowed,
            )

        if prompt_clicked:
            try:
                active_manifest_path = _active_evidence_manifest_path()
                prompt_source_input: str | None = None
                if active_manifest_path is not None:
                    active_manifest = load_and_validate_batch(active_manifest_path)
                    checkpoint = active_manifest["last_completed_checkpoint"]
                    if checkpoint == "BATCH_CREATED":
                        if not product_names_text.strip():
                            st.warning("商品名リストを入力してください。")
                        else:
                            entries = persist_source_input_and_source_map(
                                active_manifest_path,
                                product_names_text,
                                search_title_builder=build_search_title,
                            )
                            prompt_source_input = product_names_text
                            st.session_state["asin_resolver_evidence_next_action"] = (
                                "generate_initial_prompt"
                            )
                    elif checkpoint == "SOURCE_MAP_SAVED":
                        entries = st.session_state.get("asin_resolver_evidence_source_entries", [])
                        prompt_source_input = st.session_state.get(
                            "asin_resolver_evidence_source_input", ""
                        )
                        if not prompt_source_input:
                            raise EvidenceValidationError("saved source input is unavailable for resume")
                    else:
                        raise EvidenceValidationError(
                            f"prompt generation is not allowed at checkpoint {checkpoint}"
                        )
                elif product_names_text.strip():
                    entries = []
                    prompt_source_input = product_names_text
                else:
                    st.warning("商品名リストを入力してください。")

                if prompt_source_input is None:
                    pass
                else:
                    if active_manifest_path is not None:
                        source_map = {
                            (
                                entry.resolver_source_id
                                if hasattr(entry, "resolver_source_id")
                                else entry["resolver_source_id"]
                            ): (
                                entry.original_title
                                if hasattr(entry, "original_title")
                                else entry["original_title"]
                            )
                            for entry in entries
                        }
                        st.session_state["asin_resolver_evidence_source_entries"] = [
                            entry.to_record() if hasattr(entry, "to_record") else entry
                            for entry in entries
                        ]
                    else:
                        source_map = build_source_map(prompt_source_input)
                    generated_prompt = build_ai_prompt(prompt_source_input)
                    if active_manifest_path is not None:
                        record_initial_prompt(active_manifest_path, generated_prompt)
                        st.session_state["asin_resolver_evidence_response_phase"] = "initial"
                        st.session_state["asin_resolver_evidence_next_action"] = (
                            "enter_initial_response"
                        )
                    st.session_state["asin_resolver_prompt"] = generated_prompt
                    st.session_state["asin_resolver_prompt_display"] = generated_prompt
                    st.session_state["asin_resolver_source_map"] = source_map
                    st.session_state["asin_resolver_preview_rows"] = []
                    st.session_state["asin_resolver_rows"] = []
                    st.session_state["asin_resolver_input_line_count"] = 0
                    st.session_state.pop("asin_resolver_selection_editor", None)
                    _clear_retry_state()
            except EvidenceValidationError as exc:
                st.error(f"Evidence Batchを変更せず停止しました: {exc}")

        st.text_area(
            "生成されたプロンプト",
            height=320,
            key="asin_resolver_prompt_display",
        )
        _render_direct_chat_assist(
            "asin_resolver_prompt_display",
            "asin-resolver-initial-prompt-copy",
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
                    "source_id\tinput_title\tamazon_url\n"
                    "R0001\tAnua Heartleaf 77 Toner 250ml\thttps://www.amazon.co.jp/dp/B08C4Z1XF4\n"
                    "R0002\tUnknown Product\t不明"
                ),
                height=220,
            )
            parse_clicked = st.form_submit_button(
                "AI返答を解析",
                type="primary",
                width="stretch",
                disabled=not evidence_response_action_allowed,
            )

        if parse_clicked:
            st.session_state["asin_resolver_preview_rows"] = []
            st.session_state["asin_resolver_rows"] = []
            st.session_state["asin_resolver_input_line_count"] = 0
            st.session_state.pop("asin_resolver_selection_editor", None)
            _clear_retry_state()

            active_manifest_path = _active_evidence_manifest_path()
            use_saved_response = False
            if not ai_response_text.strip() and active_manifest_path is not None:
                restored = restore_batch_state(active_manifest_path)
                checkpoint = restored["manifest"]["last_completed_checkpoint"]
                if checkpoint == "INITIAL_RESPONSE_SAVED":
                    ai_response_text = restored["initial_ai_response"]
                    st.session_state["asin_resolver_evidence_response_phase"] = "initial"
                    use_saved_response = True
                elif checkpoint == "RETRY_RESPONSE_SAVED":
                    ai_response_text = restored["retry_ai_response"]
                    st.session_state["asin_resolver_evidence_response_phase"] = "retry"
                    use_saved_response = True

            if not ai_response_text.strip():
                st.warning("ChatGPT / Geminiの返答を入力してください。")
            else:
                try:
                    response_phase = st.session_state.get(
                        "asin_resolver_evidence_response_phase", "initial"
                    )
                    if active_manifest_path is not None and not use_saved_response:
                        if response_phase == "initial":
                            record_initial_response(active_manifest_path, ai_response_text)
                            st.session_state["asin_resolver_evidence_next_action"] = (
                                "parse_saved_initial_response"
                            )
                        elif response_phase == "retry":
                            record_retry_response(active_manifest_path, ai_response_text)
                            st.session_state["asin_resolver_evidence_next_action"] = (
                                "parse_saved_retry_response"
                            )
                        else:
                            raise EvidenceValidationError("unknown Evidence response phase")
                    preview_rows = preview_candidates(
                        ai_response_text,
                        st.session_state.get("asin_resolver_source_map"),
                    )
                    if active_manifest_path is not None:
                        candidate_csv = rows_to_resolver_csv(preview_rows)
                        if response_phase == "initial":
                            record_initial_parse(active_manifest_path, preview_rows, candidate_csv)
                            st.session_state["asin_resolver_evidence_next_action"] = (
                                "prepare_retry_or_export"
                            )
                        else:
                            record_retry_parse(active_manifest_path, preview_rows, candidate_csv)
                            st.session_state["asin_resolver_evidence_next_action"] = "export"
                    st.session_state["asin_resolver_preview_rows"] = preview_rows
                    st.session_state["asin_resolver_input_line_count"] = len(
                        clean_ai_response(ai_response_text).splitlines()
                    )
                    if preview_rows:
                        st.success(f"{len(preview_rows)}件の候補行を解析しました。")
                    else:
                        st.warning("確認対象または候補として残す行はありませんでした。")
                except EvidenceValidationError as exc:
                    st.error(f"Evidence Batchを変更せず停止しました: {exc}")

        preview_rows = st.session_state.get("asin_resolver_preview_rows", [])
        if preview_rows:
            editable_preview = st.data_editor(
                pd.DataFrame(preview_rows),
                column_config={
                    "selected": st.column_config.CheckboxColumn("確認対象"),
                    "row_id": None,
                    "source_id_known": None,
                },
                disabled=[
                    "source_id",
                    "input_title",
                    "amazon_url",
                    "asin",
                    "parse_status",
                    "status",
                    "verification",
                    "note",
                    "row_id",
                    "source_id_known",
                ],
                hide_index=True,
                key="asin_resolver_selection_editor",
                width="stretch",
            )
            selected_preview_rows = editable_preview.to_dict("records")
            preview_summary = summarize_preview(selected_preview_rows)
            input_line_count = st.session_state.get("asin_resolver_input_line_count", 0)
            verified_count = sum(
                1
                for row in st.session_state.get("asin_resolver_rows", [])
                if row.get("verification") != "NOT_CHECKED"
            )
            st.caption(
                f"解析対象入力行数: {input_line_count}件（空行・コードブロックを除く）。"
                f"選択されたAmazon商品確認対象ASIN数: {preview_summary['selected_unique_asins']}件"
                "（重複を除く）。"
                "プレビューではAmazon data providerを呼びません。"
                "AI返答を変更した場合は、もう一度解析してください。"
            )
            preview_cols = st.columns(3)
            preview_cols[0].metric("抽出候補行数", preview_summary["extracted_asin_rows"])
            preview_cols[1].metric("選択候補行数", preview_summary["selected_rows"])
            preview_cols[2].metric(
                "選択されたユニークASIN数", preview_summary["selected_unique_asins"]
            )
            preview_detail_cols = st.columns(2)
            preview_detail_cols[0].metric("選択解除件数", preview_summary["deselected_rows"])
            preview_detail_cols[1].metric("Amazon商品確認済み件数", verified_count)

            verify_clicked = st.button(
                "選択したASINをAmazon商品として確認",
                type="primary",
                width="stretch",
                disabled=(
                    preview_summary["selected_unique_asins"] == 0
                    or not evidence_export_action_allowed
                ),
            )

            if verify_clicked:
                st.session_state["asin_resolver_rows"] = []
                try:
                    client = create_amazon_data_client(amazon_settings)
                    with st.spinner("Amazon data providerでASINの実在確認をしています..."):
                        verified_rows = verify_selected_rows(
                            selected_preview_rows,
                            client,
                        )
                        active_manifest_path = _active_evidence_manifest_path()
                        if active_manifest_path is not None:
                            response_phase = st.session_state.get(
                                "asin_resolver_evidence_response_phase", "initial"
                            )
                            record_resolver_export(
                                active_manifest_path,
                                rows_to_resolver_csv(verified_rows),
                                source_phase=response_phase,
                            )
                            st.session_state["asin_resolver_evidence_next_action"] = (
                                "complete_or_view"
                            )
                    st.session_state["asin_resolver_rows"] = verified_rows
                except AmazonDataProviderError as exc:
                    st.error(str(exc))
                except EvidenceValidationError as exc:
                    st.error(f"Evidence Batchを変更せず停止しました: {exc}")
                except Exception:
                    st.error(
                        "想定外のエラーが発生しました。アプリを再起動し、同じ内容で再実行してください。"
                    )

        resolver_rows = st.session_state.get("asin_resolver_rows", [])
        if resolver_rows:
            summary = summarize_statuses(resolver_rows)
            st.success(f"{len(resolver_rows)}件のAmazon商品確認を完了しました。")
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
            try:
                resolver_prelisting = resolver_rows_to_prelisting_candidates(resolver_rows)
                st.write(f"保安ゲートCSV対象件数: {resolver_prelisting.eligible_row_count}件")
                st.write(
                    "未確認・不明・エラー等による除外件数: "
                    f"{resolver_prelisting.excluded_row_count}件"
                )
                if resolver_prelisting.eligible_row_count > 0:
                    resolver_prelisting_csv = rows_to_prelisting_candidate_csv(
                        resolver_prelisting.output_rows
                    )
                    resolver_safety_facts = facts_for_candidate_rows(
                        resolver_prelisting.output_rows,
                        resolver_rows,
                    )
                    resolver_safety_sidecar = rows_to_ingredient_safety_sidecar(
                        resolver_prelisting_csv,
                        resolver_prelisting.output_rows,
                        resolver_safety_facts,
                    )
                    resolver_product_text_facts = product_text_facts_for_candidate_rows(
                        resolver_prelisting.output_rows,
                        resolver_rows,
                    )
                    resolver_product_text_sidecar = rows_to_product_text_safety_sidecar(
                        resolver_prelisting_csv,
                        resolver_prelisting.output_rows,
                        resolver_product_text_facts,
                    )
                    resolver_image_sidecar = create_image_sidecar(
                        resolver_prelisting_csv, resolver_prelisting.output_rows, resolver_rows,
                    )
            except PrelistingCandidateCsvError:
                st.error(
                    "出品前保安ゲート用CSVを生成できませんでした。確認結果を確認してください。"
                )
            except IngredientSafetyError:
                st.error(
                    "出品前保安ゲート用CSVを生成できませんでした。確認結果を確認してください。"
                )
            except (ProductTextSafetyError, ImageSafetyError):
                st.error(
                    "出品前保安ゲート用CSVを生成できませんでした。確認結果を確認してください。"
                )
            else:
                if resolver_prelisting.eligible_row_count == 0:
                    st.info(
                        "Amazon実在確認が完了した候補がないため、"
                        "出品前保安ゲート用CSVは生成しません。"
                    )
                else:
                    st.caption(
                        "ここでの除外は、Amazon実在確認が完了していないため、"
                        "保安ゲート用CSVへ含めない件数です。"
                    )
                    st.caption(
                        "このCSVは外部出品ツールへ直接渡さず、"
                        "出品前保安ゲートの候補CSVとして使用してください。"
                    )
                    st.download_button(
                        label="出品前保安ゲート用CSVダウンロード",
                        data=resolver_prelisting_csv,
                        file_name="prelisting_candidates_resolver.csv",
                        mime="text/csv",
                        key="prelisting-resolver-download",
                        width="stretch",
                    )
                    st.download_button(
                        label="Ingredient Safety Fact sidecarダウンロード",
                        data=resolver_safety_sidecar,
                        file_name="ingredient_safety_facts_resolver.csv",
                        mime="text/csv",
                        key="ingredient-safety-resolver-download",
                        width="stretch",
                    )
                    st.download_button(
                        label="Product Text Safety Fact sidecarダウンロード",
                        data=resolver_product_text_sidecar,
                        file_name="product_text_safety_facts_resolver.csv",
                        mime="text/csv",
                        key="product-text-safety-resolver-download",
                        width="stretch",
                    )
                    st.download_button(
                        label="PH画像確認ファイルをダウンロード", data=resolver_image_sidecar,
                        file_name="ph_image_safety_resolver.json", mime="application/json",
                        key="ph-image-safety-resolver-download", width="stretch",
                    )
            comparison_columns = [
                "source_id",
                "input_title",
                "product_title",
                "product_brand",
                "amazon_url",
                "asin",
                "status",
                "verification",
                "note",
            ]
            comparison_rows = [
                {column: row.get(column, "") or "" for column in comparison_columns}
                for row in resolver_rows
            ]
            st.subheader("Amazon商品候補比較")
            st.dataframe(
                pd.DataFrame(comparison_rows),
                column_config={
                    "source_id": st.column_config.TextColumn("source_id", width="small", pinned=True),
                    "input_title": st.column_config.TextColumn("input_title", width="large"),
                    "product_title": st.column_config.TextColumn("product_title", width="large"),
                    "product_brand": st.column_config.TextColumn("product_brand", width="medium"),
                    "amazon_url": st.column_config.TextColumn("amazon_url", width="large"),
                    "asin": st.column_config.TextColumn("asin", width="small"),
                    "status": st.column_config.TextColumn("status", width="small"),
                    "verification": st.column_config.TextColumn("verification", width="medium"),
                    "note": st.column_config.TextColumn("note", width="large"),
                },
                width="stretch",
                hide_index=True,
            )

    with retry_tab:
        st.info(
            "初回AI返答で「不明」になった既知source_idの商品だけを、手動修正したタイトルで再検索できます。"
            "このタブではKeepa APIを呼びません。"
        )
        preview_rows = st.session_state.get("asin_resolver_preview_rows", [])
        if not preview_rows:
            st.info("先に「AI返答 → ASIN確認」で初回AI返答を解析してください。")
        else:
            if st.button(
                "再検索対象を生成",
                width="stretch",
                disabled=not evidence_retry_action_allowed,
            ):
                _clear_retry_state()
                st.session_state["asin_resolver_retry_rows"] = build_retry_rows(
                    preview_rows,
                    st.session_state.get("asin_resolver_source_map"),
                )

            retry_rows = st.session_state.get("asin_resolver_retry_rows", [])
            if not retry_rows:
                if "asin_resolver_retry_rows" in st.session_state:
                    st.info("再検索対象の初回不明商品はありません。")
                else:
                    st.caption("初回不明商品を確認するには、再検索対象を生成してください。")
            else:
                editable_retry_rows = st.data_editor(
                    pd.DataFrame(retry_rows),
                    column_config={
                        "selected": st.column_config.CheckboxColumn("再検索対象"),
                        "row_id": None,
                    },
                    disabled=["source_id", "input_title", "initial_search_title", "row_id"],
                    hide_index=True,
                    key="asin_resolver_retry_editor",
                    width="stretch",
                )
                selected_retry_rows = editable_retry_rows.to_dict("records")
                retry_summary = summarize_retry_rows(selected_retry_rows)
                retry_columns = st.columns(3)
                retry_columns[0].metric("初回不明商品数", retry_summary["initial_unknown_products"])
                retry_columns[1].metric("再検索対象として選択", retry_summary["selected_products"])
                retry_columns[2].metric("再検索対象から外した商品", retry_summary["deselected_products"])
                retry_detail_columns = st.columns(2)
                retry_detail_columns[0].metric(
                    "再検索用タイトル未入力", retry_summary["missing_retry_search_titles"]
                )
                retry_detail_columns[1].metric(
                    "再検索プロンプトへ出力するsource_id数", retry_summary["prompt_source_ids"]
                )

                current_fingerprint = retry_rows_fingerprint(selected_retry_rows)
                saved_fingerprint = st.session_state.get("asin_resolver_retry_prompt_fingerprint")
                if saved_fingerprint is not None and saved_fingerprint != current_fingerprint:
                    st.session_state["asin_resolver_retry_prompt"] = ""
                    st.session_state["asin_resolver_retry_prompt_display"] = ""
                    st.session_state.pop("asin_resolver_retry_prompt_fingerprint", None)
                    st.info("編集内容が変更されています。再検索プロンプトを再生成してください。")

                retry_prompt_clicked = st.button(
                    "再検索用プロンプト生成",
                    type="primary",
                    width="stretch",
                    disabled=(
                        retry_summary["prompt_source_ids"] == 0
                        or not evidence_retry_action_allowed
                    ),
                )
                if retry_prompt_clicked:
                    retry_prompt = build_retry_prompt(selected_retry_rows)
                    if not retry_prompt:
                        st.warning("再検索対象と再検索用タイトルを確認してください。")
                    else:
                        try:
                            active_manifest_path = _active_evidence_manifest_path()
                            if active_manifest_path is not None:
                                active_manifest = load_and_validate_batch(active_manifest_path)
                                checkpoint = active_manifest["last_completed_checkpoint"]
                                if checkpoint == "INITIAL_PARSE_SAVED":
                                    prepare_retry(active_manifest_path, selected_retry_rows)
                                elif checkpoint != "RETRY_PREPARED":
                                    raise EvidenceValidationError(
                                        f"retry prompt generation is not allowed at checkpoint {checkpoint}"
                                    )
                                record_retry_prompt(active_manifest_path, retry_prompt)
                                st.session_state["asin_resolver_evidence_response_phase"] = "retry"
                                st.session_state["asin_resolver_evidence_next_action"] = (
                                    "enter_retry_response"
                                )
                            st.session_state["asin_resolver_retry_prompt"] = retry_prompt
                            st.session_state["asin_resolver_retry_prompt_display"] = retry_prompt
                            st.session_state["asin_resolver_retry_prompt_fingerprint"] = current_fingerprint
                        except EvidenceValidationError as exc:
                            st.error(f"Evidence Batchを変更せず停止しました: {exc}")

                if st.session_state.get("asin_resolver_retry_prompt"):
                    st.text_area(
                        "生成された再検索用プロンプト",
                        height=320,
                        key="asin_resolver_retry_prompt_display",
                    )
                    _render_direct_chat_assist(
                        "asin_resolver_retry_prompt_display",
                        "asin-resolver-retry-prompt-copy",
                    )
                    st.caption(
                        "ChatGPT / Geminiの返答は「AI返答 → ASIN確認」へ貼り付けてください。"
                    )

    with research_csv_adapter_tab:
        render_research_csv_adapter_tab()


with prelisting_gate_tab:
    _render_prelisting_gate_input_tab()

with category_mapper_tab:
    render_category_mapper_tab()
