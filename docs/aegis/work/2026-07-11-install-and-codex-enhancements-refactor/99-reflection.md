# 安装与 Codex 增强全面重构 - Reflection

## 目标闭环

- Goal status: `complete`
- Stop state: `done`。
- Success evidence: 六项需求均有源码、负向退役检查、自动化回归与 Windows 产物证据。
- Non-goals respected: 未清理或迁移用户 SQLite、Credential Manager、真实 Codex
  LevelDB；未复制 CodexPlusPlus AGPL 源码或资源；未重新引入通用配置系统。
- Workspace integrity: `aegis-workspace.py bundle` 已生成 proof bundle，随后
  `aegis-workspace.py check` 通过；这些仅验证记录结构，证据充分性由 fresh checks 支撑。

## 关键判断

1. 采用 delete-first，而不是隐藏 UI 后保留 profile/protocol dormant owner。
2. Codex bundled catalog 是唯一模型候选来源；缺失 `visibility` 必须 fail closed。
3. Statsig unlock、Store/CDP launcher 与 marketplace script 分属独立 owner，避免
   profile-derived fallback 或通用 injection owner 回流。
4. 产物本身也是退役边界。旧 `app.zip` 中的 `.pyc`、`.git`、测试与旧 VBS 证明
   “源码已删除”不足以支持 release claim，因此补上 Flet exclude/cleanup 与构建后
   allowlist 守卫。
5. Flet `.exe --version` 是平台不支持的探针；修复文档和验证方法，而不是为测试
   制造新的运行时参数兼容分支。
6. Windows npm 命令是 `.CMD` shim 时，检测成功并不代表裸命令可被 `shell=False`
   执行；canonical owner 必须执行 `shutil.which()` 返回的路径，而不是在 UI 层吞错。

## 修复轨与退役轨

- Repair track: 四操作 UI、安装器、bundled-catalog/Statsig、Store/CDP 和 marketplace
  owner 均有聚焦测试与 final package evidence。
- Retirement track: configuration/storage/secret/model-fetch/config-writer/deeplink/
  protocol-document/legacy injection、installer registry block、旧 VBS 和相关测试已删除。
- Compatibility retained: 正常 GUI 启动、single-instance、状态刷新、前置环境处理、
  应用更新、Codex/Claude 安装。
- Compatibility intentionally removed: profiles、配置写入、模型抓取、`--import-url`、
  `llanfeng-code://`、scheme 注册和 profile-derived launch。
- Retained legacy carrier: none。

## 复杂度闭环

- Python source/tests 从 9,549 行降至 5,305 行，净减少 4,244 行。
- 所有维护文件均小于 2,000 行。
- `app.py` 645 行、launcher 387 行、unlocker 660 行略高于计划软目标，但职责聚焦，
  没有 unresolved major complexity alert。
- 打包守卫增加了约 100 行 PowerShell，但它位于分发 owner，替代人工清缓存和
  不可靠的 release 假设；没有增加运行时 fallback。

## 基线对齐

- Product / Requirement Baseline: `aligned`
- Architecture / Runtime Boundary Baseline: `aligned`
- Scope: `both`
- ADR backfill: 已创建 ADR-0001 并同步 post-refactor baseline。

## 风险与下一步

Residual risk 仍集中在真实宿主：用户 Codex LevelDB、账号相关 marketplace 响应、
renderer 版本变化以及交互式安装/卸载。最有价值的下一步验证是在隔离的 Windows
测试账号中完成一次模型解锁、增强启动和安装/卸载 walkthrough，并保留 LevelDB
备份与 CDP 日志。

## 反熵声明

- Deletion class: `code-retirement` 与 build-derived-state exclusion。
- New canonical owners: installer、Statsig unlocker、Store/CDP launcher、marketplace module。
- Source-of-truth data risk: none for retired code; bounded append-only risk for retained Statsig writer。
- User confirmation required for data deletion: no deletion was performed。
- Decision: `delete-first`，无 compat exception。

Method Pack output supports the completion claim with evidence but does not itself grant runtime authority.

## npm.CMD 回归闭环

- Symptom: 点击安装/更新时在 `ensure_npm_registry()` 抛出 `WinError 2`。
- Root cause: Windows 上 npm 由 `E:\nodejs\npm.CMD` 提供，旧执行路径检测到 shim
  后仍调用裸 `npm`。
- Repair: installer 与 environment 两个既有 owner 统一执行解析路径，保持
  `shell=False`；没有创建 fallback owner。
- Verification: 本机 resolved shim 返回 npm `11.12.1`，全量 `94 passed`，Ruff、
  compileall、archive 精确源码比对和 Inno Setup 重建均通过。
- Residual risk: 尚未用新安装包完成一次人工 GUI 点击 walkthrough；用户列出的第 2
  项没有报错内容，不能假定与本修复相同。
