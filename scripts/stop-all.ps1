# QBC / U097 - D5 one-click STOP (dual-channel liveness + immediate return)
# Usage (repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\stop-all.ps1
#
# Logic: CIM-match & kill all "uvicorn services.(solver|oracle).main:app"
# processes, then HTTP re-check /health on 8081+8082.
#   - both down   -> "done", exit 0
#   - any still up -> "still alive", exit 1
# No dependency on Get-NetTCPConnection (avoids silent false-success when
# the TCP table is unreadable).

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
. (Join-Path $repoRoot "scripts\lib-qbc-services.ps1")

Write-Host "[stop] stopping uvicorn services on 8081 (solver) and 8082 (oracle) ..." -ForegroundColor Cyan

# --- Channel 1: pid-file kill (primary) ---
$pids = Get-ServicePids
if ($pids.Count -eq 0) {
    Write-Host "[stop] no pid files found; will rely solely on /health + port-based fallback (channel 2)"
} else {
    Write-Host "  pid files matched $($pids.Count) service process(es): $($pids -join ', ')"
    $k = Stop-ServicePids -Pids $pids
    Write-Host "  terminated $k process(es) via pid files"
}

# --- Channel 2: HTTP re-check + port-based fallback (authoritative liveness gate) ---
Start-Sleep -Milliseconds 400
$h = Test-ServiceHealth
if ($h.Solver -or $h.Oracle) {
    # pid files were missing/stale OR the recorded pids already exited -
    # re-locate the ACTUAL listener PID by port and kill it (honest channel 2).
    $fallbackUsed = $false
    if ($h.Solver) {
        $p = Get-ListenerPidByPort 8081
        if ($p -gt 0 -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) {
            $ok = Stop-ListenerPid $p
            Write-Host "  [fallback] solver still up; killed real listener pid=$p via port 8081 owner ($($ok))"
            $fallbackUsed = $true
        } else {
            Write-Warning "  [fallback] solver /health up but no live listener pid found on 8081"
        }
    }
    if ($h.Oracle) {
        $p = Get-ListenerPidByPort 8082
        if ($p -gt 0 -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) {
            $ok = Stop-ListenerPid $p
            Write-Host "  [fallback] oracle still up; killed real listener pid=$p via port 8082 owner ($($ok))"
            $fallbackUsed = $true
        } else {
            Write-Warning "  [fallback] oracle /health up but no live listener pid found on 8082"
        }
    }
    Start-Sleep -Milliseconds 400
    $h = Test-ServiceHealth
}

if (-not $h.Solver -and -not $h.Oracle) {
    Remove-ServicePid "solver"
    Remove-ServicePid "oracle"
    Write-Host "[stop] done: both /health endpoints down" -ForegroundColor Green
    exit 0
}
Write-Warning "[stop] FAIL: service(s) still alive after pid-file + port-based channels (solver=$($h.Solver) oracle=$($h.Oracle)) - manual intervention needed"
exit 1
