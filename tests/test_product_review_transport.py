"""Offline original Candidate -> raw sidecars -> isolated SG review tests."""

from dataclasses import replace
import csv
import hashlib
from io import StringIO
import json

import pytest

from modules.product_review_transport import SGProductEvidenceLoader
from modules.ph_image_safety import create_image_sidecar, image_sidecar_bytes, prepare_image_safety
from modules.prelisting_candidate_csv import rows_to_prelisting_candidate_csv, parse_prelisting_candidate_csv
from modules.product_text_safety import rows_to_product_text_safety_sidecar
from test_product_text_safety import candidate, fact
from test_ph_image_safety import fact as image_fact, setup_case
from test_app_category_mapper_sg import _sg_gate_csv, _csv_bytes
from modules.prelisting_gate_csv import PRELISTING_GATE_RESULT_COLUMNS
from test_sg_brand_confirmation_ui import preview, workflow_preview
from test_product_review import allow, inspect


GATE_FILENAME = "prelisting_gate_eligible_sg_expansion.csv"


def files(*, extra=False):
    first = replace(candidate(), source_asin="B000000000", product_title="Example personal care item",
                    brand="Example Brand", category="Personal Care")
    rows = (first, replace(first, candidate_asin="B000000002")) if extra else (first,)
    content = rows_to_prelisting_candidate_csv(rows)
    parsed = parse_prelisting_candidate_csv(content, filename="candidate.csv")
    return dict(candidate_content=content,
                text_content=rows_to_product_text_safety_sidecar(content, parsed.rows, tuple(fact(row.candidate_asin) for row in rows)),
                image_content=create_image_sidecar(content, parsed.rows, [
                    {"candidate_asin": row.candidate_asin, "ph_image_safety_fact": image_fact(row.candidate_asin)} for row in rows
                ]), gate_content=_sg_gate_csv(), gate_filename=GATE_FILENAME)


def test_raw_evidence_can_match_gate_subset_without_reusing_decisions(preview):
    app, _, _ = preview
    item = app.session_state["sg_category_mapper_recommendations"][0]
    # Direct preview uses different metadata; use matching metadata explicitly.
    item = replace(item, product_title="Example personal care item", keepa_brand="Example Brand", keepa_category="Personal Care",
                   source_asin="B000000000")
    loader = SGProductEvidenceLoader(**files(extra=True))
    text, images = loader(item)
    assert text.capture_status == "CAPTURED" and images["image_urls"]
    images["image_urls"].clear()
    assert loader(item)[1]["image_urls"]  # Caller cannot mutate retained facts.
    with pytest.raises(ValueError):
        loader(replace(item, marketplace="PH"))
    with pytest.raises(ValueError):
        loader(replace(item, product_title="Changed"))
    with pytest.raises(ValueError):
        loader(replace(item, candidate_asin="B000000002"))  # Original but not SG eligible.


@pytest.mark.parametrize("change", ["candidate_bytes", "text_sha", "image_sha", "gate_title", "gate_brand", "gate_category", "gate_source_asin", "gate_market", "text_provider"])
def test_evidence_rejects_cross_file_or_market_mismatch(change):
    bundle = files()
    if change == "candidate_bytes":
        bundle["candidate_content"] += b"\n"
    elif change == "text_sha":
        original_sha = hashlib.sha256(bundle["candidate_content"]).hexdigest().encode()
        bundle["text_content"] = bundle["text_content"].replace(original_sha, b"0" * 64)
    elif change == "image_sha":
        data = json.loads(bundle["image_content"])
        data["candidate_sha256"] = "0" * 64
        bundle["image_content"] = image_sidecar_bytes(data)
    elif change == "gate_title":
        bundle["gate_content"] = bundle["gate_content"].replace(b"Example personal care item", b"Another product")
    elif change == "gate_market":
        bundle["gate_content"] = bundle["gate_content"].replace(b",SG,", b",PH,")
    elif change == "gate_brand":
        bundle["gate_content"] = bundle["gate_content"].replace(b"Example Brand", b"Other Brand")
    elif change == "gate_category":
        bundle["gate_content"] = bundle["gate_content"].replace(b"Personal Care", b"Other Category")
    elif change == "gate_source_asin":
        bundle["gate_content"] = bundle["gate_content"].replace(b"B000000000", b"B000000009")
    else:
        bundle["text_content"] = bundle["text_content"].replace(b",keepa,CAPTURED,", b",canopy_test,CAPTURED,")
    with pytest.raises((ValueError, RuntimeError)):
        SGProductEvidenceLoader(**bundle)


def test_resolver_evidence_binds_original_input_but_allows_auxiliary_title(workflow_preview):
    app, _, _, _ = workflow_preview
    item = app.session_state["sg_category_mapper_recommendations"][0]
    row = replace(candidate(), source_type="RESOLVER", source_id="R0001", source_asin="",
                  input_title="Original resolver title", product_title=item.product_title,
                  brand=item.keepa_brand, category=item.keepa_category, source_status="FOUND",
                  source_verification="KEEPA_VERIFIED", source="asin_resolver_keepa_verified")
    content = rows_to_prelisting_candidate_csv((row,))
    parsed = parse_prelisting_candidate_csv(content, filename="candidate.csv")
    gate_row = next(csv.DictReader(StringIO(_sg_gate_csv().decode("utf-8-sig"))))
    gate_row.update(source_type="RESOLVER", source_asin="", input_title=row.input_title)
    bundle = dict(candidate_content=content,
                  text_content=rows_to_product_text_safety_sidecar(content, parsed.rows, (fact(),)),
                  image_content=create_image_sidecar(content, parsed.rows, [{"candidate_asin": row.candidate_asin,
                                                                            "ph_image_safety_fact": image_fact(row.candidate_asin)}]),
                  gate_content=_csv_bytes(PRELISTING_GATE_RESULT_COLUMNS, [gate_row]),
                  gate_filename="prelisting_gate_eligible_sg_resolver.csv")
    loader = SGProductEvidenceLoader(**bundle)
    assert loader(replace(item, source_type="RESOLVER", source_asin="", resolver_input_title="Auxiliary title"))[0].capture_status == "CAPTURED"
    gate_row["input_title"] = "Different original title"
    bundle["gate_content"] = _csv_bytes(PRELISTING_GATE_RESULT_COLUMNS, [gate_row])
    with pytest.raises(ValueError):
        SGProductEvidenceLoader(**bundle)


def test_ph_evaluated_image_sidecar_is_never_an_sg_confirmation():
    bundle = files()
    parsed = parse_prelisting_candidate_csv(bundle["candidate_content"], filename="candidate.csv")
    content, _, base, raw = setup_case(candidates=parsed.rows)
    assert content == bundle["candidate_content"]
    bundle["image_content"] = image_sidecar_bytes(prepare_image_safety(base, raw, content))
    with pytest.raises(ValueError, match="PH image decisions"):
        SGProductEvidenceLoader(**bundle)


def upload_files(app, bundle):
    for key, name, content, mime in (
        ("sg_review_candidate_csv", "candidate.csv", bundle["candidate_content"], "text/csv"),
        ("sg_review_text_csv", "text.csv", bundle["text_content"], "text/csv"),
        ("sg_review_image_json", "images.json", bundle["image_content"], "application/json"),
    ):
        app.file_uploader(key=key).set_value((name, content, mime)).run()


def test_ui_import_requires_click_and_changed_file_invalidates_review(workflow_preview):
    app, workflow, calls, _ = workflow_preview
    bundle = files()
    upload_files(app, bundle)
    assert not app.exception and not workflow.can_load_product_evidence
    assert calls == []
    app.button(key="sg_review_load_files").click().run()
    assert not app.exception and workflow.can_load_product_evidence
    item = app.session_state["sg_category_mapper_recommendations"][0]
    assert workflow.product_review.current(item) is None  # Loading a file is not product confirmation.
    app.button(key="sg_category_mapper_fetch_product_evidence_0").click().run()
    item = app.session_state["sg_category_mapper_recommendations"][0]
    assert workflow.product_review.current(item).text.description == ("ordinary description",)
    inspect(workflow.product_review, item)
    allow(workflow.product_review, item)
    assert workflow.product_review.decision(item) == "ALLOW_PREPARATION"
    app.run()
    assert workflow.product_review.decision(item) == "ALLOW_PREPARATION"
    app.file_uploader(key="sg_review_text_csv").set_value(("text.csv", b"invalid", "text/csv")).run()
    assert not workflow.can_load_product_evidence and workflow.product_review.decision(item) is None
    app.button(key="sg_review_load_files").click().run()
    assert not app.exception and not workflow.can_load_product_evidence
    assert any("確認資料を読み込めません" in error.value for error in app.error)
    assert calls == []


def test_ui_removal_or_gate_replacement_discards_loaded_evidence(workflow_preview):
    app, workflow, _, _ = workflow_preview
    upload_files(app, files())
    app.button(key="sg_review_load_files").click().run()
    assert workflow.can_load_product_evidence
    app.file_uploader(key="sg_category_mapper_source_csv").set_value((GATE_FILENAME,
        _sg_gate_csv().replace(b"Example personal care item", b"Changed product"), "text/csv")).run()
    assert not app.exception and not workflow.can_load_product_evidence
    app.file_uploader(key="sg_category_mapper_source_csv").set_value((GATE_FILENAME, _sg_gate_csv(), "text/csv")).run()
    app.button(key="sg_review_load_files").click().run()
    assert workflow.can_load_product_evidence
    app.file_uploader(key="sg_review_image_json").set_value(None).run()
    assert not app.exception and not workflow.can_load_product_evidence
