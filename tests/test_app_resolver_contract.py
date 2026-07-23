import ast
import logging
from pathlib import Path

from streamlit.testing.v1 import AppTest

import modules.asin_resolver as asin_resolver


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"


def _standard_logger_warning(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.WARNING):
        self._log(logging.WARNING, message, args, **kwargs)


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
