# AGH 部署笔记（Windows）

本项目使用 **Agnes Harness (AGH)** 作为执行底座，以下是在 Windows 上真实踩过并已解决的坑，供复现者避坑。

## 1. pnpm 安装：ERR_PNPM_SYMLINK_FAILED

默认 isolated linker 需要创建符号链接，本机进程无该权限（`Maximum call stack size exceeded` / `SYMLINK_FAILED`）。

**解决**：改用 hoisted linker，并把 store 指到有权限的目录：

```powershell
corepack pnpm install --frozen-lockfile --config.node-linker=hoisted --store-dir <可写目录>
```

## 2. 原生模块编译：spawnSync powershell.exe EPERM

`packages/system-node/scripts/build-native.mjs` 会调用 `powershell.exe` 执行 VsDevCmd 来取 MSVC 环境。若所在环境限制子进程管道，会直接失败。

**解决**：先自己在当前会话导入 MSVC 环境，脚本检测到 `VCToolsInstallDir` 已存在就会跳过该桥接：

```powershell
& cmd.exe /c 'call "D:\VSStudio\Common7\Tools\VsDevCmd.bat" -arch=x64 -no_logo && set' |
  ForEach-Object { $i = $_.IndexOf('='); if ($i -gt 0) { Set-Item ("env:" + $_.Substring(0,$i)) -Value $_.Substring($i+1) } }
node packages\system-node\scripts\build-native.mjs   # 需要 AGNES_NODE_HEADERS 指向 node-gyp headers
```

## 3. 凭据目录必须私有（Windows）

AGH 读取 API Key 时会校验目录/文件的 DACL：只允许当前用户、SYSTEM、Administrators。若目录里混入了其他令牌 SID，会报 `CONFIG_CREDENTIAL_STORE / The credential store is unavailable`。

**解决**：让 AGH 自己创建 home（首次保存配置时它会用原生模块建私有目录），或用 `icacls /inheritance:r /grant:r` 收紧后再写凭据。

## 4. 模型配置

`<AGH_HOME>/profiles/<profile>/configuration.json`（v2）+ `<AGH_HOME>/secrets/<provider>/<name>`（明文 JSON 信封）。

改配置建议直接用 `node agnes.mjs config` 或 Web 工作台的 Provider 设置页，**不要手改**这两个文件。

## 5. 端口

`serve` 默认 `http://127.0.0.1:4177`；daemon 通过命名管道通信（`\\.\pipe\agnes-*`），因此不适合在受限沙箱里运行。
