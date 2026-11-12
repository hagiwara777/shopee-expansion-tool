"""Two direct Sora entries, the existing safety Gate, and preserved Resolver code."""

import hashlib

import streamlit as st

from modules.asin_resolver import build_ai_prompt, build_source_map, preview_candidates
from modules.listing_inventory_parser import parse_listing_inventory_csv
from modules.prelisting_gate_ui import build_prelisting_gate_preview_rows, localize_prelisting_gate_preview_rows
from modules.prelisting_sg_body_safety import prepare_body_confirmations
from modules.prelisting_sg_body_safety_ui import render_sg_body_review
from modules.research_csv_adapter import ResearchCsvInput, import_research_csvs
from modules.sora_acquisition import SoraAcquisition
from modules.sora_input import SoraInputError, parse_asin_text, parse_fromax_keepa_csv
from modules.sora_markets import SORA_MARKETS, SORA_MARKET_ORDER, market_ng_incomplete
from modules.sora_run import evaluate_sora_run, prepare_sora_run, sora_exports
from modules.sora_version import RUNNING_VERSION
from modules.sp_api_catalog import SpApiCatalogClient, SpApiCatalogError, load_sp_api_credentials, planned_catalog_calls


def _clear_gate():
    for key in list(st.session_state):
        if key in {'sora_run', 'sora_result', 'sora_body'} or key.startswith('sg_body_'):
            del st.session_state[key]


def _clear_run():
    _clear_gate()
    for key in ('sora_acquisition', 'sora_verified', 'sora_calls', 'sora_selection_signature'):
        st.session_state.pop(key, None)


def _clear_resolver():
    _clear_run()
    for key in ('sora_preview', 'sora_selection', 'sora_prompt', 'sora_response', 'sora_response_fingerprint'):
        st.session_state.pop(key, None)


def render_sora_app():
    st.set_page_config(page_title='Sora', layout='wide')
    title_column, version_column = st.columns([5, 1], vertical_alignment='center')
    title_column.title('Sora')
    version_column.caption(f'版: {RUNNING_VERSION}', text_alignment='right')
    st.caption('FROMAXのKeepaでASINを集める → Soraで商品情報・保安確認 → 通過ASINをFROMAXへ')
    marketplace = st.selectbox('対象国', SORA_MARKET_ORDER, key='sora_marketplace')
    if st.session_state.get('sora_previous_marketplace') not in {None, marketplace}:
        _clear_resolver()
        st.session_state.pop('sora_source_fingerprint', None)
        st.session_state.pop('sora_source_input', None)
    st.session_state['sora_previous_marketplace'] = marketplace
    if st.button('新しい実行を始める', key='sora_new_run'):
        _clear_resolver()
        st.success('前回の商品資料・判定・確認結果を消しました。')

    st.header('1. ASINを貼る／FROMAXのKeepa CSVを入れる')
    entry_options = ('ASINを貼る', 'FROMAXのKeepa CSV')
    if st.session_state.get('sora_entry') not in (None, *entry_options):
        st.session_state.pop('sora_entry', None)
        _clear_resolver()
    entry = st.radio('入力方法', entry_options,
                     horizontal=True, key='sora_entry')
    if st.session_state.get('sora_previous_entry') not in (None, entry):
        _clear_resolver()
    st.session_state['sora_previous_entry'] = entry
    st.caption('最大500件。商品取得は20件ずつ。取得済みの資料はこの画面内だけで保持します。'
               '入力・国・入口の変更、新しい実行、画面の再読込・終了で消えます。')
    selected_rows, input_files = _render_direct_input(entry)
    _render_acquisition(selected_rows, marketplace=marketplace, input_files=input_files)
    _render_gate(marketplace)


def _render_direct_input(entry):
    if entry == 'ASINを貼る':
        text = st.text_area('確認するASIN（1行1件・カンマ区切りも可）', key='sora_asins', height=160)
        fingerprint = (entry, text)
        content = text
        has_input = bool(text.strip())
        input_files = ('ASIN画面貼付',)
    else:
        upload = st.file_uploader('FROMAXのKeepa CSV（ASIN列から取り込み）', type=['csv'], key='sora_keepa_file')
        content = upload.getvalue() if upload is not None else b''
        has_input = upload is not None
        fingerprint = (entry, upload.name, getattr(upload, 'file_id', ''), hashlib.sha256(content).hexdigest()) if upload else (entry, None)
        input_files = (upload.name,) if upload else ()
    if st.session_state.get('sora_direct_fingerprint') != fingerprint:
        _clear_run()
    st.session_state['sora_direct_fingerprint'] = fingerprint
    if not has_input:
        return [], input_files
    try:
        parsed = parse_asin_text(content) if entry == 'ASINを貼る' else parse_fromax_keepa_csv(content)
    except (SoraInputError, SpApiCatalogError) as error:
        st.error(str(error))
        return [], input_files
    st.write(f'入力{parsed.data_row_count}件／重複除外{parsed.duplicate_count}件／対象{len(parsed.asins)}件。')
    if parsed.empty_asin_count:
        st.warning(f'ASINが空の{parsed.empty_asin_count}行は取り込んでいません。')
    if entry != 'ASINを貼る':
        st.caption('商品名や重さが空欄でも、ASINがあれば取り込みます。判定にはAmazonから取得する商品情報を使います。')
    with st.expander('取り込んだASINを確認'):
        st.code('\n'.join(parsed.asins), language='text')
    return preview_candidates('\n'.join(parsed.asins)), input_files


def _render_resolver(marketplace):
    st.subheader('Shopee調査CSVからASINを調べる')
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
    selected_rows = []
    if preview:
        displayed = [{key: row.get(key, '') for key in
                     ('selected', 'source_id', 'input_title', 'asin', 'note')} for row in preview]
        selected = st.data_editor(displayed, key='sora_selection', hide_index=True,
            disabled=('source_id', 'input_title', 'asin', 'note'),
            column_config={'selected': st.column_config.CheckboxColumn('商品情報を確認する')})
        selected_rows = [row for row, display in zip(preview, selected)
                         if display['selected'] and row.get('asin') and row.get('source_id_known') is not False]
    return selected_rows, tuple(f.name for f in uploads) or ('Resolver画面貼付',)


def _render_acquisition(selected_rows, *, marketplace, input_files):
    signature = tuple((row['row_id'], row['asin']) for row in selected_rows)
    if st.session_state.get('sora_selection_signature') not in (None, signature):
        _clear_run()
    st.session_state['sora_selection_signature'] = signature
    asins = tuple(dict.fromkeys(row['asin'] for row in selected_rows))
    if not asins:
        return
    try:
        planned = planned_catalog_calls(asins)
    except SpApiCatalogError as error:
        st.warning(str(error))
        return
    acquisition = st.session_state.get('sora_acquisition')
    st.write(f'対象{len(asins)}商品。予定：商品取得{planned}回＋認証最大1回。')
    start = st.button('SP-APIでASIN確認', key='sora_verify', type='primary', disabled=acquisition is not None)
    resume = False
    if acquisition is not None and not acquisition.complete:
        remaining = len(acquisition.pending_asins)
        st.warning(f'取得処理済み{len(acquisition.completed_asins)}件／残り{remaining}件。'
                   '全件の取得処理が終わるまで保安判定・出力は待機します。')
        st.write(f'残りだけの予定：商品取得{planned_catalog_calls(acquisition.pending_asins)}回＋認証最大1回。')
        resume = st.button(f'残り{remaining}件だけを取得する', key='sora_resume', type='primary')
    if start or resume:
        _clear_gate()
        if start:
            acquisition = SoraAcquisition(tuple(selected_rows), marketplace, input_files)
            st.session_state['sora_acquisition'] = acquisition
        client = None
        try:
            client = SpApiCatalogClient(load_sp_api_credentials())
            acquisition.advance(client)
        except SpApiCatalogError as error:
            acquisition.error = str(error)
        except Exception:
            acquisition.error = '商品情報の取得を停止しました。未確認商品は通過させません。'
        finally:
            client = None
            st.session_state['sora_calls'] = {'auth': acquisition.auth_calls, 'catalog': acquisition.catalog_calls}
            st.session_state['sora_verified'] = acquisition.verified_rows
        if acquisition.complete:
            try:
                st.session_state['sora_run'] = prepare_sora_run(acquisition.verified_rows, marketplace=marketplace,
                    auth_calls=acquisition.auth_calls, catalog_calls=acquisition.catalog_calls, input_files=input_files)
            except Exception:
                acquisition.error = '商品資料を保安ゲートへ渡せませんでした。未確認商品は通過させません。'
        # Refresh the pending count/button after this explicit attempt; this
        # rerun only renders state and never starts or resumes a request.
        st.rerun()
    if acquisition is not None and acquisition.error:
        st.error(acquisition.error)
    if acquisition is not None and acquisition.complete and 'sora_run' in st.session_state:
        st.success('商品情報を確認しました。成分・説明文も同じ画面の保安ゲートへ渡しました。')
    if st.session_state.get('sora_verified'):
        st.dataframe([{k: row.get(k, '') for k in ('source_id', 'input_title', 'asin', 'product_title', 'verification', 'note')}
                      for row in st.session_state['sora_verified']], hide_index=True)
    if 'sora_calls' in st.session_state:
        calls = st.session_state['sora_calls']
        st.caption(f"今回の実行：商品取得{calls['catalog']}回／認証{calls['auth']}回。自動再試行はしません。")

def _render_gate(marketplace):
    st.header('2. 出品前保安ゲート')
    run = st.session_state.get('sora_run')
    if run is None:
        st.info('ASIN確認が終わると、候補・成分・説明文をここへ渡します。ファイルの再アップロードは不要です。')
        return
    st.caption('商品情報は日本のAmazonから取得。長い説明本文が取得できない商品があります。通過は出品許可や輸送適合の保証ではありません。')
    if market_ng_incomplete(marketplace):
        st.warning(f'{marketplace}は国別の禁止設定が未完成のため、「通過」は出ません。通過になる商品も要確認として表示し、'
                   '通過ASIN.txtは空になります。共通ルールで止まる商品は停止のままです。')
    if run.unverified_row_count:
        st.warning(f'取得できなかった{run.unverified_row_count}行は判定対象から外しました。通過ASINへは含めません。')
    inventory_supported = SORA_MARKETS[marketplace].inventory_check
    inventory_files = tuple(st.file_uploader('既出品CSV（任意・照合する場合は対象国の全ショップ分）',
        type=['csv'], accept_multiple_files=True, key='sora_inventory') or ()) if inventory_supported else ()
    inventories = []
    if not inventory_supported:
        st.info(f'{marketplace}の既出品CSVによる重複照合は未対応です（重複照合は未実施）。')
    elif not inventory_files:
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
            st.error('これはShopeeの出品CSVとして読み取れません。FROMAXのKeepa CSVは上の入口に入れてください。'
                     'Shopeeの出品エクスポートにはProduct ID・Parent SKU・Model ID・SKU・Stock列が必要です。'
                     '対象国・ファイル名も確認してください。')
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
        if any(count > 100 for count in (result.eligible_count, result.review_count, result.exclude_count)):
            st.info('画面は先頭100件のみ。全件はCSV（要確認.csv・停止.csv・通過ASIN.txt）で確認')
        preview_rows = tuple(row for status in ('ELIGIBLE', 'REVIEW', 'EXCLUDE')
                             for row in build_prelisting_gate_preview_rows(result, final_eligibility=status))
        st.dataframe(localize_prelisting_gate_preview_rows(preview_rows), hide_index=True)
        for name, data in sora_exports(run, result).items():
            st.download_button(name, data=data, file_name=f'{marketplace}_{name}',
                               key='sora_download_'+name)
