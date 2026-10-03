# 一键启动靶场：求解服务（被测）+ 解析解基准（Oracle）
#
# 用法：
#   pwsh -File scripts\start-services.ps1
#   pwsh -File scripts\start-services.ps1 -Fault hide-blowup
#   pwsh -File scripts\start-services.ps1 -Fault silent-clamp,shared-state
#
# 可用故障开关（对应 src\solver-service.mjs 顶部说明）：
#   hide-blowup        发散时仍报 blowUp:false（谎报自身状态）
#   shared-state       异步切片推进 + 模块级共享缓冲，并发请求互相污染
#   silent-clamp       非法参数不报 400，静默取绝对值
#   partial-on-timeout 超出步数上限时返回部分结果且不标记 incomplete

param(
    [ValidateSet('hide-blowup', 'shared-state', 'silent-clamp', 'partial-on-timeout')]
    [string[]]$Fault = @(),
    [int]$SolverPort = 8081,
    [int]$OraclePort = 8082,
    [int]$TimeoutSec = 30
)

$ErrorActionPreference = 'Continue'

$repoRoot = Split-Path -Parent $PSScriptRoot
$logDir   = Join-Path $repoRoot 'evidence\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$faultMap = @{
    'hide-blowup'        = 'QBC_FAULT_HIDE_BLOWUP'
    'shared-state'       = 'QBC_FAULT_SHARED_STATE'
    'silent-clamp'       = 'QBC_FAULT_SILENT_CLAMP'
    'partial-on-timeout' = 'QBC_FAULT_PARTIAL_ON_TIMEOUT'
}

function Stop-Services {
    Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'solver-service\.mjs|oracle-service\.mjs' } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "  已停止 PID $($_.ProcessId)"
        }
    Start-Sleep -Milliseconds 700
}

function Wait-Health([int]$Port, [string]$Name) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3
            if ($r.ok) { return $true }
        } catch { }
        Start-Sleep -Milliseconds 400
    }
    return $false
}

Write-Host '[1/3] 停止已有实例'
Stop-Services

Write-Host '[2/3] 应用故障开关'
$applied = @()
foreach ($f in $Fault) {
    $name = $faultMap[$f]
    Set-Item -Path "env:$name" -Value 'on'
    $applied += $name
}
if ($applied.Count -eq 0) { Write-Host '  （无：默认全关，服务是诚实正确的）' } else { $applied | ForEach-Object { Write-Host "  $_ = on" } }

Write-Host '[3/3] 启动服务'
$env:QBC_SOLVER_PORT = "$SolverPort"
$env:QBC_ORACLE_PORT = "$OraclePort"

Start-Process -FilePath 'node' -ArgumentList @('src\solver-service.mjs') `
    -WorkingDirectory $repoRoot -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'solver.out.log') `
    -RedirectStandardError  (Join-Path $logDir 'solver.err.log')

# 故障环境变量只对求解服务有意义，Oracle 必须保持干净
foreach ($name in $faultMap.Values) { Remove-Item -Path "env:$name" -ErrorAction SilentlyContinue }

Start-Process -FilePath 'node' -ArgumentList @('src\oracle-service.mjs') `
    -WorkingDirectory $repoRoot -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'oracle.out.log') `
    -RedirectStandardError  (Join-Path $logDir 'oracle.err.log')

$okSolver = Wait-Health $SolverPort 'solver'
$okOracle = Wait-Health $OraclePort 'oracle'

Write-Host ''
if ($okSolver) { Write-Host "求解服务  http://127.0.0.1:$SolverPort/  OK" } else { Write-Host "求解服务  未就绪 —— 见 evidence\logs\solver.err.log"; exit 1 }
if ($okOracle) { Write-Host "解析解基准 http://127.0.0.1:$OraclePort/  OK" } else { Write-Host "解析解基准 未就绪 —— 见 evidence\logs\oracle.err.log"; exit 1 }
Write-Host ''
Write-Host "故障状态：$(if ($applied.Count) { $applied -join ', ' } else { '无（诚实服务）' })"

