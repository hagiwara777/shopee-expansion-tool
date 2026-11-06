from pathlib import Path
import logging
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from modules.sp_api_catalog import JP_MARKETPLACE, normalize_catalog_item


ROOT = Path(__file__).resolve().parents[1]


def button(app, key):
    return next(b for b in app.button if b.key == key)


@pytest.fixture
def client_calls(monkeypatch):
    # Same local test-only workaround as the existing AppTest suite. Do not
    # modify the Owner PC's logging installation or any running application.
    def standard_warning(logger, message, *args, **kwargs):
        if logger.isEnabledFor(logging.WARNING):
            logger._log(logging.WARNING, message, args, **kwargs)
    monkeypatch.setattr(logging.Logger, 'warning', standard_warning)
    calls = []

    class Client:
        provider_name = 'sp_api_catalog_2022_04_01'
        product_field_prefix = 'spapi'
        verification_label = 'SP_API_VERIFIED'
        not_found_label = 'SP_API_NOT_FOUND'
        auth_calls = 0
        catalog_calls = 0

        def __init__(self, credentials):
            pass

        def verify_products_by_asin(self, asins, *, on_batch=None):
            calls.append(tuple(asins))
            self.auth_calls = 1
            products = {asin: normalize_catalog_item({'asin': asin, 'attributes': {}, 'summaries': [{
                'marketplaceId': JP_MARKETPLACE, 'itemName': '普通のタオル',
                'brand': '試験ブランド', 'browseClassification': {'displayName': 'タオル'}}]},
                fetched_at='2026-11-01T09:00:00+00:00') for asin in asins}
            if on_batch:
                for start in range(0, len(asins), 20):
                    batch = tuple(asins[start:start + 20])
                    self.catalog_calls += 1
                    on_batch(batch, {a: products[a] for a in batch})
            return products

    monkeypatch.setattr('modules.sora_ui.SpApiCatalogClient', Client)
    monkeypatch.setattr('modules.sora_ui.load_sp_api_credentials', lambda: object())
    monkeypatch.setattr('modules.amazon_data_provider.create_amazon_data_client',
                        lambda *args, **kwargs: pytest.fail('Legacy provider reached'))
    return calls


@pytest.mark.parametrize('marketplace', ['PH', 'SG'])
def test_manual_chatgpt_to_sp_api_to_gate_same_normal_screen(client_calls, marketplace):
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=20).run()
    assert not app.exception
    assert client_calls == []
    assert any(caption.value.startswith('版: ') for caption in app.caption)
    app.radio(key='sora_entry').set_value('Shopee調査CSV・ChatGPT（Resolver）').run()
    app.selectbox(key='sora_marketplace').set_value(marketplace).run()
    app.text_area(key='sora_source_input').set_value('JPH-example\tA towel').run()
    button(app, 'sora_generate_prompt').click().run()
    assert 'Amazon.co.jpの商品URLを検索' in app.code[0].value
    assert 'R0001\tA towel' in app.code[0].value
    assert client_calls == []
    app.text_area(key='sora_response').set_value('R0001\tA towel\thttps://www.amazon.co.jp/dp/B000000001').run()
    button(app, 'sora_parse_response').click().run()
    assert client_calls == []
    button(app, 'sora_verify').click().run()
    assert not app.exception
    assert client_calls == [('B000000001',)]
    assert any('重複照合は未実施' in info.value for info in app.info)
    button(app, 'sora_evaluate').click().run()
    assert not app.exception
    assert app.session_state['sora_result'].eligible_count == 1
    assert len(app.get('download_button')) == 4
    app.run()
    assert client_calls == [('B000000001',)]
    other = 'PH' if marketplace == 'SG' else 'SG'
    app.selectbox(key='sora_marketplace').set_value(other).run()
    assert 'sora_run' not in app.session_state
    assert len(app.get('download_button')) == 0


def test_next_run_discards_previous_facts_and_decisions(client_calls):
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=20).run()
    app.text_area(key='sora_asins').set_value('B000000001').run()
    button(app, 'sora_verify').click().run()
    button(app, 'sora_evaluate').click().run()
    assert app.session_state['sora_result'].eligible_count == 1
    button(app, 'sora_new_run').click().run()
    assert 'sora_run' not in app.session_state
    assert 'sora_result' not in app.session_state
    assert len(app.get('download_button')) == 0
    assert len(client_calls) == 1


def test_display_input_and_country_change_never_load_secrets_or_call_api(client_calls, monkeypatch):
    monkeypatch.setattr('modules.sora_ui.load_sp_api_credentials', lambda: pytest.fail('Secret read on render'))
    monkeypatch.setattr('requests.Session.request', lambda *a, **kw: pytest.fail('Network request on render'))
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=20).run()
    app.text_area(key='sora_asins').set_value('B000000001').run()
    app.radio(key='sora_entry').set_value('Shopee調査CSV・ChatGPT（Resolver）').run()
    app.text_area(key='sora_source_input').set_value('A towel').run()
    button(app, 'sora_generate_prompt').click().run()
    app.selectbox(key='sora_marketplace').set_value('PH').run()
    assert not app.exception
    assert client_calls == []


def test_primary_paste_500_plans_25_calls_then_clicks_once(client_calls):
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=30).run()
    assert app.radio(key='sora_entry').value == 'ASINを貼る'
    asins = [f'B{i:09d}' for i in range(500)]
    app.text_area(key='sora_asins').set_value('\n'.join(asins)).run()
    assert client_calls == []
    assert any('商品取得25回＋認証最大1回' in element.value for element in app.markdown)
    button(app, 'sora_verify').click().run()
    assert not app.exception
    assert client_calls == [tuple(asins)]
    assert len(app.session_state['sora_run'].candidates.rows) == 500
    assert app.session_state['sora_run'].catalog_calls == 25
    assert button(app, 'sora_verify').disabled
    app.run()
    assert len(client_calls) == 1
    app.text_area(key='sora_asins').set_value('B999999999').run()
    assert 'sora_run' not in app.session_state
    assert 'sora_acquisition' not in app.session_state
    assert len(app.get('download_button')) == 0


def test_fromax_upload_goes_directly_to_verification_and_wrong_inventory_explains_destination(client_calls, monkeypatch):
    import streamlit as st
    original = st.file_uploader
    keepa = SimpleNamespace(name='fromax_keepa.csv', file_id='file-1',
                            getvalue=lambda: b'ASIN,Title,Weight\nB000000001,,\nB000000001,,\n')
    inventory = []
    def uploader(*args, **kwargs):
        key = kwargs.get('key')
        if key == 'sora_keepa_file':
            return keepa
        if key == 'sora_inventory':
            return inventory
        return original(*args, **kwargs)
    monkeypatch.setattr(st, 'file_uploader', uploader)
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=20).run()
    app.radio(key='sora_entry').set_value('FROMAXのKeepa CSV').run()
    assert client_calls == []
    button(app, 'sora_verify').click().run()
    button(app, 'sora_evaluate').click().run()
    assert app.session_state['sora_result'].eligible_count == 1
    inventory.append(keepa)
    app.run()
    assert not app.exception
    assert any('Shopeeの出品CSV' in e.value and '上の入口' in e.value for e in app.error)
    assert 'sora_result' not in app.session_state
    assert len(app.get('download_button')) == 0
    assert client_calls == [('B000000001',)]
    # A replacement input must clear the old facts even when parsing fails.
    keepa.getvalue = lambda: b''
    app.run()
    assert any('CSVが空' in e.value for e in app.error)
    assert 'sora_run' not in app.session_state and 'sora_acquisition' not in app.session_state
    assert client_calls == [('B000000001',)]


def test_partial_acquisition_only_resumes_on_separate_click_and_never_gates_pending(client_calls, monkeypatch):
    import requests
    from modules.sp_api_catalog import SpApiCatalogClient, SpApiCredentials
    batches = []
    def factory(credentials):
        class Transport:
            def request(self, method, url, **kwargs):
                if method == 'POST':
                    payload = {'access_token': 'offline-test-token'}
                else:
                    batch = tuple(kwargs['params']['identifiers'].split(','))
                    batches.append(batch)
                    if len(batches) == 2:
                        raise requests.Timeout('must not display this')
                    payload = {'items': [{'asin': a, 'attributes': {}, 'summaries': [{
                        'marketplaceId': JP_MARKETPLACE, 'itemName': '普通のタオル',
                        'brand': '試験ブランド', 'browseClassification': {'displayName': 'タオル'}}]} for a in batch]}
                return SimpleNamespace(status_code=200, json=lambda: payload)
        clock = [0.0]
        return SpApiCatalogClient(SpApiCredentials('test', 'test-only', 'test-only'), transport=Transport(),
            monotonic=lambda: clock[0], sleep=lambda seconds: clock.__setitem__(0, clock[0]+seconds))
    monkeypatch.setattr('modules.sora_ui.SpApiCatalogClient', factory)
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=30).run()
    asins = tuple(f'B{i:09d}' for i in range(41))
    app.text_area(key='sora_asins').set_value('\n'.join(asins)).run()
    button(app, 'sora_verify').click().run()
    assert not app.exception
    assert len(batches) == 2
    assert 'sora_run' not in app.session_state
    assert not any(b.key == 'sora_evaluate' for b in app.button)
    assert len(app.get('download_button')) == 0
    assert button(app, 'sora_resume').label == '残り21件だけを取得する'
    app.run()
    assert len(batches) == 2
    button(app, 'sora_resume').click().run()
    assert not app.exception
    assert tuple(a for batch in batches[2:] for a in batch) == asins[20:]
    assert app.session_state['sora_calls'] == {'auth': 2, 'catalog': 4}
    assert len(app.session_state['sora_run'].candidates.rows) == 41
    button(app, 'sora_evaluate').click().run()
    assert app.session_state['sora_result'].eligible_count == 41
    app.radio(key='sora_entry').set_value('FROMAXのKeepa CSV').run()
    assert 'sora_run' not in app.session_state and 'sora_acquisition' not in app.session_state
    assert len(app.get('download_button')) == 0
