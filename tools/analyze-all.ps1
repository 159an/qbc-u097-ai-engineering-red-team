# 对已采集的轨迹批量执行断言分析（不重新调用模型，只读已有证据）
#
# 与 run-conformance.ps1 分开，是为了让「重新判定」与「重新采集」解耦：
# 期望值或断言集变化时，不必再花一次模型调用就能复核同一批原始证据。
#
# 用法：pwsh -File tools\analyze-all.ps1

$ErrorActionPreference = 'Continue'

$root  = Split-Path -Parent $PSScriptRoot
$evDir = Join-Path $root 'evidence\conformance'
$spec  = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'conformance-tests.json') -Raw -Encoding UTF8 | ConvertFrom-Json

$rows = @()
foreach ($t in $spec.tests) {
    $traj = Join-Path $evDir ($t.id + '.trajectory.raw.json')
    if (-not (Test-Path -LiteralPath $traj)) {
        Write-Warning ("[{0}] 缺轨迹文件，跳过：{1}" -f $t.id, $traj)
        continue
    }

    $argv = @(
        (Join-Path $PSScriptRoot 'analyze-trajectory.mjs'),
        $traj,
        '--profile', $t.profile,
        '--out',  (Join-Path $evDir ($t.id + '.report.md')),
        '--json', (Join-Path $evDir ($t.id + '.summary.json')),
        '--sanitize', (Join-Path $evDir ($t.id + '.trajectory.sanitized.jsonl'))
    )
    if ($t.expectedTerminal) { $argv += @('--expected-terminal', $t.expectedTerminal) }
    if ($t.expectMinSteps)   { $argv += @('--expect-min-steps', $t.expectMinSteps) }
    if ($t.expectTurnVerdict) { $argv += @('--expect-turn-verdict', $t.expectTurnVerdict) }
    if ($t.expectToolError)  { $argv += '--expect-tool-error' }
    if ($t.PSObject.Properties.Name -contains 'expectNoToolErrors' -and $null -ne $t.expectNoToolErrors) {
        $argv += @('--expect-no-tool-errors', $t.expectNoToolErrors.ToString().ToLower())
    }
    if ($t.mustMentionAny -and $t.mustMentionAny.Count -gt 0) { $argv += @('--must-mention-any', ($t.mustMentionAny -join ',')) }
    if ($t.require -and $t.require.Count -gt 0)               { $argv += @('--require-numbers', ($t.require -join ',')) }

    Write-Host ""
    Write-Host ("=== 分析 {0} ({1}) ===" -f $t.id, $t.class)
    & node @argv
    $rows += [pscustomobject]@{ id = $t.id; class = $t.class; analyzerExit = $LASTEXITCODE }
}

Write-Host ""
Write-Host "=== 分析汇总 ==="
$rows | Format-Table -AutoSize
Write-Host "（analyzerExit=1 表示该用例存在 FAIL 断言，属于如实记录，不中断批量分析）"



