[CmdletBinding()]
param(
    [ValidateSet("prelisting_gate")]
    [string]$Suite = "prelisting_gate",
    [ValidateSet("v1", "v2")]
    [string]$FixtureVersion = "v1",
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
    if (-not (Test-Path -LiteralPath (Join-Path $gitRootFull "app.py")) -or
        -not (Test-Path -LiteralPath (Join-Path $gitRootFull "tests\fixtures\browser_e2e"))) {
        throw "正式リポジトリの必要ファイルが見つかりません。"
    }
    return $gitRootFull
}

function Clear-Directory([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
        return
    }
    Get-ChildItem -LiteralPath $Path -Force | Remove-Item -Recurse -Force
}

function Assert-Utf8Bom([string]$Path) {
    $bytes = [IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 3 -or $bytes[0] -ne 0xEF -or $bytes[1] -ne 0xBB -or $bytes[2] -ne 0xBF) {
        throw "UTF-8 BOMがありません: $Path"
    }
}

function Assert-OrderedHeader([string[]]$Actual, [string[]]$Expected, [string]$Label) {
    if ($Actual.Count -ne $Expected.Count -or ([string]::Join("|", $Actual) -ne [string]::Join("|", $Expected))) {
        throw "$Label の列が期待値と一致しません。期待値=[$($Expected -join ', ')] 実値=[$($Actual -join ', ')]"
    }
}

$repositoryRoot = Get-FormalRepositoryRoot
$WorkspaceRoot = [IO.Path]::GetFullPath($WorkspaceRoot)
$fixtureRoot = Join-Path $repositoryRoot "tests\fixtures\browser_e2e\$Suite\$FixtureVersion"
$python = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
$currentRoot = Join-Path $WorkspaceRoot "current"
$inputRoot = Join-Path $currentRoot "input"
$outputRoot = Join-Path $currentRoot "output"
$logsRoot = Join-Path $WorkspaceRoot "logs"
$archiveRoot = Join-Path $WorkspaceRoot "archive"
$readyPath = Join-Path $currentRoot "READY.txt"

try {
    if (-not (Test-Path -LiteralPath $python)) {
        throw "正式な仮想環境のPythonが見つかりません: $python"
    }
    if (-not (Test-Path -LiteralPath $fixtureRoot)) {
        throw "fixtureが見つかりません: $fixtureRoot"
    }

    & $python -m pytest "tests/test_browser_e2e_fixture_contract.py" -q
    if ($LASTEXITCODE -ne 0) {
        throw "fixture契約テストが失敗しました。Chrome用フォルダは更新しません。"
    }

    if (Test-Path -LiteralPath $readyPath) {
        Remove-Item -LiteralPath $readyPath -Force
    }

    $hasPreviousOutput = Test-Path -LiteralPath $outputRoot
    $hasPreviousLogs = Test-Path -LiteralPath $logsRoot
    if ($hasPreviousOutput -or $hasPreviousLogs) {
        $archiveRunRoot = Join-Path $archiveRoot (Get-Date -Format "yyyyMMdd-HHmmssfff")
        New-Item -ItemType Directory -Path $archiveRunRoot -Force | Out-Null
        if ($hasPreviousOutput) {
            $archiveCurrentRoot = Join-Path $archiveRunRoot "current"
            New-Item -ItemType Directory -Path $archiveCurrentRoot -Force | Out-Null
            Move-Item -LiteralPath $outputRoot -Destination (Join-Path $archiveCurrentRoot "output")
        }
        if ($hasPreviousLogs) {
            Move-Item -LiteralPath $logsRoot -Destination (Join-Path $archiveRunRoot "logs")
        }
    }

    Clear-Directory $inputRoot
    Clear-Directory $outputRoot
    New-Item -ItemType Directory -Path $logsRoot -Force | Out-Null

    $sourceExpectedPath = Join-Path $fixtureRoot "expected.json"
    $expected = Get-Content -LiteralPath $sourceExpectedPath -Raw | ConvertFrom-Json
    $fixtureExistingFiles = @(Get-ChildItem -LiteralPath $fixtureRoot -File -Filter "existing_*.csv")
    if ($fixtureExistingFiles.Count -ne 1) {
        throw "既出品fixtureは1件だけ必要です。実値=$($fixtureExistingFiles.Count)"
    }

    $candidatePath = Join-Path $inputRoot "01_candidates_EXPECT_$($expected.candidate_count).csv"
    $existingPath = Join-Path $inputRoot "02_existing_$($expected.marketplace)_$($expected.shop_label)_EXPECT_$($expected.existing_listing_row_count).csv"
    Copy-Item -LiteralPath (Join-Path $fixtureRoot "candidates.csv") -Destination $candidatePath
    Copy-Item -LiteralPath $fixtureExistingFiles[0].FullName -Destination $existingPath
    Copy-Item -LiteralPath $sourceExpectedPath -Destination (Join-Path $currentRoot "expected.json")

    Assert-Utf8Bom $candidatePath
    Assert-Utf8Bom $existingPath

    $candidateHeaders = (Get-Content -LiteralPath $candidatePath -Encoding UTF8 -First 1) -split ","
    $expectedCandidateHeaders = @(
        "schema_version", "source_type", "source_id", "source_asin", "candidate_asin",
        "input_title", "product_title", "brand", "category", "amazon_url", "source_status",
        "source_verification", "source", "fetched_at", "source_note"
    )
    Assert-OrderedHeader $candidateHeaders $expectedCandidateHeaders "候補CSV"
    $candidateRows = @(Import-Csv -LiteralPath $candidatePath)
    if ($candidateRows.Count -ne [int]$expected.candidate_count) {
        throw "候補CSVの行数が期待値と一致しません。期待値=$($expected.candidate_count) 実値=$($candidateRows.Count)"
    }

    $existingLines = @(Get-Content -LiteralPath $existingPath -Encoding UTF8)
    $existingHeaderIndex = -1
    $requiredInventoryHeaders = @("Product ID", "Parent SKU", "Model ID", "SKU", "Stock")
    for ($index = 0; $index -lt $existingLines.Count; $index++) {
        $possibleHeader = $existingLines[$index] -split ","
        if (@($requiredInventoryHeaders | Where-Object { $_ -notin $possibleHeader }).Count -eq 0) {
            $existingHeaderIndex = $index
            break
        }
    }
    if ($existingHeaderIndex -lt 0) {
        throw "既出品CSVの正式ヘッダーが見つかりません。"
    }
    $existingHeader = $existingLines[$existingHeaderIndex] -split ","
    if ($existingHeader.Count -ne [int]$expected.inventory_column_count -or
        @($requiredInventoryHeaders | Where-Object { $_ -notin $existingHeader }).Count -gt 0) {
        throw "既出品CSVの固定列契約が期待値と一致しません。"
    }
    $existingDataLines = @(
        $existingLines |
            Select-Object -Skip ($existingHeaderIndex + 1) |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
    $existingRows = @(
        $existingDataLines |
            ConvertFrom-Csv -Header @("_unused", "Product ID", "Parent SKU", "Model ID", "SKU", "Product Name", "Product Weight/kg", "Length", "Width", "Height", "Price", "Stock", "Discount ID", "Discount Price", "DTS", "Listing Status")
    )
    if ($existingRows.Count -ne [int]$expected.existing_listing_row_count) {
        throw "既出品CSVの行数が期待値と一致しません。期待値=$($expected.existing_listing_row_count) 実値=$($existingRows.Count)"
    }
    $actualExistingAsins = @($existingRows | ForEach-Object { $_.'Parent SKU' } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ([string]::Join("|", $actualExistingAsins) -ne [string]::Join("|", @($expected.existing_asins))) {
        throw "既出品CSVのParent SKUが期待値と一致しません。"
    }

    $candidateHash = (Get-FileHash -LiteralPath $candidatePath -Algorithm SHA256).Hash
    $existingHash = (Get-FileHash -LiteralPath $existingPath -Algorithm SHA256).Hash
    $readyLines = @(
        "suite=$($expected.suite)",
        "fixture_version=$($expected.fixture_version)",
        "marketplace=$($expected.marketplace)",
        "shop_count=$($expected.shop_count)",
        "shop_label=$($expected.shop_label)",
        "expected_candidate_count=$($expected.candidate_count)",
        "expected_ELIGIBLE=$($expected.ELIGIBLE)",
        "expected_REVIEW=$($expected.REVIEW)",
        "expected_EXCLUDE=$($expected.EXCLUDE)",
        "expected_existing_listing_row_count=$($expected.existing_listing_row_count)",
        "expected_existing_asin_count=$($expected.existing_asin_count)",
        "",
        "input_file=$(Split-Path -Leaf $candidatePath)",
        "absolute_path=$candidatePath",
        "data_row_count=$($candidateRows.Count)",
        "sha256=$candidateHash",
        "",
        "input_file=$(Split-Path -Leaf $existingPath)",
        "absolute_path=$existingPath",
        "data_row_count=$($existingRows.Count)",
        "sha256=$existingHash"
    )

    Start-Process -FilePath "explorer.exe" -ArgumentList @($inputRoot) | Out-Null
    [IO.File]::WriteAllText(
        $readyPath,
        (($readyLines -join [Environment]::NewLine) + [Environment]::NewLine),
        [Text.UTF8Encoding]::new($false)
    )
    Write-Host "READY: Browser E2E input is prepared at $inputRoot" -ForegroundColor Green
}
catch {
    if (Test-Path -LiteralPath $readyPath) {
        Remove-Item -LiteralPath $readyPath -Force
    }
    Write-Error "Browser E2E preparation failed: $($_.Exception.Message)"
    exit 1
}
