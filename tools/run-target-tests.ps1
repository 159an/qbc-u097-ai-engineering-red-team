# 靶场三类测试编排器：正常 / 边界 / 失败
#
# 与 tools\run-conformance.ps1 的区别：
#   run-conformance.ps1  测的是 **AGH 运行底座**本身（文件读写、审批、fail-closed）
#   本脚本               测的是 **靶场（工程传热求解服务）**，智能体必须通过插件工具与它交互
#
# 每个用例：
#   1. 按 faults 字段重启靶场（应用故障开关）
#   2. 在独立工作区里跑智能体任务（独立会话，避免互相污染与 taint 干扰）
#   3. 导出 AGH 原生轨迹 → 断言分析 → 生成可发布脱敏版
#
# 用法：
#   pwsh -File tools\run-target-tests.ps1              # 跑全部
#   pwsh -File tools\run-target-tests.ps1 -Only T-F1   # 只跑一个

param(
    [string]$Only
)

$ErrorActionPreference = 'Continue'

. "$PSScriptRoot\agh-env.ps1"
$Agh      = Get-AghPaths -RepoRoot (Split-Path -Parent $PSScriptRoot)
$root     = $Agh.RepoRoot
$entry    = $Agh.Entry
$evDir    = Join-Path $root 'evidence\target-tests'
$workRoot = Join-Path $root 'runtime\target-tests'
$specPath = Join-Path $PSScriptRoot 'target-tests.json'

$env:AGNES_PROFILE = 'local-dev'

if (-not $entry) { Write-AghMissing $Agh; exit 1 }

New-Item -ItemType Directory -Force -Path $evDir, $workRoot | Out-Null

$spec = Get-Content -LiteralPath $specPath -Raw -Encoding UTF8 | ConvertFrom-Json
$results = @()

foreach ($t in $spec.tests) {
    if ($Only -and $t.id -ne $Only) { continue }

    Write-Host ''
    Write-Host ("=== [{0}] {1} ({2}) ===" -f $t.id, $t.title, $t.class)

    # 1) 按用例需要重启靶场
    #    用**哈希表** splat 而不是数组 splat：数组 splat 在这里会把 '-Fault' 本身当成
    #    参数值传进去（实测报 "参数 -Fault 不属于 ValidateSet"），哈希表没有这个歧义。
    $svcArgs = @{}
    if ($t.faults -and $t.faults.Count -gt 0) { $svcArgs['Fault'] = @($t.faults) }
    Write-Host ("靶场故障开关: {0}" -f $(if ($svcArgs.Count) { $t.faults -join ',' } else { '无（诚实服务）' }))
    & (Join-Path $root 'scripts\start-services.ps1') @svcArgs | Select-Object -Last 3

    # 2) 独立工作区（每次运行都用新的时间戳目录，保证独立会话）
    #
    # 为什么要带时间戳：AGH 的会话 id 由工作区路径派生（agnes:...:workspace:<hash>）。
    # 复用同一路径会让多次运行**累加到同一个会话**，轨迹里混着上一轮的失败调用与终态，
    # 分析器取到的 turn/end 可能来自上一轮——证据就变成混淆的。实测踩过这个坑：
    # 放宽 schema 后重跑，报告仍显示上一轮的 blocked 与 5 次被拒调用。
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $ws = Join-Path $workRoot ("{0}-{1}" -f $t.id, $stamp)
    Remove-Item -LiteralPath $ws -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $ws | Out-Null

    $resultLog = Join-Path $evDir ($t.id + '.result.jsonl')
    $trajPath  = Join-Path $evDir ($t.id + '.trajectory.raw.json')

    $started = Get-Date
    & node $entry -p --mode json --cwd $ws $t.prompt *>&1 | Tee-Object -FilePath $resultLog | Out-Null
    $exitCode = $LASTEXITCODE
    $elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)

    # 3) 导出轨迹
    $sid = $null
    try {
        $raw = Get-Content -LiteralPath $resultLog -Raw -Encoding UTF8
        $m = [regex]::Match($raw, '"sessionId":"([^"]+)"')
        if ($m.Success) { $sid = $m.Groups[1].Value }
    } catch { }
    if ($sid) {
        & node $entry export $sid --raw -o $trajPath --format agnes *>&1 | Out-Null
        Write-Host ("会话: {0}" -f $sid)
    } else {
        Write-Warning ("[{0}] 未能提取 sessionId，跳过轨迹导出" -f $t.id)
    }

    # 4) 断言分析
    $argv = @(
        (Join-Path $PSScriptRoot 'analyze-trajectory.mjs'), $trajPath,
        '--profile', $t.profile,
        '--expected-terminal', $t.expectedTerminal,
        '--expect-min-steps', $t.expectMinSteps,
        '--out',  (Join-Path $evDir ($t.id + '.report.md')),
        '--json', (Join-Path $evDir ($t.id + '.summary.json')),
        '--sanitize', (Join-Path $evDir ($t.id + '.sanitized.jsonl'))
    )
    if ($t.mustMentionAny -and $t.mustMentionAny.Count -gt 0) { $argv += @('--must-mention-any', ($t.mustMentionAny -join ',')) }
    if ($t.require -and $t.require.Count -gt 0) { $argv += @('--require-numbers', ($t.require -join ',')) }

    & node @argv
    $analyzerExit = $LASTEXITCODE

    $results += [pscustomobject]@{
        id           = $t.id
        class        = $t.class
        title        = $t.title
        faults       = ($t.faults -join ',')
        exitCode     = $exitCode
        wallSeconds  = $elapsed
        sessionId    = $sid
        analyzerExit = $analyzerExit
    }
}

# 收尾：把靶场恢复到诚实配置，避免影响后续手工使用
& (Join-Path $root 'scripts\start-services.ps1') | Select-Object -Last 3

$indexPath = Join-Path $evDir 'run-index.json'
$results | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $indexPath -Encoding UTF8

Write-Host ''
Write-Host ("运行索引: {0}" -f $indexPath)
$results | Format-Table -AutoSize
Write-Host "（analyzerExit=1 表示该用例存在 FAIL 断言，属如实记录，不中断批量分析）"



