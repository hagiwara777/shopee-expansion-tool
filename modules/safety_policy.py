"""Owner policy: shared rules plus market data, independent of ASIN origin.

Amazon category nodes are product evidence only. They never assign a Shopee
category, produce SLS ALLOW, or override another Safety result.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re


POLICY_DIR = Path(__file__).resolve().parents[1] / "guardrails" / "policy"
FIELDS = {"title", "text", "ingredients", "category", "brand", "asin"}
CONDITIONS = {"always", "medical", "general", "spray", "mask", "weapon_attachment",
              "food", "laser", "certification", "sample", "used", "food_review", "battery"}
RISKS = {"drug_or_hemp", "medical_or_therapeutic", "regulated_ingredient", "brand_ip",
         "weapon", "weapon_related_toy", "food_restricted", "shipping_restricted",
         "tobacco_or_vape", "alcohol", "license_or_certification_required", "own_penalty_product", "other"}
TEXT_FIELDS = ("description", "features", "shortDescription", "safetyWarning", "itemHighlights")
INGREDIENT_FIELDS = ("ingredients", "activeIngredients", "specialIngredients")


class SafetyPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class PolicyHit:
    rule_id: str
    term: str
    action: str
    risk: str
    field: str
    note: str
    source: str


def load_policy_rules(directory=None):
    """No missing/malformed asset may silently become an empty policy."""
    path = Path(directory) if directory is not None else POLICY_DIR
    try:
        data = json.loads((path / "rules.json").read_text(encoding="utf-8"))
        if set(data) != {"schema", "decision", "rules"} or data["schema"] != "SORA_SAFETY_POLICY_V1":
            raise ValueError
        if data["decision"] != "DEC-0167" or not isinstance(data["rules"], list) or not data["rules"]:
            raise ValueError
        seen = set()
        for rule in data["rules"]:
            if set(rule) != {"id", "markets", "action", "risk", "fields", "terms", "condition", "note", "source"}:
                raise ValueError
            if not isinstance(rule["id"], str) or not rule["id"] or rule["id"] in seen:
                raise ValueError
            seen.add(rule["id"])
            if rule["action"] not in {"BLOCK", "REVIEW"} or rule["risk"] not in RISKS:
                raise ValueError
            if rule["condition"] not in CONDITIONS or rule["source"] not in {"internal_rule", "shopee_policy", "own_penalty_case"}:
                raise ValueError
            for key, allowed in (("fields", FIELDS), ("markets", {"ALL", "SG", "PH", "MY", "TH", "TW"})):
                if (not isinstance(rule[key], list) or not rule[key] or len(set(rule[key])) != len(rule[key])
                        or any(value not in allowed for value in rule[key])):
                    raise ValueError
            if "ALL" in rule["markets"] and rule["markets"] != ["ALL"]:
                raise ValueError
            if (not isinstance(rule["terms"], list) or not rule["terms"]
                    or any(not isinstance(t, str) or not t.strip() or "\n" in t for t in rule["terms"])
                    or len(set(rule["terms"])) != len(rule["terms"])):
                raise ValueError
            if not isinstance(rule["note"], str) or not rule["note"].strip():
                raise ValueError
        return tuple(data["rules"])
    except (OSError, ValueError, KeyError, TypeError):
        raise SafetyPolicyError("共通・国別の保安ルール設定を確認できません。判定を停止しました。") from None


def _values(row, fields):
    for group in fields:
        names = {"title": ("product_title",), "text": TEXT_FIELDS, "ingredients": INGREDIENT_FIELDS,
                 "category": ("category",), "brand": ("brand",), "asin": ("candidate_asin",)}[group]
        for name in names:
            raw = row.get(name)
            if raw is None:
                continue
            if isinstance(raw, str):
                raw = (raw,)
            if not isinstance(raw, (tuple, list)) or any(not isinstance(v, str) for v in raw):
                raise SafetyPolicyError("商品情報の形式を確認できません。判定を停止しました。")
            for value in raw:
                if value.strip():
                    yield group, name, value


def mask_harmless_phrases(value):
    """Suppress only these occurrences, not other positive statements nearby."""
    return re.sub(r"アルコールフリー|ノンアルコール|(?<![a-z0-9])alcohol[- ]free(?![a-z0-9])"
                  r"|(?<![a-z0-9])fake\s+lashes(?![a-z0-9])|つけまつげ", " ", value)


def _condition(rule, value, row, group):
    """Return BLOCK/REVIEW for a match, or None for a bounded exclusion."""
    condition = rule["condition"]
    action = rule["action"]
    if condition == "battery":
        if group != "title" or re.search(r"(?:ケース|ホルダー|用カバー|用替刃|別売|付属しません|not included|holder|case|cover|not supplied)", value):
            return None
        return action
    if condition in {"always", "medical"}:
        return action
    from modules.guardrails import normalize_text
    title = normalize_text(row.get("product_title", ""))
    category = normalize_text(row.get("category", ""))
    context = title + " " + value
    decoration = re.search(r"フィギュア|キーホルダー|キーチェーン|ペンダント|figure|keychain|pendant", context)
    if condition == "general":
        if decoration and rule["risk"] in {"weapon", "weapon_related_toy"}:
            return None  # Dedicated attachment rule decides this ambiguity.
        return action
    if condition == "spray":
        return action if re.search(r"スプレー|エアゾール|エアロゾル|spray|aerosol", context) else None
    if condition == "mask":
        cosmetic = re.search(r"ヘアマスク|シートマスク|フェイスパック|hair mask|sheet mask|face pack|トリートメント", context)
        hair_category = re.search(r"ヘアケア|ヘアトリートメント|フェイスパック|シートマスク", category)
        positive = re.search(r"不織布|立体マスク|防塵|防じん|医療用マスク|サージカル|n95|respirator|surgical|口と鼻|口鼻", context)
        if positive:
            return "BLOCK"
        if cosmetic or hair_category:
            return None
        return "REVIEW"
    if condition == "weapon_attachment":
        if not decoration:
            return None
        attached = re.search(r"(?:剣|刀|銃|武器|ナイフ)(?:の模型)?(?:パーツ)?(?:付き|付属|同梱|型|装備|を持つ)"
                             r"|(?:剣|刀|銃|武器|ナイフ).{0,12}(?:付属|同梱|装備|セット)"
                             r"|(?:with|includes?|equipped with)\s+(?:a\s+)?(?:sword|gun|weapon|knife)"
                             r"|(?:gun|sword)[- ](?:shaped|keychain|pendant)", context)
        return "BLOCK" if attached else "REVIEW"
    if condition in {"food", "food_review"}:
        food_context = re.search(r"食品|フード|飲料|スナック|肉|ジャーキー|ソーセージ|ベーコン|ハム|卵|豆腐|アイスクリーム|乳製品|牛乳|食用油|野生キノコ|粉ミルク|food|snack|jerky|sausage|bacon|dairy|milk|tofu|seafood", context)
        cosmetic = re.search(r"シャンプー|トリートメント|化粧|美容|石鹸|石けん|ソープ|ヘア|shampoo|cosmetic|soap|hair", title)
        if group != "category" and cosmetic and not re.search(r"食品|食用|飲料|snack|food", title):
            return None
        food_category = re.search(r"食品|食品・飲料|food|grocery|飲料", category)
        return action if food_context or food_category else "REVIEW"
    if condition == "laser":
        power = re.search(r"(\d+(?:\.\d+)?)\s*mw", context)
        return ("BLOCK" if float(power[1]) >= 5 else None) if power else "REVIEW"
    if condition == "certification":
        return "BLOCK" if re.search(r"(?:ps|icc).{0,12}(?:なし|無し|未認証|未取得|without|no mark)", context) else "REVIEW"
    if condition == "sample":
        if re.search(r"詰め?替え|つめかえ|つめ替え|詰替|レフィル|リフィル|refill", value) and not re.search(r"試供品|小分け|非売品|量り売り|sample", value):
            return None
        return "REVIEW"
    if condition == "used":
        return action if re.search(r"中古|使用済|used|second[- ]hand", context) else None
    raise SafetyPolicyError("未対応の保安ルール条件です。")


def evaluate_policy(row, marketplace, rules=None):
    # This pure evaluator accepts configured future markets without enabling UI,
    # API credentials, Catalog/Mapper, or other market operation.
    from modules.guardrails import normalize_text, _contains_term, _contains_rule_term, GuardrailRule
    rules = load_policy_rules() if rules is None else rules
    hits = []
    for rule in rules:
        if "ALL" not in rule["markets"] and marketplace not in rule["markets"]:
            continue
        for group, field, raw in _values(row, rule["fields"]):
            value = normalize_text(raw)
            if rule["condition"] == "general":
                value = mask_harmless_phrases(value)
            for term in rule["terms"]:
                normalized = normalize_text(term)
                if group == "category":
                    matched = (normalized == value if ">" in normalized else normalized in [n.strip() for n in value.split(">")])
                elif group in {"brand", "asin"}:
                    matched = value == normalized
                elif rule["condition"] == "medical" or (rule["condition"] == "general" and rule["risk"] == "medical_or_therapeutic"):
                    probe = GuardrailRule(term, normalized, rule["action"], "medical_or_therapeutic",
                                          "title", "contains", rule["source"], rule["note"], "rules.json", 0, "policy")
                    matched = _contains_rule_term(value, probe)
                elif rule["id"] == "COMMON-DRUG":
                    matched = normalized in value if normalized == "hemp" else _contains_term(value, normalized)
                else:
                    # Japanese vitamin prefixes need the same Latin boundary as AHA.
                    matched = bool(re.search(re.escape(normalized) + r"(?![a-z0-9])", value)) if re.search(r"[^a-z0-9 -].*[a-z0-9]$", normalized) else _contains_term(value, normalized)
                if normalized == "ライター":
                    matched = bool(re.search(r"(?<!ハイ)ライター", value))
                if normalized == "マッチ":
                    matched = bool(re.search(r"マッチ(?!ング)", value))
                if not matched:
                    continue
                action = _condition(rule, value, row, group)
                if action:
                    hits.append(PolicyHit(rule["id"], term, action, rule["risk"], field,
                                          rule["note"], rule["source"]))
    return hits
