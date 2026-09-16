[CmdletBinding()]
param([string]$PythonPath)

$invoke = Join-Path $PSScriptRoot "Invoke-GovernanceV2.ps1"
& $invoke -Mode Validate -PythonPath $PythonPath
exit $LASTEXITCODE
