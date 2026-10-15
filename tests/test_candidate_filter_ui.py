"""F05/F06/F08 through both markets' normal beta UI; all data synthetic."""
from copy import deepcopy
from dataclasses import replace
import csv
from datetime import datetime, timezone
import hashlib
from io import StringIO

import pytest
import streamlit as st

from modules.candidate_filters import extract_keepa_observation
from modules.prelisting_candidate_csv import parse_prelisting_candidate_csv
from modules.prelisting_gate_handoff import PACKET_KEY, validate_packet
from test_expansion_gate_handoff import offline, beta, result


@pytest.fixture(autouse=True)
def no_network(offline):
    pass


@pytest.fixture
def downloads(monkeypatch):
    saved = {}
    original = st.download_button
    def capture(label, data=None, **kwargs):
        saved[kwargs.get('key', label)] = data
        return original(label, data, **kwargs)
    monkeypatch.setattr(st, 'download_button', capture)
    return saved


def generated():
    value = result()
    value.rows.clear()
    for index, price, rating in [(1, 1000, 45), (2, 5000, 40), (3, 5001, 45), (4, -1, -1)]:
        row = deepcopy(result(asin=f'B00000000{index}').rows[0])
        current = [-1] * 17
        current[0], current[16] = price, rating
        row['candidate_observation'] = extract_keepa_observation(
            {'asin': row['candidate_asin'], 'domainId': 5, 'stats': {'current': current}},
            captured_at=datetime.now(timezone.utc))
        value.rows.append(row)
    return replace(value, final_display_count=4)


def apply(app, key='f12_expansion_', low='1000', high='5000', rating='4.0以上'):
    app.text_input(key=key+'min').set_value(low)
    app.text_input(key=key+'max').set_value(high)
    app.selectbox(key=key+'rating').select(rating)
    app.button(key=key+'apply').click().run()
    assert not app.exception, [e.value for e in app.exception]


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_same_controls_match_subset_sidecars_sha_and_clear(market, downloads):
    app = beta(market, generated())
    assert app.text_input(key='f12_expansion_min').value == ''
    assert app.selectbox(key='f12_resolver_rating').value == '指定なし'
    apply(app)
    assert [(m.label, m.value) for m in app.metric[:3]] == [
        ('一致件数', '2'), ('条件外件数', '1'), ('未確認件数', '1')]
    app.button(key='expansion_gate_use').click().run()
    packet = app.session_state[PACKET_KEY]
    parsed = validate_packet(packet, marketplace=market, generation=packet.generation)
    assert len(parsed.rows) == 2
    assert len(packet.candidate.content.decode('utf-8-sig').splitlines()[0].split(',')) == 15
    raw = downloads['f12_expansion_confirmation']
    assert raw.startswith(b'\xef\xbb\xbf')
    confirmation = list(csv.DictReader(StringIO(raw.decode('utf-8-sig'))))
    assert len(confirmation) == 4
    assert {r['candidate_sha256'] for r in confirmation} == {hashlib.sha256(packet.candidate.content).hexdigest()}
    assert {r['marketplace'] for r in confirmation} == {market}
    apply(app, rating='4.5以上')
    with pytest.raises(KeyError):
        _ = app.session_state[PACKET_KEY]
    assert len(parse_prelisting_candidate_csv(downloads['prelisting-expansion-download'], filename='candidate.csv').rows) == 1
    app.button(key='f12_expansion_clear').click().run()
    assert app.text_input(key='f12_expansion_min').value == ''
    assert len(parse_prelisting_candidate_csv(downloads['prelisting-expansion-download'], filename='candidate.csv').rows) == 4


@pytest.mark.parametrize('market', ['PH', 'SG'])
@pytest.mark.parametrize('invalid', [False, True])
def test_zero_or_invalid_has_no_old_csv_or_gate(market, invalid, downloads):
    app = beta(market, generated())
    app.button(key='expansion_gate_use').click().run()
    downloads.clear()
    apply(app, low='6000', high='1000' if invalid else '', rating='指定なし')
    assert 'prelisting-expansion-download' not in downloads
    assert not any(b.key == 'expansion_gate_use' for b in app.button)
    with pytest.raises(KeyError):
        _ = app.session_state[PACKET_KEY]
    if invalid:
        assert any('下限' in e.value for e in app.error)


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_old_cache_is_unknown_then_rating_only_does_not_need_price(market, downloads):
    value = generated()
    value.rows[0].pop('candidate_observation')
    value.rows[1]['candidate_observation']['price_status'] = 'NOT_CAPTURED'
    value.rows[1]['candidate_observation']['price_jpy'] = None
    app = beta(market, value)
    apply(app, low='', high='', rating='4.0以上')
    assert [(m.label, m.value) for m in app.metric[:3]] == [
        ('一致件数', '2'), ('条件外件数', '0'), ('未確認件数', '2')]
    assert any('対象 1 ASIN / 最大 2 tokens' in c.value for c in app.caption)
    # The fixture denies creating any provider: apply/clear/rerender are local.
    app.run()
    app.button(key='f12_expansion_clear').click().run()
    assert not app.exception


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_resolver_keeps_duplicate_source_rows_and_candidate_contract(market, downloads):
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    rows = []
    for source_id, index in [('R0001', 0), ('R0002', 0), ('R0003', 2)]:
        source = generated().rows[index]
        rows.append(dict(source_id=source_id, input_title='synthetic title',
            amazon_url='https://www.amazon.co.jp/dp/'+source['candidate_asin'],
            asin=source['candidate_asin'], status='FOUND', verification='KEEPA_VERIFIED', note='',
            keepa_title=source['product_title'], keepa_brand=source['brand'], keepa_category=source['category'],
            keepa_fetched_at=source['fetched_at'], product_title=source['product_title'],
            ingredient_safety_fact=source.get('ingredient_safety_fact'),
            product_text_safety_fact=source.get('product_text_safety_fact'),
            candidate_observation=source['candidate_observation']))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app_beta.py'), default_timeout=30)
    app.session_state['beta_marketplace'] = market
    app.session_state['asin_resolver_preview_rows'] = [dict(r, selected=True, row_id=str(i)) for i,r in enumerate(rows)]
    app.session_state['asin_resolver_rows'] = rows
    app.run()
    assert not app.exception
    apply(app, key='f12_resolver_')
    matched = list(csv.DictReader(StringIO(downloads['起点ASIN候補CSVダウンロード'].decode('utf-8-sig'))))
    assert [r['source_id'] for r in matched] == ['R0001', 'R0002']
    confirmation = list(csv.DictReader(StringIO(downloads['f12_resolver_confirmation'].decode('utf-8-sig'))))
    assert [r['source_id'] for r in confirmation] == ['R0001', 'R0002', 'R0003']
    candidate = parse_prelisting_candidate_csv(downloads['prelisting-resolver-download'], filename='candidate.csv')
    assert candidate.data_row_count == 1  # Existing Gate consolidation; provenance remains joined.
    assert len(downloads['prelisting-resolver-download'].decode('utf-8-sig').splitlines()[0].split(',')) == 15


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_failed_explicit_refill_blocks_old_exports_and_handoff(market, downloads, monkeypatch):
    value = generated()
    value.rows[3].pop('candidate_observation')
    app = beta(market, value)
    apply(app)
    app.button(key='expansion_gate_use').click().run()
    old = app.session_state[PACKET_KEY]
    attempts = []
    def fail(*args, **kwargs):
        attempts.append(1)
        raise RuntimeError('synthetic transport failure')
    monkeypatch.setattr('app.create_amazon_data_client', fail)
    downloads.clear()
    app.button(key='f12_expansion_refresh').click().run()
    assert attempts == [1]
    assert not app.exception
    assert 'prelisting-expansion-download' not in downloads
    assert not any(b.key == 'expansion_gate_use' for b in app.button)
    with pytest.raises(KeyError):
        _ = app.session_state[PACKET_KEY]
    assert any('取得できません' in e.value for e in app.error)
    app.run()
    assert attempts == [1]
    assert 'prelisting-expansion-download' not in downloads


@pytest.mark.parametrize('market', ['PH', 'SG'])
def test_p4_offline_has_common_controls_and_refill_stays_closed(market, tmp_path, monkeypatch):
    from test_practical_beta_p4_ui import full_app
    workspaces = {m: {'db_path': str(tmp_path/(m+'.sqlite3')), 'shop_id': 'synthetic-shop'} for m in ('PH','SG')}
    app = full_app(workspaces, market)
    value = generated()
    value.rows[0].pop('candidate_observation')
    app.session_state['result'] = value
    app.run()
    apply(app)
    assert app.button(key='f12_expansion_refresh').disabled
    assert len([s for s in app.subheader if s.value == '候補の絞り込み']) == 2
    assert any('PH_SG_P1_OFFLINE' in w.value for w in app.warning)
    original_button = st.button
    def crafted_trigger(*args, **kwargs):
        result = original_button(*args, **kwargs)
        return True if kwargs.get('key') == 'f12_expansion_refresh' else result
    monkeypatch.setattr(st, 'button', crafted_trigger)
    app.run()  # Even a disabled-widget trigger must not construct a live client.
    assert not app.exception


def test_canopy_active_filters_stop_before_provider_creation(monkeypatch):
    monkeypatch.setenv('AMAZON_DATA_PROVIDER', 'canopy_test')
    monkeypatch.setenv('CANOPY_API_KEY', 'synthetic-not-a-credential')
    app = beta('PH')
    apply(app)
    assert any('未対応' in e.value for e in app.error)
    assert next(b for b in app.button if b.label == '検索開始').disabled
    app.button(key='f12_expansion_clear').click().run()
    assert not next(b for b in app.button if b.label == '検索開始').disabled
