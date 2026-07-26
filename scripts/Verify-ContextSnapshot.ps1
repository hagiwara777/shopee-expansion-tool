[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-FormalRepositoryRoot {
    $scriptRepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $gitRepositoryRoot = (& git -C $scriptRepositoryRoot rev-parse --show-toplevel).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Gitリポジトリのルートを確認できません。"
    }

    $scriptRootFull = [IO.Path]::GetFullPath($scriptRepositoryRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $gitRootFull = [IO.Path]::GetFullPath($gitRepositoryRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if (-not [string]::Equals($scriptRootFull, $gitRootFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "この検証は正式リポジトリの scripts から実行する必要があります。"
    }
    return $gitRootFull
}

function Get-FileHashMap {
    param(
        [string]$RepositoryRoot,
        [string[]]$RelativePaths
    )

    $hashes = @{}
    foreach ($relativePath in $RelativePaths) {
        $path = Join-Path $RepositoryRoot $relativePath
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "必須の正本がありません: $relativePath"
        }
        $hashes[$relativePath] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
    return $hashes
}

function Assert-EqualHashMaps {
    param(
        [hashtable]$Before,
        [hashtable]$After
    )

    foreach ($key in $Before.Keys) {
        if ($Before[$key] -ne $After[$key]) {
            throw "生成中に正本が変更されました: $key"
        }
    }
}

function Assert-SnapshotSectionHasSubstantiveContent {
    param(
        [string]$Snapshot,
        [string]$Heading
    )

    $insideSection = $false
    $contentLines = @()
    foreach ($line in ($Snapshot -split "\r?\n")) {
        if (-not $insideSection) {
            if ($line.Trim() -eq $Heading) {
                $insideSection = $true
            }
            continue
        }

        if ($line.Trim().StartsWith("## ")) {
            break
        }
        $value = $line.Trim()
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            if ($value.StartsWith("- ")) {
                $value = $value.Substring(2).Trim()
            }
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                $contentLines += $value
            }
        }
    }

    if (-not $insideSection) {
        throw "snapshotに必須節がありません: $Heading"
    }
    $substantiveLines = @($contentLines | Where-Object {
        -not [regex]::IsMatch($_, "^(?i:なし|todo)$")
    })
    if ($substantiveLines.Count -eq 0) {
        throw "snapshotの必須節に実質的な内容がありません: $Heading"
    }
}

function Assert-InvalidSnapshotRejected {
    param(
        [string]$Snapshot,
        [string]$Description
    )

    $temporaryDirectory = Join-Path ([IO.Path]::GetTempPath()) ("ContextSnapshotVerify-$PID-" + [Guid]::NewGuid().ToString("N"))
    $temporaryPath = Join-Path $temporaryDirectory "CONTEXT_SNAPSHOT.md"
    try {
        [void][IO.Directory]::CreateDirectory($temporaryDirectory)
        [System.IO.File]::WriteAllText($temporaryPath, $Snapshot, [System.Text.UTF8Encoding]::new($false))
        $temporarySnapshot = Get-Content -LiteralPath $temporaryPath -Raw -Encoding utf8
        try {
            Assert-SnapshotContent -Snapshot $temporarySnapshot
        }
        catch {
            return
        }
        throw "異常系のsnapshotを検出できませんでした: $Description"
    }
    finally {
        if (Test-Path -LiteralPath $temporaryDirectory -PathType Container) {
            Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
        }
    }
}

function Assert-SnapshotContent {
    param([string]$Snapshot)

    $requiredTexts = @(
        "# CONTEXT SNAPSHOT",
        "## このファイルの位置づけ",
        "## Git基準",
        "## 現在の管理作業",
        "## 一時停止中の実作業",
        "## 判定区分",
        "## 進行禁止",
        "## 停止条件",
        "## 未確認事項",
        "## 参照すべき正本",
        "管理基盤Ver1",
        "marketplace: PH",
        "module: ASIN Resolver",
        "phase: 固定30件評価",
        "Amazon候補: 13件",
        "MATCH",
        "VARIANT_MATCH",
        "UNCERTAIN",
        "MISMATCH"
    )
    foreach ($requiredText in $requiredTexts) {
        if ($Snapshot.IndexOf($requiredText, [StringComparison]::Ordinal) -lt 0) {
            throw "snapshotに必須情報がありません: $requiredText"
        }
    }
    Assert-SnapshotSectionHasSubstantiveContent -Snapshot $Snapshot -Heading "## 停止条件"
    Assert-SnapshotSectionHasSubstantiveContent -Snapshot $Snapshot -Heading "## 未確認事項"

    $forbiddenTexts = @(
        ("C:" + [char]92 + "Users" + [char]92),
        "http://",
        "https://",
        "OPENAI_API_KEY",
        "access_token",
        "refresh_token",
        "partner_key",
        "authorization",
        ".env",
        "diff --git"
    )
    foreach ($forbiddenText in $forbiddenTexts) {
        if ($Snapshot.IndexOf($forbiddenText, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            throw "snapshotに禁止情報パターンが含まれています: $forbiddenText"
        }
    }
    if ([regex]::IsMatch($Snapshot, 'B[0-9A-Z]{9}')) {
        throw "snapshotにASIN形式の値が含まれています。"
    }
}

$repositoryRoot = Get-FormalRepositoryRoot
$generatorPath = Join-Path $repositoryRoot "scripts/Update-ContextSnapshot.ps1"
$snapshotPath = Join-Path $repositoryRoot "docs/CONTEXT_SNAPSHOT.md"
$sourceDocuments = @(
    "AGENTS.md",
    "docs/PROJECT_ROADMAP.md",
    "docs/CURRENT_WORK.md",
    "docs/DECISION_LOG.md"
)

if (-not (Test-Path -LiteralPath $generatorPath -PathType Leaf)) {
    throw "snapshot生成スクリプトがありません。"
}

$hashesBefore = Get-FileHashMap -RepositoryRoot $repositoryRoot -RelativePaths $sourceDocuments
if (Test-Path -LiteralPath $snapshotPath -PathType Leaf) {
    Remove-Item -LiteralPath $snapshotPath -Force
}

& $generatorPath
if ($LASTEXITCODE -ne 0) {
    throw "1回目のsnapshot生成に失敗しました。"
}
if (-not (Test-Path -LiteralPath $snapshotPath -PathType Leaf)) {
    throw "snapshotが生成されませんでした。"
}
$firstSnapshot = Get-Content -LiteralPath $snapshotPath -Raw -Encoding utf8
Assert-SnapshotContent -Snapshot $firstSnapshot

& $generatorPath
if ($LASTEXITCODE -ne 0) {
    throw "2回目のsnapshot生成に失敗しました。"
}
$secondSnapshot = Get-Content -LiteralPath $snapshotPath -Raw -Encoding utf8
Assert-SnapshotContent -Snapshot $secondSnapshot

$missingSectionSnapshot = $secondSnapshot.Replace("## 停止条件", "## 削除済み停止条件")
Assert-InvalidSnapshotRejected -Snapshot $missingSectionSnapshot -Description "停止条件の欠落"
$todoOnlySnapshot = [regex]::Replace(
    $secondSnapshot,
    "(?ms)(## 未確認事項\r?\n).*?(?=^## |\z)",
    ('$1- TODO' + [Environment]::NewLine)
)
Assert-InvalidSnapshotRejected -Snapshot $todoOnlySnapshot -Description "未確認事項がTODOだけ"

$ignoredCheck = & git -C $repositoryRoot check-ignore -q "docs/CONTEXT_SNAPSHOT.md"
if ($LASTEXITCODE -ne 0) {
    throw "snapshotがGit管理対象外ではありません。"
}
$normalStatus = @(& git -C $repositoryRoot status --short --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or ($normalStatus | Where-Object { $_.IndexOf("CONTEXT_SNAPSHOT.md", [StringComparison]::Ordinal) -ge 0 })) {
    throw "通常のGit statusにsnapshotが含まれています。"
}
$ignoredStatus = @(& git -C $repositoryRoot status --short --ignored --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or -not ($ignoredStatus | Where-Object { $_.IndexOf("CONTEXT_SNAPSHOT.md", [StringComparison]::Ordinal) -ge 0 })) {
    throw "Git管理対象外のsnapshotを確認できません。"
}

$hashesAfter = Get-FileHashMap -RepositoryRoot $repositoryRoot -RelativePaths $sourceDocuments
Assert-EqualHashMaps -Before $hashesBefore -After $hashesAfter

Write-Host "PASS: CONTEXT_SNAPSHOT verification"
