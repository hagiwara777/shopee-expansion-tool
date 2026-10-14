"""P1 synthetic PH/SG negative regression. No production files or API access."""
from dataclasses import asdict, replace
from io import StringIO
import copy
import csv

import pytest

from modules.preparation_validity import (
    PreparationSession, PreparationError, ClassificationEvidence, BrandEvidence, InventoryEvidence,
)
from modules.sg_beta_workbench import BrandObservation, capture_weapon_review, recommendation
from modules.sg_beta_facts import facts_from_saved_keepa, ProductFacts
from modules.category_ai_core import CategoryCatalog
from modules.product_review import WeaponImageReviewSession
from modules.product_text_safety import extract_keepa_product_text_safety_fact, rows_to_product_text_safety_sidecar
from modules.prelisting_candidate_csv import expansion_rows_to_prelisting_candidates, rows_to_prelisting_candidate_csv
from test_sg_initial_beta import catalog, inventory, raw


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError('P1 must remain offline')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('modules.shopee_catalog_client.urlopen', forbidden)


def prepared_case(market='SG', *, shop='synthetic-shop', title='Synthetic wired headphone', root=3210981):
    session = PreparationSession(market, shop)
    tree = replace(catalog(), marketplace=market)
    classification = ClassificationEvidence(session.scope, tree, 'MOCK_CATEGORY_1', (), (), 'RULE_ALIAS_1')
    session.accept_classification(classification)
    observation = BrandObservation(100578, shop, ((7, 'Synthetic Maker', False), (0, 'No brand', True)),
                                   'MOCK_BRAND_1', True, True, 'OFFLINE_MOCK', marketplace=market)
    session.accept_brand(BrandEvidence(session.scope, observation))
    inv = inventory(shop=shop, name=market+'_shop.csv', marketplace=market)
    session.accept_inventory(InventoryEvidence(session.scope, (inv,), (shop,), 'MOCK_INVENTORY_1', True))
    product = raw(title=title)
    product['categoryTree'][0]['catId'] = root if type(root) is int else 1
    facts = facts_from_saved_keepa(product, source_format='keepa_response', evidence_ref='SYNTHETIC_RAW')
    rows = expansion_rows_to_prelisting_candidates([{
        'seed_asin':'B000000000', 'candidate_asin':product['asin'], 'product_title':title,
        'brand':product['brand'], 'category':'Headphones', 'source':'synthetic',
        'fetched_at':product['fetched_at']}])
    content = rows_to_prelisting_candidate_csv(rows)
    text = extract_keepa_product_text_safety_fact(product, candidate_asin=facts.asin,
                                                fetched_at=product['fetched_at'])
    record = {'asin':facts.asin, 'facts':facts.to_dict(), 'source':{
        'candidate':content.decode('utf-8'), 'filename':'candidates.csv',
        'text':rows_to_product_text_safety_sidecar(content,rows,[text]).decode('utf-8'),
        'ingredients':'', 'body':''}}
    item = recommendation(record, marketplace=market)
    images = {'candidate_asin':facts.asin, 'provider':'keepa', 'capture_error':False,
              'image_urls':[], 'root_category_id':root}
    review = WeaponImageReviewSession(market)
    review.supply(item, text=text, images=images)
    record['weapon'] = capture_weapon_review(item, review, images=images)
    session.accept_facts(facts)
    record = session.bind_product(record)
    record = session.confirm_category(record, 100578, human_verified=True)
    record = session.confirm_brand(record, 7, human_verified=True)
    return session, record


@pytest.mark.parametrize('market', ['PH','SG'])
def test_complete_current_evidence_can_prepare_offline(market):
    session, record = prepared_case(market)
    result = session.assess(record)
    assert result['valid'], result
    assert not result['listing_ready']
    output, text = session.output([record])
    row = list(csv.DictReader(StringIO(output.decode('utf-8-sig'))))[0]
    assert row['marketplace'] == market and row['listing_ready'] == 'FALSE'
    assert row['output_scope'] == 'PH_SG_P1_OFFLINE'
    assert b'B000000001' in text


@pytest.mark.parametrize('source,target', [('PH','SG'),('SG','PH')])
def test_other_market_records_and_ids_rejected_even_when_ids_match(source,target):
    a, record = prepared_case(source)
    b, _ = prepared_case(target)
    assert not b.assess(record)['valid']
    with pytest.raises(PreparationError):
        b.output([record])
    with pytest.raises(PreparationError):
        b.accept_brand(BrandEvidence(a.scope, a._brands[100578]))
    with pytest.raises(PreparationError):
        b.accept_classification(a._classification)


@pytest.mark.parametrize('market',['PH','SG'])
def test_other_shop_and_restart_cannot_reuse_confirmations(market):
    first, record = prepared_case(market)
    for second in (prepared_case(market,shop='other-shop')[0], prepared_case(market)[0]):
        assert not second.assess(record)['valid']
        with pytest.raises(PreparationError):
            second.bind_product(record)


@pytest.mark.parametrize('market',['PH','SG'])
@pytest.mark.parametrize('target',['catalog','brand','inventory','fact'])
def test_refresh_failure_invalidates_before_new_response(market,target):
    session, record = prepared_case(market)
    if target == 'catalog': session.begin_catalog_refresh()
    elif target == 'brand': session.begin_brand_refresh(100578)
    elif target == 'inventory': session.begin_inventory_refresh()
    else: session.begin_fact_refresh(record['asin'])
    assert not session.assess(record)['valid']
    with pytest.raises(PreparationError): session.output([record])


@pytest.mark.parametrize('market',['PH','SG'])
@pytest.mark.parametrize('field',['title','brand','category_tree'])
@pytest.mark.parametrize('origin',['SEED_FALLBACK','UNKNOWN','MISSING'])
def test_human_confirmation_does_not_prove_own_jp_fact(market,field,origin):
    session, record = prepared_case(market)
    record['facts']['fields'][field]['origin'] = origin
    session.accept_facts(ProductFacts.from_dict(record['facts']))
    record = session.confirm_category(record,100578,human_verified=True)
    record = session.confirm_brand(record,7,human_verified=True)
    assert 'OWN_JP_FACT_REQUIRED:'+field in session.assess(record)['reasons']
    with pytest.raises(PreparationError): session.output([record])


@pytest.mark.parametrize('market',['PH','SG'])
@pytest.mark.parametrize('change',[{'complete':False},{'current':False},{'source':'SAVED_COMPARISON'},
                                    {'source':'OFFICIAL_SESSION'}, {'brands':()}])
def test_partial_saved_unproven_official_brands_never_current(market,change):
    session, record = prepared_case(market)
    with pytest.raises(PreparationError):
        session.accept_brand(BrandEvidence(session.scope,replace(session._brands[100578],**change)))
    assert not session.assess(record)['valid']


@pytest.mark.parametrize('market',['PH','SG'])
@pytest.mark.parametrize('target',['rule','catalog','name','kind','id'])
def test_changed_catalog_rule_and_brand_invalidate(market,target):
    session, record = prepared_case(market)
    if target in {'rule','catalog'}:
        evidence = session._classification
        if target == 'rule': evidence=replace(evidence,revision='RULE_ALIAS_2')
        else: evidence=replace(evidence,catalog=replace(evidence.catalog,catalog_version='changed'))
        old = session._brands[100578]
        session.accept_classification(evidence)
        session.accept_brand(BrandEvidence(session.scope,old))
    else:
        option = {'name':(7,'Changed',False),'kind':(7,'No brand',True),'id':(8,'Synthetic Maker',False)}[target]
        session.accept_brand(BrandEvidence(session.scope,replace(session._brands[100578],brands=(option,))))
    assert not session.assess(record)['valid']
    with pytest.raises(PreparationError): session.output([record])


@pytest.mark.parametrize('market',['PH','SG'])
def test_no_brand_requires_explicit_current_option_and_never_fallback(market):
    session, record = prepared_case(market)
    record['brand'] = None
    assert not session.assess(record)['valid']
    with pytest.raises(PreparationError): session.confirm_brand(record,999,human_verified=True)
    explicit = session.confirm_brand(record,0,human_verified=True)
    assert explicit['brand']['is_no_brand'] and session.assess(explicit)['valid']


@pytest.mark.parametrize('market',['PH','SG'])
def test_existing_in_any_shop_refuses_preparation(market):
    session, record = prepared_case(market)
    other = inventory(record['asin'],shop='second-shop',name=market+'_second.csv',marketplace=market)
    session.accept_inventory(InventoryEvidence(session.scope, (session._inventory.inventories[0],other),
        (session.scope.shop_id,'second-shop'),'MOCK_INVENTORY_2',True))
    result=session.assess(record)
    assert not result['valid'] and result['existing']
    with pytest.raises(PreparationError): session.output([record])


@pytest.mark.parametrize('market',['PH','SG'])
@pytest.mark.parametrize('title',['Synthetic rechargeable battery', 'Synthetic power bank'])
def test_battery_and_block_not_released_by_classification(market,title):
    session, record=prepared_case(market,title=title)
    result=session.assess(record)
    assert not result['valid'] and any('GATE_' in r for r in result['reasons'])
    with pytest.raises(PreparationError): session.output([record])


@pytest.mark.parametrize('market',['PH','SG'])
def test_missing_and_target_image_doubt_stop(market):
    session, record=prepared_case(market,root=None)
    assert not session.assess(record)['valid']
    record.pop('weapon')
    assert 'WEAPON_EVIDENCE_MISSING' in session.assess(record)['reasons']


@pytest.mark.parametrize('market',['PH','SG'])
def test_output_revalidates_after_formatter(market,monkeypatch):
    import modules.preparation_validity as module
    session, record=prepared_case(market)
    original=module.format_preparation_groups
    def invalidate(*a,**k):
        result=original(*a,**k)
        session.begin_inventory_refresh()
        return result
    monkeypatch.setattr(module,'format_preparation_groups',invalidate)
    with pytest.raises(PreparationError,match='CHANGED_BEFORE_RETURN'):
        session.output([record])
