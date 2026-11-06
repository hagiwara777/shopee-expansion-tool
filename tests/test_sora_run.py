import codecs
import csv
from dataclasses import replace
from io import StringIO
import json

import pytest

from modules.asin_resolver import preview_candidates, verify_preview_rows
from modules.prelisting_gate import PrelistingGateError, evaluate_prelisting_gate
from modules.prelisting_gate_csv import build_prelisting_gate_exports
from modules.prelisting_gate_ui import build_prelisting_gate_preview_rows, localize_prelisting_gate_preview_rows
from modules.sora_run import evaluate_sora_run, prepare_sora_run, sora_exports
from modules.sp_api_catalog import JP_MARKETPLACE, normalize_catalog_item


class Client:
    provider_name = 'sp_api_catalog_2022_04_01'
    product_field_prefix = 'spapi'
    verification_label = 'SP_API_VERIFIED'

    def __init__(self, attributes=None):
        self.attributes = attributes or {}

    def verify_products_by_asin(self, asins):
        return {asin: normalize_catalog_item({'asin': asin, 'attributes': self.attributes,
            'summaries': [{'marketplaceId': JP_MARKETPLACE, 'itemName': '普通のタオル',
                          'brand': '試験ブランド', 'browseClassification': {'displayName': 'タオル'}}]},
            fetched_at='2026-11-01T09:00:00+00:00') for asin in asins}


def run_for(attributes=None, marketplace='SG'):
    verified = verify_preview_rows(preview_candidates('B000000001'), Client(attributes))
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


@pytest.mark.parametrize('marketplace', ['PH', 'SG'])
@pytest.mark.parametrize(('description', 'expected'), [
    ('全成分：水、香料、サリチル酸', 'REVIEW'),
    ('<h3>全成分</h3>水、香料、ナイアシンアミド', 'REVIEW'),
    ('全成分：水、香料\nサリチル酸配合', 'EXCLUDE'),
    ('水、香料、サリチル酸', 'EXCLUDE'),
])
def test_sp_api_description_preserves_ingredient_section_boundaries(description, expected, marketplace):
    run = run_for({'product_description': [{'value': description}]}, marketplace)
    result = evaluate_sora_run(run)
    assert result.rows[0].final_eligibility == expected
    outputs = sora_exports(run, result)
    assert b'B000000001' in outputs['要確認.csv' if expected == 'REVIEW' else '停止.csv']


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


def _synthetic_export_result(run, *, exclude=0, review=0, eligible=0):
    """Create distinct, interleaved decisions without changing safety evaluation."""
    original = evaluate_sora_run(run)
    seed = original.rows[0]
    rows = []
    definitions = (
        ('EXCLUDE', exclude, 'BLOCK', 'GUARDRAIL_BLOCK'),
        ('REVIEW', review, 'REVIEW', 'GUARDRAIL_REVIEW'),
        ('ELIGIBLE', eligible, 'SAFE', None),
    )
    for i in range(max(exclude, review, eligible, 0)):
        for status, count, guardrail, reason in definitions:
            if i >= count:
                continue
            index = len(rows) + 1
            candidate = replace(seed.candidate, candidate_asin=f'B{index:09d}',
                                product_title=f'合成商品,{index} "確認"')
            rows.append(replace(seed, candidate=candidate, guardrail_status=guardrail,
                                guardrail_matched_terms='試験語', guardrail_note='前後, "メモ"\n2行',
                                final_eligibility=status, reason_codes=(reason,) if reason else ()))
    return replace(original, rows=tuple(rows), candidate_count=len(rows),
                   exclude_count=exclude, review_count=review, eligible_count=eligible)


def _read_reason_csv(data):
    assert data.startswith(codecs.BOM_UTF8)
    return list(csv.DictReader(StringIO(data.decode('utf-8-sig'), newline='')))


def test_sora_reason_exports_include_all_decisions_beyond_the_display_limit():
    run = run_for()
    result = _synthetic_export_result(run, exclude=130, review=120, eligible=50)
    outputs = sora_exports(run, result)
    assert set(outputs) == {'停止.csv', '要確認.csv', '通過ASIN.txt', '実行記録.json'}
    for status, filename, expected_count in (
        ('EXCLUDE', '停止.csv', 130), ('REVIEW', '要確認.csv', 120),
    ):
        rows = _read_reason_csv(outputs[filename])
        expected = [row.candidate.candidate_asin for row in result.rows if row.final_eligibility == status]
        assert len(rows) == expected_count
        assert [row['ASIN'] for row in rows] == expected
        assert rows[100]['判定メモ'] == '前後, "メモ"\n2行'
        assert len(build_prelisting_gate_preview_rows(result, final_eligibility=status)) == 100
    eligible = [row.candidate.candidate_asin for row in result.rows if row.final_eligibility == 'ELIGIBLE']
    assert len(eligible) == 50
    assert outputs['通過ASIN.txt'] == ('\n'.join(eligible) + '\n').encode('utf-8')


@pytest.mark.parametrize('count', [0, 1, 100])
def test_sora_reason_csvs_match_existing_bytes_at_or_below_100(count):
    run = run_for()
    result = _synthetic_export_result(run, exclude=count, review=count)
    outputs = sora_exports(run, result)
    for status, filename in (('EXCLUDE', '停止.csv'), ('REVIEW', '要確認.csv')):
        old_rows = localize_prelisting_gate_preview_rows(
            build_prelisting_gate_preview_rows(result, final_eligibility=status))
        columns = tuple(old_rows[0]) if old_rows else ('ASIN', '商品名', '理由')
        old = StringIO(newline='')
        writer = csv.DictWriter(old, fieldnames=columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows(old_rows)
        assert outputs[filename] == old.getvalue().encode('utf-8-sig')
        assert len(_read_reason_csv(outputs[filename])) == count


def test_sora_reason_csv_small_case_has_existing_columns_and_utf8_bom():
    run = run_for()
    result = _synthetic_export_result(run, exclude=1, review=1, eligible=1)
    outputs = sora_exports(run, result)
    header = 'ASIN,商品名,ブランド,カテゴリ,保安判定,該当語,判定メモ,既出品,商品情報,最終判定,理由,既出品一致件数\n'
    common = ',試験ブランド,タオル,{},試験語,"前後, ""メモ""\n2行",重複照合は未実施,商品情報あり,{},{},0\n'
    exclude = 'B000000001,"合成商品,1 ""確認"""' + common.format('除外対象', '除外', '禁止・除外ルール該当')
    review = 'B000000002,"合成商品,2 ""確認"""' + common.format('要確認', '要確認', '要確認ルール該当')
    assert outputs['停止.csv'] == (header + exclude).encode('utf-8-sig')
    assert outputs['要確認.csv'] == (header + review).encode('utf-8-sig')
