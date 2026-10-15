"""P3: existing producers -> P1 decisions -> P2 atomic selected-product saves.

No API discovery, legacy database migration or rule activation. Offline mock
catalogs and saved producer facts never become official acquisition receipts.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import copy
from uuid import uuid4

from modules.beta_workbench import BetaWorkBench
from modules.beta_work_store import WorkStoreError
from modules.preparation_validity import (
    PreparationScope, ClassificationEvidence, InventoryEvidence, BrandEvidence,
)
from modules.prelisting_candidate_csv import parse_prelisting_candidate_csv
from modules.ph_image_safety import parse_image_sidecar
from modules.product_review import WeaponImageReviewSession
from modules.sg_beta_facts import ProductFacts, facts_from_saved_keepa, normalized
from modules.sg_beta_workbench import recommendation, capture_weapon_review, _sources


@dataclass(frozen=True)
class ClassificationSelection:
    scope: PreparationScope
    evidence_revision: int
    products: tuple[tuple[str, int], ...]


def records_from_producer(*, marketplace, candidate_content, filename, producer_rows,
                          text_content, ingredient_content=None, image_content=None,
                          body_content=None, weapon_session=None):
    """Bind normal Expansion/Resolver payloads to their unchanged Candidate CSV.

    Missing legacy provenance becomes UNKNOWN, never reconstructed OWN_PRODUCT.
    Existing image review may be injected only for the same selected market.
    """
    candidates = parse_prelisting_candidate_csv(candidate_content, filename=filename)
    sources = {}
    for row in producer_rows:
        asin = row.get('candidate_asin') or row.get('asin')
        if asin in sources and sources[asin].get('classification_facts') != row.get('classification_facts'):
            raise WorkStoreError('Ambiguous producer product')
        sources[asin] = row
    images = (parse_image_sidecar(image_content, candidate_content=candidate_content,
                                 candidates=candidates) if image_content else None)
    image_facts = {r['fact']['candidate_asin']: r['fact'] for r in images['rows']} if images else {}
    review = weapon_session or WeaponImageReviewSession(marketplace)
    if review.marketplace != marketplace:
        raise WorkStoreError('Image review marketplace mismatch')
    records = []
    for row in candidates.rows:
        payload = sources.get(row.candidate_asin, {}).get('classification_facts')
        if payload is None:
            facts = facts_from_saved_keepa({'asin': row.candidate_asin, 'title': row.product_title,
                'brand': row.brand, 'fetched_at': row.fetched_at}, source_format='cache_snapshot',
                evidence_ref='LEGACY_UNPROVEN')
        else:
            facts = ProductFacts.from_dict(payload)
        if facts.asin != row.candidate_asin:
            raise WorkStoreError('Producer target mismatch')
        record = {'asin': row.candidate_asin, 'marketplace': marketplace, 'facts': facts.to_dict(),
            'source': {'candidate': candidate_content.decode('utf-8'), 'filename': filename,
                'text': (text_content or b'').decode('utf-8'),
                'ingredients': (ingredient_content or b'').decode('utf-8'),
                'body': (body_content or b'').decode('utf-8')}}
        _, text, _, _ = _sources(record)  # Existing SHA and body validators.
        image = image_facts.get(row.candidate_asin)
        if image is not None and text is not None:
            item = recommendation(record, marketplace=marketplace)
            previous = review.current(item)
            if (previous is None or previous.text != text.facts_by_asin[row.candidate_asin]
                    or tuple(image['image_urls']) != previous.image_urls
                    or image['root_category_id'] != previous.root_category_id
                    or image['capture_error'] != previous.image_capture_error
                    or image['provider'] != previous.image_provider):
                review.supply(item, text=text.facts_by_asin[row.candidate_asin], images=image)
            record['weapon'] = capture_weapon_review(item, review, images=image)
        records.append(record)
    return tuple(records)


class ClassificationWorkflow:
    def __init__(self, bench: BetaWorkBench):
        self.bench, self.session = bench, bench.session

    def supply_catalog(self, catalog, *, reference, rules=(), aliases=(), revision):
        self.session.begin_catalog_refresh()
        if not isinstance(reference, str) or not reference.strip():
            raise WorkStoreError('Current catalog acquisition reference required')
        self.session.accept_classification(ClassificationEvidence(self.session.scope, catalog,
            reference + ':' + uuid4().hex, tuple(rules), tuple(aliases), revision))
        self.bench.refresh()

    def supply_inventory(self, inventories, *, expected_shops, reference, confirmed_current):
        self.session.begin_inventory_refresh()
        self.session.accept_inventory(InventoryEvidence(self.session.scope, tuple(inventories),
            tuple(expected_shops), reference, confirmed_current))
        self.bench.refresh()

    def supply_mock_brand(self, observation):
        self.session.begin_brand_refresh(observation.category_id)
        self.session.accept_brand(BrandEvidence(self.session.scope,
            replace(observation, observation_ref=observation.observation_ref + ':' + uuid4().hex)))
        self.bench.refresh()

    def acquire_brand(self, client, category_id, *, max_pages=10):
        # P1 invalidates first, performs strict complete bounded acquisition and
        # distinguishes fake transport from an official session receipt.
        try:
            return self.session.acquire_brand(client, category_id, max_pages=max_pages)
        finally:
            self.bench.refresh()

    def ingest(self, records, *, scope, batch_ref):
        self.session._require_scope(scope)
        records = tuple(records)
        previous_bindings = {r['asin']: self.session._fact_bindings.get(r['asin']) for r in records}
        # A failed replacement must not leave old target facts as current.
        for r in records:
            self.session.begin_fact_refresh(r['asin'])
        facts = tuple(ProductFacts.from_dict(r['facts']) for r in records)
        recheck = tuple(f.asin for f in facts if previous_bindings[f.asin] != f.binding)
        for f in facts:
            self.session.accept_facts(f)
        try:
            return self.bench.ingest(records, batch_ref=batch_ref, require_review_asins=recheck)
        except Exception:
            for r in records:
                self.session.begin_fact_refresh(r['asin'])
            raise

    def select(self, asins):
        asins = tuple(asins)
        current = {r['asin']: r for r in self.bench.refresh()}
        if not asins or len(set(asins)) != len(asins) or any(a not in current for a in asins):
            raise WorkStoreError('Explicit unique current product selection required')
        return ClassificationSelection(self.session.scope, self.session.evidence_revision,
            tuple((a, current[a]['revision']) for a in asins))

    def _expected(self, selection):
        if (not isinstance(selection, ClassificationSelection) or selection.scope != self.session.scope
                or selection.evidence_revision != self.session.evidence_revision
                or not selection.products or len(dict(selection.products)) != len(selection.products)):
            raise WorkStoreError('Stale selection or preparation material; select again')
        return dict(selection.products)

    def candidates(self, asin, *, kind, query=''):
        record = next(r for r in self.bench.store.products() if r['asin'] == asin)
        ctx = self.session.classification_context()
        if kind == 'CATEGORY':
            options = tuple({'id': n.category_id, 'name': n.category_path} for n in ctx.catalog.nodes
                            if n.is_leaf and normalized(query) in normalized(n.category_path))
        elif kind == 'BRAND':
            # Brand candidates require this product's independently valid Category.
            if not self.session.assess(record).get('category_valid'):
                return {'options': (), 'auto': None}
            observation = ctx.brands.get(record['category']['category_id'])
            options = tuple({'id': b[0], 'name': b[1], 'is_no_brand': b[2]} for b in
                (observation.brands if observation else ()) if normalized(query) in normalized(b[1]))
        else:
            raise WorkStoreError('Category or Brand required')
        try:
            automatic = self.session.auto_decision(record, kind=kind)
        except ValueError:
            automatic = None
        return {'options': options, 'auto': automatic}

    def confirm(self, selection, *, kind, option_id, reviewer, note, human_verified):
        self.bench.confirm(self._expected(selection), kind=kind, option_id=option_id,
            reviewer=reviewer, note=note, human_verified=human_verified,
            evidence_revision=selection.evidence_revision)

    def revoke(self, selection, *, kind, reviewer, note):
        self.bench._human(isinstance(reviewer, str) and bool(reviewer.strip()), note)
        self.bench.revoke(self._expected(selection), kind=kind, note=f'{reviewer}: {note}',
                          evidence_revision=selection.evidence_revision)

    def apply_auto(self, selection, *, kind, reviewer, note):
        self.bench._human(isinstance(reviewer, str) and bool(reviewer.strip()), note)
        expected = self._expected(selection)
        if kind not in {'CATEGORY', 'BRAND'}:
            raise WorkStoreError('Category or Brand required')
        with self.bench._transaction(evidence_revision=selection.evidence_revision) as conn:
            for record in self.bench._selection(conn, expected):
                decision = self.session.auto_decision(record, kind=kind)
                if decision is None:
                    raise WorkStoreError('Limited rule not uniquely supported; hold for review')
                record[kind.lower()] = copy.deepcopy(decision)
                if kind == 'CATEGORY':
                    record['brand'] = None
                ctx = self.session.classification_context()
                self.bench._note(record, kind, 'CONFIRMED', note,
                    reviewer=reviewer.strip(), authority='AUTO_RULE', catalog_version=ctx.catalog.catalog_version,
                    rule_alias_revision=ctx.classification.revision, catalog_binding=ctx.catalog_binding)
                self.bench._update_assessment(record, self.bench._assess(record))
                self.bench.store.write(conn, record, action='AUTO_' + kind,
                                       expected_revision=record['revision'])
