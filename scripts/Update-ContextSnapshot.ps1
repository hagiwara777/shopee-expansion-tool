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
        throw "このスクリプトは正式リポジトリの scripts から実行する必要があります。"
    }
    return $gitRootFull
}

function Invoke-GitText {
    param(
        [string]$RepositoryRoot,
        [string[]]$GitArguments
    )

    $output = @(& git -C $RepositoryRoot @GitArguments)
    if ($LASTEXITCODE -ne 0) {
        throw "Git読み取りに失敗しました: $($GitArguments -join ' ')"
    }
    return ($output -join [Environment]::NewLine).Trim()
}

function Get-RequiredDocumentPath {
    param(
        [string]$RepositoryRoot,
        [string]$RelativePath
    )

    $path = Join-Path $RepositoryRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "必須の管理文書がありません: $RelativePath"
    }
    return $path
}

function Get-BulletValue {
    param(
        [string]$Content,
        [string]$Label
    )

    $pattern = "(?m)^-[ ]*" + [regex]::Escape($Label) + ":[ ]*(?<value>.+?)[ ]*$"
    $match = [regex]::Match($Content, $pattern)
    if (-not $match.Success) {
        throw "CURRENT_WORK.md に必須項目がありません: $Label"
    }

    $value = $match.Groups["value"].Value.Trim().Replace([string][char]96, "")
    Assert-SafeSnapshotValue -Value $value -Label $Label
    return $value
}

function Get-SectionBulletValues {
    param(
        [string]$Content,
        [string]$Heading
    )

    $insideSection = $false
    $values = @()
    $currentValue = $null
    foreach ($line in ($Content -split "\r?\n")) {
        if (-not $insideSection) {
            if ($line.Trim() -eq "## $Heading") {
                $insideSection = $true
            }
            continue
        }

        if ($line.Trim().StartsWith("## ")) {
            break
        }
        if ($line.Trim().StartsWith("- ")) {
            if ($null -ne $currentValue) {
                Assert-SafeSnapshotValue -Value $currentValue -Label $Heading
                $values += $currentValue
            }
            $currentValue = $line.Trim().Substring(2).Trim()
        }
        elseif ($null -ne $currentValue -and -not [string]::IsNullOrWhiteSpace($line)) {
            $currentValue += " " + $line.Trim()
        }
    }

    if ($null -ne $currentValue) {
        Assert-SafeSnapshotValue -Value $currentValue -Label $Heading
        $values += $currentValue
    }

    if (-not $insideSection -or $values.Count -eq 0) {
        throw "CURRENT_WORK.md に安全に要約できる節がありません: $Heading"
    }
    return $values
}

function Assert-SafeSnapshotValue {
    param(
        [string]$Value,
        [string]$Label
    )

    if (
        [string]::IsNullOrWhiteSpace($Value) -or
        $Value.Length -gt 240 -or
        $Value.Contains([string][char]13) -or
        $Value.Contains([string][char]10)
    ) {
        throw "snapshotに安全に出力できない値です: $Label"
    }

    $forbiddenTexts = @(
        "http://",
        "https://",
        ("C:" + [char]92 + "Users" + [char]92),
        "OPENAI_API_KEY",
        "access_token",
        "refresh_token",
        "partner_key",
        "authorization",
        ".env"
    )
    foreach ($forbiddenText in $forbiddenTexts) {
        if ($Value.IndexOf($forbiddenText, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            throw "snapshotに禁止情報が含まれています: $Label"
        }
    }
}

function Write-SnapshotAtomically {
    param(
        [string]$RepositoryRoot,
        [string]$SnapshotPath,
        [string]$Content
    )

    $expectedSnapshotPath = [IO.Path]::GetFullPath((Join-Path $RepositoryRoot "docs/CONTEXT_SNAPSHOT.md"))
    $snapshotFullPath = [IO.Path]::GetFullPath($SnapshotPath)
    if (-not [string]::Equals($snapshotFullPath, $expectedSnapshotPath, [StringComparison]::OrdinalIgnoreCase)) {
        throw "snapshotの出力先が検証済みのパスではありません。"
    }

    $snapshotDirectory = [IO.Path]::GetDirectoryName($snapshotFullPath)
    $temporaryPath = Join-Path $snapshotDirectory "CONTEXT_SNAPSHOT.md.tmp-$PID"
    $backupPath = Join-Path $snapshotDirectory "CONTEXT_SNAPSHOT.md.backup-$PID"
    if (
        -not [string]::Equals([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($temporaryPath)), $snapshotDirectory, [StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($backupPath)), $snapshotDirectory, [StringComparison]::OrdinalIgnoreCase)
    ) {
        throw "snapshotの一時ファイルの出力先が不正です。"
    }

    $utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
    try {
        [System.IO.File]::WriteAllText($temporaryPath, $Content, $utf8WithoutBom)
        if (Test-Path -LiteralPath $snapshotFullPath -PathType Leaf) {
            [System.IO.File]::Replace($temporaryPath, $snapshotFullPath, $backupPath)
            if (Test-Path -LiteralPath $backupPath -PathType Leaf) {
                Remove-Item -LiteralPath $backupPath -Force
            }
        }
        else {
            [System.IO.File]::Move($temporaryPath, $snapshotFullPath)
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
        if (Test-Path -LiteralPath $backupPath -PathType Leaf) {
            Remove-Item -LiteralPath $backupPath -Force
        }
    }
}

$repositoryRoot = Get-FormalRepositoryRoot
$allowedDocuments = @(
    "AGENTS.md",
    "docs/PROJECT_ROADMAP.md",
    "docs/CURRENT_WORK.md",
    "docs/DECISION_LOG.md"
)
foreach ($document in $allowedDocuments) {
    [void](Get-RequiredDocumentPath -RepositoryRoot $repositoryRoot -RelativePath $document)
}

$currentWorkPath = Get-RequiredDocumentPath -RepositoryRoot $repositoryRoot -RelativePath "docs/CURRENT_WORK.md"
$currentWorkContent = Get-Content -LiteralPath $currentWorkPath -Raw -Encoding utf8

$currentWorkType = Get-BulletValue -Content $currentWorkContent -Label "current_work_type"
$currentPhase = Get-BulletValue -Content $currentWorkContent -Label "current_phase"
$expectedBranch = Get-BulletValue -Content $currentWorkContent -Label "working_branch"
$nextAction = Get-BulletValue -Content $currentWorkContent -Label "next_action"
$marketplace = Get-BulletValue -Content $currentWorkContent -Label "marketplace"
$module = Get-BulletValue -Content $currentWorkContent -Label "module"
$phase = Get-BulletValue -Content $currentWorkContent -Label "phase"
$cohort = Get-BulletValue -Content $currentWorkContent -Label "固定評価コホート"
$sourceProductCount = Get-BulletValue -Content $currentWorkContent -Label "Amazon候補を取得できた元Shopee商品"
$candidateCount = Get-BulletValue -Content $currentWorkContent -Label "Amazon候補"
$keepaStatus = Get-BulletValue -Content $currentWorkContent -Label "Keepa確認"
$gateStatus = Get-BulletValue -Content $currentWorkContent -Label "PH Prelisting Gate"
$stopConditions = Get-SectionBulletValues -Content $currentWorkContent -Heading "停止条件"
$successState = Get-SectionBulletValues -Content $currentWorkContent -Heading "成功判定の状態"
$documentInconsistencies = Get-SectionBulletValues -Content $currentWorkContent -Heading "既知の文書不整合"
$unconfirmedItems = @(
    $successState | Where-Object {
        $_.IndexOf("未確認", [StringComparison]::Ordinal) -ge 0 -or
        $_.IndexOf("未決定", [StringComparison]::Ordinal) -ge 0
    }
    $documentInconsistencies | Where-Object {
        $_.IndexOf("未確認", [StringComparison]::Ordinal) -ge 0 -or
        $_.IndexOf("不整合", [StringComparison]::Ordinal) -ge 0
    }
)
if ($unconfirmedItems.Count -eq 0) {
    throw "CURRENT_WORK.md に安全に要約できる未確認事項がありません。"
}
$stopConditionSummary = ($stopConditions | ForEach-Object { "- $_" }) -join [Environment]::NewLine
$unconfirmedSummary = ($unconfirmedItems | ForEach-Object { "- $_" }) -join [Environment]::NewLine

$currentBranch = Invoke-GitText -RepositoryRoot $repositoryRoot -GitArguments @("branch", "--show-current")
if ([string]::IsNullOrWhiteSpace($currentBranch)) {
    throw "detached HEADではsnapshotを生成できません。"
}
$unresolvedWorkingBranch = "再開時にGit状態を確認して確定"
if ($expectedBranch -ne $unresolvedWorkingBranch -and $currentBranch -ne $expectedBranch) {
    throw "CURRENT_WORK.md のworking_branchとGitの現在ブランチが一致しません。"
}

$head = Invoke-GitText -RepositoryRoot $repositoryRoot -GitArguments @("rev-parse", "HEAD")
$main = Invoke-GitText -RepositoryRoot $repositoryRoot -GitArguments @("rev-parse", "main")
$originMain = Invoke-GitText -RepositoryRoot $repositoryRoot -GitArguments @("rev-parse", "refs/remotes/origin/main")
$aiExperimentHead = Invoke-GitText -RepositoryRoot $repositoryRoot -GitArguments @("rev-parse", "feature/ph-category-mapper-ai-shadow-v0.2.1")
$worktreeLines = @(& git -C $repositoryRoot status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0) {
    throw "Git作業ツリーの状態を確認できません。"
}
$worktreeState = if ($worktreeLines.Count -eq 0) { "clean" } else { "dirty" }
$changedFileCount = $worktreeLines.Count
$generatedAt = [DateTimeOffset]::Now.ToString("yyyy-MM-ddTHH:mm:ssK", [Globalization.CultureInfo]::InvariantCulture)

$snapshot = @"
# CONTEXT SNAPSHOT

## このファイルの位置づけ

- 再生成可能な読み取り用の派生物
- 正本ではない
- 手動編集禁止
- Git管理対象外
- 古くなった場合は再生成する
- 正本と矛盾する場合は正本を優先する

## Git基準

- current branch: $currentBranch
- current HEAD: $head
- main: $main
- origin/main: $originMain
- AI実験ブランチHEAD: $aiExperimentHead
- worktree: $worktreeState
- 変更ファイル数: $changedFileCount
- generated_at: $generatedAt

## 現在作業

- current_work_type: $currentWorkType
- current_phase: $currentPhase
- working_branch: $expectedBranch
- next_action: $nextAction

## 評価対象

- marketplace: $marketplace
- module: $module
- phase: $phase
- 固定評価コホート: $cohort
- Amazon候補を取得できた元Shopee商品: $sourceProductCount
- Amazon候補: $candidateCount
- Keepa確認: $keepaStatus
- PH Prelisting Gate: $gateStatus

## 判定区分

- MATCH
- VARIANT_MATCH
- UNCERTAIN
- MISMATCH

VARIANT_MATCHは完全一致率に含めない。

## 進行禁止

- Category Mapper
- AI Shadow実評価
- 大機能追加
- SG / MY / TH情報の使用
- Shopee商品系書込API
- 自動出品

## 停止条件

$stopConditionSummary

## 未確認事項

$unconfirmedSummary

## 参照すべき正本

- Gitの実状態
- AGENTS.md
- docs/CURRENT_WORK.md
- docs/DECISION_LOG.md
- docs/PROJECT_ROADMAP.md
"@

Write-SnapshotAtomically -RepositoryRoot $repositoryRoot -SnapshotPath (Join-Path $repositoryRoot "docs/CONTEXT_SNAPSHOT.md") -Content $snapshot
Write-Host "CONTEXT_SNAPSHOT を生成しました。"
