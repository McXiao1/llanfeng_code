from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

import llanfeng_code_assistant.codex_desktop_launcher as launcher


def test_build_codex_launch_command_enables_cdp_and_origin(tmp_path) -> None:
    executable = tmp_path / "ChatGPT.exe"

    assert launcher.build_codex_launch_command(executable, 9317) == [
        str(executable),
        "--remote-debugging-port=9317",
        "--remote-allow-origins=http://127.0.0.1:9317",
    ]


def test_find_codex_desktop_executable_uses_store_install_location(monkeypatch, tmp_path) -> None:
    executable = tmp_path / "app" / "ChatGPT.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"")
    monkeypatch.setattr(
        launcher.subprocess,
        "run",
        lambda *_, **__: subprocess.CompletedProcess([], 0, stdout=str(tmp_path), stderr=""),
    )

    assert launcher.find_codex_desktop_executable() == executable


def test_select_codex_target_accepts_only_app_page_with_websocket() -> None:
    targets = (
        launcher.CdpTarget("worker", "worker", "", "", "ws://worker"),
        launcher.CdpTarget("web", "page", "Browser", "https://example.com", "ws://web"),
        launcher.CdpTarget("codex", "page", "Codex", "app://-/index.html", "ws://codex"),
    )

    assert launcher.select_codex_target(targets).target_id == "codex"


def test_select_codex_target_rejects_unrelated_pages() -> None:
    targets = (
        launcher.CdpTarget("web", "page", "Browser", "https://example.com", "ws://web"),
    )

    with pytest.raises(launcher.CodexDesktopError, match="Codex renderer"):
        launcher.select_codex_target(targets)


class _FakeSocket:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.sent: list[dict[str, object]] = []

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str:
        return json.dumps(self.responses.pop(0))


async def test_send_injection_commands_installs_and_evaluates_script() -> None:
    socket = _FakeSocket(
        [
            {"id": 1, "result": {"identifier": "script-1"}},
            {"id": 2, "result": {"result": {"type": "object"}}},
        ]
    )

    await launcher.send_injection_commands(socket, "window.test = true;")

    assert [message["method"] for message in socket.sent] == [
        "Page.addScriptToEvaluateOnNewDocument",
        "Runtime.evaluate",
    ]
    assert socket.sent[0]["params"] == {"source": "window.test = true;"}
    assert socket.sent[1]["params"]["expression"] == "window.test = true;"


async def test_send_injection_commands_raises_on_cdp_error() -> None:
    socket = _FakeSocket([{"id": 1, "error": {"message": "denied"}}])

    with pytest.raises(launcher.CodexDesktopError, match="denied"):
        await launcher.send_injection_commands(socket, "window.test = true;")


async def test_launch_plugin_marketplace_rejects_running_codex(monkeypatch) -> None:
    monkeypatch.setattr(launcher, "is_codex_desktop_running", lambda: True)

    result = await launcher.launch_plugin_marketplace()

    assert result.started is False
    assert result.enhanced is False
    assert "关闭" in result.message


async def test_launch_plugin_marketplace_reports_started_when_cdp_times_out(
    monkeypatch,
    tmp_path,
) -> None:
    executable = tmp_path / "ChatGPT.exe"
    monkeypatch.setattr(launcher, "is_codex_desktop_running", lambda: False)
    monkeypatch.setattr(launcher, "find_codex_desktop_executable", lambda: executable)
    monkeypatch.setattr(launcher, "allocate_cdp_port", lambda: 9333)
    monkeypatch.setattr(
        launcher,
        "launch_codex_with_cdp",
        lambda *_: SimpleNamespace(pid=42),
    )

    async def timeout(*_: object, **__: object) -> launcher.CdpTarget:
        raise TimeoutError("not ready")

    monkeypatch.setattr(launcher, "wait_for_codex_target", timeout)

    result = await launcher.launch_plugin_marketplace()

    assert result.started is True
    assert result.enhanced is False
    assert result.process_id == 42
    assert result.cdp_port == 9333
    assert "超时" in result.message


async def test_launch_plugin_marketplace_returns_enhanced_success(monkeypatch, tmp_path) -> None:
    executable = tmp_path / "ChatGPT.exe"
    target = launcher.CdpTarget(
        "codex",
        "page",
        "Codex",
        "app://-/index.html",
        "ws://codex",
    )
    injected: list[tuple[str, str]] = []
    monkeypatch.setattr(launcher, "is_codex_desktop_running", lambda: False)
    monkeypatch.setattr(launcher, "find_codex_desktop_executable", lambda: executable)
    monkeypatch.setattr(launcher, "allocate_cdp_port", lambda: 9444)
    monkeypatch.setattr(
        launcher,
        "launch_codex_with_cdp",
        lambda *_: SimpleNamespace(pid=84),
    )

    async def ready(*_: object, **__: object) -> launcher.CdpTarget:
        return target

    async def inject(websocket_url: str, script: str) -> None:
        injected.append((websocket_url, script))

    monkeypatch.setattr(launcher, "wait_for_codex_target", ready)
    monkeypatch.setattr(launcher, "inject_script", inject)

    result = await launcher.launch_plugin_marketplace("plugin-script")

    assert result.started is True
    assert result.enhanced is True
    assert result.process_id == 84
    assert injected == [("ws://codex", "plugin-script")]


def test_parse_cdp_targets_ignores_invalid_rows() -> None:
    payload = [
        {
            "id": "codex",
            "type": "page",
            "title": "Codex",
            "url": "app://-/index.html",
            "webSocketDebuggerUrl": "ws://codex",
        },
        {"id": 2, "type": "page"},
        "invalid",
    ]

    assert launcher.parse_cdp_targets(payload) == (
        launcher.CdpTarget(
            "codex",
            "page",
            "Codex",
            "app://-/index.html",
            "ws://codex",
        ),
    )


def test_allocate_cdp_port_returns_loopback_port() -> None:
    port = launcher.allocate_cdp_port()

    assert 0 < port < 65536


def test_is_codex_desktop_running_handles_probe_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        launcher.subprocess,
        "run",
        lambda *_, **__: (_ for _ in ()).throw(OSError("missing powershell")),
    )

    assert launcher.is_codex_desktop_running() is False
