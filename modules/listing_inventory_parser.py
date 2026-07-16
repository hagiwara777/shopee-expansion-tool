"""Parse existing Shopee listing inventory CSV exports without API access."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from typing import Iterable
import unicodedata

from modules.keepa_client import normalize_asin


REQUIRED_HEADERS = ("Product ID", "Parent SKU", "Model ID", "SKU", "Stock")
OPTIONAL_PRODUCT_NAME_HEADER = "Product Name"


class ListingInventoryParseError(RuntimeError):
    """Raised when an existing-listing CSV cannot be trusted."""


@dataclass(frozen=True)
class ListingEvidence:
    """One existing-listing ASIN occurrence from a parsed CSV row."""

    asin: str
    marketplace: str
    shop_label: str
    source_file: str
    source_row_number: int
    match_field: str
    product_id: str
    model_id: str
    stock: str
    product_name: str
    parent_sku: str
    sku: str


@dataclass(frozen=True)
class ListingInventoryFileResult:
    """The validated contents of one existing-listing CSV export."""

    marketplace: str
    shop_label: str
    source_file: str
    header_row_number: int
    data_row_count: int
    unique_asin_count: int
    evidence_records: tuple[ListingEvidence, ...]


def parse_listing_inventory_csv(
    content: bytes,
    *,
    filename: str,
    marketplace: str,
    shop_label: str,
) -> ListingInventoryFileResult:
    """Parse one UTF-8 existing-listing CSV and retain every ASIN occurrence."""

    text = _decode_utf8_content(content, filename)
    rows = _read_csv_rows(text, filename)
    header_index, header_row_number, header_positions = _find_header(rows, filename)

    evidence_records: list[ListingEvidence] = []
    data_row_count = 0
    for source_row_number, row in rows[header_index + 1 :]:
        if _is_blank_row(row):
            continue

        product_id = _cell(row, header_positions["product id"])
        parent_sku_raw = _cell(row, header_positions["parent sku"])
        model_id = _cell(row, header_positions["model id"])
        sku_raw = _cell(row, header_positions["sku"])
        stock = _cell(row, header_positions["stock"])
        product_name_index = header_positions.get("product name")
        product_name = _cell(row, product_name_index) if product_name_index is not None else ""

        if not _has_major_field_value(
            product_id,
            parent_sku_raw,
            model_id,
            sku_raw,
            stock,
            product_name,
        ):
            continue

        data_row_count += 1
        if not product_id.strip():
            raise _row_error(
                filename,
                source_row_number,
                "Product ID",
                product_id,
                "Product IDが空です。",
            )

        parent_sku = _normalize_row_asin(
            parent_sku_raw,
            filename=filename,
            source_row_number=source_row_number,
            column_name="Parent SKU",
            required=True,
        )
        sku = _normalize_row_asin(
            sku_raw,
            filename=filename,
            source_row_number=source_row_number,
            column_name="SKU",
            required=False,
        )

        evidence_records.append(
            ListingEvidence(
                asin=parent_sku,
                marketplace=marketplace,
                shop_label=shop_label,
                source_file=filename,
                source_row_number=source_row_number,
                match_field="Parent SKU",
                product_id=product_id,
                model_id=model_id,
                stock=stock,
                product_name=product_name,
                parent_sku=parent_sku,
                sku=sku,
            )
        )
        if sku:
            evidence_records.append(
                ListingEvidence(
                    asin=sku,
                    marketplace=marketplace,
                    shop_label=shop_label,
                    source_file=filename,
                    source_row_number=source_row_number,
                    match_field="SKU",
                    product_id=product_id,
                    model_id=model_id,
                    stock=stock,
                    product_name=product_name,
                    parent_sku=parent_sku,
                    sku=sku,
                )
            )

    if data_row_count == 0:
        raise ListingInventoryParseError(
            f"{filename}: ヘッダー行の後に既出品データ行がありません。"
        )

    unique_asins = {evidence.asin for evidence in evidence_records}
    if not unique_asins:
        raise ListingInventoryParseError(
            f"{filename}: 有効な既出品ASINが0件です。CSV内容を確認してください。"
        )

    return ListingInventoryFileResult(
        marketplace=marketplace,
        shop_label=shop_label,
        source_file=filename,
        header_row_number=header_row_number,
        data_row_count=data_row_count,
        unique_asin_count=len(unique_asins),
        evidence_records=tuple(evidence_records),
    )


def build_existing_asin_index(
    results: Iterable[ListingInventoryFileResult],
) -> dict[str, list[ListingEvidence]]:
    """Build an ordered ASIN-to-evidence index from validated CSV results."""

    file_results = tuple(results)
    marketplaces = {
        _normalize_marketplace(result.marketplace)
        for result in file_results
    }
    if len(marketplaces) > 1:
        raise ListingInventoryParseError(
            "既出品CSVに異なるマーケットプレイスが混在しています。"
        )

    index: dict[str, list[ListingEvidence]] = {}
    for result in file_results:
        for evidence in result.evidence_records:
            asin = _normalize_row_asin(
                evidence.asin,
                filename=evidence.source_file,
                source_row_number=evidence.source_row_number,
                column_name=evidence.match_field,
                required=True,
            )
            index.setdefault(asin, []).append(evidence)

    if not index:
        raise ListingInventoryParseError(
            "有効な既出品ASINが0件です。CSV内容を確認してください。"
        )
    return index


def _decode_utf8_content(content: bytes, filename: str) -> str:
    if not isinstance(content, (bytes, bytearray)):
        raise ListingInventoryParseError(f"{filename}: CSV内容がバイト列ではありません。")
    try:
        text = bytes(content).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ListingInventoryParseError(
            f"{filename} をUTF-8として読み込めません。"
            "GoogleスプレッドシートからCSV形式で再ダウンロードしてください。"
        ) from exc

    if not text.strip():
        raise ListingInventoryParseError(f"{filename}: CSV内容が空です。")
    return text


def _read_csv_rows(text: str, filename: str) -> list[tuple[int, list[str]]]:
    reader = csv.reader(StringIO(text, newline=""), strict=True)
    rows: list[tuple[int, list[str]]] = []
    try:
        for row in reader:
            rows.append((reader.line_num, row))
    except csv.Error as exc:
        raise ListingInventoryParseError(
            f"{filename} をCSVとして解析できません: {exc}"
        ) from exc
    return rows


def _find_header(
    rows: list[tuple[int, list[str]]],
    filename: str,
) -> tuple[int, int, dict[str, int]]:
    required_keys = tuple(_normalize_header_name(name) for name in REQUIRED_HEADERS)
    candidates: list[tuple[int, int, dict[str, int]]] = []

    for row_index, (source_row_number, row) in enumerate(rows):
        positions: dict[str, int] = {}
        duplicate_required_headers: set[str] = set()
        for column_index, value in enumerate(row):
            header_name = _normalize_header_name(value)
            if header_name in positions and header_name in required_keys:
                duplicate_required_headers.add(header_name)
            elif header_name not in positions:
                positions[header_name] = column_index

        if all(key in positions for key in required_keys):
            if duplicate_required_headers:
                duplicated = ", ".join(sorted(duplicate_required_headers))
                raise ListingInventoryParseError(
                    f"{filename} のCSV {source_row_number}行目: "
                    f"必須ヘッダーが重複しています: {duplicated}"
                )
            candidates.append((row_index, source_row_number, positions))

    if not candidates:
        required_display = ", ".join(REQUIRED_HEADERS)
        raise ListingInventoryParseError(
            f"{filename}: 必須ヘッダーが見つかりません: {required_display}"
        )
    if len(candidates) > 1:
        row_numbers = ", ".join(str(candidate[1]) for candidate in candidates)
        raise ListingInventoryParseError(
            f"{filename}: ヘッダー行が複数見つかりました: {row_numbers}行目"
        )
    return candidates[0]


def _normalize_header_name(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").strip().casefold()


def _normalize_marketplace(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").strip().casefold()


def _normalize_row_asin(
    raw_value: str,
    *,
    filename: str,
    source_row_number: int,
    column_name: str,
    required: bool,
) -> str:
    original_value = "" if raw_value is None else str(raw_value)
    candidate = unicodedata.normalize("NFKC", original_value).strip().upper()
    if not candidate:
        if required:
            raise _row_error(
                filename,
                source_row_number,
                column_name,
                original_value,
                f"{column_name}が空です。",
            )
        return ""

    try:
        return normalize_asin(candidate)
    except ValueError as exc:
        raise _row_error(
            filename,
            source_row_number,
            column_name,
            original_value,
            f"ASIN形式が不正です: {exc}",
        ) from exc


def _row_error(
    filename: str,
    source_row_number: int,
    column_name: str,
    value: str,
    message: str,
) -> ListingInventoryParseError:
    return ListingInventoryParseError(
        f"{filename} のCSV {source_row_number}行目、{column_name}: "
        f"{message} 値={value!r}"
    )


def _cell(row: list[str], index: int) -> str:
    return row[index] if index < len(row) else ""


def _is_blank_row(row: list[str]) -> bool:
    return not any(cell.strip() for cell in row)


def _has_major_field_value(*values: str) -> bool:
    return any(value.strip() for value in values)
