[CmdletBinding()]
param(
    [ValidateSet(
        "ReadOnly",
        "LocalEdit",
        "LocalTest",
        "LocalCommit",
        "PaidApi",
        "ExternalWrite",
        "IrrecoverableDelete",
        "MajorScopeChange",
        "Push",
        "DraftPr",
        "Merge",
        "Deploy"
    )]
    [string]$Scenario,
    [switch]$Approved,
    [switch]$DirtyOverwritesUserChanges,
    [switch]$SecretToGit
)

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
        throw "この検証は正式リポジトリのscriptsから実行する必要があります。"
    }
    return $gitRootFull
}

function Get-RequiredContent {
    param(
        [string]$RepositoryRoot,
        [string]$RelativePath
    )

    $path = Join-Path $RepositoryRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "必須文書がありません: $RelativePath"
    }
    return Get-Content -LiteralPath $path -Raw -Encoding utf8
}

function Assert-ContainsText {
    param(
        [string]$Content,
        [string]$DocumentName,
        [string[]]$RequiredTexts
    )

    foreach ($requiredText in $RequiredTexts) {
        if ($Content.IndexOf($requiredText, [StringComparison]::Ordinal) -lt 0) {
            throw "$DocumentName に必須記述がありません: $requiredText"
        }
    }
}

function Assert-DoesNotContainText {
    param(
        [string]$Content,
        [string]$DocumentName,
        [string[]]$ForbiddenTexts
    )

    foreach ($forbiddenText in $ForbiddenTexts) {
        if ($Content.IndexOf($forbiddenText, [StringComparison]::Ordinal) -ge 0) {
            throw "$DocumentName に廃止済みの現役ルールが残っています: $forbiddenText"
        }
    }
}

function Get-PolicyDecision {
    param(
        [string]$Action,
        [bool]$HasApproval,
        [bool]$WouldOverwriteUserChanges,
        [bool]$WouldCommitSecret
    )

    if ($WouldCommitSecret) {
        return "STOP"
    }
    if ($WouldOverwriteUserChanges) {
        return "STOP"
    }

    $approvalRequired = $Action -in @(
        "PaidApi",
        "ExternalWrite",
        "IrrecoverableDelete",
        "MajorScopeChange",
        "Push",
        "DraftPr",
        "Merge",
        "Deploy"
    )
    if ($approvalRequired -and -not $HasApproval) {
        return "STOP"
    }
    return "PASS"
}

function Assert-Decision {
    param(
        [string]$Description,
        [string]$Expected,
        [string]$Actual
    )

    if ($Actual -ne $Expected) {
        throw "$Description の判定が不正です。expected=$Expected actual=$Actual"
    }
}

$repositoryRoot = Get-FormalRepositoryRoot
$agents = Get-RequiredContent -RepositoryRoot $repositoryRoot -RelativePath "AGENTS.md"
$runbook = Get-RequiredContent -RepositoryRoot $repositoryRoot -RelativePath "docs/RUNBOOK_CHATGPT_CODEX.md"
$template = Get-RequiredContent -RepositoryRoot $repositoryRoot -RelativePath "docs/templates/WORK_BRIEF.md"
$decisionLog = Get-RequiredContent -RepositoryRoot $repositoryRoot -RelativePath "docs/DECISION_LOG.md"

Assert-ContainsText -Content $agents -DocumentName "AGENTS.md" -RequiredTexts @(
    "軽量開発運用 v1",
    "ローカルcommit",
    "pushとDraft PR作成",
    "GPTは必須の伝言役または承認者にしない"
)
Assert-ContainsText -Content $runbook -DocumentName "docs/RUNBOOK_CHATGPT_CODEX.md" -RequiredTexts @(
    "小さく可逆",
    "操作境界",
    "WORK_BRIEFを使う条件",
    "GPTは必須の伝言役または承認者ではない"
)
Assert-ContainsText -Content $template -DocumentName "docs/templates/WORK_BRIEF.md" -RequiredTexts @(
    "すべての作業の開始条件ではありません",
    "何ができれば満足か",
    "外部・不可逆操作"
)
Assert-ContainsText -Content $decisionLog -DocumentName "docs/DECISION_LOG.md" -RequiredTexts @(
    "DEC-0018",
    "軽量開発運用 v1"
)

$retiredFields = @(
    "GPT chat disposition",
    "result target GPT project",
    "result target GPT chat",
    "FORMAL_WORK_UNIT_CLOSED",
    "CHAT_HANDOFF_GATE"
)
Assert-DoesNotContainText -Content $agents -DocumentName "AGENTS.md" -ForbiddenTexts $retiredFields
Assert-DoesNotContainText -Content $runbook -DocumentName "docs/RUNBOOK_CHATGPT_CODEX.md" -ForbiddenTexts $retiredFields
Assert-DoesNotContainText -Content $template -DocumentName "docs/templates/WORK_BRIEF.md" -ForbiddenTexts $retiredFields

$cases = @(
    @{ Description = "GPTチャット名なしの読み取り"; Action = "ReadOnly"; Approved = $false; Overwrite = $false; Secret = $false; Expected = "PASS" },
    @{ Description = "安全なローカル編集"; Action = "LocalEdit"; Approved = $false; Overwrite = $false; Secret = $false; Expected = "PASS" },
    @{ Description = "ローカルテスト"; Action = "LocalTest"; Approved = $false; Overwrite = $false; Secret = $false; Expected = "PASS" },
    @{ Description = "ローカルcommit"; Action = "LocalCommit"; Approved = $false; Overwrite = $false; Secret = $false; Expected = "PASS" },
    @{ Description = "ユーザー変更の上書き"; Action = "LocalEdit"; Approved = $false; Overwrite = $true; Secret = $false; Expected = "STOP" },
    @{ Description = "無許可の有料API"; Action = "PaidApi"; Approved = $false; Overwrite = $false; Secret = $false; Expected = "STOP" },
    @{ Description = "無許可の外部書込み"; Action = "ExternalWrite"; Approved = $false; Overwrite = $false; Secret = $false; Expected = "STOP" },
    @{ Description = "無許可の復元不能削除"; Action = "IrrecoverableDelete"; Approved = $false; Overwrite = $false; Secret = $false; Expected = "STOP" },
    @{ Description = "無許可の目的・責務・満足条件の大幅変更"; Action = "MajorScopeChange"; Approved = $false; Overwrite = $false; Secret = $false; Expected = "STOP" },
    @{ Description = "承認済みの目的・責務・満足条件の大幅変更"; Action = "MajorScopeChange"; Approved = $true; Overwrite = $false; Secret = $false; Expected = "PASS" },
    @{ Description = "無許可のpush"; Action = "Push"; Approved = $false; Overwrite = $false; Secret = $false; Expected = "STOP" },
    @{ Description = "無許可のDraft PR"; Action = "DraftPr"; Approved = $false; Overwrite = $false; Secret = $false; Expected = "STOP" },
    @{ Description = "無許可のmerge"; Action = "Merge"; Approved = $false; Overwrite = $false; Secret = $false; Expected = "STOP" },
    @{ Description = "無許可のdeploy"; Action = "Deploy"; Approved = $false; Overwrite = $false; Secret = $false; Expected = "STOP" },
    @{ Description = "秘密情報のcommit"; Action = "LocalCommit"; Approved = $true; Overwrite = $false; Secret = $true; Expected = "STOP" },
    @{ Description = "承認済みpush"; Action = "Push"; Approved = $true; Overwrite = $false; Secret = $false; Expected = "PASS" }
)

foreach ($case in $cases) {
    $actual = Get-PolicyDecision -Action $case.Action -HasApproval $case.Approved -WouldOverwriteUserChanges $case.Overwrite -WouldCommitSecret $case.Secret
    Assert-Decision -Description $case.Description -Expected $case.Expected -Actual $actual
}

if ($PSBoundParameters.ContainsKey("Scenario")) {
    $decision = Get-PolicyDecision -Action $Scenario -HasApproval $Approved.IsPresent -WouldOverwriteUserChanges $DirtyOverwritesUserChanges.IsPresent -WouldCommitSecret $SecretToGit.IsPresent
    Write-Host "POLICY_DECISION: $decision"
    if ($decision -eq "STOP") {
        exit 3
    }
}

Write-Host "PASS: lightweight development policy verification"
