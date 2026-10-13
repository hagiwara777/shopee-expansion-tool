"""One Streamlit app, one country selector, existing PH and bounded SG flows."""
import argparse
from pathlib import Path

import streamlit as st

from modules.beta_runtime_paths import beta_runtime_paths, BetaRuntimePathError
from app import render_application


def clear_country_session():
    """Never carry transient confirmations, credentials or exports across markets."""
    runtime = st.session_state.get('sg_live_runtime')
    if runtime is not None:
        runtime.close()
    for key in list(st.session_state):
        if key != 'beta_marketplace':
            del st.session_state[key]


def render_beta(*, sg_config_path=None, ph_runtime_root=None, ph_api_env_path=None,
                sg_work_db=None, sg_work_shop=None):
    st.set_page_config(page_title='Shopee 出品支援ツール', layout='wide')
    st.title('Shopee 出品支援ツール')
    if st.session_state.get('beta_marketplace', 'PH') not in {'PH', 'SG'}:
        clear_country_session()
        st.error('対象国を確認してください。')
        return
    marketplace = st.selectbox('対象国', ('PH', 'SG'), key='beta_marketplace',
                               on_change=clear_country_session)
    if marketplace not in {'PH', 'SG'}:
        clear_country_session()
        st.error('対象国を確認してください。')
        return
    previous = st.session_state.get('beta_active_marketplace')
    if previous is not None and previous != marketplace:
        clear_country_session()
    st.session_state['beta_active_marketplace'] = marketplace
    st.caption('国を切り替えると未保存の入力をクリアします。保存済みの確認・API消費記録は保持します。')
    if sg_work_db is not None:
        # An explicit offline work area must not initialize any legacy runtime.
        if marketplace != 'SG':
            st.info('このoffline作業画面はSG専用です。対象国をSGへ切り替えてください。')
        elif not isinstance(sg_work_shop, str) or not sg_work_shop.strip():
            st.error('SG作業保存先には対象ショップを明示してください。')
        else:
            from modules.sg_beta_workbench_ui import render_sg_workbench
            render_sg_workbench(db_path=sg_work_db, shop_id=sg_work_shop)
        return
    try:
        with beta_runtime_paths(ph_runtime_root, ph_api_env_path):
            render_application(marketplace, sg_config_path=sg_config_path, enable_expansion_handoff=True)
    except BetaRuntimePathError:
        # Path validation occurs before rendering any work area.
        st.error('PHの保存先・既存API設定を確認してください。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sg-config', type=Path)
    parser.add_argument('--ph-runtime-root', type=Path)
    parser.add_argument('--ph-api-env', type=Path)
    parser.add_argument('--sg-work-db', type=Path)
    parser.add_argument('--sg-work-shop')
    args, _ = parser.parse_known_args()
    render_beta(sg_config_path=args.sg_config, ph_runtime_root=args.ph_runtime_root,
                ph_api_env_path=args.ph_api_env, sg_work_db=args.sg_work_db, sg_work_shop=args.sg_work_shop)
