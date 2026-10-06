"""Separate SG review app: offline by default; bounded live mode by explicit grant."""

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import streamlit as st

from modules.category_mapper_sg_ui import render_sg_category_mapper, clear_sg_category_mapper_result
from modules.sg_candidate_runtime import SGReplayBundle, create_sg_candidate_workflow


def _clear_candidate(state):
    previous = state.get("sg_candidate_workflow")
    if previous is not None:
        previous.product_review.clear()
    # Reset confirmation widgets too, before any downstream widget is rendered.
    for key in list(state):
        if key.startswith("sg_") and key not in {"sg_candidate_bundle", "sg_candidate_fingerprint"}:
            del state[key]
    clear_sg_category_mapper_result(state)


def render_sg_candidate(*, live_grant_path=None, api_env_path=None):
    if live_grant_path is not None:
        return render_sg_live_candidate(live_grant_path,api_env_path=api_env_path)
    st.title("SG 開発版の確認")
    st.info("隔離した開発環境です。外部APIには接続せず、通常のPHデータを変更しません。出力は開発用の確認資料です。")
    uploaded = st.file_uploader("SG接続確認用の再生資料（JSON）", type=["json"], key="sg_candidate_bundle")
    content = uploaded.getvalue() if uploaded is not None else None
    fingerprint = sha256(content).hexdigest() if content else None
    state = st.session_state
    if state.get("sg_candidate_fingerprint") != fingerprint:
        _clear_candidate(state)
        state["sg_candidate_fingerprint"] = fingerprint
    if st.button("隔離した確認環境を作る", disabled=content is None, key="sg_candidate_initialize"):
        # Clear previous results even when the same bundle is explicitly reopened.
        _clear_candidate(state)
        try:
            bundle = SGReplayBundle(content)
            path = Path(__file__).parent / "outputs" / "sg-candidate" / uuid4().hex / "candidate.sqlite3"
            workflow = create_sg_candidate_workflow(bundle, db_path=path)
            state["sg_candidate_engine"] = bundle.category_engine()
            state["sg_candidate_workflow"] = workflow
        except Exception:
            state.pop("sg_candidate_workflow", None)
            st.error("再生資料を確認できませんでした。SG用の資料を確認してください。")
    workflow = state.get("sg_candidate_workflow")
    if workflow is None:
        st.caption("確認環境を作成後、SG catalogと商品CSV・確認資料を読み込んで操作できます。通常データは自動取込しません。")
        return
    render_sg_category_mapper(brand_workflow=workflow, ai_engine=state.get("sg_candidate_engine"))


def render_sg_live_candidate(grant_path, *, api_env_path=None, beta_output=False):
    """Explicit launch only; initialization is local and buttons perform I/O."""
    from modules.sg_live_runtime import SGLiveRunGrant, SGLiveRuntime
    if beta_output:
        from modules.sg_beta_release import require_sg_beta_operation, SGBetaNotAdopted
        try:
            require_sg_beta_operation()
        except SGBetaNotAdopted:
            st.error("SGベータ版は正式採用前です。採用が完了するまで利用を開始できません。")
            return
    st.title("SG ベータ版" if beta_output else "SG 開発版・実接続確認")
    st.info("SGの商品を確認し、出品準備資料を作ります。取得・費用は指定した枠内で管理します。" if beta_output else
            "承認済みの対象・取得上限・費用枠内で読み取り確認を行う隔離環境です。出力は開発用です。")
    try:
        grant=SGLiveRunGrant.from_file(grant_path)
        grant.validate(Path(__file__).parent/"outputs"/"sg-live-ui"/grant.digest/"validation.sqlite3")
    except Exception:
        st.error("実接続の設定を確認できません。承認済みの対象・上限を確認してください。")
        return
    state=st.session_state
    existing=state.get("sg_live_runtime")
    if existing is not None and state.get("sg_live_grant_digest")!=grant.digest:
        existing.close()
        _clear_candidate(state)
        state.pop("sg_live_runtime",None)
    st.caption(f"対象商品: {len(grant.allowed_asins)}件 / Brand上限: 各{grant.brand_page_limit}ページ / OpenAI上限: {grant.openai_limit_usd} USD")
    if st.button("SGの作業を開始" if beta_output else "承認枠で隔離した確認環境を開く",key="sg_live_open",disabled=state.get("sg_live_runtime") is not None):
        try:
            import os
            key=os.environ.get("OPENAI_API_KEY","")
            if not key and api_env_path is not None:
                from dotenv import dotenv_values
                key=dotenv_values(api_env_path).get("OPENAI_API_KEY") or ""
            runtime=SGLiveRuntime(grant=grant,run_path=Path(__file__).parent/"outputs"/"sg-live-ui"/grant.digest,api_key=key)
            state["sg_live_runtime"]=runtime
            state["sg_live_grant_digest"]=grant.digest
        except Exception:
            st.error("隔離環境を開けません。既存の取得記録・設定・認証を確認してください。")
    runtime=state.get("sg_live_runtime")
    if runtime is None:
        return
    st.caption("画面の再表示だけではAPIを呼びません。停止や失敗も取得枠・費用枠へ計上します。")
    if st.button("SGの最新カテゴリー一覧を取得",key="sg_live_refresh_catalog"):
        clear_sg_category_mapper_result(state)
        try:
            count=runtime.refresh_catalog()
        except Exception:
            runtime.workflow.product_review.clear_review_results()
            st.error("最新カテゴリーを取得できません。未確認のまま停止します。")
        else:
            st.success(f"SGカテゴリー {count}件を取得しました。商品CSVを読み込んで確認できます。")
    d=runtime.ledger.data
    st.caption(f"カテゴリー取得: {d['catalog_requests']}/{grant.catalog_request_limit}回 / 属性取得: {d['attribute_requests']}/{grant.attribute_request_limit}回 / Brand取得: {sum(d['brand_page_counts'].values())}ページ / OpenAI予約額: {d['openai']['reserved_upper_bound_usd']} USD")
    render_sg_category_mapper(brand_workflow=runtime.workflow,ai_engine=runtime.category_engine,beta_output=beta_output)


if __name__ == "__main__":
    st.set_page_config(page_title="SG 開発版の確認", layout="wide")
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--live-validation-grant",type=Path)
    parser.add_argument("--api-env",type=Path)
    args,_=parser.parse_known_args()
    render_sg_candidate(live_grant_path=args.live_validation_grant,api_env_path=args.api_env)
