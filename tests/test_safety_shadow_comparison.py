"""Offline comparison acceptance, with real Gate decisions and synthetic Facts."""
from copy import deepcopy
from dataclasses import asdict, replace
import csv
from io import StringIO
import hashlib
import json
import socket

import pytest

from modules.prelisting_candidate_csv import (
    PRELISTING_CANDIDATE_COLUMNS, parse_prelisting_candidate_csv, rows_to_prelisting_candidate_csv,
)
from modules.prelisting_gate import evaluate_prelisting_gate
from modules.prelisting_gate_csv import build_prelisting_gate_exports
from modules.prelisting_sg_body_safety import record_body_confirmation
from modules.product_text_safety import parse_product_text_safety_sidecar, rows_to_product_text_safety_sidecar
from modules.safety_shadow import classify_product, fact_from_saved_product
from modules.safety_shadow_comparison import compare_saved_shadow, comparison_context
from test_product_text_safety import candidate
from test_prelisting_gate import inventory


def setup_case(title="Kitchen knife case", market="SG", *, origin="OWN_PRODUCT", body=None,
               source_type="EXPANSION", description="Knife not included", brand="Synthetic Brand"):
    row = replace(candidate(), product_title=title, category="Kitchen > Accessories", brand=brand)
    if source_type == "RESOLVER":
        row = replace(row, source_type="RESOLVER", source_asin="", source_id="R0001", source_status="FOUND",
                      source_verification="KEEPA_VERIFIED", source="asin_resolver_keepa_verified")
    product = dict(asin=row.candidate_asin, title=row.product_title, brand=row.brand,
                   fetched_at=row.fetched_at, domainId=5, category_origin=origin,
                   description=description, categories=[13945801],
                   categoryTree=[dict(catId=999, name="Kitchen"), dict(catId=13945801, name="Accessories")])
    fact = fact_from_saved_product(product, source_format="keepa_response", evidence_ref="synthetic")
    content = rows_to_prelisting_candidate_csv((row,))
    candidates = parse_prelisting_candidate_csv(content, filename="candidate.csv")
    encoded = rows_to_product_text_safety_sidecar(content, candidates.rows, (fact.text,))
    text = parse_product_text_safety_sidecar(encoded, filename="text.csv", candidate_content=content, candidates=candidates)
    confirmations = None
    if body is not None:
        confirmations = record_body_confirmation(candidates, text, None, asin=row.candidate_asin, family="KNIFE",
                       outcome=body, evidence_reviewed=True, note="Synthetic human confirmation for test")
    gate = evaluate_prelisting_gate(candidates, (inventory(marketplace=market, data_row_count=0),),
                marketplace=market, expected_shop_count=1, product_text_safety=text, sg_body_confirmations=confirmations)
    return candidates, content, text, gate, product


def compare(case, products=None, **kwargs):
    candidates, content, text, gate, product = case
    evidence = json.dumps(dict(products=[product] if products is None else products)).encode()
    return compare_saved_shadow(candidates, content, text, gate, marketplace=gate.marketplace,
                                evidence_content=evidence, **kwargs)


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("source_type", ["EXPANSION", "RESOLVER"])
def test_matches_current_candidate_and_reuses_exact_v3_signals(market, source_type, monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: pytest.fail("Unexpected network"))
    case = setup_case(market=market, source_type=source_type)
    baseline = deepcopy(case)
    exports = build_prelisting_gate_exports(case[3])
    result = compare(case)
    row = result.rows[0]
    assert row.status == "COMPARABLE"
    assert row.signals == classify_product(fact_from_saved_product(
        case[4], source_format="keepa_response", evidence_ref="sha256:" + result.evidence_sha256))
    assert case == baseline
    assert build_prelisting_gate_exports(case[3]) == exports


@pytest.mark.parametrize("title,description,brand,body,expected", [
    ("Kitchen knife", "Includes a knife", "Synthetic Brand", None, "REVIEW"),
    ("Kitchen knife case", "Knife not included", "Synthetic Brand", "BODY_PRESENT", "EXCLUDE"),
    ("Kitchen knife case", "Knife not included", "Adidas", "ACCESSORY_ONLY", "EXCLUDE"),
    ("Kitchen knife case", "Battery case; knife not included", "Synthetic Brand", "ACCESSORY_ONLY", "REVIEW"),
    ("Contact lens case", "Lenses not included", "Synthetic Brand", None, "REVIEW"),
    ("Ordinary case", "Ordinary description", "Synthetic Brand", None, "ELIGIBLE"),
])
def test_shadow_never_changes_block_review_safe_or_confirmed_body_exclude(title, description, brand, body, expected):
    case = setup_case(title, description=description, brand=brand, body=body)
    gate = case[3]
    assert gate.rows[0].final_eligibility == expected
    before = deepcopy(asdict(gate)), build_prelisting_gate_exports(gate)
    assert compare(case).rows[0].status == "COMPARABLE"
    assert (asdict(gate), build_prelisting_gate_exports(gate)) == before
    if brand == "Adidas":
        assert gate.rows[0].guardrail_status == "BLOCK"


@pytest.mark.parametrize("change,reason", [
    ({"asin":"B000000002"}, "MISSING_PRODUCT"), ({"title":"Other"}, "PRODUCT_IDENTITY_MISMATCH"),
    ({"brand":"Other"}, "PRODUCT_IDENTITY_MISMATCH"), ({"fetched_at":"yesterday"}, "PRODUCT_IDENTITY_MISMATCH"),
    ({"fetched_at":""}, "PRODUCT_IDENTITY_MISMATCH"), ({"description":"Other"}, "PRODUCT_TEXT_MISMATCH"),
    ({"domainId":1}, "PRODUCT_DOMAIN_UNVERIFIED"), ({"domainId":None}, "PRODUCT_DOMAIN_UNVERIFIED"),
    ({"categoryTree":[dict(catId=490276011,name="Knife")]}, "OWN_CATEGORY_MISMATCH"),
    ({"categories":False}, "INVALID_PRODUCT_FACT"),
])
def test_mismatched_or_missing_fact_never_yields_a_signal(change, reason):
    case = setup_case()
    row = compare(case, [{**case[4], **change}]).rows[0]
    assert row.status == "NOT_COMPARABLE" and row.reason == reason and row.signals == ()


@pytest.mark.parametrize("content", [b"", b"{}", b'{"products":[]}', b'{"products":{},"products":[]}',
                                     b'{"products":[null]}', b'{"products":[NaN]}', b"\xff",
                                     b'{"schema_version":"SAFETY_SHADOW_REPORT_V2","products":[]}'])
def test_bad_or_old_report_is_comparison_failure_only(content):
    candidates, raw, text, gate, _ = setup_case()
    before = deepcopy(gate)
    result = compare_saved_shadow(candidates, raw, text, gate, marketplace="SG", evidence_content=content)
    assert result.rows[0].status == "NOT_COMPARABLE" and result.rows[0].signals == ()
    assert gate == before


def test_duplicate_saved_asins_are_ambiguous_and_missing_rows_stay_visible():
    case = setup_case()
    assert compare(case, [case[4], case[4]]).rows[0].reason == "INVALID_EVIDENCE"
    assert compare(case, [{**case[4], "asin":"B000000002"}]).rows[0].reason == "MISSING_PRODUCT"


@pytest.mark.parametrize("origin", ["SEED_FALLBACK", "MISSING"])
def test_seed_fallback_is_never_product_category_fact(origin):
    case = setup_case("Ordinary case", origin=origin, description="Ordinary description")
    case[4]["categoryTree"] = [dict(catId=490276011, name="Knife")]
    case[4]["categories"] = [490276011]
    result = compare(case).rows[0]
    assert result.status == "COMPARABLE" and result.signals == ()
    assert result.category_basis == "TITLE_TEXT_ONLY_" + origin


def test_cache_requires_explicit_category_origin_and_matching_text_payload():
    case = setup_case()
    saved = deepcopy(case[4])
    saved["category_tree"] = saved.pop("categoryTree")
    saved.update(product_text_safety_payload_version="PRODUCT_TEXT_SAFETY_PAYLOAD_V1",
                 product_text_safety_capture_status="CAPTURED")
    assert compare(case, [saved], source_format="cache_snapshot").rows[0].status == "COMPARABLE"
    del saved["category_origin"]
    assert compare(case, [saved], source_format="cache_snapshot").rows[0].status == "NOT_COMPARABLE"
    saved["category_origin"] = "OWN_PRODUCT"
    del saved["product_text_safety_payload_version"]
    assert compare(case, [saved], source_format="cache_snapshot").rows[0].reason == "PRODUCT_TEXT_MISMATCH"


@pytest.mark.parametrize("field", PRELISTING_CANDIDATE_COLUMNS)
def test_all_candidate_fields_invalidate_previous_context(field):
    candidates, raw, text, gate, _ = setup_case()
    before = comparison_context(candidates, raw, text, gate, "SG")
    row = replace(candidates.rows[0], **{field:getattr(candidates.rows[0], field) + "_changed"})
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=PRELISTING_CANDIDATE_COLUMNS)
    writer.writeheader()
    writer.writerow(asdict(row))
    changed_raw = output.getvalue().encode("utf-8-sig")
    changed_candidates = replace(candidates, rows=(row,))
    changed_gate = replace(gate, rows=(replace(gate.rows[0], candidate=row),))
    try:
        after = comparison_context(changed_candidates, changed_raw, text, changed_gate, "SG")
    except (ValueError, RuntimeError):
        return  # Invalid CSV contracts cannot become a current comparison.
    assert after != before
    assert compare_saved_shadow(changed_candidates, changed_raw, text, changed_gate, marketplace="SG",
                                evidence_content=b"{}").rows[0].status == "NOT_COMPARABLE"


def test_market_switch_and_candidate_change_cannot_display_previous_result():
    sg = setup_case()
    ph = setup_case(market="PH")
    assert compare(sg).context_sha256 != compare(ph).context_sha256
    assert compare_saved_shadow(*sg[:4], marketplace="PH").rows[0].reason == "CONTEXT_MISMATCH"
    changed = replace(sg[0], rows=(replace(sg[0].rows[0], source_note="Changed source"),))
    assert compare_saved_shadow(changed, *sg[1:4], marketplace="SG").rows[0].reason == "CONTEXT_MISMATCH"
    assert compare_saved_shadow(sg[0], sg[1], None, sg[3], marketplace="SG",
                                evidence_content=b"{}").rows[0].reason == "MISSING_CURRENT_TEXT_FACT"


def test_changed_current_text_and_gate_decision_also_change_context():
    candidates, raw, text, gate, _ = setup_case()
    before = comparison_context(candidates, raw, text, gate, "SG")
    altered_text = replace(text, rows=(replace(text.rows[0], description=("Changed",)),))
    assert comparison_context(candidates, raw, altered_text, gate, "SG") != before
    altered_gate = replace(gate, rows=(replace(gate.rows[0], final_eligibility="EXCLUDE"),))
    assert comparison_context(candidates, raw, text, altered_gate, "SG") != before


def test_multi_product_join_uses_asin_and_keeps_missing_product_separate():
    first = setup_case()
    second = setup_case("Contact lens case", description="Lenses not included")
    row2 = replace(second[0].rows[0], candidate_asin="B000000002")
    product2 = {**second[4], "asin": row2.candidate_asin}
    facts = (first[2].rows[0], fact_from_saved_product(
        product2, source_format="keepa_response", evidence_ref="synthetic").text)
    raw = rows_to_prelisting_candidate_csv((first[0].rows[0], row2))
    candidates = parse_prelisting_candidate_csv(raw, filename="candidate.csv")
    text = parse_product_text_safety_sidecar(
        rows_to_product_text_safety_sidecar(raw, candidates.rows, facts),
        filename="text.csv", candidate_content=raw, candidates=candidates)
    gate = evaluate_prelisting_gate(candidates, (inventory(marketplace="SG", data_row_count=0),),
                marketplace="SG", expected_shop_count=1, product_text_safety=text)
    case = (candidates, raw, text, gate, first[4])
    result = compare(case, [product2, first[4]])
    assert [row.status for row in result.rows] == ["COMPARABLE", "COMPARABLE"]
    assert result.rows[0].signals[0].family == "KNIFE"
    assert "CONTACT_LENS" in {signal.family for signal in result.rows[1].signals}
    assert result.rows[1].signals == classify_product(fact_from_saved_product(
        product2, source_format="keepa_response", evidence_ref="sha256:" + result.evidence_sha256))
    missing = compare(case, [product2])
    assert missing.rows[0].reason == "MISSING_PRODUCT"
    assert missing.rows[1].status == "COMPARABLE"
    assert missing.rows[1].signals == classify_product(fact_from_saved_product(
        product2, source_format="keepa_response", evidence_ref="sha256:" + missing.evidence_sha256))


def test_duplicate_current_candidate_asins_cannot_be_joined_to_one_saved_fact():
    candidates, _, text, _, product = setup_case()
    raw = rows_to_prelisting_candidate_csv((candidates.rows[0], candidates.rows[0]))
    candidates = parse_prelisting_candidate_csv(raw, filename="candidate.csv")
    # A valid sidecar cannot be built for duplicate Candidates. Even a stale
    # in-memory object with an updated digest must fail the schema roundtrip.
    text = replace(text, candidate_sha256=hashlib.sha256(raw).hexdigest())
    gate = evaluate_prelisting_gate(candidates, (inventory(marketplace="SG", data_row_count=0),),
                marketplace="SG", expected_shop_count=1)
    result = compare((candidates, raw, text, gate, product))
    assert len(result.rows) == 2
    assert all(row.reason == "CURRENT_TEXT_MISMATCH" and not row.signals for row in result.rows)
