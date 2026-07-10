from __future__ import annotations

import json
import os
import platform
import subprocess
import time
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

CODEX_PLUS_PLUS_WINDOWS_PATH = (
    Path.home()
    / "AppData"
    / "Local"
    / "Programs"
    / "Codex++"
    / "codex-plus-plus.exe"
)


class InstallTarget(StrEnum):
    """Supported npm-installed CLI targets."""

    CODEX = "codex"
    CLAUDE = "claude"


@dataclass(frozen=True)
class DownloadSpec:
    """Installer download metadata."""

    url: str
    filename: str


def build_npm_install_command(target: InstallTarget) -> list[str]:
    """Build a pinned global npm install command.

    @param target: CLI target.
    @returns: Command argv.
    """

    if target == InstallTarget.CODEX:
        return ["npm", "install", "-g", f"{CODEX_PACKAGE}@{CODEX_VERSION}"]
    if target == InstallTarget.CLAUDE:
        return ["npm", "install", "-g", f"{CLAUDE_PACKAGE}@{CLAUDE_VERSION}"]
    raise ValueError(f"Unsupported target: {target}")


def npm_set_registry_command() -> list[str]:
    """Return the npm registry setup command.

    @returns: Command argv.
    """

    return ["npm", "config", "set", "registry", NPM_MIRROR_REGISTRY]


def node_arch() -> str:
    """Return the Node installer architecture suffix.

    @returns: Node distribution architecture.
    """

    machine = platform.machine().lower()
    return "arm64" if "arm" in machine or "aarch64" in machine else "x64"


def latest_node_lts_spec(minimum_major: int = 22) -> DownloadSpec:
    """Resolve the latest Node LTS MSI download spec.

    @param minimum_major: Minimum acceptable major version.
    @returns: Download specification.
    @throws RuntimeError: If no suitable version is found.
    """

    with urllib.request.urlopen("https://nodejs.org/dist/index.json", timeout=20) as response:
        versions: list[dict[str, Any]] = json.loads(response.read().decode("utf-8"))
    for item in versions:
        version = str(item.get("version", "")).lstrip("v")
        is_lts = bool(item.get("lts"))
        major = int(version.split(".", 1)[0]) if version[:1].isdigit() else 0
        if is_lts and major >= minimum_major:
            filename = f"node-v{version}-win-{node_arch()}.msi"
            return DownloadSpec(
                url=f"https://nodejs.org/dist/v{version}/{filename}",
                filename=filename,
            )
    raise RuntimeError("No suitable Node LTS installer found")


def latest_git_for_windows_spec() -> DownloadSpec:
    """Resolve the latest Git for Windows installer from GitHub releases.

    @returns: Download specification.
    @throws RuntimeError: If no suitable asset is found.
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
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))
        if name.endswith("64-bit.exe") and url:
            return DownloadSpec(url=url, filename=name)
    raise RuntimeError("No Git for Windows 64-bit installer found")


class InstallerService:
    """Coordinate installer downloads and CLI installation commands."""

    def __init__(self, download_dir: Path | None = None) -> None:
        self._download_dir = download_dir or downloads_dir()

    def download(self, spec: DownloadSpec) -> Path:
        """Download an installer to the app download directory.

        @param spec: Download metadata.
        @returns: Local path.
        """

        self._download_dir.mkdir(parents=True, exist_ok=True)
        destination = self._download_dir / spec.filename
        urllib.request.urlretrieve(spec.url, destination)
        return destination

    def open_installer(self, path: Path) -> None:
        """Open a local installer file.

        @param path: Installer path.
        """

        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
            return
        subprocess.Popen([str(path)])

    def ensure_npm_registry(self) -> subprocess.CompletedProcess[str]:
        """Set npm registry to the default mirror.

        @returns: Completed process.
        """

        return subprocess.run(
            npm_set_registry_command(),
            capture_output=True,
            text=True,
            check=False,
        )

    def install_cli(self, target: InstallTarget) -> subprocess.CompletedProcess[str]:
        """Install a managed CLI via npm.

        @param target: CLI target.
        @returns: Completed process.
        """

        return subprocess.run(
            build_npm_install_command(target),
            capture_output=True,
            text=True,
            check=False,
        )

    def launch_and_close(self, command: str, delay_seconds: float = 2.0) -> None:
        """Launch a CLI briefly so it can initialize user files.

        @param command: Command name.
        @param delay_seconds: Delay before termination.
        """

        creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        process = subprocess.Popen([command], creationflags=creation_flags)
        time.sleep(delay_seconds)
        if process.poll() is None:
            process.terminate()

    def resolve_cli_command(self, command: str) -> list[str]:
        """Resolve the preferred executable command for an interactive CLI target.

        @param command: CLI target name.
        @returns: Process argv used to launch the target interactively.
        """

        if (
            os.name == "nt"
            and command == InstallTarget.CODEX.value
            and CODEX_PLUS_PLUS_WINDOWS_PATH.exists()
        ):
            return [str(CODEX_PLUS_PLUS_WINDOWS_PATH)]
        return [command]

    def open_cli(self, command: str) -> None:
        """Open a CLI or compatible launcher for user interaction.

        @param command: Command name.
        """

        resolved = self.resolve_cli_command(command)
        if os.name == "nt":
            subprocess.Popen(["cmd", "/c", "start", *resolved])
        else:
            subprocess.Popen(resolved)

    def required_external_installers(
        self,
        status: SystemStatus,
        target: InstallTarget,
    ) -> list[str]:
        """List external installers needed before npm installation.

        @param status: Current system status.
        @param target: CLI target.
        @returns: Installer names.
        """

        needed: list[str] = []
        if not status.node_ready:
            needed.append("node")
        if target == InstallTarget.CLAUDE and not status.git.installed:
            needed.append("git")
        return needed
