from __future__ import annotations

import json
import os
import struct
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import llanfeng_code_assistant.codex_statsig_unlocker as unlocker


def _evaluation_value(
    available_models: object,
    *,
    default_model: str = "gpt-5.4",
) -> bytes:
    data = {
        "dynamic_configs": {
            "107580212": {
                "value": {
                    "available_models": available_models,
                    "default_model": default_model,
                    "use_hidden_models": True,
                }
            }
        }
    }
    outer = {"data": json.dumps(data, separators=(",", ":"))}
    return b"\x00" + json.dumps(outer, separators=(",", ":")).encode("utf-16-le")


def _decode_evaluation(raw_value: bytes) -> dict[str, object]:
    outer = json.loads(raw_value[1:].decode("utf-16-le"))
    return json.loads(outer["data"])


def _evaluation_key(suffix: str = "account") -> bytes:
    return f"_app://-\x00\x01statsig.cached.evaluations.{suffix}".encode()


def _timestamp_key() -> bytes:
    return b"_app://-\x00\x01statsig.last_modified_time.evaluations"


def test_parse_bundled_model_slugs_keeps_only_visible_supported_unique_models() -> None:
    payload = {
        "models": [
            {"slug": "gpt-5.6-sol", "visibility": "list", "supported_in_api": True},
            {"slug": "gpt-5.6-terra", "visibility": "LIST"},
            {"slug": "codex-auto-review", "visibility": "hide"},
            {"slug": "internal", "visibility": "list", "supported_in_api": False},
            {"slug": "gpt-5.6-sol", "visibility": "list"},
            {"slug": "  gpt-5.6-luna  ", "visibility": "list"},
            {"slug": "", "visibility": "list"},
            "not-a-model",
        ]
    }

    assert unlocker.parse_bundled_model_slugs(payload) == (
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
    )


def test_parse_bundled_model_slugs_excludes_models_without_explicit_list_visibility() -> None:
    payload = {
        "models": [
            {"slug": "missing-visibility"},
            {"slug": "visible", "visibility": "list"},
        ]
    }

    assert unlocker.parse_bundled_model_slugs(payload) == ("visible",)


@pytest.mark.parametrize("payload", [None, [], {}, {"models": "invalid"}])
def test_parse_bundled_model_slugs_rejects_invalid_catalog_shape(payload: object) -> None:
    with pytest.raises(ValueError, match="models"):
        unlocker.parse_bundled_model_slugs(payload)


def test_discover_bundled_model_slugs_runs_resolved_codex_command(monkeypatch) -> None:
    calls: list[list[str]] = []
    payload = {"models": [{"slug": "gpt-5.6-sol", "visibility": "list"}]}

    monkeypatch.setattr(unlocker.shutil, "which", lambda _: r"C:\tools\codex.exe")

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(unlocker.subprocess, "run", fake_run)

    result = unlocker.discover_bundled_model_slugs()

    assert result.success is True
    assert result.model_slugs == ("gpt-5.6-sol",)
    assert calls == [[r"C:\tools\codex.exe", "debug", "models", "--bundled"]]


def test_discover_bundled_model_slugs_reports_missing_cli(monkeypatch) -> None:
    monkeypatch.setattr(unlocker.shutil, "which", lambda _: None)

    result = unlocker.discover_bundled_model_slugs()

    assert result.success is False
    assert result.model_slugs == ()
    assert "未安装" in result.message


def test_discover_bundled_model_slugs_reports_command_failure(monkeypatch) -> None:
    monkeypatch.setattr(unlocker.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(
        unlocker.subprocess,
        "run",
        lambda command, **_: subprocess.CompletedProcess(
            command,
            2,
            stdout="",
            stderr="unsupported command",
        ),
    )

    result = unlocker.discover_bundled_model_slugs()

    assert result.success is False
    assert "unsupported command" in result.message


def test_find_codex_leveldb_path_selects_most_recent_valid_candidate(tmp_path) -> None:
    packages = tmp_path / "Packages"
    older = packages / "OpenAI.Codex_old" / unlocker.CODEX_LEVELDB_RELATIVE_PATH
    newer = packages / "OpenAI.Codex_new" / unlocker.CODEX_LEVELDB_RELATIVE_PATH
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    (older / "CURRENT").write_text("MANIFEST-000001\n", encoding="utf-8")
    (newer / "CURRENT").write_text("MANIFEST-000002\n", encoding="utf-8")
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    assert unlocker.find_codex_leveldb_path(tmp_path) == newer


def test_plan_statsig_updates_preserves_default_and_updates_all_valid_evaluations() -> None:
    first_key = _evaluation_key("first")
    second_key = _evaluation_key("second")
    state = unlocker.LevelDbState(
        max_sequence=7,
        live_entries={
            first_key: _evaluation_value(["gpt-5.4"]),
            second_key: _evaluation_value(["gpt-5.4", "gpt-5.6-sol"]),
        },
    )

    plan = unlocker.plan_statsig_model_updates(
        state,
        ("gpt-5.6-sol", "gpt-5.6-terra"),
        now_ms=1234,
    )

    assert plan.modified_records == 2
    assert plan.models_added == ("gpt-5.6-sol", "gpt-5.6-terra")
    assert len(plan.puts) == 2
    decoded = {key: _decode_evaluation(value) for key, value in plan.puts}
    first_value = decoded[first_key]["dynamic_configs"]["107580212"]["value"]
    second_value = decoded[second_key]["dynamic_configs"]["107580212"]["value"]
    assert first_value["available_models"] == [
        "gpt-5.4",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
    ]
    assert second_value["available_models"] == [
        "gpt-5.4",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
    ]
    assert first_value["default_model"] == "gpt-5.4"
    assert second_value["default_model"] == "gpt-5.4"


def test_plan_statsig_updates_leaves_malformed_whitelist_untouched() -> None:
    malformed_key = _evaluation_key("malformed")
    state = unlocker.LevelDbState(
        max_sequence=2,
        live_entries={malformed_key: _evaluation_value("gpt-5.4")},
    )

    plan = unlocker.plan_statsig_model_updates(state, ("gpt-5.6-sol",), now_ms=1)

    assert plan.puts == ()
    assert plan.valid_records == 0
    assert plan.modified_records == 0
    assert any("available_models" in warning for warning in plan.warnings)


def test_plan_statsig_updates_refreshes_utf8_timestamp_record() -> None:
    evaluation_key = _evaluation_key()
    timestamp_key = _timestamp_key()
    timestamp_name = "statsig.cached.evaluations.account"
    state = unlocker.LevelDbState(
        max_sequence=3,
        live_entries={
            evaluation_key: _evaluation_value(["gpt-5.4"]),
            timestamp_key: b"\x01" + json.dumps({timestamp_name: 10}).encode("utf-8"),
        },
    )

    plan = unlocker.plan_statsig_model_updates(state, ("gpt-5.6-sol",), now_ms=999)

    timestamp_put = next(value for key, value in plan.puts if key == timestamp_key)
    assert json.loads(timestamp_put[1:].decode("utf-8")) == {timestamp_name: 999}


def test_unlock_statsig_models_does_not_back_up_or_write_when_already_unlocked(
    monkeypatch,
    tmp_path,
) -> None:
    state = unlocker.LevelDbState(
        max_sequence=1,
        live_entries={_evaluation_key(): _evaluation_value(["gpt-5.6-sol"])},
    )
    monkeypatch.setattr(unlocker, "read_leveldb_state", lambda _: state)
    monkeypatch.setattr(
        unlocker,
        "backup_leveldb",
        lambda _: pytest.fail("idempotent unlock must not create a backup"),
    )
    monkeypatch.setattr(
        unlocker,
        "_append_to_log",
        lambda *_: pytest.fail("idempotent unlock must not write"),
    )

    result = unlocker.unlock_statsig_models(tmp_path, ("gpt-5.6-sol",))

    assert result.success is True
    assert result.models_added == ()
    assert result.backup_path is None
    assert result.modified_records == 0


def test_unlock_statsig_models_backs_up_once_before_real_write(monkeypatch, tmp_path) -> None:
    state = unlocker.LevelDbState(
        max_sequence=9,
        live_entries={_evaluation_key(): _evaluation_value(["gpt-5.4"])},
    )
    log_path = tmp_path / "000001.log"
    backup_path = tmp_path / "backup"
    calls: list[str] = []
    captured_batches: list[bytes] = []
    monkeypatch.setattr(unlocker, "read_leveldb_state", lambda _: state)
    monkeypatch.setattr(unlocker, "_active_log_path", lambda _: log_path)

    def fake_backup(_: Path) -> Path:
        calls.append("backup")
        return backup_path

    def fake_append(_: Path, batch: bytes) -> None:
        calls.append("write")
        captured_batches.append(batch)

    monkeypatch.setattr(unlocker, "backup_leveldb", fake_backup)
    monkeypatch.setattr(unlocker, "_append_to_log", fake_append)

    result = unlocker.unlock_statsig_models(tmp_path, ("gpt-5.6-sol",))

    assert calls == ["backup", "write"]
    assert result.success is True
    assert result.backup_path == backup_path
    assert result.models_added == ("gpt-5.6-sol",)
    sequence, count = struct.unpack("<QI", captured_batches[0][:12])
    assert sequence == 10
    assert count == 1


def test_discover_and_unlock_models_stops_before_leveldb_when_discovery_fails(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        unlocker,
        "discover_bundled_model_slugs",
        lambda: unlocker.BundledModelDiscoveryResult(False, (), "catalog unavailable"),
    )
    monkeypatch.setattr(
        unlocker,
        "find_codex_leveldb_path",
        lambda *_: pytest.fail("LevelDB lookup must not run after discovery failure"),
    )

    result = unlocker.discover_and_unlock_models()

    assert result.success is False
    assert result.message == "catalog unavailable"


def test_append_to_log_fragments_large_write_batch(tmp_path) -> None:
    log_path = tmp_path / "000001.log"
    batch = unlocker._make_writebatch(1, [(b"key", b"x" * 70000)])

    unlocker._append_to_log(log_path, batch)

    raw = log_path.read_bytes()
    assert raw[6] == unlocker._TYPE_FIRST
    second_header = unlocker._BLOCK_SIZE
    assert raw[second_header + 6] == unlocker._TYPE_MIDDLE
    third_header = unlocker._BLOCK_SIZE * 2
    assert raw[third_header + 6] == unlocker._TYPE_LAST


def test_is_codex_running_returns_false_when_process_probe_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        unlocker.subprocess,
        "run",
        lambda *_, **__: (_ for _ in ()).throw(OSError("powershell unavailable")),
    )

    assert unlocker.is_codex_running() is False


def test_terminate_codex_returns_true_only_after_process_exits(monkeypatch) -> None:
    probes = iter([True, False])
    monkeypatch.setattr(unlocker, "is_codex_running", lambda: next(probes))
    monkeypatch.setattr(
        unlocker.subprocess,
        "run",
        lambda *_, **__: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(unlocker.time, "sleep", lambda _: None)

    assert unlocker.terminate_codex() is True


def test_plan_statsig_cache_invalidation_selects_only_approved_live_keys() -> None:
    evaluation_key = _evaluation_key("restore")
    timestamp_key = _timestamp_key()
    unrelated_statsig_key = b"_app://-\x00\x01statsig.stable_id"
    unrelated_key = b"other-key"
    state = unlocker.LevelDbState(
        max_sequence=12,
        live_entries={
            evaluation_key: b"evaluation",
            timestamp_key: b"timestamp",
            unrelated_statsig_key: b"stable",
            unrelated_key: b"other",
        },
    )

    plan = unlocker.plan_statsig_cache_invalidation(state)

    assert plan.keys == (evaluation_key, timestamp_key)
    assert plan.evaluation_count == 1
    assert plan.timestamp_count == 1


def test_plan_statsig_cache_invalidation_is_empty_without_approved_keys() -> None:
    state = unlocker.LevelDbState(
        max_sequence=3,
        live_entries={b"_app://-\x00\x01statsig.stable_id": b"stable"},
    )

    plan = unlocker.plan_statsig_cache_invalidation(state)

    assert plan.keys == ()
    assert plan.evaluation_count == 0
    assert plan.timestamp_count == 0


def test_make_writebatch_encodes_leveldb_deletion_records() -> None:
    key = b"statsig-key"

    batch = unlocker._make_writebatch(41, (), (key,))

    sequence, count = struct.unpack("<QI", batch[:12])
    assert sequence == 41
    assert count == 1
    assert batch[12] == 0
    assert batch[13] == len(key)
    assert batch[14 : 14 + len(key)] == key


def test_invalidate_statsig_cache_is_idempotent_without_matching_keys(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        unlocker,
        "read_leveldb_state",
        lambda _: unlocker.LevelDbState(max_sequence=5, live_entries={}),
    )
    monkeypatch.setattr(
        unlocker,
        "_append_to_log",
        lambda *_: pytest.fail("empty invalidation must not write"),
    )

    result = unlocker.invalidate_statsig_cache(tmp_path)

    assert result.success is True
    assert result.invalidated_keys == 0
    assert result.write_attempted is False


def test_invalidate_statsig_cache_appends_one_exact_deletion_batch(
    monkeypatch,
    tmp_path,
) -> None:
    evaluation_key = _evaluation_key("restore")
    timestamp_key = _timestamp_key()
    state = unlocker.LevelDbState(
        max_sequence=20,
        live_entries={
            evaluation_key: b"evaluation",
            timestamp_key: b"timestamp",
            b"_app://-\x00\x01statsig.stable_id": b"stable",
        },
    )
    captured: list[bytes] = []
    monkeypatch.setattr(unlocker, "read_leveldb_state", lambda _: state)
    monkeypatch.setattr(unlocker, "_active_log_path", lambda _: tmp_path / "000001.log")
    monkeypatch.setattr(unlocker, "_append_to_log", lambda _, batch: captured.append(batch))

    result = unlocker.invalidate_statsig_cache(tmp_path)

    assert result.success is True
    assert result.invalidated_keys == 2
    assert result.write_attempted is True
    assert len(captured) == 1
    sequence, count = struct.unpack("<QI", captured[0][:12])
    assert sequence == 21
    assert count == 2
    assert captured[0].count(unlocker._TYPE_DELETION) >= 2


def test_invalidate_statsig_cache_reports_attempted_write_failure(
    monkeypatch,
    tmp_path,
) -> None:
    state = unlocker.LevelDbState(
        max_sequence=8,
        live_entries={_evaluation_key("restore"): b"evaluation"},
    )
    monkeypatch.setattr(unlocker, "read_leveldb_state", lambda _: state)
    monkeypatch.setattr(unlocker, "_active_log_path", lambda _: tmp_path / "000001.log")
    monkeypatch.setattr(
        unlocker,
        "_append_to_log",
        lambda *_: (_ for _ in ()).throw(OSError("disk full")),
    )

    result = unlocker.invalidate_statsig_cache(tmp_path)

    assert result.success is False
    assert result.invalidated_keys == 0
    assert result.write_attempted is True
    assert "disk full" in result.message


def test_append_to_log_fragments_large_deletion_batch(tmp_path) -> None:
    log_path = tmp_path / "000002.log"
    keys = tuple(f"key-{index:04d}-".encode() + b"x" * 110 for index in range(800))
    batch = unlocker._make_writebatch(1, (), keys)

    unlocker._append_to_log(log_path, batch)

    raw = log_path.read_bytes()
    assert raw[6] == unlocker._TYPE_FIRST
    assert raw[unlocker._BLOCK_SIZE + 6] == unlocker._TYPE_MIDDLE
    assert raw[unlocker._BLOCK_SIZE * 2 + 6] == unlocker._TYPE_LAST
