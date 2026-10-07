[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'ShopeeExpansionTool\Beta\deployment.json')
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'SGBetaProcess.ps1')
$profile = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$root = Split-Path -Parent $PSScriptRoot
if ([IO.Path]::GetFullPath($profile.repository_path) -ne [IO.Path]::GetFullPath($root) -or $profile.port -ne 8503) {
    throw 'Beta stop command does not belong to the configured release.'
}
$recordPath = Join-Path $profile.server_data_root 'server.json'
if (-not (Test-Path -LiteralPath $recordPath)) { Write-Output 'PH/SG beta has no recorded server.'; return }
$record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
$appPath = Join-Path $root 'app_beta.py'
$identity = Get-SGBetaProcessIdentity -AppPath $appPath -Port 8503 -RecordedIdentity $record -AllowNoListener
if ($null -eq $identity) { Write-Output 'PH/SG beta server is already stopped.'; return }
Stop-Process -Id $identity.pid -ErrorAction Stop
Write-Output 'PH/SG beta stopped. PH and all SG data/API ledgers are preserved.'
