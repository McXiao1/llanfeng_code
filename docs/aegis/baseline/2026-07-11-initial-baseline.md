# Llanfeng Code Assistant Initial Baseline

Date: `2026-07-11`
Status: `initial dual-baseline snapshot`

## 1. Purpose

This snapshot records the product and runtime boundaries that existed before the
install-and-Codex-enhancements refactor. Later alignment checks should use it to
distinguish the confirmed target state from legacy implementation that is being
retired.

## 2. Workspace Structure

- `src/llanfeng_code_assistant/`: Flet UI, CLI entrypoint, installers, provider
  configuration, Codex enhancement logic, updates, and persistence.
- `tests/`: unit and contract-oriented tests for the current Python application.
- `scripts/`: Flet and Inno Setup packaging workflow.
- `docs/`: packaging, product, and protocol documentation.
- `build/reference/`: ignored, read-only excerpts from CodexPlusPlus used for
  behavioral research; it is not a distribution input.

## 3. Current Authority Surfaces

- `README.md`: current released product description and developer commands.
- `Codex.md`: user-provided analysis of the Codex Statsig model whitelist.
- The active `/goal` request: confirmed target scope for the refactor.
- `pyproject.toml`: Python package, dependency, test, and lint configuration.
- `scripts/installer.iss`: Windows installer and protocol registration contract.
- `build/reference/CodexPlusPlus-README.md` and `renderer-inject.js`: external
  behavioral reference for plugin marketplace enhancement.
- No accepted ADR existed before this Aegis workspace was initialized.

## 4. Product / Requirement Baseline

### 4.1 Current Truth

- The released application presents itself as a Codex and Claude configuration
  manager with profiles, activation, model fetching, deep-link import, CLI
  installation, updates, and Codex Desktop enhancement launch.
- The new confirmed target removes provider configuration and protocol import,
  leaving Codex and Claude one-click installation plus two Codex enhancements:
  model whitelist unlocking and plugin marketplace unlocking.
- The application targets Windows 10/11 and Python 3.12+.
- The default presentation is a compact light-theme Flet desktop application.
- Acceptance requires automated tests, Ruff, CLI version smoke testing, residual
  reference scans, and packaging validation where the local toolchain permits.

### 4.2 Non-negotiables

1. No configuration list, profile editor, add button, activation flow, or
   provider model fetcher remains in the product.
2. No `llanfeng-code://` protocol documentation, parser, CLI argument, or
   installer registry registration remains.
3. Codex model candidates come from the installed Codex CLI catalog, not an
   application-maintained model list.
4. Hidden/internal Codex models are not exposed.
5. Plugin marketplace enhancement does not require an active provider profile.
6. The application does not automatically delete existing user SQLite or
   Windows Credential Manager data.

### 4.3 Product Non-goals

- A replacement provider configuration editor.
- Migration or purge of legacy profile and keyring data.
- Bundling the complete CodexPlusPlus application, plugin snapshot, or settings
  subsystem.
- Changing the user's current Codex default model.
- Supporting non-Windows desktop platforms in this refactor.

## 5. Architecture / Runtime Boundary Baseline

### 5.1 Current Truth

- `app.py` currently coordinates UI, profiles, persistence, configuration files,
  deep links, installation, model fetching, model unlocking, CDP injection, and
  updates; this is an over-broad owner scheduled for reduction.
- `storage.py`, `secrets.py`, `models.py`, `model_fetcher.py`, and `config/`
  collectively own the legacy provider configuration system.
- `deeplink.py`, `protocol_document.py`, `__main__.py`, and
  `scripts/installer.iss` collectively own the legacy protocol contract.
- `codex_statsig_unlocker.py` is the existing owner for persistent Statsig
  LevelDB mutation.
- `codex_desktop_launcher.py` is the existing owner for Codex executable
  discovery, CDP launch, target connection, and runtime script injection.
- `installer.py` is the existing owner for Node/Git prerequisite acquisition and
  pinned npm CLI installation.

### 5.2 Architecture Non-negotiables

1. Each retained behavior has one canonical owner.
2. The UI orchestrates services but does not contain LevelDB or JavaScript patch
   implementation details.
3. Model unlocking and plugin marketplace unlocking are independent flows.
4. Persistent model unlocking writes only missing list-visible model slugs and
   creates a backup only when a write is required.
5. CDP injection targets only a verified Codex renderer and is idempotent.
6. Retired configuration and protocol owners are deleted rather than kept as
   dormant compatibility paths.

### 5.3 Architecture Non-goals

- A generic browser-injection framework.
- A second model catalog maintained by this application.
- A fallback that reads legacy profiles for Codex enhancement behavior.
- An in-app database migration layer for data that is no longer read.

## 6. Ownership / Contract Snapshot

| Surface | Pre-refactor owner | Target owner |
| --- | --- | --- |
| UI orchestration | `app.py` | reduced `app.py` |
| CLI installation | `installer.py` | `installer.py` |
| Environment status | `environment.py` | `environment.py` |
| Persistent model unlock | `codex_statsig_unlocker.py` | rewritten same module |
| Codex Desktop CDP lifecycle | `codex_desktop_launcher.py` | reduced same module |
| Plugin marketplace patch | mixed into launcher | `codex_plugin_marketplace.py` |
| Provider profiles/config | multiple modules | retired |
| Deep-link protocol | multiple modules and installer registry | retired |
| Application updates | updater modules | retained |

## 7. Current State and Risks

- The pre-refactor baseline is `158 passed, 12 failed`; failures were observed
  before implementation and are concentrated in legacy model/UI expectations.
- Ruff reports 64 pre-refactor findings across legacy source and tests.
- The worktree already contains user changes in `CHANGELOG.md`,
  `model_fetcher.py`, `models.py`, plus untracked `Codex.md`.
- `model_fetcher.py` and `models.py` are inside the confirmed retirement scope;
  their local edits must not be silently reintroduced through a compatibility
  layer.
- LevelDB mutation can corrupt or lose cached state if locking, backup, encoding,
  sequence numbering, or record fragmentation is mishandled.
- CDP injection can affect an unrelated Electron page if target selection is not
  strict.
- CodexPlusPlus currently documents an `AGPL-3.0-only` license; implementation
  must not copy its source or bundled assets into this project without an
  explicit license decision.

## 8. Alignment Use

- Read the Product / Requirement Baseline before changing user-visible scope,
  labels, actions, or acceptance criteria.
- Read the Architecture / Runtime Boundary Baseline before adding an owner,
  fallback, persistence path, or compatibility carrier.
- Report `scope: both` when a change affects both the user workflow and the
  canonical owner/source-of-truth boundary.

## 9. Compatibility Boundary

- Preserve normal application startup, single-instance behavior, release update
  checks, environment detection, and Codex/Claude installation.
- Intentionally remove provider profile/configuration behavior and the public
  `llanfeng-code://` import contract.
- Preserve existing user-owned database and keyring records on disk, but stop
  reading or writing them.
- Do not force-close a running Codex process without an explicit in-app
  confirmation for that action.
