# 启动 AGH 运行底座（可复现运行说明的一部分）
#
# 用法：
#   pwsh -File tools\start-agh.ps1 -Check      # 只体检：打印配置并做一次真实推理探测
#   pwsh -File tools\start-agh.ps1             # 启动 Web 工作台
#   pwsh -File tools\start-agh.ps1 -Workspace D:\your\project
#
# 凭据策略：优先使用 AGH credential store 里已保存的凭据（正常路径，不依赖环境变量）。
# 仅当传 -WithEnvKey 时，才从本地密钥文件注入环境变量作为回落，用于凭据丢失后的应急。

param(
    [string]$Profile   = 'local-dev',
    [string]$Workspace = 'D:\dshworkplace\agh',
    [int]$Port         = 4177,
    [switch]$Check,
    [switch]$WithEnvKey
)

$ErrorActionPreference = 'Continue'

$entry   = 'D:\dshworkplace\agh-build\runtime\agnes.mjs'
$keyFile = 'D:\dshworkplace\secrets\agnes.key'

if (-not (Test-Path -LiteralPath $entry)) {
    throw "找不到 AGH 构建产物: $entry。请先执行构建：corepack pnpm --filter @agnes/cli build:local --output-dir D:\dshworkplace\agh-build\runtime"
}

$env:AGNES_PROFILE = $Profile

# 环境变量只作应急回落：credential store 命中时它不会被读取。
if ($WithEnvKey -and -not $env:AGNES_SECRET_AGNES_AI_DEFAULT) {
    if (Test-Path -LiteralPath $keyFile) {
        $env:AGNES_SECRET_AGNES_AI_DEFAULT = (Get-Content -LiteralPath $keyFile -Raw).Trim()
        Write-Host "[凭据] 已从本地密钥文件注入环境变量回落（正常路径应为 credential store）"
    } else {
        Write-Warning "[凭据] 指定了 -WithEnvKey 但找不到 $keyFile"
    }
}

if ($Check) {
    Write-Host "entry     : $entry"
    Write-Host "profile   : $env:AGNES_PROFILE"
    Write-Host "workspace : $Workspace"
    Write-Host "port      : $Port"
    Write-Host "[1/2] 平台探测"
    & node $entry doctor platform --json
    Write-Host "[2/2] 真实推理探测（会调用 Agnes 模型，产生少量计费）"
    & node $entry doctor provider --probe --json
    exit $LASTEXITCODE
}

Write-Host "启动 AGH Web 工作台：http://127.0.0.1:$Port/"
Write-Host "（保持此终端开启；关闭终端即停止服务）"
& node $entry serve --profile $Profile --cwd $Workspace

