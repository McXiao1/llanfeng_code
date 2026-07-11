"""Codex Statsig configuration unlocker via LevelDB modification.

Pure-Python implementation — no native extensions, no C++ compiler required.

Reading is handled by the ``chromium-reader`` package (a pure-Python
re-implementation of Chromium's LevelDB / localStorage format).  Writing uses
a hand-rolled LevelDB log-append: a WriteBatch record is appended to the
active ``.log`` file with a correctly masked CRC32C checksum, which is all
LevelDB needs to pick up new/updated key-value pairs on the next open.

Key advantages over CDP injection:
- One-time modification, permanent effect.
- No need for CDP injection on every launch.
- Codex reads the modified configuration naturally.
- Survives application restarts.

Technical details:
- Target: LevelDB under %LOCALAPPDATA%\\Packages\\OpenAI.Codex_*\\…\\leveldb\\
- Key pattern (raw bytes): b"_app://-\\x00\\x01statsig.cached.evaluations.{hash}"
- Value format: 0x00 byte + UTF-16LE encoded JSON
- Statsig config ID: dynamic_configs["107580212"].value
"""
from __future__ import annotations

import json
import shutil
import struct
import subprocess
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Pure-Python CRC32C (Castagnoli, polynomial 0x82F63B78)
# Used in LevelDB log-record headers.
# ---------------------------------------------------------------------------

_CRC32C_TABLE: list[int] = []
for _i in range(256):
    _v = _i
    for _ in range(8):
        _v = (_v >> 1) ^ (0x82F63B78 if _v & 1 else 0)
    _CRC32C_TABLE.append(_v)


def _crc32c(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for b in data:
        crc = (crc >> 8) ^ _CRC32C_TABLE[(crc ^ b) & 0xFF]
    return crc ^ 0xFFFFFFFF


def _masked_crc32c(data: bytes) -> int:
    """LevelDB masked CRC32C: rotate-right 15 + constant offset."""
    crc = _crc32c(data)
    return (((crc >> 15) | (crc << 17)) + 0xA282EAD8) & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# WriteBatch / log-record helpers
# ---------------------------------------------------------------------------

_BLOCK_SIZE = 32768   # LevelDB log block size
_HEADER_SIZE = 7      # 4-byte CRC + 2-byte length + 1-byte type
_TYPE_FULL   = 1      # RecordType::kFullType
_TYPE_FIRST  = 2      # RecordType::kFirstType
_TYPE_MIDDLE = 3      # RecordType::kMiddleType
_TYPE_LAST   = 4      # RecordType::kLastType
_TYPE_VALUE  = b"\x01"  # WriteBatch kTypeValue


def _varint(n: int) -> bytes:
    """Encode *n* as a little-endian base-128 varint."""
    parts: list[int] = []
    while n >= 0x80:
        parts.append((n & 0x7F) | 0x80)
        n >>= 7
    parts.append(n)
    return bytes(parts)


def _make_writebatch(seq: int, puts: list[tuple[bytes, bytes]]) -> bytes:
    """Build a LevelDB WriteBatch payload.

    @param seq: First sequence number to assign to the batch.
    @param puts: List of (raw_key, raw_value) pairs to PUT.
    @returns: WriteBatch bytes (header + records).
    """
    payload = struct.pack("<QI", seq, len(puts))
    for key, value in puts:
        payload += _TYPE_VALUE + _varint(len(key)) + key + _varint(len(value)) + value
    return payload


def _make_fragment(data_slice: bytes, record_type: int) -> bytes:
    """Wrap one fragment in a LevelDB log record header with masked CRC32C.

    @param data_slice: Fragment data bytes.
    @param record_type: One of _TYPE_FULL / _TYPE_FIRST / _TYPE_MIDDLE / _TYPE_LAST.
    @returns: 7-byte header + data_slice.
    """
    crc = _masked_crc32c(bytes([record_type]) + data_slice)
    return struct.pack("<IHB", crc, len(data_slice), record_type) + data_slice


def _append_to_log(log_path: Path, writebatch: bytes) -> None:
    """Append a WriteBatch to a LevelDB .log file with multi-block fragmentation.

    Large WriteBatches (e.g. Statsig evaluation JSON ~3 MB) are automatically
    split across 32 KiB blocks using FIRST / MIDDLE / LAST record types, which
    is what LevelDB's log reader expects when a logical record spans blocks.

    @param log_path: Path to the active ``.log`` file (created if absent).
    @param writebatch: Raw WriteBatch bytes to append (any size).
    """
    log_path.touch()
    block_offset = log_path.stat().st_size % _BLOCK_SIZE
    remaining_data = writebatch
    is_first = True

    with log_path.open("ab") as fh:
        while remaining_data:
            remaining_in_block = _BLOCK_SIZE - block_offset

            # Pad to next block when there is no room for even a header.
            if remaining_in_block < _HEADER_SIZE:
                fh.write(b"\x00" * remaining_in_block)
                block_offset = 0
                remaining_in_block = _BLOCK_SIZE

            available = remaining_in_block - _HEADER_SIZE  # data capacity

            if len(remaining_data) <= available:
                # Final (or only) fragment.
                rtype = _TYPE_FULL if is_first else _TYPE_LAST
                fh.write(_make_fragment(remaining_data, rtype))
                break

            # More data than fits in this block: write a partial fragment.
            chunk, remaining_data = remaining_data[:available], remaining_data[available:]
            rtype = _TYPE_FIRST if is_first else _TYPE_MIDDLE
            fh.write(_make_fragment(chunk, rtype))
            block_offset = 0   # next iteration starts at a fresh block
            is_first = False


# ---------------------------------------------------------------------------
# LevelDB directory helpers
# ---------------------------------------------------------------------------

def find_codex_leveldb_path() -> Path | None:
    """Locate the Codex LevelDB localStorage directory.

    @returns: Path to the LevelDB directory, or None if not found.
    """
    localappdata = Path.home() / "AppData" / "Local"
    packages_dir = localappdata / "Packages"

    if not packages_dir.exists():
        return None

    codex_dirs = list(packages_dir.glob("OpenAI.Codex_*"))
    if not codex_dirs:
        return None

    leveldb_path = (
        codex_dirs[0]
        / "LocalCache"
        / "Roaming"
        / "Codex"
        / "web"
        / "Codex"
        / "Default"
        / "Local Storage"
        / "leveldb"
    )
    return leveldb_path if leveldb_path.exists() else None


def _active_log_path(db_path: Path) -> Path:
    """Return the active (highest-numbered) .log file in *db_path*.

    LevelDB log files are named with 6 hex digits, e.g. ``000001.log``.
    If none exists, returns a default ``000001.log`` path (not yet created).

    @param db_path: LevelDB directory.
    @returns: Path to the active log file.
    """
    logs = sorted(db_path.glob("*.log"), key=lambda p: int(p.stem, 16))
    return logs[-1] if logs else db_path / "000001.log"


# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------

def is_codex_running() -> bool:
    """Check whether ChatGPT.exe / Codex.exe is currently running.

    @returns: True if a Codex process is detected.
    """
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Process -Name ChatGPT,Codex -ErrorAction SilentlyContinue | "
                "Select-Object -First 1",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def force_kill_codex() -> bool:
    """Force-kill all ChatGPT.exe / Codex.exe processes.

    @returns: True when no Codex process remains after the kill attempt.
    """
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Process -Name ChatGPT,Codex -ErrorAction SilentlyContinue | "
                "Stop-Process -Force -ErrorAction SilentlyContinue",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        time.sleep(1)
        return not is_codex_running()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def backup_leveldb(db_path: Path) -> Path:
    """Copy the LevelDB directory to a timestamped sibling for safety.

    @param db_path: LevelDB directory to back up.
    @returns: Path to the created backup directory.
    @throws OSError: If the copy fails.
    """
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = db_path.parent / f"leveldb_backup_{ts}"
    shutil.copytree(db_path, backup)
    return backup


# ---------------------------------------------------------------------------
# Core unlock logic
# ---------------------------------------------------------------------------

# Prefix shared by all Codex localStorage entries for the app:// origin.
_STATSIG_PREFIX = b"_app://-\x00"


def unlock_statsig_models(
    db_path: Path,
    models_to_add: list[str],
    default_model: str | None = None,
    create_backup: bool = True,
) -> dict[str, Any]:
    """Unlock custom models by modifying Statsig cached evaluations in LevelDB.

    Reads the database with *chromium-reader* (pure Python), modifies the
    JSON payload of every ``statsig.cached.evaluations.*`` key, then appends
    a WriteBatch to the active ``.log`` file so LevelDB picks up the changes
    on next open.

    @param db_path: Path to the Codex LevelDB directory.
    @param models_to_add: Model IDs to add to ``available_models``.
    @param default_model: If set, overwrite ``default_model`` in the config.
    @param create_backup: Copy the directory before any modification.
    @returns: Dict with keys ``success`` (bool), ``message`` (str),
              ``backup_path`` (Path | None), ``models_added`` (list[str]).
    @throws ImportError: If *chromium-reader* is not installed.
    """
    try:
        from chromium_reader.leveldb import KeyState, RawLevelDb
    except ImportError as exc:
        raise ImportError(
            "chromium-reader is required for LevelDB operations. "
            "Install with: pip install chromium-reader"
        ) from exc

    backup_path: Path | None = None
    if create_backup:
        try:
            backup_path = backup_leveldb(db_path)
        except Exception as exc:
            return {
                "success": False,
                "message": f"备份创建失败: {exc}",
                "backup_path": None,
                "models_added": [],
            }

    # ── Read phase ───────────────────────────────────────────────────────────
    max_seq = 0
    live_entries: dict[bytes, bytes] = {}   # raw_key → raw_value

    try:
        with RawLevelDb(db_path) as db:
            for record in db.iterate_records_raw():
                max_seq = max(max_seq, record.seq)
                if record.state != KeyState.LIVE:
                    continue
                if not record.user_key.startswith(_STATSIG_PREFIX):
                    continue
                live_entries[record.user_key] = record.value
    except Exception as exc:
        err = str(exc).upper()
        if "LOCK" in err or "PERMISSION" in err:
            return {
                "success": False,
                "message": "LevelDB 被锁定，请先完全关闭 Codex 再试",
                "backup_path": backup_path,
                "models_added": [],
            }
        raise

    if not live_entries:
        return {
            "success": False,
            "message": "未找到 Statsig 缓存，请先启动一次 Codex",
            "backup_path": backup_path,
            "models_added": [],
        }

    # ── Identify target keys ─────────────────────────────────────────────────
    # Key layout:  b"_app://-\x00" + suffix
    # The suffix usually starts with a version byte (e.g. \x01) then the JS key.
    eval_keys = {
        k: v
        for k, v in live_entries.items()
        if b"statsig.cached.evaluations." in k
    }

    lmt_key = next(
        (k for k in live_entries if b"statsig.last_modified_time.evaluations" in k),
        None,
    )

    if not eval_keys:
        return {
            "success": False,
            "message": "未找到 Statsig 评估缓存，请先启动一次 Codex",
            "backup_path": backup_path,
            "models_added": [],
        }

    # ── Modify phase ─────────────────────────────────────────────────────────
    models_added: list[str] = []
    puts: list[tuple[bytes, bytes]] = []

    for raw_key, raw_value in eval_keys.items():
        try:
            # Value format: 0x00 prefix + UTF-16LE JSON
            if not raw_value or raw_value[0] != 0:
                continue
            json_str = raw_value[1:].decode("utf-16-le")
            outer = json.loads(json_str)
            data = json.loads(outer["data"])
        except Exception:
            continue

        cfg = data.get("dynamic_configs", {}).get("107580212")
        if not cfg or "value" not in cfg:
            continue

        val = cfg["value"]
        changed = False

        if "available_models" not in val:
            val["available_models"] = []

        for model in models_to_add:
            if model not in val["available_models"]:
                val["available_models"].append(model)
                models_added.append(model)
                changed = True

        if default_model and val.get("default_model") != default_model:
            val["default_model"] = default_model
            changed = True

        if not changed:
            continue

        cfg["value"] = val
        outer["data"] = json.dumps(data)
        new_json = json.dumps(outer)
        new_raw = b"\x00" + new_json.encode("utf-16-le")
        puts.append((raw_key, new_raw))

    if not puts:
        return {
            "success": True,
            "message": "模型已存在于白名单中，无需修改",
            "backup_path": backup_path,
            "models_added": [],
        }

    # Also update last_modified_time so Statsig treats the cache as fresh.
    if lmt_key is not None and lmt_key in live_entries:
        try:
            raw_lmt = live_entries[lmt_key]
            prefix_byte = raw_lmt[0:1]
            enc = "utf-16-le" if prefix_byte == b"\x00" else "iso-8859-1"
            lmt_json = raw_lmt[1:].decode(enc)
            lmt_data = json.loads(lmt_json)
            now_ms = int(time.time() * 1000)
            for k in lmt_data:
                if "statsig.cached.evaluations." in k:
                    lmt_data[k] = now_ms
            new_lmt_str = json.dumps(lmt_data)
            new_lmt_raw = prefix_byte + new_lmt_str.encode(enc)
            puts.append((lmt_key, new_lmt_raw))
        except Exception:
            pass  # Non-fatal — Codex will still load the modified evaluations.

    # ── Write phase ──────────────────────────────────────────────────────────
    new_seq = max_seq + 1
    writebatch = _make_writebatch(new_seq, puts)
    active_log = _active_log_path(db_path)
    _append_to_log(active_log, writebatch)

    return {
        "success": True,
        "message": (
            f"成功解锁 {len(models_added)} 个模型，"
            f"已追加到 {active_log.name}"
        ),
        "backup_path": backup_path,
        "models_added": list(dict.fromkeys(models_added)),  # deduplicate
    }


def restore_leveldb_backup(backup_path: Path, target_path: Path) -> bool:
    """Restore a LevelDB backup created by :func:`backup_leveldb`.

    @param backup_path: Backup directory created by :func:`backup_leveldb`.
    @param target_path: Destination (the live LevelDB directory).
    @returns: True on success.
    """
    try:
        if target_path.exists():
            shutil.rmtree(target_path)
        shutil.copytree(backup_path, target_path)
        return True
    except Exception:
        return False
