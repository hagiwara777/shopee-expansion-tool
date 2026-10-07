"""One Streamlit app, one country selector, existing PH and bounded SG flows."""
import argparse
from pathlib import Path
import runpy

import streamlit as st

from modules.beta_runtime_paths import beta_runtime_paths, BetaRuntimePathError


def clear_country_session():
    """Never carry transient confirmations, credentials or exports across markets."""
    runtime = st.session_state.get('sg_live_runtime')
    if runtime is not None:
        runtime.close()
    for key in list(st.session_state):
        if key != 'beta_marketplace':
            del st.session_state[key]


def render_beta(*, sg_config_path=None, ph_runtime_root=None, ph_api_env_path=None):
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
    try:
        with beta_runtime_paths(ph_runtime_root, ph_api_env_path):
            runpy.run_path(str(Path(__file__).with_name('app.py')),
                           init_globals={'BETA_MARKETPLACE': marketplace,
                                         'BETA_SG_CONFIG_PATH': sg_config_path})
    except BetaRuntimePathError:
        # Path validation occurs before rendering any work area.
        st.error('PHの保存先・既存API設定を確認してください。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sg-config', type=Path)
    parser.add_argument('--ph-runtime-root', type=Path)
    parser.add_argument('--ph-api-env', type=Path)
    args, _ = parser.parse_known_args()
    render_beta(sg_config_path=args.sg_config, ph_runtime_root=args.ph_runtime_root,
                ph_api_env_path=args.ph_api_env)
