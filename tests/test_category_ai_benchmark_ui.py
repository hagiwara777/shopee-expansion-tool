"""Headless initial-render test; no API call or credential is used."""

from pathlib import Path
import logging

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "category_ai_benchmark_app.py"


def test_standalone_benchmark_ui_renders_required_controls_without_api_call(monkeypatch):
    # The shared local Python runtime has a known unrelated logging.warning defect.
    monkeypatch.setattr(logging.Logger, "warning", lambda self, *args, **kwargs: None)
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    assert not app.exception
    assert app.title[0].value == "Category AI Benchmark V1"
    assert app.selectbox(key="category_ai_marketplace").value == "PH"
    assert app.multiselect(key="category_ai_models").value == ["gpt-5.6-terra"]
    assert app.number_input(key="category_ai_item_count").value == 3
    assert app.file_uploader(key="category_ai_source_file")
    assert app.file_uploader(key="category_ai_catalog_file")
    assert app.file_uploader(key="category_ai_gold_file")
    assert next(button for button in app.button if button.label == "Benchmarkを実行")
