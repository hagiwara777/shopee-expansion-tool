import csv
from io import StringIO
from typing import Iterable


CSV_COLUMNS = [
    "seed_asin",
    "candidate_asin",
    "brand",
    "category",
    "product_title",
    "source",
    "token_estimate",
    "fetched_at",
    "duplicate_flag",
    "note",
    "guardrail_status",
    "guardrail_risk_category",
    "guardrail_matched_terms",
    "guardrail_source",
    "guardrail_note",
]


def rows_to_csv(rows: Iterable[dict]) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()

    for row in rows:
        writer.writerow({column: row.get(column, "") or "" for column in CSV_COLUMNS})

    return buffer.getvalue().encode("utf-8-sig")
