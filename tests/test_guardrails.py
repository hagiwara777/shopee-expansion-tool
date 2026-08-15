import csv
from io import StringIO
from pathlib import Path

import pytest

import modules.guardrails as guardrails_module
from modules.export_csv import rows_to_csv
from modules.guardrails import (
    ALLOWED_RISK_CATEGORIES,
    GuardrailDictionaryError,
    apply_guardrails,
    filter_safe_rows,
    load_deterministic_block_rules_v2,
    load_guardrail_dictionaries,
    normalize_text,
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


PH_BRAND_CSV = """term,action,risk_category,match_field,match_type,source_type,note,enabled
"""
PH_RISK_CSV = """term,action,risk_category,match_field,match_type,source_type,note,enabled
PH review,REVIEW,other,title,contains,internal_rule,PH review rule,TRUE
"""
PH_RISK_KEYWORDS_PATH = Path(__file__).resolve().parents[1] / "guardrails" / "risk_keywords_ph.csv"
PH_PROHIBITED_BRANDS_PATH = Path(__file__).resolve().parents[1] / "guardrails" / "prohibited_brands_ph.csv"
PH_V2_RULESET_PATH = Path(__file__).resolve().parents[1] / "guardrails" / guardrails_module.V2_RULESET_FILE
PH_BLOCK_RULE_IDS = {
    *(f"PH-D{number:03d}" for number in range(1, 8)),
    *(f"PH-D{number:03d}" for number in range(8, 15)),
    *(f"PH-D{number:03d}" for number in range(19, 21)),
    *(f"PH-D{number:03d}" for number in range(59, 64)),
    *(f"PH-D{number:03d}" for number in range(66, 73)),
    *(f"PH-D{number:03d}" for number in range(73, 76)),
}


def write_ph_dictionaries(
    tmp_path,
    brand_csv=PH_BRAND_CSV,
    risk_csv=PH_RISK_CSV,
    v2_csv=None,
):
    dictionary_dir = tmp_path / "guardrails"
    dictionary_dir.mkdir(parents=True)
    (dictionary_dir / "prohibited_brands_ph.csv").write_text(brand_csv, encoding="utf-8")
    (dictionary_dir / "risk_keywords_ph.csv").write_text(risk_csv, encoding="utf-8")
    if v2_csv is None:
        v2_csv = PH_V2_RULESET_PATH.read_text(encoding="utf-8-sig")
    (dictionary_dir / guardrails_module.V2_RULESET_FILE).write_text(v2_csv, encoding="utf-8")
    return dictionary_dir


def ph_keyword_rows():
    with PH_RISK_KEYWORDS_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def ph_rule_id(row):
    return row["note"].split(";", 1)[0]


def ph_rules_with_action(action):
    return [row for row in ph_keyword_rows() if row["action"] == action]


def test_marketplace_defaults_to_existing_sg_dictionaries_and_normalizes_marketplace_names():
    default_dictionaries = load_guardrail_dictionaries()
    explicit_sg_dictionaries = load_guardrail_dictionaries(marketplace="SG")
    normalized_sg_dictionaries = load_guardrail_dictionaries(marketplace="  ｓｇ  ")
    with RISK_KEYWORDS_PATH.open("r", encoding="utf-8-sig", newline="") as csv_file:
        sg_keyword_rows = list(csv.DictReader(csv_file))

    assert len(default_dictionaries.brand_rules) == 60
    assert len(sg_keyword_rows) == 182
    assert len(default_dictionaries.keyword_rules) == 177
    assert default_dictionaries == explicit_sg_dictionaries == normalized_sg_dictionaries
    assert {rule.file_name for rule in default_dictionaries.brand_rules} == {"prohibited_brands_sg.csv"}
    assert {rule.file_name for rule in default_dictionaries.keyword_rules} == {"risk_keywords_sg.csv"}


def test_marketplace_ph_loads_only_ph_dictionaries_and_allows_zero_brand_rules():
    dictionaries = load_guardrail_dictionaries(marketplace="  ｐｈ ")

    assert dictionaries.brand_rules == []
    assert len(dictionaries.keyword_rules) == 89
    assert {rule.file_name for rule in dictionaries.keyword_rules} == {"risk_keywords_ph.csv"}


@pytest.mark.parametrize("marketplace", ["", "MY", "TH", "JP", None])
def test_unsupported_marketplace_fails_closed(marketplace):
    with pytest.raises(GuardrailDictionaryError, match="未対応の marketplace"):
        load_guardrail_dictionaries(marketplace=marketplace)


def test_missing_ph_dictionary_fails_closed_without_sg_fallback(tmp_path):
    dictionary_dir = write_dictionaries(tmp_path)

    with pytest.raises(GuardrailDictionaryError, match="prohibited_brands_ph.csv"):
        apply_guardrails([candidate(title="PH review")], dictionary_dir, marketplace="PH")


def test_ph_dictionary_files_use_utf8_bom_and_the_existing_eight_column_contract():
    assert PH_PROHIBITED_BRANDS_PATH.read_bytes().startswith(b"\xef\xbb\xbf")
    assert PH_RISK_KEYWORDS_PATH.read_bytes().startswith(b"\xef\xbb\xbf")

    expected_columns = {
        "term",
        "action",
        "risk_category",
        "match_field",
        "match_type",
        "source_type",
        "note",
        "enabled",
    }
    with PH_PROHIBITED_BRANDS_PATH.open("r", encoding="utf-8-sig", newline="") as brand_file:
        brand_reader = csv.DictReader(brand_file)
        brand_rows = list(brand_reader)
    with PH_RISK_KEYWORDS_PATH.open("r", encoding="utf-8-sig", newline="") as keyword_file:
        keyword_reader = csv.DictReader(keyword_file)
        keyword_rows = list(keyword_reader)

    assert brand_rows == []
    assert set(brand_reader.fieldnames or []) == expected_columns
    assert set(keyword_reader.fieldnames or []) == expected_columns
    assert all(set(row) == expected_columns for row in keyword_rows)


def test_ph_dictionary_contains_exactly_the_approved_rules_and_metadata():
    rows = ph_keyword_rows()
    terms = [normalize_text(row["term"]) for row in rows]
    block_rows = ph_rules_with_action("BLOCK")
    review_rows = ph_rules_with_action("REVIEW")

    assert len(rows) == 89
    assert len(block_rows) == 31
    assert len(review_rows) == 58
    assert len(terms) == len(set(terms))
    assert {ph_rule_id(row) for row in block_rows} == PH_BLOCK_RULE_IDS
    assert {ph_rule_id(row) for row in review_rows}.isdisjoint(PH_BLOCK_RULE_IDS)
    for row in rows:
        assert row["source_type"] in {"shopee_policy", "own_penalty_case", "internal_rule"}
        assert row["risk_category"] in ALLOWED_RISK_CATEGORIES
        assert row["match_field"] in {"asin", "brand", "title", "category", "all"}
        assert row["match_type"] in {"exact", "contains"}
        assert row["enabled"] == "TRUE"
        assert all(label in row["note"] for label in ("PH-D", "source:", "source date:", "regulatory position:", "company operation:"))


@pytest.mark.parametrize("rule", ph_rules_with_action("BLOCK"), ids=ph_rule_id)
def test_every_ph_block_rule_routes_its_own_term_to_block(rule):
    row = apply_guardrails(
        [candidate(asin=rule["term"] if rule["match_field"] == "asin" else "B000000001", title=rule["term"])],
        marketplace="PH",
    )[0]

    assert row["guardrail_status"] == "BLOCK"
    assert rule["term"] in row["guardrail_matched_terms"].split("|")


@pytest.mark.parametrize("rule", ph_rules_with_action("REVIEW"), ids=ph_rule_id)
def test_every_ph_review_rule_routes_its_own_term_to_review(rule):
    row = apply_guardrails([candidate(title=rule["term"])], marketplace="PH")[0]

    assert row["guardrail_status"] == "REVIEW"
    assert rule["term"] in row["guardrail_matched_terms"].split("|")


def test_ph_d001_is_an_asin_exact_rule_only():
    rows = apply_guardrails(
        [
            candidate(asin="B000FQTRS0"),
            candidate(asin="b000fqtrs0"),
            candidate(asin="B000FQTRS00"),
            candidate(asin="B000000001", title="B000FQTRS0"),
        ],
        marketplace="PH",
    )

    assert [row["guardrail_status"] for row in rows] == ["BLOCK", "BLOCK", "SAFE", "SAFE"]


def test_ph_normalization_boundary_contains_and_hyphen_behavior_match_the_existing_contract():
    rows = apply_guardrails(
        [
            candidate(title="ＰＯＷＥＲ　ＢＡＮＫ"),
            candidate(title="notpower bank"),
            candidate(title="これはスタンガン本体です"),
            candidate(title="notCOVID-19 test kit"),
        ],
        marketplace="PH",
    )

    assert [row["guardrail_status"] for row in rows] == ["BLOCK", "SAFE", "BLOCK", "BLOCK"]


def test_ph_multiple_matches_keep_evidence_and_block_wins_over_review_and_safe():
    rows = apply_guardrails(
        [
            candidate(title="処方薬 薬用"),
            candidate(title="ordinary household product"),
        ],
        marketplace="PH",
    )

    assert rows[0]["guardrail_status"] == "BLOCK"
    assert rows[0]["guardrail_matched_terms"] == "処方薬|薬用"
    assert "PH-D008" in rows[0]["guardrail_note"]
    assert "PH-D015" in rows[0]["guardrail_note"]
    assert rows[1]["guardrail_status"] == "SAFE"


def test_marketplace_isolation_uses_only_the_requested_dictionary():
    ph_only_rows = apply_guardrails([candidate(title="COVID-19 test kit")], marketplace="PH")
    sg_rows = apply_guardrails([candidate(title="COVID-19 test kit")], marketplace="SG")
    sg_brand_rows = apply_guardrails([candidate(brand="Biore", title="ordinary product")], marketplace="SG")
    ph_brand_rows = apply_guardrails([candidate(brand="Biore", title="ordinary product")], marketplace="PH")

    assert ph_only_rows[0]["guardrail_status"] == "BLOCK"
    assert sg_rows[0]["guardrail_status"] == "SAFE"
    assert sg_brand_rows[0]["guardrail_status"] == "BLOCK"
    assert ph_brand_rows[0]["guardrail_status"] == "SAFE"


@pytest.mark.parametrize(
    ("risk_csv", "error_match"),
    [
        ("""term,action,risk_category,match_field,match_type,source_type,note,enabled
invalid action,SAFE,other,title,contains,internal_rule,Invalid action,TRUE
""", "action"),
        ("""term,action,risk_category,match_field,match_type,source_type,note,enabled
invalid category,REVIEW,not_allowed,title,contains,internal_rule,Invalid category,TRUE
""", "risk_category"),
        ("""term,action,risk_category,match_field,match_type,source_type,note,enabled
invalid field,REVIEW,other,invalid,contains,internal_rule,Invalid field,TRUE
""", "match_field"),
        ("""term,action,risk_category,match_field,match_type,source_type,note,enabled
invalid type,REVIEW,other,title,regex,internal_rule,Invalid type,TRUE
""", "match_type"),
        ("""term,action,risk_category,match_field,match_type,source_type,note,enabled
invalid source,REVIEW,other,title,contains,not_allowed,Invalid source,TRUE
""", "source_type"),
    ],
)
def test_ph_dictionary_rejects_unapproved_contract_values(risk_csv, error_match, tmp_path):
    with pytest.raises(GuardrailDictionaryError, match=error_match):
        apply_guardrails([candidate()], write_ph_dictionaries(tmp_path, risk_csv=risk_csv), marketplace="PH")


def test_ph_dictionary_rejects_missing_required_column(tmp_path):
    missing_column_csv = """term,action,risk_category,match_field,match_type,source_type,note
PH rule,REVIEW,other,title,contains,internal_rule,Missing enabled
"""

    with pytest.raises(GuardrailDictionaryError, match="必須列"):
        apply_guardrails([candidate()], write_ph_dictionaries(tmp_path, risk_csv=missing_column_csv), marketplace="PH")


PHASE1_V2_BRAND_RULES = [
    ("PH-V2-BRAND-001", "グルマンディーズ"),
    ("PH-V2-BRAND-002", "Gourmandise"),
    ("PH-V2-BRAND-003", "OXO"),
    ("PH-V2-BRAND-004", "ZOJIRUSHI"),
    ("PH-V2-BRAND-005", "Schleich"),
    ("PH-V2-BRAND-006", "L'OREAL"),
    ("PH-V2-BRAND-007", "nivea"),
    ("PH-V2-BRAND-008", "LEGO"),
    ("PH-V2-BRAND-009", "Shu Uemura"),
    ("PH-V2-BRAND-010", "ロート製薬"),
    ("PH-V2-BRAND-011", "Endgame Gear"),
    ("PH-V2-BRAND-012", "エーザイ"),
    ("PH-V2-BRAND-013", "ゼンハイザー"),
]
V2_COLUMNS = [
    "schema_version",
    "rule_id",
    "scope",
    "fact_field",
    "operator",
    "value",
    "action",
    "risk_category",
    "source_type",
    "decision_ref",
    "evidence_ref",
    "note",
]


def v2_rule(**overrides):
    row = {
        "schema_version": guardrails_module.V2_RULESET_SCHEMA_VERSION,
        "rule_id": "PH-V2-TEST-001",
        "scope": "PH_BLOCK",
        "fact_field": "brand",
        "operator": "exact",
        "value": "Synthetic Brand",
        "action": "BLOCK",
        "risk_category": "community_report",
        "source_type": "community_report",
        "decision_ref": "DEC-0030",
        "evidence_ref": "OWNER_SOURCE_COMMUNITY_NG_LIST",
        "note": "Synthetic canonical test rule",
    }
    row.update(overrides)
    return row


def render_v2_rules(*rows, columns=V2_COLUMNS):
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return output.getvalue()


def test_production_v2_ruleset_contains_only_the_13_canonical_ph_brand_rules():
    rules = load_deterministic_block_rules_v2()

    assert [rule.rule_id for rule in rules] == [rule_id for rule_id, _ in PHASE1_V2_BRAND_RULES]
    assert [rule.value for rule in rules] == [brand for _, brand in PHASE1_V2_BRAND_RULES]
    assert len(rules) == 13
    assert sum(rule.scope == "COMMON_BLOCK" for rule in rules) == 0
    assert sum(rule.scope == "PH_BLOCK" for rule in rules) == 13
    assert {rule.schema_version for rule in rules} == {guardrails_module.V2_RULESET_SCHEMA_VERSION}
    assert all(rule.fact_field == "brand" for rule in rules)
    assert all(rule.operator == "exact" for rule in rules)
    assert all(rule.action == "BLOCK" for rule in rules)
    assert all(rule.risk_category == "community_report" for rule in rules)
    assert all(rule.source_type == "community_report" for rule in rules)
    assert all(rule.decision_ref == "DEC-0030" for rule in rules)
    assert all(rule.evidence_ref == "OWNER_SOURCE_COMMUNITY_NG_LIST" for rule in rules)
    assert "Bose" not in {rule.value for rule in rules}


@pytest.mark.parametrize(("rule_id", "brand"), PHASE1_V2_BRAND_RULES, ids=[item[0] for item in PHASE1_V2_BRAND_RULES])
def test_every_phase1_v2_brand_rule_blocks_ph_by_normalized_exact(rule_id, brand):
    row = apply_guardrails([candidate(brand=brand)], marketplace="PH")[0]

    assert row["guardrail_status"] == "BLOCK"
    assert row["guardrail_risk_category"] == "community_report"
    assert row["guardrail_matched_terms"] == brand
    assert row["guardrail_source"] == "community_report"
    assert f"V2 Rule matched: {rule_id}" in row["guardrail_note"]
    assert "No guardrail dictionary match" not in row["guardrail_note"]


@pytest.mark.parametrize("brand", ["  ｌｅｇｏ  ", "SHU   UEMURA", "ｏｘｏ"])
def test_phase1_v2_brand_exact_uses_nfkc_case_trim_and_space_normalization(brand):
    row = apply_guardrails([candidate(brand=brand)], marketplace="PH")[0]

    assert row["guardrail_status"] == "BLOCK"
    assert "V2 Rule matched" in row["guardrail_note"]


def test_phase1_v2_never_matches_contains_title_blank_or_unrelated_brand():
    rows = apply_guardrails(
        [
            candidate(brand="LEGO Store"),
            candidate(brand="Other", title="LEGO building set"),
            candidate(brand="", title="ordinary product"),
            candidate(brand="Other", title="ordinary product"),
        ],
        marketplace="PH",
    )

    assert [row["guardrail_status"] for row in rows] == ["SAFE", "SAFE", "SAFE", "SAFE"]
    assert all("V2 Rule matched" not in row["guardrail_note"] for row in rows)


def test_phase1_v2_no_match_preserves_complete_v1_output_order_and_count():
    rows = [
        candidate(brand="Other", title="ordinary product"),
        candidate(brand="Other", title="medicated cleanser"),
        candidate(brand="Other", title="処方薬"),
    ]
    dictionaries = load_guardrail_dictionaries(marketplace="PH")
    v1_only = [
        guardrails_module._apply_matches_to_row(
            row,
            guardrails_module._find_matches(row, dictionaries),
        )
        for row in rows
    ]

    combined = apply_guardrails(rows, marketplace="PH")

    assert combined == v1_only
    assert len(combined) == len(rows)
    assert [row["product_title"] for row in combined] == [row["product_title"] for row in rows]


def test_phase1_v2_block_veto_composes_after_v1_without_losing_v1_audit_evidence():
    safe_v2 = apply_guardrails(
        [candidate(brand="LEGO", title="ordinary product")],
        marketplace="PH",
    )[0]
    review_v2 = apply_guardrails(
        [candidate(brand="LEGO", title="medicated cleanser")],
        marketplace="PH",
    )[0]
    block_v2 = apply_guardrails(
        [candidate(brand="LEGO", title="処方薬")],
        marketplace="PH",
    )[0]

    assert safe_v2["guardrail_status"] == "BLOCK"
    assert safe_v2["guardrail_matched_terms"] == "LEGO"
    assert review_v2["guardrail_status"] == "BLOCK"
    assert review_v2["guardrail_matched_terms"] == "medicated|LEGO"
    assert review_v2["guardrail_source"] == "internal_rule|community_report"
    assert "PH-D018" in review_v2["guardrail_note"]
    assert "PH-V2-BRAND-008" in review_v2["guardrail_note"]
    assert block_v2["guardrail_status"] == "BLOCK"
    assert block_v2["guardrail_matched_terms"] == "処方薬|LEGO"
    assert block_v2["guardrail_source"] == "shopee_policy|community_report"
    assert "PH-D008" in block_v2["guardrail_note"]
    assert "PH-V2-BRAND-008" in block_v2["guardrail_note"]


def test_phase1_v2_is_not_enabled_for_sg_even_when_v2_ruleset_is_missing(tmp_path):
    dictionary_dir = write_dictionaries(tmp_path)

    row = apply_guardrails(
        [candidate(brand="OXO", title="ordinary product")],
        dictionary_dir,
        marketplace="SG",
    )[0]

    assert row["guardrail_status"] == "SAFE"
    assert "V2 Rule matched" not in row["guardrail_note"]


@pytest.mark.parametrize(
    ("overrides", "error_match"),
    [
        ({"schema_version": "UNKNOWN"}, "schema_version"),
        ({"rule_id": ""}, "rule_id"),
        ({"scope": "SG_BLOCK"}, "scope"),
        ({"fact_field": "title"}, "fact_field"),
        ({"operator": "contains"}, "operator"),
        ({"action": "REVIEW"}, "action"),
        ({"value": ""}, "value"),
        ({"risk_category": "other"}, "risk_category"),
        ({"source_type": "internal_rule"}, "source_type"),
        ({"decision_ref": "DEC-0029"}, "decision_ref"),
        ({"evidence_ref": "UNKNOWN"}, "evidence_ref"),
        ({"note": ""}, "note"),
    ],
)
def test_v2_ruleset_contract_errors_fail_closed(tmp_path, overrides, error_match):
    dictionary_dir = write_ph_dictionaries(
        tmp_path,
        v2_csv=render_v2_rules(v2_rule(**overrides)),
    )

    with pytest.raises(GuardrailDictionaryError, match=error_match):
        apply_guardrails([candidate()], dictionary_dir, marketplace="PH")


def test_v2_ruleset_missing_required_column_fails_closed(tmp_path):
    columns = [column for column in V2_COLUMNS if column != "evidence_ref"]
    dictionary_dir = write_ph_dictionaries(
        tmp_path,
        v2_csv=render_v2_rules(v2_rule(), columns=columns),
    )

    with pytest.raises(GuardrailDictionaryError, match="V2必須列"):
        apply_guardrails([candidate()], dictionary_dir, marketplace="PH")


def test_v2_duplicate_rule_id_and_semantic_duplicate_fail_closed(tmp_path):
    duplicate_id_dir = write_ph_dictionaries(
        tmp_path / "duplicate-id",
        v2_csv=render_v2_rules(
            v2_rule(rule_id="PH-V2-DUPLICATE", value="First Brand"),
            v2_rule(rule_id="PH-V2-DUPLICATE", value="Second Brand"),
        ),
    )
    semantic_duplicate_dir = write_ph_dictionaries(
        tmp_path / "semantic-duplicate",
        v2_csv=render_v2_rules(
            v2_rule(rule_id="PH-V2-SEMANTIC-001", value="LEGO"),
            v2_rule(rule_id="PH-V2-SEMANTIC-002", value="  lego  "),
        ),
    )

    with pytest.raises(GuardrailDictionaryError, match="duplicate rule_id"):
        apply_guardrails([candidate()], duplicate_id_dir, marketplace="PH")
    with pytest.raises(GuardrailDictionaryError, match="semantic duplicate"):
        apply_guardrails([candidate()], semantic_duplicate_dir, marketplace="PH")


def test_v2_missing_empty_and_malformed_rulesets_fail_closed(tmp_path):
    missing_dir = write_ph_dictionaries(tmp_path / "missing")
    (missing_dir / guardrails_module.V2_RULESET_FILE).unlink()
    empty_dir = write_ph_dictionaries(
        tmp_path / "empty",
        v2_csv=render_v2_rules(),
    )
    malformed_dir = write_ph_dictionaries(
        tmp_path / "malformed",
        v2_csv=",".join(V2_COLUMNS) + '\n"unterminated',
    )

    with pytest.raises(GuardrailDictionaryError, match="見つかりません"):
        apply_guardrails([candidate()], missing_dir, marketplace="PH")
    with pytest.raises(GuardrailDictionaryError, match="active V2 rule"):
        apply_guardrails([candidate()], empty_dir, marketplace="PH")
    with pytest.raises(GuardrailDictionaryError, match="V2 CSV形式"):
        apply_guardrails([candidate()], malformed_dir, marketplace="PH")


def test_v2_common_and_ph_scopes_form_a_union_for_ph(tmp_path):
    dictionary_dir = write_ph_dictionaries(
        tmp_path,
        v2_csv=render_v2_rules(
            v2_rule(rule_id="COMMON-V2-BRAND-001", scope="COMMON_BLOCK", value="Common Brand"),
            v2_rule(rule_id="PH-V2-BRAND-TEST", scope="PH_BLOCK", value="PH Brand"),
        ),
    )

    rows = apply_guardrails(
        [candidate(brand="Common Brand"), candidate(brand="PH Brand")],
        dictionary_dir,
        marketplace="PH",
    )

    assert [row["guardrail_status"] for row in rows] == ["BLOCK", "BLOCK"]
    assert "COMMON-V2-BRAND-001" in rows[0]["guardrail_note"]
    assert "PH-V2-BRAND-TEST" in rows[1]["guardrail_note"]
