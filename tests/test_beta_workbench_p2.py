"""P2 synthetic restart/abnormal-operation tests; all transport is forbidden."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import StringIO
import csv
import sqlite3

import pytest

from modules.beta_work_store import BetaWorkStore, WorkStoreError
from modules.beta_workbench import BetaWorkBench
from modules.preparation_validity import PreparationSession, ClassificationEvidence, BrandEvidence, InventoryEvidence
from modules.prelisting_candidate_csv import expansion_rows_to_prelisting_candidates, rows_to_prelisting_candidate_csv
from modules.product_text_safety import extract_keepa_product_text_safety_fact, rows_to_product_text_safety_sidecar
from modules.product_review import WeaponImageReviewSession
from modules.sg_beta_facts import ProductFacts, facts_from_saved_keepa
from modules.sg_beta_workbench import BrandObservation, recommendation, capture_weapon_review, _sources
from modules.sg_beta_work_store import SGWorkStore
from test_sg_initial_beta import catalog, inventory, raw


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('P2 is offline only')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('modules.shopee_catalog_client.urlopen', forbidden)


def session_for(market, *, shop='synthetic-shop'):
    session = PreparationSession(market, shop)
    tree = replace(catalog(), marketplace=market)
    session.accept_classification(ClassificationEvidence(session.scope, tree, 'MOCK_CATEGORY_1', (), (), 'RULE_ALIAS_1'))
    observation = BrandObservation(100578, shop, ((7, 'Synthetic Maker', False), (0, 'No brand', True)),
        'MOCK_BRAND_1', True, True, 'OFFLINE_MOCK', marketplace=market)
    session.accept_brand(BrandEvidence(session.scope, observation))
    session.accept_inventory(InventoryEvidence(session.scope,
        (inventory(shop=shop, name=market+'_shop.csv', marketplace=market),), (shop,), 'MOCK_INVENTORY_1', True))
    return session


def product(market, asin='B000000001', *, title='Synthetic wired headphone', root=3210981, source_type='EXPANSION'):
    p = raw(asin, title)
    p['categoryTree'][0]['catId'] = root if type(root) is int else 1
    facts = facts_from_saved_keepa(p, source_format='keepa_response', evidence_ref='SYNTHETIC_RAW')
    rows = expansion_rows_to_prelisting_candidates([{'seed_asin':'B000000000', 'candidate_asin':asin,
        'product_title':title, 'brand':p['brand'], 'category':'Headphones', 'source':'synthetic', 'fetched_at':p['fetched_at']}])
    if source_type=='RESOLVER':
        rows=tuple(replace(r,source_type='RESOLVER',source_asin='',source_id='R0001',source_status='FOUND',
            source_verification='KEEPA_VERIFIED',source='asin_resolver_keepa_verified') for r in rows)
    content = rows_to_prelisting_candidate_csv(rows)
    text = extract_keepa_product_text_safety_fact(p, candidate_asin=asin, fetched_at=p['fetched_at'])
    record = {'asin':asin, 'marketplace':market, 'facts':facts.to_dict(), 'source':{
        'candidate':content.decode('utf-8'), 'filename':'candidate.csv',
        'text':rows_to_product_text_safety_sidecar(content,rows,[text]).decode('utf-8'), 'ingredients':'', 'body':''}}
    item = recommendation(record, marketplace=market)
    images = {'candidate_asin':asin, 'provider':'keepa', 'capture_error':False, 'image_urls':[], 'root_category_id':root}
    review = WeaponImageReviewSession(market)
    review.supply(item, text=text, images=images)
    record['weapon'] = capture_weapon_review(item, review, images=images)
    return record


def selected(bench, *asins):
    return {p['asin']:p['revision'] for p in bench.store.products() if not asins or p['asin'] in asins}


def confirm(bench, *asins):
    for kind, option in [('CATEGORY',100578), ('BRAND',7)]:
        bench.confirm(selected(bench,*asins), kind=kind, option_id=option, human_verified=True, note='Synthetic human '+kind)


def intake(bench, records=None, *, batch='A', prepare=True):
    records = records or [product(bench.scope.marketplace)]
    for r in records:
        bench.session.accept_facts(ProductFacts.from_dict(r['facts']))
    bench.ingest(records, batch_ref=batch)
    if prepare:
        confirm(bench, *(r['asin'] for r in records))
    return bench.store.products()


@pytest.fixture(params=['PH','SG'])
def bench(request, tmp_path):
    market = request.param
    return BetaWorkBench(BetaWorkStore.create(tmp_path/(market+'.sqlite3'), marketplace=market,
                         shop_id='synthetic-shop'), session_for(market))


def reopen(bench, *, current=False):
    session = session_for(bench.scope.marketplace) if current else PreparationSession(bench.scope.marketplace, bench.scope.shop_id)
    return BetaWorkBench(BetaWorkStore(bench.store.path, marketplace=bench.scope.marketplace,
                         shop_id=bench.scope.shop_id), session)


def test_restart_keeps_history_but_never_restores_preparation(bench):
    intake(bench)
    assert bench.prepared_pool()[0]['assessment']['valid']
    before = bench.store.history()
    resumed = reopen(bench)
    value = resumed.store.products()[0]
    assert value['state']=='RECHECK' and value['preparation_state']=='RECHECK'
    assert value['category'] and value['brand'] and value['notes']
    assert resumed.store.history()[:len(before)] == before
    assert resumed.prepared_pool()==()
    with pytest.raises(WorkStoreError): resumed.output(selected(resumed))
    # Even new catalog/Brand success does not rebind old decisions or old Facts.
    resumed = reopen(bench,current=True)
    with pytest.raises(ValueError): confirm(resumed)
    facts = ProductFacts.from_dict(value['facts'])
    resumed.session.accept_facts(facts)
    assert resumed.prepared_pool()==()
    confirm(resumed)
    assert len(resumed.prepared_pool())==1


def test_group_a_restart_b_and_same_asin_accumulate_without_history_loss(bench):
    intake(bench)
    history = bench.store.history()
    resumed = reopen(bench,current=True)
    intake(resumed,[product(bench.scope.marketplace,'B000000002',source_type='RESOLVER')],batch='Resolver B')
    assert resumed.store.products()[1]['batches'][0]['source_type']=='RESOLVER'
    assert {v['asin'] for v in resumed.store.products()}=={'B000000001','B000000002'}
    assert {v['asin'] for v in resumed.prepared_pool()}=={'B000000002'}
    first = resumed.store.products()[0]
    resumed.session.accept_facts(ProductFacts.from_dict(first['facts']))
    confirm(resumed,'B000000001')
    assert len(resumed.prepared_pool())==2
    output, txt, oid = resumed.output(selected(resumed))
    rows = list(csv.DictReader(StringIO(output.decode('utf-8-sig'))))
    assert len(rows)==2 and all(r['marketplace']==bench.scope.marketplace and r['listing_ready']=='FALSE' for r in rows)
    assert b'B000000001' in txt and b'B000000002' in txt and oid is None
    previous = resumed.store.products()[0]
    resumed.ingest([product(bench.scope.marketplace)],batch_ref='Same ASIN C')
    assert resumed.store.products()[0]['category']==previous['category']
    assert len(resumed.store.products()[0]['batches'])==2
    assert resumed.store.history()[:len(history)]==history


@pytest.mark.parametrize('kind',['CATEGORY','BRAND'])
def test_cancellation_is_durable_and_intake_does_not_reconfirm(bench,kind):
    intake(bench)
    bench.revoke(selected(bench),kind=kind,note='Wrong synthetic option')
    bench.ingest([product(bench.scope.marketplace)],batch_ref='B')
    value = bench.store.products()[0]
    assert value[kind.lower()] is None and value['revoked'][-1]['kind']==kind
    assert value['state']=='RECHECK'
    with pytest.raises(WorkStoreError): bench.output(selected(bench))
    assert 'REVOKE_'+kind in {e['action'] for e in reopen(bench).store.history()}


@pytest.mark.parametrize('target',['catalog','brand','inventory','fact'])
def test_p1_refresh_failure_never_uses_saved_valid(bench,target):
    intake(bench)
    if target=='catalog': bench.session.begin_catalog_refresh()
    elif target=='brand': bench.session.begin_brand_refresh(100578)
    elif target=='inventory': bench.session.begin_inventory_refresh()
    else: bench.session.begin_fact_refresh('B000000001')
    assert bench.prepared_pool()==()
    assert bench.store.products()[0]['state']=='RECHECK'
    with pytest.raises(WorkStoreError): bench.output(selected(bench),reserve_copy=True)
    assert not bench.store.operations()


def test_five_states_and_recheck_cannot_reset_confirmed_submission(bench):
    intake(bench)
    old = selected(bench)
    bench.output(old)
    assert bench.store.products()[0]['state']=='WAITING'
    with pytest.raises(WorkStoreError): bench.output(old)
    _,_,oid = bench.output(selected(bench),reserve_copy=True)
    bench.finish_copy(oid,selected(bench),outcome='SUCCESS',note='External tool accepted',human_confirmed=True)
    assert bench.store.products()[0]['state']=='AWAITING_LISTING'
    bench.session.begin_brand_refresh(100578)
    assert bench.refresh()[0]['state']=='RECHECK'
    assert bench.store.products()[0]['listing_progress']=='AWAITING_LISTING'
    obs = BrandObservation(100578, bench.scope.shop_id, ((7,'Synthetic Maker',False),),
                           'NEW_MOCK_BRAND',True,True,'OFFLINE_MOCK',marketplace=bench.scope.marketplace)
    bench.session.accept_brand(BrandEvidence(bench.scope,obs))
    confirm(bench)
    assert bench.store.products()[0]['state']=='AWAITING_LISTING'
    with pytest.raises(WorkStoreError): bench.output(selected(bench),reserve_copy=True)
    bench.listing_action(selected(bench),action='ERROR',note='Tool reported error',human_confirmed=True)
    assert bench.store.products()[0]['state']=='ERROR'
    bench.listing_action(selected(bench),action='RETURN',note='Failure verified before retry',human_confirmed=True)
    assert bench.store.products()[0]['state']=='WAITING'
    bench.session.accept_inventory(InventoryEvidence(bench.scope,
        (inventory('B000000001',marketplace=bench.scope.marketplace,name=bench.scope.marketplace+'_shop.csv'),),
        (bench.scope.shop_id,),'LATEST_CSV',True))
    assert bench.refresh()[0]['state']=='LISTED'
    with pytest.raises(WorkStoreError): bench.listing_action(selected(bench),action='RETURN',note='Retry',human_confirmed=True)


def test_unknown_reservation_survives_restart_and_requires_complete_explicit_resolution(bench):
    intake(bench,[product(bench.scope.marketplace),product(bench.scope.marketplace,'B000000002')])
    _,_,oid=bench.output(selected(bench),reserve_copy=True)
    bench.finish_copy(oid,selected(bench),outcome='UNKNOWN',note='Submission timed out',human_confirmed=True)
    resumed=reopen(bench,current=True)
    assert resumed.store.operations()[0]['state']=='UNKNOWN'
    with pytest.raises(WorkStoreError): resumed.output(selected(resumed),reserve_copy=True)
    with pytest.raises(WorkStoreError): resumed.finish_copy(oid,selected(resumed),outcome='CANCELLED',note='No proof',human_confirmed=False)
    with pytest.raises(WorkStoreError): resumed.finish_copy(oid,selected(resumed,'B000000001'),outcome='CANCELLED',note='Partial',human_confirmed=True)
    # Fresh evidence/classification cannot approve an old reservation.
    for value in resumed.store.products(): resumed.session.accept_facts(ProductFacts.from_dict(value['facts']))
    confirm(resumed)
    with pytest.raises(WorkStoreError): resumed.finish_copy(oid,selected(resumed),outcome='SUCCESS',note='Old operation',human_confirmed=True)
    resumed.finish_copy(oid,selected(resumed),outcome='CANCELLED',note='No items accepted; human verified both',human_confirmed=True)
    assert resumed.store.operations()[0]['state']=='CANCELLED'
    with pytest.raises(WorkStoreError): resumed.finish_copy(oid,selected(resumed),outcome='SUCCESS',note='Double close',human_confirmed=True)
    assert resumed.output(selected(resumed),reserve_copy=True)[2]!=oid


def test_same_session_unknown_can_be_resolved_successfully(bench):
    intake(bench)
    _,_,oid=bench.output(selected(bench),reserve_copy=True)
    bench.finish_copy(oid,selected(bench),outcome='UNKNOWN',note='Unsure',human_confirmed=True)
    bench.finish_copy(oid,selected(bench),outcome='SUCCESS',note='Human verified tool accepted',human_confirmed=True)
    assert bench.store.products()[0]['state']=='AWAITING_LISTING'
    assert {e['action'] for e in bench.store.history()} >= {'COPY_UNKNOWN','COPY_SUCCESS'}


def test_changed_product_and_old_revision_cannot_finish_success(bench):
    intake(bench)
    _,_,oid=bench.output(selected(bench),reserve_copy=True)
    old=selected(bench)
    bench.record_review(old,result='EVIDENCE_REVIEWED',note='New human memo',human_confirmed=True)
    for expected in [old,selected(bench)]:
        with pytest.raises(WorkStoreError): bench.finish_copy(oid,expected,outcome='SUCCESS',note='Old copy',human_confirmed=True)
    bench.finish_copy(oid,selected(bench),outcome='FAILED',note='Verified no submission',human_confirmed=True)
    assert bench.output(selected(bench),reserve_copy=True)[2]


def test_parallel_connections_allow_only_one_reservation(bench):
    intake(bench)
    other=BetaWorkBench(BetaWorkStore(bench.store.path,marketplace=bench.scope.marketplace,shop_id=bench.scope.shop_id),bench.session)
    expected=selected(bench)
    def attempt(b):
        try: return b.output(expected,reserve_copy=True)[2]
        except WorkStoreError: return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(attempt,[bench,other]))
    assert sum(r is not None for r in results)==1
    assert len(bench.store.operations())==1


def test_latest_all_shop_parent_or_sku_matches_even_without_preparation_and_never_unlists(bench):
    intake(bench,prepare=False)
    market=bench.scope.marketplace
    from modules.listing_inventory_parser import parse_listing_inventory_csv
    second=parse_listing_inventory_csv(b'Product ID,Parent SKU,Model ID,SKU,Stock\n1,B000000099,1,B000000001,1\n',
        filename=market+'_second.csv',marketplace=market,shop_label='second')
    first=inventory(name=market+'_first.csv',marketplace=market)
    bench.session.accept_inventory(InventoryEvidence(bench.scope,(first,second),(bench.scope.shop_id,'second'),'LATEST_ALL_SHOPS',True))
    value=bench.refresh()[0]
    assert value['state']=='LISTED' and value['listing_match']['matches'][0]['match_field']=='SKU'
    assert value['listing_match']['matches'][0]['shop_label']=='second'
    bench.session.accept_inventory(InventoryEvidence(bench.scope,(first,),(bench.scope.shop_id,),'NEXT_ABSENT',True))
    assert bench.refresh()[0]['state']=='LISTED'
    assert reopen(bench).store.products()[0]['state']=='LISTED'


def test_safety_notes_never_override_validator_stops_and_are_persistent(bench):
    intake(bench,[product(bench.scope.marketplace,title='Synthetic rechargeable battery')])
    for result in ['UNRESOLVED','EVIDENCE_REVIEWED']:
        bench.record_review(selected(bench),result=result,note='Synthetic safety review',human_confirmed=True)
        assert bench.prepared_pool()==()
        with pytest.raises(WorkStoreError): bench.output(selected(bench))
    assert bench.store.products()[0]['assessment']['safety_reasons']
    assert b'Synthetic safety review' in bench.queue_csv(queue='SAFETY')
    resumed = reopen(bench)
    assert resumed.store.products()[0]['notes'][-1]['kind']=='SAFETY'
    assert b'FACT_GUARDRAIL_REVIEW' in resumed.queue_csv(queue='SAFETY')


@pytest.mark.parametrize('title,root',[('Synthetic kitchen knife',3210981),('Synthetic contact lens',3210981),
    ('Synthetic wired headphone with charging case',3210981),('Synthetic wired headphone',None),
    ('Synthetic power bank',3210981)])
def test_body_battery_image_and_block_never_prepare(bench,title,root):
    intake(bench,[product(bench.scope.marketplace,title=title,root=root)])
    if bench.scope.marketplace=='PH' and title=='Synthetic contact lens':
        # SG-only body policy must not leak into PH.
        assert len(bench.prepared_pool())==1
        return
    assert bench.prepared_pool()==()
    with pytest.raises(WorkStoreError): bench.output(selected(bench))


def test_unknown_fact_provenance_and_saved_success_are_not_permissions(bench):
    r=product(bench.scope.marketplace)
    r['facts']['fields']['category_tree']['origin']='UNKNOWN'
    r['assessment']={'valid':True,'listing_ready':True}
    r['category']={'authority':'HUMAN','category_id':100578}
    r['brand']={'authority':'HUMAN','brand_id':7}
    intake(bench,[r])
    assert bench.prepared_pool()==()
    assert 'OWN_JP_FACT_REQUIRED:category_tree' in bench.store.products()[0]['assessment']['reasons']


def test_cross_market_shop_schema_and_legacy_open_never_mutate(tmp_path):
    path=tmp_path/'ph.sqlite3'
    store=BetaWorkStore.create(path,marketplace='PH',shop_id='ph-shop')
    before=path.read_bytes()
    for market,shop in [('SG','ph-shop'),('PH','other-shop')]:
        with pytest.raises(WorkStoreError): BetaWorkStore(path,marketplace=market,shop_id=shop)
    with pytest.raises(FileExistsError): BetaWorkStore.create(path,marketplace='SG',shop_id='sg-shop')
    with pytest.raises(WorkStoreError): SGWorkStore(path,shop_id='ph-shop')
    assert path.read_bytes()==before
    legacy=SGWorkStore.create(tmp_path/'legacy.sqlite3',shop_id='synthetic-shop')
    before=legacy.path.read_bytes()
    with pytest.raises(WorkStoreError): BetaWorkStore(legacy.path,marketplace='SG',shop_id='synthetic-shop')
    with pytest.raises(WorkStoreError): BetaWorkBench(legacy,session_for('SG'))
    assert legacy.path.read_bytes()==before
    with pytest.raises(WorkStoreError): BetaWorkBench(store,session_for('SG',shop='ph-shop'))


@pytest.mark.parametrize('damage',['missing','bytes','schema','product','event','delete_event','locks','operation','both_operation_and_locks'])
def test_database_missing_corruption_and_lost_reservation_stop_without_repair(bench,damage):
    intake(bench)
    bench.output(selected(bench),reserve_copy=True)
    path=bench.store.path
    if damage=='missing': path.unlink()
    elif damage=='bytes': path.write_bytes(b'corrupt synthetic database')
    else:
        with sqlite3.connect(path) as conn:
            statements={'schema':'ALTER TABLE events RENAME COLUMN checksum TO broken',
                'product':"UPDATE products SET checksum='bad'", 'event':"UPDATE events SET payload='{}'",
                'delete_event':'DELETE FROM events WHERE revision=1', 'locks':'DELETE FROM copy_locks',
                'operation':'DELETE FROM copy_operations', 'both_operation_and_locks':'DELETE FROM copy_operations'}
            conn.execute(statements[damage])
            if damage=='both_operation_and_locks': conn.execute('DELETE FROM copy_locks')
    before=path.read_bytes() if path.exists() else None
    with pytest.raises(WorkStoreError): bench.output(selected(bench),reserve_copy=True)
    with pytest.raises(WorkStoreError): BetaWorkStore(path,marketplace=bench.scope.marketplace,shop_id=bench.scope.shop_id)
    assert (path.read_bytes() if path.exists() else None)==before


@pytest.mark.parametrize('action',['ingest','confirm','revoke','review','output','reserve','finish'])
def test_partial_save_rolls_back_all_products_history_and_locks(bench,monkeypatch,action):
    records=[product(bench.scope.marketplace),product(bench.scope.marketplace,'B000000002')]
    intake(bench,records)
    if action=='finish': _,_,oid=bench.output(selected(bench),reserve_copy=True)
    before=(bench.store.products(),bench.store.history(),bench.store.operations())
    write=bench.store.write
    count=0
    def fail_second(*args,**kwargs):
        nonlocal count
        count+=1
        if count==2: raise sqlite3.OperationalError('Synthetic disk failure')
        return write(*args,**kwargs)
    monkeypatch.setattr(bench.store,'write',fail_second)
    with pytest.raises(WorkStoreError):
        if action=='ingest': bench.ingest(records,batch_ref='B')
        elif action=='confirm': confirm(bench)
        elif action=='revoke': bench.revoke(selected(bench),kind='CATEGORY',note='Wrong group')
        elif action=='review': bench.record_review(selected(bench),result='EXCLUDE',note='Stop group',human_confirmed=True)
        elif action=='finish': bench.finish_copy(oid,selected(bench),outcome='SUCCESS',note='Accepted',human_confirmed=True)
        else: bench.output(selected(bench),reserve_copy=action=='reserve')
    assert (bench.store.products(),bench.store.history(),bench.store.operations())==before


def test_commit_failure_never_delivers_bytes_or_keeps_partial_reservation(bench,monkeypatch):
    intake(bench)
    before=(bench.store.products(),bench.store.history())
    real_connect=sqlite3.connect
    class FailingCommit:
        def __init__(self,*args,**kwargs): object.__setattr__(self,'connection',real_connect(*args,**kwargs))
        def __getattr__(self,name): return getattr(self.connection,name)
        def __setattr__(self,name,value): setattr(self.connection,name,value)
        def commit(self):
            if self.connection.total_changes: raise sqlite3.OperationalError('Synthetic commit failure')
            self.connection.commit()
    monkeypatch.setattr('modules.beta_work_store.sqlite3.connect',FailingCommit)
    with pytest.raises(WorkStoreError): bench.output(selected(bench),reserve_copy=True)
    assert (bench.store.products(),bench.store.history())==before
    assert not bench.store.operations()


def test_p1_invalidation_during_formatter_rolls_back_output(bench,monkeypatch):
    import modules.preparation_validity as p1
    intake(bench)
    before=(bench.store.products(),bench.store.history())
    formatter=p1.format_preparation_groups
    def invalidate(*args,**kwargs):
        result=formatter(*args,**kwargs)
        bench.session.begin_inventory_refresh()
        return result
    monkeypatch.setattr(p1,'format_preparation_groups',invalidate)
    with pytest.raises(ValueError): bench.output(selected(bench),reserve_copy=True)
    assert (bench.store.products(),bench.store.history())==before
    assert not bench.store.operations()


def test_unchanged_refresh_has_no_spurious_revision_but_changed_fact_invalidates(bench):
    intake(bench)
    before=(bench.store.products(),bench.store.history())
    bench.refresh()
    assert (bench.store.products(),bench.store.history())==before
    changed=product(bench.scope.marketplace,title='Changed synthetic headphone')
    intake(bench,[changed],batch='B',prepare=False)
    assert bench.store.products()[0]['category'] is None
    assert bench.store.products()[0]['brand'] is None
    assert bench.prepared_pool()==()
    assert len(bench.store.products()[0]['batches'])==2


def test_unresolved_queue_and_exclusion_cannot_be_cleared_by_group_confirm(bench):
    intake(bench)
    bench.record_review(selected(bench),result='UNRESOLVED',note='Need evidence',human_confirmed=True)
    confirm(bench)
    assert bench.prepared_pool()==()
    bench.record_review(selected(bench),result='EVIDENCE_REVIEWED',note='Evidence inspected',human_confirmed=True)
    assert len(bench.prepared_pool())==1
    bench.record_review(selected(bench),result='EXCLUDE',note='Exclude item',human_confirmed=True)
    intake(bench,batch='B')
    assert bench.prepared_pool()==()
    assert reopen(bench).store.products()[0]['manual_exclude']


def test_old_selection_and_other_market_intake_are_atomic(bench):
    intake(bench)
    previous=selected(bench)
    bench.revoke(previous,kind='BRAND',note='Recheck Brand')
    with pytest.raises(WorkStoreError): bench.confirm(previous,kind='BRAND',option_id=7,human_verified=True,note='Old selection')
    before=bench.store.products()
    other='SG' if bench.scope.marketplace=='PH' else 'PH'
    with pytest.raises(WorkStoreError): bench.ingest([product(other)],batch_ref='Wrong market')
    assert bench.store.products()==before


def test_saved_body_exclusion_survives_changed_sources_and_restart(tmp_path):
    from modules.prelisting_sg_body_safety import record_body_confirmation, body_confirmation_bytes
    b=BetaWorkBench(BetaWorkStore.create(tmp_path/'body.sqlite3',marketplace='SG',shop_id='synthetic-shop'),session_for('SG'))
    record=product('SG',title='Synthetic kitchen knife')
    candidates,text,_,_ = _sources(record)
    body=record_body_confirmation(candidates,text,None,asin=record['asin'],family='KNIFE',
        outcome='BODY_PRESENT',evidence_reviewed=True,note='Synthetic confirmed body')
    record['source']['body']=body_confirmation_bytes(body).decode('utf-8')
    intake(b,[record])
    assert b.store.products()[0]['body_excluded']
    # Changed title loses the old body binding, but cannot clear the exclusion history.
    intake(b,[product('SG',title='Synthetic wired headphone')],batch='B')
    assert b.prepared_pool()==()
    assert 'SG_BODY_EXCLUDE_HISTORY' in b.store.products()[0]['assessment']['reasons']
    assert reopen(b).store.products()[0]['body_excluded']


def test_two_markets_and_shops_can_share_asin_without_shared_history(tmp_path):
    benches=[]
    for market,shop in [('PH','shop-a'),('SG','shop-a'),('SG','shop-b')]:
        b=BetaWorkBench(BetaWorkStore.create(tmp_path/(market+shop+'.sqlite3'),marketplace=market,shop_id=shop),
                        session_for(market,shop=shop))
        intake(b)
        benches.append(b)
    benches[0].revoke(selected(benches[0]),kind='CATEGORY',note='PH only cancellation')
    assert benches[0].prepared_pool()==()
    assert all(len(b.prepared_pool())==1 for b in benches[1:])
    assert all('REVOKE_CATEGORY' not in {e['action'] for e in b.store.history()} for b in benches[1:])


def test_replaced_valid_same_market_shop_database_is_rejected_by_open_handle(bench,tmp_path):
    intake(bench)
    replacement=BetaWorkStore.create(tmp_path/'replacement.sqlite3',marketplace=bench.scope.marketplace,shop_id=bench.scope.shop_id)
    bench.store.path.write_bytes(replacement.path.read_bytes())
    before=bench.store.path.read_bytes()
    with pytest.raises(WorkStoreError): bench.store.products()
    assert bench.store.path.read_bytes()==before


def test_reservation_remains_locked_if_evidence_changes_after_commit_before_return(bench,monkeypatch):
    intake(bench)
    real_connect=sqlite3.connect
    class InvalidateAfterCommit:
        def __init__(self,*args,**kwargs): object.__setattr__(self,'connection',real_connect(*args,**kwargs))
        def __getattr__(self,name): return getattr(self.connection,name)
        def __setattr__(self,name,value): setattr(self.connection,name,value)
        def commit(self):
            changed=self.connection.total_changes
            self.connection.commit()
            if changed: bench.session.begin_inventory_refresh()
    monkeypatch.setattr('modules.beta_work_store.sqlite3.connect',InvalidateAfterCommit)
    with pytest.raises(WorkStoreError): bench.output(selected(bench),reserve_copy=True)
    assert bench.store.operations()[0]['state']=='PENDING'
    assert reopen(bench).prepared_pool()==()
    with pytest.raises(WorkStoreError): bench.output(selected(bench),reserve_copy=True)


def test_sls_stop_cannot_be_cleared_by_category_brand_or_notes(bench):
    from modules.sls_category_assets import load_sg_context,load_ph_context
    ctx=(load_sg_context() if bench.scope.marketplace=='SG' else load_ph_context())
    cid=next(cid for cid,r in ctx.rules.items() if r.status=='NO')
    tree=replace(catalog(cid),marketplace=bench.scope.marketplace)
    bench.session.accept_classification(ClassificationEvidence(bench.scope,tree,'SLS_STOP_CATALOG',(),(),'SLS_RULES'))
    observation=BrandObservation(cid,bench.scope.shop_id,((7,'Synthetic Maker',False),),'SLS_BRAND',True,True,
        'OFFLINE_MOCK',marketplace=bench.scope.marketplace)
    bench.session.accept_brand(BrandEvidence(bench.scope,observation))
    intake(bench,prepare=False)
    bench.confirm(selected(bench),kind='CATEGORY',option_id=cid,human_verified=True,note='Classified only')
    bench.confirm(selected(bench),kind='BRAND',option_id=7,human_verified=True,note='Brand only')
    bench.record_review(selected(bench),result='EVIDENCE_REVIEWED',note='Does not release SLS',human_confirmed=True)
    assert 'SLS_STOP' in bench.store.products()[0]['assessment']['safety_reasons']
    assert bench.prepared_pool()==()


@pytest.mark.parametrize('action',['refresh','listing'])
def test_refresh_and_listing_group_failure_roll_back(bench,monkeypatch,action):
    intake(bench,[product(bench.scope.marketplace),product(bench.scope.marketplace,'B000000002')])
    _,_,oid=bench.output(selected(bench),reserve_copy=True)
    bench.finish_copy(oid,selected(bench),outcome='SUCCESS',note='Accepted both',human_confirmed=True)
    if action=='refresh': bench.session.begin_brand_refresh(100578)
    before=(bench.store.products(),bench.store.history(),bench.store.operations())
    write=bench.store.write
    calls=[]
    def fail_second(*args,**kwargs):
        calls.append(1)
        if len(calls)==2: raise sqlite3.OperationalError('Synthetic second write failure')
        return write(*args,**kwargs)
    monkeypatch.setattr(bench.store,'write',fail_second)
    with pytest.raises(WorkStoreError):
        if action=='refresh': bench.refresh()
        else: bench.listing_action(selected(bench),action='ERROR',note='Both failed',human_confirmed=True)
    assert (bench.store.products(),bench.store.history(),bench.store.operations())==before
