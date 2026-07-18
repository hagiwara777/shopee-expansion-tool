from __future__ import annotations

import csv
from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Any, Iterable
import unicodedata


GUARDRAIL_COLUMNS = [
    "guardrail_status",
    "guardrail_risk_category",
    "guardrail_matched_terms",
    "guardrail_source",
    "guardrail_note",
]

REQUIRED_COLUMNS = {
    "term",
    "action",
    "risk_category",
    "match_field",
    "match_type",
    "source_type",
    "note",
    "enabled",
}
ALLOWED_ACTIONS = {"BLOCK", "REVIEW"}
ALLOWED_RISK_CATEGORIES = {
    "brand_ip",
    "weapon",
    "weapon_related_toy",
    "drug_or_hemp",
    "regulated_ingredient",
    "medical_or_therapeutic",
    "pesticide_or_hazardous",
    "tobacco_or_vape",
    "alcohol",
    "food_restricted",
    "community_report",
    "own_penalty_product",
    "brand_medical_risk",
    "controlled_goods_unverified",
    "license_or_certification_required",
    "shipping_restricted",
    "other",
}
ALLOWED_MATCH_FIELDS = {"asin", "brand", "title", "category", "all"}
ALLOWED_MATCH_TYPES = {"exact", "contains"}
ALLOWED_SOURCE_TYPES = {
    "shopee_brand_list",
    "shopee_policy",
    "community_report",
    "internal_rule",
    "own_penalty_case",
}
STATUS_PRIORITY = {"SAFE": 0, "REVIEW": 1, "BLOCK": 2}


class GuardrailDictionaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class GuardrailRule:
    term: str
    normalized_term: str
    action: str
    risk_category: str
    match_field: str
    match_type: str
    source_type: str
    note: str
    file_name: str
    row_number: int
    dictionary_type: str


@dataclass(frozen=True)
class GuardrailDictionaries:
    brand_rules: list[GuardrailRule]
    keyword_rules: list[GuardrailRule]


@dataclass(frozen=True)
class GuardrailMatch:
    rule: GuardrailRule


def apply_guardrails(
    rows: Iterable[dict[str, Any]],
    dictionary_dir: str | Path | None = None,
) -> list[dict[str, str]]:
    dictionaries = load_guardrail_dictionaries(dictionary_dir)
    guarded_rows: list[dict[str, str]] = []

    for row in rows:
        matches = _find_matches(row, dictionaries)
        guarded_rows.append(_apply_matches_to_row(row, matches))

    return guarded_rows


def summarize_guardrails(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "SAFE": 0,
        "REVIEW": 0,
        "BLOCK": 0,
        "total": 0,
        "safe_csv_count": 0,
        "audit_csv_count": 0,
    }

    for row in rows:
        status = str(row.get("guardrail_status") or "").strip().upper()
        if status not in {"SAFE", "REVIEW", "BLOCK"}:
            raise ValueError(f"不正なguardrail_statusです: {status or '空欄'}")
        summary[status] += 1
        summary["total"] += 1

    summary["safe_csv_count"] = summary["SAFE"]
    summary["audit_csv_count"] = summary["total"]
    return summary


def filter_safe_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("guardrail_status") or "").strip().upper() == "SAFE"
    ]


def load_guardrail_dictionaries(
    dictionary_dir: str | Path | None = None,
) -> GuardrailDictionaries:
    base_dir = Path(dictionary_dir) if dictionary_dir is not None else _default_dictionary_dir()
    brand_path = base_dir / "prohibited_brands_sg.csv"
    keyword_path = base_dir / "risk_keywords_sg.csv"
    return GuardrailDictionaries(
        brand_rules=_load_rules(brand_path, dictionary_type="brand"),
        keyword_rules=_load_rules(keyword_path, dictionary_type="keyword"),
    )


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""

    text = unicodedata.normalize("NFKC", str(value))
    text = text.strip().lower()
    return re.sub(r"\s+", " ", text)


def normalize_asin(value: Any) -> str:
    """Normalize an ASIN without repairing malformed values."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""

    return unicodedata.normalize("NFKC", str(value)).strip().upper()


def _default_dictionary_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "guardrails"


def _load_rules(path: Path, dictionary_type: str) -> list[GuardrailRule]:
    if not path.exists():
        raise GuardrailDictionaryError(f"{path.name} が見つかりません。guardrails フォルダを確認してください。")

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise GuardrailDictionaryError(f"{path.name} にヘッダー行がありません。")

            fieldnames = {str(field or "").strip() for field in reader.fieldnames}
            missing_columns = REQUIRED_COLUMNS - fieldnames
            if missing_columns:
                missing = ", ".join(sorted(missing_columns))
                raise GuardrailDictionaryError(f"{path.name} の必須列が不足しています: {missing}")

            rules: list[GuardrailRule] = []
            for row_number, raw_row in enumerate(reader, start=2):
                row = _normalize_csv_row(raw_row)
                if _is_blank_row(row):
                    continue
                rule = _parse_rule(path.name, row_number, row, dictionary_type)
                if row["enabled"].strip().upper() == "TRUE":
                    rules.append(rule)
            return rules
    except UnicodeDecodeError as exc:
        raise GuardrailDictionaryError(
            f"{path.name} をUTF-8として読み込めません。UTF-8またはUTF-8 BOMで保存してください。"
        ) from exc
    except csv.Error as exc:
        raise GuardrailDictionaryError(f"{path.name} のCSV形式を読み込めません: {exc}") from exc


def _normalize_csv_row(raw_row: dict[str, Any]) -> dict[str, str]:
    return {
        str(key or "").strip(): "" if value is None else str(value).strip()
        for key, value in raw_row.items()
        if key is not None
    }


def _is_blank_row(row: dict[str, str]) -> bool:
    return all(not str(value or "").strip() for value in row.values())


def _parse_rule(
    file_name: str,
    row_number: int,
    row: dict[str, str],
    dictionary_type: str,
) -> GuardrailRule:
    enabled = _require_choice(
        file_name,
        row_number,
        "enabled",
        row.get("enabled", ""),
        {"TRUE", "FALSE"},
        normalize_upper=True,
    )
    action = _require_choice(
        file_name,
        row_number,
        "action",
        row.get("action", ""),
        ALLOWED_ACTIONS,
        normalize_upper=True,
    )
    risk_category = _require_choice(
        file_name,
        row_number,
        "risk_category",
        row.get("risk_category", ""),
        ALLOWED_RISK_CATEGORIES,
    )
    match_field = _require_choice(
        file_name,
        row_number,
        "match_field",
        row.get("match_field", ""),
        ALLOWED_MATCH_FIELDS,
    )
    match_type = _require_choice(
        file_name,
        row_number,
        "match_type",
        row.get("match_type", ""),
        ALLOWED_MATCH_TYPES,
    )
    source_type = _require_choice(
        file_name,
        row_number,
        "source_type",
        row.get("source_type", ""),
        ALLOWED_SOURCE_TYPES,
    )
    term = str(row.get("term") or "").strip()
    normalized_term = normalize_text(term)
    if match_field != "asin" and not normalized_term:
        raise GuardrailDictionaryError(f"{file_name} {row_number}行目: term が空です。")

    if dictionary_type == "brand":
        if match_field != "brand":
            raise GuardrailDictionaryError(
                f"{file_name} {row_number}行目: ブランド辞書の match_field は brand のみ許可します。"
            )
        if match_type != "exact":
            raise GuardrailDictionaryError(
                f"{file_name} {row_number}行目: ブランド辞書の match_type は exact のみ許可します。"
            )

    if match_field == "asin":
        if match_type != "exact":
            raise GuardrailDictionaryError(
                f"{file_name} {row_number}行目: ASINルールの match_type は exact のみ許可します。"
            )
        normalized_term = normalize_asin(term)
        if re.fullmatch(r"[A-Z0-9]{10}", normalized_term) is None:
            raise GuardrailDictionaryError(
                f"{file_name} {row_number}行目: ASINルールの term は正規化後に10文字の英数字にしてください。"
            )

    return GuardrailRule(
        term=term,
        normalized_term=normalized_term,
        action=action,
        risk_category=risk_category,
        match_field=match_field,
        match_type=match_type,
        source_type=source_type,
        note=str(row.get("note") or "").strip(),
        file_name=file_name,
        row_number=row_number,
        dictionary_type=dictionary_type,
    )


def _require_choice(
    file_name: str,
    row_number: int,
    column: str,
    value: str,
    allowed_values: set[str],
    normalize_upper: bool = False,
) -> str:
    raw_value = str(value or "").strip()
    parsed_value = raw_value.upper() if normalize_upper else normalize_text(raw_value)
    if not raw_value or parsed_value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        current = raw_value if raw_value else "空欄"
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: {column} は {allowed} のいずれかにしてください。現在値: {current}"
        )
    return parsed_value


def _find_matches(
    row: dict[str, Any],
    dictionaries: GuardrailDictionaries,
) -> list[GuardrailMatch]:
    target_values = {
        "asin": normalize_asin(row.get("candidate_asin")),
        "brand": normalize_text(row.get("brand")),
        "title": normalize_text(row.get("product_title")),
        "category": normalize_text(row.get("category")),
    }
    matches: list[GuardrailMatch] = []

    for rule in dictionaries.brand_rules:
        if _rule_matches(rule, target_values):
            matches.append(GuardrailMatch(rule=rule))

    for rule in dictionaries.keyword_rules:
        if _rule_matches(rule, target_values):
            matches.append(GuardrailMatch(rule=rule))

    return matches


def _rule_matches(rule: GuardrailRule, target_values: dict[str, str]) -> bool:
    fields = ("title", "brand", "category") if rule.match_field == "all" else (rule.match_field,)
    for field in fields:
        target = target_values.get(field, "")
        if not target:
            continue
        if rule.match_type == "exact" and target == rule.normalized_term:
            return True
        if rule.match_type == "contains" and _contains_term(target, rule.normalized_term):
            return True
    return False


def _contains_term(target: str, term: str) -> bool:
    if not term:
        return False
    if _is_ascii_token_phrase(term):
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
        return re.search(pattern, target) is not None
    return term in target


def _is_ascii_token_phrase(term: str) -> bool:
    return re.fullmatch(r"[a-z0-9]+(?: [a-z0-9]+)*", term) is not None


def _apply_matches_to_row(
    row: dict[str, Any],
    matches: list[GuardrailMatch],
) -> dict[str, str]:
    guarded_row = {str(key): "" if value is None else str(value) for key, value in row.items()}

    if not matches:
        guarded_row.update(
            {
                "guardrail_status": "SAFE",
                "guardrail_risk_category": "",
                "guardrail_matched_terms": "",
                "guardrail_source": "",
                "guardrail_note": "No guardrail dictionary match. SAFE is not a safety guarantee.",
            }
        )
        return guarded_row

    final_status = max(
        (match.rule.action for match in matches),
        key=lambda status: STATUS_PRIORITY[status],
    )
    guarded_row.update(
        {
            "guardrail_status": final_status,
            "guardrail_risk_category": _join_unique(match.rule.risk_category for match in matches),
            "guardrail_matched_terms": _join_unique(match.rule.term for match in matches),
            "guardrail_source": _join_unique(match.rule.source_type for match in matches),
            "guardrail_note": _join_unique(_match_note(match) for match in matches),
        }
    )
    return guarded_row


def _match_note(match: GuardrailMatch) -> str:
    prefix = "Brand matched" if match.rule.dictionary_type == "brand" else "Keyword matched"
    note = f"{prefix}: {match.rule.term}"
    if match.rule.note:
        note = f"{note} ({match.rule.note})"
    return note


def _join_unique(values: Iterable[str]) -> str:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique_values.append(text)
    return "|".join(unique_values)
