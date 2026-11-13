"""Exact brand-field stops and country-scoped title-only review evidence."""
from dataclasses import dataclass, field
from collections.abc import Mapping
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata
from types import MappingProxyType

from modules.match_context import excerpt_at


CONFIG_DIR = Path(__file__).resolve().parents[1] / "guardrails" / "brand_monitoring"
COUNTRY_FILES = {
    "SG": "counterfeit_sg.json", "PH": "counterfeit_ph.json",
    "MY": "counterfeit_my.json", "TH": "counterfeit_th.json", "TW": "counterfeit_tw.json",
}
ALIAS_MARKETS = frozenset({"SG", "PH", "MY", "TH", "TW"})
NO_COUNTRY_LIST_MARKETS = frozenset()


class BrandMonitoringError(ValueError):
    pass


def normalize_brand(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("’", "'")
    # Accent equivalence is for Latin spelling (Bioré/Biore), not Kana dakuten.
    output = []
    latin_base = False
    for char in unicodedata.normalize("NFD", value):
        if unicodedata.combining(char):
            if not latin_base:
                output.append(char)
        else:
            latin_base = unicodedata.name(char, "").startswith("LATIN ")
            output.append(char)
    value = "".join(unicodedata.normalize("NFC", "".join(output)).split())
    value = value.replace("・", "").replace("·", "")
    # Fold glyph variants next to Kana while keeping the long vowel itself:
    # アリエール and アリエル must remain different complete brand names.
    dash = r"[-‐‑‒–—―−]"
    value = re.sub(rf"(?<=[ぁ-ゖァ-ヶー]){dash}|{dash}(?=[ぁ-ゖァ-ヶー])", "ー", value)
    return value


def primary_brand(value: str) -> str:
    return " ".join(re.sub(r"\([^()]*\)", "", normalize_brand(value)).split())


def country_brand_names(value: str, marketplace: str) -> tuple[str, ...]:
    """TW's paired Latin/Chinese official names are two complete identities.

    Spaces within a Latin name stay intact. No child brand or spelling is
    inferred. The ledger uses this same decomposition as the runtime.
    """
    if marketplace == "TW":
        pair = re.fullmatch(r"([A-Za-z][^\u3400-\u9fff]+?)\s+([\u3400-\u9fff].*)", value.strip())
        if pair:
            return tuple(part.strip() for part in pair.groups())
    return (value,)


@dataclass(frozen=True)
class MonitoringBrand:
    term: str
    scope: str
    file_name: str


@dataclass(frozen=True)
class TitleBrandMention:
    brand: MonitoringBrand
    name: str
    context: str


def _title_text(value):
    # Keep word boundaries while reusing the approved spelling equivalences.
    return " ".join(normalize_brand(part) for part in value.split())


def _title_pattern(name):
    outer = re.sub(r"\([^()]*\)", "", unicodedata.normalize("NFKC", name))
    parts = [normalize_brand(part) for part in outer.split() if normalize_brand(part)]
    spelling = "".join(parts)
    body = r"\s*".join(re.escape(part) for part in parts)
    left = r"(?<![a-z0-9])" if spelling[0].isascii() and spelling[0].isalnum() else ""
    right = r"(?![a-z0-9])" if spelling[-1].isascii() and spelling[-1].isalnum() else ""
    return re.compile(left + body + right)


@dataclass(frozen=True)
class BrandMonitoring:
    rules: tuple[MonitoringBrand, ...]
    aliases: Mapping[str, str]
    company_names: frozenset[str] = frozenset()
    ambiguous_names: frozenset[str] = frozenset()
    _rule_keys: tuple[tuple[MonitoringBrand, frozenset[str]], ...] = field(init=False, repr=False)
    _title_rules: tuple = field(init=False, repr=False)

    def __post_init__(self):
        # These official names are constant for the whole candidate batch.
        object.__setattr__(self, "_rule_keys", tuple(
            (rule, frozenset((normalize_brand(rule.term), primary_brand(rule.term))))
            for rule in self.rules))
        title_rules = []
        for rule, keys in self._rule_keys:
            if rule.scope == "COMPANY" or keys & self.company_names:
                continue
            spellings = {primary_brand(rule.term): rule.term}
            spellings.update({alias: alias for alias, canonical in self.aliases.items() if canonical in keys})
            for spelling, raw in spellings.items():
                if not spelling:
                    continue
                ambiguous = (spelling in self.ambiguous_names or
                             bool(re.fullmatch(r"[a-z]{1,3}", spelling)))
                # Compile only plausible hits. Absent names must not evict the
                # shared regex cache during a large product batch.
                title_rules.append((rule, spelling, raw, ambiguous, (primary_brand(rule.term), rule.scope)))
        object.__setattr__(self, "_title_rules", tuple(title_rules))

    def matches(self, value: str) -> tuple[MonitoringBrand, ...]:
        complete = normalize_brand(value)
        # Only the outer, primary brand is eligible. Parent companies or other
        # names inside parentheses must never widen a child brand's identity.
        primary = primary_brand(value)
        keys = {complete, primary} - {""}
        keys |= {self.aliases[key] for key in tuple(keys) if key in self.aliases}
        return tuple(rule for rule, official_keys in self._rule_keys if official_keys & keys)

    def title_matches(self, value: str) -> tuple[TitleBrandMention, ...]:
        text = _title_text(value)
        compact = normalize_brand(value)
        found, seen = [], set()
        for rule, spelling, raw, ambiguous, key in self._title_rules:
            if spelling not in compact or key in seen:
                continue
            for match in _title_pattern(raw).finditer(text):
                if ambiguous:
                    prefix, suffix = text[:match.start()], text[match.end():]
                    if not (re.search(r"(?:ブランド|brand)\s*[:：]\s*$", prefix)
                            or re.match(r"\s*(?:[®™]|ブランド)", suffix)):
                        continue
                found.append(TitleBrandMention(rule, spelling, excerpt_at(text, match.start(), match.end())))
                seen.add(key)
                break
        return tuple(found)


def _read(name: str, text: str) -> dict:
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError
        return data
    except ValueError as exc:
        raise BrandMonitoringError(f"監視ブランド設定を読めません: {name}") from exc


def load_brand_monitoring(
    marketplace: str,
    config_dir: str | Path | None = None,
    *,
    without_country_list: bool = False,
) -> BrandMonitoring:
    """Every configured market reads its own official counterfeit list.

    The explicit no-list option is reserved for future unconfigured markets;
    it cannot disable an existing country's list.
    """
    if marketplace not in COUNTRY_FILES and not (without_country_list and marketplace in NO_COUNTRY_LIST_MARKETS):
        raise BrandMonitoringError("監視ブランド照合の対象市場ではありません。")
    base = Path(config_dir) if config_dir is not None else CONFIG_DIR
    sources = []
    # Read every current file before reuse: missing, malformed, or changed
    # settings must never fall back to a previously valid configuration.
    for name in ("ipr.json", *COUNTRY_FILES.values(), "company.json", "aliases.json", "title_review.json"):
        try:
            sources.append((name, (base / name).read_text(encoding="utf-8")))
        except (OSError, UnicodeError) as exc:
            raise BrandMonitoringError(f"監視ブランド設定を読めません: {name}") from exc
    return _compile_brand_monitoring(marketplace, tuple(sources))


@lru_cache(maxsize=8)
def _compile_brand_monitoring(marketplace: str, sources: tuple[tuple[str, str], ...]) -> BrandMonitoring:
    """Reuse only immutable parsed settings keyed by their entire current text.

    No product facts, decisions, credentials, or file metadata enter this cache.
    """
    texts = dict(sources)
    rules = []
    country_file = COUNTRY_FILES.get(marketplace)
    for filename, scope in (("ipr.json", "ALL"), (country_file, marketplace)):
        if filename is None:
            continue
        data = _read(filename, texts[filename])
        brands = data.get("brands")
        if (data.get("scope") != scope or not isinstance(data.get("source_url"), str)
                or not isinstance(brands, list) or not brands
                or any(not isinstance(v, str) or not v.strip() or "\n" in v or "\r" in v for v in brands)):
            raise BrandMonitoringError(f"監視ブランド設定が不正です: {filename}")
        rules.extend(MonitoringBrand(name, scope, filename) for v in brands
                     for name in country_brand_names(v, scope))
    company = _read("company.json", texts["company.json"])
    if (company.get("scope") != "COMPANY" or company.get("decision") != "DEC-0167"
            or not isinstance(company.get("brands"), list) or not company["brands"]
            or any(not isinstance(b, str) or not b.strip() for b in company["brands"])):
        raise BrandMonitoringError("自社共通禁止ブランド設定が不正です。")
    rules.extend(MonitoringBrand(v, "COMPANY", "company.json") for v in company["brands"])
    raw_aliases = _read("aliases.json", texts["aliases.json"]).get("aliases")
    if not isinstance(raw_aliases, list):
        raise BrandMonitoringError("監視ブランドの別表記設定が不正です。")
    known = {normalize_brand(rule.term) for rule in rules}
    official_pairs = []
    if raw_aliases:
        # Shared aliases may target a brand active only in the other country.
        # Check references against existing official files, without applying
        # that country's rules to the selected market.
        for filename in set(COUNTRY_FILES.values()) - {country_file}:
            other = _read(filename, texts[filename]).get("brands")
            if not isinstance(other, list) or any(not isinstance(v, str) for v in other):
                raise BrandMonitoringError(f"監視ブランド設定が不正です: {filename}")
            market = next(m for m, name in COUNTRY_FILES.items() if name == filename)
            known.update(normalize_brand(name) for v in other for name in country_brand_names(v, market))
    # Paired names are the same official brand, so their approved alias does
    # not conflict with a different official brand. Other collisions still fail.
    for value in _read(COUNTRY_FILES["TW"], texts[COUNTRY_FILES["TW"]])["brands"]:
        names = country_brand_names(value, "TW")
        if len(names) == 2:
            official_pairs.append({normalize_brand(n) for n in names})
    aliases = {}
    seen_aliases = set()
    for item in raw_aliases:
        if (not isinstance(item, dict) or not {"alias", "canonical"} <= set(item)
                or set(item) - {"alias", "canonical", "markets"}
                or any(not isinstance(item.get(k), str) or not item[k].strip() for k in ("alias", "canonical"))):
            raise BrandMonitoringError("監視ブランドの別表記設定が不正です。")
        markets = item.get("markets")
        if markets is not None and (
                not isinstance(markets, list) or not markets
                or any(not isinstance(m, str) or m not in ALIAS_MARKETS for m in markets)
                or len(set(markets)) != len(markets)):
            raise BrandMonitoringError("監視ブランドの別表記の対象市場が不正です。")
        key, canonical = normalize_brand(item["alias"]), normalize_brand(item["canonical"])
        if not key or key in seen_aliases or key == canonical:
            raise BrandMonitoringError("監視ブランドの別表記が重複しています。")
        seen_aliases.add(key)
        if canonical not in known:
            raise BrandMonitoringError("監視ブランドの別表記の参照先が公式設定にありません。")
        if key in known and key != canonical and not any({key, canonical} <= pair for pair in official_pairs):
            raise BrandMonitoringError("監視ブランドの別表記が別の公式ブランドと競合しています。")
        if markets is None or marketplace in markets:
            aliases[key] = canonical
    if marketplace == "TW":
        for value in _read(country_file, texts[country_file])["brands"]:
            names = country_brand_names(value, "TW")
            if len(names) == 2:
                aliases[normalize_brand(value)] = normalize_brand(names[0])
    title_config = _read("title_review.json", texts["title_review.json"])
    if (set(title_config) != {"schema", "company_names", "ambiguous_names"}
            or title_config.get("schema") != "SORA_TITLE_BRAND_REVIEW_V1"):
        raise BrandMonitoringError("商品名の監視ブランド確認設定が不正です。")
    names = {}
    for label in ("company_names", "ambiguous_names"):
        raw = title_config[label]
        if (not isinstance(raw, list) or any(not isinstance(v, str) or not v.strip() or "\n" in v for v in raw)
                or len({normalize_brand(v) for v in raw}) != len(raw)):
            raise BrandMonitoringError("商品名の監視ブランド確認設定の名前が不正です。")
        names[label] = frozenset(normalize_brand(v) for v in raw)
    all_aliases = {normalize_brand(item["alias"]): normalize_brand(item["canonical"]) for item in raw_aliases}
    companies = frozenset(all_aliases.get(name, name) for name in names["company_names"])
    if not companies <= known:
        raise BrandMonitoringError("商品名の会社名除外の参照先が公式設定にありません。")
    return BrandMonitoring(tuple(rules), MappingProxyType(aliases), companies, names["ambiguous_names"])
