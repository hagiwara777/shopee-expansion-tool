import ast
import csv
from io import StringIO
from pathlib import Path

import modules.prelisting_candidate_csv as prelisting_candidate_csv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
APP_TREE = ast.parse(APP_SOURCE)


def _function_calls(name: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(APP_TREE)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name
    ]


def _download_call(label: str) -> ast.Call:
    for node in ast.walk(APP_TREE):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "download_button"
        ):
            continue
        for keyword in node.keywords:
            if (
                keyword.arg == "label"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == label
            ):
                return node
    raise AssertionError(f"download button not found: {label}")


def _keyword_value(call: ast.Call, name: str) -> ast.expr:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    raise AssertionError(f"keyword not found: {name}")


def test_app_imports_only_the_phase2a_public_adapter_functions():
    imports = next(
        node
        for node in ast.walk(APP_TREE)
        if isinstance(node, ast.ImportFrom) and node.module == "modules.prelisting_candidate_csv"
    )
    imported_names = {alias.name for alias in imports.names}

    assert imported_names == {
        "PrelistingCandidateCsvError",
        "expansion_rows_to_prelisting_candidates",
        "resolver_rows_to_prelisting_candidates",
        "rows_to_prelisting_candidate_csv",
    }
    assert all(hasattr(prelisting_candidate_csv, name) for name in imported_names)
    assert "DictWriter" not in APP_SOURCE
    assert "PRELISTING_CANDIDATE_COLUMNS" not in APP_SOURCE


def test_expansion_adapter_uses_unguarded_result_rows_and_preserves_existing_buttons():
    expansion_calls = _function_calls("expansion_rows_to_prelisting_candidates")

    assert len(expansion_calls) == 1
    argument = expansion_calls[0].args[0]
    assert isinstance(argument, ast.Attribute)
    assert isinstance(argument.value, ast.Name)
    assert argument.value.id == "result"
    assert argument.attr == "rows"
    assert "expansion_rows_to_prelisting_candidates(safe_rows)" not in APP_SOURCE
    assert "expansion_rows_to_prelisting_candidates(guarded_rows)" not in APP_SOURCE

    for label in (
        "出品候補CSVダウンロード（SAFEのみ）",
        "監査用CSVダウンロード（SAFE / REVIEW / BLOCK 全件）",
    ):
        _download_call(label)

    prelisting_download = _download_call("出品前保安ゲート用CSVダウンロード")
    assert ast.get_source_segment(APP_SOURCE, _keyword_value(prelisting_download, "file_name")) == (
        'f"prelisting_candidates_expansion_{result.source_asin}.csv"'
    )
    assert ast.literal_eval(_keyword_value(prelisting_download, "mime")) == "text/csv"
    assert ast.literal_eval(_keyword_value(prelisting_download, "width")) == "stretch"


def test_resolver_adapter_uses_conversion_result_for_counts_and_conditional_download():
    resolver_calls = _function_calls("resolver_rows_to_prelisting_candidates")

    assert len(resolver_calls) == 1
    assert isinstance(resolver_calls[0].args[0], ast.Name)
    assert resolver_calls[0].args[0].id == "resolver_rows"
    assert "resolver_prelisting.eligible_row_count" in APP_SOURCE
    assert "resolver_prelisting.excluded_row_count" in APP_SOURCE
    assert "if resolver_prelisting.eligible_row_count > 0:" in APP_SOURCE
    assert "if resolver_prelisting.eligible_row_count == 0:" in APP_SOURCE

    resolver_downloads = [
        call
        for call in ast.walk(APP_TREE)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "download_button"
        and ast.get_source_segment(APP_SOURCE, _keyword_value(call, "file_name"))
        == '"prelisting_candidates_resolver.csv"'
    ]
    assert len(resolver_downloads) == 1
    assert ast.literal_eval(_keyword_value(resolver_downloads[0], "mime")) == "text/csv"
    assert ast.literal_eval(_keyword_value(resolver_downloads[0], "width")) == "stretch"
    _download_call("起点ASIN候補CSVダウンロード")


def test_prelisting_errors_hide_new_downloads_and_existing_state_clear_contracts_remain():
    error_handlers = [
        handler
        for node in ast.walk(APP_TREE)
        if isinstance(node, ast.Try)
        for handler in node.handlers
        if isinstance(handler.type, ast.Name) and handler.type.id == "PrelistingCandidateCsvError"
    ]

    assert len(error_handlers) == 2
    assert all(
        not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "download_button"
            for node in ast.walk(handler)
        )
        for handler in error_handlers
    )
    assert 'st.session_state["result"] = None' in APP_SOURCE
    assert APP_SOURCE.count('st.session_state["asin_resolver_rows"] = []') >= 3
    assert not any(
        "prelisting" in line and "session_state" in line for line in APP_SOURCE.splitlines()
    )


def test_ui_adapter_equivalent_csvs_use_the_phase2a_fixed_contract_without_api_calls():
    expansion_rows = [
        {
            "seed_asin": "B000000001",
            "candidate_asin": "B000000002",
            "product_title": "Synthetic expansion title",
            "brand": "Synthetic brand",
            "category": "Synthetic category",
            "source": "synthetic_expansion",
            "fetched_at": "2026-07-16T00:00:00+00:00",
            "note": "",
            "guardrail_status": "BLOCK",
        }
    ]
    resolver_rows = [
        {
            "source_id": "R0001",
            "input_title": "Synthetic resolver title",
            "amazon_url": "https://www.amazon.co.jp/dp/B000000003",
            "asin": "B000000003",
            "status": "FOUND",
            "verification": "KEEPA_VERIFIED",
            "keepa_title": "Synthetic Keepa title",
            "keepa_brand": "Synthetic Keepa brand",
            "keepa_category": "Synthetic Keepa category",
            "keepa_fetched_at": "2026-07-16T00:00:00+00:00",
            "note": "",
        },
        {
            "source_id": "R0002",
            "asin": "B000000004",
            "status": "UNKNOWN",
            "verification": "KEEPA_NOT_FOUND",
        },
    ]

    expansion_csv = prelisting_candidate_csv.rows_to_prelisting_candidate_csv(
        prelisting_candidate_csv.expansion_rows_to_prelisting_candidates(expansion_rows)
    )
    resolver_conversion = prelisting_candidate_csv.resolver_rows_to_prelisting_candidates(resolver_rows)
    resolver_csv = prelisting_candidate_csv.rows_to_prelisting_candidate_csv(
        resolver_conversion.output_rows
    )

    expansion_header = next(csv.reader(StringIO(expansion_csv.decode("utf-8-sig"))))
    resolver_header = next(csv.reader(StringIO(resolver_csv.decode("utf-8-sig"))))
    resolver_file = prelisting_candidate_csv.parse_prelisting_candidate_csv(
        resolver_csv,
        filename="synthetic_resolver.csv",
    )

    assert expansion_header == list(prelisting_candidate_csv.PRELISTING_CANDIDATE_COLUMNS)
    assert resolver_header == list(prelisting_candidate_csv.PRELISTING_CANDIDATE_COLUMNS)
    assert "guardrail_status" not in expansion_header
    assert resolver_conversion.input_row_count == 2
    assert resolver_conversion.eligible_row_count == 1
    assert resolver_conversion.excluded_row_count == 1
    assert resolver_file.rows[0].category == "Synthetic Keepa category"
    assert resolver_file.rows[0].fetched_at == "2026-07-16T00:00:00+00:00"
