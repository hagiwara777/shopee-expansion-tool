"""Artificial failures and synthetic products; no claim about real ASIN safety."""
from dataclasses import asdict, replace
from io import StringIO
import csv
import json
import sqlite3

import pytest

from modules.category_mapper_sg import build_sg_category_catalog_csv, parse_sg_category_catalog
from modules.listing_inventory_parser import parse_listing_inventory_csv
from modules.prelisting_candidate_csv import expansion_rows_to_prelisting_candidates, rows_to_prelisting_candidate_csv
from modules.product_review import WeaponImageReviewSession
from modules.product_text_safety import extract_keepa_product_text_safety_fact, rows_to_product_text_safety_sidecar
from modules.sg_beta_facts import FieldFact, ProductFacts, facts_from_saved_keepa, offline_wired_audio_rule
from modules.sg_beta_workbench import (BrandAlias, BrandObservation, ValidationContext, SGWorkBench,
    auto_category, auto_brand, category_valid, brand_valid, capture_weapon_review, recommendation)
from modules.sg_beta_work_store import SGWorkStore, SGWorkError
from modules.sls_category_assets import load_sg_context


def catalog(cid=100578):
    names = load_sg_context().names[cid]
    rows = [{'category_id': cid if depth == len(names)-1 else 9000000+depth,
             'parent_category_id': None if depth == 0 else 9000000+depth-1,
             'category_name': name, 'is_leaf': depth == len(names)-1} for depth, name in enumerate(names)]
    return parse_sg_category_catalog(build_sg_category_catalog_csv(rows, marketplace='SG'), filename='sg.csv')


def inventory(*asins, shop='synthetic-shop', name='SG_shop.csv', marketplace='SG'):
    text = 'Product ID,Parent SKU,Model ID,SKU,Stock\n'
    text += ''.join(f'{i},{a},{i},{a},1\n' for i,a in enumerate(asins,1))
    return parse_listing_inventory_csv(text.encode('utf-8-sig'), filename=name,
                                        marketplace=marketplace, shop_label=shop)


def context():
    tree = catalog()
    rule = offline_wired_audio_rule(tree.get(100578).category_path)
    obs = BrandObservation(100578, 'synthetic-shop', ((7,'Synthetic Maker',False),(0,'No brand',True)),
                           'MOCK_COMPLETE_CATALOG_1', True, True, 'OFFLINE_MOCK')
    alias = BrandAlias('Synthetic Maker', 100578, 7, 'Synthetic Maker', 'SYNTHETIC_HUMAN_ALIAS', '1')
    return ValidationContext(tree, True, {100578:obs}, (rule,), (alias,), (inventory(),), 1, True, 'MOCK_INVENTORY_1')


def raw(asin='B000000001', title='Synthetic wired headphone', brand='Synthetic Maker'):
    return {'asin':asin, 'domainId':5, 'title':title, 'brand':brand, 'model':'Synthetic model',
            'categoryTree':[{'catId':1,'name':'Headphones'}],
            'description':['Synthetic passive wired audio product'], 'fetched_at':'2026-10-12T00:00:00+00:00'}


def fact(product=None):
    return facts_from_saved_keepa(product or raw(), source_format='keepa_response', evidence_ref='SYNTHETIC_RAW_RESPONSE')


def intake(bench, products, *, operation='MOCK_OPERATION_A', text_override=None, root=3210981):
    rows = expansion_rows_to_prelisting_candidates([{'seed_asin':'B000000000','candidate_asin':p['asin'],
        'product_title':p['title'], 'brand':p['brand'], 'category':'Headphones', 'source':'synthetic',
        'fetched_at':p['fetched_at']} for p in products])
    content = rows_to_prelisting_candidate_csv(rows)
    texts = [extract_keepa_product_text_safety_fact({**p,'description':text_override or p['description']},
                         candidate_asin=p['asin'],fetched_at=p['fetched_at']) for p in products]
    source = {'candidate':content.decode('utf-8'),'filename':'candidates.csv','text':'','ingredients':'','body':''}
    weapons = {}
    for p,t in zip(products,texts):
        item = recommendation({'asin':p['asin'],'source':source})
        images = {'candidate_asin':p['asin'],'provider':'keepa','capture_error':False,
                  'image_urls':['https://m.media-amazon.com/images/I/SYNTHETIC.jpg'], 'root_category_id':root}
        session = WeaponImageReviewSession('SG')
        session.supply(item,text=t,images=images)
        weapons[p['asin']] = capture_weapon_review(item,session,images=images)
    bench.ingest(candidate_content=content, filename='candidates.csv', facts={p['asin']:fact(p) for p in products},
        text_content=rows_to_product_text_safety_sidecar(content,rows,texts),
        weapon_records=weapons, operation_ref=operation)
    return bench.store.products()


@pytest.fixture
def bench(tmp_path, monkeypatch):
    # Any accidental network request is a test failure.
    def forbidden(*a,**k):
        raise AssertionError('External API forbidden')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('modules.shopee_catalog_client.urlopen', forbidden)
    return SGWorkBench(SGWorkStore.create(tmp_path/'work.sqlite3',shop_id='synthetic-shop'),context())


def selected(bench, *asins):
    return {p['asin']:p['revision'] for p in bench.store.products() if not asins or p['asin'] in asins}


def test_new_asin_auto_rule_is_not_user_confirmation(bench):
    result = intake(bench,[raw()])[0]
    assert result['category']['authority'] == result['brand']['authority'] == 'AUTO_RULE'
    assert result['assessment']['valid'] and result['state'] == 'WAITING'
    output, text, oid = bench.output(selected(bench))
    row = list(csv.DictReader(StringIO(output.decode('utf-8-sig'))))[0]
    assert row['verification_status'] == 'AUTO_RULE'
    assert row['listing_ready'] == 'FALSE' and 'OFFLINE' in row['output_scope']
    assert output.startswith(b'\xef\xbb\xbf') and text.startswith(b'\xef\xbb\xbf') and oid is None
    assert 'B000000001' in text.decode('utf-8-sig')
    assert bench.store.products()[0]['state'] == 'WAITING'


@pytest.mark.parametrize('change', [
    {'title':'Synthetic Bluetooth wired headphone'}, {'title':'Synthetic replacement wired ear pads'},
    {'domainId':1}, {'domainId':None}, {'category_origin':'SEED_FALLBACK'},
    {'category_origin':'UNKNOWN'}, {'categoryTree':[]}, {'fetched_at':''},
])
def test_counterexamples_abstain(change):
    assert auto_category(fact({**raw(),**change}),context()) is None


@pytest.mark.parametrize('field',['title','brand','category_tree'])
@pytest.mark.parametrize('origin',['SEED_FALLBACK','UNKNOWN','MISSING'])
def test_per_field_origins_never_promoted(field,origin):
    f = fact()
    f = ProductFacts(f.asin,{**f.fields,field:replace(f.fields[field],origin=origin)})
    c = auto_category(f,context())
    assert (c is None if field != 'brand' else auto_brand(f,c,context(),shop_id='synthetic-shop') is None)


def test_legacy_jp_default_is_not_proof():
    old = {**raw(),'domain':'JP','category_tree':[{'catId':1,'name':'Headphones'}]}
    old.pop('domainId')
    f = facts_from_saved_keepa(old,source_format='cache_snapshot',evidence_ref='LEGACY_CACHE')
    assert f.fields['title'].origin == 'UNKNOWN' and f.fields['title'].acquired_market == ''
    assert auto_category(f,context()) is None


@pytest.mark.parametrize('change', [
    {'complete':False}, {'current':False}, {'source':'SAVED_COMPARISON'}, {'shop_id':'other-shop'},
    {'brands':((0,'No brand',True),)},
    {'brands':((7,'Synthetic Maker',False),(8,'Synthetic Maker',False))},
])
def test_brand_incomplete_ambiguous_expired_and_old_stop(change):
    ctx = context()
    ctx = replace(ctx,brands={100578:replace(ctx.brands[100578],**change)})
    assert auto_brand(fact(),auto_category(fact(),ctx),ctx,shop_id='synthetic-shop') is None


def test_brand_missing_only_waits_for_brand(bench):
    p = intake(bench,[raw(brand='Unknown Synthetic Brand')])[0]
    assert p['assessment']['category_valid'] and not p['assessment']['brand_valid']
    assert p['brand'] is None
    assert p['assessment']['safety_reasons'] == []
    with pytest.raises(SGWorkError):
        bench.output(selected(bench))


def test_brand_conflicts_and_no_brand_auto_prohibited():
    ctx = context()
    ctx = replace(ctx,aliases=ctx.aliases+(replace(ctx.aliases[0],brand_id=8),))
    assert auto_brand(fact(),auto_category(fact(),ctx),ctx,shop_id='synthetic-shop') is None
    ctx = replace(context(),aliases=(replace(context().aliases[0],brand_id=0,brand_name='No brand'),))
    assert auto_brand(fact(),auto_category(fact(),ctx),ctx,shop_id='synthetic-shop') is None


@pytest.mark.parametrize('target',['fact','rule','catalog','brand','alias'])
def test_changes_invalidate_and_stop_downstream(bench,target):
    p = intake(bench,[raw()])[0]
    ctx = bench.context
    if target == 'fact':
        with bench.store.transaction() as c:
            p['facts']['fields']['model']['value']='Changed model'
            bench.store.write(c,p,action='FACT_REFRESH',expected_revision=p['revision'])
    elif target == 'rule':
        bench.context=replace(ctx,rules=(replace(ctx.rules[0],version='2'),))
    elif target == 'catalog':
        bench.context=replace(ctx,catalog=replace(ctx.catalog,catalog_version='changed'))
    elif target == 'brand':
        bench.context=replace(ctx,brands={100578:replace(ctx.brands[100578],observation_ref='changed')})
    else:
        bench.context=replace(ctx,aliases=(replace(ctx.aliases[0],version='2'),))
    assert not bench.refresh()[0]['assessment']['valid']
    with pytest.raises(SGWorkError):
        bench.output(selected(bench))


def test_review_persistence_restart_and_human_note_cannot_clear_battery(bench):
    p=intake(bench,[raw()],text_override=['Contains a rechargeable battery'])[0]
    assert p['assessment']['safety_reasons']
    bench.record_review(selected(bench),result='EVIDENCE_REVIEWED',note='Synthetic review findings')
    reopened=SGWorkBench(SGWorkStore(bench.store.path,shop_id='synthetic-shop'),bench.context)
    assert reopened.refresh()[0]['notes'][-1]['note']=='Synthetic review findings'
    assert reopened.refresh()[0]['assessment']['safety_reasons']
    assert b'GUARDRAIL_REVIEW' in reopened.queue_csv()
    with pytest.raises(SGWorkError):
        reopened.output(selected(reopened))


def test_group_subset_human_category_does_not_adopt_brand_and_mixed_csv(bench):
    intake(bench,[raw(),raw('B000000002')])
    bench.confirm(selected(bench,'B000000002'),kind='CATEGORY',option_id=100578,human_verified=True,note='Synthetic category review')
    p=bench.store.products()[1]
    assert p['category']['authority']=='HUMAN' and p['brand'] is None
    bench.confirm(selected(bench,'B000000002'),kind='BRAND',option_id=7,human_verified=True,note='Synthetic Brand review')
    rows=list(csv.DictReader(StringIO(bench.output(selected(bench))[0].decode('utf-8-sig'))))
    assert [r['verification_status'] for r in rows]==['AUTO_RULE','HUMAN']
    assert all(r['asin_count']=='2' for r in rows)


def test_human_no_brand_explicit_and_category_first(bench):
    intake(bench,[raw(brand='Unknown Synthetic Brand')])
    bench.confirm(selected(bench),kind='BRAND',option_id=0,human_verified=True,note='Checked product No Brand explicitly')
    assert bench.store.products()[0]['brand']['authority']=='HUMAN'
    assert bench.store.products()[0]['brand']['is_no_brand'] is True
    bench.revoke(selected(bench),kind='CATEGORY',note='Correct classification')
    with pytest.raises(SGWorkError):
        bench.confirm(selected(bench),kind='BRAND',option_id=0,human_verified=True,note='Checked')


def test_pool_cross_batch_operation_and_restart(bench):
    intake(bench,[raw()],operation='OPERATION_A')
    intake(bench,[raw('B000000002')],operation='OPERATION_B')
    reopened=SGWorkBench(SGWorkStore(bench.store.path,shop_id='synthetic-shop'),bench.context)
    assert len(reopened.refresh())==2
    assert {p['operation_ref'] for p in reopened.store.products()}=={'OPERATION_A','OPERATION_B'}
    assert bench.store.path == reopened.store.path
    assert len(reopened.output(selected(reopened))[0].decode('utf-8-sig').splitlines())==3


def test_copy_unknown_restart_double_operation_cancel_and_five_states(bench):
    intake(bench,[raw()])
    _,_,oid=bench.output(selected(bench),reserve_copy=True)
    with pytest.raises(SGWorkError):
        bench.output(selected(bench),reserve_copy=True)
    bench.finish_copy(oid,outcome='UNKNOWN',note='Clipboard result unknown',human_confirmed=True)
    reopened=SGWorkBench(SGWorkStore(bench.store.path,shop_id='synthetic-shop'),bench.context)
    assert reopened.store.operations()[0]['state']=='UNKNOWN'
    with pytest.raises(SGWorkError):
        reopened.output(selected(reopened))
    reopened.finish_copy(oid,outcome='CANCELLED',note='Explicitly cancel old operation',human_confirmed=True)
    _,_,oid=reopened.output(selected(reopened),reserve_copy=True)
    reopened.finish_copy(oid,outcome='SUCCESS',note='Copied by human',human_confirmed=True)
    assert reopened.store.products()[0]['state']=='AWAITING_LISTING'
    assert reopened.refresh()[0]['state']=='AWAITING_LISTING'  # CSV absence cannot undo copy.
    reopened.listing_action(selected(reopened),action='ERROR',note='External tool failed',human_confirmed=True)
    assert reopened.store.products()[0]['state']=='ERROR'
    reopened.listing_action(selected(reopened),action='RETURN',note='Retry accepted',human_confirmed=True)
    assert reopened.store.products()[0]['state']=='WAITING'
    reopened.context=replace(reopened.context,inventories=(inventory('B000000001'),))
    assert reopened.refresh()[0]['state']=='LISTED'
    reopened.context=replace(reopened.context,inventories=(inventory(),))
    assert reopened.refresh()[0]['state']=='LISTED'
    assert {'COPY_INTENT','COPY_UNKNOWN','COPY_CANCELLED','COPY_SUCCESS','LISTING_ERROR','LISTING_RETURN'} <= {
        e['action'] for e in reopened.store.history()}


def test_copy_success_after_revocation_stops_and_cannot_repeat(bench):
    intake(bench,[raw()])
    _,_,oid=bench.output(selected(bench),reserve_copy=True)
    bench.revoke(selected(bench),kind='CATEGORY',note='Wrong rule')
    with pytest.raises(SGWorkError):
        bench.finish_copy(oid,outcome='SUCCESS',note='Copied',human_confirmed=True)
    assert bench.store.products()[0]['state']=='RECHECK'
    bench.finish_copy(oid,outcome='CANCELLED',note='Explicit recovery',human_confirmed=True)
    intake(bench,[raw()],operation='B')
    assert bench.store.products()[0]['category'] is None


@pytest.mark.parametrize('action',['confirm','export','copy','finish'])
def test_atomic_db_failure_never_returns_success_or_partial_update(bench,monkeypatch,action):
    intake(bench,[raw(),raw('B000000002')])
    expected=selected(bench)
    if action=='finish':
        _,_,oid=bench.output(expected,reserve_copy=True)
        expected=selected(bench)
    before=bench.store.products()
    write=bench.store.write
    calls=[]
    def fail_second(*a,**k):
        calls.append(1)
        if len(calls)==2:
            raise sqlite3.OperationalError('Synthetic disk failure')
        return write(*a,**k)
    monkeypatch.setattr(bench.store,'write',fail_second)
    with pytest.raises(SGWorkError):
        if action=='confirm':
            bench.confirm(expected,kind='CATEGORY',option_id=100578,human_verified=True,note='Checked')
        elif action=='finish':
            bench.finish_copy(oid,outcome='SUCCESS',note='Copied',human_confirmed=True)
        else:
            bench.output(expected,reserve_copy=action=='copy')
    assert bench.store.products()==before
    if action=='copy':
        assert bench.store.operations()==()


@pytest.mark.parametrize('change',[{'inventories':()}, {'inventory_confirmed_current':False},
                                  {'catalog_current':False}])
def test_current_context_missing_stops(bench,change):
    intake(bench,[raw()])
    bench.context=replace(bench.context,**change)
    with pytest.raises(SGWorkError):
        bench.output(selected(bench))


def test_existing_parent_and_sku_all_shops_and_market_isolation(bench):
    intake(bench,[raw()])
    csv_bytes=b'Product ID,Parent SKU,Model ID,SKU,Stock\n1,B000000099,1,B000000001,1\n'
    second=parse_listing_inventory_csv(csv_bytes,filename='SG_second.csv',marketplace='SG',shop_label='second')
    bench.context=replace(bench.context,inventories=(inventory(),second),expected_shop_count=2)
    assert bench.refresh()[0]['state']=='LISTED'
    with pytest.raises(SGWorkError):
        SGWorkStore(bench.store.path,shop_id='PH-other')
    with pytest.raises(SGWorkError):
        bench.output(selected(bench))


def test_unresolved_other_product_does_not_block_ready_subset(bench):
    intake(bench,[raw(),raw('B000000002',brand='Unknown Synthetic Brand')])
    assert b'B000000001' in bench.output(selected(bench,'B000000001'))[0]
    with pytest.raises(SGWorkError):
        bench.output(selected(bench))


def test_new_db_only_no_silent_creation_repair_or_old_db_migration(tmp_path):
    old=tmp_path/'old.sqlite3'
    old.write_bytes(b'Synthetic legacy database')
    with pytest.raises(FileExistsError):
        SGWorkStore.create(old,shop_id='synthetic-shop')
    assert old.read_bytes()==b'Synthetic legacy database'
    with pytest.raises(SGWorkError):
        SGWorkStore(tmp_path/'missing.sqlite3',shop_id='synthetic-shop')
    assert not (tmp_path/'missing.sqlite3').exists()


def test_safety_body_weapon_and_sls_stops(bench):
    for title,root in [('Synthetic kitchen knife wired headphone',3210981),
                       ('Synthetic contact lens wired headphone',3210981),
                       ('Synthetic wired headphone',None),
                       ('Synthetic wired headphone with charging case',3210981)]:
        intake(bench,[raw(title=title)],root=root)
        assert bench.refresh()[0]['assessment']['safety_reasons']
        with pytest.raises(SGWorkError):
            bench.output(selected(bench))


def test_stale_revision_group_change_and_json_damage_stop(bench):
    intake(bench,[raw()])
    old=selected(bench)
    bench.record_review(old,result='UNRESOLVED',note='Need more evidence')
    with pytest.raises(SGWorkError):
        bench.output(old)
    with sqlite3.connect(bench.store.path) as conn:
        conn.execute("UPDATE products SET checksum='bad'")
    with pytest.raises(SGWorkError):
        bench.store.products()


def test_refresh_is_stable_and_does_not_create_spurious_history(bench):
    intake(bench,[raw()])
    before=bench.store.products()
    assert bench.refresh()==before
    assert bench.refresh()==before


def test_ui_subset_and_confirmation_widget_invalidates(bench):
    from streamlit.testing.v1 import AppTest
    intake(bench,[raw(),raw('B000000002')])
    def script():
        import streamlit as st
        from modules.sg_beta_workbench_ui import render_work_queues
        render_work_queues(st.session_state['bench'])
    app=AppTest.from_function(script)
    app.session_state['bench']=bench
    app.run(timeout=20)
    assert not app.exception
    app.multiselect(key='sg_work_selected').set_value(['B000000001']).run()
    app.text_area(key='sg_work_note').set_value('Synthetic group confirmation').run()
    app.checkbox(key='sg_work_human').check().run()
    assert not app.button(key='sg_work_confirm_category').disabled
    app.multiselect(key='sg_work_selected').set_value(['B000000002']).run()
    assert not app.checkbox(key='sg_work_human').value
    assert app.button(key='sg_work_confirm_category').disabled
    app.checkbox(key='sg_work_human').check().run()
    app.button(key='sg_work_confirm_category').click().run()
    assert not app.exception
    assert bench.store.products()[0]['category']['authority']=='AUTO_RULE'
    assert bench.store.products()[1]['category']['authority']=='HUMAN'


def test_pending_copy_lock_loss_and_state_corruption_stop(bench):
    intake(bench,[raw()])
    bench.output(selected(bench),reserve_copy=True)
    with sqlite3.connect(bench.store.path) as conn:
        conn.execute('DELETE FROM copy_locks')
    with pytest.raises(SGWorkError):
        bench.store.products()
    with pytest.raises(SGWorkError):
        bench.output({'B000000001':2})


@pytest.mark.parametrize('captured',['UNKNOWN_NOT_RECORDED','2026-10-12','2026-10-12T00:00:00'])
def test_unproven_capture_time_is_not_auto_fact(captured):
    assert auto_category(fact({**raw(),'fetched_at':captured}),context()) is None


def test_sls_exclusion_cannot_be_overridden_by_auto_classification(bench):
    sls=load_sg_context()
    cid=next(cid for cid,r in sls.rules.items() if r.status=='NO')
    cat=catalog(cid)
    ctx=bench.context
    rule=replace(ctx.rules[0],category_id=cid,category_path=cat.get(cid).category_path)
    obs=replace(ctx.brands[100578],category_id=cid)
    alias=replace(ctx.aliases[0],category_id=cid)
    bench.context=replace(ctx,catalog=cat,brands={cid:obs},rules=(rule,),aliases=(alias,))
    result=intake(bench,[raw()])[0]
    assert result['assessment']['category_valid'] and result['assessment']['brand_valid']
    assert 'SLS_STOP' in result['assessment']['safety_reasons']
    with pytest.raises(SGWorkError):
        bench.output(selected(bench))


def test_manual_exclude_and_brand_revocation_survive_new_batches(bench):
    intake(bench,[raw()])
    bench.record_review(selected(bench),result='EXCLUDE',note='Synthetic exclusion decision')
    intake(bench,[raw()],operation='NEW_OPERATION')
    assert 'HUMAN_EXCLUDE' in bench.refresh()[0]['assessment']['safety_reasons']
    bench.revoke(selected(bench),kind='BRAND',note='Alias correction')
    intake(bench,[raw()],operation='ANOTHER_OPERATION')
    assert bench.store.products()[0]['brand'] is None


def test_failed_copy_and_double_finish_are_explicit(bench):
    intake(bench,[raw()])
    _,_,oid=bench.output(selected(bench),reserve_copy=True)
    bench.finish_copy(oid,outcome='FAILED',note='Clipboard failed',human_confirmed=True)
    assert bench.store.products()[0]['state']=='WAITING'
    with pytest.raises(SGWorkError):
        bench.finish_copy(oid,outcome='SUCCESS',note='Later result',human_confirmed=True)
    assert bench.output(selected(bench),reserve_copy=True)[2] != oid


def test_two_connections_cannot_reserve_the_same_asin(bench):
    intake(bench,[raw()])
    other=SGWorkBench(SGWorkStore(bench.store.path,shop_id='synthetic-shop'),bench.context)
    old=selected(other)
    bench.output(selected(bench),reserve_copy=True)
    with pytest.raises(SGWorkError):
        other.output(old,reserve_copy=True)
    with pytest.raises(SGWorkError):
        other.output(selected(other),reserve_copy=True)


def test_confirming_classification_cannot_clear_guardrail_block(bench):
    intake(bench,[raw(brand='加美乃素')])
    bench.confirm(selected(bench),kind='CATEGORY',option_id=100578,human_verified=True,note='Classification only')
    bench.confirm(selected(bench),kind='BRAND',option_id=0,human_verified=True,note='Explicit option, not Safety permission')
    assert bench.refresh()[0]['assessment']['safety_reasons']
    with pytest.raises(SGWorkError):
        bench.output(selected(bench))


def test_versioned_demo_contract_uses_mock_brand_and_stops_exceptions(tmp_path):
    from pathlib import Path
    from modules.sg_beta_workbench_ui import context_from_bundle
    p=Path(__file__).parent/'fixtures/browser_e2e/sg_initial_beta'
    ctx=context_from_bundle((p/'context.json').read_bytes(),inventories=(inventory(),),
        shop_id='synthetic-shop',inventory_current=True,inventory_ref='SYNTHETIC_DEMO')
    b=SGWorkBench(SGWorkStore.create(tmp_path/'demo.sqlite3',shop_id='synthetic-shop'),ctx)
    b.ingest(candidate_content=(p/'candidate.csv').read_bytes(),filename='candidate.csv',
        facts={f['asin']:ProductFacts.from_dict(f) for f in json.loads((p/'facts.json').read_text(encoding='utf-8'))},
        text_content=(p/'product_text.csv').read_bytes(),weapon_records=json.loads((p/'weapon.json').read_text(encoding='utf-8')))
    assert [r['assessment']['valid'] for r in b.refresh()]==[True,False,False,False]
    assert b.output(selected(b,'B000000001'))[0].startswith(b'\xef\xbb\xbf')


def test_saved_cache_audit_is_readonly_and_never_invents_provenance(tmp_path):
    from pathlib import Path
    from hashlib import sha256
    from scripts.sg_initial_beta_saved_audit import audit
    p=tmp_path/'saved.sqlite3'
    old={**raw(),'domain':'JP','category_tree':[{'catId':1,'name':'Headphones'}]}
    old.pop('domainId')
    with sqlite3.connect(p) as conn:
        conn.execute('CREATE TABLE products(asin TEXT,response_json TEXT)')
        conn.execute('INSERT INTO products VALUES (?,?)',(old['asin'],json.dumps(old)))
    before=sha256(p.read_bytes()).hexdigest()
    result=audit(p,Path(__file__).parent/'fixtures/browser_e2e/sg_initial_beta/context.json',('B000000001',))
    assert result['products'][0]['reason']=='SOURCE_PROVENANCE_UNPROVEN'
    assert result['products'][0]['auto_category'] is False
    assert result['products'][0]['auto_brand'] is False
    assert sha256(p.read_bytes()).hexdigest()==before


def test_listing_error_history_remains_recordable_after_preparation_expires(bench):
    intake(bench,[raw()])
    assert bench.store.products()[0]['amazon_url']=='https://www.amazon.co.jp/dp/B000000001'
    _,_,oid=bench.output(selected(bench),reserve_copy=True)
    bench.finish_copy(oid,outcome='SUCCESS',note='Explicit copy result',human_confirmed=True)
    bench.context=replace(bench.context,aliases=(replace(bench.context.aliases[0],version='2'),))
    assert bench.refresh()[0]['state']=='RECHECK'
    bench.listing_action(selected(bench),action='ERROR',human_confirmed=True,note='Later external tool failure')
    assert bench.store.products()[0]['state']=='ERROR'
    with pytest.raises(SGWorkError):
        bench.listing_action(selected(bench),action='RETURN',human_confirmed=True,note='Retry')
    assert b'https://www.amazon.co.jp/dp/B000000001' in bench.queue_csv(queue='BRAND')


def test_explicit_offline_entry_never_opens_legacy_ph_or_sg_runtime(tmp_path,monkeypatch):
    import app_beta
    from streamlit.testing.v1 import AppTest
    def forbidden(*a,**k):
        raise AssertionError('Legacy runtime must not be opened by offline entry')
    monkeypatch.setattr(app_beta,'render_application',forbidden)
    path=tmp_path/'new-work.sqlite3'
    script='from app_beta import render_beta\n' + f"render_beta(sg_work_db={str(path)!r}, sg_work_shop='synthetic-shop')"
    app=AppTest.from_string(script)
    app.run(timeout=20)
    assert not app.exception and not path.exists()
    app.selectbox(key='beta_marketplace').select('SG').run()
    assert not app.exception and not path.exists()
    app.button(key='sg_work_create').click().run()
    assert not app.exception and path.exists()


@pytest.mark.parametrize('defect', ['missing_images', 'capture_error', 'missing_digests', 'image_error'])
def test_saved_completed_weapon_inspection_cannot_hide_missing_images(bench, defect):
    from modules.weapon_image_inspection import WeaponImageInspection
    from modules.product_text_safety import product_text_safety_fact_from_transport
    intake(bench, [raw()], root=None)
    value = bench.store.products()[0]
    saved = value['weapon']
    if defect == 'missing_images':
        saved['images']['image_urls'] = []
    elif defect == 'capture_error':
        saved['images']['capture_error'] = True
    item = recommendation(value)
    session = WeaponImageReviewSession('SG')
    session.supply(item, text=product_text_safety_fact_from_transport(
        saved['text'], candidate_asin=value['asin'], provider='keepa'), images=saved['images'])
    urls = saved['images']['image_urls']
    digests = [(url, 'LOADED', 'a' * 64, 'image/jpeg') for url in urls]
    if defect == 'missing_digests':
        digests = []
    elif defect == 'image_error':
        digests = [(url, 'ERROR', '', '') for url in urls]
    saved['inspection'] = asdict(WeaponImageInspection('synthetic-inspection', 'COMPLETED',
        'NO_SIGNAL', 'Synthetic saved result', session.current(item).binding, tuple(digests)))
    with bench.store.transaction() as conn:
        bench.store.write(conn, value, action='SAVED_INSPECTION_IMPORT', expected_revision=value['revision'])
    assert bench.refresh()[0]['assessment']['safety_reasons']
    with pytest.raises(SGWorkError):
        bench.output(selected(bench))


@pytest.mark.parametrize('input_name', ['cache', 'context'])
def test_saved_audit_output_cannot_overwrite_inputs(tmp_path, monkeypatch, input_name):
    from scripts import sg_initial_beta_saved_audit as script
    cache, ctx = tmp_path / 'saved.sqlite3', tmp_path / 'context.json'
    cache.write_bytes(b'Synthetic saved cache')
    ctx.write_bytes(b'Synthetic context')
    before = (cache.read_bytes(), ctx.read_bytes())
    def forbidden(*args, **kwargs):
        raise AssertionError('Input collision must stop before audit')
    monkeypatch.setattr(script, 'audit', forbidden)
    monkeypatch.setattr('sys.argv', ['audit', '--cache-db', str(cache), '--context-file', str(ctx),
        '--output', str(cache if input_name == 'cache' else ctx), '--asin', 'B000000001'])
    with pytest.raises(ValueError, match='Output must be separate'):
        script.main()
    assert (cache.read_bytes(), ctx.read_bytes()) == before


@pytest.mark.parametrize('human_review', [False, True])
def test_valid_saved_weapon_inspection_retains_targeted_human_contract(bench, human_review):
    from modules.weapon_image_inspection import WeaponImageInspection
    from modules.product_text_safety import product_text_safety_fact_from_transport
    intake(bench, [raw()], root=None)
    value = bench.store.products()[0]
    saved = value['weapon']
    item = recommendation(value)
    session = WeaponImageReviewSession('SG')
    session.supply(item, text=product_text_safety_fact_from_transport(
        saved['text'], candidate_asin=value['asin'], provider='keepa'), images=saved['images'])
    evidence = session.current(item)
    inspection = WeaponImageInspection('synthetic-valid-inspection', 'COMPLETED',
        'REVIEW' if human_review else 'NO_SIGNAL', 'Synthetic valid inspection', evidence.binding,
        tuple((url, 'LOADED', 'a' * 64, 'image/jpeg') for url in evidence.image_urls))
    session.finish_image_inspection(item, evidence_binding=evidence.binding, inspection=inspection)
    if human_review:
        session.record_weapon_decision(item, decision='ALLOW_PREPARATION', reviewed_images=True,
                                       note='Synthetic targeted weapon review')
    value['weapon'] = capture_weapon_review(item, session, images=saved['images'])
    with bench.store.transaction() as conn:
        bench.store.write(conn, value, action='VALID_INSPECTION_IMPORT', expected_revision=value['revision'])
    assert bench.refresh()[0]['assessment']['valid']
    bench.listing_action(selected(bench), action='RETURN', human_confirmed=True,
                         note='Current image evidence rechecked before returning')
    assert b'B000000001' in bench.output(selected(bench))[0]


def test_commit_failure_cannot_deliver_copy_bytes_or_retain_reservation(bench, monkeypatch):
    intake(bench, [raw()])
    before = bench.store.products()
    real_connect = sqlite3.connect
    class FailingCommit:
        def __init__(self, *args, **kwargs):
            object.__setattr__(self, 'connection', real_connect(*args, **kwargs))
        def __getattr__(self, name):
            return getattr(self.connection, name)
        def __setattr__(self, name, value):
            setattr(self.connection, name, value)
        def commit(self):
            if self.connection.total_changes:
                raise sqlite3.OperationalError('Synthetic commit failure')
            self.connection.commit()
    monkeypatch.setattr('modules.sg_beta_work_store.sqlite3.connect', FailingCommit)
    with pytest.raises(SGWorkError):
        bench.output(selected(bench), reserve_copy=True)
    assert bench.store.products() == before
    assert bench.store.operations() == ()
