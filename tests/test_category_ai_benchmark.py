"""Offline Gold, scoring, profile, price, and export contract tests."""

from collections import Counter
from hashlib import sha256
from pathlib import Path

import pytest

from modules.category_ai_benchmark import (
    GOLD_ABSTAIN_REQUIRED,
    GOLD_CONFIRMED,
    PriceBook,
    aggregate_by_model,
    evaluate_predictions,
    load_request_profiles,
    parse_catalog_csv,
    parse_gold_csv,
    parse_source_csv,
    prediction_batch_hash,
    prediction_rows,
    rows_to_csv,
)
from modules.category_ai_core import (
    BenchmarkRequestProfile,
    CategoryAIEngine,
    CategoryAIError,
    FakeCategoryAIProvider,
    ProductEvidence,
    make_fake_abstain,
    make_fake_select,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = (
    Path.home()
    / "Documents"
    / "ShopeePortfolioControl"
    / "Artifacts"
    / "PH_Category_AI_Benchmark_V1"
)
FORMAL_SOURCE = (
    ARTIFACT_ROOT
    / "benchmark_100_source_v1_1_20260912T034005Z"
    / "BENCHMARK_100_SOURCE_V1_1.csv"
)
FORMAL_GOLD = (
    ARTIFACT_ROOT
    / "benchmark_100_gold_final_v1_1_20260912T083737Z"
    / "BENCHMARK_100_GOLD_TRUTH_V1_1.csv"
)
FORMAL_CATALOG = (
    ARTIFACT_ROOT / "smoke_5_luna_a64162f3" / "catalog_ph_official_before.csv"
)


def source_bytes(case_id="P1", asin="B000000001"):
    return (
        "case_id,marketplace,asin,product_title,keepa_category,keepa_brand,"
        "resolver_title,expected_category_id,recommended_category,truth_status\n"
        f"{case_id},PH,{asin},Synthetic item,Health,Brand,Support title,12,999,CONFIRMED\n"
    ).encode()


def catalog_bytes():
    return (
        "category_id,parent_category_id,category_name,category_path,is_leaf\n"
        "10,,Health,Health,false\n"
        "11,10,Supplements,Health > Supplements,false\n"
        "12,11,Minerals,Health > Supplements > Minerals,true\n"
        "13,11,Vitamins,Health > Supplements > Vitamins,true\n"
    ).encode()


def catalog():
    return parse_catalog_csv(
        catalog_bytes(), marketplace="PH", catalog_version="PH-SYNTHETIC"
    )


def profile(model="gpt-5.6-luna"):
    return BenchmarkRequestProfile(
        model=model,
        reasoning_effort="low",
        text_verbosity="low",
        max_output_tokens=512,
        service_tier="default",
        timeout_seconds=30,
    )


def product(case_id="P1", asin="B000000001"):
    return ProductEvidence(
        marketplace="PH",
        case_id=case_id,
        asin=asin,
        product_title="Synthetic item",
        keepa_category="Health",
        keepa_brand="Brand",
        resolver_title="Support title",
    )


def fixed_prediction(kind, *, case_id="P1", asin="B000000001", model="gpt-5.6-luna"):
    if kind == "EXACT":
        outcomes = [make_fake_select(10), make_fake_select(11), make_fake_select(12)]
    elif kind == "WRONG":
        outcomes = [make_fake_select(10), make_fake_select(11), make_fake_select(13)]
    elif kind == "ABSTAIN":
        outcomes = [make_fake_abstain()]
    elif kind == "FAILED":
        outcomes = [CategoryAIError("TIMEOUT", api_call_count=1)]
    else:
        raise AssertionError(kind)
    return CategoryAIEngine(FakeCategoryAIProvider(outcomes)).predict(
        product(case_id, asin), catalog(), profile(model)
    )


def gold_bytes(rows):
    header = (
        "case_id,asin,expected_category_id,expected_category_path,truth_status,"
        "alternative_category_ids\n"
    )
    return (header + "".join(",".join(row) + "\n" for row in rows)).encode()


def load_gold(products, rows):
    return parse_gold_csv(gold_bytes(rows), products=products, catalog=catalog())


def evaluate_one(kind, truth_status, *, selected_alternative=False):
    prediction = fixed_prediction(kind)
    if truth_status == GOLD_CONFIRMED:
        row = (
            "P1",
            "B000000001",
            "12",
            "Health > Supplements > Minerals",
            GOLD_CONFIRMED,
            "13",
        )
    else:
        row = (
            "P1",
            "B000000001",
            "",
            "",
            GOLD_ABSTAIN_REQUIRED,
            "13" if selected_alternative else "12",
        )
    gold = load_gold((product(),), [row])
    fixed_hash = prediction_batch_hash((prediction,))
    evaluation = evaluate_predictions(
        (prediction,), gold, fixed_prediction_batch_hash=fixed_hash
    )
    return prediction, evaluation[prediction.prediction_hash]


def test_confirmed_exact_select_is_correct_select():
    _, result = evaluate_one("EXACT", GOLD_CONFIRMED)
    assert result.scoring_outcome == "CORRECT_SELECT"


def test_confirmed_wrong_select_is_wrong_category():
    _, result = evaluate_one("WRONG", GOLD_CONFIRMED)
    assert result.scoring_outcome == "WRONG_CATEGORY"


def test_confirmed_abstain_is_false_abstain():
    _, result = evaluate_one("ABSTAIN", GOLD_CONFIRMED)
    assert result.scoring_outcome == "FALSE_ABSTAIN"


def test_abstain_required_abstain_is_correct_abstain():
    _, result = evaluate_one("ABSTAIN", GOLD_ABSTAIN_REQUIRED)
    assert result.scoring_outcome == "CORRECT_ABSTAIN"


def test_abstain_required_select_is_overconfident_without_partial_credit():
    _, result = evaluate_one(
        "WRONG", GOLD_ABSTAIN_REQUIRED, selected_alternative=True
    )
    assert result.scoring_outcome == "OVERCONFIDENT_SELECT"


def test_provider_failure_is_failed_and_not_abstain_in_scoring():
    prediction, result = evaluate_one("FAILED", GOLD_ABSTAIN_REQUIRED)
    summary = aggregate_by_model(
        (prediction,), {prediction.prediction_hash: result}
    )[0]
    assert prediction.abstain is True
    assert result.prediction_decision == "FAILED"
    assert result.scoring_outcome == "FAILED"
    assert summary["failed_count"] == 1
    assert summary["correct_abstain_count"] == 0
    assert summary["overall_success_rate"] == 0
    assert summary["completed_decision_count"] == 0


@pytest.mark.parametrize(
    "row,message",
    [
        (
            ("P1", "B000000001", "12", "Health > Supplements > Minerals", GOLD_ABSTAIN_REQUIRED, ""),
            "ABSTAIN_REQUIRED",
        ),
        (("P1", "B000000001", "", "", GOLD_CONFIRMED, ""), "CONFIRMED"),
        (("P1", "B000000001", "", "", "UNCONFIRMED", ""), "truth_status"),
        (("P1", "B000000001", "", "", "REVIEW", ""), "truth_status"),
    ],
)
def test_gold_loader_rejects_invalid_status_and_expected_fields(row, message):
    with pytest.raises(ValueError, match=message):
        load_gold((product(),), [row])


def test_gold_loader_rejects_non_leaf_and_id_path_mismatch():
    non_leaf = ("P1", "B000000001", "11", "Health > Supplements", GOLD_CONFIRMED, "")
    with pytest.raises(ValueError, match="catalog leaf"):
        load_gold((product(),), [non_leaf])
    bad_path = ("P1", "B000000001", "12", "Health > Supplements > Vitamins", GOLD_CONFIRMED, "")
    with pytest.raises(ValueError, match="ID and path differ"):
        load_gold((product(),), [bad_path])


@pytest.mark.parametrize(
    "products,rows,message",
    [
        (
            (product(),),
            [("P2", "B000000001", "12", "Health > Supplements > Minerals", GOLD_CONFIRMED, "")],
            "case_id sets differ",
        ),
        (
            (product(),),
            [("P1", "B000000002", "12", "Health > Supplements > Minerals", GOLD_CONFIRMED, "")],
            "ASIN mapping differs",
        ),
    ],
)
def test_gold_loader_rejects_source_gold_identity_mismatch(products, rows, message):
    with pytest.raises(ValueError, match=message):
        load_gold(products, rows)


def test_gold_loader_rejects_duplicate_case_id_and_asin():
    duplicate_case = [
        ("P1", "B000000001", "12", "Health > Supplements > Minerals", GOLD_CONFIRMED, ""),
        ("P1", "B000000002", "12", "Health > Supplements > Minerals", GOLD_CONFIRMED, ""),
    ]
    with pytest.raises(ValueError, match="case_id"):
        load_gold((product(), product("P2", "B000000002")), duplicate_case)
    duplicate_asin = [
        ("P1", "B000000001", "12", "Health > Supplements > Minerals", GOLD_CONFIRMED, ""),
        ("P2", "B000000001", "12", "Health > Supplements > Minerals", GOLD_CONFIRMED, ""),
    ]
    with pytest.raises(ValueError, match="ASIN"):
        load_gold((product(), product("P2", "B000000002")), duplicate_asin)


def test_source_whitelist_gold_separation_and_batch_hash_order_are_enforced():
    products = parse_source_csv(source_bytes(), marketplace="PH")
    selected_catalog = catalog()
    fake = FakeCategoryAIProvider(
        [make_fake_select(10), make_fake_select(11), make_fake_select(12)]
    )
    prediction = CategoryAIEngine(fake).predict(
        products[0], selected_catalog, profile()
    )
    for _, _, payload in fake.requests:
        serialized = str(payload).lower()
        assert "expected_category" not in serialized
        assert "recommended_category" not in serialized
        assert "truth_status" not in serialized
        assert "gold" not in serialized
        assert "999" not in serialized
    fixed_hash = prediction_batch_hash((prediction,))
    gold = parse_gold_csv(
        gold_bytes(
            [
                (
                    "P1",
                    "B000000001",
                    "12",
                    "Health > Supplements > Minerals",
                    GOLD_CONFIRMED,
                    "",
                )
            ]
        ),
        products=products,
        catalog=selected_catalog,
    )
    with pytest.raises(ValueError, match="batch hash"):
        evaluate_predictions(
            (prediction,), gold, fixed_prediction_batch_hash="0" * 64
        )
    evaluation = evaluate_predictions(
        (prediction,), gold, fixed_prediction_batch_hash=fixed_hash
    )
    assert evaluation[prediction.prediction_hash].scoring_outcome == "CORRECT_SELECT"


def test_scoring_kpis_use_full_e2e_and_separate_completed_decision_reference():
    kinds = ["EXACT", "WRONG", "ABSTAIN", "ABSTAIN", "WRONG", "FAILED"]
    statuses = [
        GOLD_CONFIRMED,
        GOLD_CONFIRMED,
        GOLD_CONFIRMED,
        GOLD_ABSTAIN_REQUIRED,
        GOLD_ABSTAIN_REQUIRED,
        GOLD_CONFIRMED,
    ]
    predictions = tuple(
        fixed_prediction(kind, case_id=f"P{i}", asin=f"B{i:09d}")
        for i, kind in enumerate(kinds, 1)
    )
    products = tuple(
        product(f"P{i}", f"B{i:09d}") for i in range(1, len(kinds) + 1)
    )
    rows = []
    for i, status in enumerate(statuses, 1):
        if status == GOLD_CONFIRMED:
            rows.append(
                (
                    f"P{i}",
                    f"B{i:09d}",
                    "12",
                    "Health > Supplements > Minerals",
                    status,
                    "",
                )
            )
        else:
            rows.append((f"P{i}", f"B{i:09d}", "", "", status, "12"))
    gold = load_gold(products, rows)
    fixed_hash = prediction_batch_hash(predictions)
    evaluations = evaluate_predictions(
        predictions, gold, fixed_prediction_batch_hash=fixed_hash
    )
    summary = aggregate_by_model(predictions, evaluations)[0]
    assert summary["correct_select_count"] == 1
    assert summary["correct_abstain_count"] == 1
    assert summary["wrong_category_count"] == 1
    assert summary["false_abstain_count"] == 1
    assert summary["overconfident_select_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["overall_success_count"] == 2
    assert summary["overall_success_rate"] == pytest.approx(2 / 6)
    assert summary["confirmed_exact_accuracy"] == pytest.approx(1 / 4)
    assert summary["abstain_accuracy"] == pytest.approx(1 / 2)
    assert summary["select_precision"] == pytest.approx(1 / 3)
    assert summary["completed_decision_success_rate"] == pytest.approx(2 / 5)
    assert summary["api_call_count"] == sum(item.api_call_count for item in predictions)


def test_same_case_is_scored_independently_for_luna_and_terra():
    luna = fixed_prediction("EXACT", model="gpt-5.6-luna")
    terra = fixed_prediction("WRONG", model="gpt-5.6-terra")
    predictions = (luna, terra)
    gold = load_gold(
        (product(),),
        [
            (
                "P1",
                "B000000001",
                "12",
                "Health > Supplements > Minerals",
                GOLD_CONFIRMED,
                "",
            )
        ],
    )
    evaluations = evaluate_predictions(
        predictions,
        gold,
        fixed_prediction_batch_hash=prediction_batch_hash(predictions),
    )
    summaries = {item["model"]: item for item in aggregate_by_model(predictions, evaluations)}
    assert summaries["gpt-5.6-luna"]["correct_select_count"] == 1
    assert summaries["gpt-5.6-terra"]["wrong_category_count"] == 1


def test_gold_evaluation_exports_status_outcome_path_and_prediction_hash():
    prediction, result = evaluate_one("EXACT", GOLD_CONFIRMED)
    rows = prediction_rows((prediction,), {prediction.prediction_hash: result})
    assert rows[0]["gold_truth_status"] == GOLD_CONFIRMED
    assert rows[0]["scoring_outcome"] == "CORRECT_SELECT"
    assert rows[0]["expected_category_id"] == 12
    assert rows[0]["confidence"] == prediction.prediction_confidence
    exported = rows_to_csv(rows).decode("utf-8-sig")
    assert "benchmark_request_profile" in exported
    assert "traversal_steps" in exported
    assert prediction.prediction_hash in exported


def test_formal_100_product_fixture_loads_92_confirmed_and_8_abstain_required():
    required = (FORMAL_SOURCE, FORMAL_GOLD, FORMAL_CATALOG)
    if not all(path.exists() for path in required):
        pytest.skip("formal local Benchmark artifacts are not installed")
    source_content = FORMAL_SOURCE.read_bytes()
    gold_content = FORMAL_GOLD.read_bytes()
    products = parse_source_csv(source_content, marketplace="PH")
    fixed_catalog = parse_catalog_csv(
        FORMAL_CATALOG.read_bytes(),
        marketplace="PH",
        catalog_version=(
            "PH_OFFICIAL_BEFORE_"
            "cd57d90964411a91227ed2e2b58bd68ed6e52e2e93cc19ec6ad2a338d3e9bd7e"
        ),
    )
    gold = parse_gold_csv(gold_content, products=products, catalog=fixed_catalog)
    assert sha256(source_content).hexdigest() == (
        "a128aa7b5cad87e08397bdc09e0b2cdd656270c00be025b58d4f2e2419cccae0"
    )
    assert sha256(gold_content).hexdigest() == (
        "1faf1365ac0bb83566ea0347c12b9505895fcb9fed2cf4e5ba3964e62e28e93b"
    )
    assert fixed_catalog.catalog_hash == (
        "d694271a244bf743547d8cf9b1711f14618032954bae2cc81645f35ea65d72e6"
    )
    assert len(gold) == 100
    assert Counter(item.truth_status for item in gold.values()) == {
        GOLD_CONFIRMED: 92,
        GOLD_ABSTAIN_REQUIRED: 8,
    }


def test_versioned_profiles_and_price_config_are_fixed_and_comparable():
    profiles = load_request_profiles(
        ROOT / "config" / "category_ai_benchmark_request_profiles.json"
    )
    prices = PriceBook.from_path(ROOT / "config" / "category_ai_model_prices.json")
    assert {item.model for item in profiles} == {"gpt-5.6-luna", "gpt-5.6-terra"}
    assert {item.model for item in profiles} == set(prices.models)
    assert len({item.comparison_contract_hash for item in profiles}) == 1
    for item in profiles:
        assert item.reasoning_effort == "low"
        assert item.text_verbosity == "low"
        assert item.max_output_tokens == 512
        assert item.service_tier == "default"
        assert item.stream is False
        assert item.tool_choice == "none"
        assert item.parallel_tool_calls is False
        assert item.store is False
    assert prices.version == "OPENAI_TEXT_PRICES_2026-09-11_V1"


@pytest.mark.parametrize(
    "content,message",
    [
        (b"case_id\nP1\n", "product_title"),
        (b"case_id,product_title\nP1,x\nP1,y\n", "duplicate"),
        (b"case_id,product_title,marketplace\nP1,x,SG\n", "marketplace"),
    ],
)
def test_bad_source_csv_is_rejected(content, message):
    with pytest.raises(ValueError, match=message):
        parse_source_csv(content, marketplace="PH")


def test_catalog_snapshot_hash_is_order_independent_but_versioned():
    first = parse_catalog_csv(catalog_bytes(), marketplace="PH", catalog_version="V1")
    lines = catalog_bytes().decode().splitlines()
    reordered = (
        "\n".join([lines[0], lines[4], lines[2], lines[1], lines[3]]) + "\n"
    ).encode()
    second = parse_catalog_csv(reordered, marketplace="PH", catalog_version="V1")
    changed = parse_catalog_csv(catalog_bytes(), marketplace="PH", catalog_version="V2")
    assert first.catalog_hash == second.catalog_hash
    assert first.catalog_hash != changed.catalog_hash


def test_catalog_accepts_shopee_style_zero_parent_for_root():
    content = (
        "category_id,parent_category_id,category_name,category_path,is_leaf\n"
        "10,0,Health,Health,true\n"
    ).encode()
    parsed = parse_catalog_csv(content, marketplace="PH", catalog_version="V1")
    assert parsed.children_of(None)[0].category_id == 10
