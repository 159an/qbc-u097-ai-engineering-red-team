# QBC · AGH 运行底座与三类一致性测试套件

参赛信息（2026 江苏省高校 AI+科学与工程创新实践黑客松）

| 项 | 值 |
| --- | --- |
| 组别 | 本科生组 |
| 参赛编号 | U097 |
| 队伍名称 | QBC |
| 作品 ZIP 命名 | `组别-参赛编号-队伍名称-队长姓名`（提交前补队长姓名） |
| 智能体运行底座 | Agnes Harness（AGH）`https://github.com/AgnesAI-Labs/agnes-harness` |
| 模型 | `agnes-3.0-flash`（Agnes AI 中国站网关 `https://api.agnes-ai.cn/v1`，仅此一家） |

本仓库当前内容是**作品的运行底座与验证基础设施**：在 Windows 上从源码构建 AGH、接入仅限 Agnes 的模型、跑通真实工具调用链，并提供一套可复现的「正常 / 边界 / 失败」三类一致性测试。真正的参赛选题在选定后接入此底座。

---

## 一、目录结构

```
hackathon-qbc/
├─ tools/
│  ├─ record-env.ps1            记录 AGH commit / 工具链版本 / 构建产物摘要（不含凭据）
│  ├─ start-agh.ps1             启动 AGH Web 工作台（前台），或 -Check 只做平台与推理体检
│  ├─ open-workbench.ps1        桌面快捷方式调用的启动器（幂等、静默、失败弹窗）
│  ├─ stop-workbench.ps1        停止由本项目构建产物启动的服务
│  ├─ install-desktop-shortcuts.ps1  创建/重建桌面快捷方式
│  ├─ make-fixtures.mjs         生成测试夹具，并独立计算基准事实 ground-truth.json
│  ├─ conformance-tests.json    三类测试定义（提示词、预期终态、预期校验判定、期望数值）
│  ├─ run-conformance.ps1       执行测试：隔离工作区 → 跑任务 → 导出 AGH 轨迹 → 文件系统断言
│  ├─ analyze-trajectory.mjs    解析 AGH 事件流，产出断言报告与可发布脱敏轨迹
│  ├─ analyze-all.ps1           对已采集轨迹批量重判定（不再调用模型）
│  └─ build-evidence-index.mjs  汇总为 CONFORMANCE-SUMMARY.md
├─ fixtures/                    测试夹具 + ground-truth.json（由脚本生成，勿手改）
├─ work/<用例>/                 每个测试的隔离工作区（可删，重跑自动重建）
└─ evidence/                    全部运行证据
   ├─ CONFORMANCE-SUMMARY.md    三类测试汇总（自动生成）
   ├─ VERSION-LOG.md            时间与版本记录（追加式）
   ├─ env-record-*.json         同上，机器可读
   ├─ agh-provider-configuration.json  provider 配置（只含凭据引用，无密钥值）
   ├─ task01-*.{json,md,jsonl}  演示任务（满足「≥3 连续步骤」）
   ├─ conformance/<ID>.*        各用例的轨迹、断言报告、汇总、脱敏轨迹
   └─ logs/                     构建、配置、探测的原始日志
```

## 二、环境要求

已实机验证的组合（Windows）：

| 项 | 版本 | 备注 |
| --- | --- | --- |
| OS | Windows（win32 x64） | AGH 官方仅在 macOS 记录过本地检查，Windows 需自行验收 |
| Node.js | `>= 24.10`（实测 v24.19.0） | |
| pnpm | **10.34.5**（AGH 根 `packageManager` 锁定） | 必须经 `corepack pnpm` 调用，全局 pnpm 版本不同不影响 |
| MSVC | Visual Studio 2026 (18.6) + VC.Tools.x86.x64（实测 14.51.36231） | 编译 AGH 原生 helper |
| Windows SDK | 10.0.26100（本机位于 `D:\Windows Kits\10`） | 非默认盘时注册表 `KitsRoot10` 仍能定位 |
| PowerShell | 5.1（Desktop） | 本仓库脚本已按 5.1 处理编码（见「注意事项」） |

## 三、从零复现

### 1. 构建 AGH

```powershell
git -c http.proxy= -c https.proxy= clone --depth 1 https://github.com/AgnesAI-Labs/agnes-harness.git D:\dshworkplace\agh
Set-Location D:\dshworkplace\agh

# 锁定版本的依赖安装
$env:COREPACK_ENABLE_DOWNLOAD_PROMPT = '0'
corepack pnpm install --frozen-lockfile

# 准备 Node 头文件与导入库（原生 helper 编译前置）
& .\.github\scripts\prepare-windows-native.ps1 -CacheRoot "$env:LOCALAPPDATA\node-gyp\Cache"

# 构建完整本地分发包
corepack pnpm --filter @agnes/cli build:local --output-dir D:\dshworkplace\agh-build\runtime
node D:\dshworkplace\agh-build\runtime\agnes.mjs --help
```

### 2. 接入 Agnes 模型

`agh config` 在非 TTY 下会用 readline 读管道输入，提示输出到 stderr，因此可脚本化：

```powershell
# 回答顺序：账号名 → Provider 序号（Agnes AI = 12）→ Base URL（回车用默认）→ API Key → 模型序号
@('QBC-Agnes','12','','<你的 Agnes API Key>','1') |
  node D:\dshworkplace\agh-build\runtime\agnes.mjs config
```

配置结果可通过 `evidence/agh-provider-configuration.json` 核对：只应有 **1 个 account**，`id = agnes-ai`，`model = agnes-3.0-flash`，且 `credentialRef` 是引用（`secret://<redacted>

### 3. 体检并启动

```powershell
pwsh -File tools\start-agh.ps1 -Check   # 平台探测 + 真实推理探测
pwsh -File tools\start-agh.ps1          # Web 工作台 → http://127.0.0.1:4177/
```

### 3b. 桌面快捷方式（双击即用）

```powershell
pwsh -File tools\install-desktop-shortcuts.ps1
```

会创建两个桌面图标：

| 图标 | 行为 |
| --- | --- |
| **AGH 工作台** | 双击后：服务已在跑 → 直接开浏览器；没在跑 → 后台静默启动并等就绪，再开浏览器。全程无命令行窗口，失败会弹窗并附日志尾部 |
| **AGH 停止** | 停止由本项目构建产物启动的服务（关闭浏览器**不会**停止后台服务，需要用它） |

启动器是幂等的：重复双击不会重启服务、不会打断正在执行的任务。工作区默认是本项目目录，可用 `-Workspace` 覆盖：

```powershell
pwsh -File tools\open-workbench.ps1 -Workspace D:\some\other\project
pwsh -File tools\open-workbench.ps1 -Restart     # 强制重启
```

安全边界：启动器与停止器都**只认命令行里包含本项目 `agnes.mjs` 路径且含 `serve` 的 Node 进程**，同端口被别的程序占用时不会误杀，而是弹窗说明。服务输出落在 `evidence/logs/workbench-*.out.log` / `.err.log`。

### 4. 重跑三类一致性测试（完整证据链）

```powershell
node tools\make-fixtures.mjs        # 生成夹具与基准事实
pwsh -File tools\run-conformance.ps1   # 跑 5 个用例并导出 AGH 轨迹（会调用模型）
pwsh -File tools\analyze-all.ps1       # 对轨迹做断言判定（不再调用模型）
node tools\build-evidence-index.mjs    # 汇总为 CONFORMANCE-SUMMARY.md
pwsh -File tools\record-env.ps1        # 追加版本与时间记录
```

## 四、测试设计要点

三类测试的目的不是「跑通」，而是**尽可能证明结论不可信**：

- **基准事实独立计算**：`ground-truth.json` 由 `make-fixtures.mjs` 从真实写入的字节算出，不是手写期望值，也不让被测方看到。
- **文件系统级断言**：失败类用例不看模型说了什么，只检查禁止产物是否真的不存在（`F2`）。
- **预期终态按用例正确行为设定**：`B2` 期望 `blocked` 且回合校验 `fail`——因为该任务确实未完成，校验器不应放行；若期望 `completed`，就等于奖励编造。
- **被拒绝的调用计入工具链**：拒绝路径没有 `effect/intent` 事件，工具名只能从事件 `origin` 还原（见 FINDING-3）。
- **失败断言如实保留**：`N1` 的数值断言刻意保持 FAIL，它就是套件最有价值的产出（见 FINDING-1）。

## 五、已识别缺陷

| 编号 | 结论 | 严重度 |
| --- | --- | --- |
| FINDING-1 | 模型 token 级算术不可靠（12 行 CSV 列均值算错），且 AGH 内建回合校验仍判 `pass`——校验器没有领域基准事实 | 高 |
| FINDING-2 | 非交互模式下审批不可用，字节级测量被安全阻断；模型正确撤回估计值而非编造 | 中 |
| FINDING-3 | 被拒绝的工具调用没有 `effect/intent` 事件，只按 intent 统计会漏掉整条拒绝路径 | 中 |

详见 `evidence/CONFORMANCE-SUMMARY.md`。

## 六、注意事项（踩过的坑）

1. **PowerShell 5.1 按系统 ANSI 读取无 BOM 的 `.ps1`**，中文会乱码导致解析失败。本仓库所有 `.ps1` 均为 UTF-8 **带 BOM**；用工具改写过脚本后需重新补 BOM。
2. **`$ErrorActionPreference='Stop'` + 原生命令 stderr**：pnpm 的 `console.warn` 会被 PowerShell 转成终止性 `NativeCommandError`，导致构建被误判失败。判定构建结果请以 `$LASTEXITCODE` 为准。
3. **`serve` 的 Web origin 绑定默认端口 4177**，强行 `--port 4180` 会报 `origin does not match`。
4. **`--raw` 轨迹导出不做脱敏**（含路径、用户名）。发布前请使用 `analyze-trajectory.mjs --sanitize` 生成的脱敏版本，并确认公开发布的仓库中不含 `secrets/`。
5. **`@ant-design/icons-svg` 等包未随包发布 LICENSE 文件**，构建时会出现 `No LICENSE file found` 警告，属预期，不影响产物。

## 七、凭据处理

- API Key 只存在于两处：AGH credential store（`~/.agh/secrets/agnes-ai/...`）与本地 `D:\dshworkplace\secrets\agnes.key`（不在本仓库内）。
- 本仓库、证据文件、日志、轨迹中**均不含密钥明文**，已逐项扫描确认（`sk-` 模式）。
- 赛事要求获奖队伍公开代码库，因此 `.gitignore` 已排除 `secrets/`、`*.key`、`.env`、`.agh/`、`data/`、`work/`。**若你曾把 Key 粘贴到任何聊天/issue/截图中，请在提交前到 Agnes 控制台吊销并重建。**

## 八、许可与素材来源

- AGH 为 Apache-2.0（`https://github.com/AgnesAI-Labs/agnes-harness`），本仓库未修改 AGH 源码。
- 本目录内的脚本、夹具、文档为队伍原创。测试夹具为脚本生成的合成数据，不含第三方数据。
