from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any, Iterable

from modules.cache import KeepaCache, utc_now_iso


ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$")
ALLOWED_SEARCH_PAGES = {1, 3, 5}
CANDIDATES_PER_PAGE = 50
QUERY_BATCH_SIZE = 50
QUERY_VERSION = "product_finder_modes_v1"
SEARCH_MODES = ("strict", "standard", "broad", "category_research")
SEARCH_MODE_LABELS = {
    "strict": "strict: brand + leaf category ID（精度重視）",
    "standard": "standard: brand + parent/root category（候補数と精度の中間）",
    "broad": "broad: brand only（候補数重視・ノイズ増加の可能性あり）",
    "category_research": "category_research: category only（同カテゴリ市場調査用）",
}
SEARCH_MODE_NOTES = {
    "strict": "精度重視。候補が少ない場合はstandardまたはbroadを試してください。",
    "standard": "parent categoryを優先し、取れない場合はrootCategoryを使います。",
    "broad": "候補数重視・ノイズ増加の可能性あり。カテゴリ外商品が混ざる場合があります。",
    "category_research": "出品候補というより同カテゴリ市場調査用です。ブランド外商品も含まれます。",
}
KEEPA_DOMAIN_CODES = {
    "US": 1,
    "GB": 2,
    "DE": 3,
    "FR": 4,
    "JP": 5,
    "CA": 6,
    "IT": 8,
    "ES": 9,
    "IN": 10,
    "MX": 11,
    "BR": 12,
}


class KeepaClientError(RuntimeError):
    pass


class KeepaConfigurationError(KeepaClientError):
    pass


class KeepaDataError(KeepaClientError):
    pass


class KeepaTokenError(KeepaClientError):
    pass


class KeepaNetworkError(KeepaClientError):
    pass


@dataclass(frozen=True)
class SourceProduct:
    asin: str
    title: str
    brand: str
    category: str
    category_id: int
    leaf_category_id: int | None
    parent_category_id: int | None
    root_category_id: int | None
    category_path: str
    fetched_at: str


@dataclass(frozen=True)
class ProductFinderQuery:
    params: dict[str, Any]
    query_hash: str
    category_filter_note: str


@dataclass(frozen=True)
class ProductFinderPage:
    asin_list: list[str]
    total_results: int | None


@dataclass(frozen=True)
class ExpansionResult:
    source_asin: str
    brand: str
    category: str
    category_id: int
    search_mode: str
    search_mode_note: str
    domain: str
    per_page: int
    category_filter_note: str
    search_pages: int
    planned_candidates: int
    token_estimate: int
    raw_candidate_count: int
    total_results: int | None
    detail_success_count: int
    detail_failed_count: int
    unique_candidate_count: int
    duplicate_removed_count: int
    self_excluded_count: int
    existing_listing_exclusion_status: str
    deleted_asin_exclusion_status: str
    final_display_count: int
    total_results_note: str
    strict_low_count_suggestion: str
    cache_key_data: dict[str, Any]
    rows: list[dict[str, str]]
    fetched_at: str
    cache_hit: bool
    token_status: str
    note: str = ""
    diagnostics: list[str] | None = None

    @classmethod
    def from_cache(cls, data: dict[str, Any]) -> "ExpansionResult":
        return cls(
            source_asin=data["source_asin"],
            brand=data.get("brand", ""),
            category=data.get("category", ""),
            category_id=int(data.get("category_id") or 0),
            search_mode=data.get("search_mode", "strict"),
            search_mode_note=data.get("search_mode_note", SEARCH_MODE_NOTES["strict"]),
            domain=data.get("domain", "JP"),
            per_page=int(data.get("per_page", CANDIDATES_PER_PAGE)),
            category_filter_note=data.get("category_filter_note", ""),
            search_pages=int(data["search_pages"]),
            planned_candidates=int(data["planned_candidates"]),
            token_estimate=int(data["token_estimate"]),
            raw_candidate_count=int(data["raw_candidate_count"]),
            total_results=data.get("total_results"),
            detail_success_count=int(data.get("detail_success_count", 0)),
            detail_failed_count=int(data.get("detail_failed_count", 0)),
            unique_candidate_count=int(data["unique_candidate_count"]),
            duplicate_removed_count=int(data["duplicate_removed_count"]),
            self_excluded_count=int(data.get("self_excluded_count", 0)),
            existing_listing_exclusion_status=data.get(
                "existing_listing_exclusion_status",
                "未適用（Ver1では未連携）",
            ),
            deleted_asin_exclusion_status=data.get(
                "deleted_asin_exclusion_status",
                "未適用（Ver1では未連携）",
            ),
            final_display_count=int(data.get("final_display_count", len(data.get("rows", [])))),
            total_results_note=data.get("total_results_note", ""),
            strict_low_count_suggestion=data.get("strict_low_count_suggestion", ""),
            cache_key_data=dict(data.get("cache_key_data", {})),
            rows=list(data.get("rows", [])),
            fetched_at=data["fetched_at"],
            cache_hit=bool(data.get("cache_hit", True)),
            token_status=data.get(
                "token_status",
                "キャッシュを使用したため、Keepa APIトークンは消費していません。",
            ),
            note=data.get("note", ""),
            diagnostics=list(data.get("diagnostics", [])),
        )


def normalize_asin(value: str) -> str:
    asin = (value or "").strip().upper()
    if not ASIN_PATTERN.fullmatch(asin):
        raise ValueError("ASINは10桁の英数字で入力してください。例: B07TSC47PH")
    return asin


def planned_candidate_count(search_pages: int) -> int:
    _validate_search_pages(search_pages)
    return search_pages * CANDIDATES_PER_PAGE


def estimate_token_usage(search_pages: int) -> int:
    planned = planned_candidate_count(search_pages)
    search_tokens = search_pages * 11
    source_product_tokens = 1
    candidate_detail_tokens = planned
    return source_product_tokens + search_tokens + candidate_detail_tokens


class KeepaExpansionClient:
    def __init__(
        self,
        api_key: str | None = None,
        domain: str = "JP",
        api: Any | None = None,
        cache: KeepaCache | None = None,
    ):
        self.domain = domain
        self.api = api if api is not None else self._create_api(api_key)
        self.cache = cache if cache is not None else KeepaCache()

    def find_related_products(
        self,
        source_asin: str,
        search_pages: int,
        search_mode: str = "strict",
    ) -> ExpansionResult:
        source_asin = normalize_asin(source_asin)
        _validate_search_pages(search_pages)
        _validate_search_mode(search_mode)
        planned = planned_candidate_count(search_pages)
        token_estimate = estimate_token_usage(search_pages)

        source = self._get_source_product(source_asin)
        first_query = self._build_product_finder_query(source, search_mode, page_index=0)
        cache_key_data = _build_search_cache_key_data(
            source=source,
            search_pages=search_pages,
            search_mode=search_mode,
            domain=self.domain,
            query=first_query,
        )
        cached_search = self.cache.get_search(cache_key_data)
        if cached_search is not None:
            return ExpansionResult.from_cache(cached_search)

        fetched_at = utc_now_iso()
        candidate_asins: list[str] = []
        total_results: int | None = None
        diagnostics: list[str] = []
        note = ""
        for page_index in range(search_pages):
            query = self._build_product_finder_query(source, search_mode, page_index)
            try:
                finder_page = self._product_finder_page(
                    action=f"候補ASIN検索 {page_index + 1}ページ目",
                    params=query.params,
                )
            except KeepaClientError as exc:
                if not candidate_asins:
                    fallback_asins, fallback_note, diagnostics = self._diagnose_and_fallback(
                        source=source,
                        original_error=exc,
                    )
                    if not fallback_asins:
                        raise KeepaDataError(fallback_note) from exc
                    candidate_asins = fallback_asins
                    note = fallback_note
                    break
                note = (
                    f"候補ASIN検索の途中で停止しました。取得済み候補のみ表示しています。"
                    f"時間をおいて再実行してください。理由: {exc}"
                )
                break
            page_asins = finder_page.asin_list
            total_results = finder_page.total_results if finder_page.total_results is not None else total_results
            candidate_asins.extend(page_asins)
            if len(page_asins) < CANDIDATES_PER_PAGE:
                break

        raw_candidate_count = len(candidate_asins or [])
        unique_candidates, duplicate_removed_count, self_excluded_count, invalid_candidate_count = self._deduplicate_candidates(
            candidate_asins or [], source.asin
        )

        products_by_asin: dict[str, dict[str, Any]] = {}
        try:
            products_by_asin = self._fetch_products_by_asin(unique_candidates)
        except KeepaClientError as exc:
            detail_note = (
                f"候補ASINは取得済みですが、商品基本情報の一部取得で停止しました。"
                f"時間をおいて再実行してください。理由: {exc}"
            )
            note = f"{note} {detail_note}".strip()

        detail_success_count = len(products_by_asin)
        detail_failed_count = max(len(unique_candidates) - detail_success_count, 0)
        if invalid_candidate_count:
            diagnostics.append(f"不正ASIN除外: {invalid_candidate_count}件")

        total_results_note = _build_total_results_note(total_results, raw_candidate_count)
        strict_low_count_suggestion = _build_strict_low_count_suggestion(
            search_mode=search_mode,
            final_display_count=len(unique_candidates),
            total_results=total_results,
        )
        mode_note = SEARCH_MODE_NOTES[search_mode]
        if mode_note:
            diagnostics.append(f"検索モード: {mode_note}")
        diagnostics.append(f"利用カテゴリ条件: {first_query.category_filter_note}")
        if total_results_note:
            diagnostics.append(total_results_note)
        if strict_low_count_suggestion:
            diagnostics.append(strict_low_count_suggestion)

        rows = [
            self._build_candidate_row(
                source=source,
                candidate_asin=asin,
                product=products_by_asin.get(asin),
                token_estimate=token_estimate,
                fetched_at=fetched_at,
                source_label=f"keepa_product_finder_{search_mode}",
                note=note,
                category_filter_note=first_query.category_filter_note,
            )
            for asin in unique_candidates
        ]

        result = ExpansionResult(
            source_asin=source.asin,
            brand=source.brand,
            category=source.category,
            category_id=source.category_id,
            search_mode=search_mode,
            search_mode_note=mode_note,
            domain=self.domain,
            per_page=CANDIDATES_PER_PAGE,
            category_filter_note=first_query.category_filter_note,
            search_pages=search_pages,
            planned_candidates=planned,
            token_estimate=token_estimate,
            raw_candidate_count=raw_candidate_count,
            total_results=total_results,
            detail_success_count=detail_success_count,
            detail_failed_count=detail_failed_count,
            unique_candidate_count=len(rows),
            duplicate_removed_count=duplicate_removed_count,
            self_excluded_count=self_excluded_count,
            existing_listing_exclusion_status="未適用（Ver1では未連携）",
            deleted_asin_exclusion_status="未適用（Ver1では未連携）",
            final_display_count=len(rows),
            total_results_note=total_results_note,
            strict_low_count_suggestion=strict_low_count_suggestion,
            cache_key_data=cache_key_data,
            rows=rows,
            fetched_at=fetched_at,
            cache_hit=False,
            token_status=self._token_status(),
            note=note,
            diagnostics=diagnostics,
        )
        self.cache.save_search(asdict(result))
        return result

    def verify_products_by_asin(self, asins: list[str]) -> dict[str, dict[str, Any]]:
        normalized_asins: list[str] = []
        seen: set[str] = set()
        for asin in asins:
            normalized = normalize_asin(asin)
            if normalized in seen:
                continue
            seen.add(normalized)
            normalized_asins.append(normalized)
        return self._fetch_products_by_asin(normalized_asins)

    def _create_api(self, api_key: str | None) -> Any:
        if not api_key:
            raise KeepaConfigurationError(
                ".env に KEEPA_API_KEY を設定してください。APIキーはチャットには貼らないでください。"
            )

        try:
            import keepa
        except ImportError as exc:
            raise KeepaConfigurationError(
                "keepaライブラリがインストールされていません。requirements.txt を使ってセットアップしてください。"
            ) from exc

        self._verify_keepa_product_params(keepa)
        return keepa.Keepa(api_key)

    def _verify_keepa_product_params(self, keepa_module: Any) -> None:
        fields = getattr(keepa_module.ProductParams, "model_fields", {})
        required_fields = {"brand", "categories_include", "sort", "perPage", "page"}
        missing_fields = required_fields - set(fields)
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise KeepaConfigurationError(
                f"keepaライブラリの仕様が想定と異なります。不足フィールド: {missing}"
            )

    def _get_source_product(self, source_asin: str) -> SourceProduct:
        cached_product = self.cache.get_product(source_asin)
        if cached_product is not None:
            return self._source_from_product_data(cached_product, source_asin)

        products = self._call_keepa(
            "入力ASINの商品情報取得",
            self.api.query,
            source_asin,
            domain=self.domain,
            history=False,
            offers=None,
            stock=False,
            buybox=False,
            rating=False,
            progress_bar=False,
            wait=True,
        )
        if not products:
            raise KeepaDataError(
                "入力ASINの商品情報がKeepa APIから取得できませんでした。ASINが正しいか確認してください。"
            )

        product_data = _product_to_cache_data(products[0], fallback_asin=source_asin)
        self.cache.save_product(product_data)
        return self._source_from_product_data(product_data, source_asin)

    def _source_from_product_data(self, product_data: dict[str, Any], source_asin: str) -> SourceProduct:
        brand = str(product_data.get("brand") or "").strip()
        if not brand:
            raise KeepaDataError(
                "起点ASINからbrandが取得できないため、候補検索を実行できません。別のASINを試してください。"
            )

        leaf_category_id = _to_positive_int(product_data.get("leaf_category_id")) or _to_positive_int(
            product_data.get("category_id")
        )
        parent_category_id = _to_positive_int(product_data.get("parent_category_id"))
        root_category_id = _to_positive_int(product_data.get("root_category_id")) or _to_positive_int(
            product_data.get("category_id")
        )
        category_id = leaf_category_id
        category = str(product_data.get("category") or "").strip()
        if category_id is None or not category:
            raise KeepaDataError(
                "起点ASINからcategoryが取得できないため、候補検索を実行できません。別のASINを試してください。"
            )

        return SourceProduct(
            asin=source_asin,
            title=str(product_data.get("title") or "").strip(),
            brand=brand,
            category=category,
            category_id=category_id,
            leaf_category_id=leaf_category_id,
            parent_category_id=parent_category_id,
            root_category_id=root_category_id,
            category_path=str(product_data.get("category_path") or category),
            fetched_at=str(product_data.get("fetched_at") or utc_now_iso()),
        )

    def _build_product_finder_query(
        self,
        source: SourceProduct,
        search_mode: str,
        page_index: int,
    ) -> ProductFinderQuery:
        params: dict[str, Any] = {
            "perPage": CANDIDATES_PER_PAGE,
            "page": page_index,
            "sort": [["current_SALES", "asc"]],
        }
        category_filter_note = ""

        if search_mode == "strict":
            params["brand"] = [source.brand]
            params["categories_include"] = [_require_category_id(source.leaf_category_id, "leaf category")]
            category_filter_note = (
                f"strict: categories_include=leaf_category_id ({source.leaf_category_id})"
            )
        elif search_mode == "standard":
            params["brand"] = [source.brand]
            if source.parent_category_id:
                params["categories_include"] = [source.parent_category_id]
                category_filter_note = (
                    f"standard: categories_include=parent_category_id ({source.parent_category_id})"
                )
            else:
                root_id = _require_category_id(source.root_category_id, "root category")
                params["rootCategory"] = [str(root_id)]
                category_filter_note = f"standard: rootCategory=({root_id})"
        elif search_mode == "broad":
            params["brand"] = [source.brand]
            category_filter_note = "broad: brandのみ（カテゴリ条件なし）"
        elif search_mode == "category_research":
            params["categories_include"] = [
                _require_category_id(source.leaf_category_id, "leaf category")
            ]
            category_filter_note = (
                f"category_research: categories_include=leaf_category_id ({source.leaf_category_id})"
            )
        else:
            raise ValueError(f"未対応の検索モードです: {search_mode}")

        query_hash = _hash_query_json(params)
        return ProductFinderQuery(
            params=params,
            query_hash=query_hash,
            category_filter_note=category_filter_note,
        )

    def _product_finder_page(self, action: str, params: dict[str, Any]) -> ProductFinderPage:
        if hasattr(self.api, "_request") and hasattr(self.api, "accesskey"):
            payload = {
                "key": self.api.accesskey,
                "domain": _domain_to_keepa_code(self.domain),
                "selection": json.dumps(params, ensure_ascii=False),
            }
            response = self._call_keepa(action, self.api._request, "query", payload, wait=True)
            return ProductFinderPage(
                asin_list=list(response.get("asinList") or []),
                total_results=response.get("totalResults"),
            )

        asin_list = self._call_keepa(
            action,
            self.api.product_finder,
            params,
            domain=self.domain,
            wait=True,
            n_products=params.get("perPage", CANDIDATES_PER_PAGE),
        )
        return ProductFinderPage(asin_list=list(asin_list or []), total_results=None)

    def _diagnose_and_fallback(
        self,
        source: SourceProduct,
        original_error: KeepaClientError | None,
    ) -> tuple[list[str], str, list[str]]:
        diagnostics: list[str] = []
        fallback_asins: list[str] = []
        fallback_source = ""

        tests = [
            (
                "brandのみ",
                "keepa_product_finder_brand_only_fallback",
                {"brand": [source.brand], "perPage": CANDIDATES_PER_PAGE, "page": 0},
            ),
            (
                "categoryのみ",
                "keepa_product_finder_category_only_fallback",
                {"categories_include": [source.category_id], "perPage": CANDIDATES_PER_PAGE, "page": 0},
            ),
            (
                "brand+category",
                "keepa_product_finder_brand_category",
                self._build_product_finder_query(source, "strict", 0).params,
            ),
        ]

        for label, source_name, params in tests:
            try:
                result = self._product_finder_page(f"Product Finder診断 {label}", params)
            except KeepaClientError as exc:
                diagnostics.append(f"{label}: APIエラー ({exc})")
                continue

            count = len(result.asin_list)
            total_text = f" / totalResults={result.total_results}" if result.total_results is not None else ""
            diagnostics.append(f"{label}: {count}件取得{total_text}")
            if count and not fallback_asins:
                fallback_asins = result.asin_list
                fallback_source = source_name

        if fallback_asins:
            note = (
                "brand+categoryの通常検索が成功しなかったため、条件を緩めたProduct Finder結果を表示しています。"
                f"利用ルート: {fallback_source}。"
            )
            if original_error is not None:
                note += f" 元のエラー: {original_error}"
            return fallback_asins, note, diagnostics

        cached_products = self.cache.find_products(
            brand=source.brand,
            category_id=source.category_id,
            limit=CANDIDATES_PER_PAGE,
        )
        cache_asins = [self._safe_normalize_asin(product.get("asin")) for product in cached_products]
        cache_asins = [asin for asin in cache_asins if asin and asin != source.asin]
        if cache_asins:
            diagnostics.append(f"ローカルキャッシュ代替: {len(cache_asins)}件取得")
            note = (
                "Product Finderが利用できないため、SQLiteキャッシュ内の同一brand/category商品を代替候補として表示しています。"
            )
            return cache_asins, note, diagnostics

        error_text = f" 元のエラー: {original_error}" if original_error is not None else ""
        note = (
            "Product Finderのbrandのみ、categoryのみ、brand+categoryの診断がすべて失敗または0件でした。"
            "Keepa管理画面のProduct Finderで同じ条件を作り、Show API QueryのJSONを確認してください。"
            f"{error_text}"
        )
        return [], note, diagnostics

    def _deduplicate_candidates(
        self,
        candidate_asins: list[str],
        source_asin: str,
    ) -> tuple[list[str], int, int, int]:
        unique_candidates: list[str] = []
        seen: set[str] = set()
        duplicate_removed_count = 0
        self_excluded_count = 0
        invalid_candidate_count = 0

        for candidate in candidate_asins:
            normalized = self._safe_normalize_asin(candidate)
            if not normalized:
                invalid_candidate_count += 1
                continue
            if normalized == source_asin:
                self_excluded_count += 1
                continue
            if normalized in seen:
                duplicate_removed_count += 1
                continue
            seen.add(normalized)
            unique_candidates.append(normalized)

        return unique_candidates, duplicate_removed_count, self_excluded_count, invalid_candidate_count

    def _fetch_products_by_asin(self, asins: list[str]) -> dict[str, dict[str, Any]]:
        products_by_asin: dict[str, dict[str, Any]] = {}
        missing_asins: list[str] = []

        for asin in asins:
            cached_product = self.cache.get_product(asin)
            if cached_product is None:
                missing_asins.append(asin)
            else:
                products_by_asin[asin] = cached_product

        for batch in _chunked(missing_asins, QUERY_BATCH_SIZE):
            products = self._call_keepa(
                "候補ASINの商品基本情報取得",
                self.api.query,
                batch,
                domain=self.domain,
                history=False,
                offers=None,
                stock=False,
                buybox=False,
                rating=False,
                progress_bar=False,
                wait=True,
            )
            for product in products:
                product_data = _product_to_cache_data(product)
                asin = self._safe_normalize_asin(product_data.get("asin"))
                if asin:
                    product_data["asin"] = asin
                    self.cache.save_product(product_data)
                    products_by_asin[asin] = product_data

        return products_by_asin

    def _build_candidate_row(
        self,
        source: SourceProduct,
        candidate_asin: str,
        product: dict[str, Any] | None,
        token_estimate: int,
        fetched_at: str,
        source_label: str,
        note: str,
        category_filter_note: str,
    ) -> dict[str, str]:
        product = product or {}
        row_note = note
        if category_filter_note:
            row_note = f"{row_note} {category_filter_note}".strip()
        return {
            "seed_asin": source.asin,
            "candidate_asin": candidate_asin,
            "brand": str(product.get("brand") or source.brand or ""),
            "category": str(product.get("category") or source.category or ""),
            "product_title": str(product.get("title") or ""),
            "source": source_label,
            "token_estimate": str(token_estimate),
            "fetched_at": fetched_at,
            "duplicate_flag": "false",
            "note": row_note,
        }

    def _token_status(self) -> str:
        tokens_left = getattr(self.api, "tokens_left", None)
        if tokens_left is None:
            return "トークン残数は取得できませんでした。トークン不足時は自動で回復待ちします。"
        return f"処理後のKeepa推定残トークン: {tokens_left}。不足時は自動で回復待ちします。"

    def _call_keepa(self, action: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            raise _to_keepa_client_error(action, exc) from exc

    def _safe_normalize_asin(self, value: Any) -> str:
        try:
            return normalize_asin(str(value))
        except ValueError:
            return ""


def _validate_search_pages(search_pages: int) -> None:
    if search_pages not in ALLOWED_SEARCH_PAGES:
        raise ValueError("検索ページ数は1ページ、3ページ、5ページのいずれかを選択してください。")


def _validate_search_mode(search_mode: str) -> None:
    if search_mode not in SEARCH_MODES:
        raise ValueError("検索モードはstrict、standard、broad、category_researchから選択してください。")


def _require_category_id(category_id: int | None, label: str) -> int:
    parsed = _to_positive_int(category_id)
    if parsed is None:
        raise KeepaDataError(f"{label} が取得できないため、この検索モードは実行できません。")
    return parsed


def _hash_query_json(params: dict[str, Any]) -> str:
    query_json = json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(query_json.encode("utf-8")).hexdigest()


def _normalize_brand(brand: str) -> str:
    return " ".join((brand or "").strip().casefold().split())


def _build_search_cache_key_data(
    source: SourceProduct,
    search_pages: int,
    search_mode: str,
    domain: str,
    query: ProductFinderQuery,
) -> dict[str, Any]:
    return {
        "seed_asin": source.asin,
        "search_pages": search_pages,
        "search_mode": search_mode,
        "domain": domain,
        "per_page": CANDIDATES_PER_PAGE,
        "brand_normalized": _normalize_brand(source.brand),
        "leaf_category_id": source.leaf_category_id,
        "parent_category_id": source.parent_category_id,
        "root_category_id": source.root_category_id,
        "query_hash": query.query_hash,
        "query_version": QUERY_VERSION,
    }


def _build_total_results_note(total_results: int | None, returned_count: int) -> str:
    if total_results is None:
        return "Product Finder totalResultsは取得できませんでした。"
    if total_results == 0:
        return "Product Finder totalResults=0: 検索条件が厳しすぎる可能性があります。"
    if total_results > returned_count:
        return "Product Finder totalResultsが返却件数より多いため、ページ数を増やす意味があります。"
    return "Product Finder totalResultsが返却件数以下のため、ページ数を増やしても候補は増えにくいです。"


def _build_strict_low_count_suggestion(
    search_mode: str,
    final_display_count: int,
    total_results: int | None,
) -> str:
    if search_mode != "strict" or final_display_count >= 10:
        return ""
    total_text = f"totalResults={total_results}、" if total_results is not None else ""
    return (
        f"strict検索の候補が10件未満です（{total_text}最終表示{final_display_count}件）。"
        "候補数を増やすにはstandardまたはbroad検索を試してください。"
    )


def _domain_to_keepa_code(domain: str) -> int:
    domain_code = KEEPA_DOMAIN_CODES.get(str(domain).upper())
    if domain_code is None:
        raise KeepaConfigurationError(
            f"未対応のKeepaドメインです: {domain}。Ver1では JP を使用してください。"
        )
    return domain_code


def _row_source_from_note(note: str) -> str:
    if "keepa_product_finder_brand_only_fallback" in note:
        return "keepa_product_finder_brand_only_fallback"
    if "keepa_product_finder_category_only_fallback" in note:
        return "keepa_product_finder_category_only_fallback"
    if "SQLiteキャッシュ" in note:
        return "sqlite_cache_brand_category_fallback"
    return "keepa_product_finder_brand_category"


def _to_keepa_client_error(action: str, exc: Exception) -> KeepaClientError:
    message = str(exc)
    lower_message = message.lower()

    if "not_enough_token" in lower_message or "429" in lower_message:
        return KeepaTokenError(
            f"{action}でKeepa APIトークンが不足しています。数分待ってから再実行してください。"
        )

    if "request_rejected" in lower_message or "payment_required" in lower_message:
        if "候補asin検索" in action.lower():
            return KeepaConfigurationError(
                f"{action}がKeepa側で拒否されました。"
                "APIキーは読み込まれていますが、Product Finder検索が現在のKeepaプランで使えるか、"
                "またはbrand + category条件がKeepa側で受け付けられるかを確認してください。"
            )
        return KeepaConfigurationError(
            f"{action}に失敗しました。APIキー、Keepaプラン、またはAPIキーの有効状態を確認してください。"
        )

    if "timeout" in lower_message or "timed out" in lower_message:
        return KeepaNetworkError(
            f"{action}がタイムアウトしました。ネットワーク状態を確認し、少し待ってから再実行してください。"
        )

    network_terms = ["connection", "network", "dns", "ssl", "proxy"]
    if any(term in lower_message for term in network_terms):
        return KeepaNetworkError(
            f"{action}でネットワークエラーが発生しました。接続状態を確認して再実行してください。"
        )

    return KeepaDataError(
        f"{action}でKeepa APIの応答を正常に処理できませんでした。ASINやAPIキーを確認し、再実行してください。"
    )


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _product_to_cache_data(product: Any, fallback_asin: str = "") -> dict[str, Any]:
    asin = _get_text(product, "asin") or fallback_asin
    category_tree = _extract_category_tree(product)
    leaf_category_id = _category_tree_id(category_tree, -1)
    parent_category_id = _category_tree_id(category_tree, -2)
    root_category_id = _category_tree_id(category_tree, 0) or _to_positive_int(
        _get_value(product, "rootCategory")
    )
    category_id = leaf_category_id or root_category_id
    category = _extract_category_name(product)
    category_path = _category_path(category_tree)
    return {
        "asin": asin,
        "title": _get_text(product, "title"),
        "brand": _get_text(product, "brand"),
        "category": category,
        "category_id": category_id,
        "leaf_category_id": leaf_category_id,
        "parent_category_id": parent_category_id,
        "root_category_id": root_category_id,
        "category_path": category_path,
        "category_tree": category_tree,
        "fetched_at": utc_now_iso(),
        "response": {
            "asin": asin,
            "title": _get_text(product, "title"),
            "brand": _get_text(product, "brand"),
            "category": category,
            "category_id": category_id,
            "leaf_category_id": leaf_category_id,
            "parent_category_id": parent_category_id,
            "root_category_id": root_category_id,
            "category_path": category_path,
        },
    }


def _get_value(product: Any, key: str) -> Any:
    if isinstance(product, dict):
        return product.get(key)
    return getattr(product, key, None)


def _get_text(product: Any, key: str) -> str:
    value = _get_value(product, key)
    if value is None:
        return ""
    return str(value).strip()


def _extract_category_tree(product: Any) -> list[dict[str, Any]]:
    category_tree = _get_value(product, "categoryTree") or []
    normalized_tree = []
    for entry in category_tree:
        cat_id = _to_positive_int(_category_entry_value(entry, "catId"))
        name = _category_entry_value(entry, "name")
        normalized_tree.append(
            {
                "catId": cat_id,
                "name": str(name).strip() if name else "",
            }
        )
    return normalized_tree


def _category_tree_id(category_tree: list[dict[str, Any]], index: int) -> int | None:
    if not category_tree:
        return None
    try:
        return _to_positive_int(category_tree[index].get("catId"))
    except IndexError:
        return None


def _category_path(category_tree: list[dict[str, Any]]) -> str:
    names = [str(entry.get("name") or "").strip() for entry in category_tree]
    return " > ".join(name for name in names if name)


def _extract_category_name(product: Any) -> str:
    category_tree = _extract_category_tree(product)
    if category_tree:
        last_category = category_tree[-1]
        name = last_category.get("name")
        return str(name).strip() if name else ""

    root_category = _get_value(product, "rootCategory")
    return str(root_category).strip() if root_category else ""


def _category_entry_value(entry: Any, key: str) -> Any:
    if isinstance(entry, dict):
        return entry.get(key)
    return getattr(entry, key, None)


def _to_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
