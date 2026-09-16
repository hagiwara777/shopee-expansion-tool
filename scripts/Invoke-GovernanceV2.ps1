[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Validate", "Generate", "Verify")]
    [string]$Mode,
    [string]$PythonPath,
    [string]$OutputDirectory = "outputs/governance",
    [string]$ContextPath = "outputs/governance/context.json",
    [ValidateSet("read-only", "local-change", "local-validation", "formal-acceptance")]
    [string]$Profile = "read-only",
    [string]$TaskContext,
    [string]$Provider,
    [string[]]$Evidence = @()
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-GovernancePython {
    param([string]$ExplicitPath)

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) {
            throw "The explicitly selected Python executable was not found."
        }
        return @{ Command = (Resolve-Path -LiteralPath $ExplicitPath).Path; Prefix = @() }
    }
    if (-not [string]::IsNullOrWhiteSpace($env:GOVERNANCE_PYTHON)) {
        if (-not (Test-Path -LiteralPath $env:GOVERNANCE_PYTHON -PathType Leaf)) {
            throw "GOVERNANCE_PYTHON does not identify a Python executable."
        }
        return @{ Command = (Resolve-Path -LiteralPath $env:GOVERNANCE_PYTHON).Path; Prefix = @() }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        $python = Get-Command python -ErrorAction SilentlyContinue
    }
    if ($null -ne $python) {
        return @{ Command = $python.Source; Prefix = @() }
    }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        return @{ Command = $py.Source; Prefix = @("-3") }
    }
    throw "No Python executable is available for Governance v2."
}

$repositoryRoot = (& git -C (Join-Path $PSScriptRoot "..") rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "The Git repository root could not be determined."
}
$pythonCommand = Resolve-GovernancePython -ExplicitPath $PythonPath
$arguments = @($pythonCommand.Prefix) + @("-m", "governance.engine")
switch ($Mode) {
    "Validate" {
        $arguments += @("validate", "--repository", $repositoryRoot)
    }
    "Generate" {
        $arguments += @("generate", "--repository", $repositoryRoot, "--output-dir", $OutputDirectory)
        if (-not [string]::IsNullOrWhiteSpace($TaskContext)) {
            $arguments += @("--task-context", $TaskContext)
        }
        if (-not [string]::IsNullOrWhiteSpace($Provider)) {
            $arguments += @("--provider", $Provider)
        }
    }
    "Verify" {
        $arguments += @("verify", "--repository", $repositoryRoot, "--context", $ContextPath, "--profile", $Profile, "--output-dir", $OutputDirectory)
        if (-not [string]::IsNullOrWhiteSpace($Provider)) {
            $arguments += @("--provider", $Provider)
        }
        foreach ($evidencePath in $Evidence) {
            $arguments += @("--evidence", $evidencePath)
        }
    }
}

Push-Location $repositoryRoot
try {
    & $pythonCommand.Command @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
