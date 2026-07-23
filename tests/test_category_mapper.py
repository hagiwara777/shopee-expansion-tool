import csv
from io import StringIO
from pathlib import Path

import pytest

from modules.category_mapper import (
    CONDITIONER,
    GATE_ELIGIBLE,
    RAW_EXPANSION,
    SHAMPOO_CONDITIONER_SET,
    USER_CONFIRMED,
    CategoryMapperInputError,
    apply_manual_brand,
    apply_manual_category,
    build_mapper_exports,
    build_recommendations,
    classify_product_type,
    flatten_attribute_tree,
    group_recommendations,
    parse_category_mapper_input,
    parse_resolver_title_csv,
    recommend_brand,
    summarize_output_blockers,
    sync_brand_pages,
)
from modules.category_mapper_store import CategoryMapperStore, default_category_mapper_db_path
from modules.prelisting_candidate_csv import PRELISTING_CANDIDATE_COLUMNS
from modules.prelisting_gate_csv import PRELISTING_GATE_RESULT_COLUMNS
from modules.shopee_catalog_client import (
    BRAND_STATUS_NORMAL,
    BRAND_STATUS_PENDING,
    BrandPage,
    ShopeeCatalogError,
    ShopeeRateLimitError,
)
from modules.shopee_catalog_client import ShopeeCatalogClient, ShopeeCatalogCredentials


def _csv_bytes(columns, rows) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def _expansion_csv(*, asin="B000000001", category="シャンプー", title="Shampoo", brand="") -> bytes:
    return _csv_bytes(
        PRELISTING_CANDIDATE_COLUMNS,
        [
            {
                "schema_version": "PRELISTING_CANDIDATE_V1",
                "source_type": "EXPANSION",
                "source_id": "",
                "source_asin": "B000000000",
                "candidate_asin": asin,
                "input_title": "",
                "product_title": title,
                "brand": brand,
                "category": category,
                "amazon_url": "",
                "source_status": "",
                "source_verification": "",
                "source": "keepa",
                "fetched_at": "2026-07-21T00:00:00+00:00",
                "source_note": "",
            }
        ],
    )


def _gate_csv(
    *,
    marketplace="PH",
    eligibility="ELIGIBLE",
    asin="B000000001",
    category="シャンプー",
    title="Shampoo",
    brand="ASIENCE",
) -> bytes:
    row = {column: "" for column in PRELISTING_GATE_RESULT_COLUMNS}
    row.update(
        {
            "gate_schema_version": "PRELISTING_GATE_RESULT_V1",
            "candidate_asin": asin,
            "final_eligibility": eligibility,
            "marketplace": marketplace,
            "candidate_schema_version": "PRELISTING_CANDIDATE_V1",
            "source_type": "EXPANSION",
            "source_asin": "B000000000",
            "product_title": title,
            "brand": brand,
            "category": category,
        }
    )
    return _csv_bytes(PRELISTING_GATE_RESULT_COLUMNS, [row])


@pytest.fixture
def store(tmp_path: Path) -> CategoryMapperStore:
    return CategoryMapperStore(tmp_path / "mapper.sqlite3")


def test_accepts_expansion_and_gate_eligible_but_rejects_audit_review_exclude_and_non_ph():
    expansion = parse_category_mapper_input(_expansion_csv(), filename="expansion.csv")
    assert expansion.input_safety_state == RAW_EXPANSION
    assert expansion.source_type == "EXPANSION"

    gate = parse_category_mapper_input(_gate_csv(), filename="eligible.csv")
    assert gate.input_safety_state == GATE_ELIGIBLE
    assert gate.rows[0].candidate_asin == "B000000001"

    for content in (
        _gate_csv(eligibility="REVIEW"),
        _gate_csv(eligibility="EXCLUDE"),
        _gate_csv(marketplace="SG"),
    ):
        with pytest.raises(CategoryMapperInputError):
            parse_category_mapper_input(content, filename="unsafe.csv")


def test_rejects_invalid_or_duplicate_candidate_asins():
    with pytest.raises(CategoryMapperInputError):
        parse_category_mapper_input(_expansion_csv(asin="invalid"), filename="invalid.csv")

    rows = []
    for row_number in range(2):
        rows.append(
            {
                "schema_version": "PRELISTING_CANDIDATE_V1",
                "source_type": "EXPANSION",
                "source_id": "",
                "source_asin": "B000000000",
                "candidate_asin": "B000000001",
                "input_title": "",
                "product_title": "Shampoo",
                "brand": "",
                "category": "シャンプー",
                "amazon_url": "",
                "source_status": "",
                "source_verification": "",
                "source": "keepa",
                "fetched_at": "",
                "source_note": str(row_number),
            }
        )
    with pytest.raises(CategoryMapperInputError, match="Duplicate"):
        parse_category_mapper_input(
            _csv_bytes(PRELISTING_CANDIDATE_COLUMNS, rows), filename="duplicate.csv"
        )


def test_resolver_title_csv_is_optional_evidence_only():
    resolver = _csv_bytes(
        ["source_id", "input_title", "amazon_url", "asin", "status", "verification", "note"],
        [
            {
                "source_id": "R0001",
                "input_title": "ASIENCE Moisture Rich Shampoo 450ml",
                "amazon_url": "",
                "asin": "B000000001",
                "status": "FOUND",
                "verification": "KEEPA_VERIFIED",
                "note": "",
            },
            {
                "source_id": "R0002",
                "input_title": "Unknown",
                "amazon_url": "",
                "asin": "",
                "status": "UNKNOWN",
                "verification": "NOT_CHECKED",
                "note": "",
            },
        ],
    )
    assert parse_resolver_title_csv(resolver, filename="resolver.csv") == {
        "B000000001": "ASIENCE Moisture Rich Shampoo 450ml"
    }


def test_shampoo_profile_is_confirmed_but_case_accessory_is_not(store: CategoryMapperStore):
    source = parse_category_mapper_input(_expansion_csv(), filename="shampoo.csv")
    recommendation = build_recommendations(source, resolver_titles=None, store=store)[0]
    assert recommendation.canonical_product_type == "SHAMPOO"
    assert recommendation.recommended_category_id == 100869
    assert recommendation.category_verification_status == "LISTING_TOOL_ACCEPTED"
    assert recommendation.no_brand_available is True
    assert recommendation.listing_ready is False

    accessory = parse_category_mapper_input(
        _expansion_csv(title="シャンプー用収納ケース", category="収納"),
        filename="accessory.csv",
    )
    result = build_recommendations(accessory, resolver_titles=None, store=store)[0]
    assert result.canonical_product_type == ""
    assert result.recommended_category_id is None


@pytest.mark.parametrize(
    ("category", "title"),
    [
        ("シャンプー・コンディショナーセット", "ASIENCE shampoo conditioner set"),
        ("シャンプー", "ASIENCE shampoo & conditioner set"),
        ("シャンプー", "ASIENCE トライアルセット"),
        ("シャンプー", "ASIENCE 2点セット"),
        ("", "ASIENCE hair care set"),
        ("", "ASIENCE shampoo conditioner kit"),
    ],
)
def test_shampoo_conditioner_sets_are_not_confirmed_as_single_shampoo(
    store: CategoryMapperStore, category: str, title: str
):
    source = parse_category_mapper_input(
        _gate_csv(category=category, title=title),
        filename="set.csv",
    )
    recommendation = build_recommendations(source, resolver_titles=None, store=store)[0]

    assert recommendation.canonical_product_type == SHAMPOO_CONDITIONER_SET
    assert recommendation.recommended_category_id is None
    assert recommendation.category_recommendation_status == "UNMAPPED"
    assert recommendation.category_is_confirmed is False


@pytest.mark.parametrize(
    ("category", "title"),
    [
        ("シャンプー", "ASIENCE shampoo refill"),
        ("", "Daily shampoo refill"),
    ],
)
def test_single_shampoo_without_set_marker_keeps_confirmed_profile(
    store: CategoryMapperStore, category: str, title: str
):
    source = parse_category_mapper_input(
        _gate_csv(category=category, title=title),
        filename="single.csv",
    )
    recommendation = build_recommendations(source, resolver_titles=None, store=store)[0]

    assert recommendation.canonical_product_type == "SHAMPOO"
    assert recommendation.recommended_category_id == 100869
    assert recommendation.category_is_confirmed is True


def test_unknown_type_is_unmapped_and_user_confirmed_mapping_is_reused(store: CategoryMapperStore):
    source = parse_category_mapper_input(
        _expansion_csv(category="洗顔料", title="Face wash"),
        filename="unknown.csv",
    )
    unknown = build_recommendations(source, resolver_titles=None, store=store)[0]
    assert unknown.category_recommendation_status == "UNMAPPED"

    store.save_categories(
        "PH",
        [
            {
                "category_id": 200001,
                "parent_category_id": None,
                "category_name": "Face Wash",
                "is_leaf": True,
                "is_others": False,
            }
        ],
    )
    store.save_category_mapping(
        marketplace="PH",
        mapping_key_type="KEEPA_CATEGORY",
        mapping_key="洗顔料",
        canonical_product_type="",
        category_id=200001,
        category_path="Beauty > Face Wash",
    )
    mapped = build_recommendations(source, resolver_titles=None, store=store)[0]
    assert mapped.recommended_category_id == 200001
    assert mapped.category_verification_status == "USER_CONFIRMED"


def _seed_conditioner_leaf(store: CategoryMapperStore) -> None:
    store.save_categories(
        "PH",
        [
            {
                "category_id": 100000,
                "parent_category_id": None,
                "category_name": "Beauty",
                "is_leaf": False,
                "is_others": False,
            },
            {
                "category_id": 100659,
                "parent_category_id": 100000,
                "category_name": "Hair Care",
                "is_leaf": False,
                "is_others": False,
            },
            {
                "category_id": 100872,
                "parent_category_id": 100659,
                "category_name": "Hair and Scalp Conditioner",
                "is_leaf": True,
                "is_others": False,
            },
        ],
    )


def test_conditioner_is_suggested_not_shampoo_and_user_confirmation_is_reused(
    store: CategoryMapperStore,
):
    _seed_conditioner_leaf(store)
    source = parse_category_mapper_input(
        _gate_csv(
            category="リンス・コンディショナー",
            title="Moist conditioner refill",
        ),
        filename="conditioner.csv",
    )
    suggested = build_recommendations(source, resolver_titles=None, store=store)[0]
    assert classify_product_type(
        keepa_category="リンス・コンディショナー",
        product_title="Moist conditioner refill",
        resolver_input_title="",
    ) == CONDITIONER
    assert suggested.canonical_product_type == CONDITIONER
    assert suggested.recommended_category_id == 100872
    assert suggested.category_recommendation_status == "SUGGESTED"
    assert suggested.category_is_confirmed is False
    assert suggested.listing_ready is False

    category = store.get_category("PH", 100872)
    assert category is not None
    confirmed = apply_manual_category(
        suggested,
        category=category,
        mandatory_attribute_count=None,
        no_brand_available=False,
    )
    assert confirmed.category_verification_status == USER_CONFIRMED
    assert confirmed.recommended_brand_id is None
    assert confirmed.brand_match_status == "NOT_FOUND"
    assert confirmed.listing_ready is False
    store.save_category_mapping(
        marketplace="PH",
        mapping_key_type="KEEPA_CATEGORY",
        mapping_key="リンス・コンディショナー",
        canonical_product_type=CONDITIONER,
        category_id=100872,
        category_path=str(category["category_path"]),
    )

    reopened = CategoryMapperStore(store.db_path)
    reused_source = parse_category_mapper_input(
        _gate_csv(
            asin="B000000002",
            category="リンス・コンディショナー",
            title="Another conditioner",
        ),
        filename="conditioner-reused.csv",
    )
    reused = build_recommendations(reused_source, resolver_titles=None, store=reopened)[0]
    assert reused.recommended_category_id == 100872
    assert reused.category_verification_status == USER_CONFIRMED
    assert reused.canonical_product_type == CONDITIONER


def test_category_change_resets_old_brand_and_missing_tree_mapping_is_not_reused(
    store: CategoryMapperStore,
):
    _seed_conditioner_leaf(store)
    shampoo = build_recommendations(
        parse_category_mapper_input(_gate_csv(), filename="shampoo.csv"),
        resolver_titles=None,
        store=store,
    )[0]
    ready_shampoo = apply_manual_brand(
        shampoo,
        brand={"brand_id": 0, "brand_name": "No brand", "is_no_brand": True},
    )
    assert ready_shampoo.listing_ready is True
    conditioner = store.get_category("PH", 100872)
    assert conditioner is not None
    changed = apply_manual_category(
        ready_shampoo,
        category=conditioner,
        mandatory_attribute_count=None,
        no_brand_available=False,
    )
    assert changed.recommended_category_id == 100872
    assert changed.recommended_brand_id is None
    assert changed.no_brand_selected_by_user is False
    assert changed.listing_ready is False

    store.save_category_mapping(
        marketplace="PH",
        mapping_key_type="KEEPA_CATEGORY",
        mapping_key="obsolete category",
        canonical_product_type="",
        category_id=999999,
        category_path="Missing > Category",
    )
    missing = build_recommendations(
        parse_category_mapper_input(
            _gate_csv(asin="B000000003", category="obsolete category", title="Unknown"),
            filename="missing-tree-category.csv",
        ),
        resolver_titles=None,
        store=store,
    )[0]
    assert missing.recommended_category_id is None
    assert missing.category_recommendation_status == "UNMAPPED"


def test_attribute_flatten_is_null_safe_deduplicated_and_cycle_safe():
    cyclic = {"attribute_id": "2", "attribute_name": "Size", "children": []}
    cyclic["children"].append(cyclic)
    tree = {
        "children": [
            {"attribute_id": "1", "attribute_name": "Color", "children": None},
            {"attribute_id": "1", "is_mandatory": True, "attribute_value_list": ["red"]},
            {"group_name": "Nested", "children": [{"attribute_id": "3", "children": []}]},
            {"group_name": "Unknown", "children": "not-a-list"},
            cyclic,
        ]
    }
    result = flatten_attribute_tree(tree, max_depth=4)
    by_id = {item["attribute_id"]: item for item in result.attributes}
    assert set(by_id) == {"1", "2", "3"}
    assert by_id["1"]["is_mandatory"] is True
    assert by_id["1"]["value_count"] == 1
    assert result.group_node_count >= 2
    assert result.skipped_node_count == 1

    deeply_nested = {"attribute_id": "root", "children": {"unexpected": "value"}}
    assert flatten_attribute_tree(deeply_nested).skipped_node_count == 1

    depth_limited = {"group": "0", "children": [{"group": "1", "children": [{"attribute_id": "9"}]}]}
    assert flatten_attribute_tree(depth_limited, max_depth=1).depth_limited is True


def test_attribute_flatten_accepts_official_mandatory_field_with_null_children():
    result = flatten_attribute_tree(
        {
            "attribute_id": "1",
            "display_attribute_name": "Volume",
            "mandatory": False,
            "children": None,
        }
    )
    assert result.attributes == (
        {
            "attribute_id": "1",
            "attribute_name": "Volume",
            "is_mandatory": False,
            "input_type": "",
            "validation_type": "",
            "value_count": 0,
            "unit_count": 0,
            "multi_select_max": 0,
        },
    )


def test_brand_rules_are_explicit_and_no_brand_needs_user_choice():
    brands = [
        {"brand_id": 0, "brand_name": "No brand", "is_no_brand": True},
        {"brand_id": 44, "brand_name": "ASIENCE", "is_no_brand": False},
        {"brand_id": 45, "brand_name": "A S I E N C E", "is_no_brand": False},
    ]
    exact = recommend_brand(
        marketplace="PH",
        category_id=100869,
        keepa_brand="ASIENCE",
        resolver_input_title="",
        brands=brands,
    )
    assert exact["status"] == "EXACT_MATCH"
    assert exact["brand_id"] == 44
    assert exact["confirmed"] is False

    title = recommend_brand(
        marketplace="PH",
        category_id=100869,
        keepa_brand="アジエンス",
        resolver_input_title="ASIENCE Moisture Rich Shampoo",
        brands=[brands[0], brands[1]],
    )
    assert title["status"] == "RESOLVER_TITLE_EXACT_MATCH"

    multiple = recommend_brand(
        marketplace="PH",
        category_id=100869,
        keepa_brand="",
        resolver_input_title="ASIENCE shampoo",
        brands=[brands[1], {"brand_id": 46, "brand_name": "ASIENCE Shampoo", "is_no_brand": False}],
    )
    assert multiple["status"] == "MULTIPLE_MATCHES"

    manufacturer_only = recommend_brand(
        marketplace="PH",
        category_id=100869,
        keepa_brand="Product Brand",
        resolver_input_title="",
        manufacturer_name="Maker Corp",
        brands=[{"brand_id": 50, "brand_name": "Maker Corp", "is_no_brand": False}],
    )
    assert manufacturer_only["status"] == "MANUFACTURER_ONLY"

    no_brand = recommend_brand(
        marketplace="PH",
        category_id=100869,
        keepa_brand="日本語ブランド",
        resolver_input_title="",
        brands=[brands[0]],
    )
    assert no_brand["status"] == "NO_BRAND_AVAILABLE"
    assert no_brand["brand_id"] is None


def test_no_brand_user_selection_makes_gate_row_ready_but_not_raw_expansion(
    store: CategoryMapperStore,
):
    gate = parse_category_mapper_input(_gate_csv(), filename="eligible.csv")
    recommendation = build_recommendations(gate, resolver_titles=None, store=store)[0]
    selected = apply_manual_brand(
        recommendation,
        brand={"brand_id": 0, "brand_name": "No brand", "is_no_brand": True},
    )
    assert selected.listing_ready is True

    raw = parse_category_mapper_input(_expansion_csv(), filename="raw.csv")
    raw_recommendation = build_recommendations(raw, resolver_titles=None, store=store)[0]
    raw_selected = apply_manual_brand(
        raw_recommendation,
        brand={"brand_id": 0, "brand_name": "No brand", "is_no_brand": True},
    )
    assert raw_selected.listing_ready is False


def test_no_brand_confirmation_is_scoped_to_category_and_reused_after_restart(
    store: CategoryMapperStore,
):
    source = parse_category_mapper_input(_gate_csv(), filename="eligible.csv")
    recommendation = build_recommendations(source, resolver_titles=None, store=store)[0]
    selected = apply_manual_brand(
        recommendation,
        brand={"brand_id": 0, "brand_name": "No brand", "is_no_brand": True},
    )
    store.save_brand_policy(
        marketplace="PH",
        keepa_category=selected.keepa_category,
        keepa_brand=selected.keepa_brand,
        category_id=100869,
        brand_policy="NO_BRAND_SELECTED",
        brand_id=0,
    )
    assert store.find_confirmed_brand_alias("PH", 100869, selected.keepa_brand) is None
    reopened = CategoryMapperStore(store.db_path)
    reused = build_recommendations(
        parse_category_mapper_input(_gate_csv(asin="B000000004"), filename="reused.csv"),
        resolver_titles=None,
        store=reopened,
    )[0]
    assert reused.brand_match_status == "NO_BRAND_SELECTED"
    assert reused.recommended_brand_id == 0
    assert reused.no_brand_selected_by_user is True
    assert reused.listing_ready is True


def test_real_brand_alias_does_not_conflict_with_no_brand_policy(store: CategoryMapperStore):
    store.save_brand_policy(
        marketplace="PH",
        keepa_category="リンス・コンディショナー",
        keepa_brand="ASIENCE",
        category_id=100872,
        brand_policy="NO_BRAND_SELECTED",
        brand_id=0,
    )
    store.save_brand_alias(
        source_brand="ASIENCE",
        canonical_brand="ASIENCE",
        marketplace="PH",
        category_id=100872,
        shopee_brand_name="ASIENCE",
        brand_id=12345,
    )

    assert store.find_confirmed_brand_policy(
        "PH", "リンス・コンディショナー", "ASIENCE", 100872
    )["brand_id"] == 0
    assert store.find_confirmed_brand_alias("PH", 100872, "ASIENCE")["brand_id"] == 12345
    result = recommend_brand(
        marketplace="PH",
        category_id=100872,
        keepa_brand="ASIENCE",
        resolver_input_title="",
        brands=[
            {"brand_id": 0, "brand_name": "No brand", "is_no_brand": True},
            {"brand_id": 12345, "brand_name": "ASIENCE", "is_no_brand": False},
        ],
        confirmed_brand_policy=store.find_confirmed_brand_policy(
            "PH", "リンス・コンディショナー", "ASIENCE", 100872
        ),
        confirmed_alias=store.find_confirmed_brand_alias("PH", 100872, "ASIENCE"),
    )
    assert result["status"] == "CONFIRMED_ALIAS_MATCH"
    assert result["brand_id"] == 12345


def test_output_blockers_and_group_exports_keep_all_21_gate_asins_in_order(
    store: CategoryMapperStore,
):
    rows = []
    for number in range(1, 22):
        row = {column: "" for column in PRELISTING_GATE_RESULT_COLUMNS}
        row.update(
            {
                "gate_schema_version": "PRELISTING_GATE_RESULT_V1",
                "candidate_asin": f"B{number:09d}",
                "final_eligibility": "ELIGIBLE",
                "marketplace": "PH",
                "candidate_schema_version": "PRELISTING_CANDIDATE_V1",
                "source_type": "EXPANSION",
                "source_asin": "B000000000",
                "product_title": "Shampoo",
                "brand": "ASIENCE",
                "category": "シャンプー",
            }
        )
        rows.append(row)
    recommendations = build_recommendations(
        parse_category_mapper_input(
            _csv_bytes(PRELISTING_GATE_RESULT_COLUMNS, rows), filename="twenty-one.csv"
        ),
        resolver_titles=None,
        store=store,
    )
    blockers = summarize_output_blockers(recommendations)
    assert len(blockers["ready"]) == 0
    assert len(blockers["category_unconfirmed"]) == 0
    assert len(blockers["brand_unconfirmed"]) == 21
    assert len(blockers["manual_review_required"]) == 21

    selected = tuple(
        apply_manual_brand(
            recommendation,
            brand={"brand_id": 0, "brand_name": "No brand", "is_no_brand": True},
        )
        for recommendation in recommendations
    )
    exports = build_mapper_exports(selected)
    groups = list(csv.DictReader(StringIO(exports.groups_csv.decode("utf-8-sig"))))
    txt_asins = [
        line
        for line in exports.listing_tool_text.splitlines()
        if line.startswith("B") and not line.startswith("Brand ID:")
    ]
    assert len(groups) == 21
    assert [row["asin"] for row in groups] == [f"B{number:09d}" for number in range(1, 22)]
    assert txt_asins == [f"B{number:09d}" for number in range(1, 22)]
    assert len(set(txt_asins)) == 21
    assert all(row["group_key"] == "PH|100869|0" for row in groups)


def test_real_shaped_gate_rows_keep_sets_out_of_shampoo_outputs(store: CategoryMapperStore):
    _seed_conditioner_leaf(store)
    store.save_attributes("PH", 100872, [])
    store.save_brand_page(
        "PH",
        100872,
        [{"brand_id": 0, "brand_name": "No brand", "is_no_brand": True}],
        next_offset=0,
        is_complete=True,
    )
    rows = []
    row_number = 1
    for category, title, count in (
        ("シャンプー", "ASIENCE shampoo refill", 17),
        ("リンス・コンディショナー", "ASIENCE conditioner refill", 17),
        ("ヘアトリートメント", "ASIENCE hair treatment", 10),
        ("シャンプー・コンディショナーセット", "ASIENCE shampoo & conditioner set", 4),
        ("シャンプー・コンディショナーセット", "ASIENCE trial set", 1),
    ):
        for index in range(count):
            row = {column: "" for column in PRELISTING_GATE_RESULT_COLUMNS}
            row.update(
                {
                    "gate_schema_version": "PRELISTING_GATE_RESULT_V1",
                    "candidate_asin": f"B{row_number:09d}",
                    "final_eligibility": "ELIGIBLE",
                    "marketplace": "PH",
                    "candidate_schema_version": "PRELISTING_CANDIDATE_V1",
                    "source_type": "EXPANSION",
                    "source_asin": "B000000000",
                    "product_title": f"{title} {index}",
                    "brand": "ASIENCE",
                    "category": category,
                }
            )
            rows.append(row)
            row_number += 1
    source = parse_category_mapper_input(
        _csv_bytes(PRELISTING_GATE_RESULT_COLUMNS, rows), filename="eligible.csv"
    )
    recommendations = build_recommendations(source, resolver_titles=None, store=store)
    by_type = {}
    for item in recommendations:
        by_type.setdefault(item.canonical_product_type, []).append(item)

    assert len(by_type["SHAMPOO"]) == 17
    assert all(item.recommended_category_id == 100869 for item in by_type["SHAMPOO"])
    assert len(by_type[CONDITIONER]) == 17
    assert all(item.recommended_category_id == 100872 for item in by_type[CONDITIONER])
    assert all(not item.category_is_confirmed for item in by_type[CONDITIONER])
    assert len(by_type[SHAMPOO_CONDITIONER_SET]) == 5
    assert all(item.recommended_category_id is None for item in by_type[SHAMPOO_CONDITIONER_SET])
    assert all(not item.category_is_confirmed for item in by_type[SHAMPOO_CONDITIONER_SET])

    set_groups = [
        group
        for group in group_recommendations(recommendations)
        if group["keepa_category"] == "シャンプー・コンディショナーセット"
    ]
    assert len(set_groups) == 1
    assert set_groups[0]["asin_count"] == 5
    assert set_groups[0]["category_status"] == "UNMAPPED"

    no_brand = {"brand_id": 0, "brand_name": "No brand", "is_no_brand": True}
    selected = []
    conditioner_category = store.get_category("PH", 100872)
    assert conditioner_category is not None
    for item in recommendations:
        if item.canonical_product_type == "SHAMPOO":
            selected.append(apply_manual_brand(item, brand=no_brand))
        elif item.canonical_product_type == CONDITIONER:
            confirmed = apply_manual_category(
                item,
                category=conditioner_category,
                mandatory_attribute_count=0,
                no_brand_available=True,
            )
            selected.append(apply_manual_brand(confirmed, brand=no_brand))
        else:
            selected.append(item)

    assert sum(item.listing_ready for item in selected) == 34
    exports = build_mapper_exports(selected)
    groups = list(csv.DictReader(StringIO(exports.groups_csv.decode("utf-8-sig"))))
    txt_asins = [
        line
        for line in exports.listing_tool_text.splitlines()
        if line.startswith("B") and not line.startswith("Brand ID:")
    ]
    assert len(groups) == 34
    assert len(txt_asins) == 34
    assert len(groups) == len(txt_asins)


class _FakeBrandClient:
    def __init__(self, pages, error=None):
        self.pages = list(pages)
        self.error = error
        self.calls = []

    def get_brand_list(self, marketplace, category_id, *, offset=0, page_size=100):
        self.calls.append((marketplace, category_id, offset, page_size))
        if self.error is not None:
            raise self.error
        return self.pages.pop(0)


def test_brand_paging_stops_on_match_resumes_and_uses_cached_data(store: CategoryMapperStore):
    client = _FakeBrandClient(
        [
            BrandPage(({"brand_id": 1, "brand_name": "One", "is_no_brand": False},), 100, False),
            BrandPage(({"brand_id": 2, "brand_name": "Target", "is_no_brand": False},), 200, False),
        ]
    )
    first = sync_brand_pages(
        store=store,
        client=client,
        marketplace="PH",
        category_id=100869,
        matching_terms=["Target"],
    )
    assert first["api_pages"] == 2
    assert [call[2] for call in client.calls] == [0, 100]

    cached = sync_brand_pages(
        store=store,
        client=client,
        marketplace="PH",
        category_id=100869,
        matching_terms=["Target"],
    )
    assert cached["api_pages"] == 0
    assert len(client.calls) == 2


def test_brand_paging_stops_at_ten_and_uses_previous_cache_after_failure(store: CategoryMapperStore):
    pages = [
        BrandPage(({"brand_id": index + 1, "brand_name": f"Brand {index}", "is_no_brand": False},), (index + 1) * 100, False)
        for index in range(12)
    ]
    client = _FakeBrandClient(pages)
    result = sync_brand_pages(
        store=store,
        client=client,
        marketplace="PH",
        category_id=100869,
        matching_terms=["missing"],
    )
    assert result["api_pages"] == 10
    assert len(client.calls) == 10

    failing = _FakeBrandClient([], error=ShopeeCatalogError("network"))
    fallback = sync_brand_pages(
        store=store,
        client=failing,
        marketplace="PH",
        category_id=100869,
        matching_terms=["missing"],
    )
    assert fallback["failed"] is True
    assert fallback["used_cache"] is True

    limited = _FakeBrandClient([], error=ShopeeRateLimitError("429"))
    with pytest.raises(ShopeeRateLimitError):
        sync_brand_pages(
            store=store,
            client=limited,
            marketplace="PH",
            category_id=100869,
            matching_terms=["new term"],
        )


def test_exports_are_bom_encoded_ordered_and_one_asin_per_group_row(store: CategoryMapperStore):
    source = parse_category_mapper_input(_gate_csv(), filename="eligible.csv")
    recommendation = build_recommendations(source, resolver_titles=None, store=store)[0]
    ready = apply_manual_brand(
        recommendation,
        brand={"brand_id": 0, "brand_name": "No brand", "is_no_brand": True},
    )
    exports = build_mapper_exports([ready])
    assert exports.recommendations_csv.startswith(b"\xef\xbb\xbf")
    assert exports.groups_csv.startswith(b"\xef\xbb\xbf")
    detail = list(csv.DictReader(StringIO(exports.recommendations_csv.decode("utf-8-sig"))))
    groups = list(csv.DictReader(StringIO(exports.groups_csv.decode("utf-8-sig"))))
    assert detail[0]["listing_ready"] == "TRUE"
    assert groups == [
        {
            "marketplace": "PH",
            "group_key": "PH|100869|0",
            "category_id": "100869",
            "category_path": "Beauty > Hair Care > Shampoo",
            "brand_id": "0",
            "brand_name": "No brand",
            "mandatory_attribute_count": "0",
            "verification_status": "LISTING_TOOL_ACCEPTED",
            "listing_ready": "TRUE",
            "asin_count": "1",
            "asin": "B000000001",
        }
    ]
    assert "Category ID: 100869" in exports.listing_tool_text


def test_store_is_user_local_seeded_and_preserves_existing_user_mapping(store: CategoryMapperStore):
    profile = store.find_listing_profile("PH", "SHAMPOO")
    assert profile["profile_id"] == "PH_SHAMPOO_NO_BRAND_V1"
    store.save_category_mapping(
        marketplace="PH",
        mapping_key_type="KEEPA_CATEGORY",
        mapping_key="My category",
        canonical_product_type="",
        category_id=100869,
        category_path="Beauty > Hair Care > Shampoo",
        note="user note",
    )
    reopened = CategoryMapperStore(store.db_path)
    mapping = reopened.find_confirmed_category_mapping("PH", "KEEPA_CATEGORY", "my category")
    assert mapping["note"] == "user note"
    assert reopened.no_brand_available("PH", 100869) is True


def test_store_records_empty_attribute_tree_and_multiselect_metadata(store: CategoryMapperStore):
    store.save_attributes(
        "PH",
        100139,
        [
            {
                "attribute_id": "1",
                "attribute_name": "Size",
                "is_mandatory": False,
                "input_type": "COMBO_BOX",
                "validation_type": "ENUM",
                "value_count": 2,
                "unit_count": 1,
                "multi_select_max": 3,
            }
        ],
    )
    assert store.mandatory_attribute_count("PH", 100139) == 0
    assert store.list_attributes("PH", 100139)[0]["multi_select_max"] == 3

    store.save_attributes("PH", 200001, [])
    assert store.mandatory_attribute_count("PH", 200001) == 0


def test_default_store_path_is_under_local_appdata(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    assert default_category_mapper_db_path() == (
        tmp_path / "appdata" / "ShopeeCategoryMapper" / "category_mapper.sqlite3"
    )


def test_catalog_client_is_ph_only_and_never_exposes_request_values():
    calls = []

    def request_json(url, query, timeout):
        calls.append((url, query, timeout))
        if url.endswith("get_category"):
            return {
                "response": {
                    "category_list": [
                        {
                            "category_id": 100869,
                            "parent_category_id": 100,
                            "display_category_name": "Shampoo",
                            "has_children": False,
                        }
                    ]
                }
            }
        return {
            "response": {
                "brand_list": [{"brand_id": 0, "display_brand_name": "No brand"}],
                "next_offset": 1,
                "has_next_page": False,
            }
        }

    client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "test", 2, "test"),
        request_json=request_json,
    )
    categories = client.get_categories("PH")
    brands = client.get_brand_list("PH", 100869)
    assert categories[0]["category_id"] == 100869
    assert brands.brands[0]["is_no_brand"] is True
    assert all(timeout == 30 for _, _, timeout in calls)
    assert all("sign" in query for _, query, _ in calls)
    assert calls[1][1]["status"] == str(BRAND_STATUS_NORMAL)
    with pytest.raises(ValueError):
        client.get_categories("SG")


def test_catalog_client_attribute_tree_uses_category_id_list_and_keeps_input_order():
    calls = []

    def request_json(url, query, timeout):
        calls.append((url, query, timeout))
        requested_ids = [int(value) for value in query["category_id_list"].split(",")]
        return {
            "error": "",
            "response": {
                "list": [
                    {
                        "category_id": category_id,
                        "attribute_tree": [
                            {
                                "attribute_id": str(category_id),
                                "mandatory": False,
                                "children": None,
                            }
                        ],
                    }
                    for category_id in reversed(requested_ids)
                ]
            },
        }

    client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "test", 2, "test"), request_json=request_json
    )
    one_tree = client.get_attribute_tree("PH", 100869)
    results = client.get_attribute_trees("PH", [100869, 100870])

    assert one_tree[0]["attribute_id"] == "100869"
    assert [result["category_id"] for result in results] == [100869, 100870]
    assert calls[0][1]["category_id_list"] == "100869"
    assert calls[1][1]["category_id_list"] == "100869,100870"
    assert all("category_id" not in query for _, query, _ in calls)
    assert flatten_attribute_tree(one_tree).attributes[0]["is_mandatory"] is False


def test_catalog_client_rejects_invalid_attribute_and_brand_requests_before_api_call():
    calls = []

    def request_json(url, query, timeout):
        calls.append((url, query, timeout))
        return {"error": "", "response": {"list": []}}

    client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "test", 2, "test"), request_json=request_json
    )
    invalid_category_lists = (
        [],
        "100869",
        [True],
        [0],
        [100869, 100869],
        list(range(1, 22)),
    )
    for category_ids in invalid_category_lists:
        with pytest.raises(ValueError):
            client.get_attribute_trees("PH", category_ids)
    for kwargs in (
        {"offset": -1},
        {"offset": True},
        {"page_size": 101},
        {"status": True},
        {"status": 3},
    ):
        with pytest.raises(ValueError):
            client.get_brand_list("PH", 100869, **kwargs)
    assert calls == []


def test_catalog_client_handles_shopee_application_errors_and_brand_page_contract():
    def application_error(url, query, timeout):
        return {"error": "product.error_param", "message": "CategoryIdList is required"}

    error_client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "test", 2, "test"), request_json=application_error
    )
    with pytest.raises(ShopeeCatalogError, match="product.error_param") as error:
        error_client.get_attribute_tree("PH", 100869)
    assert "/api/v2/product/get_attribute_tree" in str(error.value)

    malformed_response_client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "test", 2, "test"),
        request_json=lambda url, query, timeout: {"error": "", "category_list": []},
    )
    with pytest.raises(ShopeeCatalogError, match="response object was missing"):
        malformed_response_client.get_categories("PH")

    calls = []

    def brand_response(url, query, timeout):
        calls.append((url, query, timeout))
        return {
            "error": "",
            "response": {
                "brand_list": [{"brand_id": 0, "display_brand_name": "No brand"}],
                "next_offset": 100,
                "has_next_page": True,
                "is_mandatory": False,
                "input_type": "TEXT",
            },
        }

    brand_client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "test", 2, "test"), request_json=brand_response
    )
    page = brand_client.get_brand_list("PH", 100869, status=BRAND_STATUS_NORMAL)
    brand_client.get_brand_list("PH", 100869, status=BRAND_STATUS_PENDING)
    assert page.brands[0]["brand_id"] == 0
    assert page.brands[0]["is_no_brand"] is True
    assert page.next_offset == 100
    assert page.has_next_page is True
    assert calls[0][1]["status"] == str(BRAND_STATUS_NORMAL)
    assert calls[1][1]["status"] == str(BRAND_STATUS_PENDING)

    missing_paging_client = ShopeeCatalogClient(
        ShopeeCatalogCredentials(1, "test", 2, "test"),
        request_json=lambda url, query, timeout: {
            "error": "",
            "response": {"brand_list": [], "has_next_page": False},
        },
    )
    with pytest.raises(ShopeeCatalogError, match="next_offset"):
        missing_paging_client.get_brand_list("PH", 100869)


def test_classification_matches_english_and_excludes_accessories():
    assert classify_product_type(
        keepa_category="", product_title="Daily shampoo", resolver_input_title=""
    ) == "SHAMPOO"
    assert classify_product_type(
        keepa_category="", product_title="case for shampoo bottle", resolver_input_title=""
    ) == ""
