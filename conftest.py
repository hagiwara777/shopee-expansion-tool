"""Select reviewed test cases without changing or deleting the tests themselves."""
from __future__ import annotations

import json
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parent


def pytest_addoption(parser):
    parser.getgroup('Sora test scope').addoption(
        '--test-scope', choices=('active', 'retired', 'all'), default='active',
        help='active: normal suite; retired: preserved discontinued-feature tests; all: both',
    )


def _retired_nodes():
    try:
        registry = json.loads((ROOT / 'tests' / 'test_scopes.json').read_text(encoding='utf-8'))
        if registry['schema_version'] != 1 or not isinstance(registry['retired'], dict):
            raise ValueError
        nodes = set()
        for file, entry in registry['retired'].items():
            if not re.fullmatch(r'tests/test_[A-Za-z0-9_]+\.py', file):
                raise ValueError
            if not entry['reason'] or not isinstance(entry['tests'], list):
                raise ValueError
            for name in entry['tests']:
                if not re.fullmatch(r'test_[A-Za-z0-9_]+', name):
                    raise ValueError
                node = file + '::' + name
                if node in nodes:
                    raise ValueError
                nodes.add(node)
        return nodes
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise pytest.UsageError('Invalid tests/test_scopes.json; refusing an unverified test selection') from exc


def pytest_collection_modifyitems(config, items):
    retired_nodes = _retired_nodes()
    scope = config.getoption('--test-scope')
    selected, deselected = [], []
    for item in items:
        retired = item.nodeid.split('[', 1)[0] in retired_nodes
        include = scope == 'all' or (scope == 'retired') == retired
        (selected if include else deselected).append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected


def pytest_report_header(config):
    return 'Sora test scope: ' + config.getoption('--test-scope')
