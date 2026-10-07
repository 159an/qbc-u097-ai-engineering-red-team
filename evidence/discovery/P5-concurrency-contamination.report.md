# AGH 执行记录分析报告 — P5-concurrency-contamination.trajectory.raw.json

- 生成时间：2026-10-03T09:08:52.170Z
- 断言集：`normal`
- 事件总数：122（解析失败 0）
- 模型：`agnes-3.0-flash`　路由：`account-<redacted>`
- 最大连续步骤：5　结束原因：turn=`completed`

## 断言结果

| 断言 | 结果 | 证据 |
| --- | --- | --- |
| 仅使用 Agnes 模型（agnes-*） | PASS | agnes-3.0-flash |
| 推理请求发出且返回 200 | PASS | status=200 req=51265e074929a6ee4a24298b30871c75; status=200 req=6ffed8e0f68ea22170c923541c1622e6; status=200 req=f215b9acfc9fc6ba4fee8978a09aba2d; status=200 req=3ca3d14e69ecd65ff032f5bb2fb1f5a5; status=200 req=083a34aa661e4a28df07887d802d6538 |
| 存在工具调用链 | PASS | 8 次调用 |
| 工具返回与调用一一对应 | PASS | 0 次缺返回 |
| 工具级校验全部通过 | PASS | 8 条 tool 级 signal |
| 终态符合预期（completed） | PASS | 实际 turn/end reason = completed |
| 连续步骤 >= 3 | PASS | 实际最大 step=5 |

## 工具调用链（按发生顺序）

| # | seq | 工具 | toolUseId | 有返回 | isError | 被拒绝 | 返回字节 | 校验 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 24 | `solver_solve` | `t1-49dfbc2eaafefafa156c0c233d9477e4` | 是 | false | 否 | 132 | pass |
| 2 | 25 | `solver_solve` | `t2-a2817407c8b3f5afafbf753a07bb0338` | 是 | false | 否 | 132 | pass |
| 3 | 26 | `solver_solve` | `t0-41a1b7eca4291db53343f81080ea2cd8` | 是 | false | 否 | 132 | pass |
| 4 | 53 | `solver_solve` | `t5-7f30c721f4b2c5430c6c0acf732c31e4` | 是 | false | 否 | 7874 | pass |
| 5 | 54 | `solver_solve` | `t4-a4402566f5ff222878f6e5431a771169` | 是 | false | 否 | 7894 | pass |
| 6 | 55 | `solver_solve` | `t3-2a9ed6653e96b164e1238f34c5315805` | 是 | false | 否 | 7901 | pass |
| 7 | 79 | `solver_burst` | `t6-aa207dea57d734ab3f2b3d0238703443` | 是 | false | 否 | 2245 | pass |
| 8 | 99 | `solver_solve` | `t7-731e07c08bf48afedada3d2ae141e5d1` | 是 | false | 否 | 7901 | pass |

工具调用统计：`solver_solve`×7、`solver_burst`×1

## 计费账本（真实 API 调用凭据）

| seq | 用途 | 模型 | input | output | cacheRead | ttft(ms) | 时长(ms) | status | x-request-id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 22 | inference | agnes-3.0-flash | 7231 | 657 | 3072 | 1766 | 11793 | 200 | 51265e074929a6ee4a24298b30871c75 |
| 51 | inference | agnes-3.0-flash | 1106 | 686 | 10240 | 7802 | 17291 | 200 | 6ffed8e0f68ea22170c923541c1622e6 |
| 77 | inference | agnes-3.0-flash | 21317 | 386 | 10240 | 3130 | 9327 | 200 | f215b9acfc9fc6ba4fee8978a09aba2d |
| 97 | inference | agnes-3.0-flash | 1784 | 859 | 31488 | 1215 | 14885 | 200 | 3ca3d14e69ecd65ff032f5bb2fb1f5a5 |
| 117 | inference | agnes-3.0-flash | 7634 | 1313 | 33024 | 22787 | 58680 | 200 | 083a34aa661e4a28df07887d802d6538 |

合计 tokens：input 39072、output 3901、cacheRead 88064

## 最终回答（节选）

```text
**Verification complete.** All numbers below are taken directly from tool returns.

## 1. 串行 3 次同参数调用（solver_solve ×3）

固定参数：`nodes=41, length=2, alpha=0.01, dt=0.0005, tEnd=0.5, 边界两侧 Dirichlet=0, 初始 sin 单模`

| 次序 | taskId | summary.maxAbsU |
|---|---|---|
| 第 1 次 | t-2-mus64vfh | 0.966063149209155 |
| 第 2 次 | t-1-mus64vfe | 0.9708398293547366 |
| 第 3 次 | t-3-mus64vfj | 0.9636836296250979 |

三次结果**互不相同**（差值在 1e-2~1e-3 量级，远超浮点噪声）。

## 2. 并发 6 次（solver_burst，concurrency=3）

- **statusCounts**: `{"200": 6}`（全部成功，非服务端错误）
- **distinctResponseBodies**: 6（6 个响应体全不同）
- **distinctMaxAbsUValues**: 6
- **consistent**: `false`
- **逐请求 maxAbsU**: 0.9355824505371837, 0.9309792420769322, 0.9286861380074045, 0.9083007066268053, 0.8993847384491936, 0.8949596282574915
- 工具给出的 verdict：*"INCONSISTENT — identical requests did NOT return identical results; this is cross-request state contamination, not floating-point noise"*

## 3. 判定：不满足同请求同结果

判据：
- 纯函数语义要求：同输入 → 同输出。此处 3 次串行即得 3 个不同值；并发 6 次得 6 个不同值、6 个不同响应体。
- 数值证据：串行 maxAbsU 三个互异（0.9661 / 0.9708 / 0.9637）；并发时 6 个 bodyHash 全不同，且逐请求的 `totalHeatInitial` 依次递减（1.2264 → 1.1587）。

关键旁证（排除"精度问题"）：`totalHeatInitial` 是**请求声明的初始条件**（sin 单模、幅度 1）算出的应有初值，理论上是确定的；但实测它随调用次数变化（1.266 → 1.273 → 1.257 → 1.139……），说明服务端并非每次从请求参数重建初始场，而是**沿用了上一次（或并发改写中的）内部场状态**。

## 4. 缺陷类别与实际影响

- **类别**：这不是数值精度/收敛性问题，而是**跨请求状态污染（服务端共享可写状态）**——服务端持有全局/单例的求解器状态，`/solve` 没有先按请求参数重置初始条件，而是从残留场继续演化（或并发请求同时读写同一场）。违反 HTTP 无状态性。
- **对使用者的实际影响**：
  - 结果不可复现：同一参数在不同时刻/并发下得到不同答案，任何"验证性"调用（重跑核对）都会"失败"；
  - 缓存/重试语义被破坏：网关重试、结果缓存都会混入"上次请求的解"；
  - 并发场景下答案随并发时序漂移（本次 6 个值单调递减即此现象），下游基于"同一请求同一结果"的假设（如比对测试、回归基线、多实例负载均衡后取"任意一节点"结果）全部失效；
  - 甚至掩盖真实 bug：用户以为数值在"噪声范围内波动"，而实际是系统性错误。

## 5. 最小复现（2 次请求即可稳定复现）

可照抄步骤：
1. 用 `solver_solve` 发送参数 A：`nodes=41, length=2, alpha=0.01, dt=0.0005, tEnd=0.5, leftKind=dirichlet/leftValue=0, rightKind=dirichlet/rightValue=0, initialKind=sin, initialModes=1, probes=[0.25,0.5,0.75]`，记录第一次返回的 `summary.maxAbsU`。
2. 用 `solver_solve` 发送**完全相同**的参数 A，记录第二次返回的 `summar
```
