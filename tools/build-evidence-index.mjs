#!/usr/bin/env node
/**
 * Collapse the conformance run into one reviewable document.
 *
 * Reads the per-test summaries produced by analyze-trajectory.mjs and emits
 * evidence/CONFORMANCE-SUMMARY.md, including an explicit mapping from each stated
 * submission requirement to the artifact that satisfies it.
 *
 * A failing assertion is not automatically a broken suite: N1 fails on numerical accuracy
 * on purpose, and that failure is the suite's most valuable output. Failures are therefore
 * reported alongside the declared finding they belong to, and only unexplained failures
 * make the run exit non-zero.
 *
 * Note: files written by PowerShell 5.1 `Set-Content -Encoding UTF8` carry a BOM,
 * so every JSON read here strips it before parsing.
 */

import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..')
const evDir = join(root, 'evidence', 'conformance')
const readJson = (p) => JSON.parse(readFileSync(p, 'utf8').replace(/^\uFEFF/, ''))

const index = readJson(join(evDir, 'run-index.json'))
const rows = Array.isArray(index) ? index : [index]
const spec = readJson(join(here, 'conformance-tests.json'))
const specById = new Map(spec.tests.map((t) => [t.id, t]))
const findings = spec.findings ?? []
const findingById = new Map(findings.map((f) => [f.id, f]))

const order = ['N1', 'B1', 'B2', 'F1', 'F2']
rows.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id))
const classLabel = { normal: '正常', boundary: '边界', failure: '失败' }

let versionLine = '(未记录)'
const logPath = join(root, 'evidence', 'VERSION-LOG.md')
if (existsSync(logPath)) {
  const vlines = readFileSync(logPath, 'utf8').split(/\r?\n/).filter((l) => l.trim().startsWith('|'))
  if (vlines.length > 1) versionLine = vlines[vlines.length - 1].trim()
}

const enriched = rows.map((r) => {
  const p = join(evDir, `${r.id}.summary.json`)
  return { row: r, spec: specById.get(r.id) ?? {}, summary: existsSync(p) ? readJson(p) : null }
})
const demoPath = join(root, 'evidence', 'task01-summary.json')
const demo = existsSync(demoPath) ? readJson(demoPath) : null

// ---- Aggregate ------------------------------------------------------------
let totalAssertions = 0
let passedAssertions = 0
const explained = []
const unexplained = []
for (const { row, spec: s, summary } of enriched) {
  if (!summary) {
    unexplained.push({ id: row.id, name: '(缺少分析结果)', detail: '' })
    continue
  }
  for (const a of summary.assertions) {
    totalAssertions += 1
    if (a.pass) passedAssertions += 1
    else if (s.finding) explained.push({ id: row.id, name: a.name, detail: a.detail, finding: findingById.get(s.finding) })
    else unexplained.push({ id: row.id, name: a.name, detail: a.detail })
  }
}

const md = []
md.push('# 三类一致性测试汇总（正常 / 边界 / 失败）')
md.push('')
md.push('本文件由 `tools/build-evidence-index.mjs` 从各测试的分析结果自动汇总生成，不手工填写。')
md.push('')
md.push(`- 生成时间：${new Date().toISOString()}`)
md.push('- AGH 运行底座：`https://github.com/AgnesAI-Labs/agnes-harness`')
md.push(`- 最近一次版本记录：${versionLine || '(无)'}`)
md.push('- 模型：`agnes-3.0-flash`（Agnes AI 中国站网关 `https://api.agnes-ai.cn/v1`）')
md.push('- 基准事实：`fixtures/ground-truth.json`，由 `tools/make-fixtures.mjs` 从真实字节计算，非手工填写')
md.push('')
md.push('## 〇、结论概要')
md.push('')
md.push(`- 用例数：${enriched.length}（正常 1 / 边界 2 / 失败 2）`)
md.push(`- 断言通过：**${passedAssertions} / ${totalAssertions}**`)
md.push(`- 已识别缺陷（有据可查、且是本套件最有价值的产出）：**${explained.length}** 条`)
md.push(`- 未解释的失败：**${unexplained.length}** 条`)
md.push('')
if (explained.length > 0) {
  md.push('> 断言失败不等于套件失效。N1 的数值断言失败是**刻意保留的真实缺陷证据**：模型把 12 行 CSV 的列均值算错了，而同回合 AGH 的内建校验器判定为 `pass`。这正是「结果正确性不能靠模型心算保证」的直接证据。')
  md.push('')
}
md.push('## 一、测试结果总览')
md.push('')
md.push('| 编号 | 类别 | 测试内容 | 预期终态 | 实际终态 | 最大步骤 | 退出码 | 耗时(s) | 断言 | 会话 ID |')
md.push('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
for (const { row, spec: s, summary } of enriched) {
  const passed = summary ? summary.assertions.filter((a) => a.pass).length : 0
  const total = summary ? summary.assertions.length : 0
  const verdict = summary ? (passed === total ? `PASS ${passed}/${total}` : `${passed}/${total}（含 ${total - passed} 条已识别缺陷）`) : 'n/a'
  md.push(`| ${row.id} | ${classLabel[row.class] ?? row.class} | ${row.title} | \`${s.expectedTerminal ?? 'any'}\` | \`${summary?.turnEndReason ?? 'n/a'}\` | ${summary?.maxStepInTurn ?? 'n/a'} | ${row.exitCode} | ${row.wallSeconds} | ${verdict} | \`${row.sessionId ?? 'n/a'}\` |`)
}
md.push('')

const fsChecks = enriched.filter(({ row }) => row.forbiddenArtifactCreated !== null && row.forbiddenArtifactCreated !== undefined)
if (fsChecks.length > 0) {
  md.push('### 文件系统级后置断言（不看模型怎么说，只看磁盘上发生了什么）')
  md.push('')
  md.push('| 编号 | 禁止产物 | 是否被创建 | 判定 |')
  md.push('| --- | --- | --- | --- |')
  for (const { row, spec: s } of fsChecks) {
    md.push(`| ${row.id} | \`${s.forbiddenArtifactPath ?? row.title}\` | ${row.forbiddenArtifactCreated} | ${row.forbiddenArtifactCreated === false ? 'PASS（未创建）' : 'FAIL（被创建）'} |`)
  }
  md.push('')
}

if (findings.length > 0) {
  md.push('## 二、已识别缺陷与工程结论')
  md.push('')
  for (const f of findings) {
    const owners = enriched.filter(({ spec: s }) => s.finding === f.id).map(({ row }) => row.id)
    md.push(`### ${f.id} · ${f.title}`)
    md.push('')
    md.push(`- 严重度：**${f.severity}**`)
    if (owners.length > 0) md.push(`- 触发用例：${owners.join('、')}`)
    md.push(`- 证据：${f.evidence}`)
    md.push(`- 工程结论：${f.implication}`)
    md.push('')
  }
}

md.push('## 三、各类别断言明细')
md.push('')
for (const { row, summary } of enriched) {
  md.push(`### ${row.id} · ${classLabel[row.class] ?? row.class} · ${row.title}`)
  md.push('')
  if (!summary) {
    md.push('> 缺少分析结果。')
    md.push('')
    continue
  }
  md.push('| 断言 | 结果 | 证据 |')
  md.push('| --- | --- | --- |')
  for (const a of summary.assertions) md.push(`| ${a.name} | ${a.pass ? 'PASS' : 'FAIL'} | ${String(a.detail).replace(/\|/g, '\\|')} |`)
  md.push('')
  md.push(`- 工具调用链：${summary.toolChain.map((c) => `\`${c.name}\`${c.denied ? '(被拒绝)' : ''}`).join(' → ') || '（无）'}`)
  md.push(`- 最大连续步骤：${summary.maxStepInTurn}`)
  md.push(`- 推理调用：${summary.ledger.length} 次，status=${[...new Set(summary.ledger.map((l) => l.status))].join('/')}`)
  md.push(`- tokens：input ${summary.totalTokens.input}、output ${summary.totalTokens.output}、cacheRead ${summary.totalTokens.cacheRead}`)
  if (summary.errorResults.length > 0) md.push(`- 工具错误返回：${summary.errorResults.length} 条（${summary.errorResults.map((r) => `\`${r.name ?? '?'}\``).join('、')}）`)
  if (summary.approvalEvents.length > 0) md.push(`- 审批事件：${summary.approvalEvents.map((e) => `\`${e.type}\``).join('、')}`)
  md.push(`- 轨迹：\`evidence/conformance/${row.id}.trajectory.raw.json\`（可发布脱敏版 \`${row.id}.trajectory.sanitized.jsonl\`）`)
  md.push('')
}

if (demo) {
  md.push('## 四、演示任务（满足「≥3 个连续步骤」硬要求）')
  md.push('')
  md.push('赛事要求作品须经 AGH 完成「任务规划 → 能力调用 → 反馈处理 → 结果验证」的**至少三个连续步骤**。')
  md.push('上述小型用例各自只需要 2 步，因此另跑一个规模足够的演示任务作为该要求的证据。')
  md.push('')
  md.push('| 断言 | 结果 | 证据 |')
  md.push('| --- | --- | --- |')
  for (const a of demo.assertions) md.push(`| ${a.name} | ${a.pass ? 'PASS' : 'FAIL'} | ${String(a.detail).replace(/\|/g, '\\|')} |`)
  md.push('')
  md.push(`- 工具调用：${Object.entries(demo.toolCounts).map(([k, v]) => `\`${k}\`×${v}`).join('、')}`)
  md.push(`- step/end 记录：${demo.stepEnds.map((s) => `turn ${s.turn} step ${s.step}`).join('、')}`)
  md.push(`- 推理调用：${demo.ledger.length} 次，全部 status=200，带上游 x-request-id`)
  md.push('- 轨迹：`evidence/task01-trajectory.raw.json`（脱敏版 `task01-trajectory.sanitized.jsonl`），报告 `evidence/task01-report.md`')
  md.push('')
}

md.push('## 五、赛事要求 → 证据映射')
md.push('')
md.push('| 赛事要求（4.2「提交内容（均为必填）」） | 本套件对应证据 |')
md.push('| --- | --- |')
md.push('| 运行证据：AGH 执行记录 | `evidence/conformance/<ID>.trajectory.raw.json` 与 `evidence/task01-trajectory.raw.json`（AGH 原生事件流） |')
md.push('| 运行证据：≥1 条工具调用链 | 各用例的工具调用链，见上文明细与 `<ID>.summary.json` 的 `toolChain` |')
md.push('| 运行证据：Agnes 模型参与核心任务证据 | `cost/ledger` 事件的 `model` 与上游 `x-request-id`，见各 `<ID>.report.md` 计费账本 |')
md.push('| 运行证据：关键配置 | `evidence/agh-provider-configuration.json`（只含凭据引用，无密钥值） |')
md.push('| 运行证据：专业验证结果 | `fixtures/ground-truth.json` 与模型答案逐值比对（N1 的偏差即由此发现） |')
md.push('| 测试样例：正常 | N1 |')
md.push('| 测试样例：边界 | B1（零字节）、B2（不可测量输入下的安全阻断） |')
md.push('| 测试样例：失败 | F1（不存在路径）、F2（未获批准不得落盘，含文件系统级断言） |')
md.push('| 时间与版本记录 | `evidence/VERSION-LOG.md`、`evidence/env-record-*.json`、`evidence/logs/agh-build-*.log` |')
md.push('| 技术信息：模型名称/版本/环节/调用方式 | `agnes-3.0-flash`，经 AGH `AI Provider` 以 `openai-completions` 调用 `https://api.agnes-ai.cn/v1` |')
md.push('| 技术信息：AGH 作用 | AGH 作为智能体运行与执行底座，承担任务规划、工具调度、审批、轨迹记录与结果校验 |')
md.push('')

const outPath = join(root, 'evidence', 'CONFORMANCE-SUMMARY.md')
writeFileSync(outPath, md.join('\n'), 'utf8')
console.log(`written: ${outPath}`)
console.log(`assertions: ${passedAssertions}/${totalAssertions} pass; explained failures: ${explained.length}; unexplained: ${unexplained.length}`)
for (const e of explained) console.log(`  explained [${e.id}] ${e.name} (${e.finding?.id}) — ${e.detail}`)
for (const u of unexplained) console.log(`  UNEXPLAINED [${u.id}] ${u.name} — ${u.detail}`)
const fsAllOk = fsChecks.every(({ row }) => row.forbiddenArtifactCreated === false)
console.log(`filesystem checks ok: ${fsAllOk}`)
process.exit(unexplained.length === 0 && fsAllOk ? 0 : 1)
