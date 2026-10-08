"""Current SG CSV/TXT exit and raw evidence reload cannot bypass body stops."""

from dataclasses import replace
import csv
from io import StringIO

import pytest

from modules.category_mapper_sg_preparation import build_sg_beta_preparation_files
from modules.ph_image_safety import create_image_sidecar
from modules.prelisting_gate_csv import build_prelisting_gate_exports, PRELISTING_GATE_RESULT_COLUMNS
from modules.prelisting_sg_body_safety import body_confirmation_bytes
from modules.product_review_transport import SGProductEvidenceLoader
from modules.product_text_safety import rows_to_product_text_safety_sidecar
from test_prelisting_sg_body_safety import case, confirm, run
from test_ph_image_safety import fact as image_fact
from test_sg_beta_release import activation, ready


def bundle(title, *, outcome=None, description="ordinary description"):
    content, candidates, text = case(title, description=description, brand="Maker")
    family = "CONTACT_LENS" if "lens" in title else "KNIFE"
    record = None if outcome is None else confirm(candidates, text, outcome=outcome, family=family)
    # Emulate an old ELIGIBLE file from before DEC-0129 enforcement.
    old_row = next(csv.DictReader(StringIO(build_prelisting_gate_exports(run(candidates, text)).audit_csv.decode("utf-8-sig"))))
    old_row.update(final_eligibility="ELIGIBLE", reason_codes="", guardrail_status="SAFE",
                   guardrail_risk_category="", guardrail_note="", guardrail_matched_terms="", guardrail_source="")
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=PRELISTING_GATE_RESULT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(old_row)
    values = dict(candidate_content=content,
                  text_content=rows_to_product_text_safety_sidecar(content, candidates.rows, text.rows),
                  image_content=create_image_sidecar(content, candidates.rows, [{
                      "candidate_asin": row.candidate_asin,
                      "ph_image_safety_fact": image_fact(row.candidate_asin, root=999999, images=()),
                  } for row in candidates.rows]),
                  gate_content=output.getvalue().encode("utf-8-sig"),
                  gate_filename="prelisting_gate_eligible_sg_expansion.csv")
    if record is not None:
        values["body_confirmation_content"] = body_confirmation_bytes(record)
    return values, candidates, text


@pytest.mark.parametrize("title", ["Kitchen knife", "Contact lens"])
@pytest.mark.parametrize("outcome", [None, "UNRESOLVED", "BODY_PRESENT"])
def test_old_eligible_csv_and_current_sls_allow_cannot_bypass_body_stop(activation, ready, title, outcome):
    values, candidates, text = bundle(title, outcome=outcome)
    with pytest.raises(ValueError): SGProductEvidenceLoader(**values)
    workflow, item = ready
    row = candidates.rows[0]
    item = replace(item, source_asin=row.source_asin, product_title=row.product_title,
                   keepa_brand=row.brand, keepa_category=row.category)
    workflow.product_review.supply(item, text=text.rows[0], images={
        "candidate_asin": item.candidate_asin, "provider": "keepa", "capture_error": False,
        "image_urls": [], "root_category_id": 999999,
    })
    for _ in range(2):
        csv_bytes, txt, count = build_sg_beta_preparation_files((item,), workflow=workflow)
        assert count == 0 and item.candidate_asin not in txt
        assert not list(csv.DictReader(StringIO(csv_bytes.decode("utf-8-sig"))))


def test_verified_accessory_can_follow_normal_csv_txt_flow_with_current_bound_evidence(activation, ready):
    values, candidates, _ = bundle("Kitchen knife sharpener", outcome="ACCESSORY_ONLY")
    loader = SGProductEvidenceLoader(**values)
    workflow, item = ready
    row = candidates.rows[0]
    item = replace(item, source_asin=row.source_asin, product_title=row.product_title,
                   keepa_brand=row.brand, keepa_category=row.category)
    workflow.bind_product_evidence_files("synthetic-current-files")
    workflow.install_product_evidence_loader(loader)
    workflow.load_product_evidence(item)
    for _ in range(2):
        csv_bytes, txt, count = build_sg_beta_preparation_files((item,), workflow=workflow)
        assert count == 1 and item.candidate_asin in txt
        assert next(csv.DictReader(StringIO(csv_bytes.decode("utf-8-sig"))))["listing_ready"] == "TRUE"
    # Current evidence acquiring a new doubt must not reuse an accessory check.
    from test_product_review import evidence
    changed, images = evidence(item, "Set now includes contact lenses")
    workflow.product_review.supply(item, text=changed, images={**images, "root_category_id":999999})
    assert build_sg_beta_preparation_files((item,), workflow=workflow)[2] == 0


def test_accessory_confirmation_does_not_bypass_current_battery_or_other_guardrail_stop(activation, ready):
    values, candidates, _ = bundle("Kitchen knife sharpener", outcome="ACCESSORY_ONLY", description="Contains battery")
    loader = SGProductEvidenceLoader(**values)
    workflow, item = ready
    row = candidates.rows[0]
    item = replace(item, source_asin=row.source_asin, product_title=row.product_title,
                   keepa_brand=row.brand, keepa_category=row.category)
    workflow.bind_product_evidence_files("synthetic-current-files")
    workflow.install_product_evidence_loader(loader)
    workflow.load_product_evidence(item)
    assert workflow.product_review.current(item).guardrail_status == "REVIEW"
    assert build_sg_beta_preparation_files((item,), workflow=workflow)[2] == 0
