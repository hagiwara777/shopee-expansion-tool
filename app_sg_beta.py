"""SG beta entry. Formal state and an approved API run are both required."""

import argparse
from pathlib import Path

import streamlit as st

from app_sg_candidate import render_sg_live_candidate


def render_sg_beta(grant_path, *, api_env_path=None, runtime_root=None):
    from modules.sg_beta_release import require_sg_beta_operation, SGBetaNotAdopted
    try:
        require_sg_beta_operation()
    except SGBetaNotAdopted:
        st.title("SG ベータ版")
        st.info("正式採用の準備が整うまで、ベータ利用を開始できません。")
        return
    if grant_path is None:
        st.title("SG ベータ版")
        st.info("利用する商品とAPIの取得・費用枠を設定してください。")
        return
    render_sg_live_candidate(grant_path, api_env_path=api_env_path, beta_output=True, runtime_root=runtime_root)


if __name__ == "__main__":
    st.set_page_config(page_title="SG ベータ版", layout="wide")
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-validation-grant", type=Path)
    parser.add_argument("--api-env", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    args, _ = parser.parse_known_args()
    render_sg_beta(args.live_validation_grant, api_env_path=args.api_env, runtime_root=args.runtime_root)
