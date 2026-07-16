from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
import re
from typing import Any, Iterable
from urllib.parse import urlparse
import unicodedata

from modules.keepa_client import KeepaClientError, KeepaExpansionClient, normalize_asin


RESOLVER_CSV_COLUMNS = [
    "source_id",
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
SOURCE_ID_PATTERN = re.compile(r"^R\d{4}$", re.IGNORECASE)
LEADING_SOURCE_ID_PATTERN = re.compile(r"^(R\d{4})\b\s*(.*)$", re.IGNORECASE)
SPACE_HEADER_PATTERN = re.compile(
    r"^source_id\s+input_title\s+(?:amazon_url|url|asin|amazon_asin)$",
    re.IGNORECASE,
)
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
SEARCH_TITLE_REMOVAL_PHRASES = (
    "100% authentic",
    "direct from japan",
    "official store",
    "made in japan",
    "ship from japan",
    "shipped from japan",
    "in stock",
    "new!!",
    "new!",
)
SEARCH_TITLE_BRACKET_PATTERN = re.compile(r"\[(?P<square>[^\]]*)\]|【(?P<corner>[^】]*)】")
SEARCH_TITLE_EDGE_SEPARATOR_PATTERN = re.compile(r"^[\s\-|/・,:]+|[\s\-|/・,:]+$")


@dataclass(frozen=True)
class ResolverInput:
    input_title: str
    amazon_url: str
    asin: str
    status: str
    verification: str
    note: str
    source_id: str = ""
    source_id_known: bool | None = None


def build_ai_prompt(product_names_text: str) -> str:
    source_map = build_source_map(product_names_text)
    source_lines = "\n".join(
        f"{source_id}\t{build_search_title(name)}" for source_id, name in source_map.items()
    )
    return (
        "以下の商品について、Amazon.co.jpの商品URLをTSV形式で返してください。\n"
        "説明文は付けず、Markdown表にはしないでください。\n"
        "1行目は source_id<TAB>input_title<TAB>amazon_url としてください。\n"
        "各行のsource_idは入力どおりに保持してください。1つの商品に複数候補がある場合は、同じsource_idで複数行を返してください。\n"
        "見つからなければ「不明」としてください。\n"
        "Amazon.co.jpの商品URLだけを返し、amazon.comやamazon.sgなど海外Amazonは返さないでください。\n"
        "URLが不明な場合は推測URLを作らず、商品の順番を維持してください。\n\n"
        "出力形式:\n"
        "source_id\tinput_title\tamazon_url\n\n"
        "商品名:\n\n"
        f"{source_lines}"
    )


def build_source_map(product_names_text: str) -> dict[str, str]:
    return {
        f"R{index:04d}": name
        for index, name in enumerate(_non_empty_lines(product_names_text), 1)
    }


def build_search_title(input_title: str) -> str:
    normalized = unicodedata.normalize("NFKC", input_title or "")
    without_bracketed_promos = SEARCH_TITLE_BRACKET_PATTERN.sub(
        _remove_bracketed_search_title_promo,
        normalized,
    )
    cleaned = _remove_unbracketed_search_title_promos(without_bracketed_promos)
    cleaned = SEARCH_TITLE_EDGE_SEPARATOR_PATTERN.sub("", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or input_title


def build_retry_rows(
    preview_rows: Iterable[dict[str, Any]],
    source_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Build one retry row for each known source_id with only AI-unknown results."""
    rows_by_source_id: dict[str, list[dict[str, Any]]] = {}
    for row in preview_rows:
        source_id = str(row.get("source_id") or "").strip().upper()
        if not SOURCE_ID_PATTERN.fullmatch(source_id):
            continue
        rows_by_source_id.setdefault(source_id, []).append(dict(row))

    retry_rows: list[dict[str, Any]] = []
    for source_id, rows in rows_by_source_id.items():
        if source_map and source_id not in source_map:
            continue
        if any(row.get("source_id_known") is False for row in rows):
            continue
        if any("Unknown source_id" in str(row.get("note") or "") for row in rows):
            continue
        if any(
            not _is_retry_blank(row.get("amazon_url"))
            or not _is_retry_blank(row.get("asin"))
            for row in rows
        ):
            continue
        if not all(_is_ai_unknown_row(row) for row in rows):
            continue

        input_title = (
            source_map[source_id]
            if source_map and source_id in source_map
            else str(rows[0].get("input_title") or "")
        )
        initial_search_title = build_search_title(input_title)
        retry_rows.append(
            {
                "row_id": f"retry-{source_id}",
                "source_id": source_id,
                "input_title": input_title,
                "initial_search_title": initial_search_title,
                "retry_search_title": initial_search_title,
                "selected": True,
            }
        )
    return retry_rows


def build_retry_prompt(rows: Iterable[dict[str, Any]]) -> str:
    source_lines: list[str] = []
    included_source_ids: set[str] = set()
    for row in rows:
        source_id = str(row.get("source_id") or "").strip().upper()
        retry_search_title = str(row.get("retry_search_title") or "").strip()
        if (
            not row.get("selected")
            or not SOURCE_ID_PATTERN.fullmatch(source_id)
            or not retry_search_title
            or source_id in included_source_ids
        ):
            continue
        included_source_ids.add(source_id)
        source_lines.append(f"{source_id}\t{retry_search_title}")

    if not source_lines:
        return ""

    return (
        "以下の商品について、Amazon.co.jpの商品URLをTSV形式で返してください。\n"
        "商品名には誤記やShopee独自の販売文言が含まれる可能性があります。"
        "ブランド名、型番、シリーズ名を優先して検索してください。\n"
        "完全一致がない場合は、同じシリーズ・容量違い・色違い・サイズ違い・セット違い・関連商品でも構いません。\n"
        "推測URLは作らず、見つからなければ「不明」としてください。\n"
        "Amazon.co.jp以外のURLは返さないでください。\n"
        "入力されたすべてのsource_idについて、必ず1行以上返してください。\n"
        "説明文やMarkdown表は付けないでください。1候補を必ず1行にし、各列はタブ文字で区切ってください。\n\n"
        "出力形式:\n"
        "source_id\tinput_title\tamazon_url\n\n"
        "商品名:\n"
        f"{'\n'.join(source_lines)}"
    )


def retry_rows_fingerprint(rows: Iterable[dict[str, Any]]) -> tuple[tuple[str, bool, str], ...]:
    return tuple(
        (
            str(row.get("source_id") or "").strip().upper(),
            bool(row.get("selected")),
            str(row.get("retry_search_title") or "").strip(),
        )
        for row in rows
    )


def summarize_retry_rows(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    materialized = list(rows)
    selected_rows = [row for row in materialized if row.get("selected")]
    return {
        "initial_unknown_products": len(materialized),
        "selected_products": len(selected_rows),
        "deselected_products": len(materialized) - len(selected_rows),
        "missing_retry_search_titles": sum(
            1
            for row in materialized
            if not str(row.get("retry_search_title") or "").strip()
        ),
        "prompt_source_ids": len(
            {
                str(row.get("source_id") or "").strip().upper()
                for row in selected_rows
                if str(row.get("retry_search_title") or "").strip()
            }
        ),
    }


def parse_ai_response(
    response_text: str,
    source_map: dict[str, str] | None = None,
) -> list[ResolverInput]:
    cleaned = clean_ai_response(response_text)
    if not cleaned:
        return []

    parsed_rows: list[ResolverInput] = []
    header_indexes: dict[str, int] | None = None
    fallback_context: tuple[str, str] | None = None
    markdown_header_indexes: dict[str, int] | None = None
    markdown_table_active = False
    for line in cleaned.splitlines():
        if _looks_like_markdown_row(line):
            markdown_cells = _markdown_cells(line)
            if MARKDOWN_SEPARATOR_PATTERN.fullmatch(line.strip()):
                if markdown_header_indexes is not None:
                    header_indexes = markdown_header_indexes
                    markdown_table_active = True
                continue
            detected_markdown_headers = _header_indexes(markdown_cells)
            if not markdown_table_active and detected_markdown_headers is not None:
                markdown_header_indexes = detected_markdown_headers
                continue
            cells = markdown_cells if markdown_table_active else [line.strip()]
        else:
            markdown_header_indexes = None
            if markdown_table_active:
                markdown_table_active = False
                header_indexes = None
            cells = _parse_cells(line)
        if _is_space_separated_header(line):
            header_indexes = None
            fallback_context = None
            continue
        detected_headers = _header_indexes(cells)
        if detected_headers is not None:
            header_indexes = detected_headers
            fallback_context = None
            continue

        fallback_source = _leading_source_id_context(line, cells)
        if fallback_source is not None:
            source_id, ai_title = fallback_source
            fallback_context = (source_id, ai_title)
            inline_candidate = _parse_fallback_source_line(source_id, ai_title)
            if inline_candidate is not None:
                parsed_rows.append(_finalize_candidate_source_id(inline_candidate, source_map))
            else:
                unknown_title = _trailing_unknown_title(ai_title)
                if unknown_title is not None:
                    unknown_row = ResolverInput(
                        unknown_title,
                        "",
                        "",
                        UNKNOWN,
                        NOT_CHECKED,
                        "AI returned unknown",
                        source_id,
                    )
                    parsed_rows.append(_finalize_candidate_source_id(unknown_row, source_map))
                    fallback_context = None
            continue

        if fallback_context is not None:
            context_candidate = _parse_context_url_line(line, fallback_context)
            if context_candidate is not None:
                parsed_rows.append(_finalize_candidate_source_id(context_candidate, source_map))
                continue
            if _find_unknown_value(cells) is not None:
                fallback_context = None

        parsed = _parse_line(line, cells, header_indexes)
        if parsed is not None:
            parsed_rows.append(_finalize_candidate_source_id(parsed, source_map))
            if len(cells) > 1 or _looks_like_markdown_row(line):
                fallback_context = None
    return parsed_rows


def preview_candidates(
    response_text: str,
    source_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(parse_ai_response(response_text, source_map), 1):
        preview_row = _row_to_dict(row)
        preview_row["row_id"] = f"candidate-{index:04d}"
        preview_row["selected"] = bool(row.asin) and row.source_id_known is not False
        preview_row["parse_status"] = "CANDIDATE" if row.asin else "UNKNOWN"
        rows.append(preview_row)
    return rows


def summarize_preview(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
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
        "selected_rows": sum(1 for row in materialized if row.get("selected")),
        "selected_unique_asins": len(
            {
                str(row.get("asin") or "")
                for row in materialized
                if row.get("selected") and row.get("asin")
            }
        ),
        "deselected_rows": sum(1 for row in materialized if not row.get("selected")),
    }


def verify_preview_rows(
    rows: Iterable[dict[str, Any]],
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
                _verified_row(
                    row,
                    FOUND,
                    KEEPA_VERIFIED,
                    row.get("note", ""),
                    products_by_asin.get(asin),
                )
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


def verify_selected_rows(
    rows: Iterable[dict[str, Any]],
    client: KeepaExpansionClient,
) -> list[dict[str, Any]]:
    return verify_preview_rows((row for row in rows if row.get("selected")), client)


def resolve_candidates(
    response_text: str,
    client: KeepaExpansionClient,
) -> list[dict[str, str]]:
    return verify_preview_rows(preview_candidates(response_text), client)


def rows_to_resolver_csv(rows: Iterable[dict[str, Any]]) -> bytes:
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


def _is_space_separated_header(line: str) -> bool:
    return bool(SPACE_HEADER_PATTERN.fullmatch(line.strip()))


def _leading_source_id_context(
    line: str,
    cells: list[str],
) -> tuple[str, str] | None:
    if len(cells) != 1:
        return None
    match = LEADING_SOURCE_ID_PATTERN.match(line.strip())
    if match is None:
        return None
    return match.group(1).upper(), match.group(2).strip()


def _trailing_unknown_title(value: str) -> str | None:
    for unknown_value in sorted(UNKNOWN_VALUES - {""}, key=len, reverse=True):
        match = re.search(
            rf"(?:^|\s){re.escape(unknown_value)}$",
            value.strip(),
            re.IGNORECASE,
        )
        if match is not None:
            return value[: match.start()].strip()
    return None


def _parse_fallback_source_line(source_id: str, ai_title: str) -> ResolverInput | None:
    amazon_url, asin = _extract_amazon_jp_url_and_asin(ai_title)
    if not asin:
        return None
    try:
        normalized_asin = normalize_asin(asin)
    except ValueError:
        return None
    url_match = AMAZON_JP_URL_PATTERN.search(ai_title)
    title_without_url = ai_title[: url_match.start()].strip() if url_match else ai_title
    return ResolverInput(
        title_without_url,
        amazon_url,
        normalized_asin,
        UNKNOWN,
        NOT_CHECKED,
        "Extracted ASIN from Amazon.co.jp URL",
        source_id,
    )


def _parse_context_url_line(
    line: str,
    context: tuple[str, str],
) -> ResolverInput | None:
    stripped = _strip_list_prefix(line).strip()
    if AMAZON_JP_URL_PATTERN.fullmatch(stripped) is None:
        return None
    amazon_url, asin = _extract_amazon_jp_url_and_asin(stripped)
    if not asin:
        return None
    try:
        normalized_asin = normalize_asin(asin)
    except ValueError:
        return None
    source_id, ai_title = context
    return ResolverInput(
        ai_title,
        amazon_url,
        normalized_asin,
        UNKNOWN,
        NOT_CHECKED,
        "Extracted ASIN from Amazon.co.jp URL",
        source_id,
    )


def _parse_line(
    line: str,
    cells: list[str],
    header_indexes: dict[str, int] | None,
) -> ResolverInput | None:
    source_id = _source_id(cells, header_indexes)
    input_title = _input_title(line, cells, header_indexes)
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
            source_id,
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
                source_id,
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
                source_id,
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
            source_id,
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
            source_id,
        )

    if invalid_amazon_url:
        return ResolverInput(
            input_title,
            invalid_amazon_url,
            "",
            UNKNOWN,
            NOT_CHECKED,
            "Invalid ASIN format",
            source_id,
        )

    if amazon_url_without_asin:
        return ResolverInput(
            input_title,
            amazon_url_without_asin,
            "",
            UNKNOWN,
            NOT_CHECKED,
            "No Amazon.co.jp URL or ASIN",
            source_id,
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
        source_id,
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
    return stripped.startswith("|") and stripped.endswith("|")


def _markdown_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|") if cell.strip()]


def _input_title(
    line: str,
    cells: list[str],
    header_indexes: dict[str, int] | None,
) -> str:
    if header_indexes is not None:
        title_index = header_indexes.get("input_title")
        if title_index is not None and title_index < len(cells) and cells[title_index]:
            return _strip_list_prefix(cells[title_index])
    if len(cells) >= 3 and SOURCE_ID_PATTERN.fullmatch(cells[0]):
        return _strip_list_prefix(cells[1])
    if len(cells) >= 2 and cells[0]:
        return _strip_list_prefix(cells[0])
    return _strip_list_prefix(line.strip())


def _source_id(cells: list[str], header_indexes: dict[str, int] | None) -> str:
    if header_indexes is not None:
        source_index = header_indexes.get("source_id")
        if source_index is not None and source_index < len(cells):
            return cells[source_index].strip().upper()
    if cells and SOURCE_ID_PATTERN.fullmatch(cells[0].strip()):
        return cells[0].strip().upper()
    return ""


def _header_indexes(cells: list[str]) -> dict[str, int] | None:
    normalized = [re.sub(r"[\s-]+", "_", cell.strip().casefold()) for cell in cells]
    indexes = {value: index for index, value in enumerate(normalized)}
    if "input_title" in indexes and ({"amazon_url", "url", "asin", "amazon_asin"} & set(indexes)):
        return indexes
    return None


def _apply_source_context(
    row: ResolverInput,
    source_map: dict[str, str] | None,
) -> ResolverInput:
    if not row.source_id:
        return row
    if source_map and row.source_id in source_map:
        return ResolverInput(
            source_map[row.source_id],
            row.amazon_url,
            row.asin,
            row.status,
            row.verification,
            row.note,
            row.source_id,
            True,
        )
    return ResolverInput(
        row.input_title,
        row.amazon_url,
        row.asin,
        row.status,
        row.verification,
        _join_notes(row.note, "Unknown source_id"),
        row.source_id,
        False,
    )


def _finalize_candidate_source_id(
    row: ResolverInput,
    source_map: dict[str, str] | None,
) -> ResolverInput:
    normalized = _apply_source_context(row, source_map)
    if normalized.source_id or not normalized.asin:
        return normalized

    match = LEADING_SOURCE_ID_PATTERN.match(normalized.input_title.strip())
    if match is None:
        return normalized

    recovered = ResolverInput(
        match.group(2).strip(),
        normalized.amazon_url,
        normalized.asin,
        normalized.status,
        normalized.verification,
        normalized.note,
        match.group(1).upper(),
    )
    return _apply_source_context(recovered, source_map)


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


def _unique_asins_from_rows(rows: Iterable[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    unique_asins: list[str] = []
    for row in rows:
        asin = str(row.get("asin") or "")
        if not asin or asin in seen:
            continue
        seen.add(asin)
        unique_asins.append(asin)
    return unique_asins


def _is_ai_unknown_row(row: dict[str, Any]) -> bool:
    return (
        str(row.get("status") or "").strip().upper() == UNKNOWN
        and str(row.get("verification") or "").strip().upper() == NOT_CHECKED
        and str(row.get("note") or "").strip() == "AI returned unknown"
    )


def _is_retry_blank(value: Any) -> bool:
    return str(value or "").strip().casefold() in UNKNOWN_VALUES


def _row_to_dict(row: ResolverInput) -> dict[str, Any]:
    return {
        "source_id": row.source_id,
        "input_title": row.input_title,
        "amazon_url": row.amazon_url,
        "asin": row.asin,
        "status": row.status,
        "verification": row.verification,
        "note": row.note,
    }


def _verified_row(
    row: dict[str, Any],
    status: str,
    verification: str,
    note: str,
    keepa_product: Any | None = None,
) -> dict[str, Any]:
    verified = dict(row)
    verified.update(
        {
            "status": status,
            "verification": verification,
            "note": note,
            "keepa_title": _keepa_display_text(keepa_product, "title"),
            "keepa_brand": _keepa_display_text(keepa_product, "brand"),
        }
    )
    return verified


def _keepa_display_text(product: Any, field: str) -> str:
    if not isinstance(product, dict):
        return ""
    value = product.get(field)
    return "" if value is None else str(value).strip()


def _join_notes(*notes: str) -> str:
    return " ".join(note.strip() for note in notes if note and note.strip())


def _remove_bracketed_search_title_promo(match: re.Match[str]) -> str:
    content = match.group("square") or match.group("corner") or ""
    if content.strip().casefold() in SEARCH_TITLE_REMOVAL_PHRASES:
        return " "
    return match.group(0)


def _remove_unbracketed_search_title_promos(title: str) -> str:
    chunks: list[str] = []
    start = 0
    for bracket_match in SEARCH_TITLE_BRACKET_PATTERN.finditer(title):
        chunks.append(_remove_search_title_phrases(title[start : bracket_match.start()]))
        chunks.append(bracket_match.group(0))
        start = bracket_match.end()
    chunks.append(_remove_search_title_phrases(title[start:]))
    return "".join(chunks)


def _remove_search_title_phrases(value: str) -> str:
    result = value
    for phrase in sorted(SEARCH_TITLE_REMOVAL_PHRASES, key=len, reverse=True):
        pattern = re.compile(
            rf"(?<![0-9A-Z]){re.escape(phrase)}(?![0-9A-Z])",
            re.IGNORECASE,
        )
        result = pattern.sub(" ", result)
    return result


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]
