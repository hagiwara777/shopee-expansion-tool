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
MARKETPLACE_DICTIONARY_FILES = {
    "SG": ("prohibited_brands_sg.csv", "risk_keywords_sg.csv"),
    "PH": ("prohibited_brands_ph.csv", "risk_keywords_ph.csv"),
}
V2_RULESET_FILE = "deterministic_block_rules_v2.csv"
V2_RULESET_SCHEMA_VERSION = "GUARDRAIL_RULE_V2_V2"
V2_REQUIRED_COLUMNS = {
    "schema_version",
    "rule_id",
    "scope",
    "fact_field",
    "operator",
    "canonical_term",
    "value",
    "action",
    "risk_category",
    "source_type",
    "decision_ref",
    "evidence_ref",
    "note",
}
V2_ALLOWED_SCOPES = {"COMMON_BLOCK", "PH_BLOCK"}


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


@dataclass(frozen=True)
class DeterministicBlockRuleV2:
    schema_version: str
    rule_id: str
    scope: str
    fact_field: str
    operator: str
    canonical_term: str
    normalized_canonical_term: str
    value: str
    normalized_value: str
    action: str
    risk_category: str
    source_type: str
    decision_ref: str
    evidence_ref: str
    note: str
    file_name: str
    row_number: int


@dataclass(frozen=True)
class DeterministicBlockMatchV2:
    rule: DeterministicBlockRuleV2
    actual_fact_field: str
    matched_value: str


def apply_guardrails(
    rows: Iterable[dict[str, Any]],
    dictionary_dir: str | Path | None = None,
    *,
    marketplace: str = "SG",
) -> list[dict[str, str]]:
    normalized_marketplace = _normalize_marketplace(marketplace)
    dictionaries = load_guardrail_dictionaries(
        dictionary_dir,
        marketplace=normalized_marketplace,
    )
    v2_rules = (
        load_deterministic_block_rules_v2(dictionary_dir)
        if normalized_marketplace == "PH"
        else []
    )
    guarded_rows: list[dict[str, str]] = []

    for row in rows:
        matches = _find_matches(row, dictionaries)
        v1_row = _apply_matches_to_row(row, matches)
        v2_matches = evaluate_deterministic_blocks_v2(
            row,
            v2_rules,
            marketplace=normalized_marketplace,
        )
        guarded_rows.append(_apply_v2_matches_to_row(v1_row, v2_matches))

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
    *,
    marketplace: str = "SG",
) -> GuardrailDictionaries:
    base_dir = Path(dictionary_dir) if dictionary_dir is not None else _default_dictionary_dir()
    normalized_marketplace = _normalize_marketplace(marketplace)
    brand_file, keyword_file = MARKETPLACE_DICTIONARY_FILES[normalized_marketplace]
    brand_path = base_dir / brand_file
    keyword_path = base_dir / keyword_file
    return GuardrailDictionaries(
        brand_rules=_load_rules(brand_path, dictionary_type="brand"),
        keyword_rules=_load_rules(keyword_path, dictionary_type="keyword"),
    )


def load_deterministic_block_rules_v2(
    dictionary_dir: str | Path | None = None,
) -> list[DeterministicBlockRuleV2]:
    base_dir = Path(dictionary_dir) if dictionary_dir is not None else _default_dictionary_dir()
    path = base_dir / V2_RULESET_FILE
    if not path.exists():
        raise GuardrailDictionaryError(
            f"{path.name} が見つかりません。V2 rulesetを確認してください。"
        )

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file, strict=True)
            if reader.fieldnames is None:
                raise GuardrailDictionaryError(f"{path.name} にヘッダー行がありません。")

            fieldnames = {str(field or "").strip() for field in reader.fieldnames}
            missing_columns = V2_REQUIRED_COLUMNS - fieldnames
            if missing_columns:
                missing = ", ".join(sorted(missing_columns))
                raise GuardrailDictionaryError(
                    f"{path.name} のV2必須列が不足しています: {missing}"
                )
            unsupported_columns = fieldnames - V2_REQUIRED_COLUMNS
            if unsupported_columns:
                unsupported = ", ".join(sorted(unsupported_columns))
                raise GuardrailDictionaryError(
                    f"{path.name} に未対応のV2列があります: {unsupported}"
                )

            rules: list[DeterministicBlockRuleV2] = []
            rule_ids: set[str] = set()
            semantic_keys: set[tuple[str, str, str, str, str]] = set()
            for row_number, raw_row in enumerate(reader, start=2):
                if None in raw_row:
                    raise GuardrailDictionaryError(
                        f"{path.name} {row_number}行目: V2列数がヘッダーと一致しません。"
                    )
                row = _normalize_csv_row(raw_row)
                if _is_blank_row(row):
                    continue
                rule = _parse_v2_rule(path.name, row_number, row)
                if rule.rule_id in rule_ids:
                    raise GuardrailDictionaryError(
                        f"{path.name} {row_number}行目: duplicate rule_idです: {rule.rule_id}"
                    )
                semantic_key = (
                    rule.scope,
                    rule.fact_field,
                    rule.operator,
                    rule.normalized_value,
                    rule.action,
                )
                if semantic_key in semantic_keys:
                    raise GuardrailDictionaryError(
                        f"{path.name} {row_number}行目: semantic duplicate ruleです: {rule.value}"
                    )
                rule_ids.add(rule.rule_id)
                semantic_keys.add(semantic_key)
                rules.append(rule)

            if not rules:
                raise GuardrailDictionaryError(f"{path.name} にactive V2 ruleがありません。")
            return rules
    except GuardrailDictionaryError:
        raise
    except UnicodeDecodeError as exc:
        raise GuardrailDictionaryError(
            f"{path.name} をUTF-8として読み込めません。UTF-8またはUTF-8 BOMで保存してください。"
        ) from exc
    except csv.Error as exc:
        raise GuardrailDictionaryError(f"{path.name} のV2 CSV形式を読み込めません: {exc}") from exc
    except OSError as exc:
        raise GuardrailDictionaryError(f"{path.name} のV2 rulesetを読み込めません。") from exc


def evaluate_deterministic_blocks_v2(
    row: dict[str, Any],
    rules: Iterable[DeterministicBlockRuleV2],
    *,
    marketplace: str,
) -> list[DeterministicBlockMatchV2]:
    """Evaluate already-validated deterministic BLOCK rules without I/O."""
    normalized_marketplace = _normalize_marketplace(marketplace)
    if normalized_marketplace != "PH":
        return []

    applicable_scopes = {"COMMON_BLOCK", "PH_BLOCK"}
    matches: list[DeterministicBlockMatchV2] = []
    for rule in rules:
        if rule.scope not in applicable_scopes:
            continue
        if rule.fact_field == "brand" and rule.operator == "exact":
            brand = normalize_v2_text(row.get("brand"))
            if brand and brand == rule.normalized_value:
                matches.append(
                    DeterministicBlockMatchV2(
                        rule=rule,
                        actual_fact_field="brand",
                        matched_value=str(row.get("brand") or "").strip(),
                    )
                )
            continue
        if rule.fact_field == "ingredient_safety" and rule.operator == "contains_term":
            for actual_field, value in _ingredient_safety_values(row):
                if _contains_v2_term(normalize_v2_text(value), rule.normalized_value):
                    matches.append(
                        DeterministicBlockMatchV2(
                            rule=rule,
                            actual_fact_field=actual_field,
                            matched_value=rule.value,
                        )
                    )
                    break
            continue
        if rule.fact_field == "product_text" and rule.operator == "contains":
            for actual_field, value in _product_text_values(row):
                if rule.normalized_value in normalize_v2_text(value):
                    matches.append(
                        DeterministicBlockMatchV2(
                            rule=rule,
                            actual_fact_field=actual_field,
                            matched_value=rule.value,
                        )
                    )
                    break
            continue
        raise GuardrailDictionaryError(
            f"unsupported V2 evaluator pair: {rule.fact_field}/{rule.operator}"
        )
    return matches


def _normalize_marketplace(marketplace: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(marketplace)).strip().upper()
    if normalized not in MARKETPLACE_DICTIONARY_FILES:
        supported = ", ".join(sorted(MARKETPLACE_DICTIONARY_FILES))
        raise GuardrailDictionaryError(
            f"未対応の marketplace です: {normalized or '空欄'}。対応市場: {supported}"
        )
    return normalized


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""

    text = unicodedata.normalize("NFKC", str(value))
    text = text.strip().lower()
    return re.sub(r"\s+", " ", text)


def normalize_v2_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""

    text = unicodedata.normalize("NFKC", str(value))
    text = text.strip().casefold()
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


def _parse_v2_rule(
    file_name: str,
    row_number: int,
    row: dict[str, str],
) -> DeterministicBlockRuleV2:
    schema_version = str(row.get("schema_version") or "").strip()
    if schema_version != V2_RULESET_SCHEMA_VERSION:
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: schema_versionが不正です: "
            f"{schema_version or '空欄'}"
        )

    rule_id = str(row.get("rule_id") or "").strip()
    if not rule_id:
        raise GuardrailDictionaryError(f"{file_name} {row_number}行目: rule_idが空です。")
    if re.fullmatch(r"[A-Z0-9][A-Z0-9._-]*", rule_id) is None:
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: rule_idはmachine-readable形式にしてください。"
        )

    scope = unicodedata.normalize("NFKC", str(row.get("scope") or "")).strip().upper()
    if scope not in V2_ALLOWED_SCOPES:
        allowed = ", ".join(sorted(V2_ALLOWED_SCOPES))
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: unsupported scopeです。"
            f"許可値: {allowed}、現在値: {scope or '空欄'}"
        )

    fact_field = normalize_v2_text(row.get("fact_field"))
    if fact_field not in {"brand", "ingredient_safety", "product_text"}:
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: unsupported fact_fieldです: "
            f"{fact_field or '空欄'}"
        )
    operator = normalize_v2_text(row.get("operator"))
    allowed_pair = (fact_field, operator) in {
        ("brand", "exact"),
        ("ingredient_safety", "contains_term"),
        ("product_text", "contains"),
    }
    if not allowed_pair:
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: unsupported operatorです: "
            f"{operator or '空欄'}"
        )
    action = unicodedata.normalize("NFKC", str(row.get("action") or "")).strip().upper()
    if action != "BLOCK":
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: unsupported actionです: "
            f"{action or '空欄'}"
        )

    value = str(row.get("value") or "").strip()
    normalized_value = normalize_v2_text(value)
    if not normalized_value:
        raise GuardrailDictionaryError(f"{file_name} {row_number}行目: valueが空です。")

    canonical_term = str(row.get("canonical_term") or "").strip()
    normalized_canonical_term = normalize_v2_text(canonical_term)
    if not normalized_canonical_term:
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: canonical_termが空です。"
        )

    risk_category = normalize_v2_text(row.get("risk_category"))
    if risk_category not in ALLOWED_RISK_CATEGORIES:
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: risk_categoryが不正です。"
        )
    source_type = normalize_v2_text(row.get("source_type"))
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: source_typeが不正です。"
        )
    decision_ref = str(row.get("decision_ref") or "").strip()
    if re.fullmatch(r"DEC-\d{4}", decision_ref) is None:
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: decision_refが不正です。"
        )
    evidence_ref = str(row.get("evidence_ref") or "").strip()
    if not evidence_ref:
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: evidence_refが空です。"
        )
    if fact_field == "brand" and (
        risk_category != "community_report"
        or source_type != "community_report"
        or decision_ref != "DEC-0030"
        or evidence_ref != "OWNER_SOURCE_COMMUNITY_NG_LIST"
    ):
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: Brand exact canonical evidenceの"
            "risk_category/source_type/decision_ref/evidence_refが不正です。"
        )
    if fact_field == "ingredient_safety" and risk_category != "regulated_ingredient":
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: Ingredient Safety ruleの"
            "risk_categoryはregulated_ingredientにしてください。"
        )
    if fact_field == "product_text" and (
        normalized_canonical_term != "hemp"
        or normalized_value != "hemp"
        or risk_category != "drug_or_hemp"
        or source_type != "internal_rule"
        or decision_ref != "DEC-0050"
        or evidence_ref != "OWNER_APPROVED_PH_HEMP_BOUNDARY"
    ):
        raise GuardrailDictionaryError(
            f"{file_name} {row_number}行目: Product Text hemp ruleの"
            "canonical evidenceが不正です。"
        )
    note = str(row.get("note") or "").strip()
    if not note:
        raise GuardrailDictionaryError(f"{file_name} {row_number}行目: noteが空です。")

    return DeterministicBlockRuleV2(
        schema_version=schema_version,
        rule_id=rule_id,
        scope=scope,
        fact_field=fact_field,
        operator=operator,
        canonical_term=canonical_term,
        normalized_canonical_term=normalized_canonical_term,
        value=value,
        normalized_value=normalized_value,
        action=action,
        risk_category=risk_category,
        source_type=source_type,
        decision_ref=decision_ref,
        evidence_ref=evidence_ref,
        note=note,
        file_name=file_name,
        row_number=row_number,
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


def _contains_v2_term(target: str, term: str) -> bool:
    if not term:
        return False
    if re.search(r"[a-z0-9]", term):
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
        return re.search(pattern, target) is not None
    return term in target


def _is_ascii_token_phrase(term: str) -> bool:
    return re.fullmatch(r"[a-z0-9]+(?: [a-z0-9]+)*", term) is not None


def _ingredient_safety_values(row: dict[str, Any]) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    title = row.get("product_title")
    if title is not None and not isinstance(title, str):
        raise GuardrailDictionaryError("product_title Ingredient Safety Fact must be a string")
    if isinstance(title, str) and title.strip():
        values.append(("product_title", title))

    for field in ("ingredients", "activeIngredients", "specialIngredients"):
        raw_value = row.get(field)
        if raw_value is None:
            continue
        if isinstance(raw_value, str):
            if raw_value.strip():
                values.append((field, raw_value))
            continue
        if not isinstance(raw_value, (list, tuple)):
            raise GuardrailDictionaryError(f"{field} Ingredient Safety Fact is malformed")
        for item in raw_value:
            if not isinstance(item, str):
                raise GuardrailDictionaryError(f"{field} Ingredient Safety Fact is malformed")
            if item.strip():
                values.append((field, item))
    return values


def _product_text_values(row: dict[str, Any]) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    for field in (
        "product_title",
        "description",
        "features",
        "shortDescription",
        "safetyWarning",
        "itemHighlights",
    ):
        raw_value = row.get(field)
        if raw_value is None:
            continue
        if isinstance(raw_value, str):
            if raw_value.strip():
                values.append((field, raw_value))
            continue
        if not isinstance(raw_value, (list, tuple)):
            raise GuardrailDictionaryError(f"{field} Product Text Safety Fact is malformed")
        for item in raw_value:
            if not isinstance(item, str):
                raise GuardrailDictionaryError(
                    f"{field} Product Text Safety Fact is malformed"
                )
            if item.strip():
                values.append((field, item))
    return values


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


def _apply_v2_matches_to_row(
    v1_row: dict[str, str],
    matches: list[DeterministicBlockMatchV2],
) -> dict[str, str]:
    if not matches:
        return v1_row

    guarded_row = dict(v1_row)
    v1_status = guarded_row.get("guardrail_status", "")
    if v1_status == "SAFE":
        risk_values: Iterable[str] = (match.rule.risk_category for match in matches)
        term_values: Iterable[str] = (match.rule.canonical_term for match in matches)
        source_values: Iterable[str] = (match.rule.source_type for match in matches)
        note_values: Iterable[str] = (_v2_match_note(match) for match in matches)
    else:
        risk_values = (
            guarded_row.get("guardrail_risk_category", ""),
            *(match.rule.risk_category for match in matches),
        )
        term_values = (
            guarded_row.get("guardrail_matched_terms", ""),
            *(match.rule.canonical_term for match in matches),
        )
        source_values = (
            guarded_row.get("guardrail_source", ""),
            *(match.rule.source_type for match in matches),
        )
        note_values = (
            guarded_row.get("guardrail_note", ""),
            *(_v2_match_note(match) for match in matches),
        )

    guarded_row.update(
        {
            "guardrail_status": "BLOCK",
            "guardrail_risk_category": _join_unique(risk_values),
            "guardrail_matched_terms": _join_unique(term_values),
            "guardrail_source": _join_unique(source_values),
            "guardrail_note": _join_unique(note_values),
        }
    )
    return guarded_row


def _match_note(match: GuardrailMatch) -> str:
    prefix = "Brand matched" if match.rule.dictionary_type == "brand" else "Keyword matched"
    note = f"{prefix}: {match.rule.term}"
    if match.rule.note:
        note = f"{note} ({match.rule.note})"
    return note


def _v2_match_note(match: DeterministicBlockMatchV2) -> str:
    return (
        f"V2 Rule matched: {match.rule.rule_id} "
        f"(canonical_term={match.rule.canonical_term}; "
        f"matched_value={match.rule.value}; "
        f"fact_field={match.actual_fact_field}; "
        f"evidence_ref={match.rule.evidence_ref}; {match.rule.note})"
    )


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
