"""Contract tests for the versioned, local-only Browser E2E fixtures."""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path

from modules.listing_inventory_parser import parse_listing_inventory_csv
from modules.prelisting_candidate_csv import (
    PRELISTING_CANDIDATE_COLUMNS,
    parse_prelisting_candidate_csv,
)
from modules.prelisting_gate import evaluate_prelisting_gate


FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "browser_e2e"
    / "prelisting_gate"
    / "v1"
)
CANDIDATES_PATH = FIXTURE_DIR / "candidates.csv"
EXISTING_LISTINGS_PATH = FIXTURE_DIR / "existing_sg_shop1.csv"
EXPECTED_PATH = FIXTURE_DIR / "expected.json"
UTF8_BOM = b"\xef\xbb\xbf"
EXPECTED_ASINS = ("B000000001", "B000000002", "B000000004", "B000FQTRS0")


def _expected() -> dict[str, object]:
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


def _candidate_header(content: bytes) -> list[str]:
    return next(csv.reader(StringIO(content.decode("utf-8-sig"))))


def test_fixture_files_have_the_versioned_input_contract():
    expected = _expected()
    candidate_content = CANDIDATES_PATH.read_bytes()
    existing_content = EXISTING_LISTINGS_PATH.read_bytes()

    assert candidate_content.startswith(UTF8_BOM)
    assert _candidate_header(candidate_content) == list(PRELISTING_CANDIDATE_COLUMNS)

    candidates = parse_prelisting_candidate_csv(
        candidate_content,
        filename=CANDIDATES_PATH.name,
    )
    assert candidates.data_row_count == 4
    assert tuple(row.candidate_asin for row in candidates.rows) == EXPECTED_ASINS

    assert existing_content.startswith(UTF8_BOM)
    inventory = parse_listing_inventory_csv(
        existing_content,
        filename=EXISTING_LISTINGS_PATH.name,
        marketplace=str(expected["marketplace"]),
        shop_label=str(expected["shop_label"]),
    )
    assert inventory.data_row_count == 1
    assert inventory.evidence_records[0].parent_sku == "B000000004"


def test_fixture_expected_values_match_the_formal_local_decision_pipeline():
    expected = _expected()
    expected_asins = expected["asins"]
    assert isinstance(expected_asins, dict)
    assert expected["suite"] == "prelisting_gate"
    assert expected["fixture_version"] == "v1"
    assert expected["marketplace"] == "SG"
    assert expected["shop_count"] == 1
    assert expected["shop_label"] == "SG_E2E_SHOP_1"
    assert expected["candidate_count"] == 4
    assert expected["candidate_count"] == (
        expected["ELIGIBLE"] + expected["REVIEW"] + expected["EXCLUDE"]
    )
    assert tuple(expected_asins) == EXPECTED_ASINS

    candidates = parse_prelisting_candidate_csv(
        CANDIDATES_PATH.read_bytes(),
        filename=CANDIDATES_PATH.name,
    )
    inventory = parse_listing_inventory_csv(
        EXISTING_LISTINGS_PATH.read_bytes(),
        filename=EXISTING_LISTINGS_PATH.name,
        marketplace=str(expected["marketplace"]),
        shop_label=str(expected["shop_label"]),
    )

    # This path only parses local fixture bytes and local Guardrail dictionaries.
    # It deliberately uses the production parser and evaluator; no API client is called.
    result = evaluate_prelisting_gate(
        candidates,
        [inventory],
        marketplace=str(expected["marketplace"]),
        expected_shop_count=int(expected["shop_count"]),
    )

    assert result.candidate_count == expected["candidate_count"]
    assert result.eligible_count == expected["ELIGIBLE"]
    assert result.review_count == expected["REVIEW"]
    assert result.exclude_count == expected["EXCLUDE"]

    actual_by_asin = {
        row.candidate.candidate_asin: {
            "guardrail": row.guardrail_status,
            "inventory": row.existing_listing_status,
            "final": row.final_eligibility,
        }
        for row in result.rows
    }
    assert actual_by_asin == expected_asins
