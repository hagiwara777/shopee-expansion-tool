import csv
from dataclasses import replace
from io import StringIO

import pytest

from modules.guardrails import apply_guardrails
from modules.product_text_safety import (
    CAPTURED,
    NOT_AVAILABLE,
    NOT_CAPTURED,
    PRODUCT_TEXT_SAFETY_PAYLOAD_VERSION,
    PRODUCT_TEXT_SAFETY_SIDECAR_SCHEMA_VERSION,
    PROVIDER_UNSUPPORTED,
    ProductTextSafetyError,
    ProductTextSafetyFact,
    extract_keepa_product_text_safety_fact,
    facts_for_candidate_rows,
    parse_product_text_safety_sidecar,
    product_text_safety_fact_from_product_data,
    rows_to_product_text_safety_sidecar,
)
from modules.prelisting_candidate_csv import (
    PRELISTING_CANDIDATE_COLUMNS,
    PrelistingCandidateRow,
    parse_prelisting_candidate_csv,
    rows_to_prelisting_candidate_csv,
)


def candidate(asin="B000000001"):
    return PrelistingCandidateRow(
        schema_version="PRELISTING_CANDIDATE_V1",
        source_type="EXPANSION",
        source_id="",
        source_asin="B000000009",
        candidate_asin=asin,
        input_title="",
        product_title="ordinary product",
        brand="Synthetic Brand",
        category="Synthetic Category",
        amazon_url="",
        source_status="",
        source_verification="",
        source="keepa_product_finder_strict",
        fetched_at="2026-09-01T00:00:00+00:00",
        source_note="",
    )


def fact(asin="B000000001", **overrides):
    values = {
        "candidate_asin": asin,
        "provider": "keepa",
        "capture_status": CAPTURED,
        "description": ("ordinary description",),
        "features": (),
        "short_description": (),
        "safety_warning": (),
        "item_highlights": (),
        "fetched_at": "2026-09-01T00:00:00+00:00",
    }
    values.update(overrides)
    return ProductTextSafetyFact(**values)


def test_keepa_fact_extracts_only_approved_same_name_fields_without_splitting():
    result = extract_keepa_product_text_safety_fact(
        {
            "description": " description ",
            "features": [" feature one ", "feature two"],
            "shortDescription": " short ",
            "safetyWarning": [" warning "],
            "itemHighlights": (" highlight ",),
            "otherDescription": "must not be captured",
        },
        candidate_asin="B000000001",
        fetched_at="2026-09-01T00:00:00+00:00",
    )

    assert result.capture_status == CAPTURED
    assert result.description == ("description",)
    assert result.features == ("feature one", "feature two")
    assert result.short_description == ("short",)
    assert result.safety_warning == ("warning",)
    assert result.item_highlights == ("highlight",)


@pytest.mark.parametrize("value", [{"text": "hemp"}, [["hemp"]], 123, [123]])
def test_keepa_fact_rejects_untrusted_text_structures(value):
    with pytest.raises(ProductTextSafetyError):
        extract_keepa_product_text_safety_fact(
            {"description": value},
            candidate_asin="B000000001",
            fetched_at="2026-09-01T00:00:00+00:00",
        )


def test_new_response_without_product_text_is_not_available():
    result = extract_keepa_product_text_safety_fact(
        {},
        candidate_asin="B000000001",
        fetched_at="2026-09-01T00:00:00+00:00",
    )

    assert result.capture_status == NOT_AVAILABLE
    assert result.description == ()


def test_old_cache_is_not_captured_and_canopy_is_provider_unsupported():
    old = product_text_safety_fact_from_product_data(
        {"description": "untrusted legacy text"},
        candidate_asin="B000000001",
        provider="keepa",
    )
    canopy = product_text_safety_fact_from_product_data(
        {},
        candidate_asin="B000000002",
        provider="canopy_test",
    )

    assert old.capture_status == NOT_CAPTURED
    assert old.description == ()
    assert canopy.capture_status == PROVIDER_UNSUPPORTED


@pytest.mark.parametrize(
    ("capture_status", "description"),
    [
        (CAPTURED, ["captured text"]),
        (NOT_AVAILABLE, []),
    ],
)
def test_new_keepa_cache_round_trips_capture_status(capture_status, description):
    restored = product_text_safety_fact_from_product_data(
        {
            "product_text_safety_payload_version": PRODUCT_TEXT_SAFETY_PAYLOAD_VERSION,
            "product_text_safety_capture_status": capture_status,
            "description": description,
            "features": [],
            "shortDescription": [],
            "safetyWarning": [],
            "itemHighlights": [],
        },
        candidate_asin="B000000001",
        provider="keepa",
    )

    assert restored.capture_status == capture_status


def test_sidecar_round_trip_binds_final_candidate_bytes_and_keeps_15_columns():
    rows = (candidate(), candidate("B000000002"))
    candidate_bytes = rows_to_prelisting_candidate_csv(rows)
    parsed_candidate = parse_prelisting_candidate_csv(candidate_bytes, filename="candidate.csv")
    sidecar = rows_to_product_text_safety_sidecar(
        candidate_bytes,
        rows,
        (fact(), fact("B000000002", description=(), features=("hemp feature",))),
    )

    parsed = parse_product_text_safety_sidecar(
        sidecar,
        filename="product-text.csv",
        candidate_content=candidate_bytes,
        candidates=parsed_candidate,
    )

    assert parsed.schema_version == PRODUCT_TEXT_SAFETY_SIDECAR_SCHEMA_VERSION
    assert parsed.rows[1].features == ("hemp feature",)
    assert len(PRELISTING_CANDIDATE_COLUMNS) == 15


def test_expansion_and_resolver_use_one_product_text_transport_contract():
    expansion = candidate()
    resolver = replace(
        candidate("B000000002"),
        source_type="RESOLVER",
        source_asin="",
        source_id="R0001",
        source_status="FOUND",
        source_verification="CANOPY_VERIFIED",
        source="asin_resolver_canopy_verified",
    )
    expansion_payload = {
        "candidate_asin": "B000000001",
        "provider": "keepa",
        "capture_status": CAPTURED,
        "description": ["description"],
        "features": [],
        "shortDescription": [],
        "safetyWarning": [],
        "itemHighlights": [],
        "fetched_at": "2026-09-01T00:00:00+00:00",
    }
    resolver_payload = {
        "candidate_asin": "B000000002",
        "provider": "canopy_test",
        "capture_status": PROVIDER_UNSUPPORTED,
        "description": [],
        "features": [],
        "shortDescription": [],
        "safetyWarning": [],
        "itemHighlights": [],
        "fetched_at": "2026-09-01T00:00:00+00:00",
    }

    expansion_facts = facts_for_candidate_rows(
        (expansion,),
        ({"candidate_asin": expansion.candidate_asin, "product_text_safety_fact": expansion_payload},),
    )
    resolver_facts = facts_for_candidate_rows(
        (resolver,),
        ({"asin": resolver.candidate_asin, "product_text_safety_fact": resolver_payload},),
    )

    assert expansion_facts[0].description == ("description",)
    assert resolver_facts[0].capture_status == PROVIDER_UNSUPPORTED


def _mutate_sidecar(sidecar: bytes, **updates) -> bytes:
    reader = csv.DictReader(StringIO(sidecar.decode("utf-8-sig")))
    rows = list(reader)
    rows[0].update(updates)
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


@pytest.mark.parametrize(
    ("updates", "error"),
    [
        ({"candidate_sha256": "0" * 64}, "SHA-256"),
        ({"candidate_asin": "B000000002"}, "ASIN"),
        ({"description_json": "not-json"}, "JSON"),
        ({"schema_version": "UNKNOWN"}, "schema"),
    ],
)
def test_sidecar_rejects_sha_asin_json_and_schema_mismatch(updates, error):
    rows = (candidate(),)
    candidate_bytes = rows_to_prelisting_candidate_csv(rows)
    parsed_candidate = parse_prelisting_candidate_csv(candidate_bytes, filename="candidate.csv")
    sidecar = rows_to_product_text_safety_sidecar(candidate_bytes, rows, (fact(),))

    with pytest.raises(ProductTextSafetyError, match=error):
        parse_product_text_safety_sidecar(
            _mutate_sidecar(sidecar, **updates),
            filename="product-text.csv",
            candidate_content=candidate_bytes,
            candidates=parsed_candidate,
        )


@pytest.mark.parametrize(
    "product_text",
    ["hemp", "HEMP-FREE formula", "cold pressed hempseed oil"],
)
@pytest.mark.parametrize("field", ["product_title", "description", "features"])
def test_ph_hemp_literal_substring_blocks_in_title_description_and_features(
    product_text, field
):
    row = {
        "candidate_asin": "B000000001",
        "brand": "Synthetic Brand",
        "product_title": "ordinary product",
        "category": "Synthetic Category",
    }
    row[field] = product_text if field == "product_title" else [product_text]

    result = apply_guardrails((row,), marketplace="PH")[0]

    assert result["guardrail_status"] == "BLOCK"
    assert "hemp" in result["guardrail_matched_terms"].lower()


def test_hemp_rule_is_not_applied_to_sg_and_unapproved_alias_is_not_added():
    hemp = {
        "candidate_asin": "B000000001",
        "brand": "Synthetic Brand",
        "product_title": "ordinary product",
        "category": "Synthetic Category",
        "description": ["hemp product"],
    }
    inferred_alias = {**hemp, "description": ["CBD product"]}

    assert apply_guardrails((hemp,), marketplace="SG")[0]["guardrail_status"] == "SAFE"
    assert apply_guardrails((inferred_alias,), marketplace="PH")[0]["guardrail_status"] == "SAFE"


@pytest.mark.parametrize(
    "capture_status",
    [NOT_CAPTURED, NOT_AVAILABLE, PROVIDER_UNSUPPORTED],
)
def test_uncaptured_status_without_text_does_not_block_or_review(capture_status):
    provider = "canopy_test" if capture_status == PROVIDER_UNSUPPORTED else "keepa"
    empty_fact = fact(
        provider=provider,
        capture_status=capture_status,
        description=(),
    )
    row = {
        "candidate_asin": empty_fact.candidate_asin,
        "brand": "Synthetic Brand",
        "product_title": "ordinary product",
        "category": "Synthetic Category",
        "description": empty_fact.description,
        "features": empty_fact.features,
    }

    assert apply_guardrails((row,), marketplace="PH")[0]["guardrail_status"] == "SAFE"
