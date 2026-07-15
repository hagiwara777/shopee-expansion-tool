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


def test_own_penalty_case_blocks_kaminomoto_asin_brand_title_and_ingredient(tmp_path):
    brand_csv = BRAND_CSV + """加美乃素,BLOCK,brand_medical_risk,brand,exact,own_penalty_case,Own penalty brand case,TRUE
Kaminomoto,BLOCK,brand_medical_risk,brand,exact,own_penalty_case,Own penalty brand case,TRUE
"""
    risk_csv = RISK_CSV + """B000FQTRS0,BLOCK,medical_or_therapeutic,asin,exact,own_penalty_case,Own delist ASIN case,TRUE
薬用加美乃素S-II,BLOCK,medical_or_therapeutic,all,contains,own_penalty_case,Own delist product case,TRUE
塩酸ジフェンヒドラミン,BLOCK,regulated_ingredient,all,contains,own_penalty_case,Own prohibited ingredient case,TRUE
"""
    dictionary_dir = write_dictionaries(tmp_path, brand_csv=brand_csv, risk_csv=risk_csv)

    rows = apply_guardrails(
        [
            candidate(asin="B000FQTRS0"),
            candidate(brand="Kaminomoto"),
            candidate(title="薬用加美乃素S-II 育毛剤"),
            candidate(title="塩酸ジフェンヒドラミン 配合"),
        ],
        dictionary_dir,
    )

    assert [row["guardrail_status"] for row in rows] == ["BLOCK", "BLOCK", "BLOCK", "BLOCK"]
    assert rows[0]["guardrail_matched_terms"] == "B000FQTRS0"
    assert rows[1]["guardrail_risk_category"] == "brand_medical_risk"
    assert rows[1]["guardrail_source"] == "own_penalty_case"
    assert rows[2]["guardrail_matched_terms"] == "薬用加美乃素S-II"
    assert rows[3]["guardrail_matched_terms"] == "塩酸ジフェンヒドラミン"

def test_asin_match_field_checks_candidate_asin_and_asin_columns(tmp_path):
    risk_csv = RISK_CSV + """B000FQTRS0,BLOCK,medical_or_therapeutic,asin,exact,own_penalty_case,Own delist ASIN case,TRUE
"""
    dictionary_dir = write_dictionaries(tmp_path, risk_csv=risk_csv)

    rows = apply_guardrails(
        [
            candidate(asin="B000FQTRS0"),
            {
                "seed_asin": "B07TSC47PH",
                "asin": "B000FQTRS0",
                "brand": "Other",
                "category": "Beauty",
                "product_title": "Normal item",
            },
        ],
        dictionary_dir,
    )

    assert [row["guardrail_status"] for row in rows] == ["BLOCK", "BLOCK"]
    assert [row["guardrail_matched_terms"] for row in rows] == ["B000FQTRS0", "B000FQTRS0"]


def test_medicated_and_hair_growth_terms_are_block_or_review(tmp_path):
    risk_csv = RISK_CSV + """医薬部外品,BLOCK,medical_or_therapeutic,all,contains,internal_rule,Japanese quasi-drug category is blocked for SG mass listing safety,TRUE
薬用,BLOCK,medical_or_therapeutic,all,contains,internal_rule,Medicated/quasi-drug expression risk,TRUE
quasi-drug,BLOCK,medical_or_therapeutic,all,contains,internal_rule,Japanese quasi-drug category risk,TRUE
有効成分,REVIEW,medical_or_therapeutic,all,contains,internal_rule,Active ingredient expression risk; review context,TRUE
発毛促進,BLOCK,medical_or_therapeutic,all,contains,internal_rule,Hair growth therapeutic claim risk,TRUE
育毛,BLOCK,medical_or_therapeutic,all,contains,internal_rule,Hair growth/scalp treatment claim risk,TRUE
hair growth,BLOCK,medical_or_therapeutic,all,contains,internal_rule,Hair growth therapeutic claim risk,TRUE
hair loss,BLOCK,medical_or_therapeutic,all,contains,internal_rule,Hair loss reversal or treatment claim risk,TRUE
"""
    dictionary_dir = write_dictionaries(tmp_path, risk_csv=risk_csv)

    rows = apply_guardrails(
        [
            candidate(title="医薬部外品 スキンケア"),
            candidate(title="薬用 ヘアトニック"),
            candidate(title="発毛促進 ローション"),
            candidate(title="育毛 トニック"),
            candidate(title="Active ingredient 有効成分"),
        ],
        dictionary_dir,
    )

    assert [row["guardrail_status"] for row in rows] == ["BLOCK", "BLOCK", "BLOCK", "BLOCK", "REVIEW"]
