[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [ValidateRange(1024, 65535)][int]$Port = 8502,
    [switch]$CheckOnly,
    [switch]$BetaRelease,
    [string]$LiveGrantPath,
    [string]$ApiEnvPath,
    [string]$GoogleCredentialsPath
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw "Python executable was not found." }
$candidateRoot = Split-Path -Parent $PSScriptRoot
$candidateApp = Join-Path $candidateRoot "app_sg_candidate.py"
if ($BetaRelease) {
    $candidateApp = Join-Path $candidateRoot "app_sg_beta.py"
    if (-not $CheckOnly -and -not $LiveGrantPath) { throw "SG beta requires an approved API run configuration." }
}
 $previousGoogleCredentials = $env:GOOGLE_APPLICATION_CREDENTIALS
Push-Location -LiteralPath $candidateRoot
try {
    if ($CheckOnly) {
        & $PythonPath -c "import streamlit; import app_sg_candidate; import app_sg_beta; from modules.sg_candidate_runtime import SGReplayBundle"
    } elseif ($LiveGrantPath) {
        if (-not (Test-Path -LiteralPath $LiveGrantPath -PathType Leaf)) { throw "Approved live grant file was not found." }
        if (-not $GoogleCredentialsPath -and -not $env:GOOGLE_APPLICATION_CREDENTIALS) {
            $existingReader = Join-Path $env:LOCALAPPDATA "ShopeeOpenPlatform\google\google-sheets-reader.json"
            if (Test-Path -LiteralPath $existingReader -PathType Leaf) { $GoogleCredentialsPath = $existingReader }
        }
        if ($GoogleCredentialsPath) {
            if (-not (Test-Path -LiteralPath $GoogleCredentialsPath -PathType Leaf)) { throw "Existing Google reader file was not found." }
            $env:GOOGLE_APPLICATION_CREDENTIALS = $GoogleCredentialsPath
        }
        $applicationArguments = @("--live-validation-grant", $LiveGrantPath)
        if ($ApiEnvPath) {
            if (-not (Test-Path -LiteralPath $ApiEnvPath -PathType Leaf)) { throw "Existing API settings file was not found." }
            $applicationArguments += @("--api-env", $ApiEnvPath)
        }
        & $PythonPath -m streamlit run $candidateApp --server.address 127.0.0.1 --server.port $Port --browser.gatherUsageStats false -- @applicationArguments
    } else {
        & $PythonPath -m streamlit run $candidateApp --server.address 127.0.0.1 --server.port $Port --browser.gatherUsageStats false
    }
    if ($LASTEXITCODE -ne 0) { throw "SG candidate startup failed." }
} finally {
    $env:GOOGLE_APPLICATION_CREDENTIALS = $previousGoogleCredentials
    Pop-Location
}
