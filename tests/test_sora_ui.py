from pathlib import Path
import logging

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

        def verify_products_by_asin(self, asins):
            calls.append(tuple(asins))
            self.auth_calls = self.catalog_calls = 1
            return {asin: normalize_catalog_item({'asin': asin, 'attributes': {}, 'summaries': [{
                'marketplaceId': JP_MARKETPLACE, 'itemName': '普通のタオル',
                'brand': '試験ブランド', 'browseClassification': {'displayName': 'タオル'}}]},
                fetched_at='2026-11-01T09:00:00+00:00') for asin in asins}

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
    app.text_area(key='sora_response').set_value('B000000001').run()
    button(app, 'sora_parse_response').click().run()
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
    app.text_area(key='sora_source_input').set_value('A towel').run()
    button(app, 'sora_generate_prompt').click().run()
    app.selectbox(key='sora_marketplace').set_value('PH').run()
    assert not app.exception
    assert client_calls == []
