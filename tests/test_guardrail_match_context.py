"""Decision-note excerpts retain the actual matched product evidence."""
from modules.guardrails import GuardrailMatch, GuardrailRule, _apply_matches_to_row, apply_guardrails
from modules.match_context import excerpt_at


def rule(term="試験語", *, field="title", risk="other", kind="keyword", note="Synthetic source"):
    return GuardrailRule(term, term.lower(), "BLOCK", risk, field, "contains",
                         "internal_rule", note, "synthetic.csv", 1, kind)


def test_excerpt_is_bounded_one_line_and_does_not_add_note_delimiters():
    value = "前" * 40 + "\n試験語|" + "後" * 40
    start = value.index("試験語")
    text = excerpt_at(value, start, start + 3)
    assert text.startswith("…") and text.endswith("…")
    assert len(text) == 45  # 20 + matched 3 + 20 + two ellipses.
    assert "\n" not in text and "|" not in text and "｜" in text


def test_legacy_note_keeps_source_and_quotes_only_the_matching_product_field():
    row = {"product_title": "前" * 40 + "試験語" + "後" * 40,
           "private_notes": "must not appear", "description": "must not appear"}
    result = _apply_matches_to_row(row, [GuardrailMatch(rule())])
    assert result["guardrail_status"] == "BLOCK"
    assert "Keyword matched: 試験語" in result["guardrail_note"]
    assert "Synthetic source" in result["guardrail_note"]
    assert "該当箇所[product_title]: 「…" + "前" * 20 + "試験語" + "後" * 20 + "…」" in result["guardrail_note"]
    assert "must not appear" not in result["guardrail_note"]


def test_context_does_not_choose_the_earlier_negated_medical_occurrence():
    row = {"description": "医薬品ではありません。" + "区切り" * 20 + "医薬品に該当します。"}
    matched = GuardrailMatch(rule("医薬品", risk="medical_or_therapeutic"), "description")
    result = _apply_matches_to_row(row, [matched])
    assert "該当箇所[description]" in result["guardrail_note"]
    assert "医薬品に該当します" in result["guardrail_note"]
    assert "医薬品ではありません" not in result["guardrail_note"]


def test_context_does_not_quote_a_harmless_occurrence_next_to_a_positive_hit():
    row = {"description": "アルコールフリー。" + "区切り" * 20 + "アルコール度数を表示。"}
    matched = GuardrailMatch(rule("アルコール", risk="alcohol"), "description")
    result = _apply_matches_to_row(row, [matched])
    assert "アルコール度数" in result["guardrail_note"]
    assert "アルコールフリー" not in result["guardrail_note"]


def test_precise_policy_context_is_kept_without_a_second_guess():
    note = "Policy source; 該当箇所[features]: 「actual ingredient section」"
    row = {"product_title": "試験語", "features": ["actual ingredient section"]}
    result = _apply_matches_to_row(row, [GuardrailMatch(rule(kind="policy", note=note), "features")])
    assert result["guardrail_note"].count("該当箇所[") == 1
    assert "actual ingredient section" in result["guardrail_note"]


def test_alias_without_literal_product_match_keeps_the_note_without_inventing_context():
    row = {"brand": "別表記", "description": "Canonical brand", "private_notes": "Canonical brand"}
    result = _apply_matches_to_row(row, [GuardrailMatch(rule("canonical brand", field="brand", kind="brand"))])
    assert "Brand matched" in result["guardrail_note"]
    assert "該当箇所[" not in result["guardrail_note"]


def test_v2_excerpt_uses_the_matching_ingredient_list_item_and_preserves_evidence():
    row = {"product_title": "Ordinary soap", "ingredients": ["unrelated", "水とGABAを配合した成分資料"]}
    result = apply_guardrails([row], marketplace="SG")[0]
    assert result["guardrail_status"] == "BLOCK"
    assert "ART-PH-GABA-FREEZE-OWNER-ATTESTATION-V1" in result["guardrail_note"]
    assert "該当箇所[ingredients]: 「水とgabaを配合した成分資料」" in result["guardrail_note"]
    assert "unrelated" not in result["guardrail_note"]


def test_community_note_retains_its_scope_and_actual_brand():
    result = apply_guardrails([{"product_title": "Ordinary item", "brand": "LEGO"}], marketplace="PH")[0]
    assert result["guardrail_status"] == "BLOCK"
    assert "Community NG matched: marketplace=PH" in result["guardrail_note"]
    assert "該当箇所[brand]: 「LEGO」" in result["guardrail_note"]


def test_matched_context_reaches_the_localized_gate_decision_memo():
    from modules.prelisting_gate_ui import build_prelisting_gate_preview_rows, localize_prelisting_gate_preview_rows
    from test_prelisting_sg_body_safety import case, run

    _, candidates, text = case("Ordinary case", description="収納用のbattery caseという表記")
    result = run(candidates, text)
    displayed = localize_prelisting_gate_preview_rows(build_prelisting_gate_preview_rows(result, final_eligibility="REVIEW"))
    assert "該当箇所[description]" in displayed[0]["判定メモ"]
    assert "battery" in displayed[0]["判定メモ"]
