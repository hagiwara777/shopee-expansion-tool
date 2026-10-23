[CmdletBinding()]
param(
    [string]$PythonPath,
    [string]$OutputDirectory = "outputs/governance",
    [string]$TaskContext,
    [ValidateSet("local-file", "ci-env-json")]
    [string]$TrustAnchorSource,
    [string]$Provider
)

$invoke = Join-Path $PSScriptRoot "Invoke-GovernanceV2.ps1"
& $invoke -Mode Generate -PythonPath $PythonPath -OutputDirectory $OutputDirectory -TaskContext $TaskContext -TrustAnchorSource $TrustAnchorSource -Provider $Provider
exit $LASTEXITCODE
