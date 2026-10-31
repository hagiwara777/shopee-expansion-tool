"""Small, deterministic battery facts used in addition to shared REVIEW words.

The shared words remain suspicion signals.  A warning about handling batteries
does not establish that this package contains one; no result here clears a
shared or market-specific stop.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable
import unicodedata


@dataclass(frozen=True)
class BatteryPresenceEvidence:
    action: str
    term: str
    fact_field: str
    reason: str


_BATTERY = r"(?:電池|バッテリ[ー-]?|batter(?:y|ies))"
_NOT_INCLUDED = re.compile(
    rf"{_BATTERY}.{{0,16}}(?:別売|別途購入|付属し(?:てい)?ません|付属しておりません|"
    r"付属しない|含まれ(?:てい)?ません|含まれておりません|含まれない|非同梱|不要|なし)|"
    rf"{_BATTERY}(?:が|は|を)?(?:付き|つき|入り|付属|同梱|内蔵|搭載).{{0,10}}(?:ません|ない)|"
    rf"(?:電池|バッテリ[ー-]?)(?:は|を)?(?:使用しません|搭載していません|内蔵していません)|"
    r"\b(?:no|without)\s+(?:a\s+)?batter(?:y|ies)\b|"
    r"\bbatter(?:y|ies)\s+(?:(?:is|are)\s+)?(?:not\s+(?:included|supplied|built[- ]in)|sold\s+separately)\b|"
    r"\b(?:(?:does|do)\s+not\s+(?:include|contain|come\s+with)|not\s+(?:supplied|provided)\s+with)"
    r"\s+(?:a\s+)?batter(?:y|ies)\b|"
    r"\b(?:battery[- ]free|corded|ac[- ]powered)\b|コード式|交流(?:電源)?専用|ac電源専用"
)
_EXPLICIT_INCLUDED = re.compile(
    r"(?:電池|バッテリ[ー-]?)(?:が|を)?(?:付き|つき|入り|付属|同梱|内蔵|搭載)|"
    r"(?:付属|同梱|内蔵|搭載)(?:の|された|する)?(?:電池|バッテリ[ー-]?)|"
    r"\b(?:includes?|contains?|comes?\s+with|supplied\s+with|built[- ]in)\s+"
    r"(?:(?:a|an|the)\s+)?(?:(?:rechargeable|lithium(?:[- ]ion)?|alkaline)\s+)?"
    r"batter(?:y|ies)\b(?!\s+(?:acid|fluid|leak|chemicals?|compartment|holder|cover|charger)\b)|"
    r"\bbatter(?:y|ies)\s+(?:(?:is|are)\s+)?(?:included|supplied|built[- ]in)\b"
)
_CONDITIONAL = re.compile(
    r"\b(?:if|whether|may|might|compatible|suitable)\b|場合|対応(?:品|機種)?|専用|用の|"
    r"用(?:ケース|カバー|ホルダー|充電器|ケーブル)"
)
_POWER_SPECIFICATION = re.compile(
    r"(?:単[1-6一二三四五六]\s*(?:形|型)?\s*(?:乾電池|電池)|"
    r"(?:リチウム(?:イオン)?|ニッケル水素|アルカリ)(?:蓄)?電池)"
    r"\s*[（(]?\s*(?:[×x]\s*)?[0-9一二三四五六]+\s*(?:本|個)?\s*(?:を)?(?:使用|付属|同梱)|"
    r"\buses?\s+(?:[0-9]+\s+)?(?:aa|aaa|aaaa|lithium(?:[- ]ion)?|alkaline)\s+batter(?:y|ies)\b"
)
_ELECTRIC = re.compile(r"電動|\belectric\b")
_BODY = re.compile(r"(?:本体|ホルダー)(?!\s*(?:用|専用|対応|向け|の|に))|\b(?:body|handle)\b")
_RAZOR = re.compile(r"カミソリ|かみそり|剃刀|髭剃り|ひげ剃り|シェーバー|\b(?:razor|shaver)\b")
_ACCESSORY = re.compile(
    r"替え?刃|交換刃|替え?ブラシ|交換ブラシ|ケース|カバー|保護|ケーブル|充電器|収納|ホルダー|"
    r"\b(?:blades?|cartridges?|brush[- ]heads?|case|cover|cable|charger|holder|storage|box)\b"
)
_BATTERY_PRODUCT = re.compile(
    r"モバイルバッテリー|バッテリーパック|\b(?:power\s?bank|battery\s+pack)\b|"
    r"(?:充電式|リチウム(?:イオン)?|アルカリ|ニッケル水素|乾|ボタン|コイン)電池|"
    r"単[1-6一二三四五六]\s*(?:形|型)?\s*(?:アルカリ)?(?:乾)?電池|"
    r"\b(?:rechargeable|lithium(?:[- ]ion)?|alkaline|aa|aaa|aaaa|coin[- ]cell|button[- ]cell)"
    r"\s+batter(?:y|ies)\b"
)
_BATTERY_DRIVEN = re.compile(r"\bbattery[- ](?:powered|operated)\b|(?:乾)?電池(?:駆動|式)")


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().lower()


def _references_battery_device(title: str, match: re.Match[str]) -> bool:
    """A battery in the compatible device is not a battery in the accessory."""
    if re.search(r"用(?:替え?刃|交換刃|替え?ブラシ|パッド|ケース|カバー)|向け|対応", title[match.end():]):
        return True
    if re.search(r"\bfor\b", title[:match.start()]):
        return True
    return bool(
        _ACCESSORY.search(title)
        and not _BODY.search(title)
        and "built" in match.group()
    )


def assess_battery_presence(
    title: str,
    text_values: Iterable[tuple[str, str]],
) -> BatteryPresenceEvidence | None:
    """Return affirmative inclusion or title-only electric uncertainty.

    No ASIN, brand, marketplace, category or absence of a match proves safety.
    Explicit no-battery/corded statements prevent an inferred BLOCK; contradictory
    facts remain REVIEW.  Generic replacement/handling warnings are not inclusion.
    """
    values = [(field, _normalize(value)) for field, value in text_values]
    normalized_title = _normalize(title)
    no_battery = any(_NOT_INCLUDED.search(value) for _, value in values)
    affirmative: BatteryPresenceEvidence | None = None
    power_evidence: BatteryPresenceEvidence | None = None

    for field, value in values:
        for clause in re.split(r"[。.!?！？\n;；]", value):
            if _NOT_INCLUDED.search(clause) or _CONDITIONAL.search(clause):
                continue
            for match in _EXPLICIT_INCLUDED.finditer(clause):
                if _references_battery_device(clause, match):
                    continue
                affirmative = BatteryPresenceEvidence(
                    "BLOCK", match.group(), field, "explicit_battery_inclusion"
                )
                break
            if affirmative is not None:
                break
            match = _POWER_SPECIFICATION.search(clause)
            if match is not None and power_evidence is None:
                power_evidence = BatteryPresenceEvidence(
                    "REVIEW", match.group(), field, "battery_power_specification_inclusion_unknown"
                )
        if affirmative is not None:
            break

    title_has_accessory = bool(_ACCESSORY.search(normalized_title))
    accessory_only = title_has_accessory and (
        not _BODY.search(normalized_title)
        or bool(re.search(r"\b(?:replacement|refill)\b", normalized_title))
    )
    if affirmative is None:
        match = _BATTERY_PRODUCT.search(normalized_title)
        if match is not None and not title_has_accessory:
            affirmative = BatteryPresenceEvidence(
                "BLOCK", match.group(), "product_title", "battery_product"
            )
        elif (
            not title_has_accessory
            and (match := _BATTERY_DRIVEN.search(normalized_title)) is not None
        ):
            affirmative = BatteryPresenceEvidence(
                "REVIEW", match.group(), "product_title", "battery_power_specification_inclusion_unknown"
            )
        elif (
            not accessory_only
            and _ELECTRIC.search(normalized_title)
            and _RAZOR.search(normalized_title)
            and _BODY.search(normalized_title)
        ):
            affirmative = BatteryPresenceEvidence(
                "REVIEW", "電動", "product_title", "electric_razor_body_battery_inclusion_unknown"
            )

    if affirmative is None:
        affirmative = power_evidence
    if affirmative is not None:
        if no_battery:
            return BatteryPresenceEvidence(
                "REVIEW", affirmative.term, affirmative.fact_field,
                "battery_presence_conflicting_or_not_included",
            )
        return affirmative
    if _ELECTRIC.search(normalized_title):
        return BatteryPresenceEvidence(
            "REVIEW", _ELECTRIC.search(normalized_title).group(), "product_title", "electric_item_battery_presence_unknown"
        )
    return None
