"""Trusted Ingredient Safety Fact transport and SHA-bound sidecar contract."""

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


INGREDIENT_SAFETY_PAYLOAD_VERSION = "INGREDIENT_SAFETY_PAYLOAD_V1"
INGREDIENT_SAFETY_SIDECAR_SCHEMA_VERSION = "INGREDIENT_SAFETY_FACT_V1"
PRELISTING_CANDIDATE_SCHEMA_VERSION = "PRELISTING_CANDIDATE_V1"
CAPTURED = "CAPTURED"
NOT_CAPTURED = "NOT_CAPTURED"
PROVIDER_UNSUPPORTED = "PROVIDER_UNSUPPORTED"
INGREDIENT_SAFETY_CAPTURE_STATUSES = {
    CAPTURED,
    NOT_CAPTURED,
    PROVIDER_UNSUPPORTED,
}
INGREDIENT_SAFETY_SIDECAR_COLUMNS = (
    "schema_version",
    "candidate_schema_version",
    "candidate_sha256",
    "candidate_asin",
    "provider",
    "capture_status",
    "ingredients_json",
    "activeIngredients_json",
    "specialIngredients_json",
    "fetched_at",
)
_FACT_FIELDS = ("ingredients", "activeIngredients", "specialIngredients")


class IngredientSafetyError(RuntimeError):
    """Raised when Ingredient Safety data cannot be trusted."""


@dataclass(frozen=True)
class IngredientSafetyFact:
    candidate_asin: str
    provider: str
    capture_status: str
    ingredients: tuple[str, ...]
    active_ingredients: tuple[str, ...]
    special_ingredients: tuple[str, ...]
    fetched_at: str


@dataclass(frozen=True)
class IngredientSafetySidecarResult:
    schema_version: str
    candidate_schema_version: str
    candidate_sha256: str
    rows: tuple[IngredientSafetyFact, ...]

    @property
    def facts_by_asin(self) -> dict[str, IngredientSafetyFact]:
        return {fact.candidate_asin: fact for fact in self.rows}


def extract_keepa_ingredient_safety_fact(
    product: Any,
    *,
    candidate_asin: str,
    fetched_at: str,
) -> IngredientSafetyFact:
    """Extract only the three approved fields from one newly fetched Keepa product."""

    return IngredientSafetyFact(
        candidate_asin=_required_text(candidate_asin, "candidate_asin"),
        provider=KEEPA_PROVIDER,
        capture_status=CAPTURED,
        ingredients=_normalize_ingredient_value(_value(product, "ingredients"), "ingredients"),
        active_ingredients=_normalize_ingredient_value(
            _value(product, "activeIngredients"), "activeIngredients"
        ),
        special_ingredients=_normalize_ingredient_value(
            _value(product, "specialIngredients"), "specialIngredients"
        ),
        fetched_at=_required_text(fetched_at, "fetched_at"),
    )


def ingredient_safety_fact_from_product_data(
    product: Mapping[str, Any] | None,
    *,
    candidate_asin: str,
    provider: str,
    fetched_at: str = "",
) -> IngredientSafetyFact:
    """Restore a trusted Fact; an old Keepa cache entry becomes NOT_CAPTURED."""

    normalized_provider = _required_text(provider, "provider")
    if normalized_provider == CANOPY_TEST_PROVIDER:
        return unsupported_ingredient_safety_fact(
            candidate_asin=candidate_asin,
            provider=normalized_provider,
            fetched_at=fetched_at,
        )
    if normalized_provider != KEEPA_PROVIDER:
        raise IngredientSafetyError(f"unsupported Ingredient Safety provider: {normalized_provider}")

    payload = product if isinstance(product, Mapping) else {}
    marker = payload.get("ingredient_safety_payload_version")
    if marker is None:
        return IngredientSafetyFact(
            candidate_asin=_required_text(candidate_asin, "candidate_asin"),
            provider=KEEPA_PROVIDER,
            capture_status=NOT_CAPTURED,
            ingredients=(),
            active_ingredients=(),
            special_ingredients=(),
            fetched_at=_text(fetched_at or payload.get("fetched_at")),
        )
    if marker != INGREDIENT_SAFETY_PAYLOAD_VERSION:
        raise IngredientSafetyError("unsupported ingredient_safety_payload_version")
    capture_status = _required_text(
        payload.get("ingredient_safety_capture_status"), "capture_status"
    )
    if capture_status != CAPTURED:
        raise IngredientSafetyError("Keepa Ingredient Safety payload must be CAPTURED")
    return IngredientSafetyFact(
        candidate_asin=_required_text(candidate_asin, "candidate_asin"),
        provider=KEEPA_PROVIDER,
        capture_status=CAPTURED,
        ingredients=_normalize_ingredient_value(payload.get("ingredients"), "ingredients"),
        active_ingredients=_normalize_ingredient_value(
            payload.get("activeIngredients"), "activeIngredients"
        ),
        special_ingredients=_normalize_ingredient_value(
            payload.get("specialIngredients"), "specialIngredients"
        ),
        fetched_at=_text(fetched_at or payload.get("fetched_at")),
    )


def unsupported_ingredient_safety_fact(
    *, candidate_asin: str, provider: str, fetched_at: str
) -> IngredientSafetyFact:
    return IngredientSafetyFact(
        candidate_asin=_required_text(candidate_asin, "candidate_asin"),
        provider=_required_text(provider, "provider"),
        capture_status=PROVIDER_UNSUPPORTED,
        ingredients=(),
        active_ingredients=(),
        special_ingredients=(),
        fetched_at=_text(fetched_at),
    )


def ingredient_safety_fact_to_payload(fact: IngredientSafetyFact) -> dict[str, Any]:
    _validate_fact(fact)
    return {
        "candidate_asin": fact.candidate_asin,
        "provider": fact.provider,
        "capture_status": fact.capture_status,
        "ingredients": list(fact.ingredients),
        "activeIngredients": list(fact.active_ingredients),
        "specialIngredients": list(fact.special_ingredients),
        "fetched_at": fact.fetched_at,
    }


def ingredient_safety_fact_from_transport(
    payload: Any,
    *,
    candidate_asin: str,
    provider: str,
    fetched_at: str = "",
) -> IngredientSafetyFact:
    """Read an internal JSON-safe transport payload, with legacy fallback."""

    if payload is None:
        return ingredient_safety_fact_from_product_data(
            None,
            candidate_asin=candidate_asin,
            provider=provider,
            fetched_at=fetched_at,
        )
    if not isinstance(payload, Mapping):
        raise IngredientSafetyError("Ingredient Safety transport payload must be an object")
    payload_asin = _required_text(payload.get("candidate_asin"), "candidate_asin")
    if payload_asin != candidate_asin:
        raise IngredientSafetyError("Ingredient Safety transport ASIN mismatch")
    payload_provider = _required_text(payload.get("provider"), "provider")
    if payload_provider != provider:
        raise IngredientSafetyError("Ingredient Safety transport provider mismatch")
    capture_status = _required_text(payload.get("capture_status"), "capture_status")
    fact = IngredientSafetyFact(
        candidate_asin=payload_asin,
        provider=payload_provider,
        capture_status=capture_status,
        ingredients=_normalize_ingredient_value(payload.get("ingredients"), "ingredients"),
        active_ingredients=_normalize_ingredient_value(
            payload.get("activeIngredients"), "activeIngredients"
        ),
        special_ingredients=_normalize_ingredient_value(
            payload.get("specialIngredients"), "specialIngredients"
        ),
        fetched_at=_text(payload.get("fetched_at") or fetched_at),
    )
    _validate_fact(fact)
    return fact


def facts_for_candidate_rows(
    candidate_rows: Iterable[PrelistingCandidateRow],
    source_rows: Iterable[Mapping[str, Any]],
    *,
    provider_for_row: Callable[[Mapping[str, Any]], str] | None = None,
) -> tuple[IngredientSafetyFact, ...]:
    """Pair canonical Candidate rows with source rows without changing Candidate V1."""

    candidates = tuple(candidate_rows)
    sources = tuple(source_rows)
    source_by_asin: dict[str, Mapping[str, Any]] = {}
    for source in sources:
        asin = _text(source.get("candidate_asin") or source.get("asin")).strip().upper()
        if asin and asin not in source_by_asin:
            source_by_asin[asin] = source

    facts: list[IngredientSafetyFact] = []
    for candidate in candidates:
        source = source_by_asin.get(candidate.candidate_asin)
        if source is None:
            raise IngredientSafetyError("Candidate ASIN is missing from Ingredient Safety source rows")
        if provider_for_row is not None:
            provider = str(provider_for_row(source))
        elif candidate.source_verification == "CANOPY_VERIFIED" or candidate.source.startswith("canopy"):
            provider = CANOPY_TEST_PROVIDER
        else:
            provider = KEEPA_PROVIDER
        facts.append(
            ingredient_safety_fact_from_transport(
                source.get("ingredient_safety_fact"),
                candidate_asin=candidate.candidate_asin,
                provider=provider,
                fetched_at=candidate.fetched_at,
            )
        )
    return tuple(facts)


def rows_to_ingredient_safety_sidecar(
    candidate_content: bytes,
    candidate_rows: Iterable[PrelistingCandidateRow],
    facts: Iterable[IngredientSafetyFact],
) -> bytes:
    """Serialize one exact Candidate-ASIN set bound to the final Candidate bytes."""

    if not isinstance(candidate_content, bytes) or not candidate_content:
        raise IngredientSafetyError("Candidate CSV bytes are required")
    candidates = tuple(candidate_rows)
    fact_rows = tuple(facts)
    candidate_asins = _unique_candidate_asins(candidates)
    fact_asins = _unique_fact_asins(fact_rows)
    if set(candidate_asins) != set(fact_asins):
        raise IngredientSafetyError("Candidate and Ingredient Safety ASIN sets do not match")
    facts_by_asin = {fact.candidate_asin: fact for fact in fact_rows}
    candidate_sha = hashlib.sha256(candidate_content).hexdigest()

    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=INGREDIENT_SAFETY_SIDECAR_COLUMNS,
        lineterminator="\n",
    )
    writer.writeheader()
    for asin in candidate_asins:
        fact = facts_by_asin[asin]
        _validate_fact(fact)
        writer.writerow(
            {
                "schema_version": INGREDIENT_SAFETY_SIDECAR_SCHEMA_VERSION,
                "candidate_schema_version": PRELISTING_CANDIDATE_SCHEMA_VERSION,
                "candidate_sha256": candidate_sha,
                "candidate_asin": fact.candidate_asin,
                "provider": fact.provider,
                "capture_status": fact.capture_status,
                "ingredients_json": _json_tuple(fact.ingredients),
                "activeIngredients_json": _json_tuple(fact.active_ingredients),
                "specialIngredients_json": _json_tuple(fact.special_ingredients),
                "fetched_at": fact.fetched_at,
            }
        )
    return output.getvalue().encode("utf-8-sig")


def parse_ingredient_safety_sidecar(
    content: bytes,
    *,
    filename: str,
    candidate_content: bytes,
    candidates: PrelistingCandidateFileResult,
) -> IngredientSafetySidecarResult:
    """Validate schema, JSON cells, SHA binding, duplicates, and exact ASIN set."""

    if not isinstance(content, bytes):
        raise IngredientSafetyError(f"{filename}: sidecar content must be bytes")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IngredientSafetyError(f"{filename}: sidecar must be UTF-8") from exc
    try:
        reader = csv.DictReader(StringIO(text, newline=""), strict=True)
        if tuple(reader.fieldnames or ()) != INGREDIENT_SAFETY_SIDECAR_COLUMNS:
            raise IngredientSafetyError(f"{filename}: sidecar header mismatch")
        raw_rows = list(reader)
    except csv.Error as exc:
        raise IngredientSafetyError(f"{filename}: malformed sidecar CSV") from exc
    if not raw_rows:
        raise IngredientSafetyError(f"{filename}: sidecar has no data rows")

    expected_sha = hashlib.sha256(candidate_content).hexdigest()
    facts: list[IngredientSafetyFact] = []
    schema_values: set[str] = set()
    candidate_schema_values: set[str] = set()
    sha_values: set[str] = set()
    for row_number, row in enumerate(raw_rows, 2):
        if None in row:
            raise IngredientSafetyError(f"{filename} row {row_number}: sidecar column mismatch")
        schema_values.add(_text(row.get("schema_version")))
        candidate_schema_values.add(_text(row.get("candidate_schema_version")))
        sha_values.add(_text(row.get("candidate_sha256")))
        fact = IngredientSafetyFact(
            candidate_asin=_required_text(row.get("candidate_asin"), "candidate_asin"),
            provider=_required_text(row.get("provider"), "provider"),
            capture_status=_required_text(row.get("capture_status"), "capture_status"),
            ingredients=_parse_json_tuple(row.get("ingredients_json"), "ingredients_json"),
            active_ingredients=_parse_json_tuple(
                row.get("activeIngredients_json"), "activeIngredients_json"
            ),
            special_ingredients=_parse_json_tuple(
                row.get("specialIngredients_json"), "specialIngredients_json"
            ),
            fetched_at=_text(row.get("fetched_at")),
        )
        _validate_fact(fact)
        facts.append(fact)

    if schema_values != {INGREDIENT_SAFETY_SIDECAR_SCHEMA_VERSION}:
        raise IngredientSafetyError(f"{filename}: unsupported sidecar schema")
    if candidate_schema_values != {PRELISTING_CANDIDATE_SCHEMA_VERSION}:
        raise IngredientSafetyError(f"{filename}: candidate schema mismatch")
    if sha_values != {expected_sha}:
        raise IngredientSafetyError(f"{filename}: candidate SHA-256 mismatch")
    candidate_asins = _unique_candidate_asins(candidates.rows)
    fact_asins = _unique_fact_asins(facts)
    if set(candidate_asins) != set(fact_asins):
        raise IngredientSafetyError(f"{filename}: Candidate ASIN set mismatch")
    return IngredientSafetySidecarResult(
        schema_version=INGREDIENT_SAFETY_SIDECAR_SCHEMA_VERSION,
        candidate_schema_version=PRELISTING_CANDIDATE_SCHEMA_VERSION,
        candidate_sha256=expected_sha,
        rows=tuple(facts),
    )


def summarize_capture_statuses(
    sidecar: IngredientSafetySidecarResult,
) -> dict[str, int]:
    summary = {status: 0 for status in sorted(INGREDIENT_SAFETY_CAPTURE_STATUSES)}
    for fact in sidecar.rows:
        summary[fact.capture_status] += 1
    return summary


def _normalize_ingredient_value(value: Any, field: str) -> tuple[str, ...]:
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
                raise IngredientSafetyError(f"{field} contains an unsupported nested value")
            text = item.strip()
            if text:
                normalized.append(text)
        return tuple(normalized)
    raise IngredientSafetyError(f"{field} has an unsupported value type")


def _validate_fact(fact: IngredientSafetyFact) -> None:
    if not isinstance(fact, IngredientSafetyFact):
        raise IngredientSafetyError("Ingredient Safety Fact type is invalid")
    _required_text(fact.candidate_asin, "candidate_asin")
    provider = _required_text(fact.provider, "provider")
    if provider not in {KEEPA_PROVIDER, CANOPY_TEST_PROVIDER}:
        raise IngredientSafetyError("unsupported Ingredient Safety provider")
    if fact.capture_status not in INGREDIENT_SAFETY_CAPTURE_STATUSES:
        raise IngredientSafetyError("unsupported Ingredient Safety capture_status")
    for field, values in (
        ("ingredients", fact.ingredients),
        ("activeIngredients", fact.active_ingredients),
        ("specialIngredients", fact.special_ingredients),
    ):
        if not isinstance(values, tuple) or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise IngredientSafetyError(f"{field} must be a tuple of non-empty strings")
    if fact.capture_status != CAPTURED and any(
        (fact.ingredients, fact.active_ingredients, fact.special_ingredients)
    ):
        raise IngredientSafetyError("uncaptured Ingredient Safety Fact must be empty")
    if provider == CANOPY_TEST_PROVIDER and fact.capture_status != PROVIDER_UNSUPPORTED:
        raise IngredientSafetyError("Canopy Ingredient Safety Fact must be PROVIDER_UNSUPPORTED")
    if provider == KEEPA_PROVIDER and fact.capture_status == PROVIDER_UNSUPPORTED:
        raise IngredientSafetyError("Keepa Ingredient Safety Fact cannot be PROVIDER_UNSUPPORTED")


def _unique_candidate_asins(rows: Iterable[PrelistingCandidateRow]) -> tuple[str, ...]:
    asins = tuple(row.candidate_asin for row in rows)
    if not asins or len(asins) != len(set(asins)):
        raise IngredientSafetyError("Candidate ASINs must be non-empty and unique")
    return asins


def _unique_fact_asins(facts: Iterable[IngredientSafetyFact]) -> tuple[str, ...]:
    asins = tuple(fact.candidate_asin for fact in facts)
    if not asins or len(asins) != len(set(asins)):
        raise IngredientSafetyError("Ingredient Safety sidecar ASINs must be unique")
    return asins


def _json_tuple(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def _parse_json_tuple(value: Any, field: str) -> tuple[str, ...]:
    try:
        parsed = json.loads(_required_text(value, field))
    except (json.JSONDecodeError, TypeError) as exc:
        raise IngredientSafetyError(f"{field} is malformed JSON") from exc
    if not isinstance(parsed, list):
        raise IngredientSafetyError(f"{field} must contain a JSON array")
    return _normalize_ingredient_value(parsed, field)


def _value(source: Any, key: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def _required_text(value: Any, field: str) -> str:
    text = _text(value).strip()
    if not text:
        raise IngredientSafetyError(f"{field} is required")
    return text


def _text(value: Any) -> str:
    return "" if value is None else str(value)
