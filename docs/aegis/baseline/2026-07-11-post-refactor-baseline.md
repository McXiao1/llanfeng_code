# Llanfeng Code Assistant Post-Refactor Baseline

Date: `2026-07-11`
Status: `post-refactor dual-baseline snapshot`
Decision record: `docs/aegis/adr/ADR-0001-codex-owned-install-and-enhancement-boundaries.md`

## 1. Purpose

This snapshot records the product and runtime boundaries after the approved
install-and-Codex-enhancements refactor. It supersedes the initial snapshot as
the current-state reference while preserving the initial file as historical
pre-refactor evidence.

## 2. Current Authority Surfaces

- The active six-item `/goal` request and the user-approved design define the
  accepted refactor scope.
- `README.md` and `PRODUCT.md` describe the current four-action product.
- `Codex.md` remains the user-supplied technical reference for the Codex Statsig
  whitelist format.
- `ADR-0001` records why provider/protocol owners were deleted and why Codex,
  Statsig, the CDP launcher, and the marketplace module have distinct authority.
- `pyproject.toml`, `scripts/build_windows.ps1`, and `scripts/installer.iss` own
  the package and Windows distribution contract.
- Work evidence and final verification live under
  `docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/`.

## 3. Product / Requirement Baseline

### 3.1 Current Product

The Windows desktop application exposes exactly four primary actions:

1. `安装/更新 Codex`
2. `安装/更新 Claude`
3. `解锁模型`
4. `增强启动 Codex`

Environment status, manual refresh, single-instance startup, and the in-app
release update banner remain support behavior rather than additional primary
product actions.

### 3.2 Removed Product Contracts

The product no longer exposes or supports:

- provider configuration lists or profile persistence;
- Add/Edit/Delete/Enable controls or profile dialogs;
- provider model fetching, config writers, reset-config, or profile terminals;
- profile-derived model or launch behavior;
- protocol documentation, `--import-url`, `llanfeng-code://` parsing, or URL
  scheme registration.

These removals are intentional breaking changes, not deferred UI hiding.

### 3.3 Product Non-goals

- Replacing the removed provider configuration system.
- Purging or migrating legacy profile SQLite or Windows Credential Manager data.
- Changing the user's current Codex default model.
- Exposing Codex models marked hidden/internal.
- Bundling CodexPlusPlus source, assets, plugin snapshots, or settings UI.
- Supporting arbitrary Electron targets or non-Windows hosts.

## 4. Architecture / Runtime Boundary Baseline

### 4.1 Canonical Owners

| Surface | Canonical owner | Contract |
| --- | --- | --- |
| Flet orchestration | `src/llanfeng_code_assistant/app.py` | Render four actions, coordinate async work, confirmations, status, and updates; no LevelDB or JavaScript implementation. |
| CLI installation | `src/llanfeng_code_assistant/installer.py` | Install only pinned Codex and Claude npm packages, execute npm through its resolved executable or Windows `.CMD` shim, and acquire Node/Git prerequisites. |
| Environment status | `src/llanfeng_code_assistant/environment.py` | Detect Node, npm, Git, Codex, and Claude by executing each resolved command path. |
| Model candidate discovery and persistent unlock | `src/llanfeng_code_assistant/codex_statsig_unlocker.py` | Query the Codex bundled catalog and append missing eligible slugs to Statsig. |
| Codex Desktop launch and CDP delivery | `src/llanfeng_code_assistant/codex_desktop_launcher.py` | Find Microsoft Store Codex, allocate loopback CDP, verify the renderer, and deliver the script. |
| Marketplace compatibility script | `src/llanfeng_code_assistant/codex_plugin_marketplace.py` | Independently implement plugin list/install/filter compatibility behavior. |
| Application updates | `src/llanfeng_code_assistant/updater.py` and `update_banner.py` | Check, download, and start release installers. |
| Single-instance behavior | `src/llanfeng_code_assistant/single_instance.py` | Prevent duplicate normal GUI instances. |

No retained behavior has a profile, protocol, local-catalog, or generic-injection
fallback owner.

### 4.2 Model Source-of-Truth Chain

```text
installed Codex CLI bundled catalog
  -> explicit visibility == "list" and supported_in_api is not False
  -> unique non-empty slugs in catalog order
  -> Statsig dynamic config 107580212 available_models
  -> append missing values only
```

- Missing, malformed, timed-out, or empty catalog discovery fails before backup
  or write.
- A missing `visibility` field is not treated as visible.
- Hidden models such as `codex-auto-review` remain excluded.
- Existing order, unknown fields, and `default_model` are preserved.
- A LevelDB backup is created only when a real mutation plan exists.
- Malformed Statsig records remain untouched and are surfaced as warnings.

### 4.3 Marketplace Enhancement Chain

```text
Microsoft Store package OpenAI.Codex
  -> ChatGPT.exe or Codex.exe
  -> loopback CDP port
  -> target type page with app:// URL
  -> Page.addScriptToEvaluateOnNewDocument
  -> Runtime.evaluate
  -> independent marketplace compatibility script
```

- An already-running Codex process is not attached to or terminated by the
  marketplace action; the user is asked to close it.
- Partial launch is explicit: the process can start while enhancement fails.
- The script is behavior-level independent work and does not copy or distribute
  CodexPlusPlus AGPL source or resources.
- Unsupported renderer/request shapes fail closed or remain best-effort; they do
  not reactivate legacy profile/model injection.

### 4.4 Process and Persistent-Data Safety

- Model unlocking requests explicit in-app confirmation before terminating a
  running Codex process.
- The application does not read, migrate, or delete the retired profile SQLite
  database or Credential Manager records.
- The only retained persistent mutation is the bounded Statsig LevelDB append,
  protected by process checks and delayed backup.

## 5. Packaging and Dependency Baseline

Runtime dependencies are limited to fixed versions of `certifi`, `flet`,
`httpx`, `websockets`, and `chromium-reader`. `tomlkit`, `pydantic`, and
`keyring` are no longer runtime dependencies.

The Inno Setup installer:

- installs per-user under `%LOCALAPPDATA%\Programs\Llanfeng Code Assistant`;
- contains no `[Registry]` block or URL scheme registration;
- packages the recursively built Flet Windows directory;
- builds `app.zip` from an explicit runtime-root allowlist and rejects development
  roots, retired modules, `.pyc`, `__pycache__`, and `.egg-info` contamination;
- uses Inno Setup 6.7.3 in the maintained build workflow.

The source entrypoint supports `python -m llanfeng_code_assistant --version`.
The generated Flet Windows runner reserves non-empty arguments for developer
mode and therefore is not used as an arbitrary CLI or packaged `--version`
probe; packaged verification uses build success, artifact inspection, hashing,
and manual GUI checks.

## 6. Retirement State

The following internal owners are deleted rather than retained as compatibility
carriers:

- `src/llanfeng_code_assistant/config/`
- `storage.py`, `secrets.py`, `models.py`, and `model_fetcher.py`
- `codex_model_catalog_editor.py`
- `deeplink.py` and `protocol_document.py`
- `inject_launch.py` and `file_ops.py`
- `docs/protocol.md`
- `assets/codex-plugin.vbs`
- tests whose only purpose was a retired owner or contract

The complete Inno Setup protocol registration block is also deleted. Historical
changelog and Aegis baseline references may still name retired concepts as
history; they are not runtime owners.

## 7. Complexity and Dependency Direction

- `app.py` is an orchestration owner only. At 645 physical lines it is above the
  plan's approximate 550-line target but far below the project 2000-line hard
  limit and no longer contains profile, persistence, model parsing, or script
  construction responsibilities.
- `codex_desktop_launcher.py` is 387 physical lines versus an approximate
  350-line planning target, and `codex_statsig_unlocker.py` is 660 versus an
  approximate 650-line target. Both remain below the hard limit and keep focused
  CDP and Statsig responsibilities rather than mixed profile behavior.
- `codex_plugin_marketplace.py` is 395 physical lines, within its approximate
  450-line budget. Launcher, Statsig, marketplace, installer, update, and
  single-instance logic remain separate modules with one reason to change each.
- Current Python source/tests total 5,305 physical lines versus 9,549 at `HEAD`,
  a net reduction of 4,244 lines after deleting 19 legacy files and adding five
  focused owners/tests.
- Net maintained-source entropy decreases because the refactor removes the
  multi-module profile/protocol systems and does not retain dormant fallbacks.

## 8. Verification Boundary and Known Risks

Automated verification covers pure catalog filtering, Statsig mutation planning
and log encoding, UI action contracts, install command construction, CDP target
selection and command delivery, marketplace script behavior, packaging
configuration, imports, linting, and Windows build/installer generation. Exact
results and hashes are recorded in the work evidence bundle.

Still outside automated coverage:

- mutating a real user Codex Statsig LevelDB;
- launching and validating enhancement against the user's live Codex Desktop
  renderer and account-specific marketplace response;
- full interactive installer install/uninstall and GUI walkthrough.

These are bounded release/manual-validation risks, not alternate owners or
compatibility paths.

## 9. Alignment Conclusion

Result: `aligned`
Scope: `both`

The current product and runtime architecture implement the approved six-item
scope, the owner map in ADR-0001, the delete-first retirement boundary, and the
persistent-data non-goal. Any future reintroduction of profiles, protocol
registration, local model catalogs, unverified CDP targets, or CodexPlusPlus
source/assets requires a new explicit product and architecture decision.
