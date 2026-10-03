# QBC / U097 — D5 一键停止脚本
# 用法（仓库根目录）：.\scripts\stop-all.ps1

$ErrorActionPreference = "SilentlyContinue"
$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "[stop] 关闭 8081 (solver) 与 8082 (oracle) 上的 uvicorn ..." -ForegroundColor Cyan
# 找到监听 8081/8082 的 python 进程并停止
foreach ($port in @(8081, 8082)) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        foreach ($c in $conn) {
            Write-Host "  停止 PID $($c.OwningProcess) (port $port)"
            Stop-Process -Id $c.OwningProcess -Force
        }
    } else {
        Write-Host "  port $port 无监听，跳过"
    }
}

# 兜底：杀掉所有 uvicorn services.*.main:app 子进程
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "uvicorn.*services\.(solver|oracle)\.main:app" } |
    ForEach-Object {
        Write-Host "  兜底停止 PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force
    }

Write-Host "[stop] 完成" -ForegroundColor Green
