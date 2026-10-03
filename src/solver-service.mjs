// 工程传热求解服务 —— 被测系统（SUT, system under test）
//
// 角色：这是智能体要"攻击"的对象。它必须是一个**诚实、正确**的数值求解器
// （默认配置下），因为智能体要发现的不是人为埋的 bug，而是数值方法**固有的数学边界**。
//
// 接口契约见 docs/队友B-工作任务书.md 4.1，字段名不得随意改动（插件工具按契约写死了）。
//
// 四种"故障开关"通过环境变量控制，默认全部关闭：
//   QBC_FAULT_HIDE_BLOWUP=on        发散时仍报 blowUp:false（谎报自身状态）
//   QBC_FAULT_SHARED_STATE=on       时间推进异步切片 + 模块级共享缓冲，并发请求互相污染
//   QBC_FAULT_SILENT_CLAMP=on       非法参数（负 alpha 等）不报 400，静默取绝对值
//   QBC_FAULT_PARTIAL_ON_TIMEOUT=on 超出步数上限时返回部分结果且不标记 incomplete
//
// 刻意不做的设计：**不对 r = alpha·dt/dx² 设上限保护**。
// r > 0.5 时 FTCS 发散是数值方法固有的数学边界，智能体的任务是自己二分搜索出这个临界值。
// 若服务在 r > 0.5 时直接报错拒绝，Agent 读一眼错误信息就知道了，那就不是"自主发现"。
//
// 用法：node src/solver-service.mjs [--port 8081]

import { createServer } from 'node:http'

const PORT = Number(process.env.QBC_SOLVER_PORT ?? argPort() ?? 8081)

// 单次求解允许的最大时间步数。超过就拒绝——否则一个极小的 dt 会让进程卡死。
// 注意这个上限取在 5e5，对 r 的二分搜索（dt 在 1e-5 ~ 1e-2 量级）完全够用。
const MAX_STEPS = 500000
const MAX_NODES = 2001

const FAULTS = {
  hideBlowUp: env('QBC_FAULT_HIDE_BLOWUP') === 'on',
  sharedState: env('QBC_FAULT_SHARED_STATE') === 'on',
  silentClamp: env('QBC_FAULT_SILENT_CLAMP') === 'on',
  partialOnTimeout: env('QBC_FAULT_PARTIAL_ON_TIMEOUT') === 'on',
}

const SCHEMES = ['ftcs', 'btcs', 'cn']
// 只实现 FTCS。btcs / cn 在 /health 里列出但 /solve 会明确拒绝——
// 宁可如实说不支持，也不要假装实现了（假装实现会被智能体发现算得不对）。
const IMPLEMENTED = ['ftcs']

function argPort() {
  const i = process.argv.indexOf('--port')
  return i >= 0 ? process.argv[i + 1] : undefined
}
function env(name) {
  return process.env[name]
}

// ---------------------------------------------------------------------------
// 共享状态故障：模块级缓冲 + 异步切片推进。
// Node 是单线程，同步循环无法被其他请求插入；所以真实世界里的这类 bug 总是伴随
// 异步让出（写进度、刷日志、流式返回）。这里如实模拟这一点。
//
// 故障形态刻意选成"**忘记按请求重置**"这种最常见的写法：缓冲只在首次分配时写入初值。
// 后果是第二次及以后的请求会以**上一个请求的终态**作为自己的初态——
// 对同一个请求重复执行会得到不同结果，而这在纯函数语义下是不可能的。
// （初版实现是"每步都重新写入同一初值"，对参数相同的并发请求其实无害、测不出来，
//   属于故障注入本身没做到位；已按上面这种可检测的形态重写。）
// ---------------------------------------------------------------------------
let sharedCurrent = null
let sharedNext = null
let sharedInitialized = false

function ensureShared(nodes) {
  if (!sharedCurrent || sharedCurrent.length !== nodes) {
    sharedCurrent = new Float64Array(nodes)
    sharedNext = new Float64Array(nodes)
    sharedInitialized = false
  }
}

// ---------------------------------------------------------------------------
// 数值内核
// ---------------------------------------------------------------------------

/** 由参数推出网格量。r 与 peclet 一律由代码算，不交给调用方也不交给模型心算。 */
function numerics({ alpha, length, nodes, dt, advection }) {
  const dx = length / (nodes - 1)
  const r = (alpha * dt) / (dx * dx)
  const velocity = advection && advection.enabled ? Number(advection.velocity ?? 0) : 0
  const peclet = velocity === 0 ? 0 : (velocity * dx) / alpha
  return { dx, r, velocity, peclet }
}

function initialValue(initial, x, length) {
  const kind = initial?.kind ?? 'sin'
  if (kind === 'sin') {
    const amplitude = Number(initial?.amplitude ?? 1)
    const modes = Number(initial?.modes ?? 1)
    return amplitude * Math.sin((modes * Math.PI * x) / length)
  }
  if (kind === 'constant') return Number(initial?.value ?? 0)
  if (kind === 'pulse') {
    // 矩形脉冲。存在的理由很重要：**单模态 sin 初值激发不出 r=0.5 的网格尺度失稳**。
    // m=1 模态的 FTCS 放大因子是 G = 1 − 4r·sin²(π/(2(N−1)))，N=101 时要求
    // r ≤ 2/(4·sin²(π/200)) ≈ 2024 才失稳——远在 0.5 之上。
    // 因为 r>0.5 的不稳定性是**最高网格模态**的性质，必须让初值含高频成分才能观察到。
    // 脉冲宽度取到与 dx 同量级即可激发全谱。用脉冲而不是随机数，是为了可复现：
    // 没有 PRNG、没有种子，同样的参数永远得到同样的结果。
    const amplitude = Number(initial?.amplitude ?? 1)
    const center = Number(initial?.center ?? 0.5) * length
    const width = Number(initial?.width ?? 0.01) * length
    return Math.abs(x - center) <= width / 2 ? amplitude : 0
  }
  throw badRequest('E_INITIAL_KIND', `unsupported initial kind: ${kind}`)
}

/** 一次性写入初值并施加边界。 */
function applyInitial(u, spec) {
  // dx 同样在 spec.num 里（与 step 中 r 的情况一样）：写成 spec.dx 会得到 undefined，
  // i*undefined = NaN 会让整个初值变成 NaN，且被 inspect 误判为"发散"。
  const { nodes, initial, boundary, num } = spec
  for (let i = 0; i < nodes; i++) u[i] = initialValue(initial, i * num.dx, spec.length)
  // Dirichlet 直接钉住端点；Neumann 在推进过程中按通量形式处理。
  if (boundary.left.kind === 'dirichlet') u[0] = boundary.left.value
  if (boundary.right.kind === 'dirichlet') u[nodes - 1] = boundary.right.value
}

/** 推进一个时间步（FTCS + 可选中心差分对流）。 */
function step(u, next, spec) {
  const { nodes, boundary, num } = spec
  // 注意 r 在 spec.num 里，不在 spec 顶层——写成 spec.r 会拿到 undefined，
  // undefined 参与算术会静默变成 NaN，且 inspect 会把它当成发散而误报复。
  const r = num.r
  const k = num.velocity === 0 ? 0 : num.velocity / (2 * num.dx)

  for (let i = 1; i < nodes - 1; i++) {
    const diffusion = r * (u[i + 1] - 2 * u[i] + u[i - 1])
    const advection = k === 0 ? 0 : -k * (u[i + 1] - u[i - 1])
    next[i] = u[i] + diffusion + advection
  }

  // ---- 边界：采用「通量形式」，而不是朴素幽灵点法 ----
  //
  // 这一点很容易写错，值得说明：朴素幽灵点写法是
  //     next[0] = u[0] + 2r(u[1] - u[0])
  // 它虽然也近似满足 ∂u/∂x = 0，但**不严格守恒**。推导 Σᵢ(nextᵢ - uᵢ) 得
  //     -r(u₀ - u₁ + u_{N-1} - u_{N-2})
  // 一般不为零，即离散总热量会缓慢漂移。
  //
  // 正确做法按有限体积写：界面通量 F_{i+1/2} = -α(u_{i+1}-u_i)/dx，
  // 更新式 u_i^{n+1} = u_i + (dt/dx)(F_{i-1/2} - F_{i+1/2})。内点求和严格望远镜化相消，
  // 绝热面 F = 0 时 Σuᵢdx 精确守恒（到浮点误差）。
  // 换算到 r 记号：绝热面（g=0）下 next[0] = u[0] + r(u[1]-u[0])，系数是 r 而不是 2r。
  // 通量面给定梯度 g 时 F = -αg，于是多出 -r·dx·g 一项。
  //
  // 对流项与 Neumann 边界在本服务中被拒绝组合（见 validate），故边界处 k 必为 0。

  if (boundary.left.kind === 'dirichlet') {
    next[0] = boundary.left.value
  } else {
    const g = boundary.left.value
    next[0] = u[0] + r * (u[1] - u[0] - num.dx * g)
  }

  if (boundary.right.kind === 'dirichlet') {
    next[nodes - 1] = boundary.right.value
  } else {
    const g = boundary.right.value
    next[nodes - 1] = u[nodes - 1] + r * (u[nodes - 2] - u[nodes - 1] + num.dx * g)
  }
}

function inspect(u, scale) {
  let maxAbs = 0
  let minU = Infinity
  let maxU = -Infinity
  let blown = false
  for (let i = 0; i < u.length; i++) {
    const v = u[i]
    if (!Number.isFinite(v)) { blown = true; break }
    const a = Math.abs(v)
    if (a > maxAbs) maxAbs = a
    if (v < minU) minU = v
    if (v > maxU) maxU = v
    if (a > scale * 1e6) { blown = true; break }
  }
  if (blown) return { maxAbsU: maxAbs, minU, maxU, blowUp: true }
  return { maxAbsU: maxAbs, minU, maxU, blowUp: false }
}

// ---------------------------------------------------------------------------
// 稳态对流扩散（P3 用）
//
//   v·du/dx = α·d²u/dx²,  u(0)=left, u(L)=right
//
// 用**中心差分**离散（这是工程代码里最常见的默认选择，也正是问题所在）：
//   对 (v·dx/2α) 记 c = Pe_cell/2，内点方程化为
//       −(1−c)·u_{i−1} + 2·u_i − (1+c)·u_{i+1} = 0
// 当 0 ≤ c ≤ 1（即 Pe_cell ≤ 2）时，|2| = |1−c| + |1+c|，矩阵是弱对角占优的 M 矩阵，
// 解不会越过边界值。当 c > 1（Pe_cell > 2）时对角占优被破坏，解出现**非物理振荡**。
// 这就是智能体要发现的第三个性质的来源——不是我们埋的 bug，是中心差分的固有缺陷。
//
// 三对角用 Thomas 算法直接求解，不做时间推进（与瞬态路径完全独立）。
// ---------------------------------------------------------------------------
function solveSteady(spec) {
  const { nodes, boundary, num, probes } = spec
  const a = new Float64Array(nodes) // 下对角
  const b = new Float64Array(nodes) // 主对角
  const c = new Float64Array(nodes) // 上对角
  const d = new Float64Array(nodes) // 右端项

  const cellPeclet = num.peclet
  const cHalf = cellPeclet / 2

  b[0] = 1
  d[0] = boundary.left.value
  for (let i = 1; i < nodes - 1; i++) {
    a[i] = -(1 - cHalf)
    b[i] = 2
    c[i] = -(1 + cHalf)
    d[i] = 0
  }
  b[nodes - 1] = 1
  d[nodes - 1] = boundary.right.value

  // Thomas 算法（前向消元 + 回代）
  const cp = new Float64Array(nodes)
  const dp = new Float64Array(nodes)
  cp[0] = c[0] / b[0]
  dp[0] = d[0] / b[0]
  for (let i = 1; i < nodes; i++) {
    const m = b[i] - a[i] * cp[i - 1]
    cp[i] = c[i] / m
    dp[i] = (d[i] - a[i] * dp[i - 1]) / m
  }
  const u = new Float64Array(nodes)
  u[nodes - 1] = dp[nodes - 1]
  for (let i = nodes - 2; i >= 0; i--) u[i] = dp[i] - cp[i] * u[i + 1]

  const probeIdx = probes.map((x) => Math.min(nodes - 1, Math.max(0, Math.round(x * (nodes - 1)))))
  const series = probes.map((x, p) => ({ x, points: [{ t: 0, u: u[probeIdx[p]] }] }))

  const summary = inspect(u, Math.max(1, Math.abs(boundary.right.value - boundary.left.value)))
  return {
    status: 'completed',
    numerics: { dx: num.dx, dt: null, r: null, peclet: num.peclet, steps: 0, steady: true },
    probes: series,
    // 稳态解越界（overshoot/undershoot）就是非物理振荡的判据，这里直接给出极值便于判定。
    summary: { ...summary, steady: true, overshoot: Math.max(0, summary.maxU - Math.max(boundary.left.value, boundary.right.value)), undershoot: Math.max(0, Math.min(boundary.left.value, boundary.right.value) - summary.minU) },
  }
}

// ---------------------------------------------------------------------------
// 请求校验
// ---------------------------------------------------------------------------

function badRequest(code, message) {
  const error = new Error(message)
  error.code = code
  error.status = 400
  return error
}

function validate(body) {
  const f = body ?? {}
  const scheme = String(f.scheme ?? 'ftcs')
  if (!SCHEMES.includes(scheme)) throw badRequest('E_SCHEME_UNKNOWN', `unknown scheme: ${scheme}`)
  if (!IMPLEMENTED.includes(scheme))
    throw badRequest('E_SCHEME_NOT_IMPLEMENTED', `scheme ${scheme} is listed but not implemented in this build`)

  let alpha = Number(f.alpha ?? 1)
  if (!(alpha > 0)) {
    if (FAULTS.silentClamp) {
      // 故障：非法参数不报错，静默取绝对值（甚至把 0 变成 1）
      alpha = Math.abs(alpha) || 1
    } else {
      throw badRequest('E_ALPHA_INVALID', `alpha must be > 0, got ${f.alpha}`)
    }
  }

  const length = Number(f.length ?? 1)
  if (!(length > 0)) throw badRequest('E_LENGTH_INVALID', `length must be > 0, got ${f.length}`)

  const nodes = Number(f.nodes ?? 101)
  if (!Number.isInteger(nodes) || nodes < 2) throw badRequest('E_NODES_INVALID', `nodes must be an integer >= 2, got ${f.nodes}`)
  if (nodes > MAX_NODES) throw badRequest('E_NODES_TOO_LARGE', `nodes must be <= ${MAX_NODES}, got ${nodes}`)

  // 稳态模式：不做时间推进，因此不需要 dt / tEnd，但必须有对流项与两端 Dirichlet。
  const steady = f.steady === true

  let dt = null
  let tEnd = null
  let steps = 0
  if (!steady) {
    dt = Number(f.dt ?? 1e-4)
    if (!(dt > 0)) throw badRequest('E_DT_INVALID', `dt must be > 0, got ${f.dt}`)

    tEnd = Number(f.tEnd ?? 0.05)
    if (!(tEnd >= 0)) throw badRequest('E_TEND_INVALID', `tEnd must be >= 0, got ${f.tEnd}`)

    steps = Math.ceil(tEnd / dt)
    if (steps > MAX_STEPS && !FAULTS.partialOnTimeout)
      throw badRequest('E_TOO_MANY_STEPS', `tEnd/dt = ${steps} exceeds MAX_STEPS=${MAX_STEPS}; increase dt or lower tEnd`)
  }

  const boundary = {
    left: normBoundary(f.boundary?.left, 'dirichlet', 0),
    right: normBoundary(f.boundary?.right, 'dirichlet', 0),
  }
  const advection = { enabled: Boolean(f.advection?.enabled), velocity: Number(f.advection?.velocity ?? 0) }
  if (advection.enabled && (boundary.left.kind === 'neumann' || boundary.right.kind === 'neumann'))
    throw badRequest('E_BC_COMBINATION', 'advection with Neumann boundaries is not supported in this build')

  const probesRaw = Array.isArray(f.probes) && f.probes.length > 0 ? f.probes : [0.5]
  const probes = probesRaw.map((x) => {
    const v = Number(x)
    if (!(v >= 0 && v <= 1)) throw badRequest('E_PROBE_RANGE', `probes must be normalized positions within [0,1], got ${x}`)
    return v
  })

  const recordEvery = Number(f.recordEvery ?? 1)
  if (!Number.isInteger(recordEvery) || recordEvery < 1) throw badRequest('E_RECORDEVERY_INVALID', 'recordEvery must be an integer >= 1')

  const initial = f.initial ?? { kind: 'sin', amplitude: 1, modes: 1 }
  const num = numerics({ alpha, length, nodes, dt: dt ?? 1, advection })

  if (steady) {
    if (!advection.enabled) throw badRequest('E_STEADY_NEEDS_ADVECTION', 'steady mode requires advection.enabled = true')
    if (boundary.left.kind !== 'dirichlet' || boundary.right.kind !== 'dirichlet')
      throw badRequest('E_STEADY_BC', 'steady mode requires Dirichlet boundaries on both ends')
    if (nodes < 3) throw badRequest('E_NODES_INVALID', 'steady mode requires nodes >= 3')
  }

  return { scheme, alpha, length, nodes, dt, tEnd, steps, boundary, advection, probes, recordEvery, initial, num, steady }
}

function normBoundary(value, kind, fallback) {
  const b = value ?? {}
  const k = b.kind ?? kind
  if (k !== 'dirichlet' && k !== 'neumann') throw badRequest('E_BC_KIND', `unsupported boundary kind: ${k}`)
  const v = Number(b.value ?? fallback)
  if (!Number.isFinite(v)) throw badRequest('E_BC_VALUE', `boundary value must be finite, got ${b.value}`)
  return { kind: k, value: v }
}

// ---------------------------------------------------------------------------
// 求解
// ---------------------------------------------------------------------------

async function solve(spec) {
  const { nodes, steps, probes, recordEvery, num } = spec
  const scale = Math.max(1, Math.abs(Number(spec.initial?.amplitude ?? 1)))

  let u, next
  if (FAULTS.sharedState) {
    ensureShared(nodes)
    u = sharedCurrent
    next = sharedNext
    // 故障：只在首次分配时写入初值，之后不再按请求重置 —— 见文件顶部说明。
    if (!sharedInitialized) {
      applyInitial(u, spec)
      sharedInitialized = true
    }
  } else {
    u = new Float64Array(nodes)
    next = new Float64Array(nodes)
    applyInitial(u, spec)
  }

  const probeIdx = probes.map((x) => Math.min(nodes - 1, Math.max(0, Math.round(x * (nodes - 1)))))
  const series = probes.map((x) => ({ x, points: [] }))
  const t0 = 0
  for (let p = 0; p < probes.length; p++) series[p].points.push({ t: t0, u: u[probeIdx[p]] })

  // 总热量由服务计算，不交给调用方（更不交给模型心算）——这样绝热守恒不变量
  // 可以由两个代码算出的数直接比较，验证不掺入任何主观判断。
  const totalHeat = (arr) => {
    let s = 0
    for (let i = 0; i < arr.length; i++) s += arr[i]
    return s * num.dx
  }
  const heatInitial = totalHeat(u)

  const effectiveSteps = steps > MAX_STEPS ? MAX_STEPS : steps
  let completed = 0
  for (let n = 1; n <= effectiveSteps; n++) {
    step(u, next, spec)
    const tmp = u; u = next; next = tmp
    completed = n
    if (FAULTS.sharedState && n % 200 === 0) await new Promise((r) => setImmediate(r))
    if (n % recordEvery === 0 || n === effectiveSteps) {
      const t = n * spec.dt
      for (let p = 0; p < probes.length; p++) series[p].points.push({ t, u: u[probeIdx[p]] })
    }
  }

  const summary = inspect(u, scale)
  const heatFinal = totalHeat(u)
  const reportedBlowUp = FAULTS.hideBlowUp ? false : summary.blowUp

  const incomplete = completed < steps
  if (incomplete && !FAULTS.partialOnTimeout) {
    throw badRequest('E_TOO_MANY_STEPS', `stopped after ${completed} of ${steps} steps`)
  }

  return {
    status: 'completed',
    numerics: { dx: num.dx, dt: spec.dt, r: num.r, peclet: num.peclet, steps: completed },
    probes: series,
    summary: {
      ...summary,
      blowUp: reportedBlowUp,
      totalHeatInitial: heatInitial,
      totalHeatFinal: heatFinal,
      heatDriftRelative: Math.abs(heatInitial) > 0 ? Math.abs(heatFinal - heatInitial) / Math.abs(heatInitial) : Math.abs(heatFinal - heatInitial),
      ...(incomplete ? { incomplete: true } : {}),
    },
  }
}

// ---------------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------------

let taskSeq = 0

function send(res, status, payload) {
  const body = JSON.stringify(payload)
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'content-length': Buffer.byteLength(body) })
  res.end(body)
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let raw = ''
    req.on('data', (c) => {
      raw += c
      if (raw.length > 1e6) reject(badRequest('E_BODY_TOO_LARGE', 'request body too large'))
    })
    req.on('end', () => {
      if (!raw.trim()) return resolve({})
      try { resolve(JSON.parse(raw)) } catch { reject(badRequest('E_BODY_JSON', 'request body is not valid JSON')) }
    })
    req.on('error', reject)
  })
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost')

    if (req.method === 'GET' && url.pathname === '/health') {
      return send(res, 200, {
        ok: true,
        scheme: 'solver-service',
        schemes: SCHEMES,
        implemented: IMPLEMENTED,
        version: '1.0.0',
        limits: { maxSteps: MAX_STEPS, maxNodes: MAX_NODES },
      })
    }

    if (req.method === 'POST' && url.pathname === '/solve') {
      const body = await readJson(req)
      const spec = validate(body)
      const result = spec.steady ? solveSteady(spec) : await solve(spec)
      return send(res, 200, { taskId: `t-${(++taskSeq).toString(36)}-${Date.now().toString(36)}`, ...result })
    }

    return send(res, 404, { error: { code: 'E_NOT_FOUND', message: `no route for ${req.method} ${url.pathname}` } })
  } catch (error) {
    const status = error?.status ?? 500
    return send(res, status, { error: { code: error?.code ?? 'E_INTERNAL', message: String(error?.message ?? error) } })
  }
})

server.listen(PORT, '127.0.0.1', () => {
  const on = Object.entries(FAULTS).filter(([, v]) => v).map(([k]) => k)
  console.log(`[solver-service] http://127.0.0.1:${PORT}/  version=1.0.0`)
  console.log(`[solver-service] implemented schemes: ${IMPLEMENTED.join(', ')} (listed: ${SCHEMES.join(', ')})`)
  console.log(`[solver-service] faults active: ${on.length ? on.join(', ') : 'none'}`)
})
