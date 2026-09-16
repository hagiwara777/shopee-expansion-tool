[CmdletBinding()]
param(
    [string]$PythonPath,
    [string]$ContextPath = "outputs/governance/context.json",
    [string]$OutputDirectory = "outputs/governance",
    [ValidateSet("read-only", "local-change", "local-validation", "formal-acceptance")]
    [string]$Profile = "read-only",
    [string]$Provider,
    [string[]]$Evidence = @()
)

# Verifier is deliberately independent: it never calls the Generator and never
# deletes or rewrites an existing context.
$invoke = Join-Path $PSScriptRoot "Invoke-GovernanceV2.ps1"
& $invoke -Mode Verify -PythonPath $PythonPath -ContextPath $ContextPath -OutputDirectory $OutputDirectory -Profile $Profile -Provider $Provider -Evidence $Evidence
exit $LASTEXITCODE
