"""Export current BLOCK terms without silently dropping matching boundaries.

FROMAX uses case-insensitive substring matching. Exact, brand, ASIN and
word-boundary rules therefore stay in a separate caution file for manual use.
This module never changes the Guardrail rules or contacts an external service.
"""
from dataclasses import dataclass
import csv
from io import StringIO
from pathlib import Path
import re
import unicodedata

from modules.guardrails import load_guardrail_dictionaries, load_deterministic_block_rules_v2
from modules.community_ng import load_community_ng_assets


@dataclass(frozen=True)
class NgCaution:
    term: str
    reason: str
    source: str


@dataclass(frozen=True)
class FromaxNgExport:
    marketplace: str
    keywords: tuple[str, ...]
    cautions: tuple[NgCaution, ...]

    @property
    def keywords_txt(self) -> bytes:
        return ("\n".join(self.keywords) + ("\n" if self.keywords else "")).encode("utf-8")

    @property
    def cautions_csv(self) -> bytes:
        output = StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("語句", "通常リストから分けた理由", "出典"))
        for item in self.cautions:
            writer.writerow(tuple(_safe_cell(value) for value in (item.term, item.reason, item.source)))
        return output.getvalue().encode("utf-8-sig")


def _safe_cell(value: str) -> str:
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def _variants(term: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", term).strip()
    hira = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in normalized)
    kata = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in normalized)
    return tuple(dict.fromkeys((term.strip(), normalized, hira, kata)))


def build_fromax_ng_export(
    marketplace: str, *, dictionary_dir: str | Path | None = None,
    community_dir: str | Path | None = None,
) -> FromaxNgExport:
    if marketplace not in {"SG", "PH"}:
        raise ValueError("FROMAX用NG出力はSG・PHだけが対象です。")
    dictionaries = load_guardrail_dictionaries(dictionary_dir, marketplace=marketplace)
    v2 = load_deterministic_block_rules_v2(dictionary_dir)
    community = load_community_ng_assets(community_dir)
    keywords: dict[str, str] = {}
    cautions: dict[tuple[str, str, str], NgCaution] = {}

    def add(term: str, source: str, reason: str = "", *, boundary: bool = False):
        normalized = unicodedata.normalize("NFKC", term).strip().casefold()
        if not normalized or "\n" in term or "\r" in term:
            raise ValueError("NG語句を1行に収められません。")
        # The app's V1 ASCII token phrases have word boundaries; FROMAX does not.
        # Short ASCII fragments are also separated, including literal V2 terms.
        ascii_phrase = re.fullmatch(r"[a-z0-9]+(?: [a-z0-9]+)*", normalized) is not None
        short_ascii = re.fullmatch(r"[a-z0-9]{1,4}", normalized) is not None
        if not reason and (boundary or ascii_phrase or short_ascii):
            reason = "英字の単語境界を保てず部分一致が広がります（例：OTCとHotcake）。一括貼付しないでください。"
        for value in _variants(term):
            if reason:
                key = (value.casefold(), reason, source)
                cautions.setdefault(key, NgCaution(value, reason, source))
            else:
                # FROMAX ignores ASCII case, but width and Kana equivalence are unverified.
                keywords.setdefault(value.casefold(), value)

    for rule in dictionaries.brand_rules + dictionaries.keyword_rules:
        if rule.action != "BLOCK":
            continue
        reason = ""
        if rule.dictionary_type == "brand" or rule.match_field == "brand":
            reason = "ブランド照合をNGキーワードへ置換しません。FROMAXのNGブランドも双方向部分一致に注意してください。"
        elif rule.match_field == "asin":
            reason = "ASIN指定の除外です。商品名のNGキーワードでは再現できません。"
        elif rule.match_type != "contains" or rule.match_field not in {"title", "all"}:
            reason = "完全一致・カテゴリ等の条件を、商品名の部分一致へ置換できません。"
        add(rule.term, f"{rule.file_name}:{rule.row_number}", reason)

    for rule in v2:
        if rule.scope not in {"COMMON_BLOCK", f"{marketplace}_BLOCK"} or rule.action != "BLOCK":
            continue
        reason = ""
        if rule.fact_field == "brand" or rule.operator == "exact":
            reason = "ブランド等の完全一致を部分一致へ置換しません。"
        elif rule.operator not in {"contains", "contains_term"}:
            reason = "条件付きの判定をNGキーワードだけでは再現できません。"
        boundary = rule.operator == "contains_term" and re.search(r"[a-z0-9]", rule.normalized_value) is not None
        add(rule.value, rule.rule_id, reason, boundary=boundary)

    for block in community.brand_blocks:
        if block.marketplace == marketplace:
            add(block.match_value, f"Community NG:{block.source_id}:{block.source_row}",
                "登録ブランドの照合です。NGキーワードや双方向部分一致へ無言で変換しません。")
    for block in community.asin_blocks:
        if block.marketplace == marketplace:
            add(block.asin, f"Community NG:{block.source_id}:{block.source_row}",
                "ASIN指定の除外です。商品名のNGキーワードでは再現できません。")
    return FromaxNgExport(marketplace,
        tuple(sorted(keywords.values(), key=str.casefold)),
        tuple(sorted(cautions.values(), key=lambda c: (c.term.casefold(), c.reason, c.source))))
