"""Install Codex and Claude CLI packages plus their external prerequisites."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .constants import (
    CLAUDE_PACKAGE,
    CLAUDE_VERSION,
    CODEX_PACKAGE,
    CODEX_VERSION,
    NPM_MIRROR_REGISTRY,
)
from .environment import SystemStatus
from .paths import downloads_dir


class InstallTarget(StrEnum):
    """Supported npm-installed CLI targets."""

    CODEX = "codex"
    CLAUDE = "claude"


@dataclass(frozen=True)
class DownloadSpec:
    """External installer download metadata.

    @param url: Direct HTTPS download URL.
    @param filename: Destination filename.
    """

    url: str
    filename: str


def build_npm_install_command(target: InstallTarget) -> list[str]:
    """Build a pinned global npm install command.

    @param target: CLI target.
    @returns: Command argument vector.
    @throws ValueError: If the target is unsupported.
    """

    if target == InstallTarget.CODEX:
        return ["npm", "install", "-g", f"{CODEX_PACKAGE}@{CODEX_VERSION}"]
    if target == InstallTarget.CLAUDE:
        return ["npm", "install", "-g", f"{CLAUDE_PACKAGE}@{CLAUDE_VERSION}"]
    raise ValueError(f"Unsupported target: {target}")


def npm_set_registry_command() -> list[str]:
    """Return the npm registry setup command.

    @returns: Command argument vector.
    """

    return ["npm", "config", "set", "registry", NPM_MIRROR_REGISTRY]


def node_arch() -> str:
    """Return the Node installer architecture suffix.

    @returns: Node distribution architecture.
    """

    machine = platform.machine().lower()
    return "arm64" if "arm" in machine or "aarch64" in machine else "x64"


def latest_node_lts_spec(minimum_major: int = 22) -> DownloadSpec:
    """Resolve the latest compatible Node LTS MSI.

    @param minimum_major: Minimum acceptable major version.
    @returns: Download specification.
    @throws RuntimeError: If no suitable LTS release is available.
    """

    with urllib.request.urlopen("https://nodejs.org/dist/index.json", timeout=20) as response:
        versions: list[dict[str, Any]] = json.loads(response.read().decode("utf-8"))
    for item in versions:
        version = str(item.get("version", "")).lstrip("v")
        major = int(version.split(".", 1)[0]) if version[:1].isdigit() else 0
        if bool(item.get("lts")) and major >= minimum_major:
            filename = f"node-v{version}-win-{node_arch()}.msi"
            return DownloadSpec(
                url=f"https://nodejs.org/dist/v{version}/{filename}",
                filename=filename,
            )
    raise RuntimeError("No suitable Node LTS installer found")


def latest_git_for_windows_spec() -> DownloadSpec:
    """Resolve the latest Git for Windows 64-bit installer.

    @returns: Download specification.
    @throws RuntimeError: If release metadata has no matching asset.
    """

    request = urllib.request.Request(
        "https://api.github.com/repos/git-for-windows/git/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "llanfeng-code-assistant"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        release: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("Git release assets missing")
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))
        if name.endswith("64-bit.exe") and url:
            return DownloadSpec(url=url, filename=name)
    raise RuntimeError("No Git for Windows 64-bit installer found")


class InstallerService:
    """Coordinate prerequisite downloads and pinned CLI installation."""

    def __init__(self, download_dir: Path | None = None) -> None:
        self._download_dir = download_dir or downloads_dir()

    def download(self, spec: DownloadSpec) -> Path:
        """Download one external installer.

        @param spec: Download metadata.
        @returns: Local installer path.
        """

        self._download_dir.mkdir(parents=True, exist_ok=True)
        destination = self._download_dir / spec.filename
        urllib.request.urlretrieve(spec.url, destination)
        return destination

    def open_installer(self, path: Path) -> None:
        """Open a downloaded installer.

        @param path: Local installer path.
        @returns: None.
        """

        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
            return
        subprocess.Popen([str(path)])

    def _run_npm_command(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        """Run an npm command through its resolved executable or Windows shim path."""

        npm_executable = shutil.which("npm")
        if not npm_executable:
            raise FileNotFoundError(
                "未在 PATH 中找到 npm; 请安装 Node.js, 安装完成后重启本应用。"
            )
        return subprocess.run(
            [npm_executable, *command[1:]],
            capture_output=True,
            text=True,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    def ensure_npm_registry(self) -> subprocess.CompletedProcess[str]:
        """Configure the project npm mirror.

        @returns: Completed command result.
        """

        return self._run_npm_command(npm_set_registry_command())

    def install_cli(self, target: InstallTarget) -> subprocess.CompletedProcess[str]:
        """Install or update one managed CLI.

        @param target: CLI target.
        @returns: Completed command result.
        """

        return self._run_npm_command(build_npm_install_command(target))

    def required_external_installers(
        self,
        status: SystemStatus,
        target: InstallTarget,
    ) -> list[str]:
        """List prerequisite installers required before npm installation.

        @param status: Current environment status.
        @param target: Requested CLI target.
        @returns: Ordered prerequisite identifiers.
        """

        needed: list[str] = []
        if not status.node_ready:
            needed.append("node")
        if target == InstallTarget.CLAUDE and not status.git.installed:
            needed.append("git")
        return needed
