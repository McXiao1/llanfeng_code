from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pytest

from llanfeng_code_assistant.installer import InstallTarget, build_npm_install_command
from llanfeng_code_assistant.models import CodexModel, ProviderDraft
from llanfeng_code_assistant.secrets import MemorySecretStore
from llanfeng_code_assistant.storage import ProfileRepository


def _codex_draft(
    *,
    name: str = "Relay",
    codex_models: Sequence[CodexModel] = (),
) -> ProviderDraft:
    return ProviderDraft(
        target="codex",
        name=name,
        base_url="https://api.example.com/v1",
        api_key="sk-secret",
        model="gpt-5-codex",
        codex_models=list(codex_models),
    )


def test_profile_repository_closes_connection_after_operation(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "profiles.sqlite"
    repo = ProfileRepository(database_path, MemorySecretStore())

    class CloseTrackingConnection(sqlite3.Connection):
        close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            super().close()

    connection = sqlite3.connect(database_path, factory=CloseTrackingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(repo, "_connect", lambda: connection)

    try:
        repo.list_profiles()

        assert connection.close_calls == 1
    finally:
        if connection.close_calls == 0:
            connection.close()


def test_profile_repository_initializes_model_schema_and_constraints_idempotently(
    tmp_path,
) -> None:
    database_path = tmp_path / "profiles.sqlite"
    repo = ProfileRepository(database_path, MemorySecretStore())
    ProfileRepository(database_path, MemorySecretStore())
    profile = repo.create_profile(_codex_draft())

    with repo._connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "profile_models" in tables

        columns = connection.execute("PRAGMA table_info(profile_models)").fetchall()
        assert [
            (
                row["name"],
                row["type"],
                row["notnull"],
                row["dflt_value"],
                row["pk"],
            )
            for row in columns
        ] == [
            ("profile_id", "TEXT", 1, None, 1),
            ("model_id", "TEXT", 1, None, 2),
            ("display_name", "TEXT", 1, None, 0),
            ("context_window", "INTEGER", 1, "1000000", 0),
            ("position", "INTEGER", 1, None, 0),
        ]

        foreign_keys = connection.execute("PRAGMA foreign_key_list(profile_models)").fetchall()
        assert [
            (row["table"], row["from"], row["to"], row["on_delete"])
            for row in foreign_keys
        ] == [("profiles", "profile_id", "id", "CASCADE")]

        connection.execute(
            """
            INSERT INTO profile_models (profile_id, model_id, display_name, position)
            VALUES (?, ?, ?, ?)
            """,
            (profile.id, "gpt-default", "Default", 0),
        )
        stored_default = connection.execute(
            """
            SELECT context_window FROM profile_models
            WHERE profile_id = ? AND model_id = ?
            """,
            (profile.id, "gpt-default"),
        ).fetchone()
        assert stored_default["context_window"] == 1_000_000

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO profile_models (
                    profile_id, model_id, display_name, context_window, position
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (profile.id, "gpt-invalid-context", "Invalid", 0, 1),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO profile_models (
                    profile_id, model_id, display_name, context_window, position
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (profile.id, "gpt-invalid-position", "Invalid", 1, -1),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO profile_models (
                    profile_id, model_id, display_name, context_window, position
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (profile.id, "gpt-duplicate-position", "Duplicate", 1, 0),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO profile_models (
                    profile_id, model_id, display_name, context_window, position
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                ("missing-profile", "gpt-orphan", "Orphan", 1, 0),
            )


def test_profile_repository_round_trips_codex_models_in_position_order(tmp_path) -> None:
    repo = ProfileRepository(tmp_path / "profiles.sqlite", MemorySecretStore())
    models = [
        CodexModel(
            model_id="gpt-last",
            display_name="Last",
            context_window=300_000,
            position=2,
        ),
        CodexModel(
            model_id="gpt-first",
            display_name="First",
            context_window=100_000,
            position=0,
        ),
        CodexModel(
            model_id="gpt-middle",
            display_name="Middle",
            context_window=200_000,
            position=1,
        ),
    ]

    draft = _codex_draft(codex_models=models)
    profile = repo.create_profile(draft)
    listed = repo.list_profiles("codex")

    assert profile.codex_models == models
    assert profile.codex_models is not draft.codex_models
    assert listed[0].codex_models == [models[1], models[2], models[0]]


def test_profile_repository_update_replaces_codex_models_and_name(tmp_path) -> None:
    repo = ProfileRepository(tmp_path / "profiles.sqlite", MemorySecretStore())
    original_models = [
        CodexModel(model_id="gpt-old-a", display_name="Old A", position=0),
        CodexModel(model_id="gpt-old-b", display_name="Old B", position=1),
    ]
    profile = repo.create_profile(_codex_draft(codex_models=original_models))
    replacement_models = [
        CodexModel(model_id="gpt-new-b", display_name="New B", position=1),
        CodexModel(model_id="gpt-new-a", display_name="New A", position=0),
    ]
    updated = profile.model_copy(
        update={"name": "Renamed Relay", "codex_models": replacement_models}
    )

    repo.update_profile(updated)

    listed = repo.list_profiles("codex")
    assert listed[0].name == "Renamed Relay"
    assert listed[0].codex_models == [replacement_models[1], replacement_models[0]]
    with repo._connect() as connection:
        stored_ids = {
            str(row["model_id"])
            for row in connection.execute(
                "SELECT model_id FROM profile_models WHERE profile_id = ?",
                (profile.id,),
            ).fetchall()
        }
    assert stored_ids == {"gpt-new-a", "gpt-new-b"}


def test_profile_repository_rolls_back_profile_and_model_update_together(
    tmp_path,
    monkeypatch,
) -> None:
    repo = ProfileRepository(tmp_path / "profiles.sqlite", MemorySecretStore())
    original_models = [
        CodexModel(model_id="gpt-old-a", display_name="Old A", position=0),
        CodexModel(model_id="gpt-old-b", display_name="Old B", position=1),
    ]
    profile = repo.create_profile(_codex_draft(codex_models=original_models))
    updated = profile.model_copy(
        update={
            "name": "Name That Must Roll Back",
            "codex_models": [
                CodexModel(model_id="gpt-new", display_name="New", position=0)
            ],
        }
    )

    def fail_after_delete(
        connection: sqlite3.Connection,
        profile_id: str,
        _models: Sequence[CodexModel],
    ) -> None:
        connection.execute("DELETE FROM profile_models WHERE profile_id = ?", (profile_id,))
        raise sqlite3.IntegrityError("forced model replacement failure")

    monkeypatch.setattr(repo, "_replace_codex_models", fail_after_delete, raising=False)

    with pytest.raises(sqlite3.IntegrityError, match="forced model replacement failure"):
        repo.update_profile(updated)

    stored = repo.list_profiles("codex")[0]
    assert stored.name == "Relay"
    assert stored.codex_models == original_models


def test_profile_repository_delete_removes_model_rows(tmp_path) -> None:
    repo = ProfileRepository(tmp_path / "profiles.sqlite", MemorySecretStore())
    profile = repo.create_profile(
        _codex_draft(
            codex_models=[
                CodexModel(model_id="gpt-delete", display_name="Delete", position=0)
            ]
        )
    )
    repo.set_active_profile(profile)

    repo.delete_profile(profile)

    with repo._connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM profile_models WHERE profile_id = ?",
            (profile.id,),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM active_profiles WHERE profile_id = ?",
            (profile.id,),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM profiles WHERE id = ?",
            (profile.id,),
        ).fetchone()[0] == 0


def test_profile_repository_stores_metadata_in_sqlite_and_secret_in_secret_store(tmp_path) -> None:
    secret_store = MemorySecretStore()
    repo = ProfileRepository(tmp_path / "profiles.sqlite", secret_store)
    draft = ProviderDraft(
        target="codex",
        name="Relay",
        base_url="https://api.example.com/v1",
        api_key="sk-secret",
        model="gpt-5-codex",
    )

    profile = repo.create_profile(draft)
    listed = repo.list_profiles("codex")

    assert listed == [profile]
    assert secret_store.get_secret(profile.secret_ref) == "sk-secret"
    assert b"sk-secret" not in (tmp_path / "profiles.sqlite").read_bytes()
    assert repo.get_secret(profile) == "sk-secret"


def test_profile_repository_stores_claude_fable_model(tmp_path) -> None:
    secret_store = MemorySecretStore()
    repo = ProfileRepository(tmp_path / "profiles.sqlite", secret_store)
    draft = ProviderDraft(
        target="claude",
        name="Claude Relay",
        base_url="https://claude.example.com",
        api_key="sk-ant",
        model="claude-sonnet",
        haiku_model="claude-haiku",
        sonnet_model="claude-sonnet",
        fable_model="claude-fable",
        opus_model="claude-opus",
    )

    profile = repo.create_profile(draft)
    listed = repo.list_profiles("claude")

    assert profile.fable_model == "claude-fable"
    assert profile.codex_models == []
    assert listed[0].fable_model == "claude-fable"
    assert listed[0].codex_models == []


def test_profile_repository_tracks_active_profile_per_target(tmp_path) -> None:
    secret_store = MemorySecretStore()
    repo = ProfileRepository(tmp_path / "profiles.sqlite", secret_store)
    codex_profile = repo.create_profile(
        ProviderDraft(
            target="codex",
            name="Codex Relay",
            base_url="https://codex.example.com",
            api_key="sk-codex",
            model="gpt-5-codex",
        )
    )
    claude_profile = repo.create_profile(
        ProviderDraft(
            target="claude",
            name="Claude Relay",
            base_url="https://claude.example.com",
            api_key="sk-claude",
            model="claude-sonnet",
        )
    )

    repo.set_active_profile(codex_profile)
    repo.set_active_profile(claude_profile)

    assert repo.get_active_profile_id("codex") == codex_profile.id
    assert repo.get_active_profile_id("claude") == claude_profile.id

    repo.delete_profile(codex_profile)

    assert repo.get_active_profile_id("codex") is None
    assert repo.get_active_profile_id("claude") == claude_profile.id


def test_build_npm_install_command_pins_expected_cli_packages() -> None:
    assert build_npm_install_command(InstallTarget.CODEX) == [
        "npm",
        "install",
        "-g",
        "@openai/codex@0.144.1",
    ]
    assert build_npm_install_command(InstallTarget.CLAUDE) == [
        "npm",
        "install",
        "-g",
        "@anthropic-ai/claude-code@2.1.201",
    ]


def test_resolve_cli_command_prefers_codex_plus_plus_on_windows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from llanfeng_code_assistant.installer import InstallerService, InstallTarget

    launcher = tmp_path / "codex-plus-plus.exe"
    launcher.write_text("", encoding="utf-8")
    monkeypatch.setattr("llanfeng_code_assistant.installer.os.name", "nt")
    monkeypatch.setattr("llanfeng_code_assistant.installer.CODEX_PLUS_PLUS_WINDOWS_PATH", launcher)

    assert InstallerService().resolve_cli_command(InstallTarget.CODEX.value) == [str(launcher)]


def test_resolve_cli_command_falls_back_to_original_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from llanfeng_code_assistant.installer import InstallerService

    monkeypatch.setattr("llanfeng_code_assistant.installer.os.name", "nt")
    monkeypatch.setattr(
        "llanfeng_code_assistant.installer.CODEX_PLUS_PLUS_WINDOWS_PATH",
        Path(r"C:/missing/codex-plus-plus.exe"),
    )

    assert InstallerService().resolve_cli_command("codex") == ["codex"]
