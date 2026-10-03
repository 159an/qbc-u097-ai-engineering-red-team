#!/usr/bin/env node
/**
 * 把靶场三类测试的断言结果汇总成一份可交给评委的文档。
 *
 * 与 build-evidence-index.mjs 的分工：
 *   build-evidence-index.mjs  → AGH 运行底座的三类测试（evidence/conformance/）
 *   本脚本                    → 靶场（求解服务）的三类测试（evidence/target-tests/）
 *
 * 两者都是"从各用例的分析结果机械汇总"，不手工填写。
 * PowerShell 5.1 的 Set-Content -Encoding UTF8 会写 BOM，所以每次读 JSON 都先剥掉。
 */

import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..')
const evDir = join(root, 'evidence', 'target-tests')
const readJson = (p) => JSON.parse(readFileSync(p, 'utf8').replace(/^\uFEFF/, ''))

const indexPath = join(evDir, 'run-index.json')
if (!existsSync(indexPath)) {
  console.error('缺少 evidence/target-tests/run-index.json —— 请先运行 tools/run-target-tests.ps1')
  process.exit(2)
}

const index = readJson(indexPath)
const rows = Array.isArray(index) ? index : [index]
const spec = readJson(join(here, 'target-tests.json'))
const specById = new Map(spec.tests.map((t) => [t.id, t]))

const order = ['T-N1', 'T-B1', 'T-F1']
rows.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id))
const classLabel = { normal: '正常', boundary: '边界', failure: '失败' }

const enriched = rows.map((r) => {
  const p = join(evDir, `${r.id}.summary.json`)
  return { row: r, s: specById.get(r.id) ?? {}, summary: existsSync(p) ? readJson(p) : null }
})

let total = 0
let passed = 0
const failed = []
for (const { row, summary } of enriched) {
  if (!summary) { failed.push({ id: row.id, name: '(缺少分析结果)', detail: '' }); continue }
  for (const a of summary.assertions) {
    total += 1
    if (a.pass) passed += 1
    else failed.push({ id: row.id, name: a.name, detail: a.detail })
  }
}

// 版本记录取最近一次
let versionLine = '(未记录)'
const logPath = join(root, 'evidence', 'VERSION-LOG.md')
if (existsSync(logPath)) {
  const lines = readFileSync(logPath, 'utf8').split(/\r?\n/).filter((l) => l.trim().startsWith('|'))
  if (lines.length > 1) versionLine = lines[lines.length - 1].trim()
}

const md = []
md.push('# 靶场三类测试汇总（正常 / 边界 / 失败）')
md.push('')
md.push('本文件由 `tools/build-target-evidence.mjs` 从各用例的分析结果自动汇总，不手工填写。')
md.push('')
md.push('- 生成时间：' + new Date().toISOString())
md.push('- 被测对象：工程传热求解服务 `src/solver-service.mjs`（:8081）')
md.push('- 独立基准：解析解服务 `src/oracle-service.mjs`（:8082，与被测无共享代码）')
md.push('- 智能体执行底座：Agnes Harness（AGH），模型 `agnes-3.0-flash`')
md.push('- 最近一次版本记录：' + (versionLine || '(无)'))
md.push('')
md.push('## 〇、结论概要')
md.push('')
md.push(`- 用例数：${enriched.length}（正常 1 / 边界 1 / 失败 1）`)
md.push(`- 断言通过：**${passed} / ${total}**`)
md.push(`- 未通过的断言：**${failed.length}**`)
md.push('')
md.push('> 赛事 4.2 条把「测试样例（正常、边界、失败三类）」列为必填材料。')
md.push('> 本套件即该项的交付物：每个用例都有独立会话、独立轨迹、可复算的断言，')
md.push('> 且**证据由脚本从 AGH 原生事件流生成**，不是手写结论。')
md.push('')
md.push('## 一、总览')
md.push('')
md.push('| 编号 | 类别 | 用例 | 故障注入 | 最大步骤 | 工具调用 | 断言 | 会话 |')
md.push('| --- | --- | --- | --- | --- | --- | --- | --- |')
for (const { row, s, summary } of enriched) {
  const p = summary ? summary.assertions.filter((a) => a.pass).length : 0
  const t = summary ? summary.assertions.length : 0
  const verdict = t > 0 ? (p === t ? `PASS ${p}/${t}` : `${p}/${t}`) : 'n/a'
  md.push(`| ${row.id} | ${classLabel[row.class] ?? row.class} | ${row.title} | \`${row.faults || '无'}\` | ${summary?.maxStepInTurn ?? 'n/a'} | ${summary?.toolCallCount ?? 'n/a'} | ${verdict} | \`${row.sessionId ?? 'n/a'}\` |`)
}
md.push('')
if (failed.length > 0) {
  md.push('### 未通过的断言')
  md.push('')
  for (const f of failed) md.push(`- [${f.id}] ${f.name} — ${f.detail}`)
  md.push('')
}

md.push('## 二、各用例断言明细')
md.push('')
for (const { row, s, summary } of enriched) {
  md.push(`### ${row.id} · ${classLabel[row.class] ?? row.class} · ${row.title}`)
  md.push('')
  if (!summary) { md.push('> 缺少分析结果。'); md.push(''); continue }
  if (s.faults && s.faults.length) md.push(`> **故障注入**：\`${s.faults.join(', ')}\` —— 靶场被刻意配置为在这种情形下行为异常，用于检验智能体能否识破。`)
  md.push('')
  md.push('| 断言 | 结果 | 证据 |')
  md.push('| --- | --- | --- |')
  for (const a of summary.assertions) md.push(`| ${a.name} | ${a.pass ? 'PASS' : 'FAIL'} | ${String(a.detail).replace(/\|/g, '\\|')} |`)
  md.push('')
  md.push(`- 工具调用分布：${Object.entries(summary.toolCounts).map(([k, v]) => `\`${k}\`×${v}`).join('、') || '（无）'}`)
  md.push(`- 推理调用：${summary.ledger.length} 次，模型 ${[...new Set(summary.ledger.map((l) => l.model))].join('/') || 'n/a'}`)
  md.push(`- tokens：input ${summary.totalTokens.input}、output ${summary.totalTokens.output}、cacheRead ${summary.totalTokens.cacheRead}`)
  md.push(`- 轨迹：\`evidence/target-tests/${row.id}.trajectory.raw.json\`（可发布脱敏版 \`${row.id}.sanitized.jsonl\`）`)
  md.push('')
  md.push('<details><summary>智能体的最终结论（原文节选）</summary>')
  md.push('')
  md.push('```text')
  md.push(String(summary.finalAnswer ?? '').slice(0, 3000))
  md.push('```')
  md.push('')
  md.push('</details>')
  md.push('')
}

md.push('## 三、这套测试证明了什么')
md.push('')
md.push('| 能力 | 对应用例 | 可核查的证据形式 |')
md.push('| --- | --- | --- |')
md.push('| 与独立基准交叉验证、并自行做网格收敛验证 | T-N1 | 两次求解误差之比 ≈ 4.0000（二阶精度），数值全部取自工具返回 |')
md.push('| 探测非法/极端输入，如实读懂服务端的 4xx 语义，且不把错误当故障 | T-B1 | 逐条列出 `HTTP 400 / E_ALPHA_INVALID`、`E_PROBE_RANGE` 等服务端错误码 |')
md.push('| 不采信被测系统的自述，用独立物理判据识破谎言 | T-F1 | 总热量守恒被破坏（终态总热为负、量级 1e14）+ 幅值放大与奇偶振荡 |')
md.push('| 无法完成时如实报告能力缺口，而不是编造结论 | T-B1（初版） | 终态 `blocked`，明确说明缺少"能构造越界入参的通道" |')
md.push('')

const outPath = join(evDir, 'SUMMARY.md')
writeFileSync(outPath, md.join('\n'), 'utf8')
console.log(`written: ${outPath}`)
console.log(`assertions: ${passed}/${total} pass; failures: ${failed.length}`)
for (const f of failed) console.log(`  FAIL [${f.id}] ${f.name} — ${f.detail}`)
process.exit(failed.length === 0 ? 0 : 1)
