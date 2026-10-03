#!/usr/bin/env node
/**
 * 独立基准测量（D4）—— 产出 ground-truth/ground-truth.json
 *
 * 为什么需要它：智能体的任务不是"跑出结果"，而是"自主发现失效边界"。既然它的结论要被
 * 判定对错，就必须先有一个**独立于它**的标准答案。这个脚本由人（本队）在智能体之外运行，
 * 用与智能体完全不同的路径（直接二分测量）得出四个性质的实测值。
 *
 * 它回答的问题：
 *   P1  FTCS 时空离散的稳定性临界 r* = α·Δt/Δx² 是多少？（理论 0.5）
 *   P2  空间/时间收敛阶是多少？（理论 2）
 *   P3  中心差分对流的非物理振荡阈值（网格 Péclet 数）是多少？（理论 2）
 *   P4  两端绝热时离散总热量是否守恒？（理论：精确守恒）
 *
 * 前置：靶场已启动（scripts/start-services.ps1）
 * 用法：node tools/measure-ground-truth.mjs
 *
 * 输出目录会被 .gitignore 吗？不会——ground-truth 是提交材料的一部分。
 * 但**智能体不得读取它**，见 docs/分工与总体计划.md 红线 4。
 */

import { writeFileSync, mkdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..')

const SOLVER = process.env.QBC_SOLVER_URL ?? 'http://127.0.0.1:8081'
const ORACLE = process.env.QBC_ORACLE_URL ?? 'http://127.0.0.1:8082'

// ---------------------------------------------------------------------------
// HTTP 辅助
// ---------------------------------------------------------------------------
async function post(base, path, body) {
  const res = await fetch(`${base}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  const text = await res.text()
  let json
  try { json = JSON.parse(text) } catch { json = { raw: text } }
  return { status: res.status, body: json }
}

async function get(base, path) {
  const res = await fetch(`${base}${path}`)
  return { status: res.status, body: await res.json() }
}

const solve = (body) => post(SOLVER, '/solve', body)
const exact = (body) => post(ORACLE, '/exact', body)

const DIRICHLET0 = { left: { kind: 'dirichlet', value: 0 }, right: { kind: 'dirichlet', value: 0 } }
const PULSE = (width = 0.01) => ({ kind: 'pulse', amplitude: 1, center: 0.5, width })
const SIN = { kind: 'sin', amplitude: 1, modes: 1 }

/** 是否已发散：服务自报 blowUp，或幅值涨到初值 10 倍以上。 */
function diverged(res) {
  if (res.status !== 200) return null
  const s = res.body.summary
  return s.blowUp === true || s.maxAbsU > 10
}

const r6 = (x) => (x === null || x === undefined ? null : Number(Number(x).toPrecision(6)))

// ---------------------------------------------------------------------------
// P1：二分搜索 FTCS 稳定性临界 r*
//
// 为什么用脉冲初值而不是单模态 sin：r>0.5 的失稳是**最高网格模态**的性质，
// 而 sin(m=1) 的放大因子 G = 1 − 4r·sin²(π/(2(N−1)))，N=101 时要 r≈2024 才失稳。
// 单模态初值激发不出高频，就测不到 0.5 这个边界。
// ---------------------------------------------------------------------------
async function measureP1() {
  const nodes = 101
  const alpha = 1
  const length = 1
  const dx = length / (nodes - 1)
  const tEnd = 0.1

  const attempt = async (dt) => {
    const res = await solve({
      scheme: 'ftcs', alpha, length, nodes, dt, tEnd,
      initial: PULSE(), boundary: DIRICHLET0, probes: [0.5], recordEvery: 100000,
    })
    return diverged(res)
  }

  // 先扫一遍确认边界确实在区间内，否则二分无意义（也避免把"参数非法"误判成"稳定"）。
  let lo = 1e-5   // r = 0.1，稳定
  let hi = 1e-4   // r = 1.0，发散
  if ((await attempt(lo)) !== false) throw new Error(`P1 下界未表现为稳定: dt=${lo}`)
  if ((await attempt(hi)) !== true) throw new Error(`P1 上界未表现为发散: dt=${hi}`)

  let iterations = 0
  while (hi - lo > 1e-13 && iterations < 80) {
    const mid = (lo + hi) / 2
    if ((await attempt(mid)) === true) hi = mid
    else lo = mid
    iterations += 1
  }

  const dtStar = hi
  const rStar = (alpha * dtStar) / (dx * dx)
  return {
    rMeasured: r6(rStar),
    dtMeasured: dtStar,
    theory: 0.5,
    absoluteDeviationFromTheory: r6(Math.abs(rStar - 0.5)),
    bisection: { iterations, dtLow: lo, dtHigh: hi, nodes, alpha, dx, tEnd, initialKind: 'pulse(center=0.5,width=0.01)' },
    note:
      '二分给出的是"在有限观测时间 tEnd 内幅值增长超过 10 倍"的边界，因此系统性略高于真实临界值：' +
      '网格模态每步放大 |G|≈4r−1，需 4ε·N ≈ ln10 才被判为发散，ε ≈ ln10/(4·tEnd/dt) ≈ 3e-4。' +
      '这是有限观测时间的固有偏差，不是实现缺陷；真实临界值由理论给出为 0.5。',
  }
}

// ---------------------------------------------------------------------------
// P2：收敛阶。固定 r（使时间误差远小于空间误差），逐次细化网格，与解析解比对。
//
// 方法学要点（第一版测出 3.40 就是踩了这个坑）：**不能用均值**。
// 最粗的网格往往还在前渐近区——实测 pairwise 阶数为 [6.20, 2.0002, 2.0001]，
// 前三个数一平均得到 3.4，毫无意义。渐近阶数必须取自足够细的网格。
// 因此这里只用已经进入渐近区的网格，并同时给出全部 pairwise 阶数以供复核。
// ---------------------------------------------------------------------------
async function measureP2() {
  const alpha = 1
  const length = 1
  const r = 0.4
  const tEnd = 0.01
  const x = 0.5

  // 起点取 101：dx=0.01 时已进入渐近区（51 那档明显是前渐近，仅作对照记录）。
  const gridSizes = [101, 201, 401, 801]
  const rows = []
  for (const nodes of gridSizes) {
    const dx = length / (nodes - 1)
    const dt = (r * dx * dx) / alpha
    const res = await solve({
      scheme: 'ftcs', alpha, length, nodes, dt, tEnd,
      initial: SIN, boundary: DIRICHLET0, probes: [x], recordEvery: 100000,
    })
    if (res.status !== 200) throw new Error(`P2 求解失败 nodes=${nodes}: ${JSON.stringify(res.body)}`)
    const numeric = res.body.probes[0].points.at(-1).u

    const ref = await exact({
      alpha, length, initial: SIN, boundary: DIRICHLET0, points: [{ x, t: tEnd }],
    })
    if (ref.status !== 200) throw new Error(`P2 解析解失败: ${JSON.stringify(ref.body)}`)
    const analytic = ref.body.points[0].u

    rows.push({ nodes, dx, dt, steps: res.body.numerics.steps, numeric, analytic, absError: Math.abs(numeric - analytic) })
  }

  const pairwiseOrders = []
  for (let i = 1; i < rows.length; i++) pairwiseOrders.push(Math.log2(rows[i - 1].absError / rows[i].absError))

  // 最小二乘拟合 ln(err) ~ p·ln(dx)：对全部（已进入渐近区的）网格做，抗单点噪声。
  const n = rows.length
  const xs = rows.map((row) => Math.log(row.dx))
  const ys = rows.map((row) => Math.log(row.absError))
  const mx = xs.reduce((a, b) => a + b, 0) / n
  const my = ys.reduce((a, b) => a + b, 0) / n
  const slope = xs.reduce((acc, xi, i) => acc + (xi - mx) * (ys[i] - my), 0) / xs.reduce((acc, xi) => acc + (xi - mx) ** 2, 0)
  const orderFromFinestPair = pairwiseOrders.at(-1)

  return {
    orderMeasured: r6(slope),
    orderFromFinestPair: r6(orderFromFinestPair),
    method: 'least-squares slope of ln|error| vs ln(dx) over the asymptotic grids; primary value = that slope',
    theory: 2,
    absoluteDeviationFromTheory: r6(Math.abs(slope - 2)),
    pairwiseOrders: pairwiseOrders.map(r6),
    fixedRatio: r,
    probe: { x, t: tEnd },
    asymptoticGrids: gridSizes,
    preAsymptoticNote:
      'nodes=51（dx=0.02）测得阶数约 6.2，属前渐近区：该网格分辨单模态正弦尚不充分，' +
      '高阶项未衰减，不能计入。这正是"用均值算阶数"会得出 3.4 这种无意义结果的原因。',
    rows: rows.map((row) => ({ ...row, numeric: r6(row.numeric), analytic: r6(row.analytic), absError: r6(row.absError) })),
  }
}

// ---------------------------------------------------------------------------
// P3：中心差分对流的振荡阈值。固定网格，二分速度 v，找解开始越过边界值的点。
// 判据是"非物理越界"（overshoot/undershoot > 0），而不是"看起来不对"——可判定。
// ---------------------------------------------------------------------------
async function measureP3() {
  const alpha = 1
  const length = 1
  const nodes = 101
  const dx = length / (nodes - 1)
  const steady = {
    scheme: 'ftcs', alpha, length, nodes, steady: true,
    boundary: { left: { kind: 'dirichlet', value: 0 }, right: { kind: 'dirichlet', value: 1 } },
    probes: [0.25, 0.5, 0.75], recordEvery: 1,
  }

  const overshootAt = async (velocity) => {
    const res = await solve({ ...steady, advection: { enabled: true, velocity } })
    if (res.status !== 200) return null
    const s = res.body.summary
    return { overshoot: s.overshoot, undershoot: s.undershoot, peclet: res.body.numerics.peclet }
  }

  const eps = 1e-12
  let lo = 1    // Pe_cell = 0.01，无振荡
  let hi = 2000 // Pe_cell = 20，强烈振荡
  const loProbe = await overshootAt(lo)
  const hiProbe = await overshootAt(hi)
  if (!loProbe || loProbe.overshoot > eps) throw new Error(`P3 下界已有振荡: ${JSON.stringify(loProbe)}`)
  if (!hiProbe || hiProbe.overshoot <= eps) throw new Error(`P3 上界仍未振荡: ${JSON.stringify(hiProbe)}`)

  let iterations = 0
  while (hi - lo > 1e-10 * Math.max(1, hi) && iterations < 80) {
    const mid = (lo + hi) / 2
    const probe = await overshootAt(mid)
    if (!probe) throw new Error(`P3 求解失败 velocity=${mid}`)
    if (probe.overshoot > eps) hi = mid
    else lo = mid
    iterations += 1
  }

  const vStar = hi
  const peCellStar = (vStar * dx) / alpha
  const peDomain = (vStar * length) / alpha
  return {
    pecletCellMeasured: r6(peCellStar),
    velocityMeasured: r6(vStar),
    theory: 2,
    absoluteDeviationFromTheory: r6(Math.abs(peCellStar - 2)),
    pecletDomain: r6(peDomain),
    bisection: { iterations, velocityLow: lo, velocityHigh: hi, nodes, dx, alpha },
    thresholdDefinition: 'overshoot（解越过右边界值 1）首次变为正',
    note:
      '被测服务返回的 numerics.peclet 是**网格** Péclet 数 v·dx/α；本项测出的正是它的阈值 2。' +
      '注意与域 Péclet 数 v·L/α 区分：两者相差 (N−1) 倍。',
  }
}

// ---------------------------------------------------------------------------
// P4：两端绝热（Neumann=0）时，离散总热量 ΣuᵢΔx 应精确守恒。
// 若边界按朴素幽灵点法写（系数 2r 而非 r），这个量会缓慢漂移——所以它是一条有判别力的不变量。
// ---------------------------------------------------------------------------
async function measureP4() {
  const alpha = 1
  const length = 1
  const nodes = 101
  const dx = length / (nodes - 1)
  const r = 0.4
  const dt = (r * dx * dx) / alpha
  const tEnd = 0.05

  const res = await solve({
    scheme: 'ftcs', alpha, length, nodes, dt, tEnd,
    initial: PULSE(0.02),
    boundary: { left: { kind: 'neumann', value: 0 }, right: { kind: 'neumann', value: 0 } },
    probes: [0.25, 0.5], recordEvery: 100000,
  })
  if (res.status !== 200) throw new Error(`P4 求解失败: ${JSON.stringify(res.body)}`)
  const s = res.body.summary

  return {
    heatDriftRelativeMeasured: s.heatDriftRelative,
    theory: 0,
    tolerance: 1e-12,
    totalHeatInitial: s.totalHeatInitial,
    totalHeatFinal: s.totalHeatFinal,
    steps: res.body.numerics.steps,
    note:
      '判据是相对漂移 < 1e-12。该判据有判别力：若边界按朴素幽灵点法（next[0] = u[0] + 2r(u[1]−u[0])）' +
      '实现，Σ 的变化量为 −r(u₀−u₁+u_{N−1}−u_{N−2})，一般不为零，漂移会远大于 1e-12。',
  }
}

// ---------------------------------------------------------------------------
// 负路径：没有闭式解时 Oracle 必须 422，绝不能返回数值解冒充解析解。
// ---------------------------------------------------------------------------
async function probeNoClosedForm() {
  const neumann = await exact({
    alpha: 1, length: 1, initial: SIN,
    boundary: { left: { kind: 'neumann', value: 0 }, right: { kind: 'neumann', value: 0 } },
    points: [{ x: 0.5, t: 0.01 }],
  })
  const weird = await exact({ alpha: 1, length: 1, initial: { kind: 'pulse' }, boundary: DIRICHLET0, points: [{ x: 0.5, t: 0.01 }] })
  return {
    neumannRequestStatus: neumann.status,
    neumannRequestCode: neumann.body?.error?.code ?? null,
    pulseRequestStatus: weird.status,
    pulseRequestCode: weird.body?.error?.code ?? null,
    pass: neumann.status === 422 && weird.status === 422,
    note: '红线：无闭式解必须 422。谎报基准比没有基准更糟——那会让整个验证失效。',
  }
}

// ---------------------------------------------------------------------------
async function main() {
  const health = {
    solver: (await get(SOLVER, '/health')).body,
    oracle: (await get(ORACLE, '/health')).body,
  }
  console.log(`[solver] ${JSON.stringify(health.solver)}`)
  console.log(`[oracle] ${JSON.stringify(health.oracle)}`)

  console.log('\nP1 二分搜索 FTCS 稳定性临界 ...')
  const P1 = await measureP1()
  console.log(`   r* = ${P1.rMeasured}   （理论 0.5，偏差 ${P1.absoluteDeviationFromTheory}）`)

  console.log('P2 测定收敛阶 ...')
  const P2 = await measureP2()
  console.log(`   order = ${P2.orderMeasured}   （理论 2，偏差 ${P2.absoluteDeviationFromTheory}）`)

  console.log('P3 二分搜索对流振荡阈值 ...')
  const P3 = await measureP3()
  console.log(`   Pe_cell* = ${P3.pecletCellMeasured}   （理论 2，偏差 ${P3.absoluteDeviationFromTheory}）`)

  console.log('P4 测定绝热守恒漂移 ...')
  const P4 = await measureP4()
  console.log(`   heatDriftRelative = ${P4.heatDriftRelativeMeasured}`)

  console.log('负路径：无闭式解是否 422 ...')
  const noClosedForm = await probeNoClosedForm()
  console.log(`   neumann=${noClosedForm.neumannRequestStatus} pulse=${noClosedForm.pulseRequestStatus} pass=${noClosedForm.pass}`)

  const groundTruth = {
    generatedAt: new Date().toISOString(),
    measuredBy: 'tools/measure-ground-truth.mjs（独立于智能体运行，不走 AGH）',
    services: health,
    acceptance: {
      P1: { measurement: P1.rMeasured, theory: 0.5, tolerance: 0.002, pass: Math.abs(P1.rMeasured - 0.5) <= 0.002 },
      P2: { measurement: P2.orderMeasured, theory: 2, tolerance: 0.15, pass: Math.abs(P2.orderMeasured - 2) <= 0.15 },
      P3: { measurement: P3.pecletCellMeasured, theory: 2, tolerance: 0.1, pass: Math.abs(P3.pecletCellMeasured - 2) <= 0.1 },
      P4: { measurement: P4.heatDriftRelativeMeasured, theory: 0, tolerance: 1e-12, pass: P4.heatDriftRelativeMeasured <= 1e-12 },
    },
    P1_ftcsStabilityThreshold: P1,
    P2_convergenceOrder: P2,
    P3_pecletOscillationThreshold: P3,
    P4_energyConservation: P4,
    oracleNoClosedFormPath: noClosedForm,
  }

  const outDir = join(root, 'ground-truth')
  mkdirSync(outDir, { recursive: true })
  const outFile = join(outDir, 'ground-truth.json')
  writeFileSync(outFile, JSON.stringify(groundTruth, null, 2) + '\n', 'utf8')

  const failures = Object.entries(groundTruth.acceptance).filter(([, v]) => !v.pass)
  console.log(`\n写入 ${outFile}`)
  console.log(`验收：${Object.keys(groundTruth.acceptance).length - failures.length}/${Object.keys(groundTruth.acceptance).length} 通过`)
  for (const [k, v] of failures) console.log(`  FAIL ${k}: 实测 ${v.measurement}，理论 ${v.theory}，容差 ${v.tolerance}`)
  if (!noClosedForm.pass) console.log('  FAIL oracleNoClosedFormPath：无闭式解未返回 422')
  process.exit(failures.length === 0 && noClosedForm.pass ? 0 : 1)
}

main().catch((e) => {
  console.error('测量失败：', e)
  process.exit(2)
})
