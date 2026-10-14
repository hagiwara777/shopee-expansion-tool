"""SG initial-beta decisions, durable queues and explicit manual listing work.

No client, credentials, operation ledger or external tool is owned here.
The initial integration is offline only. Catalog currentness is explicit;
there is deliberately no invented Brand TTL or implicit old-DB fallback.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
from io import StringIO
import json
from uuid import uuid4

from modules.category_ai_core import CategoryCatalog
from modules.category_mapper_sg import SGMapperRecommendation
from modules.guardrails import apply_guardrails
from modules.prelisting_candidate_csv import parse_prelisting_candidate_csv
from modules.prelisting_gate import evaluate_prelisting_gate
from modules.prelisting_sg_body_safety import body_confirmation_bytes, parse_body_confirmations
from modules.product_text_safety import parse_product_text_safety_sidecar
from modules.ingredient_safety import parse_ingredient_safety_sidecar
from modules.preparation_group_output import format_preparation_groups
from modules.sg_beta_facts import ProductFacts, CategoryRule, digest, normalized, FIELDS, FieldFact
from modules.sg_beta_work_store import SGWorkError, SGWorkStore, encode, timestamp
from modules.sls_category_assets import load_sg_context
from modules.sls_category_rules_sg import evaluate_sg_category


@dataclass(frozen=True)
class BrandObservation:
    category_id: int
    shop_id: str
    brands: tuple[tuple[int, str, bool], ...]
    observation_ref: str
    complete: bool
    current: bool
    source: str  # OFFLINE_MOCK, SAVED_COMPARISON, OFFICIAL_SESSION
    marketplace: str = 'SG'

    def __post_init__(self):
        if (self.marketplace not in {'PH', 'SG'}
                or type(self.category_id) is not int or self.category_id <= 0
                or not self.shop_id or not self.observation_ref
                or type(self.complete) is not bool or type(self.current) is not bool
                or self.source not in {'OFFLINE_MOCK', 'SAVED_COMPARISON', 'OFFICIAL_SESSION'}
                or len({b[0] for b in self.brands}) != len(self.brands)):
            raise SGWorkError('Brand observation identity/completeness invalid')
        for bid, name, no_brand in self.brands:
            if type(bid) is not int or bid < 0 or not isinstance(name, str) or not name.strip() or type(no_brand) is not bool:
                raise SGWorkError('Invalid Brand option')
            # Reuse the existing strict No Brand spelling boundary, not ID.
            if (name.strip().casefold() in {'no brand', 'nobrand'}) != no_brand:
                raise SGWorkError('Brand name/No Brand kind conflict')

    @property
    def binding(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class BrandAlias:
    source_brand: str
    category_id: int
    brand_id: int
    brand_name: str
    approval_ref: str
    version: str
    scope: str = 'OFFLINE_ONLY'
    marketplace: str = 'SG'

    def __post_init__(self):
        if (self.marketplace not in {'PH', 'SG'}
                or type(self.category_id) is not int or self.category_id <= 0
                or type(self.brand_id) is not int or self.brand_id < 0
                or not all(isinstance(s, str) for s in
                           (self.source_brand, self.brand_name, self.approval_ref, self.version))):
            raise SGWorkError('Invalid human-reviewed Brand alias')


@dataclass(frozen=True)
class ValidationContext:
    catalog: CategoryCatalog
    catalog_current: bool
    brands: dict[int, BrandObservation]
    rules: tuple[CategoryRule, ...]
    aliases: tuple[BrandAlias, ...]
    inventories: tuple  # freshly parsed all-shop files; do not reuse invisibly
    expected_shop_count: int
    inventory_confirmed_current: bool
    inventory_ref: str
    mode: str = 'OFFLINE'

    def __post_init__(self):
        if (self.catalog.marketplace != 'SG' or self.mode != 'OFFLINE'
                or type(self.catalog_current) is not bool
                or type(self.inventory_confirmed_current) is not bool
                or type(self.expected_shop_count) is not int or not 1 <= self.expected_shop_count <= 3):
            raise SGWorkError('SG initial beta requires an explicit offline SG context')
        if len({r.rule_id for r in self.rules}) != len(self.rules):
            raise SGWorkError('Conflicting rule identity')
        from modules.category_mapper_sg import _validate_sg_catalog_paths
        _validate_sg_catalog_paths(self.catalog)
        if any(k != v.category_id for k, v in self.brands.items()):
            raise SGWorkError('Brand Category binding mismatch')

    @property
    def catalog_binding(self):
        return digest({'marketplace': self.catalog.marketplace, 'version': self.catalog.catalog_version,
                       'nodes': [asdict(n) for n in self.catalog.nodes]})


def _category_basis(facts, ctx, *, authority, cid, path, rule=None):
    return digest({'fact': facts.binding, 'catalog': ctx.catalog_binding, 'authority': authority,
                   'category_id': cid, 'path': path, 'rule': asdict(rule) if rule else None})


def _brand_basis(facts, category, observation, *, authority, alias=None):
    return digest({'fact': facts.binding, 'category': category, 'catalog': observation.binding,
                   'authority': authority, 'alias': asdict(alias) if alias else None})


def auto_category(facts, ctx):
    matches = [r for r in ctx.rules if r.marketplace == ctx.catalog.marketplace
               and r.matches(facts, mode=ctx.mode)]
    if not ctx.catalog_current or len(matches) != 1:
        return None
    rule = matches[0]
    node = ctx.catalog.get(rule.category_id)
    if node is None or not node.is_leaf or node.category_path != rule.category_path:
        return None
    return {'authority': 'AUTO_RULE', 'category_id': node.category_id, 'category_path': node.category_path,
            'rule_id': rule.rule_id, 'rule': json.loads(encode(asdict(rule))), 'catalog_version': ctx.catalog.catalog_version,
            'basis': _category_basis(facts, ctx, authority='AUTO_RULE',
                cid=node.category_id, path=node.category_path, rule=rule)}


def category_valid(facts, decision, ctx):
    if not decision or not ctx.catalog_current:
        return False
    cid, path = decision.get('category_id'), decision.get('category_path')
    node = ctx.catalog.get(cid) if type(cid) is int else None
    if node is None or not node.is_leaf or node.category_path != path:
        return False
    authority = decision.get('authority')
    if authority == 'AUTO_RULE':
        return auto_category(facts, ctx) == decision
    return authority == 'HUMAN' and decision.get('basis') == _category_basis(facts, ctx,
                                            authority='HUMAN', cid=cid, path=path)


def _current_brand(category, ctx, shop_id):
    observation = ctx.brands.get(category['category_id']) if category else None
    return (observation if observation and observation.current and observation.complete
            and observation.marketplace == ctx.catalog.marketplace
            and observation.shop_id == shop_id and observation.source != 'SAVED_COMPARISON' else None)


def auto_brand(facts, category, ctx, *, shop_id):
    if not category_valid(facts, category, ctx) or not facts.fields['brand'].owned_by(facts.asin):
        return None
    observation = _current_brand(category, ctx, shop_id)
    if observation is None:
        return None
    aliases = [a for a in ctx.aliases if a.marketplace == ctx.catalog.marketplace
               and a.category_id == category['category_id']
               and normalized(a.source_brand) == normalized(facts.fields['brand'].value)
               and a.approval_ref and a.version and a.scope in {'OFFLINE_ONLY', 'OPERATION_APPROVED'}]
    if len(aliases) != 1:
        return None
    alias = aliases[0]
    if (alias.brand_id, alias.brand_name, False) not in observation.brands:
        return None  # Includes missing/unregistered Brand and No Brand.
    # Ambiguous official names cannot be resolved by a source-name alias alone.
    if sum(normalized(b[1]) == normalized(alias.brand_name) and not b[2] for b in observation.brands) != 1:
        return None
    return {'authority': 'AUTO_RULE', 'brand_id': alias.brand_id, 'brand_name': alias.brand_name,
            'is_no_brand': False, 'alias': asdict(alias), 'observation_ref': observation.observation_ref,
            'brand_catalog_binding': observation.binding, 'basis': _brand_basis(facts, category, observation,
                                                      authority='AUTO_RULE', alias=alias)}


def brand_valid(facts, category, decision, ctx, shop_id):
    if not decision or not category_valid(facts, category, ctx):
        return False
    observation = _current_brand(category, ctx, shop_id)
    if observation is None or (decision.get('brand_id'), decision.get('brand_name'),
                               decision.get('is_no_brand')) not in observation.brands:
        return False
    if decision.get('authority') == 'AUTO_RULE':
        return auto_brand(facts, category, ctx, shop_id=shop_id) == decision
    return (decision.get('authority') == 'HUMAN' and decision.get('basis') ==
            _brand_basis(facts, category, observation, authority='HUMAN'))


def _sources(record):
    source = record['source']
    content = source['candidate'].encode('utf-8')
    candidates = parse_prelisting_candidate_csv(content, filename=source['filename'])
    text = (parse_product_text_safety_sidecar(source['text'].encode('utf-8'), filename='text.csv',
            candidate_content=content, candidates=candidates) if source.get('text') else None)
    ingredients = (parse_ingredient_safety_sidecar(source['ingredients'].encode('utf-8'),
                   filename='ingredients.csv', candidate_content=content, candidates=candidates)
                   if source.get('ingredients') else None)
    body = (parse_body_confirmations(source['body'].encode('utf-8'), candidates, text)
            if source.get('body') else None)
    return candidates, text, ingredients, body


def recommendation(record, *, marketplace="SG"):
    candidates, _, _, _ = _sources(record)
    c = next(c for c in candidates.rows if c.candidate_asin == record['asin'])
    return SGMapperRecommendation(marketplace, c.source_type, c.source_asin, c.candidate_asin,
                                  c.product_title, c.brand, c.category, c.input_title, 'GATE_ELIGIBLE')


def capture_weapon_review(item, session, *, images):
    """Copy only current existing workflow results. No AI request is performed."""
    from modules.product_text_safety import product_text_safety_fact_to_payload
    evidence = session.current(item)
    if evidence is None:
        raise SGWorkError('Current product/image evidence required')
    inspection = session.current_image_inspection(item)
    decision = session.decision(item)
    saved = session._decisions.get(item.candidate_asin)
    return {'text': product_text_safety_fact_to_payload(evidence.text), 'images': dict(images),
            'inspection': asdict(inspection) if inspection else None,
            'decision': decision, 'note': saved[2] if saved and decision else '',
            'policy': list(session.policy_binding(item))}


def _weapon_blocker(record, item, text):
    from modules.product_review import WeaponImageReviewSession
    from modules.product_text_safety import product_text_safety_fact_from_transport
    from modules.weapon_image_inspection import WeaponImageInspection, OfflineWeaponImageInspector
    saved = record.get('weapon')
    if not saved or text is None:
        return 'WEAPON_EVIDENCE_MISSING'
    fact = product_text_safety_fact_from_transport(saved['text'], candidate_asin=item.candidate_asin,
                                                  provider='keepa')
    if fact != text.facts_by_asin[item.candidate_asin]:
        return 'WEAPON_TEXT_CHANGED'
    session = WeaponImageReviewSession(item.marketplace)
    session.supply(item, text=fact, images=saved['images'])
    if saved['policy'] != list(session.policy_binding(item)):
        return 'WEAPON_POLICY_CHANGED'
    if saved.get('inspection'):
        inspection = WeaponImageInspection(**saved['inspection'])
        if (not isinstance(inspection.evaluation_id, str) or not inspection.evaluation_id
                or not isinstance(inspection.image_digests, (list, tuple))
                or any(not isinstance(d, (list, tuple)) or len(d) != 4 for d in inspection.image_digests)
                or inspection.system_status == 'COMPLETED' and not session.current(item).image_urls):
            return 'WEAPON_INSPECTION_INVALID'
        # Reuse the original response validator for saved image coverage,
        # digest/type and completion consistency. Attempt count was not saved;
        # the adapter value only satisfies the status-shape check, not history.
        OfflineWeaponImageInspector._validate({
            'system_status': inspection.system_status, 'ai_status': inspection.ai_status,
            'note': inspection.note, 'images': [dict(zip(('url', 'status', 'sha256', 'mime'), d))
                                                for d in inspection.image_digests],
            'attempts': 1 if inspection.ai_status is not None else 0,
        }, session.current(item))
        session.finish_image_inspection(item, evidence_binding=session.current(item).binding,
                                         inspection=inspection)
    if saved.get('decision'):
        session.record_weapon_decision(item, decision=saved['decision'], reviewed_images=True, note=saved['note'])
    return 'WEAPON_REVIEW_REQUIRED' if session.preparation_blocker(item) else None


def assess(record, ctx, *, shop_id, marketplace="SG"):
    """Single contract for queues, confirmation, preparation, SLS and every output."""
    if marketplace not in {"PH", "SG"} or ctx.catalog.marketplace != marketplace:
        raise SGWorkError("Preparation marketplace mismatch")
    facts = ProductFacts.from_dict(record['facts'])
    candidates, text, ingredients, body = _sources(record)
    c = next(c for c in candidates.rows if c.candidate_asin == facts.asin)
    missing = []
    for name in ('title', 'brand', 'category_tree'):
        if not facts.fields[name].owned_by(facts.asin):
            missing.append('OWN_JP_FACT_REQUIRED:' + name)
    if record.get('asin') != facts.asin:
        missing.append('FACT_ASIN_MISMATCH')
    if (facts.fields['title'].value != c.product_title or facts.fields['brand'].value != c.brand):
        missing.append('FACT_CANDIDATE_MISMATCH')
    if not ctx.inventory_confirmed_current or not ctx.inventory_ref:
        missing.append('CURRENT_ALL_SHOP_INVENTORY_REQUIRED')
    try:
        gate = evaluate_prelisting_gate(candidates, ctx.inventories, marketplace=marketplace,
            expected_shop_count=ctx.expected_shop_count, product_text_safety=text,
            ingredient_safety=ingredients, sg_body_confirmations=body)
        row = next(r for r in gate.rows if r.candidate.candidate_asin == facts.asin)
        safety = list(row.reason_codes)
        if row.final_eligibility != 'ELIGIBLE':
            safety.append('GATE_' + row.final_eligibility)
        existing = row.existing_listing_status == 'EXISTING'
    except (ValueError, RuntimeError):
        safety, existing = ['GATE_REVALIDATION_REQUIRED'], False
    # Own product Facts also participate in the unchanged Guardrail matcher.
    own_row = {'candidate_asin': facts.asin, 'product_title': c.product_title, 'brand': c.brand,
               'category': c.category}
    for name in FIELDS[4:]:
        f = facts.fields[name]
        if f.owned_by(facts.asin):
            own_row[name] = list(f.value)
    guarded = apply_guardrails((own_row,), marketplace=marketplace)[0]
    if guarded['guardrail_status'] != 'SAFE':
        safety.extend(('FACT_GUARDRAIL_' + guarded['guardrail_status'], guarded['guardrail_matched_terms']))
    if record.get('manual_exclude'):
        safety.append('HUMAN_EXCLUDE')
    if record.get('body_excluded'):
        safety.append('SG_BODY_EXCLUDE_HISTORY')
    cat = record.get('category')
    valid_cat = category_valid(facts, cat, ctx)
    valid_brand = brand_valid(facts, cat, record.get('brand'), ctx, shop_id)
    if not valid_cat:
        missing.append('CATEGORY_CONFIRMATION_REQUIRED')
    if not valid_brand:
        missing.append('BRAND_CONFIRMATION_REQUIRED')
    if valid_cat:
        node = ctx.catalog.get(cat['category_id'])
        if marketplace == 'SG':
            sls = evaluate_sg_category(marketplace='SG', category_id=node.category_id,
                category_confirmed=True, category_path=cat['category_path'], current_category_path=node.category_path,
                current_is_leaf=node.is_leaf, catalog_version=ctx.catalog_binding, context=load_sg_context())
        else:
            from modules.sls_category_assets import load_ph_context
            from modules.sls_category_rules import evaluate_ph_category
            sls = evaluate_ph_category(marketplace='PH', category_id=node.category_id,
                category_confirmed=True, context=load_ph_context())
        if sls.check_state != 'EVALUATED' or sls.action != 'CATEGORY_ALLOW':
            safety.extend(('SLS_STOP', *sls.reason_codes))
    else:
        sls = None
    try:
        weapon = _weapon_blocker(record, recommendation(record, marketplace=marketplace), text)
    except (ValueError, RuntimeError, KeyError, TypeError):
        weapon = 'WEAPON_REVALIDATION_REQUIRED'
    if weapon:
        safety.append(weapon)
    missing.extend(safety)
    return json.loads(encode({'valid': not missing, 'category_valid': valid_cat, 'brand_valid': valid_brand,
            'safety_reasons': tuple(safety), 'reasons': tuple(dict.fromkeys(missing)),
            'existing': existing, 'sls': asdict(sls) if sls else None,
            'basis': digest({'facts': facts.to_dict(), 'category': cat, 'brand': record.get('brand'),
                             'source': record['source'], 'weapon': record.get('weapon'),
                             'catalog': ctx.catalog_binding,
                             'sls': asdict(sls) if sls else None, 'guarded': guarded})}))


class SGWorkBench:
    def __init__(self, store: SGWorkStore, context: ValidationContext):
        self.store, self.context = store, context

    def ingest(self, *, candidate_content, filename, facts, text_content=None,
               ingredient_content=None, body_confirmations=None, weapon_records=None, operation_ref=''):
        candidates = parse_prelisting_candidate_csv(candidate_content, filename=filename)
        asins = [c.candidate_asin for c in candidates.rows]
        if len(asins) != len(set(asins)) or set(facts) != set(asins):
            raise SGWorkError('Unique ASINs and full explicit Fact correspondence required')
        source = {'candidate': candidate_content.decode('utf-8'), 'filename': filename,
                  'text': text_content.decode('utf-8') if text_content else '',
                  'ingredients': ingredient_content.decode('utf-8') if ingredient_content else '',
                  'body': body_confirmation_bytes(body_confirmations).decode('utf-8') if body_confirmations else ''}
        with self.store.transaction() as conn:
            old = self.store.read_all(conn)
            for c in candidates.rows:
                f = facts[c.candidate_asin]
                if f.asin != c.candidate_asin or f.fields['title'].value != c.product_title or f.fields['brand'].value != c.brand:
                    raise SGWorkError('Fact/Candidate product mismatch')
                previous = old.get(f.asin)
                payload = {'asin': f.asin, 'facts': f.to_dict(), 'source': source,
                           'weapon': (weapon_records or {}).get(f.asin), 'operation_ref': operation_ref,
                           'amazon_url': c.amazon_url or f'https://www.amazon.co.jp/dp/{f.asin}',
                           'first_seen_at': previous['first_seen_at'] if previous else timestamp(),
                           'evaluated_at': timestamp()}
                unchanged = previous and all(previous.get(k) == payload[k] for k in ('facts', 'source', 'weapon'))
                category = previous.get('category') if unchanged else auto_category(f, self.context)
                brand = previous.get('brand') if unchanged else auto_brand(f, category, self.context, shop_id=self.store.shop_id)
                payload.update(category=category, brand=brand,
                               state=previous['state'] if previous else 'WAITING',
                               revoked=previous.get('revoked', []) if previous else [],
                               notes=previous.get('notes', []) if previous else [])
                payload['manual_exclude'] = bool(previous and previous.get('manual_exclude'))
                payload['body_excluded'] = bool(previous and previous.get('body_excluded')) or any(
                    r.get('candidate_asin') == f.asin and r.get('outcome') == 'BODY_PRESENT'
                    for r in (body_confirmations or {}).get('records', []))
                # A revoked rule cannot silently re-confirm after new intake.
                if category and category.get('rule_id') in payload['revoked']:
                    payload['category'], payload['brand'] = None, None
                if 'BRAND' in payload['revoked']:
                    payload['brand'] = None
                result = assess(payload, self.context, shop_id=self.store.shop_id)
                payload['assessment'] = result
                if previous and not unchanged and previous['state'] != 'LISTED':
                    payload['state'] = 'RECHECK'
                elif not result['valid'] and payload['state'] == 'WAITING':
                    payload['state'] = 'RECHECK'
                self.store.write(conn, payload, action='INGEST', expected_revision=previous['revision'] if previous else 0)

    def refresh(self):
        with self.store.transaction() as conn:
            for value in self.store.read_all(conn).values():
                result = assess(value, self.context, shop_id=self.store.shop_id)
                state = value['state']
                if result['existing'] and self.context.inventory_confirmed_current:
                    state = 'LISTED'
                elif not result['valid'] and state in {'WAITING', 'AWAITING_LISTING'}:
                    state = 'RECHECK'
                # Absence in CSV never resets LISTED, ERROR or a pending copy.
                if result != value.get('assessment') or state != value['state']:
                    self.store.write(conn, {**value, 'assessment': result, 'state': state, 'evaluated_at': timestamp()},
                                     action='REVALIDATE', expected_revision=value['revision'])
        return self.store.products()

    def _selection(self, conn, expected):
        if not expected:
            raise SGWorkError('Select one or more products explicitly')
        values = self.store.read_all(conn)
        selected = []
        for asin, revision in expected.items():
            value = values.get(asin)
            if value is None or value['revision'] != revision:
                raise SGWorkError('Stale product selection; refresh first')
            selected.append(value)
        return selected

    def confirm(self, expected, *, kind, option_id, human_verified, note):
        if human_verified is not True or not isinstance(note, str) or not note.strip() or kind not in {'CATEGORY', 'BRAND'}:
            raise SGWorkError('Explicit human confirmation and evidence note required')
        with self.store.transaction() as conn:
            for value in self._selection(conn, expected):
                facts = ProductFacts.from_dict(value['facts'])
                if kind == 'CATEGORY':
                    node = self.context.catalog.get(option_id) if type(option_id) is int else None
                    if node is None or not node.is_leaf or not self.context.catalog_current:
                        raise SGWorkError('Current leaf Category required')
                    value['category'] = {'authority': 'HUMAN', 'category_id': node.category_id,
                        'category_path': node.category_path, 'catalog_version': self.context.catalog.catalog_version,
                        'basis': _category_basis(facts, self.context,
                        authority='HUMAN', cid=node.category_id, path=node.category_path)}
                    value['brand'] = None  # Category adoption never adopts Brand.
                else:
                    if not category_valid(facts, value.get('category'), self.context):
                        raise SGWorkError('Confirm current Category before Brand')
                    observation = _current_brand(value['category'], self.context, self.store.shop_id)
                    option = next((b for b in observation.brands if b[0] == option_id), None) if observation else None
                    if type(option_id) is not int or option is None:
                        raise SGWorkError('Current complete Brand list and exact option required')
                    value['brand'] = {'authority': 'HUMAN', 'brand_id': option[0], 'brand_name': option[1],
                        'is_no_brand': option[2], 'observation_ref': observation.observation_ref,
                        'brand_catalog_binding': observation.binding,
                        'basis': _brand_basis(facts, value['category'], observation, authority='HUMAN')}
                value['notes'].append({'kind': kind, 'result': 'CONFIRMED', 'note': note.strip(), 'at': timestamp()})
                value['assessment'] = assess(value, self.context, shop_id=self.store.shop_id)
                if value['assessment']['valid'] and value['state'] == 'RECHECK':
                    value['state'] = 'WAITING'
                self.store.write(conn, value, action='HUMAN_' + kind, expected_revision=value['revision'])

    def revoke(self, expected, *, kind, note):
        if kind not in {'CATEGORY', 'BRAND'} or not note.strip():
            raise SGWorkError('Cancellation kind/reason required')
        with self.store.transaction() as conn:
            for value in self._selection(conn, expected):
                if kind == 'CATEGORY':
                    decision = value.get('category')
                    if decision and decision.get('rule_id'):
                        value['revoked'].append(decision['rule_id'])
                    value['category'], value['brand'] = None, None
                else:
                    value['brand'] = None
                    value['revoked'].append('BRAND')
                if value['state'] != 'LISTED':
                    value['state'] = 'RECHECK'
                value['notes'].append({'kind': kind, 'result': 'REVOKED', 'note': note, 'at': timestamp()})
                value['assessment'] = assess(value, self.context, shop_id=self.store.shop_id)
                self.store.write(conn, value, action='REVOKE_' + kind, expected_revision=value['revision'])

    def record_review(self, expected, *, result, note):
        """Persist human findings without changing any Safety disposition."""
        if result not in {'UNRESOLVED', 'EVIDENCE_REVIEWED', 'EXCLUDE'} or not note.strip():
            raise SGWorkError('Review result/reason required')
        with self.store.transaction() as conn:
            for value in self._selection(conn, expected):
                value['notes'].append({'kind': 'SAFETY', 'result': result, 'note': note, 'at': timestamp()})
                if result == 'EXCLUDE':
                    value['manual_exclude'] = True
                    if value['state'] != 'LISTED':
                        value['state'] = 'RECHECK'
                self.store.write(conn, value, action='SAFETY_REVIEW', expected_revision=value['revision'])

    def _output_rows(self, conn, expected):
        from modules.sg_beta_release import require_sg_beta_operation
        require_sg_beta_operation()
        rows, selected = [], self._selection(conn, expected)
        for value in selected:
            current = assess(value, self.context, shop_id=self.store.shop_id)
            locked = conn.execute('SELECT 1 FROM copy_locks WHERE asin=?', (value['asin'],)).fetchone()
            if not current['valid'] or value.get('manual_exclude') or value['state'] != 'WAITING' or locked:
                raise SGWorkError('Selected product requires recheck or is already being processed')
            cat, brand = value['category'], value['brand']
            authority = 'AUTO_RULE' if cat['authority'] == brand['authority'] == 'AUTO_RULE' else (
                        'HUMAN' if cat['authority'] == brand['authority'] == 'HUMAN' else 'MIXED')
            rows.append({'marketplace': 'SG', 'asin': value['asin'],
                'group_key': f"SG|{cat['category_id']}|{brand['brand_id']}",
                'category_id': cat['category_id'], 'category_path': cat['category_path'],
                'brand_id': brand['brand_id'], 'brand_name': brand['brand_name'],
                'mandatory_attribute_count': None, 'verification_status': authority,
                'category_authority': cat['authority'], 'brand_authority': brand['authority'],
                'listing_ready': 'FALSE', 'output_scope': 'SG_INITIAL_BETA_OFFLINE', 'basis': current['basis']})
        return rows, selected

    def output(self, expected, *, reserve_copy=False):
        """Persist export/copy intent before delivering bytes. Downloads do not copy."""
        with self.store.transaction() as conn:
            rows, values = self._output_rows(conn, expected)
            csv_bytes, text = format_preparation_groups(rows,
                extra_columns=('category_authority', 'brand_authority', 'output_scope'), unknown_attribute_text='未取得')
            operation_id = uuid4().hex if reserve_copy else None
            if reserve_copy:
                payload = {'asins': list(expected), 'basis': {r['asin']: r['basis'] for r in rows},
                           'created_at': timestamp(), 'note': ''}
                conn.execute('INSERT INTO copy_operations VALUES (?,?,?,?)',
                             (operation_id, 'PENDING', encode(payload), digest({'payload': payload, 'state': 'PENDING'})))
                conn.executemany('INSERT INTO copy_locks VALUES (?,?)', [(a, operation_id) for a in expected])
            for value in values:
                self.store.write(conn, value, action='COPY_INTENT' if reserve_copy else 'EXPORT',
                                 expected_revision=value['revision'])
        return csv_bytes, text.encode('utf-8-sig'), operation_id

    def finish_copy(self, operation_id, *, outcome, note, human_confirmed):
        if outcome not in {'SUCCESS', 'UNKNOWN', 'FAILED', 'CANCELLED'} or human_confirmed is not True or not note.strip():
            raise SGWorkError('Explicit human copy outcome/reason required')
        with self.store.transaction() as conn:
            row = conn.execute('SELECT * FROM copy_operations WHERE operation_id=?', (operation_id,)).fetchone()
            if row is None or row['state'] not in {'PENDING', 'UNKNOWN'}:
                raise SGWorkError('Copy operation already closed or missing')
            payload = json.loads(row['payload'])
            if digest({'payload': payload, 'state': row['state']}) != row['checksum']:
                raise SGWorkError('Copy operation corrupted')
            values = self.store.read_all(conn)
            for asin in payload['asins']:
                value = values[asin]
                if outcome == 'SUCCESS':
                    current = assess(value, self.context, shop_id=self.store.shop_id)
                    if (not current['valid'] or current['basis'] != payload['basis'][asin]
                            or value['state'] != 'WAITING' or value.get('manual_exclude')):
                        raise SGWorkError('Copy preparation changed; recheck the operation')
                    value['state'] = 'AWAITING_LISTING'
                self.store.write(conn, value, action='COPY_' + outcome, expected_revision=value['revision'])
            payload['note'] = note
            conn.execute('UPDATE copy_operations SET state=?,payload=?,checksum=? WHERE operation_id=?',
                         (outcome, encode(payload), digest({'payload': payload, 'state': outcome}), operation_id))
            if outcome != 'UNKNOWN':
                conn.execute('DELETE FROM copy_locks WHERE operation_id=?', (operation_id,))

    def listing_action(self, expected, *, action, human_confirmed, note):
        if action not in {'ERROR', 'RETURN'} or human_confirmed is not True or not note.strip():
            raise SGWorkError('Explicit human listing action/reason required')
        with self.store.transaction() as conn:
            for value in self._selection(conn, expected):
                if conn.execute('SELECT 1 FROM copy_locks WHERE asin=?', (value['asin'],)).fetchone():
                    raise SGWorkError('Resolve the pending copy first')
                if action == 'ERROR':
                    copied = any(row['state'] == 'SUCCESS' and value['asin'] in json.loads(row['payload'])['asins']
                                 for row in conn.execute('SELECT state,payload FROM copy_operations'))
                    if (value['state'] != 'AWAITING_LISTING'
                            and not (value['state'] == 'RECHECK' and copied)):
                        raise SGWorkError('Only a confirmed copy can be marked listing error')
                    value['state'] = 'ERROR'
                else:
                    if value['state'] not in {'AWAITING_LISTING', 'ERROR', 'RECHECK'}:
                        raise SGWorkError('Product cannot return from this state')
                    if not assess(value, self.context, shop_id=self.store.shop_id)['valid'] or value.get('manual_exclude'):
                        raise SGWorkError('Current preparation must be valid before returning')
                    value['state'] = 'WAITING'
                value['notes'].append({'kind': 'LISTING', 'result': action, 'note': note, 'at': timestamp()})
                self.store.write(conn, value, action='LISTING_' + action, expected_revision=value['revision'])

    def queue_csv(self, *, queue='SAFETY'):
        values = self.refresh()
        stream = StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=('marketplace', 'asin', 'product_title', 'amazon_url',
                                'queue', 'reasons', 'confirmation_notes', 'evaluated_at', 'state', 'revision'), lineterminator='\n')
        writer.writeheader()
        for value in values:
            a = value['assessment']
            chosen = (bool(a['safety_reasons']) if queue == 'SAFETY' else
                      not a['category_valid'] if queue == 'CATEGORY' else not a['brand_valid'] if queue == 'BRAND' else True)
            if chosen:
                candidates, _, _, _ = _sources(value)
                c = next(c for c in candidates.rows if c.candidate_asin == value['asin'])
                row = {'marketplace': 'SG', 'asin': value['asin'], 'product_title': c.product_title,
                    'amazon_url': value['amazon_url'], 'queue': queue, 'reasons': ' | '.join(a['reasons']),
                    'confirmation_notes': encode(value['notes']), 'evaluated_at': value['evaluated_at'],
                    'state': value['state'], 'revision': value['revision']}
                writer.writerow({k: "'" + str(v) if str(v).startswith(('=', '+', '-', '@')) else v for k, v in row.items()})
        return stream.getvalue().encode('utf-8-sig')
