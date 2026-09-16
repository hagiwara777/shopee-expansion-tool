"""Load and validate normalized marketplace Community NG Safety assets."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from typing import Iterable
import unicodedata


SUPPORTED_MARKETPLACES = ("MY", "PH", "SG", "TH", "TW", "VN")
RUNTIME_MARKETPLACES = {"PH", "SG"}
ASIN_COLUMNS = (
    "marketplace",
    "asin",
    "action",
    "source_id",
    "source_row",
    "enabled",
)
BRAND_COLUMNS = (
    "marketplace",
    "brand_key",
    "match_value",
    "action",
    "source_id",
    "source_row",
    "enabled",
)
MANIFEST_COLUMNS = (
    "source_id",
    "original_file_name",
    "sha256",
    "provided_date",
    "sheet_name",
    "data_type",
    "source_data_rows",
    "nonblank_records",
    "duplicate_records",
    "excluded_records",
    "quarantined_records",
    "normalized_output_rows",
    "raw_file_storage_policy",
)
RAW_STORAGE_POLICY = "OWNER_PROVIDED_REPO_EXTERNAL_HASH_PINNED"


class CommunityNgDataError(RuntimeError):
    """Raised when a normalized Community NG asset cannot be trusted."""


@dataclass(frozen=True)
class CommunityNgSource:
    source_id: str
    original_file_name: str
    sha256: str
    provided_date: str
    sheet_name: str
    data_type: str
    source_data_rows: int
    nonblank_records: int
    duplicate_records: int
    excluded_records: int
    quarantined_records: int
    normalized_output_rows: int
    raw_file_storage_policy: str


@dataclass(frozen=True)
class CommunityNgAsinBlock:
    marketplace: str
    asin: str
    source_id: str
    source_row: int


@dataclass(frozen=True)
class CommunityNgBrandBlock:
    marketplace: str
    brand_key: str
    match_value: str
    normalized_match_value: str
    source_id: str
    source_row: int


@dataclass(frozen=True)
class CommunityNgAssets:
    sources: tuple[CommunityNgSource, ...]
    asin_blocks: tuple[CommunityNgAsinBlock, ...]
    brand_blocks: tuple[CommunityNgBrandBlock, ...]


def normalize_brand_match(value: object) -> str:
    text = unicodedata.normalize("NFKC", "" if value is None else str(value))
    return re.sub(r"\s+", " ", text.strip()).casefold()


def normalize_asin(value: object) -> str:
    return unicodedata.normalize("NFKC", "" if value is None else str(value)).strip().upper()


def load_community_ng_assets(directory: str | Path | None = None) -> CommunityNgAssets:
    base_dir = Path(directory) if directory is not None else _default_directory()
    sources = _load_manifest(base_dir / "source_manifest.csv")
    source_by_id = {source.source_id: source for source in sources}
    asin_blocks = _load_asin_blocks(
        base_dir / "marketplace_asin_blocks.csv",
        source_by_id,
    )
    brand_blocks = _load_brand_blocks(
        base_dir / "marketplace_brand_blocks.csv",
        source_by_id,
    )
    return CommunityNgAssets(
        sources=tuple(sources),
        asin_blocks=tuple(asin_blocks),
        brand_blocks=tuple(brand_blocks),
    )


def asin_blocks_for_marketplace(
    assets: CommunityNgAssets,
    marketplace: str,
) -> tuple[CommunityNgAsinBlock, ...]:
    normalized_marketplace = _normalize_marketplace(marketplace)
    return tuple(
        block for block in assets.asin_blocks if block.marketplace == normalized_marketplace
    )


def brand_blocks_for_marketplace(
    assets: CommunityNgAssets,
    marketplace: str,
) -> tuple[CommunityNgBrandBlock, ...]:
    normalized_marketplace = _normalize_marketplace(marketplace)
    return tuple(
        block for block in assets.brand_blocks if block.marketplace == normalized_marketplace
    )


def _default_directory() -> Path:
    return Path(__file__).resolve().parent.parent / "guardrails" / "community_ng"


def _load_manifest(path: Path) -> list[CommunityNgSource]:
    rows = _read_rows(path, MANIFEST_COLUMNS)
    sources: list[CommunityNgSource] = []
    seen_ids: set[str] = set()
    for row_number, row in rows:
        source_id = row["source_id"]
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]*", source_id):
            raise CommunityNgDataError(f"{path.name} {row_number}行目: source_idが不正です。")
        if source_id in seen_ids:
            raise CommunityNgDataError(f"{path.name} {row_number}行目: source_idが重複しています。")
        sha256 = row["sha256"].lower()
        if row["sha256"] != sha256 or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise CommunityNgDataError(f"{path.name} {row_number}行目: SHA-256が不正です。")
        try:
            date.fromisoformat(row["provided_date"])
        except ValueError as exc:
            raise CommunityNgDataError(
                f"{path.name} {row_number}行目: provided_dateが不正です。"
            ) from exc
        data_type = row["data_type"]
        if data_type not in {"ASIN", "BRAND"}:
            raise CommunityNgDataError(f"{path.name} {row_number}行目: data_typeが不正です。")
        numeric_values = {
            column: _nonnegative_int(path.name, row_number, column, row[column])
            for column in (
                "source_data_rows",
                "nonblank_records",
                "duplicate_records",
                "excluded_records",
                "quarantined_records",
                "normalized_output_rows",
            )
        }
        if row["raw_file_storage_policy"] != RAW_STORAGE_POLICY:
            raise CommunityNgDataError(
                f"{path.name} {row_number}行目: raw_file_storage_policyが不正です。"
            )
        if not row["original_file_name"] or not row["sheet_name"]:
            raise CommunityNgDataError(f"{path.name} {row_number}行目: source identityが空です。")
        sources.append(
            CommunityNgSource(
                source_id=source_id,
                original_file_name=row["original_file_name"],
                sha256=sha256,
                provided_date=row["provided_date"],
                sheet_name=row["sheet_name"],
                data_type=data_type,
                raw_file_storage_policy=row["raw_file_storage_policy"],
                **numeric_values,
            )
        )
        seen_ids.add(source_id)
    if {source.data_type for source in sources} != {"ASIN", "BRAND"}:
        raise CommunityNgDataError(f"{path.name}: ASINとBRANDのsourceが必要です。")
    if [source.source_id for source in sources] != sorted(source.source_id for source in sources):
        raise CommunityNgDataError(f"{path.name}: source_id順に並べてください。")
    return sources


def _load_asin_blocks(
    path: Path,
    source_by_id: dict[str, CommunityNgSource],
) -> list[CommunityNgAsinBlock]:
    blocks: list[CommunityNgAsinBlock] = []
    seen: set[tuple[str, str]] = set()
    for row_number, row in _read_rows(path, ASIN_COLUMNS):
        marketplace = _normalize_marketplace(row["marketplace"], path.name, row_number)
        if row["marketplace"] != marketplace:
            raise CommunityNgDataError(f"{path.name} {row_number}行目: marketplaceが未正規化です。")
        asin = normalize_asin(row["asin"])
        if row["asin"] != asin or re.fullmatch(r"[A-Z0-9]{10}", asin) is None:
            raise CommunityNgDataError(f"{path.name} {row_number}行目: ASINが不正です。")
        _validate_block_contract(path.name, row_number, row)
        source = _source_for_row(path.name, row_number, row, source_by_id, "ASIN")
        source_row = _source_row(path.name, row_number, row["source_row"], source)
        key = (marketplace, asin)
        if key in seen:
            raise CommunityNgDataError(f"{path.name} {row_number}行目: marketplace + ASINが重複しています。")
        seen.add(key)
        blocks.append(
            CommunityNgAsinBlock(
                marketplace=marketplace,
                asin=asin,
                source_id=source.source_id,
                source_row=source_row,
            )
        )
    expected_order = sorted((block.marketplace, block.asin) for block in blocks)
    if [(block.marketplace, block.asin) for block in blocks] != expected_order:
        raise CommunityNgDataError(f"{path.name}: marketplace + ASIN順に並べてください。")
    _validate_manifest_output_count(path.name, blocks, source_by_id, "ASIN")
    return blocks


def _load_brand_blocks(
    path: Path,
    source_by_id: dict[str, CommunityNgSource],
) -> list[CommunityNgBrandBlock]:
    blocks: list[CommunityNgBrandBlock] = []
    seen: set[tuple[str, str]] = set()
    for row_number, row in _read_rows(path, BRAND_COLUMNS):
        marketplace = _normalize_marketplace(row["marketplace"], path.name, row_number)
        if row["marketplace"] != marketplace:
            raise CommunityNgDataError(f"{path.name} {row_number}行目: marketplaceが未正規化です。")
        brand_key = row["brand_key"]
        if re.fullmatch(r"[a-z0-9][a-z0-9-]*", brand_key) is None:
            raise CommunityNgDataError(f"{path.name} {row_number}行目: brand_keyが不正です。")
        match_value = _canonical_match_value(row["match_value"])
        if not match_value or match_value != row["match_value"]:
            raise CommunityNgDataError(f"{path.name} {row_number}行目: match_valueが未正規化です。")
        if re.fullmatch(r"B[A-Z0-9]{9}", normalize_asin(match_value)):
            raise CommunityNgDataError(f"{path.name} {row_number}行目: ブランド欄にASINが混入しています。")
        _validate_block_contract(path.name, row_number, row)
        source = _source_for_row(path.name, row_number, row, source_by_id, "BRAND")
        source_row = _source_row(path.name, row_number, row["source_row"], source)
        normalized_match_value = normalize_brand_match(match_value)
        key = (marketplace, normalized_match_value)
        if key in seen:
            raise CommunityNgDataError(
                f"{path.name} {row_number}行目: marketplace + match_valueが重複しています。"
            )
        seen.add(key)
        blocks.append(
            CommunityNgBrandBlock(
                marketplace=marketplace,
                brand_key=brand_key,
                match_value=match_value,
                normalized_match_value=normalized_match_value,
                source_id=source.source_id,
                source_row=source_row,
            )
        )
    expected_order = sorted(
        (block.marketplace, block.brand_key, block.normalized_match_value, block.match_value)
        for block in blocks
    )
    actual_order = [
        (block.marketplace, block.brand_key, block.normalized_match_value, block.match_value)
        for block in blocks
    ]
    if actual_order != expected_order:
        raise CommunityNgDataError(f"{path.name}: marketplace + brand_key + match_value順に並べてください。")
    _validate_manifest_output_count(path.name, blocks, source_by_id, "BRAND")
    return blocks


def _read_rows(path: Path, columns: Iterable[str]) -> list[tuple[int, dict[str, str]]]:
    expected = tuple(columns)
    if not path.exists():
        raise CommunityNgDataError(f"{path.name} が見つかりません。")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file, strict=True)
            if tuple(reader.fieldnames or ()) != expected:
                raise CommunityNgDataError(f"{path.name}: CSV列が不正です。")
            result: list[tuple[int, dict[str, str]]] = []
            for row_number, raw_row in enumerate(reader, start=2):
                if None in raw_row:
                    raise CommunityNgDataError(f"{path.name} {row_number}行目: CSV列数が不正です。")
                row = {key: "" if value is None else str(value) for key, value in raw_row.items()}
                if not any(row.values()):
                    continue
                result.append((row_number, row))
            return result
    except CommunityNgDataError:
        raise
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise CommunityNgDataError(f"{path.name} を読み込めません。") from exc


def _normalize_marketplace(
    value: str,
    file_name: str = "Community NG asset",
    row_number: int = 0,
) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).strip().upper()
    if normalized not in SUPPORTED_MARKETPLACES:
        location = f" {row_number}行目" if row_number else ""
        raise CommunityNgDataError(f"{file_name}{location}: marketplaceが不正です。")
    return normalized


def _canonical_match_value(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value)).strip()
    return re.sub(r"\s+", " ", text)


def _validate_block_contract(file_name: str, row_number: int, row: dict[str, str]) -> None:
    if row["action"] != "BLOCK" or row["enabled"] != "TRUE":
        raise CommunityNgDataError(
            f"{file_name} {row_number}行目: action=BLOCK / enabled=TRUEが必要です。"
        )


def _source_for_row(
    file_name: str,
    row_number: int,
    row: dict[str, str],
    source_by_id: dict[str, CommunityNgSource],
    expected_type: str,
) -> CommunityNgSource:
    source = source_by_id.get(row["source_id"])
    if source is None or source.data_type != expected_type:
        raise CommunityNgDataError(f"{file_name} {row_number}行目: source_idが不正です。")
    return source


def _source_row(
    file_name: str,
    row_number: int,
    raw_value: str,
    source: CommunityNgSource,
) -> int:
    source_row = _nonnegative_int(file_name, row_number, "source_row", raw_value)
    if source_row < 3 or source_row > source.source_data_rows + 2:
        raise CommunityNgDataError(f"{file_name} {row_number}行目: source_rowがsource範囲外です。")
    return source_row


def _nonnegative_int(file_name: str, row_number: int, column: str, value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise CommunityNgDataError(
            f"{file_name} {row_number}行目: {column}が整数ではありません。"
        ) from exc
    if parsed < 0 or str(parsed) != value:
        raise CommunityNgDataError(f"{file_name} {row_number}行目: {column}が不正です。")
    return parsed


def _validate_manifest_output_count(
    file_name: str,
    blocks: Iterable[object],
    source_by_id: dict[str, CommunityNgSource],
    data_type: str,
) -> None:
    actual = sum(1 for _ in blocks)
    expected = sum(
        source.normalized_output_rows
        for source in source_by_id.values()
        if source.data_type == data_type
    )
    if actual != expected:
        raise CommunityNgDataError(
            f"{file_name}: normalized output row countがsource_manifestと一致しません。"
        )
