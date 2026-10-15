"""PH/SG preparation validity, with explicit session and market evidence.

Offline validation and bounded read-only catalog contract; no credential discovery,
database migration or listing execution.
The legacy SG validators own classification and Safety; this boundary binds their
inputs and re-runs them before returning preparation information or output.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import copy
from uuid import uuid4

from modules.category_ai_core import CategoryCatalog
from modules.sg_beta_facts import ProductFacts, digest
from modules.sg_beta_workbench import (
    BrandAlias, BrandObservation, _category_basis, _brand_basis,
    auto_category, auto_brand, category_valid, _sources, assess as assess_existing,
)
from modules.preparation_group_output import format_preparation_groups


class PreparationError(ValueError):
    """A missing or expired preparation prerequisite; never a Safety override."""


@dataclass(frozen=True)
class PreparationScope:
    marketplace: str
    shop_id: str
    session_id: str

    def __post_init__(self):
        if (self.marketplace not in {'PH', 'SG'} or not isinstance(self.shop_id, str)
                or not self.shop_id.strip() or not isinstance(self.session_id, str)
                or not self.session_id.strip()):
            raise PreparationError('MARKET_SHOP_SESSION_REQUIRED')


@dataclass(frozen=True)
class ClassificationEvidence:
    """The selected market's catalog and reviewed rule/alias revision."""
    scope: PreparationScope
    catalog: CategoryCatalog
    catalog_ref: str
    rules: tuple
    aliases: tuple[BrandAlias, ...]
    revision: str

    def __post_init__(self):
        if (self.catalog.marketplace != self.scope.marketplace or not self.catalog_ref
                or not self.revision or len({r.rule_id for r in self.rules}) != len(self.rules)
                or any(r.marketplace != self.scope.marketplace for r in (*self.rules, *self.aliases))):
            raise PreparationError('CATEGORY_MARKET_OR_REVISION_INVALID')
        # Reuse the complete hierarchy validator, including exact parent/name path.
        from modules.category_mapper_sg import _validate_sg_catalog_paths
        _validate_sg_catalog_paths(self.catalog)


@dataclass(frozen=True)
class BrandEvidence:
    scope: PreparationScope
    observation: BrandObservation

    def __post_init__(self):
        if (self.observation.marketplace != self.scope.marketplace
                or self.observation.shop_id != self.scope.shop_id):
            raise PreparationError('BRAND_SHOP_MISMATCH')


@dataclass(frozen=True)
class InventoryEvidence:
    scope: PreparationScope
    inventories: tuple
    expected_shop_labels: tuple[str, ...]
    reference: str
    confirmed_current: bool

    def __post_init__(self):
        labels = self.expected_shop_labels
        if (not labels or len(set(labels)) != len(labels) or any(not s for s in labels)
                or self.scope.shop_id not in labels
                or type(self.confirmed_current) is not bool):
            raise PreparationError('ALL_SHOPS_BINDING_REQUIRED')
        if (len(self.inventories) != len(labels)
                or {i.shop_label for i in self.inventories} != set(labels)
                or any(i.marketplace != self.scope.marketplace for i in self.inventories)):
            raise PreparationError('INVENTORY_MARKET_OR_SHOPS_MISMATCH')


@dataclass(frozen=True)
class AutoRuleApproval:
    """Explicit adapter injection, never inferred from rule JSON or UI flags.

    Bind one reviewed rule/alias to this exact acquisition session and catalog.
    No normal adapter installs approvals in P3; existing examples stay offline.
    """
    scope: PreparationScope
    kind: str
    definition_binding: str
    catalog_binding: str
    approval_ref: str

    def __post_init__(self):
        if (self.kind not in {'CATEGORY', 'BRAND'} or not self.approval_ref.strip()
                or any(len(s) != 64 or any(c not in '0123456789abcdef' for c in s)
                       for s in (self.definition_binding, self.catalog_binding))):
            raise PreparationError('EXACT_AUTO_RULE_APPROVAL_REQUIRED')


@dataclass(frozen=True)
class _Context:
    """Adapter for the existing pure classification and Safety validators."""
    classification: ClassificationEvidence
    brands: dict
    inventory: InventoryEvidence
    mode: str = 'OFFLINE'
    catalog_current: bool = True

    @property
    def catalog(self):
        return self.classification.catalog

    @property
    def catalog_binding(self):
        return digest(asdict(self.classification.scope) | {
            'catalog': self.catalog.catalog_hash, 'reference': self.classification.catalog_ref,
            'revision': self.classification.revision,
            'rules': [asdict(r) for r in self.classification.rules],
            'aliases': [asdict(a) for a in self.classification.aliases],
        })

    @property
    def rules(self):
        return self.classification.rules

    @property
    def aliases(self):
        return self.classification.aliases

    @property
    def inventories(self):
        return self.inventory.inventories

    @property
    def expected_shop_count(self):
        return len(self.inventory.expected_shop_labels)

    @property
    def inventory_confirmed_current(self):
        return self.inventory.confirmed_current

    @property
    def inventory_ref(self):
        return self.inventory.reference


class PreparationSession:
    """Fresh, in-memory evidence scope. Restart/switch requires new evidence.

    Call begin_*_refresh BEFORE attempting a replacement, including failed and
    partial attempts. No clock TTL or on-disk timestamp can revive old evidence.
    Saved official lists remain comparison material. A new strict complete
    acquisition is required for official currentness; mock receipts stay offline.
    """
    def __init__(self, marketplace, shop_id):
        self.scope = PreparationScope(marketplace, shop_id, uuid4().hex)
        self._classification = None
        self._brands = {}
        self._inventory = None
        self._fact_bindings = {}
        self._official_receipts = {}
        self._official_clients = {}
        self._revision = 0
        self._auto_approvals = ()

    def accept_auto_approvals(self, approvals):
        """Trusted integration boundary; no file, DB, environment or UI loader.

        An approved deployment adapter must supply Owner-approved exact bindings.
        Merely marking a rule OPERATION_APPROVED cannot install this permission.
        """
        self._auto_approvals = ()
        self._revision += 1
        approvals = tuple(approvals)
        for approval in approvals:
            if not isinstance(approval, AutoRuleApproval):
                raise PreparationError('EXACT_AUTO_RULE_APPROVAL_REQUIRED')
            self._require_scope(approval.scope)
        self._auto_approvals = copy.deepcopy(approvals)

    def classification_context(self):
        """Detached current material for shared candidate presentation."""
        return copy.deepcopy(self._context())

    def auto_decision(self, record, *, kind):
        """Reuse the limited deterministic rules; never infer HUMAN authority."""
        self._require_record(record)
        facts, ctx = ProductFacts.from_dict(record['facts']), self._context()
        if kind == 'CATEGORY':
            return auto_category(facts, ctx)
        if kind == 'BRAND':
            return auto_brand(facts, record.get('category'), ctx, shop_id=self.scope.shop_id)
        raise PreparationError('CATEGORY_OR_BRAND_REQUIRED')

    def _require_scope(self, scope):
        if scope != self.scope:
            raise PreparationError('MARKET_SHOP_SESSION_MISMATCH')

    @property
    def evidence_revision(self):
        """In-memory invalidation counter, never a persisted readiness receipt."""
        return self._revision

    def current_inventory(self):
        """Read current all-shop evidence independently of product classification."""
        evidence = self._inventory
        if evidence is None or not evidence.confirmed_current or not evidence.reference:
            raise PreparationError('CURRENT_ALL_SHOP_INVENTORY_REQUIRED')
        self._require_scope(evidence.scope)
        return copy.deepcopy(evidence)

    def begin_catalog_refresh(self):
        self._classification = None
        self._auto_approvals = ()
        self._brands.clear()
        self._official_receipts.clear()
        self._official_clients.clear()
        self._revision += 1

    def accept_classification(self, evidence):
        self.begin_catalog_refresh()
        self._require_scope(evidence.scope)
        self._classification = copy.deepcopy(evidence)

    def begin_brand_refresh(self, category_id):
        self._brands.pop(category_id, None)
        self._official_clients.pop(category_id, None)
        self._official_receipts = {ref: obs for ref, obs in self._official_receipts.items()
                                   if obs.category_id != category_id}
        self._revision += 1

    def accept_brand(self, evidence):
        observation = evidence.observation
        self.begin_brand_refresh(observation.category_id)
        self._require_scope(evidence.scope)
        if self._classification is None:
            raise PreparationError('CURRENT_CATEGORY_CATALOG_REQUIRED')
        node = self._classification.catalog.get(observation.category_id)
        if node is None or not node.is_leaf:
            raise PreparationError('CURRENT_LEAF_REQUIRED')
        if (observation.source != 'OFFLINE_MOCK' or not observation.complete
                or not observation.current or not observation.brands):
            raise PreparationError('COMPLETE_CURRENT_OFFLINE_BRAND_REQUIRED')
        self._brands[observation.category_id] = copy.deepcopy(observation)

    def acquire_brand(self, client, category_id, *, max_pages=10):
        """Explicit call only. Reuse the Client's strict raw/page validators.

        The injected client retains credential and API-budget ownership. Tests
        use its fake transport. No factory, automatic retry or DB write is used.
        A declaration in a saved JSON is never an official acquisition receipt.
        """
        from modules.shopee_catalog_client import ShopeeCatalogClient
        self.begin_brand_refresh(category_id)
        if (not isinstance(client, ShopeeCatalogClient) or self._classification is None
                or type(category_id) is not int or self._classification.catalog.get(category_id) is None
                or not self._classification.catalog.get(category_id).is_leaf
                or type(max_pages) is not int or not 1 <= max_pages <= 10):
            raise PreparationError('BOUND_LEAF_AND_FINITE_BRAND_PAGES_REQUIRED')
        def require_client():
            if (client.marketplace != self.scope.marketplace
                    or str(client.credentials.shop_id) != self.scope.shop_id):
                raise PreparationError('BRAND_MARKET_SHOP_MISMATCH')
        require_client()
        brands, offsets, signatures = {}, set(), set()
        offset = 0
        for _ in range(max_pages):
            require_client()
            if offset in offsets:
                raise PreparationError('BRAND_PAGINATION_CYCLE')
            offsets.add(offset)
            page = client.get_brand_list(self.scope.marketplace, category_id, offset=offset,
                                         page_size=100, strict=True)
            require_client()
            signature = digest(page.brands)
            if page.brands and signature in signatures:
                raise PreparationError('BRAND_PAGE_REPEATED')
            signatures.add(signature)
            for brand in page.brands:
                old = brands.get(brand['brand_id'])
                if old is not None and old != brand:
                    raise PreparationError('BRAND_DUPLICATE_CONFLICT')
                brands[brand['brand_id']] = dict(brand)
            if page.is_complete:
                options = tuple((b['brand_id'], b['brand_name'], b['is_no_brand'])
                                for _, b in sorted(brands.items()))
                source = 'OFFICIAL_SESSION' if client.uses_default_transport else 'OFFLINE_MOCK'
                observation = BrandObservation(category_id, self.scope.shop_id, options,
                    uuid4().hex, True, True, source, marketplace=self.scope.marketplace)
                if source == 'OFFICIAL_SESSION':
                    self._official_receipts[observation.observation_ref] = observation
                    self._official_clients[category_id] = client
                    self._brands[category_id] = observation
                else:
                    self.accept_brand(BrandEvidence(self.scope, observation))
                return observation
            if page.next_offset <= offset or page.next_offset in offsets:
                raise PreparationError('BRAND_PAGINATION_NOT_ADVANCING')
            offset = page.next_offset
        raise PreparationError('BRAND_PARTIAL_PAGE_LIMIT')

    def require_operational(self, record):
        self._require_record(record)
        ctx = self._context()
        for kind in ('CATEGORY', 'BRAND'):
            decision = record.get(kind.lower()) or {}
            if decision.get('authority') == 'HUMAN':
                continue
            definition = decision.get('rule' if kind == 'CATEGORY' else 'alias') or {}
            if (decision.get('authority') != 'AUTO_RULE'
                    or self.auto_decision(record, kind=kind) != decision
                    or definition.get('scope') != 'OPERATION_APPROVED'
                    or not any(a.scope == self.scope and a.kind == kind
                        and a.definition_binding == digest(definition)
                        and a.catalog_binding == ctx.catalog_binding
                        for a in self._auto_approvals)):
                raise PreparationError('AUTO_RULE_OPERATION_NOT_APPROVED')
        self.require_official_brand(record['category']['category_id'])

    def require_official_brand(self, category_id):
        observation = self._brands.get(category_id)
        client = self._official_clients.get(category_id)
        if (observation is None or observation.source != 'OFFICIAL_SESSION' or client is None
                or self._official_receipts.get(observation.observation_ref) != observation
                or client.marketplace != self.scope.marketplace
                or str(client.credentials.shop_id) != self.scope.shop_id):
            raise PreparationError('OFFICIAL_CURRENT_PREPARATION_PROOF_REQUIRED')
        ledger = getattr(client, 'ledger', None)
        if ledger is not None:
            try:
                ledger.require_current()
            except (RuntimeError, ValueError):
                raise PreparationError('CURRENT_CATALOG_CLIENT_LEASE_REQUIRED') from None

    def begin_inventory_refresh(self):
        self._inventory = None
        self._revision += 1

    def accept_inventory(self, evidence):
        self.begin_inventory_refresh()
        self._require_scope(evidence.scope)
        if not evidence.confirmed_current or not evidence.reference:
            raise PreparationError('CURRENT_ALL_SHOP_INVENTORY_REQUIRED')
        self._inventory = copy.deepcopy(evidence)

    def begin_fact_refresh(self, asin):
        self._fact_bindings.pop(asin, None)
        self._revision += 1

    def accept_facts(self, facts):
        """Bind explicit saved evidence; never invent JP or own-product provenance."""
        self.begin_fact_refresh(facts.asin)
        self._fact_bindings[facts.asin] = facts.binding

    def _context(self):
        if self._classification is None:
            raise PreparationError('CURRENT_CATEGORY_CATALOG_REQUIRED')
        if self._inventory is None:
            raise PreparationError('CURRENT_ALL_SHOP_INVENTORY_REQUIRED')
        return _Context(self._classification, copy.deepcopy(self._brands), self._inventory)

    def bind_product(self, record):
        """Start an unconfirmed record; never transfer an old confirmation."""
        result = copy.deepcopy(record)
        if result.get('preparation_scope') not in (None, asdict(self.scope)):
            raise PreparationError('MARKET_SHOP_SESSION_MISMATCH')
        result.update(preparation_scope=asdict(self.scope), category=None, brand=None)
        return result

    def confirm_category(self, record, category_id, *, human_verified):
        self._require_record(record)
        ctx = self._context()
        if human_verified is not True or type(category_id) is not int:
            raise PreparationError('EXPLICIT_HUMAN_CATEGORY_REQUIRED')
        node = ctx.catalog.get(category_id)
        if node is None or not node.is_leaf:
            raise PreparationError('CURRENT_LEAF_REQUIRED')
        facts = ProductFacts.from_dict(record['facts'])
        value = copy.deepcopy(record)
        value['category'] = {'authority': 'HUMAN', 'category_id': category_id,
            'category_path': node.category_path, 'catalog_version': ctx.catalog.catalog_version,
            'basis': _category_basis(facts, ctx, authority='HUMAN', cid=category_id, path=node.category_path)}
        value['brand'] = None
        return value

    def confirm_brand(self, record, brand_id, *, human_verified):
        self._require_record(record)
        ctx = self._context()
        facts, category = ProductFacts.from_dict(record['facts']), record.get('category')
        if human_verified is not True or type(brand_id) is not int or not category_valid(facts, category, ctx):
            raise PreparationError('CURRENT_HUMAN_CATEGORY_REQUIRED')
        observation = ctx.brands.get(category['category_id'])
        option = next((b for b in observation.brands if b[0] == brand_id), None) if observation else None
        if option is None:
            raise PreparationError('CURRENT_COMPLETE_BRAND_OPTION_REQUIRED')
        value = copy.deepcopy(record)
        value['brand'] = {'authority': 'HUMAN', 'brand_id': option[0], 'brand_name': option[1],
            'is_no_brand': option[2], 'observation_ref': observation.observation_ref,
            'brand_catalog_binding': observation.binding,
            'basis': _brand_basis(facts, category, observation, authority='HUMAN')}
        return value

    def _require_record(self, record):
        if record.get('preparation_scope') != asdict(self.scope):
            raise PreparationError('MARKET_SHOP_SESSION_MISMATCH')
        facts = ProductFacts.from_dict(record['facts'])
        if record.get('asin') != facts.asin or self._fact_bindings.get(facts.asin) != facts.binding:
            raise PreparationError('CURRENT_TARGET_FACT_REQUIRED')

    def assess(self, record):
        try:
            self._require_record(record)
            facts = ProductFacts.from_dict(record['facts'])
            ctx = self._context()
            result = assess_existing(record, ctx, shop_id=self.scope.shop_id,
                                     marketplace=self.scope.marketplace)
            missing = list(result['reasons'])
            brand_decision = record.get('brand')
            if brand_decision and (type(brand_decision.get('brand_id')) is not int
                    or type(brand_decision.get('is_no_brand')) is not bool):
                missing.append('BRAND_DECISION_INVALID')
            # Human classification cannot turn unknown/seed/old cache provenance
            # into proof about the target product. Empty optional text remains empty.
            for name, field in facts.fields.items():
                if name not in {'title', 'brand', 'category_tree'} and field.value in ('', [], (), None):
                    continue
                if not field.owned_by(facts.asin):
                    missing.append('OWN_JP_FACT_REQUIRED:' + name)
                elif datetime.fromisoformat(field.fetched_at.replace('Z', '+00:00')) > datetime.now(timezone.utc):
                    missing.append('FACT_TIMESTAMP_IN_FUTURE:' + name)
            candidates, text, _, _ = _sources(record)
            candidate = next(c for c in candidates.rows if c.candidate_asin == facts.asin)
            tree = facts.fields['category_tree'].value
            fact_path = ' > '.join(n['name'] for n in tree)
            image_root = (record.get('weapon') or {}).get('images', {}).get('root_category_id')
            if image_root is not None and (not tree or image_root != tree[0]['catId']):
                missing.append('FACT_IMAGE_ROOT_MISMATCH')
            if any(candidate.fetched_at != facts.fields[k].fetched_at
                   for k in ('title', 'brand', 'category_tree')):
                missing.append('FACT_CAPTURE_TIME_MISMATCH')
            if candidate.category not in (fact_path, tree[-1]['name'] if tree else ''):
                missing.append('FACT_CATEGORY_MISMATCH')
            if text is None or text.facts_by_asin[facts.asin].provider != 'keepa':
                missing.append('KEEPA_TEXT_EVIDENCE_REQUIRED')
            else:
                from modules.product_text_safety import product_text_safety_fact_to_payload
                payload = product_text_safety_fact_to_payload(text.facts_by_asin[facts.asin])
                for name in ('description', 'features', 'shortDescription', 'safetyWarning', 'itemHighlights'):
                    if list(facts.fields[name].value) != list(payload[name]):
                        missing.append('FACT_TEXT_MISMATCH:' + name)
            result.update(valid=not missing, reasons=list(dict.fromkeys(missing)),
                          marketplace=self.scope.marketplace, shop_id=self.scope.shop_id,
                          listing_ready=False, output_scope='PH_SG_P1_OFFLINE')
            result['basis'] = digest({'validation': result['basis'], 'scope': asdict(self.scope),
                'revision': self._revision, 'inventory': asdict(self._inventory)})
            return result
        except PreparationError as exc:
            return {'valid': False, 'reasons': [str(exc)], 'listing_ready': False,
                    'output_scope': 'PH_SG_P1_OFFLINE'}
        except (ValueError, RuntimeError, KeyError, TypeError, StopIteration, AttributeError):
            # Malformed inputs are not a successful zero-row preparation.
            return {'valid': False, 'reasons': ['PREPARATION_EVIDENCE_INVALID_OR_EXPIRED'],
                    'listing_ready': False, 'output_scope': 'PH_SG_P1_OFFLINE'}

    def output(self, records, *, operational=False):
        if operational and self.scope.marketplace == 'SG':
            from modules.sg_beta_release import require_sg_beta_operation
            require_sg_beta_operation()
        records = tuple(copy.deepcopy(tuple(records)))
        if not records or len({r.get('asin') for r in records}) != len(records):
            raise PreparationError('UNIQUE_NONEMPTY_SELECTION_REQUIRED')
        rows = []
        bindings = []
        for record in records:
            result = self.assess(record)
            if not result['valid']:
                raise PreparationError(', '.join(result['reasons']))
            bindings.append(result['basis'])
            cat, brand = record['category'], record['brand']
            if operational:
                self.require_operational(record)
            rows.append({'marketplace': self.scope.marketplace, 'asin': record['asin'],
                'group_key': f"{self.scope.marketplace}|{cat['category_id']}|{brand['brand_id']}",
                'category_id': cat['category_id'], 'category_path': cat['category_path'],
                'brand_id': brand['brand_id'], 'brand_name': brand['brand_name'],
                'mandatory_attribute_count': None,
                'verification_status': cat['authority'] if cat['authority'] == brand['authority'] else 'MIXED',
                'category_authority': cat['authority'], 'brand_authority': brand['authority'],
                'listing_ready': 'TRUE' if operational else 'FALSE',
                'output_scope': 'PH_SG_MANUAL_PREPARATION' if operational else 'PH_SG_P1_OFFLINE'})
        csv_bytes, text = format_preparation_groups(rows, extra_columns=('category_authority', 'brand_authority', 'output_scope'),
                                                   unknown_attribute_text='未取得')
        # Detect invalidation during formatting; cached readiness is never authority.
        for record, binding in zip(records, bindings):
            result = self.assess(record)
            if not result['valid'] or result['basis'] != binding:
                raise PreparationError('PREPARATION_CHANGED_BEFORE_RETURN')
            if operational:
                self.require_operational(record)
        if operational and self.scope.marketplace == 'SG':
            require_sg_beta_operation()
        return csv_bytes, text.encode('utf-8-sig')


def assess_preparation_item(item, *, session=None, records=None, operational=False, weapon_session=None):
    """One last boundary for both legacy output adapters.

    Missing evidence is a stop, not a compatible old-success fallback. The P1
    explicit mock session can supply offline preparation, never a live-ready CSV.
    """
    if not isinstance(session, PreparationSession) or not isinstance(records, dict):
        return {'valid': False, 'reasons': ['CURRENT_PREPARATION_EVIDENCE_REQUIRED']}
    record = records.get(item.candidate_asin)
    if not isinstance(record, dict):
        return {'valid': False, 'reasons': ['CURRENT_TARGET_FACT_REQUIRED']}
    if weapon_session is not None:
        from modules.product_review import WeaponImageReviewSession
        from modules.sg_beta_workbench import capture_weapon_review
        try:
            current = weapon_session.current(item) if isinstance(weapon_session, WeaponImageReviewSession) else None
            _, bound_text, _, _ = _sources(record)
            if current is None or bound_text is None or bound_text.facts_by_asin[item.candidate_asin] != current.text:
                raise PreparationError('CURRENT_PRODUCT_TEXT_BINDING_MISMATCH')
            record = copy.deepcopy(record)
            record['weapon'] = capture_weapon_review(item, weapon_session, images={
                'candidate_asin': item.candidate_asin, 'provider': current.image_provider,
                'capture_error': current.image_capture_error, 'image_urls': list(current.image_urls),
                'root_category_id': current.root_category_id,
            })
        except (ValueError, RuntimeError, KeyError):
            return {'valid': False, 'reasons': ['CURRENT_PRODUCT_TEXT_OR_IMAGE_BINDING_MISMATCH']}
    result = session.assess(record)
    if not result['valid']:
        return result
    try:
        source = recommendation_identity(record, item.marketplace)
        category, brand = record['category'], record['brand']
        item_brand_id = getattr(item, 'confirmed_brand_id', getattr(item, 'recommended_brand_id', None))
        item_brand_name = getattr(item, 'confirmed_brand_name', getattr(item, 'recommended_brand_name', ''))
        item_no_brand = (item.no_brand_selected_by_user if hasattr(item, 'no_brand_selected_by_user')
                         else item.brand_status == 'NO_BRAND_CONFIRMED')
        if (item.marketplace != session.scope.marketplace or item.input_safety_state != 'GATE_ELIGIBLE'
                or source != (item.source_type, item.source_asin, item.product_title,
                              item.keepa_brand, item.keepa_category, item.resolver_input_title)
                or category['category_id'] != item.recommended_category_id
                or category['category_path'] != item.recommended_category_path
                or brand['brand_id'] != item_brand_id or brand['brand_name'] != item_brand_name
                or brand['is_no_brand'] != item_no_brand):
            raise PreparationError('PREPARATION_ITEM_BINDING_MISMATCH')
        if operational:
            session.require_operational(record)
    except (ValueError, KeyError, AttributeError) as exc:
        return {'valid': False, 'reasons': [str(exc) if isinstance(exc, PreparationError)
                                          else 'PREPARATION_ITEM_BINDING_MISMATCH']}
    return result


def recommendation_identity(record, marketplace):
    candidates, _, _, _ = _sources(record)
    row = next(c for c in candidates.rows if c.candidate_asin == record['asin'])
    return (row.source_type, row.source_asin, row.product_title, row.brand, row.category, row.input_title)


PREPARATION_RECHECK_MESSAGE = (
    '現在の準備根拠を確認できません。対象商品のJP Fact・市場／ショップ・最新Category／Brand完全一覧・'
    '全ショップ既出品資料を再確認してください。保存済み確認だけでは出力できません。'
)
