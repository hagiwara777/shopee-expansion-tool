"""Pure input-validation helpers for the pre-listing gate UI.

This module deliberately has no Streamlit dependency and does not evaluate
guardrails, write files, or perform external I/O.  It only prepares safe,
deterministic input metadata for the Phase 4A-1 screen.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from collections.abc import Iterable, MutableMapping
import unicodedata

from modules.listing_inventory_parser import ListingInventoryFileResult
from modules.prelisting_gate import PrelistingGateResult


PRELISTING_GATE_RESULT_STATE_KEYS = (
    "prelisting_gate_result",
    "prelisting_gate_exports",
    "prelisting_gate_fingerprint",
)
PRELISTING_GATE_PREVIEW_COLUMNS = (
    "candidate_asin",
    "product_title",
    "brand",
    "category",
    "guardrail_status",
    "existing_listing_status",
    "metadata_status",
    "final_eligibility",
    "reason_codes",
    "existing_evidence_count",
)
_PRELISTING_GATE_FINAL_ELIGIBILITIES = {"ELIGIBLE", "REVIEW", "EXCLUDE"}
_PRELISTING_GATE_DOWNLOAD_SOURCE_TYPES = {
    "EXPANSION": "expansion",
    "RESOLVER": "resolver",
}

_SAFE_ERROR_SUMMARIES = {
    "candidate": (
        "候補CSVを解析できません。\n"
        "出品前保安ゲート用の固定15列CSVか、schema versionと候補行を確認してください。"
    ),
    "inventory": (
        "既出品CSVを解析できません。\n"
        "必須ヘッダー、空ファイル、Parent SKU／SKUのASIN形式を確認してください。"
    ),
    "configuration": (
        "入力条件が揃っていません。\n"
        "全ショップ数、アップロード数、ファイル名、shop_labelを確認してください。"
    ),
    "gate": (
        "出品前チェックを完了できませんでした。\n"
        "対象国、全ショップ数、ファイル名、shop_label、Guardrail辞書を確認してください。"
    ),
    "export": (
        "判定結果CSVを作成できませんでした。\n"
        "判定結果の整合性を確認してください。"
    ),
    "unexpected": (
        "出品前チェックを完了できませんでした。\n"
        "アプリを再起動し、入力内容を確認してから再実行してください。"
    ),
}


@dataclass(frozen=True)
class ShopLabelValidationResult:
    """Validation result that keeps display labels separate from identities."""

    display_labels: tuple[str, ...]
    normalized_labels: tuple[str, ...]
    identity_labels: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class InventoryFileValidationResult:
    """Duplicate-file validation result for uploaded inventory CSVs."""

    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class PrelistingGatePreflightSummary:
    """Non-sensitive aggregate values shown before gate evaluation."""

    expected_shop_count: int
    uploaded_file_count: int
    parsed_file_count: int
    existing_listing_row_count: int
    unique_existing_asin_count: int
    evidence_count: int


def content_sha256(content: bytes) -> str:
    """Return the SHA-256 digest for uploaded bytes without persisting them."""

    return hashlib.sha256(content).hexdigest()


def normalize_shop_label(label: object) -> str:
    """Return the NFKC- and trim-normalized display representation."""

    if label is None:
        return ""
    return unicodedata.normalize("NFKC", str(label)).strip()


def validate_shop_labels(labels: Iterable[object]) -> ShopLabelValidationResult:
    """Reject blank and normalized duplicate shop labels.

    The original display label is retained for the inventory parser.  Only its
    normalized, case-folded identity is used for duplicate detection.
    """

    display_labels = tuple("" if label is None else str(label) for label in labels)
    normalized_labels = tuple(normalize_shop_label(label) for label in display_labels)
    identity_labels = tuple(label.casefold() for label in normalized_labels)

    has_blank = any(not label for label in normalized_labels)
    nonempty_identities = [label for label in identity_labels if label]
    has_duplicate = len(set(nonempty_identities)) != len(nonempty_identities)

    errors: list[str] = []
    if has_blank:
        errors.append("shop_labelが空欄です。")
    if has_duplicate:
        errors.append("shop_labelが重複しています。")

    return ShopLabelValidationResult(
        display_labels=display_labels,
        normalized_labels=normalized_labels,
        identity_labels=identity_labels,
        errors=tuple(errors),
    )


def validate_inventory_file_duplicates(
    files: Iterable[tuple[str, bytes]],
) -> InventoryFileValidationResult:
    """Reject duplicate normalized filenames and duplicate byte content."""

    file_items = tuple(files)
    normalized_names = [normalize_shop_label(filename).casefold() for filename, _ in file_items]
    content_hashes = [content_sha256(content) for _, content in file_items]

    errors: list[str] = []
    if len(set(normalized_names)) != len(normalized_names):
        errors.append("既出品CSVのファイル名が重複しています。")
    if len(set(content_hashes)) != len(content_hashes):
        errors.append("既出品CSVの内容が重複しています。")
    return InventoryFileValidationResult(errors=tuple(errors))


def shop_label_widget_key(filename: str, content: bytes) -> str:
    """Create a deterministic widget key from both filename and byte content."""

    payload = {
        "filename": str(filename),
        "content_sha256": content_sha256(content),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return f"prelisting_gate_shop_label_{hashlib.sha256(encoded).hexdigest()}"


def build_prelisting_gate_fingerprint(
    *,
    marketplace: str,
    expected_shop_count: int,
    candidate_filename: str | None,
    candidate_content: bytes | None,
    inventory_files: Iterable[tuple[str, bytes, object]],
) -> str:
    """Build a deterministic, non-reversible fingerprint of current inputs."""

    if type(expected_shop_count) is not int:
        raise TypeError("expected_shop_count must be an int")

    candidate = None
    if candidate_filename is not None or candidate_content is not None:
        if candidate_filename is None or candidate_content is None:
            raise ValueError("candidate filename and content must be provided together")
        candidate = {
            "filename": str(candidate_filename),
            "content_sha256": content_sha256(candidate_content),
        }

    inventories = [
        {
            "filename": str(filename),
            "content_sha256": content_sha256(content),
            "shop_label": normalize_shop_label(shop_label),
        }
        for filename, content, shop_label in inventory_files
    ]
    payload = {
        "marketplace": str(marketplace),
        "expected_shop_count": expected_shop_count,
        "candidate": candidate,
        "inventories": inventories,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def clear_prelisting_gate_result(state: MutableMapping[str, object]) -> None:
    """Remove only prior pre-listing-gate result state."""

    for key in PRELISTING_GATE_RESULT_STATE_KEYS:
        state.pop(key, None)


def safe_prelisting_gate_error_summary(stage: str) -> str:
    """Return a fixed message that never exposes source CSV values."""

    try:
        return _SAFE_ERROR_SUMMARIES[stage]
    except KeyError as exc:
        raise ValueError(f"unknown pre-listing gate error stage: {stage}") from exc


def prelisting_gate_download_source_type(source_type: str) -> str:
    """Return the fixed filename component for a formal candidate source type."""

    try:
        return _PRELISTING_GATE_DOWNLOAD_SOURCE_TYPES[source_type]
    except KeyError as exc:
        raise ValueError("unsupported pre-listing gate source_type") from exc


def build_prelisting_gate_preview_rows(
    result: PrelistingGateResult,
    *,
    final_eligibility: str,
    limit: int = 100,
) -> tuple[dict[str, str | int], ...]:
    """Return at most 100 ordered, display-safe rows for one eligibility tab."""

    if not isinstance(result, PrelistingGateResult):
        raise TypeError("result must be a PrelistingGateResult")
    if final_eligibility not in _PRELISTING_GATE_FINAL_ELIGIBILITIES:
        raise ValueError("final_eligibility is not supported")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an int from 1 through 100")

    preview_rows: list[dict[str, str | int]] = []
    for row in result.rows:
        if row.final_eligibility != final_eligibility:
            continue
        preview_rows.append(
            {
                "candidate_asin": row.candidate.candidate_asin,
                "product_title": row.candidate.product_title,
                "brand": row.candidate.brand,
                "category": row.candidate.category,
                "guardrail_status": row.guardrail_status,
                "existing_listing_status": row.existing_listing_status,
                "metadata_status": row.metadata_status,
                "final_eligibility": row.final_eligibility,
                "reason_codes": "|".join(row.reason_codes),
                "existing_evidence_count": len(row.existing_evidence),
            }
        )
        if len(preview_rows) == limit:
            break
    return tuple(preview_rows)


def summarize_prelisting_inventory(
    results: Iterable[ListingInventoryFileResult],
    *,
    expected_shop_count: int,
    uploaded_file_count: int,
) -> PrelistingGatePreflightSummary:
    """Aggregate parsed inventory results without candidate matching or judgment."""

    parsed_results = tuple(results)
    evidence_records = tuple(
        evidence
        for result in parsed_results
        for evidence in result.evidence_records
    )
    return PrelistingGatePreflightSummary(
        expected_shop_count=expected_shop_count,
        uploaded_file_count=uploaded_file_count,
        parsed_file_count=len(parsed_results),
        existing_listing_row_count=sum(result.data_row_count for result in parsed_results),
        unique_existing_asin_count=len({evidence.asin for evidence in evidence_records}),
        evidence_count=len(evidence_records),
    )
