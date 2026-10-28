[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$TaskContext,
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [string]$KeyPath,
    [string]$ReferenceSource,
    [string]$KeyUseAuthorizationRef,
    [string]$AdditionalGateReasonRef
)

# Metadata only: no key/Anchor loading and no signing/Provider invocation.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$exitCode = 10
try {
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'Interpreter missing' }
    $arguments = @('-B', '-m', 'governance.owner_evidence_preparation', '--task-context', $TaskContext)
    $options = [ordered]@{
        '--key-path' = $KeyPath; '--reference-source' = $ReferenceSource
        '--key-use-authorization-ref' = $KeyUseAuthorizationRef
        '--additional-gate-reason-ref' = $AdditionalGateReasonRef
    }
    foreach ($entry in $options.GetEnumerator()) {
        if (-not [string]::IsNullOrWhiteSpace($entry.Value)) { $arguments += @($entry.Key, $entry.Value) }
    }
    Push-Location $root
    try {
        $ErrorActionPreference = 'Continue'
        $lines = @(& $PythonPath @arguments 2>&1)
        $nativeExit = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
    }
    finally { Pop-Location }
    $data = ($lines | ForEach-Object { [string]$_ }) -join "`n" | ConvertFrom-Json
    if ($data.decision -notin @('CONTINUE', 'HOLD', 'HARD_STOP')) { throw 'Invalid result' }
    if ($data.reason_code -notmatch '^OWNER_[A-Z_]{1,80}$' -or $data.stage -ne 'PREPARATION' -or $data.signing_state -ne 'NOT_SIGNED') { throw 'Unsafe result' }
    if ($data.key_checked -or $data.formal_acceptance_ready) { throw 'Not preparation metadata' }
    $missing = @($data.missing | ForEach-Object { if ($_ -notmatch '^OWNER_[A-Z_]{1,80}$') { throw 'Unsafe missing item' }; [string]$_ })
    $gates = @($data.additional_gate_ids | ForEach-Object { if ($_ -notmatch '^[a-z][a-z0-9.-]*$') { throw 'Unsafe gate' }; [string]$_ })
    $expectedExit = @{ CONTINUE = 0; HOLD = 10; HARD_STOP = 20 }[$data.decision]
    if ($nativeExit -ne $expectedExit) { throw 'Exit mismatch' }
    $result = [ordered]@{ decision = $data.decision; reason_code = $data.reason_code; stage = 'PREPARATION'; signing_state = 'NOT_SIGNED'; key_checked = $false; formal_acceptance_ready = $false; requires_current_designation_review = $true; missing = $missing; additional_gate_ids = $gates }
    $exitCode = $expectedExit
}
catch {
    $result = [ordered]@{ decision = 'HOLD'; reason_code = 'OWNER_PREPARATION_LAUNCH_HOLD'; stage = 'PREPARATION'; signing_state = 'NOT_SIGNED'; key_checked = $false; formal_acceptance_ready = $false; requires_current_designation_review = $true; missing = @(); additional_gate_ids = @() }
}
Write-Output ($result | ConvertTo-Json -Compress)
exit $exitCode
