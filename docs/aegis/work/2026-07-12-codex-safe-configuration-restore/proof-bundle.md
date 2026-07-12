# Proof Bundle - 2026-07-12-codex-safe-configuration-restore

## Method Pack Boundary

This proof bundle is an advisory Aegis Method Pack record. It does not determine evidence sufficiency, produce authoritative `GateDecision`, or grant `completion authority`.

## Task Intent

- Requested outcome: 新增恢复配置按钮，安全恢复 Codex 配置并清除历史模型注入，同时保留登录和用户数据。
- Scope: Statsig owner、恢复事务 owner、Flet UI、路径、测试、打包、文档、ADR、基线和 Windows 产物。

## Impact

- Compatibility boundary: 保留四个既有操作及更新/状态/单实例，并新增一个安全恢复操作。
- Non-goals:
- 不恢复 provider/config/profile/protocol 子系统
- 不删除完整 LevelDB 或 .codex 目录
- 开发测试不操作真实用户 Codex 数据

## Evidence Bundle Refs

- docs/aegis/work/2026-07-12-codex-safe-configuration-restore/evidence-bundle-draft-architecture-and-baseline-sync.json
- docs/aegis/work/2026-07-12-codex-safe-configuration-restore/evidence-bundle-draft-complexity-and-acceptance-closure.json
- docs/aegis/work/2026-07-12-codex-safe-configuration-restore/evidence-bundle-draft-final-fresh-verification.json
- docs/aegis/work/2026-07-12-codex-safe-configuration-restore/evidence-bundle-draft-five-action-restore-ui.json
- docs/aegis/work/2026-07-12-codex-safe-configuration-restore/evidence-bundle-draft-fresh-windows-app-and-archive.json
- docs/aegis/work/2026-07-12-codex-safe-configuration-restore/evidence-bundle-draft-fresh-windows-installer.json
- docs/aegis/work/2026-07-12-codex-safe-configuration-restore/evidence-bundle-draft-full-python-and-retirement-verification.json
- docs/aegis/work/2026-07-12-codex-safe-configuration-restore/evidence-bundle-draft-packaging-and-product-contract.json
- docs/aegis/work/2026-07-12-codex-safe-configuration-restore/evidence-bundle-draft-reversible-config-restore-transaction.json
- docs/aegis/work/2026-07-12-codex-safe-configuration-restore/evidence-bundle-draft-statsig-exact-cache-invalidation.json

## Drift Check

- Scope status: All implementation, packaging, architecture, and evidence work remains inside approved safe scope A and exact mutable targets.
- Compatibility status: Five actions are verified; prior install/update, unlock, marketplace, update, environment, and single-instance contracts remain green.
- Retirement status: Provider/config/profile/protocol owners, whole-LevelDB reset, auth deletion, second writer, and compatibility fallbacks remain absent from runtime and app.zip.
- Advisory decision: continue
