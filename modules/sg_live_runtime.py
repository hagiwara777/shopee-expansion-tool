"""Explicit, bounded SG read-only UI runtime. Import and creation perform no I/O.

A grant describes an already approved run; it never establishes owner approval.
One durable run is pinned to its grant and isolated DB. No normal activation.
"""
from dataclasses import dataclass, replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from threading import RLock

from modules.category_mapper_store import CategoryMapperStore
from modules.category_mapper_sg import build_sg_category_catalog_csv, parse_sg_category_catalog
from modules.category_mapper_sg_brand_workflow import SGBrandWorkflow
from modules.product_review import WeaponImageReviewSession
from modules.shopee_catalog_client import ShopeeCatalogClient, load_shopee_catalog_credentials
from modules.shopee_access_token_source import GoogleSheetAccessTokenSource
CLAIM_DIR = Path(__file__).resolve().parents[1] / "outputs" / "sg-live-ui" / "claims"

from modules.sg_live_validation import SGLiveValidationScope, LiveValidationStopped, OpenAIValidationBudget, BudgetedOpenAISession


@dataclass(frozen=True)
class SGLiveRunGrant:
    allowed_asins: tuple[str, ...]
    shop_id: int
    bridge_spreadsheet_id: str
    brand_category_ids: tuple[int, ...]
    brand_page_limit: int
    catalog_request_limit: int
    attribute_request_limit: int
    openai_limit_usd: str
    authorization_ref: str

    def validate(self, db_path):
        SGLiveValidationScope(self.allowed_asins, self.shop_id, db_path,
            self.brand_page_limit, self.brand_category_ids)
        if not isinstance(self.openai_limit_usd,str):
            raise LiveValidationStopped("Explicit decimal OpenAI ceiling required")
        limit = Decimal(self.openai_limit_usd)
        if (not isinstance(self.bridge_spreadsheet_id, str) or not self.bridge_spreadsheet_id.strip()
                or not isinstance(self.authorization_ref, str) or not self.authorization_ref.strip()
                or not self.brand_category_ids
                or any(type(n) is not int or not 1 <= n <= 10 for n in
                       (self.catalog_request_limit, self.attribute_request_limit))
                or not limit.is_finite() or not 0 <= limit <= 1):
            raise LiveValidationStopped("Invalid explicit SG run grant")

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(self.__dict__,sort_keys=True).encode()).hexdigest()

    @classmethod
    def from_file(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["allowed_asins"] = tuple(data["allowed_asins"])
        data["brand_category_ids"] = tuple(data["brand_category_ids"])
        return cls(**data)


class SGRunLedger:
    def __init__(self, path, grant):
        self.path, self.grant = Path(path), grant
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # OS lock survives reruns, releases on process exit, prevents parallel spend.
        self._lease = (self.path.parent / "runtime.lock").open("a+b")
        self._lease.seek(0)
        if self._lease.read(1) == b"":
            self._lease.write(b"0"); self._lease.flush()
        self._lease.seek(0)
        try:
            import msvcrt
            msvcrt.locking(self._lease.fileno(), msvcrt.LK_NBLCK, 1)
        except ImportError:
            import fcntl
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lease.close()
            raise LiveValidationStopped("SG run is already open") from None
        try:
            if self.path.exists():
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
                self._validate()
            else:
                self.data = {"grant_digest": grant.digest, "catalog_requests": 0,
                    "attribute_requests": 0, "brand_page_counts": {str(cid):0 for cid in grant.brand_category_ids},
                    "openai": {"limit_usd": grant.openai_limit_usd, "reserved_upper_bound_usd":"0", "requests":0,"stopped":False}}
                self.persist()
        except Exception:
            self.close(); raise

    def _validate(self):
        d = self.data
        if (set(d) != {"grant_digest","catalog_requests","attribute_requests","brand_page_counts","openai"}
                or d["grant_digest"] != self.grant.digest
                or set(d["brand_page_counts"]) != {str(cid) for cid in self.grant.brand_category_ids}):
            raise LiveValidationStopped("Existing SG ledger binding changed")
        counts = [(d["catalog_requests"],self.grant.catalog_request_limit),
                  (d["attribute_requests"],self.grant.attribute_request_limit)]
        counts.extend((n,self.grant.brand_page_limit) for n in d["brand_page_counts"].values())
        b=d["openai"]
        if (any(type(n) is not int or not 0 <= n <= cap for n,cap in counts)
                or set(b)!={"limit_usd","reserved_upper_bound_usd","requests","stopped"}
                or b["limit_usd"] != self.grant.openai_limit_usd
                or type(b["requests"]) is not int or b["requests"]<0 or type(b["stopped"]) is not bool
                or not Decimal(b["reserved_upper_bound_usd"]).is_finite()
                or not 0 <= Decimal(b["reserved_upper_bound_usd"]) <= Decimal(b["limit_usd"])):
            raise LiveValidationStopped("Existing SG ledger is invalid")

    def persist(self):
        with self._lock:
            temporary=self.path.with_suffix(".pending")
            temporary.write_text(json.dumps(self.data,sort_keys=True),encoding="utf-8")
            temporary.replace(self.path)

    def reserve_catalog_call(self, kind, category_id=None):
        with self._lock:
            if kind=="brand":
                counts=self.data["brand_page_counts"]
                key=str(category_id)
                if key not in counts or counts[key]>=self.grant.brand_page_limit:
                    raise LiveValidationStopped("Brand grant exhausted or outside scope")
                counts[key]+=1
            else:
                key=f"{kind}_requests"
                cap=getattr(self.grant,f"{kind}_request_limit")
                if self.data[key]>=cap:
                    raise LiveValidationStopped("Catalog/attribute grant exhausted")
                if kind=="attribute" and category_id not in self.grant.brand_category_ids:
                    raise LiveValidationStopped("Attribute category outside scope")
                self.data[key]+=1
            self.persist()  # Precharge before credential lookup or network.

    def close(self):
        self._lease.close()


class PersistentSGOpenAIBudget(OpenAIValidationBudget):
    def __init__(self, ledger):
        super().__init__(limit_usd=ledger.grant.openai_limit_usd)
        self._runtime_ledger=ledger
        saved=ledger.data["openai"]
        self.reserved_usd=Decimal(saved["reserved_upper_bound_usd"])
        self.request_count=saved["requests"]
        self.stopped=saved["stopped"]

    def reserve(self,payload):
        try:
            super().reserve(payload)
        finally:
            self._runtime_ledger.data["openai"]=self.summary()
            self._runtime_ledger.persist()


class RefreshingSGCatalogClient(ShopeeCatalogClient):
    def __init__(self, *, shop_id, fresh_client_factory, ledger):
        from modules.shopee_catalog_client import ShopeeCatalogCredentials
        super().__init__(ShopeeCatalogCredentials(1,"",shop_id,""),marketplace="SG")
        self._fresh_client_factory=fresh_client_factory
        self.ledger=ledger
        self.catalog_refresh_failed=True

    def _get(self,path,parameters):
        endpoints={"/api/v2/product/get_category":"catalog",
            "/api/v2/product/get_brand_list":"brand","/api/v2/product/get_attribute_tree":"attribute"}
        if path not in endpoints:
            raise LiveValidationStopped("Only read-only catalog endpoints are permitted")
        kind=endpoints[path]
        category_id=(int(parameters["category_id"]) if kind=="brand" else
                     int(parameters["category_id_list"]) if kind=="attribute" else None)
        self.ledger.reserve_catalog_call(kind,category_id)
        client=self._fresh_client_factory()
        if (not isinstance(client,ShopeeCatalogClient) or client.marketplace!="SG"
                or client.credentials.shop_id!=self.credentials.shop_id):
            raise LiveValidationStopped("Fresh SG shop binding changed")
        return client._get(path,parameters)


def existing_sg_client_factory(grant, *, audit_env_path=None):
    def fresh():
        credentials=load_shopee_catalog_credentials(audit_env_path,marketplace="SG",require_access_token=False)
        if credentials.shop_id!=grant.shop_id:
            raise LiveValidationStopped("Existing SG shop differs from grant")
        token=GoogleSheetAccessTokenSource(grant.bridge_spreadsheet_id).get_access_token("SG",grant.shop_id)
        return ShopeeCatalogClient(replace(credentials,access_token=token.value),marketplace="SG")
    return fresh


class ScopedSGCategoryEngine:
    def __init__(self,engine,scope,current_catalog_check=None):
        self.engine,self.scope=engine,scope
        self.current_catalog_check=current_catalog_check
    def predict(self,product,catalog,profile):
        if self.current_catalog_check is not None:
            self.current_catalog_check()
        if product.marketplace!="SG" or product.asin not in self.scope.allowed_asins:
            raise LiveValidationStopped("AI product outside SG grant")
        return self.engine.predict(product,catalog,profile)


class SGLiveRuntime:
    def __init__(self, *, grant, run_path, fresh_client_factory=None, api_key="", api_session=None, image_session=None,
                 claim_dir=None):
        self.run_path=Path(run_path).resolve()
        db=self.run_path/"validation.sqlite3"
        grant.validate(db)
        claims = CLAIM_DIR if claim_dir is None else Path(claim_dir).resolve()
        claims.mkdir(parents=True,exist_ok=True)
        claim=claims/f"{grant.digest}.json"
        try:
            with claim.open("x",encoding="utf-8") as file:
                json.dump({"run_path":str(self.run_path)},file)
        except FileExistsError:
            if json.loads(claim.read_text(encoding="utf-8"))["run_path"]!=str(self.run_path):
                raise LiveValidationStopped("Existing grant cannot fund a new run")
        if not (self.run_path/"request-ledger.json").exists() and (db.exists() or (self.run_path/"run-binding.json").exists()):
            raise LiveValidationStopped("Existing SG request ledger is missing")
        # A receipt can be claimed only by one persistent run location.
        self.ledger=SGRunLedger(self.run_path/"request-ledger.json",grant)
        if db.exists() and not (self.run_path/"run-binding.json").exists():
            self.ledger.close(); raise LiveValidationStopped("Unbound existing SG database")
        binding=self.run_path/"run-binding.json"
        if binding.exists():
            if json.loads(binding.read_text())["grant_digest"]!=grant.digest:
                self.ledger.close(); raise LiveValidationStopped("Run grant cannot change")
        else:
            binding.write_text(json.dumps({"grant_digest":grant.digest}),encoding="utf-8")
        self.scope=SGLiveValidationScope(grant.allowed_asins,grant.shop_id,db,grant.brand_page_limit,grant.brand_category_ids)
        self.scope._brand_page_counts.update({int(k):v for k,v in self.ledger.data["brand_page_counts"].items()})
        self.store=CategoryMapperStore(db); self.store.initialize_sg_brand_acceptance()
        self.client=RefreshingSGCatalogClient(shop_id=grant.shop_id,
            fresh_client_factory=fresh_client_factory or existing_sg_client_factory(grant),ledger=self.ledger)
        self.category_engine=None; inspector=None
        if Decimal(grant.openai_limit_usd)>0:
            if not api_key:
                self.ledger.close(); raise LiveValidationStopped("Approved OpenAI key unavailable")
            from modules.category_ai_leaf_search import LeafSearchEngine, LeafSearchProvider
            from modules.weapon_image_inspection import BudgetedLiveWeaponImageInspector
            budget=PersistentSGOpenAIBudget(self.ledger)
            self.category_engine=ScopedSGCategoryEngine(LeafSearchEngine(LeafSearchProvider(api_key,
                session=BudgetedOpenAISession(budget,session=api_session))),self.scope,self._require_catalog)
            inspector=BudgetedLiveWeaponImageInspector(api_key=api_key,budget=budget,api_session=api_session,image_session=image_session)
        self.workflow=SGBrandWorkflow(store=self.store,client=self.client,image_inspector=inspector,live_validation_scope=self.scope)
        # Missing paid permission cannot bypass image inspection for target products.
        self.workflow.product_review=WeaponImageReviewSession("SG")

    def _require_catalog(self):
        if self.client.catalog_refresh_failed:
            raise LiveValidationStopped("Successful current catalog acquisition required")

    def refresh_catalog(self):
        from uuid import uuid4
        self.client.catalog_refresh_failed=True
        self.workflow.bind_input("CATALOG_REFRESH:"+uuid4().hex)
        raw=build_sg_category_catalog_csv(self.client.get_categories("SG"),marketplace="SG")
        count=self.store.replace_sg_category_catalog(parse_sg_category_catalog(raw,filename="sg_catalog.csv"))
        self.client.catalog_refresh_failed=False
        return count

    def close(self):
        self.workflow.product_review.clear()
        self.ledger.close()
