"""Deterministic import adapter for Shopee PH research CSV files.

This module is deliberately independent from the ASIN Resolver execution flow.
It turns reviewed Shopee research rows into the Resolver's small two-column TSV
contract, while keeping a separate manifest for traceability.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from io import StringIO
import re
from typing import Callable, Iterable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit
import unicodedata

from modules.asin_resolver import build_search_title


SCHEMA_VERSION = "SHOPEE_RESEARCH_CSV_IMPORT_ADAPTER_V0_1"
RESOLVER_TSV_COLUMNS = ("source_id", "input_title")
MANIFEST_COLUMNS = (
    "schema_version",
    "batch_id",
    "source_id",
    "inclusion_status",
    "exclusion_reason",
    "country",
    "location",
    "raw_title",
    "cleaned_title",
    "product_url",
    "normalized_product_url",
    "shop_url",
    "sold",
    "price",
    "search_date",
    "image_url",
    "source_file",
    "source_row_number",
    "duplicate_count",
    "provenance_files",
    "title_cleaning_status",
    "marketplace_validation_status",
)

INCLUDED = "INCLUDED"
DEFERRED = "DEFERRED"
COUNTRY_NOT_PH = "COUNTRY_NOT_PH"
LOCATION_NOT_JAPAN = "LOCATION_NOT_JAPAN"
MARKETPLACE_REVIEW = "MARKETPLACE_REVIEW"
URL_INVALID = "URL_INVALID"
DUPLICATE_SUPERSEDED = "DUPLICATE_SUPERSEDED"
TITLE_EMPTY = "TITLE_EMPTY"
TITLE_REVIEW = "TITLE_REVIEW"
SCHEMA_ERROR = "SCHEMA_ERROR"

_REQUIRED_COLUMNS = ("country", "location", "raw_title", "product_url", "search_date")
_COLUMN_ALIASES: Mapping[str, tuple[str, ...]] = {
    "country": ("country",),
    "location": ("location",),
    "raw_title": ("name",),
    "product_url": ("product url", "product_url", "producturl"),
    "search_date": ("search date", "search_date", "searchdate"),
    "shop_url": ("shop url", "shop_url", "shopurl"),
    "sold": ("sold",),
    "price": ("price",),
    "image_url": ("image url", "image_url", "imageurl"),
}
_PROMOTIONAL_PHRASE_PATTERN = re.compile(
    r"(?i)(?:\bofficial\s+(?:store|shop)\b|\bdirect\s+from\s+japan\b|"
    r"\bship(?:ped)?\s+from\s+japan\b|\bjapan\s+seller\b|"
    r"\bready\s+stock\b|\blocal\s+seller\b|\bfree\s+(?:shipping|delivery)\b|"
    r"\bshipping\s+fee\s+free\b|送料無料)"
)
_EMOJI_PATTERN = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\uFE0F\u200D]"
)
_DECORATION_PATTERN = re.compile(r"([!★☆✦✧~〜＝=＊*＿_｜|])\1{1,}")
_EDGE_SEPARATOR_PATTERN = re.compile(r"^[\s\-|｜/・,:;~〜!★☆]+|[\s\-|｜/・,:;~〜!★☆]+$")
_GENERIC_SOURCE_TERMS = (
    "mercari",
    "suruga-ya",
    "amazon japan",
    "rakuten",
    "yahoo shopping",
    "muji",
    "bic camera",
    "yodobashi camera",
)


@dataclass(frozen=True)
class ResearchCsvInput:
    """One uploaded CSV, represented without Streamlit-specific types."""

    filename: str
    content: bytes


@dataclass(frozen=True)
class ResearchCsvAdapterResult:
    """Rows and exports produced from one deterministic import batch."""

    batch_id: str
    resolver_rows: tuple[dict[str, str], ...]
    manifest_rows: tuple[dict[str, str], ...]
    deferred_rows: tuple[dict[str, str], ...]
    summary: Mapping[str, int]

    def resolver_tsv(self) -> bytes:
        return rows_to_tsv(self.resolver_rows, RESOLVER_TSV_COLUMNS)

    def manifest_csv(self) -> bytes:
        return rows_to_csv(self.manifest_rows, MANIFEST_COLUMNS)

    def deferred_csv(self) -> bytes:
        return rows_to_csv(self.deferred_rows, MANIFEST_COLUMNS)


@dataclass
class _Candidate:
    manifest: dict[str, str]
    file_index: int
    row_index: int
    search_timestamp: float


def import_research_csvs(files: Iterable[ResearchCsvInput]) -> ResearchCsvAdapterResult:
    """Validate, filter, deduplicate, and prepare an uploaded research batch.

    A bad file is isolated as a ``SCHEMA_ERROR`` marker.  It never changes the
    interpretation of otherwise valid files in the same upload.
    """

    uploads = tuple(files)
    batch_id = _batch_id(uploads)
    all_manifests: list[tuple[tuple[int, int], dict[str, str]]] = []
    candidates: list[_Candidate] = []
    total_rows = 0
    ph_japan_rows = 0
    location_not_japan_rows = 0
    schema_error_count = 0

    for file_index, upload in enumerate(uploads):
        parsed = _parse_csv(upload)
        total_rows += len(parsed.rows)
        if parsed.error:
            schema_error_count += 1
            marker = _empty_manifest(batch_id, upload.filename, "")
            marker.update(
                {
                    "inclusion_status": DEFERRED,
                    "exclusion_reason": SCHEMA_ERROR,
                    "title_cleaning_status": "NOT_APPLIED",
                    "marketplace_validation_status": "NOT_APPLIED",
                }
            )
            all_manifests.append(((file_index, -1), marker))
            continue

        for row_index, row in enumerate(parsed.rows):
            source_row_number = str(parsed.row_numbers[row_index])
            manifest = _empty_manifest(batch_id, upload.filename, source_row_number)
            manifest.update(row)
            order = (file_index, row_index)
            all_manifests.append((order, manifest))

            country = _match_value(manifest["country"])
            location = _match_value(manifest["location"])
            if location != "japan":
                location_not_japan_rows += 1
            if country != "ph":
                _defer(manifest, COUNTRY_NOT_PH, "NOT_APPLIED", "NOT_APPLIED")
                continue
            if location != "japan":
                _defer(manifest, LOCATION_NOT_JAPAN, "NOT_APPLIED", "NOT_APPLIED")
                continue

            ph_japan_rows += 1
            normalized_url = normalize_product_url(manifest["product_url"])
            if not normalized_url:
                _defer(manifest, URL_INVALID, "NOT_APPLIED", "INVALID")
                continue
            manifest["normalized_product_url"] = normalized_url
            if _product_host(normalized_url) != "shopee.ph":
                _defer(manifest, MARKETPLACE_REVIEW, "NOT_APPLIED", "NOT_SHOPEE_PH")
                continue

            timestamp = _parse_search_date(manifest["search_date"])
            if timestamp is None:
                _defer(manifest, SCHEMA_ERROR, "NOT_APPLIED", "VALID_SHOPEE_PH")
                schema_error_count += 1
                continue
            candidates.append(_Candidate(manifest, file_index, row_index, timestamp))

    candidates_by_url: dict[str, list[_Candidate]] = {}
    for candidate in candidates:
        candidates_by_url.setdefault(candidate.manifest["normalized_product_url"], []).append(candidate)

    source_ids = assign_source_ids(candidates_by_url)
    resolver_candidates: list[_Candidate] = []
    duplicate_superseded_count = 0
    for normalized_url, group in candidates_by_url.items():
        source_id = source_ids[normalized_url]
        provenance_files = _provenance_files(group)
        winner = min(
            group,
            key=lambda item: (-item.search_timestamp, item.file_index, item.row_index),
        )
        for candidate in group:
            candidate.manifest["source_id"] = source_id
            candidate.manifest["duplicate_count"] = str(len(group))
            candidate.manifest["provenance_files"] = provenance_files
            candidate.manifest["marketplace_validation_status"] = "VALID_SHOPEE_PH"
            if candidate is winner:
                continue
            duplicate_superseded_count += 1
            _defer(candidate.manifest, DUPLICATE_SUPERSEDED, "NOT_APPLIED", "VALID_SHOPEE_PH")

        cleaned_title, cleaning_status = clean_research_title(winner.manifest["raw_title"])
        winner.manifest["cleaned_title"] = cleaned_title
        winner.manifest["title_cleaning_status"] = cleaning_status
        if not cleaned_title:
            _defer(winner.manifest, TITLE_EMPTY, cleaning_status, "VALID_SHOPEE_PH")
        elif cleaning_status == TITLE_REVIEW:
            _defer(winner.manifest, TITLE_REVIEW, cleaning_status, "VALID_SHOPEE_PH")
        else:
            winner.manifest["inclusion_status"] = INCLUDED
            winner.manifest["exclusion_reason"] = ""
            resolver_candidates.append(winner)

    ordered_manifests = tuple(
        manifest for _, manifest in sorted(all_manifests, key=lambda item: item[0])
    )
    deferred_rows = tuple(
        manifest for manifest in ordered_manifests if manifest["inclusion_status"] == DEFERRED
    )
    resolver_rows = tuple(
        {
            "source_id": candidate.manifest["source_id"],
            "input_title": candidate.manifest["cleaned_title"],
        }
        for candidate in sorted(
            resolver_candidates, key=lambda item: (item.file_index, item.row_index)
        )
    )
    summary = {
        "input_file_count": len(uploads),
        "total_rows": total_rows,
        "ph_japan_rows": ph_japan_rows,
        "location_not_japan_rows": location_not_japan_rows,
        "unique_listing_count": len(candidates_by_url),
        "duplicate_superseded_count": duplicate_superseded_count,
        "resolver_ready_count": len(resolver_rows),
        "title_review_count": sum(
            1 for row in deferred_rows if row["exclusion_reason"] == TITLE_REVIEW
        ),
        "url_or_schema_error_count": sum(
            1
            for row in deferred_rows
            if row["exclusion_reason"] in {URL_INVALID, SCHEMA_ERROR}
        ),
        "schema_error_count": schema_error_count,
    }
    return ResearchCsvAdapterResult(
        batch_id=batch_id,
        resolver_rows=resolver_rows,
        manifest_rows=ordered_manifests,
        deferred_rows=deferred_rows,
        summary=summary,
    )


def normalize_product_url(value: str) -> str | None:
    """Return a deterministic HTTP(S) product URL without query or fragment."""

    raw = (value or "").strip()
    if not raw or any(character.isspace() for character in raw):
        return None
    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or not hostname:
        return None
    if parsed.username or parsed.password:
        return None
    host = hostname.casefold()
    if port is not None and not (
        (parsed.scheme.casefold() == "http" and port == 80)
        or (parsed.scheme.casefold() == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    path = parsed.path.rstrip("/")
    if not path:
        return None
    return urlunsplit(("https", host, path, "", ""))


def assign_source_ids(
    candidates_by_url: Mapping[str, Sequence[object]],
    *,
    hash_function: Callable[[bytes], str] | None = None,
) -> dict[str, str]:
    """Assign order-independent ``JPH`` IDs, lengthening colliding prefixes."""

    digest_for = hash_function or (lambda value: hashlib.sha256(value).hexdigest())
    digests = {url: digest_for(url.encode("utf-8")).upper() for url in candidates_by_url}
    lengths = {url: 8 for url in digests}
    while True:
        groups: dict[str, list[str]] = {}
        for url, digest in digests.items():
            groups.setdefault(digest[: lengths[url]], []).append(url)
        collisions = [urls for urls in groups.values() if len(urls) > 1]
        if not collisions:
            break
        for urls in collisions:
            for url in urls:
                if lengths[url] >= len(digests[url]):
                    raise ValueError("SHA-256 collision cannot be resolved")
                lengths[url] += 1
    return {url: f"JPH{digests[url][:lengths[url]]}" for url in sorted(digests)}


def clean_research_title(raw_title: str) -> tuple[str, str]:
    """Clean only known sales wording and retain product-identifying language."""

    raw = raw_title or ""
    if not raw.strip():
        return "", TITLE_EMPTY
    normalized = unicodedata.normalize("NFKC", raw)
    # Reuse Resolver's proven exact-promo handling without changing Resolver behavior.
    cleaned = build_search_title(normalized)
    cleaned = _PROMOTIONAL_PHRASE_PATTERN.sub(" ", cleaned)
    cleaned = _EMOJI_PATTERN.sub(" ", cleaned)
    cleaned = _DECORATION_PATTERN.sub(" ", cleaned)
    cleaned = _EDGE_SEPARATOR_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "", TITLE_EMPTY
    if _looks_like_generic_sourcing_text(cleaned):
        return cleaned, TITLE_REVIEW
    identifier_characters = re.sub(r"[^\w]", "", cleaned, flags=re.UNICODE)
    if len(identifier_characters) < 3:
        return cleaned, TITLE_REVIEW
    return cleaned, "CLEANED" if cleaned != raw else "UNCHANGED"


def rows_to_tsv(rows: Iterable[Mapping[str, str]], columns: Sequence[str]) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(columns),
        delimiter="\t",
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def rows_to_csv(rows: Iterable[Mapping[str, str]], columns: Sequence[str]) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(columns),
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


@dataclass(frozen=True)
class _ParsedCsv:
    rows: tuple[dict[str, str], ...]
    row_numbers: tuple[int, ...]
    error: str = ""


def _parse_csv(upload: ResearchCsvInput) -> _ParsedCsv:
    try:
        text = upload.content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _ParsedCsv((), (), "CSV must be UTF-8 or UTF-8 BOM")
    try:
        reader = csv.DictReader(StringIO(text, newline=""), strict=True)
        raw_rows: list[dict[str | None, str | list[str] | None]] = []
        row_numbers: list[int] = []
        for raw_row in reader:
            raw_rows.append(raw_row)
            row_numbers.append(reader.line_num)
    except (csv.Error, UnicodeError):
        return _ParsedCsv((), (), "CSV could not be parsed")
    header_map = _canonical_header_map(reader.fieldnames)
    if any(column not in header_map for column in _REQUIRED_COLUMNS):
        return _ParsedCsv((), (), "Required column is missing")
    rows = tuple(
        {
            canonical: _field_value(raw_row.get(header))
            for canonical, header in header_map.items()
        }
        for raw_row in raw_rows
    )
    return _ParsedCsv(rows, tuple(row_numbers))


def _canonical_header_map(fieldnames: Sequence[str | None] | None) -> dict[str, str]:
    if not fieldnames:
        return {}
    normalized_headers: dict[str, str] = {}
    for header in fieldnames:
        if header is None:
            continue
        key = _header_key(header)
        if key and key not in normalized_headers:
            normalized_headers[key] = header
    result: dict[str, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        matches = list(
            dict.fromkeys(
                normalized_headers[_header_key(alias)]
                for alias in aliases
                if _header_key(alias) in normalized_headers
            )
        )
        if len(matches) == 1:
            result[canonical] = matches[0]
    return result


def _header_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold().strip()
    return re.sub(r"[\s_-]+", "", normalized)


def _field_value(value: str | list[str] | None) -> str:
    return value if isinstance(value, str) else ""


def _empty_manifest(batch_id: str, filename: str, source_row_number: str) -> dict[str, str]:
    row = {column: "" for column in MANIFEST_COLUMNS}
    row.update(
        {
            "schema_version": SCHEMA_VERSION,
            "batch_id": batch_id,
            "source_file": filename,
            "source_row_number": source_row_number,
            "duplicate_count": "0",
        }
    )
    return row


def _defer(
    manifest: dict[str, str], reason: str, cleaning_status: str, marketplace_status: str
) -> None:
    manifest["inclusion_status"] = DEFERRED
    manifest["exclusion_reason"] = reason
    manifest["title_cleaning_status"] = cleaning_status
    manifest["marketplace_validation_status"] = marketplace_status


def _match_value(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").strip().casefold()


def _product_host(normalized_url: str) -> str:
    return (urlsplit(normalized_url).hostname or "").casefold()


def _parse_search_date(value: str) -> float | None:
    raw = (value or "").strip()
    if not raw:
        return None
    parsed: datetime | None = None
    for parser in (
        lambda: datetime.fromisoformat(raw.replace("Z", "+00:00")),
        lambda: datetime.strptime(raw, "%Y/%m/%d %H:%M:%S"),
        lambda: datetime.strptime(raw, "%Y/%m/%d"),
    ):
        try:
            parsed = parser()
            break
        except ValueError:
            continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _provenance_files(group: Sequence[_Candidate]) -> str:
    seen: set[str] = set()
    filenames: list[str] = []
    for candidate in sorted(group, key=lambda item: (item.file_index, item.row_index)):
        filename = candidate.manifest["source_file"]
        if filename not in seen:
            seen.add(filename)
            filenames.append(filename)
    return " | ".join(filenames)


def _batch_id(uploads: Sequence[ResearchCsvInput]) -> str:
    digest = hashlib.sha256()
    for upload in uploads:
        digest.update(upload.filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(upload.content)
        digest.update(b"\0")
    return f"SRIA{digest.hexdigest()[:12].upper()}"


def _looks_like_generic_sourcing_text(title: str) -> bool:
    normalized = title.casefold()
    matched_terms = sum(term in normalized for term in _GENERIC_SOURCE_TERMS)
    return matched_terms >= 3 or "any stores in japan" in normalized
