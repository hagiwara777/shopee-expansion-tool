"""Unit coverage for Category Mapper Ver0.2 AI shadow mode."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from urllib.error import HTTPError

import pytest

from modules.category_mapper import MapperRecommendation, build_mapper_exports
from modules.category_mapper_ai import (
    CategoryShadowConfigurationError,
    CategoryShadowResponse,
    CategoryShadowGroup,
    CategoryShadowOutputError,
    CategoryShadowProviderError,
    FakeCategoryShadowProvider,
    MAX_OUTPUT_TOKENS,
    OpenAIResponsesCategoryShadowProvider,
    PROMPT_VERSION,
    RankedCategory,
    ShadowCategoryCandidate,
    ShadowPrediction,
    build_shadow_groups,
    prefilter_category_candidates,
    rescore_saved_shadow_predictions,
    run_category_shadow,
    shadow_kpis,
    validate_shadow_response,
)
from modules.category_mapper_store import CategoryMapperStore, normalize_brand, normalize_mapping_key


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "category_mapper" / "ai_shadow_ph_groups.json"


@pytest.fixture()
def store(tmp_path: Path) -> CategoryMapperStore:
    result = CategoryMapperStore(tmp_path / "category_mapper.sqlite3")
    _seed_fixture_categories(result)
    return result


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _seed_fixture_categories(store: CategoryMapperStore) -> None:
    fixture = _fixture()
    parents: dict[tuple[int, ...], int] = {}
    categories: list[dict] = []
    next_parent_id = 900000
    for entry in fixture["categories"]:
        parts = entry["path"].split(" > ")
        parent_id = None
        for depth, name in enumerate(parts):
            key = tuple(parts[: depth + 1])
            is_leaf = depth == len(parts) - 1
            if is_leaf:
                category_id = entry["id"]
            else:
                category_id = parents.get(key)
                if category_id is None:
                    next_parent_id += 1
                    category_id = next_parent_id
                    parents[key] = category_id
            categories.append(
                {
                    "category_id": category_id,
                    "parent_category_id": parent_id,
                    "category_name": name,
                    "is_leaf": is_leaf,
                    "is_others": is_leaf and name == "Others",
                }
            )
            parent_id = category_id
    store.save_categories("PH", categories)


def _group(
    *,
    title: str,
    keepa_category: str,
    canonical_product_type: str = "",
    selected_category_id: int | None = None,
    selected_status: str = "",
) -> CategoryShadowGroup:
    normalized_category = normalize_mapping_key(keepa_category)
    return CategoryShadowGroup(
        marketplace="PH",
        group_key=f"PH|{normalized_category}|asience|{canonical_product_type or 'UNCLASSIFIED'}",
        normalized_keepa_category=normalized_category,
        normalized_keepa_brand="asience",
        canonical_product_type=canonical_product_type,
        representative_titles=(title,),
        resolver_titles=(),
        asin_count=2,
        is_main_product=not bool(canonical_product_type == "SHAMPOO_CONDITIONER_SET" or "case" in title.lower() or "replacement" in title.lower()),
        is_set=canonical_product_type == "SHAMPOO_CONDITIONER_SET" or " set" in title.lower(),
        is_accessory="case" in title.lower(),
        is_replacement_part="replacement" in title.lower(),
        selected_category_id=selected_category_id,
        selected_verification_status=selected_status,
    )


def _recommendation(
    *,
    asin: str,
    title: str,
    keepa_category: str,
    canonical_product_type: str = "",
    category_id: int | None = None,
    category_path: str = "",
    verification_status: str = "",
    confirmed: bool = False,
) -> MapperRecommendation:
    return MapperRecommendation(
        marketplace="PH",
        source_type="EXPANSION",
        source_asin="B000000000",
        candidate_asin=asin,
        product_title=title,
        keepa_brand="ASIENCE",
        keepa_category=keepa_category,
        resolver_input_title="",
        input_safety_state="GATE_ELIGIBLE",
        canonical_product_type=canonical_product_type,
        category_recommendation_status="CONFIRMED" if confirmed else "UNMAPPED",
        recommended_category_id=category_id,
        recommended_category_path=category_path,
        category_confidence="HIGH" if confirmed else "",
        category_recommendation_source="TEST",
        category_verification_status=verification_status,
        mandatory_attribute_count=0,
        no_brand_available=True,
        canonical_brand_candidate="",
        brand_match_status="NO_BRAND_SELECTED" if confirmed else "NOT_FOUND",
        recommended_brand_id=0 if confirmed else None,
        recommended_brand_name="No brand" if confirmed else "",
        brand_confidence="HIGH" if confirmed else "",
        brand_recommendation_source="TEST",
        brand_accuracy_warning="",
        category_is_confirmed=confirmed,
        brand_is_confirmed=False,
        no_brand_selected_by_user=confirmed,
        manual_review_required=False,
        manual_review_reason="",
    )


def _valid_payload(category_id: int) -> dict:
    return {
        "schema_version": "CATEGORY_SHADOW_V1",
        "canonical_product_type": "SHAMPOO",
        "is_main_product": True,
        "is_set": False,
        "is_accessory": False,
        "is_replacement_part": False,
        "risk_flags": [],
        "abstain": False,
        "abstain_reason": "",
        "ranked_candidates": [
            {"category_id": category_id, "confidence": 0.9, "short_reason": "Local candidate matches evidence."}
        ],
    }


def _payload_for_group(group: CategoryShadowGroup, category_id: int, *, ranked_ids: tuple[int, ...] | None = None) -> dict:
    """Create one strict, non-secret fake response aligned to the group guard."""

    payload = _valid_payload(category_id)
    payload.update(
        {
            "canonical_product_type": group.canonical_product_type,
            "is_main_product": group.is_main_product,
            "is_set": group.is_set,
            "is_accessory": group.is_accessory,
            "is_replacement_part": group.is_replacement_part,
            "ranked_candidates": [
                {
                    "category_id": candidate_id,
                    "confidence": 0.9 - index * 0.1,
                    "short_reason": "Local candidate matches evidence.",
                }
                for index, candidate_id in enumerate(ranked_ids or (category_id,))
            ],
            "_usage": {"input_tokens": 100, "output_tokens": 20, "cached_tokens": 10},
        }
    )
    return payload


def test_fixture_uses_real_ph_leaf_categories_and_all_required_product_groups(store: CategoryMapperStore):
    fixture = _fixture()
    names = {item["name"] for item in fixture["groups"]}
    assert {
        "Shampoo", "Conditioner", "Shampoo Conditioner Set", "Hair Treatment", "Plush Toy",
        "Plush Toy Storage Case", "Smartphone Case", "Smartphone", "T-shirt", "Apparel Set",
        "Food", "Supplement", "Camera", "Camera Case", "Replacement Part", "Unknown",
    } <= names
    for category in fixture["categories"]:
        loaded = store.get_category("PH", category["id"])
        assert loaded is not None
        assert loaded["is_leaf"] == 1


def test_prefilter_is_ph_leaf_only_capped_and_prefers_user_confirmed_mapping(store: CategoryMapperStore):
    store.save_category_mapping(
        marketplace="PH",
        mapping_key_type="KEEPA_CATEGORY",
        mapping_key="リンス・コンディショナー",
        canonical_product_type="CONDITIONER",
        category_id=100872,
        category_path="Beauty > Hair Care > Hair and Scalp Conditioner",
    )
    group = _group(
        title="ASIENCE conditioner refill",
        keepa_category="リンス・コンディショナー",
        canonical_product_type="CONDITIONER",
    )
    candidates = prefilter_category_candidates(group, store)
    assert 1 <= len(candidates) <= 20
    assert candidates[0].category_id == 100872
    assert all(store.get_category("PH", item.category_id)["is_leaf"] == 1 for item in candidates)


def test_prefilter_distinguishes_main_case_replacement_and_set(store: CategoryMapperStore):
    case_candidates = prefilter_category_candidates(
        _group(title="smartphone protective case", keepa_category="Smartphone Case"), store
    )
    assert any(item.category_id == 100490 for item in case_candidates)
    assert all(item.category_id != 100073 for item in case_candidates)
    replacement_candidates = prefilter_category_candidates(
        _group(title="replacement bearing part", keepa_category="Replacement Part"), store
    )
    assert any(item.category_id == 101451 for item in replacement_candidates)
    set_candidates = prefilter_category_candidates(
        _group(
            title="shampoo & conditioner set",
            keepa_category="シャンプー・コンディショナーセット",
            canonical_product_type="SHAMPOO_CONDITIONER_SET",
        ),
        store,
    )
    assert set_candidates == ()


def test_prefilter_no_candidate_and_others_safety(store: CategoryMapperStore):
    unknown = prefilter_category_candidates(_group(title="mystery item", keepa_category="Unknown"), store)
    assert unknown == ()
    regulated = prefilter_category_candidates(_group(title="beauty supplement", keepa_category="Supplement"), store)
    assert all("Others" not in candidate.category_path for candidate in regulated)
    assert sum("Others" in candidate.category_path for candidate in regulated) <= 1


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({**_valid_payload(999999), "ranked_candidates": [{"category_id": 999999, "confidence": 0.9, "short_reason": "x"}]}, "INVALID_AI_CATEGORY_ID"),
        ({**_valid_payload(100869), "ranked_candidates": [_valid_payload(100869)["ranked_candidates"][0]] * 4}, "INVALID_AI_RANKED_COUNT"),
        ({**_valid_payload(100869), "ranked_candidates": [{"category_id": 100869, "confidence": 2, "short_reason": "x"}]}, "INVALID_AI_CONFIDENCE"),
        ({"bad": "json"}, "INVALID_AI_SCHEMA"),
        (None, "INVALID_AI_RESPONSE_TYPE"),
    ],
)
def test_output_validation_fails_closed(payload, code):
    with pytest.raises(CategoryShadowOutputError, match=code):
        validate_shadow_response(payload, candidate_ids=(100869,))


def test_output_validation_accepts_abstain():
    response = validate_shadow_response(
        {
            "schema_version": "CATEGORY_SHADOW_V1",
            "canonical_product_type": "",
            "is_main_product": False,
            "is_set": True,
            "is_accessory": False,
            "is_replacement_part": False,
            "risk_flags": ["GROUP_TOO_BROAD"],
            "abstain": True,
            "abstain_reason": "GROUP_TOO_BROAD",
            "ranked_candidates": [],
        },
        candidate_ids=(100869,),
    )
    assert response.abstain is True
    assert response.ranked_candidates == ()


def test_shadow_run_uses_group_not_asin_cache_and_preserves_v1_exports(store: CategoryMapperStore):
    recommendations = (
        _recommendation(
            asin="B000000001", title="ASIENCE shampoo refill", keepa_category="シャンプー",
            canonical_product_type="SHAMPOO", category_id=100869,
            category_path="Beauty > Hair Care > Shampoo", verification_status="LISTING_TOOL_ACCEPTED", confirmed=True,
        ),
        _recommendation(
            asin="B000000002", title="ASIENCE shampoo refill large", keepa_category="シャンプー",
            canonical_product_type="SHAMPOO", category_id=100869,
            category_path="Beauty > Hair Care > Shampoo", verification_status="LISTING_TOOL_ACCEPTED", confirmed=True,
        ),
    )
    before = build_mapper_exports(recommendations)
    group = build_shadow_groups(recommendations)[0]
    provider = FakeCategoryShadowProvider({group.group_key: _valid_payload(100869)})
    first = run_category_shadow(recommendations=recommendations, store=store, provider=provider)
    second = run_category_shadow(recommendations=recommendations, store=store, provider=provider)
    after = build_mapper_exports(recommendations)
    assert before == after
    assert len(provider.calls) == 1
    assert first.predictions[0].top1_match is True
    assert second.predictions[0].cache_hit is True
    assert store.find_confirmed_category_mapping("PH", "KEEPA_CATEGORY", "シャンプー") is None
    assert store.find_confirmed_brand_policy("PH", "シャンプー", "ASIENCE", 100869) is None


def test_shadow_run_records_invalid_id_timeout_and_safe_provider_error(store: CategoryMapperStore):
    recommendations = (
        _recommendation(asin="B000000001", title="ASIENCE shampoo", keepa_category="シャンプー", canonical_product_type="SHAMPOO"),
        _recommendation(asin="B000000002", title="conditioner", keepa_category="リンス・コンディショナー", canonical_product_type="CONDITIONER"),
    )
    first_group = build_shadow_groups(recommendations)[0]
    invalid = FakeCategoryShadowProvider({first_group.group_key: {**_valid_payload(999999), "ranked_candidates": [{"category_id": 999999, "confidence": 0.5, "short_reason": "bad"}]}})
    invalid_result = run_category_shadow(recommendations=recommendations, store=store, provider=invalid)
    assert invalid_result.predictions[0].status == "INVALID_AI_CATEGORY_ID"
    timeout = FakeCategoryShadowProvider({first_group.group_key: CategoryShadowProviderError("TIMEOUT")})
    timeout_result = run_category_shadow(recommendations=recommendations, store=store, provider=timeout)
    assert timeout_result.status == "PARTIAL"
    assert timeout_result.predictions[0].status == "FAILED"


def test_shadow_run_safely_contains_an_unexpected_provider_exception(store: CategoryMapperStore):
    recommendation = _recommendation(
        asin="B000000001", title="ASIENCE shampoo", keepa_category="シャンプー", canonical_product_type="SHAMPOO"
    )
    group = build_shadow_groups((recommendation,))[0]
    result = run_category_shadow(
        recommendations=(recommendation,),
        store=store,
        provider=FakeCategoryShadowProvider({group.group_key: RuntimeError("unexpected")}),
    )
    assert result.status == "PARTIAL"
    assert result.predictions[0].response.abstain is True
    assert result.predictions[0].response.abstain_reason == "UNEXPECTED_PROVIDER_ERROR"


def test_db_migration_records_prediction_and_keeps_existing_mapping(store: CategoryMapperStore):
    store.save_category_mapping(
        marketplace="PH", mapping_key_type="KEEPA_CATEGORY", mapping_key="リンス・コンディショナー",
        canonical_product_type="CONDITIONER", category_id=100872,
        category_path="Beauty > Hair Care > Hair and Scalp Conditioner",
    )
    recommendations = (
        _recommendation(asin="B000000001", title="conditioner", keepa_category="リンス・コンディショナー", canonical_product_type="CONDITIONER"),
    )
    group = build_shadow_groups(recommendations)[0]
    run_category_shadow(
        recommendations=recommendations,
        store=store,
        provider=FakeCategoryShadowProvider({group.group_key: _valid_payload(100872)}),
    )
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ai_shadow_runs").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM ai_shadow_predictions").fetchone()[0] == 1
        columns = [row[1].lower() for row in connection.execute("PRAGMA table_info(ai_shadow_predictions)")]
    assert not any("token" in column and column not in {"input_tokens", "output_tokens", "cached_tokens"} for column in columns)
    with sqlite3.connect(store.db_path) as connection:
        run_columns = [row[1].lower() for row in connection.execute("PRAGMA table_info(ai_shadow_runs)")]
    assert {"cached_tokens", "processed_group_count", "ai_request_count"} <= set(run_columns)
    assert store.find_confirmed_category_mapping("PH", "KEEPA_CATEGORY", "リンス・コンディショナー") is not None


def test_marketplace_isolated_cache_key_and_prompt_version(store: CategoryMapperStore):
    recommendations = (
        _recommendation(asin="B000000001", title="ASIENCE shampoo", keepa_category="シャンプー", canonical_product_type="SHAMPOO"),
    )
    group = build_shadow_groups(recommendations)[0]
    run_category_shadow(
        recommendations=recommendations,
        store=store,
        provider=FakeCategoryShadowProvider({group.group_key: _valid_payload(100869)}),
    )
    with sqlite3.connect(store.db_path) as connection:
        row = connection.execute("SELECT marketplace, prompt_version, cache_key FROM ai_shadow_predictions").fetchone()
    assert row[0] == "PH"
    assert row[1] == PROMPT_VERSION
    assert len(row[2]) == 64


def test_invalid_cached_shadow_result_safely_falls_back_to_a_fresh_evaluation(store: CategoryMapperStore):
    recommendations = (
        _recommendation(asin="B000000001", title="ASIENCE shampoo", keepa_category="シャンプー", canonical_product_type="SHAMPOO"),
    )
    group = build_shadow_groups(recommendations)[0]
    provider = FakeCategoryShadowProvider({group.group_key: _valid_payload(100869)})
    run_category_shadow(recommendations=recommendations, store=store, provider=provider)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("UPDATE ai_shadow_predictions SET ranked_candidates_json = 'not-json'")
    result = run_category_shadow(recommendations=recommendations, store=store, provider=provider)
    assert result.predictions[0].status == "COMPLETED"
    assert len(provider.calls) == 2


def test_kpis_handle_unknown_cost_and_reference_labels(store: CategoryMapperStore):
    recommendation = _recommendation(
        asin="B000000001", title="ASIENCE shampoo", keepa_category="シャンプー", canonical_product_type="SHAMPOO",
        category_id=100869, category_path="Beauty > Hair Care > Shampoo",
        verification_status="LISTING_TOOL_ACCEPTED", confirmed=True,
    )
    group = build_shadow_groups((recommendation,))[0]
    result = run_category_shadow(
        recommendations=(recommendation,), store=store,
        provider=FakeCategoryShadowProvider({group.group_key: _valid_payload(100869)}),
    )
    kpis = shadow_kpis(result.predictions)
    assert kpis["top1_accuracy"] == 1.0
    assert kpis["top3_accuracy"] == 1.0
    assert kpis["estimated_cost_per_100_groups"] is None


def test_smoke_equivalent_kpis_separate_local_abstention_from_actual_ai_requests(store: CategoryMapperStore):
    """Mirror the bounded real smoke shape without any network or credentials."""

    recommendations = (
        _recommendation(
            asin="B000000001", title="ASIENCE shampoo refill", keepa_category="シャンプー",
            canonical_product_type="SHAMPOO", category_id=100869,
            category_path="Beauty > Hair Care > Shampoo", verification_status="LISTING_TOOL_ACCEPTED", confirmed=True,
        ),
        _recommendation(
            asin="B000000002", title="shampoo & conditioner set", keepa_category="シャンプー・コンディショナーセット",
            canonical_product_type="SHAMPOO_CONDITIONER_SET",
        ),
        _recommendation(
            asin="B000000003", title="soft stuffed toy", keepa_category="Plush Toy",
            canonical_product_type="PLUSH_TOY", category_id=101722,
            category_path="Mom & Baby > Toys > Dolls & Stuffed Toys > Stuffed Toys",
            verification_status="USER_CONFIRMED", confirmed=True,
        ),
        _recommendation(
            asin="B000000004", title="stuffed toy storage case", keepa_category="Plush Toy Case",
            canonical_product_type="PLUSH_TOY_CASE", category_id=101720,
            category_path="Mom & Baby > Toys > Dolls & Stuffed Toys > Dolls & Accessories",
            verification_status="USER_CONFIRMED", confirmed=True,
        ),
        _recommendation(
            asin="B000000005", title="unclassified mystery item", keepa_category="Unknown"),
    )
    expected_ids = {"シャンプー": 100869, "plush toy": 101722, "plush toy case": 101720}
    groups = build_shadow_groups(recommendations)
    provider = FakeCategoryShadowProvider(
        {
            group.group_key: _payload_for_group(group, expected_ids[group.normalized_keepa_category])
            for group in groups
            if group.normalized_keepa_category in expected_ids
        }
    )

    result = run_category_shadow(recommendations=recommendations, store=store, provider=provider)
    kpis = shadow_kpis(result.predictions)

    assert len(provider.calls) == 3
    assert kpis["processed_group_count"] == 5
    assert kpis["no_candidate_count"] == 2
    assert kpis["local_abstain_count"] == 2
    assert kpis["ai_request_count"] == 3
    assert kpis["ai_success_count"] == 3
    assert kpis["ai_failure_count"] == 0
    assert kpis["ai_abstain_count"] == 0
    assert kpis["ai_guard_violation_count"] == 0
    assert kpis["invalid_category_id_count"] == 0
    assert kpis["input_tokens"] == 300
    assert kpis["output_tokens"] == 60
    assert kpis["cached_tokens"] == 30
    assert 0.0 < float(kpis["candidate_reduction_rate"] or 0) <= 1.0
    with sqlite3.connect(store.db_path) as connection:
        run = connection.execute(
            "SELECT provider, model, processed_group_count, ai_request_count, input_tokens, output_tokens, cached_tokens "
            "FROM ai_shadow_runs"
        ).fetchone()
    assert run == ("fake", "fake-category-shadow-v1", 5, 3, 300, 60, 30)


def test_kpis_compare_prefilter_and_ai_rank_without_counting_single_candidate_as_reduction():
    multi_group = _group(
        title="hair care", keepa_category="Hair Care", canonical_product_type="HAIR_CARE",
        selected_category_id=100872, selected_status="USER_CONFIRMED",
    )
    single_group = _group(
        title="shampoo", keepa_category="シャンプー", canonical_product_type="SHAMPOO",
        selected_category_id=100869, selected_status="USER_CONFIRMED",
    )
    multi_candidates = tuple(
        ShadowCategoryCandidate(category_id, f"PH > {category_id}", "TEST")
        for category_id in (100869, 100872, 100871)
    )
    single_candidates = (ShadowCategoryCandidate(100869, "Beauty > Hair Care > Shampoo", "TEST"),)
    multi_response = CategoryShadowResponse(
        schema_version="CATEGORY_SHADOW_V1", canonical_product_type="HAIR_CARE",
        is_main_product=True, is_set=False, is_accessory=False, is_replacement_part=False,
        risk_flags=(), abstain=False, abstain_reason="",
        ranked_candidates=(RankedCategory(100872, 0.9, "confirmed"),),
    )
    single_response = CategoryShadowResponse(
        schema_version="CATEGORY_SHADOW_V1", canonical_product_type="SHAMPOO",
        is_main_product=True, is_set=False, is_accessory=False, is_replacement_part=False,
        risk_flags=(), abstain=False, abstain_reason="",
        ranked_candidates=(RankedCategory(100869, 0.9, "confirmed"),),
    )
    kpis = shadow_kpis(
        (
            ShadowPrediction(multi_group, multi_candidates, multi_response, "COMPLETED", 0.1, False),
            ShadowPrediction(single_group, single_candidates, single_response, "COMPLETED", 0.1, False),
        )
    )

    assert kpis["prefilter_candidate_coverage"] == 1.0
    assert kpis["prefilter_top1_accuracy"] == 0.5
    assert kpis["ai_top1_accuracy"] == 1.0
    assert kpis["ai_top3_accuracy"] == 1.0
    assert kpis["top1_accuracy_lift"] == 0.5
    assert kpis["confirmed_category_rank_improvement_count"] == 1
    assert kpis["candidate_reduction_rate"] == 0.5
    assert kpis["single_candidate_group_count"] == 1
    assert kpis["multi_candidate_group_count"] == 1
    assert kpis["reference_data_sufficient"] is False


def test_stored_predictions_rescore_after_later_confirmation_without_another_ai_request(store: CategoryMapperStore):
    """A later human truth label evaluates a prior rank without mutating it."""

    recommendation = _recommendation(
        asin="B000000001", title="shampoo conditioner hair treatment",
        keepa_category="shampoo conditioner hair treatment", canonical_product_type="HAIR_CARE",
    )
    exports_before = build_mapper_exports((recommendation,))

    class _RankProvider:
        provider_name = "fake"
        model = "fake-rescore-v1"

        def __init__(self):
            self.calls: list[str] = []

        def rank_categories(self, request, *, timeout_seconds):
            del timeout_seconds
            self.calls.append(request.group.group_key)
            ranked_ids = tuple(candidate.category_id for candidate in request.candidates[:3])
            assert len(ranked_ids) == 3
            return _payload_for_group(request.group, ranked_ids[0], ranked_ids=ranked_ids)

    provider = _RankProvider()
    run = run_category_shadow(recommendations=(recommendation,), store=store, provider=provider)
    prediction = run.predictions[0]
    assert prediction.group.selected_category_id is None
    assert len(provider.calls) == 1
    original = sqlite3.connect(store.db_path).execute(
        "SELECT selected_category_id, selected_verification_status, top1_match, top3_match, evaluated_at "
        "FROM ai_shadow_predictions"
    ).fetchone()

    assert not store.save_ai_shadow_group_confirmation(
        marketplace="PH", group_key=prediction.group.group_key,
        category_id=prediction.top1_category_id or 1, verification_status="SUGGESTED",
    )
    before_truth = rescore_saved_shadow_predictions(recommendations=(), store=store)
    assert before_truth.evaluated_prediction_count == 0
    assert before_truth.unconfirmed_group_count == 1

    assert store.save_ai_shadow_group_confirmation(
        marketplace="PH", group_key=prediction.group.group_key,
        category_id=prediction.top1_category_id or 1, verification_status="USER_CONFIRMED",
    )
    top1_truth = rescore_saved_shadow_predictions(recommendations=(), store=store)
    assert top1_truth.evaluated_prediction_count == 1
    assert top1_truth.metrics["top1_accuracy"] == 1.0
    assert top1_truth.metrics["top3_accuracy"] == 1.0
    assert len(provider.calls) == 1
    with sqlite3.connect(store.db_path) as connection:
        first_rescore_count = connection.execute("SELECT COUNT(*) FROM ai_shadow_rescores").fetchone()[0]
        unchanged = connection.execute(
            "SELECT selected_category_id, selected_verification_status, top1_match, top3_match, evaluated_at "
            "FROM ai_shadow_predictions"
        ).fetchone()
    assert unchanged == original

    repeated = rescore_saved_shadow_predictions(recommendations=(), store=store)
    with sqlite3.connect(store.db_path) as connection:
        repeated_rescore_count = connection.execute("SELECT COUNT(*) FROM ai_shadow_rescores").fetchone()[0]
    assert repeated.metrics == top1_truth.metrics
    assert repeated_rescore_count == first_rescore_count

    second_rank_truth = store.save_ai_shadow_group_confirmation(
        marketplace="PH", group_key=prediction.group.group_key,
        category_id=prediction.top3_category_ids[1], verification_status="USER_CONFIRMED",
    )
    assert second_rank_truth is True
    top3_truth = rescore_saved_shadow_predictions(recommendations=(), store=store)
    assert top3_truth.metrics["top1_accuracy"] == 0.0
    assert top3_truth.metrics["top3_accuracy"] == 1.0

    assert store.save_ai_shadow_group_confirmation(
        marketplace="PH", group_key=prediction.group.group_key,
        category_id=100244, verification_status="LISTING_TOOL_ACCEPTED",
    )
    mismatch_truth = rescore_saved_shadow_predictions(recommendations=(), store=store)
    assert mismatch_truth.metrics["top1_accuracy"] == 0.0
    assert mismatch_truth.metrics["top3_accuracy"] == 0.0
    assert len(provider.calls) == 1

    assert store.save_ai_shadow_group_confirmation(
        marketplace="PH", group_key=prediction.group.group_key + "|other",
        category_id=100869, verification_status="USER_CONFIRMED",
    )
    isolated = rescore_saved_shadow_predictions(recommendations=(), store=store)
    assert isolated.evaluated_prediction_count == 1
    with pytest.raises(ValueError):
        store.ai_shadow_rescore_availability("SG")
    assert build_mapper_exports((recommendation,)) == exports_before


def test_openai_configuration_and_safe_error_do_not_expose_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(CategoryShadowConfigurationError, match="OPENAI_API_KEY_MISSING"):
        OpenAIResponsesCategoryShadowProvider.from_environment()
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    provider = OpenAIResponsesCategoryShadowProvider.from_environment()
    request = type("Request", (), {})()
    # The transport branch is tested without making a network call.
    import modules.category_mapper_ai as ai

    payloads = []

    def fail(request, *args, **kwargs):
        payloads.append(json.loads(request.data.decode("utf-8")))
        raise HTTPError("https://example.invalid", 401, "bad", {}, None)

    monkeypatch.setattr(ai, "urlopen", fail)
    group = _group(title="shampoo", keepa_category="シャンプー", canonical_product_type="SHAMPOO")
    candidates = (type("Candidate", (), {"category_id": 100869, "category_path": "Beauty > Hair Care > Shampoo"})(),)
    from modules.category_mapper_ai import CategoryShadowRequest

    with pytest.raises(CategoryShadowProviderError) as error:
        provider.rank_categories(CategoryShadowRequest(group=group, candidates=candidates), timeout_seconds=1)
    assert "test-placeholder" not in str(error.value)
    assert payloads[0]["max_output_tokens"] == MAX_OUTPUT_TOKENS


def test_openai_provider_reads_reported_cached_tokens_without_persisting_raw_response(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    provider = OpenAIResponsesCategoryShadowProvider.from_environment()
    group = _group(title="shampoo", keepa_category="シャンプー", canonical_product_type="SHAMPOO")
    candidates = (type("Candidate", (), {"category_id": 100869, "category_path": "Beauty > Hair Care > Shampoo"})(),)
    from modules.category_mapper_ai import CategoryShadowRequest

    class _Response:
        def read(self):
            payload = {
                "output_text": json.dumps(_valid_payload(100869)),
                "usage": {
                    "input_tokens": 123,
                    "output_tokens": 45,
                    "input_tokens_details": {"cached_tokens": 67},
                },
            }
            return json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    import modules.category_mapper_ai as ai

    monkeypatch.setattr(ai, "urlopen", lambda *args, **kwargs: _Response())
    raw = provider.rank_categories(
        CategoryShadowRequest(group=group, candidates=candidates), timeout_seconds=1
    )
    response = validate_shadow_response(raw, candidate_ids=(100869,))
    assert (response.input_tokens, response.output_tokens, response.cached_tokens) == (123, 45, 67)
