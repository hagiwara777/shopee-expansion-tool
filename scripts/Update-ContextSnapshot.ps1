[CmdletBinding()]
param(
    [string]$PythonPath,
    [string]$OutputDirectory = "outputs/governance",
    [string]$TaskContext,
    [string]$Provider
)

$invoke = Join-Path $PSScriptRoot "Invoke-GovernanceV2.ps1"
& $invoke -Mode Generate -PythonPath $PythonPath -OutputDirectory $OutputDirectory -TaskContext $TaskContext -Provider $Provider
exit $LASTEXITCODE
