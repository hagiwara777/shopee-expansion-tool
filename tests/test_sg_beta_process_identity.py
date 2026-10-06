"""Real Windows venv listener identity; no Shopee/OpenAI or production data."""
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import venv

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('shell_name', ['powershell', 'pwsh'])
def test_actual_venv_child_json_resume_and_identity_rejection(tmp_path, shell_name):
    shell = shutil.which(shell_name)
    if sys.platform != 'win32' or not shell:
        pytest.skip('Windows PowerShell required')
    environment = tmp_path / 'venv'
    venv.EnvBuilder(with_pip=False).create(environment)
    app = tmp_path / 'local_server.py'
    app.write_text('import http.server,sys\nhttp.server.ThreadingHTTPServer(("127.0.0.1",int(sys.argv[1])),http.server.BaseHTTPRequestHandler).serve_forever()\n')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    driver = tmp_path / 'identity-test.ps1'
    driver.write_text(r'''
param($Helper,$Python,$App,[int]$Port,$Directory)
$ErrorActionPreference='Stop'
. $Helper
$launcher=Start-Process -FilePath $Python -ArgumentList ('"'+$App+'" '+$Port) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Directory 'out.log') -RedirectStandardError (Join-Path $Directory 'err.log')
try {
    $ready=$false
    for($attempt=0;$attempt -lt 50;$attempt++) {
        try { $identity=Get-SGBetaProcessIdentity -AppPath $App -Port $Port -LauncherId $launcher.Id; $ready=$true; break } catch { Start-Sleep -Milliseconds 100 }
    }
    if(-not $ready -or $identity.pid -eq $launcher.Id) { throw 'Real venv interpreter child was not captured' }
    $recordPath=Join-Path $Directory 'record.json'
    $identity | ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding utf8
    $record=Get-Content -LiteralPath $recordPath -Raw|ConvertFrom-Json
    $resumed=Get-SGBetaProcessIdentity -AppPath $App -Port $Port -RecordedIdentity $record
    if($resumed.pid -ne $identity.pid) { throw 'JSON resume did not preserve actual listener' }
    $record.created_utc_ticks++
    $rejected=$false
    try { Get-SGBetaProcessIdentity -AppPath $App -Port $Port -RecordedIdentity $record | Out-Null } catch { $rejected=$true }
    if(-not $rejected) { throw 'Wrong creation identity accepted' }
    $rejected=$false
    try { Get-SGBetaProcessIdentity -AppPath 'different-app.py' -Port $Port -LauncherId $launcher.Id | Out-Null } catch { $rejected=$true }
    if(-not $rejected) { throw 'Unrelated app accepted' }
    $rejected=$false
    try { Get-SGBetaProcessIdentity -AppPath $App -Port $Port -LauncherId 0 | Out-Null } catch { $rejected=$true }
    if(-not $rejected) { throw 'Unowned listener accepted' }
    Write-Output 'PASS: actual venv child, JSON resume and mismatched identity rejection'
} finally {
    # Cleanup only the test interpreter child whose parent and command match.
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$($launcher.Id)" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($App) } | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
    Stop-Process -Id $launcher.Id -ErrorAction SilentlyContinue
}
''', encoding='utf-8-sig')
    result = subprocess.run([shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(driver),
        '-Helper', str(ROOT/'scripts/SGBetaProcess.ps1'), '-Python', str(environment/'Scripts/python.exe'),
        '-App', str(app), '-Port', str(port), '-Directory', str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS: actual venv child' in result.stdout
