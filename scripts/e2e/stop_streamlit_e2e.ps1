[CmdletBinding()]
param(
    [string]$WorkspaceRoot = (Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::MyDocuments)) "ShopeeE2E")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-FormalRepositoryRoot {
    $scriptRepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    $gitRepositoryRoot = (& git -C $scriptRepositoryRoot rev-parse --show-toplevel).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Gitリポジトリのルートを確認できません。正式リポジトリから実行してください。"
    }

    $scriptRootFull = [IO.Path]::GetFullPath($scriptRepositoryRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $gitRootFull = [IO.Path]::GetFullPath($gitRepositoryRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if (-not [string]::Equals($scriptRootFull, $gitRootFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "このスクリプトは正式リポジトリの scripts\\e2e から実行する必要があります。"
    }
    return $gitRootFull
}

function Get-ListeningProcessId {
    try {
        $owners = @(
            Get-NetTCPConnection -LocalPort 8771 -State Listen -ErrorAction Stop |
                Select-Object -ExpandProperty OwningProcess -Unique
        )
        if ($owners.Count -eq 1) {
            return [int]$owners[0]
        }
    }
    catch {
        return $null
    }
    return $null
}

$repositoryRoot = Get-FormalRepositoryRoot
$WorkspaceRoot = [IO.Path]::GetFullPath($WorkspaceRoot)
$pidPath = Join-Path (Join-Path $WorkspaceRoot "state") "streamlit.pid"
$venvPython = (Join-Path $repositoryRoot ".venv\Scripts\python.exe").ToLowerInvariant()
$appPath = (Join-Path $repositoryRoot "app.py").ToLowerInvariant()

try {
    if (-not (Test-Path -LiteralPath $pidPath)) {
        if ($null -eq (Get-ListeningProcessId)) {
            Write-Host "STOPPED: PIDファイルも8771番ポートの待受もありません。" -ForegroundColor Green
            exit 0
        }
        throw "PIDファイルがありません。8771番ポートのプロセスには触れません。"
    }

    $pidText = (Get-Content -LiteralPath $pidPath -Raw).Trim()
    $streamlitProcessId = 0
    if (-not [int]::TryParse($pidText, [ref]$streamlitProcessId) -or $streamlitProcessId -lt 1) {
        throw "PIDファイルの内容が不正です: $pidPath"
    }

    $process = Get-Process -Id $streamlitProcessId -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Remove-Item -LiteralPath $pidPath -Force
        if ($null -ne (Get-ListeningProcessId)) {
            throw "PID $streamlitProcessId は存在しませんが、8771番ポートは別プロセスが使用中です。"
        }
        Write-Host "STOPPED: 記録済みPIDはすでに終了しており、PIDファイルを削除しました。" -ForegroundColor Green
        exit 0
    }

    $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $streamlitProcessId").CommandLine
    $normalizedCommandLine = if ($null -eq $commandLine) { "" } else { $commandLine.ToLowerInvariant() }
    $hasExpectedApp = $normalizedCommandLine.Contains($appPath) -or
        $normalizedCommandLine -match '(^|\s|")app\.py($|\s|")'
    if ([string]::IsNullOrWhiteSpace($normalizedCommandLine) -or
        -not $normalizedCommandLine.Contains($venvPython) -or
        -not $normalizedCommandLine.Contains("-m streamlit") -or
        -not $hasExpectedApp) {
        throw "PID $streamlitProcessId はこのE2E Streamlit起動として確認できません。別のPythonプロセスを終了しません。"
    }

    $listenerProcessId = Get-ListeningProcessId
    if ($listenerProcessId -ne $streamlitProcessId) {
        throw "PID $streamlitProcessId は8771番ポートを所有していません。別プロセスを終了しません。"
    }

    Stop-Process -Id $streamlitProcessId -Force
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline -and $null -ne (Get-ListeningProcessId)) {
        Start-Sleep -Milliseconds 500
    }
    if ($null -ne (Get-ListeningProcessId)) {
        throw "停止後も8771番ポートが待受中です。PIDファイルは確認のため残しました。"
    }

    Remove-Item -LiteralPath $pidPath -Force
    if (Test-Path -LiteralPath $pidPath) {
        throw "PIDファイルを削除できませんでした: $pidPath"
    }
    Write-Host "STOPPED: Streamlit PID $streamlitProcessId を終了し、8771番ポートとPIDファイルが解放されました。" -ForegroundColor Green
}
catch {
    Write-Error "Streamlit E2E stop failed: $($_.Exception.Message)"
    exit 1
}
