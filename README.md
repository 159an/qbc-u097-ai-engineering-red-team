# QBC / U097 — AI Engineering Red Team

> 2026 江苏省人工智能学会黑客松 · 本科生组 · 队伍 **QBC** · 参赛编号 **U097**

**一句话定义**：让 AI 像"工程红队"一样主动攻击一个**可执行、可判定的工程系统**——自主设计实验、调用工具、观察反馈、证明失效条件，并通过「攻击 → 最小反例 → 修复 → 再攻击」闭环探索系统的可靠性边界。

## 首个验证对象：工程传热求解服务

> **方向变更说明**：初稿的验证对象是"虚拟电商业务系统"，现已**改为工程传热求解服务**。
> 原因：数值求解器的"对错"由**解析解**客观判定，不需要人肉判断业务规则；它的失效边界（稳定性、边界处理、并发隔离、超时语义）都有严格数学定义，因此"发现 → 复现 → 修复 → 再验证"是可自动判定、可复现的。

> **实现归属说明（2026-10-03 夜间对齐）**：本 README 此前描述的 `services/solver/`（FastAPI/Python）
> 是一份**规划**；实际建成并已验证的实现位于 `src/solver-service.mjs` 与 `src/oracle-service.mjs`
> （Node.js，零第三方依赖）。本节以下内容已按**实际建成的实现**校正，
> 并标出三处被实测推翻的原设计。若后续决定改用 Python 实现，请连同本节一起更新。

### 被测系统 SUT — `src/solver-service.mjs`（D1）

| 项 | 内容 |
| --- | --- |
| 形态 | Node.js 内置 `http`，默认 `127.0.0.1:8081`，**零第三方依赖**（只用 `node:http`） |
| 数值格式 | **只实现 FTCS**。`/health` 会列出 `btcs` / `cn`，但 `/solve` 对它们返回 `400 E_SCHEME_NOT_IMPLEMENTED` |
| 为什么只实现一种 | **刻意的**：宁可如实说不支持，也不假装实现。假装实现会被智能体发现算得不对，反而打穿我们自己的作品（见 §已知局限） |
| 覆盖 | Dirichlet / Neumann 边界、对流项（中心差分）、稳态模式、严格参数校验、总热量守恒量输出 |
| **设计红线** | 默认配置必须是一个**正确、诚实**的求解器：非法参数报错、并发请求互不污染、发散如实上报。它是"待攻破的对象"，不是"故意写错的玩具" |

**⚠️ 原设计已被实测推翻之一：不设 `r = α·Δt/Δx²` 上限保护。**
初稿写的是"越界 CFL 触发保护"。这与本作品的核心目标**直接矛盾**——`r > 0.5` 时 FTCS 发散是数值方法
**固有的数学边界**，智能体的任务就是自己二分搜索出这个临界值；若服务在该区间报错拒绝，
Agent 读一眼错误信息就知道了，那不是"自主发现"而是"读文档"。
因此服务**照常计算并如实上报 `blowUp`**。（实测：智能体据此自定判据二分 15 次，测得 r\* ≈ 0.5001356。）

**⚠️ 原设计已被实测推翻之二：Neumann 边界必须用通量形式。**
朴素幽灵点写法 `next[0] = u[0] + 2r(u[1]−u[0])` 不严格守恒（Σ 变化量为
`−r(u₀−u₁+u_{N−1}−u_{N−2})`）；已改为有限体积通量形式（系数是 `r` 而非 `2r`），实测漂移为 0。

### 验证基准 Oracle — `src/oracle-service.mjs`（D2）

| 项 | 内容 |
| --- | --- |
| 实现 | **闭式解析解**：分离变量单模态精确解 + 稳态对流扩散指数解。**不做任何时间推进** |
| 独立性 | 与被测求解器**结构独立**：两个进程、两套算法（闭式解析 vs 数值离散）、无共享代码 |
| 无闭式解时 | 返回 **422**，**绝不用数值解冒充解析解** |
| 实测 | Neumann 与 pulse 两种无闭式解的请求均返回 422 |

**⚠️ 原设计已被实测推翻之三：Oracle 必须校验 `initial.kind`。**
初版实现忽略了这个字段，导致 `pulse` 请求会落到正弦公式上返回 200——
等于把"正弦解"当成"脉冲解的基准"返回，正是我们自己划定的"谎报基准"红线。已改为 422。

### 故障注入开关 — `src/solver-service.mjs` 内的环境变量（D3）

环境变量控制，**默认全部关闭**（即"默认系统是正确的"）：

| 环境变量 | 打开后的行为 | 实测是否可被识破 |
| --- | --- | --- |
| `QBC_FAULT_HIDE_BLOWUP=on` | 发散时仍报 `blowUp: false`（**谎报自身状态**） | ✅ 智能体用「总热量守恒 + 幅值奇偶振荡」两个独立判据识破，并明确说出"服务在这一点上不可信" |
| `QBC_FAULT_SHARED_STATE=on` | 共享缓冲只在首次分配时写初值，**跨请求污染** | ✅ 智能体用串行 3 次 + 并发 6 次检出，定性为"跨请求状态污染"并给出 2 次请求的最小复现 |
| `QBC_FAULT_SILENT_CLAMP=on` | 负 `alpha` 静默取绝对值，**不报 400** | ✅ 已实测（2026-10-06）：`alpha=-1` 由 400 变 **200**，响应 `r=0.4` 表明 alpha 被静默取绝对值 → `evidence/14-fault-switches-silent-clamp-partial-on-timeout.txt` |
| `QBC_FAULT_PARTIAL_ON_TIMEOUT=on` | 超时返回部分结果**但不标记 incomplete** | ✅ 已实测（2026-10-06）：`tEnd/dt=1,000,000` 步由 400 变 **200**，实际只跑 `steps=500000` 却仍报 `status=completed`、**无 incomplete 标记**，末点 `u=null` → 同上证据文件 |

> **`CFL_GUARD` 已被替换为 `HIDE_BLOWUP`**：原设计的"关闭稳定性保护"与上面第一条红线冲突
> （保护开着就测不出边界）。换上的 `HIDE_BLOWUP` 反而更有价值——它让**服务谎报自身状态**，
> 智能体只能靠与解析解/物理不变量比对来识破，这正是「异常处理」评分项最好的素材。

红队的任务就是：在不看这些开关的前提下，**用实验证明**它们存在（发现 → 最小复现 → 修复 → 再攻击）。

## 任务闭环

```
Plan → Attack → Execute → Observe → Verify → Minimize → Explain → Repair → Re-attack
```

| 阶段 | 本项目中的落点 |
| --- | --- |
| Plan | 读求解服务的接口契约与物理假设，形成攻击计划 |
| Attack | 参数边界、CFL 越界、并发污染、边界条件组合、与解析解的偏差 |
| Execute | 经 AGH 插件工具调用 HTTP 接口与基准服务 |
| Observe | 响应、状态码、耗时、数值序列、`numerics` / `summary` 字段 |
| **Verify** | 与**解析解基准**比对，或检验物理不变量（守恒、极值原理、对角占优） |
| Minimize | 把失败样例压缩到最小的 `nodes/dt/tEnd` 与最小并发数 |
| Explain | 定位到具体机制（最高网格模态失稳、共享状态未隔离、字段谎报） |
| Repair | 给出修复方案 |
| Re-attack | 用同一实验重放，证明修复有效 |

## 执行底座

| 项 | 值 |
| --- | --- |
| 运行与编排底座 | **Agnes Harness (AGH)**，commit `e4e782fdde270a484cf5154f9338253acb2cfffd`，Apache-2.0，来源 <https://github.com/AgnesAI-Labs/agnes-harness> |
| 模型 | **仅 Agnes 模型**：`agnes-ai/agnes-3.0-flash`（baseUrl `https://api.agnes-ai.cn/v1`） |
| 第三方模型 | **无**。不接入其他厂商模型（每次运行的断言里都含一条「仅使用 Agnes 模型」，均通过） |
| 工具层 | AGH 后端插件 `plugins/qbc-verification-tools/`，注册 5 个确定性工具 |

## 目录

| 路径 | 内容 |
| --- | --- |
| `src/solver-service.mjs` | **被测系统**：FTCS 时间推进、Dirichlet/Neumann、对流项、稳态模式、故障开关 |
| `src/oracle-service.mjs` | **验证基准**：闭式解析解（分离变量 / 稳态指数解），无闭式解返回 422 |
| `plugins/qbc-verification-tools/` | AGH 后端插件：`target_health` / `solver_solve` / `oracle_exact` / `qbc_http_burst` / `solver_burst` |
| `ground-truth/` | 独立基准测量结果（四个数学性质的实测值） |
| `tools/` | 基准测量、三类测试编排、AGH 轨迹分析器、证据汇总、非交互安装插件配方 |
| `scripts/` | 靶场一键启停（含故障开关） |
| `docs/` | 成果汇总、分工计划、任务书、提交清单、部署笔记 |
| `evidence/` | 运行证据：AGH 原生轨迹、断言报告、发现报告、汇总 |
| `REPRODUCE.md` | 环境依赖与一键跑通步骤（**复现方式的唯一入口**） |
| `TEAM.md` / `THIRD-PARTY.md` | 成员分工与独立完成声明 / 第三方来源 |

## 当前状态

**运行底座**

- [x] AGH 在 Windows 完成源码构建并接通 Agnes 模型（已实测推理）
- [x] 非交互环境下安装 AGH 插件的完整配方（命名管道才有 admin 权限 → clientId 取自认证连接 → 需源码树原生模块）→ `tools/agh-admin/README.md`
- [x] 底座三类一致性测试（正常/边界/失败）49/50 断言通过 → `evidence/CONFORMANCE-SUMMARY.md`
- [x] 插件工具在非交互模式下免审批执行（实测确认，无需 TTY）

**靶场**

- [x] D1 被测求解服务（FTCS + Dirichlet/Neumann + 对流项 + 稳态模式）→ `src/solver-service.mjs`
- [x] D2 解析解基准（闭式解；无闭式解返回 422）→ `src/oracle-service.mjs`
- [x] D3 故障开关 4 个，默认全关
- [x] HTTP 入口端到端可用（`/health` + 求解 + 稳态 + 4xx/422 路径均已实测）
- [x] `ground-truth/` 四个数学性质独立测量通过 **4/4** → `ground-truth/ground-truth.json`
- [x] AGH 插件工具集 5 个，安装并运行中（`actual=running, trusted=true`）

**自主发现（作品核心）**

- [x] D1 稳定性临界：**r\* ≈ 0.5001356**（理论 0.5；比本队基准准 6.66 倍）→ `evidence/discovery/P1-stability-threshold.report.md`
- [x] D2 二阶收敛：误差比 **4.0000** → `evidence/target-tests/T-N1.*`
- [x] D3 识破 `blowUp` 谎报 → `evidence/target-tests/T-F1.*`
- [x] D4 对流振荡阈值 **Pe = 2.0**，并自主推导中心差分系数不等式 → `evidence/discovery/P3-peclet-threshold.report.md`
- [x] D5 绝热能量守恒：12500 步漂移仍 **1.21e-15**，且论证"不随步数累积"才是证据 → `evidence/discovery/P4-energy-conservation.report.md`
- [x] D6 并发一致性：识破跨请求状态污染 → `evidence/discovery/P5-concurrency-contamination.report.md`
- [x] 用代码机械否证智能体自己捏造的一处服务缺陷指控 → `evidence/discovery/P3-claim-verification.md`

**测试样例（赛事必填第 6 项）**

- [x] 靶场三类测试 **20/20** 断言通过 → `evidence/target-tests/SUMMARY.md`

## 已知局限（如实声明）

1. **只实现 FTCS**：`btcs` / `cn` 在 `/health` 中列出但 `/solve` 返回 400。刻意为之，理由见上。
2. **基准独立性是"算法级"而非"组织级"**：求解器与 Oracle 由同一成员实现，但走完全不同的算法路径
   （数值离散 vs 闭式解析）且分属两个进程。这是结构上的独立，不等同于独立的第三方复现。
3. **P1 的基准测量存在已知偏差**（0.500903 vs 理论 0.5，约 9e-4），成因是"有限观测时间内幅值需增长 10 倍
   才判发散"。智能体用离散极值原理作判据反而更准（0.5001356），这一点已如实记录。
4. **Windows 沙箱层不可用**（`doctor platform` 实测 `sandbox.l1=unavailable`），
   因此执行边界不完全依赖沙箱，而由能力限制代码兜底（工具限定本地主机）。
5. **`silent-clamp` 与 `partial-on-timeout` 已补跑用例**（2026-10-06，证据：`evidence/14-fault-switches-silent-clamp-partial-on-timeout.txt`）：前者把非法 `alpha=-1` 从 400 变成 200（静默取绝对值）；后者把 `tEnd/dt=1,000,000` 步从 400 变成 200，但**实际只跑 500000 步却仍报 `completed`、不标记 `incomplete`** —— 即“用部分结果冒充完整结果”，是本靶场最隐蔽的一处不可信行为。

## 许可与开源

赛事要求：获奖队伍须在结果公布后 **5 个工作日内**公开赛事代码库。本仓库当前为 **private**，届时按比赛规则转为公开，并保留全部第三方来源说明（见 [THIRD-PARTY.md](THIRD-PARTY.md)）。
