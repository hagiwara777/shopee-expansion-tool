"""Real collection checks for the normal, preserved and combined suites."""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def selection_fixture(tmp_path):
    shutil.copyfile(ROOT / 'conftest.py', tmp_path / 'conftest.py')
    shutil.copyfile(ROOT / 'pytest.ini', tmp_path / 'pytest.ini')
    tests = tmp_path / 'tests'
    tests.mkdir()
    (tests / 'test_mixed.py').write_text(
        'def test_retired(): pass\ndef test_shared_safety(): pass\ndef test_new_unclassified(): pass\n',
        encoding='utf-8',
    )
    (tests / 'test_scopes.json').write_text(json.dumps({
        'schema_version': 1,
        'retired': {'tests/test_mixed.py': {'reason': 'synthetic retired feature only', 'tests': ['test_retired']}},
    }), encoding='utf-8')
    core = tmp_path / 'work' / 'ci' / 'commerce-api-core' / 'tests'
    core.mkdir(parents=True)
    (core / 'test_core.py').write_text('def test_core_only(): pass\n', encoding='utf-8')
    return tmp_path


def collect(root, *args):
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    result = subprocess.run(
        [sys.executable, '-X', 'utf8', '-B', '-m', 'pytest', '--collect-only', '-q', '-p', 'no:cacheprovider', *args],
        cwd=root, env=env, capture_output=True, encoding='utf-8', timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return {line for line in result.stdout.splitlines() if '::test_' in line}


@pytest.mark.parametrize('scope,expected', [
    ('active', {'test_shared_safety', 'test_new_unclassified'}),
    ('retired', {'test_retired'}),
    ('all', {'test_retired', 'test_shared_safety', 'test_new_unclassified'}),
])
def test_explicit_scopes_preserve_mixed_and_unknown_cases(selection_fixture, scope, expected):
    nodes = collect(selection_fixture, '--test-scope=' + scope)
    assert {node.rsplit('::', 1)[-1] for node in nodes} == expected


def test_default_suite_excludes_core_checkout_but_explicit_core_suite_is_available(selection_fixture):
    default = collect(selection_fixture)
    assert {node.rsplit('::', 1)[-1] for node in default} == {'test_shared_safety', 'test_new_unclassified'}
    core = collect(selection_fixture, 'work/ci/commerce-api-core/tests')
    assert {node.rsplit('::', 1)[-1] for node in core} == {'test_core_only'}


def test_reviewed_selectors_exist_and_shared_safety_modules_are_not_retired():
    registry = json.loads((ROOT / 'tests/test_scopes.json').read_text(encoding='utf-8'))
    protected_files = {
        'tests/test_guardrails.py', 'tests/test_prelisting_gate.py',
        'tests/test_sls_category_protected.py', 'tests/test_governance_v2.py',
        'tests/test_battery_presence.py', 'tests/test_brand_monitoring.py',
        'tests/test_ingredient_safety.py', 'tests/test_product_text_safety.py',
        'tests/test_research_csv_adapter.py', 'tests/test_app_research_csv_adapter.py',
        'tests/test_asin_resolver.py', 'tests/test_amazon_data_provider.py',
        'tests/test_app_prelisting_gate.py', 'tests/test_app_prelisting_contract.py',
        'tests/test_sg_safety_files_ui.py',
    }
    assert not protected_files.intersection(registry['retired'])
    for file, entry in registry['retired'].items():
        tree = ast.parse((ROOT / file).read_text(encoding='utf-8-sig'))
        actual = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')}
        assert entry['tests'] and set(entry['tests']) <= actual
        assert len(entry['tests']) == len(set(entry['tests']))
    for file, entry in registry['retained_mixed'].items():
        assert not set(entry['tests']).intersection(registry['retired'][file]['tests'])
    assert not set(registry['retained_uncertain']).intersection(registry['retired'])


def test_windows_identity_regressions_remain_available_only_in_retired_scope():
    registry = json.loads((ROOT / 'tests/test_scopes.json').read_text(encoding='utf-8'))
    assert registry['retired']['tests/test_sg_beta_process_identity.py']['tests'] == [
        'test_actual_venv_child_json_resume_and_identity_rejection',
    ]


def test_ci_keeps_core_and_protected_checks_separate():
    workflow = (ROOT / '.github/workflows/governance-v2.yml').read_text(encoding='utf-8')
    assert 'python -m pytest -q --junitxml=outputs/test-timing/sora-active.xml' in workflow
    assert 'python -m pytest -q work/ci/commerce-api-core/tests --junitxml=outputs/test-timing/commerce-api-core.xml' in workflow
    assert 'python -m pytest tests/test_governance_v2.py tests/test_guardrails.py tests/test_prelisting_gate.py tests/test_sls_category_protected.py -q' in workflow
