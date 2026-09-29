"""DEC-0104 offline-only contracts; all catalogs and products are synthetic."""

from dataclasses import replace
import csv
from hashlib import sha256
from io import StringIO
import json
import sqlite3
from unittest.mock import patch

import pytest

from modules.category_mapper_store import CategoryMapperStore
from modules.category_mapper_sg import (
    SGBrandSession, SGCategoryMapperError, SGMapperRecommendation,
    build_sg_category_catalog_csv, parse_sg_category_catalog, confirm_sg_category,
    confirm_sg_brand, review_sg_brand, sg_no_brand_evidence_digest,
    sync_sg_brand_catalog_offline,
)
from modules.shopee_catalog_client import (
    ShopeeCatalogClient, ShopeeCatalogCredentials, ShopeeCatalogError,
)


def raw_brand(brand_id=7, name="Maker"):
    return {"brand_id": brand_id, "display_brand_name": name, "original_brand_name": name}


def payload(brands=None, next_offset=0, has_next_page=False):
    return {"response": {"brand_list": [raw_brand()] if brands is None else brands,
                         "next_offset": next_offset, "has_next_page": has_next_page}}


def client_for(pages, *, marketplace="SG", shop_id=22):
    calls = []
    queue = iter(pages)

    def request(url, query, timeout):
        calls.append(dict(query))
        result = next(queue)
        if isinstance(result, Exception):
            raise result
        return result

    return ShopeeCatalogClient(ShopeeCatalogCredentials(1, "FAKE_KEY", shop_id, "FAKE_TOKEN"),
                               marketplace=marketplace, request_json=request), calls


@pytest.fixture(autouse=True)
def forbid_live():
    with patch("modules.shopee_catalog_client.urlopen", side_effect=AssertionError("Live transport forbidden")), \
         patch("modules.shopee_access_token_source.GoogleSheetAccessTokenSource.get_access_token",
               side_effect=AssertionError("Bridge forbidden")):
        yield


@pytest.fixture
def store(tmp_path):
    result = CategoryMapperStore(tmp_path / "acceptance.sqlite3")
    catalog = build_sg_category_catalog_csv([
        {"category_id": 10, "parent_category_id": None, "category_name": "Root", "is_leaf": False},
        {"category_id": 11, "parent_category_id": 10, "category_name": "A", "is_leaf": True},
        {"category_id": 12, "parent_category_id": 10, "category_name": "B", "is_leaf": True},
    ], marketplace="SG")
    result.replace_sg_category_catalog(parse_sg_category_catalog(catalog, filename="sg.csv"))
    result.initialize_sg_brand_acceptance()
    return result


def product(**changes):
    result = SGMapperRecommendation("SG", "EXPANSION", "B000000000", "B000000001",
                                    "Synthetic item", "Maker", "Synthetic category", "", "GATE_ELIGIBLE",
                                    category_recommendation_status="CONFIRMED", recommended_category_id=11,
                                    recommended_category_path="Root > A", category_verification_status="USER_CONFIRMED",
                                    category_is_confirmed=True)
    return replace(result, **changes)


def sync(store, pages=None, session=None, category_id=11):
    session = session or SGBrandSession(marketplace="SG", shop_id=22)
    client, calls = client_for(pages or [payload([raw_brand(), raw_brand(99, "No Brand")])])
    result = sync_sg_brand_catalog_offline(client=client, session=session, store=store,
                                         confirmed_category_id=category_id)
    return session, result, calls


def confirm(store, session, catalog, item=None, brand_id=99, name="No Brand", **flags):
    return confirm_sg_brand(item or product(), store=store, session=session, catalog=catalog,
                            brand_id=brand_id, expected_brand_name=name,
                            human_product_verified=flags.get("verified", True),
                            human_option_selected=flags.get("selected", True))


@pytest.mark.parametrize("row", [None, [], "bad", {}, {"brand_id": True},
    raw_brand(-1), raw_brand(1.5), raw_brand("7"), raw_brand(2**63),
    {**raw_brand(), "display_brand_name": None}, {**raw_brand(), "display_brand_name": 3},
    {**raw_brand(), "original_brand_name": ""},
    {**raw_brand(99, "No Brand"), "original_brand_name": "Maker"}])
def test_strict_rejects_invalid_raw_rows(row):
    client, _ = client_for([payload([row])])
    with pytest.raises(ShopeeCatalogError):
        client.get_brand_list("SG", 11, strict=True)


@pytest.mark.parametrize("response", [{}, {"brand_list": {}},
    {"brand_list": [], "has_next_page": False},
    {"brand_list": [], "next_offset": 0},
    {"brand_list": [], "next_offset": True, "has_next_page": False},
    {"brand_list": [], "next_offset": 1.5, "has_next_page": False},
    {"brand_list": [], "next_offset": -1, "has_next_page": False},
    {"brand_list": [], "next_offset": 0, "has_next_page": 0},
    {"brand_list": [raw_brand()], "next_offset": 0, "has_next_page": True},
    {"brand_list": [], "next_offset": 100, "has_next_page": True}])
def test_strict_rejects_raw_paging_contract(response):
    client, _ = client_for([{"response": response}])
    with pytest.raises(ShopeeCatalogError):
        client.get_brand_list("SG", 11, strict=True)


def test_strict_duplicate_conflict_and_exact_dedup():
    client, _ = client_for([payload([raw_brand(), raw_brand(7, "Other")])])
    with pytest.raises(ShopeeCatalogError):
        client.get_brand_list("SG", 11, strict=True)
    client, _ = client_for([payload([raw_brand(), raw_brand()])])
    assert len(client.get_brand_list("SG", 11, strict=True).brands) == 1


def test_no_brand_uses_name_and_actual_nonzero_id_only():
    client, _ = client_for([payload([raw_brand(0, "Real"), raw_brand(99, "No Brand")])])
    rows = client.get_brand_list("SG", 11, strict=True).brands
    assert [row["is_no_brand"] for row in rows] == [False, True]
    assert rows[1]["brand_id"] == 99


def test_ph_default_normalization_is_unchanged():
    client, _ = client_for([payload([None, raw_brand(0, "Real"),
                                    {"brand_id": 8, "brand_name": "Legacy"}])], marketplace="PH")
    rows = client.get_brand_list("PH", 11).brands
    assert rows == ({"brand_id": 0, "brand_name": "Real", "is_no_brand": True},
                    {"brand_id": 8, "brand_name": "Legacy", "is_no_brand": False})


def test_client_mismatch_rejected_before_request():
    client, calls = client_for([payload()])
    with pytest.raises(ValueError):
        client.get_brand_list("PH", 11, strict=True)
    assert calls == []


@pytest.mark.parametrize("bound,shop", [("PH", 22), ("SG", 23)])
def test_run_client_binding_mismatch(store, bound, shop):
    client, calls = client_for([payload()], marketplace=bound, shop_id=shop)
    with pytest.raises(SGCategoryMapperError):
        sync_sg_brand_catalog_offline(client=client, session=SGBrandSession(marketplace="SG", shop_id=22),
                                     store=store, confirmed_category_id=11)
    assert calls == []


def test_default_network_transport_not_available_to_offline_run(store):
    client = ShopeeCatalogClient(ShopeeCatalogCredentials(1, "FAKE", 22, "FAKE"), marketplace="SG")
    with pytest.raises(SGCategoryMapperError):
        sync_sg_brand_catalog_offline(client=client, session=SGBrandSession(marketplace="SG", shop_id=22),
                                     store=store, confirmed_category_id=11)


def test_complete_paging_replace_removes_old_and_preserves_ph_other_category(store):
    store.save_brand_page("PH", 11, [{"brand_id": 123, "brand_name": "PH", "is_no_brand": False}],
                          next_offset=0, is_complete=True)
    store.replace_sg_brand_catalog(11, [{"brand_id": 50, "brand_name": "Deleted", "is_no_brand": False}])
    store.replace_sg_brand_catalog(12, [{"brand_id": 51, "brand_name": "Other", "is_no_brand": False}])
    ph = store.list_brands("PH", 11), store.brand_sync_state("PH", 11)
    other = store.list_brands("SG", 12), store.brand_sync_state("SG", 12)
    session, result, calls = sync(store, [payload([raw_brand()], 100, True),
                                         payload([raw_brand(), raw_brand(99, "No Brand")])])
    assert result.status == "SUCCESS" and result.pages == 2
    assert [q["offset"] for q in calls] == ["0", "100"]
    assert all(q["category_id"] == "11" and q["shop_id"] == "22" and q["status"] == "1"
               and q["page_size"] == "100" for q in calls)
    assert {row["brand_id"] for row in store.list_brands("SG", 11)} == {7, 99}
    assert ph == (store.list_brands("PH", 11), store.brand_sync_state("PH", 11))
    assert other == (store.list_brands("SG", 12), store.brand_sync_state("SG", 12))
    assert session.require_current(11, store=store) is result.catalog


@pytest.mark.parametrize("pages", [
    [payload([raw_brand()], 100, True), payload([raw_brand(7, "Changed")])],
    [payload([raw_brand()], 100, True), payload([raw_brand()], 200, True)],
    [payload([raw_brand()], 100, True), payload([raw_brand(8)], 0, True)],
    [payload([raw_brand()], 100, True), RuntimeError("FAKE_TOKEN")],
    [payload([raw_brand()], 100, True), payload([None])],
])
def test_failed_run_keeps_old_rows_but_revokes_current(store, pages):
    session, result, _ = sync(store)
    old = store.list_brands("SG", 11), store.brand_sync_state("SG", 11)
    with pytest.raises(SGCategoryMapperError) as failure:
        sync(store, pages, session)
    assert "FAKE_TOKEN" not in str(failure.value)
    assert old == (store.list_brands("SG", 11), store.brand_sync_state("SG", 11))
    with pytest.raises(SGCategoryMapperError):
        session.require_current(11, store=store, catalog=result.catalog)


def test_ten_page_budget_does_not_request_eleven_or_replace(store):
    session, old, _ = sync(store)
    before = store.list_brands("SG", 11)
    pages = [payload([raw_brand(i + 100)], (i + 1) * 100, True) for i in range(10)]
    _, result, calls = sync(store, pages, session)
    assert result.status == "INCOMPLETE" and result.catalog is None and len(calls) == 10
    assert store.list_brands("SG", 11) == before
    with pytest.raises(SGCategoryMapperError):
        session.require_current(11, store=store)


def test_tenth_terminal_page_is_complete(store):
    pages = [payload([raw_brand(i + 100)], (i + 1) * 100, i < 9) for i in range(10)]
    _, result, calls = sync(store, pages)
    assert result.status == "SUCCESS" and len(calls) == 10


def test_replace_insert_failure_rolls_back_rows_and_state(store):
    session, old, _ = sync(store)
    before = store.list_brands("SG", 11), store.brand_sync_state("SG", 11)
    with store._connect() as connection:
        connection.execute("CREATE TRIGGER fail_brand BEFORE INSERT ON catalog_brands BEGIN SELECT RAISE(ABORT, 'fixture failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        sync(store, [payload([raw_brand(8)])], session)
    assert before == (store.list_brands("SG", 11), store.brand_sync_state("SG", 11))
    with pytest.raises(SGCategoryMapperError):
        session.require_current(11, store=store)


def test_new_session_never_restores_persisted_success(store):
    session, result, _ = sync(store)
    assert store.brand_sync_state("SG", 11)["is_complete"]
    new = SGBrandSession(marketplace="SG", shop_id=22)
    with pytest.raises(SGCategoryMapperError):
        new.require_current(11, store=store, catalog=result.catalog)
    with pytest.raises(SGCategoryMapperError):
        new._bind_committed(result.catalog, category_id=11, store=store)


@pytest.mark.parametrize("change", [{"category_id": 12}, {"marketplace": "PH"},
                                  {"shop_id": 23}, {"session_id": "other"}, {"digest": "wrong"}])
def test_catalog_cannot_bind_wrong_market_category_shop_session_digest(store, change):
    session, result, _ = sync(store)
    wrong = replace(result.catalog, **change)
    with pytest.raises(SGCategoryMapperError):
        session._bind_committed(wrong, category_id=11, store=store)
    with pytest.raises(SGCategoryMapperError):
        session.require_current(11, store=store, catalog=wrong)


def test_category_b_result_cannot_apply_to_category_a_product(store):
    session, a, _ = sync(store)
    _, b, _ = sync(store, session=session, category_id=12)
    with pytest.raises(SGCategoryMapperError):
        confirm(store, session, b.catalog)
    assert review_sg_brand(product(), store=store, session=session, catalog=b.catalog).brand_status == "REVIEW"


def test_client_shop_change_during_run_rejects_before_replace(store):
    session = SGBrandSession(marketplace="SG", shop_id=22)
    client, _ = client_for([])
    def corrupt(url, query, timeout):
        client.credentials = replace(client.credentials, shop_id=23)
        return payload()
    client._request_json = corrupt
    with pytest.raises(SGCategoryMapperError):
        sync_sg_brand_catalog_offline(client=client, session=session, store=store, confirmed_category_id=11)
    assert store.list_brands("SG", 11) == []


def test_db_catalog_change_revokes_current(store):
    session, result, _ = sync(store)
    with store._connect() as connection:
        connection.execute("UPDATE catalog_brands SET brand_name = 'Changed' WHERE marketplace = 'SG'")
    with pytest.raises(SGCategoryMapperError):
        session.require_current(11, store=store)
    assert review_sg_brand(product(), store=store, session=session).brand_status == "REVIEW"


def test_table_requires_explicit_initialization_and_default_db_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    normal = CategoryMapperStore()
    with normal._connect() as connection:
        before = list(connection.execute("SELECT name, sql FROM sqlite_master ORDER BY name"))
        assert not connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'product_no_brand_confirmations'").fetchone()
    with pytest.raises(ValueError):
        normal.initialize_sg_brand_acceptance()
    with normal._connect() as connection:
        assert before == list(connection.execute("SELECT name, sql FROM sqlite_master ORDER BY name"))
    explicit_default = CategoryMapperStore(normal.db_path)
    with pytest.raises(ValueError):
        explicit_default.initialize_sg_brand_acceptance()
    acceptance = CategoryMapperStore(tmp_path / "isolated.sqlite3")
    with pytest.raises(ValueError):
        acceptance.replace_sg_brand_catalog(11, [])
    acceptance.initialize_sg_brand_acceptance()
    with acceptance._connect() as connection:
        assert connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'product_no_brand_confirmations'").fetchone()


def test_two_products_no_brand_coexist_without_alias_or_other_product_reuse(store):
    session, result, _ = sync(store)
    first = confirm(store, session, result.catalog)
    second = confirm(store, session, result.catalog, product(candidate_asin="B000000002"))
    assert first.brand_status == second.brand_status == "NO_BRAND_CONFIRMED"
    for asin in ("B000000001", "B000000002"):
        assert store.find_sg_no_brand_confirmation(asin, 11)["no_brand_id"] == 99
        assert review_sg_brand(product(candidate_asin=asin), store=store, session=session).brand_status == "NO_BRAND_CONFIRMED"
    assert store.find_sg_brand_alias("Maker", 11) is None
    assert review_sg_brand(product(candidate_asin="B000000003"), store=store, session=session).brand_status == "CANDIDATE"
    assert not first.listing_ready and first.group_key == ""


@pytest.mark.parametrize("field,value", [("marketplace", "PH"), ("candidate_asin", "B000000002"),
    ("recommended_category_id", 12), ("recommended_category_path", "Old path"),
    ("product_title", "Changed"), ("keepa_brand", "Changed"), ("keepa_category", "Changed"),
    ("resolver_input_title", "Changed"), ("source_type", "RESOLVER"), ("source_asin", "B000000003"),
    ("category_is_confirmed", False), ("input_safety_state", "REVIEW")])
def test_no_brand_product_mismatch_not_reused(store, field, value):
    session, result, _ = sync(store)
    confirm(store, session, result.catalog)
    checked = review_sg_brand(replace(product(), **{field: value}), store=store, session=session)
    assert checked.brand_status not in ("NO_BRAND_CONFIRMED", "REAL_BRAND_CONFIRMED")
    assert not checked.listing_ready


@pytest.mark.parametrize("field,value", [("user_confirmed", 0), ("no_brand_id", 100),
                                      ("no_brand_name", "Changed"), ("source_brand", "Changed"),
                                      ("product_evidence_digest", "wrong")])
def test_no_brand_saved_mismatch_review_even_with_valid_real_alias(store, field, value):
    session, result, _ = sync(store)
    confirm(store, session, result.catalog, product(candidate_asin="B000000002"), 7, "Maker")
    confirm(store, session, result.catalog)
    with store._connect() as connection:
        connection.execute(f"UPDATE product_no_brand_confirmations SET {field} = ? WHERE candidate_asin = 'B000000001'", (value,))
    assert review_sg_brand(product(), store=store, session=session).brand_status == "REVIEW"


@pytest.mark.parametrize("brands", [[raw_brand()], [raw_brand(), raw_brand(100, "No Brand")],
                                   [raw_brand(), raw_brand(99, "Changed")]])
def test_current_no_brand_disappears_id_name_or_class_changes(store, brands):
    session, result, _ = sync(store)
    confirm(store, session, result.catalog)
    sync(store, [payload(brands)], session)
    assert review_sg_brand(product(), store=store, session=session).brand_status == "REVIEW"


def test_unregistered_brand_never_falls_back_to_no_brand_or_ph_policy(store):
    session, result, _ = sync(store)
    store.save_brand_alias(source_brand="Unknown", canonical_brand="Unknown", marketplace="PH", category_id=11,
                           shopee_brand_name="No Brand", brand_id=0, note="No Brand product")
    store.save_brand_policy(marketplace="PH", keepa_category="Synthetic category", keepa_brand="Unknown",
                            category_id=11, brand_policy="NO_BRAND", brand_id=0, note="No Brand product")
    checked = review_sg_brand(product(keepa_brand="Unknown"), store=store, session=session)
    assert checked.brand_status == "REVIEW" and checked.confirmed_brand_id is None
    assert store.find_sg_no_brand_confirmation("B000000001", 11) is None


def test_evidence_digest_fixed_version_fields_and_order():
    first = product()
    fields = {"candidate_asin": first.candidate_asin, "product_title": first.product_title,
              "keepa_brand": first.keepa_brand, "keepa_category": first.keepa_category,
              "resolver_input_title": first.resolver_input_title, "source_type": first.source_type,
              "source_asin": first.source_asin}
    expected = "SG_NO_BRAND_EVIDENCE_V1:" + sha256(json.dumps(fields, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    assert sg_no_brand_evidence_digest(first) == expected
    assert sg_no_brand_evidence_digest(replace(first, **dict(reversed(list(fields.items()))))) == expected
    assert sg_no_brand_evidence_digest(replace(first, brand_status="REVIEW")) == expected


@pytest.mark.parametrize("brands", [[raw_brand(8)], [raw_brand(7, "Changed")], [raw_brand(7, "No Brand")]])
def test_real_alias_current_id_name_class_changes_review(store, brands):
    session, result, _ = sync(store)
    confirm(store, session, result.catalog, brand_id=7, name="Maker")
    assert review_sg_brand(product(), store=store, session=session).brand_status == "REAL_BRAND_CONFIRMED"
    sync(store, [payload(brands)], session)
    assert review_sg_brand(product(), store=store, session=session).brand_status == "REVIEW"


def test_source_normalization_collision_and_missing_brand_review(store):
    session, result, _ = sync(store)
    confirm(store, session, result.catalog, brand_id=7, name="Maker")
    assert review_sg_brand(product(keepa_brand="Ｍaker"), store=store, session=session).brand_status == "REVIEW"
    with pytest.raises(ValueError):
        confirm(store, session, result.catalog, product(keepa_brand="Ｍaker"), 7, "Maker")
    assert review_sg_brand(product(keepa_brand=""), store=store, session=session).brand_status == "REVIEW"


@pytest.mark.parametrize("verified,selected", [(False, True), (True, False), (1, True)])
def test_human_confirmation_required(store, verified, selected):
    session, result, _ = sync(store)
    with pytest.raises(SGCategoryMapperError):
        confirm(store, session, result.catalog, verified=verified, selected=selected)
    assert store.find_sg_no_brand_confirmation("B000000001", 11) is None


def test_no_brand_to_real_change_atomic_and_rollback(store):
    session, result, _ = sync(store)
    confirm(store, session, result.catalog)
    with store._connect() as connection:
        connection.execute("CREATE TRIGGER fail_alias BEFORE INSERT ON brand_aliases BEGIN SELECT RAISE(ABORT, 'fixture'); END")
    with pytest.raises(sqlite3.IntegrityError):
        confirm(store, session, result.catalog, brand_id=7, name="Maker")
    assert store.find_sg_no_brand_confirmation("B000000001", 11) is not None
    assert store.find_sg_brand_alias("Maker", 11) is None
    with store._connect() as connection:
        connection.execute("DROP TRIGGER fail_alias")
    confirm(store, session, result.catalog, brand_id=7, name="Maker")
    assert store.find_sg_no_brand_confirmation("B000000001", 11) is None
    assert store.find_sg_brand_alias("Maker", 11)["brand_id"] == 7


@pytest.mark.parametrize("mutation", [
    "DELETE FROM catalog_brands WHERE marketplace = 'SG' AND brand_id = 99",
    "UPDATE catalog_brands SET is_no_brand = 2 WHERE marketplace = 'SG' AND brand_id = 99",
])
def test_confirmation_rechecks_db_inside_write_transaction(store, monkeypatch, mutation):
    session, result, _ = sync(store)
    original = store.save_sg_brand_confirmation
    def race(**kwargs):
        with store._connect() as connection:
            connection.execute(mutation)
        return original(**kwargs)
    monkeypatch.setattr(store, "save_sg_brand_confirmation", race)
    with pytest.raises(ValueError):
        confirm(store, session, result.catalog)
    assert store.find_sg_no_brand_confirmation("B000000001", 11) is None


@pytest.mark.parametrize("column,value", [("is_leaf", 0), ("category_path", "Old path")])
def test_no_brand_requires_current_category_path_and_leaf(store, column, value):
    session, result, _ = sync(store)
    confirm(store, session, result.catalog)
    with store._connect() as connection:
        connection.execute(f"UPDATE catalog_categories SET {column} = ? WHERE marketplace = 'SG' AND category_id = 11", (value,))
    assert review_sg_brand(product(), store=store, session=session).brand_status == "REVIEW"
    with pytest.raises(SGCategoryMapperError):
        confirm(store, session, result.catalog)


def test_category_reconfirmation_clears_previous_brand_state(store):
    session, result, _ = sync(store)
    old = confirm(store, session, result.catalog)
    changed = confirm_sg_category(old, store=store, category_id=12, expected_category_path="Root > B")
    assert changed.brand_status == "UNRESOLVED" and changed.confirmed_brand_id is None
    assert not changed.brand_current_valid and not changed.listing_ready


@pytest.mark.parametrize("item", [product(), product(keepa_brand="Ｍaker"),
                                  product(keepa_brand="Other", product_title="Maker synthetic item")])
def test_exact_normalized_and_title_matches_are_candidates_only(store, item):
    session, result, _ = sync(store)
    checked = review_sg_brand(item, store=store, session=session)
    assert checked.brand_status == "CANDIDATE" and checked.confirmed_brand_id is None
    assert checked.brand_candidates == ((7, "Maker"),)
    assert store.find_sg_brand_alias(item.keepa_brand, 11) is None
    assert not checked.listing_ready


def test_existing_ph_rows_and_schema_unchanged_by_sg_acceptance(store):
    def ph_baseline():
        with store._connect() as connection:
            schema = list(connection.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name != 'product_no_brand_confirmations' ORDER BY name"))
            rows = {}
            for name, _ in schema:
                columns = [row[1] for row in connection.execute(f"PRAGMA table_info({name})")]
                if "marketplace" in columns:
                    rows[name] = list(connection.execute(f"SELECT * FROM {name} WHERE marketplace = 'PH' ORDER BY rowid"))
            return schema, rows
    before = ph_baseline()
    session, result, _ = sync(store)
    confirm(store, session, result.catalog)
    confirm(store, session, result.catalog, brand_id=7, name="Maker")
    assert ph_baseline() == before


def test_raw_echo_fields_are_not_a_binding_authority():
    # API parser does not add undocumented market/Category identity fields.
    client, calls = client_for([payload()])
    page = client.get_brand_list("SG", 11, strict=True)
    assert all("marketplace" not in row and "category_id" not in row for row in page.brands)
    assert calls[0]["category_id"] == "11"


def test_source_brand_is_not_fabricated_for_human_no_brand(store):
    session, result, _ = sync(store)
    item = product(keepa_brand="")
    confirm(store, session, result.catalog, item)
    assert store.find_sg_no_brand_confirmation(item.candidate_asin, 11)["source_brand"] == ""
    assert review_sg_brand(item, store=store, session=session).brand_status == "NO_BRAND_CONFIRMED"


def test_category_changed_no_brand_never_silently_switches_to_real_alias(store):
    session, a, _ = sync(store)
    confirm(store, session, a.catalog)
    _, b, _ = sync(store, session=session, category_id=12)
    item_b = product(recommended_category_id=12, recommended_category_path="Root > B")
    confirm(store, session, b.catalog, replace(item_b, candidate_asin="B000000002"), 7, "Maker")
    assert review_sg_brand(item_b, store=store, session=session).brand_status == "REVIEW"
    confirm(store, session, b.catalog, item_b, 7, "Maker")
    assert not store.has_sg_no_brand_confirmation(item_b.candidate_asin)
    assert review_sg_brand(item_b, store=store, session=session).brand_status == "REAL_BRAND_CONFIRMED"


def test_evidence_digest_independent_of_csv_row_order_newlines_and_column_order():
    fields = ("candidate_asin", "product_title", "keepa_brand", "keepa_category",
              "resolver_input_title", "source_type", "source_asin")
    items = [product(), product(candidate_asin="B000000002")]
    digests = []
    for reverse, newline in ((False, "\n"), (True, "\r\n")):
        output = StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=list(reversed(fields)) if reverse else fields,
                                lineterminator=newline)
        writer.writeheader()
        for item in reversed(items) if reverse else items:
            writer.writerow({field: getattr(item, field) for field in fields})
        digests.append({row["candidate_asin"]: sg_no_brand_evidence_digest(product(**row))
                        for row in csv.DictReader(StringIO(output.getvalue(), newline=""))})
    assert digests[0] == digests[1]


@pytest.mark.parametrize("field,value", [("user_confirmed", 0), ("verification_status", "STALE"),
                                       ("canonical_brand", "Other")])
def test_unconfirmed_or_stale_alias_review(store, field, value):
    session, result, _ = sync(store)
    confirm(store, session, result.catalog, brand_id=7, name="Maker")
    with store._connect() as connection:
        connection.execute(f"UPDATE brand_aliases SET {field} = ? WHERE marketplace = 'SG'", (value,))
    assert review_sg_brand(product(), store=store, session=session).brand_status == "REVIEW"


@pytest.mark.parametrize("brand_id,name", [(999, "Missing"), (99, "Wrong"), (True, "No Brand")])
def test_selected_id_and_name_must_be_current(store, brand_id, name):
    session, result, _ = sync(store)
    with pytest.raises(SGCategoryMapperError):
        confirm(store, session, result.catalog, brand_id=brand_id, name=name)
    assert store.find_sg_no_brand_confirmation("B000000001", 11) is None


def test_strict_page_size_bound_and_original_name_conflict():
    for rows in ([raw_brand(i) for i in range(101)],
                 [raw_brand(), {**raw_brand(), "original_brand_name": "Other"}]):
        client, _ = client_for([payload(rows)])
        with pytest.raises(ShopeeCatalogError):
            client.get_brand_list("SG", 11, strict=True)
