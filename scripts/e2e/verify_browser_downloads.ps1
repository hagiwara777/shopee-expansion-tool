[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateNotNullOrEmpty()]
    [string]$DownloadPath,
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

function Test-Utf8Bom([string]$Path) {
    $bytes = [IO.File]::ReadAllBytes($Path)
    return $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
}

function Get-CsvHeader([string]$Path) {
    $text = [Text.Encoding]::UTF8.GetString([IO.File]::ReadAllBytes($Path))
    $newlineIndex = $text.IndexOf("`n")
    $headerLine = if ($newlineIndex -ge 0) { $text.Substring(0, $newlineIndex) } else { $text }
    return @($headerLine.TrimStart([char]0xFEFF).TrimEnd("`r") -split ",")
}

function Test-OrderedHeader([string[]]$Actual, [string[]]$Expected) {
    return $Actual.Count -eq $Expected.Count -and ([string]::Join("|", $Actual) -eq [string]::Join("|", $Expected))
}

function Format-Value([object]$Value) {
    if ($Value -is [array]) {
        return ($Value -join ", ")
    }
    return [string]$Value
}

$failures = [System.Collections.Generic.List[string]]::new()
function Add-Failure([string]$Check, [object]$Expected, [object]$Actual) {
    $script:failures.Add(("{0}: expected=[{1}] actual=[{2}]" -f $Check, (Format-Value $Expected), (Format-Value $Actual)))
}

$auditColumns = @(
    "gate_schema_version", "candidate_asin", "final_eligibility", "reason_codes", "marketplace",
    "candidate_schema_version", "source_type", "source_id", "source_asin", "input_title",
    "product_title", "brand", "category", "amazon_url", "source_status", "source_verification",
    "source", "fetched_at", "source_note", "guardrail_status", "guardrail_risk_category",
    "guardrail_matched_terms", "guardrail_source", "guardrail_note", "existing_listing_status",
    "existing_evidence_count", "existing_match_fields", "existing_shop_labels", "existing_source_files",
    "existing_source_row_numbers", "existing_product_ids", "existing_model_ids", "existing_stocks",
    "existing_product_names", "existing_evidence_json", "input_duplicate_status", "source_asin_status",
    "metadata_status", "metadata_missing_fields"
)

try {
    $null = Get-FormalRepositoryRoot
    $WorkspaceRoot = [IO.Path]::GetFullPath($WorkspaceRoot)
    $expectedPath = Join-Path (Join-Path $WorkspaceRoot "current") "expected.json"
    $inputCandidatePath = Join-Path (Join-Path (Join-Path $WorkspaceRoot "current") "input") "01_candidates_EXPECT_4.csv"
    if (-not (Test-Path -LiteralPath $expectedPath)) {
        throw "expected.jsonが見つかりません。先にprepare_browser_e2e.ps1を実行してください: $expectedPath"
    }
    if (-not (Test-Path -LiteralPath $inputCandidatePath)) {
        throw "Chrome用候補CSVが見つかりません。先にprepare_browser_e2e.ps1を実行してください: $inputCandidatePath"
    }
    $expected = Get-Content -LiteralPath $expectedPath -Raw | ConvertFrom-Json

    $downloadItem = Get-Item -LiteralPath $DownloadPath
    if ($downloadItem.PSIsContainer) {
        $matchingFiles = @(
            Get-ChildItem -LiteralPath $downloadItem.FullName -File -Filter "*.csv" |
                Where-Object {
                    try {
                        $candidateHeader = Get-CsvHeader $_.FullName
                        $candidateRows = @(Import-Csv -LiteralPath $_.FullName)
                        (Test-OrderedHeader $candidateHeader $auditColumns) -and $candidateRows.Count -eq [int]$expected.candidate_count
                    }
                    catch {
                        $false
                    }
                }
        )
        if ($matchingFiles.Count -ne 1) {
            throw "ダウンロードフォルダ内で監査用CSVを一意に特定できません。候補数=$($matchingFiles.Count)"
        }
        $downloadFile = $matchingFiles[0].FullName
    }
    else {
        $downloadFile = $downloadItem.FullName
    }
    if ([IO.Path]::GetExtension($downloadFile).ToLowerInvariant() -ne ".csv") {
        throw "ダウンロード対象はCSVである必要があります: $downloadFile"
    }

    if (-not (Test-Utf8Bom $downloadFile)) {
        Add-Failure "UTF-8 BOM" "present" "missing"
    }
    $actualHeader = Get-CsvHeader $downloadFile
    if (-not (Test-OrderedHeader $actualHeader $auditColumns)) {
        Add-Failure "必須列と列順" $auditColumns $actualHeader
    }

    $downloadRows = @(Import-Csv -LiteralPath $downloadFile)
    $inputRows = @(Import-Csv -LiteralPath $inputCandidatePath)
    $expectedAsinProperties = @($expected.asins.PSObject.Properties)
    $expectedAsins = @($expectedAsinProperties | ForEach-Object { $_.Name })
    $inputAsins = @($inputRows | ForEach-Object { $_.candidate_asin })
    $actualAsins = @($downloadRows | ForEach-Object { $_.candidate_asin })

    if ($downloadRows.Count -ne [int]$expected.candidate_count) {
        Add-Failure "監査用CSV全件数" $expected.candidate_count $downloadRows.Count
    }
    foreach ($status in @("ELIGIBLE", "REVIEW", "EXCLUDE")) {
        $actualCount = @($downloadRows | Where-Object { $_.final_eligibility -eq $status }).Count
        $expectedCount = $expected.PSObject.Properties[$status].Value
        if ($actualCount -ne [int]$expectedCount) {
            Add-Failure "$status 件数" $expectedCount $actualCount
        }
    }

    $duplicateAsins = @(
        $downloadRows |
            Group-Object -Property candidate_asin |
            Where-Object { [string]::IsNullOrWhiteSpace($_.Name) -or $_.Count -ne 1 } |
            ForEach-Object { "{0} (count={1})" -f $_.Name, $_.Count }
    )
    if ($duplicateAsins.Count -gt 0) {
        Add-Failure "重複または空のASIN" "none" $duplicateAsins
    }

    $missingAsins = @($expectedAsins | Where-Object { $_ -notin $actualAsins })
    $unexpectedAsins = @($actualAsins | Where-Object { $_ -notin $expectedAsins })
    if ($missingAsins.Count -gt 0) {
        Add-Failure "不足ASIN" "none" $missingAsins
    }
    if ($unexpectedAsins.Count -gt 0) {
        Add-Failure "期待しないASIN" "none" $unexpectedAsins
    }
    if ([string]::Join("|", $inputAsins) -ne [string]::Join("|", $actualAsins)) {
        Add-Failure "入力fixtureとのASIN順序対応" $inputAsins $actualAsins
    }

    foreach ($expectedAsinProperty in $expectedAsinProperties) {
        $asin = $expectedAsinProperty.Name
        $expectedResult = $expectedAsinProperty.Value
        $rowsForAsin = @($downloadRows | Where-Object { $_.candidate_asin -eq $asin })
        if ($rowsForAsin.Count -ne 1) {
            Add-Failure "$asin の行数" 1 $rowsForAsin.Count
            continue
        }
        $actualRow = $rowsForAsin[0]
        if ($actualRow.final_eligibility -ne $expectedResult.final) {
            Add-Failure "$asin の最終判定" $expectedResult.final $actualRow.final_eligibility
        }
        if ($actualRow.guardrail_status -ne $expectedResult.guardrail) {
            Add-Failure "$asin のGuardrail判定" $expectedResult.guardrail $actualRow.guardrail_status
        }
        if ($actualRow.existing_listing_status -ne $expectedResult.inventory) {
            Add-Failure "$asin の既出品判定" $expectedResult.inventory $actualRow.existing_listing_status
        }
    }
}
catch {
    Add-Failure "検証処理" "valid Browser E2E audit CSV" $_.Exception.Message
}

if ($failures.Count -gt 0) {
    Write-Host "FAIL: Browser E2E download verification" -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host " - $failure" -ForegroundColor Red
    }
    exit 1
}

Write-Host "PASS: Browser E2E download verification" -ForegroundColor Green
Write-Host "audit_csv=$downloadFile"
Write-Host "candidate_count=$($expected.candidate_count) ELIGIBLE=$($expected.ELIGIBLE) REVIEW=$($expected.REVIEW) EXCLUDE=$($expected.EXCLUDE)"
