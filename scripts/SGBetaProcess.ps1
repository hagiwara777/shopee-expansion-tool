# Shared identity checks for the actual listener, including Windows venv redirectors.
function Get-SGBetaProcessIdentity {
    param(
        [string]$AppPath,
        [int]$Port,
        [int]$LauncherId = 0,
        $RecordedIdentity = $null,
        [switch]$AllowNoListener
    )
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    $owners = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($null -ne $RecordedIdentity) {
        if ($null -eq $RecordedIdentity.created_utc_ticks) { throw 'SG process record needs confirmation.' }
        $serverId = [int]$RecordedIdentity.pid
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$serverId"
        if ($null -eq $process) { return $null }
        if ($process.CreationDate.ToUniversalTime().Ticks -ne [long]$RecordedIdentity.created_utc_ticks) {
            throw 'SG process creation identity differs.'
        }
        if (@($owners | Where-Object { $_ -ne $serverId }).Count -or
            (-not $AllowNoListener -and $owners.Count -ne 1)) {
            throw 'SG listening process differs.'
        }
    } else {
        if ($owners.Count -ne 1 -or $LauncherId -le 0) { throw 'SG listener cannot be identified.' }
        $serverId = [int]$owners[0]
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$serverId"
        # venv python.exe redirects to an interpreter child. Accept only the
        # listener descended from the process we just launched, never any port user.
        $ancestor = $process
        $owned = $false
        for ($depth=0; $depth -lt 16 -and $null -ne $ancestor; $depth++) {
            if ($ancestor.ProcessId -eq $LauncherId) { $owned=$true; break }
            if ($ancestor.ParentProcessId -eq 0) { break }
            $ancestor = Get-CimInstance Win32_Process -Filter "ProcessId=$($ancestor.ParentProcessId)"
        }
        if (-not $owned) { throw 'SG listener is not owned by this launch.' }
    }
    if ($null -eq $process -or -not $process.CommandLine.Contains($AppPath)) {
        throw 'SG application command differs.'
    }
    # Integer ticks round-trip unchanged through JSON in PowerShell 5.1 and 7;
    # ISO date strings can otherwise deserialize as different DateTime kinds.
    return [pscustomobject]@{pid=$serverId;created_utc_ticks=$process.CreationDate.ToUniversalTime().Ticks}
}
