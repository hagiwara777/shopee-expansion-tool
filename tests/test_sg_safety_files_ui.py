"""SG manual uploads must preserve the files used by the safety decision."""
from test_app_prelisting_gate import (
    _prelisting_gate_test_app, _prelisting_candidate_csv, _empty_inventory_csv,
    _run_gate_button, _upload_sg_safety_files, _product_text_sidecar,
)


def test_sg_missing_partial_valid_empty_facts_and_removed_file(monkeypatch):
    app = _prelisting_gate_test_app(monkeypatch)
    candidate = _prelisting_candidate_csv()
    app.file_uploader(key="prelisting_gate_candidate_file").set_value(("candidates.csv", candidate, "text/csv"))
    app.file_uploader(key="prelisting_gate_inventory_files").set_value(
        [("existing_SG.csv", _empty_inventory_csv("SG"), "text/csv")])
    app.run()
    assert not app.exception and _run_gate_button(app).disabled
    app.file_uploader(key="prelisting_gate_product_text_safety_file").set_value(
        ("text.csv", _product_text_sidecar(candidate), "text/csv"))
    app.run()
    assert not app.exception and _run_gate_button(app).disabled
    _upload_sg_safety_files(app, candidate)
    app.run()
    assert not app.exception and not _run_gate_button(app).disabled
    _run_gate_button(app).click().run()
    assert not app.exception
    # All facts are missing, but that alone does not add a REVIEW to ordinary goods.
    result = app.session_state["prelisting_gate_result"]
    assert result.rows[2].final_eligibility == "ELIGIBLE"
    app.file_uploader(key="prelisting_gate_ingredient_safety_file").set_value(None).run()
    assert not app.exception and _run_gate_button(app).disabled
    assert "prelisting_gate_result" not in app.session_state


def test_sg_changed_candidate_rejects_previously_valid_files(monkeypatch):
    app = _prelisting_gate_test_app(monkeypatch)
    candidate = _prelisting_candidate_csv()
    app.file_uploader(key="prelisting_gate_candidate_file").set_value(("candidates.csv", candidate, "text/csv"))
    app.file_uploader(key="prelisting_gate_inventory_files").set_value(
        [("existing_SG.csv", _empty_inventory_csv("SG"), "text/csv")])
    _upload_sg_safety_files(app, candidate)
    app.run()
    _run_gate_button(app).click().run()
    assert "prelisting_gate_result" in app.session_state
    changed = candidate.replace(b"ordinary storage box", b"ordinary storage basket")
    app.file_uploader(key="prelisting_gate_candidate_file").set_value(("candidates.csv", changed, "text/csv")).run()
    assert not app.exception and _run_gate_button(app).disabled
    assert "prelisting_gate_result" not in app.session_state
