# AGH 工作台启动器（供桌面快捷方式调用）
#
# 行为：
#   1. 若服务已在监听端口，直接打开浏览器（不重启、不打断已有任务）
#   2. 若未监听，后台静默启动 AGH serve，等端口与 HTTP 都就绪后再打开浏览器
#   3. 出错时弹窗提示，而不是静默失败（因为它通常是被双击、没有终端可看）
#
# 用法：
#   pwsh -File tools\open-workbench.ps1
#   pwsh -File tools\open-workbench.ps1 -Restart      # 强制重启服务
#   pwsh -File tools\open-workbench.ps1 -Workspace D:\some\project

param(
    [string]$Profile   = 'local-dev',
    [string]$Workspace = 'D:\dshworkplace\hackathon-qbc',
    [int]$Port         = 4177,
    [int]$TimeoutSec   = 90,
    [switch]$Restart,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Continue'

$root     = Split-Path -Parent $PSScriptRoot
$entry    = 'D:\dshworkplace\agh-build\runtime\agnes.mjs'
$logDir   = Join-Path $root 'evidence\logs'
$url      = "http://127.0.0.1:$Port/"

function Show-Error([string]$message) {
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        [System.Windows.Forms.MessageBox]::Show($message, 'AGH 工作台启动失败', 'OK', 'Error') | Out-Null
    } catch {
        Write-Host $message
    }
    exit 1
}

function Test-Port([int]$p) {
    return [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

function Test-Http([string]$u) {
    try {
        $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 5
        return $r.StatusCode -eq 200
    } catch { return $false }
}

if (-not (Test-Path -LiteralPath $entry)) {
    Show-Error "找不到 AGH 构建产物：`n$entry`n`n请先构建（见 README「三、从零复现」），或运行：`ntools\start-agh.ps1"
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# --- 已在运行 ---------------------------------------------------------------
if ((Test-Port $Port) -and -not $Restart) {
    if (-not $NoBrowser) { Start-Process $url }
    exit 0
}

# --- 需要重启时，只终止经过身份校验的本地实例 --------------------------------
if ((Test-Port $Port) -and $Restart) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($procId in ($conns | Select-Object -ExpandProperty OwningProcess -Unique)) {
        $info = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
        if ($null -eq $info -or $info.Name -ne 'node.exe') { continue }
        $cmd = [string]$info.CommandLine
        # 只认「本仓库构建出来的 serve 实例」，避免误杀占用同端口的其他程序。
        if ($cmd -like "*$entry*" -and $cmd -like '*serve*') {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            Write-Host "已停止旧实例 PID $procId"
        }
    }
    $wait = (Get-Date).AddSeconds(15)
    while ((Test-Port $Port) -and (Get-Date) -lt $wait) { Start-Sleep -Milliseconds 400 }
    if (Test-Port $Port) { Show-Error "端口 $Port 仍被占用，且占用者不是本项目的 AGH 实例。未启动新服务。" }
}

# --- 启动，并把输出落盘以便事后排查 -----------------------------------------
$stamp   = Get-Date -Format 'yyyyMMdd-HHmmss'
$outLog  = Join-Path $logDir "workbench-$stamp.out.log"
$errLog  = Join-Path $logDir "workbench-$stamp.err.log"

$env:AGNES_PROFILE = $Profile
try {
    Start-Process -FilePath 'node' `
        -ArgumentList @($entry, 'serve', '--profile', $Profile, '--cwd', $Workspace) `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError  $errLog | Out-Null
} catch {
    Show-Error "无法启动 AGH 服务：`n$($_.Exception.Message)"
}

# --- 等待就绪：端口监听 + HTTP 200 ------------------------------------------
$deadline = (Get-Date).AddSeconds($TimeoutSec)
$ready = $false
while ((Get-Date) -lt $deadline) {
    if ((Test-Port $Port) -and (Test-Http $url)) { $ready = $true; break }
    Start-Sleep -Milliseconds 600
}

if (-not $ready) {
    $tail = ''
    foreach ($f in @($errLog, $outLog)) {
        if (Test-Path -LiteralPath $f) {
            $tail += "`n--- $f ---`n" + ((Get-Content -LiteralPath $f -Tail 20 -Encoding UTF8) -join "`n")
        }
    }
    Show-Error "服务在 $TimeoutSec 秒内未就绪（$url）。`n日志：$logDir$tail"
}

if (-not $NoBrowser) { Start-Process $url }
Write-Host "AGH 工作台已就绪：$url"

