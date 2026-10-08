from copy import deepcopy
from dataclasses import asdict, replace
import json
import hashlib
from pathlib import Path
import socket

import pytest

from modules.guardrails import apply_guardrails
from modules.product_text_safety import ProductTextSafetyError
from modules.safety_shadow import classify_product, fact_from_saved_product
from scripts.safety_shadow_report import build_report, main, render_markdown

FIXTURE = Path(__file__).parent / "fixtures/safety_shadow/synthetic_products.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["products"]


def fact(product, fmt="keepa_response"):
    return fact_from_saved_product(product, source_format=fmt, evidence_ref="SYNTHETIC_TEST")


@pytest.mark.parametrize("product", CASES, ids=lambda p: p["asin"])
def test_independently_written_synthetic_expectations(product):
    signals = classify_product(fact(product))
    assert {s.family: s.classification for s in signals} == product["expected"]
    assert any(s.bundle_candidate for s in signals) == product.get("expected_bundle", False)
    assert all(s.matched_evidence and s.rule_version and s.evaluator_version for s in signals)
    assert all(e.evidence_source for s in signals for e in s.matched_evidence)


def test_category_ids_require_own_product_and_jp_domain():
    product = {"asin":"B0SYN00025", "title":"", "domainId":5, "categories":[490276011]}
    own = fact(product)
    assert classify_product(own)[0].classification == "BODY_CANDIDATE"
    for altered in (replace(own, domain_id=None), replace(own, domain_id=1),
                    replace(own, category_origin="SEED_FALLBACK"), replace(own, category_origin="MISSING")):
        assert classify_product(altered) == ()


def test_categories_all_ids_add_evidence_without_ancestor_mapping():
    product = {"asin":"B0SYN00025", "title":"", "domainId":5,
               "categoryTree":[{"catId":999999, "name":"Unverified leaf"}], "categories":[13945801]}
    s = classify_product(fact(product))[0]
    assert s.classification == "ACCESSORY_CANDIDATE"
    assert s.matched_evidence[0].field == "categories"
    assert classify_product(fact(product), include_categories=False) == ()


def test_cache_capture_status_and_missing_fields_are_not_invented():
    product = {"asin":"B0SYN00025", "title":"", "features":["Kitchen knife"],
               "category_tree":[{"catId":490276011, "name":"Knife"}]}
    old = fact(product, "cache_snapshot")
    assert old.text.capture_status == "NOT_CAPTURED"
    assert old.domain_id is None and old.categories == () and old.last_update is None
    assert classify_product(old) == ()
    product.update(product_text_safety_payload_version="PRODUCT_TEXT_SAFETY_PAYLOAD_V1",
                   product_text_safety_capture_status="CAPTURED")
    captured = fact(product, "cache_snapshot")
    assert captured.text.capture_status == "CAPTURED"
    assert classify_product(captured)[0].classification == "BODY_CANDIDATE"


def test_ablation_can_reveal_category_conflict_and_explicit_bundle():
    conflict = fact(CASES[5])
    assert classify_product(conflict, include_categories=False)[0].classification == "ACCESSORY_CANDIDATE"
    assert classify_product(conflict)[0].classification == "CONFLICT"
    bundle = fact(CASES[4])
    assert classify_product(bundle, include_text=False)[0].classification == "ACCESSORY_CANDIDATE"
    assert classify_product(bundle)[0].bundle_candidate


def test_shadow_does_not_mutate_facts_or_release_ph_sg_safety():
    facts = [fact(p) for p in CASES]
    original = deepcopy([asdict(f) for f in facts])
    rows = [f.guardrail_input() for f in facts]
    baseline = {m: apply_guardrails(rows, marketplace=m) for m in ("PH", "SG")}
    for f in facts:
        classify_product(f)
    assert [asdict(f) for f in facts] == original
    assert {m: apply_guardrails(rows, marketplace=m) for m in baseline} == baseline
    assert baseline["PH"][1]["guardrail_status"] == "BLOCK"
    assert baseline["SG"][15]["guardrail_status"] == "REVIEW"
    assert baseline["PH"][14]["guardrail_status"] == "SAFE"


@pytest.mark.parametrize("changes", [
    {"asin":"bad"}, {"domainId":True}, {"categories":[True]},
    {"categoryTree":[{"catId":0,"name":"bad"}]}, {"features":[{}]},
    {"category_origin":"INFERRED"}, {"lastUpdate":"today"},
])
def test_invalid_saved_fact_fails_offline_without_new_sales_decision(changes):
    with pytest.raises((ValueError, ProductTextSafetyError)):
        fact({"asin":"B0SYN00025", "title":"Contact lens", **changes})


@pytest.mark.parametrize("fmt,tree_key", [("keepa_response", "categoryTree"), ("cache_snapshot", "category_tree")])
@pytest.mark.parametrize("field", ["tree", "categories"])
@pytest.mark.parametrize("invalid", [{}, 0, False, ""])
def test_falsey_malformed_categories_are_not_missing(fmt, tree_key, field, invalid):
    key = tree_key if field == "tree" else field
    with pytest.raises(ValueError, match="INVALID_CATEGORY_FACT"):
        fact({"asin":"B0SYN00025", "title":"Knife", key:invalid}, fmt)


@pytest.mark.parametrize("field", ["title", "brand", "type"])
@pytest.mark.parametrize("invalid", [{}, 0, False, []])
def test_falsey_malformed_identity_and_audit_type_are_rejected(field, invalid):
    with pytest.raises(ValueError, match="INVALID_IDENTITY_TEXT|INVALID_TYPE"):
        fact({"asin":"B0SYN00025", field:invalid})


@pytest.mark.parametrize("invalid", [{}, 0, False, []])
def test_malformed_capture_time_is_not_replaced_by_envelope_time(invalid):
    with pytest.raises(ValueError, match="INVALID_CAPTURE_TIME"):
        fact_from_saved_product({"asin":"B0SYN00025", "fetched_at":invalid},
                                source_format="keepa_response", evidence_ref="SYNTHETIC_TEST",
                                fetched_at="2026-10-08T00:00:00Z")


@pytest.mark.parametrize("fmt,tree_key", [("keepa_response", "categoryTree"), ("cache_snapshot", "category_tree")])
def test_null_optional_fields_remain_compatible_and_not_invented(fmt, tree_key):
    empty = fact({"asin":"B0SYN00025"}, fmt)
    nulls = fact({"asin":"B0SYN00025", tree_key:None, "categories":None,
                  "title":None, "brand":None, "type":None, "fetched_at":None}, fmt)
    assert empty.category_origin == nulls.category_origin == "MISSING"
    assert empty.category_tree == nulls.category_tree == ()
    assert empty.categories == nulls.categories == ()
    assert empty.title == nulls.title == empty.brand == nulls.brand == ""
    assert empty.fetched_at == nulls.fetched_at == empty.keepa_type == nulls.keepa_type == ""
    assert empty.categories_capture_status == "NOT_CAPTURED"
    assert nulls.categories_capture_status == "NOT_AVAILABLE"
    assert classify_product(empty) == classify_product(nulls) == ()


def test_report_is_offline_binds_evidence_and_separates_baseline(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("Network forbidden")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    report = build_report([FIXTURE], evidence_kind="SYNTHETIC", source_format="keepa_response")
    assert report["baseline_unchanged"] and report["business_api_calls"] == 0
    assert report["evidence_kind_declared"] == "SYNTHETIC"
    assert report["inputs"][0]["evidence_ref"].startswith("sha256:")
    community_path = FIXTURE.parents[3] / "modules/community_ng.py"
    assert report["code_and_asset_sha256"]["modules/community_ng.py"] == hashlib.sha256(community_path.read_bytes()).hexdigest()
    assert set(report["products"][0]["guardrail_baseline"]) == {"PH", "SG"}
    assert len(report["variant_summaries"]) == 3
    assert report["products"][1]["investigation_candidates"][0]["kind"] == "BLOCK_WITH_ACCESSORY_SIGNAL"
    assert "OUTSIDE\\_TARGET\\_FAMILIES" in render_markdown(report)


def test_report_rejects_community_loader_binding_drift(monkeypatch):
    from scripts import safety_shadow_report as reporter
    original = reporter._bindings
    calls = 0
    def observed_bindings():
        nonlocal calls
        values = original()
        calls += 1
        if calls > 1:
            values["modules/community_ng.py"] = "0" * 64
        return values
    monkeypatch.setattr(reporter, "_bindings", observed_bindings)
    with pytest.raises(ValueError, match="BASELINE_OR_INPUT_CHANGED"):
        reporter.build_report([FIXTURE], evidence_kind="SYNTHETIC", source_format="keepa_response")


def test_labels_are_bound_and_not_generated_from_classifier(tmp_path):
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({"label_basis":"SYNTHETIC_EXPECTATION", "labels":[
        {"asin":p["asin"], "family":family, "classification":expected}
        for p in CASES for family, expected in p["expected"].items()
    ]}), encoding="utf-8")
    report = build_report([FIXTURE], evidence_kind="SYNTHETIC", source_format="keepa_response", labels_path=labels)
    full = report["variant_summaries"]["TITLE_TEXT_AND_OWN_CATEGORY"]
    assert full["label_agreements"] == full["labeled_family_cases"] == 21
    labels.write_text(json.dumps({"label_basis":"METADATA_OBSERVATION","labels":[]}), encoding="utf-8")
    with pytest.raises(ValueError, match="LABEL_BASIS"):
        build_report([FIXTURE], evidence_kind="SYNTHETIC", source_format="keepa_response", labels_path=labels)


def test_duplicate_asin_and_evidence_kind_mismatch_are_rejected():
    with pytest.raises(ValueError, match="DUPLICATE_ASIN"):
        build_report([FIXTURE, FIXTURE], evidence_kind="SYNTHETIC", source_format="keepa_response")
    with pytest.raises(ValueError, match="MIXED_EVIDENCE_KIND"):
        build_report([FIXTURE], evidence_kind="SAVED_PRODUCT", source_format="keepa_response")


def test_cli_keeps_input_bytes_and_refuses_overwrite(tmp_path):
    source = FIXTURE.read_bytes()
    output = tmp_path / "report"
    args = ["--evidence",str(FIXTURE),"--evidence-kind","SYNTHETIC",
            "--source-format","keepa_response","--output-dir",str(output)]
    assert main(args) == 0
    saved = (output / "report.json").read_bytes()
    assert main(args) == 2
    assert (output / "report.json").read_bytes() == saved and FIXTURE.read_bytes() == source


def test_shadow_only_connected_through_read_only_comparison():
    root = FIXTURE.parents[3]
    comparison_paths = {"safety_shadow.py", "safety_shadow_comparison.py", "safety_shadow_comparison_ui.py", "app.py"}
    for path in list((root / "modules").glob("*.py")) + list(root.glob("app*.py")):
        if path.name not in comparison_paths:
            assert "import safety_shadow" not in path.read_text(encoding="utf-8")
            assert "from modules.safety_shadow" not in path.read_text(encoding="utf-8")
    assert "from modules.safety_shadow import" not in (root / "app.py").read_text(encoding="utf-8")


def test_product_title_does_not_inject_markdown_table_or_html():
    report = build_report([FIXTURE], evidence_kind="SYNTHETIC", source_format="keepa_response")
    report["products"][0]["title"] = '<img src=x> [link](https://invalid.example) | row\nnext'
    rendered = render_markdown(report)
    assert '<img' not in rendered and '&lt;img' in rendered
    assert '\\[link\\]' in rendered and '\\| row next' in rendered


def test_evidence_excerpt_keeps_match_in_long_product_text():
    product = {"asin":"B0SYN00025", "title":"", "features":["Detail " * 100 + "Kitchen knife"]}
    evidence = classify_product(fact(product))[0].matched_evidence
    assert any(e.field == "features" and "knife" in e.excerpt for e in evidence)


def test_report_distinguishes_role_changes_from_extra_evidence(tmp_path):
    source = tmp_path / "three-cases.json"
    source.write_text(json.dumps({"evidence_kind":"SYNTHETIC", "products":[
        CASES[0], CASES[4], CASES[5]
    ]}), encoding="utf-8")
    report = build_report([source], evidence_kind="SYNTHETIC", source_format="keepa_response")
    assert report["schema_version"] == "SAFETY_SHADOW_REPORT_V2"
    text_delta = report["variant_changes"]["TITLE_ONLY_TO_TITLE_AND_TEXT"]
    category_delta = report["variant_changes"]["TITLE_AND_TEXT_TO_TITLE_TEXT_AND_OWN_CATEGORY"]
    assert text_delta["changed_products"] == text_delta["changed_family_cases"] == 1
    assert category_delta["changed_products"] == category_delta["changed_family_cases"] == 1
    assert text_delta["cases"][0]["asin"] == CASES[4]["asin"]
    assert category_delta["cases"][0]["asin"] == CASES[5]["asin"]
    assert category_delta["cases"][0]["after"][0] == "CONFLICT"
    assert all(c["asin"] != CASES[0]["asin"] for d in report["variant_changes"].values() for c in d["cases"])
    assert report["baseline_unchanged"] and report["business_api_calls"] == 0


def test_investigation_groups_explain_existing_stops_without_new_review(tmp_path):
    source = tmp_path / "grouped-stops.json"
    source.write_text(json.dumps({"evidence_kind":"SYNTHETIC", "products":[
        CASES[1], {**CASES[1],"asin":"B0SYN00025"}, CASES[15], CASES[14]
    ]}), encoding="utf-8")
    report = build_report([source], evidence_kind="SYNTHETIC", source_format="keepa_response")
    expected = {
        ("PH","KNIFE","BLOCK_WITH_ACCESSORY_SIGNAL","kitchen knife","internal_rule"):2,
        ("PH","CONTACT_LENS","REVIEW_WITH_ACCESSORY_SIGNAL","contact lenses","shopee_policy"):1,
        ("PH","CONTACT_LENS","SAFE_WITH_BODY_SIGNAL","",""):1,
        ("SG","CONTACT_LENS","REVIEW_WITH_ACCESSORY_SIGNAL","contact lenses","shopee_policy"):1,
        ("SG","CONTACT_LENS","REVIEW_WITH_BODY_SIGNAL","contact lens","shopee_policy"):1,
    }
    for product in report["products"]:
        for observation in product["investigation_candidates"]:
            assert any("本体" in q for q in observation["confirmation_questions"])
            assert any("解除しない" in q for q in observation["confirmation_questions"])
    actual = {(g["marketplace"],g["family"],g["kind"],g["matched_terms"],g["guardrail_source"]):g["product_count"]
              for g in report["investigation_groups"]}
    assert actual == expected
    report["investigation_groups"][0]["matched_terms"] = '<script>bad</script> | [link](https://invalid.example)'
    rendered = render_markdown(report)
    assert '<script>' not in rendered and '\\[link\\]' in rendered and '\\| ' in rendered
    assert "変化件数は精度改善件数ではありません" in rendered


def test_variant_changes_include_bundle_only_and_new_family_signals():
    from modules.safety_shadow import FamilySignal
    from scripts.safety_shadow_report import _variant_changes
    body = FamilySignal("KNIFE", "BODY_CANDIDATE", False, (), "SYNTHETIC")
    variants = {"TITLE_ONLY":{"A":(body,),"B":()},
                "TITLE_AND_TEXT":{"A":(replace(body,bundle_candidate=True),),"B":()},
                "TITLE_TEXT_AND_OWN_CATEGORY":{"A":(replace(body,bundle_candidate=True),),"B":(body,)}}
    changes = _variant_changes(variants, ["A","B"])
    assert changes["TITLE_ONLY_TO_TITLE_AND_TEXT"]["cases"][0]["before"] == ("BODY_CANDIDATE",False)
    assert changes["TITLE_ONLY_TO_TITLE_AND_TEXT"]["cases"][0]["after"] == ("BODY_CANDIDATE",True)
    assert changes["TITLE_AND_TEXT_TO_TITLE_TEXT_AND_OWN_CATEGORY"]["cases"][0]["before"] is None


@pytest.mark.parametrize("product,expected", [
    ({"title":"1DAY CLEAR 30枚 コンタクト BC8.6", "categories":[2356869051]}, "BODY_CANDIDATE"),
    ({"title":"コンタクトケース カラコン適用", "categories":[362602011]}, "ACCESSORY_CANDIDATE"),
    ({"title":"コンタクトケア用品 310ml", "categories":[362594011]}, "ACCESSORY_CANDIDATE"),
    ({"title":"Contact lens case", "categories":[2356869051]}, "CONFLICT"),
    ({"title":"Contact lenses", "categories":[362602011]}, "CONFLICT"),
    ({"title":"Contact lenses", "categories":[2356869051,362602011]}, "CONFLICT"),
    ({"title":"Contact lens case", "features":["Contact lenses included"],
      "categories":[2356869051,362602011]}, "BODY_CANDIDATE"),
    ({"title":"Contact lens case", "features":["Lenses not included"],
      "categories":[2356869051]}, "CONFLICT"),
    ({"title":"コンタクトレンズと眼鏡の科学",
      "categoryTree":[{"catId":465392,"name":"本"},{"catId":492192,"name":"科学読み物"}]}, "UNKNOWN"),
    ({"title":"Contact lenses", "categories":[2356869051],
      "categoryTree":[{"catId":465392,"name":"本"},{"catId":492192,"name":"科学読み物"}]}, "CONFLICT"),
])
def test_contact_metadata_roles_and_book_context_are_hypotheses(product, expected):
    saved = {"asin":"B0SYN00025", "domainId":5, **product}
    result = classify_product(fact(saved))
    assert result[0].classification == expected
    assert result[0].family == "CONTACT_LENS"
    assert result[0].rule_version == "CONTACT_LENS_JP_SHADOW_V2"
    assert result[0].evaluator_version == "SAFETY_SHADOW_V3"


@pytest.mark.parametrize("changes", [
    {"domainId":None}, {"domainId":1}, {"category_origin":"SEED_FALLBACK"},
    {"category_origin":"MISSING"},
])
def test_contact_categories_cannot_use_foreign_unknown_or_seed_facts(changes):
    saved = {"asin":"B0SYN00025", "title":"", "domainId":5,
             "categories":[2356869051], **changes}
    assert classify_product(fact(saved)) == ()


def test_contact_type_ancestor_and_category_names_do_not_supply_body_authority():
    saved = {"asin":"B0SYN00025", "title":"", "domainId":5, "type":"CONTACT_LENSES",
             "categoryTree":[{"catId":2356869051,"name":"ソフトコンタクトレンズ"},
                             {"catId":999999,"name":"Contact lenses"}]}
    assert classify_product(fact(saved)) == ()
    saved["categoryTree"] = [{"catId":999999,"name":"ソフトコンタクトレンズ"}]
    assert classify_product(fact(saved)) == ()


def test_book_context_requires_own_jp_root_and_does_not_release_guardrail():
    saved = {"asin":"B0SYN00025", "title":"コンタクトレンズ診療", "domainId":5,
             "categoryTree":[{"catId":465392,"name":"本"},{"catId":720820,"name":"眼科学"}]}
    own = fact(saved)
    assert classify_product(own)[0].classification == "UNKNOWN"
    assert classify_product(own, include_categories=False)[0].classification == "BODY_CANDIDATE"
    for altered in (replace(own, domain_id=None), replace(own, domain_id=1),
                    replace(own, category_origin="SEED_FALLBACK")):
        assert classify_product(altered)[0].classification == "BODY_CANDIDATE"
    before = apply_guardrails([own.guardrail_input()], marketplace="SG")
    classify_product(own)
    assert apply_guardrails([own.guardrail_input()], marketplace="SG") == before
    assert before[0]["guardrail_status"] == "REVIEW"


@pytest.mark.parametrize("family,body,accessory,paired_title", [
    ("KNIFE", "a knife", "Knife case", "Kitchen knife and sharpener set"),
    ("CONTACT_LENS", "contact lenses", "Contact lens case", "Contact lenses and lens case set"),
])
@pytest.mark.parametrize("case,expected,bundle", [
    ("mixed_set", "BODY_CANDIDATE", True),
    ("picture_only", "ACCESSORY_CANDIDATE", False),
    ("guide", "UNKNOWN", False),
    ("usage", "ACCESSORY_CANDIDATE", False),
    ("included", "BODY_CANDIDATE", True),
    ("absent", "ACCESSORY_CANDIDATE", False),
    ("picture_uncertain", "CONFLICT", False),
    ("opposing_sentences", "CONFLICT", True),
])
def test_common_bundle_reference_and_guide_boundaries(family, body, accessory, paired_title, case, expected, bundle):
    title = paired_title if case == "mixed_set" else accessory
    features = []
    if case == "picture_only":
        features = [f"Includes {body} in the photographs, which is not supplied."]
    elif case == "guide":
        title = f"{body} buying guide"
        features = [f"Instructions for using {body}."]
    elif case == "usage":
        features = [f"Insert {body} before closing."]
    elif case == "included":
        features = [f"Includes {body}."]
    elif case == "absent":
        features = [f"Includes {body} in photographs only; {body} not included."]
    elif case == "picture_uncertain":
        features = [f"Includes {body} in the photographs."]
    elif case == "opposing_sentences":
        features = [f"Includes {body}. {body} not supplied."]
    saved = {"asin":"B0SYN00025", "title":title, "features":features}
    own = fact(saved)
    before = {m:apply_guardrails([own.guardrail_input()], marketplace=m) for m in ("PH", "SG")}
    signal = next(s for s in classify_product(own) if s.family == family)
    assert (signal.classification, signal.bundle_candidate) == (expected, bundle)
    assert signal.matched_evidence
    assert {m:apply_guardrails([own.guardrail_input()], marketplace=m) for m in before} == before


@pytest.mark.parametrize("title", ["Knife sharpener and knife case set", "Contact lens case and lens holder set"])
def test_accessory_sets_do_not_invent_separate_body(title):
    signal = classify_product(fact({"asin":"B0SYN00025", "title":title}))[0]
    assert signal.classification == "ACCESSORY_CANDIDATE" and not signal.bundle_candidate


def test_guide_body_category_is_conflict_and_normal_decimal_is_not_a_clause():
    saved = {"asin":"B0SYN00025", "title":"Contact lens buying guide", "domainId":5,
             "categories":[2356869051]}
    assert classify_product(fact(saved))[0].classification == "CONFLICT"
    from modules.safety_shadow import _clauses
    assert _clauses("BC 8.6. Includes contact lenses.") == ("BC 8.6", " Includes contact lenses")


@pytest.mark.parametrize("title", ["Kitchen knife with instruction guide", "Contact lenses with instruction guide"])
def test_physical_body_with_instructions_is_not_mistaken_for_guide(title):
    signal = classify_product(fact({"asin":"B0SYN00025", "title":title}))[0]
    assert signal.classification == "BODY_CANDIDATE"


@pytest.mark.parametrize("title", ["Knife sharpener buying guide", "Contact lens case buying guide"])
def test_guide_mentions_accessory_without_selling_it(title):
    signal = classify_product(fact({"asin":"B0SYN00025", "title":title}))[0]
    assert signal.classification == "UNKNOWN"
