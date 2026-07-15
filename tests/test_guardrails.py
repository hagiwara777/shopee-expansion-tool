import csv
from io import StringIO

import pytest

from modules.export_csv import rows_to_csv
from modules.guardrails import (
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
