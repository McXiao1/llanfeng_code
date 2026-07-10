from __future__ import annotations

import os
from pathlib import Path

from .constants import APP_NAME


def app_data_dir() -> Path:
    """Return the application data directory.

    @returns: `%APPDATA%/LlanfengCodeAssistant` on Windows or a home fallback.
    """

    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME}"


def downloads_dir() -> Path:
    """Return the local installer download directory.

    @returns: Application-owned downloads path.
    """

    return app_data_dir() / "downloads"


def codex_config_dir() -> Path:
    """Return the standard Codex config directory.

    @returns: `~/.codex`.
    """

    return Path.home() / ".codex"


def claude_settings_path() -> Path:
    """Return the standard Claude Code settings file path.

    @returns: `~/.claude/settings.json`.
    """

    return Path.home() / ".claude" / "settings.json"


def database_path() -> Path:
    """Return the profile SQLite database path.

    @returns: App-owned SQLite path.
    """

    return app_data_dir() / "profiles.sqlite"
