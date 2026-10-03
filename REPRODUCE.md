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

### 4.1 安装 Python 依赖（仅一次）

```powershell
# 需要 Python 3.11+，且装有 fastapi/uvicorn/numpy/pytest/requests/scipy
cd <仓库根目录>
& "C:\Users\<你的用户名>\AppData\Local\Programs\Python\Python313\python.exe" -m pip install -r requirements.txt
```

> `start-all.ps1` / `tools/run_tests.py` / `tools/measure_ground_truth.py` 会**自动探测**本机所有 Python 解释器，跳过缺少 `uvicorn` 的候选（如 miniconda 无依赖的那个）。可设 `$env:QBC_PYTHON` 显式指定。

### 4.2 起服务（人类交互终端用，前台常驻）

```powershell
.\scripts\start-all.ps1 -Foreground   # 前台常驻（Ctrl+C 停止）
.\scripts\start-all.ps1              # 后台隐窗口常驻
.\scripts\stop-all.ps1               # 停止 8081/8082
```

服务地址：solver `http://127.0.0.1:8081`（`/health` `/solve`），oracle `http://127.0.0.1:8082`（`/health` `/exact`）。

### 4.3 跑全部测试（一条命令，自包含，无需手动起服务）

```powershell
python tools\run_tests.py     # 自起 solver+oracle -> 等 /health -> pytest 20 条 -> 自停
```

**期望：`20 passed`**（7 条 `tests/test_numerics.py` 无需常驻服务 + 13 条 `tests/test_services.py` 自起服务）。

### 4.4 跑独立基准测量（D4，B 角色专属，Agent 不可见）

```powershell
python tools\measure_ground_truth.py   # 自起服务 -> 测 P1-P4 -> 写 ground-truth/ground-truth.json -> 自停
```

**期望输出**（默认无故障配置）：
- P1 FTCS 临界 r* ≈ 0.5（理论 0.5）
- P2 网格 51→101 误差比 ≈ 65.5（纯空间二阶标称 4，因 r=0.4 固定下步数暴涨被高阶压缩，已修 record_every bug）
- P3 对流振荡临界 Pe* ≈ 2.75（理论 2.0，扩散项压制振荡）
- P4 Neumann-Neumann 总热量相对漂移 ≈ 0.0（守恒）

### 4.5 单独验证对流项生效（10/7 交付项）

```powershell
python tools\verify_advection.py   # 自起服务 -> 无对流 vs 有对流 v=0.5 -> 对比稳态分布 -> 自停
```

**期望**：无对流时 u(0.4)=u(0.6)（对称）；有对流 v=0.5 时峰右移，u(0.6)>u(0.4)（下游耗散）。返回 `peclet = 0.01`（v*dx/alpha）。

### 4.6 故障开关（D3，默认全 OFF，不通过 HTTP 暴露）

```powershell
# 默认（全 OFF，诚实行为）：
.\scripts\start-all.ps1 -Foreground

# 开 CFL 故障（允许 r>0.5 进入不稳定区，供 Agent 攻击）：
$env:QBC_FAULT_CFL_GUARD="off"; .\scripts\start-all.ps1 -Foreground

# 开共享状态故障（跨请求污染）：
$env:QBC_FAULT_SHARED_STATE="on"; .\scripts\start-all.ps1 -Foreground
```

4 个开关：`QBC_FAULT_CFL_GUARD` / `QBC_FAULT_SHARED_STATE` / `QBC_FAULT_SILENT_CLAMP` / `QBC_FAULT_PARTIAL_ON_TIMEOUT`，默认全 OFF。

## 5. 验证判据（怎么算跑通）

| 步骤 | 期望结果 |
| --- | --- |
| AGH 自检 | `node agh\...\agnes.mjs doctor provider --probe` 输出 `✓ provider ... inference verified` |
| 靶场健康 | API `GET /health` 返回 200 |
| 攻击闭环 | 至少 1 个攻击在修复前失败（有最小复现），修复后同攻击不再复现 |
| 报告 | `evidence/` 下生成机器可读 JSON + 人类可读 Markdown 各一份 |

> 尚未完成的部分以 `TODO` 标注，提交前必须清零。
