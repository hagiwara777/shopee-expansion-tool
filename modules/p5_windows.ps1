[CmdletBinding()]
param(
    [ValidateSet('Storage','Process','SetAcl','Host')][string]$Action,
    [string]$Target,
    [string]$OperatorSid,
    [int]$Port
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
if ($Action -eq 'Host') {
    # Read-only profile planning before any store or application exists.
    $parentId = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
    $parentImage = (Get-CimInstance Win32_Process -Filter "ProcessId=$parentId").ExecutablePath
    @{ machine=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Cryptography').MachineGuid;
       sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value;
       executable=$parentImage
    } | ConvertTo-Json -Compress
    exit
}
if ($Action -eq 'Process') {
    # Parent Python PID, since this script runs in a child PowerShell process.
    $parentId = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$parentId"
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop | ForEach-Object {
        @{ pid=[int]$_.OwningProcess; address=$_.LocalAddress; port=[int]$_.LocalPort }
    })
    @{ pid=[int]$process.ProcessId; started=$process.CreationDate.ToUniversalTime().ToString('o');
       sid=(Invoke-CimMethod -InputObject $process -MethodName GetOwnerSid).Sid;
       executable=$process.ExecutablePath; command=$process.CommandLine; listeners=$listeners;
       machine=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Cryptography').MachineGuid
    } | ConvertTo-Json -Depth 8 -Compress
    exit
}
$operatorIdentity = New-Object System.Security.Principal.SecurityIdentifier($OperatorSid)
$allowed = @($OperatorSid, 'S-1-5-18', 'S-1-5-32-544')
if (@($allowed | Select-Object -Unique).Count -ne 3) { throw 'P5 operator identity invalid' }
if ($Action -eq 'SetAcl') {
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetOwner($operatorIdentity)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in $allowed) {
        $identity = New-Object System.Security.Principal.SecurityIdentifier($sid)
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Target -AclObject $acl
    @{ applied=$true } | ConvertTo-Json -Compress
    exit
}
$resolved = [IO.Path]::GetFullPath($Target)
$drive = [IO.Path]::GetPathRoot($resolved)
if ($drive -notmatch '^[A-Za-z]:\\$') { throw 'P5 local fixed volume required' }
Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class P5DosDevice {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
    public static extern uint QueryDosDevice(string name, StringBuilder target, int length);
}
'@
$device = New-Object Text.StringBuilder(4096)
if ([P5DosDevice]::QueryDosDevice($drive.Substring(0,2), $device, $device.Capacity) -eq 0) { throw 'P5 volume unknown' }
$unaliased = $device.ToString() -match '^\\Device\\HarddiskVolume[0-9]+$'
$volume = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$($drive.Substring(0,2))'"
$systemVolume = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$existing = $resolved
while (-not (Test-Path -LiteralPath $existing)) { $existing = Split-Path -Parent $existing }
$acl = Get-Acl -LiteralPath $existing
$rules = @($acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
$valid = $acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -in $allowed
$principals = @($rules | ForEach-Object { $_.IdentityReference.Value } | Select-Object -Unique)
foreach ($rule in $rules) {
    if ($rule.IdentityReference.Value -notin $allowed -or $rule.AccessControlType -ne 'Allow' -or
        ($rule.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::FullControl) -ne
            [System.Security.AccessControl.FileSystemRights]::FullControl) { $valid=$false }
}
if (Test-Path -LiteralPath $resolved) {
    foreach ($child in @(Get-ChildItem -LiteralPath $resolved -Recurse -Force -ErrorAction Stop)) {
        if (($child.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'P5 alias refused' }
        $childAcl = Get-Acl -LiteralPath $child.FullName
        if ($childAcl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -notin $allowed) { $valid=$false }
        foreach ($rule in $childAcl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])) {
            if ($rule.IdentityReference.Value -notin $allowed -or $rule.AccessControlType -ne 'Allow') { $valid=$false }
        }
    }
}
$labels = @($principals | ForEach-Object {
    if ($_ -eq 'S-1-5-18') { 'SYSTEM' } elseif ($_ -eq 'S-1-5-32-544') { 'Administrators' } else { $_ }
})
@{ volume=$volume.VolumeSerialNumber; filesystem=$volume.FileSystem; fixed=($volume.DriveType -eq 3);
   unaliased=$unaliased; principals=$labels; acl_valid=$valid;
   inheritance_disabled=($existing -eq $resolved -and $acl.AreAccessRulesProtected);
   free_bytes=[long]$volume.FreeSpace; c_free_bytes=[long]$systemVolume.FreeSpace
} | ConvertTo-Json -Depth 5 -Compress
