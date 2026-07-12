# Codex Safe Configuration Restore Implementation Plan

Date: `2026-07-12`
Status: `approved specification / ready for inline execution`
Execution mode: `inline in the current user-approved dirty workspace; no subagents; no commit unless requested`
TDD route: `light regression-first for Statsig, transaction, and UI contracts`

## Goal

Implement the approved safe `恢复配置` action. Back up and remove only
`~/.codex/config.toml` and `~/.codex/models.json`, invalidate only live Codex
Statsig evaluation and last-modified LevelDB keys, preserve `auth.json` and all
unrelated user data, provide rollback, render a fifth primary action, and produce
fresh automated and Windows packaging evidence.

## Architecture

- `app.py` remains a Flet coordinator and owns preview/confirmation/busy/result
  flow only.
- New `codex_config_restorer.py` owns target discovery, backup allocation,
  manifest writing, file mutation, rollback, and typed restore results.
- `codex_statsig_unlocker.py` remains the only owner of Statsig LevelDB parsing,
  WriteBatch encoding, and log append; it gains exact-key deletion planning and
  execution.
- `paths.py` exposes the application-owned backup root.
- Existing `is_codex_running()` and `terminate_codex()` boundaries are reused;
  no third process owner is created.
- Retired provider/config/profile/protocol modules remain deleted.

## Tech Stack

- Python 3.12
- Flet 0.85.3
- `chromium-reader` 0.1.1
- pytest / pytest-asyncio
- Ruff
- PowerShell, Flet Windows build, Inno Setup 6.7.3

## Baseline / Authority Refs

- Approved specification:
  `docs/aegis/specs/2026-07-12-codex-safe-configuration-restore-design.md`
- Product/runtime baseline:
  `docs/aegis/baseline/2026-07-11-post-refactor-baseline.md`
- Existing architecture decision:
  `docs/aegis/adr/ADR-0001-codex-owned-install-and-enhancement-boundaries.md`
- Statsig storage reference: `Codex.md`
- Current product docs: `README.md`, `PRODUCT.md`
- Historical rejected implementation: commit `aa783e7`
- Current owners: `app.py`, `codex_statsig_unlocker.py`, `paths.py`

## Compatibility Boundary

Preserve Codex/Claude installation, model unlock, marketplace enhancement,
updates, environment status, and single-instance behavior. Preserve
`~/.codex/auth.json`, sessions, history, logs, skills, plugins, MCP data, and
unrelated LevelDB keys. Add exactly one primary action. Do not restore the old
`config/` package, provider profiles, API-key writers, protocol handling,
`CodexConfigManager`, full-LevelDB reset, or silent process termination.

## Verification

Focused commands:

```powershell
python -m pytest -q tests/test_codex_statsig_unlocker.py
python -m pytest -q tests/test_codex_config_restorer.py
python -m pytest -q tests/test_entrypoint_and_ui.py
python -m pytest -q tests/test_packaging_config.py
python -m ruff check src tests
```

Full commands:

```powershell
python -m pytest -q
python -m ruff check src tests
python -m compileall -q src
python -m llanfeng_code_assistant --version
git diff --check
.\scripts\build_windows.ps1
.\scripts\build_installer.ps1 -SkipAppBuild
```

Artifact audit must prove the new module is packaged, retired modules remain
absent, and the final installer/hash are refreshed.

## Requirement Ready Check

- Requirement source refs: user request, scope choice `A`, approved design, and
  approved written specification.
- Goals and scope refs: specification sections 1-4 and 17-18.
- User/scenario refs: a Windows user wants to undo this tool's Codex config and
  model whitelist changes without losing login or user data.
- Requirement item refs: fifth button, exact CLI files, exact Statsig keys,
  mandatory backup, rollback, preserved data, docs/build evidence.
- Acceptance refs: specification section 17 and this plan's verification.
- Open blocker questions: none.
- Decision: `ready`.

## Baseline Usage Draft

- Required refs: approved spec, post-refactor baseline, ADR-0001, Codex.md,
  README, PRODUCT, current owners, historical reset diff.
- Acknowledged before plan: all required refs.
- Cited in plan: all required refs.
- Missing refs: none.
- Decision: `continue`.

## Change Necessity

- User-visible need: safe one-click restoration including historical model
  injection removal.
- No-change/non-code option: cannot add UI behavior, write LevelDB tombstones,
  back up state, or provide rollback.
- Why code change is necessary: current product has no restore path; the old
  implementation deletes credentials and misses Statsig.
- Minimum boundary: Statsig owner, new restore transaction owner, Flet wiring,
  tests, package allowlist, and current product/architecture docs.
- Decision: `code-change`.

## Existence Check

- Proposed surface: `codex_config_restorer.py`.
- Reuse candidates: `app.py` and `codex_statsig_unlocker.py`.
- Why insufficient: `app.py` must not own filesystem transactions; Statsig owner
  must not own CLI file/manifest/rollback orchestration.
- Creation proof: the service isolates a separately testable transaction and
  keeps one reason to change per owner.
- Entropy/retirement impact: one focused owner; no fallback or retired subsystem.
- Decision: `add-with-proof`.

## Architecture Integrity Lens

- Invariant: exact-target mutation with backup first; credentials and unrelated
  state survive.
- Canonical contract: restorer coordinates; Statsig owner encodes deletion;
  app confirms and schedules.
- Overlap avoided: no LevelDB encoding in the new service and no file transaction
  in the UI.
- Higher-level path: cache invalidation lets Codex fetch official values instead
  of reconstructing a historical whitelist.
- Retirement falsifier: any `config/` import, `auth.json` mutation, whole-LevelDB
  delete, or legacy reset fallback fails review.
- Verdict: `proceed`.

## Ripple Signal Triage

- Producer: Statsig WriteBatch encoder now supports deletion records in addition
  to puts.
- Consumers: model unlock write path, new restore service, UI formatter,
  packaging allowlist, docs/baseline/ADR.
- Contract risk: existing put batch output and model-unlock tests must remain
  byte-compatible.
- Expanded verification: focused Statsig tests, full model unlock regression,
  restore rollback tests, full pytest, archive audit.
- Decision: expand verification across producer and both consumers.

## Plan-Time Complexity Check

| Artifact | Current pressure | Projected pressure | Governance |
| --- | ---: | ---: | --- |
| `app.py` | 645 lines | <= 750 | Wiring-only handlers and formatters; no filesystem code. |
| `codex_statsig_unlocker.py` | 660 lines | <= 760 | Exact Statsig deletion only; reuse current batch/log primitives. |
| `codex_config_restorer.py` | new | <= 320 | Single transaction owner. |
| UI tests | 444 lines | <= 580 | Restore interaction cases only. |
| Statsig tests | 334 lines | <= 450 | Deletion plan/batch cases only. |
| Restore tests | new | <= 400 | Transaction and rollback cases. |

Budget result: `within-budget`.
Recommendation: add one owner file; edit existing Statsig owner in place; keep
`app.py` wiring-only. If any file crosses the projected range because of mixed
responsibility, extract before continuing.

## Plan Pressure Test

- Owner/contract/retirement: explicit; no dormant old reset owner.
- Architecture integrity: exact cache invalidation is higher-level than guessing
  model deltas or restoring an ambiguous backup.
- Verification scope: pure planning, binary batch, transaction, rollback, UI,
  packaging, docs, Windows artifacts.
- Task executability: exact files, interfaces, tests, and commands are below.
- Pressure result: `proceed`.

## Execution Readiness View

- Intent Lock: safe scope A only.
- Scope Fence: two CLI files, approved Statsig keys, backup/manifest, fifth UI
  action, tests/docs/package evidence.
- Baseline Lock: approved 2026-07-12 spec plus 2026-07-11 current baseline.
- Approved Behavior: preview, explicit confirmation, optional process close,
  backup, exact mutation, rollback, preserved login, restart guidance.
- Owner Constraints: app orchestrates; restorer transacts; Statsig owner writes.
- Compatibility Boundary: all four existing actions remain green; auth and
  unrelated data remain untouched.
- Retirement Boundary: no provider/config/profile/protocol or whole-LevelDB path.
- Task Batches: Statsig deletion; restore transaction; UI; docs/package; final
  Windows evidence and architecture sync.
- Test Obligations: focused RED/GREEN per owner, then full regression and archive
  inspection.
- Review Gates: exact keys only, `auth.json` byte preservation, backup before
  mutation, rollback proof, no silent process termination.
- Drift/Rewind Rules: any new fallback, unclear target, or unprovable rollback
  returns to plan review.
- Evidence Required: focused/full tests, Ruff, compile/version, retirement scan,
  diff/complexity review, Windows app/installer hashes, Aegis bundle/check.
- Advisory Boundary: method-pack guidance only; not completion authority.

## Task 1: Add exact Statsig cache invalidation

Files:

- Modify `src/llanfeng_code_assistant/codex_statsig_unlocker.py`.
- Modify `tests/test_codex_statsig_unlocker.py`.

Why: historical injected models live inside Statsig evaluation cache. The owner
must delete exact live cache keys without replacing JSON or touching unrelated
LevelDB data.

Change necessity: current WriteBatch supports only put records. The minimum
stable repair is deletion planning and encoding in the existing Statsig owner.

Impact/compatibility: existing model-unlock put batches and public results must
remain unchanged. No backup is created inside the invalidation function because
the restore transaction owns the mandatory unified backup.

Target interfaces:

```python
@dataclass(frozen=True)
class StatsigInvalidationPlan:
    keys: tuple[bytes, ...]
    evaluation_count: int
    timestamp_count: int

@dataclass(frozen=True)
class StatsigInvalidationResult:
    success: bool
    message: str
    invalidated_keys: int = 0
    write_attempted: bool = False


def plan_statsig_cache_invalidation(state: LevelDbState) -> StatsigInvalidationPlan: ...

def invalidate_statsig_cache(db_path: Path) -> StatsigInvalidationResult: ...
```

WriteBatch boundary:

```python
_TYPE_DELETION = b"\x00"

def _make_writebatch(
    sequence: int,
    puts: Sequence[tuple[bytes, bytes]],
    deletes: Sequence[bytes] = (),
) -> bytes: ...
```

Repair track: select only keys with `_EVALUATION_MARKER` or
`_TIMESTAMP_MARKER`, encode deletion records, append one batch at
`max_sequence + 1`, and return typed failure with `write_attempted=True` if append
fails.

Retirement track: do not add JSON-empty-value writes, model-name guessing,
complete LevelDB deletion, or a second log writer.

Verification:

```powershell
python -m pytest -q tests/test_codex_statsig_unlocker.py
python -m ruff check src/llanfeng_code_assistant/codex_statsig_unlocker.py tests/test_codex_statsig_unlocker.py
```

Steps:

- [ ] Add tests for exact key selection, unrelated-key preservation, empty plan,
      deletion batch type/count/sequence, and append failure metadata.
- [ ] Run focused pytest and confirm failures are missing-interface/behavior RED.
- [ ] Implement dataclasses, pure plan, deletion-aware batch encoding, and typed
      execution without changing existing put behavior.
- [ ] Run focused pytest and Ruff until GREEN.
- [ ] Record evidence/checkpoint; do not commit unless requested.

## Task 2: Implement the reversible restore transaction

Files:

- Create `src/llanfeng_code_assistant/codex_config_restorer.py`.
- Create `tests/test_codex_config_restorer.py`.
- Modify `src/llanfeng_code_assistant/paths.py`.

Why: backup, manifest, exact file removal, Statsig invalidation, and rollback are
one transaction with a reason to change separate from UI and LevelDB encoding.

Change necessity: no existing owner can safely coordinate both filesystem and
Statsig mutation without mixing responsibilities. Minimum boundary is one new
service and one backup path helper.

Impact/compatibility: only `config.toml`, `models.json`, and approved Statsig
keys are mutable. `auth.json` and all unrelated paths are excluded by construction.

Target interfaces:

```python
@dataclass(frozen=True)
class CodexRestorePreview:
    config_paths: tuple[Path, ...]
    leveldb_path: Path | None
    statsig_key_count: int | None
    warnings: tuple[str, ...] = ()

    @property
    def has_targets(self) -> bool: ...

@dataclass(frozen=True)
class CodexRestoreResult:
    success: bool
    message: str
    backup_path: Path | None = None
    removed_paths: tuple[Path, ...] = ()
    invalidated_statsig_keys: int = 0
    rollback_attempted: bool = False
    rollback_completed: bool = False
    warnings: tuple[str, ...] = ()


def preview_codex_restore(...) -> CodexRestorePreview: ...

def restore_codex_configuration(...) -> CodexRestoreResult: ...
```

Path helper:

```python
def codex_restore_backups_dir() -> Path:
    return app_data_dir() / "backups"
```

Transaction details:

- Allocate `codex_restore_YYYYMMDD_HHMMSS[_N]` without overwriting.
- Copy exact CLI files under `cli/` and complete LevelDB under
  `desktop_leveldb/` only when Statsig keys will change.
- Write `manifest.json` with paths/counts/preserved targets, never file contents
  or raw LevelDB values.
- Remove exact CLI files, invoke `invalidate_statsig_cache`, update manifest.
- On failure, restore removed CLI files; restore the complete LevelDB only when a
  Statsig write was attempted; keep backup and report rollback state.
- Manifest-finalization failure after successful mutation is a warning, not a
  second mutation attempt.

Repair track: create a recoverable transaction and typed evidence.

Retirement track: no `CodexConfigManager`, no `config/` package, no `auth.json`
access, no whole-directory reset, no automatic backup cleanup.

Verification:

```powershell
python -m pytest -q tests/test_codex_config_restorer.py
python -m ruff check src/llanfeng_code_assistant/codex_config_restorer.py src/llanfeng_code_assistant/paths.py tests/test_codex_config_restorer.py
```

Steps:

- [ ] Add tests for preview, no-op, auth preservation, backup/manifest, success,
      backup failure, CLI rollback, Statsig rollback, partial rollback, and
      collision-safe backup names.
- [ ] Run focused pytest and confirm RED.
- [ ] Implement the service with small helpers, early returns, explicit phases,
      and no exception swallowing.
- [ ] Run focused pytest and Ruff until GREEN.
- [ ] Record evidence/checkpoint; do not commit unless requested.

## Task 3: Add the fifth Flet action and confirmation flow

Files:

- Modify `src/llanfeng_code_assistant/app.py`.
- Modify `tests/test_entrypoint_and_ui.py`.

Why: users need a visible, safe one-click workflow with exact scope preview and
explicit process/data confirmation.

Change necessity: no current control or handler exposes restore. Minimum boundary
is action registration, one card, preview/dialog/perform handlers, and result
formatting; business mutation remains injected.

Impact/compatibility: keep existing button labels/order and add `恢复配置` between
`解锁模型` and `增强启动 Codex`. Existing process functions are reused.

Target wiring:

```python
ActionKey = InstallTarget | Literal["unlock", "restore", "launch"]
RestorePreview = Callable[[], CodexRestorePreview]
RestoreConfiguration = Callable[[], CodexRestoreResult]
```

Handlers:

```python
async def _request_config_restore(self) -> None: ...
def _show_config_restore_dialog(self, preview: CodexRestorePreview, running: bool) -> None: ...
async def _perform_config_restore(self, force_terminate: bool) -> None: ...
@staticmethod
def _format_restore_result(result: CodexRestoreResult) -> str: ...
```

Repair track: offload preview/restore with `asyncio.to_thread`, restore busy state
in `finally`, list exact mutable and preserved targets, and require explicit
`关闭 Codex 并恢复` when running.

Retirement track: no old profile reset dialog, active-profile clearing, emoji,
or config manager import.

Verification:

```powershell
python -m pytest -q tests/test_entrypoint_and_ui.py
python -m ruff check src/llanfeng_code_assistant/app.py tests/test_entrypoint_and_ui.py
```

Steps:

- [ ] Update structural/UI tests for five actions, no-op, confirmation content,
      cancel, running-process path, termination failure, success, rollback
      warning, and busy-state restoration.
- [ ] Run focused pytest and confirm RED.
- [ ] Add injectable restore boundaries, button/card, handlers, dialog, and
      formatters without filesystem logic.
- [ ] Run focused pytest and Ruff until GREEN.
- [ ] Record evidence/checkpoint; do not commit unless requested.

## Task 4: Align packaging and product documentation

Files:

- Modify `tests/test_packaging_config.py`.
- Modify `README.md`.
- Modify `PRODUCT.md`.
- Modify `CHANGELOG.md` without discarding existing user edits.
- Modify or create packaging evidence assertions as required by the current test
  structure.

Why: the packaged runtime and user-facing contract must contain the new owner and
must not describe the obsolete four-action product.

Change necessity: source-only behavior is insufficient for a distributable
feature; package allowlists and docs are maintained contracts.

Impact/compatibility: require `codex_config_restorer.py`; continue forbidding
retired config/protocol/profile files and `auth.json` reset claims.

Verification:

```powershell
python -m pytest -q tests/test_packaging_config.py
rg -n "exactly four|四个明确操作|四操作|删除.*auth.json|CodexConfigManager" README.md PRODUCT.md docs/packaging.md tests src
```

Expected scan: no active product claim that there are only four actions and no
live old reset owner; historical Aegis/spec references are allowed.

Steps:

- [ ] Add packaging tests that require the new module and keep the retirement
      denylist.
- [ ] Run focused packaging tests and confirm RED where the module is absent.
- [ ] Update current product/docs/changelog to five actions and safe restore
      semantics; preserve unrelated changelog history.
- [ ] Run focused tests, residual scans, and diff check until GREEN.
- [ ] Record evidence/checkpoint; do not commit unless requested.

## Task 5: Full verification, architecture sync, and Windows artifacts

Files:

- Create `docs/aegis/adr/ADR-0002-safe-codex-configuration-restore.md`.
- Create `docs/aegis/baseline/2026-07-12-safe-restore-baseline.md`.
- Update `docs/aegis/INDEX.md` through the workspace helper.
- Maintain a new work record under
  `docs/aegis/work/2026-07-12-codex-safe-configuration-restore/`.
- Refresh generated Windows artifacts under ignored `build/`.

Why: the fifth action changes durable product and persistence boundaries and
requires release-grade evidence.

Change necessity: ADR/baseline sync is required by the approved spec; Windows
build proves the new module reaches users.

Impact/compatibility: preserve ADR-0001 as historical context; ADR-0002 amends
the current owner map. Do not modify real user Codex files during verification.

Verification:

```powershell
python -m pytest -q
python -m ruff check src tests
python -m compileall -q src
python -m llanfeng_code_assistant --version
git diff --check
.\scripts\build_windows.ps1
.\scripts\build_installer.ps1 -SkipAppBuild
```

Archive audit must prove:

- `src/llanfeng_code_assistant/codex_config_restorer.py` exists;
- `app.py` and Statsig owner match current source;
- retired config/protocol/profile/VBS paths have zero hits;
- no development roots or bytecode contaminate `app.zip`.

Steps:

- [ ] Run the full Python verification and resolve only plan-related failures.
- [ ] Inspect final diff, line counts, exact mutable-path strings, lingering
      references, and `auth.json` preservation tests.
- [ ] Write ADR-0002 and the new baseline from implemented evidence, append both
      to the index, and run Aegis workspace check.
- [ ] Build Windows app and installer, audit archive, capture sizes/timestamps/
      SHA-256, and rerun final tests after documentation-only sync.
- [ ] Bundle/check the work record and prepare the verification-before-completion
      receipt; do not commit unless requested.

## Risks and Stop Conditions

- Stop if LevelDB deletion encoding cannot be verified without risking existing
  put behavior.
- Stop if preview cannot distinguish exact approved keys from unrelated state.
- Stop if any code path reads, copies, deletes, or rewrites `auth.json`.
- Stop if rollback cannot restore an exact pre-write LevelDB after an attempted
  append.
- Return to plan review if a full-LevelDB delete, provider/config subsystem, new
  process owner, or unapproved target appears.
- Automated tests use only temporary directories and fakes; never invoke the
  production restore function against the real user environment.

## Retirement Decision

- Path: `delete-first` for any tempting old reset/config-manager code; no compat
  exception.
- Preserved behavior: safe restoration of approved targets only.
- Retired behavior: credential deletion, active-profile clearing, provider
  config ownership, whole-LevelDB reset, silent fallback.
- Persistent-state execution: confirmation-first at runtime; development only
  exercises temporary test fixtures.

## Plan Self-Review

- Spec coverage: every acceptance criterion maps to Tasks 1-5.
- Placeholder scan: no unresolved marker or vague future task remains.
- Type consistency: preview/result/invalidation contracts align across owners.
- Compatibility: existing four actions remain and login/unrelated state are
  explicit invariants.
- Change necessity: each source-edit task names its minimum boundary.
- Existence: the new service has add-with-proof and no duplicate owner.
- Complexity: `app.py` remains wiring-only; Statsig reuses current primitives.
- Architecture: exact cache invalidation is the canonical higher-level path.
- Verification: focused, full, retirement, packaging, archive, and Windows
  commands are explicit.
- Dual track: safe repair and rejection of the historical destructive reset are
  both explicit.
- ADR/baseline signals: preserved for Task 5.

No implementation commit is part of this plan unless the user separately asks
for staging or committing the existing dirty workspace.
