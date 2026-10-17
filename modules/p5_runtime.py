"""P5 composition boundary, not an approval source or a deployment entry point.

Import/configuration performs no I/O. Installation is a separate explicit step.
An execution permit is injected by a trusted, separately approved integration;
there is deliberately no JSON/environment/UI permit loader. Synthetic transports
never acquire official provenance. Existing PH/SG runtimes do not use this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from modules.beta_work_store import BetaWorkStore
from modules.beta_workbench import BetaWorkBench
from modules.classification_workflow import ClassificationWorkflow
from modules.preparation_validity import PreparationSession, PreparationError
from modules.sg_continuous_runtime import SGContinuousLedger, _digest
from modules.sg_live_validation import LiveValidationStopped, OpenAIValidationBudget


class P5Stopped(LiveValidationStopped):
    """Safe reason only; never expose payloads, credentials or raw exceptions."""


@dataclass(frozen=True)
class P5Scope:
    run_id: str
    marketplace: str
    shop_id: str
    credential_ref: str
    release: str
    execution_target: str
    root: str
    store_id: str
    asins: tuple[str, ...]
    category_ids: tuple[int, ...]
    # Exact, pre-reviewed Finder queries; no fallback or page expansion.
    finder_queries: tuple[str, ...]
    keepa_requests: int
    keepa_products: int
    keepa_tokens: int
    shopee_requests: int
    bridge_requests: int
    auth_requests: int
    image_requests: int
    openai_requests: int
    openai_usd: str
    openai_models: tuple[str, ...]
    openai_input_bound: int
    openai_output_tokens: int
    openai_images: int
    bridge_spreadsheet_id: str = ''
    # Opt-in two-stage discovery contract. Zero preserves fixed-ASIN grants.
    preparation_limit: int = 0
    resolver_inputs: tuple[str, ...] = ()

    def validate(self):
        from modules.p5_candidates import validate_discovery_scope
        validate_discovery_scope(self)
        identifiers = (self.run_id, self.credential_ref, self.execution_target, self.store_id)
        if (any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', v) for v in identifiers)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', self.run_id)
                or self.marketplace not in {'PH', 'SG'}
                or not isinstance(self.shop_id, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', self.shop_id)
                or not re.fullmatch(r'[0-9a-f]{40}', self.release)
                or not Path(self.root).is_absolute()
                or any(type(v) is not tuple for v in (self.asins, self.category_ids, self.finder_queries, self.openai_models))
                or not self.asins or len(self.asins) != len(set(self.asins))
                or any(not re.fullmatch(r'[A-Z0-9]{10}', a) for a in self.asins)
                or not self.category_ids or len(set(self.category_ids)) != len(self.category_ids)
                or any(type(c) is not int or c <= 0 for c in self.category_ids)):
            raise P5Stopped('P5_SCOPE_BINDING_INVALID')
        for name in ('keepa_requests', 'keepa_products', 'keepa_tokens', 'shopee_requests',
                     'bridge_requests', 'auth_requests', 'image_requests', 'openai_requests',
                     'openai_input_bound', 'openai_output_tokens', 'openai_images'):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= 1000000:
                raise P5Stopped('P5_FINITE_LIMIT_REQUIRED')
        if not isinstance(self.openai_usd, str):
            raise P5Stopped('P5_DECIMAL_BUDGET_REQUIRED')
        money = Decimal(self.openai_usd)
        if (not money.is_finite() or not 0 <= money <= 1
                or not set(self.openai_models) <= set(OpenAIValidationBudget._PRICES)
                or self.openai_images > 3 or self.openai_output_tokens > 1200
                or self.openai_input_bound > 272000):
            raise P5Stopped('P5_PAID_PROFILE_INVALID')
        for raw in self.finder_queries:
            query = json.loads(raw)
            if (not isinstance(query, dict) or type(query.get('page')) is not int or query['page'] != 0
                    or type(query.get('perPage')) is not int or not 1 <= query['perPage'] <= 50):
                raise P5Stopped('P5_FINDER_PLAN_INVALID')

    @property
    def digest(self):
        value = asdict(self)
        if self.preparation_limit == 0 and not self.resolver_inputs:
            # Existing installed fixed-ASIN scopes retain their exact binding.
            value.pop('preparation_limit')
            value.pop('resolver_inputs')
        return _digest(value)

    @property
    def directory(self):
        return Path(self.root).resolve() / self.run_id / self.marketplace / self.shop_id

    @property
    def db_path(self):
        return self.directory / 'work.sqlite3'


@dataclass(frozen=True)
class P5ExecutionPermit:
    """Trusted adapter input, analogous to P1's exact AutoRuleApproval.

    This object does NOT prove human origin. No installed loader creates it.
    Official endpoint specifications and actual release/target must be confirmed
    outside the UI before a live adapter may inject it. Offline permits cannot
    produce official Category/Brand evidence or operational output.
    """
    scope_digest: str
    authorization_ref: str
    primary_source_refs: tuple[str, ...] = ()
    offline_test: bool = False
    openai_pricing_ref: str = ''

    def require(self, scope, *, operational=False):
        if (self.scope_digest != scope.digest or not self.authorization_ref.strip()
                or type(self.offline_test) is not bool):
            raise P5Stopped('P5_EXECUTION_NOT_APPROVED')
        if not self.offline_test and (type(self.primary_source_refs) is not tuple or len(self.primary_source_refs) != 3
                or any(not isinstance(ref, str) or not ref.strip() for ref in self.primary_source_refs)):
            raise P5Stopped('PRIMARY_SOURCE_UNVERIFIED')
        if operational and self.offline_test:
            raise P5Stopped('P5_SYNTHETIC_IS_NOT_OFFICIAL')


class P5Ledger(SGContinuousLedger):
    """Reuse SG process lease, checksum, fsync/atomic replace and sticky failure.

    P5 keeps maximum reservations for the whole approved run. Actual usage is
    evidence, not an automatic refund. Missing/failed receipts stop the run.
    """
    def _initial_data(self):
        value = {'grant_digest': self.grant.digest, 'reservations': [], 'stopped': False}
        if self.grant.preparation_limit:
            value['candidates'] = {'requests': {}, 'finder': {}, 'proposals': [], 'batches': {}, 'selections': {}}
        return value

    def _validate(self):
        d = self.data
        expected = {'grant_digest', 'reservations', 'stopped', 'checksum'}
        if self.grant.preparation_limit:
            expected.add('candidates')
        if (set(d) != expected
                or d['grant_digest'] != self.grant.digest
                or d['checksum'] != _digest({k: v for k, v in d.items() if k != 'checksum'})
                or type(d['stopped']) is not bool or not isinstance(d['reservations'], list)):
            raise P5Stopped('P5_LEDGER_BINDING_INVALID')
        ids = set()
        for r in d['reservations']:
            if (set(r) != {'id', 'kind', 'units', 'tokens', 'usd', 'state', 'actual_tokens'}
                    or r['id'] in ids or r['kind'] not in self.limits
                    or type(r['units']) is not int or r['units'] < 0
                    or type(r['tokens']) is not int or r['tokens'] < 0
                    or r['state'] not in {'RESERVED', 'COMPLETE', 'UNKNOWN'}
                    or not Decimal(r['usd']).is_finite() or Decimal(r['usd']) < 0
                    or (r['actual_tokens'] is not None and
                        (type(r['actual_tokens']) is not int or r['actual_tokens'] < 0
                         or (r['actual_tokens'] > r['tokens'] and r['state'] != 'UNKNOWN')))):
                raise P5Stopped('P5_LEDGER_RECORD_INVALID')
            ids.add(r['id'])
        self._check_limits()
        if self.grant.preparation_limit:
            from modules.p5_candidates import validate_saved_candidates
            validate_saved_candidates(self)

    @property
    def limits(self):
        return {k: getattr(self.grant, k + '_requests') for k in
                ('keepa', 'shopee', 'bridge', 'auth', 'image', 'openai')}

    def _check_limits(self):
        rows = self.data['reservations']
        if (any(sum(r['kind'] == k for r in rows) > cap for k, cap in self.limits.items())
                or sum(r['units'] for r in rows if r['kind'] == 'keepa') > self.grant.keepa_products
                or sum(r['tokens'] for r in rows) > self.grant.keepa_tokens
                or sum((Decimal(r['usd']) for r in rows), Decimal(0)) > Decimal(self.grant.openai_usd)):
            raise P5Stopped('P5_BUDGET_EXHAUSTED')

    def require_active(self):
        self.require_current()
        if self.data['stopped'] or any(r['state'] != 'COMPLETE' for r in self.data['reservations']):
            raise P5Stopped('P5_UNRESOLVED_CONSUMPTION')

    def require_current(self):
        with self._lock:
            if self._lease.closed:
                raise P5Stopped('P5_PROCESS_LEASE_CLOSED')
            super().require_current()

    def reserve(self, kind, *, units=0, tokens=0, usd=Decimal(0), candidate_request=None):
        with self._lock:
            self.require_current()
            if self.data['stopped']:
                raise P5Stopped('P5_UNRESOLVED_CONSUMPTION')
            if (kind not in self.limits or type(units) is not int or units < 0
                    or type(tokens) is not int or tokens < 0 or not usd.is_finite() or usd < 0):
                raise P5Stopped('P5_RESERVATION_INVALID')
            record = {'id': uuid4().hex, 'kind': kind, 'units': units, 'tokens': tokens,
                      'usd': str(usd), 'state': 'RESERVED', 'actual_tokens': None}
            self.data['reservations'].append(record)
            try:
                self._check_limits()
            except Exception:
                self.data['reservations'].pop()
                raise
            if candidate_request is not None:
                self.data['candidates']['requests'][record['id']] = candidate_request
            self.persist()  # Must succeed before every physical send.
            return record['id']

    def finish(self, reservation, *, success, actual_tokens=None, finder_asins=None):
        with self._lock:
            self.require_current()
            row = next((r for r in self.data['reservations'] if r['id'] == reservation), None)
            if row is None or row['state'] != 'RESERVED':
                raise P5Stopped('P5_RESERVATION_NOT_CURRENT')
            row['state'] = 'COMPLETE' if success else 'UNKNOWN'
            row['actual_tokens'] = actual_tokens
            self.data['stopped'] |= not success
            if finder_asins is not None:
                self.data['candidates']['finder'][reservation] = list(finder_asins)
            self.persist()


def initialize_p5_ledger(scope):
    """Separate installation operation. Tests use temporary synthetic roots only.

    No UI/constructor calls this. Existing claim, ledger, cache or DB is never
    reset. A partial installation stays visible and requires explicit recovery.
    """
    scope.validate()
    store = BetaWorkStore(scope.db_path, marketplace=scope.marketplace, shop_id=scope.shop_id)
    if store.store_id != scope.store_id:
        raise P5Stopped('P5_STORE_ID_MISMATCH')
    claim = scope.directory / 'claim.json'
    with claim.open('x', encoding='utf-8') as file:
        json.dump({'scope_digest': scope.digest}, file)
        file.flush()
        os.fsync(file.fileno())
    if (scope.directory / 'ledger.json').exists():
        raise P5Stopped('P5_EXISTING_LEDGER_MUST_NOT_RESET')
    ledger = P5Ledger(scope.directory / 'ledger.json', scope, initialize=True)
    ledger.close()


class P5WorkBench(BetaWorkBench):
    def ingest(self, records, **kwargs):
        import copy
        records = copy.deepcopy(tuple(records))
        for record in records:
            self.session.runtime.require_preparation_target(record)
            if self.session.runtime.scope.preparation_limit:
                record['source']['p5_selection'] = self.session.runtime.candidates.require_record(record)
        return super().ingest(records, **kwargs)

    def _require_scope(self):
        if self.session.runtime.scope.preparation_limit:
            self.session.runtime.require_current()
        return super()._require_scope()


class P5PreparationSession(PreparationSession):
    def __init__(self, runtime):
        self.runtime = runtime
        super().__init__(runtime.scope.marketplace, runtime.scope.shop_id)

    def require_operational(self, record):
        self.runtime.require_output_proof(record)
        super().require_operational(record)

    def bind_product(self, record):
        self.runtime.require_preparation_target(record)
        return super().bind_product(record)

    def _require_record(self, record):
        self.runtime.require_preparation_target(record)
        return super()._require_record(record)

    def _require_safe_classification(self, record):
        self.runtime.require_preparation_target(record)
        result = self.assess(record)
        if (result.get('safety_reasons') or record.get('manual_exclude') or record.get('body_excluded')
                or record.get('review_pending') or 'safety_reasons' not in result
                or set(result['reasons']) - {'CATEGORY_CONFIRMATION_REQUIRED', 'BRAND_CONFIRMATION_REQUIRED'}):
            raise PreparationError('P5_SAFETY_OR_CURRENT_EVIDENCE_REQUIRED')

    def confirm_category(self, record, category_id, *, human_verified):
        if category_id not in self.runtime.scope.category_ids:
            raise PreparationError('P5_LEAF_OUTSIDE_SCOPE')
        if self.runtime.scope.preparation_limit:
            self._require_safe_classification(record)
        return super().confirm_category(record, category_id, human_verified=human_verified)

    def confirm_brand(self, record, brand_id, *, human_verified):
        if self.runtime.scope.preparation_limit:
            self._require_safe_classification(record)
        return super().confirm_brand(record, brand_id, human_verified=human_verified)


class P5Runtime:
    """No I/O until explicit start; no communication without injected permit."""
    def __init__(self, scope, *, permit=None, credentials=None, execution_identity=None):
        scope.validate()
        self.scope, self.permit = scope, permit
        self._credentials = credentials
        self._execution_identity = execution_identity
        self.ledger = self.workflow = None
        self._store = None
        self.category_receipt = None
        self.attributes = {}
        self.weapon_receipts = {}

    @property
    def candidates(self):
        from modules.p5_candidates import P5Candidates
        return P5Candidates(self)

    def require_preparation_target(self, record):
        if self.scope.preparation_limit:
            self.candidates.require_record(record)
        elif record.get('asin') not in self.scope.asins:
            raise PreparationError('P5_PRODUCT_OUTSIDE_SCOPE')

    def require_permit(self, *, operational=False):
        if not isinstance(self.permit, P5ExecutionPermit):
            raise P5Stopped('P5_EXECUTION_NOT_APPROVED')
        self.permit.require(self.scope, operational=operational)
        if not self.permit.offline_test and (self._execution_identity is None or
                self._execution_identity() != (self.scope.release, self.scope.execution_target)):
            raise P5Stopped('P5_RELEASE_EXECUTION_TARGET_UNVERIFIED')

    def start(self):
        self.require_permit()
        directory = self.scope.directory
        if self.ledger is not None:
            self.require_current()
            return
        if (not directory.is_dir() or not (directory / 'ledger.json').is_file()
                or json.loads((directory / 'claim.json').read_text('utf-8')) != {'scope_digest': self.scope.digest}):
            raise P5Stopped('P5_INSTALLATION_REQUIRED')
        store = BetaWorkStore(self.scope.db_path, marketplace=self.scope.marketplace, shop_id=self.scope.shop_id)
        if store.store_id != self.scope.store_id:
            raise P5Stopped('P5_STORE_ID_MISMATCH')
        ledger = P5Ledger(directory / 'ledger.json', self.scope, initialize=False)
        try:
            ledger.require_active()
            self.ledger = ledger
            self._store = store
            self.workflow = ClassificationWorkflow(P5WorkBench(store, P5PreparationSession(self)))
        except Exception:
            ledger.close()
            self.ledger = None
            self._store = None
            raise

    def require_current(self):
        self.require_permit()
        if self.ledger is None or self._store is None:
            raise P5Stopped('P5_EXPLICIT_START_REQUIRED')
        self.ledger.require_current()
        if self.ledger.data['stopped']:
            raise P5Stopped('P5_UNRESOLVED_CONSUMPTION')
        store = self.workflow.bench.store if self.workflow is not None else self._store
        # A read-only identity check works inside P2's write transaction too.
        with sqlite3.connect(store.path.as_uri() + '?mode=ro', uri=True) as conn:
            meta = dict(conn.execute('SELECT key,value FROM meta'))
        if (store.path != self.scope.db_path or store.store_id != self.scope.store_id
                or store.marketplace != self.scope.marketplace or store.shop_id != self.scope.shop_id
                or self.ledger.grant.digest != self.scope.digest
                or any(meta.get(k) != v for k, v in {'schema': BetaWorkStore.SCHEMA,
                    'store_id': self.scope.store_id, 'marketplace': self.scope.marketplace,
                    'shop_id': self.scope.shop_id}.items())
                or json.loads((self.scope.directory / 'claim.json').read_text('utf-8')) != {'scope_digest': self.scope.digest}):
            raise P5Stopped('P5_CURRENT_BINDING_CHANGED')

    def secrets(self):
        self.require_current()
        from modules.p5_transport import P5Secrets
        if (not isinstance(self._credentials, P5Secrets)
                or self._credentials.credential_ref != self.scope.credential_ref
                or self._credentials.marketplace != self.scope.marketplace
                or self._credentials.shop_id != self.scope.shop_id):
            raise P5Stopped('P5_APPROVED_CREDENTIAL_ADAPTER_REQUIRED')
        return self._credentials

    def refresh_access_token(self):
        """Explicit bounded Bridge read. Never write credentials or auto-refresh."""
        from modules.p5_transport import P5BridgeTransport
        from modules.shopee_access_token_source import GoogleSheetAccessTokenSource
        secrets = self.secrets()
        if not secrets.google_credential_file or not self.scope.bridge_spreadsheet_id:
            raise P5Stopped('P5_APPROVED_BRIDGE_REFERENCE_REQUIRED')
        bridge = P5BridgeTransport(self, credential_file=secrets.google_credential_file,
                                  spreadsheet_id=self.scope.bridge_spreadsheet_id)
        token = GoogleSheetAccessTokenSource(self.scope.bridge_spreadsheet_id, transport=bridge).get_access_token(
            self.scope.marketplace, int(self.scope.shop_id))
        self._credentials = replace(secrets, shopee_credentials=replace(secrets.shopee_credentials, access_token=token.value))

    def amazon_client(self):
        from modules.p5_transport import make_keepa_client
        return make_keepa_client(self, self.secrets())

    def catalog_client(self):
        from modules.p5_transport import make_catalog_client
        return make_catalog_client(self, self.secrets())

    def require_output_proof(self, record):
        self.require_permit(operational=True)
        self.require_current()
        self.require_preparation_target(record)
        session = self.workflow.session
        receipt = self.category_receipt
        if (receipt is None or receipt['session'] != session.scope
                or receipt['binding'] != session.current_classification_binding()
                or not receipt['official']
                or record['category']['category_id'] not in self.scope.category_ids):
            raise PreparationError('P5_CURRENT_OFFICIAL_CATEGORY_REQUIRED')
        self._require_catalog_client(receipt['client'], record['category']['category_id'])
        if not receipt['client'].uses_default_transport:
            raise PreparationError('P5_OFFICIAL_CATEGORY_TRANSPORT_CHANGED')
        if any((record.get(k) or {}).get('authority') != 'HUMAN' for k in ('category', 'brand')):
            raise PreparationError('P5_INITIAL_HUMAN_ONLY')
        from modules.image_inspection_policy import select_image_inspection
        from modules.sg_beta_facts import digest
        images = record['weapon']['images']
        if select_image_inspection(marketplace=self.scope.marketplace,
                root_category_id=images['root_category_id'], provider=images['provider'],
                guardrail_status='SAFE') in {'TARGET_ROOT', 'ROOT_UNKNOWN'}:
            observed = self.weapon_receipts.get(record['asin'])
            expected = (digest([record['facts'], record['source'], record['weapon']['images']]),
                        digest(record['weapon'].get('inspection')))
            if observed != expected:
                raise PreparationError('P5_CURRENT_IMAGE_ACQUISITION_REQUIRED')

    def invalidate_catalog(self):
        self.category_receipt = None
        self.attributes.clear()
        self.workflow.session.begin_catalog_refresh()

    def acquire_catalog(self, client):
        from modules.category_ai_core import CategoryCatalog, CategoryNode
        self.require_current()
        self.invalidate_catalog()
        self._require_client_identity(client)
        rows = client.get_categories(self.scope.marketplace, strict=True)
        by_id = {r['category_id']: r for r in rows}
        def path(cid, ancestors=()):
            if cid in ancestors or cid not in by_id:
                raise P5Stopped('P5_CATEGORY_HIERARCHY_INVALID')
            row = by_id[cid]
            parent = row['parent_category_id']
            return (path(parent, (*ancestors, cid)) + ' > ' if parent else '') + row['category_name']
        catalog = CategoryCatalog(self.scope.marketplace, uuid4().hex, tuple(CategoryNode(
            r['category_id'], r['parent_category_id'] or None, r['category_name'], path(r['category_id']),
            r['is_leaf']) for r in rows))
        for cid in self.scope.category_ids:
            if catalog.get(cid) is None or not catalog.get(cid).is_leaf:
                raise P5Stopped('P5_APPROVED_LEAF_MISSING')
        self.workflow.supply_catalog(catalog, reference=uuid4().hex, revision=uuid4().hex)
        self.category_receipt = {'session': self.workflow.session.scope,
            'binding': self.workflow.session.current_classification_binding(),
            'client': client,
            'official': client.uses_default_transport and not self.permit.offline_test}
        return catalog

    def acquire_brand(self, client, category_id):
        self.require_current()
        self._require_catalog_client(client, category_id)
        return self.workflow.acquire_brand(client, category_id, max_pages=10)

    def _require_catalog_client(self, client, category_id):
        self._require_client_identity(client)
        if (category_id not in self.scope.category_ids or self.category_receipt is None
                or self.category_receipt['binding'] != self.workflow.session.current_classification_binding()):
            raise P5Stopped('P5_CURRENT_CATALOG_ROUTE_REQUIRED')

    def _require_client_identity(self, client):
        from modules.p5_transport import P5CatalogPolicy
        from modules.shopee_catalog_client import ShopeeCatalogClient, SHOPEE_PARTNER_BASE_URL
        # Do not borrow the default-transport flag from a mock/legacy subclass.
        if (type(client) is not ShopeeCatalogClient
                or type(getattr(client, 'request_policy', None)) is not P5CatalogPolicy
                or client.request_policy.runtime is not self
                or client.marketplace != self.scope.marketplace
                or str(client.credentials.shop_id) != self.scope.shop_id
                or client.base_url != SHOPEE_PARTNER_BASE_URL or getattr(client, 'ledger', None) is not self.ledger):
            raise P5Stopped('P5_APPROVED_CATALOG_ROUTE_REQUIRED')

    def acquire_attributes(self, client, category_id):
        self.require_current()
        self.attributes[category_id] = {'state': 'FAILED', 'tree_count': None,
            'session': self.workflow.session.scope,
            'catalog_binding': self.workflow.session.current_classification_binding()}
        self._require_catalog_client(client, category_id)
        result = client.get_attribute_trees(self.scope.marketplace, (category_id,))[0]
        self.attributes[category_id] = {'state': 'FETCHED', 'tree_count': len(result['attribute_tree']),
            'tree': result['attribute_tree'], 'session': self.workflow.session.scope,
            'catalog_binding': self.category_receipt['binding']}
        return self.attributes[category_id]

    def attribute_status(self, category_id):
        current = self.attributes.get(category_id)
        if (current is None or current.get('session') != self.workflow.session.scope
                or self.category_receipt is None
                or current.get('catalog_binding') != self.workflow.session.current_classification_binding()):
            return {'state': 'NOT_FETCHED', 'tree_count': None}
        return dict(current)

    def output(self, expected, *, reserve_copy=False):
        self.require_permit(operational=True)
        self.require_current()
        return self.workflow.bench.output(expected, reserve_copy=reserve_copy, operational=True)

    def close(self):
        if self.ledger is not None:
            self.ledger.close()
        self.ledger = self.workflow = self.category_receipt = None
        self._store = None
        self.attributes.clear()
        self.weapon_receipts.clear()
