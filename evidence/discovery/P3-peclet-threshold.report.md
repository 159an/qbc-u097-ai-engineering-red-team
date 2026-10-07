# AGH 执行记录分析报告 — P3-peclet-threshold.trajectory.raw.json

- 生成时间：2026-10-03T08:14:51.867Z
- 断言集：`normal`
- 事件总数：623（解析失败 0）
- 模型：`agnes-3.0-flash`　路由：`account-<redacted>`
- 最大连续步骤：31　结束原因：turn=`completed`

## 断言结果

| 断言 | 结果 | 证据 |
| --- | --- | --- |
| 仅使用 Agnes 模型（agnes-*） | PASS | agnes-3.0-flash |
| 推理请求发出且返回 200 | PASS | status=200 req=c96c31388add1202773182971f8c3090; status=200 req=0209ad2a8f6f035241e300cfa0d060ee; status=200 req=af54b4fd0e4f71ef36d73696daac49ca; status=200 req=09f976bbb80973723e9fa8a974e8a47d; status=200 req=44e9cb7b51ea3db4691e094380c8fbc6; status=200 req=fb6f3528353864f3b31b1ea4ee2ab592; status=200 req=f622456edb7c2017fc02bff561578573; status=200 req=4d71ffded0e7b0ef507d0c6f5b340eec; status=200 req=6756dca47c99c9354fd077dd5ab9b51c; status=200 req=4958dd42bfbf1c86f6c7af7a2ad474dc; status=200 req=5b3e5dd73f99ca3c64c3368430687c4d; status=200 req=b300c7d8c47efc5c3cb11461f4c6aa86; status=200 req=382751aa45d1049f92c9f0b82c6caaf1; status=200 req=a8fe04355ff8ecba6981faa1c4ed133e; status=200 req=9915c4efeb504aafa962d5b65ce04d77; status=200 req=a9a97379b8d16c8667fe420b821e5271; status=200 req=e2c2272659d09a345e6638ef3505a723; status=200 req=0cb066807fba4757114390042110da20; status=200 req=bfa80a7ec341e309dc66fdde17a826f8; status=200 req=4fe6d33ddede35ec1e47023f9b215fce; status=200 req=008b80597145651ccecde3efac3fc82d; status=200 req=13c10511f956a2b28f42c517593b557c; status=200 req=2a2a3e4255fa0baec8532572accb5998; status=200 req=d5e67aae3ada852fd73dfd279ef68382; status=200 req=b8c49a12c21865b5334955c2df9a2f3d; status=200 req=dc5c24ceba9298696a2aeacd077b78d9; status=200 req=a4d86d3c99e5fcb3a05e803cef76ec55; status=200 req=736566879fd614993c2a720aa31fc01b; status=200 req=791756756578494950a660df807686c1; status=200 req=a017b7350cf817375a9ba6cab8dc2b2a; status=200 req=45f3c6b6c7f40bb8a487f0458b30f529 |
| 存在工具调用链 | PASS | 43 次调用 |
| 工具返回与调用一一对应 | PASS | 0 次缺返回 |
| 工具级校验全部通过 | PASS | 42 条 tool 级 signal |
| 终态符合预期（completed） | PASS | 实际 turn/end reason = completed |
| 连续步骤 >= 3 | PASS | 实际最大 step=31 |

## 工具调用链（按发生顺序）

| # | seq | 工具 | toolUseId | 有返回 | isError | 被拒绝 | 返回字节 | 校验 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 23 | `target_health` | `t0-535d178f0eb8b6fcee6e3285345f4bc1` | 是 | false | 否 | 460 | pass |
| 2 | 24 | `solver_solve` | `t2-1d8dc772eb2027035ae3cae213ae193a` | 是 | false | 否 | 390 | pass |
| 3 | 25 | `solver_solve` | `t1-a547ae25c4f4591c0bbea90c9a46eddd` | 是 | false | 否 | 391 | pass |
| 4 | 52 | `solver_solve` | `t4-8ad4e60b704fddbf34004b468e314986` | 是 | false | 否 | 369 | pass |
| 5 | 53 | `solver_solve` | `t3-13c77630ed2ec604769e095b818f5692` | 是 | false | 否 | 389 | pass |
| 6 | 54 | `solver_solve` | `t5-bc86639bfd3e7ff90021ad877dbf770f` | 是 | false | 否 | 439 | pass |
| 7 | 55 | `solver_solve` | `t6-216a0ab20ba6138d41aaf6be4e017948` | 是 | false | 否 | 390 | pass |
| 8 | 85 | `solver_solve` | `t8-383101b32fd9a69d98578741e9a13ce2` | 是 | false | 否 | 390 | pass |
| 9 | 86 | `solver_solve` | `t7-378dd7fd7448a4818d7dea59f98678c9` | 是 | false | 否 | 388 | pass |
| 10 | 87 | `solver_solve` | `t9-cdd5e00080280e107c935eb92b87a2b1` | 是 | false | 否 | 389 | pass |
| 11 | 112 | `solver_solve` | `t10-a2aa0ffd962b4e697d650510bdd1dc9d` | 是 | false | 否 | 388 | pass |
| 12 | 118 | `(名称未记录)` | `t11-b3ee19d515d17380143975a3c5fbcd41` | 是 | true | 是 | 17 | n/a |
| 13 | 134 | `solver_solve` | `t13-cb9d4d876305ae912dd825325b88cc42` | 是 | false | 否 | 388 | pass |
| 14 | 135 | `solver_solve` | `t12-824de64682259818564fd22cf0a09eef` | 是 | false | 否 | 389 | pass |
| 15 | 157 | `solver_solve` | `t15-4fabc71b8a2199674a116cfff1a5d8bc` | 是 | false | 否 | 369 | pass |
| 16 | 158 | `solver_solve` | `t14-76bc8b5aa0c1c67c3078304c024ff2e8` | 是 | false | 否 | 388 | pass |
| 17 | 183 | `solver_solve` | `t16-7648e23a09448e6da181376f4db72ee2` | 是 | false | 否 | 369 | pass |
| 18 | 184 | `solver_solve` | `t18-f76f7eff6df10bcb69f65157bde78e83` | 是 | false | 否 | 434 | pass |
| 19 | 185 | `solver_solve` | `t17-866f85965d3f361735956af7dc7ed4d3` | 是 | false | 否 | 421 | pass |
| 20 | 186 | `solver_solve` | `t19-d5ca692cb11c2991e250b9f1d7b1a164` | 是 | false | 否 | 436 | pass |
| 21 | 213 | `solver_solve` | `t20-dfc6864eb040c1d2ca020d085a4efe38` | 是 | false | 否 | 369 | pass |
| 22 | 232 | `solver_solve` | `t21-0b5b814a02296083723fbd425a543370` | 是 | false | 否 | 440 | pass |
| 23 | 250 | `solver_solve` | `t22-7c693e2d59a935212890f1e0940afee5` | 是 | false | 否 | 427 | pass |
| 24 | 267 | `solver_solve` | `t23-dfe79e30695ff95cd985e10173c7a480` | 是 | false | 否 | 428 | pass |
| 25 | 284 | `solver_solve` | `t24-cb726ac6b09676f2842f5ceb4c3d697e` | 是 | false | 否 | 428 | pass |
| 26 | 302 | `solver_solve` | `t25-7f548d98686d24e946d190b813caa614` | 是 | false | 否 | 431 | pass |
| 27 | 319 | `solver_solve` | `t26-44667ee846f01956f194563dacc073d9` | 是 | false | 否 | 432 | pass |
| 28 | 336 | `solver_solve` | `t27-2c051d6ebdc8db4902b17c5080668f9a` | 是 | false | 否 | 432 | pass |
| 29 | 353 | `solver_solve` | `t28-b686779f774b54d3c7e321bd291a6ba9` | 是 | false | 否 | 434 | pass |
| 30 | 370 | `solver_solve` | `t29-cfc85cde11f8166d04fc7901ea53bee3` | 是 | false | 否 | 436 | pass |
| 31 | 387 | `solver_solve` | `t30-67c0860784f27dfd735e751858934037` | 是 | false | 否 | 437 | pass |
| 32 | 404 | `solver_solve` | `t31-1760a620751d9a53bd43047698ea0b3c` | 是 | false | 否 | 438 | pass |
| 33 | 421 | `solver_solve` | `t32-f89cd61dc0ef3d28b20a080a7de15337` | 是 | false | 否 | 440 | pass |
| 34 | 438 | `solver_solve` | `t33-b064a610e678f9099aab848a044d44c8` | 是 | false | 否 | 437 | pass |
| 35 | 456 | `solver_solve` | `t34-0f2346d99493d708687ee459f87b8f93` | 是 | false | 否 | 438 | pass |
| 36 | 473 | `solver_solve` | `t35-34fb670b589e7f97cafda3dd07ee9eba` | 是 | false | 否 | 438 | pass |
| 37 | 490 | `solver_solve` | `t36-5fede029c1bdfb25f70fea7983e3ef03` | 是 | false | 否 | 438 | pass |
| 38 | 507 | `solver_solve` | `t37-382170a3c1c6720d277e1aacedc984fb` | 是 | false | 否 | 439 | pass |
| 39 | 524 | `solver_solve` | `t38-3dd2ebcce57f22d943270b32b837a3ed` | 是 | false | 否 | 439 | pass |
| 40 | 541 | `solver_solve` | `t39-ed9571066be09d1e69712fa936406ada` | 是 | false | 否 | 440 | pass |
| 41 | 558 | `solver_solve` | `t40-47f9c479439e849b9a7ba38a38eb5665` | 是 | false | 否 | 438 | pass |
| 42 | 575 | `solver_solve` | `t41-0bcd0c49481250bdc2153f302ca129a4` | 是 | false | 否 | 438 | pass |
| 43 | 593 | `solver_solve` | `t42-42f30881b2dc4f5e94cb464a91e9ea78` | 是 | false | 否 | 371 | pass |

工具调用统计：`target_health`×1、`solver_solve`×41、`(名称未记录)`×1

## 工具错误记录（失败类证据）

- seq 118 `t11-b3ee19d515d17380143975a3c5fbcd41`：approval rejected

## 审批/权限相关事件

- seq 116 `approval/asked` origin=`system` data={"requestId":"r-f768a7c64a0ce67f0dc3a8eeacd75d4d","kind":"tool","toolUseId":"t11-b3ee19d515d17380143975a3c5fbcd41","summary":"qbc_http_burst {\"body\":\"{\\\"advectionVelocity\\\":2,\\\"alpha\\\":1,\\\"leftValue\\\":0,\\\"length\\\":1,\\\"nodes\\\":101,\\\"rightValue\\\":1,\\\"steady\\\":true}\",\"c
- seq 117 `approval/decided` origin=`system` data={"requestId":"r-f768a7c64a0ce67f0dc3a8eeacd75d4d","verdict":"rejected","via":"sync","scope":"tool:qbc_http_burst:execute"}

## 计费账本（真实 API 调用凭据）

| seq | 用途 | 模型 | input | output | cacheRead | ttft(ms) | 时长(ms) | status | x-request-id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 21 | inference | agnes-3.0-flash | 737 | 249 | 9216 | 1151 | 5949 | 200 | c96c31388add1202773182971f8c3090 |
| 50 | inference | agnes-3.0-flash | 1210 | 496 | 9728 | 684 | 6357 | 200 | 0209ad2a8f6f035241e300cfa0d060ee |
| 83 | inference | agnes-3.0-flash | 1718 | 621 | 10752 | 658 | 8519 | 200 | af54b4fd0e4f71ef36d73696daac49ca |
| 110 | inference | agnes-3.0-flash | 1564 | 225 | 12288 | 1130 | 14347 | 200 | 09f976bbb80973723e9fa8a974e8a47d |
| 132 | inference | agnes-3.0-flash | 2055 | 210 | 12288 | 2008 | 4263 | 200 | 44e9cb7b51ea3db4691e094380c8fbc6 |
| 155 | inference | agnes-3.0-flash | 2776 | 211 | 12288 | 1205 | 3959 | 200 | fb6f3528353864f3b31b1ea4ee2ab592 |
| 181 | inference | agnes-3.0-flash | 918 | 521 | 14848 | 668 | 7816 | 200 | f622456edb7c2017fc02bff561578573 |
| 211 | inference | agnes-3.0-flash | 1784 | 240 | 15616 | 3096 | 8253 | 200 | 4d71ffded0e7b0ef507d0c6f5b340eec |
| 230 | inference | agnes-3.0-flash | 728 | 371 | 17152 | 1045 | 7784 | 200 | 6756dca47c99c9354fd077dd5ab9b51c |
| 248 | inference | agnes-3.0-flash | 898 | 244 | 17664 | 862 | 4474 | 200 | 4958dd42bfbf1c86f6c7af7a2ad474dc |
| 265 | inference | agnes-3.0-flash | 671 | 109 | 18432 | 1981 | 2896 | 200 | 5b3e5dd73f99ca3c64c3368430687c4d |
| 282 | inference | agnes-3.0-flash | 567 | 110 | 18944 | 1011 | 2144 | 200 | b300c7d8c47efc5c3cb11461f4c6aa86 |
| 300 | inference | agnes-3.0-flash | 975 | 143 | 18944 | 833 | 2632 | 200 | 382751aa45d1049f92c9f0b82c6caaf1 |
| 317 | inference | agnes-3.0-flash | 652 | 112 | 19712 | 3494 | 4414 | 200 | a8fe04355ff8ecba6981faa1c4ed133e |
| 334 | inference | agnes-3.0-flash | 1066 | 113 | 19712 | 1295 | 2360 | 200 | 9915c4efeb504aafa962d5b65ce04d77 |
| 351 | inference | agnes-3.0-flash | 1482 | 114 | 19712 | 1105 | 2350 | 200 | a9a97379b8d16c8667fe420b821e5271 |
| 368 | inference | agnes-3.0-flash | 621 | 115 | 20992 | 2194 | 3113 | 200 | e2c2272659d09a345e6638ef3505a723 |
| 385 | inference | agnes-3.0-flash | 2578 | 116 | 19456 | 1772 | 2654 | 200 | 0cb066807fba4757114390042110da20 |
| 402 | inference | agnes-3.0-flash | 1465 | 117 | 20992 | 3249 | 4284 | 200 | bfa80a7ec341e309dc66fdde17a826f8 |
| 419 | inference | agnes-3.0-flash | 610 | 118 | 22272 | 1276 | 2887 | 200 | 4fe6d33ddede35ec1e47023f9b215fce |
| 436 | inference | agnes-3.0-flash | 1039 | 119 | 22272 | 1315 | 2626 | 200 | 008b80597145651ccecde3efac3fc82d |
| 454 | inference | agnes-3.0-flash | 441 | 132 | 23296 | 2156 | 3652 | 200 | 13c10511f956a2b28f42c517593b557c |
| 471 | inference | agnes-3.0-flash | 626 | 121 | 23552 | 1987 | 2981 | 200 | 2a2a3e4255fa0baec8532572accb5998 |
| 488 | inference | agnes-3.0-flash | 1055 | 122 | 23552 | 1298 | 2894 | 200 | d5e67aae3ada852fd73dfd279ef68382 |
| 505 | inference | agnes-3.0-flash | 1484 | 121 | 23552 | 1293 | 2173 | 200 | b8c49a12c21865b5334955c2df9a2f3d |
| 522 | inference | agnes-3.0-flash | 635 | 120 | 24832 | 1572 | 2506 | 200 | dc5c24ceba9298696a2aeacd077b78d9 |
| 539 | inference | agnes-3.0-flash | 1065 | 120 | 24832 | 34216 | 35239 | 200 | a4d86d3c99e5fcb3a05e803cef76ec55 |
| 556 | inference | agnes-3.0-flash | 1496 | 120 | 24832 | 1213 | 2228 | 200 | 736566879fd614993c2a720aa31fc01b |
| 573 | inference | agnes-3.0-flash | 644 | 120 | 26112 | 1715 | 2897 | 200 | 791756756578494950a660df807686c1 |
| 591 | inference | agnes-3.0-flash | 1074 | 328 | 26112 | 1804 | 5822 | 200 | a017b7350cf817375a9ba6cab8dc2b2a |
| 616 | inference | agnes-3.0-flash | 619 | 2716 | 27136 | 937 | 45374 | 200 | 45f3c6b6c7f40bb8a487f0458b30f529 |
| 622 | title | agnes-3.0-flash | 2488 | 8 | 0 | 1405 | 1473 |  |  |

合计 tokens：input 37741、output 8702、cacheRead 601088

## 最终回答（节选）

```text
nodes=201 时 dx=0.005，peclet（按定义 v·dx/α）= 200×0.005 = 1.0，overshoot=0，无振荡。对照实验完成。

现在整理全部结果，撰写报告。

---

# 稳态对流扩散失效边界测定报告

## 一、服务确认（target_health）

`target_health` 返回 `ok:true`，solver-service 与 oracle-service 均 200，在线正常。oracle 支持 "steady advection-diffusion (exponential)" 闭式解。

## 二、粗扫（nodes=101，dx=0.01，alpha=1）

| advectionVelocity | numerics.peclet（工具返回） | overshoot | 判据 |
|---|---|---|---|
| 1 | 1 | 0 | 无振荡 |
| 10 | 0.1（工具值，与定义不符） | 0 | 无振荡 |
| 200 | 2 | 0 | 无振荡 |
| 201 | 2.01 | 0.002494 | **出现振荡** |
| 500 | 10 | 0.6667 | 振荡显著 |
| 10000 | 100 | 0.9973 | 振荡强烈 |

说明：`numerics.peclet` 字段在低速度区存在明显的数据不稳定/随机化（v=0.5 返回 0.0001、v=100 返回 0.6 等，均与定义 v·dx/α 不符），但在 v≥200 区间与定义一致（v=200→2，v=201→2.01，v=200.5→2.005）。本实验以 **v·dx/α 的定义值** 为准绳，工具返回的 peclet 仅作辅助核对。

## 三、二分法（判据：overshoot > 0 即"出现非物理振荡"）

从 v=200（overshoot=0，无振荡）与 v=201（overshoot>0，有振荡）开始二分：

| 迭代 | v | peclet | overshoot |
|---|---|---|---|
| 初 | 200 | 2.00 | 0（无） |
| 初 | 201 | 2.01 | 0.00249（有） |
| 1 | 200.5 | 2.005 | 0.00125（有） |
| 2 | 200.25 | 2.0025 | 0.000625（有） |
| 3 | 200.125 | 2.00125 | 0.000312（有） |
| 4 | 200.0625 | 2.000625 | 0.000156（有） |
| 5 | 200.03125 | 2.0003125 | 0.0000781（有） |
| 6 | 200.015625 | 2.00015625 | 0.0000391（有） |
| 7 | 200.0078125 | 2.000078125 | 0.0000195（有） |
| 8 | 200.00390625 | 2.0000390625 | 0.00000977（有） |
| 9 | 200.001953125 | 2.00001953125 | 0.00000488（有） |
| 10 | 200.0009765625 | 2.000009765625 | 0.00000244（有） |
| 11 | 200.00048828125 | 2.0000048828125 | 0.00000122（有） |
| 12 | 200.000244140625 | 2.00000244140625 | 0.000000610（有） |
| 13 | 200.0001220703125 | 2.000001220703125 | 0.000000305（有） |
| 14 | 200.00006103515625 | 2.0000006103515626 | 0.000000153（有） |
| 15 | 200.00003051757812 | 2.000000305175781 | 0.0000000763（有） |
| 16 | 200.00001525878906 | 2.0000001525878908 | 0.0000000381（有） |
| 17 | 200.0000076293945 | 2.000000076293945 | 0.0000000191（有） |
| 18 | 200.0000038146972 | 2.0000000381469722 | 0.00000000954（有） |
| 19 | 200.0000019073486 | 2.000000019073486 | 0.00000000477（有） |
```
