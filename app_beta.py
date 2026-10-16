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
    runtime = st.session_state.get('p5_runtime')
    if runtime is not None:
        runtime.close()
    for key in list(st.session_state):
        if key != 'beta_marketplace':
            del st.session_state[key]


def render_beta(*, sg_config_path=None, ph_runtime_root=None, ph_api_env_path=None,
                sg_work_db=None, sg_work_shop=None, classification_workspaces=None,
                practical_workspaces=None, p5_runtimes=None):
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
    if p5_runtimes is not None:
        from modules.p5_ui import render_p5_start
        runtime = p5_runtimes.get(marketplace)
        if runtime is None:
            st.info('この国のP5対象設定がありません。')
            return
        previous = st.session_state.get('p5_runtime')
        if previous is not None and previous.scope.digest != runtime.scope.digest:
            clear_country_session()
        st.session_state['p5_runtime'] = runtime
        st.session_state['p4_diagnostics'] = False
        if not render_p5_start(runtime):
            return
        render_application(marketplace, enable_expansion_handoff=True,
            practical_workspace={'db_path': runtime.scope.db_path, 'shop_id': runtime.scope.shop_id},
            p5_runtime=runtime)
        return
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
    practical = (practical_workspaces or {}).get(marketplace)
    if practical_workspaces is not None:
        if practical is None:
            st.info('この国の共通作業保存先とショップを起動設定で指定してください。')
            return
        binding = (str(Path(practical['db_path']).resolve()), marketplace, practical['shop_id'])
        if st.session_state.get('p4_active_workspace') not in (None, binding):
            clear_country_session()
            st.session_state['beta_active_marketplace'] = marketplace
        st.session_state['p4_active_workspace'] = binding
        from modules.practical_beta_ui import render_source_settings
        render_source_settings(marketplace, **practical)
    try:
        with beta_runtime_paths(ph_runtime_root, ph_api_env_path):
            workspace = (classification_workspaces or {}).get(marketplace)
            render_application(marketplace, sg_config_path=sg_config_path, enable_expansion_handoff=True,
                               classification_workspace=workspace, practical_workspace=practical)
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
    parser.add_argument('--ph-classification-db', type=Path)
    parser.add_argument('--ph-classification-shop')
    parser.add_argument('--sg-classification-db', type=Path)
    parser.add_argument('--sg-classification-shop')
    parser.add_argument('--ph-practical-db', type=Path)
    parser.add_argument('--ph-practical-shop')
    parser.add_argument('--sg-practical-db', type=Path)
    parser.add_argument('--sg-practical-shop')
    parser.add_argument('--p5-config', type=Path)
    args, _ = parser.parse_known_args()
    workspaces = {market: {'db_path': path, 'shop_id': shop} for market, path, shop in (
        ('PH', args.ph_classification_db, args.ph_classification_shop),
        ('SG', args.sg_classification_db, args.sg_classification_shop)) if path is not None}
    practical = {market: {'db_path': path, 'shop_id': shop} for market, path, shop in (
        ('PH', args.ph_practical_db, args.ph_practical_shop),
        ('SG', args.sg_practical_db, args.sg_practical_shop)) if path is not None}
    p5_runtimes = None
    if args.p5_config is not None:
        # Scope files are descriptive only; never deserialize a permit/client.
        import json
        from modules.p5_runtime import P5Scope, P5Runtime
        p5_runtimes = {}
        for value in json.loads(args.p5_config.read_text('utf-8')):
            for name in ('asins', 'category_ids', 'finder_queries', 'openai_models'):
                value[name] = tuple(value[name])
            scope = P5Scope(**value)
            if scope.marketplace in p5_runtimes:
                raise ValueError('Duplicate P5 marketplace')
            p5_runtimes[scope.marketplace] = P5Runtime(scope)
    render_beta(sg_config_path=args.sg_config, ph_runtime_root=args.ph_runtime_root,
                ph_api_env_path=args.ph_api_env, sg_work_db=args.sg_work_db, sg_work_shop=args.sg_work_shop,
                classification_workspaces=workspaces, practical_workspaces=practical or None,
                p5_runtimes=p5_runtimes)
