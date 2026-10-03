# AGH 工作台停止器（供桌面快捷方式调用）
#
# 只终止「本项目构建产物启动的 serve 实例」，不碰同端口的其他程序。
# 关闭浏览器不会结束后台服务，需要停止时用这个。
#
# 用法：
#   pwsh -File tools\stop-workbench.ps1
#   pwsh -File tools\stop-workbench.ps1 -NoUi    # 不弹窗，供脚本调用

param(
    [int]$Port = 4177,
    [switch]$NoUi
)

$ErrorActionPreference = 'Continue'

# 用同一个解析器取入口路径，保证「认进程」的判断标准与启动器一致。
. "$PSScriptRoot\agh-env.ps1"
$entry = (Get-AghPaths -RepoRoot (Split-Path -Parent $PSScriptRoot)).Entry

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
    # 入口路径解析不到时，退化为「含 agnes.mjs 且含 serve」，仍然不会误杀无关进程。
    $matchEntry = if ($entry) { $cmd -like "*$entry*" } else { $cmd -like '*agnes.mjs*' }
    if ($matchEntry -and $cmd -like '*serve*') {
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


