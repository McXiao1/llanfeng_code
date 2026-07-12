# Install and Codex Enhancements Refactor Design

Date: `2026-07-11`
Status: `approved by user on 2026-07-11`
Architecture review required: `yes`

## 1. Decision Summary

Refactor Llanfeng Code Assistant into a small Windows installation and Codex
enhancement console. Fully retire the provider configuration and deep-link
protocol systems. Retain exactly four primary user actions:

1. Install or update Codex CLI.
2. Install or update Claude Code CLI.
3. Unlock eligible Codex models in the persistent Statsig whitelist.
4. Launch Codex Desktop with a runtime plugin marketplace enhancement.

The recommended architecture reuses the existing installer, Statsig unlocker,
and CDP launcher owners. It adds one focused plugin-marketplace script module and
removes all profile-derived behavior.

## 2. Requirement Mapping

| User requirement | Design response |
| --- | --- |
| Remove configuration list and related code | Delete the full profile, secret, model-fetch, config-write, activation, reset, and profile-terminal system. |
| Keep only Codex and Claude one-click installation | The install area contains only Codex and Claude actions; prerequisite handling remains internal. |
| Remove protocol documentation and registration | Delete protocol parser/document UI and files, remove `--import-url`, and remove the Inno Setup registry section. |
| Remove the Add button | The new UI has no tabs, profile list, Add/Edit/Delete/Enable controls, or profile dialogs. |
| Unlock unrendered Codex models | Discover the installed Codex bundled catalog and append only eligible missing slugs to Statsig configuration `107580212`. |
| Unlock plugin marketplace | Start Codex Desktop with CDP and inject an independently implemented request/filter compatibility patch based on observed CodexPlusPlus behavior. |

## 3. Evidence and Constraints

- `README.md` describes the legacy configuration and protocol product that the
  goal supersedes.
- `Codex.md` identifies Statsig dynamic config `107580212` and the LevelDB value
  encoding used by Codex Desktop.
- On this machine, `codex --version` reports `codex-cli 0.144.1`.
- `codex debug models --bundled` returns structured JSON with `slug`,
  `visibility`, `supported_in_api`, and ordering metadata. It currently lists
  `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` as visible models and
  `codex-auto-review` as hidden.
- The current CodexPlusPlus renderer reference uses marketplace unlock version
  `12`, expands list requests to include `vertical`, restores marketplace aliases,
  repairs install requests, bypasses two UI filters, and covers client, Electron
  bridge, and window-message request paths.
- CodexPlusPlus currently states an `AGPL-3.0-only` license. This project will
  reimplement the minimum required behavior independently and will not copy or
  distribute its source, plugin snapshots, labels, assets, or settings system.

## 4. Options

### Option A: Full retirement plus focused Codex enhancement owners (recommended)

- Delete the configuration and protocol systems completely.
- Use `codex debug models --bundled` as the model candidate source.
- Reuse `codex_statsig_unlocker.py` for persistent whitelist mutation.
- Reuse `codex_desktop_launcher.py` for verified CDP launch and injection.
- Add `codex_plugin_marketplace.py` for a small, self-contained marketplace
  compatibility script.

Trade-off: requires broad test and documentation replacement, but leaves one
owner per behavior and directly matches the requested product.

### Option B: Hide legacy UI while retaining configuration internals

- Remove profile controls from the visible screen but keep persistence,
  configuration writers, protocol parser, and profile-derived injection paths.

Trade-off: smaller initial diff, but contradicts the request to remove related
code, retains unnecessary dependencies and public contracts, and leaves dormant
owners that future changes can accidentally revive. Rejected.

### Option C: Embed the complete CodexPlusPlus enhancement stack

- Vendor its renderer script, plugin snapshots, launcher settings, backend
  bridge, and update behavior.

Trade-off: wider compatibility coverage, but introduces a second application
inside this one, materially increases distribution size and maintenance, and
requires an explicit AGPL licensing decision. Rejected for this refactor.

## 5. First-Principles and Architecture Review

### First-principles invariants

- Non-negotiable goal: the application installs two CLIs and exposes two Codex
  enhancements without owning provider configuration.
- Non-negotiable constraints: user persistent data is not deleted; hidden models
  remain hidden; the default model is not changed; Codex Desktop is not silently
  terminated; plugin injection targets only Codex.
- Historical assumptions to delete: enhancements need an active profile; the app
  needs its own model list; retaining old code is safer than deleting it.

### Architecture Integrity Lens

- Invariant: every retained behavior has one canonical owner and no profile
  fallback.
- Canonical owner / contract: Codex CLI owns the bundled model catalog; Statsig
  owns render eligibility; the launcher owns CDP lifecycle; the plugin module
  owns only marketplace request/filter adaptation.
- Responsibility overlap: current runtime model injection, profile model data,
  catalog editing, and persistent whitelist mutation overlap. Runtime model
  injection and catalog editing are retired; persistent Statsig mutation remains.
- Higher-level simplification: query Codex's own bundled catalog instead of
  fetching or maintaining models in this application.
- Retirement / falsifier: if a supported Codex build lacks the bundled catalog
  command or no verified renderer target can be selected, fail clearly rather
  than restore legacy profile owners.
- Verdict: proceed with Option A after user approval.

### Existence Check

- Proposed new surface: `codex_plugin_marketplace.py`.
- Existing reuse candidates: `codex_desktop_launcher.py` and its embedded script.
- Why the existing surface is insufficient: executable/CDP lifecycle and
  marketplace JavaScript change on different boundaries and need independent
  tests; keeping both in the launcher recreates the current mixed responsibility.
- Creation proof: one script owner removes hundreds of unrelated model-injection
  lines from the launcher and supports direct script contract tests.
- Entropy / retirement impact: one new focused module replaces mixed embedded
  logic while `inject_launch.py` and profile coupling are deleted.
- Decision: `add-with-proof`.

## 6. Target Architecture

```text
app.py
├── environment.py                  system status
├── installer.py                    Codex / Claude installation
├── codex_statsig_unlocker.py       bundled catalog + Statsig LevelDB mutation
├── codex_desktop_launcher.py       Codex discovery + CDP lifecycle
│   └── codex_plugin_marketplace.py marketplace script and invariants
├── updater.py / update_banner.py   retained update flow
└── single_instance.py              retained process guard
```

`app.py` becomes a thin Flet coordinator. It starts background work, updates
control state, asks for destructive-process confirmation when required, and
renders results. It does not parse model catalogs, encode LevelDB records, or
construct marketplace JavaScript.

## 7. UI Design

The application uses a compact, single-page, light-theme layout with no tabs and
no gradients.

### Header

- Application name and version.
- Refresh-status icon button with tooltip.
- Existing update banner behavior remains available when a release is found.

### Environment status

- Compact status chips for Node.js, npm, Git, Codex, and Claude.
- Status is informational; no configuration state is displayed.

### Installation

- A Codex row/card with installed version, one install/update button, and a
  progress/result state.
- A Claude row/card with the same interaction.
- Node.js and Git prerequisite downloads remain part of the one-click workflow,
  not separate primary product actions.

### Codex enhancements

- `解锁模型` action: discovers eligible models and updates the Statsig whitelist.
- `增强启动 Codex` action: launches Codex Desktop with plugin marketplace
  enhancement.
- Results use text and Flet icons. No emoji, profile picker, Add button, protocol
  button, reset-config button, or profile terminal button exists.

## 8. Model Unlock Design

### 8.1 Candidate discovery

1. Resolve `codex` from the environment.
2. Run `codex debug models --bundled` with captured output and a bounded timeout.
3. Require a JSON object containing a `models` array.
4. Preserve CLI order while accepting unique, non-empty `slug` values only when:
   - `visibility` equals `list`, case-insensitively; and
   - `supported_in_api` is not explicitly `false`.
5. Never synthesize a model descriptor or maintain a local fallback list.

Malformed output, command failure, timeout, or zero eligible models aborts before
any LevelDB backup or write.

### 8.2 Statsig comparison and mutation

1. Locate the Codex LevelDB path by enumerating `OpenAI.Codex_*` package
   directories, validating LevelDB markers, and selecting the most recently
   modified valid storage path deterministically.
2. Read live Statsig evaluation records and find dynamic config `107580212`.
3. For every valid evaluation record, require `value.available_models` to be a
   string array and compare it with the candidate slugs. Malformed records remain
   untouched and are returned as warnings.
4. Preserve existing order and values; append only missing candidates in bundled
   catalog order.
5. Do not change `default_model`, `use_hidden_models`, model metadata, or other
   Statsig fields.
6. If no record requires a change, return an idempotent success and create no
   backup.
7. If a change is required, create one timestamped sibling backup, then append a
   correctly sequenced and fragmented LevelDB WriteBatch.
8. Update the matching Statsig last-modified timestamps when they can be parsed;
   failure to update that auxiliary record is non-fatal and reported in detail.

### 8.3 Running-process behavior

- If Codex is running, present an explicit confirmation that closing it can lose
  unsaved UI state.
- Only the confirmed action may terminate Codex and continue.
- Cancel performs no backup or write.
- A lock or permission error after confirmation fails without retry loops or
  partial fallback behavior.

## 9. Plugin Marketplace Design

### 9.1 Launch and target selection

1. Locate Microsoft Store Codex Desktop (`ChatGPT.exe` or `Codex.exe`). The npm
   CLI binary is not accepted as a desktop injection target.
2. Reject enhancement launch when Codex is already running without the expected
   CDP endpoint; ask the user to close it instead of attaching unpredictably.
3. Launch with `--remote-debugging-port=<port>` and
   `--remote-allow-origins=http://127.0.0.1:<port>`.
4. Poll `/json` with a bounded timeout and select only a page target whose URL or
   title matches the Codex application contract.
5. Install the script for future documents and evaluate it immediately.

### 9.2 Independently implemented runtime patch

The script is idempotent and limited to plugin marketplace behavior:

- Normalize plugin methods including `vscode://codex/list-plugins`,
  `vscode://codex/plugin/install`, `plugin/list`, and `plugin/install`.
- For list requests, restore known marketplace aliases, start with `local` when
  no kinds are supplied, add `vertical`, and deduplicate values.
- For install requests, restore `remoteMarketplaceName`; convert a
  `remote:<name>` marketplace path into the remote marketplace field expected by
  Codex.
- Patch the Electron bridge and window message request/response paths used by
  different Codex builds.
- Patch direct app-server clients only when the known module is discovered; this
  is an optional compatibility layer, not a required success condition.
- Bypass marketplace-hidden and build-flavor filters only when both the callback
  source signature and array item structure match known plugin marketplace
  shapes. Do not execute the callback merely to detect it.
- Do not merge local plugin snapshots, rename official marketplaces, inject
  models, alter service tiers, block Statsig networking, or add CodexPlusPlus UI.

If the renderer loads but no supported request path is found, the launch result
reports that Codex started without confirmed marketplace enhancement.

## 10. Retirement Scope

### Delete

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
- Tests whose only purpose is a retired owner or contract

The existing uncommitted edits in `models.py` and `model_fetcher.py` are part of
this explicit code-retirement decision. No behavior from those files is carried
forward.

### Rewrite or reduce

- `app.py`: single-page install/enhancement console.
- `codex_statsig_unlocker.py`: add bundled model discovery, typed result objects,
  delayed backup, and no default-model mutation.
- `codex_desktop_launcher.py`: remove profile/model/fast-startup scripts and keep
  verified desktop CDP lifecycle only.
- `__main__.py`: remove `--import-url`; retain `--version` and single-instance
  startup.
- `constants.py`: remove protocol, keyring, and Anthropic configuration constants.
- `paths.py`: retain only application-owned download/data paths still in use.
- `scripts/installer.iss`: remove all protocol registry entries.
- `pyproject.toml`: remove `pydantic`, `keyring`, and `tomlkit` after residual
  import verification.
- README, product, packaging, and changelog documentation: describe only the new
  product and contracts.

### Retain

- `installer.py`, `environment.py`, update modules, packaging support, and
  single-instance behavior, subject to small interface cleanup.
- `flet`, `httpx`, `websockets`, `chromium-reader`, and `certifi` dependencies.
- User-owned legacy SQLite and Credential Manager data files, untouched.

## 11. Anti-Entropy Decision

### Anti-Entropy Declaration

- Deletion class: configuration code is `code-retirement`; protocol registration
  is `contract-carrying code`; user database/keyring records are
  `persistent-state`.
- Old path: provider profiles, activation/config writers, profile-derived model
  injection, and `llanfeng-code://` import.
- New canonical owner: no replacement for retired configuration; Codex CLI and
  Statsig become the model source-of-truth chain.
- Expected preserved behavior: app startup, updates, environment detection,
  Codex/Claude installation, model unlocking, and Codex Desktop enhancement.
- Expected retired behavior: creating, editing, importing, enabling, resetting,
  or opening terminals from provider profiles.
- External boundary touched: yes, the explicitly removed URL protocol.
- Source-of-truth data risk: possible only if user data were deleted; the design
  forbids that deletion.
- User confirmation required: no for code retirement; yes only for terminating a
  running Codex process during an actual unlock action.

### Retirement Decision

- Path: `delete-first` for internal and protocol code.
- Why: the user explicitly removed the product contract and no active external
  compatibility requirement was provided.
- Non-edits: do not purge or migrate legacy database/keyring data.

## 12. Error Handling and Observability

- Service functions return typed success/failure result objects; UI text is
  derived at the orchestration layer.
- Subprocess commands use argument arrays, captured output, timeouts, and no
  shell interpolation.
- User-facing failures identify the failed stage and a concrete recovery action.
- Technical details are logged without API keys or legacy secrets.
- UI actions disable themselves while running and always restore control state in
  `finally` paths.
- Partial states are explicit: Codex may start while CDP injection fails; this is
  reported as launched-without-enhancement, not success.

## 13. Testing Strategy

### Model unlock tests

- Parse valid bundled catalogs and preserve order.
- Exclude hidden, unsupported, empty, malformed, and duplicate models.
- Abort before write on command failure or malformed JSON.
- Append only missing models and preserve `default_model`.
- Create no backup for an idempotent result.
- Create exactly one backup before a real write.
- Handle multiple evaluation keys, auxiliary timestamp failures, locked data,
  fragmented records, and missing Statsig configuration.

### Plugin and launcher tests

- Build launch arguments including the CDP origin allowance.
- Select Codex targets and reject unrelated pages.
- Verify immediate and new-document CDP evaluation commands.
- Exercise request normalization, alias restoration, kind expansion, install
  repair, and filter guards in a Node-based harness when Node is available.
- Verify clear timeout, occupied-port, missing-desktop, and already-running paths.

### UI, CLI, retirement, and packaging tests

- Assert the four primary actions and absence of tabs, Add, profile, protocol,
  reset-config, and import controls.
- Assert `--version` works and `--import-url` is rejected.
- Assert the installer has no protocol registry section.
- Assert packaging includes retained runtime dependencies only.
- Run residual scans for configuration, protocol, keyring, Pydantic, and Tomlkit
  imports or labels.

## 14. Acceptance Criteria

1. The application opens to a compact light-theme page with only the two install
   and two Codex enhancement actions as primary commands.
2. No configuration list, Add button, profile dialog, activation, model fetch,
   reset-config, profile terminal, protocol document, or deep-link import path
   remains.
3. Codex and Claude one-click installation still handles prerequisites and
   reports success/failure.
4. Model unlock derives candidates from the installed Codex bundled catalog,
   excludes hidden/unsupported models, appends only missing whitelist values,
   preserves the default model, and backs up only before a real write.
5. Plugin enhancement starts a verified Codex Desktop renderer and applies the
   minimal marketplace request/filter patch without requiring a profile.
6. Existing user profile database and Credential Manager data are not deleted.
7. `python -m pytest -q` passes.
8. `python -m ruff check src tests` passes.
9. `python -m llanfeng_code_assistant --version` exits successfully.
10. Residual source/document scans find no unintended configuration or protocol
    owners.
11. Windows application and installer builds succeed when the required local
    Flet/Inno Setup toolchain is available.

## 15. Compatibility and Rollback Boundary

- Compatibility retained: normal app invocation, `--version`, single instance,
  update checks, prerequisite installation, and installed CLI detection.
- Compatibility intentionally removed: `--import-url`, `llanfeng-code://`, all
  profile/database/keyring APIs, configuration writers, and profile-derived CDP
  launch.
- Model write rollback: timestamped LevelDB backup path is surfaced to the user.
- Code rollback: normal Git revert of the refactor; no database migration must be
  reversed because no legacy data is mutated.

## 16. Non-goals

- Changing CLI package versions during this refactor.
- Adding a settings page, theme switcher, plugin manager, or model selector.
- Unlocking models with `visibility: hide`.
- Changing the Statsig default model.
- Supporting arbitrary Electron apps or browser pages through the CDP launcher.
- Copying or distributing CodexPlusPlus implementation code or plugin content.

## 17. ADR Signal

This design changes durable owners, removes a public URL protocol, establishes
the Codex CLI as the model catalog source of truth, and separates persistent
model unlocking from runtime plugin enhancement. After implementation and
verification, evaluate an ADR that records these owner and compatibility
decisions and synchronizes the project baseline.

## Appendix A: TaskIntentDraft

- Outcome: remove configuration/protocol behavior, retain two installers, and add
  profile-independent Codex model/plugin enhancement.
- Success evidence: retirement scans, focused tests, full pytest/Ruff, CLI smoke,
  and packaging checks.
- Stop condition: pause on persistent-data risk, unknown destructive action,
  missing Codex contract evidence, or implementation outside this design.
- Non-goals: legacy data purge, full CodexPlusPlus integration, or a replacement
  configuration system.

## Appendix B: BaselineUsageDraft

- Required baseline refs: `README.md`, `Codex.md`, `pyproject.toml`,
  `scripts/installer.iss`, current source/tests, and the read-only CodexPlusPlus
  reference excerpts.
- Acknowledged before plan: all required refs above.
- Cited in design: all required refs above.
- Missing refs: none for design approval.
- Decision: `pause-for-user` at the design review gate.

## Appendix C: ImpactStatementDraft

- Affected layers: Flet UI/CLI, package dependencies, installer registry,
  Statsig LevelDB, Codex Desktop CDP, tests, and product documentation.
- Owners: reduced `app.py`; retained `installer.py`,
  `codex_statsig_unlocker.py`, and `codex_desktop_launcher.py`; new focused
  `codex_plugin_marketplace.py`.
- Invariants: no hidden models, no default-model change, no silent process kill,
  no legacy data deletion, no profile fallback, and no unrelated CDP target.
- Compatibility boundary: preserve install/update/startup; intentionally remove
  configuration and protocol contracts.



