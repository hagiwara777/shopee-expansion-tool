"""Shared minimum P3 controls in the usual Mapper tab; full UI remains P4."""
from dataclasses import asdict, replace
import json
from pathlib import Path

import streamlit as st

from modules.beta_work_store import BetaWorkStore
from modules.beta_workbench import BetaWorkBench
from modules.classification_workflow import ClassificationWorkflow, ClassificationSelection, records_from_producer
from modules.category_ai_core import CategoryCatalog, CategoryNode
from modules.preparation_validity import PreparationSession
from modules.sg_beta_facts import CategoryRule, digest
from modules.sg_beta_workbench import BrandAlias, BrandObservation


def load_offline_catalog(workflow, content):
    """Same strict catalog model and limited definitions; no operational permits."""
    workflow.session.begin_catalog_refresh()
    value = json.loads(content.decode('utf-8-sig'))
    market = workflow.session.scope.marketplace
    if value['schema'] != 'PH_SG_P3_OFFLINE_V1' or value['marketplace'] != market:
        raise ValueError('Classification marketplace/schema mismatch')
    catalog = CategoryCatalog(market, value['version'],
        tuple(CategoryNode(**n) for n in value['nodes']))
    rules = tuple(CategoryRule(**{**r, **{k: tuple(r[k]) for k in
        ('leaf_names', 'required_text', 'excluded_text')}}) for r in value['rules'])
    aliases = tuple(BrandAlias(**a) for a in value['aliases'])
    if any(r.scope != 'OFFLINE_ONLY' for r in (*rules, *aliases)):
        raise ValueError('Offline bundle cannot activate operational rules')
    observations = tuple(BrandObservation(**{**b, 'brands': tuple(tuple(o) for o in b['brands'])})
                         for b in value['brands'])
    if (len({b.category_id for b in observations}) != len(observations)
            or any(b.marketplace != market or b.shop_id != workflow.session.scope.shop_id
                   or b.source != 'OFFLINE_MOCK' or not b.current or not b.complete for b in observations)):
        raise ValueError('Unique complete mock Brand observations required')
    workflow.supply_catalog(catalog, reference=digest(value), rules=rules,
                            aliases=aliases, revision=value['revision'])
    for observation in observations:
        workflow.supply_mock_brand(observation)


def _action(call):
    try:
        call()
    except (ValueError, RuntimeError, OSError, KeyError, TypeError):
        st.error('保存できませんでした。最新資料・選択商品・保存先を確認し、選択し直してください。')
        return
    st.success('選択商品の操作を保存しました。')
    st.rerun()


def render_classification_workspace(marketplace, *, db_path, shop_id, workflow=None,
                                    controls_renderer=None):
    if (marketplace not in {'PH', 'SG'} or not isinstance(shop_id, str) or not shop_id.strip()
            or (workflow is not None and (workflow.session.scope.marketplace != marketplace
                                         or workflow.session.scope.shop_id != shop_id))):
        st.error('作業対象の市場・ショップを確認してください。')
        return
    practical = controls_renderer is not None
    st.subheader('分類・準備・出品管理' if practical else 'Category / Brand確認')
    st.caption(f'{marketplace} / ショップ {shop_id}：選択した商品だけを確認・保存します。')
    st.info('offline操作用。模擬catalog・Brand・限定AUTO_RULEは公式取得済みではありません。実出品には使えません。'
            if practical else 'P3 offline確認用。模擬Brand・限定AUTO_RULEは実運用の出力許可になりません。')
    key = 'p3_' + marketplace + '_'
    if workflow is None:
        path = Path(db_path)
        if not path.exists():
            if st.button('新しい作業保存先を作成', key=key+'create'):
                _action(lambda: BetaWorkStore.create(path, marketplace=marketplace, shop_id=shop_id))
            return
        binding = (str(path.resolve()), marketplace, shop_id)
        saved = st.session_state.get(key+'workflow')
        if saved is None or st.session_state.get(key+'workspace') != binding:
            try:
                store = BetaWorkStore(path, marketplace=marketplace, shop_id=shop_id)
                saved = ClassificationWorkflow(BetaWorkBench(store, PreparationSession(marketplace, shop_id)))
            except (ValueError, RuntimeError, OSError):
                st.error('保存先を開けません。市場・ショップ・新規作業DBを確認してください。')
                return
            st.session_state[key+'workflow'] = saved
            st.session_state[key+'workspace'] = binding
        workflow = saved
        with st.expander('管理・分類資料設定', expanded=False):
            st.caption('模擬資料を使用します。再取得・読込失敗後は同じ内容でもCategory / Brandを再確認してください。')
            catalog_file = st.file_uploader('今回の分類資料（offline JSON）', type=['json'], key=key+'catalog')
            reload_catalog = st.button('分類資料を再読込（旧確認を失効）', key=key+'reload', disabled=catalog_file is None)
        catalog_hash = digest(catalog_file.getvalue().hex()) if catalog_file else None
        if st.session_state.get(key+'catalog_hash') != catalog_hash or reload_catalog:
            workflow.session.begin_catalog_refresh()
            st.session_state[key+'catalog_hash'] = catalog_hash
            if catalog_file:
                try:
                    load_offline_catalog(workflow, catalog_file.getvalue())
                except (ValueError, RuntimeError, KeyError, TypeError):
                    workflow.session.begin_catalog_refresh()
                    st.error('分類資料を確認できません。未確認のまま停止します。')
        render_current_batch(workflow, marketplace, key=key)
    if controls_renderer is None:
        render_classification_controls(workflow, key=key)
    else:
        controls_renderer(workflow, key=key)


def render_current_batch(workflow, marketplace, *, key):
    batch = st.session_state.get('classification_current_batch')
    if batch is None or batch['marketplace'] != marketplace:
        if not st.session_state.get(key+'inventory_missing'):
            workflow.session.begin_inventory_refresh()
        st.session_state[key+'inventory_missing'] = True
        st.info('保安ゲートで今回の候補・全ショップCSVを確認してください。保存済み履歴は保持します。')
    else:
        st.session_state[key+'inventory_missing'] = False
        if st.session_state.get(key+'batch_binding') != batch['product_binding']:
            # New/changed normal material expires affected existing products
            # before any new intake action. Adding B does not invalidate A.
            try:
                incoming = records_from_producer(marketplace=marketplace, **batch['product_arguments'])
                existing = {r['asin']: r for r in workflow.bench.store.products()}
                for record in incoming:
                    previous = existing.get(record['asin'])
                    if previous and any(previous.get(k) != record.get(k) for k in ('facts', 'source', 'weapon')):
                        workflow.session.begin_fact_refresh(record['asin'])
                st.session_state[key+'batch_binding'] = batch['product_binding']
            except (ValueError, RuntimeError, KeyError, TypeError):
                workflow.session.begin_inventory_refresh()
                st.error('今回の商品根拠を照合できません。確認・保存を停止します。')
                return
        # Gate labels are internal evidence labels, not authenticated shop IDs.
        # Explicitly bind each uploaded file to the actual shop before P1 use.
        labels = [st.text_input(f'{i.source_file} のショップID', key=key+'shop_'+str(n))
                  for n, i in enumerate(batch['inventories'])]
        inventory_binding = digest([batch['inventory_binding'], labels])
        if st.session_state.get(key+'inventory_binding') != inventory_binding:
            workflow.session.begin_inventory_refresh()
            st.session_state[key+'current'] = False
            st.session_state[key+'inventory_binding'] = inventory_binding
        current = st.checkbox('全ショップ分の今回の最新出品CSVと対応を確認しました', key=key+'current')
        if not current and st.session_state.get(key+'inventory_was_current'):
            workflow.session.begin_inventory_refresh()
        st.session_state[key+'inventory_was_current'] = current
        if st.button('今回の商品根拠を確認待ちへ保存', key=key+'ingest', disabled=not current):
            def ingest():
                workflow.supply_inventory(tuple(replace(i, shop_label=label) for i, label in
                    zip(batch['inventories'], labels, strict=True)), expected_shops=labels,
                    reference=inventory_binding, confirmed_current=current)
                records = records_from_producer(marketplace=marketplace,
                    **batch['product_arguments'])
                workflow.ingest(records, scope=workflow.session.scope, batch_ref=batch['product_binding'])
            _action(ingest)


def render_classification_controls(workflow, *, key='p3_', practical=False):
    try:
        display_revision = workflow.session.evidence_revision
        records = workflow.bench.refresh()
        context = workflow.session.classification_context()
        if display_revision != workflow.session.evidence_revision:
            raise ValueError('Preparation material changed during display')
    except (ValueError, RuntimeError, OSError):
        st.info('現在の分類資料・全ショップ資料を確認すると分類操作へ進めます。')
        return
    if practical:
        from modules.practical_beta_ui import filter_queue, decision_label, state_label, recovery_text
        records = filter_queue(records, key=key)
    else:
        st.metric('現在の準備pool', len(workflow.bench.prepared_pool()))
    st.dataframe([{'ASIN': r['asin'], '商品名': r['facts']['fields']['title']['value'],
        'Category': (r.get('category') or {}).get('category_id'),
        'Category確認': (decision_label(r, 'category') if practical else
                        (r.get('category') or {}).get('authority', '未確認')),
        'Brand': (r.get('brand') or {}).get('brand_name', '未確認'),
        'Brand確認': (decision_label(r, 'brand') if practical else
                     (r.get('brand') or {}).get('authority', '未確認')),
        '状態': state_label(r) if practical else r['state'],
        '確認事項': ' / '.join(r['assessment']['reasons']),
        **({'必要な操作': recovery_text(r)} if practical else {})} for r in records])
    groups = sorted({r['facts']['fields']['brand']['value'] + ' | ' +
        ' > '.join(n['name'] for n in r['facts']['fields']['category_tree']['value']) for r in records})
    group = st.selectbox('商品グループ', ['全商品', *groups], key=key+'group')
    shown = [r for r in records if group == '全商品' or group ==
        r['facts']['fields']['brand']['value'] + ' | ' +
        ' > '.join(n['name'] for n in r['facts']['fields']['category_tree']['value'])]
    shown_binding = digest([group, [r['asin'] for r in shown]])
    if st.session_state.get(key+'shown_binding') != shown_binding:
        st.session_state[key+'shown_binding'] = shown_binding
        st.session_state[key+'selected'] = []
    selected = st.multiselect('操作するASIN（選択分だけ採用）', [r['asin'] for r in shown], key=key+'selected')
    if any(a not in {r['asin'] for r in shown} for a in selected):
        st.error('表示中の商品の中から選択し直してください。')
        return
    selection_binding = digest([asdict(workflow.session.scope), display_revision,
        [(r['asin'], r['revision']) for r in shown], selected])
    if st.session_state.get(key+'selection_binding') != selection_binding:
        st.session_state[key+'selection_binding'] = selection_binding
        st.session_state[key+'human'] = False
        # Bind the displayed revisions. Never silently upgrade a stale screen
        # by re-reading newer revisions while constructing its selection.
        st.session_state[key+'selection'] = (ClassificationSelection(workflow.session.scope,
            display_revision,
            tuple((r['asin'], r['revision']) for r in shown if r['asin'] in selected)) if selected else None)
    selection = st.session_state.get(key+'selection')
    query = st.text_input('Category検索', key=key+'category_query')
    categories = [n for n in context.catalog.nodes if n.is_leaf and query.casefold() in n.category_path.casefold()]
    category_id = st.selectbox('Category候補', [n.category_id for n in categories],
        format_func=lambda cid: context.catalog.get(cid).category_path, index=None, key=key+'category')
    brand_query = st.text_input('Brand検索', key=key+'brand_query')
    options = [workflow.candidates(a, kind='BRAND', query=brand_query)['options'] for a in selected]
    brands = [b for b in options[0] if all(b in others for others in options[1:])] if options else []
    brand_id = st.selectbox('Brand / No Brand候補', [b['id'] for b in brands],
        format_func=lambda bid: next(b['name'] for b in brands if b['id'] == bid), index=None, key=key+'brand')
    reviewer = st.text_input('確認者', key=key+'reviewer')
    note = st.text_area('判断根拠', key=key+'note')
    action_binding = digest([selection_binding, category_id, brand_id, reviewer, note])
    if st.session_state.get(key+'action_binding') != action_binding:
        st.session_state[key+'action_binding'] = action_binding
        st.session_state[key+'human'] = False
    human = st.checkbox('選択した商品と今回の操作を確認しました', key=key+'human')
    enabled = bool(selection and reviewer.strip() and note.strip() and human)
    for kind, option_id, label in [('CATEGORY', category_id, 'Category'), ('BRAND', brand_id, 'Brand')]:
        if st.button(label+'を人間確認して保存', disabled=not enabled or option_id is None,
                     key=key+'confirm_'+kind):
            _action(lambda: workflow.confirm(selection, kind=kind, option_id=option_id,
                reviewer=reviewer, note=note, human_verified=human))
        supported = bool(selected) and all(workflow.candidates(a, kind=kind)['auto'] for a in selected)
        if st.button(label+'の限定AUTO_RULEを適用（offline）', disabled=not enabled or not supported,
                     key=key+'auto_'+kind):
            _action(lambda: workflow.apply_auto(selection, kind=kind, reviewer=reviewer, note=note))
        if st.button(label+'の採用を取り消す', disabled=not enabled, key=key+'revoke_'+kind):
            _action(lambda: workflow.revoke(selection, kind=kind, reviewer=reviewer, note=note))
