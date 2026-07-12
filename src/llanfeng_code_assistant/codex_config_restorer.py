"""Safely restore Codex configuration with mandatory backup and rollback."""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from .codex_statsig_unlocker import (
    StatsigInvalidationResult,
    find_codex_leveldb_path,
    invalidate_statsig_cache,
    plan_statsig_cache_invalidation,
    read_leveldb_state,
)
from .paths import codex_restore_backups_dir

_CONFIG_FILENAMES = ("config.toml", "models.json", "auth.json")
_MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CodexRestorePreview:
    """Read-only preview of safe Codex restore targets.

    @param config_paths: Existing approved CLI configuration files.
    @param leveldb_path: Located Codex Desktop LevelDB directory.
    @param statsig_key_count: Exact live keys to invalidate, or ``None`` when unreadable.
    @param warnings: Non-fatal discovery details.
    """

    config_paths: tuple[Path, ...]
    leveldb_path: Path | None
    statsig_key_count: int | None
    warnings: tuple[str, ...] = ()

    @property
    def has_targets(self) -> bool:
        """Whether at least one approved restore target may require mutation.

        @returns: ``True`` for existing CLI files or a non-empty/unknown LevelDB target.
        """

        if self.config_paths:
            return True
        if self.leveldb_path is None:
            return False
        return self.statsig_key_count is None or self.statsig_key_count > 0


@dataclass(frozen=True)
class CodexRestoreResult:
    """Result of the safe Codex configuration restore transaction.

    @param success: Whether the requested restore completed.
    @param message: User-facing result or recovery guidance.
    @param backup_path: Created backup directory, if any.
    @param removed_paths: CLI configuration files removed on success.
    @param invalidated_statsig_keys: Statsig deletion records appended on success.
    @param rollback_attempted: Whether rollback ran after mutation began.
    @param rollback_completed: Whether every required rollback step succeeded.
    @param warnings: Non-fatal details or partial rollback errors.
    """

    success: bool
    message: str
    backup_path: Path | None = None
    removed_paths: tuple[Path, ...] = ()
    invalidated_statsig_keys: int = 0
    rollback_attempted: bool = False
    rollback_completed: bool = False
    warnings: tuple[str, ...] = ()


def _resolve_codex_home(codex_home: Path | None) -> Path:
    return codex_home if codex_home is not None else Path.home() / ".codex"


def preview_codex_restore(
    *,
    codex_home: Path | None = None,
    local_app_data: Path | None = None,
) -> CodexRestorePreview:
    """Discover exact safe restore targets without writing or backing up data.

    @param codex_home: Optional explicit ``.codex`` directory.
    @param local_app_data: Optional Local AppData root for LevelDB discovery.
    @returns: Typed read-only preview.
    """

    resolved_home = _resolve_codex_home(codex_home)
    config_paths = tuple(
        path
        for filename in _CONFIG_FILENAMES
        if (path := resolved_home / filename).is_file()
    )
    leveldb_path = find_codex_leveldb_path(local_app_data)
    if leveldb_path is None:
        return CodexRestorePreview(config_paths, None, 0)

    try:
        state = read_leveldb_state(leveldb_path)
    except Exception as exc:
        return CodexRestorePreview(
            config_paths,
            leveldb_path,
            None,
            (f"无法读取 Codex Statsig 缓存: {exc}",),
        )

    plan = plan_statsig_cache_invalidation(state)
    return CodexRestorePreview(
        config_paths,
        leveldb_path,
        len(plan.keys),
    )


def _allocate_backup_directory(backup_root: Path) -> Path:
    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    candidate = backup_root / f"codex_restore_{timestamp}"
    suffix = 1
    while candidate.exists():
        candidate = backup_root / f"codex_restore_{timestamp}_{suffix}"
        suffix += 1
    candidate.mkdir()
    return candidate


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _initial_manifest(
    preview: CodexRestorePreview,
    backup_path: Path,
) -> dict[str, object]:
    config_entries = [
        {
            "source": str(source),
            "backup": str(Path("cli") / source.name),
        }
        for source in preview.config_paths
    ]
    return {
        "schema_version": _MANIFEST_SCHEMA_VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "prepared",
        "backup_path": str(backup_path),
        "config_files": config_entries,
        "leveldb_path": str(preview.leveldb_path) if preview.leveldb_path else None,
        "statsig_keys_planned": preview.statsig_key_count or 0,
        "statsig_keys_invalidated": 0,
        "preserved_targets": [
            "sessions",
            "history",
            "skills",
            "plugins",
            "unrelated_leveldb_keys",
        ],
    }


def _backup_targets(preview: CodexRestorePreview, backup_path: Path) -> Path | None:
    if preview.config_paths:
        cli_backup = backup_path / "cli"
        cli_backup.mkdir()
        for source in preview.config_paths:
            shutil.copy2(source, cli_backup / source.name)

    if not preview.leveldb_path or not preview.statsig_key_count:
        return None
    leveldb_backup = backup_path / "desktop_leveldb"
    shutil.copytree(preview.leveldb_path, leveldb_backup)
    return leveldb_backup


def _remove_config_file(path: Path) -> None:
    path.unlink()


def _unique_sibling(path: Path, suffix: str) -> Path:
    candidate = path.with_name(f".{path.name}.{suffix}")
    number = 1
    while candidate.exists():
        candidate = path.with_name(f".{path.name}.{suffix}_{number}")
        number += 1
    return candidate


def _restore_leveldb_directory(backup_path: Path, live_path: Path) -> None:
    quarantine = _unique_sibling(live_path, "restore_rollback")
    moved_live = False
    if live_path.exists():
        live_path.rename(quarantine)
        moved_live = True
    try:
        shutil.copytree(backup_path, live_path)
    except Exception:
        if live_path.exists():
            shutil.rmtree(live_path)
        if moved_live and quarantine.exists():
            quarantine.rename(live_path)
        raise
    if moved_live and quarantine.exists():
        shutil.rmtree(quarantine)


def _rollback(
    removed_paths: tuple[Path, ...],
    backup_path: Path,
    *,
    restore_leveldb: bool,
    leveldb_path: Path | None,
    leveldb_backup: Path | None,
) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    for original in removed_paths:
        source = backup_path / "cli" / original.name
        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, original)
        except OSError as exc:
            errors.append(f"恢复 {original.name} 失败: {exc}")

    if restore_leveldb and leveldb_path is not None and leveldb_backup is not None:
        try:
            _restore_leveldb_directory(leveldb_backup, leveldb_path)
        except OSError as exc:
            errors.append(f"恢复 Codex LevelDB 失败: {exc}")
    return not errors, tuple(errors)


def _finalize_manifest(
    manifest_path: Path,
    manifest: dict[str, object],
    *,
    status: str,
    invalidated_keys: int,
    rollback_completed: bool | None = None,
) -> str | None:
    manifest["status"] = status
    manifest["statsig_keys_invalidated"] = invalidated_keys
    if rollback_completed is not None:
        manifest["rollback_completed"] = rollback_completed
    try:
        _write_manifest(manifest_path, manifest)
    except OSError as exc:
        return f"更新恢复清单失败: {exc}"
    return None


def restore_codex_configuration(
    *,
    codex_home: Path | None = None,
    local_app_data: Path | None = None,
    backup_root: Path | None = None,
) -> CodexRestoreResult:
    """Back up and restore approved Codex configuration targets transactionally.

    @param codex_home: Optional explicit ``.codex`` directory.
    @param local_app_data: Optional Local AppData root for LevelDB discovery.
    @param backup_root: Optional explicit application backup root.
    @returns: Typed restore result with rollback and backup evidence.
    """

    resolved_home = _resolve_codex_home(codex_home)
    preview = preview_codex_restore(
        codex_home=resolved_home,
        local_app_data=local_app_data,
    )
    if preview.leveldb_path is not None and preview.statsig_key_count is None:
        detail = "; ".join(preview.warnings) or "Codex LevelDB 无法读取"
        return CodexRestoreResult(False, detail, warnings=preview.warnings)
    if not preview.has_targets:
        return CodexRestoreResult(True, "Codex 配置已是默认状态, 无需恢复")

    resolved_backup_root = backup_root or codex_restore_backups_dir()
    backup_path: Path | None = None
    leveldb_backup: Path | None = None
    manifest: dict[str, object] = {}
    manifest_path: Path | None = None
    try:
        backup_path = _allocate_backup_directory(resolved_backup_root)
        leveldb_backup = _backup_targets(preview, backup_path)
        manifest = _initial_manifest(preview, backup_path)
        manifest_path = backup_path / "manifest.json"
        _write_manifest(manifest_path, manifest)
    except Exception as exc:
        return CodexRestoreResult(
            False,
            f"创建 Codex 恢复备份失败: {exc}",
            backup_path=backup_path,
            warnings=preview.warnings,
        )

    removed: list[Path] = []
    try:
        for config_path in preview.config_paths:
            _remove_config_file(config_path)
            removed.append(config_path)
    except OSError as exc:
        rollback_attempted = bool(removed)
        rollback_completed = True
        rollback_warnings: tuple[str, ...] = ()
        if rollback_attempted:
            rollback_completed, rollback_warnings = _rollback(
                tuple(removed),
                backup_path,
                restore_leveldb=False,
                leveldb_path=None,
                leveldb_backup=None,
            )
        manifest_warning = _finalize_manifest(
            manifest_path,
            manifest,
            status="rolled_back" if rollback_completed else "rollback_incomplete",
            invalidated_keys=0,
            rollback_completed=rollback_completed,
        )
        warnings = [*preview.warnings, *rollback_warnings]
        if manifest_warning:
            warnings.append(manifest_warning)
        return CodexRestoreResult(
            False,
            f"删除 Codex 配置失败: {exc}",
            backup_path=backup_path,
            rollback_attempted=rollback_attempted,
            rollback_completed=rollback_completed,
            warnings=tuple(warnings),
        )

    invalidation = StatsigInvalidationResult(True, "无需清除 Statsig 缓存")
    if preview.leveldb_path is not None and preview.statsig_key_count:
        try:
            invalidation = invalidate_statsig_cache(preview.leveldb_path)
        except Exception as exc:
            invalidation = StatsigInvalidationResult(
                False,
                f"清除 Statsig 模型缓存失败: {exc}",
                write_attempted=True,
            )

    if not invalidation.success:
        rollback_completed, rollback_warnings = _rollback(
            tuple(removed),
            backup_path,
            restore_leveldb=invalidation.write_attempted,
            leveldb_path=preview.leveldb_path,
            leveldb_backup=leveldb_backup,
        )
        manifest_warning = _finalize_manifest(
            manifest_path,
            manifest,
            status="rolled_back" if rollback_completed else "rollback_incomplete",
            invalidated_keys=0,
            rollback_completed=rollback_completed,
        )
        warnings = [*preview.warnings, *rollback_warnings]
        if manifest_warning:
            warnings.append(manifest_warning)
        rollback_note = "已完成回滚" if rollback_completed else "回滚不完整, 请使用备份手动恢复"
        return CodexRestoreResult(
            False,
            f"{invalidation.message}; {rollback_note}",
            backup_path=backup_path,
            rollback_attempted=True,
            rollback_completed=rollback_completed,
            warnings=tuple(warnings),
        )

    warnings = list(preview.warnings)
    manifest_warning = _finalize_manifest(
        manifest_path,
        manifest,
        status="completed",
        invalidated_keys=invalidation.invalidated_keys,
    )
    if manifest_warning:
        warnings.append(manifest_warning)
    return CodexRestoreResult(
        True,
        "Codex 配置已完全恢复至默认状态, 登录信息已清除",
        backup_path=backup_path,
        removed_paths=tuple(removed),
        invalidated_statsig_keys=invalidation.invalidated_keys,
        warnings=tuple(warnings),
    )
