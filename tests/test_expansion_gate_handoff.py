"""Synthetic handoff material, identity and confirmation safety contracts."""
from dataclasses import replace
import logging

import pytest

from modules.prelisting_gate_handoff import (
    Artifact, ExpansionPacket, HandoffError, validate_packet, current_body_confirmations,
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
from modules.ph_image_safety import ImageSafetyError, create_image_sidecar
from modules.prelisting_sg_body_safety import SGBodySafetyError, body_confirmation_bytes, record_body_confirmation
from category_mapper_test_support import _standard_logger_warning
from test_product_text_safety import fact as text_fact
from test_offline_network_support import _deny_network_except_socketpair

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
    monkeypatch.setattr("modules.amazon_data_provider.create_amazon_data_client", lambda *a, **k: pytest.fail("Unexpected provider creation"))










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












def body_record(p, outcome="BODY_PRESENT", family="KNIFE"):
    candidates = validate_packet(p, marketplace="SG", generation=p.generation)
    text = parse_product_text_safety_sidecar(p.product_text.content, filename=p.product_text.name,
                                            candidate_content=p.candidate.content, candidates=candidates)
    record = record_body_confirmation(candidates, text, None, asin="B000000001", family=family,
                                       outcome=outcome, evidence_reviewed=True, note="Synthetic bundle list reviewed")
    return candidates, text, record




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
