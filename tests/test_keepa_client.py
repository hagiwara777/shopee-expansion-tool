import pytest

from modules.cache import KeepaCache
from modules.keepa_client import (
    CANDIDATES_PER_PAGE,
    KeepaDataError,
    KeepaExpansionClient,
    QUERY_VERSION,
    estimate_token_usage,
    normalize_asin,
    planned_candidate_count,
)


SOURCE_ASIN = "B07TSC47PH"


class FakeKeepaApi:
    def __init__(self, source_product=None, finder_asins=None, detail_products=None):
        self.source_product = source_product or {
            "asin": SOURCE_ASIN,
            "brand": "SampleBrand",
            "rootCategory": 12345,
            "categoryTree": [
                {"catId": 100, "name": "Root"},
                {"catId": 200, "name": "Parent"},
                {"catId": 12345, "name": "Leaf"},
            ],
        }
        self.finder_asins = finder_asins or [SOURCE_ASIN, "B000000001", "B000000002"]
        self.detail_products = detail_products or [
            {
                "asin": "B000000001",
                "title": "First",
                "brand": "SampleBrand",
                "categoryTree": [
                    {"catId": 12345, "name": "Root"},
                    {"catId": 99999, "name": "Leaf"},
                ],
            },
            {
                "asin": "B000000002",
                "title": "Second",
                "brand": "SampleBrand",
                "categoryTree": [],
            },
        ]
        self.query_calls = []
        self.product_finder_calls = []

    def query(self, items, **kwargs):
        self.query_calls.append((items, kwargs))
        if items == SOURCE_ASIN:
            return [self.source_product]
        return self.detail_products

    def product_finder(self, product_parms, **kwargs):
        self.product_finder_calls.append((product_parms, kwargs))
        return self.finder_asins


def test_normalize_asin_accepts_10_alphanumeric_chars():
    assert normalize_asin(" b07tsc47ph ") == SOURCE_ASIN


@pytest.mark.parametrize("asin", ["", "B07TSC47P", "B07TSC47PHX", "B07TSC-7PH"])
def test_normalize_asin_rejects_invalid_values(asin):
    with pytest.raises(ValueError):
        normalize_asin(asin)


def test_token_estimate_uses_50_candidates_per_page():
    assert planned_candidate_count(1) == 50
    assert planned_candidate_count(3) == 150
    assert planned_candidate_count(5) == 250
    assert estimate_token_usage(1) == 62
    assert estimate_token_usage(3) == 184
    assert estimate_token_usage(5) == 306


def test_find_related_products_uses_brand_category_and_excludes_duplicates(tmp_path):
    api = FakeKeepaApi()
    cache = KeepaCache(tmp_path / "cache.sqlite3")
    client = KeepaExpansionClient(domain="JP", api=api, cache=cache)

    result = client.find_related_products(SOURCE_ASIN, 1)
    rows = result.rows

    assert [row["candidate_asin"] for row in rows] == ["B000000001", "B000000002"]
    params, finder_kwargs = api.product_finder_calls[0]
    assert params == {
        "brand": ["SampleBrand"],
        "categories_include": [12345],
        "sort": [["current_SALES", "asc"]],
        "perPage": 50,
        "page": 0,
    }
    assert finder_kwargs == {"domain": "JP", "wait": True, "n_products": 50}
    assert api.query_calls[0] == (
        SOURCE_ASIN,
        {
            "domain": "JP",
            "history": False,
            "offers": None,
            "stock": False,
            "buybox": False,
            "rating": False,
            "progress_bar": False,
            "wait": True,
        },
    )
    assert api.query_calls[1] == (
        ["B000000001", "B000000002"],
        {
            "domain": "JP",
            "history": False,
            "offers": None,
            "stock": False,
            "buybox": False,
            "rating": False,
            "progress_bar": False,
            "wait": True,
        },
    )
    assert rows[0]["category"] == "Leaf"
    assert rows[1]["category"] == "Leaf"
    assert all(row["seed_asin"] == SOURCE_ASIN for row in rows)
    assert result.raw_candidate_count == 3
    assert result.unique_candidate_count == 2
    assert result.duplicate_removed_count == 0
    assert result.self_excluded_count == 1
    assert result.token_estimate == 62
    assert result.search_mode == "strict"
    assert result.category_filter_note == "strict: categories_include=leaf_category_id (12345)"
    assert result.detail_success_count == 2
    assert result.detail_failed_count == 0
    assert result.existing_listing_exclusion_status == "未適用（Ver1では未連携）"
    assert result.deleted_asin_exclusion_status == "未適用（Ver1では未連携）"
    assert result.final_display_count == 2
    assert "standardまたはbroad" in result.strict_low_count_suggestion


def test_find_related_products_deduplicates_repeated_candidates(tmp_path):
    api = FakeKeepaApi(finder_asins=["B000000001", "B000000001"])
    cache = KeepaCache(tmp_path / "cache.sqlite3")
    client = KeepaExpansionClient(domain="JP", api=api, cache=cache)

    result = client.find_related_products(SOURCE_ASIN, 1)

    assert [row["candidate_asin"] for row in result.rows] == ["B000000001"]
    assert result.duplicate_removed_count == 1


def test_search_mode_params_for_strict_standard_broad_and_category_research(tmp_path):
    api = FakeKeepaApi()
    cache = KeepaCache(tmp_path / "cache.sqlite3")
    client = KeepaExpansionClient(domain="JP", api=api, cache=cache)
    source = client._get_source_product(SOURCE_ASIN)

    strict = client._build_product_finder_query(source, "strict", 0)
    standard = client._build_product_finder_query(source, "standard", 0)
    broad = client._build_product_finder_query(source, "broad", 0)
    category_research = client._build_product_finder_query(source, "category_research", 0)

    assert strict.params == {
        "brand": ["SampleBrand"],
        "categories_include": [12345],
        "sort": [["current_SALES", "asc"]],
        "perPage": CANDIDATES_PER_PAGE,
        "page": 0,
    }
    assert standard.params["brand"] == ["SampleBrand"]
    assert standard.params["categories_include"] == [200]
    assert "parent_category_id" in standard.category_filter_note
    assert broad.params == {
        "perPage": CANDIDATES_PER_PAGE,
        "page": 0,
        "sort": [["current_SALES", "asc"]],
        "brand": ["SampleBrand"],
    }
    assert category_research.params["categories_include"] == [12345]
    assert "brand" not in category_research.params


def test_standard_search_uses_root_category_when_parent_is_unavailable(tmp_path):
    api = FakeKeepaApi(
        source_product={
            "asin": SOURCE_ASIN,
            "brand": "SampleBrand",
            "rootCategory": 100,
            "categoryTree": [{"catId": 100, "name": "Root"}],
        }
    )
    cache = KeepaCache(tmp_path / "cache.sqlite3")
    client = KeepaExpansionClient(domain="JP", api=api, cache=cache)
    source = client._get_source_product(SOURCE_ASIN)

    standard = client._build_product_finder_query(source, "standard", 0)

    assert standard.params["rootCategory"] == ["100"]
    assert "categories_include" not in standard.params
    assert "rootCategory" in standard.category_filter_note


def test_cache_key_includes_mode_domain_categories_hash_and_version(tmp_path):
    api = FakeKeepaApi()
    cache = KeepaCache(tmp_path / "cache.sqlite3")
    client = KeepaExpansionClient(domain="JP", api=api, cache=cache)

    result = client.find_related_products(SOURCE_ASIN, 1, search_mode="strict")

    cache_key = result.cache_key_data
    assert cache_key["seed_asin"] == SOURCE_ASIN
    assert cache_key["search_pages"] == 1
    assert cache_key["search_mode"] == "strict"
    assert cache_key["domain"] == "JP"
    assert cache_key["per_page"] == CANDIDATES_PER_PAGE
    assert cache_key["brand_normalized"] == "samplebrand"
    assert cache_key["leaf_category_id"] == 12345
    assert cache_key["parent_category_id"] == 200
    assert cache_key["root_category_id"] == 100
    assert len(cache_key["query_hash"]) == 64
    assert cache_key["query_version"] == QUERY_VERSION


def test_detail_success_and_failure_counts_are_separate(tmp_path):
    api = FakeKeepaApi(detail_products=[{"asin": "B000000001", "title": "First"}])
    cache = KeepaCache(tmp_path / "cache.sqlite3")
    client = KeepaExpansionClient(domain="JP", api=api, cache=cache)

    result = client.find_related_products(SOURCE_ASIN, 1)

    assert result.raw_candidate_count == 3
    assert result.detail_success_count == 1
    assert result.detail_failed_count == 1
    assert result.final_display_count == 2


def test_broad_mode_marks_noise_risk(tmp_path):
    api = FakeKeepaApi(finder_asins=["B000000001"])
    cache = KeepaCache(tmp_path / "cache.sqlite3")
    client = KeepaExpansionClient(domain="JP", api=api, cache=cache)

    result = client.find_related_products(SOURCE_ASIN, 1, search_mode="broad")

    assert result.search_mode == "broad"
    assert "ノイズ増加" in result.search_mode_note
    assert result.rows[0]["source"] == "keepa_product_finder_broad"


def test_find_related_products_uses_search_cache_without_api_calls(tmp_path):
    cache = KeepaCache(tmp_path / "cache.sqlite3")
    first_api = FakeKeepaApi()
    first_client = KeepaExpansionClient(domain="JP", api=first_api, cache=cache)
    first_result = first_client.find_related_products(SOURCE_ASIN, 1)

    second_api = FakeKeepaApi()
    second_client = KeepaExpansionClient(domain="JP", api=second_api, cache=cache)
    second_result = second_client.find_related_products(SOURCE_ASIN, 1)

    assert first_result.cache_hit is False
    assert second_result.cache_hit is True
    assert second_api.query_calls == []
    assert second_api.product_finder_calls == []
    assert second_result.rows == first_result.rows


def test_find_related_products_requires_source_brand(tmp_path):
    api = FakeKeepaApi(source_product={"asin": SOURCE_ASIN, "rootCategory": 12345})
    cache = KeepaCache(tmp_path / "cache.sqlite3")
    client = KeepaExpansionClient(domain="JP", api=api, cache=cache)

    with pytest.raises(KeepaDataError):
        client.find_related_products(SOURCE_ASIN, 1)


def test_find_related_products_requires_source_category(tmp_path):
    api = FakeKeepaApi(source_product={"asin": SOURCE_ASIN, "brand": "SampleBrand"})
    cache = KeepaCache(tmp_path / "cache.sqlite3")
    client = KeepaExpansionClient(domain="JP", api=api, cache=cache)

    with pytest.raises(KeepaDataError):
        client.find_related_products(SOURCE_ASIN, 1)
