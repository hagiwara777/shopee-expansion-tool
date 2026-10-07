[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'ShopeeExpansionTool\Beta\deployment.json'),
    [switch]$CheckOnly,
    [switch]$NoBrowser,
    [switch]$ShowError
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'SGBetaProcess.ps1')
try {
$profile = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$scriptRoot = Split-Path -Parent $PSScriptRoot
if ([IO.Path]::GetFullPath($profile.repository_path) -ne [IO.Path]::GetFullPath($scriptRoot)) {
    throw 'PH/SG beta launcher does not belong to the configured release.'
}
Push-Location -LiteralPath $scriptRoot
try {
    & $profile.python_path -m modules.beta_environment --config $ConfigPath
    if ($LASTEXITCODE -ne 0) { throw 'PH/SG beta preflight did not pass.' }
    if ($CheckOnly) { return }
    New-Item -ItemType Directory -Force -Path $profile.server_data_root | Out-Null
    $lease = [IO.File]::Open((Join-Path $profile.server_data_root 'startup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        $recordPath = Join-Path $profile.server_data_root 'server.json'
        $configHash = (Get-FileHash -LiteralPath $ConfigPath -Algorithm SHA256).Hash
        $appPath = Join-Path $scriptRoot 'app_beta.py'
        $listeners = @(Get-NetTCPConnection -State Listen -LocalPort 8503 -ErrorAction SilentlyContinue)
        if ($listeners.Count) {
            if (-not (Test-Path -LiteralPath $recordPath)) { throw 'Beta port is used by another application.' }
            $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
            $identity = Get-SGBetaProcessIdentity -AppPath $appPath -Port 8503 -RecordedIdentity $record
            if ($null -eq $identity -or $record.config_sha256 -ne $configHash) {
                throw 'The listening process is not the configured PH/SG beta.'
            }
        } else {
            $logs = Join-Path $profile.server_data_root 'logs'
            New-Item -ItemType Directory -Force -Path $logs | Out-Null
            $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
            $arguments = @('-m','streamlit','run',$appPath,'--server.address','127.0.0.1',
                '--server.port','8503','--server.headless','true','--browser.gatherUsageStats','false',
                '--','--sg-config',$profile.sg_config_path,'--ph-runtime-root',$profile.ph_runtime_root,
                '--ph-api-env',$profile.ph_api_env_path)
            # Windows paths cannot contain quotes. Quote each argument independently;
            # no generated command is evaluated by a shell.
            $quoted = ($arguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
            $previousReader = $env:GOOGLE_APPLICATION_CREDENTIALS
            try {
                $sgProfile = Get-Content -LiteralPath $profile.sg_config_path -Raw | ConvertFrom-Json
                $env:GOOGLE_APPLICATION_CREDENTIALS = $sgProfile.google_credentials_path
                $server = Start-Process -FilePath $profile.python_path -ArgumentList $quoted -WorkingDirectory $scriptRoot `
                    -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs "$stamp.out.log") `
                    -RedirectStandardError (Join-Path $logs "$stamp.err.log") -PassThru
            } finally { $env:GOOGLE_APPLICATION_CREDENTIALS = $previousReader }
            $ready = $false
            for ($attempt=0; $attempt -lt 30; $attempt++) {
                if ($server.HasExited) { throw 'PH/SG beta server exited before becoming ready.' }
                try {
                    $health = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8503/_stcore/health' -TimeoutSec 1
                    if ($health.StatusCode -eq 200) { $ready=$true; break }
                } catch { }
                Start-Sleep -Milliseconds 300
            }
            if (-not $ready) {
                if (-not $server.HasExited) { $server.Kill() }
                throw 'PH/SG beta server did not become ready.'
            }
            $identity = Get-SGBetaProcessIdentity -AppPath $appPath -Port 8503 -LauncherId $server.Id
            @{schema_version=1;pid=$identity.pid;config_sha256=$configHash;created_utc_ticks=$identity.created_utc_ticks} |
                ConvertTo-Json | Set-Content -LiteralPath $recordPath -Encoding utf8
        }
        if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8503' }
        Write-Output 'PASS: PH/SG beta is available at http://127.0.0.1:8503'
    } finally { $lease.Dispose() }
} finally { Pop-Location }
} catch {
    if ($ShowError) {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(
            'Shopee Beta could not start. Check the deployment settings and run Start-Beta.ps1 -CheckOnly.',
            'Shopee Beta', 'OK', 'Error') | Out-Null
    }
    throw 'PH/SG beta startup failed. Check the dedicated SG configuration and private server logs.'
}
