import csv
from io import StringIO

from modules.export_csv import CSV_COLUMNS, rows_to_csv


def test_rows_to_csv_uses_expected_columns_and_utf8_sig():
    data = rows_to_csv(
        [
            {
                "seed_asin": "B07TSC47PH",
                "candidate_asin": "B000000001",
                "product_title": "Sample",
                "brand": "Brand",
                "category": "Category",
                "source": "keepa_product_finder_brand_category",
                "token_estimate": "21",
                "fetched_at": "2026-07-09T00:00:00+00:00",
                "duplicate_flag": "false",
                "note": "",
                "guardrail_status": "SAFE",
                "guardrail_risk_category": "",
                "guardrail_matched_terms": "",
                "guardrail_source": "",
                "guardrail_note": "No guardrail dictionary match.",
                "ignored": "value",
            }
        ]
    )

    assert data.startswith(b"\xef\xbb\xbf")
    decoded = data.decode("utf-8-sig")
    header = decoded.splitlines()[0].split(",")
    assert header == CSV_COLUMNS


def test_rows_to_csv_fills_missing_values_with_blank():
    decoded = rows_to_csv(
        [{"seed_asin": "B07TSC47PH", "candidate_asin": "B000000001"}]
    ).decode("utf-8-sig")
    rows = list(csv.DictReader(StringIO(decoded)))

    assert rows[0] == {
        "seed_asin": "B07TSC47PH",
        "candidate_asin": "B000000001",
        "brand": "",
        "category": "",
        "product_title": "",
        "source": "",
        "token_estimate": "",
        "fetched_at": "",
        "duplicate_flag": "",
        "note": "",
        "guardrail_status": "",
        "guardrail_risk_category": "",
        "guardrail_matched_terms": "",
        "guardrail_source": "",
        "guardrail_note": "",
    }
