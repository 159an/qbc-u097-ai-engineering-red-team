# AGH 执行记录分析报告 — P4-energy-conservation.trajectory.raw.json

- 生成时间：2026-10-03T09:11:49.096Z
- 断言集：`normal`
- 事件总数：126（解析失败 0）
- 模型：`agnes-3.0-flash`　路由：`account-<redacted>`
- 最大连续步骤：6　结束原因：turn=`completed`

## 断言结果

| 断言 | 结果 | 证据 |
| --- | --- | --- |
| 仅使用 Agnes 模型（agnes-*） | PASS | agnes-3.0-flash |
| 推理请求发出且返回 200 | PASS | status=200 req=f1322852e2fe3010d45fb36d51ce77a7; status=200 req=cdc7df0e7ad14edb18b3f701af8cd055; status=200 req=ebd2f5de05701e2c15e836f7e1baa415; status=200 req=ae830c09b2ea9986d888c7450a2ce010; status=200 req=778c1bbb9ee18ffaf16ae9170d16edc4; status=200 req=5371636fb73b1bfbaa089037c284a17e |
| 存在工具调用链 | PASS | 7 次调用 |
| 工具返回与调用一一对应 | PASS | 0 次缺返回 |
| 工具级校验全部通过 | PASS | 7 条 tool 级 signal |
| 终态符合预期（completed） | PASS | 实际 turn/end reason = completed |
| 连续步骤 >= 3 | PASS | 实际最大 step=6 |

## 工具调用链（按发生顺序）

| # | seq | 工具 | toolUseId | 有返回 | isError | 被拒绝 | 返回字节 | 校验 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 20 | `target_health` | `t0-804348df910e3ead08ce5ee45dad437c` | 是 | false | 否 | 460 | pass |
| 2 | 39 | `solver_solve` | `t1-7e876f659f2ee9d03cf1efe74a9ca55b` | 是 | false | 否 | 444 | pass |
| 3 | 40 | `solver_solve` | `t2-b4812b0bc74d48491b51718e1e260d33` | 是 | false | 否 | 444 | pass |
| 4 | 61 | `solver_solve` | `t3-14b7e5a3930294c5811beea6cf4de199` | 是 | false | 否 | 3275 | pass |
| 5 | 78 | `solver_solve` | `t4-446dfb2d7c8de80dcf3b8aa944353d10` | 是 | false | 否 | 3280 | pass |
| 6 | 97 | `solver_solve` | `t5-1595c45a78b782717948479bf6fe7fc7` | 是 | false | 否 | 3280 | pass |
| 7 | 98 | `solver_solve` | `t6-c5788283d74a6fcef8a4ead4befe7ae7` | 是 | false | 否 | 3269 | pass |

工具调用统计：`target_health`×1、`solver_solve`×6

## 计费账本（真实 API 调用凭据）

| seq | 用途 | 模型 | input | output | cacheRead | ttft(ms) | 时长(ms) | status | x-request-id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 18 | inference | agnes-3.0-flash | 3154 | 14 | 7168 | 2804 | 2846 | 200 | f1322852e2fe3010d45fb36d51ce77a7 |
| 37 | inference | agnes-3.0-flash | 3407 | 368 | 7168 | 7061 | 10864 | 200 | cdc7df0e7ad14edb18b3f701af8cd055 |
| 59 | inference | agnes-3.0-flash | 1050 | 274 | 10496 | 841 | 4819 | 200 | ebd2f5de05701e2c15e836f7e1baa415 |
| 76 | inference | agnes-3.0-flash | 3073 | 186 | 11520 | 14904 | 17102 | 200 | ae830c09b2ea9986d888c7450a2ce010 |
| 95 | inference | agnes-3.0-flash | 6039 | 402 | 11520 | 3942 | 10972 | 200 | 778c1bbb9ee18ffaf16ae9170d16edc4 |
| 119 | inference | agnes-3.0-flash | 6097 | 1282 | 17408 | 1243 | 17843 | 200 | 5371636fb73b1bfbaa089037c284a17e |
| 125 | title | agnes-3.0-flash | 2108 | 8 | 0 | 451 | 547 |  |  |

合计 tokens：input 24928、output 2534、cacheRead 65280

## 最终回答（节选）

```text
# 核验报告：绝热边界的守恒性

全部数字直接取自 `solver_solve` 的 summary 字段，数值：nodes=101（dx=0.01）、alpha=1、dt=4e-5（r=0.4，稳定性判据 r≤0.5 满足）、pulse（amplitude=1, center=0.5, width=0.02）。

## 1. 实验 A：两端 Neumann(0)（绝热），tEnd=0.05
- totalHeatInitial = 0.01
- totalHeatFinal = 0.01
- heatDriftRelative = 0
- steps=1250，maxAbsU≈0.01277，均匀趋平，blowUp=false（健康扩散形态：孤立高斯脉冲在绝热端上弥散、总热不变）

## 2. 实验 B：两端 Dirichlet(0)，tEnd=0.05
- totalHeatInitial = 0.01
- totalHeatFinal = 0.007722301443554894
- heatDriftRelative = 0.2277698556445106（损失约 22.8%）
- minU=0：边界被钉在 0，初始脉冲向边界扩散时被边界"吸走"

## 3. A 与 B 的本质区别（物理判据）
- 判据就是 **Σuᵢ·dx 是否守恒**：
  - **Neumann(0)**：∂u/∂n=0 → 边界热流 q=−α·∂u/∂n=0，是**绝热壁**，热量只能进内/出内，系统封闭。正确实现下总热应恒为初值。
  - **Dirichlet(0)**：端点固定为 0，与内部温度梯度形成持续热流，热量**流出**系统，总热必然单调减少（本例损失 22.8%）。
- 因此 A 的"热守恒"与 B 的"热流出"是物理上截然不同的行为，不能用同一把尺子要求。B 出现 heatDrift≠0 是**预期**，不是 bug。

## 4. 实验 A 能否判定 Neumann 实现是否正确？阈值取多少？
**能。** 判据与阈值：
- 绝热系统总热解析上守恒（误差仅来自离散与舍入），在 r=0.4 的 FTCS 上，1250 步的守恒偏差主要是：(i) 格式耗散造成的 O(dt) 误差，(ii) 浮点舍入 O(ε·steps)。
- 实测 A 的 drift = 0（服务直接报 0），12500 步（实验 C）也仅 1.2e-15——处于双精度舍入底噪量级，说明本实现守恒到机器精度。
- 建议阈值：**|heatDriftRelative| ≤ 1e-10（本配置）**，或更宽松地 **≤ 1e-6 作为"通过线"**（比 1e-3 严格、比 1e-15 宽松，覆盖不同 dt/步数的合理范围；阈值远大于浮点底噪 1e-15、远小于 B 实验 0.228 的物理流失量级，可干净区分"实现错误"与"物理流失"）。
- 更稳的做法：同时要求 drift 对 tEnd 不放大（见第 5 条）。若服务把 Neumann 误写成 Dirichlet，A 的 drift 会达到 B 的 2e-1 量级，与阈值直接冲突。

## 5. 实验 C：绝热，tEnd=0.5（12500 步）
- heatDriftRelative = **1.214306433183765e-15**
- 结论：**不随积分时间累积**。步数×10，drift 仍停留在 1e-15 量级（双精度 eps≈2.2e-16 的底噪），与 B 实验 0.228 的物理流失形成鲜明对比。这是格式无系统性热流泄漏的直接证据——若 Neumann 实现有边界误差项，drift 会随步数线性增长（∝steps），而这里没有。

## 总结
| 实验 | 边界 | 步骤 | 总热初 | 总热末 | 相对漂移 |
|---|---|---|---|---|---|
| A | Neumann(0) 绝热 | 1250 | 0.01 | 0.01 | 0 |
| B | Dirichlet(0) | 1250 | 0.01 | 0.0077223 | 0.22777 |
| C | Neumann(0) 绝热 | 12500 | 0.01 | 0.009999999999999988 | 1.21e-15 |

该服务的 Neumann 边界实现**守恒行为正确**：tEnd=0.05 与 0.5 下漂移均 ≤1e-15，与步数无关、不累积，落在机器精度水平；而 Dirichlet 端对照 B 给出 22.8% 的物理热流失，验证了"守恒 vs 不守恒"的判别力确实有效。
```
