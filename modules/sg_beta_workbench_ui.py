"""Optional offline work area inside the existing beta app; no API discovery."""
import json

import streamlit as st

from modules.category_mapper_sg import parse_sg_category_catalog
from modules.listing_inventory_parser import parse_listing_inventory_csv
from modules.sg_beta_facts import CategoryRule, ProductFacts, digest
from modules.sg_beta_workbench import BrandAlias, BrandObservation, ValidationContext, SGWorkBench
from modules.sg_beta_work_store import SGWorkStore, SGWorkError

STATE_LABELS = {'WAITING': '出品待ち', 'AWAITING_LISTING': '出品確認待ち', 'LISTED': '出品済み',
                'ERROR': '出品エラー', 'RECHECK': '再確認必要'}


def context_from_bundle(content, *, inventories, shop_id, inventory_current, inventory_ref):
    """Read explicit offline examples; saved official DB is comparison only."""
    value = json.loads(content.decode('utf-8-sig'))
    if set(value) != {'schema', 'catalog_csv', 'catalog_current', 'brands', 'rules', 'aliases'} or value['schema'] != 'SG_INITIAL_BETA_OFFLINE_V1':
        raise SGWorkError('Invalid offline work context')
    catalog = parse_sg_category_catalog(value['catalog_csv'].encode('utf-8-sig'), filename='sg_catalog.csv')
    observations = {}
    for raw in value['brands']:
        observation = BrandObservation(**{**raw, 'brands': tuple(tuple(b) for b in raw['brands'])})
        if observation.shop_id != shop_id or observation.source != 'OFFLINE_MOCK' or observation.category_id in observations:
            raise SGWorkError('Explicit mock SG Brand observations required')
        observations[observation.category_id] = observation
    rules = []
    for raw in value['rules']:
        rule = CategoryRule(**{**raw, **{k: tuple(raw[k]) for k in ('leaf_names', 'required_text', 'excluded_text')}})
        if rule.scope != 'OFFLINE_ONLY':
            raise SGWorkError('Operational rule activation requires separate acceptance')
        rules.append(rule)
    return ValidationContext(catalog, value['catalog_current'], observations, tuple(rules),
        tuple(BrandAlias(**a) for a in value['aliases']), tuple(inventories), 1,
        inventory_current, inventory_ref)


def _action(call):
    try:
        result = call()
    except (ValueError, RuntimeError, OSError):
        st.error('操作を完了できませんでした。商品・最新資料・保存先を再確認してください。状態は成功扱いにしません。')
        return None
    st.success('操作を保存しました。')
    st.rerun()
    return result


def render_sg_workbench(*, db_path, shop_id, bench=None):
    st.subheader('SG初期Beta：継続作業')
    st.info('offline検証用です。Brand一覧は模擬資料です。実出品や実APIの確認を意味しません。')
    if bench is None:
        from pathlib import Path
        path = Path(db_path)
        if not path.exists():
            if st.button('新しいSG作業保存先を作成', key='sg_work_create'):
                _action(lambda: SGWorkStore.create(path, shop_id=shop_id))
            return
        try:
            store = SGWorkStore(path, shop_id=shop_id)
        except (ValueError, OSError):
            st.error('SG作業保存先を開けません。既存DBは初期化しません。')
            return
        uploads = st.file_uploader('分類確認用offline資料（JSON）', type=['json'], key='sg_work_context')
        files = st.file_uploader('SGの全ショップ既出品CSV（初回は1ショップ）', type=['csv'],
                                 accept_multiple_files=True, key='sg_work_inventory')
        fingerprint = digest([uploads.getvalue().hex() if uploads else '',
                              [(f.name, f.getvalue().hex()) for f in files or []]])
        if st.session_state.get('sg_work_context_fingerprint') != fingerprint:
            st.session_state['sg_work_context_fingerprint'] = fingerprint
            st.session_state['sg_work_inventory_current'] = False
        current = st.checkbox('今回のSGショップの最新CSVであることを確認', key='sg_work_inventory_current')
        if uploads is None or not files:
            st.dataframe([{'ASIN': p['asin'], '出品作業': STATE_LABELS[p['state']]} for p in store.products()])
            st.caption('保存済み履歴は保持しています。現在資料を読み込むと確認・再評価できます。')
            return
        try:
            if len(files) != 1:
                raise SGWorkError('First acceptance uses one SG shop')
            inventories = [parse_listing_inventory_csv(f.getvalue(), filename=f.name, marketplace='SG',
                                                        shop_label=shop_id) for f in files]
            context = context_from_bundle(uploads.getvalue(), inventories=inventories, shop_id=shop_id,
                                          inventory_current=current, inventory_ref=fingerprint)
            bench = SGWorkBench(store, context)
        except (ValueError, RuntimeError, KeyError, TypeError):
            st.error('offline分類資料とSG既出品CSVを確認してください。出力は停止しています。')
            return
        with st.expander('新しい候補群を保存'):
            candidate = st.file_uploader('Expansion / Resolver候補CSV', type=['csv'], key='sg_work_candidates')
            facts_file = st.file_uploader('商品Factと項目別出所（JSON）', type=['json'], key='sg_work_facts')
            text = st.file_uploader('商品文章Safety CSV', type=['csv'], key='sg_work_text')
            ingredients = st.file_uploader('Ingredient Safety CSV', type=['csv'], key='sg_work_ingredients')
            body = st.file_uploader('SG本体確認記録（任意）', type=['json'], key='sg_work_body')
            weapon = st.file_uploader('保存済みSG武器画像確認（任意）', type=['json'], key='sg_work_weapon')
            operation = st.text_input('取得operationの参照（任意）', key='sg_work_operation')
            if st.button('候補群と確認待ちを保存', disabled=candidate is None or facts_file is None, key='sg_work_ingest'):
                def ingest():
                    records = json.loads(facts_file.getvalue().decode('utf-8-sig'))
                    facts = {r['asin']: ProductFacts.from_dict(r) for r in records}
                    if len(facts) != len(records):
                        raise SGWorkError('Duplicate Fact ASIN')
                    return bench.ingest(candidate_content=candidate.getvalue(), filename=candidate.name,
                        facts=facts, text_content=text.getvalue() if text else None,
                        ingredient_content=ingredients.getvalue() if ingredients else None,
                        body_confirmations=json.loads(body.getvalue().decode('utf-8-sig')) if body else None,
                        weapon_records=json.loads(weapon.getvalue().decode('utf-8-sig')) if weapon else None,
                        operation_ref=operation)
                _action(ingest)
    render_work_queues(bench)


def render_work_queues(bench):
    try:
        records = bench.refresh()
        operations = bench.store.operations()
    except (ValueError, RuntimeError, OSError):
        st.error('再評価・保存に失敗しました。確認や出力は停止しています。')
        return
    if not records:
        st.caption('保存済み商品はありません。')
        return
    queues = ('出品待ち', 'Safety確認待ち', 'Category確認待ち', 'Brand確認待ち', '出品作業状態', '全商品')
    queue = st.selectbox('作業対象', queues, key='sg_work_queue')
    if queue not in queues:
        st.error('作業対象を確認してください。')
        return
    locks = {a for op in operations if op['state'] in {'PENDING', 'UNKNOWN'} for a in op['asins']}
    predicates = {
        '出品待ち': lambda r: r['assessment']['valid'] and r['state'] == 'WAITING' and r['asin'] not in locks,
        'Safety確認待ち': lambda r: bool(r['assessment']['safety_reasons']),
        'Category確認待ち': lambda r: not r['assessment']['category_valid'],
        'Brand確認待ち': lambda r: not r['assessment']['brand_valid'],
        '出品作業状態': lambda r: r['state'] != 'WAITING' or r['asin'] in locks,
        '全商品': lambda r: True}
    shown = [r for r in records if predicates[queue](r)]
    def group_key(r):
        category = r.get('category')
        brand = r.get('brand')
        return ('SG | ' + (str(category['category_id']) if category else
                ' > '.join(n['name'] for n in r['facts']['fields']['category_tree']['value']))
                + ' | ' + (str(brand['brand_id']) + ' ' + brand['brand_name'] if brand else
                            r['facts']['fields']['brand']['value']))
    groups = sorted({group_key(r) for r in shown})
    group = st.selectbox('類似商品グループ', ('全グループ', *groups), key='sg_work_group')
    if group != '全グループ':
        shown = [r for r in shown if group_key(r) == group]
    # Explicit subset permits exceptions; never treat all members as adopted.
    st.dataframe([{'ASIN': r['asin'], '商品名': r['facts']['fields']['title']['value'],
                  '出品作業': STATE_LABELS[r['state']], '確認事項': ' / '.join(r['assessment']['reasons']),
                  'Category': r.get('category'), 'Brand': r.get('brand'),
                  'コピー結果待ち': r['asin'] in locks} for r in shown])
    selected = st.multiselect('同じ分類・必須属性値を適用できるASINを選択（例外は外す）',
                              [r['asin'] for r in shown], key='sg_work_selected')
    if any(a not in {r['asin'] for r in shown} for a in selected):
        st.error('現在の一覧から選択し直してください。')
        return
    expected = {r['asin']: r['revision'] for r in shown if r['asin'] in selected}
    categories = [n for n in bench.context.catalog.nodes if n.is_leaf]
    category_id = st.selectbox('採用するleaf Category', [n.category_id for n in categories],
                              format_func=lambda cid: bench.context.catalog.get(cid).category_path, key='sg_work_category')
    brands = bench.context.brands.get(category_id)
    brand_ids = [b[0] for b in brands.brands] if brands else []
    brand_id = st.selectbox('採用するBrand / No Brand', brand_ids,
        format_func=lambda bid: next(f'{b[0]} | {b[1]}' for b in brands.brands if b[0] == bid), key='sg_work_brand')
    note = st.text_area('確認根拠・作業メモ', key='sg_work_note')
    # Reset before widget creation. A later rerun cannot revive an old check.
    selection_binding = digest([expected, category_id, brand_id, note])
    if st.session_state.get('sg_work_selection_binding') != selection_binding:
        st.session_state['sg_work_selection_binding'] = selection_binding
        st.session_state['sg_work_human'] = False
    confirmed = st.checkbox('選択した全ASINと今回の操作を確認しました', key='sg_work_human')
    enabled = bool(expected) and confirmed and bool(note.strip())
    if st.button('選択商品のCategoryを一括確認', disabled=not enabled, key='sg_work_confirm_category'):
        _action(lambda: bench.confirm(expected, kind='CATEGORY', option_id=category_id, human_verified=confirmed, note=note))
    if st.button('選択商品のBrandを一括確認', disabled=not enabled or brand_id is None, key='sg_work_confirm_brand'):
        _action(lambda: bench.confirm(expected, kind='BRAND', option_id=brand_id, human_verified=confirmed, note=note))
    for kind, label in (('CATEGORY', 'Category'), ('BRAND', 'Brand')):
        if st.button(f'{label}確定を取り消す', disabled=not enabled, key='sg_work_revoke_' + kind):
            _action(lambda kind=kind: bench.revoke(expected, kind=kind, note=note))
    if st.button('Safety確認メモを保存・再評価', disabled=not enabled, key='sg_work_review'):
        _action(lambda: bench.record_review(expected, result='EVIDENCE_REVIEWED', note=note))
    for action, label in (('ERROR', '出品エラーを一括登録'), ('RETURN', '出品待ちへ戻す')):
        if st.button(label, disabled=not enabled, key='sg_work_listing_' + action):
            _action(lambda action=action: bench.listing_action(expected, action=action, human_confirmed=confirmed, note=note))
    for reserve, label in ((False, 'CSV / TXTを作成'), (True, '一括コピー用TXTを準備')):
        if st.button(label, disabled=not expected, key='sg_work_output_' + str(reserve)):
            try:
                files = bench.output(expected, reserve_copy=reserve)
            except (ValueError, RuntimeError, OSError):
                st.error('出力できません。最新の準備状態と保存先を確認してください。')
            else:
                # Render only in this explicit action run; no stale download cache.
                st.download_button('選択商品のCSV', files[0], file_name='sg_initial_beta.csv', mime='text/csv', on_click='ignore')
                st.download_button('選択商品のTXT', files[1], file_name='sg_initial_beta.txt', mime='text/plain', on_click='ignore')
                st.code(files[1].decode('utf-8-sig'), language=None)
                st.caption('ダウンロードだけでは出品作業状態は変わりません。コピー結果は下で明示確認します。')
    operations = bench.store.operations()
    for operation in operations:
        if operation['state'] not in {'PENDING', 'UNKNOWN'}:
            continue
        oid = operation['operation_id']
        st.write('コピー結果の確認待ち：' + ', '.join(operation['asins']))
        outcome = st.selectbox('コピー結果', ('UNKNOWN', 'SUCCESS', 'FAILED', 'CANCELLED'),
            format_func=lambda x: {'UNKNOWN': '不明・再コピー停止', 'SUCCESS': 'コピー成功を確認',
                                  'FAILED': 'コピー失敗を確認', 'CANCELLED': '取消・再操作を許可'}[x], key='sg_work_outcome_' + oid)
        binding = digest([oid, operation['state'], outcome, note])
        if st.session_state.get('sg_work_copy_binding_' + oid) != binding:
            st.session_state['sg_work_copy_binding_' + oid] = binding
            st.session_state['sg_work_copy_confirm_' + oid] = False
        explicit = st.checkbox('このコピー結果を本人が確認しました', key='sg_work_copy_confirm_' + oid)
        if st.button('コピー結果を保存', disabled=not explicit or not note.strip(), key='sg_work_finish_' + oid):
            _action(lambda: bench.finish_copy(oid, outcome=outcome, note=note, human_confirmed=explicit))
    for q, label in (('SAFETY', 'Safety確認待ち'), ('CATEGORY', 'Category確認待ち'), ('BRAND', 'Brand確認待ち')):
        st.download_button(label + ' CSV', bench.queue_csv(queue=q), file_name='sg_' + q.lower() + '_queue.csv',
                           mime='text/csv', key='sg_work_queue_' + q)
    with st.expander('操作・確認・取消履歴'):
        st.dataframe([{'日時': e['created_at'], 'ASIN': e['asin'], '操作': e['action'],
                      '記録': e['payload']} for e in bench.store.history()])
