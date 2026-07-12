# ADR-0002 - Safe Codex configuration restore

Status: `recorded-from-work`
Date: `2026-07-12`

## Source Evidence

- Approved safe-restore specification plus focused Statsig, transaction, UI, packaging, and lint evidence from the 2026-07-12 work record.
## Context

The four-action architecture intentionally retired provider-oriented reset logic, but users now require a fifth restore action that also removes historical model whitelist injection without losing authentication or unrelated Codex data. The old reset deleted auth.json and did not address Statsig; deleting the complete Desktop LevelDB would violate the preserved-data boundary.

## Decision

Expose exactly five primary actions and add codex_config_restorer.py as the sole transaction owner for preview, mandatory backup, non-secret manifest, exact CLI file removal, and rollback. Keep codex_statsig_unlocker.py as the only LevelDB writer and invalidate only live statsig.cached.evaluations.* and statsig.last_modified_time.evaluations keys with deletion WriteBatch records. Keep app.py orchestration-only and require explicit confirmation before closing Codex. Preserve auth.json, sessions, history, skills, plugins, MCP data, and unrelated LevelDB keys.

## Alternatives Considered

- Revive CodexConfigManager.reset() and delete config.toml, models.json, and auth.json; rejected because it logs the user out, misses Statsig injection, and restores a retired owner.
- Back up and replace or delete the complete LevelDB; rejected because unrelated Desktop state cannot be proven preserved.
- Guess and remove previously injected model names from cached JSON; rejected because historical model sets are unknowable and this would create a second cache-reconstruction authority.
## Consequences

- Every mutation is preceded by a timestamped application-owned backup; no actionable targets is a no-op; failures attempt CLI and, when required, full pre-write LevelDB rollback.
- Codex must restart and may require network access to fetch official Statsig values after successful restoration.
- The product changes from four to five primary actions, while provider/profile/protocol owners remain deleted and marketplace enhancement remains runtime-only.
## Compatibility Boundary

Preserve Codex/Claude installation, model unlock, marketplace launch, environment status, updates, and single-instance behavior. Preserve auth.json and all excluded user data. Restore only config.toml, models.json, and the two approved Statsig key classes; never delete the complete .codex directory or live LevelDB as the success path.

## Retirement Impact

ADR-0001 remains historical, but its exact four-action current-state assertion is superseded. CodexConfigManager, config/, provider profiles, protocol registration, whole-LevelDB reset, credential deletion, and silent process termination remain retired with no compatibility fallback.

## Baseline Sync

- Needed: needed
- Target: docs/aegis/baseline/2026-07-12-safe-restore-baseline.md
- Action: create snapshot
- Reason: The implemented fifth action changes the current product contract, canonical owner map, persistent-data mutation boundary, rollback contract, packaging contents, and release verification surface.

## Evidence References

- docs/aegis/specs/2026-07-12-codex-safe-configuration-restore-design.md
- docs/aegis/plans/2026-07-12-codex-safe-configuration-restore.md
- docs/aegis/work/2026-07-12-codex-safe-configuration-restore/90-evidence.md
- tests/test_codex_config_restorer.py
- tests/test_codex_statsig_unlocker.py
- tests/test_entrypoint_and_ui.py
## Supersedes

- ADR: docs/aegis/adr/ADR-0001-codex-owned-install-and-enhancement-boundaries.md
- Reason: The prior decision remains the historical reason provider/protocol owners were removed, but its exact four-action product boundary and single persistent-mutation statement are replaced by the approved, implemented fifth safe-restore action.
## Boundary

This ADR is an advisory Aegis Method Pack record. It does not grant completion authority or replace project-authoritative architecture sources.
