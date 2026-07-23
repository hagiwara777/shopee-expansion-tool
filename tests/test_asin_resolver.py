import csv
from io import StringIO

import pytest

from modules.asin_resolver import (
    KEEPA_NOT_FOUND,
    KEEPA_VERIFIED,
    NOT_CHECKED,
    RESOLVER_CSV_COLUMNS,
    build_ai_prompt,
    build_retry_prompt,
    build_retry_rows,
    build_search_title,
    build_source_map,
    clean_ai_response,
    parse_ai_response,
    preview_candidates,
    retry_rows_fingerprint,
    resolve_candidates,
    rows_to_resolver_csv,
    summarize_preview,
    summarize_retry_rows,
    verify_selected_rows,
    verify_preview_rows,
)
from modules.cache import KeepaCache
from modules.keepa_client import KeepaClientError, KeepaExpansionClient


class FakeResolverClient:
    def __init__(self, found_asins=None, error=None, products_by_asin=None):
        self.found_asins = set(found_asins or [])
        self.error = error
        self.products_by_asin = products_by_asin
        self.calls = []

    def verify_products_by_asin(self, asins):
        self.calls.append(list(asins))
        if self.error:
            raise self.error
        if self.products_by_asin is not None:
            return {
                asin: self.products_by_asin[asin]
                for asin in asins
                if asin in self.products_by_asin
            }
        return {asin: {"asin": asin, "title": "Found"} for asin in asins if asin in self.found_asins}


class FakeKeepaApi:
    def __init__(self, found_asins):
        self.found_asins = set(found_asins)
        self.query_calls = []
        self.product_finder_calls = []

    def query(self, items, **kwargs):
        self.query_calls.append((items, kwargs))
        if isinstance(items, str):
            items = [items]
        return [{"asin": asin, "title": "Found"} for asin in items if asin in self.found_asins]

    def product_finder(self, *args, **kwargs):
        self.product_finder_calls.append((args, kwargs))
        return []


def test_build_ai_prompt_prefers_tsv_and_includes_source_ids():
    prompt = build_ai_prompt("First\n\nSecond")

    assert "TSV形式" in prompt
    assert "source_id\tinput_title\tamazon_url" in prompt
    assert "Markdown表にはしない" in prompt
    assert "R0001\tFirst" in prompt
    assert "R0002\tSecond" in prompt


def test_build_source_map_assigns_stable_ids_to_non_empty_product_names():
    assert build_source_map("First\n\nSecond") == {
        "R0001": "First",
        "R0002": "Second",
    }


def test_build_search_title_removes_known_bracketed_promos_with_nfkc_and_casefolding():
    assert build_search_title("【100% Authentic】Anua Toner 250ml") == "Anua Toner 250ml"
    assert build_search_title("［ＤＩＲＥＣＴ　ＦＲＯＭ　ＪＡＰＡＮ］ HAKUBA Case M Black") == (
        "HAKUBA Case M Black"
    )
    assert build_search_title("[made in JAPAN] Product") == "Product"


def test_build_search_title_only_removes_bracketed_exact_phrase_matches():
    assert build_search_title("[In Stock 3 Pack] Product") == "[In Stock 3 Pack] Product"
    assert build_search_title("【Limited Edition】Refill 200ml") == "【Limited Edition】Refill 200ml"


def test_build_search_title_removes_unbracketed_promos_and_edge_separators():
    assert build_search_title("Anua Toner - Direct from Japan") == "Anua Toner"
    assert build_search_title("New! | KATE Lip Monster") == "KATE Lip Monster"
    assert build_search_title("New!! KATE Lip Monster") == "KATE Lip Monster"


def test_build_search_title_removes_added_unbracketed_shopee_promos():
    assert build_search_title("petit main Official Store kids T-Shirt") == "petit main kids T-Shirt"
    assert build_search_title("Takara Tomy Room Set Shipped from Japan") == "Takara Tomy Room Set"
    assert build_search_title("petit main ＯＦＦＩＣＩＡＬ　ＳＴＯＲＥ kids T-Shirt") == (
        "petit main kids T-Shirt"
    )


@pytest.mark.parametrize(
    "title",
    [
        "[Official Store] Product",
        "［ＯＦＦＩＣＩＡＬ ＳＴＯＲＥ］ Product",
        "【Official Store】 Product",
        "[Shipped from Japan] Product",
        "［ＳＨＩＰＰＥＤ ＦＲＯＭ ＪＡＰＡＮ］ Product",
        "【Shipped from Japan】 Product",
    ],
)
def test_build_search_title_removes_added_exact_bracketed_shopee_promos(title):
    assert build_search_title(title) == "Product"


@pytest.mark.parametrize(
    "title",
    [
        "[Official Store Exclusive Edition]",
        "【Shipped from Japan 3 Pack】",
        "[Official Store Limited Color]",
        "【Officially Licensed Product】",
        "Officially Licensed Product",
        "Official Product",
        "Official License",
        "Store Display Model",
        "Limited Edition",
        "Original",
        "Model X-100 250ml Blue 3 Pack",
    ],
)
def test_build_search_title_preserves_non_matching_identifying_information(title):
    assert build_search_title(title) == title


def test_added_search_title_promos_preserve_source_titles_and_feed_initial_and_retry_prompts():
    original_title = (
        "petit main Official Store kids【Disney】【Pixar】【Cool Touch】Cars Appliqué T-Shirt "
        "(Officially Licensed Product) 【Shipped from Japan】"
    )
    expected_search_title = (
        "petit main kids【Disney】【Pixar】【Cool Touch】Cars Appliqué T-Shirt "
        "(Officially Licensed Product)"
    )
    source_map = build_source_map(original_title)

    assert build_search_title(original_title) == expected_search_title
    assert original_title == (
        "petit main Official Store kids【Disney】【Pixar】【Cool Touch】Cars Appliqué T-Shirt "
        "(Officially Licensed Product) 【Shipped from Japan】"
    )
    assert source_map == {"R0001": original_title}

    initial_prompt = build_ai_prompt(original_title)
    assert f"R0001\t{expected_search_title}" in initial_prompt
    assert original_title not in initial_prompt

    retry_rows = build_retry_rows(
        [
            {
                "source_id": "R0001",
                "input_title": original_title,
                "amazon_url": "",
                "asin": "",
                "status": "UNKNOWN",
                "verification": "NOT_CHECKED",
                "note": "AI returned unknown",
            }
        ],
        source_map,
    )
    assert retry_rows[0]["input_title"] == original_title
    assert retry_rows[0]["initial_search_title"] == expected_search_title
    assert retry_rows[0]["retry_search_title"] == expected_search_title

    retry_rows[0]["retry_search_title"] = "Official Store Custom Title"
    retry_prompt = build_retry_prompt(retry_rows)
    assert "R0001\tOfficial Store Custom Title" in retry_prompt


def test_build_search_title_preserves_identifying_information_and_internal_symbols():
    assert build_search_title("Original Refill 200ml") == "Original Refill 200ml"
    assert build_search_title("Model-A/B Direct from Japan") == "Model-A/B"
    assert build_search_title("BrandNew!Product") == "BrandNew!Product"


def test_build_search_title_falls_back_to_original_title_when_everything_is_removed():
    assert build_search_title("New!") == "New!"


def test_source_map_keeps_original_title_while_prompt_uses_search_title():
    original_title = "【100% Authentic】Anua Toner 250ml"

    assert build_source_map(original_title) == {"R0001": original_title}
    prompt = build_ai_prompt(original_title)

    assert "R0001\tAnua Toner 250ml" in prompt
    assert original_title not in prompt


def test_retry_rows_group_by_source_id_and_exclude_sources_with_a_candidate():
    rows = [
        {
            "source_id": "R0012",
            "input_title": "AI title",
            "amazon_url": "https://www.amazon.co.jp/dp/B07TSC47PH",
            "asin": "B07TSC47PH",
            "status": "UNKNOWN",
            "verification": NOT_CHECKED,
            "note": "Extracted ASIN from Amazon.co.jp URL",
        },
        {
            "source_id": "R0012",
            "input_title": "AI title",
            "amazon_url": "",
            "asin": "",
            "status": "UNKNOWN",
            "verification": NOT_CHECKED,
            "note": "AI returned unknown",
        },
    ]

    assert build_retry_rows(rows, {"R0012": "Original title"}) == []


def test_retry_rows_collapse_multiple_unknown_rows_and_keep_original_source_map_title():
    rows = [
        {
            "source_id": "R0014",
            "input_title": "AI title one",
            "amazon_url": "不明",
            "asin": "",
            "status": "UNKNOWN",
            "verification": NOT_CHECKED,
            "note": "AI returned unknown",
        },
        {
            "source_id": "R0014",
            "input_title": "AI title two",
            "amazon_url": "",
            "asin": "",
            "status": "UNKNOWN",
            "verification": NOT_CHECKED,
            "note": "AI returned unknown",
        },
    ]

    source_map = {"R0014": "Original Bugaboo title"}
    retry_rows = build_retry_rows(rows, source_map)

    assert retry_rows == [
        {
            "row_id": "retry-R0014",
            "source_id": "R0014",
            "input_title": "Original Bugaboo title",
            "initial_search_title": "Original Bugaboo title",
            "retry_search_title": "Original Bugaboo title",
            "selected": True,
        }
    ]
    assert source_map == {"R0014": "Original Bugaboo title"}


def test_retry_prompt_uses_two_column_product_input_and_three_column_output_format():
    prompt = build_retry_prompt(
        [
            {
                "source_id": "R0012",
                "retry_search_title": "Pampers Premium Care diapers",
                "selected": True,
            },
            {
                "source_id": "R0014",
                "retry_search_title": "Excluded title",
                "selected": False,
            },
        ]
    )

    assert "source_id\tinput_title\tamazon_url" in prompt
    assert "商品名:\nR0012\tPampers Premium Care diapers" in prompt
    assert "R0012\tPampers Premium Care diapers\t" not in prompt
    assert "R0014\tExcluded title" not in prompt


def test_retry_prompt_fingerprint_changes_after_selection_or_title_edit():
    rows = [
        {"source_id": "R0001", "selected": True, "retry_search_title": "Original title"}
    ]
    original = retry_rows_fingerprint(rows)

    rows[0]["selected"] = False
    assert retry_rows_fingerprint(rows) != original

    rows[0]["selected"] = True
    rows[0]["retry_search_title"] = "Corrected title"
    assert retry_rows_fingerprint(rows) != original


def test_retry_rows_exclude_invalid_unknown_reasons_and_unknown_source_ids_without_keepa_calls():
    rows = [
        {
            "source_id": "R0001",
            "input_title": "Invalid ASIN",
            "amazon_url": "https://www.amazon.co.jp/dp/INVALID",
            "asin": "",
            "status": "UNKNOWN",
            "verification": NOT_CHECKED,
            "note": "Invalid ASIN format",
        },
        {
            "source_id": "R9999",
            "input_title": "Unknown source",
            "amazon_url": "",
            "asin": "",
            "status": "UNKNOWN",
            "verification": NOT_CHECKED,
            "note": "AI returned unknown Unknown source_id",
        },
    ]

    assert build_retry_rows(rows, {"R0001": "Original"}) == []


def test_retry_rows_exclude_keepa_not_found_and_error_rows():
    rows = [
        {
            "source_id": "R0001",
            "input_title": "Missing product",
            "amazon_url": "",
            "asin": "",
            "status": "UNKNOWN",
            "verification": KEEPA_NOT_FOUND,
            "note": "Keepa did not return product data",
        },
        {
            "source_id": "R0002",
            "input_title": "Error product",
            "amazon_url": "",
            "asin": "",
            "status": "ERROR",
            "verification": "ERROR",
            "note": "Keepa failed",
        },
    ]

    assert build_retry_rows(rows, {"R0001": "Missing", "R0002": "Error"}) == []


def test_retry_summary_counts_selected_titles_and_empty_titles():
    summary = summarize_retry_rows(
        [
            {"source_id": "R0001", "selected": True, "retry_search_title": "Title"},
            {"source_id": "R0002", "selected": True, "retry_search_title": ""},
            {"source_id": "R0003", "selected": False, "retry_search_title": "Title"},
        ]
    )

    assert summary == {
        "initial_unknown_products": 3,
        "selected_products": 2,
        "deselected_products": 1,
        "missing_retry_search_titles": 1,
        "prompt_source_ids": 1,
    }


def test_clean_ai_response_removes_csv_tsv_code_fences_and_blank_lines():
    cleaned = clean_ai_response(
        """
        ```tsv

        input_title\tamazon_url
        Item\thttps://www.amazon.co.jp/dp/B07TSC47PH
        ```
        """
    )

    assert cleaned == "input_title\tamazon_url\nItem\thttps://www.amazon.co.jp/dp/B07TSC47PH"


def test_parses_standard_csv_with_quoted_comma_for_backward_compatibility():
    rows = parse_ai_response(
        'input_title,amazon_url\n"KATE Lip Monster, 03",https://www.amazon.co.jp/dp/B07TSC47PH'
    )

    assert rows[0].input_title == "KATE Lip Monster, 03"
    assert rows[0].asin == "B07TSC47PH"


def test_parses_tsv_with_comma_inside_title():
    rows = parse_ai_response(
        "input_title\tamazon_url\nKATE Lip Monster, 03\thttps://www.amazon.co.jp/dp/B07TSC47PH"
    )

    assert rows[0].input_title == "KATE Lip Monster, 03"
    assert rows[0].asin == "B07TSC47PH"


def test_parses_markdown_table_and_skips_header_and_separator():
    rows = parse_ai_response(
        "\n".join(
            [
                "| input_title | amazon_url |",
                "|---|---|",
                "| Keepa smoke test | https://www.amazon.co.jp/dp/B07TSC47PH |",
            ]
        )
    )

    assert len(rows) == 1
    assert rows[0].input_title == "Keepa smoke test"
    assert rows[0].asin == "B07TSC47PH"


def test_searches_all_csv_cells_for_amazon_url():
    rows = parse_ai_response(
        "input_title,amazon_title,amazon_url\n"
        "商品名,Amazon商品名,https://www.amazon.co.jp/dp/B07TSC47PH"
    )

    assert len(rows) == 1
    assert rows[0].input_title == "商品名"
    assert rows[0].asin == "B07TSC47PH"


def test_extracts_supported_amazon_jp_url_patterns_including_no_scheme():
    response = "\n".join(
        [
            "A,https://www.amazon.co.jp/dp/B07TSC47PH",
            "B,https://www.amazon.co.jp/gp/product/B08C4Z1XF4",
            "C,https://www.amazon.co.jp/xxxxx/dp/B000000001?th=1",
            "D,https://amazon.co.jp/dp/B000000002",
            "E,www.amazon.co.jp/dp/B000000003",
            "F,amazon.co.jp/dp/B000000004",
        ]
    )

    rows = parse_ai_response(response)

    assert [row.asin for row in rows] == [
        "B07TSC47PH",
        "B08C4Z1XF4",
        "B000000001",
        "B000000002",
        "B000000003",
        "B000000004",
    ]
    assert rows[4].amazon_url == "https://www.amazon.co.jp/dp/B000000003"
    assert rows[5].amazon_url == "https://amazon.co.jp/dp/B000000004"


def test_parses_numbered_list_with_url():
    rows = parse_ai_response("1. Keepa smoke test - https://www.amazon.co.jp/dp/B07TSC47PH")

    assert rows[0].input_title.startswith("Keepa smoke test")
    assert rows[0].asin == "B07TSC47PH"


def test_extracts_contextual_embedded_asin_but_not_arbitrary_product_code():
    rows = parse_ai_response(
        "\n".join(
            [
                "Keepa smoke test ASIN: B07TSC47PH",
                "候補ASIN=B08C4Z1XF4",
                "This sentence contains B000000001 but has no ASIN label",
            ]
        )
    )

    assert rows[0].asin == "B07TSC47PH"
    assert rows[0].note == "Extracted ASIN from embedded text"
    assert rows[1].asin == "B08C4Z1XF4"
    assert rows[2].asin == ""
    assert rows[2].note == "No Amazon.co.jp URL or ASIN"


def test_direct_asin_must_fill_a_cell_after_list_prefix_removal():
    rows = parse_ai_response("\n".join(["B07TSC47PH", "Title,B08C4Z1XF4", "1. B000000001"]))

    assert [row.asin for row in rows] == ["B07TSC47PH", "B08C4Z1XF4", "B000000001"]
    assert all(row.note == "Extracted ASIN from direct ASIN" for row in rows)


def test_explanation_lines_are_skipped_only_after_candidate_extraction():
    rows = parse_ai_response(
        "\n".join(
            [
                "以下に結果を示します。",
                "こちらが調査結果です。",
                "以下が結果です: https://www.amazon.co.jp/dp/B07TSC47PH",
            ]
        )
    )

    assert len(rows) == 1
    assert rows[0].asin == "B07TSC47PH"


def test_non_amazon_jp_urls_are_not_checked():
    rows = parse_ai_response(
        "\n".join(
            [
                "A,https://www.amazon.com/dp/B07TSC47PH",
                "B,https://www.amazon.sg/dp/B07TSC47PH",
                "C,https://item.rakuten.co.jp/example",
            ]
        )
    )

    assert all(row.status == "UNKNOWN" for row in rows)
    assert all(row.verification == NOT_CHECKED for row in rows)
    assert all(row.note == "Not Amazon.co.jp URL" for row in rows)


@pytest.mark.parametrize("malformed_url", ["http://[invalid", "https://[abc"])
@pytest.mark.parametrize("format_name", ["tsv", "csv", "markdown"])
def test_malformed_url_candidates_are_ignored_without_interrupting_supported_formats(
    malformed_url,
    format_name,
):
    rows = [
        ["R0001", "Malformed URL candidate", malformed_url],
        [
            "R0002",
            f"Valid Japan URL after {malformed_url}",
            "https://www.amazon.co.jp/dp/B07TSC47PH",
        ],
        [
            "R0003",
            f"Valid overseas URL after {malformed_url}",
            "https://www.amazon.com/dp/B08C4Z1XF4",
        ],
    ]
    if format_name == "tsv":
        response = "\n".join(
            ["source_id\tinput_title\tamazon_url", *["\t".join(row) for row in rows]]
        )
    elif format_name == "csv":
        response = "\n".join(
            ["source_id,input_title,amazon_url", *[",".join(row) for row in rows]]
        )
    else:
        response = "\n".join(
            [
                "| source_id | input_title | amazon_url |",
                "| --- | --- | --- |",
                *[f"| {' | '.join(row)} |" for row in rows],
            ]
        )

    preview_rows = preview_candidates(
        response,
        {
            "R0001": "Original malformed title",
            "R0002": "Original Japan title",
            "R0003": "Original overseas title",
        },
    )

    assert [row["source_id"] for row in preview_rows] == ["R0001", "R0002", "R0003"]
    assert [row["input_title"] for row in preview_rows] == [
        "Original malformed title",
        "Original Japan title",
        "Original overseas title",
    ]
    assert preview_rows[0]["amazon_url"] == ""
    assert preview_rows[0]["note"] == "No Amazon.co.jp URL or ASIN"
    assert preview_rows[1]["asin"] == "B07TSC47PH"
    assert preview_rows[1]["amazon_url"] == "https://www.amazon.co.jp/dp/B07TSC47PH"
    assert preview_rows[2]["asin"] == ""
    assert preview_rows[2]["amazon_url"] == "https://www.amazon.com/dp/B08C4Z1XF4"
    assert preview_rows[2]["note"] == "Not Amazon.co.jp URL"


@pytest.mark.parametrize(
    "title",
    [
        "Collector bundle [2-piece set]",
        "Limited edition [color: navy] - gift set",
    ],
)
def test_regular_titles_with_brackets_and_colons_are_not_treated_as_urls(title):
    rows = parse_ai_response(title)

    assert len(rows) == 1
    assert rows[0].input_title == title
    assert rows[0].amazon_url == ""
    assert rows[0].asin == ""
    assert rows[0].note == "No Amazon.co.jp URL or ASIN"


def test_unknown_url_less_text_and_invalid_asin_are_not_checked():
    rows = parse_ai_response(
        "\n".join(
            [
                "Unknown Product,不明",
                "Plain text without URL",
                "Invalid,https://www.amazon.co.jp/dp/B07TSC47PHX",
            ]
        )
    )

    assert [(row.status, row.verification) for row in rows] == [
        ("UNKNOWN", NOT_CHECKED),
        ("UNKNOWN", NOT_CHECKED),
        ("UNKNOWN", NOT_CHECKED),
    ]
    assert rows[0].note == "AI returned unknown"
    assert rows[1].note == "No Amazon.co.jp URL or ASIN"
    assert rows[2].note == "Invalid ASIN format"


def test_url_mixed_text_uses_whole_line_as_input_title():
    line = "Please use this https://www.amazon.co.jp/dp/B07TSC47PH for the item"

    rows = parse_ai_response(line)

    assert rows[0].input_title == line
    assert rows[0].amazon_url == "https://www.amazon.co.jp/dp/B07TSC47PH"
    assert rows[0].asin == "B07TSC47PH"


def test_preview_summary_uses_documented_definitions_without_keepa_calls():
    rows = preview_candidates(
        "\n".join(
            [
                "A,https://www.amazon.co.jp/dp/B07TSC47PH",
                "B,ASIN: B07TSC47PH",
                "C,不明",
                "D,https://www.amazon.com/dp/B07TSC47PH",
                "Product without candidate",
            ]
        )
    )

    summary = summarize_preview(rows)

    assert summary == {
        "extracted_asin_rows": 2,
        "unique_asins": 1,
        "not_checked": 5,
        "non_jp_url": 1,
        "unresolved": 1,
        "selected_rows": 2,
        "selected_unique_asins": 1,
        "deselected_rows": 3,
    }
    assert all(row["verification"] == NOT_CHECKED for row in rows)


def test_verify_preview_rows_deduplicates_keepa_checks_but_keeps_rows():
    client = FakeResolverClient(found_asins={"B07TSC47PH"})
    preview_rows = preview_candidates(
        "\n".join(
            [
                "A,https://www.amazon.co.jp/dp/B07TSC47PH",
                "B,ASIN: B07TSC47PH",
            ]
        )
    )

    rows = verify_preview_rows(preview_rows, client)

    assert client.calls == [["B07TSC47PH"]]
    assert [row["status"] for row in rows] == ["FOUND", "FOUND"]
    assert [row["verification"] for row in rows] == [KEEPA_VERIFIED, KEEPA_VERIFIED]


def test_verify_preview_rows_copies_keepa_comparison_fields_to_duplicate_asin_rows():
    client = FakeResolverClient(
        products_by_asin={
            "B07TSC47PH": {
                "asin": "B07TSC47PH",
                "title": "Keepa Product Title",
                "brand": "Keepa Brand",
                "category": "Keepa Category",
                "fetched_at": "2026-07-16T00:00:00+00:00",
            }
        }
    )
    preview_rows = preview_candidates(
        "\n".join(
            [
                "source_id\tinput_title\tamazon_url",
                "R0001\tAI title\thttps://www.amazon.co.jp/dp/B07TSC47PH",
                "R0001\tAI title\thttps://www.amazon.co.jp/dp/B07TSC47PH?th=1",
            ]
        ),
        {"R0001": "Original Shopee Title"},
    )

    rows = verify_preview_rows(preview_rows, client)

    assert client.calls == [["B07TSC47PH"]]
    assert [row["source_id"] for row in rows] == ["R0001", "R0001"]
    assert [row["input_title"] for row in rows] == [
        "Original Shopee Title",
        "Original Shopee Title",
    ]
    assert [row["keepa_title"] for row in rows] == ["Keepa Product Title", "Keepa Product Title"]
    assert [row["keepa_brand"] for row in rows] == ["Keepa Brand", "Keepa Brand"]
    assert [row["keepa_category"] for row in rows] == ["Keepa Category", "Keepa Category"]
    assert [row["keepa_fetched_at"] for row in rows] == [
        "2026-07-16T00:00:00+00:00",
        "2026-07-16T00:00:00+00:00",
    ]
    assert [row["asin"] for row in rows] == ["B07TSC47PH", "B07TSC47PH"]


@pytest.mark.parametrize(
    ("product", "expected_title", "expected_brand"),
    [
        ({"asin": "B07TSC47PH", "brand": "Keepa Brand"}, "", "Keepa Brand"),
        ({"asin": "B07TSC47PH", "title": "Keepa Product Title"}, "Keepa Product Title", ""),
        (None, "", ""),
    ],
)
def test_verify_preview_rows_allows_missing_keepa_comparison_data(
    product,
    expected_title,
    expected_brand,
):
    rows = verify_preview_rows(
        preview_candidates("A,https://www.amazon.co.jp/dp/B07TSC47PH"),
        FakeResolverClient(products_by_asin={"B07TSC47PH": product}),
    )

    assert rows[0]["status"] == "FOUND"
    assert rows[0]["verification"] == KEEPA_VERIFIED
    assert rows[0]["keepa_title"] == expected_title
    assert rows[0]["keepa_brand"] == expected_brand
    assert rows[0]["keepa_category"] == ""
    assert rows[0]["keepa_fetched_at"] == ""


def test_source_id_uses_source_map_title_and_allows_multiple_candidates():
    rows = preview_candidates(
        "\n".join(
            [
                "source_id\tinput_title\tamazon_url",
                "R0001\tAI title\thttps://www.amazon.co.jp/dp/B07TSC47PH",
                "R0001\tAI title\thttps://www.amazon.co.jp/dp/B08C4Z1XF4",
            ]
        ),
        {"R0001": "Original title"},
    )

    assert [row["source_id"] for row in rows] == ["R0001", "R0001"]
    assert [row["input_title"] for row in rows] == ["Original title", "Original title"]
    assert [row["selected"] for row in rows] == [True, True]


def test_fallback_parses_same_line_source_id_without_mixing_it_into_title():
    original_title = "【Direct from JAPAN】Anua Toner 250ml"
    rows = preview_candidates(
        "R0001 Anua Toner 250ml https://www.amazon.co.jp/dp/AAAAAAAAAA",
        {"R0001": original_title},
    )

    assert len(rows) == 1
    assert rows[0]["source_id"] == "R0001"
    assert rows[0]["input_title"] == original_title
    assert rows[0]["amazon_url"] == "https://www.amazon.co.jp/dp/AAAAAAAAAA"
    assert rows[0]["asin"] == "AAAAAAAAAA"
    assert "R0001" not in rows[0]["input_title"]


def test_final_source_id_normalization_recovers_id_from_structured_title_cell():
    original_title = "【Direct from JAPAN】Kao Biore Kids Stamp UV Sunscreen SPF50 PA+++"
    rows = preview_candidates(
        "input_title,amazon_url\n"
        "R0001 Kao Biore Kids Stamp UV Sunscreen SPF50 PA+++,https://www.amazon.co.jp/dp/AAAAAAAAAA",
        {"R0001": original_title},
    )

    assert rows[0]["source_id"] == "R0001"
    assert rows[0]["input_title"] == original_title
    assert rows[0]["asin"] == "AAAAAAAAAA"


def test_final_source_id_normalization_applies_to_multiple_candidates_for_one_title():
    rows = preview_candidates(
        "input_title,amazon_url\n"
        "R0010 Poled airluv 4+ (Donut),https://www.amazon.co.jp/dp/AAAAAAAAAA\n"
        "R0010 Poled airluv 4+ (Donut),https://www.amazon.co.jp/dp/BBBBBBBBBB",
        {"R0010": "Original Poled airluv 4+ (Donut)"},
    )

    assert [row["source_id"] for row in rows] == ["R0010", "R0010"]
    assert [row["input_title"] for row in rows] == [
        "Original Poled airluv 4+ (Donut)",
        "Original Poled airluv 4+ (Donut)",
    ]


def test_final_source_id_normalization_preserves_long_title_after_id_removal():
    title = (
        "R0024 Whipple Character [Sylvanian Families Whipple Keychain Kit "
        "(Chocolate Mint)] W-170 Ages 8+ Toy Decoration Patissier Making Toy "
        "Whipple Epoch Co."
    )
    rows = preview_candidates(
        f"input_title,amazon_url\n{title},https://www.amazon.co.jp/dp/AAAAAAAAAA"
    )

    assert rows[0]["source_id"] == "R0024"
    assert rows[0]["input_title"] == title.removeprefix("R0024 ")


def test_final_source_id_normalization_leaves_existing_source_id_and_normal_title_unchanged():
    structured_rows = preview_candidates(
        "source_id\tinput_title\tamazon_url\n"
        "R0001\tOriginal title\thttps://www.amazon.co.jp/dp/AAAAAAAAAA",
        {"R0001": "Mapped title"},
    )
    plain_rows = preview_candidates(
        "input_title,amazon_url\n"
        "Ordinary Product,https://www.amazon.co.jp/dp/BBBBBBBBBB"
    )

    assert structured_rows[0]["source_id"] == "R0001"
    assert structured_rows[0]["input_title"] == "Mapped title"
    assert plain_rows[0]["source_id"] == ""
    assert plain_rows[0]["input_title"] == "Ordinary Product"


def test_final_source_id_normalization_marks_unknown_source_id_without_losing_title():
    rows = preview_candidates(
        "input_title,amazon_url\n"
        "R9999 Unknown Product,https://www.amazon.co.jp/dp/AAAAAAAAAA",
        {"R0001": "Known title"},
    )

    assert rows[0]["source_id"] == "R9999"
    assert rows[0]["input_title"] == "Unknown Product"
    assert "Unknown source_id" in rows[0]["note"]
    assert rows[0]["selected"] is False


def test_fallback_carries_source_context_to_url_on_next_line():
    rows = preview_candidates(
        "R0001 Anua Toner 250ml\nhttps://www.amazon.co.jp/dp/AAAAAAAAAA",
        {"R0001": "Original Anua Toner"},
    )

    assert len(rows) == 1
    assert rows[0]["source_id"] == "R0001"
    assert rows[0]["input_title"] == "Original Anua Toner"
    assert rows[0]["asin"] == "AAAAAAAAAA"


def test_fallback_keeps_source_id_unknown_row_and_restores_source_map_title():
    rows = preview_candidates(
        "R0001 Product title 不明",
        {"R0001": "Original Shopee title"},
    )

    assert len(rows) == 1
    assert rows[0]["source_id"] == "R0001"
    assert rows[0]["input_title"] == "Original Shopee title"
    assert rows[0]["asin"] == ""
    assert rows[0]["amazon_url"] == ""
    assert rows[0]["status"] == "UNKNOWN"
    assert rows[0]["verification"] == NOT_CHECKED
    assert rows[0]["note"] == "AI returned unknown"
    assert rows[0]["selected"] is False


def test_fallback_preserves_pipes_inside_source_id_unknown_title():
    original_title = (
        "Nino Nana MegaCase Diaper Pants [Bundle of 4] M(6-11kg) | L(9-14kg) | "
        "XL(12-18kg) | XXL(15-23kg)"
    )
    rows = preview_candidates(
        f"R0002 {original_title} 不明",
        {"R0002": original_title},
    )

    assert len(rows) == 1
    assert rows[0]["source_id"] == "R0002"
    assert rows[0]["input_title"] == original_title
    assert rows[0]["status"] == "UNKNOWN"
    assert rows[0]["verification"] == NOT_CHECKED
    assert rows[0]["note"] == "AI returned unknown"


def test_nine_source_id_lines_keep_unknown_rows_and_select_only_url_candidate():
    source_map = {f"R{index:04d}": f"Original title {index}" for index in range(1, 10)}
    lines = ["source_id input_title amazon_url"]
    for index in range(1, 10):
        if index == 8:
            lines.append(
                "R0008 Tetris Puzzle Wooden Building Blocks "
                "https://www.amazon.co.jp/dp/B0GQ9ZD41R"
            )
        else:
            lines.append(f"R{index:04d} Product {index} 不明")

    rows = preview_candidates("\n".join(lines), source_map)

    assert len(rows) == 9
    assert [row["source_id"] for row in rows] == [f"R{index:04d}" for index in range(1, 10)]
    assert [row["selected"] for row in rows] == [False, False, False, False, False, False, False, True, False]
    assert rows[7]["asin"] == "B0GQ9ZD41R"
    assert all(row["verification"] == NOT_CHECKED for row in rows)


def test_fallback_carries_source_context_to_multiple_url_lines():
    rows = preview_candidates(
        "\n".join(
            [
                "R0001 Anua Toner 250ml",
                "https://www.amazon.co.jp/dp/AAAAAAAAAA",
                "https://www.amazon.co.jp/dp/BBBBBBBBBB",
            ]
        ),
        {"R0001": "Original Anua Toner"},
    )

    assert [row["source_id"] for row in rows] == ["R0001", "R0001"]
    assert [row["input_title"] for row in rows] == [
        "Original Anua Toner",
        "Original Anua Toner",
    ]
    assert [row["asin"] for row in rows] == ["AAAAAAAAAA", "BBBBBBBBBB"]


def test_fallback_switches_context_when_another_source_id_appears():
    rows = preview_candidates(
        "\n".join(
            [
                "R0001 Anua Toner 250ml",
                "https://www.amazon.co.jp/dp/AAAAAAAAAA",
                "R0002 HAKUBA Case Black",
                "https://www.amazon.co.jp/dp/BBBBBBBBBB",
            ]
        ),
        {"R0001": "Original Anua", "R0002": "Original HAKUBA"},
    )

    assert [(row["source_id"], row["input_title"], row["asin"]) for row in rows] == [
        ("R0001", "Original Anua", "AAAAAAAAAA"),
        ("R0002", "Original HAKUBA", "BBBBBBBBBB"),
    ]


def test_fallback_unknown_source_id_keeps_ai_title_and_starts_deselected():
    rows = preview_candidates(
        "R9999 Unknown Product https://www.amazon.co.jp/dp/AAAAAAAAAA",
        {"R0001": "Known title"},
    )

    assert rows[0]["source_id"] == "R9999"
    assert rows[0]["input_title"] == "Unknown Product"
    assert "Unknown source_id" in rows[0]["note"]
    assert rows[0]["selected"] is False


def test_space_separated_header_is_skipped_without_creating_unknown_row():
    rows = preview_candidates(
        "source_id    input_title    amazon_url\n"
        "R0001 Anua Toner\n"
        "https://www.amazon.co.jp/dp/AAAAAAAAAA",
        {"R0001": "Original Anua"},
    )

    assert len(rows) == 1
    assert rows[0]["source_id"] == "R0001"
    assert rows[0]["asin"] == "AAAAAAAAAA"


def test_source_id_less_v02_input_remains_selected_when_asin_is_valid():
    rows = preview_candidates("Title,https://www.amazon.co.jp/dp/B07TSC47PH")

    assert rows[0]["source_id"] == ""
    assert rows[0]["input_title"] == "Title"
    assert rows[0]["selected"] is True


def test_unknown_or_lost_source_map_warns_but_allows_manual_selection():
    rows = preview_candidates(
        "source_id\tinput_title\tamazon_url\n"
        "R0001\tAI title\thttps://www.amazon.co.jp/dp/B07TSC47PH"
    )

    assert rows[0]["source_id"] == "R0001"
    assert rows[0]["input_title"] == "AI title"
    assert rows[0]["selected"] is False
    assert "Unknown source_id" in rows[0]["note"]

    rows[0]["selected"] = True
    client = FakeResolverClient(found_asins={"B07TSC47PH"})
    verified = verify_selected_rows(rows, client)

    assert client.calls == [["B07TSC47PH"]]
    assert verified[0]["status"] == "FOUND"


def test_verify_selected_rows_only_checks_selected_rows_and_deduplicates_asins():
    preview_rows = preview_candidates(
        "\n".join(
            [
                "A,https://www.amazon.co.jp/dp/B07TSC47PH",
                "B,ASIN: B07TSC47PH",
                "C,https://www.amazon.co.jp/dp/B08C4Z1XF4",
            ]
        )
    )
    preview_rows[1]["selected"] = False
    preview_rows[2]["selected"] = False
    client = FakeResolverClient(found_asins={"B07TSC47PH"})

    rows = verify_selected_rows(preview_rows, client)

    assert client.calls == [["B07TSC47PH"]]
    assert len(rows) == 1
    assert rows[0]["input_title"] == "A"
    assert rows[0]["verification"] == KEEPA_VERIFIED


def test_selected_csv_includes_not_found_rows_but_excludes_deselected_rows():
    preview_rows = preview_candidates(
        "\n".join(
            [
                "source_id\tinput_title\tamazon_url",
                "R0001\tA\thttps://www.amazon.co.jp/dp/B07TSC47PH",
                "R0002\tB\thttps://www.amazon.co.jp/dp/B08C4Z1XF4",
            ]
        ),
        {"R0001": "A", "R0002": "B"},
    )
    preview_rows[1]["selected"] = False

    verified = verify_selected_rows(preview_rows, FakeResolverClient(found_asins=set()))
    csv_rows = list(csv.DictReader(StringIO(rows_to_resolver_csv(verified).decode("utf-8-sig"))))

    assert len(csv_rows) == 1
    assert csv_rows[0]["source_id"] == "R0001"
    assert csv_rows[0]["status"] == "UNKNOWN"
    assert csv_rows[0]["verification"] == KEEPA_NOT_FOUND


def test_resolve_candidates_remains_backward_compatible():
    client = FakeResolverClient(found_asins={"B07TSC47PH"})

    rows = resolve_candidates("A,https://www.amazon.co.jp/dp/B07TSC47PH", client)

    assert client.calls == [["B07TSC47PH"]]
    assert rows[0]["status"] == "FOUND"


def test_verify_preview_rows_marks_keepa_not_found():
    rows = verify_preview_rows(
        preview_candidates("A,https://www.amazon.co.jp/dp/B07TSC47PH"),
        FakeResolverClient(found_asins=set()),
    )

    assert rows[0]["status"] == "UNKNOWN"
    assert rows[0]["verification"] == KEEPA_NOT_FOUND
    assert "Keepa did not return product data" in rows[0]["note"]
    assert rows[0]["keepa_title"] == ""
    assert rows[0]["keepa_brand"] == ""


def test_verify_preview_rows_marks_keepa_errors():
    rows = verify_preview_rows(
        preview_candidates("A,https://www.amazon.co.jp/dp/B07TSC47PH"),
        FakeResolverClient(error=KeepaClientError("Keepa failed")),
    )

    assert rows[0]["status"] == "ERROR"
    assert rows[0]["verification"] == "ERROR"
    assert rows[0]["note"].endswith("Keepa failed")
    assert rows[0]["keepa_title"] == ""
    assert rows[0]["keepa_brand"] == ""


def test_resolver_csv_uses_expected_columns_and_utf8_sig():
    data = rows_to_resolver_csv(
        [
            {
                "source_id": "R0002",
                "input_title": "元Shopeeタイトル",
                "amazon_url": "https://www.amazon.co.jp/dp/B0B1P81W6W",
                "asin": "B0B1P81W6W",
                "status": "FOUND",
                "verification": KEEPA_VERIFIED,
                "note": "",
                "keepa_title": "Keepa Product Title",
                "keepa_brand": "EPOCH",
                "keepa_category": "Keepa Category",
                "keepa_fetched_at": "2026-07-16T00:00:00+00:00",
                "row_id": "candidate-0002",
                "selected": True,
                "parse_status": "CANDIDATE",
                "ignored": "value",
            }
        ]
    )

    assert data.startswith(b"\xef\xbb\xbf")
    decoded = data.decode("utf-8-sig")
    header = decoded.splitlines()[0].split(",")
    assert header == RESOLVER_CSV_COLUMNS
    rows = list(csv.DictReader(StringIO(decoded)))
    assert rows == [
        {
            "source_id": "R0002",
            "input_title": "元Shopeeタイトル",
            "amazon_url": "https://www.amazon.co.jp/dp/B0B1P81W6W",
            "asin": "B0B1P81W6W",
            "status": "FOUND",
            "verification": KEEPA_VERIFIED,
            "note": "",
        }
    ]
    assert "keepa_title" not in rows[0]
    assert "keepa_brand" not in rows[0]
    assert "keepa_category" not in rows[0]
    assert "keepa_fetched_at" not in rows[0]
    assert "row_id" not in rows[0]
    assert "selected" not in rows[0]
    assert "parse_status" not in rows[0]


@pytest.mark.parametrize(
    ("status", "verification", "note"),
    [
        ("UNKNOWN", KEEPA_NOT_FOUND, "Keepa did not return product data"),
        ("ERROR", "ERROR", "Keepa failed"),
    ],
)
def test_resolver_csv_keeps_fixed_columns_for_not_found_and_error_rows(
    status,
    verification,
    note,
):
    data = rows_to_resolver_csv(
        [
            {
                "source_id": "R0002",
                "input_title": "元Shopeeタイトル",
                "amazon_url": "https://www.amazon.co.jp/dp/B0B1P81W6W",
                "asin": "B0B1P81W6W",
                "status": status,
                "verification": verification,
                "note": note,
                "keepa_title": "",
                "keepa_brand": "",
                "keepa_category": "",
                "keepa_fetched_at": "",
                "row_id": "candidate-0002",
                "selected": True,
                "parse_status": "CANDIDATE",
            }
        ]
    )

    decoded = data.decode("utf-8-sig")
    assert decoded.splitlines()[0].split(",") == RESOLVER_CSV_COLUMNS
    rows = list(csv.DictReader(StringIO(decoded)))
    assert rows == [
        {
            "source_id": "R0002",
            "input_title": "元Shopeeタイトル",
            "amazon_url": "https://www.amazon.co.jp/dp/B0B1P81W6W",
            "asin": "B0B1P81W6W",
            "status": status,
            "verification": verification,
            "note": note,
        }
    ]


def test_keepa_existence_check_uses_query_batches_without_product_finder(tmp_path):
    asins = [f"B{index:09d}" for index in range(51)]
    api = FakeKeepaApi(found_asins=asins)
    client = KeepaExpansionClient(domain="JP", api=api, cache=KeepaCache(tmp_path / "cache.sqlite3"))

    products = client.verify_products_by_asin(asins)

    assert set(products) == set(asins)
    assert len(api.query_calls) == 2
    assert len(api.query_calls[0][0]) == 50
    assert len(api.query_calls[1][0]) == 1
    assert api.query_calls[0][1]["domain"] == "JP"
    assert api.product_finder_calls == []
