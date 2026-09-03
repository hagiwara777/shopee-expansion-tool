"""Mocked provider-to-candidate handoff; no additional Keepa calls or cache schema."""
import pytest

from modules.cache import KeepaCache
from modules.keepa_client import KeepaExpansionClient, _product_to_cache_data
from modules.asin_resolver import preview_candidates, verify_preview_rows
from modules.prelisting_candidate_csv import (
    expansion_rows_to_prelisting_candidates,
    resolver_rows_to_prelisting_candidates,
    rows_to_prelisting_candidate_csv,
    parse_prelisting_candidate_csv,
)
from modules.ph_image_safety import create_image_sidecar, parse_image_sidecar
from test_keepa_client import FakeKeepaApi, SOURCE_ASIN


def test_existing_keepa_response_carries_root_images_through_both_entrypoints(tmp_path):
    api = FakeKeepaApi(
        detail_products=[
            {
                "asin": "B000000001",
                "title": "ordinary box",
                "brand": "Synthetic",
                "imagesCSV": "one.jpg,two.png,three.webp,four.jpg",
                "categoryTree": [
                    {"catId": 13299531, "name": "Root"},
                    {"catId": 99999, "name": "Leaf"},
                ],
            }
        ],
        finder_asins=["B000000001"],
    )
    cache = KeepaCache(tmp_path / "keepa.sqlite3")
    client = KeepaExpansionClient(domain="JP", api=api, cache=cache)
    expansion = client.find_related_products(SOURCE_ASIN, 1)
    assert len(api.query_calls) == 2  # Existing seed + candidate request only.
    assert len(api.product_finder_calls) == 1
    fact = expansion.rows[0]["ph_image_safety_fact"]
    assert fact["root_category_id"] == 13299531
    assert len(fact["image_urls"]) == 3
    cached = cache.get_product("B000000001")
    assert cached["ph_image_safety_fact"] == fact
    resolver = verify_preview_rows(
        preview_candidates("box,https://www.amazon.co.jp/dp/B000000001"), client
    )
    assert (
        len(api.query_calls) == 2
    )  # Resolver reuses existing cache, no image-only request.
    assert resolver[0]["ph_image_safety_fact"] == fact
    for candidates, sources in [
        (expansion_rows_to_prelisting_candidates(expansion.rows), expansion.rows),
        (resolver_rows_to_prelisting_candidates(resolver).output_rows, resolver),
    ]:
        content = rows_to_prelisting_candidate_csv(candidates)
        payload = create_image_sidecar(content, candidates, sources)
        parsed = parse_image_sidecar(
            payload,
            candidate_content=content,
            candidates=parse_prelisting_candidate_csv(
                content, filename="candidate.csv"
            ),
        )
        assert parsed["rows"][0]["fact"] == fact
        assert (
            "base64" not in payload.decode()
            and len(content.decode("utf-8-sig").splitlines()[0].split(",")) == 15
        )


@pytest.mark.parametrize("root", [True, 999.5, "bad", 0, -1])
def test_keepa_invalid_raw_root_is_not_coerced_into_a_known_non_target(root):
    product = _product_to_cache_data(
        {
            "asin": "B000000001",
            "rootCategory": 999,
            "categoryTree": [{"catId": root, "name": "Unknown"}],
        }
    )
    assert product["ph_image_safety_fact"]["root_category_id"] is None


def test_keepa_rootcategory_fallback_is_captured_without_a_tree():
    product = _product_to_cache_data(
        {"asin": "B000000001", "rootCategory": 13299531, "imagesCSV": "one.jpg"}
    )
    assert product["ph_image_safety_fact"]["root_category_id"] == 13299531
