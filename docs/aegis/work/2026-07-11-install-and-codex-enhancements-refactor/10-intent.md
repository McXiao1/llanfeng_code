# 安装与 Codex 增强全面重构 - Intent

## TaskIntentDraft

- Requested outcome: 移除配置与协议体系，仅保留 Codex/Claude 一键安装，并增加 Codex 模型白名单与插件市场解锁。
- Goal: 以单一职责架构完成安装器与 Codex 增强能力重构，彻底退役旧配置 owner，同时保护用户持久数据。
- Success evidence:
- 配置与协议相关源码、入口、依赖、测试和文档全部退役；Codex/Claude 安装、模型解锁、插件市场增强有自动化测试且全量验证通过。
- Stop condition: 全部验收证据满足则完成；发现持久数据破坏风险、未知 Codex 契约或验证不足则暂停；超出已批准设计则返回设计评审。
- Non-goals:
- 不复制完整 CodexPlusPlus 插件快照，不实现通用配置编辑器，不迁移或清理用户旧数据库。
- Scope: 应用 UI、CLI、配置/协议代码退役、模型白名单解锁、Codex Desktop CDP 插件市场增强、依赖、测试、文档与 Windows 打包。
- Change kinds:
- architecture-refactor
- Risk hints:
- 跨模块删除、LevelDB 写入、Codex Desktop CDP 注入和安装器注册表变更均需边界验证。

## BaselineReadSetHint

- README.md
- Codex.md
- pyproject.toml
- scripts/installer.iss
- build/reference/renderer-inject.js

## BaselineUsageDraft

- Required baseline refs:
- README.md
- Codex.md
- pyproject.toml
- scripts/installer.iss
- build/reference/renderer-inject.js
- Acknowledged before plan:
- none
- Cited in plan:
- none
- Missing refs:
- README.md
- Codex.md
- pyproject.toml
- scripts/installer.iss
- build/reference/renderer-inject.js
- Advisory decision: needs-baseline-readback

## ImpactStatementDraft

- Compatibility boundary: 保留应用启动、更新与 Codex/Claude 一键安装；明确移除 llanfeng-code:// 协议和配置导入能力。
- Affected layers:
- Flet UI/CLI
- Codex model catalog/Statsig LevelDB
- Codex Desktop CDP/plugin marketplace
- packaging/docs/tests
- Owners:
- app.py 负责编排；installer.py 负责安装；codex_statsig_unlocker.py 负责 Codex bundled catalog 与 Statsig 白名单；codex_desktop_launcher.py 负责 CDP 生命周期；codex_plugin_marketplace.py 负责插件市场运行时补丁。
- Invariants:
- 不修改用户当前默认模型，不解锁 visibility=hide 或 supported_in_api=false 模型，不自动删除用户 SQLite/Keyring 数据，不在未经明确确认时强制终止正在运行的 Codex。
- Non-goals:
- 不复制完整 CodexPlusPlus 插件快照，不实现通用配置编辑器，不迁移或清理用户旧数据库。

These records are Method Pack drafts / hints, not authoritative runtime decisions.

## BaselineUsageDraft

- Required baseline refs:
- README.md
- Codex.md
- pyproject.toml
- scripts/installer.iss
- build/reference/renderer-inject.js
- Delivered context refs:
- none
- Acknowledged before plan:
- README.md
- Codex.md
- pyproject.toml
- scripts/installer.iss
- build/reference/renderer-inject.js
- Cited in plan:
- docs/aegis/specs/2026-07-11-install-and-codex-enhancements-design.md
- Missing refs:
- none
- Advisory decision: pause-for-user

