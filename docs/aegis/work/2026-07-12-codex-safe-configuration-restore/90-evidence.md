# Codex 安全配置恢复 - Evidence

Evidence bundles are recorded below; this file is a Method Pack evidence trail.

## EvidenceBundleDraft

- Artifact key: statsig-exact-cache-invalidation
- Type: test-output
- Source: python -m pytest -q tests/test_codex_statsig_unlocker.py; focused Ruff
- Summary: Regression-first Statsig slice passed: 26 tests verify exact evaluation/timestamp key selection, unrelated-key preservation, LevelDB deletion record encoding, sequence/count compatibility, idempotence, write-attempt failure metadata, and large-batch fragmentation; Ruff is clean.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: reversible-config-restore-transaction
- Type: test-output
- Source: python -m pytest -q tests/test_codex_config_restorer.py; focused Ruff
- Summary: New restore transaction owner passed 10 tests covering exact preview scope, unreadable LevelDB guard, no-op idempotence, mandatory file/LevelDB backup, non-secret manifest, auth.json byte preservation, backup hard-stop, CLI rollback, LevelDB rollback, partial rollback reporting, and collision-safe backup names; Ruff is clean.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: five-action-restore-ui
- Type: test-output
- Source: python -m pytest -q tests/test_entrypoint_and_ui.py; focused Ruff
- Summary: Five-action Flet UI passed 19 tests: restore no-op, exact target/preserved-data confirmation, running-Codex close confirmation, success backup/restart guidance, termination failure, partial rollback visibility, existing install/unlock/launch/update behavior, and absence of retired UI; Ruff is clean.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: packaging-and-product-contract
- Type: test-output
- Source: python -m pytest -q tests/test_packaging_config.py; python -m ruff check src tests; git diff --check; active-doc residual scan
- Summary: Packaging contract passed 22 tests, requires codex_config_restorer.py, current docs describe exactly five actions and safe restore semantics, retired reset/auth-deletion wording has zero active hits, Ruff is clean, and diff whitespace checks pass after two EOF-only fixes.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: architecture-and-baseline-sync
- Type: architecture-record
- Source: ADR creation gate; helper-backed supersede-adr; new current baseline; aegis-workspace check
- Summary: ADR-0002 supersedes only ADR-0001 current-state assertions while preserving ADR-0001 as history; the new baseline records five actions, the restorer/Statsig owner split, exact mutable targets, auth preservation, rollback, packaging, complexity, and retirement boundaries. Workspace structure check passed.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: full-python-and-retirement-verification
- Type: test-output
- Source: python -m pytest -q; python -m ruff check src tests; python -m compileall -q src; python -m llanfeng_code_assistant --version; git diff --check; retired-symbol/path scans
- Summary: Fresh full verification passed: 118 pytest tests, Ruff clean, source compileall exit 0, version entrypoint 1.2.0, diff whitespace check clean aside from line-ending notices, retired-symbol scan had zero live hits, and every explicitly retired path is absent.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: fresh-windows-app-and-archive
- Type: build-output
- Source: .\scripts\build_windows.ps1; independent Python ZipFile audit; Get-FileHash
- Summary: Fresh Flet Windows build passed after running outside the sandbox because Flutter required its SDK lockfile. app.zip contains 17 runtime entries, includes codex_config_restorer.py, has zero retired/bytecode/development-root hits, and six key packaged modules match source byte-for-byte. app.zip: 46,210 bytes, 2026-07-12 11:42:01 +08:00, SHA-256 17633AE40C701EF23750D086B46E9A032F4D5DD30FB0C2F1A4A7F0272BAA7B02.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: fresh-windows-installer
- Type: build-output
- Source: .\scripts\build_installer.ps1 -SkipAppBuild; Inno Setup 6.7.3; Get-FileHash
- Summary: Fresh installer build passed using the audited Windows app. Llanfeng-Code-Assistant-Setup-1.2.0.exe: 28,769,900 bytes, 2026-07-12 11:45:06 +08:00, SHA-256 7F2E10FE971F4CEE20F3CFCFEAE65E8E1FD0305969DD9CB6EC3E3624C1BC4116. ProductVersion is 1.2.0; artifact is not Authenticode-signed.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: final-fresh-verification
- Type: test-output
- Source: final pytest/Ruff/compile/version/retirement/diff/archive/hash rerun after all source and documentation edits
- Summary: Final fresh verification passed: full suite 118 tests, critical installer/Statsig/restore/UI/packaging subset 84 tests, Ruff clean, compileall exit 0, version 1.2.0, diff and retirement scans clean, app.zip source parity retained, and artifact hashes remain 17633AE40C701EF23750D086B46E9A032F4D5DD30FB0C2F1A4A7F0272BAA7B02 / 7F2E10FE971F4CEE20F3CFCFEAE65E8E1FD0305969DD9CB6EC3E3624C1BC4116.
- Verifier: main-agent

## EvidenceBundleDraft

- Artifact key: complexity-and-acceptance-closure
- Type: audit
- Source: physical-line comparison against HEAD; owner scan; specification section 17 acceptance audit
- Summary: All 11 specification acceptance criteria have direct test/build/document evidence. Current maintained Python source/tests are 27 files and 6,630 lines versus 39 files and 9,549 lines at HEAD, a net reduction of 2,919 lines. Largest files are app.py 769 and codex_statsig_unlocker.py 768; no maintained file exceeds 800 or the project 2,000-line limit, and no filesystem logic entered app.py, transaction logic entered the Statsig owner, second LevelDB writer, or legacy reset fallback.
- Verifier: main-agent
