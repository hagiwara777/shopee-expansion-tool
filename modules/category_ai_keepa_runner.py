"""Dedicated Keepa candidate acquisition runner for Category AI Benchmark V1.

This module deliberately does not use ``KeepaExpansionClient``. The benchmark
contract requires one sequential attempt, no fallback, an explicit request and
token budget, and preservation of Product Finder pages before any candidate is
selected for Product confirmation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Protocol, Sequence


RUNNER_VERSION = "CATEGORY_AI_BENCHMARK_KEEPA_RUNNER_V1"
DOMAIN_ID = 5
DOMAIN = "JP"
FINDER_PAGE_SIZE = 50
PRODUCT_BATCH_SIZE = 50
CATEGORY_BATCH_SIZE = 10
NORMAL_TOKEN_ESTIMATE = 617
HARD_TOKEN_CAP = 1_140
HARD_REQUEST_CAP = 77
ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$")
REQUIRED_NEW_BY_GENRE = {
    "Health": 10,
    "Beauty": 9,
    "Food & Beverages": 10,
    "Home & Living": 10,
    "Home Appliances": 10,
    "Mobile & Gadgets": 10,
    "Computers & Accessories": 10,
    "Mom & Baby": 10,
    "Hobbies & Collections": 5,
    "Stationery": 10,
}

VERIFICATION_SCOPE = (
    "Keepa JPでASIN・title・category等の商品データが確認できた。"
    "Amazon.co.jpの現在のlive pageまたは購入可能性を確認したものではない。"
)


class KeepaBenchmarkRunnerError(RuntimeError):
    """Base error for the dedicated runner."""


class KeepaTransportError(KeepaBenchmarkRunnerError):
    """A single Keepa request failed. It is never retried or redirected."""


class RunStopped(KeepaBenchmarkRunnerError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class LeafPlan:
    genre: str
    ph_root_category_id: int
    amazon_root_category_id: int
    amazon_leaf_category_id: int
    seed_asin: str
    amazon_category_path: str
    product_check_target: int


def _leaf(
    genre: str,
    ph_root: int,
    amazon_root: int,
    amazon_leaf: int,
    seed: str,
    path: str,
    product_target: int,
) -> LeafPlan:
    return LeafPlan(
        genre=genre,
        ph_root_category_id=ph_root,
        amazon_root_category_id=amazon_root,
        amazon_leaf_category_id=amazon_leaf,
        seed_asin=seed,
        amazon_category_path=path,
        product_check_target=product_target,
    )


# Owner-approved 10-genre / 32-leaf execution plan. Finder returns at most 50
# ASINs per page; Product confirmation is limited to the per-leaf targets.
LEAF_PLANS: tuple[LeafPlan, ...] = (
    _leaf("Health", 100001, 160384011, 3457082051, "B000NHZUMS", "ドラッグストア > 栄養補助食品 > サプリメント・ビタミン > コラーゲン", 8),
    _leaf("Health", 100001, 160384011, 3456982051, "B01EMX9ERK", "ドラッグストア > 栄養補助食品 > サプリメント・ビタミン > ビタミンC", 8),
    _leaf("Health", 100001, 160384011, 169764011, "B0C379SKGN", "ドラッグストア > オーラルケア > 大人用ハミガキ粉", 8),
    _leaf("Beauty", 100630, 52374051, 170092011, "B011TX0DB2", "ビューティー > スキンケア > 化粧水", 7),
    _leaf("Beauty", 100630, 52374051, 169668011, "B000FQOZNW", "ビューティー > ヘアケア > シャンプー", 7),
    _leaf("Beauty", 100630, 52374051, 170212011, "B08KSPPN8D", "ビューティー > メイクアップ > フェイスパウダー", 7),
    _leaf("Food & Beverages", 100629, 57239051, 4844225051, "B092D5HM5S", "食品・飲料・お酒 > 飲料 > 水 > ミネラルウォーター", 8),
    _leaf("Food & Beverages", 100629, 57239051, 2421963051, "B002PGXK4A", "食品・飲料・お酒 > ごはん > ごはんパック", 8),
    _leaf("Food & Beverages", 100629, 57239051, 71207051, "B09TF7336K", "食品・飲料・お酒 > 調味料・スパイス > しょうゆ", 8),
    _leaf("Home & Living", 100636, 3828871, 490238011, "B08XMNVVTG", "ホーム＆キッチン > キッチン用品 > 鍋・フライパン > 炊飯鍋", 8),
    _leaf("Home & Living", 100636, 3828871, 334630011, "B0BYZJMTH8", "ホーム＆キッチン > 生活雑貨 > 冷却タオル", 8),
    _leaf("Home & Living", 100636, 3828871, 2574224051, "B08XQPTRNT", "ホーム＆キッチン > 掃除用品 > スポンジ > 浴室掃除用", 8),
    _leaf("Home Appliances", 100010, 3828871, 16245081, "B0CHHYQHGP", "ホーム＆キッチン > 家電 > キッチン家電 > 電気ケトル", 8),
    _leaf("Home Appliances", 100010, 3828871, 2275305051, "B099242274", "ホーム＆キッチン > 家電 > キッチン家電 > 炊飯器・精米器 > 炊飯器", 8),
    _leaf("Home Appliances", 100010, 3828871, 15691411, "B0CKWQQXLB", "ホーム＆キッチン > 家電 > キッチン家電 > 電子レンジ・オーブン > 電子レンジ", 8),
    _leaf("Mobile & Gadgets", 100013, 3210981, 128197011, "B002BASTHS", "家電＆カメラ > 携帯電話アクセサリ > ストラップ", 8),
    _leaf("Mobile & Gadgets", 100013, 3210981, 2544551051, "B08K2RCF8N", "家電＆カメラ > 充電器 > モバイルバッテリー", 8),
    _leaf("Mobile & Gadgets", 100013, 3210981, 5975597051, "B0DY84Z94C", "家電＆カメラ > ウェアラブル > スマートトラッカー", 8),
    _leaf("Computers & Accessories", 100644, 2127209051, 2151973051, "B07DVC25R2", "パソコン・周辺機器 > キーボード・マウス > ゲーミングマウス", 8),
    _leaf("Computers & Accessories", 100644, 2127209051, 2151962051, "B08P4CN4YC", "パソコン・周辺機器 > 外付けストレージ > 外付けSSD", 8),
    _leaf("Computers & Accessories", 100644, 2127209051, 2151952051, "B07BK6696F", "パソコン・周辺機器 > 外付けストレージ > 外付けHDD", 8),
    _leaf("Mom & Baby", 100632, 344845011, 22250676051, "B084H7R7L6", "ベビー＆マタニティ > おむつ・トイレ > ベビー用おむつ", 8),
    _leaf("Mom & Baby", 100632, 344845011, 10395289051, "B0F2NZL4FK", "ベビー＆マタニティ > ベビーカー > ベビーカー小物 > ベビーカーシート・クッション", 8),
    _leaf("Mom & Baby", 100632, 344845011, 345986011, "B09QC6JBZK", "ベビー＆マタニティ > 授乳用品 > 哺乳びん > 乳首・キャップ", 8),
    _leaf("Hobbies & Collections", 100639, 13299531, 2189286051, "B0GG8Q1HP4", "おもちゃ > 子ども向けフィギュア > ロボット", 4),
    _leaf("Hobbies & Collections", 100639, 13299531, 10305503051, "B01C2M6EWG", "おもちゃ > ぬいぐるみ > 動物", 4),
    _leaf("Hobbies & Collections", 100639, 13299531, 10290223051, "B0CP4DMFJ4", "おもちゃ > ブロック > ブロックセット", 4),
    _leaf("Hobbies & Collections", 100639, 13299531, 2189597051, "B07RLBNWSP", "おもちゃ > パズル > ジグソーパズル", 4),
    _leaf("Stationery", 100638, 86731051, 16391858051, "B00BLYJ76W", "文房具・オフィス用品 > ファイル・バインダー > スパイラルバインダー", 6),
    _leaf("Stationery", 100638, 86731051, 89118051, "B07G7C61NH", "文房具・オフィス用品 > ファイル・バインダー > リングファイル", 6),
    _leaf("Stationery", 100638, 86731051, 196991011, "B06Y1GWK24", "文房具・オフィス用品 > デジタル文具 > ラベルライター", 6),
    _leaf("Stationery", 100638, 86731051, 89360051, "B00EB70MCO", "文房具・オフィス用品 > オフィス機器 > 電卓", 6),
)


@dataclass(frozen=True)
class ExclusionSet:
    existing_35: frozenset[str]
    smoke_5: frozenset[str]
    known_family_keys: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        existing = frozenset(_normalize_asin(value) for value in self.existing_35)
        smoke = frozenset(_normalize_asin(value) for value in self.smoke_5)
        if len(existing) != 35:
            raise ValueError("existing Benchmark exclusion set must contain exactly 35 ASINs")
        if len(smoke) != 5:
            raise ValueError("smoke exclusion set must contain exactly 5 ASINs")
        if existing & smoke:
            raise ValueError("existing and smoke exclusion sets must be disjoint")
        object.__setattr__(self, "existing_35", existing)
        object.__setattr__(self, "smoke_5", smoke)
        object.__setattr__(
            self,
            "known_family_keys",
            frozenset(value.strip().upper() for value in self.known_family_keys if value.strip()),
        )


@dataclass(frozen=True)
class KeepaResponse:
    payload: Mapping[str, Any]
    tokens_consumed: int
    tokens_left: int
    fetched_at: str

    def __post_init__(self) -> None:
        if isinstance(self.tokens_consumed, bool) or self.tokens_consumed < 0:
            raise ValueError("tokens_consumed must be a non-negative integer")
        if isinstance(self.tokens_left, bool) or not isinstance(self.tokens_left, int):
            raise ValueError("tokens_left must be an integer")


class KeepaTransport(Protocol):
    def request(self, endpoint: str, params: Mapping[str, Any]) -> KeepaResponse:
        """Execute exactly one HTTP request and return measured response usage."""


class KeepaHTTPTransport:
    """Single-attempt low-level Keepa transport; no wait, retry, or fallback."""

    def __init__(self, api_key: str, *, timeout_seconds: float = 30.0, session: Any = None) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("Keepa API key is required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if session is None:
            import requests

            session = requests.Session()
        self._api_key = api_key.strip()
        self._timeout_seconds = timeout_seconds
        self._session = session

    def request(self, endpoint: str, params: Mapping[str, Any]) -> KeepaResponse:
        if endpoint not in {"product", "category", "query"}:
            raise KeepaTransportError("UNAPPROVED_KEEPA_ENDPOINT")
        request_params = dict(params)
        request_params["key"] = self._api_key
        try:
            response = self._session.get(
                f"https://api.keepa.com/{endpoint}/",
                params=request_params,
                timeout=self._timeout_seconds,
            )
        except Exception as exc:
            raise KeepaTransportError(f"NETWORK_{type(exc).__name__.upper()}") from None
        try:
            payload = response.json()
        except Exception:
            raise KeepaTransportError(f"HTTP_{response.status_code}_INVALID_JSON") from None
        if response.status_code != 200:
            raise KeepaTransportError(f"HTTP_{response.status_code}")
        consumed = payload.get("tokensConsumed")
        if isinstance(consumed, bool) or not isinstance(consumed, int) or consumed < 0:
            raise KeepaTransportError("TOKENS_CONSUMED_MISSING_OR_INVALID")
        tokens_left = payload.get("tokensLeft")
        if isinstance(tokens_left, bool) or not isinstance(tokens_left, int):
            raise KeepaTransportError("TOKENS_LEFT_MISSING_OR_INVALID")
        return KeepaResponse(
            payload=payload,
            tokens_consumed=consumed,
            tokens_left=tokens_left,
            fetched_at=_utc_now(),
        )


@dataclass
class TokenLedger:
    hard_token_cap: int = HARD_TOKEN_CAP
    hard_request_cap: int = HARD_REQUEST_CAP
    consumed_tokens: int = 0
    request_count: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)

    def reserve(self, kind: str, tokens: int, available_tokens: int | None) -> int:
        if tokens <= 0:
            raise ValueError("reserved tokens must be positive")
        if self.request_count + 1 > self.hard_request_cap:
            raise RunStopped("HARD_REQUEST_CAP_BEFORE_REQUEST")
        if self.consumed_tokens + tokens > self.hard_token_cap:
            raise RunStopped("HARD_TOKEN_CAP_BEFORE_REQUEST")
        if available_tokens is not None and available_tokens < tokens:
            raise RunStopped("ACCOUNT_TOKEN_RESERVATION_UNAVAILABLE")
        self.request_count += 1
        return self.request_count

    def record(self, index: int, kind: str, reserved: int, actual: int) -> None:
        self.consumed_tokens += actual
        self.events.append(
            {
                "request_index": index,
                "kind": kind,
                "reserved_tokens": reserved,
                "tokens_consumed": actual,
                "cumulative_tokens_consumed": self.consumed_tokens,
            }
        )
        if actual > reserved:
            raise RunStopped("UNEXPECTED_TOKEN_CONSUMPTION", f"kind={kind}")
        if self.consumed_tokens > self.hard_token_cap:
            raise RunStopped("HARD_TOKEN_CAP_AFTER_RESPONSE")


@dataclass(frozen=True)
class RunResult:
    status: str
    stop_code: str
    consumed_tokens: int
    request_count: int
    finder_page_count: int
    verified_candidate_count: int
    rejected_candidate_count: int
    token_balance_sufficient_for_hard_cap: bool | None
    artifact_directory: str


class CategoryAIBenchmarkKeepaRunner:
    """Run the fixed candidate acquisition plan with an injected transport."""

    def __init__(
        self,
        transport: KeepaTransport,
        artifact_directory: str | Path,
        exclusions: ExclusionSet,
        *,
        initial_available_tokens: int | None,
        leaf_plans: Sequence[LeafPlan] = LEAF_PLANS,
    ) -> None:
        if tuple(leaf_plans) != LEAF_PLANS:
            raise ValueError("only the owner-approved 32-leaf plan may be executed")
        if initial_available_tokens is not None and (
            isinstance(initial_available_tokens, bool) or initial_available_tokens < 0
        ):
            raise ValueError("initial_available_tokens must be non-negative or None")
        self.transport = transport
        self.artifacts = _ArtifactStore(artifact_directory)
        self.exclusions = exclusions
        self.leaf_plans = tuple(leaf_plans)
        self.ledger = TokenLedger()
        self._available_tokens = initial_available_tokens
        self._balance_sufficient = (
            None if initial_available_tokens is None else initial_available_tokens >= HARD_TOKEN_CAP
        )
        self._started_at = _utc_now()
        self._finished_at = ""
        self._status = "NOT_STARTED"
        self._stop_code = ""
        self._stop_detail = ""
        self._finder_pages: list[dict[str, Any]] = []
        self._verified: list[dict[str, Any]] = []
        self._rejected: list[dict[str, Any]] = []
        self._seed_diagnostics: list[dict[str, Any]] = []

    def run(self) -> RunResult:
        self._status = "RUNNING"
        try:
            if self._available_tokens is None:
                raise RunStopped("TOKEN_BALANCE_NOT_PROVIDED")
            if not self._balance_sufficient:
                raise RunStopped("TOKEN_BALANCE_BELOW_HARD_CAP")
            self._confirm_seeds()
            self._confirm_categories()
            self._collect_finder_page_zero()
            pools = self._candidate_pools()
            self._collect_required_page_one(pools)
            pools = self._candidate_pools()
            shortages = [
                plan.amazon_leaf_category_id
                for plan in self.leaf_plans
                if len(pools[plan.amazon_leaf_category_id]) < plan.product_check_target
            ]
            if shortages:
                raise RunStopped(
                    "INSUFFICIENT_FINDER_CANDIDATES",
                    "leaf_ids=" + ",".join(str(value) for value in shortages),
                )
            selected = self._select_product_confirmation_asins(pools)
            self._confirm_products(selected)
            self._validate_verified_pool_capacity()
            self._status = "COMPLETED"
        except RunStopped as exc:
            self._status = "STOPPED"
            self._stop_code = exc.code
            self._stop_detail = exc.detail
        except KeepaTransportError as exc:
            self._status = "STOPPED"
            self._stop_code = "TRANSPORT_FAILURE"
            self._stop_detail = str(exc)
        except Exception as exc:
            self._status = "STOPPED"
            self._stop_code = "UNEXPECTED_RUNNER_FAILURE"
            self._stop_detail = type(exc).__name__
        finally:
            self._finished_at = _utc_now()
            self._persist()
        return RunResult(
            status=self._status,
            stop_code=self._stop_code,
            consumed_tokens=self.ledger.consumed_tokens,
            request_count=self.ledger.request_count,
            finder_page_count=len(self._finder_pages),
            verified_candidate_count=len(self._verified),
            rejected_candidate_count=len(self._rejected),
            token_balance_sufficient_for_hard_cap=self._balance_sufficient,
            artifact_directory=str(self.artifacts.directory),
        )

    def _request(self, endpoint: str, params: Mapping[str, Any], kind: str, reserved: int) -> KeepaResponse:
        index = self.ledger.reserve(kind, reserved, self._available_tokens)
        response = self.transport.request(endpoint, params)
        self.ledger.record(index, kind, reserved, response.tokens_consumed)
        self._available_tokens = response.tokens_left
        self._persist()
        return response

    def _confirm_seeds(self) -> None:
        seed_asins = [plan.seed_asin for plan in self.leaf_plans]
        response = self._request(
            "product",
            _product_params(seed_asins),
            "seed_product_confirmation",
            len(seed_asins),
        )
        products = _product_map(response.payload)
        for plan_number, plan in enumerate(self.leaf_plans, 1):
            product = products.get(plan.seed_asin)
            if product is None:
                root_id = None
                leaf_id = None
                category_path = ""
                title_present = False
                status = "SEED_NOT_CONFIRMED"
            else:
                root_id, _, category_path = _category_evidence(product)
                leaf_id = _deepest_category_id(product)
                title_present = bool(str(product.get("title") or "").strip())
                root_match = root_id == plan.amazon_root_category_id
                leaf_match = leaf_id == plan.amazon_leaf_category_id
                if not title_present:
                    status = "SEED_TITLE_MISSING"
                elif root_match and leaf_match:
                    status = "PASS"
                elif not root_match and not leaf_match:
                    status = "ROOT_AND_LEAF_MISMATCH"
                elif not root_match:
                    status = "ROOT_MISMATCH"
                else:
                    status = "LEAF_MISMATCH"
            self._seed_diagnostics.append(
                {
                    "plan_number": plan_number,
                    "genre": plan.genre,
                    "seed_asin": plan.seed_asin,
                    "asin_exists": product is not None,
                    "title_present": title_present,
                    "expected_root_category_id": plan.amazon_root_category_id,
                    "actual_root_category_id": root_id,
                    "expected_leaf_category_id": plan.amazon_leaf_category_id,
                    "actual_leaf_category_id": leaf_id,
                    "root_match": root_id == plan.amazon_root_category_id,
                    "leaf_match": leaf_id == plan.amazon_leaf_category_id,
                    "expected_category_path": plan.amazon_category_path,
                    "actual_category_path": category_path,
                    "status": status,
                }
            )

        failures = [row for row in self._seed_diagnostics if row["status"] != "PASS"]
        if failures:
            plans = ",".join(str(row["plan_number"]) for row in failures)
            if any(row["status"] == "SEED_NOT_CONFIRMED" for row in failures):
                code = "SEED_NOT_CONFIRMED"
            elif any(row["status"] == "SEED_TITLE_MISSING" for row in failures):
                code = "SEED_TITLE_MISSING"
            else:
                code = "SEED_CATEGORY_MISMATCH"
            raise RunStopped(code, f"plans={plans}")

    def _confirm_categories(self) -> None:
        leaf_ids = [plan.amazon_leaf_category_id for plan in self.leaf_plans]
        for batch in _chunks(leaf_ids, CATEGORY_BATCH_SIZE):
            response = self._request(
                "category",
                {
                    "domain": DOMAIN_ID,
                    "category": ",".join(str(value) for value in batch),
                    "parents": 1,
                },
                "category_lookup",
                1,
            )
            categories = response.payload.get("categories")
            if not isinstance(categories, Mapping):
                raise RunStopped("CATEGORY_LOOKUP_SCHEMA_INVALID")
            confirmed = {
                int(value.get("catId", key))
                for key, value in categories.items()
                if isinstance(value, Mapping) and str(value.get("catId", key)).isdigit()
            }
            missing = sorted(set(batch) - confirmed)
            if missing:
                raise RunStopped(
                    "CATEGORY_LOOKUP_MISSING",
                    "leaf_ids=" + ",".join(str(value) for value in missing),
                )

    def _collect_finder_page_zero(self) -> None:
        for plan in self.leaf_plans:
            self._finder_page(plan, page=0)

    def _collect_required_page_one(self, pools: Mapping[int, list[str]]) -> None:
        for plan in self.leaf_plans:
            if len(pools[plan.amazon_leaf_category_id]) < plan.product_check_target:
                self._finder_page(plan, page=1)

    def _finder_page(self, plan: LeafPlan, *, page: int) -> None:
        selection = {
            "rootCategory": [plan.amazon_root_category_id],
            "categories_include": [plan.amazon_leaf_category_id],
            "sort": [["current_SALES", "asc"]],
            "perPage": FINDER_PAGE_SIZE,
            "page": page,
            "productType": [0],
            "singleVariation": True,
        }
        response = self._request(
            "query",
            {"domain": DOMAIN_ID, "selection": _canonical_json(selection)},
            "product_finder",
            11,
        )
        raw_asins = response.payload.get("asinList")
        if not isinstance(raw_asins, list):
            raise RunStopped("FINDER_SCHEMA_INVALID", f"leaf_id={plan.amazon_leaf_category_id}")
        asins: list[str] = []
        for raw_asin in raw_asins:
            try:
                asins.append(_normalize_asin(str(raw_asin)))
            except ValueError:
                raise RunStopped("FINDER_ASIN_INVALID", f"leaf_id={plan.amazon_leaf_category_id}") from None
        self._finder_pages.append(
            {
                "fetched_at": response.fetched_at,
                "genre": plan.genre,
                "amazon_root_category_id": plan.amazon_root_category_id,
                "amazon_leaf_category_id": plan.amazon_leaf_category_id,
                "page": page,
                "selection": selection,
                "selection_hash": _content_hash(selection),
                "asin_list": asins,
            }
        )
        self._persist()

    def _candidate_pools(self) -> dict[int, list[str]]:
        excluded = (
            self.exclusions.existing_35
            | self.exclusions.smoke_5
            | frozenset(plan.seed_asin for plan in self.leaf_plans)
        )
        plan_order = {
            plan.amazon_leaf_category_id: index for index, plan in enumerate(self.leaf_plans)
        }
        records = sorted(
            self._finder_pages,
            key=lambda item: (item["page"], plan_order[item["amazon_leaf_category_id"]]),
        )
        pools = {plan.amazon_leaf_category_id: [] for plan in self.leaf_plans}
        seen: set[str] = set()
        for record in records:
            leaf_id = record["amazon_leaf_category_id"]
            for asin in record["asin_list"]:
                if asin in excluded or asin in seen:
                    continue
                seen.add(asin)
                pools[leaf_id].append(asin)
        return pools

    def _select_product_confirmation_asins(
        self,
        pools: Mapping[int, list[str]],
    ) -> list[tuple[str, LeafPlan]]:
        selected: list[tuple[str, LeafPlan]] = []
        for plan in self.leaf_plans:
            selected.extend(
                (asin, plan)
                for asin in pools[plan.amazon_leaf_category_id][: plan.product_check_target]
            )
        if len(selected) != 229:
            raise RunStopped("PRODUCT_CONFIRMATION_TARGET_MISMATCH")
        return selected

    def _confirm_products(self, selected: Sequence[tuple[str, LeafPlan]]) -> None:
        assignments = {asin: plan for asin, plan in selected}
        products: dict[str, Mapping[str, Any]] = {}
        ordered_asins = [asin for asin, _ in selected]
        for batch in _chunks(ordered_asins, PRODUCT_BATCH_SIZE):
            response = self._request(
                "product",
                _product_params(batch),
                "candidate_product_confirmation",
                len(batch),
            )
            products.update(_product_map(response.payload))

        family_seen: set[str] = set()
        identifier_seen: set[str] = set()
        for asin in ordered_asins:
            plan = assignments[asin]
            product = products.get(asin)
            if product is None:
                self._reject(asin, plan, "PRODUCT_NOT_CONFIRMED")
                continue
            title = str(product.get("title") or "").strip()
            root_id, category_ids, category_path = _category_evidence(product)
            if not title:
                self._reject(asin, plan, "TITLE_MISSING")
                continue
            if root_id != plan.amazon_root_category_id:
                self._reject(asin, plan, "ROOT_CATEGORY_MISMATCH")
                continue
            if plan.amazon_leaf_category_id not in category_ids:
                self._reject(asin, plan, "LEAF_CATEGORY_MISMATCH")
                continue
            parent_asin = _optional_asin(product.get("parentAsin"))
            family_key = parent_asin or asin
            all_excluded = self.exclusions.existing_35 | self.exclusions.smoke_5
            seed_asins = frozenset(item.seed_asin for item in self.leaf_plans)
            if family_key in all_excluded or family_key in seed_asins:
                self._reject(asin, plan, "EXCLUDED_FAMILY")
                continue
            if family_key in self.exclusions.known_family_keys:
                self._reject(asin, plan, "KNOWN_VARIANT_FAMILY")
                continue
            if family_key in family_seen:
                self._reject(asin, plan, "DUPLICATE_FAMILY")
                continue
            identifier = _product_identifier(product)
            if identifier and identifier in identifier_seen:
                self._reject(asin, plan, "SUBSTANTIAL_DUPLICATE")
                continue
            family_seen.add(family_key)
            if identifier:
                identifier_seen.add(identifier)
            self._verified.append(
                {
                    "asin": asin,
                    "product_title": title,
                    "keepa_category": category_path,
                    "keepa_brand": str(product.get("brand") or "").strip(),
                    "resolver_title": "",
                    "benchmark_genre": plan.genre,
                    "ph_root_category_id": plan.ph_root_category_id,
                    "amazon_root_category_id": plan.amazon_root_category_id,
                    "amazon_leaf_category_id": plan.amazon_leaf_category_id,
                    "amazon_category_path": category_path,
                    "keepa_parent_asin": parent_asin,
                    "family_key": family_key,
                    "verification_scope": VERIFICATION_SCOPE,
                    "source_provenance": "KEEPA_PRODUCT_CONFIRMED_AFTER_FINDER_DISCOVERY",
                }
            )

    def _reject(self, asin: str, plan: LeafPlan, reason: str) -> None:
        self._rejected.append(
            {
                "asin": asin,
                "benchmark_genre": plan.genre,
                "amazon_leaf_category_id": plan.amazon_leaf_category_id,
                "reason": reason,
            }
        )

    def _validate_verified_pool_capacity(self) -> None:
        counts = {genre: 0 for genre in REQUIRED_NEW_BY_GENRE}
        for candidate in self._verified:
            counts[candidate["benchmark_genre"]] += 1
        shortages = {
            genre: required - counts[genre]
            for genre, required in REQUIRED_NEW_BY_GENRE.items()
            if counts[genre] < required
        }
        if shortages:
            raise RunStopped(
                "VALID_POOL_SHORTAGE",
                ",".join(f"{genre}:{count}" for genre, count in shortages.items()),
            )

    def _persist(self) -> None:
        manifest = {
            "runner_version": RUNNER_VERSION,
            "status": self._status,
            "stop_code": self._stop_code,
            "stop_detail": self._stop_detail,
            "started_at": self._started_at,
            "finished_at": self._finished_at,
            "domain": DOMAIN,
            "domain_id": DOMAIN_ID,
            "retry": 0,
            "concurrency": 1,
            "automatic_fallback": False,
            "hard_token_cap": HARD_TOKEN_CAP,
            "hard_request_cap": HARD_REQUEST_CAP,
            "normal_token_estimate": NORMAL_TOKEN_ESTIMATE,
            "product_finder_scope": "CATEGORY_AI_BENCHMARK_V1_SOURCE_CANDIDATE_DISCOVERY_ONLY",
            "verification_scope": VERIFICATION_SCOPE,
            "product_confirmation_scope": "SELECTED_CANDIDATES_ONLY",
            "page_policy": "PAGE_0_FIRST_THEN_PAGE_1_ONLY_FOR_SHORTAGE_LEAVES",
            "production_sqlite_used": False,
            "production_sqlite_modified": False,
            "openai_api_called": False,
            "api_key_persisted_or_displayed": False,
            "raw_response_persisted": False,
            "token_balance_sufficient_for_hard_cap": self._balance_sufficient,
            "token_ledger": {
                "tokens_consumed": self.ledger.consumed_tokens,
                "request_count": self.ledger.request_count,
                "events": self.ledger.events,
            },
            "plan": [asdict(plan) for plan in self.leaf_plans],
            "plan_hash": _content_hash([asdict(plan) for plan in self.leaf_plans]),
            "finder_page_count": len(self._finder_pages),
            "verified_candidate_count": len(self._verified),
            "rejected_candidate_count": len(self._rejected),
            "required_new_by_genre": REQUIRED_NEW_BY_GENRE,
            "verified_pool_count_by_genre": {
                genre: sum(1 for row in self._verified if row["benchmark_genre"] == genre)
                for genre in REQUIRED_NEW_BY_GENRE
            },
            "diversity_targets": {
                "difficulty_mix_per_genre": {"EASY": 4, "MEDIUM": 4, "HARD": 2},
                "brand_max_per_genre": 2,
                "leaf_max_per_genre": 4,
                "policy": "TARGETS_NOT_SILENTLY_RELAXED; REPORT_SHORTAGE_WITHOUT_UNBOUNDED_FETCHING",
                "selection_method": "AMAZON_KEEPA_FACTS_AND_HUMAN_REVIEW_ONLY",
                "ai_prediction_used": False,
            },
        }
        self.artifacts.write_json("execution_manifest.json", manifest)
        self.artifacts.write_json(
            "seed_diagnostic.json",
            {
                "diagnostic_schema_version": "CATEGORY_AI_KEEPA_SEED_DIAGNOSTIC_V1",
                "validation_status": (
                    "NOT_RUN"
                    if not self._seed_diagnostics
                    else "PASS"
                    if all(row["status"] == "PASS" for row in self._seed_diagnostics)
                    else "FAILED"
                ),
                "row_count": len(self._seed_diagnostics),
                "pass_count": sum(row["status"] == "PASS" for row in self._seed_diagnostics),
                "failure_count": sum(row["status"] != "PASS" for row in self._seed_diagnostics),
                "rows": self._seed_diagnostics,
                "raw_response_persisted": False,
                "api_key_persisted_or_displayed": False,
            },
        )
        self.artifacts.write_jsonl("finder_pages.jsonl", self._finder_pages)
        self.artifacts.write_jsonl("verified_candidates.jsonl", self._verified)
        self.artifacts.write_jsonl("rejected_candidates.jsonl", self._rejected)


class _ArtifactStore:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory).resolve()
        if self.directory.suffix.lower() in {".sqlite", ".sqlite3", ".db"}:
            raise ValueError("artifact_directory must not be a SQLite path")
        self.directory.mkdir(parents=True, exist_ok=True)

    def write_json(self, name: str, value: Mapping[str, Any]) -> None:
        self._atomic_write(name, _canonical_json(value) + "\n")

    def write_jsonl(self, name: str, rows: Sequence[Mapping[str, Any]]) -> None:
        text = "".join(_canonical_json(row) + "\n" for row in rows)
        self._atomic_write(name, text)

    def _atomic_write(self, name: str, text: str) -> None:
        target = self.directory / name
        temporary = self.directory / f".{name}.tmp"
        temporary.write_text(text, encoding="utf-8", newline="\n")
        temporary.replace(target)


def _product_params(asins: Sequence[str]) -> dict[str, Any]:
    return {
        "domain": DOMAIN_ID,
        "asin": ",".join(asins),
        "history": 0,
        "update": -1,
    }


def _product_map(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw_products = payload.get("products")
    if not isinstance(raw_products, list):
        raise RunStopped("PRODUCT_RESPONSE_SCHEMA_INVALID")
    products: dict[str, Mapping[str, Any]] = {}
    for raw_product in raw_products:
        if not isinstance(raw_product, Mapping):
            raise RunStopped("PRODUCT_RESPONSE_SCHEMA_INVALID")
        try:
            asin = _normalize_asin(str(raw_product.get("asin") or ""))
        except ValueError:
            raise RunStopped("PRODUCT_RESPONSE_ASIN_INVALID") from None
        if asin in products:
            raise RunStopped("PRODUCT_RESPONSE_DUPLICATE_ASIN", f"asin={asin}")
        products[asin] = raw_product
    return products


def _category_evidence(product: Mapping[str, Any]) -> tuple[int | None, set[int], str]:
    root_value = product.get("rootCategory")
    root_id = int(root_value) if str(root_value or "").isdigit() else None
    category_tree = product.get("categoryTree")
    if not isinstance(category_tree, list):
        category_tree = []
    ids: set[int] = set()
    names: list[str] = []
    for item in category_tree:
        if not isinstance(item, Mapping):
            continue
        cat_id = item.get("catId")
        if str(cat_id or "").isdigit():
            ids.add(int(cat_id))
        name = str(item.get("name") or "").strip()
        if name:
            names.append(name)
    return root_id, ids, " > ".join(names)


def _deepest_category_id(product: Mapping[str, Any]) -> int | None:
    category_tree = product.get("categoryTree")
    if not isinstance(category_tree, list):
        return None
    deepest: int | None = None
    for item in category_tree:
        if not isinstance(item, Mapping):
            continue
        cat_id = item.get("catId")
        if str(cat_id or "").isdigit():
            deepest = int(cat_id)
    return deepest


def _product_identifier(product: Mapping[str, Any]) -> str:
    for field_name in ("eanList", "upcList"):
        values = product.get(field_name)
        if isinstance(values, list):
            normalized = sorted(str(value).strip().upper() for value in values if str(value).strip())
            if normalized:
                return f"{field_name}:{'|'.join(normalized)}"
    brand = str(product.get("brand") or "").strip().casefold()
    model = str(product.get("model") or product.get("partNumber") or "").strip().casefold()
    if brand and model:
        return f"brand-model:{brand}|{model}"
    return ""


def _optional_asin(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text if ASIN_PATTERN.fullmatch(text) else ""


def _normalize_asin(value: str) -> str:
    asin = value.strip().upper()
    if not ASIN_PATTERN.fullmatch(asin):
        raise ValueError("invalid ASIN")
    return asin


def _chunks(values: Sequence[Any], size: int) -> list[list[Any]]:
    return [list(values[index : index + size]) for index in range(0, len(values), size)]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
