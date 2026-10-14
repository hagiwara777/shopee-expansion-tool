"""Synthetic complete P1 proof for legacy formatter integration tests.

The network transport is replaced before Client creation. OFFICIAL_SESSION here
exercises the receipt contract against a fake API, never real acquisition evidence.
"""
from dataclasses import replace
from unittest.mock import patch

from modules.category_ai_core import CategoryCatalog, CategoryNode
from modules.preparation_validity import PreparationSession, ClassificationEvidence, InventoryEvidence
from modules.sg_beta_facts import facts_from_saved_keepa
from modules.sg_beta_workbench import recommendation, capture_weapon_review
from modules.prelisting_candidate_csv import (PrelistingCandidateRow, rows_to_prelisting_candidate_csv,
                                              PRELISTING_CANDIDATE_SCHEMA_VERSION)
from modules.product_text_safety import extract_keepa_product_text_safety_fact, rows_to_product_text_safety_sidecar
from modules.ingredient_safety import extract_keepa_ingredient_safety_fact, rows_to_ingredient_safety_sidecar
from modules.listing_inventory_parser import parse_listing_inventory_csv
from modules.product_review import WeaponImageReviewSession
from modules.shopee_catalog_client import ShopeeCatalogClient, ShopeeCatalogCredentials


def bound_preparation(items, *, shop='22', product_review=None, source_bundle=None):
    items=tuple(items)
    market=items[0].marketplace
    session=PreparationSession(market,shop)
    paths={item.recommended_category_path:item.recommended_category_id for item in items
           if item.category_is_confirmed and item.recommended_category_id is not None}
    ids={path:cid for path,cid in paths.items()}
    for path in tuple(paths):
        parts=path.split(' > ')
        for n in range(1,len(parts)):
            prefix=' > '.join(parts[:n])
            if prefix not in ids: ids[prefix]=9000000+len(ids)
    nodes=[]
    for path,cid in ids.items():
        parts=path.split(' > ')
        parent=' > '.join(parts[:-1])
        nodes.append(CategoryNode(cid,ids.get(parent),parts[-1],path,path in paths))
    session.accept_classification(ClassificationEvidence(session.scope,
        CategoryCatalog(market,'SYNTHETIC_CURRENT',tuple(nodes)), 'SYNTHETIC_CURRENT_CATEGORY',(),(),'SYNTHETIC_RULE_ALIAS_1'))
    inv=parse_listing_inventory_csv(b'Product ID,Parent SKU,Model ID,SKU,Stock\n',
        filename=market+'_inventory.csv',marketplace=market,shop_label=shop)
    session.accept_inventory(InventoryEvidence(session.scope,(inv,),(shop,),'SYNTHETIC_ALL_SHOPS',True))
    for cid in set(paths.values()):
        brands={}
        for item in items:
            if item.recommended_category_id != cid: continue
            bid=getattr(item,'confirmed_brand_id',getattr(item,'recommended_brand_id',None))
            name=getattr(item,'confirmed_brand_name',getattr(item,'recommended_brand_name',''))
            if bid is not None: brands[bid]=name
        if not brands: continue
        response={'response':{'brand_list':[{'brand_id':bid,'display_brand_name':name,
            'original_brand_name':name} for bid,name in brands.items()], 'next_offset':0,'has_next_page':False}}
        with patch('modules.shopee_catalog_client._urlopen_json',return_value=response):
            client=ShopeeCatalogClient(ShopeeCatalogCredentials(1,'FAKE_KEY',int(shop),'FAKE_TOKEN'),marketplace=market)
        session.acquire_brand(client,cid)
    records={}
    for item in items:
        bid=getattr(item,'confirmed_brand_id',getattr(item,'recommended_brand_id',None))
        if item.recommended_category_id is None or bid is None: continue
        current = product_review.current(item) if product_review else None
        fetched=current.text.fetched_at if current else '2026-10-12T00:00:00+00:00'
        raw={'asin':item.candidate_asin,'domainId':5,'title':item.product_title,'brand':item.keepa_brand,
             'categoryTree':[{'catId':(current.root_category_id if current and current.root_category_id else 3210981),
                              'name':item.keepa_category}],
             'description':[], 'ingredients':['water'], 'fetched_at':fetched}
        if current:
            from modules.product_text_safety import product_text_safety_fact_to_payload
            raw.update({k:v for k,v in product_text_safety_fact_to_payload(current.text).items()
                        if k in {'description','features','shortDescription','safetyWarning','itemHighlights'}})
        facts=facts_from_saved_keepa(raw,source_format='keepa_response',evidence_ref='SYNTHETIC_OWN_PRODUCT')
        row=PrelistingCandidateRow(PRELISTING_CANDIDATE_SCHEMA_VERSION,item.source_type,'SYNTHETIC',
            item.source_asin,item.candidate_asin,item.resolver_input_title,item.product_title,
            item.keepa_brand,item.keepa_category,'https://www.amazon.co.jp/dp/'+item.candidate_asin,
            'VERIFIED','KEEPA_VERIFIED','synthetic',fetched,'')
        candidate=rows_to_prelisting_candidate_csv((row,))
        text=extract_keepa_product_text_safety_fact(raw,candidate_asin=item.candidate_asin,fetched_at=fetched)
        ingredient=extract_keepa_ingredient_safety_fact(raw,candidate_asin=item.candidate_asin,fetched_at=fetched)
        record={'asin':item.candidate_asin,'facts':facts.to_dict(),'source':{
            'candidate':candidate.decode('utf-8'),'filename':'synthetic.csv',
            'text':rows_to_product_text_safety_sidecar(candidate,(row,),(text,)).decode('utf-8'),
            'ingredients':rows_to_ingredient_safety_sidecar(candidate,(row,),(ingredient,)).decode('utf-8'), 'body':''}}
        if source_bundle:
            record['source'].update(candidate=source_bundle['candidate_content'].decode('utf-8'),
                text=source_bundle['text_content'].decode('utf-8'),
                ingredients=source_bundle.get('ingredient_content',b'').decode('utf-8'),
                body=source_bundle.get('body_confirmation_content',b'').decode('utf-8'))
        review=product_review or WeaponImageReviewSession(market)
        images={'candidate_asin':item.candidate_asin,'provider':'keepa','capture_error':False,
                'image_urls':[],'root_category_id':3210981}
        if current:
            images.update(image_urls=list(current.image_urls),capture_error=current.image_capture_error,
                          root_category_id=current.root_category_id,provider=current.image_provider)
        else:
            review.supply(recommendation(record,marketplace=market),text=text,images=images)
        record['weapon']=capture_weapon_review(recommendation(record,marketplace=market),review,images=images)
        session.accept_facts(facts)
        record=session.bind_product(record)
        record=session.confirm_category(record,item.recommended_category_id,human_verified=True)
        record=session.confirm_brand(record,bid,human_verified=True)
        records[item.candidate_asin]=record
    return session, records
