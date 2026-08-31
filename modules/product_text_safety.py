"""Trusted Product Text Safety Fact transport and SHA-bound sidecar contract."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
from io import StringIO
import json
from typing import Any, Callable, Iterable, Mapping, TYPE_CHECKING

from modules.amazon_data_provider import CANOPY_TEST_PROVIDER, KEEPA_PROVIDER

if TYPE_CHECKING:
    from modules.prelisting_candidate_csv import (
        PrelistingCandidateFileResult,
        PrelistingCandidateRow,
    )


PRODUCT_TEXT_SAFETY_PAYLOAD_VERSION = "PRODUCT_TEXT_SAFETY_PAYLOAD_V1"
PRODUCT_TEXT_SAFETY_SIDECAR_SCHEMA_VERSION = "PRODUCT_TEXT_SAFETY_FACT_V1"
PRELISTING_CANDIDATE_SCHEMA_VERSION = "PRELISTING_CANDIDATE_V1"
CAPTURED = "CAPTURED"
NOT_CAPTURED = "NOT_CAPTURED"
NOT_AVAILABLE = "NOT_AVAILABLE"
PROVIDER_UNSUPPORTED = "PROVIDER_UNSUPPORTED"
PRODUCT_TEXT_SAFETY_CAPTURE_STATUSES = {
    CAPTURED,
    NOT_CAPTURED,
    NOT_AVAILABLE,
    PROVIDER_UNSUPPORTED,
}
PRODUCT_TEXT_SAFETY_SIDECAR_COLUMNS = (
    "schema_version",
    "candidate_schema_version",
    "candidate_sha256",
    "candidate_asin",
    "provider",
    "capture_status",
    "description_json",
    "features_json",
    "shortDescription_json",
    "safetyWarning_json",
    "itemHighlights_json",
    "fetched_at",
)


class ProductTextSafetyError(RuntimeError):
    """Raised when Product Text Safety data cannot be trusted."""


@dataclass(frozen=True)
class ProductTextSafetyFact:
    candidate_asin: str
    provider: str
    capture_status: str
    description: tuple[str, ...]
    features: tuple[str, ...]
    short_description: tuple[str, ...]
    safety_warning: tuple[str, ...]
    item_highlights: tuple[str, ...]
    fetched_at: str


@dataclass(frozen=True)
class ProductTextSafetySidecarResult:
    schema_version: str
    candidate_schema_version: str
    candidate_sha256: str
    rows: tuple[ProductTextSafetyFact, ...]

    @property
    def facts_by_asin(self) -> dict[str, ProductTextSafetyFact]:
        return {fact.candidate_asin: fact for fact in self.rows}


def extract_keepa_product_text_safety_fact(
    product: Any,
    *,
    candidate_asin: str,
    fetched_at: str,
) -> ProductTextSafetyFact:
    """Extract only approved, same-name fields from one existing Keepa response."""

    values = _fact_values_from_mapping_or_object(product)
    capture_status = CAPTURED if any(values.values()) else NOT_AVAILABLE
    return ProductTextSafetyFact(
        candidate_asin=_required_text(candidate_asin, "candidate_asin"),
        provider=KEEPA_PROVIDER,
        capture_status=capture_status,
        fetched_at=_required_text(fetched_at, "fetched_at"),
        **values,
    )


def product_text_safety_fact_from_product_data(
    product: Mapping[str, Any] | None,
    *,
    candidate_asin: str,
    provider: str,
    fetched_at: str = "",
) -> ProductTextSafetyFact:
    """Restore a trusted Fact; an old Keepa cache entry becomes NOT_CAPTURED."""

    normalized_provider = _required_text(provider, "provider")
    if normalized_provider == CANOPY_TEST_PROVIDER:
        return unsupported_product_text_safety_fact(
            candidate_asin=candidate_asin,
            provider=normalized_provider,
            fetched_at=fetched_at,
        )
    if normalized_provider != KEEPA_PROVIDER:
        raise ProductTextSafetyError(
            f"unsupported Product Text Safety provider: {normalized_provider}"
        )

    payload = product if isinstance(product, Mapping) else {}
    marker = payload.get("product_text_safety_payload_version")
    if marker is None:
        return _empty_fact(
            candidate_asin=candidate_asin,
            provider=KEEPA_PROVIDER,
            capture_status=NOT_CAPTURED,
            fetched_at=_text(fetched_at or payload.get("fetched_at")),
        )
    if marker != PRODUCT_TEXT_SAFETY_PAYLOAD_VERSION:
        raise ProductTextSafetyError("unsupported product_text_safety_payload_version")
    capture_status = _required_text(
        payload.get("product_text_safety_capture_status"), "capture_status"
    )
    if capture_status not in {CAPTURED, NOT_AVAILABLE}:
        raise ProductTextSafetyError(
            "Keepa Product Text Safety payload must be CAPTURED or NOT_AVAILABLE"
        )
    fact = ProductTextSafetyFact(
        candidate_asin=_required_text(candidate_asin, "candidate_asin"),
        provider=KEEPA_PROVIDER,
        capture_status=capture_status,
        fetched_at=_text(fetched_at or payload.get("fetched_at")),
        **_fact_values_from_mapping_or_object(payload),
    )
    _validate_fact(fact)
    return fact


def unsupported_product_text_safety_fact(
    *, candidate_asin: str, provider: str, fetched_at: str
) -> ProductTextSafetyFact:
    return _empty_fact(
        candidate_asin=candidate_asin,
        provider=provider,
        capture_status=PROVIDER_UNSUPPORTED,
        fetched_at=fetched_at,
    )


def product_text_safety_fact_to_payload(fact: ProductTextSafetyFact) -> dict[str, Any]:
    _validate_fact(fact)
    return {
        "candidate_asin": fact.candidate_asin,
        "provider": fact.provider,
        "capture_status": fact.capture_status,
        "description": list(fact.description),
        "features": list(fact.features),
        "shortDescription": list(fact.short_description),
        "safetyWarning": list(fact.safety_warning),
        "itemHighlights": list(fact.item_highlights),
        "fetched_at": fact.fetched_at,
    }


def product_text_safety_fact_from_transport(
    payload: Any,
    *,
    candidate_asin: str,
    provider: str,
    fetched_at: str = "",
) -> ProductTextSafetyFact:
    """Read an internal JSON-safe transport payload, with legacy fallback."""

    if payload is None:
        return product_text_safety_fact_from_product_data(
            None,
            candidate_asin=candidate_asin,
            provider=provider,
            fetched_at=fetched_at,
        )
    if not isinstance(payload, Mapping):
        raise ProductTextSafetyError("Product Text Safety transport payload must be an object")
    payload_asin = _required_text(payload.get("candidate_asin"), "candidate_asin")
    if payload_asin != candidate_asin:
        raise ProductTextSafetyError("Product Text Safety transport ASIN mismatch")
    payload_provider = _required_text(payload.get("provider"), "provider")
    if payload_provider != provider:
        raise ProductTextSafetyError("Product Text Safety transport provider mismatch")
    fact = ProductTextSafetyFact(
        candidate_asin=payload_asin,
        provider=payload_provider,
        capture_status=_required_text(payload.get("capture_status"), "capture_status"),
        fetched_at=_text(payload.get("fetched_at") or fetched_at),
        **_fact_values_from_mapping_or_object(payload),
    )
    _validate_fact(fact)
    return fact


def facts_for_candidate_rows(
    candidate_rows: Iterable[PrelistingCandidateRow],
    source_rows: Iterable[Mapping[str, Any]],
    *,
    provider_for_row: Callable[[Mapping[str, Any]], str] | None = None,
) -> tuple[ProductTextSafetyFact, ...]:
    """Pair canonical Candidate rows with source rows without changing Candidate V1."""

    candidates = tuple(candidate_rows)
    source_by_asin: dict[str, Mapping[str, Any]] = {}
    for source in source_rows:
        asin = _text(source.get("candidate_asin") or source.get("asin")).strip().upper()
        if asin and asin not in source_by_asin:
            source_by_asin[asin] = source

    facts: list[ProductTextSafetyFact] = []
    for candidate in candidates:
        source = source_by_asin.get(candidate.candidate_asin)
        if source is None:
            raise ProductTextSafetyError(
                "Candidate ASIN is missing from Product Text Safety source rows"
            )
        if provider_for_row is not None:
            provider = str(provider_for_row(source))
        elif (
            candidate.source_verification == "CANOPY_VERIFIED"
            or candidate.source.startswith("canopy")
        ):
            provider = CANOPY_TEST_PROVIDER
        else:
            provider = KEEPA_PROVIDER
        facts.append(
            product_text_safety_fact_from_transport(
                source.get("product_text_safety_fact"),
                candidate_asin=candidate.candidate_asin,
                provider=provider,
                fetched_at=candidate.fetched_at,
            )
        )
    return tuple(facts)


def rows_to_product_text_safety_sidecar(
    candidate_content: bytes,
    candidate_rows: Iterable[PrelistingCandidateRow],
    facts: Iterable[ProductTextSafetyFact],
) -> bytes:
    """Serialize one exact Candidate-ASIN set bound to the final Candidate bytes."""

    if not isinstance(candidate_content, bytes) or not candidate_content:
        raise ProductTextSafetyError("Candidate CSV bytes are required")
    candidates = tuple(candidate_rows)
    fact_rows = tuple(facts)
    candidate_asins = _unique_candidate_asins(candidates)
    fact_asins = _unique_fact_asins(fact_rows)
    if set(candidate_asins) != set(fact_asins):
        raise ProductTextSafetyError("Candidate and Product Text Safety ASIN sets do not match")
    facts_by_asin = {fact.candidate_asin: fact for fact in fact_rows}
    candidate_sha = hashlib.sha256(candidate_content).hexdigest()

    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=PRODUCT_TEXT_SAFETY_SIDECAR_COLUMNS,
        lineterminator="\n",
    )
    writer.writeheader()
    for asin in candidate_asins:
        fact = facts_by_asin[asin]
        _validate_fact(fact)
        writer.writerow(
            {
                "schema_version": PRODUCT_TEXT_SAFETY_SIDECAR_SCHEMA_VERSION,
                "candidate_schema_version": PRELISTING_CANDIDATE_SCHEMA_VERSION,
                "candidate_sha256": candidate_sha,
                "candidate_asin": fact.candidate_asin,
                "provider": fact.provider,
                "capture_status": fact.capture_status,
                "description_json": _json_tuple(fact.description),
                "features_json": _json_tuple(fact.features),
                "shortDescription_json": _json_tuple(fact.short_description),
                "safetyWarning_json": _json_tuple(fact.safety_warning),
                "itemHighlights_json": _json_tuple(fact.item_highlights),
                "fetched_at": fact.fetched_at,
            }
        )
    return output.getvalue().encode("utf-8-sig")


def parse_product_text_safety_sidecar(
    content: bytes,
    *,
    filename: str,
    candidate_content: bytes,
    candidates: PrelistingCandidateFileResult,
) -> ProductTextSafetySidecarResult:
    """Validate schema, JSON cells, SHA binding, duplicates, and exact ASIN set."""

    if not isinstance(content, bytes):
        raise ProductTextSafetyError(f"{filename}: sidecar content must be bytes")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ProductTextSafetyError(f"{filename}: sidecar must be UTF-8") from exc
    try:
        reader = csv.DictReader(StringIO(text, newline=""), strict=True)
        if tuple(reader.fieldnames or ()) != PRODUCT_TEXT_SAFETY_SIDECAR_COLUMNS:
            raise ProductTextSafetyError(f"{filename}: sidecar header mismatch")
        raw_rows = list(reader)
    except csv.Error as exc:
        raise ProductTextSafetyError(f"{filename}: malformed sidecar CSV") from exc
    if not raw_rows:
        raise ProductTextSafetyError(f"{filename}: sidecar has no data rows")

    expected_sha = hashlib.sha256(candidate_content).hexdigest()
    facts: list[ProductTextSafetyFact] = []
    schema_values: set[str] = set()
    candidate_schema_values: set[str] = set()
    sha_values: set[str] = set()
    for row_number, row in enumerate(raw_rows, 2):
        if None in row:
            raise ProductTextSafetyError(f"{filename} row {row_number}: sidecar column mismatch")
        schema_values.add(_text(row.get("schema_version")))
        candidate_schema_values.add(_text(row.get("candidate_schema_version")))
        sha_values.add(_text(row.get("candidate_sha256")))
        fact = ProductTextSafetyFact(
            candidate_asin=_required_text(row.get("candidate_asin"), "candidate_asin"),
            provider=_required_text(row.get("provider"), "provider"),
            capture_status=_required_text(row.get("capture_status"), "capture_status"),
            description=_parse_json_tuple(row.get("description_json"), "description_json"),
            features=_parse_json_tuple(row.get("features_json"), "features_json"),
            short_description=_parse_json_tuple(
                row.get("shortDescription_json"), "shortDescription_json"
            ),
            safety_warning=_parse_json_tuple(
                row.get("safetyWarning_json"), "safetyWarning_json"
            ),
            item_highlights=_parse_json_tuple(
                row.get("itemHighlights_json"), "itemHighlights_json"
            ),
            fetched_at=_text(row.get("fetched_at")),
        )
        _validate_fact(fact)
        facts.append(fact)

    if schema_values != {PRODUCT_TEXT_SAFETY_SIDECAR_SCHEMA_VERSION}:
        raise ProductTextSafetyError(f"{filename}: unsupported sidecar schema")
    if candidate_schema_values != {PRELISTING_CANDIDATE_SCHEMA_VERSION}:
        raise ProductTextSafetyError(f"{filename}: candidate schema mismatch")
    if sha_values != {expected_sha}:
        raise ProductTextSafetyError(f"{filename}: candidate SHA-256 mismatch")
    candidate_asins = _unique_candidate_asins(candidates.rows)
    fact_asins = _unique_fact_asins(facts)
    if set(candidate_asins) != set(fact_asins):
        raise ProductTextSafetyError(f"{filename}: Candidate ASIN set mismatch")
    return ProductTextSafetySidecarResult(
        schema_version=PRODUCT_TEXT_SAFETY_SIDECAR_SCHEMA_VERSION,
        candidate_schema_version=PRELISTING_CANDIDATE_SCHEMA_VERSION,
        candidate_sha256=expected_sha,
        rows=tuple(facts),
    )


def summarize_capture_statuses(sidecar: ProductTextSafetySidecarResult) -> dict[str, int]:
    summary = {status: 0 for status in sorted(PRODUCT_TEXT_SAFETY_CAPTURE_STATUSES)}
    for fact in sidecar.rows:
        summary[fact.capture_status] += 1
    return summary


def _fact_values_from_mapping_or_object(source: Any) -> dict[str, tuple[str, ...]]:
    return {
        "description": _normalize_text_value(_value(source, "description"), "description"),
        "features": _normalize_text_value(_value(source, "features"), "features"),
        "short_description": _normalize_text_value(
            _value(source, "shortDescription"), "shortDescription"
        ),
        "safety_warning": _normalize_text_value(
            _value(source, "safetyWarning"), "safetyWarning"
        ),
        "item_highlights": _normalize_text_value(
            _value(source, "itemHighlights"), "itemHighlights"
        ),
    }


def _normalize_text_value(value: Any, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, (list, tuple)):
        normalized: list[str] = []
        for item in value:
            if item is None:
                continue
            if not isinstance(item, str):
                raise ProductTextSafetyError(f"{field} contains an unsupported nested value")
            text = item.strip()
            if text:
                normalized.append(text)
        return tuple(normalized)
    raise ProductTextSafetyError(f"{field} has an unsupported value type")


def _empty_fact(
    *, candidate_asin: str, provider: str, capture_status: str, fetched_at: str
) -> ProductTextSafetyFact:
    fact = ProductTextSafetyFact(
        candidate_asin=_required_text(candidate_asin, "candidate_asin"),
        provider=_required_text(provider, "provider"),
        capture_status=capture_status,
        description=(),
        features=(),
        short_description=(),
        safety_warning=(),
        item_highlights=(),
        fetched_at=_text(fetched_at),
    )
    _validate_fact(fact)
    return fact


def _validate_fact(fact: ProductTextSafetyFact) -> None:
    if not isinstance(fact, ProductTextSafetyFact):
        raise ProductTextSafetyError("Product Text Safety Fact type is invalid")
    _required_text(fact.candidate_asin, "candidate_asin")
    provider = _required_text(fact.provider, "provider")
    if provider not in {KEEPA_PROVIDER, CANOPY_TEST_PROVIDER}:
        raise ProductTextSafetyError("unsupported Product Text Safety provider")
    if fact.capture_status not in PRODUCT_TEXT_SAFETY_CAPTURE_STATUSES:
        raise ProductTextSafetyError("unsupported Product Text Safety capture_status")
    values = (
        fact.description,
        fact.features,
        fact.short_description,
        fact.safety_warning,
        fact.item_highlights,
    )
    for field, field_values in zip(
        ("description", "features", "shortDescription", "safetyWarning", "itemHighlights"),
        values,
    ):
        if not isinstance(field_values, tuple) or any(
            not isinstance(value, str) or not value.strip() for value in field_values
        ):
            raise ProductTextSafetyError(f"{field} must be a tuple of non-empty strings")
    has_text = any(values)
    if fact.capture_status == CAPTURED and not has_text:
        raise ProductTextSafetyError("CAPTURED Product Text Safety Fact must contain text")
    if fact.capture_status != CAPTURED and has_text:
        raise ProductTextSafetyError("uncaptured Product Text Safety Fact must be empty")
    if provider == CANOPY_TEST_PROVIDER and fact.capture_status != PROVIDER_UNSUPPORTED:
        raise ProductTextSafetyError(
            "Canopy Product Text Safety Fact must be PROVIDER_UNSUPPORTED"
        )
    if provider == KEEPA_PROVIDER and fact.capture_status == PROVIDER_UNSUPPORTED:
        raise ProductTextSafetyError(
            "Keepa Product Text Safety Fact cannot be PROVIDER_UNSUPPORTED"
        )


def _unique_candidate_asins(rows: Iterable[PrelistingCandidateRow]) -> tuple[str, ...]:
    asins = tuple(row.candidate_asin for row in rows)
    if not asins or len(asins) != len(set(asins)):
        raise ProductTextSafetyError("Candidate ASINs must be non-empty and unique")
    return asins


def _unique_fact_asins(facts: Iterable[ProductTextSafetyFact]) -> tuple[str, ...]:
    asins = tuple(fact.candidate_asin for fact in facts)
    if not asins or len(asins) != len(set(asins)):
        raise ProductTextSafetyError("Product Text Safety sidecar ASINs must be unique")
    return asins


def _json_tuple(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def _parse_json_tuple(value: Any, field: str) -> tuple[str, ...]:
    try:
        parsed = json.loads(_required_text(value, field))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ProductTextSafetyError(f"{field} is malformed JSON") from exc
    if not isinstance(parsed, list):
        raise ProductTextSafetyError(f"{field} must contain a JSON array")
    return _normalize_text_value(parsed, field)


def _value(source: Any, key: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def _required_text(value: Any, field: str) -> str:
    text = _text(value).strip()
    if not text:
        raise ProductTextSafetyError(f"{field} is required")
    return text


def _text(value: Any) -> str:
    return "" if value is None else str(value)
