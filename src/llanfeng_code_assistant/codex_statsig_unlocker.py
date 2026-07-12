"""Discover and persistently unlock eligible Codex models in Statsig LevelDB."""
from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

CODEX_LEVELDB_RELATIVE_PATH = Path(
    "LocalCache/Roaming/Codex/web/Codex/Default/Local Storage/leveldb"
)
STATSIG_CONFIG_ID = "107580212"
_STATSIG_PREFIX = b"_app://-\x00"
_EVALUATION_MARKER = b"statsig.cached.evaluations."
_TIMESTAMP_MARKER = b"statsig.last_modified_time.evaluations"

_BLOCK_SIZE = 32768
_HEADER_SIZE = 7
_TYPE_FULL = 1
_TYPE_FIRST = 2
_TYPE_MIDDLE = 3
_TYPE_LAST = 4
_TYPE_DELETION = b"\x00"
_TYPE_VALUE = b"\x01"


@dataclass(frozen=True)
class BundledModelDiscoveryResult:
    """Result of querying the installed Codex bundled model catalog.

    @param success: Whether discovery completed with at least one eligible model.
    @param model_slugs: Eligible model slugs in Codex catalog order.
    @param message: User-facing result or recovery guidance.
    """

    success: bool
    model_slugs: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class ModelUnlockResult:
    """Result of a persistent Statsig whitelist update.

    @param success: Whether the operation completed without a fatal error.
    @param message: User-facing result or recovery guidance.
    @param candidate_models: Eligible models considered for the whitelist.
    @param models_added: Unique models appended to at least one evaluation record.
    @param backup_path: Backup directory created before a real write.
    @param modified_records: Number of Statsig evaluation records changed.
    @param warnings: Non-fatal malformed or auxiliary-record details.
    """

    success: bool
    message: str
    candidate_models: tuple[str, ...] = ()
    models_added: tuple[str, ...] = ()
    backup_path: Path | None = None
    modified_records: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class LevelDbState:
    """Live LevelDB entries required to plan a Statsig update.

    @param max_sequence: Highest sequence number observed in the database.
    @param live_entries: Latest live values keyed by raw user key.
    """

    max_sequence: int
    live_entries: Mapping[bytes, bytes]


@dataclass(frozen=True)
class StatsigMutationPlan:
    """Pure write plan produced before backup or LevelDB mutation.

    @param puts: Raw LevelDB key/value pairs to append.
    @param models_added: Unique model slugs missing from at least one record.
    @param valid_records: Number of valid target configuration records found.
    @param modified_records: Number of target records requiring changes.
    @param warnings: Non-fatal records intentionally left untouched.
    """

    puts: tuple[tuple[bytes, bytes], ...]
    models_added: tuple[str, ...]
    valid_records: int
    modified_records: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class StatsigInvalidationPlan:
    """Exact live Statsig cache keys selected for LevelDB deletion.

    @param keys: Unique raw LevelDB keys in live-entry order.
    @param evaluation_count: Number of cached evaluation keys selected.
    @param timestamp_count: Number of evaluation timestamp keys selected.
    """

    keys: tuple[bytes, ...]
    evaluation_count: int
    timestamp_count: int


@dataclass(frozen=True)
class StatsigInvalidationResult:
    """Result of appending exact Statsig cache deletion records.

    @param success: Whether invalidation completed without a fatal error.
    @param message: User-facing result or recovery guidance.
    @param invalidated_keys: Number of deletion records successfully appended.
    @param write_attempted: Whether the LevelDB log append was attempted.
    """

    success: bool
    message: str
    invalidated_keys: int = 0
    write_attempted: bool = False


_CRC32C_TABLE: tuple[int, ...]
_crc_table: list[int] = []
for _table_index in range(256):
    _table_value = _table_index
    for _ in range(8):
        _table_value = (_table_value >> 1) ^ (0x82F63B78 if _table_value & 1 else 0)
    _crc_table.append(_table_value)
_CRC32C_TABLE = tuple(_crc_table)


def parse_bundled_model_slugs(payload: object) -> tuple[str, ...]:
    """Parse eligible model slugs from ``codex debug models --bundled`` JSON.

    @param payload: Decoded JSON payload.
    @returns: Unique eligible slugs in catalog order.
    @throws ValueError: If the root or ``models`` collection has an invalid shape.
    """

    if not isinstance(payload, dict):
        raise ValueError("Codex model catalog must contain a models array")
    raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        raise ValueError("Codex model catalog must contain a models array")

    slugs: list[str] = []
    seen: set[str] = set()
    for raw_model in raw_models:
        if not isinstance(raw_model, dict):
            continue
        raw_slug = raw_model.get("slug")
        raw_visibility = raw_model.get("visibility")
        supported_in_api = raw_model.get("supported_in_api", True)
        if not isinstance(raw_slug, str) or not isinstance(raw_visibility, str):
            continue
        slug = raw_slug.strip()
        if (
            not slug
            or raw_visibility.strip().lower() != "list"
            or supported_in_api is False
            or slug in seen
        ):
            continue
        seen.add(slug)
        slugs.append(slug)
    return tuple(slugs)


def discover_bundled_model_slugs(
    codex_command: str = "codex",
    timeout_seconds: float = 15.0,
) -> BundledModelDiscoveryResult:
    """Query the installed Codex CLI for its bundled model catalog.

    @param codex_command: Command name resolved through ``PATH``.
    @param timeout_seconds: Maximum command runtime.
    @returns: Typed discovery result with eligible model slugs.
    """

    executable = shutil.which(codex_command)
    if executable is None:
        return BundledModelDiscoveryResult(
            False,
            (),
            "未安装 Codex CLI, 请先完成 Codex 一键安装",
        )

    command = [executable, "debug", "models", "--bundled"]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        return BundledModelDiscoveryResult(False, (), "读取 Codex 模型目录超时, 请重试")
    except OSError as exc:
        return BundledModelDiscoveryResult(False, (), f"无法运行 Codex CLI: {exc}")

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "未知错误"
        return BundledModelDiscoveryResult(False, (), f"读取 Codex 模型目录失败: {detail}")

    try:
        payload: object = json.loads(completed.stdout)
        model_slugs = parse_bundled_model_slugs(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        return BundledModelDiscoveryResult(False, (), f"Codex 模型目录格式无效: {exc}")

    if not model_slugs:
        return BundledModelDiscoveryResult(False, (), "Codex 模型目录中没有可显示模型")
    return BundledModelDiscoveryResult(
        True,
        model_slugs,
        f"发现 {len(model_slugs)} 个可显示模型",
    )


def find_codex_leveldb_path(local_app_data: Path | None = None) -> Path | None:
    """Locate the most recently modified valid Codex localStorage LevelDB.

    @param local_app_data: Optional Local AppData root used by tests.
    @returns: Deterministically selected LevelDB path, or ``None``.
    """

    root = local_app_data
    if root is None:
        configured = os.environ.get("LOCALAPPDATA")
        root = Path(configured) if configured else Path.home() / "AppData" / "Local"
    packages_dir = root / "Packages"
    if not packages_dir.is_dir():
        return None

    candidates: list[Path] = []
    for package_dir in packages_dir.glob("OpenAI.Codex_*"):
        leveldb_path = package_dir / CODEX_LEVELDB_RELATIVE_PATH
        if leveldb_path.is_dir() and (leveldb_path / "CURRENT").is_file():
            candidates.append(leveldb_path)
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path).lower()))


def is_codex_running() -> bool:
    """Return whether a ChatGPT or Codex desktop process is running.

    @returns: ``True`` when at least one matching process is detected.
    """

    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-Process -Name ChatGPT,Codex -ErrorAction SilentlyContinue | "
                "Select-Object -First 1 -ExpandProperty Id",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return bool(completed.stdout.strip())


def terminate_codex() -> bool:
    """Terminate Codex after explicit caller confirmation.

    @returns: ``True`` when no matching process remains.
    """

    if not is_codex_running():
        return True
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-Process -Name ChatGPT,Codex -ErrorAction SilentlyContinue | "
                "Stop-Process -Force -ErrorAction SilentlyContinue",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    time.sleep(1)
    return not is_codex_running()


def backup_leveldb(db_path: Path) -> Path:
    """Create a timestamped sibling backup of a Codex LevelDB directory.

    @param db_path: Live LevelDB path.
    @returns: Created backup path.
    @throws OSError: If the directory cannot be copied.
    """

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"leveldb_backup_{timestamp}"
    suffix = 1
    while backup_path.exists():
        backup_path = db_path.parent / f"leveldb_backup_{timestamp}_{suffix}"
        suffix += 1
    shutil.copytree(db_path, backup_path)
    return backup_path


def read_leveldb_state(db_path: Path) -> LevelDbState:
    """Read the latest live Codex Statsig entries with ``chromium-reader``.

    @param db_path: LevelDB directory.
    @returns: Maximum sequence and relevant live entries.
    @throws ImportError: If ``chromium-reader`` is unavailable.
    @throws OSError: If the database cannot be read.
    """

    try:
        from chromium_reader.leveldb import KeyState, RawLevelDb
    except ImportError as exc:
        raise ImportError("缺少 chromium-reader, 无法读取 Codex LevelDB") from exc

    max_sequence = 0
    live_entries: dict[bytes, bytes] = {}
    with RawLevelDb(db_path) as database:
        for record in database.iterate_records_raw():
            max_sequence = max(max_sequence, record.seq)
            if record.state != KeyState.LIVE:
                continue
            if not record.user_key.startswith(_STATSIG_PREFIX):
                continue
            if not isinstance(record.value, bytes):
                continue
            live_entries[record.user_key] = record.value
    return LevelDbState(max_sequence=max_sequence, live_entries=live_entries)


def _decode_evaluation(raw_value: bytes) -> tuple[dict[str, object], dict[str, object]]:
    if not raw_value or raw_value[0] != 0:
        raise ValueError("evaluation value is not UTF-16 localStorage data")
    outer_payload: object = json.loads(raw_value[1:].decode("utf-16-le"))
    if not isinstance(outer_payload, dict):
        raise ValueError("evaluation outer payload is not an object")
    embedded = outer_payload.get("data")
    if not isinstance(embedded, str):
        raise ValueError("evaluation data field is missing")
    data_payload: object = json.loads(embedded)
    if not isinstance(data_payload, dict):
        raise ValueError("evaluation data payload is not an object")
    return outer_payload, data_payload


def _encode_evaluation(outer: dict[str, object], data: dict[str, object]) -> bytes:
    outer["data"] = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return b"\x00" + json.dumps(
        outer,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-16-le")


def _timestamp_update(
    raw_value: bytes,
    now_ms: int,
) -> tuple[bytes | None, str | None]:
    if not raw_value:
        return None, "Statsig 时间戳记录为空"
    prefix = raw_value[:1]
    encoding = "utf-16-le" if prefix == b"\x00" else "utf-8"
    try:
        payload: object = json.loads(raw_value[1:].decode(encoding))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"Statsig 时间戳记录无法解析: {exc}"
    if not isinstance(payload, dict):
        return None, "Statsig 时间戳记录不是对象"

    changed = False
    for key in tuple(payload):
        if isinstance(key, str) and "statsig.cached.evaluations." in key:
            payload[key] = now_ms
            changed = True
    if not changed:
        return None, "Statsig 时间戳记录中没有 evaluation 键"
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(encoding)
    return prefix + encoded, None


def plan_statsig_model_updates(
    state: LevelDbState,
    model_slugs: Sequence[str],
    *,
    now_ms: int,
) -> StatsigMutationPlan:
    """Build a pure LevelDB write plan for missing model whitelist entries.

    @param state: Live relevant LevelDB entries.
    @param model_slugs: Eligible model candidates in desired append order.
    @param now_ms: Timestamp used for Statsig freshness metadata.
    @returns: Mutation plan; no filesystem operation is performed.
    """

    candidates = tuple(dict.fromkeys(slug.strip() for slug in model_slugs if slug.strip()))
    puts: list[tuple[bytes, bytes]] = []
    warnings: list[str] = []
    added: list[str] = []
    seen_added: set[str] = set()
    valid_records = 0
    modified_records = 0

    for raw_key, raw_value in state.live_entries.items():
        if _EVALUATION_MARKER not in raw_key:
            continue
        try:
            outer, data = _decode_evaluation(raw_value)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            warnings.append(f"跳过无法解析的 Statsig evaluation: {exc}")
            continue

        dynamic_configs = data.get("dynamic_configs")
        if not isinstance(dynamic_configs, dict):
            continue
        config = dynamic_configs.get(STATSIG_CONFIG_ID)
        if not isinstance(config, dict):
            continue
        value = config.get("value")
        if not isinstance(value, dict):
            warnings.append("跳过 value 结构无效的 Statsig 107580212 记录")
            continue
        available_models = value.get("available_models")
        if not isinstance(available_models, list) or not all(
            isinstance(item, str) for item in available_models
        ):
            warnings.append("跳过 available_models 不是字符串数组的 Statsig 107580212 记录")
            continue

        valid_records += 1
        existing = set(available_models)
        missing = [slug for slug in candidates if slug not in existing]
        if not missing:
            continue
        value["available_models"] = [*available_models, *missing]
        puts.append((raw_key, _encode_evaluation(outer, data)))
        modified_records += 1
        for slug in missing:
            if slug not in seen_added:
                seen_added.add(slug)
                added.append(slug)

    if modified_records:
        timestamp_entry = next(
            (
                (key, value)
                for key, value in state.live_entries.items()
                if _TIMESTAMP_MARKER in key
            ),
            None,
        )
        if timestamp_entry is not None:
            timestamp_key, timestamp_value = timestamp_entry
            updated_timestamp, warning = _timestamp_update(timestamp_value, now_ms)
            if updated_timestamp is not None:
                puts.append((timestamp_key, updated_timestamp))
            elif warning is not None:
                warnings.append(warning)

    return StatsigMutationPlan(
        puts=tuple(puts),
        models_added=tuple(added),
        valid_records=valid_records,
        modified_records=modified_records,
        warnings=tuple(warnings),
    )


def plan_statsig_cache_invalidation(state: LevelDbState) -> StatsigInvalidationPlan:
    """Select only live Statsig evaluation cache keys for deletion.

    @param state: Current live LevelDB state.
    @returns: Exact-key invalidation plan that excludes unrelated entries.
    """

    keys: list[bytes] = []
    evaluation_count = 0
    timestamp_count = 0
    for raw_key in state.live_entries:
        if _EVALUATION_MARKER in raw_key:
            keys.append(raw_key)
            evaluation_count += 1
            continue
        if _TIMESTAMP_MARKER in raw_key:
            keys.append(raw_key)
            timestamp_count += 1
    return StatsigInvalidationPlan(
        keys=tuple(keys),
        evaluation_count=evaluation_count,
        timestamp_count=timestamp_count,
    )


def _crc32c(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in data:
        crc = (crc >> 8) ^ _CRC32C_TABLE[(crc ^ byte) & 0xFF]
    return crc ^ 0xFFFFFFFF


def _masked_crc32c(data: bytes) -> int:
    crc = _crc32c(data)
    return (((crc >> 15) | (crc << 17)) + 0xA282EAD8) & 0xFFFFFFFF


def _varint(number: int) -> bytes:
    encoded: list[int] = []
    while number >= 0x80:
        encoded.append((number & 0x7F) | 0x80)
        number >>= 7
    encoded.append(number)
    return bytes(encoded)


def _make_writebatch(
    sequence: int,
    puts: Sequence[tuple[bytes, bytes]],
    deletes: Sequence[bytes] = (),
) -> bytes:
    """Build a LevelDB WriteBatch payload with put and deletion records.

    @param sequence: First sequence number for the batch.
    @param puts: Raw key/value writes.
    @param deletes: Exact raw keys to tombstone.
    @returns: Encoded WriteBatch.
    """

    payload = bytearray(struct.pack("<QI", sequence, len(puts) + len(deletes)))
    for key, value in puts:
        payload.extend(_TYPE_VALUE)
        payload.extend(_varint(len(key)))
        payload.extend(key)
        payload.extend(_varint(len(value)))
        payload.extend(value)
    for key in deletes:
        payload.extend(_TYPE_DELETION)
        payload.extend(_varint(len(key)))
        payload.extend(key)
    return bytes(payload)


def _make_fragment(data: bytes, record_type: int) -> bytes:
    checksum = _masked_crc32c(bytes([record_type]) + data)
    return struct.pack("<IHB", checksum, len(data), record_type) + data


def _append_to_log(log_path: Path, writebatch: bytes) -> None:
    """Append a potentially fragmented WriteBatch to a LevelDB log.

    @param log_path: Active LevelDB log path.
    @param writebatch: Encoded WriteBatch.
    @returns: None.
    """

    log_path.touch(exist_ok=True)
    block_offset = log_path.stat().st_size % _BLOCK_SIZE
    remaining = writebatch
    first = True

    with log_path.open("ab") as handle:
        while remaining:
            block_remaining = _BLOCK_SIZE - block_offset
            if block_remaining < _HEADER_SIZE:
                handle.write(b"\x00" * block_remaining)
                block_offset = 0
                block_remaining = _BLOCK_SIZE

            capacity = block_remaining - _HEADER_SIZE
            chunk = remaining[:capacity]
            remaining = remaining[capacity:]
            if first and not remaining:
                record_type = _TYPE_FULL
            elif first:
                record_type = _TYPE_FIRST
            elif remaining:
                record_type = _TYPE_MIDDLE
            else:
                record_type = _TYPE_LAST
            handle.write(_make_fragment(chunk, record_type))
            block_offset = 0 if remaining else block_offset + _HEADER_SIZE + len(chunk)
            first = False


def _active_log_path(db_path: Path) -> Path:
    logs = list(db_path.glob("*.log"))

    def log_number(path: Path) -> tuple[int, str]:
        try:
            return int(path.stem), path.name
        except ValueError:
            return -1, path.name

    return max(logs, key=log_number) if logs else db_path / "000001.log"


def invalidate_statsig_cache(db_path: Path) -> StatsigInvalidationResult:
    """Append tombstones for live Statsig evaluation cache keys only.

    The caller owns the mandatory pre-write backup.

    @param db_path: Codex localStorage LevelDB directory.
    @returns: Typed invalidation result including write-attempt metadata.
    """

    try:
        state = read_leveldb_state(db_path)
    except ImportError as exc:
        return StatsigInvalidationResult(False, str(exc))
    except Exception as exc:
        detail = str(exc)
        if "LOCK" in detail.upper() or "PERMISSION" in detail.upper():
            detail = "Codex LevelDB 被锁定, 请完全关闭 Codex 后重试"
        else:
            detail = f"读取 Codex LevelDB 失败: {detail}"
        return StatsigInvalidationResult(False, detail)

    plan = plan_statsig_cache_invalidation(state)
    if not plan.keys:
        return StatsigInvalidationResult(True, "Statsig 模型缓存已是默认状态")

    writebatch = _make_writebatch(state.max_sequence + 1, (), plan.keys)
    try:
        _append_to_log(_active_log_path(db_path), writebatch)
    except OSError as exc:
        return StatsigInvalidationResult(
            False,
            f"清除 Statsig 模型缓存失败: {exc}",
            write_attempted=True,
        )

    return StatsigInvalidationResult(
        True,
        f"已清除 {len(plan.keys)} 项 Statsig 模型缓存",
        invalidated_keys=len(plan.keys),
        write_attempted=True,
    )


def unlock_statsig_models(
    db_path: Path,
    models_to_add: Sequence[str],
    *,
    create_backup: bool = True,
) -> ModelUnlockResult:
    """Append missing eligible models to Codex Statsig cached evaluations.

    @param db_path: Codex localStorage LevelDB path.
    @param models_to_add: Eligible model slugs from the bundled catalog.
    @param create_backup: Whether to back up before a real write.
    @returns: Typed unlock result.
    """

    candidates = tuple(dict.fromkeys(slug.strip() for slug in models_to_add if slug.strip()))
    if not candidates:
        return ModelUnlockResult(False, "没有可解锁的 Codex 模型")
    try:
        state = read_leveldb_state(db_path)
    except ImportError as exc:
        return ModelUnlockResult(False, str(exc), candidate_models=candidates)
    except Exception as exc:
        detail = str(exc)
        if "LOCK" in detail.upper() or "PERMISSION" in detail.upper():
            detail = "Codex LevelDB 被锁定, 请完全关闭 Codex 后重试"
        else:
            detail = f"读取 Codex LevelDB 失败: {detail}"
        return ModelUnlockResult(False, detail, candidate_models=candidates)

    plan = plan_statsig_model_updates(
        state,
        candidates,
        now_ms=int(time.time() * 1000),
    )
    if plan.valid_records == 0:
        return ModelUnlockResult(
            False,
            "未找到结构有效的 Statsig 模型白名单, 请先正常启动一次 Codex",
            candidate_models=candidates,
            warnings=plan.warnings,
        )
    if not plan.puts:
        return ModelUnlockResult(
            True,
            "所有可显示模型均已在白名单中",
            candidate_models=candidates,
            warnings=plan.warnings,
        )

    backup_path: Path | None = None
    if create_backup:
        try:
            backup_path = backup_leveldb(db_path)
        except OSError as exc:
            return ModelUnlockResult(
                False,
                f"创建 LevelDB 备份失败: {exc}",
                candidate_models=candidates,
                models_added=plan.models_added,
                warnings=plan.warnings,
            )

    writebatch = _make_writebatch(state.max_sequence + 1, plan.puts)
    active_log = _active_log_path(db_path)
    try:
        _append_to_log(active_log, writebatch)
    except OSError as exc:
        return ModelUnlockResult(
            False,
            f"写入 Codex LevelDB 失败: {exc}",
            candidate_models=candidates,
            models_added=plan.models_added,
            backup_path=backup_path,
            warnings=plan.warnings,
        )

    return ModelUnlockResult(
        True,
        f"已解锁 {len(plan.models_added)} 个模型",
        candidate_models=candidates,
        models_added=plan.models_added,
        backup_path=backup_path,
        modified_records=plan.modified_records,
        warnings=plan.warnings,
    )


def discover_and_unlock_models(db_path: Path | None = None) -> ModelUnlockResult:
    """Discover eligible bundled models and persist missing whitelist entries.

    @param db_path: Optional explicit LevelDB path used by tests or diagnostics.
    @returns: Typed end-to-end unlock result.
    """

    discovery = discover_bundled_model_slugs()
    if not discovery.success:
        return ModelUnlockResult(False, discovery.message)
    resolved_path = db_path or find_codex_leveldb_path()
    if resolved_path is None:
        return ModelUnlockResult(
            False,
            "未找到 Codex LevelDB, 请安装并至少启动一次 Codex Desktop",
            candidate_models=discovery.model_slugs,
        )
    return unlock_statsig_models(resolved_path, discovery.model_slugs)
