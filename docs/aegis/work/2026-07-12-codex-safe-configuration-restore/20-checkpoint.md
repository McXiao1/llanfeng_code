# Codex 安全配置恢复 - Checkpoint

- Task ID: 2026-07-12-codex-safe-configuration-restore
- Current todo: Execute Task 1: add exact Statsig cache invalidation.
- Active slice: Write focused deletion-plan and WriteBatch regression tests, then implement in the Statsig owner.
- Blocked on: none
- Next step: Run focused RED tests for tests/test_codex_statsig_unlocker.py.

## Checkpoint Update

- Current todo: Execute Task 2: implement the reversible restore transaction.
- Active slice: Create codex_config_restorer.py and focused transaction/rollback tests without touching UI.
- Completed todos:
- Task 1 exact Statsig cache invalidation implemented and verified.
- Evidence refs:
- statsig-exact-cache-invalidation
- Blocked on: none
- Next step: Write RED tests for preview, auth preservation, backup, success, and rollback.

## DriftCheckDraft

- Scope status: Task 1 changes only the approved Statsig evaluation/timestamp cache keys.
- Compatibility status: Existing model-unlock put batches remain green; unrelated LevelDB keys and current public behavior are preserved.
- Retirement status: No full-LevelDB delete, model-name guessing, second writer, or historical config reset was introduced.
- New risk signals:
- Restore transaction rollback still requires independent proof in Task 2.
- Advisory decision: continue

## Checkpoint Update

- Current todo: Execute Task 3: add the fifth Flet restore action.
- Active slice: Wire preview, confirmation, process-close, restore execution, and typed results into app.py without filesystem logic.
- Completed todos:
- Task 1 exact Statsig invalidation completed.
- Task 2 reversible restore transaction completed.
- Evidence refs:
- statsig-exact-cache-invalidation
- reversible-config-restore-transaction
- Blocked on: none
- Next step: Write RED UI tests for five actions and restore flows.

## DriftCheckDraft

- Scope status: Task 2 mutates only config.toml, models.json, and approved Statsig keys in temporary test fixtures.
- Compatibility status: auth.json is byte-preserved; missing targets are idempotent; backup and rollback are typed and evidenced.
- Retirement status: The historical CodexConfigManager/config package and whole-LevelDB reset remain absent.
- New risk signals:
- UI confirmation must accurately expose mutable and preserved targets before runtime execution.
- Advisory decision: continue

## Checkpoint Update

- Current todo: Execute Task 4: align packaging tests and product documentation.
- Active slice: Require the new runtime owner in packaging and update current product language without reviving retired reset contracts.
- Completed todos:
- Task 1 exact Statsig invalidation completed.
- Task 2 reversible restore transaction completed.
- Task 3 five-action Flet UI completed.
- Evidence refs:
- statsig-exact-cache-invalidation
- reversible-config-restore-transaction
- five-action-restore-ui
- Blocked on: none
- Next step: Add packaging RED assertion, then update README, PRODUCT, CHANGELOG and packaging contract.

## DriftCheckDraft

- Scope status: Task 3 adds exactly one approved primary action and keeps restore mutation behind injected services.
- Compatibility status: Existing four actions and update/status flows remain green; process confirmation is reused.
- Retirement status: No profile reset, config manager, active-profile marker, or emoji UI returned.
- New risk signals:
- Actual source files exceed approximate soft estimates but remain single-purpose and below the 2,000-line hard limit; final complexity audit is required.
- Advisory decision: continue

## Checkpoint Update

- Current todo: Execute Task 5 architecture sync and full verification.
- Active slice: Create ADR-0002 and the current five-action safe-restore baseline, then run full regression and Windows artifact verification.
- Completed todos:
- Task 1 exact Statsig invalidation completed.
- Task 2 reversible restore transaction completed.
- Task 3 five-action Flet UI completed.
- Task 4 packaging and current product documentation completed.
- Evidence refs:
- statsig-exact-cache-invalidation
- reversible-config-restore-transaction
- five-action-restore-ui
- packaging-and-product-contract
- Blocked on: none
- Next step: Read ADR-0001 and the post-refactor baseline, create ADR-0002/baseline through the workspace helper, and verify index structure.

## DriftCheckDraft

- Scope status: Task 4 changes only package inclusion assertions and current product/packaging documentation for the approved fifth action.
- Compatibility status: The existing install, unlock, marketplace, update, and single-instance contracts remain documented; auth.json preservation is explicit.
- Retirement status: Retired config/profile/protocol/VBS owners remain forbidden, and no live CodexConfigManager or destructive reset language returned.
- New risk signals:
- Windows runtime archive and installer still require a fresh build and content/hash audit.
- Advisory decision: continue

## DriftCheckDraft

- Scope status: Architecture records match the approved safe-scope A and the implemented fifth action without expanding mutable targets.
- Compatibility status: ADR-0002 preserves all four prior retained actions and support behavior while adding only the safe restore contract.
- Retirement status: ADR-0001 is retained as superseded history; retired provider/config/profile/protocol and destructive-reset paths remain explicitly absent.
- New risk signals:
- Fresh full regression and Windows archive/installer evidence are still pending.
- Advisory decision: continue

## Checkpoint Update

- Current todo: Build and audit fresh Windows application and installer artifacts.
- Active slice: Run build_windows.ps1, inspect app.zip inclusion/exclusion and source parity, then build the Inno Setup installer and capture fresh metadata and SHA-256.
- Completed todos:
- Task 1 exact Statsig invalidation completed.
- Task 2 reversible restore transaction completed.
- Task 3 five-action Flet UI completed.
- Task 4 packaging and current product documentation completed.
- ADR-0002 and the current safe-restore baseline completed.
- Full Python regression, lint, compile, version, diff, and retirement scans passed.
- Evidence refs:
- statsig-exact-cache-invalidation
- reversible-config-restore-transaction
- five-action-restore-ui
- packaging-and-product-contract
- architecture-and-baseline-sync
- full-python-and-retirement-verification
- Blocked on: none
- Next step: Build the Windows app, audit app.zip, then build and hash the installer.

## DriftCheckDraft

- Scope status: Full regression validates the approved exact restore scope and five-action runtime without new mutable targets.
- Compatibility status: All 118 tests pass across install, unlock, restore, launcher, marketplace, updater, UI, and packaging behavior.
- Retirement status: Live symbol scan is empty and all explicitly retired files/directories remain absent.
- New risk signals:
- Windows packaged runtime and installer still need fresh build, archive parity, and hash evidence.
- Advisory decision: continue

## DriftCheckDraft

- Scope status: Fresh Windows artifacts package the approved five-action runtime and exact restore owner.
- Compatibility status: The app archive is source-identical for the app, installer, Statsig, restorer, launcher, and marketplace owners; Inno Setup 6.7.3 produced version 1.2.0.
- Retirement status: Archive audit found zero retired source paths, config package entries, app bytecode, or development roots.
- New risk signals:
- The installer is unsigned and interactive install/uninstall plus live Codex restore remain manual checks.
- Advisory decision: continue

## Checkpoint Update

- Current todo: Assemble final Aegis proof bundle and completion receipt.
- Active slice: Write completion reflection, bundle/check the Aegis work record, and report only evidence-supported residual risks.
- Completed todos:
- Task 1 exact Statsig invalidation completed.
- Task 2 reversible restore transaction completed.
- Task 3 five-action Flet UI completed.
- Task 4 packaging and current product documentation completed.
- ADR-0002 and current safe-restore baseline completed.
- Full Python verification and retirement scans completed.
- Fresh Windows application/archive and installer builds completed.
- Final acceptance and complexity audit completed.
- Evidence refs:
- statsig-exact-cache-invalidation
- reversible-config-restore-transaction
- five-action-restore-ui
- packaging-and-product-contract
- architecture-and-baseline-sync
- full-python-and-retirement-verification
- fresh-windows-app-and-archive
- fresh-windows-installer
- final-fresh-verification
- complexity-and-acceptance-closure
- Blocked on: none
- Next step: Update 99-reflection.md, run aegis-workspace bundle/check, and prepare the verification-before-completion receipt.

## DriftCheckDraft

- Scope status: All implementation, packaging, architecture, and evidence work remains inside approved safe scope A and exact mutable targets.
- Compatibility status: Five actions are verified; prior install/update, unlock, marketplace, update, environment, and single-instance contracts remain green.
- Retirement status: Provider/config/profile/protocol owners, whole-LevelDB reset, auth deletion, second writer, and compatibility fallbacks remain absent from runtime and app.zip.
- New risk signals:
- Only manual live-host validation and installer signing remain outside the automated completion boundary.
- Advisory decision: continue

## Checkpoint Update

- Current todo: Report evidence-supported completion and await user direction.
- Active slice: No implementation work remains; prepare the verification-before-completion receipt without staging or committing.
- Completed todos:
- Task 1 exact Statsig invalidation completed.
- Task 2 reversible restore transaction completed.
- Task 3 five-action Flet UI completed.
- Task 4 packaging and current product documentation completed.
- ADR-0002 and current safe-restore baseline completed.
- Full and critical Python verification completed.
- Fresh Windows app/archive and installer builds completed.
- Acceptance, complexity, reflection, proof-bundle, and workspace checks completed.
- Evidence refs:
- statsig-exact-cache-invalidation
- reversible-config-restore-transaction
- five-action-restore-ui
- packaging-and-product-contract
- architecture-and-baseline-sync
- full-python-and-retirement-verification
- fresh-windows-app-and-archive
- fresh-windows-installer
- final-fresh-verification
- complexity-and-acceptance-closure
- Blocked on: none
- Next step: Await user direction for optional commit/staging, interactive installer walkthrough, or live Codex validation.
