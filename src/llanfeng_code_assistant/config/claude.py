from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..file_ops import WriteResult, atomic_write_text
from ..models import ProviderProfile


@dataclass(frozen=True)
class ClaudeApplyResult:
    """Result of applying a Claude profile."""

    settings_write: WriteResult


class ClaudeConfigManager:
    """Write standard Claude Code `settings.json` configuration."""

    def __init__(self, settings_path: Path) -> None:
        self._settings_path = settings_path

    def _read_settings(self) -> dict[str, Any]:
        if not self._settings_path.exists():
            return {}
        try:
            loaded = json.loads(self._settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def apply_profile(self, profile: ProviderProfile, api_key: str) -> ClaudeApplyResult:
        """Apply a Claude profile to `settings.json`.

        @param profile: Claude provider profile.
        @param api_key: API key for the profile.
        @returns: Write result metadata.
        """

        if profile.target != "claude":
            raise ValueError("profile target must be claude")
        if not api_key.strip():
            raise ValueError("api_key is required")

        settings = self._read_settings()
        env_value = settings.get("env")
        env: dict[str, Any] = env_value if isinstance(env_value, dict) else {}
        env["ANTHROPIC_AUTH_TOKEN"] = api_key
        env["ANTHROPIC_BASE_URL"] = profile.base_url.rstrip("/")
        if profile.model:
            env["ANTHROPIC_MODEL"] = profile.model
        if profile.haiku_model:
            env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = profile.haiku_model
        if profile.sonnet_model:
            env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = profile.sonnet_model
        if profile.fable_model:
            env["ANTHROPIC_DEFAULT_FABLE_MODEL"] = profile.fable_model
        if profile.opus_model:
            env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = profile.opus_model
        settings["env"] = env

        result = atomic_write_text(
            self._settings_path,
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        )
        return ClaudeApplyResult(settings_write=result)
