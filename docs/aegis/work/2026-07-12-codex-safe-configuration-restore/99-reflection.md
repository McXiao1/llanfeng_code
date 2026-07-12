# Codex 安全配置恢复 - Reflection

Date: `2026-07-12`
Status: `completion candidate with fresh automated and Windows artifact evidence`

## Outcome

The approved safe-scope `A` restore action is implemented as the fifth primary
action. The final runtime owns only exact CLI configuration removal and exact
Statsig cache invalidation, always after mandatory backup. Authentication and
unrelated user data remain outside the mutable boundary.

No development command invoked the production restore operation against the
real user profile. All mutation and rollback tests used temporary directories or
injected fakes. Every real runtime restore still requires the user to click the
button and confirm the in-app dialog.

## Acceptance Audit

| # | Acceptance criterion | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Exactly five primary actions including `恢复配置`. | pass | `tests/test_entrypoint_and_ui.py`; 19 focused UI tests; 84-test critical rerun. |
| 2 | No targets performs no write and creates no backup. | pass | Restorer no-op test and UI no-op test; typed success with `backup_path=None`. |
| 3 | Confirmation lists exact mutable and preserved state. | pass | UI confirmation tests cover `config.toml`, `models.json`, Statsig count, `auth.json`, sessions, Skills, and plugins. |
| 4 | `auth.json` is byte-for-byte unchanged. | pass | Every restore success/failure/rollback fixture compares pre/post bytes; production code only records its path as preserved metadata. |
| 5 | CLI files are backed up before removal. | pass | Transaction tests verify backup contents and backup-failure hard stop before invalidation. |
| 6 | Complete LevelDB is backed up before Statsig mutation. | pass | Success and rollback tests verify `desktop_leveldb/` pre-write bytes. |
| 7 | All approved evaluation/timestamp keys are tombstoned and unrelated keys survive. | pass | 26 focused Statsig tests cover exact selection, unrelated-key preservation, deletion record count/sequence/fragmentation, and idempotence. |
| 8 | Post-mutation failure proves rollback or reports partial rollback with backup path. | pass | CLI rollback, complete LevelDB rollback, partial rollback, warning, and backup-path tests. |
| 9 | No provider/config/profile/protocol owner returns. | pass | Live-symbol scan has zero hits; all explicitly retired paths are absent; app archive has zero retired entries. |
| 10 | Focused/full tests, lint, compile, version, scans, Windows build, archive audit, and installer build pass. | pass | 118 full tests; 84 critical tests; Ruff clean; compileall exit 0; version `1.2.0`; Flet build and Inno Setup 6.7.3 pass. |
| 11 | README, PRODUCT, CHANGELOG, ADR, baseline, packaging, and Aegis evidence describe the five-action boundary. | pass | Current docs and packaging tests; ADR-0002; `2026-07-12-safe-restore-baseline.md`; indexed work evidence. |

## Complexity Delta

- Maintained Python source/test files: `39 -> 27`.
- Maintained Python source/test physical lines: `9,549 -> 6,630`, net `-2,919`.
- Files over the Aegis 800-line soft pressure signal: `0`.
- Files over the project 2,000-line hard limit: `0`.
- Largest current owners: `app.py` 769 lines and
  `codex_statsig_unlocker.py` 768 lines.
- Largest tracked owner changes: `app.py` `-392` lines,
  `codex_statsig_unlocker.py` `+304` lines, and
  `codex_desktop_launcher.py` `-222` lines.
- New focused owners: `codex_config_restorer.py` 403 lines and
  `codex_plugin_marketplace.py` 395 lines.
- New fallback/adapter/duplicate owner: none.
- Retired branches/owners: provider/config/profile/protocol, legacy injection,
  generic model catalog, and VBS plugin paths.
- Net entropy: `decreased` relative to HEAD, with one new transaction owner and
  one existing Statsig writer carrying their approved single responsibilities.

### Complexity Closure

- Budget status: `within-budget`.
- Governed now: UI remains orchestration-only; filesystem transaction stays in
  the restorer; WriteBatch/log encoding stays in the Statsig owner; no second
  process or persistence owner was introduced.
- Deferred follow-up: none required for completion; monitor the two 760-line
  owners if future work would push either across the 800-line pressure signal.
- Completion impact: `complete` for the approved implementation boundary.

## Repair and Retirement Closure

### Repair Track

- Canonical restore owner: `codex_config_restorer.py`.
- Canonical LevelDB owner: `codex_statsig_unlocker.py`.
- UI owner: `app.py` with injected preview/transaction boundaries.
- Installer regression owner: `installer.py` resolves `npm` to the actual
  executable or Windows `.CMD` shim before registry and install commands.
- Main-path evidence: focused tests, full tests, source-parity archive audit,
  and fresh Windows artifacts.

### Retirement Track

- Historical `CodexConfigManager.reset()` and credential deletion remain
  retired; no compatibility carrier is retained.
- The retired `config/`, profile, protocol, storage, secret, model-fetch,
  generic injection, and VBS paths remain absent.
- ADR-0001 and the 2026-07-11 baseline remain only as explicitly superseded
  historical context.
- Lingering references are limited to historical records and negative
  assertions; no live runtime import or packaged path remains.

## Build Diagnostic Reflection

The first sandboxed Windows build timed out while Flutter waited during
`flutter --version`. A direct snapshot invocation proved the SDK could not open
`C:\Users\22353\flutter\3.41.7\bin\cache\lockfile`. Dart, Git, and
project inputs were healthy. The canonical fix was not a source fallback: the
unchanged build script was rerun with scoped sandbox escalation, after which the
build completed in about two minutes.

## Artifact Evidence

- `app.zip`
  - path: `build/windows/data/flutter_assets/app/app.zip`
  - size: `46,210` bytes
  - timestamp: `2026-07-12 11:42:01 +08:00`
  - SHA-256: `17633AE40C701EF23750D086B46E9A032F4D5DD30FB0C2F1A4A7F0272BAA7B02`
  - 17 runtime entries; restore module present; critical source parity true;
    retired paths, app bytecode, and development roots all zero.
- Installer
  - path: `build/installer/Llanfeng-Code-Assistant-Setup-1.2.0.exe`
  - size: `28,769,900` bytes
  - timestamp: `2026-07-12 11:45:06 +08:00`
  - SHA-256: `7F2E10FE971F4CEE20F3CFCFEAE65E8E1FD0305969DD9CB6EC3E3624C1BC4116`
  - Inno Setup `6.7.3`; ProductVersion `1.2.0`; Authenticode status `NotSigned`.

## Residual Risk

- The real user's Codex files and LevelDB were intentionally not mutated during
  development.
- A live Codex restart/cache refresh, account-specific marketplace renderer,
  and full interactive installer install/uninstall walkthrough remain manual
  host checks.
- The generated installer is not Authenticode-signed, so Windows reputation and
  trust prompts remain a release concern outside this feature implementation.

## Reflection Decision

- Goal: deliver the approved safe configuration restore and preserve all
  retained product behavior.
- Deeper cause unresolved: `no` for the implementation boundary; the only build
  anomaly was the demonstrated sandbox permission boundary.
- Evidence: focused/full tests, lint, compile/version, retirement scans, ADR and
  baseline sync, source-parity archive audit, installer build, hashes, and
  complexity audit.
- Risk/unknown: manual live-host validation and signing only.
- Decision: `completion candidate`; final completion wording remains subject to
  verification-before-completion and does not gain authority from this record.

Method Pack output does not grant completion authority.
