# AGH 执行记录分析报告 — T-B1.trajectory.raw.json

- 生成时间：2026-10-03T08:08:40.536Z
- 断言集：`boundary`
- 事件总数：211（解析失败 0）
- 模型：`agnes-3.0-flash`　路由：`account-<redacted>`
- 最大连续步骤：12　结束原因：turn=`completed`

## 断言结果

| 断言 | 结果 | 证据 |
| --- | --- | --- |
| 仅使用 Agnes 模型（agnes-*） | PASS | agnes-3.0-flash |
| 推理请求发出且返回 200 | PASS | status=200 req=8bc5be71f9fff85c68db125339575575; status=200 req=62de4d226fa42d0aa6039ef4a214d0b5; status=200 req=d4e464f891923c4849204b8c977095c5; status=200 req=fba4de862ecc6d1e1bd929caf3c1e098; status=200 req=3f2a829d34b26d55f3a3f17dbeae04aa; status=200 req=2e7c4e03f88dd47bfd081aca90b02218; status=200 req=4e539842f66f72490b08bb276c16d587; status=200 req=e0b6d3c57b405de018db95dcebd3e3f2; status=200 req=03a97fcd91f8726e6954032f8baa9fe1; status=200 req=ef3f93617afdc6f8df7b784092602caf; status=200 req=deee4dcd63782580f7ff0fddf30cf505; status=200 req=538eb0e9eff15980bf0d0c04112639d6 |
| 存在工具调用链 | PASS | 11 次调用 |
| 工具返回与调用一一对应 | PASS | 0 次缺返回 |
| 终态符合预期（completed） | PASS | 实际 turn/end reason = completed |
| 连续步骤 >= 3 | PASS | 实际最大 step=12 |

## 工具调用链（按发生顺序）

| # | seq | 工具 | toolUseId | 有返回 | isError | 被拒绝 | 返回字节 | 校验 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 20 | `todo` | `t0-6ecb1dfa59c0843f17f9ed2a1fccf04a` | 是 | false | 否 | 45 | pass |
| 2 | 38 | `solver_solve` | `t1-ecc34263294230baaf3c72a80e5010ee` | 是 | false | 否 | 1825 | pass |
| 3 | 57 | `(名称未记录)` | `t2-686e847952ea6c3421a22743446e2b72` | 是 | true | 是 | 17 | n/a |
| 4 | 71 | `solver_solve` | `t3-956ac110d27909308bc42372bfb4ef45` | 是 | false | 否 | 413 | pass |
| 5 | 90 | `(名称未记录)` | `t4-e5e65df52e81925403e7d49680a26ebe` | 是 | true | 是 | 17 | n/a |
| 6 | 104 | `solver_solve` | `t5-58185998c8e88ec3f1b4ced66a55b86b` | 是 | false | 否 | 102 | pass |
| 7 | 123 | `(名称未记录)` | `t6-3d03e6da4ffef6d2f1ac03af9111d431` | 是 | true | 是 | 17 | n/a |
| 8 | 137 | `solver_solve` | `t7-a9dca93f4c6f7d7bdab5184853a01281` | 是 | false | 否 | 132 | pass |
| 9 | 156 | `(名称未记录)` | `t8-b1abac5227bd832285d7942001982cf3` | 是 | true | 是 | 17 | n/a |
| 10 | 170 | `solver_solve` | `t9-822a1abf765fcecaa602c7030b4118f9` | 是 | false | 否 | 3079 | pass |
| 11 | 189 | `(名称未记录)` | `t10-461fcaca4bf55e6463ae9850fc12836c` | 是 | true | 是 | 17 | n/a |

工具调用统计：`todo`×1、`solver_solve`×5、`(名称未记录)`×5

## 工具错误记录（失败类证据）

- seq 57 `t2-686e847952ea6c3421a22743446e2b72`：approval rejected
- seq 90 `t4-e5e65df52e81925403e7d49680a26ebe`：approval rejected
- seq 123 `t6-3d03e6da4ffef6d2f1ac03af9111d431`：approval rejected
- seq 156 `t8-b1abac5227bd832285d7942001982cf3`：approval rejected
- seq 189 `t10-461fcaca4bf55e6463ae9850fc12836c`：approval rejected

## 审批/权限相关事件

- seq 55 `approval/asked` origin=`system` data={"requestId":"r-6c1655fe7cc9b669385514d087838724","kind":"tool","toolUseId":"t2-686e847952ea6c3421a22743446e2b72","summary":"todo {\"items\":[{\"content\":\"边界探测1: nodes=2, dt=1e-4, tEnd=0.01, initialKind=sin\",\"status\":\"completed\"},{\"content\":\"边界探测2: tEnd=0\",\"status\":\"in_progress\"},{\"c
- seq 56 `approval/decided` origin=`system` data={"requestId":"r-6c1655fe7cc9b669385514d087838724","verdict":"rejected","via":"sync","scope":"tool:todo:execute"}
- seq 88 `approval/asked` origin=`system` data={"requestId":"r-c92aa8bbbe9f64951b181c6f7c0bbf6f","kind":"tool","toolUseId":"t4-e5e65df52e81925403e7d49680a26ebe","summary":"todo {\"items\":[{\"content\":\"边界探测1: nodes=2, dt=1e-4, tEnd=0.01, initialKind=sin\",\"status\":\"completed\"},{\"content\":\"边界探测2: tEnd=0\",\"status\":\"completed\"},{\"con
- seq 89 `approval/decided` origin=`system` data={"requestId":"r-c92aa8bbbe9f64951b181c6f7c0bbf6f","verdict":"rejected","via":"sync","scope":"tool:todo:execute"}
- seq 121 `approval/asked` origin=`system` data={"requestId":"r-d7c7a85230ffc4d2fafc63fd45271733","kind":"tool","toolUseId":"t6-3d03e6da4ffef6d2f1ac03af9111d431","summary":"todo {\"items\":[{\"content\":\"边界探测1: nodes=2, dt=1e-4, tEnd=0.01, initialKind=sin\",\"status\":\"completed\"},{\"content\":\"边界探测2: tEnd=0\",\"status\":\"completed\"},{\"con
- seq 122 `approval/decided` origin=`system` data={"requestId":"r-d7c7a85230ffc4d2fafc63fd45271733","verdict":"rejected","via":"sync","scope":"tool:todo:execute"}
- seq 154 `approval/asked` origin=`system` data={"requestId":"r-dad47efcb07c6e8839f3c6ae9949a85c","kind":"tool","toolUseId":"t8-b1abac5227bd832285d7942001982cf3","summary":"todo {\"items\":[{\"content\":\"边界探测1: nodes=2, dt=1e-4, tEnd=0.01, initialKind=sin\",\"status\":\"completed\"},{\"content\":\"边界探测2: tEnd=0\",\"status\":\"completed\"},{\"con
- seq 155 `approval/decided` origin=`system` data={"requestId":"r-dad47efcb07c6e8839f3c6ae9949a85c","verdict":"rejected","via":"sync","scope":"tool:todo:execute"}
- seq 187 `approval/asked` origin=`system` data={"requestId":"r-639ec2d48f3fa512f8ff416845866d02","kind":"tool","toolUseId":"t10-461fcaca4bf55e6463ae9850fc12836c","summary":"todo {\"items\":[{\"content\":\"边界探测1: nodes=2, dt=1e-4, tEnd=0.01, initialKind=sin\",\"status\":\"completed\"},{\"content\":\"边界探测2: tEnd=0\",\"status\":\"completed\"},{\"co
- seq 188 `approval/decided` origin=`system` data={"requestId":"r-639ec2d48f3fa512f8ff416845866d02","verdict":"rejected","via":"sync","scope":"tool:todo:execute"}

## 计费账本（真实 API 调用凭据）

| seq | 用途 | 模型 | input | output | cacheRead | ttft(ms) | 时长(ms) | status | x-request-id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 18 | inference | agnes-3.0-flash | 2591 | 178 | 7168 | 5962 | 5971 | 200 | 8bc5be71f9fff85c68db125339575575 |
| 36 | inference | agnes-3.0-flash | 2797 | 72 | 7168 | 5719 | 6316 | 200 | 62de4d226fa42d0aa6039ef4a214d0b5 |
| 53 | inference | agnes-3.0-flash | 1629 | 178 | 9728 | 3161 | 3163 | 200 | d4e464f891923c4849204b8c977095c5 |
| 69 | inference | agnes-3.0-flash | 286 | 41 | 11264 | 3256 | 3529 | 200 | fba4de862ecc6d1e1bd929caf3c1e098 |
| 86 | inference | agnes-3.0-flash | 610 | 178 | 11264 | 4670 | 4772 | 200 | 3f2a829d34b26d55f3a3f17dbeae04aa |
| 102 | inference | agnes-3.0-flash | 291 | 42 | 11776 | 1394 | 1648 | 200 | 2e7c4e03f88dd47bfd081aca90b02218 |
| 119 | inference | agnes-3.0-flash | 463 | 178 | 11776 | 5411 | 5453 | 200 | 4e539842f66f72490b08bb276c16d587 |
| 135 | inference | agnes-3.0-flash | 400 | 46 | 12032 | 5317 | 5318 | 200 | e0b6d3c57b405de018db95dcebd3e3f2 |
| 152 | inference | agnes-3.0-flash | 584 | 178 | 12032 | 4007 | 4064 | 200 | 03a97fcd91f8726e6954032f8baa9fe1 |
| 168 | inference | agnes-3.0-flash | 777 | 89 | 12032 | 934 | 1906 | 200 | ef3f93617afdc6f8df7b784092602caf |
| 185 | inference | agnes-3.0-flash | 3420 | 178 | 12032 | 4665 | 4667 | 200 | deee4dcd63782580f7ff0fddf30cf505 |
| 204 | inference | agnes-3.0-flash | 285 | 1118 | 15360 | 3205 | 21912 | 200 | 538eb0e9eff15980bf0d0c04112639d6 |
| 210 | title | agnes-3.0-flash | 1839 | 11 | 0 | 826 | 827 |  |  |

合计 tokens：input 15972、output 2487、cacheRead 133632

## 最终回答（节选）

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
