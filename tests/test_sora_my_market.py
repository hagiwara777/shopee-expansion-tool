"""DEC-0189: configured Sora markets pass without country CSV dictionaries.

Synthetic fixtures only; not MY regulation coverage, an MY NG dictionary, or live acceptance.
"""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from modules.asin_resolver import preview_candidates, verify_preview_rows
from modules.brand_monitoring import COUNTRY_FILES, BrandMonitoringError, load_brand_monitoring
from modules.community_ng import load_community_ng_assets
from modules.guardrails import GuardrailDictionaryError, apply_guardrails, load_guardrail_dictionaries
from modules.prelisting_gate import PrelistingGateError, evaluate_prelisting_gate
from modules.prelisting_gate_ui import build_prelisting_gate_export_rows, localize_prelisting_gate_preview_rows
from modules.sora_acquisition import SoraAcquisition
from modules.sora_markets import (
    MARKET_NG_INCOMPLETE_REASON, SORA_MARKET_ORDER, SORA_MARKETS, market_ng_incomplete, normalize_sora_market,
)
from modules.sora_run import evaluate_sora_run, prepare_sora_run, sora_exports
from modules.sp_api_catalog import JP_MARKETPLACE, normalize_catalog_item

BRAND_DIR = Path(__file__).resolve().parents[1] / "guardrails" / "brand_monitoring"
COMMUNITY_DIR = Path(__file__).resolve().parents[1] / "guardrails" / "community_ng"


class Client:
    provider_name = 'sp_api_catalog_2022_04_01'
    product_field_prefix = 'spapi'
    verification_label = 'SP_API_VERIFIED'

    def __init__(self, attributes=None, brand='試験ブランド'):
        self.attributes, self.brand = attributes or {}, brand

    def verify_products_by_asin(self, asins):
        return {asin: normalize_catalog_item({'asin': asin, 'attributes': self.attributes,
            'summaries': [{'marketplaceId': JP_MARKETPLACE, 'itemName': '普通のタオル',
                          'brand': self.brand, 'browseClassification': {'displayName': 'タオル'}}]},
            fetched_at='2026-11-01T09:00:00+00:00') for asin in asins}


def run_for(attributes=None, marketplace='MY', asin='B000000001', brand='試験ブランド'):
    verified = verify_preview_rows(preview_candidates(asin), Client(attributes, brand))
    return prepare_sora_run(verified, marketplace=marketplace, auth_calls=1, catalog_calls=1,
                            input_files=('research.csv',))


def test_market_profiles_are_consistent_with_the_files_that_exist():
    assert SORA_MARKET_ORDER[0] == 'SG'  # default market is unchanged
    assert set(SORA_MARKET_ORDER) == set(SORA_MARKETS)
    for code, market in SORA_MARKETS.items():
        assert market.code == code
        assert market.country_counterfeit_list == (code in COUNTRY_FILES)
        if market.country_dictionaries:
            load_guardrail_dictionaries(marketplace=code)
        else:
            with pytest.raises(GuardrailDictionaryError):
                load_guardrail_dictionaries(marketplace=code)
        if market.ng_configured:
            assert market.country_counterfeit_list
    assert not any(market_ng_incomplete(code) for code in SORA_MARKETS)
    assert [normalize_sora_market(v) for v in ('my', ' MY ', 'ＭＹ')] == ['MY'] * 3
    assert all(normalize_sora_market(v) is None for v in ('VN', 'JP', '', None, 5))


def test_my_clean_product_with_missing_size_needs_review():
    run = run_for()
    result = evaluate_sora_run(run)
    row = result.rows[0]
    assert (result.marketplace, row.marketplace) == ('MY', 'MY')
    assert row.guardrail_status == 'REVIEW'
    assert row.final_eligibility == 'REVIEW'
    assert 'MY-VOLUMETRIC' in row.guardrail_matched_terms
    assert 'GUARDRAIL_REVIEW' in row.reason_codes
    assert MARKET_NG_INCOMPLETE_REASON not in row.reason_codes
    assert 'サイズ情報なし' in row.guardrail_note
    assert (result.eligible_count, result.review_count, result.exclude_count) == (0, 1, 0)
    outputs = sora_exports(run, result)
    assert outputs['通過ASIN.txt'] == b''
    assert 'MY-VOLUMETRIC' in outputs['要確認.csv'].decode('utf-8-sig')
    assert json.loads(outputs['実行記録.json'])['要確認'] == 1


def test_second_line_of_defence_refuses_an_unconfigured_market_result(monkeypatch):
    monkeypatch.setitem(SORA_MARKETS, 'MY', replace(SORA_MARKETS['MY'], ng_configured=False))
    run = run_for()
    result = evaluate_sora_run(run)
    forged_row = replace(result.rows[0], final_eligibility='ELIGIBLE')
    forged = replace(result, rows=(forged_row,), eligible_count=1, review_count=0)
    with pytest.raises(ValueError):
        sora_exports(run, forged)
    # A row that is ELIGIBLE although the count says zero is refused as well.
    with pytest.raises(ValueError):
        sora_exports(run, replace(result, rows=(forged_row,)))


@pytest.mark.parametrize(('attributes', 'expected', 'held'), [
    ({'bullet_point': [{'value': '医薬部外品'}]}, 'EXCLUDE', False),
    ({'batteries_included': [{'value': True}]}, 'EXCLUDE', False),
    ({'safety_warning': [{'value': 'LPG 高圧ガス'}]}, 'REVIEW', False),
    ({}, 'REVIEW', False),
])
def test_my_keeps_common_stops_and_only_demotes_would_be_passes(attributes, expected, held):
    result = evaluate_sora_run(run_for(attributes))
    row = result.rows[0]
    assert row.final_eligibility == expected
    assert (MARKET_NG_INCOMPLETE_REASON in row.reason_codes) is held
    assert result.eligible_count == (expected == 'ELIGIBLE')


@pytest.mark.parametrize('marketplace', ['PH', 'SG'])
def test_ph_sg_results_are_unchanged_and_never_carry_the_new_reason(marketplace):
    for attributes, expected in (({}, 'ELIGIBLE'), ({'bullet_point': [{'value': '医薬部外品'}]}, 'EXCLUDE')):
        result = evaluate_sora_run(run_for(attributes, marketplace))
        assert result.rows[0].final_eligibility == expected
        assert all(MARKET_NG_INCOMPLETE_REASON not in r.reason_codes for r in result.rows)
        assert b'B000000001' in sora_exports(run_for(attributes, marketplace), result)['通過ASIN.txt'] or expected != 'ELIGIBLE'


@pytest.mark.parametrize('bad', ['VN', 'JP', '', 'my2', None, 5])
def test_unsupported_markets_are_still_rejected(bad):
    run = run_for(marketplace='SG')
    with pytest.raises(ValueError):
        prepare_sora_run(verify_preview_rows(preview_candidates('B000000001'), Client()), marketplace=bad,
                         auth_calls=1, catalog_calls=1)
    with pytest.raises(ValueError):
        SoraAcquisition(({'row_id': '1', 'asin': 'B000000001'},), bad, ())
    with pytest.raises(PrelistingGateError):
        evaluate_prelisting_gate(run.candidates, [], marketplace=bad, expected_shop_count=0,
                                 check_existing_listings=False)


def test_my_gate_refuses_listing_check_and_sg_body_confirmations():
    run = run_for()
    with pytest.raises(PrelistingGateError):
        evaluate_prelisting_gate(run.candidates, [], marketplace='MY', expected_shop_count=1)
    with pytest.raises(PrelistingGateError):
        evaluate_prelisting_gate(run.candidates, [], marketplace='MY', expected_shop_count=0,
                                 check_existing_listings=False, sg_body_confirmations={})


def test_brand_monitoring_for_my_uses_its_own_list():
    monitoring = load_brand_monitoring('MY')
    scopes = {rule.scope for rule in monitoring.rules}
    assert scopes == {'ALL', 'COMPANY', 'MY'}
    assert monitoring.matches('Hada Labo')
    assert load_brand_monitoring('MY', without_country_list=True).matches('Hada Labo')
    ipr = set(json.loads((BRAND_DIR / 'ipr.json').read_text(encoding='utf-8'))['brands'])
    shared = set(json.loads((BRAND_DIR / 'company.json').read_text(encoding='utf-8'))['brands']) | ipr
    sg_only = next(b for b in json.loads((BRAND_DIR / 'counterfeit_sg.json').read_text(encoding='utf-8'))['brands']
                   if b not in shared and b not in json.loads(
                       (BRAND_DIR / 'counterfeit_my.json').read_text(encoding='utf-8'))['brands'] and b not in json.loads(
                       (BRAND_DIR / 'counterfeit_ph.json').read_text(encoding='utf-8'))['brands'])
    row = {'product_title': '普通のタオル', 'brand': sg_only, 'category': 'タオル'}
    assert apply_guardrails([row], marketplace='SG')[0]['guardrail_status'] == 'BLOCK'
    assert apply_guardrails([row], marketplace='MY')[0]['guardrail_status'] != 'BLOCK'
    shared_brand = sorted(ipr)[0]
    assert apply_guardrails([{**row, 'brand': shared_brand}], marketplace='MY')[0]['guardrail_status'] == 'BLOCK'


def test_my_uses_shared_rules_and_existing_community_reports_only():
    assert apply_guardrails([{'product_title': 'タバコ'}], marketplace='MY')[0]['guardrail_status'] == 'BLOCK'
    assert apply_guardrails([{'product_title': '普通のタオル'}], marketplace='MY')[0]['guardrail_status'] == 'SAFE'
    assets = load_community_ng_assets(COMMUNITY_DIR)
    my_asin = next(b.asin for b in assets.asin_blocks if b.marketplace == 'MY')
    row = {'product_title': '普通のタオル', 'candidate_asin': my_asin}
    assert apply_guardrails([row], marketplace='MY')[0]['guardrail_status'] == 'BLOCK'
    # A MY report does not leak into other markets.
    assert apply_guardrails([row], marketplace='SG')[0]['guardrail_status'] == 'SAFE'


def test_sg_and_ph_only_rules_do_not_apply_to_my():
    # These are SG/PH Owner rules.  MY gets its own rules later; nothing is copied.
    for title in ('ビーフジャーキー 60g', 'サバイバルナイフ', 'ドッグフード'):
        assert apply_guardrails([{'product_title': title}], marketplace='MY')[0]['guardrail_status'] in {'SAFE', 'REVIEW', 'BLOCK'}
    from modules.safety_policy import evaluate_policy
    ids = {h.rule_id for t in ('ビーフジャーキー 60g', 'サバイバルナイフ', '防護服') for h in evaluate_policy({'product_title': t}, 'MY')}
    assert not {i for i in ids if i.startswith(('SG-', 'PH-'))}
