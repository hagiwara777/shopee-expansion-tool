"""Shared, post-acquisition F1/F2 controls. Rerenders never create a client."""
from uuid import uuid4

import streamlit as st

from modules.candidate_filters import FilterCriteria, partition_rows, confirmation_csv_bytes, observation_needs_capture
from modules.prelisting_gate_handoff import PACKET_KEY, GENERATION_KEY, remember_body_confirmations
from modules.prelisting_gate_ui import clear_prelisting_gate_result


def invalidate_filter_outputs():
    remember_body_confirmations(st.session_state, st.session_state.get('prelisting_gate_sg_body_confirmations'))
    st.session_state.pop(PACKET_KEY, None)
    st.session_state[GENERATION_KEY] = uuid4().hex
    clear_prelisting_gate_result(st.session_state)
    st.session_state.pop('classification_current_batch', None)


def _clear_inputs(key):
    for field in ('min', 'max'):
        st.session_state[key + field] = ''
    st.session_state[key + 'rating'] = '指定なし'


def render_filter_controls(key, *, provider):
    st.subheader('候補の絞り込み')
    st.caption('Amazon取得元：JP / Amazon.co.jp本体の参考価格と平均評価。条件一致はSafety通過・出品許可ではありません。')
    with st.form(key + 'form'):
        lower = st.text_input('価格下限（円・空欄は指定なし）', key=key + 'min')
        upper = st.text_input('価格上限（円・空欄は指定なし）', key=key + 'max')
        rating = st.selectbox('最低平均評価', ('指定なし', '4.0以上', '4.5以上'), key=key + 'rating')
        applied = st.form_submit_button('適用', key=key + 'apply')
        cleared = st.form_submit_button('解除', key=key + 'clear', on_click=_clear_inputs, args=(key,))
    if applied or cleared:
        invalidate_filter_outputs()
        st.session_state.pop(key + 'invalid', None)
        st.session_state.pop(key + 'refresh_error', None)
        try:
            def price(value):
                if not value.strip():
                    return None
                if not value.strip().isascii() or not value.strip().isdigit():
                    raise ValueError('価格は0以上の整数（円）で指定してください。')
                return int(value.strip())
            if rating not in ('指定なし', '4.0以上', '4.5以上'):
                raise ValueError('最低平均評価を選び直してください。')
            criteria = FilterCriteria() if cleared else FilterCriteria(
                price_min_jpy=price(lower), price_max_jpy=price(upper),
                rating_min={'指定なし': None, '4.0以上': 4.0, '4.5以上': 4.5}[rating])
            st.session_state[key + 'criteria'] = criteria
        except ValueError as exc:
            st.session_state[key + 'invalid'] = str(exc)
    criteria = st.session_state.get(key + 'criteria', FilterCriteria())
    blocked = st.session_state.get(key + 'invalid')
    if criteria.active and provider != 'keepa':
        blocked = 'Canopy TESTは価格・平均評価の絞り込みに未対応です。解除するかKeepaの利用設定を確認してください。'
    if blocked:
        st.error(blocked)
    if criteria.active:
        st.caption(f'適用中：価格 {criteria.price_min_jpy if criteria.price_min_jpy is not None else "指定なし"} ～ {criteria.price_max_jpy if criteria.price_max_jpy is not None else "指定なし"} 円 / 最低評価 {criteria.rating_min or "指定なし"}。条件変更は追加APIなし。')
    return criteria, bool(blocked)


def render_filter_results(rows, criteria, *, key, blocked=False, offline_only=False, client_factory=None):
    if not criteria.active and not blocked:
        return list(rows)
    if blocked:
        return []
    partition = partition_rows(rows, None, criteria)
    identity = (criteria.fingerprint, tuple(item.evaluation.fingerprint for item in partition.evaluations))
    if st.session_state.get(key + 'identity') not in (None, identity):
        invalidate_filter_outputs()
    st.session_state[key + 'identity'] = identity
    counts = partition.counts
    cols = st.columns(3)
    for col, label, status in zip(cols, ('一致件数', '条件外件数', '未確認件数'), ('MATCH', 'OUT_OF_RANGE', 'UNKNOWN')):
        col.metric(label, counts[status])
    display = []
    missing = set()
    for item in partition.evaluations:
        evaluation = item.evaluation
        observation = evaluation.observation or {}
        display.append({'source_id': item.row.get('source_id', ''), 'ASIN': item.asin,
            '判定': evaluation.status, 'Amazon参考価格（円）': observation.get('price_jpy'),
            '平均評価': observation.get('rating'), '取得時刻': observation.get('captured_at', ''),
            '価格取得時刻': observation.get('price_captured_at', ''),
            '評価取得時刻': observation.get('rating_captured_at', ''),
            '提供元更新時刻': observation.get('provider_updated_at', ''),
            '提供元評価更新時刻': observation.get('rating_updated_at', ''),
            '価格取得状態': evaluation.price_reason or evaluation.price_status,
            '評価取得状態': evaluation.rating_reason or evaluation.rating_status})
        if observation_needs_capture(item.row, criteria):
            missing.add(item.asin)
    st.dataframe(display, hide_index=True, width='stretch')
    maximum = len(missing) * (2 if criteria.rating_min is not None else 1)
    st.caption(f'不足情報の追加取得：対象 {len(missing)} ASIN / 最大 {maximum} tokens（基本1＋評価指定時最大1／商品、概算・未実測）。取得済み欠損は自動再取得しません。')
    if offline_only:
        st.caption('offline画面：実APIの追加取得は別承認後に行います。')
    if st.session_state.get(key + 'refresh_error'):
        st.error(st.session_state[key + 'refresh_error'])
    refresh = st.button('不足情報を取得（API・表示した枠内）', key=key + 'refresh',
                        disabled=offline_only or not missing or client_factory is None)
    if refresh and not offline_only and missing and client_factory is not None:
        invalidate_filter_outputs()
        st.session_state.pop(key + 'refresh_error', None)
        # Remove current success before attempting any external operation.
        for row in rows:
            asin = str(row.get('candidate_asin') or row.get('asin') or '')
            if asin in missing:
                row.pop('candidate_observation', None)
        try:
            client = client_factory()
            plan = client.plan_candidate_observation_fetch(sorted(missing), criteria)
            products = client.fetch_candidate_observations(plan, criteria,
                token_budget=maximum, max_products=len(missing))
            for row in rows:
                asin = str(row.get('candidate_asin') or row.get('asin') or '')
                if asin in missing:
                    row['candidate_observation'] = products.get(asin, {}).get('candidate_observation')
        except Exception:
            st.session_state[key + 'refresh_error'] = '不足情報を取得できませんでした。旧一致結果を失効しました。取得枠・認証・接続を確認してください。'
        st.rerun()
    if st.session_state.get(key + 'refresh_error'):
        st.info('追加取得に失敗したため、現在のCandidate CSV・Gate引継ぎを停止しています。明示的に再取得するか、条件を適用し直してください。')
        return []
    if not partition.matched_rows:
        st.info('一致候補は0件です。現在の条件一致Candidate CSV・Gate引継ぎは生成しません。')
        return []
    return partition.matched_rows


def render_filter_confirmation(rows, criteria, candidate_content, *, key, marketplace):
    if not criteria.active:
        return
    st.download_button('絞り込み確認CSV（Gate入力不可）',
        data=confirmation_csv_bytes(rows, criteria, candidate_content, marketplace=marketplace or 'PH'),
        file_name='candidate_filter_confirmation.csv', mime='text/csv', key=key + 'confirmation')
