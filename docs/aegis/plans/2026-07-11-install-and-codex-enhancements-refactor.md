# Install and Codex Enhancements Refactor Implementation Plan

Date: `2026-07-11`
Status: `approved design / ready for inline execution`
Execution mode: `inline in the current user-approved workspace; no subagents`
TDD route: `light for pure transforms and service contracts; regression-first for UI/packaging`

## Goal

Implement the approved Option A design: completely retire provider configuration
and the deep-link protocol, preserve Codex/Claude one-click installation and
updates, derive unlockable Codex models from the installed bundled catalog, and
launch Codex Desktop with a focused plugin marketplace runtime patch.

## Architecture

- `app.py` is a thin Flet coordinator with four primary actions.
- `installer.py` owns CLI installation and prerequisite acquisition.
- `codex_statsig_unlocker.py` owns bundled catalog discovery and persistent
  Statsig LevelDB mutation.
- `codex_desktop_launcher.py` owns Store-app discovery, CDP launch, target
  validation, and script delivery.
- `codex_plugin_marketplace.py` owns only the independently implemented
  marketplace request/filter JavaScript.
- Legacy profile, secret, config writer, model fetcher, protocol, and standalone
  profile injection owners are deleted without data migration.

## Tech Stack

- Python 3.12
- Flet 0.85.3
- `chromium-reader` for LevelDB reads
- `websockets` for CDP WebSocket commands
- pytest / pytest-asyncio
- Ruff
- PowerShell, Flet Windows build, and Inno Setup 6.7.3

## Baseline / Authority Refs

- Approved design:
  `docs/aegis/specs/2026-07-11-install-and-codex-enhancements-design.md`
- Initial baseline:
  `docs/aegis/baseline/2026-07-11-initial-baseline.md`
- User model evidence: `Codex.md`
- Product baseline: `README.md`, `PRODUCT.md`
- Dependency/package baseline: `pyproject.toml`, `scripts/build_windows.ps1`
- Installer contract: `scripts/installer.iss`
- Behavioral research only: `build/reference/renderer-inject.js` and
  `build/reference/CodexPlusPlus-README.md`

## Compatibility Boundary

Preserve application startup, `--version`, single-instance behavior, update
checks/downloads, environment detection, Node/Git prerequisite handling, and
Codex/Claude npm installation. Intentionally remove `--import-url`,
`llanfeng-code://`, profiles, configuration writers, model fetching, profile
terminals, reset-config behavior, and profile-derived injection. Do not delete
legacy SQLite or Credential Manager data.

## Verification

Primary completion commands:

```powershell
python -m pytest -q
python -m ruff check src tests
python -m compileall -q src
python -m llanfeng_code_assistant --version
```

Residual retirement scan:

```powershell
rg -n "ProfileRepository|ProviderProfile|ProviderDraft|ModelFetcher|CodexConfigManager|ClaudeConfigManager|parse_deeplink|PROTOCOL_SCHEME|PROTOCOL_DOCUMENT|import_url|llanfeng-code://|keyring|pydantic|tomlkit" src tests scripts README.md PRODUCT.md docs/packaging.md pyproject.toml
```

Expected result: no matches outside historical Aegis baseline/spec records and
intentional changelog history.

Packaging checks:

```powershell
python -m pytest -q tests/test_packaging_config.py tests/test_packaging_runtime_patch.py
.\scripts\build_windows.ps1
.\scripts\build_installer.ps1 -SkipAppBuild
```

The two Windows build commands are executed when the existing local toolchain is
available; any external download/toolchain failure is reported as uncovered
release evidence rather than hidden.

## Requirement Ready Check

- Requirement source refs: active goal, approved design, `Codex.md`.
- Goals and scope refs: all six numbered user requirements are mapped in the
  approved design.
- User/scenario refs: Windows developer installing Codex/Claude and enhancing
  Codex Desktop without provider profiles.
- Acceptance refs: approved design section 14 and this plan's verification
  commands.
- Open blocker questions: none.
- Decision: `ready`.

## Change Necessity

- User-visible need: remove existing features and add two profile-independent
  Codex enhancement flows.
- No-change/non-code option: cannot remove runtime owners, UI controls, CLI
  arguments, dependencies, or installer registry contracts.
- Why code change is necessary: every requested outcome crosses maintained
  source, tests, packaging, or runtime behavior.
- Minimum change boundary: the owners and retirement files enumerated below.
- Decision: `code-change`.

## Existence Check

- Proposed new surface: `codex_plugin_marketplace.py`.
- Existing owner/reuse candidate: embedded JavaScript inside
  `codex_desktop_launcher.py`.
- Why existing surface is insufficient: CDP lifecycle and marketplace adaptation
  have separate reasons to change and separate test contracts.
- Creation proof: extracting the patch allows the launcher to shrink and removes
  all model/profile script responsibilities.
- Entropy/retirement impact: one focused module replaces mixed embedded logic;
  `inject_launch.py` retires.
- Decision: `add-with-proof`.

## Architecture Integrity Lens

- Invariant: one canonical owner per retained behavior, no profile fallback.
- Canonical owner/contract: Codex CLI catalog -> Statsig whitelist -> Codex UI;
  launcher -> verified renderer -> marketplace script.
- Responsibility overlap: runtime model injection, local model catalog editing,
  and profile-derived whitelist mutation all retire.
- Higher-level simplification: the installed Codex CLI is the model catalog
  source of truth.
- Retirement/falsifier: unsupported Codex CLI/CDP contracts fail clearly; they do
  not reactivate legacy owners.
- Verdict: `proceed`.

## Plan Pressure Test

- Owner/contract/retirement: explicit and approved.
- Architecture integrity/higher-level path: resolved by reusing existing Statsig
  and launcher modules and extracting only the marketplace patch.
- Verification scope: pure transformation, file mutation, CDP, UI, CLI,
  dependency, docs, and packaging checks are represented.
- Task executability: every task has exact files and commands.
- Pressure result: `proceed`.

## Plan-Time Complexity Check

| Artifact | Current pressure | Target pressure | Governance |
| --- | --- | --- | --- |
| `app.py` | 1161 lines, mixed UI/config/persistence/CDP | under about 550 lines, orchestration only | full rewrite, no additive patching |
| `tests/test_entrypoint_and_ui.py` | over 1200 lines, mostly retired behavior | under about 500 lines | full rewrite around four actions and updates |
| `codex_desktop_launcher.py` | 609 lines, several unrelated scripts | under about 350 lines | remove all model/fast-startup/profile script logic |
| `codex_statsig_unlocker.py` | 464 lines, weak I/O/pure boundary | under about 650 lines | extract pure catalog/mutation planning helpers |
| `codex_plugin_marketplace.py` | new | under about 450 lines | single script owner and bounded public API |

Budget result: `within-budget after planned rewrites`.

## Execution Readiness View

- Intent Lock: exactly the six approved outcomes; no replacement config system.
- Scope Fence: Python app, tests, package metadata, docs, and Windows installer.
- Baseline Lock: approved design and initial baseline above.
- Approved Behavior: two installers, persistent model unlock, enhanced Codex
  launch, updates/status.
- Owner/Contract Constraints: Codex CLI owns candidates; Statsig owns visibility;
  launcher owns CDP; plugin module owns marketplace adaptation.
- Compatibility Boundary: preserve startup/install/update; remove profile and
  protocol contracts.
- Retirement Boundary: delete listed code/tests/docs, never delete live legacy
  SQLite/keyring records.
- Task Batches: model unlock; plugin/launcher; UI/installer; retirement/package;
  docs; full verification.
- Test Obligations: targeted RED/GREEN checks per task, then full regression.
- Review Gates: no hidden models, no default model mutation, no unrelated CDP
  target, no AGPL source/assets copied.
- Drift/Rewind Rules: new fallback/owner or persistent-data mutation returns to
  plan review.
- Evidence Required Before Completion: full pytest/Ruff/compile/version,
  residual scans, diff complexity review, and best-available Windows build.
- Advisory Boundary: method-pack execution guidance only; not completion
  authority.

## Task 1: Establish the new model unlock contract

Files:

- Rewrite `src/llanfeng_code_assistant/codex_statsig_unlocker.py`.
- Create `tests/test_codex_statsig_unlocker.py`.

Why: model unlock must discover Codex-owned candidates and mutate only missing
Statsig whitelist values without profile data or default-model changes.

Change necessity: the current function accepts profile-provided models, backs up
before knowing a write is needed, can overwrite `default_model`, and lacks direct
service tests. Minimum boundary is this module and its focused test file.

Repair track:

- Add `BundledModelDiscoveryResult` and `ModelUnlockResult` frozen dataclasses.
- Add `parse_bundled_model_slugs(payload: object) -> tuple[str, ...]`.
- Add `discover_bundled_model_slugs(...)` using
  `codex debug models --bundled`, a timeout, captured output, and no shell.
- Accept unique non-empty `slug` values in CLI order only when
  `visibility == "list"` and `supported_in_api is not False`.
- Add deterministic valid LevelDB path selection.
- Separate live-record reading from pure Statsig mutation planning.
- Require `available_models` to be a string list; leave malformed records
  untouched with warnings.
- Preserve all existing config fields and never accept a `default_model`
  parameter.
- Build a backup only after a non-empty write plan exists.
- Decode non-UTF-16 timestamp records as UTF-8 and report timestamp warnings.

Retirement track:

- Remove profile/custom-catalog terminology and `restore_leveldb_backup` from the
  application API.
- Remove behavior that creates an empty whitelist or changes the default model.

Verification:

```powershell
python -m pytest -q tests/test_codex_statsig_unlocker.py
python -m ruff check src/llanfeng_code_assistant/codex_statsig_unlocker.py tests/test_codex_statsig_unlocker.py
```

Steps:

- [ ] Write parser and mutation-plan tests covering order, hidden/unsupported
  exclusion, malformed payloads, duplicate slugs, missing whitelist, default
  preservation, multiple evaluations, timestamp warnings, idempotence, and
  backup timing.
- [ ] Run the focused test file and confirm failures identify the missing new
  interfaces rather than test harness errors.
- [ ] Implement the typed discovery, mutation plan, LevelDB read/write, process
  detection/termination, and high-level `discover_and_unlock_models()` flow.
- [ ] Run focused pytest and Ruff until green.
- [ ] Record checkpoint/evidence; do not create a Git commit unless explicitly
  requested by the user.

## Task 2: Implement focused plugin marketplace enhancement

Files:

- Create `src/llanfeng_code_assistant/codex_plugin_marketplace.py`.
- Rewrite `src/llanfeng_code_assistant/codex_desktop_launcher.py`.
- Create `tests/test_codex_plugin_marketplace.py`.
- Create `tests/test_codex_desktop_launcher.py`.

Why: plugin unlocking must work without a profile and without retaining runtime
model injection or the complete CodexPlusPlus stack.

Change necessity: the current launcher mixes fast-startup, model injection,
profile catalog injection, executable fallback, CDP, and a stale marketplace
patch. The minimum stable boundary is one script module plus a reduced launcher.

Repair track:

- Export `PLUGIN_MARKETPLACE_SCRIPT` and
  `build_plugin_marketplace_script() -> str` from the new module.
- Implement idempotent alias restoration, plugin method normalization,
  `local` + `vertical` list expansion, install request repair, bridge/window
  message interception, best-effort direct-client patching, and source+structure
  filter guards that never execute callbacks during detection.
- Do not copy reference source, labels, assets, snapshots, or settings code.
- In the launcher, locate only Microsoft Store Codex Desktop.
- Detect a running Codex process and return a clear non-destructive failure.
- Allocate a loopback CDP port, add both remote debugging arguments, poll `/json`,
  and select only a verified `app://` Codex page target.
- Send `Page.addScriptToEvaluateOnNewDocument` and `Runtime.evaluate`, validate
  CDP error responses, and return a typed launch result distinguishing started
  from enhanced.

Retirement track:

- Delete `FAST_STARTUP_SCRIPT`, `MODEL_WHITELIST_SCRIPT`, profile config script,
  npm CLI executable fallback, and `build_injection_scripts()`.
- Runtime model visibility is no longer a launcher responsibility.

Verification:

```powershell
python -m pytest -q tests/test_codex_plugin_marketplace.py tests/test_codex_desktop_launcher.py
python -m ruff check src/llanfeng_code_assistant/codex_plugin_marketplace.py src/llanfeng_code_assistant/codex_desktop_launcher.py tests/test_codex_plugin_marketplace.py tests/test_codex_desktop_launcher.py
```

Steps:

- [ ] Write launcher unit tests for executable discovery, process detection,
  arguments, target selection, timeout, CDP command validation, and partial
  launch results.
- [ ] Write a Node-backed pytest harness, skipped only when Node is absent, that
  evaluates the self-contained script against fake bridge/window objects and
  verifies request/filter behavior.
- [ ] Run focused tests and confirm RED for absent/reworked interfaces.
- [ ] Implement the independent marketplace script and reduced launcher.
- [ ] Run focused pytest/Ruff and record evidence.

## Task 3: Replace the UI with the four-action console

Files:

- Rewrite `src/llanfeng_code_assistant/app.py`.
- Rewrite `tests/test_entrypoint_and_ui.py`.
- Modify `src/llanfeng_code_assistant/__main__.py`.

Why: the primary user-facing requirement is to remove all configuration UI and
expose only installation plus the two Codex enhancements.

Change necessity: hiding controls would leave old owners and imports active. A
full rewrite is the minimum boundary that removes the behavior class and reduces
`app.py` below the pressure threshold.

Repair track:

- `AppServices` contains only detector and installer dependencies; model/launcher
  functions are injectable callables where tests need deterministic behavior.
- Render a compact light-theme header, status chips, installation section, and
  Codex enhancement section with project/Flet controls, no gradients or emoji.
- Primary buttons are `安装/更新 Codex`, `安装/更新 Claude`, `解锁模型`, and
  `增强启动 Codex`.
- Keep update banner integration and refresh status.
- Run install/model/launch blocking operations through `asyncio.to_thread` and
  restore button state in `finally`.
- Require explicit confirmation before terminating a running Codex process.
- Surface typed result messages including backup path and partial CDP launch.
- Remove `--import-url`; `run_app()` takes no protocol argument.

Retirement track:

- Remove tabs, list, Add/Edit/Delete/Enable, fetch models, reset config, protocol
  document, profile terminal, import dialog, and profile-derived launch.
- Remove emoji status prefixes from user-facing messages.

Verification:

```powershell
python -m pytest -q tests/test_entrypoint_and_ui.py tests/test_environment.py tests/test_updater.py tests/test_single_instance.py
python -m ruff check src/llanfeng_code_assistant/app.py src/llanfeng_code_assistant/__main__.py tests/test_entrypoint_and_ui.py
```

Steps:

- [ ] Replace UI tests with assertions for the four actions, no tabs/Add/protocol
  controls, update flow, install busy state, model confirmation, typed results,
  enhanced launch results, single-instance behavior, and rejected import args.
- [ ] Run focused tests and confirm RED against the legacy application.
- [ ] Rewrite `app.py` and simplify `__main__.py` to the approved contract.
- [ ] Run focused pytest/Ruff and inspect the control tree for forbidden labels.
- [ ] Record checkpoint/evidence.

## Task 4: Reduce installer/package owners and retire legacy code

Files to modify:

- `src/llanfeng_code_assistant/installer.py`
- `src/llanfeng_code_assistant/constants.py`
- `src/llanfeng_code_assistant/paths.py`
- `pyproject.toml`
- `scripts/build_windows.ps1`
- `scripts/installer.iss`
- `tests/test_packaging_config.py`
- Create `tests/test_installer.py`

Files/directories to delete:

- `src/llanfeng_code_assistant/config/`
- `src/llanfeng_code_assistant/storage.py`
- `src/llanfeng_code_assistant/secrets.py`
- `src/llanfeng_code_assistant/models.py`
- `src/llanfeng_code_assistant/model_fetcher.py`
- `src/llanfeng_code_assistant/codex_model_catalog_editor.py`
- `src/llanfeng_code_assistant/deeplink.py`
- `src/llanfeng_code_assistant/protocol_document.py`
- `src/llanfeng_code_assistant/inject_launch.py`
- `src/llanfeng_code_assistant/file_ops.py`
- `docs/protocol.md`
- `tests/test_codex_model_catalog_editor.py`
- `tests/test_config_writers.py`
- `tests/test_deeplink.py`
- `tests/test_model_fetcher.py`
- `tests/test_models.py`
- `tests/test_storage_and_installer.py`

Why: these owners and contracts are explicitly removed by the user and approved
retirement design.

Change necessity: leaving files or dependencies dormant would preserve the
wrong end state and duplicate ownership.

Repair track:

- Keep only install command construction, prerequisite downloads, npm registry,
  and CLI installation in `installer.py`.
- Remove CodexPlusPlus executable preference, terminal opening, and launch-close
  initialization.
- Remove protocol/keyring/Anthropic config constants and profile/config paths.
- Remove `tomlkit`, `pydantic`, and `keyring` dependencies and runtime cache
  checks; keep `websockets` and `chromium_reader` packaging declarations.
- Remove the full Inno Setup `[Registry]` section.
- Update packaging tests to assert absence, not presence, of protocol contracts.

Retirement track:

- Delete source and tests together.
- Do not touch `%APPDATA%` databases or Windows Credential Manager entries.
- The user's current uncommitted changes in `models.py` and `model_fetcher.py`
  are intentionally retired under the approved design.

Verification:

```powershell
python -m pytest -q tests/test_installer.py tests/test_packaging_config.py tests/test_packaging_runtime_patch.py
python -m ruff check src tests
```

Steps:

- [ ] Add focused installer/package tests for pinned commands, prerequisites,
  retained runtime packages, and absent protocol registry/arguments.
- [ ] Run tests to confirm legacy expectations fail.
- [ ] Reduce retained modules/metadata/scripts and delete all listed retirement
  files using workspace-scoped operations.
- [ ] Run focused tests, Ruff, and import smoke tests.
- [ ] Run the lingering-reference scan before marking retirement complete.

## Task 5: Rewrite product and packaging documentation

Files:

- `README.md`
- `PRODUCT.md`
- `docs/packaging.md`
- `CHANGELOG.md`
- Keep `Codex.md` as the user-supplied technical reference.

Why: documentation currently advertises removed configuration/protocol behavior
and a stale build record that proves the opposite target state.

Change necessity: code-only removal would leave incorrect user and release
contracts.

Implementation:

- README describes the four actions, model eligibility rules, Codex-close
  requirement, plugin enhanced launch, development commands, and new file tree.
- PRODUCT defines Windows developers installing CLIs/enhancing Codex, not
  provider profile management.
- Packaging docs remove protocol registration and stale protocol-containing
  artifact evidence; update retained runtime package list.
- CHANGELOG adds an `Unreleased` breaking refactor entry while preserving the
  user's existing unrelated edit and historical releases.

Verification:

```powershell
rg -n "配置列表|新增配置|启用配置|导入配置|协议文档|llanfeng-code://|--import-url|注册协议" README.md PRODUCT.md docs/packaging.md
python -m pytest -q tests/test_packaging_config.py
```

Expected residual scan result: no removed product instructions.

Steps:

- [ ] Rewrite current product docs against the approved design.
- [ ] Preserve historical changelog entries but add an accurate current section.
- [ ] Run documentation residual scans and packaging tests.
- [ ] Review all links and commands against current files.
- [ ] Record checkpoint/evidence.

## Task 6: Full verification, complexity closure, and architecture record

Files:

- Review all changed files.
- Update Aegis work evidence/checkpoint/drift records.
- Create or update an ADR only if verification confirms the durable owner and
  compatibility decisions implemented by the approved design.

Why: broad deletion, persistence mutation, CDP behavior, and installer contract
changes require requirement-by-requirement evidence rather than a narrow green
unit test.

Verification sequence:

```powershell
python -m pytest -q
python -m ruff check src tests
python -m compileall -q src
python -m llanfeng_code_assistant --version
rg -n "ProfileRepository|ProviderProfile|ProviderDraft|ModelFetcher|CodexConfigManager|ClaudeConfigManager|parse_deeplink|PROTOCOL_SCHEME|PROTOCOL_DOCUMENT|import_url|llanfeng-code://|keyring|pydantic|tomlkit" src tests scripts README.md PRODUCT.md docs/packaging.md pyproject.toml
```

Then run best-available Windows packaging verification and inspect `git diff`
for file-size, owner, unexpected-data, and generated-artifact issues.

Steps:

- [ ] Run targeted tests for every new owner once more.
- [ ] Run full pytest, Ruff, compile, CLI version, and retirement scans.
- [ ] Run Windows app/installer builds when local prerequisites are available.
- [ ] Inspect the final diff and calculate complexity closure for maintained
  source and test files.
- [ ] Bundle/check Aegis work records, perform the completion audit against all
  six requirements, and only then mark the goal complete.

## Risks and Rewind Rules

- If the bundled model command schema differs, update only the parser contract;
  do not add a hard-coded fallback model list.
- If LevelDB mutation planning cannot prove it preserves unknown fields/defaults,
  stop before write and fix the canonical unlocker.
- If Codex target selection cannot distinguish the renderer, do not inject.
- If marketplace compatibility requires copying AGPL source/assets, stop and
  request a license decision rather than vendoring.
- If deleted legacy modules still have a live consumer, migrate that consumer to
  an approved owner or classify it as a design gap; do not restore dormant
  compatibility.
- If a Windows build fails due network/toolchain, preserve all logs and report
  the release evidence gap; unit/static completion claims remain narrower.

## Retirement Verification Plan

- Main-path check: four UI actions and retained update/install flows work.
- Lingering-reference check: no active imports, labels, args, registry entries,
  dependencies, or tests for retired owners.
- Negative check: `--import-url` is rejected and removed modules cannot import.
- Boundary check: existing user data paths are neither deleted nor migrated;
  model writes preserve defaults and plugin injection targets only Codex.
