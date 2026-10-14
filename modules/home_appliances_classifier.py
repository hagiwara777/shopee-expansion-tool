"""Bounded Home Appliances candidate sorting, independent of Safety Shadow/Gate.

Derived from the frozen research V3 (including V2), with two bounded repairs:
explicit replacement cartridges versus purifier bundles, and whitespace in
package contents. No ASIN, brand, model lookup or external acquisition.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

VERSION = "HOME_APPLIANCES_V3_1"
A = "NON_ELECTRIC_ACCESSORY"
B = "EXCLUDE_POLICY_CANDIDATE"
C = "UNKNOWN"
DETAIL_FIELDS = ("description", "features", "shortDescription", "itemHighlights")
PASSIVE = (r"フィルター|フィルタ|カートリッジ|紙パック|集じん袋|モップパッド|清掃パッド|"
           r"収納ケース|カバー|内釜|パッキン|ブラケット|(?:保護|冷蔵庫|洗濯機|シリコン|"
           r"滑り止め|水受け).{0,12}(?:マット|トレイ|トレー)|冷蔵庫トレイ")
BODY = (r"電気ケトル|炊飯器|電子レンジ|空気清浄機|掃除機|加湿器|除湿機|扇風機|"
        r"ヒーター|トースター|洗濯機|冷蔵庫|電動シェーバー|鼻毛カッター|ひげそり")
POWER = (r"AC\s*アダプタ|電源アダプタ|充電器|充電ケース|電動|充電|コードレス|バッテリ|"
         r"電池(?:内蔵|式|で|[0-9一二三四五六七八九十本個]|残量)|bluetooth|wi[ -]?fi|"
         r"USB[ -]?(?:給電|電源)|入力電圧|\b\d{2,3}\s*v\b|\b\d{2,4}\s*w\b")
ELECTRONIC = r"液晶表示|LED表示|デジタルスケール|電子秤|スマートプラグ|スマートコンセント|スマートリモコン"
AMBIGUOUS_PART = r"アダプタ|ドック|ドッキング|ヘッド|ノズル|リモコン|センサー|温湿度計|カーテン"


def norm(value):
    if value in (None, "MISSING", "", [], {}):
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(norm(v) for v in value)
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def hit(pattern, text):
    return re.search(pattern, text, re.I)


@dataclass(frozen=True)
class Decision:
    classification: str
    reason_code: str
    evidence: str
    missing_information: str = ""

    @property
    def letter(self):
        return {A: "A", B: "B", C: "C"}[self.classification]


def _result(label, code, match, fields="title", missing=""):
    quote = match.group() if hasattr(match, "group") else match
    meaning = {A: "非電動の販売対象を示す表現", B: "本体・電源・電子機能を示す表現",
               C: "販売対象・電源・同梱品を確定できない表現"}[label]
    return Decision(label, code, f"{fields}:「{quote}」。{meaning}に基づく候補分類。", missing)


def classify_owned_text(row):
    """Internal rule entry; callers must validate and select owned Fact fields."""
    title, category = norm(row.get("title")), norm(row.get("category"))
    details = " ".join(norm(row.get(f)) for f in DETAIL_FIELDS)
    if not title:
        return _result(C, "MISSING_TITLE", "商品名なし", missing="対象商品自身の商品名")
    # A positive sold-object context is required; do not grow into other categories.
    scope = hit(r"家電|home appliances|掃除機|vacuum|浄水|water filter|スマートプラグ|充電器", category)
    research_boundary = (hit(r"キッチン|kitchen", category)
                         and hit(BODY + "|" + ELECTRONIC
                                 + r"|浴室乾燥機|電子\s*レンジ\s*調理器|玉子焼き器|フライパン", title))
    scope = scope or research_boundary
    if not scope:
        return _result(C, "HOME_APPLIANCES_CONTEXT_UNVERIFIED", category or "カテゴリなし",
                       "category", "Home Appliancesまたは研究で扱った台所・浄水境界のカテゴリ")
    purifier = hit(r"浄水器.{0,12}ポット型|浄水ポット|蛇口直結型浄水器", title)
    cartridge_only = hit(r"交換用.{0,24}カートリッジ|交換(?:用)?カートリッジ", title)
    bundle = hit(r"本体\s*[+＋と]|本体付き|本体セット|本体同梱", title)
    if purifier and not (cartridge_only and not bundle):
        display = hit(r"液晶メモ|液晶表示|電池|バッテリ|電子表示", title + " " + details)
        if display:
            return _result(B, "PURIFIER_BODY_WITH_OWN_DISPLAY", display, "title/details")
        return _result(C, "PURIFIER_BODY_BUNDLE_POWER_UNRESOLVED", purifier,
                       missing="浄水器本体・同梱品の電源／電子機能")
    heated = hit(r"電気(?:フライパン|鍋|グリル|調理器)|ホットプレート|USB.{0,8}(?:加熱|給電)", title)
    if heated:
        return _result(B, "POWERED_COOKWARE_TITLE", heated)
    electronics = hit(ELECTRONIC, title) or bundle
    if electronics:
        return _result(B, "OWN_ELECTRONICS_OR_BODY_BUNDLE", electronics)
    # Own-product statements, not arbitrary mentions of compatible devices.
    own = hit(r"(?:本製品|本商品|この商品|使用電池|電源仕様|入力電圧|電池内蔵|バッテリー内蔵)"
              r".{0,35}(?:充電|電池|バッテリ|USB|[0-9]+\s*v)|"
              r"(?:電池|バッテリ).{0,15}(?:で動作|内蔵)|\bbatteries?\s+included\b|"
              r"\bthis (?:product|device).{0,35}(?:battery|rechargeable|usb powered)", details)
    if own:
        return _result(B, "OWN_POWER_IN_DETAILS", own, "details")
    passive = hit(PASSIVE, title)
    if passive:
        if "本体" in title and not hit(r"本体(?:用|対応)", title):
            return _result(C, "BODY_AND_PASSIVE_OBJECT_UNRESOLVED", "本体 + " + passive.group(),
                           missing="本体が販売セットに含まれるか")
        active = hit(POWER, title)
        compatibility = hit(r"(?:用|対応|保護|収納).{0,16}(?:フィルター|フィルタ|カバー|ケース|ブラケット|パッド)", title)
        if active and not compatibility:
            return _result(C, "PASSIVE_ACTIVE_IDENTITY_CONFLICT", active,
                           missing="付属品自身の電源・本体同梱の有無")
        if "液晶" in details and "本体" in title:
            return _result(C, "BUNDLE_DETAILS_CONFLICT", "液晶", "details", "実際のセット内容")
        return _result(A, "POSITIVE_PASSIVE_SOLD_OBJECT", passive)
    if "電子レンジ調理器" in re.sub(r"\s+", "", title):
        if hit(r"電子レンジで", details) and hit(r"容量|シリコン|耐熱温度|容器", details):
            return _result(A, "EXTERNAL_MICROWAVE_COOKWARE_DETAILS", "電子レンジで + 容量/材質", "details")
        return _result(C, "COOKWARE_NEEDS_POSITIVE_DETAILS", "電子レンジ調理器",
                       missing="外部電子レンジで使う非電動容器の材質・用途")
    active = hit(POWER, title)
    if active:
        return _result(B, "OWN_POWER_OR_WIRELESS_TITLE", active)
    if hit(r"アダプタ", title) and "充電器" in category:
        return _result(B, "ADAPTER_AND_CHARGER_CATEGORY", "アダプタ / 充電器", "title/category")
    power = hit(POWER, details)
    if power and hit(AMBIGUOUS_PART, title):
        return _result(B, "SOLD_DEVICE_POWER_DETAILS", power, "details")
    package = hit(r"(?:パックリスト|パッケージ内容|包装内容).{0,80}ホース.{0,25}ブラシ", details)
    if hit(r"ホース|ブラシ", title) and package:
        return _result(A, "EXPLICIT_PASSIVE_HOSE_BRUSH_PACKAGE", package, "details")
    if hit(AMBIGUOUS_PART, title) or hit(r"用.{0,24}(?:ホース|ブラシ)", title):
        return _result(C, "SOLD_PART_POWER_UNRESOLVED", title,
                       missing="販売部品自身の電源・電子機能・同梱品")
    body = hit(BODY, re.sub(r"\s+", "", title))
    if body:
        return _result(B, "BODY_IDENTITY_TITLE", body)
    english_filter = hit(r"\breplacement\s+filters?\b", title)
    if english_filter:
        if hit(r"電動|充電|バッテリ|bluetooth|wi[ -]?fi|\bpowered\b", title):
            return _result(C, "ENGLISH_FILTER_POWER_CONFLICT", english_filter,
                           missing="交換フィルター自身の電源")
        return _result(A, "POSITIVE_ENGLISH_REPLACEMENT_FILTER", english_filter)
    cookware = hit(r"玉子焼き器|フライパン", title)
    if cookware:
        return _result(A, "PASSIVE_COOKWARE_WITH_EXTERNAL_HEAT", cookware)
    if (hit(r"掃除機", norm(row.get("features"))) and hit(r"掃除機", category)
            and not hit(r"部品|アクセサリ|交換", category)):
        return _result(B, "OWN_BODY_FEATURE_AND_BODY_CATEGORY", "features:掃除機 / 本体カテゴリ", "features/category")
    return _result(C, "INSUFFICIENT_POSITIVE_IDENTITY", "肯定的な商品実体情報が不足",
                   "title/category/details", "販売対象・電源・実際のセット内容")
