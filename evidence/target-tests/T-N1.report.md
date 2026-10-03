# AGH 执行记录分析报告 — T-N1.trajectory.raw.json

- 生成时间：2026-10-03T08:07:24.886Z
- 断言集：`normal`
- 事件总数：65（解析失败 0）
- 模型：`agnes-3.0-flash`　路由：`account-acct-8f6502d5-8ed8-415d-8a0c-53565bcf8348`
- 最大连续步骤：3　结束原因：turn=`completed`

## 断言结果

| 断言 | 结果 | 证据 |
| --- | --- | --- |
| 仅使用 Agnes 模型（agnes-*） | PASS | agnes-3.0-flash |
| 推理请求发出且返回 200 | PASS | status=200 req=348e6f9f27d5b79b113cf112de1a2cb7; status=200 req=40abfc89d949d98e5e5202f616b28fda; status=200 req=dc2b9c705b74364e04eb1198840365cf |
| 存在工具调用链 | PASS | 3 次调用 |
| 工具返回与调用一一对应 | PASS | 0 次缺返回 |
| 工具级校验全部通过 | PASS | 3 条 tool 级 signal |
| 终态符合预期（completed） | PASS | 实际 turn/end reason = completed |
| 连续步骤 >= 3 | PASS | 实际最大 step=3 |

## 工具调用链（按发生顺序）

| # | seq | 工具 | toolUseId | 有返回 | isError | 被拒绝 | 返回字节 | 校验 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 22 | `solver_solve` | `t0-fb091c194c268feb1051cba2c67fbb85` | 是 | false | 否 | 510 | pass |
| 2 | 23 | `oracle_exact` | `t1-312a1b135fa6ecb7f41b3175088aa885` | 是 | false | 否 | 158 | pass |
| 3 | 43 | `solver_solve` | `t2-d420b6db8e87391ad285c261825ce721` | 是 | false | 否 | 514 | pass |

工具调用统计：`solver_solve`×2、`oracle_exact`×1

## 计费账本（真实 API 调用凭据）

| seq | 用途 | 模型 | input | output | cacheRead | ttft(ms) | 时长(ms) | status | x-request-id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | inference | agnes-3.0-flash | 6750 | 298 | 3072 | 1329 | 4796 | 200 | 348e6f9f27d5b79b113cf112de1a2cb7 |
| 41 | inference | agnes-3.0-flash | 925 | 202 | 9728 | 1892 | 4212 | 200 | 40abfc89d949d98e5e5202f616b28fda |
| 60 | inference | agnes-3.0-flash | 740 | 654 | 10496 | 11951 | 22939 | 200 | dc2b9c705b74364e04eb1198840365cf |

合计 tokens：input 8415、output 1154、cacheRead 23296

## 最终回答（节选）

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
