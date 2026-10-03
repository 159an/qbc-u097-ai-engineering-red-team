# AGH 路径解析器（供 tools/ 下各脚本共用）
#
# 为什么需要它：脚本里写死本机绝对路径（例如 <某人>\agh-build\runtime\agnes.mjs）
# 在别人机器上必然失效，且获奖后要公开代码库，绝对路径也不合适。
#
# 解析优先级（自上而下，取第一个存在的）：
#   AGH_ENTRY 环境变量 → <仓库根>\agh\packages\cli\dist\local\agnes.mjs
#                      → <仓库根的上级>\agh-build\runtime\agnes.mjs
#                      → <仓库根>\agh-build\runtime\agnes.mjs
# AGH_REPO 同理，用于读取 AGH 的 commit 信息。
#
# 用法（-RepoRoot 必须显式传入，不依赖 $script: 作用域——dot-source 时的作用域
# 语义在不同调用方下不一致，会静默失效）：
#   . "$PSScriptRoot\agh-env.ps1"
#   $Agh = Get-AghPaths -RepoRoot (Split-Path -Parent $PSScriptRoot)
#   if (-not $Agh.Entry) { Write-AghMissing $Agh; exit 1 }

function Get-AghPaths {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $repoRoot  = (Resolve-Path -LiteralPath $RepoRoot).Path
    $parentDir = Split-Path -Parent $repoRoot

    # ---- 入口 agnes.mjs ----
    $entryCandidates = @()
    if ($env:AGH_ENTRY) { $entryCandidates += $env:AGH_ENTRY }
    $entryCandidates += (Join-Path $repoRoot  'agh\packages\cli\dist\local\agnes.mjs')
    $entryCandidates += (Join-Path $parentDir 'agh-build\runtime\agnes.mjs')
    $entryCandidates += (Join-Path $repoRoot  'agh-build\runtime\agnes.mjs')

    $entry = $null
    foreach ($candidate in $entryCandidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            $entry = (Resolve-Path -LiteralPath $candidate).Path
            break
        }
    }

    # ---- AGH 源码仓库（用于记录 commit / 版本） ----
    $repoCandidates = @()
    if ($env:AGH_REPO) { $repoCandidates += $env:AGH_REPO }
    $repoCandidates += (Join-Path $repoRoot  'agh')
    $repoCandidates += (Join-Path $parentDir 'agh')

    $repo = $null
    foreach ($candidate in $repoCandidates) {
        if ($candidate -and (Test-Path -LiteralPath (Join-Path $candidate '.git'))) {
            $repo = (Resolve-Path -LiteralPath $candidate).Path
            break
        }
    }

    $buildRoot = $null
    if ($entry) { $buildRoot = Split-Path -Parent $entry }

    [pscustomobject]@{
        RepoRoot        = $repoRoot
        Entry           = $entry
        Repo            = $repo
        BuildRoot       = $buildRoot
        EntryCandidates = $entryCandidates
        RepoCandidates  = $repoCandidates
    }
}

# 统一的报错文案：告诉使用者怎么把底座准备好，而不是只说"找不到"。
function Write-AghMissing {
    param([object]$Agh)
    Write-Host '找不到 AGH 构建产物 agnes.mjs。'
    Write-Host ''
    Write-Host '已尝试以下位置：'
    if ($Agh) { foreach ($c in $Agh.EntryCandidates) { if ($c) { Write-Host "  - $c" } } }
    Write-Host ''
    Write-Host '解决办法（二选一）：'
    Write-Host '  1) 显式指定：$env:AGH_ENTRY = "<你的>\packages\cli\dist\local\agnes.mjs"'
    Write-Host '  2) 按 REPRODUCE.md 第 2 节构建 AGH，并构建到上述任一位置'
}


