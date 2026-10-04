# evidence

运行与验证证据（提交材料的一部分）。

建议存放：

- `attack-<n>-trajectory.json`：AGH 会话轨迹导出（含工具调用与返回值）
- `minimal-repro-<n>.md`：最小复现步骤
- `report-<n>.md` / `.json`：机器可读 + 人类可读的工程验证报告
- `before-after-<n>.md`：修复前后对比

> 注意体积：只保留能支撑结论的片段，原始大文件另存并说明获取方式。

> 已移除文件说明：`evidence/agh-provider-configuration.json` 已从仓库移除（理由：含 AGH 账号标识 / credentialRef / baseUrl 等敏感配置，不随公开仓库发布；如需重建请在本机 AGH 私有目录重新生成）。

