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

function Test-StreamlitHealth {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8771/_stcore/health" -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200 -and $response.Content.Trim().ToLowerInvariant() -eq "ok"
    }
    catch {
        return $false
    }
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

function Test-E2EStreamlitProcess([int]$ProcessId, [string]$RepositoryRoot) {
    try {
        $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId").CommandLine
        if ([string]::IsNullOrWhiteSpace($commandLine)) {
            return $false
        }
        $normalizedCommandLine = $commandLine.ToLowerInvariant()
        $venvPython = (Join-Path $RepositoryRoot ".venv\Scripts\python.exe").ToLowerInvariant()
        $fullAppPath = (Join-Path $RepositoryRoot "app.py").ToLowerInvariant()
        $hasExpectedApp = $normalizedCommandLine.Contains($fullAppPath) -or
            $normalizedCommandLine -match '(^|\s|")app\.py($|\s|")'
        return $normalizedCommandLine.Contains($venvPython) -and
            $normalizedCommandLine.Contains("-m streamlit") -and
            $hasExpectedApp
    }
    catch {
        return $false
    }
}

$repositoryRoot = Get-FormalRepositoryRoot
$WorkspaceRoot = [IO.Path]::GetFullPath($WorkspaceRoot)
$python = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
$appPath = Join-Path $repositoryRoot "app.py"
$stateRoot = Join-Path $WorkspaceRoot "state"
$logsRoot = Join-Path $WorkspaceRoot "logs"
$pidPath = Join-Path $stateRoot "streamlit.pid"

try {
    if (-not (Test-Path -LiteralPath $python)) {
        throw "正式な仮想環境のPythonが見つかりません: $python"
    }
    if (-not (Test-Path -LiteralPath $appPath)) {
        throw "Streamlitのエントリーポイントが見つかりません: $appPath"
    }
    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $logsRoot -Force | Out-Null

    if (Test-StreamlitHealth) {
        $existingProcessId = Get-ListeningProcessId
        if ($null -eq $existingProcessId) {
            throw "8771番ポートは正常応答していますが、所有PIDを確認できません。"
        }
        if (-not (Test-E2EStreamlitProcess $existingProcessId $repositoryRoot)) {
            Write-Host "HEALTHY: Streamlit is already serving 8771, but it is not an E2E-managed app process. PIDファイルは更新しません。" -ForegroundColor Yellow
            exit 0
        }
        [IO.File]::WriteAllText($pidPath, "$existingProcessId`n", [Text.Encoding]::ASCII)
        Write-Host "READY: Streamlit is already healthy at http://127.0.0.1:8771 (PID $existingProcessId)" -ForegroundColor Green
        exit 0
    }

    $listenerProcessId = Get-ListeningProcessId
    if ($null -ne $listenerProcessId) {
        throw "8771番ポートはPID $listenerProcessId が使用中ですが、Streamlit health checkは正常ではありません。二重起動しません。"
    }
    if (Test-Path -LiteralPath $pidPath) {
        Remove-Item -LiteralPath $pidPath -Force
    }

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmssfff"
    $stdoutPath = Join-Path $logsRoot "streamlit-$timestamp.stdout.log"
    $stderrPath = Join-Path $logsRoot "streamlit-$timestamp.stderr.log"
    $arguments = @(
        "-m",
        "streamlit",
        "run",
        ('"{0}"' -f $appPath),
        "--server.address=127.0.0.1",
        "--server.port=8771",
        "--server.headless=true"
    )
    $process = Start-Process `
        -FilePath $python `
        -ArgumentList $arguments `
        -WorkingDirectory $repositoryRoot `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden `
        -PassThru

    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 1
        if (Test-StreamlitHealth) {
            $ownerProcessId = Get-ListeningProcessId
            if ($null -eq $ownerProcessId -or -not (Test-E2EStreamlitProcess $ownerProcessId $repositoryRoot)) {
                if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
                    Stop-Process -Id $process.Id -Force
                }
                throw "8771番ポートのPIDをE2E Streamlitとして確認できません。起動PID=$($process.Id) 待受PID=$ownerProcessId"
            }
            [IO.File]::WriteAllText($pidPath, "$ownerProcessId`n", [Text.Encoding]::ASCII)
            Write-Host "READY: Streamlit is healthy at http://127.0.0.1:8771 (PID $ownerProcessId)" -ForegroundColor Green
            exit 0
        }
    }

    if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
        Stop-Process -Id $process.Id -Force
    }
    $stdoutTail = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Tail 30 | Out-String } else { "(stdout log was not created)" }
    $stderrTail = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Tail 30 | Out-String } else { "(stderr log was not created)" }
    throw "Streamlitの起動またはhealth checkが30秒以内に成功しませんでした。`nstdout:`n$stdoutTail`nstderr:`n$stderrTail"
}
catch {
    Write-Error "Streamlit E2E start failed: $($_.Exception.Message)"
    exit 1
}
