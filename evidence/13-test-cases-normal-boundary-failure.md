# 13. 测试样例（正常 / 边界 / 失败）

> 对应赛事材料「测试样例」必填项。三类样例：**正常**（服务应正确工作）、**边界**（输入到定义域边缘，服务应守住已知不变量而非崩溃或谎报）、**失败**（真实发现的缺陷，含复现与修复记录）。
> 所有「实测」列均为本轮（2026-10-04）真实运行输出，非理论预期。

## 正常

| # | 输入 / 命令 | 期望 | 实测 |
| --- | --- | --- | --- |
| N-1 | `GET http://127.0.0.1:8081/health` | 200 | 200 ✅ |
| N-2 | `/solve`（scheme=ftcs，sin 初值，Dirichlet 左0/右1，对流 v=1，nodes=21，tEnd=3，探针 x=0.25/0.5/0.75） | 三格式对流稳态离散精确解 0.165281 / 0.377516 / 0.650046（对应解析解 0.165296 / 0.377541 / 0.650068，偏差 < 2e-4） | ftcs=0.165281 / 0.377516 / 0.650046 ✅；btcs、cn 同值（见 `evidence/12-d5-start-stop-clean.txt` §3） |
| N-3 | `POST /exact`（alpha=1，sin 初值 + 零 Dirichlet 双侧） | 有闭式解，200 | 200 ✅ |

## 边界

| # | 输入 / 命令 | 期望 | 实测 |
| --- | --- | --- | --- |
| B-1 | `/solve` nodes=1 | 400（E_NODES_TOO_SMALL 或等效参数校验错误） | 400 ✅ |
| B-2 | `/solve` nodes=2 / nodes=3 | 不崩溃，200，返回结构完整 | 200 ✅ |
| B-3 | `/solve` tEnd=0 | 200，返回初值（零时长） | 200 ✅ |
| B-4 | `/solve` r=0.51（dt 设到超稳定域） | CFL 守卫拦下：`blowUp=True`（不静默跑发散后谎报稳定） | `blowUp=True` ✅ |
| B-5 | `POST /exact`（Neumann 边界 或 pulse 初值，无闭式解的组合） | 422（E_NO_CLOSED_FORM，不冒充数值解） | 422 ✅ |
| B-6 | `POST /exact` alpha<=0 | 400（物理参数校验） | 400 ✅ |

## 失败（真实缺陷的复现与修复）

### F-1. `stop-all.ps1` 报 `Stop-ServicePids : CommandNotFoundException`

- **现象**：一键停止脚本执行时报 `Stop-ServicePids : 无法将“Stop-ServicePids”项识别为 cmdlet…`（`CommandNotFoundException`），停止流程中断，两个 `/health` 探针仍存活。
- **根因**：`scripts/lib-qbc-services.ps1`（共享库）中 `Stop-ServicePids` 函数在某次功能合并时遗留缺失（合并未完整保留），而 `stop-all.ps1` 直接调用它。
- **修复**：在 `scripts/lib-qbc-services.ps1` 补回 `Stop-ServicePids` 函数实现（见当前文件 `# Kill a set of pids...` 注释段落）。
- **复测**：`CIM matched 2 → terminated 2 → both /health down`，`exit=0`（见 `evidence/12-d5-start-stop-clean.txt` §4；本轮因进程时序差异实测为 `terminated 0` 但 `/health` 双端已 down、退出码仍 0，判据不变）。

### F-2. `start-all.ps1` 报 `VariableNotWritable`

- **现象**：一键启动脚本在写入形参变量时报「VariableNotWritable」（变量不可写），启动流程中断。
- **根因**：脚本形参命名 `$Pid`，与 PowerShell 只读自动变量 `$PID`（当前进程 PID）同名，赋值被运行时拒绝。
- **修复**：形参改名为 `$procId`（提交 `d6cdfb2 fix(scripts): start-all 的 $Pid 与只读自动变量 $PID 冲突，改名修复`）。
- **复测**：`solver ready=True oracle ready=True`，`start_exit=0`（见 `evidence/12-d5-start-stop-clean.txt` §1）。
