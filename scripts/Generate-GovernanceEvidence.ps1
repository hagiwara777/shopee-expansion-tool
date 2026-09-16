[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("governance.validate", "governance.ps51", "governance.ps7")]
    [string]$GateId,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [string]$PythonPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = (& git -C (Join-Path $PSScriptRoot "..") rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0) { throw "The Git repository root could not be determined." }
$python = if ($PythonPath) { $PythonPath } elseif ($env:GOVERNANCE_PYTHON) { $env:GOVERNANCE_PYTHON } else { "python" }
& $python -m governance.engine ci-evidence --repository $repositoryRoot --gate-id $GateId --output-dir $OutputDirectory
exit $LASTEXITCODE
