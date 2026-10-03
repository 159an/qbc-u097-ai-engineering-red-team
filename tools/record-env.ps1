# 环境与版本记录（赛事要求：保留时间与版本记录）
#
# 用途：为「必须使用 AGH、模型仅限 Agnes」技术承诺提供可核查的时间与版本证据。
# 涉及的值只包含版本号、提交哈希、文件摘要；不读取、不写入任何凭据。
#
# 用法：pwsh -File tools\record-env.ps1
# 路径：不写死本机绝对路径，按 tools\agh-env.ps1 的优先级解析；
#      可用 AGH_ENTRY / AGH_REPO 环境变量显式指定（见 REPRODUCE.md）。

$ErrorActionPreference = 'Continue'

. "$PSScriptRoot\agh-env.ps1"
$Agh         = Get-AghPaths -RepoRoot (Split-Path -Parent $PSScriptRoot)
$ProjectRoot = $Agh.RepoRoot
$EvidenceDir = Join-Path $ProjectRoot 'evidence'
$AghRepo     = $Agh.Repo
$AghEntry    = $Agh.Entry

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$iso   = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')

# --- AGH 源码版本 ---
# $AghRepo / $AghEntry 可能为 $null（AGH 未按约定位置存放时），
# 因此每处都必须先判空，否则 Join-Path / Test-Path 会直接报错。
$aghCommit = $null; $aghCommitDate = $null; $aghSubject = $null; $aghBranch = $null; $aghDirty = $null
if ($AghRepo -and (Test-Path -LiteralPath (Join-Path $AghRepo '.git'))) {
    $aghCommit     = (git -C $AghRepo rev-parse HEAD 2>$null)
    $aghCommitDate = (git -C $AghRepo log -1 --format=%cI 2>$null)
    $aghSubject    = (git -C $AghRepo log -1 --format=%s 2>$null)
    $aghBranch     = (git -C $AghRepo rev-parse --abbrev-ref HEAD 2>$null)
    $aghDirty      = @(git -C $AghRepo status --porcelain 2>$null).Count
}

# --- 工具链版本 ---
$nodeVersion = (& node --version 2>$null)
# corepack 只在仓库目录内才解析 packageManager 锁定版本；必须切到 AGH 仓库再取，
# 否则记录到的是全局 pnpm 版本，与实际用于构建的版本不符。
$pnpmPinned = $null
if ($AghRepo -and (Test-Path -LiteralPath $AghRepo)) {
    Push-Location -LiteralPath $AghRepo
    try { $pnpmPinned = (& corepack pnpm --version 2>$null) } finally { Pop-Location }
}
$pnpmGlobal = (& pnpm --version 2>$null)
$psVersion = $PSVersionTable.PSVersion.ToString()

# --- 构建产物摘要 ---
$entrySha = $null; $entryBytes = $null
if ($AghEntry -and (Test-Path -LiteralPath $AghEntry)) {
    $entrySha   = (Get-FileHash -Algorithm SHA256 -LiteralPath $AghEntry).Hash
    $entryBytes = (Get-Item -LiteralPath $AghEntry).Length
}

# --- 模型提供方配置（只记录 provider 身份与 Base URL，不含密钥）---
$agnesBaseUrl = 'https://api.agnes-ai.cn/v1'
$providerId   = 'agnes-ai'
$credentialRef = 'secret://agnes-ai/default'
$envKeyName   = 'AGNES_SECRET_AGNES_AI_DEFAULT'
$envKeySet    = [bool]$env:AGNES_SECRET_AGNES_AI_DEFAULT

$record = [ordered]@{
    recordedAt          = $iso
    agh = [ordered]@{
        repository      = 'https://github.com/AgnesAI-Labs/agnes-harness'
        localPath       = $AghRepo
        branch          = $aghBranch
        commit          = $aghCommit
        commitDate      = $aghCommitDate
        commitSubject   = $aghSubject
        uncommittedFiles = $aghDirty
    }
    toolchain = [ordered]@{
        node            = $nodeVersion
        pnpmPinned      = $pnpmPinned
        pnpmGlobal      = $pnpmGlobal
        powerShell      = $psVersion
        nodeHeaders     = $env:AGNES_NODE_HEADERS
    }
    build = [ordered]@{
        entry           = $AghEntry
        entrySha256     = $entrySha
        entryBytes      = $entryBytes
    }
    model = [ordered]@{
        providerId      = $providerId
        baseUrl         = $agnesBaseUrl
        credentialRef   = $credentialRef
        credentialSource = 'credential-store（环境变量仅为回落）'
        envVarName      = $envKeyName
        credentialValueRecorded = $false
        envVarPresentInThisRecordRun = $envKeySet
    }
}

$jsonPath = Join-Path $EvidenceDir "env-record-$stamp.json"
$record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $jsonPath -Encoding utf8

# --- 追加式人类可读日志 ---
$logPath = Join-Path $EvidenceDir 'VERSION-LOG.md'
if (-not (Test-Path $logPath)) {
    @(
        '# AGH 运行环境版本与时间记录'
        ''
        '由 `tools/record-env.ps1` 自动追加。仅记录版本、提交哈希与文件摘要，不含任何凭据。'
        ''
        '| 记录时间 | AGH commit | commit 日期 | Node | pnpm(锁定) | PowerShell | agnes.mjs SHA256(前16) | 未提交变更 |'
        '| --- | --- | --- | --- | --- | --- | --- | --- |'
    ) | Set-Content -LiteralPath $logPath -Encoding utf8
}
$sha16 = if ($entrySha) { $entrySha.Substring(0,16) } else { '(未构建)' }
$shortCommit = if ($aghCommit) { $aghCommit.Substring(0,12) } else { '(无)' }
Add-Content -LiteralPath $logPath -Encoding utf8 -Value "| $iso | ``$shortCommit`` | $aghCommitDate | $nodeVersion | $pnpmPinned | $psVersion | ``$sha16`` | $aghDirty |"

Write-Host "已写入: $jsonPath"
Write-Host "已追加: $logPath"
Write-Host "AGH commit : $aghCommit ($aghCommitDate)"
Write-Host "agnes.mjs  : $entrySha"




