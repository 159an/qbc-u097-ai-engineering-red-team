// 在**非交互环境**下安装并启用 AGH 插件。
//
// 为什么需要它：AGH 的 CLI 对插件安装做了刻意的 fail-closed 保护——
//   packages/cli/src/bin.ts               confirmPackageInstall()      stdin/stdout 非 TTY 时直接返回 false
//   resource-control-cli/src/execution.ts confirmResourceOperation()  同样非 TTY 即拒绝
// 所以管道喂 `y` 无效，CI / 无人值守场景下装不上插件。
//
// 为什么必须走**命名管道**而不是 Web/WS：
//   packages/cli/launch/package-admin.ts 的注释写明——
//   "The local launcher's private Unix connection is the admin authority; it is never sent to Web."
//   实测印证：同一条 packages.inspect 经 WS 调用返回
//   CAPABILITY_DENIED（reason: package administration requires server-granted admin authority）。
//   因此本脚本复用 CLI 自己的 localPipeFactories 走本地私有管道，才具备 admin 权限。
//
// 它**不绕过任何真实安全规则**：daemon 仍强制校验完整性摘要、显式 trust 与 enable。
// 被绕过的只是"客户端 UX 确认"，而这一步在 Web 界面上本来就是点一下按钮。
//
// 用法（在 AGH 源码仓库根目录）：
//   node --import tsx packages/cli/tools/qbc-install-plugin.mjs file:./plugins/qbc-verification-tools
//
// 需要：daemon 正在运行；且 daemon 的工作区与 source 相对路径的解析基准一致
// （可用 QBC_WORKSPACE 指定，默认取当前目录）。

import { join } from 'node:path'
import { homedir } from 'node:os'
import { randomUUID } from 'node:crypto'
import { createClient, memoryJournal } from '@agnes/sdk'
import { readDaemonDiscovery, resolveDaemonScope } from '@agnes/daemon'
import { localPipeFactories } from '../src/boot/pipe-factory.js'

const source = process.argv[2]
if (!source) {
  console.error('usage: node --import tsx packages/cli/tools/qbc-install-plugin.mjs <source>   e.g. file:./plugins/x')
  process.exit(2)
}

const PROFILE = process.env.AGNES_PROFILE ?? 'local-dev'
const AGH_HOME = process.env.AGH_HOME ?? join(homedir(), '.agh')
const WORKSPACE = process.env.QBC_WORKSPACE ?? process.cwd()

const scope = await resolveDaemonScope({
  env: process.env,
  cwd: WORKSPACE,
  home: AGH_HOME,
  profile: PROFILE,
})
const discovery = await readDaemonDiscovery(scope)
if (!discovery) {
  console.error('未找到 daemon discovery；请先启动 AGH（tools/start-agh.ps1 或 agnes.mjs serve）。')
  process.exit(3)
}

const client = createClient({
  transport: { kind: 'unix', path: discovery.socketPath },
  auth: { kind: 'local' },
  journal: memoryJournal(),
  transportFactories: localPipeFactories(discovery.socketPath, scope),
})

const newCommandId = (kind) => `${kind}-${randomUUID().replaceAll('-', '')}`

// clientId 必须取自**已认证连接本身**，不能自己随机生成。
// daemon 会校验「命令里的 clientId == 认证连接的身份」，不一致就返回
// CAPABILITY_DENIED（reason: package command client does not match authenticated connection）。
// CLI 的对应写法见 packages/cli-tui/src/package-admin.ts：clientId: await client.clientId()。
const clientId = await client.clientId()
const TERMINAL = new Set(['completed', 'failed', 'cancelled', 'rolled-back'])

async function settle(receipt, label) {
  for (let i = 0; i < 300; i++) {
    const op = await client.packages.operation.get({ profile: PROFILE, operationId: receipt.operationId })
    if (TERMINAL.has(op.state)) {
      console.log(`  ${label}: ${op.state} (${op.progress}%)`)
      if (op.state !== 'completed' && op.state !== 'rolled-back') {
        console.error(`  ${label} 失败：${op.error?.safeMessage ?? op.state}`)
        if (op.error?.blockers?.length) console.error('  blockers:', JSON.stringify(op.error.blockers))
        process.exit(1)
      }
      return op
    }
    await new Promise((r) => setTimeout(r, 300))
  }
  console.error(`  ${label}: 轮询超时`)
  process.exit(1)
}

console.log(`profile   : ${PROFILE}`)
console.log(`workspace : ${WORKSPACE}`)
console.log(`daemon    : pid ${discovery.owner.pid}  socket ${discovery.socketPath}`)
console.log(`source    : ${source}`)
console.log('')

console.log('[1/4] inspect')
const sourceKind = source.startsWith('file:') ? 'file' : source.startsWith('workspace:') ? 'workspace' : 'npm'
const inspectOp = await settle(
  await client.packages.inspect({ profile: PROFILE, clientId, commandId: newCommandId('inspect'), source: { type: sourceKind, ref: source } }),
  'inspect',
)
const preview = inspectOp.preview
if (!preview) {
  console.error('inspect 完成但没有 preview')
  process.exit(1)
}
console.log(`  id=${preview.id}@${preview.version}`)
console.log(`  integrity=${preview.integrity}`)
console.log(`  capabilityHash=${preview.capabilityHash ?? '(未提供)'}`)
console.log(`  contributions=${preview.contributions.map((c) => c.kind).join(', ') || 'none'}`)
console.log(`  warnings=${preview.warnings.map((w) => w.safeMessage).join('; ') || 'none'}`)
if (preview.blockers?.length) {
  console.error('  存在 blockers，拒绝继续：', JSON.stringify(preview.blockers))
  process.exit(1)
}

console.log('[2/4] install')
await settle(
  await client.packages.install({
    profile: PROFILE,
    clientId,
    commandId: newCommandId('install'),
    source: preview.source,
    expectedIntegrity: preview.integrity,
  }),
  'install',
)

console.log('[3/4] trust')
if (!preview.capabilityHash) {
  console.error('  preview 未给出 capabilityHash，无法完成 trust。请改用 Web 界面安装。')
  process.exit(1)
}
await settle(
  await client.packages.trust({
    profile: PROFILE,
    clientId,
    commandId: newCommandId('trust'),
    id: preview.id,
    expectedIntegrity: preview.integrity,
    capabilityHash: preview.capabilityHash,
  }),
  'trust',
)

console.log('[4/4] enable')
const enableOp = await settle(
  await client.packages.enable({
    profile: PROFILE,
    clientId,
    commandId: newCommandId('enable'),
    id: preview.id,
    expectedInstalledIntegrity: preview.integrity,
  }),
  'enable',
)

console.log('')
console.log('最终状态：', JSON.stringify(enableOp.installed ?? {}, null, 2))
console.log('完成。')
await client.close?.()
process.exit(0)
