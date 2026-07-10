from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from modules.config import CACHE_DB_PATH, CACHE_TTL_DAYS


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class KeepaCache:
    def __init__(self, db_path: str | Path = CACHE_DB_PATH, ttl_days: int = CACHE_TTL_DAYS):
        self.db_path = Path(db_path)
        self.ttl = timedelta(days=ttl_days)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_product(self, asin: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    asin, brand, category, category_id, product_title, fetched_at, response_json,
                    leaf_category_id, parent_category_id, root_category_id, category_path
                FROM products
                WHERE asin = ?
                """,
                (asin,),
            ).fetchone()

        if row is None or not self._is_fresh(row["fetched_at"]):
            return None

        response_data = json.loads(row["response_json"] or "{}")
        response_data.update(
            {
                "asin": row["asin"],
                "brand": row["brand"] or "",
                "category": row["category"] or "",
                "category_id": row["category_id"],
                "leaf_category_id": row["leaf_category_id"],
                "parent_category_id": row["parent_category_id"],
                "root_category_id": row["root_category_id"],
                "category_path": row["category_path"] or "",
                "title": row["product_title"] or "",
                "fetched_at": row["fetched_at"],
            }
        )
        return response_data

    def save_product(self, product: dict[str, Any]) -> None:
        fetched_at = product.get("fetched_at") or utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO products (
                    asin, brand, category, category_id, product_title, fetched_at, response_json,
                    leaf_category_id, parent_category_id, root_category_id, category_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asin) DO UPDATE SET
                    brand = excluded.brand,
                    category = excluded.category,
                    category_id = excluded.category_id,
                    product_title = excluded.product_title,
                    fetched_at = excluded.fetched_at,
                    response_json = excluded.response_json,
                    leaf_category_id = excluded.leaf_category_id,
                    parent_category_id = excluded.parent_category_id,
                    root_category_id = excluded.root_category_id,
                    category_path = excluded.category_path
                """,
                (
                    product["asin"],
                    product.get("brand", ""),
                    product.get("category", ""),
                    product.get("category_id"),
                    product.get("title", ""),
                    fetched_at,
                    json.dumps(product, ensure_ascii=False),
                    product.get("leaf_category_id"),
                    product.get("parent_category_id"),
                    product.get("root_category_id"),
                    product.get("category_path", ""),
                ),
            )

    def find_products(self, brand: str, category_id: int, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    asin, brand, category, category_id, product_title, fetched_at, response_json,
                    leaf_category_id, parent_category_id, root_category_id, category_path
                FROM products
                WHERE brand = ? AND leaf_category_id = ?
                ORDER BY fetched_at DESC
                LIMIT ?
                """,
                (brand, category_id, limit),
            ).fetchall()

        products = []
        for row in rows:
            if not self._is_fresh(row["fetched_at"]):
                continue
            response_data = json.loads(row["response_json"] or "{}")
            response_data.update(
                {
                    "asin": row["asin"],
                    "brand": row["brand"] or "",
                    "category": row["category"] or "",
                    "category_id": row["category_id"],
                    "leaf_category_id": row["leaf_category_id"],
                    "parent_category_id": row["parent_category_id"],
                    "root_category_id": row["root_category_id"],
                    "category_path": row["category_path"] or "",
                    "title": row["product_title"] or "",
                    "fetched_at": row["fetched_at"],
                }
            )
            products.append(response_data)
        return products

    def get_search(self, cache_key_data: dict[str, Any]) -> dict[str, Any] | None:
        cache_key = _search_cache_key(cache_key_data)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT result_json, fetched_at
                FROM searches_v2
                WHERE cache_key = ?
                """,
                (cache_key,),
            ).fetchone()

        if row is None or not self._is_fresh(row["fetched_at"]):
            return None

        result = json.loads(row["result_json"])
        result["cache_hit"] = True
        result["token_status"] = "キャッシュを使用したため、Keepa APIトークンは消費していません。"
        return result

    def save_search(self, result: dict[str, Any]) -> None:
        cache_key_data = result["cache_key_data"]
        cache_key = _search_cache_key(cache_key_data)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO searches_v2 (
                    cache_key, seed_asin, search_pages, search_mode, domain, per_page,
                    brand_normalized, leaf_category_id, parent_category_id, root_category_id,
                    query_hash, query_version, fetched_at, token_estimate, result_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    fetched_at = excluded.fetched_at,
                    token_estimate = excluded.token_estimate,
                    result_json = excluded.result_json
                """,
                (
                    cache_key,
                    result["source_asin"],
                    result["search_pages"],
                    result["search_mode"],
                    result["domain"],
                    result["per_page"],
                    cache_key_data["brand_normalized"],
                    cache_key_data["leaf_category_id"],
                    cache_key_data["parent_category_id"],
                    cache_key_data["root_category_id"],
                    cache_key_data["query_hash"],
                    cache_key_data["query_version"],
                    result["fetched_at"],
                    result["token_estimate"],
                    json.dumps(result, ensure_ascii=False),
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    asin TEXT PRIMARY KEY,
                    brand TEXT,
                    category TEXT,
                    category_id INTEGER,
                    product_title TEXT,
                    fetched_at TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    leaf_category_id INTEGER,
                    parent_category_id INTEGER,
                    root_category_id INTEGER,
                    category_path TEXT
                )
                """
            )
            _ensure_column(connection, "products", "leaf_category_id", "INTEGER")
            _ensure_column(connection, "products", "parent_category_id", "INTEGER")
            _ensure_column(connection, "products", "root_category_id", "INTEGER")
            _ensure_column(connection, "products", "category_path", "TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS searches (
                    seed_asin TEXT NOT NULL,
                    search_pages INTEGER NOT NULL,
                    brand TEXT,
                    category TEXT,
                    category_id INTEGER,
                    fetched_at TEXT NOT NULL,
                    token_estimate INTEGER NOT NULL,
                    result_json TEXT NOT NULL,
                    PRIMARY KEY (seed_asin, search_pages)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS searches_v2 (
                    cache_key TEXT PRIMARY KEY,
                    seed_asin TEXT NOT NULL,
                    search_pages INTEGER NOT NULL,
                    search_mode TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    per_page INTEGER NOT NULL,
                    brand_normalized TEXT,
                    leaf_category_id INTEGER,
                    parent_category_id INTEGER,
                    root_category_id INTEGER,
                    query_hash TEXT NOT NULL,
                    query_version TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    token_estimate INTEGER NOT NULL,
                    result_json TEXT NOT NULL
                )
                """
            )

    def _is_fresh(self, fetched_at: str) -> bool:
        try:
            fetched = datetime.fromisoformat(fetched_at)
        except ValueError:
            return False
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - fetched <= self.ttl


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _search_cache_key(cache_key_data: dict[str, Any]) -> str:
    return "|".join(
        str(cache_key_data.get(key, ""))
        for key in [
            "seed_asin",
            "search_pages",
            "search_mode",
            "domain",
            "per_page",
            "brand_normalized",
            "leaf_category_id",
            "parent_category_id",
            "root_category_id",
            "query_hash",
            "query_version",
        ]
    )
