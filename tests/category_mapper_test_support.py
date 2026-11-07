"""Synthetic SG Gate rows shared by mapper and review tests."""
import csv
from io import StringIO
import logging
from modules.prelisting_gate_csv import PRELISTING_GATE_RESULT_COLUMNS


def _standard_logger_warning(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.WARNING):
        self._log(logging.WARNING, message, args, **kwargs)


def _csv_bytes(columns, rows):
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def _sg_gate_csv():
    row = {column: "" for column in PRELISTING_GATE_RESULT_COLUMNS}
    row.update(
        {
            "gate_schema_version": "PRELISTING_GATE_RESULT_V1",
            "candidate_asin": "B000000001",
            "final_eligibility": "ELIGIBLE",
            "marketplace": "SG",
            "candidate_schema_version": "PRELISTING_CANDIDATE_V1",
            "source_type": "EXPANSION",
            "source_asin": "B000000000",
            "product_title": "Example personal care item",
            "brand": "Example Brand",
            "category": "Personal Care",
            "guardrail_status": "SAFE",
            "existing_listing_status": "CLEAR",
            "input_duplicate_status": "UNIQUE",
            "source_asin_status": "CLEAR",
            "metadata_status": "COMPLETE",
        }
    )
    return _csv_bytes(PRELISTING_GATE_RESULT_COLUMNS, [row])
