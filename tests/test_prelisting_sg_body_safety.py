"""Offline DEC-0129 acceptance: body Facts, identity binding and real outputs."""

from copy import deepcopy
from dataclasses import replace
import csv
from io import StringIO
import json

import pytest

from modules.prelisting_candidate_csv import (
    PRELISTING_CANDIDATE_COLUMNS, parse_prelisting_candidate_csv, rows_to_prelisting_candidate_csv,
)
from modules.prelisting_gate import PrelistingGateError, evaluate_prelisting_gate
from modules.prelisting_gate_csv import build_prelisting_gate_exports
from modules.prelisting_sg_body_safety import (
    SGBodySafetyError, body_checks, body_confirmation_bytes, body_suspicions,
    parse_body_confirmations, prepare_body_confirmations, record_body_confirmation,
)
from modules.product_text_safety import parse_product_text_safety_sidecar, rows_to_product_text_safety_sidecar
from test_product_text_safety import candidate, fact
from test_prelisting_gate import inventory


def case(title="Kitchen knife", *, source_type="EXPANSION", description="ordinary description", **fields):
    row = replace(candidate(), product_title=title, **fields)
    if source_type == "RESOLVER":
        row = replace(row, source_type="RESOLVER", source_asin="", source_id="R0001", source_status="FOUND",
                      source_verification="KEEPA_VERIFIED", source="asin_resolver_keepa_verified")
    content = rows_to_prelisting_candidate_csv((row,))
    candidates = parse_prelisting_candidate_csv(content, filename="candidate.csv")
    text_content = rows_to_product_text_safety_sidecar(content, candidates.rows, (fact(description=(description,)),))
    text = parse_product_text_safety_sidecar(text_content, filename="text.csv", candidate_content=content, candidates=candidates)
    return content, candidates, text


def run(candidates, text=None, confirmations=None, *, marketplace="SG", inventories=None):
    return evaluate_prelisting_gate(candidates, inventories or (inventory(marketplace=marketplace, data_row_count=0),),
                                   marketplace=marketplace, expected_shop_count=1,
                                   product_text_safety=text, sg_body_confirmations=confirmations)


def confirm(candidates, text=None, *, outcome="BODY_PRESENT", family="KNIFE", confirmations=None,
            asin="B000000001", evidence_reviewed=True, note="商品内容と実同梱一覧を確認した。"):
    return record_body_confirmation(candidates, text, confirmations, asin=asin, family=family,
                                    outcome=outcome, evidence_reviewed=evidence_reviewed, note=note)


@pytest.mark.parametrize("title,family", [
    ("Kitchen knife", "KNIFE"), ("Kitchen knives storage holder", "KNIFE"),
    ("Chef knives set", "KNIFE"), ("Chef's knife case", "KNIFE"),
    ("Cook’s knife", "KNIFE"), ("Kitchen-knife case", "KNIFE"),
    ("包丁研ぎ器", "KNIFE"), ("三徳包丁セット", "KNIFE"), ("Santoku sheath", "KNIFE"),
    ("Contact lenses", "CONTACT_LENS"), ("Contact lens case", "CONTACT_LENS"),
    ("Contact-lens care solution", "CONTACT_LENS"), ("コンタクトレンズ保存ケース", "CONTACT_LENS"),
    ("カラコン 2枚", "CONTACT_LENS"),
])
def test_names_are_suspicion_never_confirmed_body(title, family):
    _, candidates, text = case(title)
    result = run(candidates, text)
    assert result.rows[0].final_eligibility == "REVIEW"
    assert "SG_BODY_REVIEW" in result.rows[0].reason_codes
    assert body_checks(candidates, text)[0]["outcome"] == "UNRESOLVED"
    assert family in body_suspicions(title)


@pytest.mark.parametrize("source_type", ["EXPANSION", "RESOLVER"])
@pytest.mark.parametrize("title,family", [("包丁セット", "KNIFE"), ("カラコンとケースのセット", "CONTACT_LENS")])
def test_confirmed_body_stays_excluded_after_serialized_restart_and_gate_rerun(tmp_path, source_type, title, family):
    _, candidates, text = case(title, source_type=source_type)
    record = confirm(candidates, text, family=family)
    path = tmp_path / "confirmations.json"
    path.write_bytes(body_confirmation_bytes(record))
    restored = parse_body_confirmations(path.read_bytes(), candidates, text)
    for _ in range(2):
        result = run(candidates, text, restored)
        assert result.exclude_count == 1 and result.eligible_count == result.review_count == 0
        assert "SG_BODY_EXCLUDE" in result.rows[0].reason_codes
        exports = build_prelisting_gate_exports(result)
        assert exports.eligible_csv is None and exports.review_csv is None
        row = next(csv.DictReader(StringIO(exports.audit_csv.decode("utf-8-sig"))))
        assert row["final_eligibility"] == "EXCLUDE" and "BODY_PRESENT" in row["guardrail_note"]
    with pytest.raises(SGBodySafetyError):
        confirm(candidates, text, outcome="ACCESSORY_ONLY", family=family, confirmations=record)
    with pytest.raises(SGBodySafetyError):
        confirm(candidates, text, outcome="UNRESOLVED", family=family, confirmations=record)


def test_accessory_confirmation_only_resolves_our_new_question():
    _, candidates, text = case("Kitchen knife sharpener")
    assert run(candidates, text).review_count == 1
    record = confirm(candidates, text, outcome="ACCESSORY_ONLY")
    assert run(candidates, text, record).eligible_count == 1
    _, candidates, text = case("Contact lens empty case")
    record = confirm(candidates, text, outcome="ACCESSORY_ONLY", family="CONTACT_LENS")
    result = run(candidates, text, record)
    assert result.review_count == 1 and result.rows[0].guardrail_status == "REVIEW"
    assert "GUARDRAIL_REVIEW" in result.rows[0].reason_codes
    assert "SG_BODY_REVIEW" not in result.rows[0].reason_codes


@pytest.mark.parametrize("stop", ["battery", "brand", "existing", "metadata"])
def test_accessory_cannot_release_other_stops(stop):
    fields = {"brand": "Adidas"} if stop == "brand" else {"brand": ""} if stop == "metadata" else {}
    _, candidates, text = case("Kitchen knife case", description="battery" if stop == "battery" else "ordinary", **fields)
    record = confirm(candidates, text, outcome="ACCESSORY_ONLY")
    inventories = None
    if stop == "existing":
        from test_prelisting_gate import evidence
        inventories = (inventory((evidence("B000000001"),)),)
    result = run(candidates, text, record, inventories=inventories)
    assert result.rows[0].final_eligibility == ("EXCLUDE" if stop in {"brand", "existing"} else "REVIEW")


def test_text_suspicion_and_unknown_do_not_require_category_or_extra_api():
    _, candidates, text = case("Ordinary boxed set", description="Contains contact lenses")
    assert run(candidates, text).review_count == 1
    _, ordinary, _ = case("Ordinary case", category="Kitchen knives", input_title="Contact lenses")
    assert run(ordinary).eligible_count == 1  # category/seed/input-title not Safety authority.
    assert body_suspicions("knife switch / camera lens / contact cleaner") == {}


@pytest.mark.parametrize("field", PRELISTING_CANDIDATE_COLUMNS)
def test_confirmation_binds_all_fifteen_candidate_fields(field):
    _, candidates, text = case()
    record = confirm(candidates, text)
    changed = replace(candidates, rows=(replace(candidates.rows[0], **{field: "Changed"}),))
    with pytest.raises(SGBodySafetyError):
        prepare_body_confirmations(changed, text, record)


def test_confirmation_rejects_changed_or_missing_text_other_market_other_asin_and_policy():
    _, candidates, text = case()
    record = confirm(candidates, text)
    changed = replace(text, rows=(replace(text.rows[0], description=("Changed bundle",)),))
    with pytest.raises(SGBodySafetyError): prepare_body_confirmations(candidates, changed, record)
    with pytest.raises(SGBodySafetyError): prepare_body_confirmations(candidates, None, record)
    with pytest.raises(PrelistingGateError): run(candidates, text, record, marketplace="PH")
    for field, value in [("marketplace", "PH"), ("policy", "another"), ("schema", "V2")]:
        wrong = {**record, field: value}
        with pytest.raises(SGBodySafetyError): parse_body_confirmations(body_confirmation_bytes(wrong), candidates, text)
    with pytest.raises(SGBodySafetyError): confirm(candidates, text, asin="B000000002")


@pytest.mark.parametrize("outcome,reviewed,note", [("BODY_PRESENT", False, "x"), ("ACCESSORY_ONLY", False, "x"),
                                                    ("BODY_PRESENT", True, ""), ("SAFE", True, "x")])
def test_explicit_body_or_accessory_requires_evidence_and_note(outcome, reviewed, note):
    _, candidates, text = case()
    with pytest.raises(SGBodySafetyError):
        confirm(candidates, text, outcome=outcome, evidence_reviewed=reviewed, note=note)


@pytest.mark.parametrize("content", [b"null", b"[]", b"{}", b"invalid", b'{"x":1,"x":2}'])
def test_malformed_confirmation_never_passes(content):
    _, candidates, text = case()
    with pytest.raises(SGBodySafetyError): parse_body_confirmations(content, candidates, text)


def test_both_families_are_independent_and_body_dominates():
    _, candidates, text = case("Kitchen knife and contact lens case set")
    record = confirm(candidates, text, outcome="ACCESSORY_ONLY")
    assert run(candidates, text, record).review_count == 1
    record = confirm(candidates, text, family="CONTACT_LENS", confirmations=record)
    assert run(candidates, text, record).exclude_count == 1


def test_non_target_and_ph_keep_existing_decisions():
    _, candidates, text = case("Ordinary storage box")
    for market in ("SG", "PH"):
        assert run(candidates, text, marketplace=market).eligible_count == 1
    _, candidates, text = case("Contact lens")
    result = run(candidates, text, marketplace="PH")
    assert all(not code.startswith("SG_BODY") for code in result.rows[0].reason_codes)


def test_changed_record_and_duplicate_product_are_rejected():
    _, candidates, text = case()
    record = confirm(candidates, text)
    changed = deepcopy(record)
    changed["records"][0]["outcome"] = "ACCESSORY_ONLY"
    with pytest.raises(SGBodySafetyError): parse_body_confirmations(body_confirmation_bytes(changed), candidates, text)
    duplicates = replace(candidates, rows=candidates.rows * 2, data_row_count=2)
    with pytest.raises(SGBodySafetyError): confirm(duplicates)
