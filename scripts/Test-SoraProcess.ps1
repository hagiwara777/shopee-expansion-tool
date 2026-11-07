param(
    [string]$AppPath,
    [string]$OwnerIds,
    [int]$Port = 8510
)

# Only SORA, UNKNOWN or ERROR is returned. Never print process commands.
function Test-SoraProcesses {
    param([string]$ExpectedAppPath, [int[]]$ProcessIds, [int]$ExpectedPort)
    try {
        if ($ProcessIds.Count -eq 0) { return 'UNKNOWN' }
        $fullAppPath = [IO.Path]::GetFullPath($ExpectedAppPath)
        if (-not ('SoraStartupCommandLine' -as [type])) {
            Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class SoraStartupCommandLine {
    [DllImport("shell32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CommandLineToArgvW(string commandLine, out int count);
    [DllImport("kernel32.dll")]
    private static extern IntPtr LocalFree(IntPtr memory);
    public static string[] Parse(string commandLine) {
        int count;
        IntPtr argv = CommandLineToArgvW(commandLine, out count);
        if (argv == IntPtr.Zero) throw new InvalidOperationException("Command line unavailable");
        try {
            var result = new string[count];
            for (int i = 0; i < count; i++)
                result[i] = Marshal.PtrToStringUni(Marshal.ReadIntPtr(argv, i * IntPtr.Size));
            return result;
        } finally { LocalFree(argv); }
    }
}
'@
        }
        foreach ($ownerProcessId in $ProcessIds) {
            if ($ownerProcessId -le 0) { return 'UNKNOWN' }
            $process = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerProcessId" -ErrorAction Stop
            if ($null -eq $process -or $process.Name -notin @('python.exe', 'pythonw.exe')) { return 'UNKNOWN' }
            if ([string]::IsNullOrWhiteSpace($process.CommandLine)) { return 'UNKNOWN' }
            $arguments = @([SoraStartupCommandLine]::Parse($process.CommandLine))
            if ($arguments.Count -lt 7 -or $arguments[1] -cne '-m' -or
                $arguments[2] -cne 'streamlit' -or $arguments[3] -cne 'run' -or
                -not [IO.Path]::IsPathRooted($arguments[4]) -or
                [IO.Path]::GetFullPath($arguments[4]) -ine $fullAppPath) { return 'UNKNOWN' }
            $ports = @()
            for ($index = 5; $index -lt $arguments.Count; $index++) {
                if ($arguments[$index] -ceq '--server.port' -and $index + 1 -lt $arguments.Count) {
                    $ports += $arguments[$index + 1]
                    $index++
                } elseif ($arguments[$index].StartsWith('--server.port=', [StringComparison]::Ordinal)) {
                    $ports += $arguments[$index].Substring('--server.port='.Length)
                }
            }
            if ($ports.Count -ne 1 -or $ports[0] -cne [string]$ExpectedPort) { return 'UNKNOWN' }
        }
        return 'SORA'
    } catch {
        return 'ERROR'
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    if ([string]::IsNullOrWhiteSpace($AppPath) -or $OwnerIds -notmatch '^\d+(,\d+)*$') { 'ERROR'; exit 1 }
    $processIds = @($OwnerIds.Split(',') | ForEach-Object { [int]$_ })
    Test-SoraProcesses -ExpectedAppPath $AppPath -ProcessIds $processIds -ExpectedPort $Port
}
