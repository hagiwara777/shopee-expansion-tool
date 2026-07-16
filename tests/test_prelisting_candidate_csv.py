from __future__ import annotations

import csv
from io import StringIO

import pytest

from modules.prelisting_candidate_csv import (
    EXPANSION_SOURCE_TYPE,
    PRELISTING_CANDIDATE_COLUMNS,
    PRELISTING_CANDIDATE_SCHEMA_VERSION,
    RESOLVER_SOURCE,
    RESOLVER_SOURCE_TYPE,
    PrelistingCandidateCsvError,
    PrelistingCandidateRow,
    expansion_rows_to_prelisting_candidates,
    parse_prelisting_candidate_csv,
    resolver_rows_to_prelisting_candidates,
    rows_to_prelisting_candidate_csv,
)


def _expansion_input_row(**overrides: str) -> dict[str, str]:
    row = {
        "seed_asin": "B000000001",
        "candidate_asin": "B000000002",
        "product_title": "Synthetic product",
        "brand": "Synthetic brand",
        "category": "Synthetic category",
        "source": "keepa_product_finder_strict",
        "fetched_at": "2026-07-16T00:00:00+00:00",
        "note": "Synthetic note",
    }
    row.update(overrides)
    return row


def _resolver_input_row(**overrides: str) -> dict[str, str]:
    row = {
        "source_id": "R0001",
        "input_title": "Synthetic input title",
        "amazon_url": "https://www.amazon.co.jp/dp/B000000002",
        "asin": "B000000002",
        "status": "FOUND",
        "verification": "KEEPA_VERIFIED",
        "note": "Synthetic note",
        "keepa_title": "Synthetic Keepa title",
        "keepa_brand": "Synthetic Keepa brand",
        "keepa_category": "Synthetic Keepa category",
        "keepa_fetched_at": "2026-07-16T00:00:00+00:00",
    }
    row.update(overrides)
    return row


def _raw_expansion_row(**overrides: str) -> dict[str, str]:
    row = {
        "schema_version": PRELISTING_CANDIDATE_SCHEMA_VERSION,
        "source_type": EXPANSION_SOURCE_TYPE,
        "source_id": "",
        "source_asin": "B000000001",
        "candidate_asin": "B000000002",
        "input_title": "",
        "product_title": "Synthetic product",
        "brand": "Synthetic brand",
        "category": "Synthetic category",
        "amazon_url": "",
        "source_status": "",
        "source_verification": "",
        "source": "keepa_product_finder_strict",
        "fetched_at": "2026-07-16T00:00:00+00:00",
        "source_note": "Synthetic note",
    }
    row.update(overrides)
    return row


def _raw_resolver_row(**overrides: str) -> dict[str, str]:
    row = {
        "schema_version": PRELISTING_CANDIDATE_SCHEMA_VERSION,
        "source_type": RESOLVER_SOURCE_TYPE,
        "source_id": "R0001",
        "source_asin": "",
        "candidate_asin": "B000000002",
        "input_title": "Synthetic input title",
        "product_title": "Synthetic Keepa title",
        "brand": "Synthetic Keepa brand",
        "category": "Synthetic Keepa category",
        "amazon_url": "https://www.amazon.co.jp/dp/B000000002",
        "source_status": "FOUND",
        "source_verification": "KEEPA_VERIFIED",
        "source": RESOLVER_SOURCE,
        "fetched_at": "2026-07-16T00:00:00+00:00",
        "source_note": "Synthetic note",
    }
    row.update(overrides)
    return row


def _contract_csv(
    rows: list[dict[str, str]],
    *,
    header: list[str] | tuple[str, ...] = PRELISTING_CANDIDATE_COLUMNS,
) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([row.get(column, "") for column in PRELISTING_CANDIDATE_COLUMNS])
    return output.getvalue().encode("utf-8-sig")


def test_expansion_conversion_csv_contract_round_trip_and_duplicate_preservation():
    rows = expansion_rows_to_prelisting_candidates(
        [
            _expansion_input_row(
                seed_asin=" ｂ００００００００１ ",
                candidate_asin=" b000000002 ",
                product_title='日本語, "引用符"\n改行を含む商品名',
                note='メモ, "引用符"\n改行',
                guardrail_status="BLOCK",
                guardrail_note="Must not be exported",
                internal_only="Must not be exported",
            ),
            _expansion_input_row(
                candidate_asin="B000000002",
                product_title="",
                brand="",
                category="",
                fetched_at="",
                note="",
            ),
        ]
    )

    assert [row.candidate_asin for row in rows] == ["B000000002", "B000000002"]
    assert rows[0].source_asin == "B000000001"
    assert rows[0].source_type == EXPANSION_SOURCE_TYPE
    assert rows[0].source_status == ""
    assert rows[1].product_title == ""
    assert rows[1].brand == ""
    assert rows[1].category == ""

    content = rows_to_prelisting_candidate_csv(rows)
    assert content.startswith(b"\xef\xbb\xbf")
    decoded = content.decode("utf-8-sig")
    csv_rows = list(csv.DictReader(StringIO(decoded)))
    assert list(csv_rows[0]) == list(PRELISTING_CANDIDATE_COLUMNS)
    assert [row["candidate_asin"] for row in csv_rows] == ["B000000002", "B000000002"]
    assert csv_rows[0]["product_title"] == '日本語, "引用符"\n改行を含む商品名'
    assert csv_rows[0]["source_note"] == 'メモ, "引用符"\n改行'
    assert "guardrail_status" not in csv_rows[0]
    assert "internal_only" not in csv_rows[0]

    parsed = parse_prelisting_candidate_csv(content + b"\n", filename="synthetic-expansion.csv")
    assert parsed.schema_version == PRELISTING_CANDIDATE_SCHEMA_VERSION
    assert parsed.source_type == EXPANSION_SOURCE_TYPE
    assert parsed.data_row_count == 2
    assert [row.candidate_asin for row in parsed.rows] == ["B000000002", "B000000002"]
    assert parsed.rows[0].source_note == 'メモ, "引用符"\n改行'


@pytest.mark.parametrize(
    ("overrides", "expected_field"),
    [
        ({"seed_asin": ""}, "source_asin"),
        ({"seed_asin": "NOT-AN-ASIN"}, "source_asin"),
        ({"candidate_asin": ""}, "candidate_asin"),
        ({"candidate_asin": "NOT-AN-ASIN"}, "candidate_asin"),
        ({"source": "   "}, "source"),
    ],
)
def test_expansion_conversion_rejects_required_fields(overrides, expected_field):
    with pytest.raises(PrelistingCandidateCsvError, match=expected_field):
        expansion_rows_to_prelisting_candidates([_expansion_input_row(**overrides)])


def test_resolver_conversion_filters_ineligible_rows_and_preserves_eligible_order():
    result = resolver_rows_to_prelisting_candidates(
        [
            _resolver_input_row(
                status=" found ",
                verification=" keepa_verified ",
                input_title="日本語入力",
                keepa_title="Keepa title",
                keepa_brand="Keepa brand",
                keepa_category="Keepa category",
                keepa_fetched_at="2026-07-16T01:02:03+00:00",
            ),
            _resolver_input_row(
                source_id="",
                asin="B000000002",
                input_title="",
                amazon_url="",
                keepa_title="",
                keepa_brand="",
                keepa_category="",
                keepa_fetched_at="",
                note="",
            ),
            _resolver_input_row(status="UNKNOWN", verification="NOT_CHECKED"),
            _resolver_input_row(status="ERROR", verification="ERROR"),
            _resolver_input_row(status="UNKNOWN", verification="KEEPA_NOT_FOUND"),
            _resolver_input_row(status="FOUND", verification="NOT_CHECKED"),
        ]
    )

    assert result.input_row_count == 6
    assert result.eligible_row_count == 2
    assert result.excluded_row_count == 4
    assert [row.candidate_asin for row in result.output_rows] == ["B000000002", "B000000002"]
    assert result.output_rows[0].source_id == "R0001"
    assert result.output_rows[0].input_title == "日本語入力"
    assert result.output_rows[0].product_title == "Keepa title"
    assert result.output_rows[0].brand == "Keepa brand"
    assert result.output_rows[0].category == "Keepa category"
    assert result.output_rows[0].fetched_at == "2026-07-16T01:02:03+00:00"
    assert result.output_rows[0].amazon_url == "https://www.amazon.co.jp/dp/B000000002"
    assert result.output_rows[0].source_type == RESOLVER_SOURCE_TYPE
    assert result.output_rows[0].source == RESOLVER_SOURCE
    assert result.output_rows[0].source_status == "FOUND"
    assert result.output_rows[0].source_verification == "KEEPA_VERIFIED"
    assert result.output_rows[1].source_id == ""
    assert result.output_rows[1].product_title == ""


def test_serializer_rejects_zero_rows_and_mixed_source_types():
    with pytest.raises(PrelistingCandidateCsvError, match="0件"):
        rows_to_prelisting_candidate_csv([])

    expansion_row = expansion_rows_to_prelisting_candidates([_expansion_input_row()])[0]
    resolver_row = resolver_rows_to_prelisting_candidates([_resolver_input_row()]).output_rows[0]
    with pytest.raises(PrelistingCandidateCsvError, match="混在"):
        rows_to_prelisting_candidate_csv([expansion_row, resolver_row])


def test_parser_ignores_complete_blank_rows_and_preserves_order_and_duplicates():
    content = _contract_csv(
        [_raw_expansion_row(), _raw_expansion_row(source_id="", candidate_asin="B000000002")]
    ) + b"\n"

    result = parse_prelisting_candidate_csv(content, filename="synthetic-expansion.csv")

    assert result.data_row_count == 2
    assert [row.candidate_asin for row in result.rows] == ["B000000002", "B000000002"]


@pytest.mark.parametrize(
    ("content", "expected_message"),
    [
        (b"", "空"),
        ("not-bytes", "bytes"),
        (b"\xff", "UTF-8"),
        (b'"unterminated', "CSVとして"),
        (_contract_csv([_raw_expansion_row()], header=["wrong", *PRELISTING_CANDIDATE_COLUMNS[1:]]), "ヘッダー"),
        (_contract_csv([_raw_expansion_row()], header=list(reversed(PRELISTING_CANDIDATE_COLUMNS))), "ヘッダー"),
        (_contract_csv([]), "候補行がありません"),
    ],
)
def test_parser_rejects_content_and_structural_errors(content, expected_message):
    with pytest.raises(PrelistingCandidateCsvError, match=expected_message):
        parse_prelisting_candidate_csv(content, filename="invalid.csv")


@pytest.mark.parametrize(
    ("rows", "expected_message"),
    [
        ([_raw_expansion_row(schema_version="PRELISTING_CANDIDATE_V0")], "schema_version"),
        (
            [_raw_expansion_row(), _raw_expansion_row(schema_version="PRELISTING_CANDIDATE_V0")],
            "schema_version",
        ),
        ([_raw_expansion_row(source_type="OTHER")], "source_type"),
        ([_raw_expansion_row(), _raw_resolver_row()], "混在"),
        ([_raw_expansion_row(candidate_asin="")], "candidate_asin"),
        ([_raw_expansion_row(candidate_asin="NOT-AN-ASIN")], "candidate_asin"),
        ([_raw_expansion_row(source_asin="")], "source_asin"),
        ([_raw_expansion_row(source_asin="NOT-AN-ASIN")], "source_asin"),
        ([_raw_expansion_row(source="")], "source"),
        ([_raw_resolver_row(source_status="UNKNOWN")], "source_status"),
        ([_raw_resolver_row(source_verification="NOT_CHECKED")], "source_verification"),
        ([_raw_resolver_row(source="wrong-source")], "source"),
    ],
)
def test_parser_rejects_semantic_contract_errors(rows, expected_message):
    with pytest.raises(PrelistingCandidateCsvError, match=expected_message):
        parse_prelisting_candidate_csv(_contract_csv(rows), filename="invalid.csv")


def test_parser_rejects_nonblank_rows_with_wrong_column_count():
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(PRELISTING_CANDIDATE_COLUMNS)
    writer.writerow([_raw_expansion_row()[column] for column in PRELISTING_CANDIDATE_COLUMNS[:-1]])

    with pytest.raises(PrelistingCandidateCsvError, match="列数"):
        parse_prelisting_candidate_csv(output.getvalue().encode("utf-8-sig"), filename="invalid.csv")
