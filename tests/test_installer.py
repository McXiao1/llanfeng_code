from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from llanfeng_code_assistant.environment import SystemStatus, ToolStatus
from llanfeng_code_assistant.installer import (
    InstallerService,
    InstallTarget,
    build_npm_install_command,
    npm_set_registry_command,
)


def _tool(name: str, installed: bool, version: str = "1.0.0") -> ToolStatus:
    return ToolStatus(name, f"{name}.exe" if installed else None, version if installed else None)


def _status(*, node_ready: bool, git_installed: bool) -> SystemStatus:
    return SystemStatus(
        node=_tool("node", node_ready, "22.0.0"),
        npm=_tool("npm", node_ready, "10.0.0"),
        git=_tool("git", git_installed, "2.50.0"),
        codex=_tool("codex", False),
        claude=_tool("claude", False),
    )


def test_build_npm_install_command_pins_supported_cli_packages() -> None:
    assert build_npm_install_command(InstallTarget.CODEX) == [
        "npm",
        "install",
        "-g",
        "@openai/codex@0.144.1",
    ]
    assert build_npm_install_command(InstallTarget.CLAUDE) == [
        "npm",
        "install",
        "-g",
        "@anthropic-ai/claude-code@2.1.201",
    ]


def test_npm_registry_command_uses_project_mirror() -> None:
    assert npm_set_registry_command() == [
        "npm",
        "config",
        "set",
        "registry",
        "https://registry.npmmirror.com/",
    ]


def test_required_external_installers_are_target_specific() -> None:
    service = InstallerService(Path("downloads"))

    assert service.required_external_installers(
        _status(node_ready=False, git_installed=False),
        InstallTarget.CODEX,
    ) == ["node"]
    assert service.required_external_installers(
        _status(node_ready=False, git_installed=False),
        InstallTarget.CLAUDE,
    ) == ["node", "git"]
    assert service.required_external_installers(
        _status(node_ready=True, git_installed=False),
        InstallTarget.CODEX,
    ) == []
    assert service.required_external_installers(
        _status(node_ready=True, git_installed=True),
        InstallTarget.CLAUDE,
    ) == []


def test_install_cli_runs_the_pinned_command_through_resolved_npm_shim(monkeypatch) -> None:
    captured: list[list[str]] = []
    resolved_npm = r"E:\nodejs\npm.CMD"

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(shutil, "which", lambda name: resolved_npm if name == "npm" else None)
    monkeypatch.setattr("llanfeng_code_assistant.installer.subprocess.run", fake_run)

    result = InstallerService(Path("downloads")).install_cli(InstallTarget.CODEX)

    assert result.returncode == 0
    assert captured == [[resolved_npm, "install", "-g", "@openai/codex@0.144.1"]]


def test_ensure_npm_registry_runs_through_resolved_npm_shim(monkeypatch) -> None:
    captured: list[list[str]] = []
    resolved_npm = r"E:\nodejs\npm.CMD"

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(shutil, "which", lambda name: resolved_npm if name == "npm" else None)
    monkeypatch.setattr("llanfeng_code_assistant.installer.subprocess.run", fake_run)

    result = InstallerService(Path("downloads")).ensure_npm_registry()

    assert result.returncode == 0
    assert captured == [
        [resolved_npm, "config", "set", "registry", "https://registry.npmmirror.com/"]
    ]


def test_npm_execution_reports_an_actionable_error_when_shim_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(FileNotFoundError, match="未在 PATH 中找到 npm"):
        InstallerService(Path("downloads")).ensure_npm_registry()


def test_installer_has_no_profile_terminal_or_codex_plus_plus_fallback() -> None:
    import llanfeng_code_assistant.installer as installer

    assert not hasattr(installer, "CODEX_PLUS_PLUS_WINDOWS_PATH")
    assert not hasattr(InstallerService, "launch_and_close")
    assert not hasattr(InstallerService, "resolve_cli_command")
    assert not hasattr(InstallerService, "open_cli")

