# 在桌面创建 AGH 工作台快捷方式
#
# 做两件事：
#   1. 「AGH 工作台」：双击 → 服务没起就静默起来，起来了就直接开浏览器；全程无命令行窗口
#   2. 「AGH 停止」  ：双击 → 停掉由本项目构建产物启动的服务（关浏览器不会停服务）
#
# 之所以做成脚本而不是一次性命令：快捷方式被删掉、换机器、或改了安装路径后可以重建。
#
# 用法：
#   pwsh -File tools\install-desktop-shortcuts.ps1
#   pwsh -File tools\install-desktop-shortcuts.ps1 -DesktopOnly   # 只创建启动快捷方式

param(
    [switch]$DesktopOnly
)

$ErrorActionPreference = 'Stop'

$root      = Split-Path -Parent $PSScriptRoot
$openPs1   = Join-Path $PSScriptRoot 'open-workbench.ps1'
$stopPs1   = Join-Path $PSScriptRoot 'stop-workbench.ps1'
$desktop   = [Environment]::GetFolderPath('Desktop')
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

foreach ($f in @($openPs1, $stopPs1, $powershell)) {
    if (-not (Test-Path -LiteralPath $f)) { throw "缺少依赖文件: $f" }
}

# 图标：用 Node.js 运行时图标。快捷方式启动的正是 AGH 的 Node 服务，
# 比借用某个浏览器图标更贴合实际，也不会在换默认浏览器后产生误导。
$nodeExe = (Get-Command node -ErrorAction SilentlyContinue).Source
$icon = if ($nodeExe) { "$nodeExe,0" } else { "$env:SystemRoot\System32\shell32.dll,13" }

$shell = New-Object -ComObject WScript.Shell

function New-Shortcut {
    param(
        [string]$Name,
        [string]$ScriptPath,
        [string]$Description
    )
    $path = Join-Path $desktop "$Name.lnk"
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath       = $powershell
    # -WindowStyle Hidden 让被双击的启动器不留下命令行窗口；
    # 失败时脚本自己会弹窗，所以隐藏窗口不会掩盖错误。
    $lnk.Arguments        = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation     = $icon
    $lnk.Description      = $Description
    $lnk.Save()
    return $path
}

$created = @()
$created += New-Shortcut -Name 'AGH 工作台' -ScriptPath $openPs1 `
    -Description '启动 Agnes Harness 工作台（agnes-3.0-flash），就绪后自动打开浏览器'

if (-not $DesktopOnly) {
    $created += New-Shortcut -Name 'AGH 停止' -ScriptPath $stopPs1 `
        -Description '停止 Agnes Harness 工作台后台服务'
}

Write-Host "桌面: $desktop"
foreach ($p in $created) {
    Write-Host "已创建: $p"
}

# 读回校验：确认快捷方式真的落盘且指向正确
Write-Host ''
Write-Host '=== 读回校验 ==='
foreach ($p in $created) {
    if (Test-Path -LiteralPath $p) {
        $lnk = $shell.CreateShortcut($p)
        Write-Host ("{0}`n  目标: {1}`n  参数: {2}`n  图标: {3}" -f (Split-Path $p -Leaf), $lnk.TargetPath, $lnk.Arguments, $lnk.IconLocation)
    } else {
        Write-Warning "未创建成功: $p"
    }
}

