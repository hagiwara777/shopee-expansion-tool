"""MY dimensional-weight review from already fetched JP catalog attributes (DEC-0189)."""
from dataclasses import dataclass, replace
import math


JP_MARKETPLACE = "A1VC38T7YXB528"
LENGTH_CM = {
    "centimeters": 1, "centimetres": 1, "centimeter": 1, "cm": 1,
    "millimeters": .1, "millimetres": .1, "millimeter": .1, "mm": .1,
    "meters": 100, "metres": 100, "meter": 100, "m": 100,
    "inches": 2.54, "inch": 2.54, "in": 2.54, "feet": 30.48, "foot": 30.48, "ft": 30.48,
}
WEIGHT_KG = {
    "kilograms": 1, "kilogram": 1, "kg": 1,
    "grams": .001, "gram": .001, "g": .001,
    "pounds": .45359237, "pound": .45359237, "lb": .45359237, "lbs": .45359237,
    "ounces": .028349523125, "ounce": .028349523125, "oz": .028349523125,
}


@dataclass(frozen=True)
class PackageMeasurements:
    candidate_asin: str
    dimensions_cm: tuple[float, float, float] | None
    weight_kg: float | None
    dimensions_source: str
    weight_source: str


def _number(value, factors):
    if not isinstance(value, dict) or type(value.get("value")) not in (int, float):
        return None
    number = value["value"]
    factor = factors.get(str(value.get("unit", "")).strip().casefold())
    if factor is None or not math.isfinite(number) or number <= 0:
        return None
    converted = number * factor
    return converted if math.isfinite(converted) and converted > 0 else None


def _attribute(attributes, names, *, dimensions=False):
    for name in names:
        entries = attributes.get(name, [])
        if not isinstance(entries, list):
            continue
        values = set()
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("marketplace_id", JP_MARKETPLACE) != JP_MARKETPLACE:
                continue
            if dimensions:
                value = tuple(_number(entry.get(axis), LENGTH_CM) for axis in ("length", "width", "height"))
                if all(part is not None for part in value):
                    values.add(value)
            else:
                value = _number(entry, WEIGHT_KG)
                if value is not None:
                    values.add(value)
        if len(values) == 1:
            return values.pop(), name
        if len(values) > 1:
            # Conflicting values are unavailable, never silently pick one.
            return None, name
    return None, ""


def package_measurements_from_attributes(asin, attributes):
    dimensions, dimension_source = _attribute(
        attributes, ("item_package_dimensions", "item_dimensions"), dimensions=True)
    weight, weight_source = _attribute(attributes, ("item_package_weight", "item_weight"))
    return PackageMeasurements(asin, dimensions, weight, dimension_source, weight_source)


def measurements_for_run(verified_rows):
    """Use only verified SP-API facts, retaining ASIN binding after consolidation."""
    by_asin = {}
    for row in verified_rows:
        if row.get("status") != "FOUND" or row.get("verification") != "SP_API_VERIFIED":
            continue
        fact = row.get("package_measurements")
        if fact is None:
            continue
        if not isinstance(fact, PackageMeasurements) or fact.candidate_asin != row.get("asin"):
            raise ValueError("梱包情報の対象商品が一致しません。")
        if fact.candidate_asin in by_asin and by_asin[fact.candidate_asin] != fact:
            raise ValueError("同じASINの梱包情報が一致しません。")
        by_asin[fact.candidate_asin] = fact
    return tuple(by_asin.values())


def apply_my_volumetric(result, measurements):
    if result.marketplace != "MY":
        return result
    by_asin = {fact.candidate_asin: fact for fact in measurements}
    rows = []
    for row in result.rows:
        fact = by_asin.get(row.candidate.candidate_asin)
        if fact is None or fact.dimensions_cm is None or fact.weight_kg is None:
            note = "MY-VOLUMETRIC: サイズ情報なし（寸法または重量が未取得・換算不能）"
            rows.append(replace(row, guardrail_note=" | ".join(filter(None, (row.guardrail_note, note)))))
            continue
        length, width, height = fact.dimensions_cm
        volumetric = length * width * height / 6000
        if not math.isfinite(volumetric):
            note = "MY-VOLUMETRIC: サイズ情報なし（容積重量を計算できません）"
            rows.append(replace(row, guardrail_note=" | ".join(filter(None, (row.guardrail_note, note)))))
            continue
        if volumetric <= fact.weight_kg or math.isclose(volumetric, fact.weight_kg, rel_tol=1e-12):
            rows.append(row)
            continue
        note = (f"MY-VOLUMETRIC: 容積重量 {round(volumetric, 6)}kg ＞ 実重量 {round(fact.weight_kg, 6)}kg"
                f"（{fact.dimensions_source} / {fact.weight_source}）")
        def append(value, addition):
            return "|".join(dict.fromkeys(filter(None, (value or "").split("|") + [addition])))
        codes = row.reason_codes
        if "GUARDRAIL_REVIEW" not in codes:
            codes += ("GUARDRAIL_REVIEW",)
        rows.append(replace(
            row, guardrail_status="BLOCK" if row.guardrail_status == "BLOCK" else "REVIEW",
            guardrail_risk_category=append(row.guardrail_risk_category, "shipping_restricted"),
            guardrail_matched_terms=append(row.guardrail_matched_terms, "MY-VOLUMETRIC"),
            guardrail_source=append(row.guardrail_source, "internal_rule"),
            guardrail_note=" | ".join(filter(None, (row.guardrail_note, note))),
            final_eligibility="EXCLUDE" if row.final_eligibility == "EXCLUDE" else "REVIEW",
            reason_codes=codes))
    return replace(result, rows=tuple(rows),
                   eligible_count=sum(row.final_eligibility == "ELIGIBLE" for row in rows),
                   review_count=sum(row.final_eligibility == "REVIEW" for row in rows),
                   exclude_count=sum(row.final_eligibility == "EXCLUDE" for row in rows))
