// 解析解基准服务（Oracle）—— 独立验证基准
//
// 角色：这是"标准答案"。它与被测求解服务**必须结构独立**：
//   - 两个进程、两个端口
//   - 求解服务走**数值离散**（有限差分时间推进）
//   - 本服务走**闭式解析解**（分离变量 / 稳态指数解），不做任何时间推进
// 若基准与被测同源，验证就是自证，作品的核心价值归零。
//
// 红线：**没有闭式解时必须返回 422，绝不许用数值解冒充解析解。**
// 谎报基准比没有基准更糟——那会让整个验证失效。
//
// 接口契约见 docs/队友B-工作任务书.md 4.2。
//
// 用法：node src/oracle-service.mjs [--port 8082]

import { createServer } from 'node:http'

const PORT = Number(process.env.QBC_ORACLE_PORT ?? argPort() ?? 8082)

function argPort() {
  const i = process.argv.indexOf('--port')
  return i >= 0 ? process.argv[i + 1] : undefined
}

function badRequest(code, message) {
  const e = new Error(message)
  e.code = code
  e.status = 400
  return e
}
function unprocessable(code, message) {
  const e = new Error(message)
  e.code = code
  e.status = 422
  return e
}

// ---------------------------------------------------------------------------
// 情况 1：初值 A·sin(mπx/L)，两端零 Dirichlet —— 分离变量法，单模态精确解
//
//   u(x,t) = A·sin(mπx/L)·exp(−α(mπ/L)²t)
//
// 这是**精确**解（不是截断级数）：初值本身只含一个模态，而每个模态独立衰减，
// 所以级数只有一项，不存在截断误差。这里如实声明 terms=1、truncationError=0，
// 不假装成"200 项级数"。
// ---------------------------------------------------------------------------
function exactSingleMode({ alpha, length, initial, points }) {
  const amplitude = Number(initial?.amplitude ?? 1)
  const modes = Number(initial?.modes ?? 1)
  const lambda = (modes * Math.PI) / length

  const out = points.map((p) => {
    const x = Number(p.x)
    const t = Number(p.t ?? 0)
    if (!Number.isFinite(x) || !Number.isFinite(t)) throw badRequest('E_POINT_INVALID', 'each point needs finite x and t')
    if (x < 0 || x > length) throw badRequest('E_POINT_RANGE', `x must be within [0, ${length}], got ${x}`)
    if (t < 0) throw badRequest('E_POINT_RANGE', `t must be >= 0, got ${t}`)
    return { x, t, u: amplitude * Math.sin(lambda * x) * Math.exp(-alpha * lambda * lambda * t) }
  })

  return {
    method: 'separation-of-variables (single analytic mode, exact)',
    terms: 1,
    truncationError: 0,
    points: out,
  }
}

// ---------------------------------------------------------------------------
// 情况 2：稳态对流扩散，u(0)=0、u(L)=1
//
//   v·du/dx = α·d²u/dx²
//   u(x) = (exp(Pe·x/L) − 1) / (exp(Pe) − 1),   Pe = v·L/α
//
// 注意 Pe 的两个口径不要混：这里是**域 Péclet 数** Pe_L = vL/α（用域长 L），
// 而被测求解服务返回的 `numerics.peclet` 是**网格 Péclet 数** Pe_cell = v·dx/α。
// 二者关系 Pe_cell = Pe_L/(N−1)。中心差分产生非物理振荡的阈值是 Pe_cell = 2，
// 也就是网格足够粗（N−1 < Pe_L/2）时才出现——这正是智能体要发现的第三个性质。
//
// 数值稳定处理：Pe 很大时 exp(Pe) 会溢出，故按符号分支改写为等价的稳定形式。
// ---------------------------------------------------------------------------
function exactSteadyAdvection({ alpha, length, advection, boundary, points }) {
  const v = Number(advection?.velocity ?? 0)
  if (v === 0) throw unprocessable('E_NO_CLOSED_FORM', 'steady advection-diffusion with zero velocity is pure diffusion; this oracle only covers the advective steady profile')

  const left = Number(boundary?.left?.value ?? 0)
  const right = Number(boundary?.right?.value ?? 1)
  if (boundary?.left?.kind !== 'dirichlet' || boundary?.right?.kind !== 'dirichlet')
    throw unprocessable('E_NO_CLOSED_FORM', 'steady profile requires Dirichlet boundaries on both ends')

  const Pe = (v * length) / alpha

  const profile = (x) => {
    const xi = x / length
    if (Pe >= 0) {
      // u = (exp(Pe·ξ) − 1)/(exp(Pe) − 1)，两边同乘 exp(−Pe) 得到稳定形式
      const denom = 1 - Math.exp(-Pe)
      if (denom === 0) return left + (right - left) * xi // Pe→0 退化为线性
      const num = Math.exp(-Pe * (1 - xi)) - Math.exp(-Pe)
      return left + (right - left) * (num / denom)
    }
    // Pe < 0 时原式不会溢出
    const denom = Math.exp(Pe) - 1
    if (denom === 0) return left + (right - left) * xi
    const num = Math.exp(Pe * xi) - 1
    return left + (right - left) * (num / denom)
  }

  const out = points.map((p) => {
    const x = Number(p.x)
    if (!Number.isFinite(x)) throw badRequest('E_POINT_INVALID', 'each point needs a finite x')
    if (x < 0 || x > length) throw badRequest('E_POINT_RANGE', `x must be within [0, ${length}], got ${x}`)
    return { x, t: null, u: profile(x) }
  })

  return {
    method: 'steady advection-diffusion (closed form, exponential profile)',
    terms: null,
    truncationError: 0,
    pecletDomain: Pe,
    points: out,
  }
}

// ---------------------------------------------------------------------------
// 路由
// ---------------------------------------------------------------------------

function solveExact(body) {
  const b = body ?? {}
  const alpha = Number(b.alpha ?? 1)
  const length = Number(b.length ?? 1)
  if (!(alpha > 0)) throw badRequest('E_ALPHA_INVALID', `alpha must be > 0, got ${b.alpha}`)
  if (!(length > 0)) throw badRequest('E_LENGTH_INVALID', `length must be > 0, got ${b.length}`)

  const points = Array.isArray(b.points) ? b.points : []
  if (points.length === 0) throw badRequest('E_POINTS_REQUIRED', 'points must be a non-empty array')

  const boundary = b.boundary ?? { left: { kind: 'dirichlet', value: 0 }, right: { kind: 'dirichlet', value: 0 } }
  const isNeumann = boundary?.left?.kind === 'neumann' || boundary?.right?.kind === 'neumann'
  const steady = b.steady === true
  const advectionOn = Boolean(b.advection?.enabled)

  if (steady) return exactSteadyAdvection({ alpha, length, advection: b.advection, boundary, points })

  // 分离变量解要求两端零 Dirichlet；Neumann（绝热）没有这个初值下的闭式解。
  if (isNeumann)
    throw unprocessable(
      'E_NO_CLOSED_FORM',
      'this oracle has no closed form for Neumann boundaries with a sine initial condition. ' +
        'Reporting a numerical answer here would be presenting a solution as a reference, which this service refuses to do.',
    )
  if (boundary?.left?.value !== undefined && Number(boundary.left.value) !== 0) {
    throw unprocessable('E_NO_CLOSED_FORM', 'separation-of-variables mode requires zero left Dirichlet value')
  }
  if (boundary?.right?.value !== undefined && Number(boundary.right.value) !== 0) {
    throw unprocessable('E_NO_CLOSED_FORM', 'separation-of-variables mode requires zero right Dirichlet value')
  }
  if (advectionOn)
    throw unprocessable(
      'E_NO_CLOSED_FORM',
      'transient advection-diffusion with a sine initial condition has no single-mode closed form; use steady:true for the advective profile',
    )

  // 关键防线：分离变量模式**只**覆盖单模态正弦初值。
  // 若这里不校验 kind，pulse / constant 之类的请求会落到同一个公式上，
  // 相当于把"正弦解"当成"脉冲解的基准"返回——那正是本服务明令禁止的"谎报基准"。
  const initialKind = b.initial?.kind ?? 'sin'
  if (initialKind !== 'sin')
    throw unprocessable(
      'E_NO_CLOSED_FORM',
      `the separation-of-variables mode covers only a single sine mode, got initial.kind=${initialKind}. ` +
        'This oracle refuses to approximate: presenting a numerical answer as a reference would invalidate the whole verification.',
    )
  const modes = Number(b.initial?.modes ?? 1)
  if (!Number.isInteger(modes) || modes < 1)
    throw badRequest('E_MODES_INVALID', `initial.modes must be a positive integer, got ${b.initial?.modes}`)

  return exactSingleMode({ alpha, length, initial: b.initial, points })
}

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
        scheme: 'oracle-service',
        version: '1.0.0',
        modes: ['separation-of-variables (sin + zero Dirichlet)', 'steady advection-diffusion (exponential)'],
        independentOf: 'the numerical solver — no shared code, no time stepping',
      })
    }

    if (req.method === 'POST' && url.pathname === '/exact') {
      const body = await readJson(req)
      return send(res, 200, solveExact(body))
    }

    return send(res, 404, { error: { code: 'E_NOT_FOUND', message: `no route for ${req.method} ${url.pathname}` } })
  } catch (error) {
    const status = error?.status ?? 500
    return send(res, status, { error: { code: error?.code ?? 'E_INTERNAL', message: String(error?.message ?? error) } })
  }
})

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[oracle-service] http://127.0.0.1:${PORT}/  version=1.0.0`)
  console.log('[oracle-service] closed forms: sin+zeroDirichlet (exact single mode), steady advection-diffusion')
  console.log('[oracle-service] no closed form -> 422 (never a numerical answer)')
})
