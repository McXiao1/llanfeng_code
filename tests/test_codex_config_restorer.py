from __future__ import annotations

import json
from pathlib import Path

import pytest

import llanfeng_code_assistant.codex_config_restorer as restorer
from llanfeng_code_assistant.codex_statsig_unlocker import (
    LevelDbState,
    StatsigInvalidationResult,
)


def _evaluation_key() -> bytes:
    return b"_app://-\x00\x01statsig.cached.evaluations.restore"


def _timestamp_key() -> bytes:
    return b"_app://-\x00\x01statsig.last_modified_time.evaluations"


def _prepare_codex_home(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    models_path = codex_home / "models.json"
    auth_path = codex_home / "auth.json"
    config_path.write_text("model = 'custom'\n", encoding="utf-8")
    models_path.write_text('{"models":["custom"]}\n', encoding="utf-8")
    auth_path.write_bytes(b'{"token":"test-auth-data"}\n')
    return codex_home, config_path, models_path, auth_path


def _prepare_leveldb(tmp_path: Path) -> Path:
    leveldb_path = tmp_path / "leveldb"
    leveldb_path.mkdir()
    (leveldb_path / "CURRENT").write_text("MANIFEST-000001\n", encoding="utf-8")
    (leveldb_path / "000001.log").write_bytes(b"ORIGINAL_LEVELDB_BYTES")
    return leveldb_path


def _state() -> LevelDbState:
    return LevelDbState(
        max_sequence=8,
        live_entries={
            _evaluation_key(): b"SECRET_EVALUATION_VALUE",
            _timestamp_key(): b"SECRET_TIMESTAMP_VALUE",
            b"_app://-\x00\x01statsig.stable_id": b"stable",
        },
    )


def test_preview_reports_only_safe_config_files_and_approved_statsig_keys(
    monkeypatch,
    tmp_path,
) -> None:
    codex_home, config_path, models_path, auth_path = _prepare_codex_home(tmp_path)
    leveldb_path = _prepare_leveldb(tmp_path)
    auth_before = auth_path.read_bytes()
    monkeypatch.setattr(restorer, "find_codex_leveldb_path", lambda _: leveldb_path)
    monkeypatch.setattr(restorer, "read_leveldb_state", lambda _: _state())

    preview = restorer.preview_codex_restore(
        codex_home=codex_home,
        local_app_data=tmp_path,
    )

    assert preview.config_paths == (config_path, models_path, auth_path)
    assert preview.leveldb_path == leveldb_path
    assert preview.statsig_key_count == 2
    assert preview.has_targets is True
    assert auth_path.read_bytes() == auth_before  # preview 不修改文件


def test_preview_surfaces_unreadable_leveldb_without_touching_files(
    monkeypatch,
    tmp_path,
) -> None:
    codex_home, config_path, _, auth_path = _prepare_codex_home(tmp_path)
    leveldb_path = _prepare_leveldb(tmp_path)
    auth_before = auth_path.read_bytes()
    monkeypatch.setattr(restorer, "find_codex_leveldb_path", lambda _: leveldb_path)
    monkeypatch.setattr(
        restorer,
        "read_leveldb_state",
        lambda _: (_ for _ in ()).throw(OSError("LOCK held")),
    )

    preview = restorer.preview_codex_restore(
        codex_home=codex_home,
        local_app_data=tmp_path,
    )

    assert preview.config_paths[0] == config_path
    assert preview.statsig_key_count is None
    assert preview.has_targets is True
    assert any("LOCK held" in warning for warning in preview.warnings)
    assert auth_path.read_bytes() == auth_before


def test_restore_is_idempotent_without_targets_and_creates_no_backup(
    monkeypatch,
    tmp_path,
) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(restorer, "find_codex_leveldb_path", lambda _: None)

    result = restorer.restore_codex_configuration(
        codex_home=codex_home,
        local_app_data=tmp_path,
        backup_root=backup_root,
    )

    assert result.success is True
    assert result.backup_path is None
    assert result.removed_paths == ()
    assert result.invalidated_statsig_keys == 0
    assert not backup_root.exists()


def test_restore_backs_up_then_removes_safe_files_and_invalidates_statsig(
    monkeypatch,
    tmp_path,
) -> None:
    codex_home, config_path, models_path, auth_path = _prepare_codex_home(tmp_path)
    leveldb_path = _prepare_leveldb(tmp_path)
    backup_root = tmp_path / "backups"
    auth_before = auth_path.read_bytes()
    calls: list[str] = []
    monkeypatch.setattr(restorer, "find_codex_leveldb_path", lambda _: leveldb_path)
    monkeypatch.setattr(restorer, "read_leveldb_state", lambda _: _state())

    def invalidate(path: Path) -> StatsigInvalidationResult:
        assert path == leveldb_path
        assert not config_path.exists()
        assert not models_path.exists()
        calls.append("invalidate")
        return StatsigInvalidationResult(
            True,
            "cleared",
            invalidated_keys=2,
            write_attempted=True,
        )

    monkeypatch.setattr(restorer, "invalidate_statsig_cache", invalidate)

    result = restorer.restore_codex_configuration(
        codex_home=codex_home,
        local_app_data=tmp_path,
        backup_root=backup_root,
    )

    assert result.success is True
    assert calls == ["invalidate"]
    assert result.removed_paths == (config_path, models_path, auth_path)
    assert result.invalidated_statsig_keys == 2
    assert result.backup_path is not None
    assert (result.backup_path / "cli" / "config.toml").read_text(encoding="utf-8") == (
        "model = 'custom'\n"
    )
    assert (result.backup_path / "cli" / "models.json").is_file()
    assert (result.backup_path / "cli" / "auth.json").is_file()
    assert (result.backup_path / "desktop_leveldb" / "000001.log").read_bytes() == (
        b"ORIGINAL_LEVELDB_BYTES"
    )
    manifest_text = (result.backup_path / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    assert manifest["status"] == "completed"
    assert manifest["statsig_keys_planned"] == 2
    assert manifest["statsig_keys_invalidated"] == 2
    assert "SECRET_EVALUATION_VALUE" not in manifest_text
    assert not config_path.exists()
    assert not models_path.exists()
    assert not auth_path.exists()  # auth.json 已被完全清除


def test_restore_stops_before_mutation_when_backup_fails(
    monkeypatch,
    tmp_path,
) -> None:
    codex_home, config_path, models_path, auth_path = _prepare_codex_home(tmp_path)
    leveldb_path = _prepare_leveldb(tmp_path)
    auth_before = auth_path.read_bytes()
    monkeypatch.setattr(restorer, "find_codex_leveldb_path", lambda _: leveldb_path)
    monkeypatch.setattr(restorer, "read_leveldb_state", lambda _: _state())
    monkeypatch.setattr(
        restorer.shutil,
        "copytree",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("backup denied")),
    )
    monkeypatch.setattr(
        restorer,
        "invalidate_statsig_cache",
        lambda _: pytest.fail("backup failure must stop invalidation"),
    )

    result = restorer.restore_codex_configuration(
        codex_home=codex_home,
        local_app_data=tmp_path,
        backup_root=tmp_path / "backups",
    )

    assert result.success is False
    assert "backup denied" in result.message
    assert config_path.is_file()
    assert models_path.is_file()
    assert auth_path.read_bytes() == auth_before
    assert result.rollback_attempted is False


def test_restore_rolls_back_removed_cli_files_when_second_removal_fails(
    monkeypatch,
    tmp_path,
) -> None:
    codex_home, config_path, models_path, auth_path = _prepare_codex_home(tmp_path)
    auth_before = auth_path.read_bytes()
    monkeypatch.setattr(restorer, "find_codex_leveldb_path", lambda _: None)
    removed: list[Path] = []

    def remove(path: Path) -> None:
        if path == models_path:
            raise OSError("models busy")
        path.unlink()
        removed.append(path)

    monkeypatch.setattr(restorer, "_remove_config_file", remove)

    result = restorer.restore_codex_configuration(
        codex_home=codex_home,
        local_app_data=tmp_path,
        backup_root=tmp_path / "backups",
    )

    assert removed == [config_path]
    assert result.success is False
    assert result.rollback_attempted is True
    assert result.rollback_completed is True
    assert config_path.read_text(encoding="utf-8") == "model = 'custom'\n"
    assert models_path.is_file()
    assert auth_path.read_bytes() == auth_before


def test_restore_rolls_back_cli_files_and_leveldb_after_attempted_statsig_failure(
    monkeypatch,
    tmp_path,
) -> None:
    codex_home, config_path, models_path, auth_path = _prepare_codex_home(tmp_path)
    leveldb_path = _prepare_leveldb(tmp_path)
    auth_before = auth_path.read_bytes()
    monkeypatch.setattr(restorer, "find_codex_leveldb_path", lambda _: leveldb_path)
    monkeypatch.setattr(restorer, "read_leveldb_state", lambda _: _state())

    def fail_after_write(_: Path) -> StatsigInvalidationResult:
        (leveldb_path / "000001.log").write_bytes(b"CHANGED_LEVELDB_BYTES")
        return StatsigInvalidationResult(
            False,
            "append failed",
            write_attempted=True,
        )

    monkeypatch.setattr(restorer, "invalidate_statsig_cache", fail_after_write)

    result = restorer.restore_codex_configuration(
        codex_home=codex_home,
        local_app_data=tmp_path,
        backup_root=tmp_path / "backups",
    )

    assert result.success is False
    assert result.rollback_attempted is True
    assert result.rollback_completed is True
    assert config_path.is_file()
    assert models_path.is_file()
    assert (leveldb_path / "000001.log").read_bytes() == b"ORIGINAL_LEVELDB_BYTES"
    assert auth_path.read_bytes() == auth_before


def test_restore_reports_partial_rollback_with_backup_path(
    monkeypatch,
    tmp_path,
) -> None:
    codex_home, _, _, auth_path = _prepare_codex_home(tmp_path)
    leveldb_path = _prepare_leveldb(tmp_path)
    auth_before = auth_path.read_bytes()
    monkeypatch.setattr(restorer, "find_codex_leveldb_path", lambda _: leveldb_path)
    monkeypatch.setattr(restorer, "read_leveldb_state", lambda _: _state())
    monkeypatch.setattr(
        restorer,
        "invalidate_statsig_cache",
        lambda _: StatsigInvalidationResult(
            False,
            "append failed",
            write_attempted=True,
        ),
    )
    monkeypatch.setattr(
        restorer,
        "_restore_leveldb_directory",
        lambda *_: (_ for _ in ()).throw(OSError("rollback denied")),
    )

    result = restorer.restore_codex_configuration(
        codex_home=codex_home,
        local_app_data=tmp_path,
        backup_root=tmp_path / "backups",
    )

    assert result.success is False
    assert result.rollback_attempted is True
    assert result.rollback_completed is False
    assert result.backup_path is not None
    assert "rollback denied" in " ".join(result.warnings)
    assert auth_path.read_bytes() == auth_before


def test_restore_refuses_unreadable_existing_leveldb_before_backup(
    monkeypatch,
    tmp_path,
) -> None:
    codex_home, config_path, _, auth_path = _prepare_codex_home(tmp_path)
    leveldb_path = _prepare_leveldb(tmp_path)
    auth_before = auth_path.read_bytes()
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(restorer, "find_codex_leveldb_path", lambda _: leveldb_path)
    monkeypatch.setattr(
        restorer,
        "read_leveldb_state",
        lambda _: (_ for _ in ()).throw(OSError("LOCK held")),
    )

    result = restorer.restore_codex_configuration(
        codex_home=codex_home,
        local_app_data=tmp_path,
        backup_root=backup_root,
    )

    assert result.success is False
    assert "LOCK held" in result.message
    assert config_path.is_file()
    assert auth_path.read_bytes() == auth_before
    assert not backup_root.exists()


def test_allocate_backup_directory_never_overwrites_existing_timestamp(
    monkeypatch,
    tmp_path,
) -> None:
    backup_root = tmp_path / "backups"
    first = backup_root / "codex_restore_20260712_010203"
    first.mkdir(parents=True)
    marker = first / "marker.txt"
    marker.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(restorer.time, "strftime", lambda _: "20260712_010203")

    allocated = restorer._allocate_backup_directory(backup_root)

    assert allocated.name == "codex_restore_20260712_010203_1"
    assert marker.read_text(encoding="utf-8") == "keep"
