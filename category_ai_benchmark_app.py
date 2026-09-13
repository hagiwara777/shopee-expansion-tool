"""Standalone Streamlit UI for Category AI Benchmark V1."""

from pathlib import Path

import pandas as pd
import streamlit as st

from modules.category_ai_benchmark import (
    PriceBook,
    aggregate_by_model,
    evaluate_predictions,
    load_request_profiles,
    parse_catalog_csv,
    parse_gold_csv,
    parse_source_csv,
    prediction_batch_hash,
    prediction_rows,
    rows_to_csv,
)
from modules.category_ai_core import CategoryAIEngine
from modules.category_ai_openai import OpenAIResponsesCategoryProvider


ROOT = Path(__file__).resolve().parent
PROFILE_PATH = ROOT / "config" / "category_ai_benchmark_request_profiles.json"
PRICE_PATH = ROOT / "config" / "category_ai_model_prices.json"
MODEL_EXECUTION_ORDER = ("gpt-5.6-luna", "gpt-5.6-terra")

st.set_page_config(page_title="Category AI Benchmark V1", layout="wide")
st.title("Category AI Benchmark V1")
st.caption(
    "商品ごとに独立してShopee Category Treeを探索します。"
    "AI結果はCategory候補であり、安全性・出品可否の判断ではありません。"
)

try:
    profiles = load_request_profiles(PROFILE_PATH)
    price_book = PriceBook.from_path(PRICE_PATH)
except (OSError, ValueError) as exc:
    st.error(f"Benchmark設定を読み込めません: {exc}")
    st.stop()

profile_by_model = {profile.model: profile for profile in profiles}
st.session_state.setdefault("category_ai_predictions", ())
st.session_state.setdefault("category_ai_evaluations", {})
st.session_state.setdefault("category_ai_prediction_batch_hash", "")
st.session_state.setdefault("category_ai_model_batch_hashes", {})

with st.form("category_ai_benchmark_form", border=True):
    st.subheader("Benchmark入力")
    marketplace = st.selectbox(
        "Marketplace",
        ["PH", "SG", "MY", "TH"],
        key="category_ai_marketplace",
    )
    source_file = st.file_uploader(
        "Source CSV",
        type=["csv"],
        key="category_ai_source_file",
        help="必須列: case_id, product_title。任意列: asin, keepa_category, keepa_brand, resolver_title。",
    )
    catalog_file = st.file_uploader(
        "Catalog snapshot CSV",
        type=["csv"],
        key="category_ai_catalog_file",
        help="category_id, parent_category_id, category_name, category_path, is_leaf が必要です。",
    )
    catalog_version = st.text_input(
        "Catalog version",
        value="",
        placeholder="例: PH-2026-09-11",
        key="category_ai_catalog_version",
    )
    models = st.multiselect(
        "Models",
        list(profile_by_model),
        default=[profiles[0].model],
        key="category_ai_models",
        help="smokeでは1モデル、比較では同一条件の複数モデルを選択します。",
    )
    item_count = st.number_input(
        "実行件数",
        min_value=1,
        max_value=1000,
        value=3,
        step=1,
        key="category_ai_item_count",
    )
    gold_file = st.file_uploader(
        "Gold truth CSV（任意）",
        type=["csv"],
        key="category_ai_gold_file",
        help=(
            "正式Gold必須列: case_id, asin, expected_category_id, "
            "expected_category_path, truth_status。Prediction全件とbatch hash固定後にだけ読み取ります。"
        ),
    )
    submitted = st.form_submit_button(
        "Benchmarkを実行",
        type="primary",
        icon=":material/play_arrow:",
    )

selected_profiles = [
    profile_by_model[model]
    for model in MODEL_EXECUTION_ORDER
    if model in models
]
with st.container(border=True):
    st.subheader("固定request profile")
    st.json([profile.to_dict() for profile in selected_profiles], expanded=False)
    profile_hashes = ", ".join(
        f"{profile.model}: {profile.profile_hash}" for profile in selected_profiles
    )
    st.caption(f"profile hash: {profile_hashes or '未選択'} / price: {price_book.version}")

if submitted:
    st.session_state["category_ai_predictions"] = ()
    st.session_state["category_ai_evaluations"] = {}
    st.session_state["category_ai_prediction_batch_hash"] = ""
    st.session_state["category_ai_model_batch_hashes"] = {}
    if (
        source_file is None
        or catalog_file is None
        or not catalog_version.strip()
        or not selected_profiles
    ):
        st.error("Source CSV、Catalog snapshot、Catalog versionを指定してください。")
    else:
        try:
            products = parse_source_csv(source_file.getvalue(), marketplace=marketplace)
            catalog = parse_catalog_csv(
                catalog_file.getvalue(),
                marketplace=marketplace,
                catalog_version=catalog_version.strip(),
            )
            if any(profile.model not in price_book.models for profile in selected_profiles):
                raise ValueError("選択モデルの料金設定がありません")
            provider = OpenAIResponsesCategoryProvider.from_environment()
            selected_products = products[: int(item_count)]
            progress = st.progress(0, text="Predictionを生成しています")
            completed = []
            model_batch_hashes = {}
            total = len(selected_profiles) * len(selected_products)
            stop = False
            for selected_profile in selected_profiles:
                model_completed = []
                engine = CategoryAIEngine(
                    provider,
                    cost_estimator=price_book.estimate,
                    price_config_version=price_book.version,
                )
                for product in selected_products:
                    prediction = engine.predict(product, catalog, selected_profile)
                    completed.append(prediction)
                    model_completed.append(prediction)
                    done = len(completed)
                    progress.progress(
                        done / total,
                        text=f"Prediction {done}/{total}",
                    )
                    if prediction.status == "FAILED":
                        stop = True
                        break
                if stop:
                    break
                model_batch_hashes[selected_profile.model] = prediction_batch_hash(
                    tuple(model_completed)
                )
            predictions = tuple(completed)
            evaluations = {}
            fixed_batch_hash = ""
            # Fix every Prediction and the complete batch before Gold is parsed.
            if gold_file is not None and not stop and len(predictions) == total:
                fixed_batch_hash = prediction_batch_hash(predictions)
                gold = parse_gold_csv(
                    gold_file.getvalue(),
                    products=selected_products,
                    catalog=catalog,
                )
                evaluations = evaluate_predictions(
                    predictions,
                    gold,
                    fixed_prediction_batch_hash=fixed_batch_hash,
                )
            st.session_state["category_ai_predictions"] = predictions
            st.session_state["category_ai_evaluations"] = evaluations
            st.session_state["category_ai_prediction_batch_hash"] = fixed_batch_hash
            st.session_state["category_ai_model_batch_hashes"] = model_batch_hashes
            progress.empty()
            if predictions and predictions[-1].status == "FAILED":
                st.error(
                    "Fail closedで停止しました: " + predictions[-1].error_code
                )
            else:
                st.success(f"{len(predictions)}件のPredictionを固定しました。")
        except (OSError, ValueError, RuntimeError) as exc:
            st.error(f"Benchmarkを開始できません: {exc}")

predictions = st.session_state["category_ai_predictions"]
evaluations = st.session_state["category_ai_evaluations"]
fixed_batch_hash = st.session_state["category_ai_prediction_batch_hash"]
model_batch_hashes = st.session_state["category_ai_model_batch_hashes"]
if predictions:
    summaries = aggregate_by_model(predictions, evaluations)
    total_costs = [item.estimated_cost_usd for item in predictions]
    total_cost = (
        sum(total_costs) if all(value is not None for value in total_costs) else None
    )
    with st.container(horizontal=True):
        st.metric("Predictions", len(predictions), border=True)
        st.metric("Abstain", sum(item.abstain for item in predictions), border=True)
        st.metric("API calls", sum(item.api_call_count for item in predictions), border=True)
        st.metric(
            "Estimated cost",
            f"${total_cost:.6f}" if total_cost is not None else "N/A",
            border=True,
        )
    st.subheader("モデル集計")
    st.dataframe(pd.DataFrame(summaries), hide_index=True, width="stretch")
    if fixed_batch_hash:
        st.caption(f"Prediction batch hash: {fixed_batch_hash}")
    if model_batch_hashes:
        st.json(model_batch_hashes, expanded=False)
    result_rows = prediction_rows(predictions, evaluations)
    st.subheader("結果")
    st.dataframe(pd.DataFrame(result_rows), hide_index=True, width="stretch")
    st.download_button(
        "結果CSVを保存",
        data=rows_to_csv(result_rows),
        file_name="category_ai_benchmark_v1.csv",
        mime="text/csv",
        icon=":material/download:",
        key="category_ai_download",
    )
