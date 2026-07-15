import ast
from pathlib import Path

import pytest

import modules.asin_resolver as asin_resolver
import modules.openai_search_client as openai_search_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_app_resolver_imports_match_public_resolver_functions():
    app_tree = ast.parse((PROJECT_ROOT / "app.py").read_text(encoding="utf-8"))
    resolver_imports = next(
        node
        for node in ast.walk(app_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "modules.asin_resolver"
    )

    missing = [alias.name for alias in resolver_imports.names if not hasattr(asin_resolver, alias.name)]

    assert missing == []


def test_app_openai_search_imports_match_public_client_functions():
    app_tree = ast.parse((PROJECT_ROOT / "app.py").read_text(encoding="utf-8"))
    client_imports = next(
        node
        for node in ast.walk(app_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "modules.openai_search_client"
    )

    missing = [
        alias.name
        for alias in client_imports.names
        if not hasattr(openai_search_client, alias.name)
    ]

    assert missing == []


def test_app_openai_search_call_is_guarded_by_the_explicit_button():
    app_tree = ast.parse((PROJECT_ROOT / "app.py").read_text(encoding="utf-8"))
    parents = {
        child: parent
        for parent in ast.walk(app_tree)
        for child in ast.iter_child_nodes(parent)
    }
    calls = [
        node
        for node in ast.walk(app_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "execute_openai_web_search"
    ]

    assert len(calls) == 1
    current = calls[0]
    while current in parents:
        current = parents[current]
        if isinstance(current, ast.If) and isinstance(current.test, ast.Name):
            if current.test.id == "search_clicked":
                break
    else:
        pytest.fail("execute_openai_web_search must be guarded by search_clicked")
