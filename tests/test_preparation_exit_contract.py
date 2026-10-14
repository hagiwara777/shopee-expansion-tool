"""Regression of the actual PH/SG exits, with fully synthetic proof."""
from dataclasses import replace
import csv
from io import StringIO
from unittest.mock import patch

import pytest

from modules.category_mapper import build_mapper_exports
from modules.category_mapper_sg_preparation import (build_sg_beta_preparation_files, assess_sg_preparation)
from modules.preparation_validity import PreparationError, BrandEvidence, InventoryEvidence
from preparation_validity_support import bound_preparation
from sls_category_support import ready_item
from test_sg_beta_release import activation, ready
from test_preparation_validity import prepared_case
from test_category_mapper_sg_brand import client_for, payload, raw_brand


def test_ph_old_confirmation_flags_cannot_serialize_ready(tmp_path):
    item=ready_item(tmp_path)
    assert item.listing_ready  # The legacy local classification condition.
    output=build_mapper_exports((item,))
    assert not output.listing_tool_text
    assert not list(csv.DictReader(StringIO(output.groups_csv.decode('utf-8-sig'))))
    assert not output.evaluated_recommendations[0].listing_ready
    assert 'CURRENT_PREPARATION_EVIDENCE_REQUIRED' in output.evaluated_recommendations[0].preparation_review_reason


def test_sg_old_confirmation_flags_cannot_serialize_ready(activation,ready):
    workflow,item=ready
    del workflow.preparation_session
    del workflow.preparation_records
    result=assess_sg_preparation((item,),workflow=workflow)[0]
    assert not result['preparation_complete']
    assert 'CURRENT_PREPARATION_EVIDENCE_REQUIRED' in result['missing_steps']
    assert build_sg_beta_preparation_files((item,),workflow=workflow)[2] == 0


def test_ph_changes_during_formatter_refuse_output(tmp_path,monkeypatch):
    import modules.category_mapper as module
    item=ready_item(tmp_path)
    session,records=bound_preparation((item,))
    original=module.format_preparation_groups
    def invalidate(*a,**k):
        result=original(*a,**k)
        session.begin_fact_refresh(item.candidate_asin)
        return result
    monkeypatch.setattr(module,'format_preparation_groups',invalidate)
    with pytest.raises((ValueError,RuntimeError),match='CHANGED_BEFORE_RETURN'):
        build_mapper_exports((item,),preparation_session=session,preparation_records=records)


def test_sg_changes_during_formatter_refuse_output(activation,ready,monkeypatch):
    import modules.category_mapper_sg_preparation as module
    workflow,item=ready
    original=module.format_preparation_groups
    def invalidate(*a,**k):
        result=original(*a,**k)
        workflow.preparation_session.begin_brand_refresh(item.recommended_category_id)
        return result
    monkeypatch.setattr(module,'format_preparation_groups',invalidate)
    with pytest.raises((ValueError,RuntimeError),match='CHANGED_BEFORE_RETURN'):
        build_sg_beta_preparation_files((item,),workflow=workflow)


@pytest.mark.parametrize('market',['PH','SG'])
@pytest.mark.parametrize('pages',[
    [payload([raw_brand()],next_offset=10,has_next_page=True)],
    [payload([raw_brand()],next_offset=10,has_next_page=True),payload([raw_brand()])],
    [payload([raw_brand()],next_offset=10,has_next_page=True),RuntimeError('SYNTHETIC_FAILURE')],
    [payload([{}])],
])
def test_current_brand_invalidated_on_partial_bad_or_failed_refresh(market,pages):
    session,record=prepared_case(market,shop='22')
    client,_=client_for(pages,marketplace=market)
    with pytest.raises((ValueError,RuntimeError,StopIteration)):
        session.acquire_brand(client,100578,max_pages=1 if len(pages)==1 else 2)
    assert not session.assess(record)['valid']


@pytest.mark.parametrize('market',['PH','SG'])
def test_mock_acquisition_never_promoted_to_official(market):
    session,record=prepared_case(market,shop='22')
    client,calls=client_for([payload([raw_brand(7,'Synthetic Maker')])],marketplace=market)
    obs=session.acquire_brand(client,100578)
    assert obs.source=='OFFLINE_MOCK' and len(calls)==1
    record=session.confirm_brand(record,7,human_verified=True)
    assert session.assess(record)['valid']
    with pytest.raises(PreparationError,match='OFFICIAL_CURRENT'):
        session.output((record,),operational=True)
    with pytest.raises(PreparationError):
        session.accept_brand(BrandEvidence(session.scope,replace(obs,source='OFFICIAL_SESSION')))


@pytest.mark.parametrize('market',['PH','SG'])
def test_complete_strict_acquisition_supports_operational_contract_without_network(market):
    session,record=prepared_case(market,shop='22')
    from modules.shopee_catalog_client import ShopeeCatalogClient,ShopeeCatalogCredentials
    # Explicit fake API fixture, not evidence of a real official response.
    with patch('modules.shopee_catalog_client._urlopen_json',return_value=payload([raw_brand(7,'Synthetic Maker')])):
        client=ShopeeCatalogClient(ShopeeCatalogCredentials(1,'FAKE_KEY',22,'FAKE_TOKEN'),marketplace=market)
    session.acquire_brand(client,100578)
    record=session.confirm_brand(record,7,human_verified=True)
    output,_=session.output((record,),operational=True)
    assert next(csv.DictReader(StringIO(output.decode('utf-8-sig'))))['listing_ready']=='TRUE'
    session.begin_brand_refresh(100578)
    with pytest.raises(PreparationError): session.output((record,),operational=True)


@pytest.mark.parametrize('market',['PH','SG'])
def test_category_path_missing_id_leaf_and_inventory_market_rejected(market):
    session,record=prepared_case(market)
    record['category']['category_id']=9999999
    assert not session.assess(record)['valid']
    with pytest.raises(PreparationError):
        session.confirm_category(record,9000000,human_verified=True)  # parent
    other=replace(session._inventory.inventories[0],marketplace='SG' if market=='PH' else 'PH')
    with pytest.raises(PreparationError):
        InventoryEvidence(session.scope,(other,),(session.scope.shop_id,),'WRONG_MARKET',True)


@pytest.mark.parametrize('market',['PH','SG'])
def test_field_provenance_and_text_inconsistency_are_not_hidden(market):
    session,record=prepared_case(market)
    record['facts']['fields']['description']['value']=['different body text']
    from modules.sg_beta_facts import ProductFacts
    session.accept_facts(ProductFacts.from_dict(record['facts']))
    record=session.confirm_category(record,100578,human_verified=True)
    record=session.confirm_brand(record,7,human_verified=True)
    assert 'FACT_TEXT_MISMATCH:description' in session.assess(record)['reasons']


def test_ph_expired_proof_can_recover_without_erasing_manual_safety_stop(tmp_path):
    item=ready_item(tmp_path)
    rejected=build_mapper_exports((item,)).evaluated_recommendations[0]
    session,records=bound_preparation((item,))
    recovered=build_mapper_exports((rejected,),preparation_session=session,preparation_records=records)
    assert recovered.listing_tool_text and recovered.evaluated_recommendations[0].listing_ready
    stopped=replace(rejected,manual_review_required=True,manual_review_reason='Independent manual stop')
    result=build_mapper_exports((stopped,),preparation_session=session,preparation_records=records)
    assert not result.listing_tool_text and result.evaluated_recommendations[0].manual_review_required


@pytest.mark.parametrize('market',['PH','SG'])
def test_numeric_boolean_brand_kind_and_wrong_image_root_stop(market):
    session,record=prepared_case(market)
    record['brand']['is_no_brand']=0
    assert 'BRAND_DECISION_INVALID' in session.assess(record)['reasons']
    record=session.confirm_brand(record,7,human_verified=True)
    record['weapon']['images']['root_category_id']=999999
    assert 'FACT_IMAGE_ROOT_MISMATCH' in session.assess(record)['reasons']


def test_operational_auto_rule_is_not_activated_by_offline_match():
    session,record=prepared_case('SG')
    record['category']['authority']='AUTO_RULE'
    with pytest.raises(PreparationError,match='AUTO_RULE_OPERATION_NOT_APPROVED'):
        session.require_operational(record)


def test_shared_sg_operational_output_retains_activation_gate(monkeypatch):
    from modules.sg_beta_release import SGBetaNotAdopted
    session,record=prepared_case('SG')
    def stopped():
        raise SGBetaNotAdopted('SYNTHETIC_STATE_STOP')
    monkeypatch.setattr('modules.sg_beta_release.require_sg_beta_operation',stopped)
    with pytest.raises(SGBetaNotAdopted): session.output((record,),operational=True)


def test_ph_clear_invalidates_the_old_receipt_object(tmp_path):
    from modules.category_mapper_ui import clear_category_mapper_result
    item=ready_item(tmp_path)
    session,records=bound_preparation((item,))
    state={'category_mapper_preparation_context':{'session':session,'records':records}}
    clear_category_mapper_result(state)
    assert not state and not session.assess(records[item.candidate_asin])['valid']
