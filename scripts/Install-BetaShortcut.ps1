[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'ShopeeExpansionTool\Beta\deployment.json'),
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$profile = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$root = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $root
try {
    & $profile.python_path -m modules.beta_environment --config $ConfigPath
    if ($LASTEXITCODE -ne 0) { throw 'PH/SG beta preflight did not pass.' }
    $launcher = Join-Path $root 'scripts\Start-Beta.ps1'
    $destination = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Shopee Beta.lnk'
    if ($CheckOnly) { Write-Output 'PASS: unified shortcut can be installed; existing shortcuts untouched.'; return }
    if (Test-Path -LiteralPath $destination) { throw 'Unified shortcut already exists; inspect it before replacement.' }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($destination)
    $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $launcher + '" -ConfigPath "' + $ConfigPath + '" -ShowError'
    $shortcut.WorkingDirectory = $root
    $shortcut.Description = 'Shopee Beta - PH/SG country selection, separate saved data'
    $shortcut.WindowStyle = 7
    $shortcut.Save()
    Write-Output 'PASS: Shopee Beta shortcut installed; existing PH/SG shortcuts untouched.'
} finally { Pop-Location }
