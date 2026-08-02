[CmdletBinding()]
param(
    [string]$BriefPath,
    [switch]$SkipBriefPathExitTest
)

$ErrorActionPreference = "Stop"

if ($PSBoundParameters.Count -gt 0) {
    Write-Warning "Verify-WorkBriefHandoff.ps1 の旧引数は廃止されました。scripts/Verify-LightweightDevelopmentPolicy.ps1 を使用してください。"
    exit 2
}

Write-Warning "Verify-WorkBriefHandoff.ps1 は廃止予定の互換ファイルです。Verify-LightweightDevelopmentPolicy.ps1 を実行します。"
& (Join-Path $PSScriptRoot "Verify-LightweightDevelopmentPolicy.ps1")
exit $LASTEXITCODE
