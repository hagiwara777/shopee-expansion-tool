"""Candidate conversion keeps its shared fixed CSV contract."""
import csv
from io import StringIO
import modules.prelisting_candidate_csv as prelisting_candidate_csv


def test_ui_adapter_equivalent_csvs_use_the_phase2a_fixed_contract_without_api_calls():
    expansion_rows = [
        {
            "seed_asin": "B000000001",
            "candidate_asin": "B000000002",
            "product_title": "Synthetic expansion title",
            "brand": "Synthetic brand",
            "category": "Synthetic category",
            "source": "synthetic_expansion",
            "fetched_at": "2026-07-16T00:00:00+00:00",
            "note": "",
            "guardrail_status": "BLOCK",
        }
    ]
    resolver_rows = [
        {
            "source_id": "R0001",
            "input_title": "Synthetic resolver title",
            "amazon_url": "https://www.amazon.co.jp/dp/B000000003",
            "asin": "B000000003",
            "status": "FOUND",
            "verification": "KEEPA_VERIFIED",
            "keepa_title": "Synthetic Keepa title",
            "keepa_brand": "Synthetic Keepa brand",
            "keepa_category": "Synthetic Keepa category",
            "keepa_fetched_at": "2026-07-16T00:00:00+00:00",
            "note": "",
        },
        {
            "source_id": "R0002",
            "asin": "B000000004",
            "status": "UNKNOWN",
            "verification": "KEEPA_NOT_FOUND",
        },
    ]

    expansion_csv = prelisting_candidate_csv.rows_to_prelisting_candidate_csv(
        prelisting_candidate_csv.expansion_rows_to_prelisting_candidates(expansion_rows)
    )
    resolver_conversion = prelisting_candidate_csv.resolver_rows_to_prelisting_candidates(resolver_rows)
    resolver_csv = prelisting_candidate_csv.rows_to_prelisting_candidate_csv(
        resolver_conversion.output_rows
    )

    expansion_header = next(csv.reader(StringIO(expansion_csv.decode("utf-8-sig"))))
    resolver_header = next(csv.reader(StringIO(resolver_csv.decode("utf-8-sig"))))
    resolver_file = prelisting_candidate_csv.parse_prelisting_candidate_csv(
        resolver_csv,
        filename="synthetic_resolver.csv",
    )

    assert expansion_header == list(prelisting_candidate_csv.PRELISTING_CANDIDATE_COLUMNS)
    assert resolver_header == list(prelisting_candidate_csv.PRELISTING_CANDIDATE_COLUMNS)
    assert "guardrail_status" not in expansion_header
    assert resolver_conversion.input_row_count == 2
    assert resolver_conversion.eligible_row_count == 1
    assert resolver_conversion.excluded_row_count == 1
    assert resolver_file.rows[0].category == "Synthetic Keepa category"
    assert resolver_file.rows[0].fetched_at == "2026-07-16T00:00:00+00:00"
