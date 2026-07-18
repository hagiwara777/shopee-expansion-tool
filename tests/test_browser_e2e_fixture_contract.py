"""Contract tests for versioned, local-only Browser E2E fixtures."""

from __future__ import annotations

import csv
import json
import re
from io import StringIO
from pathlib import Path

import pytest

from modules.listing_inventory_parser import parse_listing_inventory_csv
from modules.prelisting_candidate_csv import (
    PRELISTING_CANDIDATE_COLUMNS,
    parse_prelisting_candidate_csv,
)
from modules.prelisting_gate import evaluate_prelisting_gate
from modules.prelisting_gate_csv import (
    build_prelisting_gate_export_filenames,
    build_prelisting_gate_exports,
)


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "browser_e2e" / "prelisting_gate"
FIXTURE_VERSIONS = ("v1", "v2")
UTF8_BOM = b"\xef\xbb\xbf"
EXPECTED_INVENTORY_COLUMN_COUNTS = {"v1": 7, "v2": 16}
ASIN_PATTERN = re.compile(r"B[0-9A-Z]{9}")


def _fixture_dir(version: str) -> Path:
    return FIXTURE_ROOT / version


def _expected(version: str) -> dict[str, object]:
    return json.loads((_fixture_dir(version) / "expected.json").read_text(encoding="utf-8"))


def _candidate_header(content: bytes) -> list[str]:
    return next(csv.reader(StringIO(content.decode("utf-8-sig"))))


@pytest.mark.parametrize("version", FIXTURE_VERSIONS)
def test_fixture_files_have_the_versioned_input_contract(version: str):
    fixture_dir = _fixture_dir(version)
    expected = _expected(version)
    candidate_content = (fixture_dir / "candidates.csv").read_bytes()
    existing_paths = tuple(fixture_dir.glob("existing_*.csv"))

    assert len(existing_paths) == 1
    existing_path = existing_paths[0]
    existing_content = existing_path.read_bytes()

    assert candidate_content.startswith(UTF8_BOM)
    assert _candidate_header(candidate_content) == list(PRELISTING_CANDIDATE_COLUMNS)
    candidates = parse_prelisting_candidate_csv(candidate_content, filename="candidates.csv")
    assert candidates.data_row_count == expected["candidate_count"]
    assert all(ASIN_PATTERN.fullmatch(row.candidate_asin) for row in candidates.rows)

    assert existing_content.startswith(UTF8_BOM)
    existing_lines = existing_content.decode("utf-8-sig").splitlines()
    assert len(existing_lines) >= 5
    inventory_header = next(csv.reader([existing_lines[4]]))
    assert len(inventory_header) == EXPECTED_INVENTORY_COLUMN_COUNTS[version]
    assert {"Product ID", "Parent SKU", "Model ID", "SKU", "Stock"} <= set(inventory_header)

    inventory = parse_listing_inventory_csv(
        existing_content,
        filename=existing_path.name,
        marketplace=str(expected["marketplace"]),
        shop_label=str(expected["shop_label"]),
    )
    assert inventory.header_row_number == 5
    assert inventory.data_row_count == expected["existing_listing_row_count"]
    assert inventory.unique_asin_count == expected["existing_asin_count"]
    assert len(inventory.evidence_records) == expected["evidence_count"]

    fixture_text = "\n".join(
        (
            candidate_content.decode("utf-8-sig"),
            existing_content.decode("utf-8-sig"),
            (fixture_dir / "expected.json").read_text(encoding="utf-8"),
        )
    )
    assert not re.search(r"(?i)[a-z]:\\", fixture_text)
    assert "@" not in fixture_text


@pytest.mark.parametrize("version", FIXTURE_VERSIONS)
def test_fixture_expected_values_match_the_formal_local_decision_pipeline(version: str):
    fixture_dir = _fixture_dir(version)
    expected = _expected(version)
    existing_path = next(fixture_dir.glob("existing_*.csv"))
    expected_asins = expected["asins"]

    assert isinstance(expected_asins, dict)
    assert expected["suite"] == "prelisting_gate"
    assert expected["fixture_version"] == version
    assert expected["marketplace"] in {"SG", "PH"}
    assert expected["source_type"] in {"EXPANSION", "RESOLVER"}
    assert expected["shop_count"] == 1
    assert expected["candidate_count"] == expected["audit_row_count"]
    assert expected["candidate_count"] == (
        expected["ELIGIBLE"] + expected["REVIEW"] + expected["EXCLUDE"]
    )
    assert expected["eligible_count"] == expected["ELIGIBLE"]
    assert expected["review_count"] == expected["REVIEW"]
    assert expected["exclude_count"] == expected["EXCLUDE"]
    assert set(expected["download_filenames"]) == {"eligible", "review", "audit"}
    assert tuple(expected_asins) == tuple(
        row.candidate_asin
        for row in parse_prelisting_candidate_csv(
            (fixture_dir / "candidates.csv").read_bytes(),
            filename="candidates.csv",
        ).rows
    )

    candidates = parse_prelisting_candidate_csv(
        (fixture_dir / "candidates.csv").read_bytes(),
        filename="candidates.csv",
    )
    inventory = parse_listing_inventory_csv(
        existing_path.read_bytes(),
        filename=existing_path.name,
        marketplace=str(expected["marketplace"]),
        shop_label=str(expected["shop_label"]),
    )
    result = evaluate_prelisting_gate(
        candidates,
        [inventory],
        marketplace=str(expected["marketplace"]),
        expected_shop_count=int(expected["shop_count"]),
    )
    exports = build_prelisting_gate_exports(result)

    assert result.candidate_count == expected["candidate_count"]
    assert result.eligible_count == expected["ELIGIBLE"]
    assert result.review_count == expected["REVIEW"]
    assert result.exclude_count == expected["EXCLUDE"]
    assert exports.audit_count == expected["audit_row_count"]
    assert sum(len(row.existing_evidence) for row in result.rows) == expected["evidence_count"]
    assert build_prelisting_gate_export_filenames(
        marketplace=result.marketplace,
        source_type=candidates.source_type,
    ) == expected["download_filenames"]

    actual_by_asin = {
        row.candidate.candidate_asin: {
            "guardrail": row.guardrail_status,
            "inventory": row.existing_listing_status,
            "final": row.final_eligibility,
            "reason_codes": list(row.reason_codes),
        }
        for row in result.rows
    }
    assert actual_by_asin == expected_asins

    audit_rows = list(csv.DictReader(StringIO(exports.audit_csv.decode("utf-8-sig"))))
    assert len(audit_rows) == expected["audit_row_count"]
    assert [row["candidate_asin"] for row in audit_rows] == list(expected_asins)
    for audit_row in audit_rows:
        expected_row = expected_asins[audit_row["candidate_asin"]]
        assert audit_row["marketplace"] == expected["marketplace"]
        assert audit_row["final_eligibility"] == expected_row["final"]
        assert audit_row["guardrail_status"] == expected_row["guardrail"]
        assert audit_row["reason_codes"] == "|".join(expected_row["reason_codes"])
