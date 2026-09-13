from dataclasses import replace

from modules.category_ai_core import (
    CategoryAIEngine,
    CategoryAIError,
    FakeCategoryAIProvider,
    make_fake_abstain,
    make_fake_select,
)
from modules.category_mapper import (
    CategoryMapperInput,
    CategoryMapperInputRow,
    GATE_ELIGIBLE,
    build_mapper_exports,
    build_recommendations,
)
from modules.category_mapper_ai import (
    AI_ABSTAIN,
    AI_CATALOG_MISMATCH,
    AI_FAILED,
    AI_SKIPPED_CONFIRMED,
    AI_SUGGESTED,
    AICategorySuggestion,
    build_category_ai_catalog,
    generate_ai_category_suggestions,
    group_consensus_suggestion,
    load_luna_request_profile,
)
from modules.category_mapper_store import CategoryMapperStore


def _store(tmp_path):
    store = CategoryMapperStore(tmp_path / "mapper.sqlite3")
    store.save_categories(
        "PH",
        [
            {
                "category_id": 200000,
                "parent_category_id": None,
                "category_name": "Hobbies & Collections",
                "is_leaf": False,
                "is_others": False,
            },
            {
                "category_id": 200001,
                "parent_category_id": 200000,
                "category_name": "Collectible Figures",
                "is_leaf": True,
                "is_others": False,
            },
            {
                "category_id": 200002,
                "parent_category_id": 200000,
                "category_name": "Model Kits",
                "is_leaf": True,
                "is_others": False,
            },
        ],
        synced_at="2026-09-13T00:00:00+00:00",
    )
    return store


def _recommendation(store, asin="B000000001", *, category="Collectibles", title="Figure"):
    source = CategoryMapperInput(
        marketplace="PH",
        source_type="EXPANSION",
        input_safety_state=GATE_ELIGIBLE,
        rows=(
            CategoryMapperInputRow(
                source_asin="B000000000",
                candidate_asin=asin,
                product_title=title,
                keepa_brand="Example Brand",
                keepa_category=category,
                source_type="EXPANSION",
                input_safety_state=GATE_ELIGIBLE,
                input_title="Resolver evidence",
            ),
        ),
    )
    return build_recommendations(source, resolver_titles=None, store=store)[0]


def _engine_for_leaf(category_id=200001, *, confidence=0.999):
    provider = FakeCategoryAIProvider(
        [
            make_fake_select(200000, confidence=confidence),
            make_fake_select(category_id, confidence=confidence),
        ]
    )
    return CategoryAIEngine(provider), provider


def test_catalog_uses_complete_mapper_tree_and_fixed_luna_profile(tmp_path):
    store = _store(tmp_path)

    rows = store.list_categories_for_category_ai_catalog("PH")
    catalog = build_category_ai_catalog(store)
    profile = load_luna_request_profile()

    assert {row["category_id"] for row in rows} >= {100869, 200000, 200001, 200002}
    assert {node.category_id for node in catalog.nodes} == {
        row["category_id"] for row in rows
    }
    assert catalog.get(200001).is_leaf is True
    assert profile.model == "gpt-5.6-luna"


def test_only_unconfirmed_rows_are_predicted_and_evidence_is_existing_mapper_data(tmp_path):
    store = _store(tmp_path)
    unconfirmed = _recommendation(store)
    confirmed = _recommendation(
        store,
        asin="B000000002",
        category="シャンプー",
        title="Shampoo",
    )
    engine, provider = _engine_for_leaf()

    batch = generate_ai_category_suggestions(
        (unconfirmed, confirmed),
        store=store,
        engine=engine,
        catalog=build_category_ai_catalog(store),
        profile=load_luna_request_profile(),
    )

    assert [item.status for item in batch.suggestions] == [
        AI_SUGGESTED,
        AI_SKIPPED_CONFIRMED,
    ]
    assert len(provider.requests) == 2
    evidence = provider.requests[0][0].product
    assert evidence.asin == unconfirmed.candidate_asin
    assert evidence.product_title == unconfirmed.product_title
    assert evidence.keepa_brand == unconfirmed.keepa_brand
    assert evidence.keepa_category == unconfirmed.keepa_category
    assert evidence.resolver_title == unconfirmed.resolver_input_title


def test_prediction_is_independent_and_high_confidence_never_changes_readiness(tmp_path):
    store = _store(tmp_path)
    recommendation = _recommendation(store)
    before_export = build_mapper_exports((recommendation,))
    engine, _ = _engine_for_leaf(confidence=1.0)

    batch = generate_ai_category_suggestions(
        (recommendation,),
        store=store,
        engine=engine,
        catalog=build_category_ai_catalog(store),
        profile=load_luna_request_profile(),
    )

    suggestion = batch.suggestions[0]
    assert suggestion.status == AI_SUGGESTED
    assert suggestion.confidence == 1.0
    assert suggestion.requires_hobbies_warning is True
    assert recommendation.category_is_confirmed is False
    assert recommendation.manual_review_required is True
    assert recommendation.listing_ready is False
    assert build_mapper_exports((recommendation,)) == before_export


def test_abstain_and_failure_do_not_stop_other_products_or_replace_fallback(tmp_path):
    store = _store(tmp_path)
    recommendations = (
        _recommendation(store, "B000000001"),
        _recommendation(store, "B000000002"),
        _recommendation(store, "B000000003"),
    )
    before_exports = build_mapper_exports(recommendations)
    provider = FakeCategoryAIProvider(
        [
            make_fake_abstain(),
            CategoryAIError("TIMEOUT", api_call_count=1),
            make_fake_select(200000),
            make_fake_select(200001),
        ]
    )

    batch = generate_ai_category_suggestions(
        recommendations,
        store=store,
        engine=CategoryAIEngine(provider),
        catalog=build_category_ai_catalog(store),
        profile=load_luna_request_profile(),
    )

    assert [item.status for item in batch.suggestions] == [
        AI_ABSTAIN,
        AI_FAILED,
        AI_SUGGESTED,
    ]
    assert (batch.success_count, batch.failure_count, batch.skip_count) == (1, 1, 1)
    assert batch.suggestions[1].error_code == "TIMEOUT"
    assert all(not item.category_is_confirmed for item in recommendations)
    assert all(item.listing_ready is False for item in recommendations)
    assert build_mapper_exports(recommendations) == before_exports


def test_catalog_mismatch_is_not_adoptable(tmp_path):
    store = _store(tmp_path)
    recommendation = _recommendation(store)

    class InvalidEngine:
        def predict(self, product, catalog, profile):
            engine, _ = _engine_for_leaf()
            prediction = engine.predict(product, catalog, profile)
            return replace(
                prediction,
                predicted_category_id=999999,
                predicted_category_path="Missing > Category",
            )

    batch = generate_ai_category_suggestions(
        (recommendation,),
        store=store,
        engine=InvalidEngine(),
        catalog=build_category_ai_catalog(store),
        profile=load_luna_request_profile(),
    )

    assert batch.suggestions[0].status == AI_CATALOG_MISMATCH
    assert batch.suggestions[0].is_adoptable is False
    assert batch.failure_count == 1


def test_group_consensus_requires_every_member_to_match_one_valid_leaf():
    first = AICategorySuggestion(
        candidate_asin="B000000001",
        status=AI_SUGGESTED,
        predicted_category_id=200001,
        predicted_category_path="Hobbies & Collections > Collectible Figures",
    )
    second = replace(first, candidate_asin="B000000002")
    mismatch = replace(
        second,
        predicted_category_id=200002,
        predicted_category_path="Hobbies & Collections > Model Kits",
    )

    assert group_consensus_suggestion(
        ("B000000001", "B000000002"), (first, second)
    ) == first
    assert group_consensus_suggestion(
        ("B000000001", "B000000002"), (first, mismatch)
    ) is None
    assert group_consensus_suggestion(
        ("B000000001", "B000000002"), (first,)
    ) is None
    assert group_consensus_suggestion(
        ("B000000001", "B000000002"),
        (first, replace(second, status=AI_FAILED)),
    ) is None
