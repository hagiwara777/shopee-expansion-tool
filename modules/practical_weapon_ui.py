"""Offline weapon replay and targeted human review; existing validators only."""
import copy
import json

import streamlit as st

from modules.product_review import WeaponImageReviewSession
from modules.sg_beta_facts import digest
from modules.sg_beta_workbench import _sources, recommendation, _weapon_blocker, capture_weapon_review
from modules.weapon_image_inspection import WeaponImageInspection


def weapon_source_binding(record, market):
    return digest([market, record['asin'], record['facts'], record['source'], record['weapon']['images']])


def _save(workflow, record, weapon, note, *, result='OFFLINE_REVIEW'):
    bench = workflow.bench
    with bench._transaction() as conn:
        value = bench._selection(conn, {record['asin']: record['revision']})[0]
        value['weapon'] = copy.deepcopy(weapon)
        value['category'] = value['brand'] = None
        bench._note(value, 'WEAPON', result, note)
        bench._update_assessment(value, bench._assess(value))
        bench.store.write(conn, value, action='WEAPON_REVIEW', expected_revision=value['revision'])


def _session(record, market):
    _, text, _, _ = _sources(record)
    item = recommendation(record, marketplace=market)
    if _weapon_blocker(record, item, text) not in (None, 'WEAPON_REVIEW_REQUIRED'):
        raise ValueError('Current weapon evidence required')
    review = WeaponImageReviewSession(market)
    review.supply(item, text=text.facts_by_asin[record['asin']], images=record['weapon']['images'])
    if record['weapon'].get('inspection'):
        review.finish_image_inspection(item, evidence_binding=review.current(item).binding,
                                       inspection=WeaponImageInspection(**record['weapon']['inspection']))
    return item, review


def render_weapon_controls(workflow, *, key):
    market = workflow.session.scope.marketplace
    records = [r for r in workflow.bench.store.products() if r.get('weapon')]
    if not records:
        return
    with st.expander('武器画像の対象・疑義・復旧', expanded=False):
        asin = st.selectbox('画像の確認対象ASIN', [r['asin'] for r in records], key=key+'asin')
        record = next((r for r in records if r['asin']==asin), None)
        if record is None:
            st.error('現在の商品を選択し直してください。')
            return
        try:
            item, review = _session(record, market)
        except (ValueError, RuntimeError, KeyError, TypeError):
            st.info('現在の商品文章・画像資料を再受付してください。他市場の評価は利用できません。')
            return
        target = review.image_inspection_required(item)
        st.caption(f'{market}：' + ('対象・検査が必要' if target else '対象外・未実行（追加の画像確認は不要）'))
        if not target:
            return
        key = key + asin + '_'
        st.caption('offline模擬検査だけを読み込みます。画像取得・実APIは呼びません。疑義なしでは追加の人間確認を要求しません。')
        upload = st.file_uploader('対象商品の模擬武器画像検査（JSON）', type=['json'], key=key+'replay')
        fingerprint = digest([asin, upload.getvalue().hex()]) if upload is not None else None
        if st.session_state.get(key+'replay_binding') != fingerprint:
            st.session_state[key+'replay_binding'] = fingerprint
            # Updating/removing an active replay expires it before parsing a
            # replacement. Save failure expires the target's P1 proof as well.
            if upload is not None or st.session_state.get(key+'loaded') == asin:
                invalid = {**record['weapon'], 'inspection':None, 'decision':None, 'note':''}
                try:
                    _save(workflow, record, invalid, '模擬画像検査の更新開始・旧確認失効')
                except (ValueError, RuntimeError, OSError):
                    workflow.session.begin_fact_refresh(asin)
                    st.error('画像確認の失効を保存できません。商品根拠を停止しました。')
                    return
                st.session_state[key+'loaded'] = None
                st.rerun()
        if st.button('模擬検査を検証して読み込む', key=key+'load', disabled=upload is None):
            try:
                bundle = json.loads(upload.getvalue().decode('utf-8-sig'))
                if (bundle['schema'] != 'PH_SG_P4_WEAPON_OFFLINE_V1' or bundle['marketplace'] != market
                        or bundle['asin'] != asin or bundle['source_binding'] != weapon_source_binding(record, market)
                        or bundle['weapon']['images'] != record['weapon']['images']
                        or bundle['weapon'].get('decision') is not None):
                    raise ValueError('Current market/product replay required')
                candidate = {**record, 'weapon':bundle['weapon']}
                _session(candidate, market)  # Existing digest, URL coverage, status and policy validation.
                _save(workflow, record, bundle['weapon'], '模擬画像検査を検証・明示読込')
            except (ValueError, RuntimeError, OSError, KeyError, TypeError):
                st.error('模擬検査が現在の商品・市場・画像と一致しません。準備は停止したままです。')
            else:
                st.session_state[key+'loaded'] = asin
                st.rerun()
        render_weapon_decision(workflow, record, item, review, key=key)


def render_weapon_decision(workflow, record, item, review, *, key, offline=True):
    inspection = review.current_image_inspection(item)
    if inspection is None:
        st.info('対象の画像検査は未実施です。現在根拠に一致する模擬検査を読み込んでください。'
                if offline else '対象の画像検査は未実施です。承認済みの取得経路で検査してください。')
        return
    st.caption(('模擬検査：' if offline else '今回の画像検査：') + inspection.system_status + ' / ' + str(inspection.ai_status))
    if inspection.system_status == 'COMPLETED' and inspection.ai_status == 'NO_SIGNAL':
        st.caption('模擬画像で疑義なし。追加の人間確認は不要です。' if offline else '画像疑義なし。追加の人間確認は不要です。')
        return
    note = st.text_area('武器疑義の判断根拠', key=key+'note')
    binding = digest([record['revision'], workflow.session.evidence_revision, inspection.evaluation_id, note])
    if st.session_state.get(key+'human_binding') != binding:
        st.session_state[key+'human_binding'] = binding
        st.session_state[key+'human'] = False
    checked = st.checkbox('この商品の武器疑義について十分な画像を確認しました', key=key+'human')
    for decision, label in [('ALLOW_PREPARATION','画像疑義だけの準備継続を記録'), ('EXCLUDE','武器画像の確認で除外')]:
        if st.button(label, key=key+decision, disabled=not checked or not note.strip()):
            try:
                review.record_weapon_decision(item, decision=decision, reviewed_images=checked, note=note)
                _save(workflow, record, capture_weapon_review(item, review, images=record['weapon']['images']), note,
                      result='OFFLINE_REVIEW' if offline else 'P5_HUMAN_REVIEW')
            except (ValueError, RuntimeError, OSError):
                st.error('画像判断を保存できません。現在資料と既存Safety停止を確認してください。')
            else:
                st.rerun()
