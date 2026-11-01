import json

import pytest

from modules.asin_resolver import preview_candidates, verify_preview_rows
from modules.prelisting_gate import PrelistingGateError, evaluate_prelisting_gate
from modules.prelisting_gate_csv import build_prelisting_gate_exports
from modules.sora_run import evaluate_sora_run, prepare_sora_run, sora_exports
from modules.sp_api_catalog import JP_MARKETPLACE, normalize_catalog_item


class Client:
    provider_name = 'sp_api_catalog_2022_04_01'
    product_field_prefix = 'spapi'
    verification_label = 'SP_API_VERIFIED'

    def __init__(self, attributes=None, title='普通のタオル'):
        self.attributes = attributes or {}
        self.title = title

    def verify_products_by_asin(self, asins):
        return {asin: normalize_catalog_item({'asin': asin, 'attributes': self.attributes,
            'summaries': [{'marketplaceId': JP_MARKETPLACE, 'itemName': self.title,
                          'brand': '試験ブランド', 'browseClassification': {'displayName': 'タオル'}}]},
            fetched_at='2026-11-01T09:00:00+00:00') for asin in asins}


def run_for(attributes=None, marketplace='SG', *, title='普通のタオル'):
    verified = verify_preview_rows(preview_candidates('B000000001'), Client(attributes, title))
    return prepare_sora_run(verified, marketplace=marketplace, auth_calls=1, catalog_calls=1,
                            input_files=('research.csv',))


@pytest.mark.parametrize('marketplace', ['PH', 'SG'])
@pytest.mark.parametrize(('attributes', 'expected'), [
    ({}, 'ELIGIBLE'),
    ({'bullet_point': [{'value': '医薬部外品'}]}, 'EXCLUDE'),
    ({'safety_warning': [{'value': 'LPG 高圧ガス'}]}, 'REVIEW'),
    ({'batteries_included': [{'value': True}]}, 'EXCLUDE'),
    ({'batteries_required': [{'value': True}]}, 'REVIEW'),
])
def test_actual_sp_api_source_reaches_all_safety_checks(attributes, expected, marketplace):
    run = run_for(attributes, marketplace)
    result = evaluate_sora_run(run)
    assert result.rows[0].final_eligibility == expected
    assert result.rows[0].existing_listing_status == 'NOT_CHECKED'
    outputs = sora_exports(run, result)
    record = json.loads(outputs['実行記録.json'])
    assert record['重複照合'] == '重複照合は未実施'
    assert record['SP-API呼び出し合計'] == 2
    assert (b'B000000001' in outputs['通過ASIN.txt']) == (expected == 'ELIGIBLE')
    assert len(outputs) == 4
    # The shared audit exporter must preserve NOT_CHECKED as well.
    assert b'NOT_CHECKED' in build_prelisting_gate_exports(result).audit_csv


def test_legacy_inventory_required_default_has_not_been_weakened():
    run = run_for()
    with pytest.raises(PrelistingGateError):
        evaluate_prelisting_gate(run.candidates, [], marketplace='SG', expected_shop_count=0)
    with pytest.raises(PrelistingGateError):
        evaluate_prelisting_gate(run.candidates, [], marketplace='SG', expected_shop_count=1,
                                 check_existing_listings=False)


def test_market_specific_ingredient_and_product_text_rules_preserved():
    sg = run_for({'ingredients': [{'value': 'ジフェンヒドラミン'}]}, 'SG')
    ph = run_for({'bullet_point': [{'value': 'hemp'}]}, 'PH')
    assert evaluate_sora_run(sg).rows[0].final_eligibility == 'EXCLUDE'
    assert evaluate_sora_run(ph).rows[0].final_eligibility == 'EXCLUDE'


def test_unverified_product_never_becomes_gate_candidate():
    rows = verify_preview_rows(preview_candidates('B000000001'), Client())
    rows += [{'asin': 'B000000002', 'status': 'UNKNOWN', 'verification': 'SP_API_NOT_FOUND'}]
    run = prepare_sora_run(rows, marketplace='SG', auth_calls=1, catalog_calls=1)
    assert run.unverified_row_count == 1
    assert evaluate_sora_run(run).candidate_count == 1


@pytest.mark.parametrize('marketplace', ['PH', 'SG'])
@pytest.mark.parametrize('term', [
    '塩酸ジフェンヒドラミン', 'diphenhydramine',
    'diphenhydramine hydrochloride', 'ジフェンヒドラミン',
])
@pytest.mark.parametrize('attribute', [
    'ingredients', 'active_ingredients', 'special_ingredients',
    'product_description', 'bullet_point', 'short_product_description',
    'safety_warning', 'special_feature',
])
def test_approved_medical_ingredients_in_each_captured_field_excluded_from_handoff(
    marketplace, term, attribute,
):
    run = run_for({attribute: [{'value': term}]}, marketplace)
    result = evaluate_sora_run(run)
    assert result.rows[0].final_eligibility == 'EXCLUDE'
    assert term in result.rows[0].guardrail_matched_terms
    assert sora_exports(run, result)['通過ASIN.txt'] == b''


def test_ph_ingredient_dictionary_is_limited_to_owner_approved_four_spellings():
    from modules.guardrails import load_guardrail_dictionaries
    rules = [rule for rule in load_guardrail_dictionaries(marketplace='PH').keyword_rules
             if rule.risk_category == 'regulated_ingredient']
    assert {rule.term for rule in rules} == {
        '塩酸ジフェンヒドラミン', 'diphenhydramine',
        'diphenhydramine hydrochloride', 'ジフェンヒドラミン',
    }
    assert all(rule.action == 'BLOCK' and rule.match_field == 'title' for rule in rules)


@pytest.mark.parametrize('marketplace', ['PH', 'SG'])
@pytest.mark.parametrize('term', [
    '塩酸ジフェンヒドラミン', 'diphenhydramine',
    'diphenhydramine hydrochloride', 'ジフェンヒドラミン',
])
def test_approved_ingredient_names_in_product_title_excluded(marketplace, term):
    run = run_for(marketplace=marketplace, title=term)
    result = evaluate_sora_run(run)
    assert result.rows[0].final_eligibility == 'EXCLUDE'
    assert sora_exports(run, result)['通過ASIN.txt'] == b''
