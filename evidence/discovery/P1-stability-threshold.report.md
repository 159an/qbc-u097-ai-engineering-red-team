# AGH 执行记录分析报告 — P1-stability-threshold.trajectory.raw.json

- 生成时间：2026-10-03T07:56:04.486Z
- 断言集：`normal`
- 事件总数：690（解析失败 0）
- 模型：`agnes-3.0-flash`　路由：`account-acct-8f6502d5-8ed8-415d-8a0c-53565bcf8348`
- 最大连续步骤：25　结束原因：turn=`completed`

## 断言结果

| 断言 | 结果 | 证据 |
| --- | --- | --- |
| 仅使用 Agnes 模型（agnes-*） | PASS | agnes-3.0-flash |
| 推理请求发出且返回 200 | PASS | status=200 req=5a4cbec7f8f844bea662d647d6a0cf15; status=200 req=9b35412743f1c07bb862c89783815328; status=200 req=e4917f8c023452c65c9e0b8b3d3929f4; status=200 req=f629d235516e6dbaa862d0273dc64717; status=200 req=40514a98bef673cb468e40de75280233; status=200 req=40951e5e7a5edb5e8453c59d704d9d5a; status=200 req=bf3ca8e4fecb3e3dd5a4c9db5ab5232d; status=200 req=9be2b2a992c344085714caad9b37aec9; status=200 req=590b2a96e7984953531ea7a0a2b9421a; status=200 req=b45b13448f9cccede5049ee7c35c1207; status=200 req=5f0020194a9be3b87d526450e888d2cf; status=200 req=04818a47e1ff0f608f6aac5fd2e0d28b; status=200 req=f04d0d7134c420e36e1e29739608ac08; status=200 req=d30b805f78e6976af26e3845d999c7fe; status=200 req=40cf21f32778fa033e217ba33dc0293b; status=200 req=4bd0033270b2ccd5f900c952e07b493e; status=200 req=f081daacfd6cb4131c63c51dcaf5cb3d; status=200 req=67dea79d89faec8fe3c3919d189315ec; status=200 req=de69ee3c51ee3d5e482a517c70adf6be; status=200 req=cfb6d6bf8e58693fd1d697c2888fc780; status=200 req=a86ad2bc6a6edc17989267699c52db78; status=200 req=5957d9e5599d3279442727e0c22425d8; status=200 req=7a7061298700bd69eed6adbf1b116e66; status=200 req=3e7bf4d3a1368a66d338e2446d4714e6; status=200 req=936e93ed213b763c134b2ad0ac4de01e; status=200 req=6f6159f6c19723affcadfebf75caa395; status=200 req=b25082126a79f7f5793b05de866dd948; status=200 req=1af5de2b48d7e72acdfebe8fd63ed025; status=200 req=7ae194581952ffb96a55d62665e410ad; status=200 req=4b66d039f6e47bd3866620d78e5a2bff; status=200 req=2abde437967b7da0c45375178014eb42; status=200 req=ff59ef493e631405263d48d012689061 |
| 存在工具调用链 | PASS | 37 次调用 |
| 工具返回与调用一一对应 | PASS | 0 次缺返回 |
| 工具级校验全部通过 | PASS | 31 条 tool 级 signal |
| 终态符合预期（completed） | PASS | 实际 turn/end reason = completed |
| 连续步骤 >= 3 | PASS | 实际最大 step=25 |

## 工具调用链（按发生顺序）

| # | seq | 工具 | toolUseId | 有返回 | isError | 被拒绝 | 返回字节 | 校验 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 24 | `oracle_exact` | `t3-d0079e7d5857159f4e63cf507d5aac21` | 是 | false | 否 | 158 | pass |
| 2 | 25 | `solver_solve` | `t1-0ccfbd0712e75ed633a50443953c49cb` | 是 | false | 否 | 3280 | pass |
| 3 | 26 | `solver_solve` | `t2-a8592b6cee685d52f9b5fe4671e7f1c9` | 是 | false | 否 | 1180 | pass |
| 4 | 27 | `target_health` | `t0-beaa516b44930725df0552250ebfc34f` | 是 | false | 否 | 460 | pass |
| 5 | 77 | `target_health` | `t0-9cbfe16c285be538fc8e74513c48cb44` | 是 | false | 否 | 460 | pass |
| 6 | 138 | `(名称未记录)` | `t2-6434ab2df7766783d253e382671bd095` | 是 | true | 是 | 17 | n/a |
| 7 | 145 | `(名称未记录)` | `t1-0ffcfc29bb99c33be830f69d6a8bfc93` | 是 | true | 是 | 17 | n/a |
| 8 | 146 | `(名称未记录)` | `t3-a943b5767cad0e659adf77874bfd8be5` | 是 | true | 是 | 17 | n/a |
| 9 | 147 | `(名称未记录)` | `t4-9932c32b0661a63994a2b0b32bf0b4d1` | 是 | true | 是 | 17 | n/a |
| 10 | 150 | `(名称未记录)` | `t5-ce1a4271623eabc24b405d9957437705` | 是 | true | 是 | 17 | n/a |
| 11 | 167 | `(名称未记录)` | `t6-4cc5572c8518130d491266301302f750` | 是 | true | 是 | 17 | n/a |
| 12 | 181 | `oracle_exact` | `t7-2a39a0ec1fb675636ae03058e6e1bd03` | 是 | false | 否 | 181 | pass |
| 13 | 217 | `target_health` | `t0-d274d4bdf91522a6b054ce518bf53209` | 是 | false | 否 | 460 | pass |
| 14 | 234 | `solver_solve` | `t1-f18a7886b34ef0d7439ff2195b543250` | 是 | false | 否 | 733 | pass |
| 15 | 251 | `solver_solve` | `t2-5572926f0f1d11e097eda2d59be66426` | 是 | false | 否 | 808 | pass |
| 16 | 298 | `solver_solve` | `t4-ad97afd73a7eb5e0374834e77c50d5ac` | 是 | false | 否 | 752 | pass |
| 17 | 299 | `solver_solve` | `t3-2841814bf7bff37598780ca8eb68cf37` | 是 | false | 否 | 855 | pass |
| 18 | 320 | `solver_solve` | `t5-e7203dea1e456115e23b708014989b02` | 是 | false | 否 | 875 | pass |
| 19 | 338 | `solver_solve` | `t6-5da0dd4c2093f21fd4d227d618b5f316` | 是 | false | 否 | 831 | pass |
| 20 | 356 | `solver_solve` | `t7-3d667e61fdc9c994419a1f494528128f` | 是 | false | 否 | 852 | pass |
| 21 | 374 | `solver_solve` | `t8-0090679b8aa7b5c3af143cecd34b02a2` | 是 | false | 否 | 884 | pass |
| 22 | 392 | `solver_solve` | `t9-f9e4783d997ef952e0e8add81b83bde6` | 是 | false | 否 | 853 | pass |
| 23 | 410 | `solver_solve` | `t10-c5821d747aa26f47be37249475fa097c` | 是 | false | 否 | 865 | pass |
| 24 | 428 | `solver_solve` | `t11-83ea57ac801d5b0fb6922c3b586a9a1f` | 是 | false | 否 | 864 | pass |
| 25 | 446 | `solver_solve` | `t12-21f79bde00334c6d257d4eb33fe39d6b` | 是 | false | 否 | 857 | pass |
| 26 | 463 | `solver_solve` | `t13-234a1ed358325d5bfb14eaf02832d4aa` | 是 | false | 否 | 853 | pass |
| 27 | 481 | `solver_solve` | `t14-ab6ca126eb47f4521bd9110a1e01318f` | 是 | false | 否 | 871 | pass |
| 28 | 499 | `solver_solve` | `t15-c18170572c34ea2ce6cb1f8ac1a2a8ea` | 是 | false | 否 | 900 | pass |
| 29 | 517 | `solver_solve` | `t16-385f0afc983fb862676fa449b4c30f31` | 是 | false | 否 | 854 | pass |
| 30 | 534 | `solver_solve` | `t17-cf31aa0e3657d9f40327c1c7d5a68c18` | 是 | false | 否 | 830 | pass |
| 31 | 551 | `solver_solve` | `t18-7871fa11086b29ee624a14dcd0accb34` | 是 | false | 否 | 847 | pass |
| 32 | 574 | `solver_solve` | `t19-b16b3aee2110027d1f6576498d092806` | 是 | false | 否 | 544 | pass |
| 33 | 592 | `solver_solve` | `t20-fc82970e138f9330cdc776972e48af58` | 是 | false | 否 | 740 | pass |
| 34 | 610 | `solver_solve` | `t21-1ed0e291c93a389d943a0225fca5b2b2` | 是 | false | 否 | 507 | pass |
| 35 | 628 | `solver_solve` | `t22-274e212362e772ba377e986b0991ec73` | 是 | false | 否 | 726 | pass |
| 36 | 646 | `solver_solve` | `t23-12cceafdfafaa3d71f299bccfe861528` | 是 | false | 否 | 885 | pass |
| 37 | 664 | `solver_solve` | `t24-40646f7913b0680b7f5ea71e646a3658` | 是 | false | 否 | 887 | pass |

工具调用统计：`oracle_exact`×2、`solver_solve`×26、`target_health`×3、`(名称未记录)`×6

## 工具错误记录（失败类证据）

- seq 138 `t2-6434ab2df7766783d253e382671bd095`：approval rejected
- seq 145 `t1-0ffcfc29bb99c33be830f69d6a8bfc93`：approval rejected
- seq 146 `t3-a943b5767cad0e659adf77874bfd8be5`：approval rejected
- seq 147 `t4-9932c32b0661a63994a2b0b32bf0b4d1`：approval rejected
- seq 150 `t5-ce1a4271623eabc24b405d9957437705`：approval rejected
- seq 167 `t6-4cc5572c8518130d491266301302f750`：approval rejected

## 审批/权限相关事件

- seq 136 `approval/asked` origin=`system` data={"requestId":"r-e4169ad81d4d2656baeb873e8448705a","kind":"tool","toolUseId":"t2-6434ab2df7766783d253e382671bd095","summary":"solver_solve {\"alpha\":1,\"dt\":0.000050005,\"initialKind\":\"pulse\",\"length\":1,\"nodes\":101,\"probes\":[0.5],\"recordEvery\":10000,\"tEnd\":4}","risk":"destructive","bin
- seq 137 `approval/decided` origin=`system` data={"requestId":"r-e4169ad81d4d2656baeb873e8448705a","verdict":"rejected","via":"sync","scope":"tool:solver_solve:execute"}
- seq 139 `approval/asked` origin=`system` data={"requestId":"r-bc6ced4a0d1a3f5e0de92f7363a5e0ff","kind":"tool","toolUseId":"t1-0ffcfc29bb99c33be830f69d6a8bfc93","summary":"solver_solve {\"alpha\":1,\"dt\":0.00005,\"initialKind\":\"pulse\",\"length\":1,\"nodes\":101,\"probes\":[0.5],\"recordEvery\":10000,\"tEnd\":4}","risk":"destructive","binding
- seq 140 `approval/decided` origin=`system` data={"requestId":"r-bc6ced4a0d1a3f5e0de92f7363a5e0ff","verdict":"rejected","via":"sync","scope":"tool:solver_solve:execute"}
- seq 141 `approval/asked` origin=`system` data={"requestId":"r-362e3836567332451bfcdc8224bd2294","kind":"tool","toolUseId":"t3-a943b5767cad0e659adf77874bfd8be5","summary":"solver_solve {\"alpha\":1,\"dt\":0.000049995,\"initialKind\":\"pulse\",\"length\":1,\"nodes\":101,\"probes\":[0.5],\"recordEvery\":10000,\"tEnd\":4}","risk":"destructive","bin
- seq 142 `approval/decided` origin=`system` data={"requestId":"r-362e3836567332451bfcdc8224bd2294","verdict":"rejected","via":"sync","scope":"tool:solver_solve:execute"}
- seq 143 `approval/asked` origin=`system` data={"requestId":"r-bfb43643de4ef645e57143dfe4882635","kind":"tool","toolUseId":"t4-9932c32b0661a63994a2b0b32bf0b4d1","summary":"solver_solve {\"alpha\":1,\"dt\":0.00006,\"initialKind\":\"sin\",\"length\":1,\"nodes\":101,\"probes\":[0.5],\"recordEvery\":10000,\"tEnd\":4}","risk":"destructive","bindingHa
- seq 144 `approval/decided` origin=`system` data={"requestId":"r-bfb43643de4ef645e57143dfe4882635","verdict":"rejected","via":"sync","scope":"tool:solver_solve:execute"}
- seq 148 `approval/asked` origin=`system` data={"requestId":"r-4d9787065bcaa64cbb67b8d5e5918804","kind":"tool","toolUseId":"t5-ce1a4271623eabc24b405d9957437705","summary":"solver_solve {\"alpha\":1,\"dt\":0.00006,\"initialKind\":\"constant\",\"length\":1,\"nodes\":101,\"probes\":[0.5],\"recordEvery\":10000,\"tEnd\":4}","risk":"destructive","bind
- seq 149 `approval/decided` origin=`system` data={"requestId":"r-4d9787065bcaa64cbb67b8d5e5918804","verdict":"rejected","via":"sync","scope":"tool:solver_solve:execute"}
- seq 165 `approval/asked` origin=`system` data={"requestId":"r-ab2f297bba8ab12cd300e890129b55f7","kind":"tool","toolUseId":"t6-4cc5572c8518130d491266301302f750","summary":"solver_solve {\"alpha\":1,\"dt\":0.00005,\"initialKind\":\"pulse\",\"length\":1,\"nodes\":101,\"probes\":[0.5],\"recordEvery\":10000,\"tEnd\":4}","risk":"destructive","binding
- seq 166 `approval/decided` origin=`system` data={"requestId":"r-ab2f297bba8ab12cd300e890129b55f7","verdict":"rejected","via":"sync","scope":"tool:solver_solve:execute"}

## 计费账本（真实 API 调用凭据）

| seq | 用途 | 模型 | input | output | cacheRead | ttft(ms) | 时长(ms) | status | x-request-id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 22 | inference | agnes-3.0-flash | 7708 | 293 | 2048 | 5395 | 10543 | 200 | 5a4cbec7f8f844bea662d647d6a0cf15 |
| 54 | inference | agnes-3.0-flash | 4397 | 966 | 9728 | 989 | 17278 | 200 | 9b35412743f1c07bb862c89783815328 |
| 60 | title | agnes-3.0-flash | 1743 | 10 | 0 | 7760 | 7914 |  |  |
| 75 | inference | agnes-3.0-flash | 1396 | 14 | 14080 | 3066 | 3123 | 200 | e4917f8c023452c65c9e0b8b3d3929f4 |
| 134 | inference | agnes-3.0-flash | 1649 | 13558 | 14080 | 742 | 201555 | 200 | f629d235516e6dbaa862d0273dc64717 |
| 163 | inference | agnes-3.0-flash | 15250 | 188 | 14080 | 3116 | 5640 | 200 | 40514a98bef673cb468e40de75280233 |
| 179 | inference | agnes-3.0-flash | 349 | 96 | 29184 | 18111 | 19179 | 200 | 40951e5e7a5edb5e8453c59d704d9d5a |
| 197 | inference | agnes-3.0-flash | 628 | 664 | 29184 | 4530 | 12206 | 200 | bf3ca8e4fecb3e3dd5a4c9db5ab5232d |
| 215 | inference | agnes-3.0-flash | 1098 | 14 | 29696 | 1183 | 1234 | 200 | 9be2b2a992c344085714caad9b37aec9 |
| 232 | inference | agnes-3.0-flash | 1349 | 158 | 29696 | 7123 | 8801 | 200 | 590b2a96e7984953531ea7a0a2b9421a |
| 249 | inference | agnes-3.0-flash | 786 | 163 | 30976 | 1380 | 3212 | 200 | b45b13448f9cccede5049ee7c35c1207 |
| 296 | inference | agnes-3.0-flash | 1581 | 9933 | 30976 | 1706 | 148473 | 200 | 5f0020194a9be3b87d526450e888d2cf |
| 318 | inference | agnes-3.0-flash | 11225 | 325 | 32512 | 19686 | 24814 | 200 | 04818a47e1ff0f608f6aac5fd2e0d28b |
| 336 | inference | agnes-3.0-flash | 1240 | 318 | 43520 | 121539 | 126790 | 200 | f04d0d7134c420e36e1e29739608ac08 |
| 354 | inference | agnes-3.0-flash | 2212 | 390 | 43520 | 1651 | 6863 | 200 | d30b805f78e6976af26e3845d999c7fe |
| 372 | inference | agnes-3.0-flash | 1229 | 329 | 45568 | 879 | 6141 | 200 | 40cf21f32778fa033e217ba33dc0293b |
| 390 | inference | agnes-3.0-flash | 1242 | 338 | 46592 | 1235 | 6385 | 200 | 4bd0033270b2ccd5f900c952e07b493e |
| 408 | inference | agnes-3.0-flash | 2257 | 326 | 46592 | 1297 | 9251 | 200 | f081daacfd6cb4131c63c51dcaf5cb3d |
| 426 | inference | agnes-3.0-flash | 1223 | 328 | 48640 | 1100 | 5712 | 200 | 67dea79d89faec8fe3c3919d189315ec |
| 444 | inference | agnes-3.0-flash | 2238 | 358 | 48640 | 1421 | 6733 | 200 | de69ee3c51ee3d5e482a517c70adf6be |
| 461 | inference | agnes-3.0-flash | 1228 | 167 | 50688 | 1602 | 3682 | 200 | cfb6d6bf8e58693fd1d697c2888fc780 |
| 479 | inference | agnes-3.0-flash | 1046 | 270 | 51712 | 42057 | 46488 | 200 | a86ad2bc6a6edc17989267699c52db78 |
| 497 | inference | agnes-3.0-flash | 985 | 291 | 52736 | 4761 | 9036 | 200 | 5957d9e5599d3279442727e0c22425d8 |
| 515 | inference | agnes-3.0-flash | 1231 | 280 | 53504 | 1564 | 5805 | 200 | 7a7061298700bd69eed6adbf1b116e66 |
| 532 | inference | agnes-3.0-flash | 1164 | 166 | 54528 | 1138 | 3085 | 200 | 3e7bf4d3a1368a66d338e2446d4714e6 |
| 549 | inference | agnes-3.0-flash | 958 | 167 | 55552 | 1359 | 3345 | 200 | 936e93ed213b763c134b2ad0ac4de01e |
| 572 | inference | agnes-3.0-flash | 1026 | 1776 | 56320 | 31517 | 62637 | 200 | 6f6159f6c19723affcadfebf75caa395 |
| 590 | inference | agnes-3.0-flash | 3152 | 356 | 56320 | 1729 | 7560 | 200 | b25082126a79f7f5793b05de866dd948 |
| 608 | inference | agnes-3.0-flash | 1000 | 325 | 59392 | 1401 | 5693 | 200 | 1af5de2b48d7e72acdfebe8fd63ed025 |
| 626 | inference | agnes-3.0-flash | 888 | 236 | 60160 | 2405 | 5629 | 200 | 7ae194581952ffb96a55d62665e410ad |
| 644 | inference | agnes-3.0-flash | 906 | 264 | 60928 | 1710 | 9091 | 200 | 4b66d039f6e47bd3866620d78e5a2bff |
| 662 | inference | agnes-3.0-flash | 1103 | 381 | 61696 | 2304 | 9078 | 200 | 2abde437967b7da0c45375178014eb42 |
| 686 | inference | agnes-3.0-flash | 1170 | 3227 | 62720 | 6303 | 49406 | 200 | ff59ef493e631405263d48d012689061 |

合计 tokens：input 76657、output 36675、cacheRead 1325568

## 最终回答（节选）

```text
所有实验数据已齐备。整理完整报告如下。

---

# FTCS 显式格式稳定性边界的工程测定报告

## 1. 服务可用性（target_health 实际返回）

- **solver-service**：HTTP 200。声明 schemes `["ftcs","btcs","cn"]`，实际 implemented 仅 `["ftcs"]`（v1.0.0），limits：maxSteps 500000 / maxNodes 2001。
- **oracle-service**：HTTP 200。modes：`separation-of-variables (sin + zero Dirichlet)` 与 `steady advection-diffusion (exponential)`（v1.0.0），且明确标注 "independentOf: the numerical solver — no shared code, no time stepping"，可作为独立基准。

## 2. 实验设计与二分过程

**固定参数**：alpha=1、length=1、nodes=101（服务返回 dx=0.01，故 r = 10⁴·dt）、tEnd=4、probes=[0.5]、`recordEvery=10000`。初值：pulse（width=0.01、center=0.5，t=0 时峰值=1.0、总热=0.01，等效单节点尖峰）。

**判定判据（预先固定，全程不变）**：

> **不稳定 ⟺ `summary.maxAbsU ≥ 1.0`**（辅以 `summary.blowUp` 交叉验证）
>
> 依据：脉冲初值峰值恰为 1.0。FTCS 在稳定区（r≤0.5）满足离散极值原理——场只能衰减、绝不能超过初值峰值；而 `maxAbsU` 是终刻全场最大幅值，因此"终值 ≥ 初值峰值"就是高频模无限放大（违背极值原理）的直接标志。阈值 1.0 由物理（极值原理）给出，非试探设定。
>
> 交叉验证中发现：服务自带的 `blowUp` 标记远比我这个阈值钝——在 r=0.5001357~0.5001365 这些已经越过判据阈值的运行里 `blowUp` 仍是 false（要到 r=0.5002、maxAbsU≈2.7×10⁷ 才翻 true）。所以结论只能建立在预设判据上，不能依赖 `blowUp`。

**二分迭代记录**（括号内为服务返回的 `numerics.r` 与 `summary.maxAbsU`）：

| 轮次 | dt | r | maxAbsU | 判定 |
|---|---|---|---|---|
| 界外 | 4.9995×10⁻⁵ | 0.49995 | 1.42×10⁻¹⁹ | 稳定 |
| 界外 | 5.002×10⁻⁵ | 0.5002 | 2.73×10⁷（blowUp=true） | 发散 |
| 1 | 5.00075×10⁻⁵ | 0.500075 | 3.78×10⁻⁹ | 稳定 |
| 2 | 5.001375×10⁻⁵ | 0.5001375 | 1.823 | **发散** |
| 3 | 5.0010625×10⁻⁵ | 0.50010625 | 8.32×10⁻⁵ | 稳定 |
| 4 | 5.00121875×10⁻⁵ | 0.500121875 | 0.0123 | 稳定 |
| 5 | 5.001296875×10⁻⁵ | 0.5001296875 | 0.1499 | 稳定 |
| 6 | 5.001335938×10⁻⁵ | 0.500133594 | 0.5228 | 稳定 |
| 7 | 5.001355469×10⁻⁵ | 0.500135547 | 0.9763 | 稳定 |
| 8 | 5.001365234×10⁻⁵ | 0.500136523 | 1.3342 | **发散** |
| 9 | 5.00136035×10⁻⁵ | 0.500136035 | 1.1412 | **发散** |
| 10 | 5.00135791×10⁻⁵ | 0.500135791 | 1.0556 | **发散** |
| 11 | 5.00135669×10⁻⁵ | 0.500135669 | 1.0152 | **发散** |
| 12 | 5.00135608×10⁻⁵ | 0.500135608 | **0.99555** | 稳定 |
| 13 | 5.0013564×10⁻⁵ | 0.50013564 | 1.00579 | **发散** |
| 14 | 5.00135631×10⁻⁵ | 0.500135631 | 1.00290 | *
```
