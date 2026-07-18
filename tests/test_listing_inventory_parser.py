from __future__ import annotations

import csv
from io import StringIO

import pytest

from modules.listing_inventory_parser import (
    ListingInventoryFileResult,
    ListingInventoryParseError,
    build_existing_asin_index,
    parse_listing_inventory_csv,
)


FILENAME = "existing-listings.csv"
MARKETPLACE = "SG"
SHOP_LABEL = "Main shop"
HEADER = ["", "Product ID", "Parent SKU", "Model ID", "SKU", "Stock", "Product Name"]


def _csv_bytes(rows: list[list[str]], *, bom: bool = False) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(rows)
    encoded = output.getvalue().encode("utf-8")
    return b"\xef\xbb\xbf" + encoded if bom else encoded


def _inventory_csv(
    data_rows: list[list[str]],
    *,
    header: list[str] | None = None,
    bom: bool = False,
) -> bytes:
    metadata_rows = [
        ["Report", "Existing listings"],
        ["Generated", "Synthetic only"],
        ["Marketplace", MARKETPLACE],
        ["Shop", SHOP_LABEL],
    ]
    return _csv_bytes(metadata_rows + [header or HEADER] + data_rows, bom=bom)


def _parse(
    content: bytes,
    *,
    filename: str = FILENAME,
    marketplace: str = MARKETPLACE,
    shop_label: str = SHOP_LABEL,
):
    return parse_listing_inventory_csv(
        content,
        filename=filename,
        marketplace=marketplace,
        shop_label=shop_label,
    )


def _data_row(
    product_id: str,
    parent_sku: str,
    model_id: str = "MODEL-1",
    sku: str = "",
    stock: str = "1",
    product_name: str = "Synthetic product",
) -> list[str]:
    return ["", product_id, parent_sku, model_id, sku, stock, product_name]


def test_parses_metadata_bom_blank_leading_column_and_all_asin_evidence():
    result = _parse(
        _inventory_csv(
            [
                _data_row("P-1", " B07TSC47PH ", stock="0", product_name="One"),
                [""],
                _data_row("P-2", "B08C4Z1XF4", "MODEL-2", "B0GQ9ZD41R", "5", "Two"),
                _data_row("P-3", "B07TSC47PH", "MODEL-3", "B07TSC47PH", "2", "Three"),
            ],
            bom=True,
        )
    )

    assert result.header_row_number == 5
    assert result.data_row_count == 3
    assert result.unique_asin_count == 3
    assert [record.asin for record in result.evidence_records] == [
        "B07TSC47PH",
        "B08C4Z1XF4",
        "B0GQ9ZD41R",
        "B07TSC47PH",
        "B07TSC47PH",
    ]
    assert [record.match_field for record in result.evidence_records] == [
        "Parent SKU",
        "Parent SKU",
        "SKU",
        "Parent SKU",
        "SKU",
    ]
    assert result.evidence_records[0].source_row_number == 6
    assert result.evidence_records[0].stock == "0"
    assert result.evidence_records[1].product_name == "Two"


def test_normalizes_nfkc_and_uppercases_asins():
    result = _parse(
        _inventory_csv(
            [_data_row("P-1", " ｂ０７ｔｓｃ４７ｐｈ ", sku="b08c4z1xf4")]
        )
    )

    assert [record.asin for record in result.evidence_records] == ["B07TSC47PH", "B08C4Z1XF4"]
    assert result.evidence_records[0].parent_sku == "B07TSC47PH"
    assert result.evidence_records[0].sku == "B08C4Z1XF4"


def test_product_name_is_optional_and_blank_rows_are_ignored():
    header_without_product_name = HEADER[:-1]
    row = ["", "P-1", "B07TSC47PH", "MODEL-1", "", "0"]
    result = _parse(_inventory_csv([[""], row], header=header_without_product_name))

    assert result.data_row_count == 1
    assert result.evidence_records[0].product_name == ""


def test_build_existing_asin_index_preserves_all_evidence_and_input_order():
    first = _parse(
        _inventory_csv(
            [
                _data_row("P-1", "B07TSC47PH", sku="B08C4Z1XF4"),
                _data_row("P-2", "B07TSC47PH", sku="B07TSC47PH"),
            ]
        ),
        shop_label="Shop A",
    )
    second = _parse(
        _inventory_csv([_data_row("P-3", "B07TSC47PH")]),
        shop_label="Shop B",
    )

    index = build_existing_asin_index([first, second])

    assert list(index) == ["B07TSC47PH", "B08C4Z1XF4"]
    assert [evidence.product_id for evidence in index["B07TSC47PH"]] == ["P-1", "P-2", "P-2", "P-3"]
    assert [evidence.match_field for evidence in index["B07TSC47PH"]] == [
        "Parent SKU",
        "Parent SKU",
        "SKU",
        "Parent SKU",
    ]
    assert [evidence.shop_label for evidence in index["B07TSC47PH"]] == [
        "Shop A",
        "Shop A",
        "Shop A",
        "Shop B",
    ]


def test_header_matching_is_exact_after_normalization():
    partial_header = ["", "Product Identifier", "Parent SKU", "Model ID", "SKU", "Stock"]

    with pytest.raises(ListingInventoryParseError, match="Product ID"):
        _parse(_inventory_csv([], header=partial_header))


@pytest.mark.parametrize("missing_header", ["Product ID", "Parent SKU", "Model ID", "SKU", "Stock"])
def test_missing_required_header_fails_closed(missing_header: str):
    header = [column for column in HEADER if column != missing_header]

    with pytest.raises(ListingInventoryParseError, match=missing_header):
        _parse(_inventory_csv([], header=header))


def test_missing_header_and_multiple_headers_fail_closed():
    with pytest.raises(ListingInventoryParseError, match="必須ヘッダー"):
        _parse(_csv_bytes([["not", "an", "inventory"], ["P-1", "B07TSC47PH"]]))

    content = _csv_bytes([HEADER, HEADER, _data_row("P-1", "B07TSC47PH")])
    with pytest.raises(ListingInventoryParseError, match="複数"):
        _parse(content)


def test_empty_non_utf8_and_malformed_csv_fail_closed():
    with pytest.raises(ListingInventoryParseError, match="空"):
        _parse(b"")

    with pytest.raises(ListingInventoryParseError, match="UTF-8"):
        _parse(b"\xff\xfe\x00")

    with pytest.raises(ListingInventoryParseError, match="CSVとして解析"):
        _parse(b'"unterminated')


@pytest.mark.parametrize(
    ("marketplace", "filename", "expected_marketplace"),
    [
        ("SG", "Shopee 更新_SG.csv", "SG"),
        (" ph ", "Shopee 更新_PH.csv", "PH"),
        ("ｐｈ", "Shopee 更新_ｐｈ.csv", "PH"),
    ],
)
def test_formal_zero_listing_csv_is_a_valid_empty_inventory(
    marketplace: str,
    filename: str,
    expected_marketplace: str,
):
    result = _parse(_inventory_csv([[], ["", "  "]]), marketplace=marketplace, filename=filename)

    assert result.marketplace == expected_marketplace
    assert result.data_row_count == 0
    assert result.unique_asin_count == 0
    assert result.evidence_records == ()
    assert build_existing_asin_index([result]) == {}


@pytest.mark.parametrize(
    ("marketplace", "filename"),
    [
        ("PH", "Shopee 更新_SG.csv"),
        ("SG", "Shopee 更新_PH.csv"),
        ("PH", "Shopee 更新_SG_PH.csv"),
    ],
)
def test_explicit_filename_marketplace_mismatch_fails_closed(marketplace: str, filename: str):
    with pytest.raises(ListingInventoryParseError, match="市場表記"):
        _parse(_inventory_csv([]), marketplace=marketplace, filename=filename)


def test_filename_without_marketplace_and_ordinary_words_are_accepted():
    result = _parse(_inventory_csv([]), marketplace="PH", filename="pharmacy_sgproduct.csv")

    assert result.marketplace == "PH"


def test_parent_sku_blank_fails_with_filename_line_and_column():
    with pytest.raises(ListingInventoryParseError) as exc_info:
        _parse(_inventory_csv([_data_row("P-1", "", sku="B07TSC47PH")]))

    message = str(exc_info.value)
    assert FILENAME in message
    assert "6行目" in message
    assert "Parent SKU" in message


@pytest.mark.parametrize(
    ("column_name", "row"),
    [
        ("Parent SKU", _data_row("P-1", "NOT-AN-ASIN")),
        ("SKU", _data_row("P-1", "B07TSC47PH", sku="INVALID")),
    ],
)
def test_invalid_asin_fails_with_filename_line_column_and_value(column_name: str, row: list[str]):
    with pytest.raises(ListingInventoryParseError) as exc_info:
        _parse(_inventory_csv([row]))

    message = str(exc_info.value)
    assert FILENAME in message
    assert "6行目" in message
    assert column_name in message
    assert "INVALID" in message or "NOT-AN-ASIN" in message


def test_broken_product_id_row_fails_closed():
    with pytest.raises(ListingInventoryParseError, match="Product ID"):
        _parse(_inventory_csv([_data_row("", "B07TSC47PH")]))


def test_index_accepts_empty_and_rejects_mixed_marketplace_results():
    empty_result = ListingInventoryFileResult(
        marketplace="SG",
        shop_label="Empty",
        source_file="empty.csv",
        header_row_number=5,
        data_row_count=0,
        unique_asin_count=0,
        evidence_records=(),
    )
    assert build_existing_asin_index([empty_result]) == {}

    sg_result = _parse(_inventory_csv([_data_row("P-1", "B07TSC47PH")]))
    ph_result = ListingInventoryFileResult(
        marketplace="PH",
        shop_label=sg_result.shop_label,
        source_file=sg_result.source_file,
        header_row_number=sg_result.header_row_number,
        data_row_count=sg_result.data_row_count,
        unique_asin_count=sg_result.unique_asin_count,
        evidence_records=sg_result.evidence_records,
    )
    with pytest.raises(ListingInventoryParseError, match="マーケットプレイス"):
        build_existing_asin_index([sg_result, ph_result])
