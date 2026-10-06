[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'ShopeeExpansionTool\SG-Beta\deployment.json'),
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$profile = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$root = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $root
try {
    & $profile.python_path -m modules.sg_beta_environment --config $ConfigPath
    if ($LASTEXITCODE -ne 0) { throw 'SG beta preflight did not pass.' }
    $launcher = Join-Path $root 'scripts\Start-SGBeta.ps1'
    $destination = Join-Path ([Environment]::GetFolderPath('Desktop')) 'SG Beta.lnk'
    if ($CheckOnly) { Write-Output 'PASS: dedicated SG shortcut can be installed; PH shortcut untouched.'; return }
    if (Test-Path -LiteralPath $destination) { throw 'SG shortcut already exists; inspect it before replacement.' }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($destination)
    $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $launcher + '" -ConfigPath "' + $ConfigPath + '" -ShowError'
    $shortcut.WorkingDirectory = $root
    $shortcut.Description = 'SG Beta - separate SG data and bounded API usage'
    $shortcut.WindowStyle = 7
    $shortcut.Save()
    Write-Output 'PASS: SG Beta shortcut installed; PH shortcut untouched.'
} finally { Pop-Location }
