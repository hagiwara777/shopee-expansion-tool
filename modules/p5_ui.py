"""P5-specific connection controls around the existing common daily screen."""
import streamlit as st

from modules.sg_beta_facts import digest


def render_p5_start(runtime):
    scope = runtime.scope
    st.caption(f'P5 / {scope.marketplace} / shop {scope.shop_id} / run {scope.run_id}')
    st.caption(f'P2保存先 {scope.db_path} / release {scope.release[:12]} / 実行対象 {scope.execution_target}')
    st.caption('実行許可と公式API仕様を確認してから、明示操作で接続します。')
    try:
        runtime.require_permit()
        approved = True
    except (ValueError, RuntimeError):
        approved = False
        st.warning('実行未承認、または公式API仕様が未確認です。設定だけではAPIを実行できません。')
    if st.button('承認対象のP5作業を開始', key='p5_start', disabled=not approved):
        try:
            runtime.start()
        except (ValueError, RuntimeError, OSError, KeyError, TypeError):
            st.error('作業を開始できません。対象・保存先・予約枠・同時起動を確認してください。')
            return False
    if runtime.workflow is None:
        return False
    try:
        runtime.require_current()
    except (ValueError, RuntimeError, OSError):
        st.error('接続と出力を停止しています。保存済みの消費・予約を保持して確認してください。')
        return False
    rows = runtime.ledger.data['reservations']
    st.caption(f'Keepa予約 {sum(r["tokens"] for r in rows)} / {scope.keepa_tokens} tokens、'
               f'requests {sum(r["kind"] == "keepa" for r in rows)} / {scope.keepa_requests}')
    st.caption(f'OpenAI最大費用予約 {sum(float(r["usd"]) for r in rows):.6f} / {scope.openai_usd} USD。予約は自動返金しません。')
    return True


def render_p5_workspace(runtime):
    from modules.classification_workflow_ui import render_current_batch
    from modules.practical_beta_ui import render_practical_controls, _action
    workflow = runtime.workflow
    st.subheader('分類・準備・出品管理')
    st.caption('Category / Brandは今回の公式取得経路から確認します。初回はHUMAN経路を使用します。')
    if runtime.permit.offline_test:
        st.warning('synthetic接続検証です。模擬応答を実運用の根拠には使えません。')
    with st.expander('管理・公式資料取得', expanded=False):
        st.caption('取得開始・失敗は旧確認を失効します。再描画では取得しません。')
        if st.button('承認済みBridgeからAccess Tokenを取得', key='p5_bridge',
                     disabled=not runtime.scope.bridge_spreadsheet_id):
            _action(runtime.refresh_access_token)
        if st.button('Categoryを取得・更新', key='p5_catalog'):
            _action(lambda: runtime.acquire_catalog(runtime.catalog_client()))
        cid = st.selectbox('取得対象leaf Category', runtime.scope.category_ids, key='p5_leaf')
        if st.button('Brandを完全取得', key='p5_brand', disabled=runtime.category_receipt is None):
            _action(lambda: runtime.acquire_brand(runtime.catalog_client(), cid))
        if st.button('Attributeを取得', key='p5_attribute', disabled=runtime.category_receipt is None):
            _action(lambda: runtime.acquire_attributes(runtime.catalog_client(), cid))
        status = runtime.attribute_status(cid)
        st.caption(f'Attribute：{status["state"]} / tree件数：{status["tree_count"]}')
        st.caption('空のtreeから必須属性0件とは判断しません。Seller Centerで最終確認してください。')
        if status.get('tree'):
            st.json(status['tree'])
    render_current_batch(workflow, runtime.scope.marketplace, key='p5_intake_')
    render_practical_controls(workflow, key='p5_work_', runtime=runtime)


def render_p5_weapon(runtime, *, key):
    from modules.practical_weapon_ui import _session, _save, render_weapon_decision
    from modules.sg_beta_workbench import capture_weapon_review
    from modules.p5_transport import make_image_inspector
    workflow = runtime.workflow
    records = [r for r in workflow.bench.store.products() if r.get('weapon')]
    if not records:
        return
    with st.expander('武器画像の対象・疑義・復旧', expanded=False):
        asin = st.selectbox('画像の確認対象ASIN', [r['asin'] for r in records], key=key+'asin')
        record = next(r for r in records if r['asin'] == asin)
        try:
            item, review = _session(record, runtime.scope.marketplace)
        except (ValueError, RuntimeError, KeyError, TypeError):
            st.info('現在の商品文章・画像資料を再受付してください。')
            return
        if not review.image_inspection_required(item):
            st.caption('画像検査対象外です。追加の人間確認は不要です。')
            return
        if st.button('対象商品の画像を検査', key=key+'inspect'):
            try:
                runtime.require_current()
                if asin not in runtime.scope.asins:
                    raise ValueError('P5 product outside scope')
                runtime.weapon_receipts.pop(asin, None)
                invalid = {**record['weapon'], 'inspection': None, 'decision': None, 'note': ''}
                _save(workflow, record, invalid, 'P5画像更新開始・旧確認失効', result='P5_REFRESH')
                # Use the new saved revision; all inspection paths are bounded.
                record = next(r for r in workflow.bench.store.products() if r['asin'] == asin)
                item, review = _session(record, runtime.scope.marketplace)
                evidence = review.current(item)
                result = make_image_inspector(runtime, runtime.secrets()).inspect(evidence)
                review.finish_image_inspection(item, evidence_binding=evidence.binding, inspection=result)
                _save(workflow, record, capture_weapon_review(item, review, images=record['weapon']['images']), 'P5画像検査', result='P5_INSPECTION')
                runtime.weapon_receipts[asin] = (digest([record['facts'], record['source'], record['weapon']['images']]), result.evaluation_id)
            except (ValueError, RuntimeError, OSError, KeyError, TypeError):
                workflow.session.begin_fact_refresh(asin)
                st.error('画像検査を完了できません。旧結果では準備を続行しません。')
            else:
                st.rerun()
        render_weapon_decision(workflow, record, item, review, key=key+asin+'_', offline=runtime.permit.offline_test)
