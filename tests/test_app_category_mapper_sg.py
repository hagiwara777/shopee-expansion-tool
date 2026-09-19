import csv
from io import StringIO
import logging
from pathlib import Path

from streamlit.testing.v1 import AppTest

from modules.category_mapper_sg import (
    SG_CATEGORY_CATALOG_COLUMNS,
    parse_sg_category_catalog,
    replace_sg_category_catalog,
)
from modules.category_mapper_store import CategoryMapperStore
from modules.category_ai_openai import OpenAIResponsesCategoryProvider
from modules.prelisting_gate_csv import PRELISTING_GATE_RESULT_COLUMNS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"


def _standard_logger_warning(self, message, *args, **kwargs):
    if self.isEnabledFor(logging.WARNING):
        self._log(logging.WARNING, message, args, **kwargs)


def _csv_bytes(columns, rows):
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def _catalog_csv():
    return _csv_bytes(
        SG_CATEGORY_CATALOG_COLUMNS,
        [
            {
                "marketplace": "SG",
                "category_id": "900000",
                "parent_category_id": "",
                "category_name": "Health",
                "category_path": "Health",
                "is_leaf": "FALSE",
            },
            {
                "marketplace": "SG",
                "category_id": "900001",
                "parent_category_id": "900000",
                "category_name": "Personal Care",
                "category_path": "Health > Personal Care",
                "is_leaf": "TRUE",
            },
        ],
    )


def _sg_gate_csv():
    row = {column: "" for column in PRELISTING_GATE_RESULT_COLUMNS}
    row.update(
        {
            "gate_schema_version": "PRELISTING_GATE_RESULT_V1",
            "candidate_asin": "B000000001",
            "final_eligibility": "ELIGIBLE",
            "marketplace": "SG",
            "candidate_schema_version": "PRELISTING_CANDIDATE_V1",
            "source_type": "EXPANSION",
            "source_asin": "B000000000",
            "product_title": "Example personal care item",
            "brand": "Example Brand",
            "category": "Personal Care",
            "guardrail_status": "SAFE",
            "existing_listing_status": "CLEAR",
            "input_duplicate_status": "UNIQUE",
            "source_asin_status": "CLEAR",
            "metadata_status": "COMPLETE",
        }
    )
    return _csv_bytes(PRELISTING_GATE_RESULT_COLUMNS, [row])


def _test_app(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setattr(logging.Logger, "warning", _standard_logger_warning)
    return AppTest.from_file(str(APP_PATH), default_timeout=10).run()


def _seed_sg_catalog(tmp_path):
    db_path = tmp_path / "localappdata" / "ShopeeCategoryMapper" / "category_mapper.sqlite3"
    store = CategoryMapperStore(db_path)
    catalog = parse_sg_category_catalog(_catalog_csv(), filename="sg_catalog.csv")
    replace_sg_category_catalog(store, catalog, synced_at="2026-09-19T00:00:00+00:00")


def _forbid_live_openai(monkeypatch):
    calls = []

    def forbidden_provider():
        calls.append(True)
        raise AssertionError("SG UI must not construct a live OpenAI provider")

    monkeypatch.setattr(
        OpenAIResponsesCategoryProvider,
        "from_environment",
        staticmethod(forbidden_provider),
    )
    return calls


def test_sg_category_mapper_ui_exposes_isolated_minimum_beta(monkeypatch, tmp_path):
    provider_calls = _forbid_live_openai(monkeypatch)
    app = _test_app(monkeypatch, tmp_path)

    assert not app.exception
    assert provider_calls == []
    assert any(item.value == "SG Category Mapper Minimum Beta" for item in app.subheader)
    assert app.file_uploader(key="sg_category_mapper_catalog_csv").label == (
        "出所確認済みSG Category catalog CSV"
    )
    assert app.file_uploader(key="sg_category_mapper_source_csv").label == (
        "SG Prelisting Gate eligible CSV"
    )
    assert not any(
        button.key and button.key.startswith("sg_category_mapper_")
        for button in app.download_button
    )
    assert not any(
        button.key == "sg_category_mapper_build_ai_suggestions" for button in app.button
    )
    assert not any("SG AI Category候補を作成" in button.label for button in app.button)
    assert any("live実行は未承認" in str(item.value) for item in app.info)


def test_sg_category_mapper_ui_confirms_one_product_and_stops(monkeypatch, tmp_path):
    provider_calls = _forbid_live_openai(monkeypatch)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setattr(logging.Logger, "warning", _standard_logger_warning)
    _seed_sg_catalog(tmp_path)
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()

    app.file_uploader(key="sg_category_mapper_source_csv").set_value(
        (
            "prelisting_gate_eligible_sg_expansion.csv",
            _sg_gate_csv(),
            "text/csv",
        )
    ).run()
    app.button(key="sg_category_mapper_build").click().run()

    before = app.session_state["sg_category_mapper_recommendations"][0]
    assert before.category_is_confirmed is False
    assert before.listing_ready is False
    assert before.group_key == ""
    app.number_input(key="sg_category_mapper_manual_category_0").set_value(900001).run()
    app.button(key="sg_category_mapper_confirm_manual_0").click().run()

    confirmed = app.session_state["sg_category_mapper_recommendations"][0]
    assert confirmed.category_is_confirmed is True
    assert confirmed.recommended_category_id == 900001
    assert confirmed.listing_ready is False
    assert confirmed.group_key == ""
    assert provider_calls == []
    assert not any(
        button.key == "sg_category_mapper_build_ai_suggestions" for button in app.button
    )
    assert any("SG listing_ready: 0件 / export: 停止" in str(item.value) for item in app.caption)
    assert not any(
        button.key and button.key.startswith("sg_category_mapper_")
        for button in app.download_button
    )
