# Codex Safe Configuration Restore Design

Date: `2026-07-12`
Status: `approved by user on 2026-07-12`
Architecture review required: `yes`
Approved product choice: `A - safe restore`

## 1. Decision Summary

Add a fifth primary action, `恢复配置`, that reversibly restores Codex-owned
configuration affected by this application while preserving login credentials,
sessions, history, skills, plugins, and unrelated Codex Desktop local data.

The operation removes `~/.codex/config.toml` and `~/.codex/models.json` after
backing them up. It does not remove `~/.codex/auth.json`. To undo all historical
model whitelist injection without guessing model names or replacing the complete
Desktop database, it invalidates only the live Statsig evaluation and
last-modified cache keys in the Codex localStorage LevelDB. Codex then fetches
fresh official Statsig configuration on its next launch.

The implementation must not revive the retired provider profile/configuration
subsystem or the old `CodexConfigManager.reset()` behavior.

## 2. Requirement Authority

- User request on 2026-07-12: add a configuration restore button that restores
  Codex configuration, including previously injected model content.
- User scope selection: `A`, preserving login and user data.
- User design approval: targeted Statsig cache invalidation rather than whole
  LevelDB replacement.
- Current product baseline:
  `docs/aegis/baseline/2026-07-11-post-refactor-baseline.md`.
- Current architecture decision:
  `docs/aegis/adr/ADR-0001-codex-owned-install-and-enhancement-boundaries.md`.
- Statsig format reference: `Codex.md`.
- Historical reset reference: commit `aa783e7`, used only as negative evidence
  because it deleted `auth.json` and did not clear model injection.

## 3. Requirement Mapping

| Requirement | Design response |
| --- | --- |
| Add a restore button | Add `恢复配置` as the fifth primary action in the Codex enhancement section. |
| Restore Codex configuration | Back up and remove only `config.toml` and `models.json`. |
| Remove historical model injection | Tombstone live Statsig evaluation and last-modified keys so official values are fetched again. |
| Preserve login and user data | Never read, copy, move, delete, or rewrite `auth.json`, sessions, history, skills, plugins, or unrelated LevelDB keys. |
| Make the action recoverable | Create a timestamped backup containing affected files, the complete pre-write LevelDB, and a manifest before mutation. |
| Avoid silent process termination | Require explicit in-app confirmation before closing a running Codex process. |

## 4. Scope and Non-goals

### In scope

- `~/.codex/config.toml`.
- `~/.codex/models.json`.
- Live LevelDB keys containing:
  - `statsig.cached.evaluations.`;
  - `statsig.last_modified_time.evaluations`.
- A timestamped application-owned backup and non-secret manifest.
- UI preview, confirmation, busy state, typed result, and recovery guidance.
- Automated unit, UI, regression, packaging, and retirement-boundary tests.
- README, PRODUCT, changelog, baseline, and ADR sync after implementation.

### Explicit non-goals

- Deleting or modifying `~/.codex/auth.json`.
- Deleting the complete `~/.codex` directory.
- Removing sessions, history, logs, skills, plugins, marketplace installations,
  MCP configuration, or unrelated user files.
- Deleting or replacing the complete live Codex Desktop LevelDB as the normal
  success path.
- Restoring provider profiles, config writers, API keys, protocol handling, or
  the retired `config/` package.
- Automatically deleting backups.
- Providing a general-purpose file browser or backup manager.
- Persistently undoing the runtime-only plugin marketplace enhancement, which
  ends when the enhanced Codex process exits.

## 5. Baseline Role Alignment

- Product / Requirement Baseline: the new user request supersedes the previous
  four-action/no-reset product boundary.
- Architecture / Runtime Boundary Baseline: the existing one-owner boundaries
  remain valid, but a new focused restore owner is required.
- Current implementation status: aligned with the old baseline, not a defect.
- Change classification: explicit requirement and architecture amendment.
- Result: `needs-baseline-sync-after-implementation`.
- Scope: `both`.

## 6. Options Considered

### Option 1: Revive the historical reset implementation

Delete `config.toml`, `models.json`, and `auth.json` through a restored
`CodexConfigManager`.

Rejected because it logs the user out, does not remove Statsig model injection,
and revives the retired configuration subsystem.

### Option 2: Replace or delete the complete LevelDB

Back up and remove the entire Codex localStorage LevelDB.

Rejected because it may roll back or remove unrelated Desktop state and cannot
satisfy the preserve-user-data invariant with sufficient precision.

### Option 3: Targeted Statsig cache invalidation plus safe CLI file restore

Back up all affected state, remove only `config.toml` and `models.json`, and
append LevelDB deletion records only for the live Statsig evaluation and
last-modified keys.

Approved. This removes all historical injected model whitelist content without
knowing model names and leaves unrelated LevelDB keys untouched.

## 7. Architecture Integrity and Existence Check

### Architecture Integrity Lens

- Invariant: restore only state owned or modified by the retained enhancement
  flows; preserve credentials and unrelated user state.
- Canonical owners:
  - `app.py`: UI orchestration and explicit confirmation;
  - `codex_config_restorer.py`: restore preview, backup, transaction, rollback,
    and result contract;
  - `codex_statsig_unlocker.py`: Statsig LevelDB key discovery and mutation;
  - existing process probes: detect and terminate Codex only after confirmation.
- Responsibility overlap: the restorer must not encode raw LevelDB batches;
  Statsig mutation remains in the Statsig owner.
- Higher-level simplification: invalidate official remote cache rather than
  infer an original whitelist or choose an ambiguous historical backup.
- Falsifier: if the implementation deletes whole LevelDB, touches `auth.json`,
  or restores provider/config owners, it violates this design.
- Verdict: proceed with a focused restore owner and a public Statsig invalidation
  operation.

### Existence Check

- Proposed new surface: `src/llanfeng_code_assistant/codex_config_restorer.py`.
- Existing reuse candidates: `app.py`, `paths.py`, and
  `codex_statsig_unlocker.py`.
- Why existing surfaces are insufficient: restore spans CLI files, backup
  manifests, rollback, and Statsig mutation; placing all of it in `app.py` or
  the already pressured Statsig owner mixes orchestration and persistence.
- Creation proof: one small service keeps `app.py` UI-only and allows pure target,
  manifest, rollback, and result tests.
- Entropy impact: one focused module is added; no retired subsystem or fallback
  owner is restored.
- Decision: `add-with-proof`.

## 8. Target Architecture

```text
app.py
├── codex_config_restorer.py
│   ├── discover safe restore targets
│   ├── create backup + manifest
│   ├── remove CLI config files
│   ├── coordinate rollback
│   └── call Statsig invalidation owner
├── codex_statsig_unlocker.py
│   ├── read live Statsig keys
│   ├── plan exact cache-key deletions
│   └── append LevelDB tombstone WriteBatch
├── paths.py
│   └── application backup root
└── existing process probes
    ├── is_codex_running
    └── terminate_codex
```

No import from deleted `src/llanfeng_code_assistant/config/` is allowed.

## 9. Public Restore Contracts

`codex_config_restorer.py` will expose typed frozen dataclasses and documented
functions. Exact names may be refined in the implementation plan, but the
contract must represent these fields.

### Restore preview

- existing CLI configuration paths;
- located Codex LevelDB path, if any;
- number of live Statsig keys that would be invalidated;
- whether any actionable target exists;
- warnings for malformed or unavailable state;
- preserved-path statement including `auth.json`.

Preview is read-only and creates no backup.

### Restore result

- success flag;
- user-facing message;
- backup directory, if mutation was attempted;
- removed CLI paths;
- count of Statsig keys invalidated;
- whether rollback was attempted and completed;
- non-fatal warnings.

Exported functions and dataclasses require complete docstrings following the
project JSDoc-style `@param`, `@returns`, and `@throws` conventions.

## 10. Restore Target Discovery

### CLI configuration

Resolve the Codex home as `Path.home() / ".codex"` unless an explicit test root
is supplied. Inspect exactly:

```text
config.toml
models.json
```

`auth.json` may be reported as preserved but must not be opened or copied.

### Desktop Statsig cache

Reuse deterministic LevelDB discovery from `find_codex_leveldb_path()`.
Read the current live LevelDB state and select only raw keys containing the two
approved Statsig markers. Malformed records do not need JSON decoding for cache
invalidation because deletion is keyed by the exact live raw key.

If LevelDB is absent, restore may still remove the two CLI files. If CLI files
are absent but approved Statsig keys exist, restore may still invalidate them.
If neither exists, return an idempotent no-op success with no backup.

## 11. Backup and Manifest

Before the first mutation, create:

```text
%APPDATA%/lanfeng_code/backups/codex_restore_YYYYMMDD_HHMMSS[_N]/
```

The backup contains:

```text
cli/config.toml          when present
cli/models.json          when present
desktop_leveldb/         complete pre-write LevelDB when Statsig keys will change
manifest.json
```

The manifest contains no credential values or raw LevelDB values. It records:

- schema version;
- creation time;
- original and backup paths for affected CLI files;
- original LevelDB path;
- counts and categories of planned mutations;
- explicitly preserved targets;
- final transaction status when safely writable.

Backups are never uploaded or automatically removed. Backup creation failure is
a hard stop before any mutation.

## 12. Statsig Invalidation Contract

Extend the Statsig owner with a pure deletion plan and an execution function.

### Pure plan

Input: `LevelDbState`.

Output:

- unique live raw keys containing either approved marker;
- count by evaluation and timestamp category;
- no unrelated keys.

The plan is idempotent: no matching live keys means no write.

### Write contract

- Use the next LevelDB sequence after `state.max_sequence`.
- Encode one deletion entry for each exact planned key in a WriteBatch.
- Reuse the existing block fragmentation, CRC32C, active-log selection, and
  append implementation.
- Never encode an empty or malformed JSON replacement value.
- Never delete a key merely because it shares the `_app://-` prefix.
- Return the exact number of tombstones appended.

The next normal Codex launch is expected to fetch fresh Statsig evaluations. The
UI success message must state that Codex needs to be restarted and may need
network access before the official model list appears.

## 13. Transaction and Rollback

The application must be closed before mutation. The transaction order is:

1. Discover and validate targets.
2. Create the backup directory.
3. Copy all affected CLI files and the complete LevelDB, when applicable.
4. Write and flush the initial manifest.
5. Remove only backed-up `config.toml` and `models.json`.
6. Append the exact Statsig deletion batch.
7. Update the manifest with success metadata.
8. Return a typed success result.

On any failure after mutation begins:

- restore any removed CLI files from the backup;
- if a Statsig append was attempted, restore the complete LevelDB from the
  pre-write backup while Codex remains closed;
- keep the backup directory and report rollback status;
- never fall back to deleting the complete `.codex` directory or LevelDB;
- return failure if rollback cannot be proven complete.

A partial rollback must be surfaced prominently with the exact backup path and
manual recovery guidance.

## 14. UI and Interaction Design

### Main page

The Codex enhancement section contains three cards:

1. `解锁模型`;
2. `恢复配置`;
3. `增强启动 Codex`.

The page therefore exposes five primary actions in total. The restore card uses
an icon from the existing Flet icon library and no emoji or gradient.

### Click flow

1. Enter busy state and run read-only preview off the UI event loop.
2. If no target exists, restore the button and display `无需恢复`.
3. Otherwise show a modal listing only the affected targets and explicitly
   stating that login, sessions, skills, and plugins are preserved.
4. If Codex is running, the destructive action label is
   `关闭 Codex 并恢复`; otherwise it is `确认恢复`.
5. Cancel performs no backup, file deletion, process termination, or LevelDB
   write.
6. Confirm optionally terminates Codex, then runs restore through
   `asyncio.to_thread`.
7. The button remains disabled until the operation reaches a final result and is
   restored in `finally`.

### Success message

Include:

- removed configuration filenames;
- number of Statsig keys invalidated;
- backup directory;
- preserved-login statement;
- restart/network guidance.

### Failure message

Include:

- failed phase;
- rollback state;
- backup directory when created;
- manual recovery guidance when rollback is incomplete.

## 15. Error Handling

- Missing config files or LevelDB: non-fatal and independently actionable.
- Codex process probe failure: abort before confirmation or mutation.
- Codex termination failure: abort with no backup or mutation.
- Locked LevelDB: actionable failure; no retry loop and no whole-database delete.
- Backup copy failure: hard stop before mutation.
- CLI file removal failure: rollback already removed files.
- LevelDB write failure: restore complete pre-write LevelDB and CLI files.
- Manifest finalization failure after successful data mutation: retain success
  state in memory, report a warning, and do not mutate data again merely to fix
  metadata.

No exception may be silently swallowed.

## 16. Testing Strategy

### Statsig owner tests

- deletion plan selects all and only evaluation/timestamp keys;
- duplicate candidates are deduplicated;
- unrelated Statsig and non-Statsig keys remain untouched;
- empty plan creates no backup or write;
- deletion WriteBatch uses the expected sequence and count;
- large deletion batches preserve LevelDB block fragmentation;
- write errors produce failure without claiming success.

### Restore service tests

- preview reports only `config.toml`, `models.json`, and approved Statsig count;
- `auth.json` exists but is never opened, copied, moved, or deleted;
- no targets is idempotent and creates no backup;
- backup contains exact pre-mutation files and LevelDB;
- manifest contains no credential content or raw LevelDB values;
- success removes the two CLI files and invalidates Statsig keys;
- backup failure performs no mutation;
- CLI deletion failure restores prior files;
- Statsig failure restores CLI files and complete LevelDB;
- partial rollback is reported explicitly;
- existing backups are not overwritten.

### UI tests

- five primary action labels render in the approved order;
- no retired Add/profile/protocol controls return;
- restore preview runs in busy state and restores the button;
- no-op preview does not open confirmation;
- confirmation lists exact targets and preserved data;
- running Codex requires `关闭 Codex 并恢复`;
- cancel schedules no restore;
- termination failure schedules no restore;
- success and rollback failure messages contain required evidence.

### Regression and packaging tests

- all current model unlock, install, launcher, marketplace, update, and
  single-instance tests remain green;
- packaging requires the new restore module;
- packaging continues to reject the retired `config/`, profile, protocol, and
  legacy injection owners;
- final `app.zip` contains the new module and no retired paths.

## 17. Acceptance Criteria

The feature is complete only when all are true:

1. The main page has exactly five primary actions, including `恢复配置`.
2. Clicking restore with no targets performs no write and reports no work.
3. Confirmation explicitly lists affected state and preserved state.
4. `auth.json` is byte-for-byte unchanged in all automated restore scenarios.
5. `config.toml` and `models.json` are backed up before removal.
6. The complete LevelDB is backed up before Statsig mutation.
7. All live evaluation and last-modified keys are tombstoned, with unrelated keys
   unchanged.
8. Failure after mutation begins either proves full rollback or reports a
   partial rollback with the backup path.
9. No provider/config/profile/protocol owner is restored.
10. Focused tests, full pytest, Ruff, compileall, source version check,
    retirement scan, Windows app build, archive audit, and installer build pass.
11. README, PRODUCT, CHANGELOG, ADR, baseline, and Aegis evidence describe the
    five-action product and exact data boundary.

## 18. Data Destruction Guard and Authorization

- Target class: persistent-state mutation surface.
- Exact mutable targets:
  - `~/.codex/config.toml`;
  - `~/.codex/models.json`;
  - approved live Statsig evaluation/timestamp keys.
- Explicitly excluded targets:
  - `~/.codex/auth.json`;
  - all other `.codex` and LevelDB state.
- Environment: current Windows user account, only when the user clicks and
  confirms the in-app restore dialog.
- Backup/rollback: mandatory pre-mutation backup and tested rollback.
- User scope confirmation: received as `A` on 2026-07-12.
- Design approval: received on 2026-07-12.
- Runtime confirmation: still required in the UI for every actual restore.
- Status: scoped design authorization satisfied; no real user data is modified
  during development or automated tests.

## 19. Complexity Budget

| Artifact | Current | Projected | Governance |
| --- | ---: | ---: | --- |
| `app.py` | 645 lines | about 740 lines | UI orchestration only; no backup or LevelDB encoding logic. |
| `codex_statsig_unlocker.py` | 660 lines | about 740 lines | Add only Statsig deletion planning/execution; extract helpers if pressure exceeds this range. |
| `codex_config_restorer.py` | new | under 320 lines | Single restore transaction owner. |
| `tests/test_entrypoint_and_ui.py` | 444 lines | under 560 lines | Add only restore interaction tests. |
| `tests/test_codex_statsig_unlocker.py` | 334 lines | under 430 lines | Add deletion-plan/batch tests. |
| `tests/test_codex_config_restorer.py` | new | under 380 lines | Service, backup, rollback, and preservation tests. |

Budget result: `within-budget with focused new owner`.

If `app.py` begins to contain filesystem transaction logic or the Statsig owner
exceeds its projected responsibility, the implementation plan must extract
rather than continue additive growth. Every file remains below the project
2,000-line hard limit.

## 20. Compatibility, Retirement, and ADR Signals

### Preserved compatibility

- Codex/Claude installation and update.
- Model unlock and plugin marketplace enhancement.
- Environment status, app update, and single-instance behavior.
- Codex authentication and all explicitly excluded user data.

### Intentional product amendment

- The product moves from four to five primary actions.
- A safe, narrow restore action returns, but the old provider-oriented reset
  contract does not.

### Retirement boundary

- Historical `CodexConfigManager.reset()` remains retired.
- Deleted `config/`, storage, secret, profile, protocol, and injection owners
  remain absent.
- There is no compatibility fallback to the old three-file deletion behavior.

### ADR and baseline signals

Implementation completion requires:

- amend or supersede ADR-0001 to record the fifth action and restore owner;
- update the post-refactor product/runtime baseline;
- retain the original four-action decision as historical context;
- record direct evidence that `auth.json` and unrelated LevelDB keys survive.

## 21. Working Drafts

### TaskIntentDraft

- Requested outcome: add a safe one-click Codex configuration restore action
  that also removes all historical model injection.
- Goal: restore only affected Codex configuration and Statsig cache while
  preserving login and user data.
- Success evidence: exact preservation, backup, tombstone, rollback, UI,
  regression, packaging, and documentation checks in section 17.
- Stop condition: complete when all acceptance criteria pass; stop on ambiguous
  targets, missing backup, unprovable rollback, or any `auth.json`/unrelated-data
  mutation.
- Non-goals: section 4.
- Risk hints: persistent state, LevelDB correctness, rollback, user login, and
  product-baseline amendment.

### BaselineReadSetHint

- `README.md`.
- `PRODUCT.md`.
- `Codex.md`.
- `docs/aegis/adr/ADR-0001-codex-owned-install-and-enhancement-boundaries.md`.
- `docs/aegis/baseline/2026-07-11-post-refactor-baseline.md`.
- `src/llanfeng_code_assistant/app.py`.
- `src/llanfeng_code_assistant/codex_statsig_unlocker.py`.
- historical commit `aa783e7` as rejected behavior evidence.

### BaselineUsageDraft

- Required baseline refs: all refs above.
- Acknowledged before design: all refs above.
- Cited in design: all refs above.
- Missing refs: none.
- Decision: `continue`.

### ImpactStatementDraft

- Affected layers: Flet UI, restore service, Statsig LevelDB owner, paths,
  tests, packaging, product docs, ADR, and baseline.
- New canonical owner: `codex_config_restorer.py`.
- Invariants: preserve credentials and unrelated user state; backup first;
  exact-key mutation only; explicit runtime confirmation; no retired owner.
- Compatibility boundary: current four actions remain, with one safe restore
  action added.
- Non-goals: section 4.

## 22. Spec Review Checklist

- Placeholder scan: no unresolved placeholder marker remains.
- Internal consistency: safe scope A, targeted Statsig invalidation, backup,
  rollback, UI, and acceptance criteria use the same target set.
- Ambiguity check: `auth.json`, complete LevelDB replacement, sessions, history,
  skills, plugins, and runtime marketplace behavior are explicitly classified.
- Boundary check: owners, data targets, exclusions, confirmation, rollback,
  retirement, ADR, and baseline sync are explicit.
- Implementation readiness: ready for a detailed plan only after user review of
  this written specification.

This specification records approved intent but does not itself authorize claims
that runtime restoration is safe or complete; those require implementation and
fresh verification evidence.


