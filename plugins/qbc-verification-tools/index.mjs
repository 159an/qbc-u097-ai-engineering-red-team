// QBC 验证工具插件 —— 给 AGH Agent 提供"攻击目标系统"的确定性能力。
//
// 设计要点（这些选择本身就是方案的一部分，答辩时要能讲清楚）：
//
// 1) 为什么要做成插件，而不是让 Agent 跑 shell 命令？
//    实测证据（本仓库 evidence/conformance/F2）：非交互模式下 shell 命令会触发
//    approval/asked -> approval/decided，结果是 "approval rejected"，Agent 拿不到执行结果。
//    后端插件作为受信代码在进程内运行，registerTool 注册的工具按 meta 声明决定是否需要审批。
//
// 2) 为什么声明 requiresApproval:'never' 是负责任的？
//    官方文档警告：改成调用外部系统就必须重新定义效果/审批/重放语义，不能照抄只读工具的声明。
//    所以这里做了三件事：
//      - 如实声明 isOpenWorld:true、isReadOnly:false、replay:'never'（非幂等）
//      - 用代码把能力限制在本地目标系统（ALLOWED_HOSTS），拒绝任意外网目标
//      - 对每次调用做输入校验与上限约束，避免把工具变成压测器
//    也就是说："免审批"是声明，但"能打到哪"由代码兜底，两者必须同时成立。
//
// 3) 为什么工具返回结构化结果？
//    Agent 的判定不能靠模型心算（实测证据 evidence/conformance/FINDING-1：模型把 12 行 CSV
//    的两列均值都算错了，而同回合 AGH 内建校验器仍判 pass）。所以工具必须直接给出可判定的
//    结构化事实（状态码直方图、响应体哈希、耗时），让"是否违反不变量"由代码判定。

import { createHash } from 'node:crypto'

const Kind = Symbol.for('TypeBox.Kind')

// 默认只允许本地目标系统。可用 AGH_QBC_ALLOWED_HOSTS 覆盖（逗号分隔）。
const DEFAULT_ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '::1', '[::1]']
const allowedHosts = (() => {
  const raw = process.env.AGH_QBC_ALLOWED_HOSTS
  const list = raw ? raw.split(',').map((s) => s.trim()).filter(Boolean) : DEFAULT_ALLOWED_HOSTS
  return new Set(list.map((s) => s.toLowerCase()))
})()

const MAX_REQUESTS = 64
const MAX_CONCURRENCY = 16
const MAX_BODY_BYTES = 8192

function fail(text) {
  return { content: [{ type: 'text', text }], structured: { ok: false, error: text }, isError: true }
}

function asInt(value, fallback) {
  return Number.isInteger(value) ? value : fallback
}

/** 并发执行 tasks，最多 limit 个在飞。返回与输入同序的结果数组。 */
async function runLimited(tasks, limit) {
  const results = new Array(tasks.length)
  let next = 0
  const workers = Array.from({ length: Math.min(limit, tasks.length) }, async () => {
    for (;;) {
      const index = next++
      if (index >= tasks.length) return
      results[index] = await tasks[index]()
    }
  })
  await Promise.all(workers)
  return results
}

function sha256Short(text) {
  return createHash('sha256').update(text).digest('hex').slice(0, 16)
}

const parameters = {
  [Kind]: 'Object',
  type: 'object',
  properties: {
    url: { [Kind]: 'String', type: 'string', minLength: 1, maxLength: 2048 },
    requests: { [Kind]: 'Integer', type: 'integer', minimum: 1, maximum: MAX_REQUESTS },
    concurrency: { [Kind]: 'Integer', type: 'integer', minimum: 1, maximum: MAX_CONCURRENCY },
    method: { [Kind]: 'String', type: 'string', enum: ['GET', 'POST'] },
    body: { [Kind]: 'String', type: 'string', maxLength: MAX_BODY_BYTES },
    contentType: { [Kind]: 'String', type: 'string', maxLength: 128 },
    timeoutMs: { [Kind]: 'Integer', type: 'integer', minimum: 100, maximum: 60000 },
  },
  required: ['url', 'requests'],
  additionalProperties: false,
}

const meta = {
  isReadOnly: false,
  isDestructive: false,
  isConcurrencySafe: true,
  isOpenWorld: true,
  replay: 'never',
  costHint: undefined,
  deferLoading: false,
  requiresApproval: 'never',
}

const concurrentProbeTool = {
  name: 'qbc_http_burst',
  description:
    'Send N HTTP requests to a local target system with bounded concurrency, then report a deterministic summary: status-code histogram, per-request durations, distinct response-body hashes, and errors. Use this to test for race conditions, state-machine violations and capacity limits. Only local hosts are permitted.',
  parameters,
  meta,
  async execute(args = {}) {
    const requests = asInt(args.requests, 1)
    const concurrency = asInt(args.concurrency, Math.min(requests, 4))
    const method = args.method === 'POST' ? 'POST' : 'GET'
    const timeoutMs = asInt(args.timeoutMs, 10000)

    if (!Number.isInteger(requests) || requests < 1 || requests > MAX_REQUESTS) {
      return fail(`requests must be an integer within 1..${MAX_REQUESTS}`)
    }
    if (concurrency < 1 || concurrency > MAX_CONCURRENCY) {
      return fail(`concurrency must be an integer within 1..${MAX_CONCURRENCY}`)
    }

    let target
    try {
      target = new URL(String(args.url))
    } catch {
      return fail(`url is not a valid absolute URL: ${String(args.url)}`)
    }
    if (target.protocol !== 'http:' && target.protocol !== 'https:') {
      return fail(`only http/https is supported, got ${target.protocol}`)
    }
    // 能力边界由代码兜底，而不是只靠一句"免审批"的声明。
    if (!allowedHosts.has(target.hostname.toLowerCase())) {
      return fail(
        `host not allowed: ${target.hostname}. Allowed: ${[...allowedHosts].join(', ')}. ` +
          'Set AGH_QBC_ALLOWED_HOSTS to widen this deliberately.',
      )
    }

    const startedAt = Date.now()
    const tasks = Array.from({ length: requests }, (_, index) => async () => {
      const t0 = Date.now()
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), timeoutMs)
      try {
        const response = await fetch(target, {
          method,
          signal: controller.signal,
          ...(method === 'POST' && args.body !== undefined ? { body: String(args.body) } : {}),
          ...(args.contentType ? { headers: { 'content-type': String(args.contentType) } } : {}),
        })
        const text = await response.text()
        return {
          index,
          status: response.status,
          durationMs: Date.now() - t0,
          bodyHash: sha256Short(text),
          bodyBytes: Buffer.byteLength(text, 'utf8'),
        }
      } catch (error) {
        return {
          index,
          status: null,
          durationMs: Date.now() - t0,
          error: error && error.name === 'AbortError' ? `timeout after ${timeoutMs}ms` : String(error && error.message),
        }
      } finally {
        clearTimeout(timer)
      }
    })

    const perRequest = await runLimited(tasks, concurrency)

    const statusCounts = {}
    const bodyHashCounts = {}
    const errors = []
    for (const r of perRequest) {
      if (r.status === null) errors.push(r)
      else {
        statusCounts[r.status] = (statusCounts[r.status] ?? 0) + 1
        bodyHashCounts[r.bodyHash] = (bodyHashCounts[r.bodyHash] ?? 0) + 1
      }
    }
    const durations = perRequest.map((r) => r.durationMs)

    const structured = {
      ok: true,
      method,
      target: target.href,
      requests,
      concurrency,
      wallMs: Date.now() - startedAt,
      succeeded: requests - errors.length,
      failed: errors.length,
      statusCounts,
      // 同一输入出现多个响应体哈希 = 状态依赖读的强信号（并发/状态机问题的判据）
      distinctResponseBodies: Object.keys(bodyHashCounts).length,
      bodyHashCounts,
      durationMs: {
        min: Math.min(...durations),
        max: Math.max(...durations),
        avg: Math.round(durations.reduce((a, b) => a + b, 0) / durations.length),
      },
      errors: errors.slice(0, 8),
      perRequest,
    }

    return { content: [{ type: 'text', text: JSON.stringify(structured) }], structured }
  },
}

export const verificationTools = {
  inject: ['extension'],
  apply(ctx) {
    const agnes = ctx.extension()
    agnes.registerTool(concurrentProbeTool)
  },
}
