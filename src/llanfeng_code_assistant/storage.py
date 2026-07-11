from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from .models import CodexModel, ProviderDraft, ProviderProfile, TargetName
from .secrets import SecretStore


class ProfileRepository:
    """SQLite-backed profile repository with secrets stored externally."""

    def __init__(self, db_path: Path, secret_store: SecretStore) -> None:
        self._db_path = db_path
        self._secret_store = secret_store
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Provide a transactional connection and always release it."""

        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    target TEXT NOT NULL,
                    name TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    model TEXT,
                    secret_ref TEXT NOT NULL,
                    haiku_model TEXT,
                    sonnet_model TEXT,
                    fable_model TEXT,
                    opus_model TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS profile_models (
                    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    model_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    context_window INTEGER NOT NULL DEFAULT 1000000
                        CHECK (context_window > 0),
                    position INTEGER NOT NULL CHECK (position >= 0),
                    PRIMARY KEY (profile_id, model_id),
                    UNIQUE (profile_id, position)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS active_profiles (
                    target TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_column(connection, "fable_model", "TEXT")

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        column_name: str,
        column_type: str,
    ) -> None:
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(profiles)").fetchall()
        }
        if column_name in columns:
            return
        connection.execute(f"ALTER TABLE profiles ADD COLUMN {column_name} {column_type}")

    def _replace_codex_models(
        self,
        connection: sqlite3.Connection,
        profile_id: str,
        models: Sequence[CodexModel],
    ) -> None:
        """Replace all Codex models for a profile in the caller's transaction."""

        connection.execute("DELETE FROM profile_models WHERE profile_id = ?", (profile_id,))
        connection.executemany(
            """
            INSERT INTO profile_models (
                profile_id, model_id, display_name, context_window, position
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    profile_id,
                    model.model_id,
                    model.display_name,
                    model.context_window,
                    model.position,
                )
                for model in models
            ],
        )

    def _load_codex_models(
        self,
        connection: sqlite3.Connection,
        profile_id: str,
    ) -> list[CodexModel]:
        """Load a profile's Codex models in stable display order."""

        rows = connection.execute(
            """
            SELECT model_id, display_name, context_window, position
            FROM profile_models
            WHERE profile_id = ?
            ORDER BY position ASC, model_id ASC
            """,
            (profile_id,),
        ).fetchall()
        return [
            CodexModel(
                model_id=row["model_id"],
                display_name=row["display_name"],
                context_window=row["context_window"],
                position=row["position"],
            )
            for row in rows
        ]

    def create_profile(self, draft: ProviderDraft) -> ProviderProfile:
        """Create and persist a provider profile.

        @param draft: User-entered profile data.
        @returns: Persisted profile without secret value.
        """

        profile_id = uuid.uuid4().hex
        secret_ref = f"{draft.target}:{profile_id}"
        profile = ProviderProfile(
            id=profile_id,
            target=draft.target,
            name=draft.name,
            base_url=draft.base_url,
            model=draft.model,
            codex_models=list(draft.codex_models),
            secret_ref=secret_ref,
            haiku_model=draft.haiku_model,
            sonnet_model=draft.sonnet_model,
            fable_model=draft.fable_model,
            opus_model=draft.opus_model,
        )
        self._secret_store.set_secret(secret_ref, draft.api_key)
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO profiles (
                    id, target, name, base_url, model, secret_ref,
                    haiku_model, sonnet_model, fable_model, opus_model
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.id,
                    profile.target,
                    profile.name,
                    profile.base_url,
                    profile.model,
                    profile.secret_ref,
                    profile.haiku_model,
                    profile.sonnet_model,
                    profile.fable_model,
                    profile.opus_model,
                ),
            )
            self._replace_codex_models(connection, profile.id, profile.codex_models)
        return profile

    def update_profile(self, profile: ProviderProfile, api_key: str | None = None) -> None:
        """Update profile metadata and optionally rotate its secret.

        @param profile: New profile metadata.
        @param api_key: Optional new API key.
        """

        if not profile.secret_ref:
            raise ValueError("profile.secret_ref is required")
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE profiles
                SET name = ?, base_url = ?, model = ?, haiku_model = ?,
                    sonnet_model = ?, fable_model = ?, opus_model = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    profile.name,
                    profile.base_url,
                    profile.model,
                    profile.haiku_model,
                    profile.sonnet_model,
                    profile.fable_model,
                    profile.opus_model,
                    profile.id,
                ),
            )
            self._replace_codex_models(connection, profile.id, profile.codex_models)
        if api_key:
            self._secret_store.set_secret(profile.secret_ref, api_key)

    def list_profiles(self, target: TargetName | None = None) -> list[ProviderProfile]:
        """List stored profiles.

        @param target: Optional target filter.
        @returns: Profiles sorted by creation time.
        """

        query = (
            "SELECT id, target, name, base_url, model, secret_ref, "
            "haiku_model, sonnet_model, fable_model, opus_model FROM profiles"
        )
        params: tuple[str, ...] = ()
        if target:
            query += " WHERE target = ?"
            params = (target,)
        query += " ORDER BY created_at ASC, name ASC"
        with self._connection() as connection:
            rows = connection.execute(query, params).fetchall()
            profiles = [
                ProviderProfile(
                    id=row["id"],
                    target=row["target"],
                    name=row["name"],
                    base_url=row["base_url"],
                    model=row["model"],
                    codex_models=self._load_codex_models(connection, row["id"]),
                    secret_ref=row["secret_ref"],
                    haiku_model=row["haiku_model"],
                    sonnet_model=row["sonnet_model"],
                    fable_model=row["fable_model"],
                    opus_model=row["opus_model"],
                )
                for row in rows
            ]
        return profiles

    def delete_profile(self, profile: ProviderProfile) -> None:
        """Delete a profile and its secret.

        @param profile: Profile to delete.
        """

        with self._connection() as connection:
            connection.execute("DELETE FROM profile_models WHERE profile_id = ?", (profile.id,))
            connection.execute("DELETE FROM active_profiles WHERE profile_id = ?", (profile.id,))
            connection.execute("DELETE FROM profiles WHERE id = ?", (profile.id,))
        if profile.secret_ref:
            self._secret_store.delete_secret(profile.secret_ref)

    def set_active_profile(self, profile: ProviderProfile) -> None:
        """Persist the profile currently enabled for its target.

        @param profile: Profile whose local configuration was applied.
        """

        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO active_profiles (target, profile_id, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(target) DO UPDATE SET
                    profile_id = excluded.profile_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (profile.target, profile.id),
            )

    def clear_active_profile(self, target: TargetName) -> None:
        """Remove the active-profile marker for a target.

        After a config reset the stored files are gone, so the active marker
        is no longer meaningful.  Clearing it makes the UI reflect the
        unactivated state correctly.

        @param target: Target whose active marker should be removed.
        """

        with self._connection() as connection:
            connection.execute("DELETE FROM active_profiles WHERE target = ?", (target,))

    def get_active_profile_id(self, target: TargetName) -> str | None:
        """Return the active profile id for a target.

        @param target: Target CLI application.
        @returns: Active profile id or `None`.
        """

        with self._connection() as connection:
            row = connection.execute(
                "SELECT profile_id FROM active_profiles WHERE target = ?",
                (target,),
            ).fetchone()
        return str(row["profile_id"]) if row else None

    def get_secret(self, profile: ProviderProfile) -> str | None:
        """Read a profile's secret value.

        @param profile: Profile metadata.
        @returns: API key or `None`.
        """

        if not profile.secret_ref:
            return None
        return self._secret_store.get_secret(profile.secret_ref)
