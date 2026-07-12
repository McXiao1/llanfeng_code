# 安装与 Codex 增强全面重构 - Checkpoint

- Task ID: 2026-07-11-install-and-codex-enhancements-refactor
- Current todo: 完成并提交设计规格供用户审核。
- Active slice: 初始化 Aegis 工作区并固化设计选项、owner、数据流与验收边界。
- Blocked on: 用户尚未批准设计规格，业务源码实现受 brainstorming hard gate 阻塞。
- Next step: 写入 docs/aegis/specs/2026-07-11-install-and-codex-enhancements-design.md，完成自审并请求用户批准。

## Checkpoint Update

- Current todo: Obtain user approval for the written design specification.
- Active slice: Design review gate; no business source implementation is authorized yet.
- Completed todos:
- Audit repository, baseline failures, local Codex catalog, and CodexPlusPlus reference.
- Initialize Aegis workspace, initial baseline, long-task record, and design specification.
- Evidence refs:
- docs/aegis/specs/2026-07-11-install-and-codex-enhancements-design.md
- codex-bundled-model-catalog
- codexplusplus-marketplace-reference
- Blocked on: User review and approval of the design specification.
- Next step: After approval, invoke writing-plans and create the detailed implementation plan.

## DriftCheckDraft

- Scope status: Design remains inside the six requested outcomes.
- Compatibility status: Preserved and intentionally removed contracts are explicit; persistent user data remains untouched.
- Retirement status: Delete-first targets are enumerated; implementation has not started.
- New risk signals:
- CodexPlusPlus AGPL license requires independent behavior-level reimplementation.
- Advisory decision: pause-for-user

## Checkpoint Update

- Current todo: Await explicit user approval of Option A.
- Active slice: Design approval gate; business source remains unchanged.
- Completed todos:
- Reconciled the long-task owner, protocol-scheme, and process-termination invariants with the written design.
- Evidence refs:
- docs/aegis/specs/2026-07-11-install-and-codex-enhancements-design.md
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/impact-statement-draft.json
- Blocked on: Automatic goal continuation is not explicit design approval.
- Next step: On user approval, invoke writing-plans and create the implementation plan; otherwise revise the design as requested.

## DriftCheckDraft

- Scope status: No source edits; design still covers all six requested outcomes.
- Compatibility status: Protocol scheme and explicit-confirmation process boundary are now consistent across records.
- Retirement status: Delete-first scope remains approved only at proposal level; no code deletion has occurred.
- New risk signals:
- none
- Advisory decision: pause-for-user

## Checkpoint Update

- Current todo: Obtain explicit user approval for Option A.
- Active slice: Blocked at the mandatory design review gate after three consecutive goal turns without explicit approval.
- Completed todos:
- none
- Evidence refs:
- docs/aegis/specs/2026-07-11-install-and-codex-enhancements-design.md
- Blocked on: Explicit user approval of the written design.
- Next step: Resume only after the user explicitly approves Option A or requests a design revision.

## DriftCheckDraft

- Scope status: No business source changes were made outside the unapproved design.
- Compatibility status: Persistent user data and removed-contract boundaries remain protected.
- Retirement status: Retirement implementation is pending explicit design approval.
- New risk signals:
- none
- Advisory decision: blocked

## Checkpoint Update

- Current todo: Create and execute the implementation plan for approved Option A.
- Active slice: Writing-plans: translate approved owners, retirement scope, tests, and verification into executable batches.
- Completed todos:
- User explicitly approved Option A.
- Evidence refs:
- User message: 批准
- docs/aegis/specs/2026-07-11-install-and-codex-enhancements-design.md
- Blocked on: none
- Next step: Save and index the implementation plan, then execute inline because subagents were not authorized.

## DriftCheckDraft

- Scope status: User approved the full six-item Option A scope.
- Compatibility status: Intentional protocol/config removal and retained install/update boundaries remain unchanged.
- Retirement status: Delete-first implementation is now authorized for listed code, docs, tests, and installer registration; persistent data deletion remains forbidden.
- New risk signals:
- none
- Advisory decision: continue

## Checkpoint Update

- Current todo: Execute Task 1: establish the new model unlock contract.
- Active slice: Rewrite codex_statsig_unlocker.py and add focused tests without touching UI or plugin owners.
- Completed todos:
- Approved design converted into an indexed implementation plan.
- Evidence refs:
- docs/aegis/plans/2026-07-11-install-and-codex-enhancements-refactor.md
- Blocked on: none
- Next step: Write model discovery/mutation tests, run RED, implement, then run focused pytest and Ruff.

## Checkpoint Update

- Current todo: Execute Task 2: focused plugin marketplace enhancement and CDP launcher.
- Active slice: Create codex_plugin_marketplace.py, reduce codex_desktop_launcher.py, and add focused Python/Node-backed tests.
- Completed todos:
- Task 1 model unlock contract implemented and verified.
- Evidence refs:
- task1-model-unlocker-tests
- Blocked on: none
- Next step: Write launcher and marketplace tests, confirm RED, implement, then run focused pytest/Ruff.

## DriftCheckDraft

- Scope status: Task 1 matches approved model-unlock scope.
- Compatibility status: default_model preserved; hidden/unsupported models excluded; no user data deletion.
- Retirement status: Profile-provided model ownership removed from the unlocker; UI callers remain for Task 3 migration.
- New risk signals:
- none
- Advisory decision: continue

## Checkpoint Update

- Current todo: Execute Task 3: replace the application with the four-action console.
- Active slice: Rewrite `app.py`, `tests/test_entrypoint_and_ui.py`, and simplify `__main__.py` while preserving update, status, and single-instance behavior.
- Completed todos:
  - Task 2 plugin marketplace enhancement and focused Store Codex/CDP launcher implemented.
- Evidence refs:
  - `python -m pytest -q tests/test_codex_plugin_marketplace.py tests/test_codex_desktop_launcher.py` -> `17 passed in 0.46s`
  - `python -m ruff check src/llanfeng_code_assistant/codex_plugin_marketplace.py src/llanfeng_code_assistant/codex_desktop_launcher.py tests/test_codex_plugin_marketplace.py tests/test_codex_desktop_launcher.py` -> `All checks passed!`
- Blocked on: none
- Next step: Inspect retained environment/installer/update contracts, replace UI tests, then rewrite the coordinator and CLI entrypoint.

## DriftCheckDraft

- Scope status: Task 2 remains inside the approved plugin-marketplace and launcher slice.
- Compatibility status: Store Codex discovery, verified `app://` target selection, and typed partial-launch results are retained; profile/model runtime injection is absent.
- Retirement status: Marketplace behavior has one focused owner; no CodexPlusPlus source/assets or legacy launcher fallback was retained.
- New risk signals: none
- Advisory decision: continue

## Checkpoint Update

- Current todo: Execute Task 4: reduce installer/package owners and retire legacy configuration/protocol code.
- Active slice: Update installer/constants/paths/package contracts, delete approved internal owners and their tests, and prove no live consumer remains.
- Completed todos:
  - Task 3 four-action UI and protocol-free entrypoint implemented.
- Evidence refs:
  - `python -m pytest -q tests/test_entrypoint_and_ui.py tests/test_environment.py tests/test_updater.py tests/test_single_instance.py tests/test_codex_desktop_launcher.py tests/test_codex_plugin_marketplace.py` -> `42 passed in 1.37s`
  - focused Ruff -> `All checks passed!`
  - `python -m llanfeng_code_assistant --version` -> `1.2.0`
- Blocked on: none
- Next step: Map all remaining consumers of the approved deletion set, write reduced installer/packaging tests, then delete-first with workspace-scoped paths.

## DriftCheckDraft

- Scope status: UI now exposes exactly the four approved primary actions and retains only status/update support.
- Compatibility status: `--version`, single-instance startup, update download/install, prerequisite handling, and typed Codex enhancement results remain active.
- Retirement status: Runtime UI/entrypoint no longer import profiles, config writers, model fetching, or protocol parsing; source/test/package retirement remains Task 4.
- New risk signals: `app.py` is 641 physical lines, below the project hard limit but above the plan's approximate 550-line target; no mixed profile responsibility remains.
- Advisory decision: continue

## Checkpoint Update

- Current todo: Execute Task 5: rewrite product and packaging documentation.
- Active slice: Align README, PRODUCT, packaging guide, and changelog with the four-action product while preserving unrelated changelog edits.
- Completed todos:
  - Task 4 installer/package reduction and legacy code/test retirement completed.
- Evidence refs:
  - `python -m pytest -q` -> `87 passed in 1.07s`
  - `python -m ruff check src tests` -> `All checks passed!`
  - `python -m compileall -q src` and `python -m llanfeng_code_assistant --version` -> `1.2.0`
  - production lingering-reference scan -> no matches
- Blocked on: none
- Next step: Inspect current documentation and the pre-existing changelog diff, rewrite current product contracts, then run documentation and packaging checks.

## DriftCheckDraft

- Scope status: Task 4 implemented the approved delete-first source/package boundary.
- Compatibility status: install/update/status/single-instance and Codex enhancement owners remain green; no protocol registry or CLI argument remains.
- Retirement status: all enumerated legacy source/tests/docs are deleted; live user SQLite/keyring data was not accessed or modified.
- New risk signals: none
- Advisory decision: continue

## Checkpoint Update

- Current todo: Execute Task 6: full verification, packaging evidence, complexity closure, and architecture record.
- Active slice: Re-run all acceptance checks from a clean command boundary, attempt Windows app/installer builds, inspect the final diff, and close Aegis evidence.
- Completed todos:
  - Task 5 product and packaging documentation rewritten.
- Evidence refs:
  - documentation residual scan -> no matches
  - `python -m pytest -q tests/test_packaging_config.py` -> `18 passed in 0.03s`
  - `git diff --check` -> no whitespace errors
- Blocked on: none
- Next step: Run the complete verification sequence, then best-available Windows builds and architecture/retirement audits.

## DriftCheckDraft

- Scope status: Documentation now describes only the four retained actions and current packaging contract.
- Compatibility status: Commands, links, dependencies, and output paths match the maintained files.
- Retirement status: Stale protocol build evidence and scheme integration instructions are absent; historical changelog entries remain as history.
- New risk signals: Windows release evidence has not yet been refreshed for this worktree.
- Advisory decision: continue

## Checkpoint Update

- Current todo: Refresh final Windows artifacts after documentation/ADR sync, then run the last complete verification and close evidence.
- Active slice: Final artifact refresh, Aegis evidence bundle, six-requirement audit, and completion receipt.
- Completed todos:
- Strict missing-visibility regression fixed and focused tests pass.
- Full Python tests, Ruff, compileall, residual scan, diff check, and complexity audit pass.
- ADR-0001 and the post-refactor dual baseline were created and indexed.
- Evidence refs:
- python -m pytest -q -> 88 passed before final documentation-only additions
- python -m ruff check src tests -> All checks passed
- docs/aegis/adr/ADR-0001-codex-owned-install-and-enhancement-boundaries.md
- docs/aegis/baseline/2026-07-11-post-refactor-baseline.md
- Blocked on: none
- Next step: Rebuild app/installer, capture final hash and archive checks, run fresh full verification, bundle/check workspace, then complete the goal.

## DriftCheckDraft

- Scope status: All six approved outcomes are implemented; only final post-record artifact refresh and closeout checks remain.
- Compatibility status: Retained startup/install/update boundaries are green; packaged Flet --version was correctly reclassified as an unsupported verification method and documentation was repaired.
- Retirement status: Delete-first owners and protocol registration remain absent; no legacy data was read or deleted.
- New risk signals:
- Real user Codex LevelDB mutation and live renderer marketplace behavior remain unexecuted manual-host checks.
- Advisory decision: needs-verification

## Checkpoint Update

- Current todo: Run the final fresh verification sequence and Aegis workspace bundle/check, then close the six-item goal.
- Active slice: Final evidence readback, workspace integrity check, six-item acceptance audit, and completion receipt.
- Completed todos:
- All six approved product outcomes are implemented and mapped to tests.
- Packaging contamination root cause was fixed with Flet excludes/cleanup, a build-time archive guard, and retirement of assets/codex-plugin.vbs.
- Fresh Windows app and Inno Setup installer builds succeeded; final archive and installer hashes were captured.
- Evidence refs:
- python -m pytest -q -> 91 passed
- build/windows/data/flutter_assets/app/app.zip -> 16 clean entries; SHA-256 32ADE74C6814A6CE12C0E0BEEBC58286CCDF411271833756060D5F628AA3A781
- build/installer/Llanfeng-Code-Assistant-Setup-1.2.0.exe -> SHA-256 2D3833CBB940724424592E9D4BD445E675C6C927F569D163126967E5E6AA3DC2
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/90-evidence.md
- Blocked on: none
- Next step: Run fresh pytest/Ruff/compile/version/residual/diff/complexity checks, then aegis bundle/check and complete the goal if all pass.

## DriftCheckDraft

- Scope status: All six approved outcomes remain implemented; the extra packaging repair closes a release artifact leak without expanding product scope.
- Compatibility status: Retained GUI/install/update/single-instance behavior is green; removed profile/protocol contracts remain intentionally absent; Flet CLI argument behavior is documented rather than patched.
- Retirement status: All legacy owners, the installer registry block, and assets/codex-plugin.vbs are absent from source and final app.zip; user persistent data was not read or deleted.
- New risk signals:
- Real user Codex LevelDB mutation, live account marketplace behavior, and interactive installer walkthrough remain manual-host checks.
- Advisory decision: needs-verification

## Checkpoint Update

- Current todo: Present the verified six-item completion receipt; no implementation todo remains.
- Active slice: Final user-facing completion report only.
- Completed todos:
- All six approved outcomes are implemented and mapped to direct and regression evidence.
- Fresh Python verification, retirement scans, artifact hashes, complexity checks, Windows build, and installer build passed.
- Aegis proof bundle was assembled and workspace structural check passed.
- Evidence refs:
- python -m pytest -q -> 91 passed in 1.35s
- ARTIFACT_COMPLEXITY_DIFF_CHECKS_OK
- Aegis workspace check passed: H:\Python\llanfeng_code\docs\aegis
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/90-evidence.md
- Blocked on: none
- Next step: User may perform real-host manual validation and decide whether to stage or commit the uncommitted worktree.

## DriftCheckDraft

- Scope status: All six approved outcomes and the packaging repair are fully evidenced; no scope expansion or unresolved drift remains.
- Compatibility status: Retained startup/install/update boundaries pass; intentionally removed profile/protocol contracts remain absent; no fallback owner was reintroduced.
- Retirement status: Legacy source, tests, protocol registration, old VBS, and packaged bytecode remnants are absent; no user source-of-truth data was deleted.
- New risk signals:
- Real-host LevelDB, live marketplace/account, and interactive installer checks remain release/manual validation only.
- Advisory decision: continue

## Checkpoint Update

- Current todo: Deliver the verified npm.CMD repair and refreshed Windows installer.
- Active slice: Final evidence closeout for the user-reported WinError 2 regression.
- Completed todos:
- Resolved npm through shutil.which at the canonical installer and environment owners.
- Added regression coverage for resolved Windows command shims and missing npm.
- Rebuilt the Windows app and Inno Setup installer with the repaired source.
- Completed fresh full regression, artifact, retirement, and host execution checks.
- Evidence refs:
- windows-npm-cmd-root-cause
- windows-npm-cmd-regression
- windows-npm-cmd-refreshed-artifacts
- Blocked on: none
- Next step: Present the new installer path and hashes; request the missing details for user item 2.

## DriftCheckDraft

- Scope status: The repair remains inside the retained Codex/Claude installation and environment-detection boundary.
- Compatibility status: shell=False is preserved; commands use the resolved executable or Windows .CMD shim without adding a UI fallback or duplicate owner.
- Retirement status: No retired configuration, protocol, profile, or CodexPlusPlus fallback path was restored; app.zip contains zero forbidden retired entries.
- New risk signals:
- The user numbered a second issue but supplied no error details, so it remains outside the verified repair scope.
- Advisory decision: continue
