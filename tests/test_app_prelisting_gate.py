import ast
import logging
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"
APP_SOURCE = APP_PATH.read_text(encoding="utf-8")
APP_TREE = ast.parse(APP_SOURCE)


def _gate_function() -> ast.FunctionDef:
    return next(
        node
        for node in APP_TREE.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_render_prelisting_gate_input_tab"
    )


def _gate_source() -> str:
    return ast.get_source_segment(APP_SOURCE, _gate_function()) or ""


def _result_function() -> ast.FunctionDef:
    return next(
        node
        for node in APP_TREE.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_render_prelisting_gate_result"
    )


def _result_source() -> str:
    return ast.get_source_segment(APP_SOURCE, _result_function()) or ""


def _attribute_calls(function: ast.FunctionDef, attribute: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
    ]


def _keyword(call: ast.Call, name: str) -> ast.expr:
    return next(keyword.value for keyword in call.keywords if keyword.arg == name)


def _literal_string(expression: ast.expr) -> str:
    assert isinstance(expression, ast.Constant)
    assert isinstance(expression.value, str)
    return expression.value


def _standard_logger_warning(self, message, *args, **kwargs):
    """Restore stdlib warning behavior in this test process only.

    The local Python 3.13 installation has an unrelated injected statement in
    ``logging.Logger.warning``.  AppTest emits a normal context warning while
    it initializes, so the test restores the standard method temporarily.
    """

    if self.isEnabledFor(logging.WARNING):
        self._log(logging.WARNING, message, args, **kwargs)


def test_third_top_level_tab_preserves_the_existing_two_tabs():
    tab_call = next(
        node.value
        for node in APP_TREE.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "tabs"
    )

    assert isinstance(tab_call, ast.Call)
    assert ast.literal_eval(tab_call.args[0]) == [
        "派生ASIN取得",
        "起点ASIN取得",
        "出品前保安ゲート",
    ]
    assert "with expansion_tab:" in APP_SOURCE
    assert "with resolver_tab:" in APP_SOURCE
    assert "with prelisting_gate_tab:" in APP_SOURCE


def test_gate_tab_is_sg_only_and_has_the_required_input_controls():
    function = _gate_function()
    source = _gate_source()
    number_input = _attribute_calls(function, "number_input")
    uploaders = _attribute_calls(function, "file_uploader")

    assert 'PRELISTING_GATE_MARKETPLACE = "SG"' in APP_SOURCE
    assert 'st.write("対象国: SG")' in source
    assert "st.selectbox" not in source
    assert "st.radio" not in source
    assert "PH" not in source
    assert "MY" not in source
    assert len(number_input) == 1
    assert _literal_string(number_input[0].args[0]) == "SGで現在運用している全ショップ数"
    assert ast.literal_eval(_keyword(number_input[0], "min_value")) == 1
    assert ast.literal_eval(_keyword(number_input[0], "value")) == 1
    assert ast.literal_eval(_keyword(number_input[0], "step")) == 1

    uploader_by_label = {
        _literal_string(call.args[0]): call
        for call in uploaders
    }
    candidate_uploader = uploader_by_label["出品前保安ゲート用の候補CSV"]
    inventory_uploader = uploader_by_label["SG全ショップの既出品CSV"]
    assert ast.literal_eval(_keyword(candidate_uploader, "type")) == ["csv"]
    assert ast.literal_eval(_keyword(candidate_uploader, "accept_multiple_files")) is False
    assert ast.literal_eval(_keyword(inventory_uploader, "type")) == ["csv"]
    assert ast.literal_eval(_keyword(inventory_uploader, "accept_multiple_files")) is True
    assert "candidate_file.getvalue()" in source
    assert "uploaded_file.getvalue()" in source


def test_gate_tab_uses_formal_parsers_and_gate_public_functions_only():
    function = _gate_function()
    source = _gate_source()
    calls = [
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]

    assert calls.count("parse_prelisting_candidate_csv") == 1
    assert calls.count("parse_listing_inventory_csv") == 1
    assert calls.count("evaluate_prelisting_gate") == 1
    assert calls.count("build_prelisting_gate_exports") == 1
    assert "csv.reader" not in source
    assert "pd.read_csv" not in source
    assert "apply_guardrails" not in source
    assert "rows_to_prelisting_gate_csv" not in source
    assert "build_prelisting_gate_csv" not in source
    assert "PRELISTING_GATE_RESULT_COLUMNS" not in source
    assert len(_attribute_calls(function, "button")) == 1
    assert not _attribute_calls(function, "download_button")
    session_state_lines = "\n".join(
        line
        for line in source.splitlines()
        if "st.session_state[" in line
    )
    assert "candidate_file" not in session_state_lines
    assert "candidate_bytes" not in session_state_lines
    assert "inventory_files" not in session_state_lines


def test_gate_execution_imports_and_button_follow_the_formal_contract():
    function = _gate_function()
    source = _gate_source()
    gate_import = next(
        node
        for node in ast.walk(APP_TREE)
        if isinstance(node, ast.ImportFrom) and node.module == "modules.prelisting_gate"
    )
    csv_import = next(
        node
        for node in ast.walk(APP_TREE)
        if isinstance(node, ast.ImportFrom) and node.module == "modules.prelisting_gate_csv"
    )
    run_button = next(
        call
        for call in _attribute_calls(function, "button")
        if _literal_string(call.args[0]) == "出品前チェックを実行"
    )

    assert {alias.name for alias in gate_import.names} == {
        "PrelistingGateError",
        "evaluate_prelisting_gate",
    }
    assert {alias.name for alias in csv_import.names} == {
        "PrelistingGateCsvError",
        "build_prelisting_gate_exports",
    }
    assert ast.unparse(_keyword(run_button, "disabled")) == "not input_ready"
    assert ast.literal_eval(_keyword(run_button, "type")) == "primary"
    assert "if run_gate_clicked:" in source
    assert source.index("clear_prelisting_gate_result(st.session_state)") < source.index(
        "evaluate_prelisting_gate("
    )
    assert "with st.spinner(" in source
    assert 'st.session_state["prelisting_gate_result"] = gate_result' in source
    assert 'st.session_state["prelisting_gate_exports"] = exports' in source
    assert 'st.session_state["prelisting_gate_fingerprint"] = current_fingerprint' in source


def test_gate_execution_errors_and_fingerprint_mismatch_clear_old_results():
    source = _gate_source()
    handlers = [
        handler
        for node in ast.walk(_gate_function())
        if isinstance(node, ast.Try)
        for handler in node.handlers
    ]
    handler_names = {
        handler.type.id
        for handler in handlers
        if isinstance(handler.type, ast.Name)
    }

    assert {"PrelistingGateError", "PrelistingGateCsvError"} <= handler_names
    assert source.count("clear_prelisting_gate_result(st.session_state)") >= 5
    assert 'safe_prelisting_gate_error_summary("gate")' in source
    assert 'safe_prelisting_gate_error_summary("export")' in source
    assert 'safe_prelisting_gate_error_summary("unexpected")' in source
    assert "saved_fingerprint == current_fingerprint" in source
    assert "input_ready" in source
    assert "str(exc)" not in source


def test_gate_tab_invalidates_only_reserved_result_state_on_input_changes_and_errors():
    source = _gate_source()

    assert 'saved_fingerprint = st.session_state.get("prelisting_gate_fingerprint")' in source
    assert "saved_fingerprint is not None and saved_fingerprint != current_fingerprint" in source
    assert source.count("clear_prelisting_gate_result(st.session_state)") >= 2
    assert "except PrelistingCandidateCsvError:" in source
    assert "except ListingInventoryParseError:" in source
    assert "safe_prelisting_gate_error_summary(\"candidate\")" in source
    assert "safe_prelisting_gate_error_summary(\"inventory\")" in source
    assert "str(exc)" not in source
    assert "入力準備が完了しました。" in source
    assert "出品前チェックを実行できます。" in source


def test_gate_result_view_uses_four_metrics_three_safe_tabs_and_download_contracts():
    function = _result_function()
    source = _result_source()
    metric_labels = [
        _literal_string(call.args[0])
        for call in _attribute_calls(function, "metric")
    ]
    tab_call = next(iter(_attribute_calls(function, "tabs")))
    download_by_label = {
        _literal_string(_keyword(call, "label")): call
        for call in _attribute_calls(function, "download_button")
    }

    assert metric_labels == ["候補総数", "ELIGIBLE", "REVIEW", "EXCLUDE"]
    assert ast.literal_eval(tab_call.args[0]) == ["ELIGIBLE", "REVIEW", "EXCLUDE"]
    assert source.count("build_prelisting_gate_preview_rows(") == 1
    assert "st.dataframe(preview_rows, hide_index=True, width=\"stretch\")" in source
    assert "先頭100件のみ表示。全件はCSVで確認してください" in source
    assert "該当商品はありません" in source
    assert "existing_evidence_json" not in source
    assert "product_id" not in source
    assert "model_id" not in source
    assert "source_file" not in source

    assert set(download_by_label) == {
        "出品可能CSVをダウンロード",
        "REVIEW CSVをダウンロード",
        "全件監査CSVをダウンロード",
    }
    for call in download_by_label.values():
        assert ast.literal_eval(_keyword(call, "mime")) == "text/csv"
        assert ast.literal_eval(_keyword(call, "on_click")) == "ignore"
        assert ast.literal_eval(_keyword(call, "width")) == "stretch"
    assert "if exports.eligible_csv is not None:" in source
    assert "if exports.review_csv is not None:" in source
    assert 'f"prelisting_gate_eligible_sg_{source_type_part}.csv"' in source
    assert 'f"prelisting_gate_review_sg_{source_type_part}.csv"' in source
    assert 'f"prelisting_gate_audit_sg_{source_type_part}.csv"' in source
    assert "外部出品ツールへの直接投入形式は未確認です。" in source


def test_existing_candidate_download_controls_remain_in_the_application_contract():
    assert "出品候補CSVダウンロード（SAFEのみ）" in APP_SOURCE
    assert "監査用CSVダウンロード（SAFE / REVIEW / BLOCK 全件）" in APP_SOURCE
    assert "出品前保安ゲート用CSVダウンロード" in APP_SOURCE
    assert "起点ASIN候補CSVダウンロード" in APP_SOURCE


def test_prelisting_gate_initial_ui_smoke(monkeypatch):
    monkeypatch.setattr(logging.Logger, "warning", _standard_logger_warning)
    app = AppTest.from_file(str(APP_PATH), default_timeout=10)
    app.run()

    assert len(app.exception) == 0
    tab_labels = [tab.label for tab in app.tabs]
    assert tab_labels[:2] == ["派生ASIN取得", "起点ASIN取得"]
    assert tab_labels[-1] == "出品前保安ゲート"
    assert tab_labels.count("出品前保安ゲート") == 1
    expected_shop_inputs = [
        control
        for control in app.number_input
        if control.label == "SGで現在運用している全ショップ数"
    ]
    assert len(expected_shop_inputs) == 1
    assert expected_shop_inputs[0].value == 1

    rendered_messages = "\n".join(
        str(element.value)
        for element in (*app.warning, *app.error, *app.success, *app.caption)
    )
    assert "候補CSVをアップロードしてください。" in rendered_messages
    assert "入力条件が揃っていません。" in rendered_messages
    gate_buttons = [
        button
        for button in app.button
        if button.label == "出品前チェックを実行"
    ]
    assert len(gate_buttons) == 1
    assert gate_buttons[0].disabled is True
    assert not any(
        button.label
        in {
            "出品可能CSVをダウンロード",
            "REVIEW CSVをダウンロード",
            "全件監査CSVをダウンロード",
        }
        for button in app.download_button
    )
    assert not {
        "候補総数",
        "ELIGIBLE",
        "REVIEW",
        "EXCLUDE",
    } & {metric.label for metric in app.metric}
