"""Safety contracts retained when the retired combined screen is removed.

All inputs and analyzers here are synthetic; no product or network is used.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from modules.category_mapper import apply_manual_brand, build_mapper_exports, refresh_sls_results
from modules.ingredient_safety import parse_ingredient_safety_sidecar
from modules.ph_image_safety import (
    ImageSafetyError, apply_image_safety, image_sidecar_bytes, parse_image_sidecar,
    record_human_decision, run_image_safety,
)
from modules.prelisting_gate import PrelistingGateError
from modules.prelisting_gate_csv import build_prelisting_gate_exports
from modules.prelisting_gate_handoff import validate_packet
from modules.prelisting_candidate_csv import parse_prelisting_candidate_csv
from modules.prelisting_sg_body_safety import SGBodySafetyError, body_confirmation_bytes, parse_body_confirmations
from modules.product_text_safety import parse_product_text_safety_sidecar
from modules.sls_category_assets import SlsAssetError, load_ph_context
from sls_category_support import copy_assets, ready_item
from test_ph_image_safety import FakeAnalyzer, candidate, fact, setup_case
from test_expansion_gate_handoff import packet, result as generated_result
from test_prelisting_gate import candidate as gate_candidate, evidence, evaluate, inventory
from test_prelisting_sg_body_safety import case, confirm, run


@pytest.mark.parametrize('market', ['PH', 'SG'])
@pytest.mark.parametrize(('title', 'description', 'root'), [
    ('ordinary storage box', 'ordinary description', 1),
    ('ordinary product', 'rechargeable battery inside', 1),
    ('ordinary product', 'contains hemp', 1),
    ('Contact lens case', 'ordinary description', 1),
    ('ordinary storage box', 'ordinary description', None),
    ('synthetic penalty product', 'ordinary description', 1),
])
def test_manual_and_packet_material_keep_identical_gate_results(market, title, description, root):
    asin = 'B000FQTRS0' if title == 'synthetic penalty product' else 'B000000001'
    p = packet(market, generated_result(title=title, description=description, asin=asin, root=root))
    raw = p.candidate.content
    manual = parse_prelisting_candidate_csv(raw, filename=p.candidate.name)
    internal = validate_packet(p, marketplace=market, generation=p.generation)
    ingredient = parse_ingredient_safety_sidecar(p.ingredient.content, filename=p.ingredient.name,
        candidate_content=raw, candidates=manual)
    text = parse_product_text_safety_sidecar(p.product_text.content, filename=p.product_text.name,
        candidate_content=raw, candidates=manual)
    from modules.prelisting_gate import evaluate_prelisting_gate
    def check(candidates):
        value = evaluate_prelisting_gate(candidates, (inventory(marketplace=market, data_row_count=0),),
            marketplace=market, expected_shop_count=1, ingredient_safety=ingredient, product_text_safety=text)
        if market == 'PH':
            image = parse_image_sidecar(p.image.content, candidate_content=raw, candidates=candidates)
            value = apply_image_safety(value, image, raw)
        return value
    first, second = check(manual), check(internal)
    assert first == second
    assert build_prelisting_gate_exports(first) == build_prelisting_gate_exports(second)
    expected = ('EXCLUDE' if title == 'synthetic penalty product' or description == 'contains hemp'
                or ('Contact lens' in title and market == 'SG') else
                'REVIEW' if 'battery' in description or (root is None and market == 'PH') else 'ELIGIBLE')
    assert first.rows[0].final_eligibility == expected


def test_existing_sg_listing_stays_excluded_from_output():
    row = gate_candidate()
    result = evaluate([row], [inventory((evidence('B000000001'),))], marketplace='SG')
    assert result.exclude_count == 1 and 'EXISTING_ASIN' in result.rows[0].reason_codes
    assert build_prelisting_gate_exports(result).eligible_csv is None


@pytest.mark.parametrize('action', ['CATEGORY_REVIEW', 'CATEGORY_EXCLUDE'])
@pytest.mark.parametrize('no_brand', [False, True])
def test_sls_stop_survives_brand_confirmation_and_never_exports(tmp_path, action, no_brand):
    context = load_ph_context()
    category_id = next(cid for cid, rule in context.rules.items() if rule.action == action)
    item = refresh_sls_results((replace(ready_item(tmp_path), recommended_category_id=category_id),),
                               context=context)[0]
    item = apply_manual_brand(item, brand={'brand_id': 0 if no_brand else 123,
                                          'is_no_brand': no_brand})
    assert item.sls_result.action == action
    assert not item.listing_ready
    assert not build_mapper_exports((item,)).listing_tool_text


def test_missing_sls_asset_stops_export_without_changing_database(tmp_path, monkeypatch):
    item = ready_item(tmp_path)
    database = tmp_path / 'mapper.sqlite3'
    before = database.read_bytes()
    assets = copy_assets(tmp_path, monkeypatch)
    (assets / 'markets' / 'PH.json').unlink()
    with pytest.raises(SlsAssetError):
        build_mapper_exports((item,))
    assert database.read_bytes() == before


@pytest.mark.parametrize(('title', 'family'), [
    ('Chef knives set', 'KNIFE'), ('カラコンとケースのセット', 'CONTACT_LENS'),
])
def test_body_confirmation_remains_stopped_after_reload_and_rejects_changed_material(title, family):
    _, candidates, text = case(title)
    saved = body_confirmation_bytes(confirm(candidates, text, family=family))
    restored = parse_body_confirmations(saved, candidates, text)
    for _ in range(2):
        result = run(candidates, text, restored)
        assert result.exclude_count == 1
        assert build_prelisting_gate_exports(result).eligible_csv is None
    changed = replace(text, rows=(replace(text.rows[0], description=('changed material',)),))
    with pytest.raises(SGBodySafetyError):
        parse_body_confirmations(saved, candidates, changed)
    with pytest.raises(PrelistingGateError):
        run(candidates, text, restored, marketplace='PH')


def test_image_review_cannot_release_an_existing_block_or_reuse_changed_evidence():
    content, candidates, base, sidecar = setup_case(
        [candidate(source_asin='B000000001')], [fact(images=())])
    confirmed = record_human_decision(base, sidecar, content, asin='B000000001',
        decision='ALLOW_PREPARATION', reviewed_images=True, note='Synthetic reviewed images')
    result = apply_image_safety(base, confirmed, content)
    assert result.exclude_count == 1
    assert build_prelisting_gate_exports(result).eligible_csv is None
    changed = deepcopy(confirmed)
    changed['rows'][0]['human']['evaluation_id'] = '0' * 64
    with pytest.raises(ImageSafetyError):
        parse_image_sidecar(image_sidecar_bytes(changed), candidate_content=content, candidates=candidates)


def test_image_analyzer_is_not_repeated_and_failure_does_not_leave_partial_result():
    content, _, base, sidecar = setup_case()
    analyzer = FakeAnalyzer()
    done = run_image_safety(base, sidecar, content, analyzer=analyzer)
    run_image_safety(base, done, content, analyzer=analyzer)
    assert len(analyzer.calls) == 1
    before = deepcopy(sidecar)
    with pytest.raises(ImageSafetyError):
        run_image_safety(base, sidecar, content, analyzer=FakeAnalyzer(failure=True))
    assert sidecar == before
