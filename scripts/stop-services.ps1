# 干净停止靶场（求解服务 + 解析解基准）
#
# 只终止命令行匹配 src\solver-service.mjs / src\oracle-service.mjs 的 node 进程，
# 不碰 AGH 的 serve 进程，也不碰占同端口的其他程序。
#
# 用法：pwsh -File scripts\stop-services.ps1

$ErrorActionPreference = 'Continue'

$stopped = @()
Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'solver-service\.mjs|oracle-service\.mjs' } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $stopped += $_.ProcessId
    }

Start-Sleep -Milliseconds 800

foreach ($port in 8081, 8082) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        Write-Warning "端口 $port 仍在监听"
    }
}

if ($stopped.Count -eq 0) { Write-Host '没有找到运行中的靶场服务。' }
else { Write-Host "已停止 PID: $($stopped -join ', ')" }

