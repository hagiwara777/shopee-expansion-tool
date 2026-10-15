"""P4 common offline daily controls, using the P1/P2/P3 contracts unchanged.

No live client, official receipt, operational permit or legacy migration is
created here. Downloads are transient, reservations and history are durable.
"""
from dataclasses import asdict
import json
from pathlib import Path

import streamlit as st

from modules.sg_beta_facts import ProductFacts, digest
from modules.sg_beta_workbench_ui import STATE_LABELS


def render_source_settings(marketplace, *, db_path, shop_id):
    st.caption(f'{marketplace} / ショップ {shop_id} / 作業保存先 {Path(db_path)} / P2専用schema')
    st.warning('offline操作検証：実出品不可。CSV / TXTは listing_ready=FALSE、PH_SG_P1_OFFLINE です。')
    st.caption('候補受付 → Safety・全ショップ重複確認 → Category / Brand確認 → 準備pool → 出力 → 投入結果・出品状態')
    with st.expander('管理・診断', expanded=False):
        st.checkbox('開発・診断表示を開く', key='p4_diagnostics')
        st.caption('既存の認証・API枠はこの画面から変更しません。認証切れ・取得失敗は現在根拠を失効させ、承認済み取得経路で復旧してください。')
        upload = st.file_uploader('合成商品根拠（offline JSON・任意）', type=['json'], key='p4_producer')
        reload_facts = st.button('商品根拠を再読込（旧確認を失効）', key='p4_reload_facts', disabled=upload is None)
        st.caption('通常取得の項目別Factを使えないoffline再生時に指定します。出所の自己申告を公式取得の証明にはしません。')
    fingerprint = digest(upload.getvalue().hex()) if upload is not None else None
    if st.session_state.get('p4_producer_binding') != fingerprint or reload_facts:
        previous = st.session_state.pop('p4_producer_rows', ())
        workflow = st.session_state.get('p3_' + marketplace + '_workflow')
        st.session_state['p4_producer_binding'] = fingerprint
        st.session_state.pop('classification_current_batch', None)
        if upload is not None:
            try:
                value = json.loads(upload.getvalue().decode('utf-8-sig'))
                if (value['schema'] != 'PH_SG_P4_SYNTHETIC_V1'
                        or value['marketplace'] != marketplace or not value['rows']):
                    raise ValueError('Offline marketplace/schema required')
                rows = value['rows']
                if len({r['candidate_asin'] for r in rows}) != len(rows):
                    raise ValueError('Unique product facts required')
                for row in rows:
                    if ProductFacts.from_dict(row['classification_facts']).asin != row['candidate_asin']:
                        raise ValueError('Target product facts required')
                st.session_state['p4_producer_rows'] = tuple(rows)
                st.session_state['p4_producer_error'] = False
            except (ValueError, KeyError, TypeError, AttributeError):
                st.session_state['p4_producer_rows'] = ()
                st.session_state['p4_producer_error'] = True
        if workflow is not None:
            # A new disjoint group does not revoke the earlier group's current
            # evidence. Removing/failed material or a new acquisition of the
            # same target does expire it before any new intake can succeed.
            incoming = {r['candidate_asin'] for r in st.session_state.get('p4_producer_rows', ())}
            # Refresh every incoming target, including A reacquired after B.
            # Looking only at the last upload misses A -> B -> same A.
            targets = incoming or {row['candidate_asin'] for row in previous}
            for asin in targets:
                workflow.session.begin_fact_refresh(asin)
    if st.session_state.get('p4_producer_error') and upload is not None:
        st.error('合成商品根拠を確認できません。市場・ASIN・項目別出所を確認して再読込してください。')


def state_label(record):
    return STATE_LABELS[record['state']]


def decision_label(record, kind):
    authority = (record.get(kind) or {}).get('authority', '未確認')
    return authority if record['assessment'].get(kind + '_valid') else authority + '（要再確認）'


def recovery_text(record):
    result = record['assessment']
    actions = []
    if result.get('safety_reasons') or record.get('review_pending') or record.get('manual_exclude') or record.get('body_excluded'):
        actions.append('Safety停止理由と対象市場の資料を確認。メモ・分類採用では解除されません')
    if any('CURRENT_' in r or 'EXPIRED' in r or 'SESSION' in r for r in result['reasons']):
        actions.append('現在の分類資料・全ショップCSV・商品根拠を再読込し、Category→Brandを再確認')
    if not result.get('category_valid'):
        actions.append('Categoryを現在のleaf候補から確認')
    if not result.get('brand_valid'):
        actions.append('有効なCategoryに対応するBrand / No Brandを確認')
    return ' / '.join(actions) or 'offline準備有効。実運用の許可・出品完了を意味しません'


def filter_queue(records, *, key):
    predicates = {
        '全商品': lambda r: True,
        'Safety確認待ち': lambda r: bool(r['assessment'].get('safety_reasons') or r.get('review_pending')
                                       or r.get('manual_exclude') or r.get('body_excluded')),
        'Category確認待ち': lambda r: not r['assessment'].get('category_valid'),
        'Brand確認待ち': lambda r: not r['assessment'].get('brand_valid'),
    }
    queue = st.selectbox('確認待ち', tuple(predicates), key=key+'queue')
    if queue not in predicates:
        st.error('確認対象を選択し直してください。')
        return []
    return [r for r in records if predicates[queue](r)]


def _action(call):
    try:
        call()
    except (ValueError, RuntimeError, OSError, KeyError, TypeError):
        st.error('操作を保存できません。現在根拠・選択・予約・保存先を確認してください。成功扱いにはしません。')
    else:
        st.rerun()


def render_practical_controls(workflow, *, key):
    from modules.classification_workflow_ui import render_classification_controls
    classification, preparation, listing = st.tabs(('分類・確認待ち', '準備pool・CSV / TXT', '出品作業・履歴'))
    with classification:
        from modules.practical_weapon_ui import render_weapon_controls
        try:
            render_weapon_controls(workflow, key=key+'weapon_')
        except (ValueError, RuntimeError, OSError):
            st.error('画像資料・保存先を確認できません。現在根拠を再確認してください。')
        # File widgets must render before classification actions request an
        # immediate rerun, otherwise Streamlit can remove their widget state.
        render_classification_controls(workflow, key=key, practical=True)
    with preparation:
        render_preparation_pool(workflow, key=key+'pool_')
    with listing:
        render_listing_controls(workflow, key=key+'listing_')


def _records(workflow):
    try:
        return workflow.bench.refresh(), workflow.bench.store.operations()
    except (ValueError, RuntimeError, OSError):
        st.error('作業DBの再評価・保存に失敗しました。出力と状態操作を停止しています。保存先を確認してください。')
        return None, None


def _selection(workflow, records, *, key, label):
    shown = digest([asdict(workflow.session.scope), [r['asin'] for r in records]])
    if st.session_state.get(key+'shown') != shown:
        st.session_state[key+'shown'] = shown
        st.session_state[key+'selected'] = []
    selected = st.multiselect(label, [r['asin'] for r in records], key=key+'selected')
    if len(selected) != len(set(selected)) or any(a not in {r['asin'] for r in records} for a in selected):
        st.error('現在表示中の商品から選択し直してください。')
        return {}
    return {r['asin']: r['revision'] for r in records if r['asin'] in selected}


def _human(workflow, binding, *, key, label='選択商品と今回の操作を本人が確認しました'):
    note = st.text_area('作業根拠・確認メモ', key=key+'note')
    current = digest([asdict(workflow.session.scope), workflow.session.evidence_revision, binding, note])
    if st.session_state.get(key+'binding') != current:
        st.session_state[key+'binding'] = current
        st.session_state[key+'human'] = False
    confirmed = st.checkbox(label, key=key+'human')
    return note, confirmed and bool(note.strip())


def render_preparation_pool(workflow, *, key):
    records, operations = _records(workflow)
    if records is None:
        return
    locked = {a for o in operations if o['state'] in {'PENDING', 'UNKNOWN'} for a in o['asins']}
    pool = [r for r in records if r['assessment']['valid'] and r['state'] == 'WAITING'
            and r['listing_progress'] == 'WAITING' and r['asin'] not in locked]
    st.metric('現在有効な準備pool（offline）', len(pool))
    st.caption('商品群をまたいだ現在有効分です。実運用の公式Brand receipt・承認は未接続。実出品不可。')
    group_of = lambda r: f"{workflow.session.scope.marketplace}|{r['category']['category_id']}|{r['brand']['brand_id']}"
    groups = sorted({group_of(r) for r in pool})
    group = st.selectbox('市場 / leaf Category ID / Brand ID', ['全グループ', *groups], key=key+'group')
    pool = [r for r in pool if group == '全グループ' or group_of(r) == group]
    st.dataframe([{'ASIN': r['asin'], 'グループ': group_of(r), 'Category確認': decision_label(r, 'category'),
        'Brand確認': decision_label(r, 'brand'), '出所': ', '.join(sorted({b['source_type'] for b in r['batches']})),
        '商品群': ', '.join(b['reference'] for b in r['batches']), '実出品可能': False} for r in pool])
    expected = _selection(workflow, pool, key=key, label='出力するASIN（完成分から任意選択）')
    note, confirmed = _human(workflow, [expected, group], key=key)
    for reserve, label in ((False, 'offline CSV / TXTを作成'), (True, '模擬投入前の永続予約を作成')):
        if st.button(label, key=key+'output_'+str(reserve), disabled=not expected or (reserve and not confirmed)):
            try:
                csv_bytes, txt_bytes, operation_id = workflow.bench.output(expected, reserve_copy=reserve)
            except (ValueError, RuntimeError, OSError):
                st.error('出力を停止しました。最新の資料・準備状態・未解決予約・保存先を確認してください。')
            else:
                # No session download cache: P1/P2 checked immediately before return.
                market = workflow.session.scope.marketplace.lower()
                st.download_button('offline CSVを取得', csv_bytes, file_name=market+'_offline_preparation.csv',
                                   mime='text/csv', key=key+'csv', on_click='ignore')
                st.download_button('offline TXTを取得', txt_bytes, file_name=market+'_offline_preparation.txt',
                                   mime='text/plain', key=key+'txt', on_click='ignore')
                st.code(txt_bytes.decode('utf-8-sig'), language=None)
                st.caption('ダウンロードでは出品状態は進みません。予約後の不明結果は再起動後も二重投入を停止します。')
                if operation_id:
                    st.info('模擬投入予約を保存しました。出品作業・履歴で結果を明示確認してください。')


def render_listing_controls(workflow, *, key):
    records, operations = _records(workflow)
    if records is None:
        return
    st.caption('5状態はoffline再生の作業記録です。外部ツールは操作しません。出品済みは今回の全ショップCSV一致だけで判定します。')
    for code, label in STATE_LABELS.items():
        st.caption(f'{label}：{sum(r["state"] == code for r in records)}件')
    locked = {a for o in operations if o['state'] in {'PENDING', 'UNKNOWN'} for a in o['asins']}
    st.dataframe([{'ASIN': r['asin'], '状態': state_label(r),
        '投入履歴': STATE_LABELS[r['listing_progress']], '結果不明・予約ロック': r['asin'] in locked,
        '現在根拠': 'offline有効' if r['assessment']['valid'] else '再確認必要',
        '照合資料': r.get('listing_match', {}).get('reference', ''), '必要な操作': recovery_text(r)} for r in records])
    expected = _selection(workflow, records, key=key, label='状態・確認メモを操作するASIN')
    action = st.selectbox('作業操作', ('UNRESOLVED', 'EVIDENCE_REVIEWED', 'EXCLUDE', 'ERROR', 'RETURN'),
        format_func=lambda v: {'UNRESOLVED':'保留を保存', 'EVIDENCE_REVIEWED':'Safety確認メモを保存・再評価',
            'EXCLUDE':'対象から除外', 'ERROR':'出品エラーを登録', 'RETURN':'現在準備を再検証して出品待ちへ戻す'}[v], key=key+'action')
    note, confirmed = _human(workflow, [expected, action], key=key)
    if st.button('選択商品の作業操作を保存', key=key+'save', disabled=not expected or not confirmed):
        if action in {'ERROR', 'RETURN'}:
            _action(lambda: workflow.bench.listing_action(expected, action=action, human_confirmed=confirmed, note=note))
        else:
            _action(lambda: workflow.bench.record_review(expected, result=action, human_confirmed=confirmed, note=note))
    by_asin = {r['asin']: r for r in records}
    for operation in operations:
        if operation['state'] not in {'PENDING', 'UNKNOWN'}:
            continue
        oid = operation['operation_id']
        st.write('投入結果の確認待ち：' + ', '.join(operation['asins']) + ' / ' + operation['state'])
        st.caption('再起動・資料変更後の古い成功確認は拒否します。現在CSVで反映を照合するか、結果を本人が確認して失敗・取消で解決してください。')
        outcome = st.selectbox('予約全件の結果', ('UNKNOWN', 'SUCCESS', 'FAILED', 'CANCELLED'),
            format_func=lambda v: {'UNKNOWN':'結果不明・ロック継続', 'SUCCESS':'模擬投入成功を本人が確認',
                'FAILED':'投入失敗を本人が確認', 'CANCELLED':'結果を確認して予約を取り消す'}[v], key=key+oid+'outcome')
        revisions = {a: by_asin[a]['revision'] for a in operation['asins']}
        op_note, explicit = _human(workflow, [operation, revisions, outcome], key=key+oid,
                                   label='予約した全商品についてこの結果を本人が確認しました')
        if st.button('予約全件の結果を保存', key=key+oid+'finish', disabled=not explicit):
            _action(lambda: workflow.bench.finish_copy(oid, revisions, outcome=outcome,
                                                      human_confirmed=explicit, note=op_note))
    with st.expander('操作・確認・取消履歴'):
        events = []
        for event in workflow.bench.store.history():
            payload = json.loads(event['payload'])
            last = (payload.get('notes') or [{}])[-1]
            events.append({'日時': event['created_at'], 'ASIN': event['asin'], '操作': event['action'],
                'revision': event['revision'], '確認者': last.get('reviewer', ''),
                '根拠・メモ': last.get('note', ''), '結果': last.get('result', '')})
        st.dataframe(events)
        st.dataframe([{'予約': o['operation_id'], '結果': o['state'], 'ASIN': ', '.join(o['asins']),
                       '根拠・メモ': o['note']} for o in operations])
