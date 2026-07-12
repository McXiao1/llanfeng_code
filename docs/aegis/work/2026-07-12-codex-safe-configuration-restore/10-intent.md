# Codex 安全配置恢复 - Intent

## TaskIntentDraft

- Requested outcome: 新增恢复配置按钮，安全恢复 Codex 配置并清除历史模型注入，同时保留登录和用户数据。
- Goal: 实现已批准的五操作安全恢复功能，以可逆事务处理 config.toml、models.json 和精确 Statsig 缓存键。
- Success evidence:
- 聚焦与全量测试、auth.json 保留、精确 tombstone、备份回滚、五操作 UI、文档/ADR/基线和 Windows 安装包验证全部通过。
- Stop condition: 全部验收证据满足则完成；发现 auth.json 或无关数据风险、回滚不可证明、LevelDB 编码不确定或范围外 owner 时暂停或返回计划。
- Non-goals:
- 不恢复 provider/config/profile/protocol 子系统
- 不删除完整 LevelDB 或 .codex 目录
- 开发测试不操作真实用户 Codex 数据
- Scope: Statsig owner、恢复事务 owner、Flet UI、路径、测试、打包、文档、ADR、基线和 Windows 产物。
- Change kinds:
- architecture-feature
- Risk hints:
- 持久状态、LevelDB tombstone、备份和回滚、登录凭据保护、产品契约从四操作变为五操作。

## BaselineReadSetHint

- docs/aegis/specs/2026-07-12-codex-safe-configuration-restore-design.md
- docs/aegis/plans/2026-07-12-codex-safe-configuration-restore.md
- docs/aegis/baseline/2026-07-11-post-refactor-baseline.md
- docs/aegis/adr/ADR-0001-codex-owned-install-and-enhancement-boundaries.md

## BaselineUsageDraft (initial projection; superseded by the final usage below)

- Required baseline refs:
- docs/aegis/specs/2026-07-12-codex-safe-configuration-restore-design.md
- docs/aegis/plans/2026-07-12-codex-safe-configuration-restore.md
- docs/aegis/baseline/2026-07-11-post-refactor-baseline.md
- docs/aegis/adr/ADR-0001-codex-owned-install-and-enhancement-boundaries.md
- Acknowledged before plan:
- none
- Cited in plan:
- none
- Missing refs:
- docs/aegis/specs/2026-07-12-codex-safe-configuration-restore-design.md
- docs/aegis/plans/2026-07-12-codex-safe-configuration-restore.md
- docs/aegis/baseline/2026-07-11-post-refactor-baseline.md
- docs/aegis/adr/ADR-0001-codex-owned-install-and-enhancement-boundaries.md
- Advisory decision: needs-baseline-readback

## ImpactStatementDraft

- Compatibility boundary: 保留四个既有操作及更新/状态/单实例，并新增一个安全恢复操作。
- Affected layers:
- Statsig LevelDB
- Codex CLI configuration
- Flet UI
- packaging/docs
- Owners:
- codex_config_restorer.py coordinates backup and rollback
- codex_statsig_unlocker.py owns exact LevelDB deletion
- app.py owns confirmation and scheduling
- Invariants:
- auth.json and unrelated user state are never modified
- backup completes before mutation
- only exact Statsig evaluation/timestamp keys are invalidated
- Non-goals:
- 不恢复 provider/config/profile/protocol 子系统
- 不删除完整 LevelDB 或 .codex 目录
- 开发测试不操作真实用户 Codex 数据

These records are Method Pack drafts / hints, not authoritative runtime decisions.

## BaselineUsageDraft

- Required baseline refs:
- docs/aegis/specs/2026-07-12-codex-safe-configuration-restore-design.md
- docs/aegis/plans/2026-07-12-codex-safe-configuration-restore.md
- docs/aegis/baseline/2026-07-11-post-refactor-baseline.md
- docs/aegis/adr/ADR-0001-codex-owned-install-and-enhancement-boundaries.md
- Delivered context refs:
- none
- Acknowledged before plan:
- docs/aegis/specs/2026-07-12-codex-safe-configuration-restore-design.md
- docs/aegis/plans/2026-07-12-codex-safe-configuration-restore.md
- docs/aegis/baseline/2026-07-11-post-refactor-baseline.md
- docs/aegis/adr/ADR-0001-codex-owned-install-and-enhancement-boundaries.md
- Cited in plan:
- docs/aegis/adr/ADR-0002-safe-codex-configuration-restore.md
- docs/aegis/baseline/2026-07-12-safe-restore-baseline.md
- Missing refs:
- none
- Advisory decision: continue
