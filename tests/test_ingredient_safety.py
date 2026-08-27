import csv
from dataclasses import replace
from io import StringIO

import pytest

from modules.ingredient_safety import (
    CAPTURED,
    INGREDIENT_SAFETY_PAYLOAD_VERSION,
    INGREDIENT_SAFETY_SIDECAR_SCHEMA_VERSION,
    NOT_CAPTURED,
    PROVIDER_UNSUPPORTED,
    IngredientSafetyError,
    IngredientSafetyFact,
    extract_keepa_ingredient_safety_fact,
    facts_for_candidate_rows,
    ingredient_safety_fact_from_product_data,
    parse_ingredient_safety_sidecar,
    rows_to_ingredient_safety_sidecar,
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
        fetched_at="2026-08-27T00:00:00+00:00",
        source_note="",
    )


def fact(asin="B000000001", **overrides):
    values = {
        "candidate_asin": asin,
        "provider": "keepa",
        "capture_status": CAPTURED,
        "ingredients": ("GABA",),
        "active_ingredients": (),
        "special_ingredients": (),
        "fetched_at": "2026-08-27T00:00:00+00:00",
    }
    values.update(overrides)
    return IngredientSafetyFact(**values)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  GABA  ", ("GABA",)),
        (None, ()),
        ([" one ", None, "", "two"], ("one", "two")),
        (("one", " two "), ("one", "two")),
    ],
)
def test_keepa_fact_normalizes_each_approved_field_without_splitting(value, expected):
    result = extract_keepa_ingredient_safety_fact(
        {
            "ingredients": value,
            "activeIngredients": value,
            "specialIngredients": value,
        },
        candidate_asin="B000000001",
        fetched_at="2026-08-27T00:00:00+00:00",
    )

    assert result.ingredients == expected
    assert result.active_ingredients == expected
    assert result.special_ingredients == expected
    assert result.capture_status == CAPTURED


@pytest.mark.parametrize("value", [{"term": "GABA"}, [["GABA"]], 123, [123]])
def test_keepa_fact_rejects_untrusted_structures(value):
    with pytest.raises(IngredientSafetyError):
        extract_keepa_ingredient_safety_fact(
            {"ingredients": value},
            candidate_asin="B000000001",
            fetched_at="2026-08-27T00:00:00+00:00",
        )


def test_old_cache_without_marker_is_not_captured_and_never_implies_safety():
    restored = ingredient_safety_fact_from_product_data(
        {"asin": "B000000001", "ingredients": ["ignored legacy value"]},
        candidate_asin="B000000001",
        provider="keepa",
    )

    assert restored.capture_status == NOT_CAPTURED
    assert restored.ingredients == ()


def test_new_cache_marker_round_trips_three_facts():
    restored = ingredient_safety_fact_from_product_data(
        {
            "ingredient_safety_payload_version": INGREDIENT_SAFETY_PAYLOAD_VERSION,
            "ingredient_safety_capture_status": CAPTURED,
            "ingredients": ["one"],
            "activeIngredients": ["two"],
            "specialIngredients": ["three"],
        },
        candidate_asin="B000000001",
        provider="keepa",
    )

    assert restored.ingredients == ("one",)
    assert restored.active_ingredients == ("two",)
    assert restored.special_ingredients == ("three",)


def test_canopy_is_explicitly_provider_unsupported():
    restored = ingredient_safety_fact_from_product_data(
        {},
        candidate_asin="B000000001",
        provider="canopy_test",
    )

    assert restored.capture_status == PROVIDER_UNSUPPORTED
    assert restored.ingredients == ()


def test_sidecar_round_trip_binds_exact_final_candidate_bytes():
    rows = (candidate(), candidate("B000000002"))
    candidate_bytes = rows_to_prelisting_candidate_csv(rows)
    parsed_candidate = parse_prelisting_candidate_csv(candidate_bytes, filename="candidate.csv")
    sidecar = rows_to_ingredient_safety_sidecar(
        candidate_bytes,
        rows,
        (fact(), fact("B000000002", ingredients=(), active_ingredients=("GABA",))),
    )

    parsed = parse_ingredient_safety_sidecar(
        sidecar,
        filename="safety.csv",
        candidate_content=candidate_bytes,
        candidates=parsed_candidate,
    )

    assert parsed.schema_version == INGREDIENT_SAFETY_SIDECAR_SCHEMA_VERSION
    assert [row.candidate_asin for row in parsed.rows] == ["B000000001", "B000000002"]
    assert parsed.rows[1].active_ingredients == ("GABA",)
    assert len(PRELISTING_CANDIDATE_COLUMNS) == 15


def test_expansion_and_resolver_transport_build_captured_and_unsupported_facts():
    expansion_candidate = candidate()
    resolver_candidate = replace(
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
        "ingredients": ["GABA"],
        "activeIngredients": [],
        "specialIngredients": [],
        "fetched_at": "2026-08-27T00:00:00+00:00",
    }

    expansion = facts_for_candidate_rows(
        (expansion_candidate,),
        ({"candidate_asin": "B000000001", "ingredient_safety_fact": expansion_payload},),
    )
    resolver = facts_for_candidate_rows(
        (resolver_candidate,),
        ({"asin": "B000000002", "ingredient_safety_fact": {
            "candidate_asin": "B000000002",
            "provider": "canopy_test",
            "capture_status": PROVIDER_UNSUPPORTED,
            "ingredients": [],
            "activeIngredients": [],
            "specialIngredients": [],
            "fetched_at": "2026-08-27T00:00:00+00:00",
        }},),
    )

    assert expansion[0].capture_status == CAPTURED
    assert expansion[0].ingredients == ("GABA",)
    assert resolver[0].capture_status == PROVIDER_UNSUPPORTED


def _mutate_sidecar(sidecar: bytes, **updates) -> bytes:
    text = sidecar.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
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
        ({"ingredients_json": "not-json"}, "JSON"),
        ({"schema_version": "UNKNOWN"}, "schema"),
    ],
)
def test_sidecar_rejects_sha_asin_json_and_schema_mismatch(updates, error):
    rows = (candidate(),)
    candidate_bytes = rows_to_prelisting_candidate_csv(rows)
    parsed_candidate = parse_prelisting_candidate_csv(candidate_bytes, filename="candidate.csv")
    sidecar = rows_to_ingredient_safety_sidecar(candidate_bytes, rows, (fact(),))

    with pytest.raises(IngredientSafetyError, match=error):
        parse_ingredient_safety_sidecar(
            _mutate_sidecar(sidecar, **updates),
            filename="safety.csv",
            candidate_content=candidate_bytes,
            candidates=parsed_candidate,
        )


def test_sidecar_rejects_duplicate_candidate_and_duplicate_fact_asins():
    duplicate_candidates = (candidate(), candidate())
    candidate_bytes = rows_to_prelisting_candidate_csv(duplicate_candidates)

    with pytest.raises(IngredientSafetyError, match="unique"):
        rows_to_ingredient_safety_sidecar(
            candidate_bytes,
            duplicate_candidates,
            (fact(), fact()),
        )
