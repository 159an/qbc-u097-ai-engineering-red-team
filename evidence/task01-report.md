# AGH 执行记录分析报告 — task01-trajectory.raw.json

- 生成时间：2026-10-03T06:23:51.828Z
- 断言集：`normal`
- 事件总数：116（解析失败 0）
- 模型：`agnes-3.0-flash`　路由：`account-<redacted>`
- 最大连续步骤：3　结束原因：turn=`completed`

## 断言结果

| 断言 | 结果 | 证据 |
| --- | --- | --- |
| 仅使用 Agnes 模型（agnes-*） | PASS | agnes-3.0-flash |
| 推理请求发出且返回 200 | PASS | status=200 req=41ebbd89251b09676f629e2e8c4694cd; status=200 req=ee162a88a73d2548b07b7c45cbd4cc34; status=200 req=58f6c6e878e737ebce211f82e79b1f2e |
| 存在工具调用链 | PASS | 12 次调用 |
| 工具返回与调用一一对应 | PASS | 0 次缺返回 |
| 工具级校验全部通过 | PASS | 12 条 tool 级 signal |
| 工具调用无错误返回 | PASS | 0 条错误 |
| 终态符合预期（completed） | PASS | 实际 turn/end reason = completed |
| 连续步骤 >= 3 | PASS | 实际最大 step=3 |

## 工具调用链（按发生顺序）

| # | seq | 工具 | toolUseId | 有返回 | isError | 被拒绝 | 返回字节 | 校验 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 24 | `ls` | `t2-744fc9c2f6bdf20b4b843355a119e4b3` | 是 | false | 否 | 424 | pass |
| 2 | 25 | `read` | `t0-5d23d02a78dc787ea03317bcd823ebfe` | 是 | false | 否 | 990 | pass |
| 3 | 26 | `ls` | `t3-840358005518decc0d919b92e1e451bf` | 是 | false | 否 | 624 | pass |
| 4 | 27 | `read` | `t1-c3e1c2dc0b9456ef58e925f414426fa6` | 是 | false | 否 | 18269 | pass |
| 5 | 61 | `read` | `t6-e507f7c912afe6d4eb8500f4ccf5216e` | 是 | false | 否 | 1447 | pass |
| 6 | 62 | `read` | `t7-0e192f0b7054fadeb390c0d5ddaf9c4e` | 是 | false | 否 | 553 | pass |
| 7 | 63 | `read` | `t5-acb25ee1286a41aa1df9be86fde5a7ef` | 是 | false | 否 | 2013 | pass |
| 8 | 64 | `read` | `t4-3c12958f597b68ec552b4c8144f45dc0` | 是 | false | 否 | 566 | pass |
| 9 | 77 | `read` | `t9-d10d31a6dc040fa1ecf03451366c632e` | 是 | false | 否 | 927 | pass |
| 10 | 78 | `read` | `t8-6951b0aaae4125de064a7fd9e3f173fa` | 是 | false | 否 | 705 | pass |
| 11 | 79 | `read` | `t10-64b68ca7a199c812b154705e17933d9e` | 是 | false | 否 | 243 | pass |
| 12 | 80 | `read` | `t11-9322d5a1a7cf748b307267fc1ec3bb39` | 是 | false | 否 | 796 | pass |

工具调用统计：`ls`×2、`read`×10

## 计费账本（真实 API 调用凭据）

| seq | 用途 | 模型 | input | output | cacheRead | ttft(ms) | 时长(ms) | status | x-request-id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 22 | inference | agnes-3.0-flash | 6268 | 134 | 2048 | 1624 | 3812 | 200 | 41ebbd89251b09676f629e2e8c4694cd |
| 59 | inference | agnes-3.0-flash | 5952 | 305 | 8192 | 3321 | 5919 | 200 | ee162a88a73d2548b07b7c45cbd4cc34 |
| 109 | inference | agnes-3.0-flash | 3167 | 1845 | 14080 | 3431 | 33340 | 200 | 58f6c6e878e737ebce211f82e79b1f2e |
| 115 | title | agnes-3.0-flash | 1408 | 6 | 0 | 1154 | 1184 |  |  |

合计 tokens：input 16795、output 2290、cacheRead 24320

## 最终回答（节选）

```text
根据当前工作区 `D:\dshworkplace\agh` 的文件（包括 `README.md`、`package.json`、`packages/*/package.json` 与目录列表），回答如下。

## 1. 这个项目解决什么问题

**Agnes Harness（AGH）** 是一个“可插拔 Agent 执行框架”（agent harness / execution foundation），面向 **Forward Deployed Engineering（FDE）**：把 AI 放进客户真实环境、把差异做成可复用能力。

它解决的核心问题（来自 `README.md`）：
- 客户系统各异：订单查询、知识库、内部 API 等。AGH 把这些业务能力做成 **插件（plugins）**，通过 `MCP` 或后端插件挂载；安装时记录 version、source、integrity digest、capability hash、license。
- 任务需要在 Web、CLI、SDK 之间共享上下文：AGH 的 CLI / Web / SDK 共享同一套 backend sessions；Web 会话可以在终端 `/resume <id>` 恢复。
- 客户环境需要可审计性：命令执行前要求 approval（allow once / allow session / deny），轨迹（trajectory）记录每次 model call、tool call、approval 步骤；支持 package trust、tool approvals、execution constraints、session records。
- 不同角色需要不同界面：Web workbench 可扩展 **frontend panels**，并与后端通过受控调用连接（full-stack plugins）。
- 每次部署可复用：用 **Skills** 记录任务方法，用插件和 **package lifecycle（install/enable/update/rollback/remove）** 形成可复用能力。
- 物理设备集成方向：通过 MCP 扩展，让任务流程能接入设备状态读取、动作请求、执行回执；目前为“coming soon”。

简言之：**AGH 不是一个单独的模型，而是把模型、工具、任务状态、业务接口、审批与审计连接起来的执行基础**。

---

## 2. 顶层目录结构及各自职责

从工作区根目录（`D:\dshworkplace\agh`）可以看到：

| 顶层条目 | 职责 |
|---|---|
| `.gitattributes`, `.github/`, `.gitignore`, `.npmrc` | Git/CI/包管理配置与仓库卫生 |
| `AGENTS.md`, `CLAUDE.md` | 面向 agent / Claude 工具的说明（仓库约定） |
| `CONTRIBUTING.md`, `SECURITY.md` | 贡献政策与安全/漏洞报告 |
| `LICENSE`, `NOTICE` | Apache-2.0 许可与第三方声明 |
| `README.md`, `README.en.md`, `README.zh-CN.md` | 项目入口说明（英文/中文/全语言） |
| `biome.json` | Biome 格式化/检查配置 |
| `docs/` | 文档中心：指南、开发、架构、安全、demo 等 |
| `examples/` | 可运行示例：后端工具、Web 面板、全栈插件、模拟模型 demo 等 |
| `node_modules/` | 依赖安装目录（工作区依赖） |
| `packages/` | 核心源码包（pnpm workspace）；包括 CLI、daemon、web、协议、插件运行时、资源控制等 |
| `patches/` | 对依赖的补丁（pnpm patch） |
| `pnpm-lock.yaml`, `pnpm-workspace.yaml` | pnpm workspace 与 lockfile |
| `start-local-windows.ps1` | Windows 本地启动脚本 |
| `third-party/` | 第三方组件/资源 |
| `tools/` | 构建/开发/基准工具脚本 |
| `tsconfig.base.json`, `tsconfig.config.json`, `tsconfig.json` | TypeScript 项目引用与编译配置 |
| `vitest.config.ts`, `vitest.sha
```
