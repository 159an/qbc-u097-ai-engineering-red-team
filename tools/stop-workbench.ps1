# AGH 工作台停止器（供桌面快捷方式调用）
#
# 只终止「本项目构建产物启动的 serve 实例」，不碰同端口的其他程序。
# 关闭浏览器不会结束后台服务，需要停止时用这个。

param(
    [int]$Port = 4177,
    [switch]$NoUi
)

$ErrorActionPreference = 'Continue'

$entry = 'D:\dshworkplace\agh-build\runtime\agnes.mjs'

function Show-Info([string]$message, [string]$title = 'AGH 工作台') {
    if ($NoUi) { Write-Host $message; return }
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        [System.Windows.Forms.MessageBox]::Show($message, $title, 'OK', 'Information') | Out-Null
    } catch { Write-Host $message }
}

$conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $conns) {
    Show-Info "端口 $Port 上没有正在运行的服务，无需停止。"
    exit 0
}

$stopped = @()
foreach ($procId in ($conns | Select-Object -ExpandProperty OwningProcess -Unique)) {
    $info = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
    if ($null -eq $info -or $info.Name -ne 'node.exe') { continue }
    $cmd = [string]$info.CommandLine
    if ($cmd -like "*$entry*" -and $cmd -like '*serve*') {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        $stopped += $procId
    }
}

if ($stopped.Count -eq 0) {
    Show-Info "端口 $Port 被占用，但占用者不是本项目的 AGH 实例，因此没有终止任何进程。"
    exit 1
}

Start-Sleep -Milliseconds 800
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    Show-Info "已请求停止（PID $($stopped -join ', ')），但端口 $Port 仍在监听，请稍后重试。"
    exit 1
}
Show-Info "AGH 工作台已停止（PID $($stopped -join ', ')）。"

