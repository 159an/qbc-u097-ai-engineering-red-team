# QBC / U097 - D5 one-click START
# Usage (repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1 -Fault 2
# Ports: solver 127.0.0.1:8081 / oracle 127.0.0.1:8082 (localhost only)
#
# Design (PID-file + HTTP only; NO Get-CimInstance / Win32_Process - they hang
# in the AGH shell sandbox):
#   - Pre-kill: read logs\solver.pid / logs\oracle.pid, Stop-Process -Force,
#     delete stale pid files. So a new start cannot be shadowed by an old listener.
#   - Launch each uvicorn via Start-Process ... -PassThru; capture .Id and write
#     it to logs\<svc>.pid so stop-all can find the exact handle.
#   - Redirect BOTH stdout and stderr to logs\<svc>.*.log so the long-lived
#     children never inherit the caller's stdout pipe (avoids the pipe-EOF hang
#     where a captured start would wait minutes even though services are up).
#   - Liveness = HTTP /health only (the only reliable "alive" check in this sandbox).
#   - Script returns immediately after readiness; exit 1 if either /health fails.

[CmdletBinding()]
param(
    [int]$Fault = 0,
    [switch]$Foreground
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
. (Join-Path $repoRoot "scripts\lib-qbc-services.ps1")

# --- pick python that has uvicorn (avoid miniconda) ---
# 优先级（不含任何写死的本机用户名/绝对路径）：
#   1) 环境变量 QBC_PYTHON  2) PATH 上的 python/python3  3) %LOCALAPPDATA%\Programs\Python\Python3*\python.exe 通配（版本高者优先）
$PY = $env:QBC_PYTHON
if (-not $PY) {
    $candidates = @()
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
    $cmd3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($cmd3) { $candidates += $cmd3.Source }
    $localAppData = $env:LOCALAPPDATA
    if ($localAppData) {
        $globPattern = Join-Path $localAppData "Programs\Python\Python3*\python.exe"
        $foundPy = Get-ChildItem -Path $globPattern -File -ErrorAction SilentlyContinue |
                   Sort-Object FullName -Descending
        foreach ($m in $foundPy) { $candidates += $m.FullName }
    }
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) {
            try {
                & $c -c "import uvicorn" 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) { $PY = $c; break }
            } catch { }
        }
    }
}
if (-not $PY) { $PY = (Get-Command python).Source }
Write-Host "[info] python: $PY"

# --- fault switches (default all off) ---
switch ($Fault) {
    1 { $env:QBC_FAULT_CFL_GUARD = "off" }
    2 { $env:QBC_FAULT_SHARED_STATE = "on" }
    3 { $env:QBC_FAULT_SILENT_CLAMP = "on" }
    4 { $env:QBC_FAULT_PARTIAL_ON_TIMEOUT = "on" }
    0 { }
    default { Write-Warning "unknown fault $Fault, use default (all off)" }
}

# --- clean up any stale service processes via PID files (no CIM) ---
foreach ($svc in @("solver", "oracle")) {
    $stale = Read-ServicePid $svc
    if ($stale -gt 0) {
        Write-Host "[cleanup] terminating stale $svc pid $stale (from logs\$svc.pid)"
        Kill-ServicePid $svc | Out-Null
        Remove-ServicePid $svc
    }
}
# If /health is still answering after killing recorded pids, an old listener
# (pid file missing/stale) is squatting the port - report and fail rather than
# start a duplicate that would be shadowed.
$h = Test-ServiceHealth
if ($h.Solver -or $h.Oracle) {
    Write-Warning "stale listener still answering /health after pid-file kill (solver=$($h.Solver) oracle=$($h.Oracle)); cannot guarantee a clean start - stop it manually, then retry"
    exit 1
}

$logDir = Get-LogDir

function Wait-For-Health([string]$Url, [int]$TimeoutSec) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpOk $Url) { return $true }
        Start-Sleep -Milliseconds 300
    }
    return $false
}

# Launch both, capture PIDs to files, redirect streams to files.
$ps1 = Start-Process -FilePath $PY -ArgumentList "-m","uvicorn","services.solver.main:app","--host","127.0.0.1","--port","8081" -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir "solver.log") -RedirectStandardError (Join-Path $logDir "solver.err.log")
$ps2 = Start-Process -FilePath $PY -ArgumentList "-m","uvicorn","services.oracle.main:app","--host","127.0.0.1","--port","8082" -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir "oracle.log") -RedirectStandardError (Join-Path $logDir "oracle.err.log")

if ($ps1.Id -gt 0) { Write-ServicePid "solver" $ps1.Id }
if ($ps2.Id -gt 0) { Write-ServicePid "oracle" $ps2.Id }
Write-Host "[start] solver pid=$($ps1.Id) -> logs\solver.pid ; oracle pid=$($ps2.Id) -> logs\oracle.pid"

$ok1 = Wait-For-Health "http://127.0.0.1:8081/health" 40
$ok2 = Wait-For-Health "http://127.0.0.1:8082/health" 40
Write-Host "solver ready=$ok1 oracle ready=$ok2"

if ($ok1 -and $ok2) {
    Write-Host "[ok] both ready (HTTP /health up, PIDs recorded in logs\). stop with scripts\stop-all.ps1"
} else {
    Write-Warning "not all ready: solver HTTP=$ok1 oracle HTTP=$ok2 - check logs\<svc>.err.log"
    # leave the live one running so the operator can inspect; pids are recorded
    exit 1
}
