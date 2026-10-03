#!/usr/bin/env node
/**
 * 用轨迹里的**实际工具返回**检验智能体报告中的一项断言。
 *
 * 背景（真实发生的事）：在 P3（稳态对流振荡阈值）任务中，智能体正确完成了二分、
 * 正确推导了中心差分的 Pe≤2 条件、正确做了网格加密对照，但在报告里写下一句：
 *
 *   「numerics.peclet 字段在低速度区存在明显的数据不稳定/随机化
 *     （v=0.5 返回 0.0001、v=100 返回 0.6 等，均与定义 v·dx/α 不符）」
 *
 * 这是**它自己捏造的服务缺陷**：轨迹显示 41 条 solver_solve 返回全部自洽，
 * 是它在汇总表里把 peclet 值与速度配错了行。
 *
 * 本脚本不靠"我们相信服务没问题"来反驳，而是只用**它自己收到的数据**检验一条它无权
 * 违反的不变量：
 *
 *     稳态中心差分离散下，overshoot > 0  ⟺  peclet > 2
 *
 * 若该不变量在全部返回上成立，则字段在它覆盖的整个量程上是自洽的，
 * 「数据不稳定/随机化」的断言就被它自己收到的数据否证。
 *
 * 之所以把这条检查写成代码而不是写在报告里：这正是本作品的核心主张——
 * **模型的叙述不是事实来源，轨迹才是**。所以"模型说错了"这件事也必须由代码证明。
 *
 * 用法：node tools/verify-agent-claims.mjs <trajectory.json> [--out report.md]
 */

import { readFileSync, writeFileSync } from 'node:fs'

const args = process.argv.slice(2)
const input = args.find((a) => !a.startsWith('--'))
if (!input) {
  console.error('usage: node tools/verify-agent-claims.mjs <trajectory.json> [--out report.md]')
  process.exit(2)
}
const outIndex = args.indexOf('--out')
const outPath = outIndex >= 0 ? args[outIndex + 1] : undefined

const lines = readFileSync(input, 'utf8').split(/\r?\n/).filter((l) => l.trim() !== '')

const rows = []
let finalAnswer = ''
for (const line of lines) {
  let o
  try { o = JSON.parse(line) } catch { continue }
  if (o.type === 'tool/result') {
    const text = (o.data?.content ?? []).filter((c) => c?.type === 'text').map((c) => c.text).join('')
    let j
    try { j = JSON.parse(text) } catch { continue }
    if (j?.ok === true && j.numerics?.steady === true && typeof j.numerics.peclet === 'number') {
      rows.push({
        seq: o.seq,
        peclet: j.numerics.peclet,
        overshoot: j.summary?.overshoot ?? null,
        maxU: j.summary?.maxU ?? null,
      })
    }
  }
  if (o.type === 'assistant/message') {
    const t = (o.data?.content ?? []).filter((c) => c?.type === 'text').map((c) => c.text).join('')
    if (t) finalAnswer = t
  }
}

if (rows.length === 0) {
  console.error('轨迹里没有找到稳态求解的返回（numerics.steady === true）。')
  process.exit(3)
}

// 不变量：overshoot > 0 当且仅当 peclet > 2
const violations = rows.filter((r) => {
  const oscillating = r.overshoot !== null && r.overshoot > 0
  return oscillating !== r.peclet > 2
})

const pecs = rows.map((r) => r.peclet)
const minPe = Math.min(...pecs)
const maxPe = Math.max(...pecs)

const md = []
md.push('# 智能体断言的机械核验')
md.push('')
md.push(`- 轨迹：\`${input.split(/[\\/]/).pop()}\``)
md.push(`- 核验时间：${new Date().toISOString()}`)
md.push(`- 样本：**${rows.length}** 条稳态求解返回，peclet 覆盖范围 **${minPe} ~ ${maxPe}**`)
md.push('')
md.push('## 被核验的断言')
md.push('')
md.push('智能体在最终报告中写道（原文）：')
md.push('')
md.push('> `numerics.peclet` 字段在低速度区存在明显的数据不稳定/随机化（v=0.5 返回 0.0001、v=100 返回 0.6 等，均与定义 v·dx/α 不符）')
md.push('')
md.push('## 核验方法')
md.push('')
md.push('不依赖"我们相信服务是好的"这类外部主张，只用**智能体自己收到的返回**检验一条它无权违反的不变量：')
md.push('')
md.push('```')
md.push('稳态中心差分离散下：  overshoot > 0  ⟺  peclet > 2')
md.push('```')
md.push('')
md.push('理由：中心差分的稳态对流扩散方程在网格 Péclet 数 > 2 时失去对角占优，解必然越过边界值')
md.push('（overshoot > 0）；≤ 2 时保持单调。这条关系是离散格式的数学性质，与被测系统的实现无关。')
md.push('')
md.push('## 结果')
md.push('')
md.push('| seq | peclet | overshoot | 满足不变量 |')
md.push('| --- | --- | --- | --- |')
for (const r of rows) {
  const oscillating = r.overshoot !== null && r.overshoot > 0
  const ok = oscillating === r.peclet > 2
  md.push(`| ${r.seq} | ${r.peclet} | ${r.overshoot} | ${ok ? '是' : '**否**'} |`)
}
md.push('')
md.push(`**违反不变量的返回数：${violations.length} / ${rows.length}**`)
md.push('')
md.push('## 结论')
md.push('')
if (violations.length === 0) {
  md.push(`在智能体收到的全部 ${rows.length} 条稳态返回上（peclet 覆盖 ${minPe} ~ ${maxPe}），`)
  md.push('`overshoot > 0 ⟺ peclet > 2` 这条不变量**无一违反**。')
  md.push('')
  md.push('因此 `numerics.peclet` 在它实际覆盖的整个量程上都是自洽的，')
  md.push('**它关于「数据不稳定/随机化」的断言被它自己收到的数据否证**。')
  md.push('')
  md.push('（另经直接 HTTP 核验：v=1/10/100/200/201/500 时服务返回的 peclet 与 `v·dx/α` 精确一致，')
  md.push('  见 `docs/成果汇总.md` §5.3。两条独立路径得出同一结论。）')
  md.push('')
  md.push('### 这条核验说明了什么')
  md.push('')
  md.push('智能体的**实验部分全对**：二分锁定 Pe=2、推导出中心差分的系数不等式、网格加密对照也正确。')
  md.push('出错的只是**汇总表格的誊写**，而它随即在这个誊写错误之上构建了一个不存在的缺陷结论。')
  md.push('')
  md.push('这正是本作品的核心主张：**模型的叙述不是事实来源，轨迹才是**。')
  md.push('所以本仓库的证据流水线（`tools/analyze-trajectory.mjs`）从 AGH 原生事件流生成断言，')
  md.push('而不是采信模型的自然语言总结——包括"模型说错了"这件事，也由代码而非人工判断来证明。')
} else {
  md.push(`发现 **${violations.length}** 条违反不变量的返回，说明该字段确实存在不一致，智能体的断言成立：`)
  md.push('')
  for (const v of violations) md.push(`- seq ${v.seq}: peclet=${v.peclet} 但 overshoot=${v.overshoot}`)
}
md.push('')

const report = md.join('\n')
if (outPath) {
  writeFileSync(outPath, report, 'utf8')
  console.log(`report written: ${outPath}`)
} else {
  console.log(report)
}
console.log(`samples=${rows.length} violations=${violations.length} pecletRange=${minPe}..${maxPe}`)
process.exit(0)
