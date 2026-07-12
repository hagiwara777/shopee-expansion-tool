import csv
from io import StringIO

from modules.asin_resolver import (
    KEEPA_NOT_FOUND,
    KEEPA_VERIFIED,
    NOT_CHECKED,
    RESOLVER_CSV_COLUMNS,
    build_ai_prompt,
    build_search_title,
    build_source_map,
    clean_ai_response,
    parse_ai_response,
    preview_candidates,
    resolve_candidates,
    rows_to_resolver_csv,
    summarize_preview,
    verify_selected_rows,
    verify_preview_rows,
)
from modules.cache import KeepaCache
from modules.keepa_client import KeepaClientError, KeepaExpansionClient


class FakeResolverClient:
    def __init__(self, found_asins=None, error=None):
        self.found_asins = set(found_asins or [])
        self.error = error
        self.calls = []

    def verify_products_by_asin(self, asins):
        self.calls.append(list(asins))
        if self.error:
            raise self.error
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


def test_verify_preview_rows_marks_keepa_errors():
    rows = verify_preview_rows(
        preview_candidates("A,https://www.amazon.co.jp/dp/B07TSC47PH"),
        FakeResolverClient(error=KeepaClientError("Keepa failed")),
    )

    assert rows[0]["status"] == "ERROR"
    assert rows[0]["verification"] == "ERROR"
    assert rows[0]["note"].endswith("Keepa failed")


def test_resolver_csv_uses_expected_columns_and_utf8_sig():
    data = rows_to_resolver_csv(
        [
            {
                "source_id": "R0001",
                "input_title": "A",
                "amazon_url": "https://www.amazon.co.jp/dp/B07TSC47PH",
                "asin": "B07TSC47PH",
                "status": "FOUND",
                "verification": KEEPA_VERIFIED,
                "note": "",
                "ignored": "value",
            }
        ]
    )

    assert data.startswith(b"\xef\xbb\xbf")
    decoded = data.decode("utf-8-sig")
    header = decoded.splitlines()[0].split(",")
    assert header == RESOLVER_CSV_COLUMNS
    rows = list(csv.DictReader(StringIO(decoded)))
    assert rows[0]["source_id"] == "R0001"
    assert rows[0]["asin"] == "B07TSC47PH"


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
