// QBC 验证工具插件 —— 给 AGH 智能体提供"攻击靶场"的确定性能力。
//
// ============================================================================
// 为什么必须做成插件（实测依据，不是设计偏好）
// ============================================================================
// 1) 非交互模式下 shell 会被审批拒绝。实测证据见 evidence/conformance/B2 与 F2：
//    事件链是 approval/asked -> approval/decided -> tool/result isError "approval rejected"，
//    连只读的字节统计命令也被拒。
// 2) AGH 内置的 web_fetch 明确是 "Anonymous GET only" 且 "no private network" ——
//    既不能 POST，也访问不了 127.0.0.1，够不到本地靶场。
// 3) 后端插件作为受信代码在进程内运行，registerTool 注册的工具按 meta 声明决定是否需要审批。
//
// ============================================================================
// 为什么声明 requiresApproval:'never' 是负责任的
// ============================================================================
// 官方文档警告：改成调用外部系统就必须重新定义效果/审批/重放语义，不能照抄只读工具的声明。
// 因此这里做了三件事，让"免审批"这个声明有代码兜底：
//   - 如实声明 isOpenWorld:true（确实访问网络）、isReadOnly:false、replay:'never'（非幂等）
//   - 用代码把能力限制在本地靶场（ALLOWED_HOSTS），拒绝任意外网目标
//   - 对每次调用做输入校验与上限约束（并发数、请求数、超时）
//
// ============================================================================
// 设计原则：判定不交给模型心算
// ============================================================================
// 实测证据 evidence/conformance/FINDING-1：让模型算 12 行 CSV 的两列均值，它两个都算错
// （21.4917 / 101.3083，基准 21.6667 / 101.3417），而同回合 AGH 内建校验器仍判 pass。
// 所以这些工具直接返回**可判定的结构化事实**（r、peclet、blowUp、热量漂移、越界量、
// 状态码直方图、响应体哈希），让"是否违反某个性质"由代码判定，模型只负责设计实验与解释。
//
// ============================================================================
// 返回值语义（重要，影响智能体如何推理）
// ============================================================================
// 靶场返回的 HTTP 4xx 是**关于靶场的数据**，不是工具故障：例如 422 说明"该问题没有闭式解"，
// 400 说明"参数非法"。因此这类响应用 { ok:false, httpStatus, error{code,message} } 正常返回，
// 不置 isError —— 否则智能体会把一次有信息量的探测当成工具坏了。
// 只有传输层失败（连不上、超时）才置 isError:true。

import { createHash } from 'node:crypto'

const Kind = Symbol.for('TypeBox.Kind')

// 默认只允许本地靶场。可用 AGH_QBC_ALLOWED_HOSTS 覆盖（逗号分隔）。
const DEFAULT_ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '::1', '[::1]']
const allowedHosts = (() => {
  const raw = process.env.AGH_QBC_ALLOWED_HOSTS
  const list = raw ? raw.split(',').map((s) => s.trim()).filter(Boolean) : DEFAULT_ALLOWED_HOSTS
  return new Set(list.map((s) => s.toLowerCase()))
})()

const DEFAULT_SOLVER = process.env.QBC_SOLVER_URL ?? 'http://127.0.0.1:8081'
const DEFAULT_ORACLE = process.env.QBC_ORACLE_URL ?? 'http://127.0.0.1:8082'

const MAX_REQUESTS = 64
const MAX_CONCURRENCY = 16
const MAX_BODY_BYTES = 8192
const MAX_PROBE_POINTS = 64

// ---------------------------------------------------------------------------
// 通用辅助
// ---------------------------------------------------------------------------

const str = (extra = {}) => ({ [Kind]: 'String', type: 'string', ...extra })
const num = (extra = {}) => ({ [Kind]: 'Number', type: 'number', ...extra })
const int = (extra = {}) => ({ [Kind]: 'Integer', type: 'integer', ...extra })
const bool = () => ({ [Kind]: 'Boolean', type: 'boolean' })
const arr = (items, extra = {}) => ({ [Kind]: 'Array', type: 'array', items, ...extra })
const obj = (properties, required = []) => ({
  [Kind]: 'Object',
  type: 'object',
  properties,
  required,
  additionalProperties: false,
})

function ok(structured) {
  return { content: [{ type: 'text', text: JSON.stringify(structured) }], structured }
}

/** 传输层失败：工具确实没能完成任务。 */
function transportFailure(text, structured = {}) {
  return { content: [{ type: 'text', text }], structured: { ok: false, transportError: text, ...structured }, isError: true }
}

/** 靶场返回了 4xx：这是关于靶场的数据，不是工具故障。 */
function targetResponse(httpStatus, body) {
  return ok({ ok: false, httpStatus, error: body?.error ?? { code: 'E_UNKNOWN', message: 'no error body' } })
}

function assertAllowed(url) {
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    return `only http/https is supported, got ${url.protocol}`
  }
  if (!allowedHosts.has(url.hostname.toLowerCase())) {
    return `host not allowed: ${url.hostname}. Allowed: ${[...allowedHosts].join(', ')}. Set AGH_QBC_ALLOWED_HOSTS to widen this deliberately.`
  }
  return null
}

async function requestJson(method, urlString, body, timeoutMs) {
  let target
  try {
    target = new URL(urlString)
  } catch {
    return { kind: 'badUrl', message: `not a valid absolute URL: ${urlString}` }
  }
  const denied = assertAllowed(target)
  if (denied) return { kind: 'badUrl', message: denied }

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(target, {
      method,
      signal: controller.signal,
      ...(body === undefined ? {} : { headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }),
    })
    const text = await res.text()
    let parsed
    try { parsed = JSON.parse(text) } catch { parsed = { raw: text.slice(0, 2000) } }
    return { kind: 'response', status: res.status, body: parsed, bytes: Buffer.byteLength(text, 'utf8') }
  } catch (error) {
    const message = error?.name === 'AbortError' ? `timeout after ${timeoutMs}ms` : String(error?.message ?? error)
    return { kind: 'transport', message }
  } finally {
    clearTimeout(timer)
  }
}

/** 把长序列降采样，但如实声明总数，不做"静默截断"。 */
function downsample(points, max = MAX_PROBE_POINTS) {
  if (!Array.isArray(points) || points.length <= max) return { points: points ?? [], total: points?.length ?? 0, downsampled: false }
  const step = (points.length - 1) / (max - 1)
  const out = []
  for (let i = 0; i < max; i++) out.push(points[Math.round(i * step)])
  return { points: out, total: points.length, downsampled: true }
}

function sha256Short(text) {
  return createHash('sha256').update(text).digest('hex').slice(0, 16)
}

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

const asInt = (value, fallback) => (Number.isInteger(value) ? value : fallback)

// ---------------------------------------------------------------------------
// 工具 1：靶场健康检查
// ---------------------------------------------------------------------------
const healthTool = {
  name: 'target_health',
  description:
    'Check that the local target system is reachable and report what each service advertises: implemented schemes, limits, and which closed forms the independent analytic oracle supports. Call this first.',
  parameters: obj({
    solverUrl: str({ maxLength: 2048 }),
    oracleUrl: str({ maxLength: 2048 }),
  }),
  meta: {
    isReadOnly: true,
    isDestructive: false,
    isConcurrencySafe: true,
    isOpenWorld: true,
    replay: 'safe',
    costHint: undefined,
    deferLoading: false,
    requiresApproval: 'never',
  },
  async execute(args = {}) {
    const solver = await requestJson('GET', args.solverUrl ?? `${DEFAULT_SOLVER}/health`, undefined, 10000)
    const oracle = await requestJson('GET', args.oracleUrl ?? `${DEFAULT_ORACLE}/health`, undefined, 10000)
    const wrap = (r, label) => {
      if (r.kind === 'response') return { status: r.status, body: r.body }
      return { unreachable: true, reason: r.message ?? r.kind, hint: `${label} reachable? start it with scripts/start-services.ps1` }
    }
    return ok({ ok: true, solver: wrap(solver, 'solver-service'), oracle: wrap(oracle, 'oracle-service') })
  },
}

// ---------------------------------------------------------------------------
// 工具 2：求解（被测系统）
//
// 参数刻意做成**扁平**而不是嵌套对象：模型的工具调用参数越浅越不容易写错，
// 而把它翻译成契约要求的嵌套 JSON 是本工具的责任，不是模型的责任。
// ---------------------------------------------------------------------------
const solveTool = {
  name: 'solver_solve',
  description:
    'Run one solve on the target heat-conduction service and return the quantities the service computed: dx, dt, r = alpha*dt/dx^2, peclet = velocity*dx/alpha, steps, blowUp, extrema, and total-heat drift. Set steady=true to solve the steady advection-diffusion profile instead of stepping in time. An HTTP 4xx comes back as data (ok:false with the error code), not as a tool failure. Deliberately does NOT re-validate the target\'s input domain: illegal or extreme values are passed through so you can observe how the service itself responds.',
  // ==========================================================================
  // 参数 schema 刻意**不**复刻目标系统的合法区间
  // ==========================================================================
  // 这是本项目的一条设计原则，有实测教训作为依据：
  // 初版把 alpha 声明为 exclusiveMinimum:0、probes 声明为 [0,1]，结果非法输入在**本地
  // schema 校验**就被拒绝，根本到不了目标服务——智能体因此完全观察不到服务自己的 400 响应，
  // 边界探测任务被迫以 blocked 结束（它如实报告了"缺少能构造越界入参的通道"，没有编造）。
  //
  // 对验证类作品来说这是原则性错误：**工具的客户端校验决定了智能体能发现什么**。
  // schema 比目标更严，等于把目标系统的失效模式屏蔽掉，验证就退化成"只测我们允许测的东西"。
  // 所以这里只保留传输层必要约束（字符串长度），业务域一律交给目标服务裁决。
  parameters: obj(
    {
      alpha: num(),
      nodes: int({ maximum: 2001 }),
      dt: num(),
      tEnd: num(),
      length: num(),
      steady: bool(),
      initialKind: str({ enum: ['sin', 'pulse', 'constant'] }),
      initialAmplitude: num(),
      initialModes: int(),
      initialCenter: num(),
      initialWidth: num(),
      initialValue: num(),
      leftKind: str({ enum: ['dirichlet', 'neumann'] }),
      leftValue: num(),
      rightKind: str({ enum: ['dirichlet', 'neumann'] }),
      rightValue: num(),
      advectionVelocity: num(),
      probes: arr(num(), { minItems: 1, maxItems: 16 }),
      recordEvery: int(),
      solverUrl: str({ maxLength: 2048 }),
    },
    ['nodes'],
  ),
  meta: {
    // isReadOnly / replay 的取值依据是**目标系统的实际语义**，不是"能不能少一次审批"。
    // 靶场求解接口是纯函数：结果只由请求决定，服务不持久化任何按请求的状态，
    // 重复提交同一请求得到同一结果。因此如实声明 isReadOnly:true、replay:'safe'。
    //
    // 这一条有实测依据：AGH 的判定规则是
    //   needsAsk = risk==='always' || (risk==='destructive' && isDestructive) || (taint && !isReadOnly)
    //   （packages/core/src/step/tools.ts:355）
    // 声明成 isReadOnly:false 时，会话一旦被 taint，非只读工具就要求审批；非交互环境下
    // 无人应答即被拒（实测：全新会话首个调用成功、被 taint 后同一工具返回 approval rejected）。
    // 也就是说：**声明错误会直接让自动化实验失败**，而正确声明才是这里的解法。
    //
    // 注意：若将来靶场接口有了真实副作用（例如写库、下单），必须把这里改回
    // isReadOnly:false 并重新定义审批与重放语义，不能沿用本声明。
    isReadOnly: true,
    isDestructive: false,
    isConcurrencySafe: true,
    isOpenWorld: true,
    replay: 'safe',
    costHint: undefined,
    deferLoading: false,
    requiresApproval: 'never',
  },
  async execute(args = {}) {
    const nodes = asInt(args.nodes, 101)
    const body = {
      scheme: 'ftcs',
      alpha: args.alpha ?? 1,
      length: args.length ?? 1,
      nodes,
      probes: Array.isArray(args.probes) && args.probes.length ? args.probes : [0.5],
      recordEvery: asInt(args.recordEvery, 1),
      boundary: {
        left: { kind: args.leftKind ?? 'dirichlet', value: args.leftValue ?? 0 },
        right: { kind: args.rightKind ?? 'dirichlet', value: args.rightValue ?? 0 },
      },
      advection: { enabled: Number(args.advectionVelocity ?? 0) !== 0, velocity: Number(args.advectionVelocity ?? 0) },
      initial: {
        kind: args.initialKind ?? 'sin',
        amplitude: args.initialAmplitude ?? 1,
        modes: asInt(args.initialModes, 1),
        center: args.initialCenter ?? 0.5,
        width: args.initialWidth ?? 0.01,
        value: args.initialValue ?? 0,
      },
    }
    if (args.steady === true) {
      body.steady = true
      body.dt = 1
      body.tEnd = 0
    } else {
      body.dt = args.dt ?? 1e-4
      body.tEnd = args.tEnd ?? 0.05
    }

    const r = await requestJson('POST', args.solverUrl ?? `${DEFAULT_SOLVER}/solve`, body, 120000)
    if (r.kind === 'badUrl') return transportFailure(r.message)
    if (r.kind === 'transport') return transportFailure(`solver unreachable: ${r.message}`)
    if (r.status >= 400) return targetResponse(r.status, r.body)

    const probes = (r.body.probes ?? []).map((p) => {
      const series = downsample(p.points)
      return { x: p.x, pointsReturned: series.points.length, pointsTotal: series.total, downsampled: series.downsampled, points: series.points }
    })
    return ok({
      ok: true,
      taskId: r.body.taskId,
      requested: { dt: body.dt, tEnd: body.tEnd, nodes, steady: body.steady === true },
      numerics: r.body.numerics,
      summary: r.body.summary,
      probes,
    })
  },
}

// ---------------------------------------------------------------------------
// 工具 3：独立解析解基准（Oracle）
// ---------------------------------------------------------------------------
const oracleTool = {
  name: 'oracle_exact',
  description:
    'Ask the INDEPENDENT analytic oracle for the closed-form solution at given space-time points. It uses separation of variables (single sine mode) or the steady exponential advection profile, and shares no code with the numerical solver. When no closed form exists it answers HTTP 422 and never a numerical approximation — a 422 is a real answer about what is knowable, not a tool failure. Points expand as xs outer, ts inner; steady mode ignores ts.',
  parameters: obj(
    {
      alpha: num({ exclusiveMinimum: 0 }),
      length: num({ exclusiveMinimum: 0 }),
      initialKind: str({ enum: ['sin'] }),
      amplitude: num(),
      modes: int({ minimum: 1 }),
      steady: bool(),
      advectionVelocity: num(),
      leftValue: num(),
      rightValue: num(),
      xs: arr(num({ minimum: 0 }), { minItems: 1, maxItems: 32 }),
      ts: arr(num({ minimum: 0 }), { minItems: 1, maxItems: 32 }),
      oracleUrl: str({ maxLength: 2048 }),
    },
    ['xs'],
  ),
  meta: {
    isReadOnly: true,
    isDestructive: false,
    isConcurrencySafe: true,
    isOpenWorld: true,
    replay: 'safe',
    costHint: undefined,
    deferLoading: false,
    requiresApproval: 'never',
  },
  async execute(args = {}) {
    const length = args.length ?? 1
    const xs = Array.isArray(args.xs) && args.xs.length ? args.xs : [0.5 * length]
    const ts = Array.isArray(args.ts) && args.ts.length ? args.ts : [0]
    const steady = args.steady === true

    const points = steady ? xs.map((x) => ({ x })) : xs.flatMap((x) => ts.map((t) => ({ x, t })))

    const body = {
      alpha: args.alpha ?? 1,
      length,
      initial: { kind: args.initialKind ?? 'sin', amplitude: args.amplitude ?? 1, modes: asInt(args.modes, 1) },
      boundary: steady
        ? { left: { kind: 'dirichlet', value: args.leftValue ?? 0 }, right: { kind: 'dirichlet', value: args.rightValue ?? 1 } }
        : { left: { kind: 'dirichlet', value: 0 }, right: { kind: 'dirichlet', value: 0 } },
      ...(steady ? { steady: true, advection: { enabled: true, velocity: args.advectionVelocity ?? 0 } } : {}),
      points,
    }

    const r = await requestJson('POST', args.oracleUrl ?? `${DEFAULT_ORACLE}/exact`, body, 30000)
    if (r.kind === 'badUrl') return transportFailure(r.message)
    if (r.kind === 'transport') return transportFailure(`oracle unreachable: ${r.message}`)
    if (r.status >= 400) return targetResponse(r.status, r.body)

    return ok({
      ok: true,
      method: r.body.method,
      terms: r.body.terms,
      truncationError: r.body.truncationError,
      ...(r.body.pecletDomain === undefined ? {} : { pecletDomain: r.body.pecletDomain }),
      points: r.body.points,
    })
  },
}

// ---------------------------------------------------------------------------
// 工具 4：并发探测（压力攻击）
// ---------------------------------------------------------------------------
const burstTool = {
  name: 'qbc_http_burst',
  description:
    'Send N HTTP requests to the local target with bounded concurrency, then report a deterministic summary: status-code histogram, per-request durations, distinct response-body hashes, and errors. Use it to test for race conditions and capacity limits — the same input yielding different response bodies is a strong signal of state-dependent reads. It is ALSO the raw escape hatch: with method=POST, contentType=application/json and an arbitrary body you can send any request to the target, including inputs that solver_solve\'s parameters cannot express, and read the service\'s own status code and error body. Only local hosts are permitted.',
  parameters: obj(
    {
      url: str({ minLength: 1, maxLength: 2048 }),
      requests: int({ minimum: 1, maximum: MAX_REQUESTS }),
      concurrency: int({ minimum: 1, maximum: MAX_CONCURRENCY }),
      method: str({ enum: ['GET', 'POST'] }),
      body: str({ maxLength: MAX_BODY_BYTES }),
      contentType: str({ maxLength: 128 }),
      timeoutMs: int({ minimum: 100, maximum: 60000 }),
    },
    ['url', 'requests'],
  ),
  meta: {
    isReadOnly: false,
    isDestructive: false,
    isConcurrencySafe: true,
    isOpenWorld: true,
    replay: 'never',
    costHint: undefined,
    deferLoading: false,
    requiresApproval: 'never',
  },
  async execute(args = {}) {
    const requests = asInt(args.requests, 1)
    const concurrency = asInt(args.concurrency, Math.min(requests, 4))
    const method = args.method === 'POST' ? 'POST' : 'GET'
    const timeoutMs = asInt(args.timeoutMs, 10000)

    if (requests < 1 || requests > MAX_REQUESTS) return transportFailure(`requests must be within 1..${MAX_REQUESTS}`)
    if (concurrency < 1 || concurrency > MAX_CONCURRENCY) return transportFailure(`concurrency must be within 1..${MAX_CONCURRENCY}`)

    let target
    try {
      target = new URL(String(args.url))
    } catch {
      return transportFailure(`url is not a valid absolute URL: ${String(args.url)}`)
    }
    const denied = assertAllowed(target)
    if (denied) return transportFailure(denied)

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
        return { index, status: response.status, durationMs: Date.now() - t0, bodyHash: sha256Short(text), bodyBytes: Buffer.byteLength(text, 'utf8') }
      } catch (error) {
        return { index, status: null, durationMs: Date.now() - t0, error: error?.name === 'AbortError' ? `timeout after ${timeoutMs}ms` : String(error?.message) }
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

    return ok({
      ok: true,
      method,
      target: target.href,
      requests,
      concurrency,
      wallMs: Date.now() - startedAt,
      succeeded: requests - errors.length,
      failed: errors.length,
      statusCounts,
      distinctResponseBodies: Object.keys(bodyHashCounts).length,
      bodyHashCounts,
      durationMs: { min: Math.min(...durations), max: Math.max(...durations), avg: Math.round(durations.reduce((a, b) => a + b, 0) / durations.length) },
      errors: errors.slice(0, 8),
    })
  },
}

// ---------------------------------------------------------------------------
// 工具 5：求解服务的并发一致性探测（只打求解端点，只发求解请求）
//
// 为什么不能直接用 qbc_http_burst 做这件事：
//   burst 能向任意本地端点 POST 任意体，因此它**必须**声明 isReadOnly:false；
//   而 AGH 的判定是 needsAsk = … || (taint && !isReadOnly)，
//   于是会话被 taint 后 burst 会要求审批，非交互环境下无人应答即被拒——
//   实测：并发攻击任务里 burst 三次调用全部 "approval rejected"，只有串行部分跑完。
//
// 这里的解法不是放宽声明，而是**用代码把能力收窄到可以诚实声明只读的范围内**：
//   - 目标固定为求解服务的 /solve 端点（可用 solverUrl 覆盖，但仍受本地主机白名单约束）
//   - 请求体由本工具按求解参数构造，不接受任意 JSON 体
//   - 而 /solve 是纯函数（无持久化状态、同请求同结果）
// 三者同时成立，isReadOnly:true / replay:'safe' 才是**如实描述**而非权宜之计。
//
// 返回值里给出**逐请求的 summary.maxAbsU**：对一个纯函数而言它们必须完全相同，
// 因此不一致本身就直接构成"跨请求状态污染"的判据，不需要分析者再做推断。
// ---------------------------------------------------------------------------
const solverBurstTool = {
  name: 'solver_burst',
  description:
    'Send the SAME solve request N times to the target solver with bounded concurrency and report per-request results: status, per-request summary.maxAbsU, plus a status-code histogram and the number of distinct response bodies. Because /solve is a pure function, a correct service must return identical values for identical requests; any spread in maxAbsU, or distinctResponseBodies > 1, is direct evidence of cross-request state contamination. Only the solver /solve endpoint can be reached and only solve-shaped bodies are sent.',
  parameters: obj(
    {
      alpha: num(),
      nodes: int({ maximum: 2001 }),
      dt: num(),
      tEnd: num(),
      length: num(),
      initialKind: str({ enum: ['sin', 'pulse', 'constant'] }),
      initialAmplitude: num(),
      initialModes: int(),
      initialCenter: num(),
      initialWidth: num(),
      leftKind: str({ enum: ['dirichlet', 'neumann'] }),
      leftValue: num(),
      rightKind: str({ enum: ['dirichlet', 'neumann'] }),
      rightValue: num(),
      probes: arr(num(), { minItems: 1, maxItems: 16 }),
      requests: int({ minimum: 2, maximum: MAX_REQUESTS }),
      concurrency: int({ minimum: 1, maximum: MAX_CONCURRENCY }),
      timeoutMs: int({ minimum: 100, maximum: 60000 }),
      solverUrl: str({ maxLength: 2048 }),
    },
    ['nodes', 'requests'],
  ),
  meta: {
    // 只读声明的依据：目标端点固定、请求体由本工具构造、/solve 是纯函数。见上方说明。
    isReadOnly: true,
    isDestructive: false,
    isConcurrencySafe: true,
    isOpenWorld: true,
    replay: 'safe',
    costHint: undefined,
    deferLoading: false,
    requiresApproval: 'never',
  },
  async execute(args = {}) {
    const requests = asInt(args.requests, 4)
    const concurrency = asInt(args.concurrency, Math.min(requests, 3))
    const timeoutMs = asInt(args.timeoutMs, 60000)
    if (requests < 2 || requests > MAX_REQUESTS) return transportFailure(`requests must be within 2..${MAX_REQUESTS}`)
    if (concurrency < 1 || concurrency > MAX_CONCURRENCY) return transportFailure(`concurrency must be within 1..${MAX_CONCURRENCY}`)

    const urlString = args.solverUrl ?? `${DEFAULT_SOLVER}/solve`
    let target
    try {
      target = new URL(urlString)
    } catch {
      return transportFailure(`solverUrl is not a valid absolute URL: ${urlString}`)
    }
    const denied = assertAllowed(target)
    if (denied) return transportFailure(denied)

    const body = {
      scheme: 'ftcs',
      alpha: args.alpha ?? 1,
      length: args.length ?? 1,
      nodes: asInt(args.nodes, 101),
      dt: args.dt ?? 1e-5,
      tEnd: args.tEnd ?? 0.01,
      probes: Array.isArray(args.probes) && args.probes.length ? args.probes : [0.5],
      recordEvery: 100000,
      boundary: {
        left: { kind: args.leftKind ?? 'dirichlet', value: args.leftValue ?? 0 },
        right: { kind: args.rightKind ?? 'dirichlet', value: args.rightValue ?? 0 },
      },
      advection: { enabled: false, velocity: 0 },
      initial: {
        kind: args.initialKind ?? 'sin',
        amplitude: args.initialAmplitude ?? 1,
        modes: asInt(args.initialModes, 1),
        center: args.initialCenter ?? 0.5,
        width: args.initialWidth ?? 0.01,
        value: 0,
      },
    }
    const payload = JSON.stringify(body)

    const startedAt = Date.now()
    const tasks = Array.from({ length: requests }, (_, index) => async () => {
      const t0 = Date.now()
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), timeoutMs)
      try {
        const response = await fetch(target, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: payload,
          signal: controller.signal,
        })
        const text = await response.text()
        let parsed
        try { parsed = JSON.parse(text) } catch { parsed = null }
        return {
          index,
          status: response.status,
          durationMs: Date.now() - t0,
          bodyHash: sha256Short(text),
          maxAbsU: parsed?.summary?.maxAbsU ?? null,
          totalHeatInitial: parsed?.summary?.totalHeatInitial ?? null,
          firstProbeU: parsed?.probes?.[0]?.points?.[0]?.u ?? null,
          errorCode: parsed?.error?.code ?? null,
        }
      } catch (error) {
        return {
          index,
          status: null,
          durationMs: Date.now() - t0,
          error: error?.name === 'AbortError' ? `timeout after ${timeoutMs}ms` : String(error?.message),
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

    // 纯函数语义下的判据：不一致即为状态污染，无需分析者再推断。
    const maxAbsValues = perRequest.map((r) => r.maxAbsU).filter((v) => v !== null && v !== undefined)
    const distinctMaxAbs = [...new Set(maxAbsValues)]
    const consistent = errors.length === 0 && Object.keys(bodyHashCounts).length === 1

    return ok({
      ok: true,
      target: target.href,
      requestBody: body,
      requests,
      concurrency,
      wallMs: Date.now() - startedAt,
      statusCounts,
      distinctResponseBodies: Object.keys(bodyHashCounts).length,
      distinctMaxAbsUValues: distinctMaxAbs.length,
      maxAbsUValues: perRequest.map((r) => r.maxAbsU),
      firstProbeUValues: perRequest.map((r) => r.firstProbeU),
      totalHeatInitialValues: perRequest.map((r) => r.totalHeatInitial),
      consistent,
      verdict: consistent
        ? 'IDENTICAL — identical requests returned identical results, which is what a pure function must do'
        : 'INCONSISTENT — identical requests did NOT return identical results; this is cross-request state contamination, not floating-point noise',
      perRequest,
      errors: errors.slice(0, 8),
    })
  },
}

// ---------------------------------------------------------------------------
export const verificationTools = {
  inject: ['extension'],
  apply(ctx) {
    const agnes = ctx.extension()
    agnes.registerTool(healthTool)
    agnes.registerTool(solveTool)
    agnes.registerTool(oracleTool)
    agnes.registerTool(burstTool)
    agnes.registerTool(solverBurstTool)
  },
}
