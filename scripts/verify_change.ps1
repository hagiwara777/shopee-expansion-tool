[CmdletBinding()]
param(
    [ValidateSet("Quick", "Full", "Browser")]
    [string]$Mode = "Quick",

    [string[]]$TargetTest = @(
        "tests/test_change_verification_loop.py",
        "tests/test_browser_e2e_fixture_contract.py",
        "tests/test_app_prelisting_gate.py"
    ),

    [ValidateSet("Auto", "Prepare", "Verify")]
    [string]$BrowserStage = "Auto",

    [ValidateSet("v1", "v2")]
    [string]$FixtureVersion = "v2",

    [string]$DownloadPath,

    [string]$ReportPath,

    [switch]$BrowserUiChecksPassed,

    [switch]$RemoveDownloadedCsv,

    # Used only by contract tests. It exercises the same reporting and stage
    # orchestration without launching subprocesses or touching ShopeeE2E.
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SectionNames = @(
    "Git開始状態",
    "変更ファイル",
    "対象テスト",
    "全回帰",
    "構文・diff検査",
    "セキュリティ監査",
    "AppTest",
    "Browser E2E",
    "ダウンロードCSV検証",
    "清掃結果",
    "未確認事項",
    "Git終了状態"
)
$script:Stages = [System.Collections.Generic.List[object]]::new()
$script:HasFailure = $false
$script:ChangedFiles = @()
$script:BrowserResult = $null
$script:RepositoryRoot = $null
$script:ArtifactRoot = $null

function Get-FormalRepositoryRoot {
    $scriptRepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $gitRepositoryRoot = (& git -C $scriptRepositoryRoot rev-parse --show-toplevel).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Gitリポジトリのルートを確認できません。"
    }
    $scriptRootFull = [IO.Path]::GetFullPath($scriptRepositoryRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $gitRootFull = [IO.Path]::GetFullPath($gitRepositoryRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if (-not [string]::Equals($scriptRootFull, $gitRootFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "このスクリプトは正式リポジトリの scripts から実行する必要があります。"
    }
    return $gitRootFull
}

function Test-PathInside([string]$Path, [string]$ParentPath) {
    $fullPath = [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $fullParent = [IO.Path]::GetFullPath($ParentPath).TrimEnd([IO.Path]::DirectorySeparatorChar)
    return $fullPath.StartsWith($fullParent + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
        [string]::Equals($fullPath, $fullParent, [StringComparison]::OrdinalIgnoreCase)
}

function New-Stage([string]$Name) {
    return [pscustomobject]@{
        Name = $Name
        StartedAt = Get-Date
        EndedAt = $null
        DurationSeconds = $null
        ExitCode = ""
        Status = "RUNNING"
        Detail = ""
        StdOutPath = $null
        StdErrPath = $null
    }
}

function Complete-Stage([object]$Stage, [string]$Status, [string]$ExitCode, [string]$Detail) {
    $Stage.EndedAt = Get-Date
    $Stage.DurationSeconds = [Math]::Round(($Stage.EndedAt - $Stage.StartedAt).TotalSeconds, 3)
    $Stage.ExitCode = $ExitCode
    $Stage.Status = $Status
    $Stage.Detail = $Detail
    $script:Stages.Add($Stage)
    if ($Status -eq "FAIL") {
        $script:HasFailure = $true
    }
    return $Stage
}

function Add-InProcessStage([string]$Name, [scriptblock]$Action) {
    $stage = New-Stage $Name
    if ($DryRun) {
        return Complete-Stage $stage "SKIPPED" "DRY_RUN" "dry-run"
    }
    try {
        $detail = & $Action
        return Complete-Stage $stage "PASS" "0" ([string]$detail)
    }
    catch {
        return Complete-Stage $stage "FAIL" "INTERNAL_ERROR" $_.Exception.Message
    }
}

function Invoke-ProcessStage(
    [string]$Name,
    [string]$FilePath,
    [string[]]$Arguments,
    [ValidateRange(1, 600)][int]$TimeoutSeconds
) {
    $stage = New-Stage $Name
    if ($DryRun) {
        return Complete-Stage $stage "SKIPPED" "DRY_RUN" "dry-run"
    }

    $stageId = "{0:D2}" -f ($script:Stages.Count + 1)
    $stage.StdOutPath = Join-Path $script:ArtifactRoot "$stageId.stdout.log"
    $stage.StdErrPath = Join-Path $script:ArtifactRoot "$stageId.stderr.log"
    try {
        $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $script:RepositoryRoot -RedirectStandardOutput $stage.StdOutPath -RedirectStandardError $stage.StdErrPath -PassThru -WindowStyle Hidden
        if (-not $process.WaitForExit([int]($TimeoutSeconds * 1000))) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $null = $process.WaitForExit(5000)
            return Complete-Stage $stage "FAIL" "TIMEOUT" "process timeout after $TimeoutSeconds seconds"
        }
        # The finite overload confirms process termination; the parameterless
        # call then finalizes redirected stream state before ExitCode is read.
        $process.WaitForExit()
        $process.Refresh()
        $exitCode = [int]$process.ExitCode
        if ($exitCode -eq 0) {
            return Complete-Stage $stage "PASS" $exitCode "completed"
        }
        return Complete-Stage $stage "FAIL" $exitCode "process exited non-zero"
    }
    catch {
        return Complete-Stage $stage "FAIL" "START_ERROR" $_.Exception.Message
    }
}

function Get-StageOutput([object]$Stage) {
    if ($null -eq $Stage.StdOutPath -or -not (Test-Path -LiteralPath $Stage.StdOutPath)) {
        return ""
    }
    return [IO.File]::ReadAllText($Stage.StdOutPath)
}

function Get-StageStatus([string[]]$Names) {
    $selected = @($script:Stages | Where-Object { $_.Name -in $Names })
    if ($selected.Count -eq 0) {
        return "NOT_RUN"
    }
    if (@($selected | Where-Object { $_.Status -eq "FAIL" }).Count -gt 0) {
        return "FAIL"
    }
    if (@($selected | Where-Object { $_.Status -eq "PASS" }).Count -gt 0) {
        return "PASS"
    }
    if (@($selected | Where-Object { $_.Status -eq "SKIPPED" }).Count -eq $selected.Count) {
        return "SKIPPED"
    }
    return "NOT_RUN"
}

function Get-SectionDetail([string[]]$Names) {
    $selected = @($script:Stages | Where-Object { $_.Name -in $Names })
    if ($selected.Count -eq 0) {
        return "not run"
    }
    return (($selected | ForEach-Object { "$($_.Name)=$($_.Status)" }) -join ", ")
}

function Assert-TargetTests([string[]]$Tests) {
    foreach ($test in $Tests) {
        $filePart = ($test -split "::", 2)[0]
        $candidate = Join-Path $script:RepositoryRoot $filePart
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            throw "対象テストが見つかりません: $filePart"
        }
        if (-not (Test-PathInside $candidate (Join-Path $script:RepositoryRoot "tests"))) {
            throw "対象テストは tests 配下だけを指定してください: $filePart"
        }
    }
}

function Invoke-PowerShellSyntaxCheck {
    $scriptsRoot = Join-Path $script:RepositoryRoot "scripts"
    $scriptFiles = @(Get-ChildItem -LiteralPath $scriptsRoot -Recurse -File -Filter "*.ps1")
    $errors = [System.Collections.Generic.List[string]]::new()
    foreach ($scriptFile in $scriptFiles) {
        $tokens = $null
        $parseErrors = $null
        [System.Management.Automation.Language.Parser]::ParseFile(
            $scriptFile.FullName,
            [ref]$tokens,
            [ref]$parseErrors
        ) | Out-Null
        foreach ($parseError in $parseErrors) {
            $relativePath = [IO.Path]::GetRelativePath($script:RepositoryRoot, $scriptFile.FullName)
            $errors.Add("${relativePath}:$($parseError.Extent.StartLineNumber) $($parseError.Message)")
        }
    }
    if ($errors.Count -gt 0) {
        throw ($errors -join "; ")
    }
    return "$($scriptFiles.Count) script(s) parsed"
}

function Invoke-SecurityAudit {
    if ($DryRun) {
        return Complete-Stage (New-Stage "セキュリティ監査") "SKIPPED" "DRY_RUN" "dry-run"
    }
    $tracked = Invoke-ProcessStage "security tracked files" "git.exe" @("-C", $script:RepositoryRoot, "ls-files") 20
    $unstaged = Invoke-ProcessStage "security unstaged diff" "git.exe" @("-C", $script:RepositoryRoot, "diff", "--no-ext-diff", "--unified=0") 20
    $staged = Invoke-ProcessStage "security staged diff" "git.exe" @("-C", $script:RepositoryRoot, "diff", "--cached", "--no-ext-diff", "--unified=0") 20
    $stage = New-Stage "セキュリティ監査"
    if ($tracked.Status -ne "PASS" -or $unstaged.Status -ne "PASS" -or $staged.Status -ne "PASS") {
        return Complete-Stage $stage "FAIL" "DEPENDENCY_FAILED" "security audit command failed"
    }

    $forbiddenPathPattern = "(?i)(^|/)(\.env(\..*)?|\.venv/|venv/|__pycache__/|\.pytest_cache/|\.pytest_tmp/|outputs?/|cache/|work/)|\.(pyc|pyo|sqlite3?|db)$"
    $allowedEnvironmentTemplates = "(?i)(^|/)\.env\.example$"
    $trackedFiles = @((Get-StageOutput $tracked) -split "`r?`n" | Where-Object { $_ })
    $forbiddenTracked = @($trackedFiles | Where-Object { $_ -match $forbiddenPathPattern -and $_ -notmatch $allowedEnvironmentTemplates })
    $forbiddenChanged = @($script:ChangedFiles | Where-Object { $_ -match $forbiddenPathPattern -and $_ -notmatch $allowedEnvironmentTemplates })
    $diffLines = @((Get-StageOutput $unstaged), (Get-StageOutput $staged)) -join "`n"
    $secretPattern = '(?i)(?:\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)\b\s*[:=]\s*[''"]?[^\s''"]{8,}|\bgh[pousr]_[a-z0-9]{20,}|\bsk-[a-z0-9]{16,}|\bAKIA[0-9A-Z]{16}\b|authorization\s*:\s*bearer\s+\S+)'
    $secretHitCount = @($diffLines -split "`r?`n" | Where-Object { $_ -match "^\+(?!\+\+)" -and $_ -match $secretPattern }).Count
    if ($forbiddenTracked.Count -gt 0 -or $forbiddenChanged.Count -gt 0 -or $secretHitCount -gt 0) {
        return Complete-Stage $stage "FAIL" "FINDING" "tracked=$($forbiddenTracked.Count), changed=$($forbiddenChanged.Count), potential_secret_lines=$secretHitCount"
    }
    return Complete-Stage $stage "PASS" "0" "tracked forbidden=0, changed forbidden=0, potential secret lines=0"
}

function Invoke-QuickChecks([string]$Python) {
    $gitStart = Invoke-ProcessStage "Git開始状態" "git.exe" @("-C", $script:RepositoryRoot, "status", "--porcelain=v1") 20
    $branch = Invoke-ProcessStage "Git branch" "git.exe" @("-C", $script:RepositoryRoot, "branch", "--show-current") 20
    $head = Invoke-ProcessStage "Git HEAD" "git.exe" @("-C", $script:RepositoryRoot, "rev-parse", "--short", "HEAD") 20
    if ($gitStart.Status -eq "PASS") {
        $script:ChangedFiles = @((Get-StageOutput $gitStart) -split "`r?`n" | Where-Object { $_ } | ForEach-Object { $_.Substring(3) })
        $branchValue = (Get-StageOutput $branch).Trim()
        $headValue = (Get-StageOutput $head).Trim()
        $gitStart.Detail = "branch=$branchValue, HEAD=$headValue, worktree entries=$($script:ChangedFiles.Count)"
    }
    $changeStage = Add-InProcessStage "変更ファイル" {
        if ($DryRun) { return "dry-run" }
        if ($script:ChangedFiles.Count -eq 0) { return "0 files" }
        return "$($script:ChangedFiles.Count) file(s): $($script:ChangedFiles -join ', ')"
    }

    $targetStage = New-Stage "対象テスト"
    if ($DryRun) {
        Complete-Stage $targetStage "SKIPPED" "DRY_RUN" "dry-run" | Out-Null
    }
    else {
        try {
            Assert-TargetTests $TargetTest
            $targetStage = Invoke-ProcessStage "対象テスト" $Python (@("-m", "pytest") + $TargetTest + @("-q")) 120
        }
        catch {
            Complete-Stage $targetStage "FAIL" "INVALID_TARGET" $_.Exception.Message | Out-Null
        }
    }

    Invoke-ProcessStage "Python構文検査" $Python @("scripts/check_python_syntax.py") 60 | Out-Null
    Add-InProcessStage "PowerShell構文検査" { Invoke-PowerShellSyntaxCheck } | Out-Null
    Invoke-ProcessStage "git diff --check" "git.exe" @("-C", $script:RepositoryRoot, "diff", "--check") 20 | Out-Null
    Invoke-ProcessStage "git diff --cached --check" "git.exe" @("-C", $script:RepositoryRoot, "diff", "--cached", "--check") 20 | Out-Null
    Invoke-SecurityAudit | Out-Null
}

function Invoke-StreamlitSmoke {
    $started = $false
    try {
        $startScript = Join-Path $script:RepositoryRoot "scripts\e2e\start_streamlit_e2e.ps1"
        Invoke-ProcessStage "Streamlit起動" "powershell.exe" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $startScript) 45 | Out-Null
        $started = $true
        $health = Invoke-ProcessStage "health HTTP確認" "curl.exe" @("--fail", "--silent", "--show-error", "--max-time", "10", "http://127.0.0.1:8771/_stcore/health") 15
        if ($health.Status -eq "PASS" -and (Get-StageOutput $health).Trim().ToLowerInvariant() -ne "ok") {
            $health.Status = "FAIL"; $health.ExitCode = "INVALID_RESPONSE"; $health.Detail = "health body was not ok"; $script:HasFailure = $true
        }
        $root = Invoke-ProcessStage "root HTTP確認" "curl.exe" @("--fail", "--silent", "--show-error", "--max-time", "10", "--output", "NUL", "--write-out", "%{http_code}", "http://127.0.0.1:8771/") 15
        if ($root.Status -eq "PASS" -and (Get-StageOutput $root).Trim() -ne "200") {
            $root.Status = "FAIL"; $root.ExitCode = "INVALID_RESPONSE"; $root.Detail = "root did not return HTTP 200"; $script:HasFailure = $true
        }
    }
    finally {
        if ($started -or $Mode -eq "Full") {
            $stopScript = Join-Path $script:RepositoryRoot "scripts\e2e\stop_streamlit_e2e.ps1"
            Invoke-ProcessStage "Streamlit停止・PIDポート清掃" "powershell.exe" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $stopScript) 45 | Out-Null
        }
    }
}

function Invoke-FullChecks([string]$Python) {
    Invoke-QuickChecks $Python
    Invoke-ProcessStage "E2E fixture契約" $Python @("-m", "pytest", "tests/test_browser_e2e_fixture_contract.py", "-q") 60 | Out-Null
    Invoke-ProcessStage "Streamlit AppTest" $Python @("-m", "pytest", "tests/test_app_prelisting_gate.py", "-q") 90 | Out-Null
    Invoke-ProcessStage "全回帰" $Python @("-m", "pytest", "-q") 180 | Out-Null
    Invoke-StreamlitSmoke
    Complete-Stage (New-Stage "Browser E2E") "SKIPPED" "FULL_NONINTERACTIVE" "Full does not wait for Computer Use or browser interaction" | Out-Null
    Complete-Stage (New-Stage "ダウンロードCSV検証") "SKIPPED" "FULL_NONINTERACTIVE" "Full does not wait for browser downloads" | Out-Null
}

function Get-E2EWorkspaceRoot {
    return Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::MyDocuments)) "ShopeeE2E"
}

function Invoke-BrowserPrepare([string]$Python) {
    Invoke-FullChecks $Python
    if ($script:HasFailure) { return }
    $prepareScript = Join-Path $script:RepositoryRoot "scripts\e2e\prepare_browser_e2e.ps1"
    Invoke-ProcessStage "Browser fixture準備" "powershell.exe" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $prepareScript, "-Suite", "prelisting_gate", "-FixtureVersion", $FixtureVersion) 90 | Out-Null
    $startScript = Join-Path $script:RepositoryRoot "scripts\e2e\start_streamlit_e2e.ps1"
    Invoke-ProcessStage "Browser Streamlit起動" "powershell.exe" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $startScript) 45 | Out-Null
    $health = Invoke-ProcessStage "Browser health HTTP確認" "curl.exe" @("--fail", "--silent", "--show-error", "--max-time", "10", "http://127.0.0.1:8771/_stcore/health") 15
    $root = Invoke-ProcessStage "Browser root HTTP確認" "curl.exe" @("--fail", "--silent", "--show-error", "--max-time", "10", "--output", "NUL", "--write-out", "%{http_code}", "http://127.0.0.1:8771/") 15
    if ($health.Status -eq "PASS" -and $root.Status -eq "PASS" -and (Get-StageOutput $health).Trim().ToLowerInvariant() -eq "ok" -and (Get-StageOutput $root).Trim() -eq "200") {
        $workspace = Get-E2EWorkspaceRoot
        $readyPath = Join-Path (Join-Path $workspace "current") "READY.txt"
        $pidPath = Join-Path (Join-Path $workspace "state") "streamlit.pid"
        if (-not $DryRun -and (-not (Test-Path -LiteralPath $readyPath) -or -not (Test-Path -LiteralPath $pidPath))) {
            Complete-Stage (New-Stage "Browser E2E") "FAIL" "READY_MISSING" "Browser readiness files were not created" | Out-Null
            return
        }
        Complete-Stage (New-Stage "Browser E2E") "PASS" "0" "fixture and Streamlit are ready for Codex agent" | Out-Null
        $script:BrowserResult = "BROWSER_READY"
        if (-not $DryRun) {
            Write-Host "BROWSER_READY url=http://127.0.0.1:8771 pid=$([IO.File]::ReadAllText($pidPath).Trim())"
            Get-Content -LiteralPath $readyPath
        }
    }
    else {
        Complete-Stage (New-Stage "Browser E2E") "FAIL" "PREPARE_FAILED" "fixture, Streamlit, or HTTP readiness failed" | Out-Null
    }
}

function Stop-BrowserE2E {
    $stopScript = Join-Path $script:RepositoryRoot "scripts\e2e\stop_streamlit_e2e.ps1"
    Invoke-ProcessStage "Browser Streamlit停止・PIDポート清掃" "powershell.exe" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $stopScript) 45 | Out-Null
}

function Invoke-BrowserVerify {
    if ([string]::IsNullOrWhiteSpace($DownloadPath)) {
        Complete-Stage (New-Stage "ダウンロードCSV検証") "FAIL" "MISSING_DOWNLOAD" "Browser Verify requires -DownloadPath" | Out-Null
        return
    }
    $downloadFullPath = [IO.Path]::GetFullPath($DownloadPath)
    if (-not (Test-Path -LiteralPath $downloadFullPath -PathType Leaf) -or (Test-PathInside $downloadFullPath $script:RepositoryRoot)) {
        Complete-Stage (New-Stage "ダウンロードCSV検証") "FAIL" "INVALID_DOWNLOAD" "download CSV must exist outside the repository" | Out-Null
        return
    }
    $verifyScript = Join-Path $script:RepositoryRoot "scripts\e2e\verify_browser_downloads.ps1"
    $verification = Invoke-ProcessStage "ダウンロードCSV検証" "powershell.exe" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $verifyScript, "-DownloadPath", $downloadFullPath) 60
    if ($verification.Status -eq "PASS" -and $RemoveDownloadedCsv) {
        Remove-Item -LiteralPath $downloadFullPath -Force
    }
    if ($verification.Status -eq "PASS" -and $BrowserUiChecksPassed) {
        $script:BrowserResult = "PASS"
    }
    elseif ($verification.Status -eq "PASS") {
        $script:BrowserResult = "BROWSER_UNAVAILABLE"
    }
}

function Get-OverallVerdict {
    if ($script:HasFailure) { return "FAIL" }
    if ($null -ne $script:BrowserResult) { return $script:BrowserResult }
    if ($Mode -eq "Quick" -or $DryRun) { return "CONDITIONAL_PASS" }
    return "PASS"
}

function Write-VerificationReport([string]$Path) {
    $overall = Get-OverallVerdict
    $sections = [ordered]@{
        "Git開始状態" = @("Git開始状態", "Git branch", "Git HEAD")
        "変更ファイル" = @("変更ファイル")
        "対象テスト" = @("対象テスト")
        "全回帰" = @("E2E fixture契約", "全回帰")
        "構文・diff検査" = @("Python構文検査", "PowerShell構文検査", "git diff --check", "git diff --cached --check")
        "セキュリティ監査" = @("セキュリティ監査")
        "AppTest" = @("Streamlit AppTest", "Streamlit起動", "health HTTP確認", "root HTTP確認")
        "Browser E2E" = @("Browser E2E")
        "ダウンロードCSV検証" = @("ダウンロードCSV検証")
        "清掃結果" = @("Streamlit停止・PIDポート清掃", "Browser Streamlit停止・PIDポート清掃")
        "未確認事項" = @()
        "Git終了状態" = @("Git終了状態")
    }
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add("# 変更検証ループ Ver1 レポート")
    $lines.Add("")
    $lines.Add("## 総合判定")
    $lines.Add("")
    $lines.Add($overall)
    foreach ($sectionName in $SectionNames) {
        $lines.Add("")
        $lines.Add("## $sectionName")
        $lines.Add("")
        if ($sectionName -eq "未確認事項") {
            $lines.Add("PASS: real Shopee/API and business suitability are out of scope")
            continue
        }
        $names = $sections[$sectionName]
        $lines.Add("$(Get-StageStatus $names): $(Get-SectionDetail $names)")
    }
    $lines.Add("")
    $lines.Add("## ステージ結果")
    $lines.Add("")
    $lines.Add("| stage | status | started | ended | seconds | exit code |")
    $lines.Add("| --- | --- | --- | --- | ---: | --- |")
    foreach ($stage in $script:Stages) {
        $safeDetail = ([string]$stage.Detail).Replace("|", "\\|")
        $lines.Add("| $($stage.Name) | $($stage.Status) | $($stage.StartedAt.ToString('o')) | $($stage.EndedAt.ToString('o')) | $($stage.DurationSeconds) | $($stage.ExitCode) |")
        if ($safeDetail) { $lines.Add("| detail |  |  |  |  | $safeDetail |") }
    }
    [IO.File]::WriteAllText($Path, (($lines -join [Environment]::NewLine) + [Environment]::NewLine), [Text.UTF8Encoding]::new($false))
    Write-Host "総合判定: $overall" -ForegroundColor $(if ($overall -eq "PASS") { "Green" } elseif ($overall -eq "FAIL") { "Red" } else { "Yellow" })
    Write-Host "検証レポートとステージ標準出力はリポジトリ外のTempに保存しました。"
    return $overall
}

try {
    $script:RepositoryRoot = Get-FormalRepositoryRoot
    $python = Join-Path $script:RepositoryRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "正式な .venv のPythonが見つかりません。" }
    $tempRoot = Join-Path ([IO.Path]::GetTempPath()) "ShopeeChangeVerification"
    $script:ArtifactRoot = Join-Path $tempRoot ("stage-artifacts-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmssfff"))
    New-Item -ItemType Directory -Path $script:ArtifactRoot -Force | Out-Null
    if ([string]::IsNullOrWhiteSpace($ReportPath)) {
        $ReportPath = Join-Path $script:ArtifactRoot "change-verification-report.md"
    }
    $ReportPath = [IO.Path]::GetFullPath($ReportPath)
    if (Test-PathInside $ReportPath $script:RepositoryRoot) { throw "検証レポートはリポジトリ外に保存してください。" }
    New-Item -ItemType Directory -Path (Split-Path -Parent $ReportPath) -Force | Out-Null

    switch ($Mode) {
        "Quick" { Invoke-QuickChecks $python }
        "Full" { Invoke-FullChecks $python }
        "Browser" {
            if ($BrowserStage -eq "Verify") {
                try { Invoke-BrowserVerify }
                finally { Stop-BrowserE2E }
            }
            else {
                try { Invoke-BrowserPrepare $python }
                finally {
                    if ($BrowserStage -eq "Auto" -or $script:HasFailure) {
                        Stop-BrowserE2E
                        if (-not $script:HasFailure) { $script:BrowserResult = "BROWSER_UNAVAILABLE" }
                    }
                }
            }
        }
    }
}
catch {
    Complete-Stage (New-Stage "検証ループ内部エラー") "FAIL" "INTERNAL_ERROR" $_.Exception.Message | Out-Null
}
finally {
    if ($null -ne $script:RepositoryRoot) {
        Invoke-ProcessStage "Git終了状態" "git.exe" @("-C", $script:RepositoryRoot, "status", "--porcelain=v1") 20 | Out-Null
    }
    if (-not [string]::IsNullOrWhiteSpace($ReportPath)) {
        $overall = Write-VerificationReport $ReportPath
        if ($overall -eq "FAIL") { exit 1 }
    }
}
