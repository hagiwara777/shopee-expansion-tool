"""P3 common operation contract with synthetic PH/SG inputs; network forbidden."""
from dataclasses import asdict, replace
from contextlib import contextmanager
import copy

import pytest

from modules.beta_work_store import BetaWorkStore, WorkStoreError
from modules.beta_workbench import BetaWorkBench
from modules.classification_workflow import ClassificationWorkflow, records_from_producer
from modules.preparation_validity import PreparationSession, PreparationError, AutoRuleApproval
from modules.sg_beta_facts import ProductFacts, offline_wired_audio_rule, digest
from modules.sg_beta_workbench import BrandAlias, BrandObservation
from test_beta_workbench_p2 import product, session_for, selected


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError('P3 verification is offline only')
    monkeypatch.setattr('requests.sessions.Session.request', forbidden)
    monkeypatch.setattr('modules.shopee_catalog_client.urlopen', forbidden)


def definitions(wf, *, operational=False):
    ctx = wf.session.classification_context()
    scope = 'OPERATION_APPROVED' if operational else 'OFFLINE_ONLY'
    rule = replace(offline_wired_audio_rule(ctx.catalog.get(100578).category_path),
                   marketplace=wf.session.scope.marketplace, scope=scope)
    alias = BrandAlias('Synthetic Maker', 100578, 7, 'Synthetic Maker',
        'SYNTHETIC_ALIAS_REVIEW', '1', marketplace=wf.session.scope.marketplace, scope=scope)
    return ctx, rule, alias


def install_definitions(wf, *, rules=None, aliases=None, operational=False):
    ctx, rule, alias = definitions(wf, operational=operational)
    wf.supply_catalog(ctx.catalog, reference='SYNTHETIC_CURRENT', revision='SYNTHETIC_RULE_ALIAS_1',
        rules=(rule,) if rules is None else rules, aliases=(alias,) if aliases is None else aliases)
    wf.supply_mock_brand(BrandObservation(100578, wf.session.scope.shop_id,
        ((7, 'Synthetic Maker', False), (0, 'No brand', True)), 'MOCK_BRAND_P3', True,
        True, 'OFFLINE_MOCK', marketplace=wf.session.scope.marketplace))


@pytest.fixture(params=['PH', 'SG'])
def wf(request, tmp_path):
    market = request.param
    session = session_for(market)
    workflow = ClassificationWorkflow(BetaWorkBench(BetaWorkStore.create(tmp_path/(market+'.sqlite3'),
        marketplace=market, shop_id=session.scope.shop_id), session))
    install_definitions(workflow)
    return workflow


def ingest(wf, records=None, *, batch='A'):
    records = records or [product(wf.session.scope.marketplace)]
    return wf.ingest(records, scope=wf.session.scope, batch_ref=batch)


def human(wf, asins, kind, option):
    wf.confirm(wf.select(asins), kind=kind, option_id=option, reviewer='Synthetic reviewer',
               note='Synthetic product-specific evidence', human_verified=True)


def automatic(wf, asins, kind):
    wf.apply_auto(wf.select(asins), kind=kind, reviewer='Synthetic operator', note='Explicit limited-rule action')


def test_three_of_ten_independent_human_confirmations_and_actor(wf):
    records = [product(wf.session.scope.marketplace, f'B{i:09d}') for i in range(1,11)]
    ingest(wf, records)
    subset = [r['asin'] for r in records[:3]]
    assert wf.candidates(subset[0], kind='CATEGORY', query='head')['options']
    assert not wf.candidates(subset[0], kind='BRAND')['options']
    human(wf, subset, 'CATEGORY', 100578)
    assert not wf.bench.prepared_pool()
    assert all(not r.get('brand') for r in wf.bench.store.products())
    assert wf.candidates(subset[0], kind='BRAND')['options']
    human(wf, subset, 'BRAND', 7)
    assert {r['asin'] for r in wf.bench.prepared_pool()} == set(subset)
    for r in wf.bench.store.products():
        if r['asin'] in subset:
            assert r['category']['authority'] == r['brand']['authority'] == 'HUMAN'
            assert r['notes'][-1]['reviewer'] == 'Synthetic reviewer'
            assert r['notes'][-1]['rule_alias_revision'] == 'SYNTHETIC_RULE_ALIAS_1'
            assert r['notes'][-1]['catalog_version'] == wf.session.classification_context().catalog.catalog_version
            assert r['category']['basis'] and r['brand']['brand_catalog_binding']
        else:
            assert r['category'] is None and r['brand'] is None and r['state'] == 'RECHECK'


def test_limited_auto_mixed_authority_and_default_operational_stop(wf):
    ingest(wf)
    automatic(wf, ['B000000001'], 'CATEGORY')
    assert wf.bench.store.products()[0]['brand'] is None
    human(wf, ['B000000001'], 'BRAND', 7)
    r = wf.bench.prepared_pool()[0]
    assert r['category']['authority'] == 'AUTO_RULE' and r['brand']['authority'] == 'HUMAN'
    files = wf.bench.output(selected(wf.bench))
    assert b'MIXED' in files[0] and b'FALSE' in files[0]
    with pytest.raises(PreparationError, match='AUTO_RULE_OPERATION_NOT_APPROVED'):
        wf.session.require_operational(r)
    automatic(wf, ['B000000001'], 'BRAND')
    assert wf.bench.prepared_pool()[0]['brand']['authority'] == 'AUTO_RULE'


@pytest.mark.parametrize('case', ['wireless', 'unknown-jp', 'seed', 'rule-conflict', 'alias-conflict', 'no-brand', 'duplicate-name'])
def test_ambiguous_or_unproven_automatic_decisions_hold(wf, case):
    r = product(wf.session.scope.marketplace)
    ctx, rule, alias = definitions(wf)
    if case == 'wireless':
        r = product(wf.session.scope.marketplace, title='Synthetic wireless headphone')
    elif case in {'unknown-jp', 'seed'}:
        for name in ('title', 'category_tree'):
            r['facts']['fields'][name]['acquired_market'] = '' if case == 'unknown-jp' else 'JP'
            r['facts']['fields'][name]['origin'] = 'UNKNOWN' if case == 'unknown-jp' else 'SEED_FALLBACK'
    elif case == 'rule-conflict':
        install_definitions(wf, rules=(rule, replace(rule, rule_id='CONFLICT')))
    elif case == 'alias-conflict':
        install_definitions(wf, aliases=(alias, replace(alias, version='2')))
    elif case == 'no-brand':
        install_definitions(wf, aliases=(replace(alias, brand_id=0, brand_name='No brand'),))
    elif case == 'duplicate-name':
        wf.supply_mock_brand(BrandObservation(100578, wf.session.scope.shop_id,
            ((7,'Synthetic Maker',False),(8,'Synthetic Maker',False)), 'AMBIGUOUS', True, True,
            'OFFLINE_MOCK', marketplace=wf.session.scope.marketplace))
    ingest(wf,[r])
    if case in {'wireless','unknown-jp','seed','rule-conflict'}:
        with pytest.raises(WorkStoreError): automatic(wf,[r['asin']],'CATEGORY')
        assert wf.bench.store.products()[0]['category'] is None
    else:
        automatic(wf,[r['asin']],'CATEGORY')
        with pytest.raises(WorkStoreError): automatic(wf,[r['asin']],'BRAND')
        assert wf.bench.store.products()[0]['brand'] is None
    assert not wf.bench.prepared_pool()


def test_selection_rejects_product_revision_and_material_changes(wf):
    ingest(wf)
    old = wf.select(['B000000001'])
    human(wf,['B000000001'],'CATEGORY',100578)
    with pytest.raises(WorkStoreError, match='Stale'):
        wf.confirm(old,kind='BRAND',option_id=7,reviewer='Human',note='Evidence',human_verified=True)
    old = wf.select(['B000000001'])
    wf.session.begin_brand_refresh(100578)
    with pytest.raises(WorkStoreError, match='Stale'):
        wf.revoke(old,kind='CATEGORY',reviewer='Human',note='Changed')
    assert not wf.bench.prepared_pool()


def test_group_auto_failure_rolls_back_the_whole_selected_subset(wf):
    ingest(wf,[product(wf.session.scope.marketplace),
        product(wf.session.scope.marketplace,'B000000002',title='Synthetic wireless headphone')])
    selection = wf.select(['B000000001','B000000002'])
    before, history = wf.bench.store.products(), wf.bench.store.history()
    with pytest.raises(WorkStoreError):
        wf.apply_auto(selection,kind='CATEGORY',reviewer='Human',note='Evaluate limited rule')
    assert wf.bench.store.products() == before and wf.bench.store.history() == history


def test_cancellation_requires_reason_before_any_write(wf):
    ingest(wf)
    automatic(wf,['B000000001'],'CATEGORY')
    selection = wf.select(['B000000001'])
    before, history = wf.bench.store.products(), wf.bench.store.history()
    with pytest.raises(WorkStoreError):
        wf.revoke(selection,kind='CATEGORY',reviewer='Human',note=' ')
    assert wf.bench.store.products() == before and wf.bench.store.history() == history


@pytest.mark.parametrize('action',['HUMAN','AUTO','REVOKE'])
def test_material_change_between_selection_check_and_transaction_stops(wf, monkeypatch, action):
    ingest(wf)
    selection = wf.select(['B000000001'])
    before, history = wf.bench.store.products(), wf.bench.store.history()
    transaction = wf.bench._transaction
    @contextmanager
    def change_before_begin(**kwargs):
        wf.session.begin_inventory_refresh()
        with transaction(**kwargs) as conn:
            yield conn
    monkeypatch.setattr(wf.bench,'_transaction',change_before_begin)
    with pytest.raises(WorkStoreError,match='evidence changed'):
        if action=='HUMAN':
            wf.confirm(selection,kind='CATEGORY',option_id=100578,reviewer='Human',note='Evidence',human_verified=True)
        elif action=='AUTO':
            wf.apply_auto(selection,kind='CATEGORY',reviewer='Human',note='Evidence')
        else:
            wf.revoke(selection,kind='CATEGORY',reviewer='Human',note='Evidence')
    assert wf.bench.store.products()==before and wf.bench.store.history()==history


def test_existing_strict_client_delivers_current_complete_mock_and_rejects_partial(wf, tmp_path):
    from modules.shopee_catalog_client import ShopeeCatalogClient, ShopeeCatalogCredentials
    market = wf.session.scope.marketplace
    current = ClassificationWorkflow(BetaWorkBench(BetaWorkStore.create(tmp_path/'strict.sqlite3',
        marketplace=market,shop_id='22'),session_for(market,shop='22')))
    install_definitions(current)
    ingest(current)
    human(current,['B000000001'],'CATEGORY',100578)
    response = {'response':{'brand_list':[{'brand_id':7,'display_brand_name':'Synthetic Maker',
        'original_brand_name':'Synthetic Maker'}],'has_next_page':False,'next_offset':0}}
    calls = []
    def transport(*args):
        calls.append(args[0])
        return response
    client = ShopeeCatalogClient(ShopeeCatalogCredentials(1,'SYNTHETIC_KEY',22,'SYNTHETIC_TOKEN'),
        marketplace=market,request_json=transport)
    observation = current.acquire_brand(client,100578)
    assert len(calls)==1 and observation.source=='OFFLINE_MOCK'
    human(current,['B000000001'],'BRAND',7)
    assert current.bench.prepared_pool()
    with pytest.raises(PreparationError,match='OFFICIAL_CURRENT'):
        current.session.require_operational(current.bench.store.products()[0])
    response['response'].update(has_next_page=True,next_offset=1)
    with pytest.raises(PreparationError,match='PARTIAL'):
        current.acquire_brand(client,100578,max_pages=1)
    assert len(calls)==2 and not current.bench.prepared_pool()


@pytest.mark.parametrize('kind', ['CATEGORY','BRAND'])
def test_atomic_subset_rolls_back_all_updates_and_notes(wf, monkeypatch, kind):
    ingest(wf,[product(wf.session.scope.marketplace,f'B{i:09d}') for i in (1,2,3)])
    if kind == 'BRAND': human(wf,['B000000001','B000000002'],'CATEGORY',100578)
    selection = wf.select(['B000000001','B000000002'])
    before, history = wf.bench.store.products(), wf.bench.store.history()
    write = wf.bench.store.write
    def fail_second(conn, value, **kwargs):
        if value['asin'] == 'B000000002': raise OSError('Synthetic save failure')
        return write(conn,value,**kwargs)
    monkeypatch.setattr(wf.bench.store,'write',fail_second)
    with pytest.raises(WorkStoreError):
        wf.confirm(selection,kind=kind,option_id=100578 if kind=='CATEGORY' else 7,
                   reviewer='Human',note='Evidence',human_verified=True)
    assert wf.bench.store.products() == before and wf.bench.store.history() == history


def test_add_b_keeps_a_and_revoke_survives_restart_without_auto_reaccept(wf):
    ingest(wf)
    automatic(wf,['B000000001'],'CATEGORY')
    automatic(wf,['B000000001'],'BRAND')
    before = copy.deepcopy(wf.bench.store.products()[0])
    ingest(wf,[product(wf.session.scope.marketplace,'B000000002')],batch='B')
    assert wf.bench.store.products()[0] == before
    wf.revoke(wf.select(['B000000001']),kind='BRAND',reviewer='Human',note='Recheck alias')
    history = wf.bench.store.history()
    market, shop = wf.session.scope.marketplace, wf.session.scope.shop_id
    restarted = ClassificationWorkflow(BetaWorkBench(BetaWorkStore(wf.bench.store.path,
        marketplace=market,shop_id=shop), PreparationSession(market,shop)))
    assert not restarted.bench.prepared_pool()
    assert restarted.bench.store.history()[:len(history)] == history
    assert restarted.bench.store.products()[0]['revoked'][-1]['kind'] == 'BRAND'


@pytest.mark.parametrize('change',['catalog','rule','alias','fact','brand-failure','inventory'])
def test_material_update_invalidates_prepared_pool(wf, change):
    ingest(wf)
    automatic(wf,['B000000001'],'CATEGORY')
    automatic(wf,['B000000001'],'BRAND')
    assert wf.bench.prepared_pool()
    if change in {'catalog','rule','alias'}:
        ctx, rule, alias = definitions(wf)
        wf.supply_catalog(replace(ctx.catalog,catalog_version='CHANGED') if change=='catalog' else ctx.catalog,
            reference='SYNTHETIC_CURRENT',revision='SYNTHETIC_RULE_ALIAS_1',
            rules=(replace(rule,version='2') if change=='rule' else rule,),
            aliases=(replace(alias,version='2') if change=='alias' else alias,))
    elif change=='fact': wf.session.begin_fact_refresh('B000000001')
    elif change=='brand-failure': wf.session.begin_brand_refresh(100578)
    else: wf.session.begin_inventory_refresh()
    assert not wf.bench.prepared_pool()
    with pytest.raises(WorkStoreError): wf.bench.output(selected(wf.bench))


def test_acquisition_failure_does_not_restore_previous_complete_brand(wf, monkeypatch):
    ingest(wf)
    automatic(wf,['B000000001'],'CATEGORY')
    automatic(wf,['B000000001'],'BRAND')
    assert wf.bench.prepared_pool()
    def partial(*a, **k):
        wf.session.begin_brand_refresh(100578)
        raise PreparationError('BRAND_PARTIAL_PAGE_LIMIT')
    monkeypatch.setattr(wf.session,'acquire_brand',partial)
    with pytest.raises(PreparationError): wf.acquire_brand(object(),100578)
    assert not wf.bench.prepared_pool()
    assert not wf.bench.store.products()[0]['assessment']['brand_valid']


@pytest.mark.parametrize('material',['catalog','brand','fact'])
def test_identical_material_after_failure_never_revives_old_confirmation(wf, material):
    records = [product(wf.session.scope.marketplace)]
    ingest(wf,records)
    human(wf,['B000000001'],'CATEGORY',100578)
    human(wf,['B000000001'],'BRAND',7)
    assert wf.bench.prepared_pool()
    ctx = wf.session.classification_context()
    if material=='catalog':
        wf.session.begin_catalog_refresh()
        wf.supply_catalog(ctx.catalog,reference=ctx.classification.catalog_ref,
            rules=ctx.rules,aliases=ctx.aliases,revision=ctx.classification.revision)
        wf.supply_mock_brand(ctx.brands[100578])
    elif material=='brand':
        wf.session.begin_brand_refresh(100578)
        wf.supply_mock_brand(ctx.brands[100578])
    else:
        wf.session.begin_fact_refresh('B000000001')
        ingest(wf,records,batch='Retry with same content')
    assert not wf.bench.prepared_pool()
    if material!='brand': human(wf,['B000000001'],'CATEGORY',100578)
    human(wf,['B000000001'],'BRAND',7)
    assert wf.bench.prepared_pool()


def test_invalid_fact_refresh_stays_expired_when_retried_with_same_content(wf):
    records = [product(wf.session.scope.marketplace)]
    ingest(wf,records)
    human(wf,['B000000001'],'CATEGORY',100578)
    human(wf,['B000000001'],'BRAND',7)
    bad = copy.deepcopy(records)
    bad[0]['facts']['fields'].pop('title')
    with pytest.raises(ValueError): ingest(wf,bad,batch='Invalid refresh')
    assert not wf.bench.prepared_pool()
    ingest(wf,records,batch='Retry old content')
    assert not wf.bench.prepared_pool() and wf.bench.store.products()[0]['category'] is None


def test_keepa_capture_and_resolver_keep_only_own_explicit_jp_metadata():
    from modules.keepa_client import _product_to_cache_data
    from modules.asin_resolver import _verified_row, FOUND
    from test_sg_initial_beta import raw
    p = raw('B000000001','Synthetic wired headphone')
    captured = _product_to_cache_data(p)
    facts = ProductFacts.from_dict(captured['classification_facts'])
    assert facts.fields['title'].owned_by(p['asin'])
    assert facts.fields['category_tree'].value == p['categoryTree']
    row = _verified_row({'asin':p['asin']},FOUND,'KEEPA_VERIFIED','',captured)
    assert row['classification_facts'] == facts.to_dict()
    legacy = dict(captured)
    legacy.pop('classification_facts')
    assert _verified_row({'asin':p['asin']},FOUND,'KEEPA_VERIFIED','',legacy)['classification_facts'] is None
    p.pop('domainId')
    assert not ProductFacts.from_dict(_product_to_cache_data(p)['classification_facts']).fields['title'].owned_by(p['asin'])
    p.pop('asin')
    assert _product_to_cache_data(p,fallback_asin='B000000001')['classification_facts'] is None


def test_unapproved_operation_flag_cannot_unlock_auto_and_approval_is_exact(wf, monkeypatch):
    install_definitions(wf,operational=True)
    ingest(wf)
    automatic(wf,['B000000001'],'CATEGORY')
    automatic(wf,['B000000001'],'BRAND')
    r = wf.bench.prepared_pool()[0]
    monkeypatch.setattr(wf.session,'require_official_brand',lambda cid: None)
    with pytest.raises(PreparationError, match='AUTO_RULE_OPERATION_NOT_APPROVED'):
        wf.session.require_operational(r)
    ctx = wf.session.classification_context()
    approvals = tuple(AutoRuleApproval(wf.session.scope,k,digest(r[k.lower()][field]),
        ctx.catalog_binding,'SYNTHETIC_EXACT_OWNER_ACCEPTANCE') for k,field in [('CATEGORY','rule'),('BRAND','alias')])
    wf.session.accept_auto_approvals(approvals)
    wf.session.require_operational(r)
    wf.session.accept_auto_approvals([replace(a,definition_binding='0'*64) for a in approvals])
    with pytest.raises(PreparationError): wf.session.require_operational(r)
    with pytest.raises(PreparationError):
        wf.session.accept_auto_approvals([replace(approvals[0],scope=replace(wf.session.scope,shop_id='other'))])


@pytest.mark.parametrize('source_type',['EXPANSION','RESOLVER'])
def test_normal_producer_facts_reach_p1_without_reconstruction(wf, source_type):
    market = wf.session.scope.marketplace
    r = product(market,source_type=source_type)
    producer = {'candidate_asin':r['asin'],'classification_facts':r['facts']}
    from modules.ph_image_safety import create_image_sidecar
    from modules.prelisting_candidate_csv import parse_prelisting_candidate_csv
    content = r['source']['candidate'].encode('utf-8')
    parsed = parse_prelisting_candidate_csv(content,filename='candidate.csv')
    image = create_image_sidecar(content,parsed.rows,[{'candidate_asin':r['asin'],
        'ph_image_safety_fact':r['weapon']['images']}])
    args = dict(marketplace=market,candidate_content=content,filename='candidate.csv',
        producer_rows=[producer],text_content=r['source']['text'].encode('utf-8'), image_content=image)
    records = records_from_producer(**args)
    assert records[0]['facts'] == r['facts']
    ingest(wf,records)
    human(wf,[r['asin']],'CATEGORY',100578)
    human(wf,[r['asin']],'BRAND',7)
    assert wf.bench.prepared_pool()
    args['producer_rows'] = []  # Old cache and CSV cannot invent JP provenance.
    ingest(wf,records_from_producer(**args))
    human(wf,[r['asin']],'CATEGORY',100578)
    human(wf,[r['asin']],'BRAND',7)
    assert not wf.bench.prepared_pool()
