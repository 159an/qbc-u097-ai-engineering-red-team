# 复现方式（REPRODUCE）

> 赛事要求提交"可运行作品或可复现方式"。本文件是唯一入口：照抄命令即可跑通。

## 1. 环境

| 项 | 版本 / 要求 | 说明 |
| --- | --- | --- |
| OS | Windows 11（本项目在 Windows 上验证） | Linux/macOS 可参照，AGH 亦支持 |
| Node.js | **≥ 24.10**（实测 v24.19.0） | AGH 的硬性要求 |
| pnpm | **10.34.5**（通过 Corepack 调用） | 仓库 `packageManager` 锁定 |
| MSVC | Visual Studio C++ Build Tools + Windows SDK | 仅编译 AGH 原生模块时需要 |
| Python | 3.11+（仅数据处理脚本需要） | 可选 |

### 路径配置（`tools/` 下脚本如何找到 AGH）

脚本**不写死任何本机绝对路径**。AGH 入口按以下优先级解析，取第一个存在的：

| 优先级 | 位置 |
| --- | --- |
| 1 | 环境变量 `AGH_ENTRY`（显式指定，优先级最高） |
| 2 | `<仓库根>\agh\packages\cli\dist\local\agnes.mjs`（AGH 克隆在仓库内） |
| 3 | `<仓库根的上级>\agh-build\runtime\agnes.mjs`（构建到仓库外） |
| 4 | `<仓库根>\agh-build\runtime\agnes.mjs`（构建在仓库内） |

相关环境变量：

| 变量 | 用途 |
| --- | --- |
| `AGH_ENTRY` | `agnes.mjs` 入口的绝对路径 |
| `AGH_REPO` | AGH 源码仓库路径（用于记录 commit / 版本） |
| `AGH_KEY_FILE` | 本地密钥文件路径（**仅**在 `-WithEnvKey` 应急回落时读取） |

```powershell
# 例：底座构建在别处时显式指定
$env:AGH_ENTRY = "D:\my\agh-build\runtime\agnes.mjs"
$env:AGH_REPO  = "D:\my\agnes-harness"
```

解析全部落空时，脚本会**列出已尝试的位置并给出两种解决办法**，而不是只说"找不到"。
解析逻辑集中在 `tools/agh-env.ps1`，各脚本共用同一份判断标准。

## 2. 获取并构建 Agnes Harness（AGH）

AGH 是比赛指定的执行底座，**不随本仓库分发**，按官方源码构建：

```powershell
git clone https://github.com/AgnesAI-Labs/agnes-harness.git agh
cd agh
git checkout e4e782f      # 本项目验证过的 commit

# 依赖安装（本机实测：pnpm 默认 isolated linker 会因无符号链接权限失败）
corepack pnpm install --frozen-lockfile --config.node-linker=hoisted

# 编译 Windows 原生模块：先把 MSVC 环境导入当前会话，
# 这样 build-native.mjs 就不会去 spawn powershell.exe 取 VS 环境
$env:AGNES_NODE_HEADERS = "<你的 node-gyp headers 目录>\24.19.0"
& cmd.exe /c 'call "D:\VSStudio\Common7\Tools\VsDevCmd.bat" -arch=x64 -no_logo && set' |
  ForEach-Object { $i = $_.IndexOf('='); if ($i -gt 0) { Set-Item ("env:" + $_.Substring(0,$i)) -Value $_.Substring($i+1) } }
node packages\system-node\scripts\build-native.mjs

# 构建本地分发
corepack pnpm --filter @agnes/cli build:local
node packages\cli\dist\local\agnes.mjs --help
```

> 更完整的踩坑记录见 [docs/AGH-部署笔记.md](docs/AGH-部署笔记.md)。

## 3. 配置 Agnes 模型

```powershell
$env:AGH_HOME = "$env:USERPROFILE\.agh"     # 或任意私有目录
$env:AGNES_PROFILE = "local-dev"
node agh\packages\cli\dist\local\agnes.mjs config   # 交互式：选 Agnes AI → 填 Key → 测试连接 → 选模型 → 保存
```

参数：Provider `agnes-ai`，Base URL `https://api.agnes-ai.cn/v1`，模型 `agnes-3.0-flash`。

**密钥只允许放在环境变量或 AGH 私有凭据目录，任何情况下不得写入本仓库。**

## 4. 跑起来

### 4.1 运行底座自检（已完成，可复现）

```powershell
# 平台探测 + 真实推理探测（会实际调用 Agnes 模型）
pwsh -File tools\start-agh.ps1 -Check
```

期望：`provider` 状态 `ok`，检查项 `models_endpoint` / `minimal_inference` / `fields` 全绿，
模型 `agnes-3.0-flash` 的 `observed=true`、`mismatches=[]`。

### 4.2 三类一致性测试（正常 / 边界 / 失败，已完成，可复现）

赛事必填材料第 6 项要求「测试样例（正常、边界、失败三类）」。本仓库已有一套可复现的套件：

```powershell
node tools\make-fixtures.mjs            # 生成测试夹具，并**独立计算基准事实**
pwsh -File tools\run-conformance.ps1    # 跑 5 个用例，导出 AGH 原生轨迹（会调用模型）
pwsh -File tools\analyze-all.ps1        # 对已有轨迹做断言判定（不再调用模型）
node tools\build-evidence-index.mjs     # 汇总为 evidence/CONFORMANCE-SUMMARY.md
pwsh -File tools\record-env.ps1         # 追加版本与时间记录
```

设计要点（为什么这套证据可信）：

| 要点 | 说明 |
| --- | --- |
| 基准事实独立计算 | `fixtures/ground-truth.json` 由脚本从**真实写入的字节**算出，不是手写期望值，被测方也看不到 |
| 期望终态按用例正确行为设定 | `B2` 期望 `blocked` 且回合校验 `fail`——该任务确实未完成，期望 `completed` 等于奖励编造 |
| 文件系统级断言 | `F2` 不看模型说了什么，只检查禁止产物**是否真的不存在** |
| 被拒绝的调用计入工具链 | 拒绝路径没有 `effect/intent` 事件，工具名只能从事件 `origin` 还原（见 FINDING-3） |
| 失败断言如实保留 | `N1` 的数值断言刻意保持 FAIL，它是套件最有价值的产出（见 FINDING-1） |

### 4.3 靶场与攻击闭环

靶场（工程传热求解服务 + 独立解析解基准）已完成，最小可跑路径见下文 §6「Python 版靶场（成员B 交付）最小复现」。

```powershell
# 1. 环境：Python 3.13（或 requirements.txt 满足的 3.11+）
python -m pip install -r requirements.txt

# 2. 起服务（solver 8081 / oracle 8082），两个 /health 均应 200
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-all.ps1

# 3. 端到端自检（14 项，纯标准库、不含 LLM 调用），期望「通过 14 / 14」
python tools\e2e_acceptance.py
#    （脚本内部先探测 8081/8082 两个 /health，不可用则 exit 1；
#     逐条 PASS/FAIL 后打印「通过 N / 14」；详见 evidence/12-d5-start-stop-clean.txt §3）

# 4. 全量回归测试（期望 22 passed）
python tools\run_tests.py

# 5. 四性质基准测量（P1–P4）
python tools\measure_ground_truth.py
git checkout -- ground-truth/ground-truth.json   # 复原，避免把本次测量结果误提交

# 6. 停止服务（期望 terminated 2 / both /health endpoints down）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop-all.ps1
```

## 5. 验证判据（怎么算跑通）

| 步骤 | 期望结果 | 状态 |
| --- | --- | --- |
| AGH 自检 | `doctor provider --probe` 返回 `ok:true`，三项检查全绿 | ✅ 已通过 |
| 三类一致性测试 | `evidence/CONFORMANCE-SUMMARY.md` 中未解释的失败为 0 | ✅ 49/50 通过，1 条为已识别缺陷 |
| 靶场健康 | 求解服务 `GET /health` 与解析解服务 `GET /health` 均返回 200 | ✅ 已通过（见 §4.3 / §6） |
| 攻击闭环 | 至少 1 个发现被独立基准确认为真，且给出可二分收敛的最小反例 | ✅ 已通过（见 `evidence/target-tests/`、`evidence/discovery/`） |
| 报告 | `evidence/` 下生成机器可读 JSON + 人类可读 Markdown 各一份 | ✅ 已通过（见 `evidence/CONFORMANCE-SUMMARY.md`、`evidence/` 下各 `.report.md` / `.summary.json`） |

> 本文件所有 `TODO` 已在提交前清零（含上表各行「⏳ 待建设」→ 已全部更新为「✅ 已通过」）；如后续新增待办请沿用 `TODO` 标注方式。

## 6. Python 版靶场（成员B 交付）最小复现

> 本仓库已交付的靶场实现包含 Node.js 版（`src/*.mjs`）与 **Python 版**（`services/solver/` + `services/oracle/`，FastAPI/uvicorn，成员B 交付）两套。下面是 Python 版的最小复现路径，与上文 4.3「靶场与攻击闭环」并列，二者互不依赖，可各自独立验证。

### 环境

- Python 3.13（或满足 `requirements.txt` 的任意 3.11+ 版本）
- 依赖安装：`python -m pip install -r requirements.txt`

### 步骤

```powershell
# 1. 启动两个服务（solver 8081 / oracle 8082）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-all.ps1

# 2. 两个 /health 均应返回 200 + 端到端自检（14 项，纯标准库、不含 LLM）
#    GET http://127.0.0.1:8081/health
#    GET http://127.0.0.1:8082/health
#    两项 /health 均 200 后，运行端到端自检脚本（14 项：含上表全部 12 项边界/物理判据 + 2 项 oracle /health/有闭式解探测）
python tools\e2e_acceptance.py   # 期望输出末行「通过 14 / 14」，exit 0

# 3. 全量回归测试（期望 22 passed）
python tools\run_tests.py

# 4. 四性质基准测量（P1=0.5 / P2=2.0 / P3=2.0 / P4 H_fvm 0.0），
#    会写 ground-truth/ground-truth.json
python tools\measure_ground_truth.py
git checkout -- ground-truth/ground-truth.json   # 复原，避免把本次测量结果误提交

# 5. 停止两个服务（期望 terminated 2 / both /health endpoints down）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop-all.ps1
```

### 说明

- `tools/measure_ground_truth.py` 会**写入** `ground-truth/ground-truth.json`（每次测量结果会覆盖该文件）。若希望提交前的仓库状态保持干净，跑完可用：

  ```powershell
  git checkout -- ground-truth/ground-truth.json
  ```

  复原到上一次提交的内容，再执行后续提交/推送流程。
