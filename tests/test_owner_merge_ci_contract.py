"""The readiness check must fail closed when any existing CI job is not successful."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[1]
PWSH = shutil.which('pwsh')
FIELDS = ('CHECK_GOVERNANCE', 'CHECK_PS51', 'CHECK_PS7', 'CHECK_OFFLINE', 'CHECK_PROTECTED')


@pytest.mark.skipif(PWSH is None, reason='PowerShell 7 is required to exercise the CI step')
@pytest.mark.parametrize('result', ['success', 'failure', 'skipped', 'cancelled', 'neutral', ''])
def test_owner_merge_readiness_requires_each_job_to_succeed(result):
    workflow = (ROOT / '.github/workflows/governance-v2.yml').read_text(encoding='utf-8')
    job = workflow.split('  owner-merge-readiness:\n', 1)[1]
    needs = re.search(r'^    needs: \[(.+)\]$', job, re.MULTILINE)
    assert needs is not None
    assert set(needs.group(1).split(', ')) == {'governance', 'powershell-51', 'powershell-7', 'offline-tests', 'protected-capabilities'}
    assert '    if: ${{ always() }}' in job
    for field, dependency in zip(FIELDS, ('governance', 'powershell-51', 'powershell-7', 'offline-tests', 'protected-capabilities')):
        assert f'{field}: ${{{{ needs.{dependency}.result }}}}' in job
    script = textwrap.dedent(job.split('        run: |\n', 1)[1])
    env = os.environ.copy()
    env.update({field: 'success' for field in FIELDS})
    for field in FIELDS:
        env[field] = result
        completed = subprocess.run([PWSH, '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script], env=env, capture_output=True, timeout=20, check=False)
        assert (completed.returncode == 0) == (result == 'success'), field
        env[field] = 'success'
