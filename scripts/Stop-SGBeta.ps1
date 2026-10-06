[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'ShopeeExpansionTool\SG-Beta\deployment.json')
)
$ErrorActionPreference = 'Stop'
$profile = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$root = Split-Path -Parent $PSScriptRoot
if ([IO.Path]::GetFullPath($profile.repository_path) -ne [IO.Path]::GetFullPath($root) -or $profile.port -ne 8502) {
    throw 'SG stop command does not belong to the configured release.'
}
$recordPath = Join-Path $profile.data_root 'server.json'
if (-not (Test-Path -LiteralPath $recordPath)) { Write-Output 'SG beta has no recorded server.'; return }
$record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
$serverId = [int]$record.pid
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$serverId"
if ($null -eq $process) { Write-Output 'SG beta server is already stopped.'; return }
$appPath = Join-Path $root 'app_sg_beta.py'
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort 8502 -ErrorAction SilentlyContinue)
if (-not $process.CommandLine.Contains($appPath) -or
    $record.created_utc -ne $process.CreationDate.ToUniversalTime().ToString('o') -or
    @($listeners | Where-Object OwningProcess -ne $serverId).Count) {
    throw 'Recorded process identity differs; no process was stopped.'
}
Stop-Process -Id $serverId -ErrorAction Stop
Write-Output 'SG beta stopped. PH and all SG data/API ledgers are preserved.'
