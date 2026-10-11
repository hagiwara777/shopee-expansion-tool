"""Finite SG business authorization across batches. No automatic initialization.

An authorization reference records a separately approved policy; parsing it does
not establish approval. Legacy limited Grants keep their own contract and records.
"""
from dataclasses import dataclass, asdict
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re

from modules.sg_live_validation import LiveValidationStopped, BudgetedOpenAISession, OpenAIValidationBudget
from modules.sg_live_runtime import (SGRunLedger, PersistentSGOpenAIBudget,
    RefreshingSGCatalogClient, existing_sg_client_factory, ScopedSGCategoryEngine)
from modules.category_mapper_store import CategoryMapperStore, default_category_mapper_db_path


def _digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class SGContinuousPolicy:
    operation_id: str
    shop_id: int
    bridge_spreadsheet_id: str
    catalog_request_limit: int
    attribute_request_limit: int
    brand_page_limit: int
    brand_total_page_limit: int
    keepa_request_limit: int
    openai_limit_usd: str
    authorization_ref: str

    def validate(self, db_path):
        if (not isinstance(self.operation_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", self.operation_id)
                or type(self.shop_id) is not int or self.shop_id <= 0
                or any(not isinstance(s, str) or not s.strip() for s in
                       (self.bridge_spreadsheet_id, self.authorization_ref))
                or any(type(n) is not int or not 0 <= n <= 10000 for n in
                       (self.catalog_request_limit, self.attribute_request_limit, self.brand_total_page_limit, self.keepa_request_limit))
                or type(self.brand_page_limit) is not int or not 1 <= self.brand_page_limit <= 50
                or not isinstance(self.openai_limit_usd, str)):
            raise LiveValidationStopped("Invalid finite SG continuous policy")
        limit = Decimal(self.openai_limit_usd)
        if not limit.is_finite() or limit < 0:
            raise LiveValidationStopped("Invalid finite SG paid ceiling")
        if Path(db_path).resolve() == default_category_mapper_db_path().resolve():
            raise LiveValidationStopped("PH/default DB cannot be used for continuous SG")

    @property
    def digest(self):
        return _digest(asdict(self))

    @classmethod
    def from_file(cls, path):
        return cls(**json.loads(Path(path).read_text(encoding="utf-8-sig")))


class SGContinuousScope:
    """Only a validated, currently admitted bundle can authorize product work."""
    def __init__(self, policy, db_path):
        policy.validate(db_path)
        self.policy, self.db_path = policy, Path(db_path).resolve()
        self.shop_id, self.brand_page_limit = policy.shop_id, policy.brand_page_limit
        self.clear()

    def clear(self):
        self.allowed_asins = ()
        self._loader = None
        self._categories = set()

    def accept(self, loader):
        from modules.product_review_transport import SGProductEvidenceLoader
        self.clear()
        if not isinstance(loader, SGProductEvidenceLoader) or not loader._gate_rows:
            raise LiveValidationStopped("Validated SG evidence bundle required")
        loader.require_current_safety_clear()
        self.allowed_asins = tuple(loader._gate_rows)
        self._loader = loader

    def require_client(self, client, store):
        if (client.marketplace != "SG" or client.credentials.shop_id != self.shop_id
                or store.db_path.resolve() != self.db_path):
            raise LiveValidationStopped("Continuous SG client/store binding changed")
        store._require_sg_brand_acceptance()

    def require_product(self, item):
        if self._loader is None or item.candidate_asin not in self.allowed_asins:
            raise LiveValidationStopped("Current admitted SG batch required")
        self._loader(item)

    def require_current_safety(self):
        if self._loader is not None:
            self._loader.require_current_safety_clear()

    def authorize_category(self, item, store):
        from modules.category_mapper_sg import _require_sg_brand_product
        self.require_product(item)
        self._categories.add(_require_sg_brand_product(item, store))

    def require_brand_category(self, category_id):
        if category_id not in self._categories or self._loader is None:
            raise LiveValidationStopped("Current human-confirmed Category required")

    def reserve_brand_page(self, category_id):
        # The persistent ledger charges every actual page; this is only scope.
        self.require_brand_category(category_id)


class SGContinuousLedger(SGRunLedger):
    """Reuse the process lease; checksum and precharge a finite cumulative record."""
    def __init__(self, path, policy, *, initialize=False):
        self.failed = False
        self.scope = None
        super().__init__(path, policy, initialize=initialize)

    def _initial_data(self):
        return {"grant_digest": self.grant.digest, "catalog_requests": 0, "attribute_requests": 0,
                "keepa_requests": 0,
                "brand_page_counts": {}, "openai": {"limit_usd": self.grant.openai_limit_usd,
                "reserved_upper_bound_usd": "0", "requests": 0, "stopped": False}}

    @classmethod
    def validate_saved(cls, path, policy):
        """Inspect an atomic saved record without acquiring or creating a lease."""
        validator = cls.__new__(cls)
        validator.grant = policy
        validator.data = json.loads(Path(path).read_text(encoding="utf-8"))
        validator._validate()

    def _validate(self):
        d = self.data
        if (set(d) != {"grant_digest", "catalog_requests", "attribute_requests", "keepa_requests", "brand_page_counts", "openai", "checksum"}
                or d["grant_digest"] != self.grant.digest
                or d["checksum"] != _digest({k: v for k, v in d.items() if k != "checksum"})
                or not isinstance(d["brand_page_counts"], dict)):
            raise LiveValidationStopped("Continuous SG ledger binding/integrity failed")
        counts = [(d["catalog_requests"], self.grant.catalog_request_limit),
                  (d["keepa_requests"], self.grant.keepa_request_limit),
                  (d["attribute_requests"], self.grant.attribute_request_limit)]
        counts += [(n, self.grant.brand_total_page_limit) for n in d["brand_page_counts"].values()]
        b = d["openai"]
        if (any(type(n) is not int or not 0 <= n <= cap for n, cap in counts)
                or any(not re.fullmatch(r"[1-9][0-9]*", k) for k in d["brand_page_counts"])
                or sum(d["brand_page_counts"].values()) > self.grant.brand_total_page_limit
                or set(b) != {"limit_usd", "reserved_upper_bound_usd", "requests", "stopped"}
                or b["limit_usd"] != self.grant.openai_limit_usd
                or type(b["requests"]) is not int or b["requests"] < 0 or type(b["stopped"]) is not bool
                or not Decimal(b["reserved_upper_bound_usd"]).is_finite()
                or not 0 <= Decimal(b["reserved_upper_bound_usd"]) <= Decimal(b["limit_usd"])):
            raise LiveValidationStopped("Invalid continuous SG ledger counters")

    def require_current(self):
        if self.failed:
            raise LiveValidationStopped("Continuous SG persistence stopped")
        try:
            observed = json.loads(self.path.read_text(encoding="utf-8"))
            if observed != self.data:
                raise LiveValidationStopped("Continuous SG ledger changed while open")
            self._validate()
        except Exception:
            self.failed = True
            raise LiveValidationStopped("Continuous SG ledger requires recovery") from None

    def persist(self):
        if self.failed:
            raise LiveValidationStopped("Continuous SG persistence stopped")
        with self._lock:
            self.data["checksum"] = _digest({k: v for k, v in self.data.items() if k != "checksum"})
            temporary = self.path.with_suffix(".pending")
            try:
                with temporary.open("w", encoding="utf-8") as file:
                    json.dump(self.data, file, sort_keys=True)
                    file.flush()
                    os.fsync(file.fileno())
                temporary.replace(self.path)
            except Exception:
                self.failed = True
                raise LiveValidationStopped("SG reservation could not be persisted") from None

    def reserve_catalog_call(self, kind, category_id=None):
        with self._lock:
            self.require_current()
            if kind == "brand":
                self.scope.require_brand_category(category_id)
                counts = self.data["brand_page_counts"]
                if sum(counts.values()) >= self.grant.brand_total_page_limit:
                    raise LiveValidationStopped("Continuous SG Brand budget exhausted")
                counts[str(category_id)] = counts.get(str(category_id), 0) + 1
            elif kind in {"catalog", "attribute"}:
                if kind == "attribute":
                    self.scope.require_brand_category(category_id)
                key = kind + "_requests"
                if self.data[key] >= getattr(self.grant, kind + "_request_limit"):
                    raise LiveValidationStopped("Continuous SG request budget exhausted")
                self.data[key] += 1
            else:
                raise LiveValidationStopped("Unsupported SG endpoint")
            self.persist()

    def reserve_keepa_request(self):
        with self._lock:
            self.require_current()
            if self.data['keepa_requests'] >= self.grant.keepa_request_limit:
                raise LiveValidationStopped('Continuous Keepa send budget exhausted')
            self.data['keepa_requests'] += 1
            self.persist()


class ContinuousOpenAIBudget(PersistentSGOpenAIBudget):
    def __init__(self, ledger):
        # Reuse the legacy request ceilings/reservation implementation, while
        # the new explicit finite policy owns the cumulative authorization.
        ledger.require_current()
        saved = ledger.data['openai']
        limit = Decimal(saved['limit_usd'])
        if limit <= 0:
            raise LiveValidationStopped('Paid SG execution has no authorized budget')
        OpenAIValidationBudget.__init__(self, limit_usd=min(limit, Decimal('1')))
        self.limit_usd = limit
        self._runtime_ledger = ledger
        self.reserved_usd = Decimal(saved['reserved_upper_bound_usd'])
        self.request_count, self.stopped = saved['requests'], saved['stopped']

    def summary(self):
        result = super().summary()
        result['limit_usd'] = self._runtime_ledger.grant.openai_limit_usd
        return result

    def reserve(self, payload):
        with self._runtime_ledger._lock:
            self._runtime_ledger.require_current()
            super().reserve(payload)


def _claim_path(policy, claim_dir=None):
    root = (Path(claim_dir) if claim_dir is not None else
            Path(os.environ["LOCALAPPDATA"]) / "ShopeeSG" / "continuous-claims")
    return root / (hashlib.sha256(policy.operation_id.encode()).hexdigest() + ".json")


def _binding(policy, run_path):
    return {"policy_digest": policy.digest, "run_path": str(Path(run_path).resolve())}


def validate_installation(policy, run_path, *, claim_dir=None):
    """Read-only validation; no missing file is reconstructed."""
    run = Path(run_path).resolve()
    policy.validate(run / "validation.sqlite3")
    expected = _binding(policy, run)
    for path in (_claim_path(policy, claim_dir), run / "run-binding.json"):
        if json.loads(path.read_text(encoding="utf-8")) != expected:
            raise LiveValidationStopped("Continuous SG installation binding changed")
    if not (run / "validation.sqlite3").is_file() or not (run / "request-ledger.json").is_file():
        raise LiveValidationStopped("Continuous SG persistence is missing")
    SGContinuousLedger.validate_saved(run / "request-ledger.json", policy)
    CategoryMapperStore.open_existing_sg(run / "validation.sqlite3")


def initialize_continuous_operation(policy, run_path, *, claim_dir=None):
    """Explicit one-time LOCAL setup, only with separately approved persistence.

    Not called by launch/UI. A failed setup leaves its claim to prevent reset.
    """
    run = Path(run_path).resolve()
    policy.validate(run / "validation.sqlite3")
    if run.exists():
        raise LiveValidationStopped("Continuous SG setup requires a new dedicated directory")
    claim = _claim_path(policy, claim_dir)
    claim.parent.mkdir(parents=True, exist_ok=True)
    with claim.open("x", encoding="utf-8") as file:
        json.dump(_binding(policy, run), file)
    run.mkdir(parents=True)
    (run / "run-binding.json").write_text(json.dumps(_binding(policy, run)), encoding="utf-8")
    ledger = SGContinuousLedger(run / "request-ledger.json", policy, initialize=True)
    try:
        store = CategoryMapperStore(run / "validation.sqlite3")
        store.initialize_sg_brand_acceptance()
    finally:
        ledger.close()


class SGContinuousRuntime:
    def __init__(self, *, policy, run_path, fresh_client_factory=None, api_key="", api_session=None,
                 image_session=None, claim_dir=None):
        from modules.category_mapper_sg_brand_workflow import SGBrandWorkflow
        validate_installation(policy, run_path, claim_dir=claim_dir)
        self.run_path, self.grant = Path(run_path).resolve(), policy
        self.ledger = SGContinuousLedger(self.run_path / "request-ledger.json", policy)
        try:
            self.scope = SGContinuousScope(policy, self.run_path / "validation.sqlite3")
            self.ledger.scope = self.scope
            self.store = CategoryMapperStore.open_existing_sg(self.scope.db_path)
            self.client = RefreshingSGCatalogClient(shop_id=policy.shop_id, ledger=self.ledger,
                fresh_client_factory=fresh_client_factory or existing_sg_client_factory(policy))
            self.category_engine, inspector = None, None
            if Decimal(policy.openai_limit_usd) > 0:
                if not api_key:
                    raise LiveValidationStopped("Approved OpenAI key unavailable")
                from modules.category_ai_leaf_search import LeafSearchEngine, LeafSearchProvider
                from modules.weapon_image_inspection import BudgetedLiveWeaponImageInspector
                budget = ContinuousOpenAIBudget(self.ledger)
                self.category_engine = ScopedSGCategoryEngine(LeafSearchEngine(LeafSearchProvider(api_key,
                    session=BudgetedOpenAISession(budget, session=api_session))), self.scope, self._require_catalog)
                inspector = BudgetedLiveWeaponImageInspector(api_key=api_key, budget=budget,
                    api_session=api_session, image_session=image_session)
            self.workflow = SGBrandWorkflow(store=self.store, client=self.client,
                image_inspector=inspector, live_validation_scope=self.scope)
        except Exception:
            self.ledger.close()
            raise

    def _require_catalog(self):
        self.ledger.require_current()
        self.scope.require_current_safety()
        if self.client.catalog_refresh_failed:
            raise LiveValidationStopped("Current SG Category acquisition required")

    def refresh_catalog(self):
        # Reuse the existing full acquisition/current-failure contract.
        from modules.sg_live_runtime import SGLiveRuntime
        return SGLiveRuntime.refresh_catalog(self)

    def close(self):
        with self.ledger._lock:
            # Old Expansion/Resolver clients may still reference this budget
            # after a country switch. They cannot spend without the lease.
            self.ledger.failed = True
            self.scope.clear()
            self.workflow.product_review.clear()
            self.ledger.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Explicit approved continuous SG persistence setup; no APIs')
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--run-path', type=Path, required=True)
    parser.add_argument('--initialize', action='store_true', required=True)
    args = parser.parse_args()
    try:
        initialize_continuous_operation(SGContinuousPolicy.from_file(args.policy), args.run_path)
    except Exception:
        print('SG_CONTINUOUS_SETUP_STOPPED')
        raise SystemExit(1) from None
    print('PASS: continuous SG persistence initialized (no API calls)')
