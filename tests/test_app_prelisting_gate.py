"""The formal entrypoint delegates to Sora only."""
import ast
from pathlib import Path


def test_formal_entrypoint_calls_sora_only_under_main():
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'app.py').read_text(encoding='utf-8'))
    assert len(tree.body) == 1 and isinstance(tree.body[0], ast.If)
    guard = tree.body[0]
    assert ast.unparse(guard.test) == "__name__ == '__main__'"
    assert len(guard.body) == 2 and not guard.orelse
    assert isinstance(guard.body[0], ast.ImportFrom)
    assert guard.body[0].module == 'modules.sora_ui'
    assert [name.name for name in guard.body[0].names] == ['render_sora_app']
    assert ast.unparse(guard.body[1]) == 'render_sora_app()'
