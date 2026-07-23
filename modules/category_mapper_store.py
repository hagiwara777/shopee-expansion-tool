"""Local, non-repository persistence for the Category Mapper."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping


PH_MARKETPLACE = "PH"
_INITIAL_PROFILE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "category_mapper_initial_profiles.csv"
)


def utc_now_iso() -> str:
    """Return an auditable, timezone-aware timestamp."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_category_mapper_db_path() -> Path:
    """Return the user-local database location, never a repository path."""

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base_path = Path(local_app_data)
    else:
        base_path = Path.home() / "AppData" / "Local"
    return base_path / "ShopeeCategoryMapper" / "category_mapper.sqlite3"


class CategoryMapperStore:
    """Persist only normalized catalog data and user-confirmed mappings."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else default_category_mapper_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def catalog_status(self, marketplace: str) -> dict[str, Any]:
        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            category_row = connection.execute(
                """
                SELECT synced_at, api_status
                FROM category_sync_state
                WHERE marketplace = ?
                """,
                (marketplace,),
            ).fetchone()
            category_count = connection.execute(
                "SELECT COUNT(*) FROM catalog_categories WHERE marketplace = ?",
                (marketplace,),
            ).fetchone()[0]

        return {
            "marketplace": marketplace,
            "last_synced_at": "" if category_row is None else category_row["synced_at"] or "",
            "category_count": int(category_count),
            "api_status": "" if category_row is None else category_row["api_status"] or "",
            "using_cache": bool(category_count),
        }

    def save_categories(
        self,
        marketplace: str,
        categories: Iterable[Mapping[str, Any]],
        *,
        synced_at: str | None = None,
        api_version: str = "V2",
    ) -> int:
        """Save normalized category records and derive paths without raw payload storage."""

        marketplace = _marketplace(marketplace)
        timestamp = synced_at or utc_now_iso()
        normalized: dict[int, dict[str, Any]] = {}
        for category in categories:
            category_id = _positive_int(category.get("category_id"))
            if category_id is None:
                continue
            normalized[category_id] = {
                "category_id": category_id,
                "parent_category_id": _positive_int(category.get("parent_category_id")),
                "category_name": _text(category.get("category_name")),
                "is_leaf": _bool_int(category.get("is_leaf")),
                "is_others": _bool_int(category.get("is_others")),
            }

        with self._connect() as connection:
            existing = {
                int(row["category_id"]): dict(row)
                for row in connection.execute(
                    """
                    SELECT category_id, parent_category_id, category_name, category_path,
                           is_leaf, is_others
                    FROM catalog_categories
                    WHERE marketplace = ?
                    """,
                    (marketplace,),
                )
            }
            all_categories = {**existing, **normalized}
            rows = []
            for category in normalized.values():
                path = _build_category_path(category["category_id"], all_categories)
                rows.append(
                    (
                        marketplace,
                        category["category_id"],
                        category["parent_category_id"],
                        category["category_name"],
                        path,
                        category["is_leaf"],
                        category["is_others"],
                        timestamp,
                        api_version,
                    )
                )
            connection.executemany(
                """
                INSERT INTO catalog_categories (
                    marketplace, category_id, parent_category_id, category_name, category_path,
                    is_leaf, is_others, synced_at, api_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(marketplace, category_id) DO UPDATE SET
                    parent_category_id = excluded.parent_category_id,
                    category_name = excluded.category_name,
                    category_path = excluded.category_path,
                    is_leaf = excluded.is_leaf,
                    is_others = excluded.is_others,
                    synced_at = excluded.synced_at,
                    api_version = excluded.api_version
                """,
                rows,
            )
            connection.execute(
                """
                INSERT INTO category_sync_state (marketplace, synced_at, api_status)
                VALUES (?, ?, 'SUCCESS')
                ON CONFLICT(marketplace) DO UPDATE SET
                    synced_at = excluded.synced_at,
                    api_status = excluded.api_status
                """,
                (marketplace, timestamp),
            )
        return len(normalized)

    def record_category_sync_failure(self, marketplace: str) -> None:
        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO category_sync_state (marketplace, synced_at, api_status)
                VALUES (?, '', 'FAILED')
                ON CONFLICT(marketplace) DO UPDATE SET api_status = excluded.api_status
                """,
                (marketplace,),
            )

    def search_categories(
        self,
        marketplace: str,
        *,
        query: str = "",
        leaf_only: bool = False,
        others_only: bool = False,
        root_category_id: int | None = None,
        parent_category_id: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        marketplace = _marketplace(marketplace)
        clauses = ["marketplace = ?"]
        values: list[Any] = [marketplace]
        if query.strip():
            normalized_query = f"%{query.strip().casefold()}%"
            clauses.append(
                "(CAST(category_id AS TEXT) LIKE ? OR LOWER(category_name) LIKE ? "
                "OR LOWER(category_path) LIKE ?)"
            )
            values.extend([normalized_query, normalized_query, normalized_query])
        if leaf_only:
            clauses.append("is_leaf = 1")
        if others_only:
            clauses.append("is_others = 1")
        if parent_category_id is not None:
            clauses.append("parent_category_id = ?")
            values.append(int(parent_category_id))
        if root_category_id is not None:
            root = int(root_category_id)
            clauses.append("(category_id = ? OR category_path LIKE ?)")
            values.extend([root, f"{self._category_name_for(marketplace, root)} > %"])
        values.append(max(1, min(int(limit), 500)))
        sql = (
            "SELECT marketplace, category_id, parent_category_id, category_name, category_path, "
            "is_leaf, is_others, synced_at, api_version "
            "FROM catalog_categories WHERE "
            + " AND ".join(clauses)
            + " ORDER BY category_path, category_id LIMIT ?"
        )
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql, values)]

    def get_category(self, marketplace: str, category_id: int | str | None) -> dict[str, Any] | None:
        marketplace = _marketplace(marketplace)
        numeric_id = _positive_int(category_id)
        if numeric_id is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT marketplace, category_id, parent_category_id, category_name, category_path,
                       is_leaf, is_others, synced_at, api_version
                FROM catalog_categories
                WHERE marketplace = ? AND category_id = ?
                """,
                (marketplace, numeric_id),
            ).fetchone()
        return None if row is None else dict(row)

    def save_attributes(
        self,
        marketplace: str,
        category_id: int,
        attributes: Iterable[Mapping[str, Any]],
        *,
        synced_at: str | None = None,
    ) -> None:
        marketplace = _marketplace(marketplace)
        numeric_category_id = _require_category_id(category_id)
        timestamp = synced_at or utc_now_iso()
        rows = []
        for attribute in attributes:
            attribute_id = _text(attribute.get("attribute_id"))
            if not attribute_id:
                continue
            rows.append(
                (
                    marketplace,
                    numeric_category_id,
                    attribute_id,
                    _text(attribute.get("attribute_name")),
                    _bool_int(attribute.get("is_mandatory")),
                    _text(attribute.get("input_type")),
                    _text(attribute.get("validation_type")),
                    _nonnegative_int(attribute.get("value_count")) or 0,
                    _nonnegative_int(attribute.get("unit_count")) or 0,
                    timestamp,
                    _nonnegative_int(attribute.get("multi_select_max")) or 0,
                )
            )
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM catalog_attributes WHERE marketplace = ? AND category_id = ?",
                (marketplace, numeric_category_id),
            )
            connection.executemany(
                """
                INSERT INTO catalog_attributes (
                    marketplace, category_id, attribute_id, attribute_name, is_mandatory,
                    input_type, validation_type, value_count, unit_count, synced_at
                    , multi_select_max
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.execute(
                """
                INSERT INTO attribute_sync_state (marketplace, category_id, synced_at)
                VALUES (?, ?, ?)
                ON CONFLICT(marketplace, category_id) DO UPDATE SET
                    synced_at = excluded.synced_at
                """,
                (marketplace, numeric_category_id, timestamp),
            )

    def list_attributes(self, marketplace: str, category_id: int) -> list[dict[str, Any]]:
        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT marketplace, category_id, attribute_id, attribute_name, is_mandatory,
                           input_type, validation_type, value_count, unit_count, multi_select_max,
                           synced_at
                    FROM catalog_attributes
                    WHERE marketplace = ? AND category_id = ?
                    ORDER BY is_mandatory DESC, attribute_name, attribute_id
                    """,
                    (marketplace, _require_category_id(category_id)),
                )
            ]

    def mandatory_attribute_count(self, marketplace: str, category_id: int) -> int | None:
        attributes = self.list_attributes(marketplace, category_id)
        if attributes:
            return sum(int(attribute["is_mandatory"]) for attribute in attributes)
        with self._connect() as connection:
            synced = connection.execute(
                """
                SELECT 1 FROM attribute_sync_state
                WHERE marketplace = ? AND category_id = ?
                """,
                (marketplace, _require_category_id(category_id)),
            ).fetchone()
        if synced is not None:
            return 0
        profile = self.find_listing_profile_for_category(marketplace, category_id)
        if profile is None:
            return None
        return int(profile["mandatory_attribute_count"])

    def has_attribute_cache(self, marketplace: str, category_id: int) -> bool:
        """Return whether this Category has an explicit Attribute API result, including empty."""

        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            return (
                connection.execute(
                    """
                    SELECT 1 FROM attribute_sync_state
                    WHERE marketplace = ? AND category_id = ?
                    """,
                    (marketplace, _require_category_id(category_id)),
                ).fetchone()
                is not None
            )

    def save_brands(
        self,
        marketplace: str,
        category_id: int,
        brands: Iterable[Mapping[str, Any]],
        *,
        synced_at: str | None = None,
    ) -> None:
        marketplace = _marketplace(marketplace)
        numeric_category_id = _require_category_id(category_id)
        timestamp = synced_at or utc_now_iso()
        rows = []
        for brand in brands:
            brand_id = _nonnegative_int(brand.get("brand_id"))
            if brand_id is None:
                continue
            brand_name = _text(brand.get("brand_name"))
            rows.append(
                (
                    marketplace,
                    numeric_category_id,
                    brand_id,
                    brand_name,
                    normalize_brand(brand_name),
                    _bool_int(brand.get("is_no_brand")) or int(brand_id == 0),
                    timestamp,
                )
            )
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO catalog_brands (
                    marketplace, category_id, brand_id, brand_name, normalized_brand_name,
                    is_no_brand, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(marketplace, category_id, brand_id) DO UPDATE SET
                    brand_name = excluded.brand_name,
                    normalized_brand_name = excluded.normalized_brand_name,
                    is_no_brand = excluded.is_no_brand,
                    synced_at = excluded.synced_at
                """,
                rows,
            )

    def list_brands(self, marketplace: str, category_id: int) -> list[dict[str, Any]]:
        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT marketplace, category_id, brand_id, brand_name, normalized_brand_name,
                           is_no_brand, synced_at
                    FROM catalog_brands
                    WHERE marketplace = ? AND category_id = ?
                    ORDER BY is_no_brand DESC, brand_name COLLATE NOCASE, brand_id
                    """,
                    (marketplace, _require_category_id(category_id)),
                )
            ]

    def no_brand_available(self, marketplace: str, category_id: int) -> bool:
        return any(
            int(brand["is_no_brand"]) == 1
            for brand in self.list_brands(marketplace, category_id)
        )

    def brand_sync_state(self, marketplace: str, category_id: int) -> dict[str, Any]:
        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT next_offset, is_complete, synced_at, api_status
                FROM brand_sync_state
                WHERE marketplace = ? AND category_id = ?
                """,
                (marketplace, _require_category_id(category_id)),
            ).fetchone()
        if row is None:
            return {"next_offset": 0, "is_complete": False, "synced_at": "", "api_status": ""}
        return {
            "next_offset": int(row["next_offset"]),
            "is_complete": bool(row["is_complete"]),
            "synced_at": row["synced_at"] or "",
            "api_status": row["api_status"] or "",
        }

    def has_brand_cache(self, marketplace: str, category_id: int) -> bool:
        """Return whether at least the first Brand List page was read successfully."""

        return self.brand_sync_state(marketplace, category_id)["api_status"] == "SUCCESS"

    def save_brand_page(
        self,
        marketplace: str,
        category_id: int,
        brands: Iterable[Mapping[str, Any]],
        *,
        next_offset: int,
        is_complete: bool,
        synced_at: str | None = None,
    ) -> None:
        marketplace = _marketplace(marketplace)
        numeric_category_id = _require_category_id(category_id)
        timestamp = synced_at or utc_now_iso()
        self.save_brands(marketplace, numeric_category_id, brands, synced_at=timestamp)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO brand_sync_state (
                    marketplace, category_id, next_offset, is_complete, synced_at, api_status
                ) VALUES (?, ?, ?, ?, ?, 'SUCCESS')
                ON CONFLICT(marketplace, category_id) DO UPDATE SET
                    next_offset = excluded.next_offset,
                    is_complete = excluded.is_complete,
                    synced_at = excluded.synced_at,
                    api_status = excluded.api_status
                """,
                (
                    marketplace,
                    numeric_category_id,
                    max(0, int(next_offset)),
                    int(bool(is_complete)),
                    timestamp,
                ),
            )

    def record_brand_sync_failure(self, marketplace: str, category_id: int) -> None:
        marketplace = _marketplace(marketplace)
        numeric_category_id = _require_category_id(category_id)
        state = self.brand_sync_state(marketplace, numeric_category_id)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO brand_sync_state (
                    marketplace, category_id, next_offset, is_complete, synced_at, api_status
                ) VALUES (?, ?, ?, ?, ?, 'FAILED')
                ON CONFLICT(marketplace, category_id) DO UPDATE SET
                    api_status = excluded.api_status
                """,
                (
                    marketplace,
                    numeric_category_id,
                    state["next_offset"],
                    int(state["is_complete"]),
                    state["synced_at"],
                ),
            )

    def save_category_mapping(
        self,
        *,
        marketplace: str,
        mapping_key_type: str,
        mapping_key: str,
        canonical_product_type: str,
        category_id: int,
        category_path: str,
        note: str = "",
    ) -> None:
        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO category_mappings (
                    marketplace, mapping_key_type, mapping_key, canonical_product_type, category_id,
                    category_path, verification_status, support_count, user_confirmed,
                    last_verified_at, note
                ) VALUES (?, ?, ?, ?, ?, ?, 'USER_CONFIRMED', 1, 1, ?, ?)
                ON CONFLICT(marketplace, mapping_key_type, mapping_key) DO UPDATE SET
                    canonical_product_type = excluded.canonical_product_type,
                    category_id = excluded.category_id,
                    category_path = excluded.category_path,
                    verification_status = excluded.verification_status,
                    support_count = category_mappings.support_count + 1,
                    user_confirmed = 1,
                    last_verified_at = excluded.last_verified_at,
                    note = excluded.note
                """,
                (
                    marketplace,
                    _text(mapping_key_type).upper(),
                    normalize_mapping_key(mapping_key),
                    _text(canonical_product_type).upper(),
                    _require_category_id(category_id),
                    _text(category_path),
                    utc_now_iso(),
                    _text(note),
                ),
            )

    def find_confirmed_category_mapping(
        self,
        marketplace: str,
        mapping_key_type: str,
        mapping_key: str,
    ) -> dict[str, Any] | None:
        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT marketplace, mapping_key_type, mapping_key, canonical_product_type, category_id,
                       category_path, verification_status, support_count, user_confirmed,
                       last_verified_at, note
                FROM category_mappings
                WHERE marketplace = ? AND mapping_key_type = ? AND mapping_key = ?
                      AND user_confirmed = 1
                """,
                (marketplace, _text(mapping_key_type).upper(), normalize_mapping_key(mapping_key)),
            ).fetchone()
        return None if row is None else dict(row)

    def save_brand_alias(
        self,
        *,
        source_brand: str,
        canonical_brand: str,
        marketplace: str,
        category_id: int,
        shopee_brand_name: str,
        brand_id: int,
        note: str = "",
    ) -> None:
        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO brand_aliases (
                    source_brand, canonical_brand, marketplace, category_id, shopee_brand_name,
                    brand_id, verification_status, user_confirmed, last_verified_at, note
                ) VALUES (?, ?, ?, ?, ?, ?, 'USER_CONFIRMED', 1, ?, ?)
                ON CONFLICT(source_brand, marketplace, category_id) DO UPDATE SET
                    canonical_brand = excluded.canonical_brand,
                    shopee_brand_name = excluded.shopee_brand_name,
                    brand_id = excluded.brand_id,
                    verification_status = excluded.verification_status,
                    user_confirmed = 1,
                    last_verified_at = excluded.last_verified_at,
                    note = excluded.note
                """,
                (
                    normalize_brand(source_brand),
                    _text(canonical_brand),
                    marketplace,
                    _require_category_id(category_id),
                    _text(shopee_brand_name),
                    _nonnegative_int(brand_id),
                    utc_now_iso(),
                    _text(note),
                ),
            )

    def find_confirmed_brand_alias(
        self,
        marketplace: str,
        category_id: int,
        source_brand: str,
    ) -> dict[str, Any] | None:
        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT source_brand, canonical_brand, marketplace, category_id, shopee_brand_name,
                       brand_id, verification_status, user_confirmed, last_verified_at, note
                FROM brand_aliases
                WHERE marketplace = ? AND category_id = ? AND source_brand = ?
                      AND user_confirmed = 1
                """,
                (marketplace, _require_category_id(category_id), normalize_brand(source_brand)),
            ).fetchone()
        return None if row is None else dict(row)

    def save_brand_policy(
        self,
        *,
        marketplace: str,
        keepa_category: str,
        keepa_brand: str,
        category_id: int,
        brand_policy: str,
        brand_id: int,
        note: str = "",
    ) -> None:
        """Persist a listing policy separately from real brand aliases."""

        marketplace = _marketplace(marketplace)
        normalized_category = normalize_mapping_key(keepa_category)
        normalized_brand = normalize_brand(keepa_brand)
        if not normalized_category or not normalized_brand:
            raise ValueError("keepa_category and keepa_brand are required for brand policy.")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO listing_brand_policies (
                    marketplace, normalized_keepa_category, normalized_keepa_brand,
                    category_id, brand_policy, brand_id, user_confirmed,
                    last_verified_at, note
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(
                    marketplace, normalized_keepa_category, normalized_keepa_brand, category_id
                ) DO UPDATE SET
                    brand_policy = excluded.brand_policy,
                    brand_id = excluded.brand_id,
                    user_confirmed = 1,
                    last_verified_at = excluded.last_verified_at,
                    note = excluded.note
                """,
                (
                    marketplace,
                    normalized_category,
                    normalized_brand,
                    _require_category_id(category_id),
                    _text(brand_policy).upper(),
                    _nonnegative_int(brand_id),
                    utc_now_iso(),
                    _text(note),
                ),
            )

    def find_confirmed_brand_policy(
        self,
        marketplace: str,
        keepa_category: str,
        keepa_brand: str,
        category_id: int,
    ) -> dict[str, Any] | None:
        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT marketplace, normalized_keepa_category, normalized_keepa_brand,
                       category_id, brand_policy, brand_id, user_confirmed,
                       last_verified_at, note
                FROM listing_brand_policies
                WHERE marketplace = ?
                      AND normalized_keepa_category = ?
                      AND normalized_keepa_brand = ?
                      AND category_id = ?
                      AND user_confirmed = 1
                """,
                (
                    marketplace,
                    normalize_mapping_key(keepa_category),
                    normalize_brand(keepa_brand),
                    _require_category_id(category_id),
                ),
            ).fetchone()
        return None if row is None else dict(row)

    def find_listing_profile(
        self, marketplace: str, canonical_product_type: str
    ) -> dict[str, Any] | None:
        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT profile_id, marketplace, canonical_product_type, category_id, category_path,
                       brand_policy, brand_id, mandatory_attribute_count, verification_status,
                       last_verified_at, note
                FROM listing_profiles
                WHERE marketplace = ? AND canonical_product_type = ?
                ORDER BY CASE verification_status WHEN 'LISTING_TOOL_ACCEPTED' THEN 0 ELSE 1 END,
                         last_verified_at DESC
                LIMIT 1
                """,
                (marketplace, _text(canonical_product_type).upper()),
            ).fetchone()
        return None if row is None else dict(row)

    def find_listing_profile_for_category(
        self, marketplace: str, category_id: int
    ) -> dict[str, Any] | None:
        marketplace = _marketplace(marketplace)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT profile_id, marketplace, canonical_product_type, category_id, category_path,
                       brand_policy, brand_id, mandatory_attribute_count, verification_status,
                       last_verified_at, note
                FROM listing_profiles
                WHERE marketplace = ? AND category_id = ?
                ORDER BY CASE verification_status WHEN 'LISTING_TOOL_ACCEPTED' THEN 0 ELSE 1 END,
                         last_verified_at DESC
                LIMIT 1
                """,
                (marketplace, _require_category_id(category_id)),
            ).fetchone()
        return None if row is None else dict(row)

    def _category_name_for(self, marketplace: str, category_id: int) -> str:
        category = self.get_category(marketplace, category_id)
        return "" if category is None else str(category["category_name"])

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS catalog_categories (
                    marketplace TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    parent_category_id INTEGER,
                    category_name TEXT NOT NULL,
                    category_path TEXT NOT NULL,
                    is_leaf INTEGER NOT NULL,
                    is_others INTEGER NOT NULL,
                    synced_at TEXT NOT NULL,
                    api_version TEXT NOT NULL,
                    PRIMARY KEY (marketplace, category_id)
                );
                CREATE TABLE IF NOT EXISTS catalog_attributes (
                    marketplace TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    attribute_id TEXT NOT NULL,
                    attribute_name TEXT NOT NULL,
                    is_mandatory INTEGER NOT NULL,
                    input_type TEXT NOT NULL,
                    validation_type TEXT NOT NULL,
                    value_count INTEGER NOT NULL,
                    unit_count INTEGER NOT NULL,
                    multi_select_max INTEGER NOT NULL DEFAULT 0,
                    synced_at TEXT NOT NULL,
                    PRIMARY KEY (marketplace, category_id, attribute_id)
                );
                CREATE TABLE IF NOT EXISTS catalog_brands (
                    marketplace TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    brand_id INTEGER NOT NULL,
                    brand_name TEXT NOT NULL,
                    normalized_brand_name TEXT NOT NULL,
                    is_no_brand INTEGER NOT NULL,
                    synced_at TEXT NOT NULL,
                    PRIMARY KEY (marketplace, category_id, brand_id)
                );
                CREATE TABLE IF NOT EXISTS attribute_sync_state (
                    marketplace TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    synced_at TEXT NOT NULL,
                    PRIMARY KEY (marketplace, category_id)
                );
                CREATE TABLE IF NOT EXISTS category_mappings (
                    marketplace TEXT NOT NULL,
                    mapping_key_type TEXT NOT NULL,
                    mapping_key TEXT NOT NULL,
                    canonical_product_type TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    category_path TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    support_count INTEGER NOT NULL,
                    user_confirmed INTEGER NOT NULL,
                    last_verified_at TEXT NOT NULL,
                    note TEXT NOT NULL,
                    PRIMARY KEY (marketplace, mapping_key_type, mapping_key)
                );
                CREATE TABLE IF NOT EXISTS brand_aliases (
                    source_brand TEXT NOT NULL,
                    canonical_brand TEXT NOT NULL,
                    marketplace TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    shopee_brand_name TEXT NOT NULL,
                    brand_id INTEGER NOT NULL,
                    verification_status TEXT NOT NULL,
                    user_confirmed INTEGER NOT NULL,
                    last_verified_at TEXT NOT NULL,
                    note TEXT NOT NULL,
                    PRIMARY KEY (source_brand, marketplace, category_id)
                );
                CREATE TABLE IF NOT EXISTS listing_brand_policies (
                    marketplace TEXT NOT NULL,
                    normalized_keepa_category TEXT NOT NULL,
                    normalized_keepa_brand TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    brand_policy TEXT NOT NULL,
                    brand_id INTEGER NOT NULL,
                    user_confirmed INTEGER NOT NULL,
                    last_verified_at TEXT NOT NULL,
                    note TEXT NOT NULL,
                    PRIMARY KEY (
                        marketplace, normalized_keepa_category, normalized_keepa_brand, category_id
                    )
                );
                CREATE TABLE IF NOT EXISTS listing_profiles (
                    profile_id TEXT PRIMARY KEY,
                    marketplace TEXT NOT NULL,
                    canonical_product_type TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    category_path TEXT NOT NULL,
                    brand_policy TEXT NOT NULL,
                    brand_id INTEGER NOT NULL,
                    mandatory_attribute_count INTEGER NOT NULL,
                    verification_status TEXT NOT NULL,
                    last_verified_at TEXT NOT NULL,
                    note TEXT NOT NULL,
                    UNIQUE (marketplace, canonical_product_type, category_id)
                );
                CREATE TABLE IF NOT EXISTS category_sync_state (
                    marketplace TEXT PRIMARY KEY,
                    synced_at TEXT NOT NULL,
                    api_status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS brand_sync_state (
                    marketplace TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    next_offset INTEGER NOT NULL,
                    is_complete INTEGER NOT NULL,
                    synced_at TEXT NOT NULL,
                    api_status TEXT NOT NULL,
                    PRIMARY KEY (marketplace, category_id)
                );
                """
            )
            _ensure_column(
                connection,
                "catalog_attributes",
                "multi_select_max",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self._seed_initial_profiles(connection)

    @staticmethod
    def _seed_initial_profiles(connection: sqlite3.Connection) -> None:
        with _INITIAL_PROFILE_PATH.open(encoding="utf-8", newline="") as handle:
            profiles = list(csv.DictReader(handle))
        for profile in profiles:
            connection.execute(
                """
                INSERT OR IGNORE INTO listing_profiles (
                    profile_id, marketplace, canonical_product_type, category_id, category_path,
                    brand_policy, brand_id, mandatory_attribute_count, verification_status,
                    last_verified_at, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _text(profile.get("profile_id")),
                    _marketplace(profile.get("marketplace")),
                    _text(profile.get("canonical_product_type")).upper(),
                    _require_category_id(profile.get("category_id")),
                    _text(profile.get("category_path")),
                    _text(profile.get("brand_policy")),
                    _nonnegative_int(profile.get("brand_id")),
                    _nonnegative_int(profile.get("mandatory_attribute_count")),
                    _text(profile.get("verification_status")),
                    _text(profile.get("last_verified_at")),
                    _text(profile.get("note")),
                ),
            )
            if _text(profile.get("brand_policy")) == "NO_BRAND_ALLOWED":
                connection.execute(
                    """
                    INSERT OR IGNORE INTO catalog_brands (
                        marketplace, category_id, brand_id, brand_name, normalized_brand_name,
                        is_no_brand, synced_at
                    ) VALUES (?, ?, ?, 'No brand', 'no brand', 1, ?)
                    """,
                    (
                        _marketplace(profile.get("marketplace")),
                        _require_category_id(profile.get("category_id")),
                        _nonnegative_int(profile.get("brand_id")),
                        _text(profile.get("last_verified_at")),
                    ),
                )
            category_path = _text(profile.get("category_path"))
            category_name = category_path.split(">")[-1].strip()
            connection.execute(
                """
                INSERT OR IGNORE INTO catalog_categories (
                    marketplace, category_id, parent_category_id, category_name, category_path,
                    is_leaf, is_others, synced_at, api_version
                ) VALUES (?, ?, NULL, ?, ?, 1, 0, ?, 'INITIAL_PROFILE')
                """,
                (
                    _marketplace(profile.get("marketplace")),
                    _require_category_id(profile.get("category_id")),
                    category_name,
                    category_path,
                    _text(profile.get("last_verified_at")),
                ),
            )


def normalize_brand(value: object) -> str:
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKC", _text(value)).casefold().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return re.sub(r"[\-_./・]+", " ", normalized).strip()


def normalize_mapping_key(value: object) -> str:
    return normalize_brand(value)


def _build_category_path(category_id: int, categories: Mapping[int, Mapping[str, Any]]) -> str:
    names: list[str] = []
    current_id: int | None = category_id
    visited: set[int] = set()
    for _ in range(50):
        if current_id is None or current_id in visited:
            break
        visited.add(current_id)
        category = categories.get(current_id)
        if category is None:
            break
        name = _text(category.get("category_name"))
        if name:
            names.append(name)
        current_id = _positive_int(category.get("parent_category_id"))
    return " > ".join(reversed(names))


def _marketplace(value: object) -> str:
    marketplace = _text(value).upper()
    if marketplace != PH_MARKETPLACE:
        raise ValueError("Category Mapper supports PH only.")
    return marketplace


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _positive_int(value: object) -> int | None:
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _require_category_id(value: object) -> int:
    category_id = _positive_int(value)
    if category_id is None:
        raise ValueError("category_id must be a positive integer")
    return category_id


def _nonnegative_int(value: object) -> int | None:
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _bool_int(value: object) -> int:
    if isinstance(value, str):
        return int(value.strip().casefold() in {"1", "true", "yes", "y"})
    return int(bool(value))


def _ensure_column(
    connection: sqlite3.Connection, table_name: str, column_name: str, definition: str
) -> None:
    columns = {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table_name})")
    }
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
