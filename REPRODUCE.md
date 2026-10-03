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

```powershell
# TODO：靶场与工具层完成后补齐
```

## 5. 验证判据（怎么算跑通）

| 步骤 | 期望结果 |
| --- | --- |
| AGH 自检 | `node agh\...\agnes.mjs doctor provider --probe` 输出 `✓ provider ... inference verified` |
| 靶场健康 | API `GET /health` 返回 200 |
| 攻击闭环 | 至少 1 个攻击在修复前失败（有最小复现），修复后同攻击不再复现 |
| 报告 | `evidence/` 下生成机器可读 JSON + 人类可读 Markdown 各一份 |

> 尚未完成的部分以 `TODO` 标注，提交前必须清零。
