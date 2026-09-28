import csv
from dataclasses import replace
from io import StringIO
import sqlite3

import pytest

from modules.category_ai_core import (
    CategoryAIEngine,
    CategoryAIError,
    FakeCategoryAIProvider,
    make_fake_abstain,
    make_fake_select,
)
from modules.category_mapper import build_mapper_exports
from modules.category_mapper_ai import (
    AI_ABSTAIN,
    AI_CATALOG_MISMATCH,
    AI_FAILED,
    AI_SUGGESTED,
    load_luna_request_profile,
)
from modules.category_mapper_sg import (
    SG_CATEGORY_CATALOG_COLUMNS,
    SGCategoryMapperError,
    build_sg_category_ai_catalog,
    build_sg_category_catalog_csv,
    build_sg_recommendations,
    confirm_sg_category,
    generate_sg_ai_category_suggestions,
    parse_sg_category_catalog,
    parse_sg_category_mapper_input,
    replace_sg_category_catalog,
)
from modules.category_mapper_store import CategoryMapperStore
from modules.prelisting_candidate_csv import PRELISTING_CANDIDATE_COLUMNS
from modules.prelisting_gate_csv import PRELISTING_GATE_RESULT_COLUMNS


def _csv_bytes(columns, rows) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def _catalog_csv(rows=None) -> bytes:
    if rows is None:
        rows = [
            {
                "marketplace": "SG",
                "category_id": "900000",
                "parent_category_id": "",
                "category_name": "Health",
                "category_path": "Health",
                "is_leaf": "FALSE",
            },
            {
                "marketplace": "SG",
                "category_id": "900001",
                "parent_category_id": "900000",
                "category_name": "Personal Care",
                "category_path": "Health > Personal Care",
                "is_leaf": "TRUE",
            },
            {
                "marketplace": "SG",
                "category_id": "900002",
                "parent_category_id": "900000",
                "category_name": "Wellness",
                "category_path": "Health > Wellness",
                "is_leaf": "TRUE",
            },
        ]
    return _csv_bytes(SG_CATEGORY_CATALOG_COLUMNS, rows)


def _gate_row(
    *,
    asin="B000000001",
    marketplace="SG",
    eligibility="ELIGIBLE",
    source_type="EXPANSION",
    title="Example personal care item",
):
    row = {column: "" for column in PRELISTING_GATE_RESULT_COLUMNS}
    row.update(
        {
            "gate_schema_version": "PRELISTING_GATE_RESULT_V1",
            "candidate_asin": asin,
            "final_eligibility": eligibility,
            "marketplace": marketplace,
            "candidate_schema_version": "PRELISTING_CANDIDATE_V1",
            "source_type": source_type,
            "source_id": "SOURCE-1" if source_type == "RESOLVER" else "",
            "source_asin": "B000000000" if source_type == "EXPANSION" else "",
            "input_title": "Resolver evidence title" if source_type == "RESOLVER" else "",
            "product_title": title,
            "brand": "Example Brand",
            "category": "Personal Care",
            "guardrail_status": "SAFE",
            "existing_listing_status": "CLEAR",
            "input_duplicate_status": "UNIQUE",
            "source_asin_status": "CLEAR",
            "metadata_status": "COMPLETE",
        }
    )
    return row


def _gate_csv(rows=None, *, source_type="EXPANSION") -> bytes:
    return _csv_bytes(
        PRELISTING_GATE_RESULT_COLUMNS,
        rows or [_gate_row(source_type=source_type)],
    )


def _gate_filename(source_type="EXPANSION") -> str:
    return f"prelisting_gate_eligible_sg_{source_type.lower()}.csv"


def _store_with_catalog(tmp_path):
    store = CategoryMapperStore(tmp_path / "mapper.sqlite3")
    catalog = parse_sg_category_catalog(_catalog_csv(), filename="sg_catalog.csv")
    replace_sg_category_catalog(store, catalog, synced_at="2026-09-19T00:00:00+00:00")
    return store


def _recommendations(tmp_path, rows=None, *, source_type="EXPANSION", resolver_titles=None):
    store = _store_with_catalog(tmp_path)
    source = parse_sg_category_mapper_input(
        _gate_csv(rows, source_type=source_type),
        filename=_gate_filename(source_type),
    )
    return store, build_sg_recommendations(
        source,
        resolver_titles=resolver_titles,
        store=store,
    )


@pytest.mark.parametrize("source_type", ["EXPANSION", "RESOLVER"])
def test_accepts_only_formal_all_eligible_sg_gate_csv(source_type, tmp_path):
    source = parse_sg_category_mapper_input(
        _gate_csv(source_type=source_type),
        filename=_gate_filename(source_type),
    )
    assert source.marketplace == "SG"
    assert source.source_type == source_type
    assert source.input_safety_state == "GATE_ELIGIBLE"
    assert source.rows[0].candidate_asin == "B000000001"

    store = _store_with_catalog(tmp_path)
    rows = build_sg_recommendations(source, resolver_titles=None, store=store)
    assert len(rows) == 1
    assert rows[0].listing_ready is False


@pytest.mark.parametrize(
    ("rows", "filename"),
    [
        ([_gate_row(marketplace="PH")], _gate_filename()),
        ([_gate_row(), _gate_row(asin="B000000002", marketplace="PH")], _gate_filename()),
        ([_gate_row(eligibility="REVIEW")], _gate_filename()),
        ([_gate_row(eligibility="EXCLUDE")], _gate_filename()),
        (
            [_gate_row(), _gate_row(asin="B000000002", source_type="RESOLVER")],
            _gate_filename(),
        ),
        ([_gate_row()], "prelisting_gate_audit_sg_expansion.csv"),
    ],
)
def test_rejects_non_sg_mixed_noneligible_mixed_source_and_audit(rows, filename):
    with pytest.raises(SGCategoryMapperError):
        parse_sg_category_mapper_input(_gate_csv(rows), filename=filename)


def test_rejects_raw_candidate_and_invalid_gate_schema():
    raw = {column: "" for column in PRELISTING_CANDIDATE_COLUMNS}
    raw.update(
        {
            "schema_version": "PRELISTING_CANDIDATE_V1",
            "source_type": "EXPANSION",
            "candidate_asin": "B000000001",
            "product_title": "Raw candidate",
        }
    )
    with pytest.raises(SGCategoryMapperError):
        parse_sg_category_mapper_input(
            _csv_bytes(PRELISTING_CANDIDATE_COLUMNS, [raw]),
            filename=_gate_filename(),
        )

    invalid = _gate_row()
    invalid["gate_schema_version"] = "PRELISTING_GATE_RESULT_V0"
    with pytest.raises(SGCategoryMapperError):
        parse_sg_category_mapper_input(_gate_csv([invalid]), filename=_gate_filename())


@pytest.mark.parametrize(
    "field,value",
    [
        ("guardrail_status", "REVIEW"),
        ("existing_listing_status", "EXISTING"),
        ("input_duplicate_status", "DUPLICATE"),
        ("source_asin_status", "SELF_ASIN"),
        ("metadata_status", "INCOMPLETE"),
    ],
)
def test_rejects_rows_that_are_not_formal_complete_gate_eligible(field, value):
    row = _gate_row()
    row[field] = value
    with pytest.raises(SGCategoryMapperError):
        parse_sg_category_mapper_input(_gate_csv([row]), filename=_gate_filename())


def test_sg_catalog_validates_and_replace_removes_deleted_ids_without_touching_ph(tmp_path):
    store = CategoryMapperStore(tmp_path / "mapper.sqlite3")
    store.save_categories(
        "PH",
        [
            {
                "category_id": 900001,
                "parent_category_id": None,
                "category_name": "PH Same ID",
                "is_leaf": True,
                "is_others": False,
            }
        ],
    )
    original = parse_sg_category_catalog(_catalog_csv(), filename="sg_catalog.csv")
    assert replace_sg_category_catalog(store, original) == 3
    assert store.get_category("SG", 900002)["category_path"] == "Health > Wellness"

    replacement = parse_sg_category_catalog(
        _catalog_csv(
            [
                {
                    "marketplace": "SG",
                    "category_id": "900000",
                    "parent_category_id": "",
                    "category_name": "Health",
                    "category_path": "Health",
                    "is_leaf": "FALSE",
                },
                {
                    "marketplace": "SG",
                    "category_id": "900001",
                    "parent_category_id": "900000",
                    "category_name": "Personal Care",
                    "category_path": "Health > Personal Care",
                    "is_leaf": "TRUE",
                },
            ]
        ),
        filename="sg_catalog_v2.csv",
    )
    replace_sg_category_catalog(store, replacement)

    assert store.get_category("SG", 900002) is None
    assert store.get_category("SG", 900001)["category_path"] == "Health > Personal Care"
    assert store.get_category("PH", 900001)["category_path"] == "PH Same ID"


@pytest.mark.parametrize(
    "rows",
    [
        [
            {"marketplace": "SG", "category_id": "1", "parent_category_id": "", "category_name": "Root", "category_path": "Root", "is_leaf": "TRUE"},
            {"marketplace": "SG", "category_id": "1", "parent_category_id": "", "category_name": "Again", "category_path": "Again", "is_leaf": "TRUE"},
        ],
        [
            {"marketplace": "SG", "category_id": "2", "parent_category_id": "999", "category_name": "Missing", "category_path": "Root > Missing", "is_leaf": "TRUE"},
        ],
        [
            {"marketplace": "SG", "category_id": "1", "parent_category_id": "", "category_name": "Root", "category_path": "Root", "is_leaf": "TRUE"},
            {"marketplace": "SG", "category_id": "2", "parent_category_id": "3", "category_name": "Two", "category_path": "Three > Two", "is_leaf": "FALSE"},
            {"marketplace": "SG", "category_id": "3", "parent_category_id": "2", "category_name": "Three", "category_path": "Two > Three", "is_leaf": "FALSE"},
        ],
        [
            {"marketplace": "SG", "category_id": "1", "parent_category_id": "", "category_name": "Root", "category_path": "Wrong", "is_leaf": "TRUE"},
        ],
        [
            {"marketplace": "SG", "category_id": "1", "parent_category_id": "", "category_name": "Root", "category_path": "Root", "is_leaf": "TRUE"},
            {"marketplace": "SG", "category_id": "2", "parent_category_id": "1", "category_name": "Leaf", "category_path": "Root > Leaf", "is_leaf": "TRUE"},
        ],
        [
            {"marketplace": "PH", "category_id": "1", "parent_category_id": "", "category_name": "Root", "category_path": "Root", "is_leaf": "TRUE"},
        ],
    ],
)
def test_sg_catalog_rejects_duplicate_missing_parent_cycle_path_leaf_and_market(rows):
    with pytest.raises(SGCategoryMapperError):
        parse_sg_category_catalog(_catalog_csv(rows), filename="invalid_sg_catalog.csv")


def test_failed_catalog_validation_does_not_replace_existing_sg_catalog(tmp_path):
    store = _store_with_catalog(tmp_path)
    before = store.list_categories_for_category_ai_catalog("SG")
    invalid = _catalog_csv(
        [
            {"marketplace": "SG", "category_id": "1", "parent_category_id": "99", "category_name": "Broken", "category_path": "Broken", "is_leaf": "TRUE"}
        ]
    )
    with pytest.raises(SGCategoryMapperError):
        parse_sg_category_catalog(invalid, filename="broken.csv")
    assert store.list_categories_for_category_ai_catalog("SG") == before


def test_ai_uses_sg_product_evidence_and_confidence_never_confirms(tmp_path):
    store, recommendations = _recommendations(
        tmp_path,
        resolver_titles={"B000000001": "Optional resolver title"},
    )
    provider = FakeCategoryAIProvider(
        [make_fake_select(900000, confidence=1.0), make_fake_select(900001, confidence=1.0)]
    )
    batch = generate_sg_ai_category_suggestions(
        recommendations,
        store=store,
        engine=CategoryAIEngine(provider),
        catalog=build_sg_category_ai_catalog(store),
        profile=load_luna_request_profile(),
    )

    suggestion = batch.suggestions[0]
    assert suggestion.status == AI_SUGGESTED
    assert suggestion.confidence == 1.0
    assert recommendations[0].category_is_confirmed is False
    assert recommendations[0].listing_ready is False
    evidence = provider.requests[0][0].product
    assert evidence.marketplace == "SG"
    assert evidence.api_product() == {
        "product_title": "Example personal care item",
        "keepa_category": "Personal Care",
        "keepa_brand": "Example Brand",
        "resolver_title": "Optional resolver title",
    }


def test_ai_abstain_failure_and_catalog_mismatch_stay_unconfirmed(tmp_path):
    rows = [
        _gate_row(asin="B000000001"),
        _gate_row(asin="B000000002"),
        _gate_row(asin="B000000003"),
    ]
    store, recommendations = _recommendations(tmp_path, rows)
    provider = FakeCategoryAIProvider(
        [
            make_fake_abstain(),
            CategoryAIError("TIMEOUT", api_call_count=1),
            make_fake_select(900000),
            make_fake_select(900001),
        ]
    )
    batch = generate_sg_ai_category_suggestions(
        recommendations,
        store=store,
        engine=CategoryAIEngine(provider),
        catalog=build_sg_category_ai_catalog(store),
        profile=load_luna_request_profile(),
    )
    assert [item.status for item in batch.suggestions] == [
        AI_ABSTAIN,
        AI_FAILED,
        AI_SUGGESTED,
    ]

    class OutsideCatalogEngine:
        def predict(self, product, catalog, profile):
            valid_provider = FakeCategoryAIProvider(
                [make_fake_select(900000), make_fake_select(900001)]
            )
            valid = CategoryAIEngine(valid_provider).predict(product, catalog, profile)
            return replace(
                valid,
                predicted_category_id=999999,
                predicted_category_path="Missing > Category",
            )

    mismatch = generate_sg_ai_category_suggestions(
        (recommendations[0],),
        store=store,
        engine=OutsideCatalogEngine(),
        catalog=build_sg_category_ai_catalog(store),
        profile=load_luna_request_profile(),
    )
    assert mismatch.suggestions[0].status == AI_CATALOG_MISMATCH
    assert mismatch.suggestions[0].is_adoptable is False
    assert all(not item.category_is_confirmed and not item.listing_ready for item in recommendations)


def test_human_confirmation_is_per_asin_persisted_and_revalidated(tmp_path):
    rows = [_gate_row(asin="B000000001"), _gate_row(asin="B000000002")]
    store, recommendations = _recommendations(tmp_path, rows)
    confirmed = confirm_sg_category(
        recommendations[0],
        store=store,
        category_id=900001,
        expected_category_path="Health > Personal Care",
    )
    assert confirmed.category_is_confirmed is True
    assert confirmed.listing_ready is False
    assert confirmed.group_key == ""
    assert recommendations[1].category_is_confirmed is False

    source = parse_sg_category_mapper_input(_gate_csv(rows), filename=_gate_filename())
    redisplayed = build_sg_recommendations(source, resolver_titles=None, store=store)
    assert [item.category_is_confirmed for item in redisplayed] == [True, False]
    assert redisplayed[0].category_recommendation_source == "USER_CONFIRMED_REUSE"

    changed = parse_sg_category_catalog(
        _catalog_csv(
            [
                {"marketplace": "SG", "category_id": "900000", "parent_category_id": "", "category_name": "Health", "category_path": "Health", "is_leaf": "FALSE"},
                {"marketplace": "SG", "category_id": "900001", "parent_category_id": "900000", "category_name": "Personal Wellness", "category_path": "Health > Personal Wellness", "is_leaf": "TRUE"},
            ]
        ),
        filename="changed.csv",
    )
    replace_sg_category_catalog(store, changed)
    after_catalog_change = build_sg_recommendations(source, resolver_titles=None, store=store)
    assert [item.category_is_confirmed for item in after_catalog_change] == [False, False]


def test_confirmation_rechecks_current_sg_leaf_path(tmp_path):
    store, recommendations = _recommendations(tmp_path)
    with pytest.raises(SGCategoryMapperError):
        confirm_sg_category(
            recommendations[0],
            store=store,
            category_id=900000,
            expected_category_path="Health",
        )
    with pytest.raises(SGCategoryMapperError):
        confirm_sg_category(
            recommendations[0],
            store=store,
            category_id=900001,
            expected_category_path="Stale > Path",
        )


def test_sg_never_reaches_ph_groups_listing_text_or_db_migration(tmp_path):
    store, recommendations = _recommendations(tmp_path)
    with sqlite3.connect(store.db_path) as connection:
        schema_before = connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()

    confirmed = confirm_sg_category(
        recommendations[0],
        store=store,
        category_id=900001,
        expected_category_path="Health > Personal Care",
    )
    assert confirmed.listing_ready is False
    assert confirmed.group_key == ""
    with pytest.raises(ValueError, match="CATEGORY_MAPPER_EXPORT_PH_ONLY"):
        build_mapper_exports((confirmed,))

    with sqlite3.connect(store.db_path) as connection:
        schema_after = connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
    assert schema_after == schema_before

@pytest.mark.parametrize(
    "operation",
    [
        lambda store: store.save_attributes("SG", 900001, []),
        lambda store: store.save_brands("SG", 900001, []),
        lambda store: store.save_brand_alias(
            source_brand="Example",
            canonical_brand="Example",
            marketplace="SG",
            category_id=900001,
            shopee_brand_name="Example",
            brand_id=1,
        ),
        lambda store: store.find_listing_profile("SG", "PERSONAL_CARE"),
    ],
)
def test_sg_brand_attribute_and_listing_profile_store_operations_remain_out_of_scope(
    operation, tmp_path
):
    store = _store_with_catalog(tmp_path)
    with pytest.raises(ValueError, match="PH only"):
        operation(store)


def _normalized_sg_categories():
    return [
        {"category_id": 30, "parent_category_id": 20, "category_name": "Leaf", "is_leaf": True},
        {"category_id": 10, "parent_category_id": 0, "category_name": "Root", "is_leaf": False},
        {"category_id": 20, "parent_category_id": 10, "category_name": "Child", "is_leaf": False},
    ]


@pytest.mark.parametrize("root_parent", [0, None])
def test_normalized_sg_catalog_is_deterministic_and_uses_only_parent_paths(root_parent):
    rows = _normalized_sg_categories()
    rows[1]["parent_category_id"] = root_parent
    rows[0]["category_path"] = "Untrusted source path"
    content = build_sg_category_catalog_csv(rows, marketplace="SG")
    assert content == build_sg_category_catalog_csv(list(reversed(rows)), marketplace="SG")
    parsed_rows = list(csv.DictReader(StringIO(content.decode("utf-8-sig"))))
    assert tuple(parsed_rows[0]) == SG_CATEGORY_CATALOG_COLUMNS
    assert [row["category_id"] for row in parsed_rows] == ["10", "20", "30"]
    assert [row["category_path"] for row in parsed_rows] == ["Root", "Root > Child", "Root > Child > Leaf"]
    assert parsed_rows[0]["parent_category_id"] == ""
    catalog = parse_sg_category_catalog(content, filename="normalized.csv")
    assert [node.is_leaf for node in catalog.nodes] == [False, False, True]


@pytest.mark.parametrize(
    "index,field,value",
    [
        (0, "category_id", 10),
        (0, "category_id", 0),
        (0, "category_id", -1),
        (0, "category_id", True),
        (0, "category_id", 30.0),
        (0, "category_id", "30"),
        (0, "category_name", "   "),
        (0, "category_name", None),
        (0, "parent_category_id", 999),
        (1, "parent_category_id", -1),
        (1, "parent_category_id", False),
        (1, "parent_category_id", "bad"),
        (1, "parent_category_id", "0"),
        (1, "parent_category_id", 0.0),
        (0, "is_leaf", False),
        (1, "is_leaf", True),
        (0, "is_leaf", "TRUE"),
        (0, "marketplace", "PH"),
    ],
)
def test_normalized_sg_catalog_rejects_invalid_values_before_replace(tmp_path, index, field, value):
    store = _store_with_catalog(tmp_path)
    before = store.list_categories_for_category_ai_catalog("SG")
    rows = _normalized_sg_categories()
    rows[index][field] = value
    with pytest.raises(SGCategoryMapperError):
        content = build_sg_category_catalog_csv(rows, marketplace="SG")
        replace_sg_category_catalog(store, parse_sg_category_catalog(content, filename="normalized.csv"))
    assert store.list_categories_for_category_ai_catalog("SG") == before


@pytest.mark.parametrize("case", ["empty", "no-root", "no-leaf", "disconnected-cycle", "self-cycle", "missing-field", "wrong-binding"])
def test_normalized_sg_catalog_rejects_incomplete_or_unreachable_tree(case):
    rows = _normalized_sg_categories()
    marketplace = "SG"
    if case == "empty":
        rows = []
    elif case == "no-root":
        rows[1]["parent_category_id"] = 30
    elif case == "no-leaf":
        for row in rows:
            row["is_leaf"] = False
    elif case == "disconnected-cycle":
        rows += [
            {"category_id": 40, "parent_category_id": 50, "category_name": "A", "is_leaf": False},
            {"category_id": 50, "parent_category_id": 40, "category_name": "B", "is_leaf": False},
        ]
    elif case == "self-cycle":
        rows[0]["parent_category_id"] = 30
    elif case == "missing-field":
        del rows[0]["parent_category_id"]
    elif case == "wrong-binding":
        marketplace = "PH"
    with pytest.raises(SGCategoryMapperError):
        build_sg_category_catalog_csv(rows, marketplace=marketplace)


@pytest.mark.parametrize("category_id,path", [(10, "Extra > Root"), (20, "Root > Extra > Child")])
def test_sg_parser_rejects_extra_path_segments(category_id, path):
    content = build_sg_category_catalog_csv(_normalized_sg_categories(), marketplace="SG")
    rows = list(csv.DictReader(StringIO(content.decode("utf-8-sig"))))
    for row in rows:
        if int(row["category_id"]) == category_id:
            old_path = row["category_path"]
            for descendant in rows:
                if descendant["category_path"].startswith(old_path):
                    descendant["category_path"] = path + descendant["category_path"][len(old_path):]
            break
    with pytest.raises(SGCategoryMapperError, match="exactly match hierarchy"):
        parse_sg_category_catalog(_catalog_csv(rows), filename="extra_segments.csv")


def test_normalized_sg_import_replaces_only_sg_without_schema_change(tmp_path):
    store = _store_with_catalog(tmp_path)
    store.save_categories("PH", [{"category_id": 10, "parent_category_id": None, "category_name": "PH root", "is_leaf": True}])
    ph_before = store.list_categories_for_category_ai_catalog("PH")
    with sqlite3.connect(store.db_path) as connection:
        schema_before = connection.execute("SELECT type, name, sql FROM sqlite_master ORDER BY type, name").fetchall()
    content = build_sg_category_catalog_csv(_normalized_sg_categories(), marketplace="SG")
    catalog = parse_sg_category_catalog(content, filename="normalized.csv")
    assert replace_sg_category_catalog(store, catalog) == 3
    assert store.get_category("SG", 900001) is None
    assert [row["category_id"] for row in store.list_categories_for_category_ai_catalog("SG")] == [10, 20, 30]
    assert store.list_categories_for_category_ai_catalog("PH") == ph_before
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("SELECT type, name, sql FROM sqlite_master ORDER BY type, name").fetchall() == schema_before


def test_sg_replace_rejects_direct_catalog_with_extra_path_before_db_write(tmp_path):
    store = _store_with_catalog(tmp_path)
    catalog = parse_sg_category_catalog(_catalog_csv(), filename="valid.csv")
    bad_nodes = tuple(replace(node, category_path=node.category_path.replace("Health > ", "Health > Extra > ")) for node in catalog.nodes)
    bad_catalog = replace(catalog, nodes=bad_nodes)
    before = store.list_categories_for_category_ai_catalog("SG")
    with pytest.raises(SGCategoryMapperError, match="exactly match hierarchy"):
        replace_sg_category_catalog(store, bad_catalog)
    assert store.list_categories_for_category_ai_catalog("SG") == before


def test_normalized_sg_import_rolls_back_on_insert_failure(tmp_path):
    store = _store_with_catalog(tmp_path)
    before = store.list_categories_for_category_ai_catalog("SG")
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("CREATE TRIGGER reject_new_sg BEFORE INSERT ON catalog_categories WHEN NEW.marketplace = 'SG' AND NEW.category_id = 30 BEGIN SELECT RAISE(ABORT, 'fixture failure'); END")
    content = build_sg_category_catalog_csv(_normalized_sg_categories(), marketplace="SG")
    with pytest.raises(sqlite3.IntegrityError):
        replace_sg_category_catalog(store, parse_sg_category_catalog(content, filename="normalized.csv"))
    assert store.list_categories_for_category_ai_catalog("SG") == before
