import csv
from io import StringIO
from pathlib import Path

import pytest

from modules.export_csv import rows_to_csv
from modules.guardrails import (
    ALLOWED_RISK_CATEGORIES,
    GuardrailDictionaryError,
    apply_guardrails,
    filter_safe_rows,
    summarize_guardrails,
)


BRAND_CSV = """term,action,risk_category,match_field,match_type,source_type,note,enabled
Biore,BLOCK,brand_ip,brand,exact,shopee_brand_list,Brand restriction sample,TRUE
HP,BLOCK,brand_ip,brand,exact,shopee_brand_list,Short brand exact only,TRUE
NULL,BLOCK,brand_ip,brand,exact,internal_rule,Literal NULL brand string only,TRUE
DisabledBrand,BLOCK,brand_ip,brand,exact,internal_rule,Disabled rule,FALSE
"""

RISK_CSV = """term,action,risk_category,match_field,match_type,source_type,note,enabled
水鉄砲,REVIEW,weapon_related_toy,title,contains,community_report,Weapon-like toy,TRUE
銃,BLOCK,weapon,title,contains,community_report,Weapon term,TRUE
ハイドロキノン,BLOCK,regulated_ingredient,title,contains,community_report,Regulated ingredient,TRUE
ignored,BLOCK,other,title,contains,internal_rule,Disabled keyword,FALSE
"""


def write_dictionaries(tmp_path, brand_csv=BRAND_CSV, risk_csv=RISK_CSV):
    dictionary_dir = tmp_path / "guardrails"
    dictionary_dir.mkdir()
    (dictionary_dir / "prohibited_brands_sg.csv").write_text(brand_csv, encoding="utf-8")
    (dictionary_dir / "risk_keywords_sg.csv").write_text(risk_csv, encoding="utf-8")
    return dictionary_dir


def candidate(brand="", title="Sample product", category="Beauty", asin="B000000001"):
    return {
        "seed_asin": "B07TSC47PH",
        "candidate_asin": asin,
        "brand": brand,
        "category": category,
        "product_title": title,
    }


@pytest.mark.parametrize("brand", ["Biore", "biore", "Ｂｉｏｒｅ"])
def test_brand_biore_is_block_with_normalization(tmp_path, brand):
    rows = apply_guardrails([candidate(brand=brand)], write_dictionaries(tmp_path))

    assert rows[0]["guardrail_status"] == "BLOCK"
    assert rows[0]["guardrail_matched_terms"] == "Biore"


def test_brand_hp_is_block_but_happy_title_is_not_hp(tmp_path):
    dictionary_dir = write_dictionaries(tmp_path)

    hp_rows = apply_guardrails([candidate(brand="HP")], dictionary_dir)
    happy_rows = apply_guardrails([candidate(brand="Other", title="happy skincare")], dictionary_dir)

    assert hp_rows[0]["guardrail_status"] == "BLOCK"
    assert happy_rows[0]["guardrail_status"] == "SAFE"


def test_blank_brand_does_not_match_null_but_literal_null_does(tmp_path):
    dictionary_dir = write_dictionaries(tmp_path)

    blank_rows = apply_guardrails([candidate(brand="")], dictionary_dir)
    null_rows = apply_guardrails([candidate(brand="NULL")], dictionary_dir)

    assert blank_rows[0]["guardrail_status"] == "SAFE"
    assert null_rows[0]["guardrail_status"] == "BLOCK"
    assert null_rows[0]["guardrail_matched_terms"] == "NULL"


def test_title_keywords_review_and_block(tmp_path):
    dictionary_dir = write_dictionaries(tmp_path)

    review_rows = apply_guardrails([candidate(title="水鉄砲 おもちゃ")], dictionary_dir)
    gun_rows = apply_guardrails([candidate(title="銃 モデル")], dictionary_dir)
    ingredient_rows = apply_guardrails([candidate(title="ハイドロキノン クリーム")], dictionary_dir)

    assert review_rows[0]["guardrail_status"] == "REVIEW"
    assert gun_rows[0]["guardrail_status"] == "BLOCK"
    assert ingredient_rows[0]["guardrail_status"] == "BLOCK"


def test_block_wins_over_review_and_keeps_all_matched_terms(tmp_path):
    rows = apply_guardrails(
        [candidate(brand="Biore", title="水鉄砲 おもちゃ")],
        write_dictionaries(tmp_path),
    )

    assert rows[0]["guardrail_status"] == "BLOCK"
    assert rows[0]["guardrail_matched_terms"] == "Biore|水鉄砲"
    assert rows[0]["guardrail_risk_category"] == "brand_ip|weapon_related_toy"
    assert "Brand matched: Biore" in rows[0]["guardrail_note"]
    assert "Keyword matched: 水鉄砲" in rows[0]["guardrail_note"]


def test_unmatched_candidate_is_safe_and_disabled_rules_are_ignored(tmp_path):
    dictionary_dir = write_dictionaries(tmp_path)

    safe_rows = apply_guardrails([candidate(brand="Other", title="Normal item")], dictionary_dir)
    disabled_rows = apply_guardrails(
        [candidate(brand="DisabledBrand", title="ignored product")],
        dictionary_dir,
    )

    assert safe_rows[0]["guardrail_status"] == "SAFE"
    assert disabled_rows[0]["guardrail_status"] == "SAFE"


def test_summary_safe_filter_and_csv_outputs(tmp_path):
    guarded_rows = apply_guardrails(
        [
            candidate(brand="Other", asin="B000000001"),
            candidate(brand="Biore", asin="B000000002"),
            candidate(title="水鉄砲", asin="B000000003"),
        ],
        write_dictionaries(tmp_path),
    )

    summary = summarize_guardrails(guarded_rows)
    safe_rows = filter_safe_rows(guarded_rows)
    safe_csv = rows_to_csv(safe_rows).decode("utf-8-sig")
    audit_csv = rows_to_csv(guarded_rows).decode("utf-8-sig")

    assert summary["SAFE"] == 1
    assert summary["BLOCK"] == 1
    assert summary["REVIEW"] == 1
    assert [row["candidate_asin"] for row in safe_rows] == ["B000000001"]

    safe_csv_rows = list(csv.DictReader(StringIO(safe_csv)))
    audit_csv_rows = list(csv.DictReader(StringIO(audit_csv)))
    assert [row["guardrail_status"] for row in safe_csv_rows] == ["SAFE"]
    assert {row["guardrail_status"] for row in audit_csv_rows} == {"SAFE", "REVIEW", "BLOCK"}


def test_missing_required_column_is_dictionary_error(tmp_path):
    bad_brand_csv = """term,action,risk_category,match_field,match_type,source_type,note
Biore,BLOCK,brand_ip,brand,exact,shopee_brand_list,Missing enabled
"""

    with pytest.raises(GuardrailDictionaryError, match="必須列"):
        apply_guardrails([candidate(brand="Biore")], write_dictionaries(tmp_path, brand_csv=bad_brand_csv))


@pytest.mark.parametrize(
    "risk_csv,error_match",
    [
        (
            """term,action,risk_category,match_field,match_type,source_type,note,enabled
safe term,SAFE,other,title,contains,internal_rule,SAFE is invalid,TRUE
""",
            "action",
        ),
        (
            """term,action,risk_category,match_field,match_type,source_type,note,enabled
bad enabled,BLOCK,other,title,contains,internal_rule,Bad enabled,
""",
            "enabled",
        ),
        (
            """term,action,risk_category,match_field,match_type,source_type,note,enabled
bad match,BLOCK,other,title,fuzzy,internal_rule,Bad match type,TRUE
""",
            "match_type",
        ),
    ],
)
def test_invalid_dictionary_values_are_errors(tmp_path, risk_csv, error_match):
    with pytest.raises(GuardrailDictionaryError, match=error_match):
        apply_guardrails([candidate()], write_dictionaries(tmp_path, risk_csv=risk_csv))


@pytest.mark.parametrize(
    "brand_csv,error_match",
    [
        (
            """term,action,risk_category,match_field,match_type,source_type,note,enabled
Biore,BLOCK,brand_ip,title,exact,shopee_brand_list,Bad field,TRUE
""",
            "match_field",
        ),
        (
            """term,action,risk_category,match_field,match_type,source_type,note,enabled
Biore,BLOCK,brand_ip,brand,contains,shopee_brand_list,Bad type,TRUE
""",
            "match_type",
        ),
    ],
)
def test_prohibited_brand_dictionary_rejects_non_brand_exact_rules(tmp_path, brand_csv, error_match):
    with pytest.raises(GuardrailDictionaryError, match=error_match):
        apply_guardrails([candidate(brand="Biore")], write_dictionaries(tmp_path, brand_csv=brand_csv))


OWN_PENALTY_ASIN_CSV = """B000FQTRS0,BLOCK,own_penalty_product,asin,exact,own_penalty_case,Own delist ASIN case,TRUE
"""


def test_own_penalty_asin_exact_match_uses_candidate_asin_only(tmp_path):
    dictionary_dir = write_dictionaries(tmp_path, risk_csv=RISK_CSV + OWN_PENALTY_ASIN_CSV)
    rows = apply_guardrails(
        [
            candidate(asin="B000FQTRS0"),
            candidate(asin="  b000fqtrs0  "),
            candidate(asin="B000FQTRS00"),
            candidate(asin="XB000FQTRS0"),
            candidate(asin=""),
            candidate(asin=None),
        ],
        dictionary_dir,
    )

    assert [row["guardrail_status"] for row in rows] == ["BLOCK", "BLOCK", "SAFE", "SAFE", "SAFE", "SAFE"]
    assert rows[0]["guardrail_matched_terms"] == "B000FQTRS0"
    assert rows[0]["guardrail_source"] == "own_penalty_case"
    assert rows[0]["guardrail_risk_category"] == "own_penalty_product"


def test_asin_rule_does_not_search_title_seed_asin_or_legacy_asin_column(tmp_path):
    dictionary_dir = write_dictionaries(tmp_path, risk_csv=RISK_CSV + OWN_PENALTY_ASIN_CSV)
    rows = apply_guardrails(
        [
            candidate(title="B000FQTRS0", asin="B000000001"),
            {
                "seed_asin": "B000FQTRS0",
                "candidate_asin": "B000000002",
                "asin": "B000FQTRS0",
                "brand": "Other",
                "category": "Beauty",
                "product_title": "Normal item",
            },
        ],
        dictionary_dir,
    )

    assert [row["guardrail_status"] for row in rows] == ["SAFE", "SAFE"]


def test_all_contains_rule_does_not_search_candidate_asin(tmp_path):
    risk_csv = RISK_CSV + """B000FQTRS0,BLOCK,other,all,contains,internal_rule,Text-only rule,TRUE
"""

    rows = apply_guardrails([candidate(asin="B000FQTRS0")], write_dictionaries(tmp_path, risk_csv=risk_csv))

    assert rows[0]["guardrail_status"] == "SAFE"


def test_lowercase_asin_rule_is_normalized_and_accepted(tmp_path):
    risk_csv = RISK_CSV + """b000fqtrs0,BLOCK,own_penalty_product,asin,exact,own_penalty_case,Lowercase ASIN rule,TRUE
"""

    rows = apply_guardrails([candidate(asin="B000FQTRS0")], write_dictionaries(tmp_path, risk_csv=risk_csv))

    assert rows[0]["guardrail_status"] == "BLOCK"


@pytest.mark.parametrize("term", ["B000FQTRS", "B000FQTRS00", "B000-FQTRS0", "B000FQTRS!", ""])
def test_invalid_asin_rule_term_is_dictionary_error(tmp_path, term):
    risk_csv = RISK_CSV + f"{term},BLOCK,own_penalty_product,asin,exact,own_penalty_case,Invalid ASIN rule,TRUE\n"

    with pytest.raises(GuardrailDictionaryError, match="ASINルール"):
        apply_guardrails([candidate()], write_dictionaries(tmp_path, risk_csv=risk_csv))


def test_asin_contains_rule_is_dictionary_error(tmp_path):
    risk_csv = RISK_CSV + """B000FQTRS0,BLOCK,own_penalty_product,asin,contains,own_penalty_case,Invalid ASIN rule,TRUE
"""

    with pytest.raises(GuardrailDictionaryError, match="ASINルールの match_type は exact"):
        apply_guardrails([candidate()], write_dictionaries(tmp_path, risk_csv=risk_csv))


def test_own_penalty_brand_rules_are_exact_and_keep_metadata(tmp_path):
    brand_csv = BRAND_CSV + """加美乃素,BLOCK,brand_medical_risk,brand,exact,own_penalty_case,Own penalty brand case,TRUE
Kaminomoto,BLOCK,brand_medical_risk,brand,exact,own_penalty_case,Own penalty brand case,TRUE
"""
    dictionary_dir = write_dictionaries(tmp_path, brand_csv=brand_csv)
    rows = apply_guardrails(
        [
            candidate(brand="加美乃素"),
            candidate(brand="Kaminomoto"),
            candidate(brand="ＫＡＭＩＮＯＭＯＴＯ"),
            candidate(brand="Other", title="加美乃素 育毛剤"),
        ],
        dictionary_dir,
    )

    assert [row["guardrail_status"] for row in rows] == ["BLOCK", "BLOCK", "BLOCK", "SAFE"]
    assert rows[0]["guardrail_source"] == "own_penalty_case"
    assert rows[0]["guardrail_risk_category"] == "brand_medical_risk"


@pytest.mark.parametrize(
    "term",
    [
        "薬用加美乃素S-II",
        "薬用加美乃素S-2",
        "加美乃素S-II",
        "加美乃素S-2",
        "Kaminomoto S-II",
        "Kaminomoto S-2",
    ],
)
def test_own_penalty_product_title_variants_are_blocked(tmp_path, term):
    risk_csv = RISK_CSV + f"{term},BLOCK,own_penalty_product,title,contains,own_penalty_case,Own delist product case,TRUE\n"

    rows = apply_guardrails([candidate(title=f"限定品 {term} 内容量")], write_dictionaries(tmp_path, risk_csv=risk_csv))

    assert rows[0]["guardrail_status"] == "BLOCK"
    assert rows[0]["guardrail_matched_terms"] == term
    assert rows[0]["guardrail_source"] == "own_penalty_case"
    assert rows[0]["guardrail_risk_category"] == "own_penalty_product"


RISK_KEYWORDS_PATH = Path(__file__).resolve().parents[1] / "guardrails" / "risk_keywords_sg.csv"
V12_CG_RULE_COUNTS = {
    "CG-001": 3,
    "CG-002": 3,
    "CG-003": 3,
    "CG-004": 4,
    "CG-005": 3,
    "CG-006": 2,
    "CG-007": 3,
    "CG-008": 3,
    "CG-009": 5,
    "CG-010": 3,
    "CG-011": 4,
    "CG-012": 3,
    "CG-013": 3,
    "CG-014": 2,
    "CG-015": 3,
    "CG-016": 3,
    "CG-017": 2,
    "CG-018": 2,
    "CG-019": 1,
    "CG-020": 3,
    "CG-021": 3,
    "CG-022": 2,
    "CG-023": 3,
    "CG-024": 3,
    "CG-025": 3,
    "CG-026": 3,
    "CG-027": 1,
    "CG-028": 3,
    "CG-029": 3,
    "CG-030": 4,
    "CG-031": 3,
    "CG-032": 1,
    "CG-033": 3,
}
V12_LIC_RULE_COUNTS = {
    "LIC-001": 3,
    "LIC-002": 4,
    "LIC-003": 5,
    "LIC-004": 6,
    "LIC-005": 2,
    "LIC-006": 4,
    "LIC-007": 3,
}


def v12_risk_rows():
    with RISK_KEYWORDS_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return [
            row
            for row in csv.DictReader(csv_file)
            if row["note"].startswith(("CG-", "LIC-"))
        ]


def v12_rule_counts(prefix):
    counts = {}
    for row in v12_risk_rows():
        rule_id = row["note"].split(";", 1)[0]
        if rule_id.startswith(prefix):
            counts[rule_id] = counts.get(rule_id, 0) + 1
    return counts


def test_v12_risk_categories_are_allowed_and_unknown_categories_fail_closed(tmp_path):
    assert {
        "controlled_goods_unverified",
        "license_or_certification_required",
        "shipping_restricted",
    } <= ALLOWED_RISK_CATEGORIES

    risk_csv = RISK_CSV + """unknown category,REVIEW,not_an_allowed_category,title,contains,shopee_policy,Invalid category,TRUE
"""
    with pytest.raises(GuardrailDictionaryError, match="risk_category"):
        apply_guardrails([candidate()], write_dictionaries(tmp_path, risk_csv=risk_csv))


def test_v12_dictionary_rows_are_unique_complete_and_use_the_approved_contract():
    with RISK_KEYWORDS_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    terms = [row["term"].casefold() for row in rows]
    assert len(terms) == len(set(terms))
    assert v12_rule_counts("CG-") == V12_CG_RULE_COUNTS
    assert v12_rule_counts("LIC-") == V12_LIC_RULE_COUNTS

    for row in v12_risk_rows():
        rule_id = row["note"].split(";", 1)[0]
        assert row["action"] == "REVIEW"
        assert row["match_field"] == "title"
        assert row["match_type"] == "contains"
        assert row["source_type"] == "shopee_policy"
        assert row["enabled"] == "TRUE"
        assert "title alone cannot determine" in row["note"]
        if rule_id.startswith("CG-"):
            assert row["risk_category"] == "controlled_goods_unverified"
            assert "Official category:" in row["note"]
            assert "physical Controlled Goods main item is company-policy BLOCK" in row["note"]
        else:
            assert row["risk_category"] == "license_or_certification_required"
            assert "Category:" in row["note"]
            assert "normal cross-border operations" in row["note"]


@pytest.mark.parametrize("term", [row["term"] for row in v12_risk_rows()])
def test_every_v12_title_rule_routes_its_own_term_to_review(term):
    row = apply_guardrails([candidate(title=f"Featured {term} product")])[0]

    assert row["guardrail_status"] == "REVIEW"
    assert term in row["guardrail_matched_terms"].split("|")


def test_v12_title_rules_do_not_match_category_only():
    row = apply_guardrails([candidate(title="ordinary household item", category="electric kettle")])[0]

    assert row["guardrail_status"] == "SAFE"


def test_v12_shipping_reclassifications_preserve_existing_match_contracts():
    with RISK_KEYWORDS_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        rows_by_term = {row["term"]: row for row in csv.DictReader(csv_file)}

    assert rows_by_term["モバイルバッテリー"] == {
        "term": "モバイルバッテリー",
        "action": "REVIEW",
        "risk_category": "shipping_restricted",
        "match_field": "all",
        "match_type": "contains",
        "source_type": "internal_rule",
        "note": "Battery-powered item requires shipping and logistics review",
        "enabled": "TRUE",
    }
    assert rows_by_term["PowerCore"]["risk_category"] == "shipping_restricted"
    assert rows_by_term["PowerCore"]["match_field"] == "all"
    assert rows_by_term["PowerCore"]["match_type"] == "contains"
    assert rows_by_term["浄水器"]["risk_category"] == "shipping_restricted"
    assert rows_by_term["浄水器"]["match_field"] == "all"
    assert rows_by_term["浄水器"]["match_type"] == "contains"


@pytest.mark.parametrize(
    "title,expected_status",
    [
        ("cooler lamp adapter audio video speaker player fan computer PC monitor", "SAFE"),
        ("iron socket outlet cleaner plug hose regulator valve switch fuse cooker canister dryer", "SAFE"),
        ("transformer kettle microwave range hob oven washer washing refrigerator water heater", "SAFE"),
        ("AC adapter case", "REVIEW"),
        ("hair dryer storage case", "REVIEW"),
        ("dog food storage container", "REVIEW"),
        ("cat food bowl", "REVIEW"),
        ("Nintendo Switch carrying case", "SAFE"),
        ("Iron Man collectible", "SAFE"),
        ("PC replacement part", "SAFE"),
        ("pet bowl", "SAFE"),
        ("automatic pet feeder", "SAFE"),
        ("pet storage container", "SAFE"),
        ("pet accessory pouch", "SAFE"),
    ],
)
def test_v12_false_positive_controls_never_create_a_block(title, expected_status):
    row = apply_guardrails([candidate(title=title, category="Pet Supplies")])[0]

    assert row["guardrail_status"] == expected_status
    assert row["guardrail_status"] != "BLOCK"


@pytest.mark.parametrize(
    ("term", "false_positive_title"),
    [
        ("multi-way adaptor", "notmulti-way adaptor"),
        ("3-pin mains plug", "13-pin mains plug"),
        ("3ピン電源プラグ", "13ピン電源プラグ"),
        ("pre-paid top-up card", "notpre-paid top-up card"),
        ("e-scooter", "note-scooter"),
        ("e-bicycle", "note-bicycle"),
        ("self-defense stick", "notself-defense stick"),
    ],
)
def test_v12_hyphenated_or_numeric_terms_are_excluded_due_to_current_contains_behavior(
    tmp_path,
    term,
    false_positive_title,
):
    risk_csv = RISK_CSV + (
        f"{term},REVIEW,controlled_goods_unverified,title,contains,shopee_policy,"
        "Synthetic boundary check,TRUE\n"
    )

    row = apply_guardrails(
        [candidate(title=false_positive_title)],
        write_dictionaries(tmp_path, risk_csv=risk_csv),
    )[0]

    assert row["guardrail_status"] == "REVIEW"
