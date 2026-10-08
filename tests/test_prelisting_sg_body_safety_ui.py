"""Offline ordinary Gate UI: save, rerun, restart and stale-record rejection."""

from dataclasses import replace

import pytest

from modules.prelisting_sg_body_safety import body_confirmation_bytes
from modules.prelisting_candidate_csv import rows_to_prelisting_candidate_csv
from modules.prelisting_gate_csv import build_prelisting_gate_exports
from test_app_prelisting_gate import _empty_inventory_csv, _prelisting_gate_test_app, _run_gate_button
from test_prelisting_sg_body_safety import case


def upload(app, candidate_content, *, record=None):
    app.file_uploader(key="prelisting_gate_candidate_file").set_value(("candidate.csv", candidate_content, "text/csv")).run()
    app.file_uploader(key="prelisting_gate_inventory_files").set_value(
        [("existing_SG.csv", _empty_inventory_csv("SG"), "text/csv")]).run()
    if record is not None:
        app.file_uploader(key="prelisting_gate_sg_body_file").set_value(("confirmations.json", record, "application/json")).run()
    assert not app.exception
    return app


@pytest.mark.parametrize("title", ["Kitchen knife set", "カラコンとケースのセット"])
def test_confirmed_body_never_returns_to_output_on_ui_rerun_or_restart(monkeypatch, title):
    content, _, _ = case(title)
    app = upload(_prelisting_gate_test_app(monkeypatch), content)
    _run_gate_button(app).click().run()
    assert app.session_state["prelisting_gate_result"].review_count == 1
    next(control for control in app.selectbox if control.label == "本体・同梱の確認結果").select("本体あり・本体を含むセット").run()
    next(control for control in app.checkbox if control.label.startswith("名称だけで決めず")).check().run()
    next(control for control in app.text_area if control.label == "確認した資料・内容と判断根拠").input("同梱一覧に本体を確認した").run()
    next(button for button in app.button if button.label == "本体確認結果を反映").click().run()
    assert not app.exception
    record = body_confirmation_bytes(app.session_state["prelisting_gate_sg_body_confirmations"])
    for _ in range(2):
        app.run()
        _run_gate_button(app).click().run()
        assert not app.exception
        result = app.session_state["prelisting_gate_result"]
        assert result.exclude_count == 1 and result.eligible_count == 0
        assert build_prelisting_gate_exports(result).eligible_csv is None
    restarted = upload(_prelisting_gate_test_app(monkeypatch), content, record=record)
    _run_gate_button(restarted).click().run()
    assert not restarted.exception
    assert restarted.session_state["prelisting_gate_result"].exclude_count == 1
    assert not any(button.label == "出品可能CSVをダウンロード" for button in restarted.get("download_button"))


def test_accessory_confirmation_releases_only_new_question_and_changed_candidate_resets(monkeypatch):
    content, candidates, _ = case("Kitchen knife sharpener")
    app = upload(_prelisting_gate_test_app(monkeypatch), content)
    _run_gate_button(app).click().run()
    next(control for control in app.selectbox if control.label == "本体・同梱の確認結果").select("本体なし・付属品／ケア用品のみ").run()
    # A choice without evidence cannot release the stop.
    next(button for button in app.button if button.label == "本体確認結果を反映").click().run()
    assert not app.exception and app.session_state["prelisting_gate_result"].review_count == 1
    next(control for control in app.checkbox if control.label.startswith("名称だけで決めず")).check().run()
    next(control for control in app.text_area if control.label == "確認した資料・内容と判断根拠").input("研ぎ器だけ。本体は付属しないと確認した").run()
    next(button for button in app.button if button.label == "本体確認結果を反映").click().run()
    assert not app.exception and app.session_state["prelisting_gate_result"].eligible_count == 1
    changed = rows_to_prelisting_candidate_csv((replace(candidates.rows[0], fetched_at="2026-10-09T00:00:00Z"),))
    app.file_uploader(key="prelisting_gate_candidate_file").set_value(("candidate.csv", changed, "text/csv")).run()
    assert "prelisting_gate_result" not in app.session_state
    _run_gate_button(app).click().run()
    assert app.session_state["prelisting_gate_result"].review_count == 1


def test_bad_uploaded_confirmation_stops_gate(monkeypatch):
    content, _, _ = case()
    app = upload(_prelisting_gate_test_app(monkeypatch), content, record=b"null")
    assert _run_gate_button(app).disabled
    assert "prelisting_gate_result" not in app.session_state
    assert any("SG本体確認記録を検証できません" in message.value for message in app.error)
