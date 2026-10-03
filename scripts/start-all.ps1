# QBC / U097 - D5 one-click start (background mode by default)
# Usage (repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1 -Fault 2
# Stop: scripts\stop-all.ps1
# Ports: solver 127.0.0.1:8081 / oracle 127.0.0.1:8082 (localhost only)

[CmdletBinding()]
param(
    [int]$Fault = 0,
    [switch]$Foreground
)

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# --- pick python that has uvicorn (avoid miniconda) ---
$PY = $env:QBC_PYTHON
if (-not $PY) {
    $candidates = @()
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
    $candidates += @(
        "C:\Users\26293\AppData\Local\Programs\Python\Python313\python.exe",
        "C:\Users\26293\AppData\Local\Programs\Python\Python311\python.exe",
        "D:\Claude Code\miniconda\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            try { $null = & $c -c "import uvicorn" 2>&1; if ($LASTEXITCODE -eq 0) { $PY = $c; break } } catch { }
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

# --- stop old listeners ---
function Stop-Port($port) {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($c) { foreach ($x in $c) { Stop-Process -Id $x.OwningProcess -Force -ErrorAction SilentlyContinue } }
}
Stop-Port 8081
Stop-Port 8082
Start-Sleep 1

# --- log dir ---
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Wait-For-Health($url, $timeoutSec) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1
            if ($r.StatusCode -eq 200) { return $true }
        } catch { }
        Start-Sleep -Milliseconds 300
    }
    return $false
}

if ($Foreground) {
    Write-Host "[fg] starting solver+oracle in foreground. Ctrl+C to stop."
    Start-Process -FilePath $PY -ArgumentList "-m","uvicorn","services.solver.main:app","--host","127.0.0.1","--port","8081" -WorkingDirectory $repoRoot
    Start-Process -FilePath $PY -ArgumentList "-m","uvicorn","services.oracle.main:app","--host","127.0.0.1","--port","8082" -WorkingDirectory $repoRoot
    $ok1 = Wait-For-Health "http://127.0.0.1:8081/health" 40
    $ok2 = Wait-For-Health "http://127.0.0.1:8082/health" 40
    Write-Host "solver ready=$ok1 oracle ready=$ok2"
    if (-not ($ok1 -and $ok2)) { exit 1 }
    Write-Host "[fg] both ready. stopping..."
    Stop-Port 8081
    Stop-Port 8082
} else {
    $s1 = Start-Process -FilePath $PY -ArgumentList "-m","uvicorn","services.solver.main:app","--host","127.0.0.1","--port","8081" -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir "solver.log") -RedirectStandardError (Join-Path $logDir "solver.err.log")
    $s2 = Start-Process -FilePath $PY -ArgumentList "-m","uvicorn","services.oracle.main:app","--host","127.0.0.1","--port","8082" -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir "oracle.log") -RedirectStandardError (Join-Path $logDir "oracle.err.log")
    $ok1 = Wait-For-Health "http://127.0.0.1:8081/health" 40
    $ok2 = Wait-For-Health "http://127.0.0.1:8082/health" 40
    Write-Host "solver pid=$($s1.Id) oracle pid=$($s2.Id)"
    if ($ok1 -and $ok2) {
        Write-Host "[ok] both ready. stop: scripts\stop-all.ps1"
    } else {
        Write-Warning "not all ready. check logs/"
        exit 1
    }
}
