[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'ShopeeExpansionTool\SG-Beta\deployment.json'),
    [switch]$CheckOnly,
    [switch]$NoBrowser,
    [switch]$ShowError
)
$ErrorActionPreference = 'Stop'
try {
$profile = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$scriptRoot = Split-Path -Parent $PSScriptRoot
if ([IO.Path]::GetFullPath($profile.repository_path) -ne [IO.Path]::GetFullPath($scriptRoot)) {
    throw 'SG beta launcher does not belong to the configured release.'
}
Push-Location -LiteralPath $scriptRoot
try {
    & $profile.python_path -m modules.sg_beta_environment --config $ConfigPath
    if ($LASTEXITCODE -ne 0) { throw 'SG beta preflight did not pass.' }
    if ($CheckOnly) { return }
    New-Item -ItemType Directory -Force -Path $profile.data_root | Out-Null
    $lease = [IO.File]::Open((Join-Path $profile.data_root 'startup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        $recordPath = Join-Path $profile.data_root 'server.json'
        $configHash = (Get-FileHash -LiteralPath $ConfigPath -Algorithm SHA256).Hash
        $appPath = Join-Path $scriptRoot 'app_sg_beta.py'
        $listeners = @(Get-NetTCPConnection -State Listen -LocalPort 8502 -ErrorAction SilentlyContinue)
        if ($listeners.Count) {
            if (-not (Test-Path -LiteralPath $recordPath)) { throw 'SG port is used by another application.' }
            $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
            $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($record.pid)"
            if ($null -eq $process -or @($listeners | Where-Object OwningProcess -ne $record.pid).Count -or
                $record.config_sha256 -ne $configHash -or -not $process.CommandLine.Contains($appPath) -or
                $record.created_utc -ne $process.CreationDate.ToUniversalTime().ToString('o')) {
                throw 'The listening process is not the configured SG beta.'
            }
        } else {
            $logs = Join-Path $profile.data_root 'logs'
            New-Item -ItemType Directory -Force -Path $logs | Out-Null
            $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
            $arguments = @('-m','streamlit','run',$appPath,'--server.address','127.0.0.1',
                '--server.port','8502','--server.headless','true','--browser.gatherUsageStats','false',
                '--','--live-validation-grant',$profile.grant_path,'--api-env',$profile.api_env_path,
                '--runtime-root',$profile.data_root)
            # Windows paths cannot contain quotes. Quote each argument independently;
            # no generated command is evaluated by a shell.
            $quoted = ($arguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
            $previousReader = $env:GOOGLE_APPLICATION_CREDENTIALS
            try {
                $env:GOOGLE_APPLICATION_CREDENTIALS = $profile.google_credentials_path
                $server = Start-Process -FilePath $profile.python_path -ArgumentList $quoted -WorkingDirectory $scriptRoot `
                    -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs "$stamp.out.log") `
                    -RedirectStandardError (Join-Path $logs "$stamp.err.log") -PassThru
            } finally { $env:GOOGLE_APPLICATION_CREDENTIALS = $previousReader }
            $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($server.Id)"
            @{pid=$server.Id;config_sha256=$configHash;created_utc=$process.CreationDate.ToUniversalTime().ToString('o')} |
                ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding utf8
            $ready = $false
            for ($attempt=0; $attempt -lt 30; $attempt++) {
                if ($server.HasExited) { throw 'SG beta server exited before becoming ready.' }
                try {
                    $health = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8502/_stcore/health' -TimeoutSec 1
                    if ($health.StatusCode -eq 200) { $ready=$true; break }
                } catch { }
                Start-Sleep -Milliseconds 300
            }
            if (-not $ready) {
                if (-not $server.HasExited) { $server.Kill() }
                throw 'SG beta server did not become ready.'
            }
        }
        if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8502' }
        Write-Output 'PASS: SG beta is available at http://127.0.0.1:8502'
    } finally { $lease.Dispose() }
} finally { Pop-Location }
} catch {
    if ($ShowError) {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(
            'SG Beta could not start. Check the deployment settings and run Start-SGBeta.ps1 -CheckOnly.',
            'SG Beta', 'OK', 'Error') | Out-Null
    }
    throw 'SG beta startup failed. Check the dedicated SG configuration and private server logs.'
}
