from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
import re
from typing import Any, Iterable
from urllib.parse import urlparse

from modules.keepa_client import KeepaClientError, KeepaExpansionClient, normalize_asin


RESOLVER_CSV_COLUMNS = [
    "input_title",
    "amazon_url",
    "asin",
    "status",
    "verification",
    "note",
]

FOUND = "FOUND"
UNKNOWN = "UNKNOWN"
ERROR = "ERROR"
KEEPA_VERIFIED = "KEEPA_VERIFIED"
KEEPA_NOT_FOUND = "KEEPA_NOT_FOUND"
NOT_CHECKED = "NOT_CHECKED"

UNKNOWN_VALUES = {"", "不明", "unknown", "n/a", "na", "none", "null", "-"}
DIRECT_ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


@dataclass(frozen=True)
class ResolverInput:
    input_title: str
    amazon_url: str
    asin: str
    status: str
    verification: str
    note: str


def build_ai_prompt(product_names_text: str) -> str:
    names = _non_empty_lines(product_names_text)
    numbered_names = "\n".join(f"{index}. {name}" for index, name in enumerate(names, 1))
    return (
        "以下の商品について、Amazon.co.jpの商品URLだけをCSV形式で返してください。\n"
        "説明は不要です。\n"
        "見つからなければ「不明」としてください。\n\n"
        "出力形式:\n"
        "input_title,amazon_url\n\n"
        "商品名:\n\n"
        f"{numbered_names}"
    )


def parse_ai_response(response_text: str) -> list[ResolverInput]:
    cleaned = clean_ai_response(response_text)
    if not cleaned:
        return []

    rows = list(csv.reader(StringIO(cleaned)))
    parsed_rows: list[ResolverInput] = []

    for row_index, row in enumerate(rows):
        if _is_header_row(row_index, row):
            continue
        parsed = _parse_csv_row(row)
        if parsed is not None:
            parsed_rows.append(parsed)

    return parsed_rows


def resolve_candidates(
    response_text: str,
    client: KeepaExpansionClient,
) -> list[dict[str, str]]:
    resolver_rows = parse_ai_response(response_text)
    asins_to_check = _unique_asins_to_check(resolver_rows)

    verified_asins: set[str] = set()
    if asins_to_check:
        try:
            products_by_asin = client.verify_products_by_asin(asins_to_check)
        except KeepaClientError as exc:
            return [
                _row_to_dict(
                    row,
                    status=ERROR,
                    verification=ERROR,
                    note=_join_notes(row.note, str(exc)),
                )
                if row.asin in asins_to_check
                else _row_to_dict(row)
                for row in resolver_rows
            ]
        verified_asins = set(products_by_asin)

    output_rows: list[dict[str, str]] = []
    for row in resolver_rows:
        if row.asin and row.asin in verified_asins:
            output_rows.append(
                _row_to_dict(row, status=FOUND, verification=KEEPA_VERIFIED, note=row.note)
            )
        elif row.asin and row.verification != NOT_CHECKED:
            output_rows.append(
                _row_to_dict(
                    row,
                    status=UNKNOWN,
                    verification=KEEPA_NOT_FOUND,
                    note=_join_notes(row.note, "Keepa did not return product data"),
                )
            )
        else:
            output_rows.append(_row_to_dict(row))

    return output_rows


def rows_to_resolver_csv(rows: Iterable[dict[str, str]]) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=RESOLVER_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") or "" for column in RESOLVER_CSV_COLUMNS})
    return buffer.getvalue().encode("utf-8-sig")


def summarize_statuses(rows: Iterable[dict[str, str]]) -> dict[str, int]:
    summary = {FOUND: 0, UNKNOWN: 0, ERROR: 0}
    for row in rows:
        status = str(row.get("status") or "").strip().upper()
        if status in summary:
            summary[status] += 1
    return summary


def clean_ai_response(response_text: str) -> str:
    lines = []
    for line in (response_text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower() == "```csv" or stripped == "```":
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def _parse_csv_row(row: list[str]) -> ResolverInput | None:
    if not row:
        return None

    cells = [cell.strip() for cell in row]
    if len(cells) >= 2:
        return _build_resolver_input(input_title=cells[0], value=cells[1])

    line = cells[0]
    return _build_resolver_input(input_title=line, value=line)


def _build_resolver_input(input_title: str, value: str) -> ResolverInput:
    normalized_value = (value or "").strip()
    if normalized_value.casefold() in UNKNOWN_VALUES:
        return ResolverInput(input_title, normalized_value, "", UNKNOWN, NOT_CHECKED, "AI returned unknown")

    amazon_jp_url, asin_from_url = _extract_amazon_jp_url_and_asin(normalized_value)
    if asin_from_url:
        try:
            asin = normalize_asin(asin_from_url)
        except ValueError:
            return ResolverInput(
                input_title,
                amazon_jp_url,
                "",
                UNKNOWN,
                NOT_CHECKED,
                "Invalid ASIN format",
            )
        return ResolverInput(input_title, amazon_jp_url, asin, UNKNOWN, KEEPA_NOT_FOUND, "")

    if _contains_url(normalized_value):
        return ResolverInput(
            input_title,
            normalized_value,
            "",
            UNKNOWN,
            NOT_CHECKED,
            "Not Amazon.co.jp URL",
        )

    if DIRECT_ASIN_PATTERN.fullmatch(normalized_value):
        asin = normalize_asin(normalized_value)
        return ResolverInput(input_title, "", asin, UNKNOWN, KEEPA_NOT_FOUND, "")

    return ResolverInput(input_title, normalized_value, "", UNKNOWN, NOT_CHECKED, "No Amazon.co.jp URL or ASIN")


def _extract_amazon_jp_url_and_asin(value: str) -> tuple[str, str]:
    for url in URL_PATTERN.findall(value):
        cleaned_url = url.rstrip(".,);]")
        parsed = urlparse(cleaned_url)
        if parsed.netloc.lower() not in {"amazon.co.jp", "www.amazon.co.jp"}:
            continue
        path_parts = [part for part in parsed.path.split("/") if part]
        for index, part in enumerate(path_parts):
            if part == "dp" and index + 1 < len(path_parts):
                return cleaned_url, path_parts[index + 1].upper()
            if part == "gp" and index + 2 < len(path_parts) and path_parts[index + 1] == "product":
                return cleaned_url, path_parts[index + 2].upper()
    return "", ""


def _contains_url(value: str) -> bool:
    return bool(URL_PATTERN.search(value))


def _unique_asins_to_check(rows: Iterable[ResolverInput]) -> list[str]:
    seen: set[str] = set()
    unique_asins: list[str] = []
    for row in rows:
        if not row.asin or row.verification == NOT_CHECKED or row.asin in seen:
            continue
        seen.add(row.asin)
        unique_asins.append(row.asin)
    return unique_asins


def _row_to_dict(
    row: ResolverInput,
    status: str | None = None,
    verification: str | None = None,
    note: str | None = None,
) -> dict[str, str]:
    return {
        "input_title": row.input_title,
        "amazon_url": row.amazon_url,
        "asin": row.asin,
        "status": status or row.status,
        "verification": verification or row.verification,
        "note": note if note is not None else row.note,
    }


def _join_notes(*notes: str) -> str:
    return " ".join(note.strip() for note in notes if note and note.strip())


def _is_header_row(row_index: int, row: list[str]) -> bool:
    if row_index != 0 or len(row) < 2:
        return False
    first = row[0].strip().casefold()
    second = row[1].strip().casefold()
    return first == "input_title" and second == "amazon_url"


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]
