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

# Channel B: read pid files and kill every recorded process
$pids = Get-ServicePids
if ($pids.Count -eq 0) {
    Write-Host "[stop] no pid files; nothing to stop" -ForegroundColor Cyan
    exit 0
}
Write-Host "  pid files matched $($pids.Count) service process(es): $($pids -join ', ')"
$k = Stop-ServicePids -Pids $pids
Write-Host "  terminated $k process(es)"

# Channel A: HTTP re-check after a short grace
Start-Sleep -Milliseconds 400
$h = Test-ServiceHealth
if ($h.Solver -or $h.Oracle) {
    Write-Warning "  still alive after kill (solver=$($h.Solver) oracle=$($h.Oracle)) - retrying"
    $pids2 = Get-ServicePids
    if ($pids2.Count -gt 0) { Stop-ServicePids -Pids $pids2 | Out-Null; Start-Sleep -Milliseconds 400 }
    $h = Test-ServiceHealth
}

if (-not $h.Solver -and -not $h.Oracle) {
    Remove-ServicePid "solver"
    Remove-ServicePid "oracle"
    Write-Host "[stop] done: both /health endpoints down" -ForegroundColor Green
    exit 0
}
Write-Warning "[stop] FAIL: service(s) still alive (solver=$($h.Solver) oracle=$($h.Oracle))"
exit 1
