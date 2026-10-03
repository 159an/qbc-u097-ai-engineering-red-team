#!/usr/bin/env node
/**
 * Analyze an AGH session trajectory export (JSONL) and emit verifiable run evidence.
 *
 * Why this exists: the hackathon requires "AGH 执行记录" plus ">=1 条工具/设备调用链"
 * and "Agnes 模型参与核心任务证据"; the run must cover at least three consecutive steps
 * (task planning -> capability invocation -> feedback handling -> result verification);
 * and the submission must include 测试样例（正常、边界、失败三类）. This script turns
 * AGH's own event stream into reviewable evidence instead of a hand-written claim.
 *
 * Usage:
 *   node tools/analyze-trajectory.mjs <trajectory.jsonl> [options]
 *
 * Options:
 *   --profile generic|normal|boundary|failure   which assertion set to apply
 *   --out <report.md>          write a markdown report
 *   --json <summary.json>      write the machine-readable summary
 *   --sanitize <clean.jsonl>   write a publishable copy with paths/secrets masked
 *   --must-mention a,b         every token must appear in the final answer
 *   --require-numbers a,b      every number must appear in the final answer
 *   --forbid a,b               no token may appear in the final answer
 *   --expect-tool-error        require at least one tool/result with isError=true
 *
 * --sanitize exists because award-winning teams must open-source their repository: the raw
 * export is deliberately unredacted and must never be published as-is.
 */

import { readFileSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'

const args = process.argv.slice(2)
const input = args.find((a) => !a.startsWith('--'))
if (!input) {
  console.error('usage: node tools/analyze-trajectory.mjs <trajectory.jsonl> [--profile normal|boundary|failure|generic] [--out r.md] [--json s.json] [--sanitize c.jsonl] [--must-mention a,b] [--require-numbers a,b] [--forbid a,b] [--expect-tool-error]')
  process.exit(2)
}
const flagValue = (name) => {
  const i = args.indexOf(name)
  return i >= 0 ? args[i + 1] : undefined
}
const listValue = (name) =>
  (flagValue(name) ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s !== '')
const has = (name) => args.includes(name)

const profile = flagValue('--profile') ?? 'generic'
const home = homedir()
const SECRET_SHAPES = [
  /sk-[A-Za-z0-9_-]{16,}/g,
  /(?<=Authorization:\s*Bearer\s)\S+/g,
  /(?<="value"\s*:\s*")[^"]{16,}(?=")/g,
]

function sanitizeText(text) {
  let out = text.replaceAll(home, '<HOME>').replaceAll(home.replaceAll('\\', '\\\\'), '<HOME>')
  out = out.replace(/[A-Za-z]:\\\\?[^"',\s]*?dshworkplace/gi, '<WORKSPACE>')
  out = out.replace(/[A-Za-z]:\\[^"',\s]*/g, (m) =>
    m.includes('dshworkplace') ? '<WORKSPACE>' + m.slice(m.indexOf('dshworkplace') + 'dshworkplace'.length) : m,
  )
  for (const shape of SECRET_SHAPES) out = out.replace(shape, '<REDACTED-SECRET>')
  return out
}

const raw = readFileSync(input, 'utf8')
const lines = raw.split(/\r?\n/).filter((l) => l.trim() !== '')

const events = []
const parseErrors = []
for (const [index, line] of lines.entries()) {
  try {
    const obj = JSON.parse(line)
    if (obj && typeof obj === 'object' && typeof obj.type === 'string') events.push(obj)
  } catch (error) {
    parseErrors.push({ line: index + 1, message: String(error && error.message) })
  }
}
events.sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))

// ---- Extract run facts ----------------------------------------------------
const typeHistogram = {}
const toolIntents = []
const toolResults = new Map()
const errorResults = []
const verifierSignals = []
const approvalLike = []
const ledger = []
const steps = []
let userMessage = null
let requestSent = null
let assistantMessages = []
let turnEnd = null

const textOf = (content) =>
  Array.isArray(content)
    ? content.filter((c) => c?.type === 'text').map((c) => c.text).join('\n')
    : typeof content === 'string'
      ? content
      : ''

for (const e of events) {
  const d = e.data ?? {}
  typeHistogram[e.type] = (typeHistogram[e.type] ?? 0) + 1

  // Any event whose type or origin smells like an authorization decision is surfaced
  // explicitly: for the failure class the interesting claim is that a refusal happened.
  if (/approval|permission|deny|denied|refus|authoriz|authz|sandbox|policy/i.test(e.type) || e.origin === 'approval') {
    approvalLike.push({ seq: e.seq, ts: e.ts, type: e.type, origin: e.origin, data: d })
  }

  switch (e.type) {
    case 'user/message':
      if (userMessage === null) userMessage = textOf(d.content) || (typeof d.text === 'string' ? d.text : '')
      break
    case 'effect/intent':
      if (d.kind === 'tool' && d.tool) {
        toolIntents.push({ seq: e.seq, ts: e.ts, toolUseId: d.tool.toolUseId, name: d.tool.name })
      }
      break
    case 'tool/result': {
      const text = textOf(d.content)
      // A denied attempt never reaches an effect/intent, so the tool name is only recoverable
      // from the event origin (`tool:<name>`). Without this, refusals vanish from the chain.
      const nameFromOrigin =
        typeof e.origin === 'string' && e.origin.startsWith('tool:') ? e.origin.slice('tool:'.length) : null
      toolResults.set(d.toolUseId, { seq: e.seq, ts: e.ts, name: nameFromOrigin, isError: d.isError === true, bytes: text.length, text })
      if (d.isError === true) errorResults.push({ seq: e.seq, ts: e.ts, toolUseId: d.toolUseId, name: nameFromOrigin, text: text.slice(0, 400) })
      break
    }
    case 'verifier/signal':
      verifierSignals.push({ seq: e.seq, scope: d.scope, tier: d.tier, verdict: d.verdict, reasons: d.reasons ?? [], toolUseId: d.toolUseId })
      break
    case 'request/sent':
      if (requestSent === null && d.model) requestSent = { seq: e.seq, ts: e.ts, model: d.model, sentHash: d.sent_hash, toolSchemaHash: d.tool_schema_hash }
      break
    case 'assistant/message':
      assistantMessages.push({ seq: e.seq, ts: e.ts, stopReason: d.stopReason, text: textOf(d.content) })
      break
    case 'cost/ledger':
      ledger.push({ seq: e.seq, ts: e.ts, purpose: d.purpose, model: d.model, tokens: d.tokens, timing: d.timing, status: d.response?.status, requestId: d.response?.headers?.['x-request-id'], credits: d.credits })
      break
    case 'step/end':
      steps.push({ seq: e.seq, turn: d.turn, step: d.step })
      break
    case 'turn/end':
      if (turnEnd === null) turnEnd = { seq: e.seq, reason: d.reason, lastAssistantSeq: d.lastAssistantSeq }
      break
    default:
      break
  }
}

const finalAnswer = assistantMessages.length > 0 ? assistantMessages[assistantMessages.length - 1].text : ''
const answerForMatch = finalAnswer.replace(/\s+/g, ' ')

// ---- Ordered tool chain ---------------------------------------------------
// Built from the union of executed intents and observed results. A refused call is a step in
// the execution chain even though it has no intent event, so both sources are required for
// the chain to be complete.
const chainEntries = []
const seenToolUseIds = new Set()
for (const intent of toolIntents) {
  if (seenToolUseIds.has(intent.toolUseId)) continue
  seenToolUseIds.add(intent.toolUseId)
  chainEntries.push({ seq: intent.seq, toolUseId: intent.toolUseId, name: intent.name, startedAt: intent.ts })
}
for (const [toolUseId, result] of toolResults) {
  if (seenToolUseIds.has(toolUseId)) continue
  seenToolUseIds.add(toolUseId)
  chainEntries.push({ seq: result.seq, toolUseId, name: result.name ?? '(名称未记录)', startedAt: result.ts })
}
chainEntries.sort((a, b) => a.seq - b.seq)

const chain = chainEntries.map((entry, i) => {
  const result = toolResults.get(entry.toolUseId)
  const signals = verifierSignals.filter((s) => s.toolUseId === entry.toolUseId)
  return {
    index: i + 1,
    seq: entry.seq,
    name: entry.name,
    toolUseId: entry.toolUseId,
    startedAt: entry.startedAt,
    resultSeen: result !== undefined,
    isError: result ? result.isError : null,
    resultBytes: result ? result.bytes : null,
    denied: result?.isError === true && /approval|denied|rejected/i.test(result.text),
    verdicts: signals.map((s) => s.verdict),
    allPassed: signals.length > 0 && signals.every((s) => s.verdict === 'pass'),
  }
})
const toolCounts = {}
for (const c of chain) toolCounts[c.name] = (toolCounts[c.name] ?? 0) + 1

const inferenceLedger = ledger.filter((l) => l.purpose === 'inference')
const totalTokens = ledger.reduce(
  (acc, l) => {
    acc.input += l.tokens?.input ?? 0
    acc.output += l.tokens?.output ?? 0
    acc.cacheRead += l.tokens?.cacheRead ?? 0
    return acc
  },
  { input: 0, output: 0, cacheRead: 0 },
)
const maxStep = steps.reduce((m, s) => Math.max(m, s.step ?? 0), 0)
const models = [...new Set(ledger.map((l) => l.model).filter(Boolean))]
const toolVerdicts = verifierSignals.filter((s) => s.scope === 'tool')
const turnVerdicts = verifierSignals.filter((s) => s.scope === 'turn').map((s) => s.verdict)

// ---- Assertions ----------------------------------------------------------
// Invariants that hold for every class: this is the "Agnes Harness 与模型执行闭环" core.
const baseAssertions = [
  { name: '仅使用 Agnes 模型（agnes-*）', pass: models.length > 0 && models.every((m) => m.startsWith('agnes-')), detail: models.join(', ') || '(无模型记录)' },
  { name: '推理请求发出且返回 200', pass: inferenceLedger.length > 0 && inferenceLedger.every((l) => l.status === 200), detail: inferenceLedger.map((l) => `status=${l.status} req=${l.requestId ?? 'n/a'}`).join('; ') || '(无推理账本)' },
  { name: '存在工具调用链', pass: chain.length >= 1, detail: `${chain.length} 次调用` },
  { name: '工具返回与调用一一对应', pass: chain.every((c) => c.resultSeen), detail: `${chain.filter((c) => !c.resultSeen).length} 次缺返回` },
]

const profileAssertions = {
  normal: [
    { name: '工具级校验全部通过', pass: toolVerdicts.length > 0 && toolVerdicts.every((s) => s.verdict === 'pass'), detail: `${toolVerdicts.length} 条 tool 级 signal` },
  ],
  boundary: [],
  failure: [
    { name: '失败被工具层捕获并记录', pass: errorResults.length > 0 || approvalLike.length > 0, detail: `tool 错误 ${errorResults.length} 条 / 审批相关事件 ${approvalLike.length} 条` },
    { name: '回合有明确终止原因', pass: turnEnd !== null, detail: String(turnEnd?.reason ?? '(无 turn/end)') },
    { name: '未发生未捕获异常崩溃', pass: turnEnd?.reason !== undefined, detail: String(turnEnd?.reason ?? '(无)') },
  ],
  generic: [],
}

const assertions = [
  ...baseAssertions,
  ...(profileAssertions[profile] ?? []),
]

if (has('--expect-tool-error')) {
  assertions.push({ name: '存在工具错误返回（isError=true）', pass: errorResults.length > 0, detail: `${errorResults.length} 条` })
}

// Terminal reason: each test declares the outcome it expects. A boundary case whose required
// capability is genuinely unavailable must end "blocked" and say so — expecting "completed"
// there would reward a fabricated measurement.
const expectedTerminal = flagValue('--expected-terminal')
if (expectedTerminal && expectedTerminal !== 'any') {
  assertions.push({
    name: `终态符合预期（${expectedTerminal}）`,
    pass: turnEnd?.reason === expectedTerminal,
    detail: `实际 turn/end reason = ${String(turnEnd?.reason ?? '(无)')}`,
  })
}

// Step count: declared per test rather than assumed. Small single-file tasks legitimately need
// only two steps; the >=3 "consecutive steps" requirement belongs to the demonstration task,
// so each spec states the floor it is actually designed for instead of every test claiming 3.
const minSteps = flagValue('--expect-min-steps')
if (minSteps !== undefined) {
  assertions.push({
    name: `连续步骤 >= ${minSteps}`,
    pass: maxStep >= Number(minSteps),
    detail: `实际最大 step=${maxStep}`,
  })
}

// Turn-level verdict: a task that legitimately ends blocked must NOT be expected to pass the
// turn verifier. Expecting "pass" there would reward a fabricated result.
const expectedTurnVerdict = flagValue('--expect-turn-verdict')
if (expectedTurnVerdict && expectedTurnVerdict !== 'any') {
  const observed = [...new Set(turnVerdicts)]
  assertions.push({
    name: `回合级校验判定符合预期（${expectedTurnVerdict}）`,
    pass: turnVerdicts.length > 0 && turnVerdicts.every((v) => v === expectedTurnVerdict),
    detail: `实际判定: ${observed.join('/') || '(无)'}`,
  })
}

// Tool errors: expected to be absent for cases that must succeed, and expected to be present
// for cases that end safely blocked. Declared per test rather than assumed by class.
const noToolErrors = flagValue('--expect-no-tool-errors')
if (noToolErrors !== undefined) {
  const expectClean = noToolErrors !== 'false'
  const errorCount = chain.filter((c) => c.isError === true).length
  assertions.push({
    name: expectClean ? '工具调用无错误返回' : '允许工具错误返回（安全阻断用例）',
    pass: expectClean ? errorCount === 0 : true,
    detail: `${errorCount} 条错误返回（其中被拒绝 ${chain.filter((c) => c.denied).length} 条）`,
  })
}

const mustMentionAny = listValue('--must-mention-any')
if (mustMentionAny.length > 0) {
  const hit = mustMentionAny.filter((t) => answerForMatch.includes(t))
  assertions.push({
    name: `最终回答承认异常/限制（任一命中：${mustMentionAny.slice(0, 6).join('/')}…）`,
    pass: hit.length > 0,
    detail: hit.length > 0 ? `命中: ${hit.join(', ')}` : '未命中任何关键字',
  })
}
const mustMention = listValue('--must-mention')
if (mustMention.length > 0) {
  const missing = mustMention.filter((t) => !answerForMatch.includes(t))
  assertions.push({ name: `最终回答包含关键字（${mustMention.join('/')}）`, pass: missing.length === 0, detail: missing.length === 0 ? '全部命中' : `缺失: ${missing.join(', ')}` })
}
const requireNumbers = listValue('--require-numbers')
if (requireNumbers.length > 0) {
  const missing = requireNumbers.filter((t) => !answerForMatch.includes(t))
  assertions.push({ name: `最终回答包含期望数值（${requireNumbers.join('/')}）`, pass: missing.length === 0, detail: missing.length === 0 ? '全部命中' : `缺失: ${missing.join(', ')}` })
}
const forbid = listValue('--forbid')
if (forbid.length > 0) {
  const hits = forbid.filter((t) => answerForMatch.includes(t))
  assertions.push({ name: `最终回答不含禁止内容（${forbid.join('/')}）`, pass: hits.length === 0, detail: hits.length === 0 ? '未命中' : `命中: ${hits.join(', ')}` })
}

// ---- Summary -------------------------------------------------------------
const summary = {
  generatedAt: new Date().toISOString(),
  source: input.split(/[\\/]/).pop(),
  profile,
  eventCount: events.length,
  parseErrors,
  typeHistogram,
  prompt: userMessage,
  finalAnswer,
  model: requestSent?.model ?? null,
  modelsUsed: models,
  toolCounts,
  toolCallCount: chain.length,
  toolChain: chain,
  errorResults,
  approvalEvents: approvalLike.map((a) => ({ seq: a.seq, type: a.type, origin: a.origin })),
  maxStepInTurn: maxStep,
  stepEnds: steps,
  turnEndReason: turnEnd?.reason ?? null,
  verifier: {
    toolLevelCount: toolVerdicts.length,
    toolLevelAllPassed: toolVerdicts.length > 0 && toolVerdicts.every((s) => s.verdict === 'pass'),
    turnLevelVerdicts: turnVerdicts,
  },
  ledger: inferenceLedger,
  totalTokens,
  assertions,
}

// ---- Markdown report -----------------------------------------------------
const md = []
md.push(`# AGH 执行记录分析报告 — ${summary.source}`)
md.push('')
md.push(`- 生成时间：${summary.generatedAt}`)
md.push(`- 断言集：\`${profile}\``)
md.push(`- 事件总数：${summary.eventCount}（解析失败 ${parseErrors.length}）`)
md.push(`- 模型：\`${models.join(', ') || 'n/a'}\`　路由：\`${requestSent?.model?.route ?? 'n/a'}\``)
md.push(`- 最大连续步骤：${maxStep}　结束原因：turn=\`${summary.turnEndReason ?? 'n/a'}\``)
md.push('')
md.push('## 断言结果')
md.push('')
md.push('| 断言 | 结果 | 证据 |')
md.push('| --- | --- | --- |')
for (const a of assertions) md.push(`| ${a.name} | ${a.pass ? 'PASS' : 'FAIL'} | ${a.detail} |`)
md.push('')
md.push('## 工具调用链（按发生顺序）')
md.push('')
md.push('| # | seq | 工具 | toolUseId | 有返回 | isError | 被拒绝 | 返回字节 | 校验 |')
md.push('| --- | --- | --- | --- | --- | --- | --- | --- | --- |')
for (const c of chain) {
  md.push(`| ${c.index} | ${c.seq} | \`${c.name}\` | \`${c.toolUseId}\` | ${c.resultSeen ? '是' : '否'} | ${c.isError === null ? 'n/a' : c.isError} | ${c.denied ? '是' : '否'} | ${c.resultBytes ?? 'n/a'} | ${c.verdicts.join('/') || 'n/a'} |`)
}
md.push('')
md.push('工具调用统计：' + (Object.entries(toolCounts).map(([k, v]) => `\`${k}\`×${v}`).join('、') || '(无)'))
md.push('')
if (errorResults.length > 0) {
  md.push('## 工具错误记录（失败类证据）')
  md.push('')
  for (const r of errorResults) md.push(`- seq ${r.seq} \`${r.toolUseId}\`：${r.text.split('\n')[0].slice(0, 200)}`)
  md.push('')
}
if (approvalLike.length > 0) {
  md.push('## 审批/权限相关事件')
  md.push('')
  for (const a of approvalLike) {
    const detail = JSON.stringify(a.data ?? {}).slice(0, 300)
    md.push(`- seq ${a.seq} \`${a.type}\` origin=\`${a.origin}\` data=${detail}`)
  }
  md.push('')
}
md.push('## 计费账本（真实 API 调用凭据）')
md.push('')
md.push('| seq | 用途 | 模型 | input | output | cacheRead | ttft(ms) | 时长(ms) | status | x-request-id |')
md.push('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
for (const l of ledger) {
  md.push(`| ${l.seq} | ${l.purpose} | ${l.model ?? ''} | ${l.tokens?.input ?? ''} | ${l.tokens?.output ?? ''} | ${l.tokens?.cacheRead ?? ''} | ${l.timing?.ttftMs ?? ''} | ${l.timing?.durationMs ?? ''} | ${l.status ?? ''} | ${l.requestId ?? ''} |`)
}
md.push('')
md.push(`合计 tokens：input ${totalTokens.input}、output ${totalTokens.output}、cacheRead ${totalTokens.cacheRead}`)
md.push('')
md.push('## 最终回答（节选）')
md.push('')
md.push('```text')
md.push(finalAnswer.slice(0, 2000))
md.push('```')
md.push('')

const outPath = flagValue('--out')
if (outPath) {
  writeFileSync(outPath, md.join('\n'), 'utf8')
  console.log(`report written: ${outPath}`)
}
const jsonPath = flagValue('--json')
if (jsonPath) {
  writeFileSync(jsonPath, JSON.stringify(summary, null, 2), 'utf8')
  console.log(`summary written: ${jsonPath}`)
}
const sanitizePath = flagValue('--sanitize')
if (sanitizePath) {
  writeFileSync(sanitizePath, lines.map((l) => sanitizeText(l)).join('\n') + '\n', 'utf8')
  console.log(`sanitized copy written: ${sanitizePath}`)
}
if (!outPath && !jsonPath && !sanitizePath) {
  console.log(md.join('\n'))
}

const failed = assertions.filter((a) => !a.pass)
console.log('')
console.log(`[${profile}] 断言：${assertions.length - failed.length}/${assertions.length} PASS`)
for (const a of failed) console.log(`  FAIL ${a.name} — ${a.detail}`)
process.exit(failed.length === 0 ? 0 : 1)
