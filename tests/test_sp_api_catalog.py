"""Offline SP-API transport, provenance and safety-data integration checks."""

import json
from types import SimpleNamespace

import pytest
import requests

from modules.asin_resolver import preview_candidates, verify_preview_rows
from modules.ingredient_safety import facts_for_candidate_rows as ingredient_facts
from modules.prelisting_candidate_csv import (
    normalize_resolver_gate_handoff, parse_prelisting_candidate_csv,
    resolver_rows_to_prelisting_candidates, rows_to_prelisting_candidate_csv,
)
from modules.product_text_safety import facts_for_candidate_rows as text_facts
from modules.sp_api_catalog import (
    JP_MARKETPLACE, SpApiCatalogClient, SpApiCatalogError, SpApiCredentials,
    load_sp_api_credentials, normalize_catalog_item, planned_catalog_calls,
)


CREDS = SpApiCredentials('test-client', 'not-a-real-secret', 'not-a-real-refresh')


def item(asin='B000000001', **attributes):
    return {'asin': asin, 'attributes': attributes, 'summaries': [{
        'marketplaceId': JP_MARKETPLACE, 'itemName': '普通のタオル', 'brand': '試験ブランド',
        'browseClassification': {'displayName': 'タオル'},
    }]}


def attr(value, marketplace=JP_MARKETPLACE):
    return [{'value': value, 'marketplace_id': marketplace}]


class Transport:
    def __init__(self, products=None, failure=None):
        self.calls = []
        self.products = products
        self.failure = failure

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.failure:
            raise self.failure
        if method == 'POST':
            payload = {'access_token': 'test-access-only'}
        else:
            payload = {'items': self.products if self.products is not None else
                       [item(asin) for asin in kwargs['params']['identifiers'].split(',')]}
        return SimpleNamespace(status_code=200, json=lambda: payload)


def test_explicit_sora_config_ignores_other_process_credentials(tmp_path, monkeypatch):
    path = tmp_path / 'sora.env'
    path.write_text('SP_API_CLIENT_ID=sora\nSP_API_CLIENT_SECRET=literal-${OTHER}\n'
                    'SP_API_REFRESH_TOKEN=refresh-for-tests\n', encoding='utf-8')
    monkeypatch.setenv('SP_API_CLIENT_ID', 'fromax-process-value')
    monkeypatch.setenv('OTHER', 'must-not-interpolate')
    result = load_sp_api_credentials(path)
    assert result.client_id == 'sora'
    assert result.client_secret == 'literal-${OTHER}'
    assert 'sora' not in repr(result)
    assert 'literal' not in repr(result)


def test_missing_config_does_not_fall_back_to_process_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv('SP_API_CLIENT_ID', 'other-client')
    with pytest.raises(SpApiCatalogError, match='保存先'):
        load_sp_api_credentials(tmp_path/'missing.env')


def test_chunk_deduplication_counts_and_two_second_spacing():
    transport = Transport()
    clock = [0.0]
    client = SpApiCatalogClient(CREDS, transport=transport,
        monotonic=lambda: clock[0], sleep=lambda seconds: clock.__setitem__(0, clock[0]+seconds))
    asins = [f'B{i:09d}' for i in range(21)]
    products = client.verify_products_by_asin(asins + asins[:1])
    assert len(products) == 21 and client.auth_calls == 1 and client.catalog_calls == 2
    assert clock[0] >= 2
    assert len(transport.calls) == 3
    for method, url, kwargs in transport.calls:
        assert kwargs['allow_redirects'] is False
        assert kwargs['timeout'] == (10, 45)
        if method == 'GET':
            assert len(kwargs['params']['identifiers'].split(',')) <= 20
            assert kwargs['params']['marketplaceIds'] == JP_MARKETPLACE
    with pytest.raises(SpApiCatalogError, match='終了'):
        client.verify_products_by_asin(asins)
    assert len(transport.calls) == 3


@pytest.mark.parametrize('asins', [['bad'], [f'B{i:09d}' for i in range(101)], 'B000000001'])
def test_invalid_plan_sends_nothing(asins):
    transport = Transport()
    client = SpApiCatalogClient(CREDS, transport=transport)
    with pytest.raises(SpApiCatalogError):
        client.verify_products_by_asin(asins)
    assert transport.calls == []


def test_network_exception_is_sanitized_and_never_retried():
    transport = Transport(failure=requests.Timeout('not-a-real-secret should not be shown'))
    client = SpApiCatalogClient(CREDS, transport=transport)
    with pytest.raises(SpApiCatalogError) as error:
        client.verify_products_by_asin(['B000000001'])
    assert 'not-a-real-secret' not in str(error.value)
    assert len(transport.calls) == 1 and client.auth_calls == 1 and client.catalog_calls == 0


def test_unrequested_item_is_rejected():
    client = SpApiCatalogClient(CREDS, transport=Transport([item('B000000002')]))
    with pytest.raises(SpApiCatalogError, match='ASIN'):
        client.verify_products_by_asin(['B000000001'])


@pytest.mark.parametrize('status', [301, 403, 429, 500])
def test_http_error_or_redirect_stops_without_retry_or_raw_message(status):
    class Rejected:
        def __init__(self):
            self.calls = 0
        def request(self, *args, **kwargs):
            self.calls += 1
            assert kwargs['allow_redirects'] is False
            return SimpleNamespace(status_code=status, json=lambda: {'secret': 'must-not-show'})
    transport = Rejected()
    client = SpApiCatalogClient(CREDS, transport=transport)
    with pytest.raises(SpApiCatalogError) as error:
        client.verify_products_by_asin(['B000000001'])
    assert str(status) in str(error.value)
    assert 'must-not-show' not in str(error.value)
    assert transport.calls == 1


def test_facts_preserve_jp_fields_and_do_not_invent_description():
    product = normalize_catalog_item(item(
        ingredients=attr('ジフェンヒドラミン'),
        bullet_point=attr('薬用の肯定表示'),
        product_description=attr('other market only', 'OTHER'),
        safety_warning=attr('LPG 高圧ガス'), batteries_included=attr(True),
    ), fetched_at='2026-11-01T09:00:00+00:00')
    assert product['product_text_safety_fact']['description'] == []
    assert product['product_text_safety_fact']['features'] == ['薬用の肯定表示']
    assert product['product_text_safety_fact']['itemHighlights'] == ['電池付属']
    assert product['ingredient_safety_fact']['ingredients'] == ['ジフェンヒドラミン']
    assert product['ingredient_safety_fact']['provider'] == 'sp_api_catalog_2022_04_01'


def test_resolver_candidate_and_both_safety_transports_accept_actual_sp_api_source():
    product = item(bullet_point=attr('医薬部外品'), ingredients=attr('有効成分'))
    client = SpApiCatalogClient(CREDS, transport=Transport([product]))
    rows = verify_preview_rows(preview_candidates('B000000001'), client)
    assert rows[0]['verification'] == 'SP_API_VERIFIED'
    converted = resolver_rows_to_prelisting_candidates(rows)
    handoff = normalize_resolver_gate_handoff(converted.output_rows, rows)
    data = rows_to_prelisting_candidate_csv(handoff.candidate_rows)
    candidates = parse_prelisting_candidate_csv(data, filename='sp_api.csv')
    assert candidates.rows[0].source == 'asin_resolver_sp_api_verified'
    assert ingredient_facts(candidates.rows, rows)[0].provider == client.provider_name
    assert text_facts(candidates.rows, rows)[0].features == ('医薬部外品',)
    assert rows[0]['ph_image_safety_fact'] is None


def test_zero_products_has_zero_calls():
    client = SpApiCatalogClient(CREDS, transport=Transport())
    assert planned_catalog_calls([]) == 0
    assert client.verify_products_by_asin([]) == {}
    assert client.auth_calls == client.catalog_calls == 0
