import csv
from io import StringIO

from modules.asin_resolver import (
    KEEPA_NOT_FOUND,
    KEEPA_VERIFIED,
    NOT_CHECKED,
    RESOLVER_CSV_COLUMNS,
    build_ai_prompt,
    clean_ai_response,
    parse_ai_response,
    resolve_candidates,
    rows_to_resolver_csv,
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


def test_build_ai_prompt_numbers_non_empty_product_names():
    prompt = build_ai_prompt("First\n\nSecond")

    assert "Amazon.co.jp" in prompt
    assert "1. First" in prompt
    assert "2. Second" in prompt


def test_clean_ai_response_removes_markdown_code_fences_and_blank_lines():
    cleaned = clean_ai_response(
        """
        ```csv

        input_title,amazon_url
        Item,https://www.amazon.co.jp/dp/B07TSC47PH
        ```
        """
    )

    assert cleaned == "input_title,amazon_url\nItem,https://www.amazon.co.jp/dp/B07TSC47PH"


def test_parse_csv_with_comma_inside_title_uses_csv_module():
    rows = parse_ai_response(
        'input_title,amazon_url\n"KATE Lip Monster, 03",https://www.amazon.co.jp/dp/B07TSC47PH'
    )

    assert rows[0].input_title == "KATE Lip Monster, 03"
    assert rows[0].amazon_url == "https://www.amazon.co.jp/dp/B07TSC47PH"
    assert rows[0].asin == "B07TSC47PH"


def test_extracts_supported_amazon_jp_url_patterns():
    response = "\n".join(
        [
            "A,https://www.amazon.co.jp/dp/B07TSC47PH",
            "B,https://www.amazon.co.jp/gp/product/B08C4Z1XF4",
            "C,https://www.amazon.co.jp/xxxxx/dp/B000000001?th=1",
            "D,https://amazon.co.jp/dp/B000000002",
        ]
    )

    rows = parse_ai_response(response)

    assert [row.asin for row in rows] == [
        "B07TSC47PH",
        "B08C4Z1XF4",
        "B000000001",
        "B000000002",
    ]


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
    assert rows[2].note == "Invalid ASIN format"


def test_direct_asin_must_be_whole_cell_or_whole_line():
    rows = parse_ai_response(
        "\n".join(
            [
                "B07TSC47PH",
                "Title,B08C4Z1XF4",
                "This sentence contains B000000001 but should not be picked",
            ]
        )
    )

    assert rows[0].asin == "B07TSC47PH"
    assert rows[1].asin == "B08C4Z1XF4"
    assert rows[2].asin == ""
    assert rows[2].verification == NOT_CHECKED


def test_url_mixed_text_uses_whole_line_as_input_title():
    line = "Please use this https://www.amazon.co.jp/dp/B07TSC47PH for the item"

    rows = parse_ai_response(line)

    assert rows[0].input_title == line
    assert rows[0].amazon_url == "https://www.amazon.co.jp/dp/B07TSC47PH"
    assert rows[0].asin == "B07TSC47PH"


def test_resolve_candidates_deduplicates_keepa_checks_but_keeps_rows():
    client = FakeResolverClient(found_asins={"B07TSC47PH"})

    rows = resolve_candidates(
        "\n".join(
            [
                "A,https://www.amazon.co.jp/dp/B07TSC47PH",
                "B,https://www.amazon.co.jp/dp/B07TSC47PH",
            ]
        ),
        client,
    )

    assert client.calls == [["B07TSC47PH"]]
    assert [row["status"] for row in rows] == ["FOUND", "FOUND"]
    assert [row["verification"] for row in rows] == [KEEPA_VERIFIED, KEEPA_VERIFIED]


def test_resolve_candidates_marks_keepa_not_found():
    rows = resolve_candidates(
        "A,https://www.amazon.co.jp/dp/B07TSC47PH",
        FakeResolverClient(found_asins=set()),
    )

    assert rows[0]["status"] == "UNKNOWN"
    assert rows[0]["verification"] == KEEPA_NOT_FOUND


def test_resolve_candidates_marks_keepa_errors():
    rows = resolve_candidates(
        "A,https://www.amazon.co.jp/dp/B07TSC47PH",
        FakeResolverClient(error=KeepaClientError("Keepa failed")),
    )

    assert rows[0]["status"] == "ERROR"
    assert rows[0]["verification"] == "ERROR"
    assert rows[0]["note"] == "Keepa failed"


def test_resolver_csv_uses_expected_columns_and_utf8_sig():
    data = rows_to_resolver_csv(
        [
            {
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
