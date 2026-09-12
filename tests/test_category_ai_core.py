"""Offline contract tests; no test in this file claims AI semantic accuracy."""

from dataclasses import replace
import json

import pytest

from modules.category_ai_benchmark import PriceBook, ModelPrice
from modules.category_ai_core import (
    BenchmarkRequestProfile,
    CategoryAIEngine,
    CategoryAIError,
    CategoryCatalog,
    CategoryNode,
    FakeCategoryAIProvider,
    FakeProviderOutcome,
    ProductEvidence,
    TokenUsage,
    assert_profiles_comparable,
    make_fake_abstain,
    make_fake_select,
)
from modules.category_ai_prompts import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_SHA256,
)


def catalog(marketplace="PH"):
    return CategoryCatalog(
        marketplace=marketplace,
        catalog_version=f"{marketplace}-SYNTHETIC-V1",
        nodes=(
            CategoryNode(10, None, "Health", "Health", False),
            CategoryNode(20, None, "Electronics", "Electronics", False),
            CategoryNode(11, 10, "Supplements", "Health > Supplements", False),
            CategoryNode(12, 11, "Minerals", "Health > Supplements > Minerals", True),
            CategoryNode(21, 20, "Tablets", "Electronics > Tablets", True),
        ),
    )


def product(marketplace="PH"):
    return ProductEvidence(
        marketplace=marketplace,
        case_id=f"{marketplace}-001",
        asin="B000000001",
        product_title="Synthetic zinc tablet",
        keepa_category="Health",
        keepa_brand="Example",
        resolver_title="Synthetic electronic tablet accessory",
    )


def profile(model="gpt-5.6-terra"):
    return BenchmarkRequestProfile(
        model=model,
        reasoning_effort="low",
        text_verbosity="low",
        max_output_tokens=512,
        service_tier="default",
        timeout_seconds=30,
    )


def test_root_child_leaf_traversal_records_every_step_and_minimum_confidence():
    fake = FakeCategoryAIProvider(
        [
            make_fake_select(10, confidence=0.91),
            make_fake_select(11, confidence=0.72),
            make_fake_select(12, confidence=0.84),
        ]
    )
    prediction = CategoryAIEngine(fake).predict(product(), catalog(), profile())

    assert prediction.status == "COMPLETED"
    assert prediction.predicted_category_id == 12
    assert prediction.prediction_confidence == 0.72
    assert [step.parent_category_id for step in prediction.traversal_steps] == [None, 10, 11]
    assert [step.candidate_count for step in prediction.traversal_steps] == [2, 1, 1]
    assert [step.selected_category_id for step in prediction.traversal_steps] == [10, 11, 12]
    assert all(step.short_reason for step in prediction.traversal_steps)


def test_root_leaf_selection_finishes_in_one_step():
    leaf_catalog = CategoryCatalog(
        marketplace="PH",
        catalog_version="SYNTHETIC",
        nodes=(CategoryNode(1, None, "Only leaf", "Only leaf", True),),
    )
    prediction = CategoryAIEngine(
        FakeCategoryAIProvider([make_fake_select(1, confidence=0.6)])
    ).predict(product(), leaf_catalog, profile())
    assert prediction.status == "COMPLETED"
    assert prediction.api_call_count == 1
    assert prediction.prediction_confidence == 0.6


def test_low_confidence_is_recorded_but_never_used_as_confirmation_threshold():
    leaf_catalog = CategoryCatalog(
        marketplace="PH",
        catalog_version="SYNTHETIC",
        nodes=(CategoryNode(1, None, "Only leaf", "Only leaf", True),),
    )
    prediction = CategoryAIEngine(
        FakeCategoryAIProvider([make_fake_select(1, confidence=0.01)])
    ).predict(product(), leaf_catalog, profile())
    assert prediction.status == "COMPLETED"
    assert prediction.prediction_confidence == 0.01


def test_abstain_never_selects_a_category_or_invents_root_confidence():
    prediction = CategoryAIEngine(
        FakeCategoryAIProvider([make_fake_abstain(confidence=0.3)])
    ).predict(product(), catalog(), profile())
    assert prediction.status == "ABSTAIN" and prediction.abstain
    assert prediction.predicted_category_id is None
    assert prediction.prediction_confidence is None
    assert prediction.traversal_steps[0].confidence == 0.3


@pytest.mark.parametrize("category_id", [999999, 12])
def test_candidate_outside_current_step_is_fail_closed(category_id):
    prediction = CategoryAIEngine(
        FakeCategoryAIProvider([make_fake_select(category_id)])
    ).predict(product(), catalog(), profile())
    assert prediction.status == "FAILED" and prediction.abstain
    assert prediction.predicted_category_id is None
    assert prediction.error_code == "CANDIDATE_OUTSIDE_ALLOWLIST"


@pytest.mark.parametrize(
    "bad",
    [
        "not-json",
        "",
        {"decision": "SELECT"},
        {
            "prompt_version": PROMPT_VERSION,
            "product_type_summary": "x",
            "decision": "SELECT",
            "selected_category_id": None,
            "confidence": 0.5,
            "short_reason": "x",
        },
        {
            "prompt_version": PROMPT_VERSION,
            "product_type_summary": "x",
            "decision": "ABSTAIN",
            "selected_category_id": 10,
            "confidence": 0.5,
            "short_reason": "x",
        },
        '{"prompt_version":"CATEGORY_AI_BENCHMARK_PROMPT_V1",'
        '"product_type_summary":"x","decision":"ABSTAIN",'
        '"selected_category_id":null,"confidence":0.4,'
        '"confidence":0.5,"short_reason":"x"}',
    ],
)
def test_invalid_json_or_structured_output_violation_fails_closed(bad):
    prediction = CategoryAIEngine(FakeCategoryAIProvider([bad])).predict(
        product(), catalog(), profile()
    )
    assert prediction.status == "FAILED" and prediction.predicted_category_id is None
    assert prediction.error_code in {"INVALID_JSON", "SCHEMA_VIOLATION"}


@pytest.mark.parametrize("code", ["TIMEOUT", "HTTP_500", "RATE_LIMIT", "EMPTY_RESPONSE"])
def test_transport_equivalent_fake_failures_are_fail_closed(code):
    prediction = CategoryAIEngine(
        FakeCategoryAIProvider([CategoryAIError(code, api_call_count=1)])
    ).predict(product(), catalog(), profile())
    assert prediction.status == "FAILED" and prediction.error_code == code
    assert prediction.api_call_count == 1


def test_fake_provider_contract_captures_allowed_input_but_makes_no_semantic_claim():
    fake = FakeCategoryAIProvider([make_fake_abstain()])
    CategoryAIEngine(fake).predict(product(), catalog(), profile())
    payload = fake.requests[0][2]
    assert set(payload) == {"prompt_version", "marketplace", "product", "category_context"}
    assert list(payload["product"]) == [
        "product_title",
        "keepa_category",
        "keepa_brand",
        "resolver_title",
    ]
    assert payload["product"]["product_title"] == "Synthetic zinc tablet"
    assert payload["product"]["resolver_title"].endswith("tablet accessory")
    assert "product_title — strongest evidence" in SYSTEM_PROMPT
    assert "resolver_title must never override" in SYSTEM_PROMPT
    assert "Powder" in SYSTEM_PROMPT and "Tablet" in SYSTEM_PROMPT
    assert "main product" in SYSTEM_PROMPT and "replacement part" in SYSTEM_PROMPT
    # The scripted ABSTAIN is the only fake result. No semantic correctness is asserted.


def test_owner_approved_prompt_v1_content_is_byte_locked():
    assert SYSTEM_PROMPT_SHA256 == (
        "7fb5dfb95f3c9293b96acd1c50fbb382e12e4f715d0e77d0d7e93da3f587983d"
    )


def test_same_core_operates_on_ph_and_sg_synthetic_catalogs():
    for marketplace in ("PH", "SG"):
        fake = FakeCategoryAIProvider(
            [make_fake_select(10), make_fake_select(11), make_fake_select(12)]
        )
        prediction = CategoryAIEngine(fake).predict(
            product(marketplace), catalog(marketplace), profile()
        )
        assert prediction.marketplace == marketplace
        assert prediction.predicted_category_id == 12


def test_usage_cost_profile_and_prediction_hash_are_saved():
    prices = PriceBook(
        version="TEST_PRICE_V1",
        updated_at="2026-01-01",
        service_tier="default",
        models={
            "gpt-5.6-terra": ModelPrice(2.0, 0.2, 1.25, 12.0),
        },
    )
    fake = FakeCategoryAIProvider(
        [
            FakeProviderOutcome(
                make_fake_select(10, confidence=0.9),
                usage=TokenUsage(100, 20, 10, 5),
                latency_seconds=0.1,
            ),
            FakeProviderOutcome(
                make_fake_select(11, confidence=0.8),
                usage=TokenUsage(50, 0, 0, 5),
                latency_seconds=0.2,
            ),
            FakeProviderOutcome(
                make_fake_select(12, confidence=0.7),
                usage=TokenUsage(50, 0, 0, 5),
                latency_seconds=0.3,
            ),
        ]
    )
    selected_profile = profile()
    prediction = CategoryAIEngine(
        fake,
        cost_estimator=prices.estimate,
        price_config_version=prices.version,
    ).predict(product(), catalog(), selected_profile)
    assert (prediction.input_tokens, prediction.cached_tokens, prediction.output_tokens) == (
        200,
        20,
        15,
    )
    assert prediction.estimated_cost_usd == prices.estimate(
        selected_profile, TokenUsage(200, 20, 10, 15)
    )
    assert prediction.price_config_version == "TEST_PRICE_V1"
    assert prediction.benchmark_request_profile == selected_profile.to_dict()
    assert prediction.benchmark_request_profile_hash == selected_profile.profile_hash
    assert len(prediction.prediction_hash) == 64
    assert prediction.with_hash().prediction_hash == prediction.prediction_hash


def test_model_comparison_allows_only_exact_model_id_to_change():
    terra, luna = profile("gpt-5.6-terra"), profile("gpt-5.6-luna")
    assert_profiles_comparable((terra, luna))
    assert terra.profile_hash != luna.profile_hash
    assert terra.comparison_contract_hash == luna.comparison_contract_hash
    with pytest.raises(ValueError, match="settings changed"):
        assert_profiles_comparable((terra, replace(luna, max_output_tokens=999)))


def test_catalog_validation_rejects_missing_parent_and_leaf_contradiction():
    with pytest.raises(ValueError, match="missing parent"):
        CategoryCatalog(
            "PH",
            "bad",
            (
                CategoryNode(1, None, "root", "root", True),
                CategoryNode(2, 99, "x", "x", True),
            ),
        )
    with pytest.raises(ValueError, match="contradicts"):
        CategoryCatalog("PH", "bad", (CategoryNode(1, None, "x", "x", False),))
