# 三类一致性测试编排器：正常 / 边界 / 失败
#
# 每个测试使用独立工作区（work\<id>\），因此每个测试产生独立会话与独立轨迹，
# 不会互相污染。基准事实来自 fixtures\ground-truth.json（由 make-fixtures.mjs 计算）。
#
# 用法：
#   pwsh -File tools\run-conformance.ps1            # 跑全部
#   pwsh -File tools\run-conformance.ps1 -Only F1   # 只跑某一个
#   pwsh -File tools\run-conformance.ps1 -SkipAnalyze

param(
    [string]$Only,
    [switch]$SkipAnalyze
)

$ErrorActionPreference = 'Continue'

$root    = Split-Path -Parent $PSScriptRoot
$entry   = 'D:\dshworkplace\agh-build\runtime\agnes.mjs'
$evDir   = Join-Path $root 'evidence\conformance'
$workDir = Join-Path $root 'work'
$fixtures = Join-Path $root 'fixtures'

$env:AGNES_PROFILE = 'local-dev'

if (-not (Test-Path -LiteralPath $entry)) { throw "找不到 AGH 入口: $entry" }
if (-not (Test-Path -LiteralPath $fixtures)) { throw "找不到 fixtures，请先运行 node tools\make-fixtures.mjs" }

New-Item -ItemType Directory -Force -Path $evDir   | Out-Null
New-Item -ItemType Directory -Force -Path $workDir | Out-Null

$spec = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'conformance-tests.json') -Raw -Encoding UTF8 | ConvertFrom-Json

$results = @()
foreach ($t in $spec.tests) {
    if ($Only -and $t.id -ne $Only) { continue }

    $ws = Join-Path $workDir $t.id
    Remove-Item -LiteralPath $ws -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $ws | Out-Null
    Copy-Item -LiteralPath $fixtures -Destination $ws -Recurse -Force

    $resultLog = Join-Path $evDir ($t.id + '.result.jsonl')
    $trajPath  = Join-Path $evDir ($t.id + '.trajectory.raw.json')

    Write-Host ""
    Write-Host ("=== [{0}] {1} ({2}) ===" -f $t.id, $t.title, $t.class)
    Write-Host ("工作区: {0}" -f $ws)

    $started = Get-Date
    & node $entry -p --mode json --cwd $ws $t.prompt *>&1 | Tee-Object -FilePath $resultLog
    $exit = $LASTEXITCODE
    $elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)

    # 会话 id 用正则提取，避免对含中文的结果行做 JSON 解析。
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

    # 文件系统级后置断言：写入类失败测试必须证明产物不存在。
    $forbiddenCreated = $null
    if ($t.PSObject.Properties.Name -contains 'forbiddenArtifactPath' -and $t.forbiddenArtifactPath) {
        $forbiddenFull = Join-Path $ws $t.forbiddenArtifactPath
        $forbiddenCreated = Test-Path -LiteralPath $forbiddenFull
        Write-Host ("禁止产物是否被创建: {0}" -f $forbiddenCreated)
    }

    $results += [pscustomobject]@{
        id            = $t.id
        class         = $t.class
        title         = $t.title
        workspace     = $ws
        sessionId     = $sid
        exitCode      = $exit
        wallSeconds   = $elapsed
        resultLog     = $resultLog
        trajectory    = $trajPath
        forbiddenArtifactCreated = $forbiddenCreated
        ranAt         = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
    }
}

$summaryPath = Join-Path $evDir 'run-index.json'
$results | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
Write-Host ""
Write-Host ("运行索引已写入: {0}" -f $summaryPath)
Write-Host ""
$results | Select-Object id, class, exitCode, wallSeconds, sessionId, forbiddenArtifactCreated | Format-Table -AutoSize


