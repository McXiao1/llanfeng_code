# ADR-0001 - Codex-owned installation and enhancement boundaries

Status: `recorded-from-work`
Date: `2026-07-11`

## Source Evidence

- Approved design, completed refactor, full automated verification, residual scans, and fresh Windows packaging evidence.
## Context

The application previously mixed provider profiles, secret/config persistence, URL protocol import, model fetching, runtime model injection, CDP launch, and installation. The approved four-action product removes provider configuration and the public protocol while retaining Codex/Claude installation plus persistent model and runtime plugin enhancements. Future maintainers need a durable explanation for the delete-first compatibility break, the source-of-truth chain, and the independent CodexPlusPlus behavior reimplementation boundary.

## Decision

Retain exactly four primary actions. InstallerService owns only pinned Codex and Claude CLI installation and prerequisites. The installed Codex CLI bundled catalog is the sole model candidate source; codex_statsig_unlocker.py accepts only explicit list-visible, API-supported slugs and appends missing Statsig whitelist entries without changing the default model. codex_desktop_launcher.py owns Microsoft Store Codex discovery, loopback CDP lifecycle, verified app:// renderer selection, and script delivery. codex_plugin_marketplace.py independently owns marketplace compatibility behavior. Provider/profile/configuration and llanfeng-code protocol owners are deleted with no compatibility fallback, while user SQLite and Credential Manager data remain untouched.

## Alternatives Considered

- Hide the legacy profile/protocol UI while retaining dormant owners; rejected because it preserves duplicate authority and contradicts code removal.
- Vendor the complete CodexPlusPlus stack; rejected because it adds unrelated product scope and requires an explicit AGPL distribution decision.
- Maintain a local or profile-derived model catalog fallback; rejected because it duplicates the Codex source of truth and can expose hidden/internal models.
## Consequences

- The profile and llanfeng-code:// contracts are intentionally breaking removals; no migration layer or dormant fallback remains.
- Unsupported Codex bundled-catalog or verified-renderer contracts fail closed with actionable messages instead of reactivating legacy owners.
- Marketplace enhancement remains version-sensitive to Codex Desktop internals and requires real-host validation beyond unit and packaging tests.
## Compatibility Boundary

Preserve normal GUI startup, single-instance behavior, update checks, environment status, prerequisite handling, and pinned Codex/Claude installation. Intentionally remove profiles, config writers, model fetching, --import-url, llanfeng-code:// registration, and profile-derived launch. Never purge legacy SQLite/keyring data; terminate Codex only after explicit in-app confirmation for model writes.

## Retirement Impact

Delete the configuration, storage, secret, model-fetch, config-writer, deep-link, protocol-document, legacy injection, `assets/codex-plugin.vbs`, and related test owners plus the Inno Setup Registry block. No compatibility carrier is retained. Codex CLI, Statsig mutation, CDP lifecycle, and marketplace script each have one canonical owner. Flet packaging now excludes development roots and fails the build if retired modules, derived bytecode, or non-runtime roots enter `app.zip`.

## Baseline Sync

- Needed: needed
- Target: docs/aegis/baseline/2026-07-11-post-refactor-baseline.md
- Action: create snapshot
- Reason: The completed work changes the ownership map, source-of-truth chain, public compatibility boundary, runtime injection contract, dependency set, and retirement state.

## Evidence References

- docs/aegis/specs/2026-07-11-install-and-codex-enhancements-design.md
- docs/aegis/plans/2026-07-11-install-and-codex-enhancements-refactor.md
- docs/aegis/work/2026-07-11-install-and-codex-enhancements-refactor/90-evidence.md
- README.md
- tests/test_codex_statsig_unlocker.py
- tests/test_codex_desktop_launcher.py
- tests/test_codex_plugin_marketplace.py
## Boundary

This ADR is an advisory Aegis Method Pack record. It does not grant completion authority or replace project-authoritative architecture sources.

## Superseded By

- Status: superseded
- Date: 2026-07-12
- ADR: docs/aegis/adr/ADR-0002-safe-codex-configuration-restore.md
- Reason: The prior decision remains the historical reason provider/protocol owners were removed, but its exact four-action product boundary and single persistent-mutation statement are replaced by the approved, implemented fifth safe-restore action.
