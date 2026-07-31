[CmdletBinding()]
param(
    [string]$BriefPath,
    [switch]$SkipBriefPathExitTest
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

function Get-WorkBriefField {
    param(
        [string]$Content,
        [string]$Field
    )

    $pattern = "(?m)^[ \t]*(?:[-*][ \t]*)?" + [regex]::Escape($Field) + ":[ \t]*(?<value>.*?)[ \t]*$"
    $matches = [regex]::Matches($Content, $pattern)
    if ($matches.Count -eq 0) {
        throw "WORK_BRIEF の必須欄がありません: $Field"
    }

    $values = @(
        foreach ($match in $matches) {
            $match.Groups["value"].Value.Trim().Trim([char]96).Trim()
        }
    )
    if ($values | Where-Object { [string]::IsNullOrWhiteSpace($_) }) {
        throw "WORK_BRIEF の必須欄が空です: $Field"
    }

    $uniqueValues = @($values | Select-Object -Unique)
    if ($uniqueValues.Count -ne 1) {
        throw "WORK_BRIEF のcanonical fieldが矛盾しています: $Field"
    }
    return $uniqueValues[0]
}

function Assert-ConfirmedTarget {
    param(
        [string]$Value,
        [string]$Field
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "WORK_BRIEF の必須欄が空です: $Field"
    }
    if ([regex]::IsMatch($Value, '(?:TBD|UNCONFIRMED|未確定|未定)', [Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
        throw "WORK_BRIEF の結果戻し先が未確定です: $Field"
    }
    if ([regex]::IsMatch($Value, '^(?:N/?A)$', [Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
        throw "WORK_BRIEF の結果戻し先が未確定です: $Field"
    }
}

function Assert-StopDoesNotAllowMutation {
    param([string]$Content)

    $permissionPatterns = @(
        '(?mi)^[ \t]*(?:[-*][ \t]*)?(?:編集|ファイル編集|edit|commit|push)[ \t]*:[ \t]*(?:許可|allowed)[ \t]*$',
        '(?mi)^[ \t]*(?:[-*][ \t]*)?Git操作[ \t]*:[ \t]*(?=[^\r\n]*(?:編集|edit|commit|push))(?=[^\r\n]*(?:許可|allowed))[^\r\n]*$',
        '(?mi)^[ \t]*\|[ \t]*(?:編集|ファイル編集|edit|commit|push)[ \t]*\|[ \t]*(?:許可|allowed)[ \t]*\|[ \t]*$',
        '(?mi)^[ \t]*\|[ \t]*Git操作[ \t]*\|(?=[^|\r\n]*(?:編集|edit|commit|push))(?=[^|\r\n]*(?:許可|allowed))[^|\r\n]*\|[ \t]*$'
    )
    foreach ($permissionPattern in $permissionPatterns) {
        if ($Content -match $permissionPattern) {
            throw "CHAT_HANDOFF_GATE: STOPなのに編集、commitまたはpushを許可しています。"
        }
    }
}

function Assert-WorkBriefHandoff {
    param([string]$Content)

    $disposition = Get-WorkBriefField -Content $Content -Field "GPT chat disposition"
    $project = Get-WorkBriefField -Content $Content -Field "result target GPT project"
    $chat = Get-WorkBriefField -Content $Content -Field "result target GPT chat"
    $closed = Get-WorkBriefField -Content $Content -Field "FORMAL_WORK_UNIT_CLOSED"
    $gate = Get-WorkBriefField -Content $Content -Field "CHAT_HANDOFF_GATE"

    if ($disposition -notin @("CONTINUE_CURRENT_CHAT", "CREATE_NEW_CHAT")) {
        throw "GPT chat dispositionが許容値ではありません: $disposition"
    }
    Assert-ConfirmedTarget -Value $project -Field "result target GPT project"
    Assert-ConfirmedTarget -Value $chat -Field "result target GPT chat"
    if ($closed -notin @("YES", "NO")) {
        throw "FORMAL_WORK_UNIT_CLOSEDが許容値ではありません: $closed"
    }
    if ($gate -notin @("PASS", "STOP")) {
        throw "CHAT_HANDOFF_GATEが許容値ではありません: $gate"
    }
    if ($disposition -eq "CREATE_NEW_CHAT" -and $closed -ne "YES") {
        throw "CREATE_NEW_CHATにはFORMAL_WORK_UNIT_CLOSED: YESが必要です。"
    }
    if ($disposition -eq "CONTINUE_CURRENT_CHAT" -and $closed -eq "YES") {
        throw "閉鎖済みFORMAL作業の次の開始にはCREATE_NEW_CHATが必要です。"
    }
    if ($gate -eq "STOP") {
        Assert-StopDoesNotAllowMutation -Content $Content
    }

    return [pscustomobject]@{
        Disposition = $disposition
        Closed = $closed
        Gate = $gate
    }
}

function New-TestWorkBrief {
    param(
        [string]$Disposition,
        [string]$Project = "Shopee Portfolio Control",
        [string]$Chat = "GPTチャット切替基準正式化",
        [string]$Closed,
        [string]$Gate,
        [string]$OmitField,
        [switch]$AllowMutation,
        [string]$MutationStatement
    )

    $fields = [ordered]@{
        "GPT chat disposition" = $Disposition
        "result target GPT project" = $Project
        "result target GPT chat" = $Chat
        "FORMAL_WORK_UNIT_CLOSED" = $Closed
        "CHAT_HANDOFF_GATE" = $Gate
    }
    if (-not [string]::IsNullOrWhiteSpace($OmitField)) {
        [void]$fields.Remove($OmitField)
    }

    $lines = @()
    foreach ($field in $fields.Keys) {
        $lines += "${field}: $($fields[$field])"
    }
    if ($AllowMutation) {
        $lines += "編集: 許可"
    }
    if (-not [string]::IsNullOrWhiteSpace($MutationStatement)) {
        $lines += $MutationStatement
    }
    return ($lines -join [Environment]::NewLine)
}

function Assert-Rejected {
    param(
        [string]$Description,
        [scriptblock]$Action
    )

    try {
        & $Action
    }
    catch {
        return
    }
    throw "異常系を拒否できませんでした: $Description"
}

function Assert-StopBriefPathRejected {
    param([string]$ScriptPath)

    $temporaryDirectory = Join-Path ([IO.Path]::GetTempPath()) ("WorkBriefHandoff-$PID-" + [Guid]::NewGuid().ToString("N"))
    $temporaryBriefPath = Join-Path $temporaryDirectory "stop-work-brief.md"
    try {
        [void][IO.Directory]::CreateDirectory($temporaryDirectory)
        $stopBrief = New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Closed "NO" -Gate "STOP" -MutationStatement "Git操作: 編集、commit、pushは禁止"
        [System.IO.File]::WriteAllText($temporaryBriefPath, $stopBrief, [System.Text.UTF8Encoding]::new($true))
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $childOutput = @(& powershell -NoProfile -ExecutionPolicy Bypass -File $ScriptPath -BriefPath $temporaryBriefPath -SkipBriefPathExitTest 2>&1)
            $childExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        $childOutputText = ($childOutput | Out-String)

        if ($childExitCode -eq 0) {
            throw "CHAT_HANDOFF_GATE: STOPの実Briefがゼロ終了しました。"
        }
        if ($childOutputText.IndexOf("CHAT_HANDOFF_GATE: STOPのためBRIEF_GATE: STOP", [StringComparison]::Ordinal) -lt 0) {
            throw "CHAT_HANDOFF_GATE: STOPの終了メッセージを確認できません。"
        }
        if ($childOutputText.IndexOf("PASS: WORK_BRIEF handoff verification", [StringComparison]::Ordinal) -ge 0) {
            throw "CHAT_HANDOFF_GATE: STOPの実BriefがPASSメッセージを出力しました。"
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporaryDirectory -PathType Container) {
            Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
        }
    }
}

$repositoryRoot = Get-FormalRepositoryRoot
$canonicalFields = @(
    "GPT chat disposition",
    "result target GPT project",
    "result target GPT chat",
    "FORMAL_WORK_UNIT_CLOSED",
    "CHAT_HANDOFF_GATE"
)

$agentsContent = Get-RequiredContent -RepositoryRoot $repositoryRoot -RelativePath "AGENTS.md"
$runbookContent = Get-RequiredContent -RepositoryRoot $repositoryRoot -RelativePath "docs/RUNBOOK_CHATGPT_CODEX.md"
$decisionLogContent = Get-RequiredContent -RepositoryRoot $repositoryRoot -RelativePath "docs/DECISION_LOG.md"
$templateContent = Get-RequiredContent -RepositoryRoot $repositoryRoot -RelativePath "docs/templates/WORK_BRIEF.md"
$formalClosureTerms = @(
    "PR-backed FORMAL work unit",
    "no-PR FORMAL work unit",
    "PRを伴うFORMAL作業",
    "PRを伴わないFORMAL作業",
    "読み取り専用監査",
    "形式だけのPRを作成しない",
    "CURRENT_WORK更新不要時の正式確認"
)

Assert-ContainsText -Content $agentsContent -DocumentName "AGENTS.md" -RequiredTexts ($canonicalFields + @(
    "BRIEF_GATE: STOP",
    "編集、commit、push"
))
Assert-ContainsText -Content $runbookContent -DocumentName "docs/RUNBOOK_CHATGPT_CODEX.md" -RequiredTexts ($canonicalFields + @(
    "FORMAL work unit",
    "対象PRがmainへ統合済み",
    "ChatGPTが統合後のformal main commitをGitHubから直接確認済み",
    "docs/CURRENT_WORK.mdが統合後の現在地と次の単一作業へ更新済み",
    "CONTINUE_CURRENT_CHAT",
    "CREATE_NEW_CHAT",
    "YES / NO",
    "PASS / STOP",
    "CHAT_HANDOFF_GATE: STOP"
))
Assert-ContainsText -Content $templateContent -DocumentName "docs/templates/WORK_BRIEF.md" -RequiredTexts ($canonicalFields + @(
    "GPT chat disposition: CONTINUE_CURRENT_CHAT / CREATE_NEW_CHAT",
    "FORMAL_WORK_UNIT_CLOSED: YES / NO",
    "CHAT_HANDOFF_GATE: PASS / STOP",
    "PR-backed closure条件",
    "no-PR closure条件"
))
Assert-ContainsText -Content $agentsContent -DocumentName "AGENTS.md" -RequiredTexts $formalClosureTerms
Assert-ContainsText -Content $runbookContent -DocumentName "docs/RUNBOOK_CHATGPT_CODEX.md" -RequiredTexts $formalClosureTerms
Assert-ContainsText -Content $decisionLogContent -DocumentName "docs/DECISION_LOG.md" -RequiredTexts $formalClosureTerms

[void](Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Closed "NO" -Gate "PASS"))
[void](Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CREATE_NEW_CHAT" -Closed "YES" -Gate "PASS"))
[void](Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Project "Shopee Portfolio Control" -Chat "GPTチャット切替基準正式化" -Closed "NO" -Gate "PASS"))
$explicitlyDeniedMutations = @(
    "編集: 禁止",
    "commit: 禁止",
    "push: 禁止",
    "Git操作: 編集、commit、pushは禁止",
    "| Git操作 | commit、pushは禁止 |"
) -join [Environment]::NewLine
[void](Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Closed "NO" -Gate "STOP" -MutationStatement $explicitlyDeniedMutations))

Assert-Rejected -Description "必須欄欠落" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Closed "NO" -Gate "PASS" -OmitField "result target GPT chat")
}
Assert-Rejected -Description "空欄" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Project "" -Closed "NO" -Gate "PASS")
}
Assert-Rejected -Description "不正な列挙値" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "PAUSE" -Closed "NO" -Gate "PASS")
}
Assert-Rejected -Description "chatに未確定を含む" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Chat "未確定（新規チャット作成後）" -Closed "NO" -Gate "PASS")
}
Assert-Rejected -Description "chatに新規チャット・未確定を含む" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Chat "新規チャット・未確定" -Closed "NO" -Gate "PASS")
}
Assert-Rejected -Description "chatにTBDを含む" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Chat "TBD after handoff" -Closed "NO" -Gate "PASS")
}
Assert-Rejected -Description "chatにUNCONFIRMEDを含む" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Chat "UNCONFIRMED_CHAT" -Closed "NO" -Gate "PASS")
}
Assert-Rejected -Description "projectに未定を含む" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Project "project未定" -Closed "NO" -Gate "PASS")
}
Assert-Rejected -Description "projectがN/A" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Project "N/A" -Closed "NO" -Gate "PASS")
}
Assert-Rejected -Description "projectがNA" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Project "NA" -Closed "NO" -Gate "PASS")
}
Assert-Rejected -Description "CREATE_NEW_CHATとchat空欄" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CREATE_NEW_CHAT" -Chat "" -Closed "YES" -Gate "PASS")
}
Assert-Rejected -Description "CREATE_NEW_CHATとFORMAL_WORK_UNIT_CLOSED: NO" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CREATE_NEW_CHAT" -Closed "NO" -Gate "PASS")
}
Assert-Rejected -Description "不正な組合せなのにCHAT_HANDOFF_GATE: PASS" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CREATE_NEW_CHAT" -Closed "NO" -Gate "PASS")
}
Assert-Rejected -Description "同一canonical fieldの矛盾" -Action {
    $conflictingBrief = New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Closed "NO" -Gate "PASS"
    $conflictingBrief += [Environment]::NewLine + "result target GPT chat: 別のチャット"
    Assert-WorkBriefHandoff -Content $conflictingBrief
}
Assert-Rejected -Description "CHAT_HANDOFF_GATE: STOPなのに作業許可" -Action {
    Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Closed "NO" -Gate "STOP" -AllowMutation)
}
$mutationPermissionCases = @(
    "commit: 許可",
    "push: 許可",
    "ファイル編集: 許可",
    "Git操作: 編集、commit、pushを許可",
    "Git操作: branch作成、編集、commit、通常pushを許可",
    "edit: allowed",
    "commit: allowed",
    "push: allowed",
    "| 編集 | 許可 |",
    "| commit | 許可 |",
    "| push | 許可 |",
    "| ファイル編集 | 許可 |",
    "| Git操作 | 編集、commit、pushを許可 |",
    "| Git操作 | branch作成、編集、commit、通常pushを許可 |"
)
foreach ($mutationPermissionCase in $mutationPermissionCases) {
    Assert-Rejected -Description "CHAT_HANDOFF_GATE: STOPの変更許可: $mutationPermissionCase" -Action {
        Assert-WorkBriefHandoff -Content (New-TestWorkBrief -Disposition "CONTINUE_CURRENT_CHAT" -Closed "NO" -Gate "STOP" -MutationStatement $mutationPermissionCase)
    }
}

if (-not $SkipBriefPathExitTest) {
    Assert-StopBriefPathRejected -ScriptPath $PSCommandPath
}

if ($PSBoundParameters.ContainsKey("BriefPath")) {
    if (-not (Test-Path -LiteralPath $BriefPath -PathType Leaf)) {
        throw "指定されたWORK_BRIEFがありません: $BriefPath"
    }
    $briefContent = Get-Content -LiteralPath $BriefPath -Raw -Encoding utf8
    $briefResult = Assert-WorkBriefHandoff -Content $briefContent
    if ($briefResult.Gate -eq "STOP") {
        throw "CHAT_HANDOFF_GATE: STOPのためBRIEF_GATE: STOP"
    }
}

Write-Host "PASS: WORK_BRIEF handoff verification"
