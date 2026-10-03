# QBC / U097 - D5 shared service-liveness library (start-all.ps1 / stop-all.ps1)
#
# Liveness + control via HTTP + PID files (NO Get-CimInstance / Win32_Process,
# which hangs or returns empty in the AGH shell sandbox).
#
#   Channel A (live)  : HTTP /health on 127.0.0.1:808x (200 == service up).
#                       This is the ONLY reliable "alive" check in this sandbox.
#   Channel B (handle): PID files under logs\  (solver.pid / oracle.pid) written
#                       by start-all at launch (Start-Process -PassThru .Id).
#                       stop-all reads them, Stop-Process -Id <pid> -Force,
#                       deletes them, then re-verifies /health unreachable.
#
# Exposed helpers (no side effects here):
#   Test-HttpOk [string]$Url [int]$TimeoutMs -> [bool]
#   Test-ServiceHealth                       -> [hashtable]{Solver,Oracle}
#   Get-LogDir                               -> [string] (repoRoot\logs, creates it)
#   Write-ServicePid [string]$Name [int]$procId -> writes logs\<name>.pid
#   Read-ServicePid  [string]$Name           -> [int] (0 if absent / not a number)
#   Kill-ServicePid  [string]$Name          -> [bool] (true if killed or already gone)
#   Remove-ServicePid [string]$Name         -> deletes logs\<name>.pid
#   Get-ServicePids  [string]$Name = "all"   -> [int[]]  (from pid files, no WMI)
#   Stop-ServicePids [int[]]$Pids            -> [int]    (kills pids, returns count actually killed)

$ErrorActionPreference = "Stop"

function Test-HttpOk([string]$Url, [int]$TimeoutMs = 800) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec ([double]($TimeoutMs / 1000)) -ErrorAction Stop
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Test-ServiceHealth {
    $s1 = Test-HttpOk "http://127.0.0.1:8081/health"
    $s2 = Test-HttpOk "http://127.0.0.1:8082/health"
    return @{ Solver = [bool]$s1; Oracle = [bool]$s2 }
}

function Get-LogDir {
    $d = Join-Path (Split-Path -Parent $PSScriptRoot) "logs"
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
    return $d
}

function Write-ServicePid([string]$Name, [int]$procId) {
    Set-Content -Path (Join-Path (Get-LogDir) "$Name.pid") -Value $procId.ToString() -Encoding ascii
}

function Read-ServicePid([string]$Name) {
    $f = Join-Path (Get-LogDir) "$Name.pid"
    if (-not (Test-Path $f)) { return 0 }
    $v = (Get-Content $f -Raw).Trim()
    if ($v -match '^\d+$') { return [int]$v }
    return 0
}

function Kill-ServicePid([string]$Name) {
    $pidNum = Read-ServicePid $Name
    if ($pidNum -le 0) { return $true }  # no record; nothing to kill
    try {
        Stop-Process -Id $pidNum -Force -ErrorAction Stop
        # graceful + force both covered; process gone
        return $true
    } catch {
        # Stop-Process throws when the process is already gone too;
        # re-check via /health is the authoritative liveness gate in stop-all.
        Write-Warning "kill $Name (pid $pidNum) threw: $_ (will fall back to /health recheck)"
        return $false
    }
}

function Remove-ServicePid([string]$Name) {
    $f = Join-Path (Get-LogDir) "$Name.pid"
    if (Test-Path $f) { Remove-Item -Path $f -Force -ErrorAction SilentlyContinue }
}

# Kill a set of pids (from pid files). Tolerates already-gone pids; returns
# how many were actually stopped. Used by stop-all.ps1's CIM channel.
function Stop-ServicePids([int[]]$Pids) {
    $killed = 0
    foreach ($pidNum in $Pids) {
        if ($pidNum -le 0) { continue }
        try {
            Stop-Process -Id $pidNum -Force -ErrorAction Stop
            $killed++
        } catch {
            Write-Warning "stop pid $pidNum threw: $_ (may already be gone)"
        }
    }
    return $killed
}

# Return pids for one or both services from the pid files (no WMI).
function Get-ServicePids([string]$Name = "all") {
    $out = @()
    if ($Name -eq "all" -or $Name -eq "solver") {
        $p = Read-ServicePid "solver"; if ($p -gt 0) { $out += $p }
    }
    if ($Name -eq "all" -or $Name -eq "oracle") {
        $p = Read-ServicePid "oracle"; if ($p -gt 0) { $out += $p }
    }
    return $out
}
