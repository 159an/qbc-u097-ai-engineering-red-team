# QBC / U097 — AI Engineering Red Team

> 2026 江苏省人工智能学会黑客松 · 本科生组 · 队伍 **QBC** · 参赛编号 **U097**

**一句话定义**：让一个基于 Agnes Harness（AGH）的智能体，在**不被告知任何数值分析理论**的前提下，自主设计实验、调用求解器与独立解析解基准、二分收敛最小反例，从而**发现一个工程传热求解服务的失效边界**，并给出可复现证据。

## 参考方向

| 项 | 值 |
| --- | --- |
| 主方向 | **工程仿真与优化**（结构 / 流体 / 控制 / 能源智能仿真与优化） |
| 兼报 | Agent 与 Harness 工程 |

## 定位

不是做求解器，也不是做测试工具，而是做一个**能自主完成工程验证任务**的 Agent；工程传热求解服务只是它的实验对象（靶场）。

**为什么靶场从"虚拟电商"改为"数值求解器"**（2026-10-03 决定）：

| 原电商方案的问题 | 数值求解器如何解决 |
| --- | --- |
| 电商是业务系统，赛事主题是"AI+**科学与工程**" | 传热/对流扩散方程是 CFD、结构动力学与传热学的基础，属「工程仿真与优化」无疑义 |
| "自己注入 bug 再让 AI 找"→ 评委会问价值何在 | **不需要注入任何人为 bug**：智能体发现的是数值方法**固有的数学失效边界** |
| "库存 −2"要自定义不变量，易变主观约定 | 临界值是实数（可二分收敛到任意精度）、收敛阶是整数，**是数学事实而非主观判断** |


## 执行底座（比赛硬性要求）

| 项 | 值 |
| --- | --- |
| 运行与编排底座 | **Agnes Harness (AGH)**，commit `e4e782f`，Apache-2.0，来源 <https://github.com/AgnesAI-Labs/agnes-harness> |
| 模型 | **仅 Agnes 模型**：`agnes-ai/agnes-3.0-flash`（baseUrl `https://api.agnes-ai.cn/v1`） |
| 第三方模型 | 无。不接入任何其他厂商模型 |

## 任务闭环

`Plan → Attack → Execute → Observe → Verify → Minimize → Explain → Repair → Re-attack`

## 架构

```
Agent 层    Agnes 模型 + AGH（任务规划 / 工具编排 / 多步执行 / 轨迹留痕）
工具层      AGH 后端插件注册的确定性工具：求解调用 · 解析解查询 · 并发探测 · 健康检查
环境层      工程传热求解服务（FTCS/BTCS/Crank–Nicolson + Dirichlet/Neumann + 对流项）
基准层      独立解析解服务（分离变量级数展开，**与被测服务不共享代码路径**）
验证层      与解析解逐点比对 · 收敛阶拟合 · 稳定性临界二分 · 能量守恒不变量
报告层      攻击轨迹 · 最小复现 · 根因 · 失效边界 · 修复前后对比
```

> **红线**：被测服务与验证基准必须**结构独立**（两个进程、两套算法）。若"标准答案"与"被检查的答案"同源，验证即自证。
> **红线**：判定不得交给模型——误差、临界值、收敛阶全部由代码计算（依据见 `evidence/conformance/FINDING-1`：模型把 12 行 CSV 的两列均值都算错了，而同回合内建校验器仍判 `pass`）。

## 目录

| 路径 | 内容 |
| --- | --- |
| `src/` | 靶场服务（工程传热求解器 + 独立解析解基准）、验证器 |
| `plugins/` | AGH 后端插件：智能体可调用的确定性工具 |
| `tools/` | 三类一致性测试编排、AGH 轨迹分析器、证据汇总、版本记录、桌面启动器 |
| `fixtures/` | 测试夹具与**独立计算的基准事实**（由脚本生成，勿手改） |
| `scripts/` | 构建、启动、复现脚本 |
| `docs/` | 设计说明、分工计划、攻击策略、验证方法、提交清单 |
| `evidence/` | 运行证据：AGH 轨迹、断言报告、日志、时间与版本记录 |
| `REPRODUCE.md` | 环境依赖与一键跑通步骤（**复现方式的唯一入口**） |
| `TEAM.md` | 成员分工与独立完成声明 |
| `THIRD-PARTY.md` | 第三方代码/数据/素材来源与许可 |

## 当前状态

**运行底座**

- [x] AGH 在 Windows 上完成源码构建并接通 Agnes 模型（已实测推理，2026-10-03）
- [x] 底座三类一致性测试（正常 / 边界 / 失败），49/50 断言通过 → `evidence/CONFORMANCE-SUMMARY.md`
- [x] 非交互环境下安装 AGH 插件的完整配方（三道门）→ `tools/agh-admin/README.md`
- [x] 插件工具在非交互模式下免审批执行（实测确认，无需 TTY）

**靶场**

- [x] 工程传热求解服务（FTCS + Dirichlet/Neumann + 对流项 + 稳态模式）
- [x] 独立解析解基准（闭式解；无闭式解时返回 422，绝不用数值解冒充）
- [x] 四个数学性质实测通过 4/4 → `ground-truth/ground-truth.json`
- [x] AGH 插件工具集（target_health / solver_solve / oracle_exact / qbc_http_burst）

**自主发现（作品核心）**

- [x] 智能体自主测定 FTCS 稳定性临界 **r\* ≈ 0.5001356**（理论 0.5），
      自定判据、二分 15 次、区间宽度 1.5e-11，并自行推导偏差来源
      → `evidence/discovery/P1-stability-threshold.report.md`
- [x] 智能体自主完成二阶收敛验证（误差比 4.0000）→ `evidence/target-tests/T-N1.*`
- [x] 智能体识破服务谎报 `blowUp`（用总热量守恒 + 幅值振荡两个独立判据）
      → `evidence/target-tests/T-F1.*`

**测试样例（赛事必填第 6 项）**

- [x] 靶场三类测试 20/20 断言通过 → `evidence/target-tests/SUMMARY.md`

**自主发现（补全）**

- [x] P3 稳态对流振荡阈值 **Pe = 2**，并自主推导出中心差分系数不等式
      → `evidence/discovery/P3-peclet-threshold.report.md`
- [x] P4 绝热能量守恒：漂移不随步数累积（12500 步仍 1.21e-15）
      → `evidence/discovery/P4-energy-conservation.report.md`
- [x] P5 并发一致性：识破跨请求状态污染，给出 2 次请求的最小复现
      → `evidence/discovery/P5-concurrency-contamination.report.md`
- [x] 用代码机械否证智能体自己捏造的服务缺陷指控
      → `evidence/discovery/P3-claim-verification.md`

**待完成（需人工）**

- [ ] 公开内容（赛事必填第 8 项，需在公开平台发布）
- [ ] 演示视频（3–5 分钟）与提交材料组装
- [ ] `TEAM.md` 填写姓名 / 学校 / 学院 / 学号

## 许可与开源

赛事要求：获奖队伍须在结果公布后 **5 个工作日内**公开赛事代码库。本仓库当前为 **private**，届时按比赛规则转为公开，并保留全部第三方来源说明（见 [THIRD-PARTY.md](THIRD-PARTY.md)）。
