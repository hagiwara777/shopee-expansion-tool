"""Normal Gate UI: uploads, stale input, comparison failure, exports unchanged."""
from dataclasses import replace
import json
import socket

from modules.prelisting_candidate_csv import rows_to_prelisting_candidate_csv
from modules.product_text_safety import rows_to_product_text_safety_sidecar
from test_app_prelisting_gate import _prelisting_gate_test_app, _empty_inventory_csv, _run_gate_button
from test_safety_shadow_comparison import setup_case


def _comparison_frame(app):
    return next(frame.value for frame in app.dataframe if "分類候補" in frame.value.columns)


def _upload(app, data):
    uploader = next(u for u in app.file_uploader if u.label == "保存済み商品Fact JSON")
    uploader.set_value(("facts.json", data, "application/json"))
    return app.run()


def test_normal_gate_compares_accessory_without_releasing_review_and_rejects_stale_inputs(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("Unexpected network")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    candidates, raw, text, _, product = setup_case()
    app = _prelisting_gate_test_app(monkeypatch)
    app.file_uploader(key="prelisting_gate_candidate_file").set_value(("candidate.csv", raw, "text/csv"))
    app.file_uploader(key="prelisting_gate_inventory_files").set_value(
        [("Shopee 更新_SG.csv", _empty_inventory_csv("SG"), "text/csv")])
    app.file_uploader(key="prelisting_gate_product_text_safety_file").set_value(
        ("text.csv", rows_to_product_text_safety_sidecar(raw, candidates.rows, text.rows), "text/csv"))
    app.run()
    _run_gate_button(app).click().run()
    assert not app.exception
    gate = app.session_state["prelisting_gate_result"]
    exports = app.session_state["prelisting_gate_exports"]
    assert gate.rows[0].final_eligibility == "REVIEW"
    assert _comparison_frame(app).iloc[0]["比較"] == "比較不能"
    _upload(app, json.dumps(dict(products=[product])).encode())
    assert not app.exception
    displayed = _comparison_frame(app).iloc[0]
    assert displayed["比較"] == "比較可能" and "ACCESSORY_CANDIDATE" in displayed["分類候補"]
    assert displayed["既存Gate"] == "REVIEW"
    assert app.session_state["prelisting_gate_result"] == gate
    assert app.session_state["prelisting_gate_exports"] == exports
    _upload(app, b"invalid json")
    assert _comparison_frame(app).iloc[0]["比較"] == "比較不能"
    assert app.session_state["prelisting_gate_exports"] == exports

    from modules import safety_shadow_comparison_ui
    def fail_comparison(*args, **kwargs):
        raise RuntimeError("Synthetic display failure")
    with monkeypatch.context() as patch:
        patch.setattr(safety_shadow_comparison_ui, "render_shadow_comparison", fail_comparison)
        app.run()
        assert not app.exception
        assert app.session_state["prelisting_gate_result"] == gate
        assert app.session_state["prelisting_gate_exports"] == exports
        assert any("Shadow比較不能" in element.value for element in app.info)

    changed_raw = rows_to_prelisting_candidate_csv((replace(candidates.rows[0], source_note="New source"),))
    app.file_uploader(key="prelisting_gate_candidate_file").set_value(("candidate.csv", changed_raw, "text/csv"))
    app.run()
    assert "prelisting_gate_result" not in app.session_state
    assert not any("分類候補" in frame.value.columns for frame in app.dataframe)
    app.selectbox(key="prelisting_gate_marketplace").set_value("PH").run()
    assert not app.exception
    assert "prelisting_gate_result" not in app.session_state
    assert not any(u.label == "保存済み商品Fact JSON" for u in app.file_uploader)
