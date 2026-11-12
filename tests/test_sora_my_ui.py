"""DEC-0184: the real Sora screen offers MY, but MY never shows a pass. Offline, no live API."""
import logging
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from modules.sp_api_catalog import JP_MARKETPLACE, normalize_catalog_item

ROOT = Path(__file__).resolve().parents[1]


def button(app, key):
    return next(b for b in app.button if b.key == key)


@pytest.fixture
def client_calls(monkeypatch):
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
                self.catalog_calls += 1
                on_batch(tuple(asins), products)
            return products

    monkeypatch.setattr('modules.sora_ui.SpApiCatalogClient', Client)
    monkeypatch.setattr('modules.sora_ui.load_sp_api_credentials', lambda: object())
    monkeypatch.setattr('requests.Session.request', lambda *a, **kw: pytest.fail('Live API reached'))
    return calls


def test_screen_offers_my_last_and_keeps_sg_as_default(client_calls):
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=20).run()
    assert not app.exception
    selector = app.selectbox(key='sora_marketplace')
    assert list(selector.options) == ['SG', 'PH', 'MY']
    assert selector.value == 'SG'


def test_my_run_shows_no_pass_and_a_notice(client_calls):
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=20).run()
    app.selectbox(key='sora_marketplace').set_value('MY').run()
    app.text_area(key='sora_asins').set_value('B000000001').run()
    button(app, 'sora_verify').click().run()
    assert not app.exception
    warnings = ' '.join(w.value for w in app.warning)
    assert '国別の禁止設定が未完成' in warnings and '通過」は出ません' in warnings
    assert any('重複照合は未対応' in info.value for info in app.info)
    button(app, 'sora_evaluate').click().run()
    assert not app.exception
    summary = [m.value for m in app.markdown if '通過' in m.value and '件' in m.value]
    assert any(v.startswith('通過0件／要確認1件／停止0件') for v in summary), summary
    preview = app.dataframe[-1].value
    assert set(preview['最終判定']) == {'要確認'}
    assert client_calls == [('B000000001',)]


def test_sg_still_shows_a_pass_for_the_same_clean_product(client_calls):
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=20).run()
    app.text_area(key='sora_asins').set_value('B000000001').run()
    button(app, 'sora_verify').click().run()
    assert not any('国別の禁止設定' in w.value for w in app.warning)
    button(app, 'sora_evaluate').click().run()
    assert not app.exception
    assert any(m.value.startswith('通過1件／要確認0件／停止0件') for m in app.markdown), [m.value for m in app.markdown]
