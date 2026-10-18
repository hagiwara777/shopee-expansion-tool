"""P5-specific connection controls around the existing common daily screen."""
from dataclasses import asdict
import streamlit as st

from modules.sg_beta_facts import digest


def render_p5_selection(runtime, source_type, rows):
    """The checkbox records selection/identity, never an execution permit."""
    if not runtime.scope.preparation_limit:
        return rows
    try:
        criteria = st.session_state.get('f12_' + ('expansion' if source_type == 'EXPANSION' else 'resolver') + '_criteria')
        bid = runtime.candidates.offer(source_type, rows, filter_criteria=criteria)
    except (ValueError, RuntimeError, KeyError, TypeError):
        st.warning('承認済み探索結果との対応を確認できません。未確認・仕様不一致の商品は引き継げません。')
        return []
    key = 'p5_select_' + source_type + '_'
    fixed = runtime.candidates.data['selections'].get(bid)
    if fixed:
        st.caption('固定した準備対象：' + ' / '.join(fixed['asins']))
        if st.button('固定した対象をSafetyへ引き継ぐ', key=key+'handoff'):
            _activate_batch(runtime, bid)
        return [r for r in rows if (r.get('candidate_asin') or r.get('asin')) in fixed['asins']]
    if st.session_state.get(key+'batch') != bid:
        st.session_state[key+'batch'] = bid
        for suffix, value in [('asins', []), ('human', False), ('identity', 'UNKNOWN')]:
            st.session_state[key+suffix] = value
    st.dataframe(rows, hide_index=True)
    asins = st.multiselect('準備するASINを明示選択', [r.get('candidate_asin') or r.get('asin') for r in rows], key=key+'asins')
    identity = 'NOT_APPLICABLE'
    if source_type == 'RESOLVER':
        identity = st.selectbox('元の商品との同一性（型番・仕様・同梱を確認）',
            ('UNKNOWN', 'CONFIRMED', 'MISMATCH'), key=key+'identity')
    reviewer = st.text_input('対象選択の確認者', key=key+'reviewer')
    note = st.text_input('対象選択・同一性の確認根拠', key=key+'note')
    binding = digest([bid, asins, identity, reviewer, note])
    if st.session_state.get(key+'binding') != binding:
        st.session_state[key+'binding'] = binding
        st.session_state[key+'human'] = False
    human = st.checkbox('この対象を固定します（追加・差替えはできません）', key=key+'human')
    if st.button('準備対象を固定してSafetyへ引き継ぐ', key=key+'fix',
                 disabled=not (asins and human and reviewer.strip() and note.strip()) or identity in {'UNKNOWN', 'MISMATCH'}):
        try:
            runtime.candidates.select(bid, asins, human_confirmed=human, reviewer=reviewer, note=note, identity=identity)
            _activate_batch(runtime, bid)
        except (ValueError, RuntimeError, OSError):
            st.error('対象を固定できません。承認範囲・最大件数・保存状態を確認してください。')
    return []


def _activate_batch(runtime, bid):
    from modules.prelisting_gate_ui import clear_prelisting_gate_result
    # Material binding is revalidated again in the Gate and P1/P2.
    runtime.candidates.handoff(bid)
    clear_prelisting_gate_result(st.session_state)
    st.session_state['p5_active_batch'] = bid
    st.rerun()


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
    if runtime.scope.preparation_limit:
        saved = runtime.candidates.data['selections']
        with st.expander('固定した対象の再開（追加APIなし）', expanded=False):
            if saved:
                bid = st.selectbox('再開する商品群', list(saved), key='p5_resume_batch',
                    format_func=lambda b: runtime.candidates.data['batches'][b]['source_type'] + ' / ' + ' / '.join(saved[b]['asins']))
                if st.button('保存済み対象をSafetyへ再搬送', key='p5_resume'):
                    _activate_batch(runtime, bid)
            st.caption('対象固定と累積予算・履歴を維持します。現在のSafety・全ショップ資料・分類確認は再検証します。')
        if 'material_updates' in runtime.ledger.data:
            render_material_update(runtime)
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


def render_material_update(runtime):
    """Intent only; no network or credential access during rendering."""
    with st.expander('固定商品の資料を更新', expanded=False):
        selected = sorted({a for s in runtime.candidates.data['selections'].values() for a in s['asins']})
        stored = {p['asin']:p for p in runtime.workflow.bench.store.products()}
        asins = st.multiselect('資料更新の対象ASIN', [a for a in selected if a in stored], key='p5_update_asins')
        st.caption(f'追加取得は選択した {len(asins)} 商品、最大 {len(asins)*2} Keepa tokens＋残高確認1 send。'
                   '元の累積枠へ計上します。取得後は同じ内容でもCategory→Brandを再確認します。')
        reviewer = st.text_input('資料更新の確認者', key='p5_update_reviewer')
        note = st.text_input('資料更新・比較の理由', key='p5_update_note')
        explicit = st.checkbox('対象旧readyを失効して資料を更新する', key='p5_update_confirm')
        if st.button('選択商品の資料を更新', key='p5_update',
                     disabled=not (asins and explicit and reviewer.strip() and note.strip())):
            try:
                if explicit is not True:
                    raise ValueError('Explicit update required')
                runtime.update_material({a:stored[a]['revision'] for a in asins}, reviewer=reviewer, note=note)
                st.success('新しい資料世代を保存しました。Safety・全shop照合・Category→Brandを再確認してください。')
            except (ValueError, RuntimeError, OSError, KeyError, TypeError):
                st.error('更新を停止しました。旧readyは使用せず、保存済みintent・消費・P2履歴をofflineで照合してください。')
                return
        items = runtime.ledger.data['material_updates']['intents']
        for item in items[-5:]:
            st.caption(f'{item["state"]} / 対象 {len(item["targets"])} 商品 / '
                       f'資料世代 {max(item["parent"].values())+1} / 再確認が必要')


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
                runtime.require_preparation_target(record)
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
                runtime.weapon_receipts[asin] = (digest([record['facts'], record['source'], record['weapon']['images']]), digest(asdict(result)))
            except (ValueError, RuntimeError, OSError, KeyError, TypeError):
                workflow.session.begin_fact_refresh(asin)
                st.error('画像検査を完了できません。旧結果では準備を続行しません。')
            else:
                st.rerun()
        render_weapon_decision(workflow, record, item, review, key=key+asin+'_', offline=runtime.permit.offline_test)
