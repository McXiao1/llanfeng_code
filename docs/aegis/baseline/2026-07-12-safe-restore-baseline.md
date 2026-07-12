# Llanfeng Code Assistant Safe Restore Baseline

Date: `2026-07-12`
Status: `current five-action dual-baseline snapshot`
Decision record: `docs/aegis/adr/ADR-0002-safe-codex-configuration-restore.md`
Supersedes current-state snapshot: `docs/aegis/baseline/2026-07-11-post-refactor-baseline.md`

## 1. Purpose

This snapshot records the current product and runtime boundaries after adding the
approved safe Codex configuration restore action. The 2026-07-11 snapshot and
ADR-0001 remain historical evidence for the provider/protocol retirement, while
ADR-0002 and this file own the current five-action state.

## 2. Current Authority Surfaces

- The approved safe-restore specification and implementation plan define the
  exact mutable and preserved targets.
- `README.md` and `PRODUCT.md` describe the current five-action product.
- `Codex.md` remains the user-supplied technical reference for Codex Statsig
  storage and model-unlock behavior.
- `ADR-0002` records why targeted cache invalidation and a focused restore owner
  supersede the prior four-action boundary.
- `pyproject.toml`, `scripts/build_windows.ps1`, and `scripts/installer.iss` own
  the Python package and Windows distribution contract.
- Implementation and verification evidence live under
  `docs/aegis/work/2026-07-12-codex-safe-configuration-restore/`.

## 3. Product / Requirement Baseline

### 3.1 Current Product

The Windows desktop application exposes exactly five primary actions:

1. `安装/更新 Codex`
2. `安装/更新 Claude`
3. `解锁模型`
4. `恢复配置`
5. `增强启动 Codex`

Environment status, manual refresh, single-instance startup, and the in-app
release update banner remain support behavior rather than additional primary
actions.

### 3.2 Safe Restore Contract

`恢复配置` is a narrow, confirmation-first recovery workflow. It may mutate only:

- `~/.codex/config.toml`;
- `~/.codex/models.json`;
- live LevelDB keys containing `statsig.cached.evaluations.`;
- live LevelDB keys containing `statsig.last_modified_time.evaluations`.

Before the first mutation, the application creates a collision-safe timestamped
backup under `%APPDATA%/lanfeng_code/backups/`. The backup contains the affected
CLI files, the complete pre-write LevelDB when Statsig keys will change, and a
non-secret `manifest.json`.

The workflow explicitly preserves `~/.codex/auth.json`, login state, sessions,
history, logs, Skills, plugins, MCP data, and unrelated LevelDB keys. Production
restore code does not open, copy, move, delete, or rewrite `auth.json`; its path
is recorded only as a preserved target in the manifest and UI contract.

### 3.3 Removed Product Contracts and Non-goals

The safe restore action does not revive:

- provider configuration lists or profile persistence;
- Add/Edit/Delete/Enable controls or profile dialogs;
- provider model fetching, config writers, or profile-derived launch behavior;
- `CodexConfigManager` or the retired `config/` package;
- protocol documentation, `--import-url`, `llanfeng-code://` parsing, or URL
  scheme registration;
- credential deletion, complete `.codex` deletion, or complete live LevelDB
  deletion as a success path;
- a persistent undo operation for runtime-only marketplace enhancement.

## 4. Architecture / Runtime Boundary Baseline

### 4.1 Canonical Owners

| Surface | Canonical owner | Contract |
| --- | --- | --- |
| Flet orchestration | `src/llanfeng_code_assistant/app.py` | Render five actions, coordinate preview/confirmation/process close/async execution/status/update messages; no filesystem transaction or raw LevelDB encoding. |
| CLI installation | `src/llanfeng_code_assistant/installer.py` | Install only pinned Codex and Claude npm packages, use resolved Windows command shims, and acquire prerequisites. |
| Environment status | `src/llanfeng_code_assistant/environment.py` | Detect Node, npm, Git, Codex, and Claude through resolved executable paths. |
| Model discovery and Statsig mutation | `src/llanfeng_code_assistant/codex_statsig_unlocker.py` | Query the bundled Codex catalog, append eligible missing models, plan exact restore tombstones, and remain the only LevelDB WriteBatch/log writer. |
| Restore transaction | `src/llanfeng_code_assistant/codex_config_restorer.py` | Discover exact targets, allocate backups, write manifests, remove approved CLI files, invoke Statsig invalidation, and coordinate rollback. |
| Restore backup root | `src/llanfeng_code_assistant/paths.py` | Resolve the application-owned `%APPDATA%/lanfeng_code/backups/` root. |
| Codex Desktop launch and CDP delivery | `src/llanfeng_code_assistant/codex_desktop_launcher.py` | Find Microsoft Store Codex, allocate loopback CDP, verify `app://` renderers, and deliver the enhancement script. |
| Marketplace compatibility script | `src/llanfeng_code_assistant/codex_plugin_marketplace.py` | Independently implement plugin list/install/filter compatibility behavior. |
| Application updates | `src/llanfeng_code_assistant/updater.py` and `update_banner.py` | Check, download, and start release installers. |
| Single-instance behavior | `src/llanfeng_code_assistant/single_instance.py` | Prevent duplicate normal GUI instances. |

No retained behavior has a provider/profile/protocol, local-catalog, generic
injection, historical reset, or second LevelDB-writer fallback owner.

### 4.2 Restore Discovery and Mutation Chain

```text
read-only preview
  -> exact CLI file existence check
  -> deterministic Codex Desktop LevelDB discovery
  -> exact Statsig evaluation/timestamp tombstone plan
  -> explicit UI confirmation and optional confirmed process termination
  -> timestamped backup + fsynced manifest
  -> remove backed-up config.toml/models.json
  -> append one deletion WriteBatch through the Statsig owner
  -> finalize manifest and return typed result
```

- Unreadable LevelDB state fails closed before backup or mutation.
- No actionable targets returns an idempotent success and creates no backup.
- A LevelDB backup is required only when at least one approved Statsig key will
  be invalidated, and it is complete rather than key-selective so rollback can
  restore the exact pre-write directory.
- The manifest stores paths, categories, counts, status, and preserved targets;
  it stores no credential contents or raw LevelDB values.
- Deletion records use the next LevelDB sequence and reuse the existing CRC32C,
  fragmentation, active-log selection, and append primitives.
- Unknown Statsig fields, unrelated keys, and non-Statsig data are not selected.

### 4.3 Rollback and Failure Contract

- Backup allocation, copying, and initial manifest completion are hard
  prerequisites; any failure stops before mutation.
- CLI removal failure restores every CLI file already removed.
- If a Statsig write was attempted and did not succeed, rollback restores both
  removed CLI files and the complete pre-write LevelDB directory.
- Incomplete rollback is a typed failure that retains and reports the backup
  path plus warnings for manual recovery.
- Final manifest-update failure after successful data mutation is a warning; it
  does not trigger another data mutation.
- No error path falls back to deleting `.codex`, deleting the live LevelDB, or
  restoring the retired configuration subsystem.

### 4.4 Process and User Interaction Safety

- Preview and restore execute off the Flet UI event loop through
  `asyncio.to_thread`.
- The restore action remains disabled while work is active and is restored in a
  `finally` block.
- Confirmation lists exact mutable targets and explicitly preserved data.
- If Codex is running, the user must choose `关闭 Codex 并恢复`; termination
  failure aborts before backup or mutation.
- Success reports removed files, invalidated-key count, backup path, preserved
  login state, and restart/network guidance.

## 5. Model Unlock and Marketplace Boundaries

The existing model source-of-truth chain remains:

```text
installed Codex CLI bundled catalog
  -> visibility == "list" and supported_in_api is not False
  -> unique non-empty slugs in catalog order
  -> Statsig dynamic config available_models
  -> append missing values only
```

Restore does not guess which models were historically injected. It invalidates
the complete approved Statsig evaluation cache classes so Codex can fetch fresh
official values. Marketplace enhancement remains a process-lifetime CDP behavior
and creates no persistent restore target.

## 6. Packaging and Dependency Baseline

Runtime dependencies remain fixed to `certifi`, `flet`, `httpx`, `websockets`,
and `chromium-reader`. `tomlkit`, `pydantic`, and `keyring` are not runtime
dependencies.

The Windows build contract requires
`src/llanfeng_code_assistant/codex_config_restorer.py` in `app.zip` and continues
to reject retired modules, development roots, `.pyc`, `__pycache__`, and
`.egg-info` content. The installer remains per-user, contains no URL-scheme
Registry block, and packages the recursively built Flet Windows directory.

## 7. Retirement State

The following paths remain deleted rather than retained as compatibility
carriers:

- `src/llanfeng_code_assistant/config/`;
- `storage.py`, `secrets.py`, `models.py`, and `model_fetcher.py`;
- `codex_model_catalog_editor.py`;
- `deeplink.py` and `protocol_document.py`;
- `inject_launch.py` and `file_ops.py`;
- `docs/protocol.md`;
- `assets/codex-plugin.vbs`;
- tests whose only purpose was a retired owner or contract;
- the Inno Setup URL-protocol registration block.

Historical changelog, ADR, baseline, specification, and work records may name
retired behavior as history. They are not runtime owners or compatibility paths.

## 8. Complexity and Dependency Direction

- `app.py` is 769 physical lines and remains orchestration-only.
- `codex_statsig_unlocker.py` is 768 physical lines and remains the single
  Statsig parsing, planning, WriteBatch, and log-append owner.
- `codex_config_restorer.py` is 403 physical lines and owns only the reversible
  restore transaction.
- The principal restore UI, Statsig, and transaction test modules are 612, 472,
  and 362 physical lines respectively.
- These files exceed some soft planning estimates but remain below the project
  2,000-line hard limit and do not introduce mixed filesystem/UI ownership, a
  second LevelDB writer, or a legacy reset fallback.

Complexity result: `within hard budget; soft-estimate variance accepted with
focused owners and final diff audit required`.

## 9. Verification Boundary and Known Risks

Automated verification covers exact Statsig key selection and deletion batch
encoding, large-batch fragmentation, no-op behavior, backup and manifest shape,
`auth.json` byte preservation, transaction rollback, partial rollback reporting,
five-action UI flow, process-confirmation paths, packaging inclusion, retirement
deny lists, imports, and linting. Exact commands and results are recorded in the
2026-07-12 work evidence bundle.

Still outside automated coverage:

- invoking restore against the user's real Codex files or live LevelDB;
- proving the next live Codex launch successfully refreshes official Statsig
  values for every account/network condition;
- launching and validating the marketplace enhancement against the user's live
  renderer and account-specific marketplace response;
- full interactive installer install/uninstall and GUI walkthrough.

These are bounded manual/release risks. They do not authorize broader mutation,
an alternate owner, or a compatibility fallback.

## 10. Alignment Conclusion

Result: `aligned`
Scope: `both`

The current product and runtime architecture implement the approved five-action
safe-restore boundary: backup first, exact mutation only, typed rollback,
credential preservation, one transaction owner, one LevelDB writer, and no
revived provider/profile/protocol path. Future additions to the mutable target
set, restoration of credential deletion, complete LevelDB replacement, or a
second persistence owner require a new explicit product and architecture
decision.
