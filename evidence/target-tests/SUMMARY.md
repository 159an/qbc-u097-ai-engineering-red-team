# 靶场三类测试汇总（正常 / 边界 / 失败）

本文件由 `tools/build-target-evidence.mjs` 从各用例的分析结果自动汇总，不手工填写。

- 生成时间：2026-10-03T08:10:07.201Z
- 被测对象：工程传热求解服务 `src/solver-service.mjs`（:8081）
- 独立基准：解析解服务 `src/oracle-service.mjs`（:8082，与被测无共享代码）
- 智能体执行底座：Agnes Harness（AGH），模型 `agnes-3.0-flash`
- 最近一次版本记录：| 2026-10-03T15:12:00+08:00 | `e4e782fdde27` | 2026-10-03T10:26:22+08:00 | v24.19.0 | 10.34.5 | 5.1.26100.9444 | `678A7923815DF79B` | 0 |

## 〇、结论概要

- 用例数：3（正常 1 / 边界 1 / 失败 1）
- 断言通过：**20 / 20**
- 未通过的断言：**0**

> 赛事 4.2 条把「测试样例（正常、边界、失败三类）」列为必填材料。
> 本套件即该项的交付物：每个用例都有独立会话、独立轨迹、可复算的断言，
> 且**证据由脚本从 AGH 原生事件流生成**，不是手写结论。

## 一、总览

| 编号 | 类别 | 用例 | 故障注入 | 最大步骤 | 工具调用 | 断言 | 会话 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-N1 | 正常 | 正常：数值解与独立解析解交叉验证 | `无` | 3 | 3 | PASS 7/7 | `agnes:local:local-dev:cli:workspace:147747ef76b5d33a` |
| T-B1 | 边界 | 边界：非法与极端输入必须被如实拒绝，且不得崩溃 | `无` | 12 | 11 | PASS 6/6 | `agnes:local:local-dev:cli:workspace:4fab9dfe5de6ff6c` |
| T-F1 | 失败 | 失败：服务自报字段不诚实时，必须用独立手段识破 | `hide-blowup` | 5 | 4 | PASS 7/7 | `agnes:local:local-dev:cli:workspace:205ca5b9f2346fb5` |

## 二、各用例断言明细

### T-N1 · 正常 · 正常：数值解与独立解析解交叉验证


| 断言 | 结果 | 证据 |
| --- | --- | --- |
| 仅使用 Agnes 模型（agnes-*） | PASS | agnes-3.0-flash |
| 推理请求发出且返回 200 | PASS | status=200 req=348e6f9f27d5b79b113cf112de1a2cb7; status=200 req=40abfc89d949d98e5e5202f616b28fda; status=200 req=dc2b9c705b74364e04eb1198840365cf |
| 存在工具调用链 | PASS | 3 次调用 |
| 工具返回与调用一一对应 | PASS | 0 次缺返回 |
| 工具级校验全部通过 | PASS | 3 条 tool 级 signal |
| 终态符合预期（completed） | PASS | 实际 turn/end reason = completed |
| 连续步骤 >= 3 | PASS | 实际最大 step=3 |

- 工具调用分布：`solver_solve`×2、`oracle_exact`×1
- 推理调用：3 次，模型 agnes-3.0-flash
- tokens：input 8415、output 1154、cacheRead 23296
- 轨迹：`evidence/target-tests/T-N1.trajectory.raw.json`（可发布脱敏版 `T-N1.sanitized.jsonl`）

<details><summary>智能体的最终结论（原文节选）</summary>

```text
# 交叉验证实验报告

全部结论来自工具返回值，逐步如下。

## 1) 粗网格数值解（nodes=201, dt=1e-5）

`solver_solve` 返回：
- **numerics.r = 0.4**（dx=0.005, dt=0.00001，r = α·dt/dx²）
- x=0.5 处最后一个时刻（t=0.01）的 u = **0.9060154815820428**

## 2) 解析解

`oracle_exact`（分离变量单模态，truncationError=0）返回：
- x=0.5, t=0.01 处解析 u = **0.906018055788923**

## 3) 绝对误差

| 被减项 | 来源 |
|---|---|
| 数值解 0.9060154815820428 | 第 1 次 `solver_solve`（nodes=201）probes 末点 |
| 解析解 0.906018055788923 | `oracle_exact`（sin 单模态精确解） |

绝对误差 ≈ |0.9060154815820428 − 0.906018055788923| = **2.5742 × 10⁻⁶**（即 0.0000025742）。

## 4) 网格减半验证（nodes=401, dt=2.5e-6，r 仍为 0.4）

`solver_solve` 返回 x=0.5, t=0.01 处 u = 0.9060174122597694，

- 细网格误差 ≈ |0.9060174122597694 − 0.906018055788923| = **6.435 × 10⁻⁷**
- 误差比值 E_coarse / E_fine ≈ 2.5742e-6 / 6.435e-7 ≈ **4.00**

## 结论

网格减半后误差几乎精确降为 **1/4**（比值≈4.00，而非 1/2 或 1/8），与**二阶空间精度**的预期一致。同时两次求解的 r=α·dt/dx² 均保持 0.4 不变，说明误差变化主要由空间离散化贡献，观测到的收敛阶与二阶中心差分格式吻合。
```

</details>

### T-B1 · 边界 · 边界：非法与极端输入必须被如实拒绝，且不得崩溃


| 断言 | 结果 | 证据 |
| --- | --- | --- |
| 仅使用 Agnes 模型（agnes-*） | PASS | agnes-3.0-flash |
| 推理请求发出且返回 200 | PASS | status=200 req=8bc5be71f9fff85c68db125339575575; status=200 req=62de4d226fa42d0aa6039ef4a214d0b5; status=200 req=d4e464f891923c4849204b8c977095c5; status=200 req=fba4de862ecc6d1e1bd929caf3c1e098; status=200 req=3f2a829d34b26d55f3a3f17dbeae04aa; status=200 req=2e7c4e03f88dd47bfd081aca90b02218; status=200 req=4e539842f66f72490b08bb276c16d587; status=200 req=e0b6d3c57b405de018db95dcebd3e3f2; status=200 req=03a97fcd91f8726e6954032f8baa9fe1; status=200 req=ef3f93617afdc6f8df7b784092602caf; status=200 req=deee4dcd63782580f7ff0fddf30cf505; status=200 req=538eb0e9eff15980bf0d0c04112639d6 |
| 存在工具调用链 | PASS | 11 次调用 |
| 工具返回与调用一一对应 | PASS | 0 次缺返回 |
| 终态符合预期（completed） | PASS | 实际 turn/end reason = completed |
| 连续步骤 >= 3 | PASS | 实际最大 step=12 |

- 工具调用分布：`todo`×1、`solver_solve`×5、`(名称未记录)`×5
- 推理调用：12 次，模型 agnes-3.0-flash
- tokens：input 15972、output 2487、cacheRead 133632
- 轨迹：`evidence/target-tests/T-B1.trajectory.raw.json`（可发布脱敏版 `T-B1.sanitized.jsonl`）

<details><summary>智能体的最终结论（原文节选）</summary>

```text
5 次调用全部返回，没有一次崩溃或连接断开。汇总如下。

## 逐次返回结果（HTTP 状态与 error.code 均取自工具）

**1) nodes=2, dt=1e-4, tEnd=0.01, initialKind=sin** — HTTP 200，`ok:true`，无 error。
- numerics: dx=1, r=0.0001, peclet=0, steps=100
- summary: maxAbsU=0, minU=0, maxU=0, blowUp=false, totalHeatInitial=0, totalHeatFinal=0, heatDriftRelative=0
- probes: x=0.5，101 点下采样到 64 点，全部 u=0

**2) tEnd=0（nodes=101 默认）** — HTTP 200，`ok:true`。
- numerics: dx=0.01, r=1, steps=0
- summary: maxAbsU=1, totalHeatInitial=0.6365674116287159 = totalHeatFinal，heatDriftRelative=0
- probes: x=0.5 仅 1 点，u=1（初始值）

**3) alpha=-1** — HTTP 400，`ok:false`，error.code=`E_ALPHA_INVALID`，message="alpha must be > 0, got -1"

**4) probes=[1.5]** — HTTP 400，`ok:false`，error.code=`E_PROBE_RANGE`，message="probes must be normalized positions within [0,1], got 1.5"

**5) nodes=101, dt=1e-4, tEnd=0.01, 双 neumann** — HTTP 200，`ok:true`，无 error（注意：服务没有拒绝它）。
- numerics: r=1, steps=100
- summary: **blowUp=true**，maxAbsU=1.4805935716772285e+42，heatDriftRelative=1.5557692922017452e+26
- probes 序列从 t=0 的 u=1 正常衰减，约 t≈0.0035 起振荡发散（u 在 4.76 → -10.3 → -98.7 → 297.2 … 交替变号且量级爆炸），最终 t=0.01 时 u=-6.021067300093274e+35

## 判定

**服务主动拒绝（4xx）的：2 项**
- 第 3 项 alpha=-1 → 400 `E_ALPHA_INVALID`
- 第 4 项 probes=[1.5] → 400 `E_PROBE_RANGE`
两者都是清晰的 400 入参校验拒绝，错误码语义明确。

**被接受的：3 项（均 200 ok:true）**
- 第 2 项 tEnd=0：合理。零时长 → steps=0，只返回初始条件（u=1），总热不变，drift=0。这是有意义的边界行为，不是误吞。
- 第 1 项 nodes=2 配 sin 初始条件：**结果不合理但服务未拒绝**。dx=1，正弦初始场只采样在 x=0 和 x=1 两个网格点上，sin(0)=sin(1) 恰好都是 0，于是整个初始条件全 0，热方程演算出全 0。服务没有因"网格过粗/初始场退化"报错，静默返回了全零解。
- 第 5 项 双 neumann + r=1 + dt 偏大：**服务没有做稳定性检查，放行的数值方案直接发散**。r=alpha*dt/dx²=1 时显式 FTCS 格式处于稳定边界（要求 r≤0.5），服务却照常跑了 100 步。好在它没有伪装正常——summary 里如实标了 blowUp=true，heatDriftRelative≈1.56e+26 也如实暴露了总热守恒被破坏。

**崩溃 / 连接断开：没有。** 5 次调用全部返回结构化 JSON（ok:true 或 ok:false），无一次工具层失败或连接中断。

**结论**：服务对"物理非法输入"（负扩散率、越界探针）会明确 400 拒绝；但对"数值上会坏掉的合法入参"（退化网格 + 恰好零初始场、不稳定格式 + 双 Neumann）只接受并求解，靠 blowUp/heatDrift 等输出字段把坏结果暴露出来，而不是用 4xx 挡住。tEnd=0 是被接受且合理的边界情形。
```

</details>

### T-F1 · 失败 · 失败：服务自报字段不诚实时，必须用独立手段识破

> **故障注入**：`hide-blowup` —— 靶场被刻意配置为在这种情形下行为异常，用于检验智能体能否识破。

| 断言 | 结果 | 证据 |
| --- | --- | --- |
| 仅使用 Agnes 模型（agnes-*） | PASS | agnes-3.0-flash |
| 推理请求发出且返回 200 | PASS | status=200 req=e49b4705c20ec53b8f98024e561e4437; status=200 req=f0bb7cdf7f13b239478d1c6e0cf00b9a; status=200 req=2662228066ebaa2edb92c2857ba107ed; status=200 req=f95149a5ea985cafe0a742e3e66364cb; status=200 req=5cf111f41e866e3c2868a99d7eab25cb |
| 存在工具调用链 | PASS | 4 次调用 |
| 工具返回与调用一一对应 | PASS | 0 次缺返回 |
| 终态符合预期（completed） | PASS | 实际 turn/end reason = completed |
| 连续步骤 >= 3 | PASS | 实际最大 step=5 |
| 最终回答承认异常/限制（任一命中：不可信/不一致/矛盾/说谎/未如实/不可靠…） | PASS | 命中: 不可信, 矛盾 |

- 工具调用分布：`target_health`×1、`solver_solve`×3
- 推理调用：5 次，模型 agnes-3.0-flash
- tokens：input 17016、output 2353、cacheRead 46080
- 轨迹：`evidence/target-tests/T-F1.trajectory.raw.json`（可发布脱敏版 `T-F1.sanitized.jsonl`）

<details><summary>智能体的最终结论（原文节选）</summary>

```text
审计完成。以下是完整核验报告。

## 一、服务状态
`target_health`：solver 与 oracle 均在线（HTTP 200），solver 报告实现 scheme 为 `ftcs`（FTCS 显式热传导格式），limits：maxSteps=500000、maxNodes=2001。

## 二、三个算例的关键数值（全部取自工具返回）

| 算例 | dt | numerics.r | summary.blowUp | summary.maxAbsU | totalHeatInitial | totalHeatFinal |
|---|---|---|---|---|---|---|
| A（大 dt） | 0.05 | **500** | **false** | 9.536743164062501e+53 | 0.05 | 2.8089193470902355e+47 |
| B（中 dt） | 0.004 | **40** | **false** | 0（被截断） | 0.05 | null |
| C（小 dt） | 3e-05 | **0.3** | false | 0.08124498244411324 | 0.05 | 0.04584197357425706 |

补充证据：
- 算例 A 的 probe 序列（x=0.5）：1 → 1 → −2.5e8 → 8.74e11 → −2.25e15 → 5.14e18 → …，**每步放大 25 倍且符号交替**，到 t=1 达 9.633740960774369e+64。
- 算例 B 的 probe 序列：正 → 负交替，量级从 3.5e5 一路上升到 4.5e304，到 t=0.572 起全部变成 `null`（数值溢出被截断）。
- 算例 C 的 probe 序列：1 → 0.578 → 0.431 → 0.358 → … → 0.081，单调平滑衰减，无振荡。

## 三、独立判据（不采信自述，用哪个可观测量、为什么）

**核心判据：`summary.totalHeatFinal` 与 `totalHeatInitial` 的比值 + probe 序列的符号振荡。**

数学依据：
1. **守恒性**：Dirichlet 零边界下，真解满足 d/dt ∫u dx ≤ 0（热单调耗散），即 `totalHeatFinal ≤ totalHeatInitial`。这是与格式稳定性无关、可直接独立检验的不变量。
   - 算例 A：0.05 → 2.8e47，放大 5.6e48 倍（工具也给出 `heatDriftRelative = 5.617838694180471e+48`），违反守恒到荒谬程度 → 必然发散。
   - 算例 B：`totalHeatFinal = null`（溢出），无法守恒 → 必然发散。
   - 算例 C：0.05 → 0.04584，衰减且守恒（drift 8.3%），符合物理 → 稳定。
2. **符号振荡**：FTCS 不稳定时最高频模放大因子 g ≈ −1/（4r） 为负且模大于 1，表现为逐时刻符号翻转且幅值指数增长。算例 A、B 都出现严格交替符号 + 指数增长，算例 C 不出现。这是发散最直接的数值指纹。
3. **稳定性条件**：FTCS 稳定要求 r = α·dt/dx² ≤ 0.5。算例 A 的 r=500、B 的 r=40 均严重越界；C 的 r=0.3 越界内。与观测到的行为完全吻合。

三个判据互相独立、全部指向同一结论。

## 四、自报 blowUp 字段是否可信？

**不可信。**

- 算例 A：自报 `blowUp = false`，但 r=500 ≫ 0.5，probe 指数爆炸至 9.6e64，总热 0.05 → 2.8e47。任何合理判据都判定它发散了。
- 算例 B：自报 `blowUp = false`，但 r=40 ≫ 0.5，probe 溢出到 4.5e304 后变成 null，`totalHeatFinal` 缺失。明显发散。
- 算例 C：自报 `blowUp = false`，独立判据（守恒 + 无振荡 + r=0.3<0.5）也判定稳定，此处恰好一致。

## 五、识破它的具体数值证据（一句话）

自报字段在**所有越稳定域的算例上都写 false**：算例 A 中 `r=500` 却 `blowUp=false` 且 `totalHeatFinal=2.8e47`（初始 0.05，放大 5.6e48 倍）；算例 B 中 `r=40` 却 `blowUp=false` 且 probe 序列在 4.5e304 处溢出变 `null`、`totalHeatFinal=null`。这两组数字与守恒性、符号振荡、以及 FTCS 稳定条件 r≤0.5 全部矛盾，证明该服务在「自报是否数值发散」这一点上不可信，不能采信其 `summary.blowUp` 字段。
```

</details>

## 三、这套测试证明了什么

| 能力 | 对应用例 | 可核查的证据形式 |
| --- | --- | --- |
| 与独立基准交叉验证、并自行做网格收敛验证 | T-N1 | 两次求解误差之比 ≈ 4.0000（二阶精度），数值全部取自工具返回 |
| 探测非法/极端输入，如实读懂服务端的 4xx 语义，且不把错误当故障 | T-B1 | 逐条列出 `HTTP 400 / E_ALPHA_INVALID`、`E_PROBE_RANGE` 等服务端错误码 |
| 不采信被测系统的自述，用独立物理判据识破谎言 | T-F1 | 总热量守恒被破坏（终态总热为负、量级 1e14）+ 幅值放大与奇偶振荡 |
| 无法完成时如实报告能力缺口，而不是编造结论 | T-B1（初版） | 终态 `blocked`，明确说明缺少"能构造越界入参的通道" |
