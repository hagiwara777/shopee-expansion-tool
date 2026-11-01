"""Normal Sora operations: manual ChatGPT Resolver and one-run safety Gate."""

import hashlib

import streamlit as st

from modules.asin_resolver import build_ai_prompt, build_source_map, preview_candidates, verify_preview_rows
from modules.listing_inventory_parser import parse_listing_inventory_csv
from modules.prelisting_gate_ui import build_prelisting_gate_preview_rows, localize_prelisting_gate_preview_rows
from modules.prelisting_sg_body_safety import prepare_body_confirmations
from modules.prelisting_sg_body_safety_ui import render_sg_body_review
from modules.research_csv_adapter import ResearchCsvInput, import_research_csvs
from modules.sora_run import evaluate_sora_run, prepare_sora_run, sora_exports
from modules.sp_api_catalog import SpApiCatalogClient, SpApiCatalogError, load_sp_api_credentials, planned_catalog_calls


def _clear_run():
    for key in list(st.session_state):
        if key in {'sora_run', 'sora_result', 'sora_body', 'sora_verified', 'sora_calls'} or key.startswith('sg_body_'):
            del st.session_state[key]


def _clear_resolver():
    _clear_run()
    for key in ('sora_preview', 'sora_selection', 'sora_prompt', 'sora_response', 'sora_response_fingerprint'):
        st.session_state.pop(key, None)


def render_sora_app():
    st.set_page_config(page_title='Sora', layout='wide')
    st.title('Sora')
    st.caption('Shopee調査 → ChatGPTでASIN候補を調べる → Amazonの商品情報を確認 → 出品前保安ゲート')
    marketplace = st.selectbox('対象国', ('SG', 'PH'), key='sora_marketplace')
    if st.session_state.get('sora_previous_marketplace') not in {None, marketplace}:
        _clear_resolver()
        st.session_state.pop('sora_source_fingerprint', None)
        st.session_state.pop('sora_source_input', None)
    st.session_state['sora_previous_marketplace'] = marketplace
    if st.button('新しい実行を始める', key='sora_new_run'):
        _clear_resolver()
        st.success('前回の商品資料・判定・確認結果を消しました。')

    st.header('1. ASIN Resolver')
    uploads = st.file_uploader('Shopee調査CSV（任意・複数選択可）', type=['csv'],
                              accept_multiple_files=True, key='sora_research_files')
    uploads = tuple(uploads or ())
    upload_fingerprint = (marketplace, tuple((f.name, hashlib.sha256(f.getvalue()).hexdigest()) for f in uploads))
    if st.session_state.get('sora_upload_fingerprint') not in (None, upload_fingerprint):
        _clear_resolver()
        st.session_state.pop('sora_source_input', None)
    st.session_state['sora_upload_fingerprint'] = upload_fingerprint
    if st.button('CSVの商品名をResolverへ渡す', disabled=not uploads, key='sora_import_research'):
        imported = import_research_csvs(
            [ResearchCsvInput(f.name, f.getvalue()) for f in uploads], marketplace=marketplace)
        _clear_resolver()
        st.session_state['sora_source_input'] = '\n'.join(
            f"{row['source_id']}\t{row['input_title']}" for row in imported.resolver_rows)
        st.info(f"入力{imported.summary['total_rows']}行／Resolver対象{len(imported.resolver_rows)}行。対象外・重複は除きました。")
        if imported.deferred_rows:
            st.dataframe([{'商品名': r['raw_title'], '見送り理由': r['exclusion_reason']}
                          for r in imported.deferred_rows], hide_index=True)
    names = st.text_area('商品名（1行1商品、またはsource_idと商品名のTSV）',
                         key='sora_source_input', height=140)
    source_fingerprint = (marketplace, names)
    if st.session_state.get('sora_source_fingerprint') not in (None, source_fingerprint):
        _clear_resolver()
    st.session_state['sora_source_fingerprint'] = source_fingerprint
    if st.button('AI用プロンプト生成', disabled=not names.strip(), key='sora_generate_prompt'):
        st.session_state['sora_prompt'] = build_ai_prompt(names)
    if st.session_state.get('sora_prompt'):
        st.caption('コピーしてChatGPTへ手作業で貼り、返答を下に貼り戻してください。SoraからOpenAI APIは呼びません。')
        st.code(st.session_state['sora_prompt'], language='text')
        st.link_button('ChatGPTを開く', 'https://chatgpt.com/')
    response = st.text_area('AI返答／確認するASIN一覧', key='sora_response', height=160)
    response_fingerprint = (source_fingerprint, response)
    if st.session_state.get('sora_response_fingerprint') not in (None, response_fingerprint):
        _clear_run()
        st.session_state.pop('sora_preview', None)
        st.session_state.pop('sora_selection', None)
    st.session_state['sora_response_fingerprint'] = response_fingerprint
    if st.button('返答を解析', disabled=not response.strip(), key='sora_parse_response'):
        _clear_run()
        st.session_state.pop('sora_selection', None)
        st.session_state['sora_preview'] = preview_candidates(response, build_source_map(names) if names.strip() else None)
    preview = st.session_state.get('sora_preview', [])
    if preview:
        displayed = [{key: row.get(key, '') for key in
                     ('selected', 'source_id', 'input_title', 'asin', 'note')} for row in preview]
        selected = st.data_editor(displayed, key='sora_selection', hide_index=True,
            disabled=('source_id', 'input_title', 'asin', 'note'),
            column_config={'selected': st.column_config.CheckboxColumn('商品情報を確認する')})
        selected_rows = [row for row, display in zip(preview, selected)
                         if display['selected'] and row.get('asin') and row.get('source_id_known') is not False]
        asins = tuple(dict.fromkeys(row['asin'] for row in selected_rows))
        selection_signature = tuple(row['row_id'] for row in selected_rows)
        if st.session_state.get('sora_selection_signature') not in (None, selection_signature):
            _clear_run()
        st.session_state['sora_selection_signature'] = selection_signature
        try:
            planned = planned_catalog_calls(asins)
        except SpApiCatalogError as error:
            st.warning(str(error))
            planned = None
        st.write(f'選択{len(selected_rows)}行／重複を除いて{len(asins)}商品。'
                 f'予定：商品取得{planned if planned is not None else "上限超過"}回＋認証最大1回。')
        if st.button('SP-APIでASIN確認', key='sora_verify', type='primary',
                     disabled=not asins or planned is None or 'sora_calls' in st.session_state):
            _clear_run()
            client = None
            st.session_state['sora_calls'] = {'auth': 0, 'catalog': 0}
            try:
                client = SpApiCatalogClient(load_sp_api_credentials())
                verified = verify_preview_rows(selected_rows, client)
                st.session_state['sora_verified'] = verified
                if any(row.get('status') == 'ERROR' for row in verified):
                    st.error(next(row['note'] for row in verified if row.get('status') == 'ERROR'))
                else:
                    st.session_state['sora_run'] = prepare_sora_run(verified, marketplace=marketplace,
                        auth_calls=client.auth_calls, catalog_calls=client.catalog_calls,
                        input_files=tuple(f.name for f in uploads) or ('画面貼付',))
                    st.success('商品情報を確認しました。成分・説明文も同じ画面の保安ゲートへ渡しました。')
            except SpApiCatalogError as error:
                st.error(str(error))
            except Exception:
                st.error('商品資料を保安ゲートへ渡せませんでした。未確認商品は通過させません。')
            finally:
                st.session_state['sora_calls'] = {'auth': client.auth_calls if client else 0,
                                                  'catalog': client.catalog_calls if client else 0}
                client = None
    if st.session_state.get('sora_verified'):
        st.dataframe([{k: row.get(k, '') for k in ('source_id', 'input_title', 'asin', 'product_title', 'verification', 'note')}
                      for row in st.session_state['sora_verified']], hide_index=True)
    if 'sora_calls' in st.session_state:
        calls = st.session_state['sora_calls']
        st.caption(f"今回の実行：商品取得{calls['catalog']}回／認証{calls['auth']}回。自動再試行はしません。")

    st.header('2. 出品前保安ゲート')
    run = st.session_state.get('sora_run')
    if run is None:
        st.info('ASIN確認が終わると、候補・成分・説明文をここへ渡します。ファイルの再アップロードは不要です。')
        return
    st.caption('商品情報は日本のAmazonから取得。長い説明本文が取得できない商品があります。通過は出品許可や輸送適合の保証ではありません。')
    if run.unverified_row_count:
        st.warning(f'取得できなかった{run.unverified_row_count}行は判定対象から外しました。通過ASINへは含めません。')
    inventory_files = tuple(st.file_uploader('既出品CSV（任意・照合する場合は対象国の全ショップ分）',
        type=['csv'], accept_multiple_files=True, key='sora_inventory') or ())
    inventories = []
    if not inventory_files:
        st.info('重複照合は未実施')
    else:
        expected_shops = st.number_input('対象国の全ショップ数', min_value=1, value=1, step=1, key='sora_shop_count')
        if len(inventory_files) != expected_shops:
            st.warning('全ショップ分の既出品CSVを選択してください。')
            st.session_state.pop('sora_result', None)
            return
        try:
            inventories = [parse_listing_inventory_csv(f.getvalue(), filename=f.name,
                marketplace=marketplace, shop_label=f'shop-{n}') for n, f in enumerate(inventory_files, 1)]
        except Exception:
            st.error('既出品CSVを読み取れません。対象国・ファイル名・必須列を確認してください。')
            st.session_state.pop('sora_result', None)
            return
    inventory_fingerprint = tuple((f.name, hashlib.sha256(f.getvalue()).hexdigest()) for f in inventory_files)
    if st.session_state.get('sora_inventory_fingerprint') != inventory_fingerprint:
        st.session_state.pop('sora_result', None)
    st.session_state['sora_inventory_fingerprint'] = inventory_fingerprint
    if marketplace == 'SG':
        current = prepare_body_confirmations(run.candidates, run.product_text_safety,
                                            st.session_state.get('sora_body'))
        updated = render_sg_body_review(run.candidates, run.product_text_safety, current, persist=False)
        if updated != current:
            st.session_state.pop('sora_result', None)
        st.session_state['sora_body'] = updated
    if st.button('保安ゲートで判定する', key='sora_evaluate', type='primary'):
        try:
            st.session_state['sora_result'] = evaluate_sora_run(run, inventories,
                body_confirmations=st.session_state.get('sora_body') if marketplace == 'SG' else None)
        except Exception:
            st.session_state.pop('sora_result', None)
            st.error('保安ゲートの判定を完了できません。入力資料と判定データを確認してください。')
    result = st.session_state.get('sora_result')
    if result:
        st.write(f'通過{result.eligible_count}件／要確認{result.review_count}件／停止{result.exclude_count}件')
        preview_rows = tuple(row for status in ('ELIGIBLE', 'REVIEW', 'EXCLUDE')
                             for row in build_prelisting_gate_preview_rows(result, final_eligibility=status))
        st.dataframe(localize_prelisting_gate_preview_rows(preview_rows), hide_index=True)
        for name, data in sora_exports(run, result).items():
            st.download_button(name, data=data, file_name=f'{marketplace}_{name}',
                               key='sora_download_'+name)
