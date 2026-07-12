# Product

## Register

product

## Users

Windows developers who want a small desktop utility for installing Codex and
Claude Code, discovering eligible bundled Codex models, safely restoring Codex
configuration, and launching Microsoft Store Codex Desktop with plugin marketplace
enhancements.

## Product Purpose

Llanfeng Code Assistant provides five focused actions: install or update Codex,
install or update Claude, persist eligible Codex model visibility in Statsig,
safely restore affected Codex configuration, and start Codex Desktop with a
verified CDP marketplace patch. It does not own provider profiles, API keys,
upstream endpoints, or a replacement settings system.

Success means each retained operation has one clear owner, reports partial and
failure states accurately, and leaves unrelated user data untouched.

## Core Product Contract

- Keep exactly five primary actions in the main UI.
- Preserve tool status, single-instance startup, and in-app software updates.
- Derive model candidates from `codex debug models --bundled` rather than a
  hard-coded catalog or user profile.
- Append only eligible missing model slugs, preserve `default_model`, and back
  up LevelDB only before a real write.
- Restore only `config.toml`, `models.json`, and exact Statsig evaluation /
  timestamp cache keys; back up first and preserve `auth.json` and unrelated data.
- Inject marketplace behavior only into a verified Codex `app://` page target.
- Require Codex to be closed before LevelDB mutation, safe restore, or enhanced launch.
- Never delete `auth.json`, sessions, history, skills, plugins, unrelated LevelDB keys,
  or legacy SQLite / credential-manager data.

## Brand Personality

Quiet, precise, compact, and dependable. The interface should make operation
state obvious without becoming decorative or dashboard-like.

## Anti-references

Avoid marketing-style composition, gradients, emoji icons, oversized
headlines, ornamental motion, ambiguous combined actions, hidden destructive
steps, and replacement settings systems.

## Design Principles

- Small is beautiful: show only the retained operations and their current state.
- Use project-level controls before raw third-party controls.
- Keep blocking work off the UI event loop and restore controls in `finally`.
- Distinguish process started, enhancement applied, no-op, partial success, and
  failure instead of collapsing them into a generic success message.
- Prefer canonical owners and delete retired internal paths rather than keeping
  fallback behavior.
- Preserve native keyboard behavior, readable contrast, text labels, and icon
  tooltips; never communicate state through color alone.
