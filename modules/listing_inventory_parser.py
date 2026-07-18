"""Parse existing Shopee listing inventory CSV exports without API access."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from typing import Any, Iterable
import unicodedata

from modules.keepa_client import normalize_asin


REQUIRED_HEADERS = ("Product ID", "Parent SKU", "Model ID", "SKU", "Stock")
OPTIONAL_PRODUCT_NAME_HEADER = "Product Name"
SUPPORTED_MARKETPLACES = frozenset({"SG", "PH"})


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

    normalized_marketplace = normalize_marketplace(marketplace, context="marketplace")
    normalized_shop_label = _normalize_shop_label(shop_label)
    _validate_filename_marketplace(filename, normalized_marketplace)
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
                marketplace=normalized_marketplace,
                shop_label=normalized_shop_label,
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
                    marketplace=normalized_marketplace,
                    shop_label=normalized_shop_label,
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

    unique_asins = {evidence.asin for evidence in evidence_records}
    if data_row_count and not unique_asins:
        raise ListingInventoryParseError(
            f"{filename}: 有効な既出品ASINが0件です。CSV内容を確認してください。"
        )

    return ListingInventoryFileResult(
        marketplace=normalized_marketplace,
        shop_label=normalized_shop_label,
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
    marketplaces: set[str] = set()
    result_marketplaces: list[str] = []
    for result in file_results:
        if not isinstance(result, ListingInventoryFileResult):
            raise ListingInventoryParseError("既出品CSVの結果型が不正です。")
        result_marketplace = normalize_marketplace(
            result.marketplace,
            context="既出品CSVのmarketplace",
        )
        marketplaces.add(result_marketplace)
        result_marketplaces.append(result_marketplace)
    if len(marketplaces) > 1:
        raise ListingInventoryParseError(
            "既出品CSVに異なるマーケットプレイスが混在しています。"
        )

    index: dict[str, list[ListingEvidence]] = {}
    for result, result_marketplace in zip(file_results, result_marketplaces):
        for evidence_number, evidence in enumerate(result.evidence_records, 1):
            if not isinstance(evidence, ListingEvidence):
                raise ListingInventoryParseError("既出品CSVの証跡型が不正です。")
            if normalize_marketplace(
                evidence.marketplace,
                context="既出品CSVの証跡marketplace",
            ) != result_marketplace:
                raise ListingInventoryParseError(
                    f"{result.source_file}: 証跡 {evidence_number}件目のmarketplaceが不一致です。"
                )
            asin = _normalize_row_asin(
                evidence.asin,
                filename=evidence.source_file,
                source_row_number=evidence.source_row_number,
                column_name=evidence.match_field,
                required=True,
            )
            index.setdefault(asin, []).append(evidence)

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


def normalize_marketplace(value: Any, *, context: str = "marketplace") -> str:
    """Return the canonical supported marketplace or raise fail-closed."""

    if not isinstance(value, str):
        raise ListingInventoryParseError(f"{context}は文字列でSGまたはPHを指定してください。")
    marketplace = unicodedata.normalize("NFKC", value).strip().upper()
    if marketplace not in SUPPORTED_MARKETPLACES:
        supported = "、".join(sorted(SUPPORTED_MARKETPLACES))
        raise ListingInventoryParseError(
            f"{context}は{supported}のいずれかを指定してください。"
        )
    return marketplace


def validate_inventory_filename_marketplace(filename: Any, marketplace: Any) -> None:
    """Reject only explicit SG/PH filename tokens that conflict with marketplace."""

    normalized_marketplace = normalize_marketplace(marketplace, context="marketplace")
    _validate_filename_marketplace(filename, normalized_marketplace)


def _normalize_shop_label(value: Any) -> str:
    if not isinstance(value, str):
        raise ListingInventoryParseError("shop_labelは空でない文字列で指定してください。")
    shop_label = unicodedata.normalize("NFKC", value).strip()
    if not shop_label:
        raise ListingInventoryParseError("shop_labelが空です。")
    return shop_label


def _validate_filename_marketplace(filename: Any, marketplace: str) -> None:
    if not isinstance(filename, str) or not filename.strip():
        raise ListingInventoryParseError("filenameは空でない文字列で指定してください。")
    tokens = _filename_marketplace_tokens(filename)
    if len(tokens) > 1:
        raise ListingInventoryParseError(
            f"{filename}: ファイル名にSGとPHの両方の市場表記があります。"
        )
    if tokens and marketplace not in tokens:
        stated_marketplace = next(iter(tokens))
        raise ListingInventoryParseError(
            f"{filename}: ファイル名の市場表記{stated_marketplace}が"
            f"指定marketplace {marketplace}と一致しません。"
        )


def _filename_marketplace_tokens(filename: str) -> frozenset[str]:
    """Find standalone market tokens without matching ordinary words or product names."""

    leaf_name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = leaf_name.rsplit(".", 1)[0] if "." in leaf_name else leaf_name
    normalized = unicodedata.normalize("NFKC", stem).strip().upper()
    tokens: list[str] = []
    current: list[str] = []
    for character in normalized:
        if character.isalnum():
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return frozenset(token for token in tokens if token in SUPPORTED_MARKETPLACES)


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
