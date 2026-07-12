# Proof Bundle - 2026-07-11-install-and-codex-enhancements-refactor

## Method Pack Boundary

This proof bundle is an advisory Aegis Method Pack record. It does not determine evidence sufficiency, produce authoritative `GateDecision`, or grant `completion authority`.

## Task Intent

- Requested outcome: 移除配置与协议体系，仅保留 Codex/Claude 一键安装，并增加 Codex 模型白名单与插件市场解锁。
- Scope: 应用 UI、CLI、配置/协议代码退役、模型白名单解锁、Codex Desktop CDP 插件市场增强、依赖、测试、文档与 Windows 打包。

## Impact

- Compatibility boundary: 保留应用启动、更新与 Codex/Claude 一键安装；明确移除 llanfeng-code:// 协议和配置导入能力。
- Non-goals:
- 不复制完整 CodexPlusPlus 插件快照，不实现通用配置编辑器，不迁移或清理用户旧数据库。

## Evidence Bundle Refs

- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-clean-flet-app-archive.json
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-codex-bundled-model-catalog.json
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-codexplusplus-marketplace-reference.json
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-complexity-closure-after-npm-cmd-repair.json
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-complexity-closure.json
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-final-python-verification.json
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-final-windows-installer.json
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-retirement-and-package-guard.json
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-strict-visibility-regression.json
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-task1-model-unlocker-tests.json
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-windows-npm-cmd-refreshed-artifacts.json
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-windows-npm-cmd-regression.json
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/evidence-bundle-draft-windows-npm-cmd-root-cause.json

## Drift Check

- Scope status: The repair remains inside the retained Codex/Claude installation and environment-detection boundary.
- Compatibility status: shell=False is preserved; commands use the resolved executable or Windows .CMD shim without adding a UI fallback or duplicate owner.
- Retirement status: No retired configuration, protocol, profile, or CodexPlusPlus fallback path was restored; app.zip contains zero forbidden retired entries.
- Advisory decision: continue
