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
EMBEDDED_ASIN_PATTERN = re.compile(
    r"(?i)(?:amazon\s+asin|候補\s*asin|asin)\s*[:=]?\s*"
    r"(?<![A-Z0-9])([A-Z0-9]{10})(?![A-Z0-9])"
)
AMAZON_JP_URL_PATTERN = re.compile(
    r"(?<![A-Z0-9.-])((?:https?://)?(?:www\.)?amazon\.co\.jp/[^\s\"'<>|]+)",
    re.IGNORECASE,
)
URL_LIKE_PATTERN = re.compile(
    r"(?<!@)(?:(?:https?://|www\.)[^\s\"'<>|]+|"
    r"(?:[A-Z0-9-]+\.)+[A-Z]{2,}/[^\s\"'<>|]+)",
    re.IGNORECASE,
)
MARKDOWN_SEPARATOR_PATTERN = re.compile(r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?$")
EXPLANATION_PATTERNS = [
    re.compile(r"^以下(?:に|が).*(?:結果|示し)", re.IGNORECASE),
    re.compile(r"^こちら(?:が|に).*(?:結果|調査)", re.IGNORECASE),
    re.compile(r"^商品が見つからない場合", re.IGNORECASE),
    re.compile(r"^(?:here are|here is|the following).*(?:result|finding)", re.IGNORECASE),
]


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
        "以下の商品について、Amazon.co.jpの商品URLをTSV形式で返してください。\n"
        "説明文は付けず、Markdown表にはしないでください。\n"
        "1行目は input_title<TAB>amazon_url としてください。\n"
        "見つからなければ「不明」としてください。\n"
        "Amazon.co.jpの商品URLだけを返し、amazon.comやamazon.sgなど海外Amazonは返さないでください。\n"
        "URLが不明な場合は推測URLを作らず、商品の順番を維持してください。\n\n"
        "出力形式:\n"
        "input_title\tamazon_url\n\n"
        "商品名:\n\n"
        f"{numbered_names}"
    )


def parse_ai_response(response_text: str) -> list[ResolverInput]:
    cleaned = clean_ai_response(response_text)
    if not cleaned:
        return []

    parsed_rows: list[ResolverInput] = []
    for line in cleaned.splitlines():
        parsed = _parse_line(line)
        if parsed is not None:
            parsed_rows.append(parsed)
    return parsed_rows


def preview_candidates(response_text: str) -> list[dict[str, str]]:
    return [_row_to_dict(row) for row in parse_ai_response(response_text)]


def summarize_preview(rows: Iterable[dict[str, str]]) -> dict[str, int]:
    materialized = list(rows)
    extracted_asin_rows = sum(1 for row in materialized if row.get("asin"))
    unique_asins = {str(row.get("asin") or "") for row in materialized if row.get("asin")}
    return {
        "extracted_asin_rows": extracted_asin_rows,
        "unique_asins": len(unique_asins),
        "not_checked": sum(
            1 for row in materialized if row.get("verification") == NOT_CHECKED
        ),
        "non_jp_url": sum(
            1 for row in materialized if row.get("note") == "Not Amazon.co.jp URL"
        ),
        "unresolved": sum(
            1
            for row in materialized
            if row.get("note") == "No Amazon.co.jp URL or ASIN"
        ),
    }


def verify_preview_rows(
    rows: Iterable[dict[str, str]],
    client: KeepaExpansionClient,
) -> list[dict[str, str]]:
    materialized = [dict(row) for row in rows]
    asins_to_check = _unique_asins_from_rows(materialized)

    verified_asins: set[str] = set()
    if asins_to_check:
        try:
            products_by_asin = client.verify_products_by_asin(asins_to_check)
        except KeepaClientError as exc:
            return [
                _verified_row(row, ERROR, ERROR, _join_notes(row.get("note", ""), str(exc)))
                if row.get("asin") in asins_to_check
                else row
                for row in materialized
            ]
        verified_asins = set(products_by_asin)

    output_rows: list[dict[str, str]] = []
    for row in materialized:
        asin = str(row.get("asin") or "")
        if asin and asin in verified_asins:
            output_rows.append(
                _verified_row(row, FOUND, KEEPA_VERIFIED, row.get("note", ""))
            )
        elif asin:
            output_rows.append(
                _verified_row(
                    row,
                    UNKNOWN,
                    KEEPA_NOT_FOUND,
                    _join_notes(row.get("note", ""), "Keepa did not return product data"),
                )
            )
        else:
            output_rows.append(row)
    return output_rows


def resolve_candidates(
    response_text: str,
    client: KeepaExpansionClient,
) -> list[dict[str, str]]:
    return verify_preview_rows(preview_candidates(response_text), client)


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
        if not stripped or stripped.startswith("```"):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def _parse_line(line: str) -> ResolverInput | None:
    cells = _parse_cells(line)
    input_title = _input_title(line, cells)
    search_values = [*cells, line]

    invalid_amazon_url = ""
    amazon_url_without_asin = ""
    for value in search_values:
        amazon_url, asin_from_url = _extract_amazon_jp_url_and_asin(value)
        if not amazon_url:
            continue
        if not asin_from_url:
            amazon_url_without_asin = amazon_url_without_asin or amazon_url
            continue
        try:
            asin = normalize_asin(asin_from_url)
        except ValueError:
            invalid_amazon_url = invalid_amazon_url or amazon_url
            continue
        return ResolverInput(
            input_title,
            amazon_url,
            asin,
            UNKNOWN,
            NOT_CHECKED,
            "Extracted ASIN from Amazon.co.jp URL",
        )

    for value in search_values:
        embedded_match = EMBEDDED_ASIN_PATTERN.search(value)
        if embedded_match:
            asin = normalize_asin(embedded_match.group(1))
            return ResolverInput(
                input_title,
                "",
                asin,
                UNKNOWN,
                NOT_CHECKED,
                "Extracted ASIN from embedded text",
            )

    for value in cells:
        direct_value = _strip_list_prefix(value)
        if DIRECT_ASIN_PATTERN.fullmatch(direct_value):
            asin = normalize_asin(direct_value)
            return ResolverInput(
                input_title,
                "",
                asin,
                UNKNOWN,
                NOT_CHECKED,
                "Extracted ASIN from direct ASIN",
            )

    unknown_value = _find_unknown_value(cells)
    if unknown_value is not None:
        return ResolverInput(
            input_title,
            unknown_value,
            "",
            UNKNOWN,
            NOT_CHECKED,
            "AI returned unknown",
        )

    external_url = _find_non_jp_url(search_values)
    if external_url:
        return ResolverInput(
            input_title,
            external_url,
            "",
            UNKNOWN,
            NOT_CHECKED,
            "Not Amazon.co.jp URL",
        )

    if invalid_amazon_url:
        return ResolverInput(
            input_title,
            invalid_amazon_url,
            "",
            UNKNOWN,
            NOT_CHECKED,
            "Invalid ASIN format",
        )

    if amazon_url_without_asin:
        return ResolverInput(
            input_title,
            amazon_url_without_asin,
            "",
            UNKNOWN,
            NOT_CHECKED,
            "No Amazon.co.jp URL or ASIN",
        )

    if _is_skippable_line(line, cells):
        return None

    return ResolverInput(
        input_title,
        "",
        "",
        UNKNOWN,
        NOT_CHECKED,
        "No Amazon.co.jp URL or ASIN",
    )


def _parse_cells(line: str) -> list[str]:
    if "\t" in line:
        return _read_delimited_line(line, "\t")
    if _looks_like_markdown_row(line):
        return [cell.strip() for cell in line.strip().strip("|").split("|") if cell.strip()]
    if "," in line:
        return _read_delimited_line(line, ",")
    return [line.strip()]


def _read_delimited_line(line: str, delimiter: str) -> list[str]:
    try:
        return [cell.strip() for cell in next(csv.reader([line], delimiter=delimiter))]
    except csv.Error:
        return [line.strip()]


def _looks_like_markdown_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") or stripped.endswith("|") or stripped.count("|") >= 2


def _input_title(line: str, cells: list[str]) -> str:
    if len(cells) >= 2 and cells[0]:
        return _strip_list_prefix(cells[0])
    return _strip_list_prefix(line.strip())


def _extract_amazon_jp_url_and_asin(value: str) -> tuple[str, str]:
    first_amazon_url = ""
    for match in AMAZON_JP_URL_PATTERN.finditer(value):
        amazon_url = _normalize_url(match.group(1))
        first_amazon_url = first_amazon_url or amazon_url
        parsed = urlparse(amazon_url)
        if parsed.netloc.lower() not in {"amazon.co.jp", "www.amazon.co.jp"}:
            continue
        path_parts = [part for part in parsed.path.split("/") if part]
        for index, part in enumerate(path_parts):
            normalized_part = part.casefold()
            if normalized_part == "dp" and index + 1 < len(path_parts):
                return amazon_url, path_parts[index + 1].upper()
            if (
                normalized_part == "gp"
                and index + 2 < len(path_parts)
                and path_parts[index + 1].casefold() == "product"
            ):
                return amazon_url, path_parts[index + 2].upper()
    return first_amazon_url, ""


def _normalize_url(value: str) -> str:
    cleaned = value.rstrip(".,);]}。、、")
    if not re.match(r"^https?://", cleaned, re.IGNORECASE):
        cleaned = f"https://{cleaned}"
    return cleaned


def _find_non_jp_url(values: Iterable[str]) -> str:
    for value in values:
        for match in URL_LIKE_PATTERN.finditer(value):
            candidate = _normalize_url(match.group(0))
            host = urlparse(candidate).netloc.lower()
            if host not in {"amazon.co.jp", "www.amazon.co.jp"}:
                return candidate
    return ""


def _find_unknown_value(cells: Iterable[str]) -> str | None:
    for cell in cells:
        normalized = cell.strip()
        if normalized.casefold() in UNKNOWN_VALUES:
            return normalized
    return None


def _is_skippable_line(line: str, cells: list[str]) -> bool:
    if MARKDOWN_SEPARATOR_PATTERN.fullmatch(line.strip()):
        return True
    normalized_cells = {
        re.sub(r"[\s-]+", "_", cell.strip().casefold()) for cell in cells if cell.strip()
    }
    title_headers = {"input_title", "product_title", "商品名"}
    candidate_headers = {"amazon_url", "url", "asin", "amazon_asin"}
    if normalized_cells & title_headers and normalized_cells & candidate_headers:
        return True
    return any(pattern.search(line.strip()) for pattern in EXPLANATION_PATTERNS)


def _strip_list_prefix(value: str) -> str:
    return re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", value).strip()


def _unique_asins_from_rows(rows: Iterable[dict[str, str]]) -> list[str]:
    seen: set[str] = set()
    unique_asins: list[str] = []
    for row in rows:
        asin = str(row.get("asin") or "")
        if not asin or asin in seen:
            continue
        seen.add(asin)
        unique_asins.append(asin)
    return unique_asins


def _row_to_dict(row: ResolverInput) -> dict[str, str]:
    return {
        "input_title": row.input_title,
        "amazon_url": row.amazon_url,
        "asin": row.asin,
        "status": row.status,
        "verification": row.verification,
        "note": row.note,
    }


def _verified_row(
    row: dict[str, str],
    status: str,
    verification: str,
    note: str,
) -> dict[str, str]:
    verified = dict(row)
    verified.update({"status": status, "verification": verification, "note": note})
    return verified


def _join_notes(*notes: str) -> str:
    return " ".join(note.strip() for note in notes if note and note.strip())


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]
