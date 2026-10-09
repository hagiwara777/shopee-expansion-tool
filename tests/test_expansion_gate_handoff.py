"""DESIGN eight criteria, synthetic-only, through the real unified beta UI."""
from dataclasses import replace
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from modules.prelisting_gate_handoff import (
    Artifact, ExpansionPacket, HandoffError, INTERNAL, MANUAL, PACKET_KEY,
    GENERATION_KEY, SOURCE_KEY, BODY_CACHE_KEY, validate_packet, current_body_confirmations,
)
from modules.prelisting_candidate_csv import (
    expansion_rows_to_prelisting_candidates, rows_to_prelisting_candidate_csv,
)
from modules.ingredient_safety import IngredientSafetyError, facts_for_candidate_rows, rows_to_ingredient_safety_sidecar
from modules.product_text_safety import (
    ProductTextSafetyError, facts_for_candidate_rows as text_facts,
    product_text_safety_fact_to_payload, rows_to_product_text_safety_sidecar,
    parse_product_text_safety_sidecar,
)
from modules.ph_image_safety import ImageSafetyError, create_image_sidecar, record_human_decision
from modules.prelisting_sg_body_safety import SGBodySafetyError, body_confirmation_bytes, record_body_confirmation
from test_app_prelisting_gate import _empty_inventory_csv, _run_gate_button, _standard_logger_warning
from test_product_text_safety import fact as text_fact
from test_safety_shadow_comparison_ui import _deny_network_except_socketpair

ROOT = Path(__file__).resolve().parents[1]


def result(*, title="ordinary storage box", description="ordinary description", asin="B000000001", root=1):
    row = dict(seed_asin="B000000009", candidate_asin=asin, product_title=title,
               brand="Synthetic Brand", category="Synthetic Category", source="keepa_product_finder_strict",
               fetched_at="2026-09-01T00:00:00+00:00", note="", root_category_id=root,
               product_text_safety_fact=product_text_safety_fact_to_payload(text_fact(asin, description=(description,))))
    from modules.keepa_client import ExpansionResult
    return ExpansionResult.from_cache(dict(source_asin="B000000009", brand="Synthetic Brand", category="Synthetic Category",
        search_pages=1, planned_candidates=1, token_estimate=0, raw_candidate_count=1, unique_candidate_count=1,
        duplicate_removed_count=0, rows=[row], fetched_at=row["fetched_at"]))


def packet(market="PH", generated=None):
    generated = generated or result()
    rows = expansion_rows_to_prelisting_candidates(generated.rows)
    raw = rows_to_prelisting_candidate_csv(rows)
    return ExpansionPacket(market, "synthetic-generation", generated.source_asin,
        Artifact("candidate.csv", raw),
        Artifact("ingredient.csv", rows_to_ingredient_safety_sidecar(raw, rows, facts_for_candidate_rows(rows, generated.rows))),
        Artifact("text.csv", rows_to_product_text_safety_sidecar(raw, rows, text_facts(rows, generated.rows))),
        Artifact("image.json", create_image_sidecar(raw, rows, generated.rows)))


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    for key in ("KEEPA_API_KEY", "OPENAI_API_KEY", "PH_IMAGE_SAFETY_API_ENABLED", "AMAZON_DATA_PROVIDER"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("modules.config.ENV_PATH", tmp_path / "missing.env")
    monkeypatch.setattr(logging.Logger, "warning", _standard_logger_warning)
    _deny_network_except_socketpair(monkeypatch)
    monkeypatch.setattr("app.create_amazon_data_client", lambda *a, **k: pytest.fail("Unexpected provider creation"))


def beta(market="PH", generated=None):
    app = AppTest.from_file(str(ROOT / "app_beta.py"), default_timeout=30)
    app.session_state["beta_marketplace"] = market
    if generated is not None:
        app.session_state["result"] = generated
    app.run()
    assert not app.exception
    return app


def inventory(app, market="PH"):
    app.file_uploader(key="prelisting_gate_inventory_files").set_value(
        [(f"existing_{market}.csv", _empty_inventory_csv(market), "text/csv")]).run()
    return app


def upload(app, bundle, *, rename=False):
    for key, artifact in (("candidate", bundle.candidate), ("ingredient_safety", bundle.ingredient),
                          ("product_text_safety", bundle.product_text)):
        app.file_uploader(key=f"prelisting_gate_{key}_file").set_value(
            (("renamed_" if rename else "") + artifact.name, artifact.content, "text/csv"))
    if bundle.marketplace == "PH":
        app.file_uploader(key="prelisting_gate_image_safety_file").set_value((bundle.image.name, bundle.image.content, "application/json"))
    app.run()
    assert not app.exception
    return app


@pytest.mark.parametrize("market", ["PH", "SG"])
@pytest.mark.parametrize("title,description,root", [
    ("ordinary storage box", "ordinary description", 1),
    ("ordinary product", "rechargeable battery inside", 1),
    ("ordinary product", "contains hemp", 1),
    ("Contact lens case", "ordinary description", 1),
    ("ordinary storage box", "ordinary description", None),
    ("synthetic penalty product", "ordinary description", 1),
])
def test_manual_and_internal_whole_results_reasons_and_export_bytes_match(market, title, description, root, monkeypatch):
    generated = result(title=title, description=description, root=root,
                       asin="B000FQTRS0" if title == "synthetic penalty product" else "B000000001")
    bundles = {}
    original = st.download_button
    def capture(*args, **kwargs):
        if kwargs.get("key", "").endswith("expansion-download"):
            bundles[kwargs["key"]] = (kwargs["file_name"], kwargs["data"])
        return original(*args, **kwargs)
    monkeypatch.setattr(st, "download_button", capture)
    internal = inventory(beta(market, generated), market)
    internal.button(key="expansion_gate_use").click().run()
    p = internal.session_state[PACKET_KEY]
    assert any("候補: 1件" in info.value for info in internal.info)
    assert [(a.name, a.content) for a in (p.candidate, p.ingredient, p.product_text, p.image)] == list(bundles.values())
    assert not _run_gate_button(internal).disabled
    assert all(u.value is None for u in internal.file_uploader if u.key in {
        "prelisting_gate_candidate_file", "prelisting_gate_ingredient_safety_file", "prelisting_gate_product_text_safety_file", "prelisting_gate_image_safety_file"})
    _run_gate_button(internal).click().run()
    manual = upload(inventory(beta(market), market), p)
    _run_gate_button(manual).click().run()
    assert not internal.exception and not manual.exception
    assert internal.session_state["prelisting_gate_result"] == manual.session_state["prelisting_gate_result"]
    assert internal.session_state["prelisting_gate_exports"] == manual.session_state["prelisting_gate_exports"]
    gate = internal.session_state["prelisting_gate_result"]
    expected = ("EXCLUDE" if title == "synthetic penalty product" or (description == "contains hemp" and market == "PH") else
                "REVIEW" if "battery" in description or ("Contact lens" in title and market == "SG") or (root is None and market == "PH") else "ELIGIBLE")
    assert gate.rows[0].final_eligibility == expected
    before = internal.session_state["prelisting_gate_exports"]
    internal.run()
    assert internal.session_state["prelisting_gate_exports"] == before


@pytest.mark.parametrize("field", ["candidate", "ingredient", "product_text", "image"])
@pytest.mark.parametrize("bad", [None, b"", b"invalid"])
def test_packet_missing_or_invalid_artifact_is_rejected(field, bad):
    p = packet()
    broken = replace(p, **{field: None if bad is None else replace(getattr(p, field), content=bad)})
    with pytest.raises((HandoffError, IngredientSafetyError, ProductTextSafetyError, ImageSafetyError, RuntimeError)):
        validate_packet(broken, marketplace="PH", generation=p.generation)


@pytest.mark.parametrize("change", ["market", "generation", "source", "sha", "asins", "duplicate-json", "schema", "duplicate-candidate"])
def test_packet_existing_validators_reject_wrong_identity_or_sidecars(change):
    p = packet()
    if change == "market": p = replace(p, marketplace="SG")
    elif change == "generation": p = replace(p, generation="old")
    elif change == "source": p = replace(p, source_asin="B000000008")
    elif change == "sha": p = replace(p, candidate=replace(p.candidate, content=p.candidate.content.replace(b"ordinary storage box", b"changed title")))
    elif change == "asins": p = replace(p, product_text=replace(p.product_text, content=p.product_text.content.replace(b"B000000001", b"B000000002")))
    elif change == "duplicate-json": p = replace(p, image=replace(p.image, content=b'{"schema_version":"one","schema_version":"two"}'))
    elif change == "schema": p = replace(p, image=replace(p.image, content=p.image.content.replace(b"PH_IMAGE_SAFETY_V1", b"UNKNOWN_SCHEMA")))
    else: p = replace(p, candidate=replace(p.candidate, content=p.candidate.content + p.candidate.content.splitlines(keepends=True)[1]))
    with pytest.raises((HandoffError, IngredientSafetyError, ProductTextSafetyError, ImageSafetyError)):
        validate_packet(p, marketplace="PH", generation="synthetic-generation")


def test_internal_missing_packet_never_uses_valid_manual_uploads():
    app = upload(inventory(beta()), packet())
    assert not _run_gate_button(app).disabled
    app.radio(key=SOURCE_KEY).set_value(INTERNAL).run()
    assert _run_gate_button(app).disabled and "prelisting_gate_result" not in app.session_state


@pytest.mark.parametrize("bad", ["missing", "count", "invalid", "wrong-market", "duplicate"])
def test_internal_keeps_all_shop_inventory_obligation(bad):
    app = beta(generated=result())
    app.button(key="expansion_gate_use").click().run()
    if bad != "missing":
        entries = [("existing_SG.csv" if bad == "wrong-market" else "existing_PH.csv", b"broken" if bad == "invalid" else _empty_inventory_csv("PH"), "text/csv")]
        if bad == "duplicate": entries *= 2
        app.file_uploader(key="prelisting_gate_inventory_files").set_value(entries)
        if bad == "count": app.number_input(key="prelisting_gate_expected_shop_count").set_value(2)
        app.run()
    assert _run_gate_button(app).disabled and "prelisting_gate_result" not in app.session_state


def test_existing_asin_remains_excluded():
    raw = _empty_inventory_csv("SG") + b",1,B000000001,2,B000000001,1,Synthetic\n"
    app = beta("SG", result())
    app.file_uploader(key="prelisting_gate_inventory_files").set_value([("existing_SG.csv", raw, "text/csv")])
    app.button(key="expansion_gate_use").click().run()
    _run_gate_button(app).click().run()
    gate = app.session_state["prelisting_gate_result"]
    assert gate.exclude_count == 1 and "EXISTING_ASIN" in gate.rows[0].reason_codes


@pytest.mark.parametrize("outcome", ["success", "failed", "zero", "invalid-facts"])
def test_research_invalidates_old_packet_outputs_before_success_or_failure(monkeypatch, outcome):
    app = inventory(beta(generated=result()))
    app.button(key="expansion_gate_use").click().run()
    _run_gate_button(app).click().run()
    old = app.session_state[PACKET_KEY]
    calls = []
    def search(**kwargs):
        calls.append(kwargs)
        if outcome == "failed": raise ValueError("Synthetic failure")
        generated = result(asin="B000000002")
        if outcome == "zero": generated.rows = []; generated.final_display_count = 0
        if outcome == "invalid-facts": generated.rows[0]["product_text_safety_fact"]["candidate_asin"] = "B000000003"
        return generated
    monkeypatch.setattr("app.create_amazon_data_client", lambda *a: SimpleNamespace(find_related_products=search))
    next(control for control in app.text_input if control.label == "ASIN").input("B000000009")
    next(button for button in app.button if button.label == "検索開始").click().run()
    assert not app.exception and len(calls) == 1
    assert PACKET_KEY not in app.session_state and "prelisting_gate_exports" not in app.session_state
    assert _run_gate_button(app).disabled
    app.run()
    assert len(calls) == 1 and PACKET_KEY not in app.session_state
    if outcome == "success":
        app.button(key="expansion_gate_use").click().run()
        assert app.session_state[PACKET_KEY] != old and not _run_gate_button(app).disabled


def test_market_switch_clears_packet_and_all_bound_confirmations():
    app = inventory(beta(generated=result()))
    app.button(key="expansion_gate_use").click().run()
    _run_gate_button(app).click().run()
    app.session_state[BODY_CACHE_KEY] = {"synthetic": {"records": []}}
    app.selectbox(key="beta_marketplace").select("SG").run()
    assert not app.exception
    for key in (PACKET_KEY, GENERATION_KEY, BODY_CACHE_KEY, "prelisting_gate_bound_ph_image", "prelisting_gate_exports"):
        assert key not in app.session_state
    app.selectbox(key="beta_marketplace").select("PH").run()
    assert PACKET_KEY not in app.session_state and _run_gate_button(app).disabled


def body_record(p, outcome="BODY_PRESENT", family="KNIFE"):
    candidates = validate_packet(p, marketplace="SG", generation=p.generation)
    text = parse_product_text_safety_sidecar(p.product_text.content, filename=p.product_text.name,
                                            candidate_content=p.candidate.content, candidates=candidates)
    record = record_body_confirmation(candidates, text, None, asin="B000000001", family=family,
                                       outcome=outcome, evidence_reviewed=True, note="Synthetic bundle list reviewed")
    return candidates, text, record


@pytest.mark.parametrize("title,family", [("Kitchen knife sharpener", "KNIFE"), ("Contact lens empty case", "CONTACT_LENS")])
def test_confirmed_sg_body_survives_both_source_switches_and_filename_changes(title, family):
    generated = result(title=title)
    app = inventory(beta("SG", generated), "SG")
    app.button(key="expansion_gate_use").click().run()
    p = app.session_state[PACKET_KEY]
    _, _, record = body_record(p, family=family)
    app.file_uploader(key="prelisting_gate_sg_body_file").set_value(("body.json", body_confirmation_bytes(record), "application/json")).run()
    _run_gate_button(app).click().run()
    expected, exports = app.session_state["prelisting_gate_result"], app.session_state["prelisting_gate_exports"]
    assert expected.exclude_count == 1 and exports.eligible_csv is None
    # Remove resume upload after validation; session confirmation must stand on its own.
    app.file_uploader(key="prelisting_gate_sg_body_file").set_value(None).run()
    upload(app, p, rename=True)
    for mode in (MANUAL, INTERNAL, MANUAL):
        app.radio(key=SOURCE_KEY).set_value(mode).run()
        assert "prelisting_gate_exports" not in app.session_state
        _run_gate_button(app).click().run()
        assert not app.exception and app.session_state["prelisting_gate_result"] == expected
        assert app.session_state["prelisting_gate_exports"] == exports
        app.run()
        assert app.session_state["prelisting_gate_result"].eligible_count == 0


def test_saved_body_cannot_be_downgraded_by_new_resume_upload():
    p = packet("SG", result(title="Kitchen knife sharpener"))
    candidates, text, confirmed = body_record(p)
    _, _, accessory = body_record(p, "ACCESSORY_ONLY")
    with pytest.raises(SGBodySafetyError):
        current_body_confirmations(candidates, text, body_confirmation_bytes(accessory), {confirmed["context_sha256"]: confirmed})


def test_changed_fact_never_reuses_old_confirmation_or_silently_eligible():
    p = packet("SG", result(title="Kitchen knife sharpener"))
    candidates, text, confirmed = body_record(p)
    cache = {confirmed["context_sha256"]: confirmed}
    changed = replace(text, rows=(replace(text.rows[0], description=("changed bundle",)),))
    fresh = current_body_confirmations(candidates, changed, None, cache)
    assert not fresh["records"] and fresh["context_sha256"] != confirmed["context_sha256"]
    from modules.prelisting_sg_body_safety import body_checks
    assert body_checks(candidates, changed, fresh)[0]["outcome"] == "UNRESOLVED"
    with pytest.raises(SGBodySafetyError):
        current_body_confirmations(candidates, changed, body_confirmation_bytes(confirmed), cache)
    removed = replace(candidates, rows=(replace(candidates.rows[0], product_title="ordinary storage box"),))
    with pytest.raises(SGBodySafetyError):
        current_body_confirmations(removed, changed, None, cache)


def test_ph_confirmed_image_survives_same_facts_source_switch_and_changed_fact_expires():
    generated = result(root=None)
    app = inventory(beta(generated=generated))
    app.button(key="expansion_gate_use").click().run()
    _run_gate_button(app).click().run()
    p = app.session_state[PACKET_KEY]
    base = app.session_state["prelisting_gate_base_result"]
    image = record_human_decision(base, app.session_state["prelisting_gate_image_sidecar"], p.candidate.content,
        asin="B000000001", decision="EXCLUDE", reviewed_images=True, note="Synthetic review")
    app.session_state["prelisting_gate_bound_ph_image"] = ((p.candidate.content, p.ingredient.content, p.product_text.content), image)
    app.session_state["prelisting_gate_image_sidecar"] = image
    app.run()
    upload(app, p, rename=True)
    app.radio(key=SOURCE_KEY).set_value(MANUAL).run()
    _run_gate_button(app).click().run()
    assert app.session_state["prelisting_gate_result"].exclude_count == 1
    app.radio(key=SOURCE_KEY).set_value(INTERNAL).run()
    _run_gate_button(app).click().run()
    assert app.session_state["prelisting_gate_result"].exclude_count == 1
    generated.rows[0]["root_category_id"] = 13299531
    app.session_state["result"] = generated
    app.run()
    assert PACKET_KEY not in app.session_state and "prelisting_gate_exports" not in app.session_state
    app.button(key="expansion_gate_use").click().run()
    _run_gate_button(app).click().run()
    assert app.session_state["prelisting_gate_result"].review_count == 1
    assert all(row["human"] is None for row in app.session_state["prelisting_gate_image_sidecar"]["rows"])
