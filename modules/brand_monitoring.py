"""Country-scoped official monitoring brands; exact primary-brand matching only."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata


CONFIG_DIR = Path(__file__).resolve().parents[1] / "guardrails" / "brand_monitoring"
COUNTRY_FILES = {"SG": "counterfeit_sg.json", "PH": "counterfeit_ph.json"}


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
    return " ".join(unicodedata.normalize("NFC", "".join(output)).split())


def primary_brand(value: str) -> str:
    return " ".join(re.sub(r"\([^()]*\)", "", normalize_brand(value)).split())


@dataclass(frozen=True)
class MonitoringBrand:
    term: str
    scope: str
    file_name: str


@dataclass(frozen=True)
class BrandMonitoring:
    rules: tuple[MonitoringBrand, ...]
    aliases: dict[str, str]

    def matches(self, value: str) -> tuple[MonitoringBrand, ...]:
        complete = normalize_brand(value)
        # Only the outer, primary brand is eligible. Parent companies or other
        # names inside parentheses must never widen a child brand's identity.
        primary = primary_brand(value)
        keys = {complete, primary} - {""}
        keys |= {self.aliases[key] for key in tuple(keys) if key in self.aliases}
        return tuple(rule for rule in self.rules
                     if {normalize_brand(rule.term), primary_brand(rule.term)} & keys)


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (OSError, ValueError) as exc:
        raise BrandMonitoringError(f"監視ブランド設定を読めません: {path.name}") from exc


def load_brand_monitoring(marketplace: str, config_dir: str | Path | None = None) -> BrandMonitoring:
    if marketplace not in COUNTRY_FILES:
        raise BrandMonitoringError("監視ブランド照合の対象市場ではありません。")
    base = Path(config_dir) if config_dir is not None else CONFIG_DIR
    rules = []
    for filename, scope in (("ipr.json", "ALL"), (COUNTRY_FILES[marketplace], marketplace)):
        data = _read(base / filename)
        brands = data.get("brands")
        if (data.get("scope") != scope or not isinstance(data.get("source_url"), str)
                or not isinstance(brands, list) or not brands
                or any(not isinstance(v, str) or not v.strip() or "\n" in v or "\r" in v for v in brands)):
            raise BrandMonitoringError(f"監視ブランド設定が不正です: {filename}")
        rules.extend(MonitoringBrand(v, scope, filename) for v in brands)
    raw_aliases = _read(base / "aliases.json").get("aliases")
    if not isinstance(raw_aliases, list):
        raise BrandMonitoringError("監視ブランドの別表記設定が不正です。")
    known = {normalize_brand(rule.term) for rule in rules}
    if raw_aliases:
        # Shared aliases may target a brand active only in the other country.
        # Check references against existing official files, without applying
        # that country's rules to the selected market.
        for filename in set(COUNTRY_FILES.values()) - {COUNTRY_FILES[marketplace]}:
            other = _read(base / filename).get("brands")
            if not isinstance(other, list) or any(not isinstance(v, str) for v in other):
                raise BrandMonitoringError(f"監視ブランド設定が不正です: {filename}")
            known.update(normalize_brand(v) for v in other)
    aliases = {}
    for item in raw_aliases:
        if (not isinstance(item, dict) or set(item) != {"alias", "canonical"}
                or any(not isinstance(v, str) or not v.strip() for v in item.values())):
            raise BrandMonitoringError("監視ブランドの別表記設定が不正です。")
        key, canonical = normalize_brand(item["alias"]), normalize_brand(item["canonical"])
        if key in aliases or key == canonical:
            raise BrandMonitoringError("監視ブランドの別表記が重複しています。")
        if canonical not in known:
            raise BrandMonitoringError("監視ブランドの別表記の参照先が公式設定にありません。")
        aliases[key] = canonical
    return BrandMonitoring(tuple(rules), aliases)
