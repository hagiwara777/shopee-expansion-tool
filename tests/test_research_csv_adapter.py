import csv
from io import StringIO

from modules.research_csv_adapter import (
    COUNTRY_NOT_PH,
    DUPLICATE_SUPERSEDED,
    LOCATION_NOT_JAPAN,
    MANIFEST_COLUMNS,
    MARKETPLACE_REVIEW,
    RESOLVER_TSV_COLUMNS,
    SCHEMA_ERROR,
    TITLE_EMPTY,
    TITLE_REVIEW,
    URL_INVALID,
    ResearchCsvInput,
    assign_source_ids,
    clean_research_title,
    import_research_csvs,
)


HEADERS = [
    "Country",
    "Location",
    "Name",
    "Product URL",
    "Search Date",
    "Shop URL",
    "Sold",
    "Price",
    "Image URL",
]


def _row(**overrides):
    row = {
        "Country": "PH",
        "Location": "Japan",
        "Name": "Official Store Acme X-100 500ml 2 Pack Bundle Kit Case Replacement",
        "Product URL": "https://shopee.ph/product-i.100.200",
        "Search Date": "2026-07-23 15:06:27",
        "Shop URL": "https://shopee.ph/shop/100",
        "Sold": "12",
        "Price": "1000",
        "Image URL": "https://example.test/image.jpg",
    }
    row.update(overrides)
    return row


def _csv(rows, headers=HEADERS, *, encoding="utf-8-sig"):
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode(encoding)


def _result(*files):
    return import_research_csvs(
        ResearchCsvInput(filename=name, content=content) for name, content in files
    )


def test_schema_accepts_required_columns_aliases_and_multiple_files():
    alias_headers = [
        " country ",
        "location",
        "Name",
        "product_url",
        "search_date",
        "Shop URL",
        "Sold",
        "Price",
        "Image URL",
    ]
    alias_row = {
        " country ": "PH",
        "location": "Japan",
        "Name": "Camera",
        "product_url": "https://shopee.ph/product-i.11.12",
        "search_date": "2026-07-23 15:00:00",
        "Shop URL": "",
        "Sold": "",
        "Price": "",
        "Image URL": "",
    }
    result = _result(
        ("first.csv", _csv([_row()])),
        ("alias.csv", _csv([alias_row], alias_headers)),
    )

    assert result.summary["input_file_count"] == 2
    assert result.summary["total_rows"] == 2
    assert result.summary["resolver_ready_count"] == 2


def test_schema_errors_are_isolated_for_missing_empty_and_non_utf8_files():
    missing = _csv([{"Country": "PH"}], headers=["Country"])
    empty = b""
    non_utf8 = "Country,Location,Name,Product URL,Search Date\nPH,Japan,\u30c6\u30b9\u30c8,https://shopee.ph/product-i.1.2,2026-07-23".encode(
        "cp932"
    )
    valid = _csv([_row(Name="Included")])
    result = _result(
        ("missing.csv", missing),
        ("empty.csv", empty),
        ("legacy.csv", non_utf8),
        ("valid.csv", valid),
    )

    assert result.summary["resolver_ready_count"] == 1
    assert [row["source_file"] for row in result.deferred_rows[:3]] == [
        "missing.csv",
        "empty.csv",
        "legacy.csv",
    ]
    assert {row["exclusion_reason"] for row in result.deferred_rows[:3]} == {SCHEMA_ERROR}


def test_filter_requires_exact_nfkc_country_and_location_without_title_inference():
    result = _result(
        (
            "filters.csv",
            _csv(
                [
                    _row(Country=" \uff30\uff28 ", Location=" jApAn ", Name="Accepted"),
                    _row(Location="Korea", Name="Japan title is not enough", **{"Product URL": "https://shopee.ph/product-i.1.2"}),
                    _row(Country="SG", Location="Japan", Name="Singapore", **{"Product URL": "https://shopee.sg/product-i.1.3"}),
                    _row(Location="", Name="Direct from Japan", **{"Product URL": "https://shopee.ph/product-i.1.4"}),
                ]
            ),
        )
    )

    assert result.summary["ph_japan_rows"] == 1
    assert result.summary["location_not_japan_rows"] == 2
    assert result.summary["resolver_ready_count"] == 1
    assert [row["exclusion_reason"] for row in result.deferred_rows] == [
        LOCATION_NOT_JAPAN,
        COUNTRY_NOT_PH,
        LOCATION_NOT_JAPAN,
    ]


def test_marketplace_and_invalid_urls_are_deferred_without_guessing():
    result = _result(
        (
            "urls.csv",
            _csv(
                [
                    _row(**{"Product URL": "https://shopee.sg/product-i.1.2"}),
                    _row(**{"Product URL": "not a URL"}),
                    _row(**{"Product URL": ""}),
                ]
            ),
        )
    )

    assert [row["exclusion_reason"] for row in result.deferred_rows] == [
        MARKETPLACE_REVIEW,
        URL_INVALID,
        URL_INVALID,
    ]
    assert result.summary["url_or_schema_error_count"] == 2


def test_url_dedup_uses_query_fragment_normalization_latest_date_and_provenance():
    older = _row(
        Name="Older",
        **{
            "Product URL": "http://SHOPEE.PH/product-i.1.2/?source=first#one",
            "Search Date": "2026-07-23 15:00:00",
        },
    )
    newest = _row(
        Name="Newest",
        **{
            "Product URL": "https://shopee.ph/product-i.1.2#two",
            "Search Date": "2026-07-23 15:01:00",
        },
    )
    result = _result(("older.csv", _csv([older])), ("newest.csv", _csv([newest])))

    assert result.summary["unique_listing_count"] == 1
    assert result.summary["duplicate_superseded_count"] == 1
    assert result.resolver_rows[0]["input_title"] == "Newest"
    deferred = result.deferred_rows[0]
    assert deferred["exclusion_reason"] == DUPLICATE_SUPERSEDED
    assert deferred["duplicate_count"] == "2"
    assert deferred["provenance_files"] == "older.csv | newest.csv"
    included = next(row for row in result.manifest_rows if row["inclusion_status"] == "INCLUDED")
    assert included["normalized_product_url"] == "https://shopee.ph/product-i.1.2"


def test_same_search_date_uses_input_file_then_row_order_deterministically():
    first = _row(Name="First", **{"Product URL": "https://shopee.ph/product-i.1.2?a=1"})
    second = _row(Name="Second", **{"Product URL": "https://shopee.ph/product-i.1.2?a=2"})
    result = _result(("first.csv", _csv([first])), ("second.csv", _csv([second])))

    assert result.resolver_rows[0]["input_title"] == "First"
    assert result.deferred_rows[0]["raw_title"] == "Second"


def test_source_ids_are_url_stable_across_file_order_and_lengthen_collisions():
    first = _csv([_row(**{"Product URL": "https://shopee.ph/product-i.1.2"})])
    second = _csv([_row(**{"Product URL": "https://shopee.ph/product-i.3.4"})])
    forward = _result(("first.csv", first), ("second.csv", second))
    reversed_order = _result(("second.csv", second), ("first.csv", first))

    assert {row["source_id"] for row in forward.resolver_rows} == {
        row["source_id"] for row in reversed_order.resolver_rows
    }
    ids = assign_source_ids(
        {"https://shopee.ph/product-i.1.2": (), "https://shopee.ph/product-i.3.4": ()},
        hash_function=lambda value: (
            "01234567A" + "0" * 55 if value.endswith(b"1.2") else "01234567B" + "0" * 55
        ),
    )
    assert set(ids.values()) == {"JPH01234567A", "JPH01234567B"}


def test_title_cleaning_removes_sales_text_and_preserves_product_identifiers():
    raw = "\U0001f525 Official Shop Acme X-100 500ml 2 Pack Bundle Kit Case Replacement Direct from Japan!!!"
    cleaned, status = clean_research_title(raw)

    assert "Official Shop" not in cleaned
    assert "Direct from Japan" not in cleaned
    for expected in ("Acme", "X-100", "500ml", "2 Pack", "Bundle", "Kit", "Case", "Replacement"):
        assert expected in cleaned
    assert status == "CLEANED"
    assert raw == "\U0001f525 Official Shop Acme X-100 500ml 2 Pack Bundle Kit Case Replacement Direct from Japan!!!"


def test_empty_and_short_titles_are_not_sent_to_resolver_and_raw_title_is_retained():
    result = _result(
        (
            "titles.csv",
            _csv(
                [
                    _row(Name="Direct from Japan", **{"Product URL": "https://shopee.ph/product-i.1.2"}),
                    _row(Name="X1", **{"Product URL": "https://shopee.ph/product-i.1.3"}),
                ]
            ),
        )
    )

    assert not result.resolver_rows
    assert [row["exclusion_reason"] for row in result.deferred_rows] == [TITLE_EMPTY, TITLE_REVIEW]
    assert result.deferred_rows[0]["raw_title"] == "Direct from Japan"
    assert result.deferred_rows[0]["cleaned_title"] == ""


def test_generic_sourcing_text_is_marked_for_title_review():
    cleaned, status = clean_research_title(
        "Direct from Japan, Mercari, Suruga-ya, Amazon Japan, Rakuten, Yahoo Shopping or any Stores in Japan"
    )

    assert "Mercari" in cleaned
    assert status == TITLE_REVIEW


def test_exports_are_bom_encoded_fixed_and_joinable_in_input_order():
    first = _row(Name="First", **{"Product URL": "https://shopee.ph/product-i.1.2"})
    second = _row(Name="Second", **{"Product URL": "https://shopee.ph/product-i.3.4"})
    result = _result(("ordered.csv", _csv([first, second])))

    tsv = result.resolver_tsv()
    manifest = result.manifest_csv()
    deferred = result.deferred_csv()
    assert tsv.startswith(b"\xef\xbb\xbf")
    assert manifest.startswith(b"\xef\xbb\xbf")
    assert deferred.startswith(b"\xef\xbb\xbf")
    assert tsv.decode("utf-8-sig").splitlines()[0].split("\t") == list(RESOLVER_TSV_COLUMNS)
    assert manifest.decode("utf-8-sig").splitlines()[0].split(",") == list(MANIFEST_COLUMNS)
    assert [row["input_title"] for row in result.resolver_rows] == ["First", "Second"]
    manifest_by_id = {row["source_id"]: row for row in result.manifest_rows}
    assert all(manifest_by_id[row["source_id"]]["cleaned_title"] == row["input_title"] for row in result.resolver_rows)
    assert all(row["input_title"] for row in result.resolver_rows)
