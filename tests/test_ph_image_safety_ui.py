"""AppTest of explicit image execution, human review and stale-result invalidation."""
import logging
from copy import deepcopy

from streamlit.testing.v1 import AppTest

from modules.ph_image_safety import (
    create_image_sidecar,
    image_sidecar_bytes,
)
from modules.prelisting_candidate_csv import (
    rows_to_prelisting_candidate_csv,
    parse_prelisting_candidate_csv,
)
from modules.prelisting_gate_csv import build_prelisting_gate_exports
from test_app_prelisting_gate import (
    APP_PATH,
    _standard_logger_warning,
    _empty_inventory_csv,
    _product_text_sidecar,
)
from test_ph_image_safety import candidate, fact, FakeAnalyzer


def open_ph(monkeypatch, *, images=("one.jpg",), roots=(13299531,)):
    monkeypatch.setattr(logging.Logger, "warning", _standard_logger_warning)
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    app.selectbox(key="prelisting_gate_marketplace").set_value("PH").run()
    candidates = tuple(candidate(f"B00000000{i+1}") for i, _ in enumerate(roots))
    content = rows_to_prelisting_candidate_csv(candidates)
    sources = [
        {
            "candidate_asin": c.candidate_asin,
            "ph_image_safety_fact": fact(c.candidate_asin, root=r, images=images),
        }
        for c, r in zip(candidates, roots)
    ]
    sidecar = create_image_sidecar(content, candidates, sources)
    app.file_uploader(key="prelisting_gate_candidate_file").set_value(
        ("candidate.csv", content, "text/csv")
    )
    app.file_uploader(key="prelisting_gate_inventory_files").set_value(
        [("inventory_PH.csv", _empty_inventory_csv("PH"), "text/csv")]
    )
    app.file_uploader(key="prelisting_gate_product_text_safety_file").set_value(
        ("text.csv", _product_text_sidecar(content), "text/csv")
    )
    app.run()
    assert next(
        b for b in app.button if b.label == "出品前チェックを実行"
    ).disabled  # image sidecar mandatory
    app.file_uploader(key="prelisting_gate_image_safety_file").set_value(
        ("images.json", sidecar, "application/json")
    )
    app.run()
    next(b for b in app.button if b.label == "出品前チェックを実行").click().run()
    assert not app.exception
    return app, content


def enable_and_run_ai(app):
    next(c for c in app.checkbox if c.label == "対象商品の画像AI有料実行を許可する").check().run()
    app.button(key="ph_image_ai_run").click().run()


def choose_human(app, decision, *, confirmed, note):
    next(c for c in app.selectbox if c.label == "画像確認後の判断").set_value(decision)
    next(c for c in app.checkbox if c.label == "この商品の十分な画像を確認した").set_value(confirmed)
    next(c for c in app.text_area if c.label == "確認した画像・判断の根拠").set_value(note)
    app.button(key="ph_image_human_save").click().run()


def test_explicit_api_run_then_rerender_never_repeats_or_changes_candidate(monkeypatch):
    analyzer = FakeAnalyzer()
    monkeypatch.setattr(
        "modules.ph_image_safety_ui.OpenAIImageAnalyzer.from_environment",
        lambda: analyzer,
    )
    app, content = open_ph(monkeypatch)
    assert (
        app.session_state["prelisting_gate_result"].review_count == 1
        and not analyzer.calls
    )
    assert app.button(key="ph_image_ai_run").disabled
    app.run()
    assert not analyzer.calls
    enable_and_run_ai(app)
    assert not app.exception
    assert (
        len(analyzer.calls) == 1
        and app.session_state["prelisting_gate_result"].eligible_count == 1
    )
    app.run()
    assert len(analyzer.calls) == 1
    assert app.session_state[
        "prelisting_gate_exports"
    ] == build_prelisting_gate_exports(app.session_state["prelisting_gate_result"])
    assert (
        rows_to_prelisting_candidate_csv(
            parse_prelisting_candidate_csv(content, filename="candidate.csv").rows
        )
        == content
    )
    assert not any(
        "data:" in str(value) for value in app.session_state.filtered_state.values()
    )


def test_missing_images_can_only_allow_after_sufficient_human_confirmation(monkeypatch):
    app, _ = open_ph(monkeypatch, images=())
    assert app.session_state["prelisting_gate_result"].review_count == 1
    assert not any(b.key == "ph_image_ai_run" for b in app.button)
    choose_human(app, "画像確認済み・準備継続", confirmed=False, note="別経路")
    assert app.session_state["prelisting_gate_result"].review_count == 1
    assert any("十分な画像確認" in e.value for e in app.error)
    choose_human(app, "画像確認済み・準備継続", confirmed=True, note="別経路でこの商品の十分な画像を確認")
    assert not app.exception
    assert app.session_state["prelisting_gate_result"].eligible_count == 1
    app.run()
    assert app.session_state["prelisting_gate_result"].eligible_count == 1
    app.button(key="ph_image_human_clear").click().run()
    assert app.session_state["prelisting_gate_result"].review_count == 1


def test_human_exclude_changes_final_but_not_guardrail(monkeypatch):
    app, _ = open_ph(monkeypatch, images=())
    choose_human(app, "除外", confirmed=False, note="画像が十分に確認できないため除外")
    result = app.session_state["prelisting_gate_result"]
    assert result.exclude_count == 1 and result.rows[0].guardrail_status == "SAFE"
    assert result.rows[0].reason_codes == ("IMAGE_SAFETY_EXCLUDE",)
    assert (
        b"IMAGE_SAFETY_EXCLUDE"
        in app.session_state["prelisting_gate_exports"].audit_csv
    )


def test_global_api_error_clears_all_results_including_other_root_eligible(monkeypatch):
    monkeypatch.setattr(
        "modules.ph_image_safety_ui.OpenAIImageAnalyzer.from_environment",
        lambda: FakeAnalyzer(failure=True),
    )
    app, _ = open_ph(monkeypatch, roots=(13299531, 999))
    assert app.session_state["prelisting_gate_result"].eligible_count == 1
    enable_and_run_ai(app)
    assert not app.exception
    assert "prelisting_gate_result" not in app.session_state
    assert "prelisting_gate_exports" not in app.session_state
    assert "prelisting_gate_image_sidecar" not in app.session_state
    assert not app.download_button
    assert any("Gateを停止" in e.value for e in app.error)


def test_changed_image_file_invalidates_human_decision_and_exports(monkeypatch):
    app, _ = open_ph(monkeypatch, images=())
    choose_human(app, "画像確認済み・準備継続", confirmed=True, note="別経路の画像を確認")
    changed = deepcopy(app.session_state["prelisting_gate_image_sidecar"])
    changed["rows"][0]["human"]["evaluation_id"] = "0" * 64
    app.file_uploader(key="prelisting_gate_image_safety_file").set_value(
        ("changed.json", image_sidecar_bytes(changed), "application/json")
    )
    app.run()
    assert not app.exception
    assert "prelisting_gate_result" not in app.session_state and not app.download_button
    assert next(b for b in app.button if b.label == "出品前チェックを実行").disabled


def test_candidate_change_invalidates_bound_image_records(monkeypatch):
    app, _ = open_ph(monkeypatch, images=())
    changed = rows_to_prelisting_candidate_csv(
        (candidate(product_title="changed title"),)
    )
    app.file_uploader(key="prelisting_gate_candidate_file").set_value(
        ("changed.csv", changed, "text/csv")
    )
    app.run()
    assert "prelisting_gate_result" not in app.session_state and not app.download_button
    assert next(b for b in app.button if b.label == "出品前チェックを実行").disabled
