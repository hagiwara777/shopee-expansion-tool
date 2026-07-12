import ast
from pathlib import Path

import modules.asin_resolver as asin_resolver


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
