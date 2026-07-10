from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class WriteResult:
    """Result of an atomic file write.

    @param path: Written path.
    @param backup_path: Backup path if a previous file existed.
    @returns: Write metadata.
    """

    path: Path
    backup_path: Path | None


def backup_file(path: Path) -> Path | None:
    """Back up a file if it exists.

    @param path: File to back up.
    @returns: Backup path, or `None` when no file existed.
    """

    if not path.exists():
        return None
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    backup_path = path.with_name(f"{path.name}.{timestamp}.bak")
    shutil.copy2(path, backup_path)
    return backup_path


def atomic_write_text(path: Path, content: str) -> WriteResult:
    """Atomically write UTF-8 text with a best-effort backup.

    @param path: Destination path.
    @param content: Text content.
    @returns: Write metadata.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = backup_file(path)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return WriteResult(path=path, backup_path=backup_path)


def restore_write(result: WriteResult) -> None:
    """Restore the destination state that preceded an atomic write.

    @param result: Successful write metadata containing the destination and optional backup.
    @returns: None.
    @throws OSError: If removing the new file or replacing it with its backup fails.
    """

    if result.backup_path is None:
        result.path.unlink(missing_ok=True)
        return
    os.replace(result.backup_path, result.path)
