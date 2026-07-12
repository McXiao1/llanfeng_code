"""Launch Microsoft Store Codex Desktop and inject a verified CDP script."""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

CDP_WAIT_TIMEOUT = 15.0
CDP_WAIT_INTERVAL = 0.3
STORE_PACKAGE_NAME = "OpenAI.Codex"
STORE_EXECUTABLE_PATHS = (Path("app/ChatGPT.exe"), Path("app/Codex.exe"))


class CodexDesktopError(RuntimeError):
    """Raised when Codex Desktop cannot be safely enhanced."""


class CdpSocket(Protocol):
    """Minimal WebSocket protocol required by CDP command delivery."""

    async def send(self, message: str) -> None:
        """Send one text frame."""

    async def recv(self) -> str | bytes:
        """Receive one CDP response frame."""


@dataclass(frozen=True)
class CdpTarget:
    """Chrome DevTools Protocol target metadata.

    @param target_id: CDP target identifier.
    @param target_type: CDP target type, normally ``page``.
    @param title: Renderer title.
    @param url: Renderer URL.
    @param websocket_url: Target WebSocket debugger URL.
    """

    target_id: str
    target_type: str
    title: str
    url: str
    websocket_url: str


@dataclass(frozen=True)
class CodexLaunchResult:
    """Result of starting Codex and applying the marketplace enhancement.

    @param started: Whether the Codex process was started.
    @param enhanced: Whether the runtime script was confirmed delivered.
    @param message: User-facing status.
    @param process_id: Started process identifier when available.
    @param cdp_port: Loopback CDP port when a process was started.
    """

    started: bool
    enhanced: bool
    message: str
    process_id: int | None = None
    cdp_port: int | None = None


def build_codex_launch_command(executable: Path, cdp_port: int) -> list[str]:
    """Build the Store Codex command with loopback CDP arguments.

    @param executable: Microsoft Store ChatGPT/Codex executable.
    @param cdp_port: Allocated loopback debug port.
    @returns: Process argument vector.
    """

    return [
        str(executable),
        f"--remote-debugging-port={cdp_port}",
        f"--remote-allow-origins=http://127.0.0.1:{cdp_port}",
    ]


def find_codex_desktop_executable() -> Path | None:
    """Locate the Microsoft Store Codex Desktop executable.

    @returns: Existing ChatGPT/Codex executable path, or ``None``.
    """

    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"(Get-AppxPackage -Name '{STORE_PACKAGE_NAME}').InstallLocation",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    install_location = completed.stdout.strip()
    if completed.returncode != 0 or not install_location:
        return None
    root = Path(install_location)
    return next(
        (root / relative for relative in STORE_EXECUTABLE_PATHS if (root / relative).is_file()),
        None,
    )


def is_codex_desktop_running() -> bool:
    """Return whether a Codex Desktop process is already running.

    @returns: ``True`` when ChatGPT or Codex is detected.
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


def allocate_cdp_port() -> int:
    """Allocate an available loopback TCP port for the CDP endpoint.

    @returns: Available port number.
    """

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def launch_codex_with_cdp(
    executable: Path,
    cdp_port: int,
) -> subprocess.Popen[bytes]:
    """Start Codex Desktop with CDP enabled.

    @param executable: Store Codex executable.
    @param cdp_port: Allocated debug port.
    @returns: Started process handle.
    @throws OSError: If process creation fails.
    """

    creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    return subprocess.Popen(
        build_codex_launch_command(executable, cdp_port),
        creationflags=creation_flags,
        close_fds=True,
    )


def parse_cdp_targets(payload: object) -> tuple[CdpTarget, ...]:
    """Parse valid target rows returned by the CDP ``/json`` endpoint.

    @param payload: Decoded endpoint response.
    @returns: Valid target metadata rows.
    """

    if not isinstance(payload, list):
        return ()
    targets: list[CdpTarget] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        values = (
            row.get("id"),
            row.get("type"),
            row.get("title", ""),
            row.get("url", ""),
            row.get("webSocketDebuggerUrl"),
        )
        if not all(isinstance(value, str) for value in values):
            continue
        target_id, target_type, title, url, websocket_url = values
        if not target_id or not target_type or not websocket_url:
            continue
        targets.append(CdpTarget(target_id, target_type, title, url, websocket_url))
    return tuple(targets)


def fetch_cdp_targets(cdp_port: int) -> tuple[CdpTarget, ...]:
    """Fetch current CDP targets from the loopback endpoint.

    @param cdp_port: Debug port.
    @returns: Parsed target rows.
    @throws OSError: If the endpoint is unavailable.
    """

    with urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=2) as response:
        payload: object = json.loads(response.read().decode("utf-8"))
    return parse_cdp_targets(payload)


def select_codex_target(targets: tuple[CdpTarget, ...]) -> CdpTarget:
    """Select a verified Codex ``app://`` page target.

    @param targets: Available CDP targets.
    @returns: Verified Codex renderer target.
    @throws CodexDesktopError: If no safe target is available.
    """

    for target in targets:
        if target.target_type == "page" and target.url.lower().startswith("app://"):
            return target
    raise CodexDesktopError("CDP endpoint did not expose a verified Codex renderer")


async def wait_for_codex_target(
    cdp_port: int,
    timeout_seconds: float = CDP_WAIT_TIMEOUT,
) -> CdpTarget:
    """Poll until Codex exposes a verified renderer target.

    @param cdp_port: Debug port.
    @param timeout_seconds: Maximum polling duration.
    @returns: Verified renderer target.
    @throws TimeoutError: If no target becomes ready.
    """

    deadline = time.monotonic() + timeout_seconds
    last_error = "CDP endpoint unavailable"
    while time.monotonic() < deadline:
        try:
            targets = await asyncio.to_thread(fetch_cdp_targets, cdp_port)
            return select_codex_target(targets)
        except (OSError, ValueError, json.JSONDecodeError, CodexDesktopError) as exc:
            last_error = str(exc)
        await asyncio.sleep(CDP_WAIT_INTERVAL)
    raise TimeoutError(last_error)


def _decode_cdp_response(raw_response: str | bytes) -> dict[str, object]:
    text = raw_response.decode("utf-8") if isinstance(raw_response, bytes) else raw_response
    payload: object = json.loads(text)
    if not isinstance(payload, dict):
        raise CodexDesktopError("CDP returned a non-object response")
    return payload


async def _send_cdp_command(
    websocket: CdpSocket,
    message_id: int,
    method: str,
    params: dict[str, object],
) -> None:
    await websocket.send(
        json.dumps(
            {"id": message_id, "method": method, "params": params},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    try:
        response = _decode_cdp_response(await websocket.recv())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CodexDesktopError(f"CDP response is invalid: {exc}") from exc
    error = response.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        detail = message if isinstance(message, str) else json.dumps(error, ensure_ascii=False)
        raise CodexDesktopError(f"CDP command {method} failed: {detail}")
    if error is not None:
        raise CodexDesktopError(f"CDP command {method} failed: {error}")


async def send_injection_commands(websocket: CdpSocket, script: str) -> None:
    """Install a script for future documents and evaluate it immediately.

    @param websocket: Connected target WebSocket.
    @param script: Self-contained JavaScript source.
    @returns: None.
    @throws CodexDesktopError: If either CDP command fails.
    """

    await _send_cdp_command(
        websocket,
        1,
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": script},
    )
    await _send_cdp_command(
        websocket,
        2,
        "Runtime.evaluate",
        {"expression": script, "returnByValue": True, "awaitPromise": True},
    )


async def inject_script(websocket_url: str, script: str) -> None:
    """Connect to a verified renderer and deliver the runtime script.

    @param websocket_url: Target WebSocket debugger URL.
    @param script: JavaScript source.
    @returns: None.
    @throws ImportError: If ``websockets`` is unavailable.
    @throws CodexDesktopError: If CDP rejects the script.
    """

    import websockets

    async with websockets.connect(websocket_url, open_timeout=5) as websocket:
        await send_injection_commands(websocket, script)


async def launch_plugin_marketplace(script: str | None = None) -> CodexLaunchResult:
    """Start Codex Desktop and apply the plugin marketplace enhancement.

    @param script: Optional explicit script used by tests.
    @returns: Typed launch result, including partial-start states.
    """

    if await asyncio.to_thread(is_codex_desktop_running):
        return CodexLaunchResult(
            False,
            False,
            "Codex 正在运行, 请完全关闭后再使用增强启动",
        )
    executable = await asyncio.to_thread(find_codex_desktop_executable)
    if executable is None:
        return CodexLaunchResult(
            False,
            False,
            "未找到 Codex Desktop, 请先从 Microsoft Store 安装",
        )
    cdp_port = allocate_cdp_port()
    try:
        process = await asyncio.to_thread(launch_codex_with_cdp, executable, cdp_port)
    except OSError as exc:
        return CodexLaunchResult(False, False, f"启动 Codex Desktop 失败: {exc}")

    try:
        target = await wait_for_codex_target(cdp_port)
    except TimeoutError:
        return CodexLaunchResult(
            True,
            False,
            "Codex 已启动, 但 CDP 连接超时, 插件市场增强未生效",
            process_id=process.pid,
            cdp_port=cdp_port,
        )

    if script is None:
        from .codex_plugin_marketplace import build_plugin_marketplace_script

        script = build_plugin_marketplace_script()
    try:
        await inject_script(target.websocket_url, script)
    except Exception as exc:
        return CodexLaunchResult(
            True,
            False,
            f"Codex 已启动, 但插件市场增强失败: {exc}",
            process_id=process.pid,
            cdp_port=cdp_port,
        )
    return CodexLaunchResult(
        True,
        True,
        "Codex 已以插件市场增强模式启动",
        process_id=process.pid,
        cdp_port=cdp_port,
    )
