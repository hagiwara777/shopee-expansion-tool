import ast
import logging
from pathlib import Path

from streamlit.testing.v1 import AppTest

import modules.asin_resolver as asin_resolver
from modules.asin_resolver_evidence import (
    APPROVED_FORMAL_MAIN_COMMIT_ENV,
    create_evidence_batch,
    load_and_validate_batch,
    persist_source_input_and_source_map,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"
FORMAL_MAIN_COMMIT = "1c5a16a843a10140c75df9214744fe1c692da101"
PRODUCT_INPUT_KEY = "asin_resolver_product_names_input"


def _standard_logger_warning(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.WARNING):
        self._log(logging.WARNING, message, args, **kwargs)


def _new_evidence_manifest(tmp_path, monkeypatch, batch_id, *, save_source_map):
    monkeypatch.setenv(APPROVED_FORMAL_MAIN_COMMIT_ENV, FORMAL_MAIN_COMMIT)
    manifest_path = create_evidence_batch(
        tmp_path / "runs",
        batch_id=batch_id,
        formal_main_commit=FORMAL_MAIN_COMMIT,
        resolver_version="0.4.3",
    )
    if save_source_map:
        persist_source_input_and_source_map(
            manifest_path,
            "JPH-001\tSaved product one\nJPH-002\tSaved product two\n",
        )
    return manifest_path


def _test_app(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setattr(logging.Logger, "warning", _standard_logger_warning)
    return AppTest.from_file(str(APP_PATH), default_timeout=10).run()


def _resume_evidence_batch(app, manifest_path):
    app.text_input(key="asin_resolver_evidence_resume_path").set_value(str(manifest_path))
    next(
        button for button in app.button if button.label == "Evidence Manifestを検証して再開"
    ).click().run()


def _prompt_button(app):
    return next(button for button in app.button if button.label == "AI用プロンプト生成")


def test_app_resolver_imports_match_public_resolver_functions():
    app_tree = ast.parse((PROJECT_ROOT / "app.py").read_text(encoding="utf-8"))
    resolver_imports = next(
        node
        for node in ast.walk(app_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "modules.asin_resolver"
    )

    missing = [alias.name for alias in resolver_imports.names if not hasattr(asin_resolver, alias.name)]

    assert missing == []


def test_resolver_ui_handles_30_synthetic_tsv_lines_and_malformed_url(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setattr(logging.Logger, "warning", _standard_logger_warning)
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()

    assert not app.exception
    initial_titles = "\n".join(
        f"R{index:04d}\tSynthetic product {index:02d} [variant: test]"
        for index in range(1, 31)
    )
    next(area for area in app.text_area if area.label == "商品名リスト").set_value(initial_titles)
    next(button for button in app.button if button.label == "AI用プロンプト生成").click().run()
    assert len(app.session_state["asin_resolver_source_map"]) == 30

    response_rows = ["source_id\tinput_title\tamazon_url"]
    for index in range(1, 31):
        source_id = f"R{index:04d}"
        if index == 1:
            url = "http://[invalid"
        elif index == 2:
            url = "https://www.amazon.co.jp/dp/B07TSC47PH"
        else:
            url = "不明"
        response_rows.append(f"{source_id}\tAI result {index:02d}\t{url}")

    next(area for area in app.text_area if area.label == "ChatGPT / Geminiの返答").set_value(
        "\n".join(response_rows)
    )
    next(button for button in app.button if button.label == "AI返答を解析").click().run()

    assert not app.exception
    preview_rows = app.session_state["asin_resolver_preview_rows"]
    assert len(preview_rows) == 30
    assert preview_rows[0]["amazon_url"] == ""
    assert preview_rows[0]["note"] == "No Amazon.co.jp URL or ASIN"
    assert preview_rows[1]["source_id"] == "R0002"
    assert preview_rows[1]["asin"] == "B07TSC47PH"


def test_source_map_saved_resume_uses_saved_input_with_an_empty_widget_once(monkeypatch, tmp_path):
    manifest_path = _new_evidence_manifest(
        tmp_path, monkeypatch, "PH-ASIN-app-resume-0001", save_source_map=True
    )
    app = _test_app(monkeypatch, tmp_path)

    _resume_evidence_batch(app, manifest_path)
    assert not app.exception
    assert app.text_area(key=PRODUCT_INPUT_KEY).value == ""
    assert _prompt_button(app).disabled is False

    _prompt_button(app).click().run()

    manifest = load_and_validate_batch(manifest_path)
    artifact_types = [artifact["artifact_type"] for artifact in manifest["artifacts"]]
    assert manifest["last_completed_checkpoint"] == "INITIAL_PROMPT_SAVED"
    assert artifact_types.count("source_input") == 1
    assert artifact_types.count("source_map") == 1
    assert artifact_types.count("initial_prompt") == 1
    assert "Saved product one" in app.session_state["asin_resolver_prompt"]


def test_source_map_saved_resume_missing_input_stops_without_manifest_write(monkeypatch, tmp_path):
    manifest_path = _new_evidence_manifest(
        tmp_path, monkeypatch, "PH-ASIN-app-resume-0002", save_source_map=True
    )
    manifest_before = manifest_path.read_bytes()
    source_input = next(
        artifact
        for artifact in load_and_validate_batch(manifest_path)["artifacts"]
        if artifact["artifact_type"] == "source_input"
    )
    (manifest_path.parent / source_input["filename"]).unlink()
    app = _test_app(monkeypatch, tmp_path)

    _resume_evidence_batch(app, manifest_path)

    assert manifest_path.read_bytes() == manifest_before
    assert any("Evidence Manifestを変更せず停止しました" in str(error.value) for error in app.error)


def test_batch_created_resume_still_requires_widget_input(monkeypatch, tmp_path):
    manifest_path = _new_evidence_manifest(
        tmp_path, monkeypatch, "PH-ASIN-app-resume-0003", save_source_map=False
    )
    app = _test_app(monkeypatch, tmp_path)

    _resume_evidence_batch(app, manifest_path)
    _prompt_button(app).click().run()

    assert load_and_validate_batch(manifest_path)["last_completed_checkpoint"] == "BATCH_CREATED"
    assert any("商品名リストを入力してください。" in str(warning.value) for warning in app.warning)


def test_legacy_mode_still_rejects_an_empty_widget_input(monkeypatch, tmp_path):
    app = _test_app(monkeypatch, tmp_path)

    _prompt_button(app).click().run()

    assert any("商品名リストを入力してください。" in str(warning.value) for warning in app.warning)
    assert "asin_resolver_source_map" not in app.session_state


def test_loading_another_batch_clears_the_previous_product_input_widget(monkeypatch, tmp_path):
    first_manifest = _new_evidence_manifest(
        tmp_path, monkeypatch, "PH-ASIN-app-resume-0004", save_source_map=True
    )
    second_manifest = _new_evidence_manifest(
        tmp_path, monkeypatch, "PH-ASIN-app-resume-0005", save_source_map=True
    )
    app = _test_app(monkeypatch, tmp_path)

    _resume_evidence_batch(app, first_manifest)
    app.text_area(key=PRODUCT_INPUT_KEY).set_value("stale first-batch input").run()
    _resume_evidence_batch(app, second_manifest)

    assert app.text_area(key=PRODUCT_INPUT_KEY).value == ""
