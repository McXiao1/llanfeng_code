from __future__ import annotations

import os
from pathlib import Path

from .constants import APP_NAME


def app_data_dir() -> Path:
    """Return the application data directory.

    @returns: `%APPDATA%/lanfeng_code` on Windows or a home fallback.
    """

    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME}"


def downloads_dir() -> Path:
    """Return the application-owned installer download directory.

    @returns: Local download path.
    """

    return app_data_dir() / "downloads"

def codex_restore_backups_dir() -> Path:
    """Return the application-owned Codex restore backup root.

    @returns: Backup root below the application data directory.
    """

    return app_data_dir() / "backups"
