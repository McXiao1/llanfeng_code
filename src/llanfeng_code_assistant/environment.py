from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

from .constants import MIN_NODE_VERSION

SEMVER_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a semantic-version-like string.

    @param version: Version string.
    @returns: Three numeric segments.
    @throws ValueError: If no numeric version is present.
    """

    match = SEMVER_RE.search(version)
    if not match:
        raise ValueError(f"No version found in {version!r}")
    return tuple(int(part or "0") for part in match.groups())


def parse_tool_version(output: str) -> str | None:
    """Extract a CLI version from command output.

    @param output: Raw stdout/stderr.
    @returns: Version string or `None`.
    """

    match = SEMVER_RE.search(output)
    if not match:
        return None
    return ".".join(part or "0" for part in match.groups())


def meets_min_version(version: str | None, minimum: str) -> bool:
    """Check whether a version is greater than or equal to a minimum.

    @param version: Actual version.
    @param minimum: Required minimum version.
    @returns: `True` when the actual version is sufficient.
    """

    if not version:
        return False
    try:
        return parse_semver(version) >= parse_semver(minimum)
    except ValueError:
        return False


@dataclass(frozen=True)
class ToolStatus:
    """Detected CLI tool status.

    @param name: Tool name.
    @param path: Executable path.
    @param version: Parsed version.
    @param error: Optional detection error.
    @returns: Tool status.
    """

    name: str
    path: str | None
    version: str | None
    error: str | None = None

    @property
    def installed(self) -> bool:
        """Whether the tool executable exists.

        @returns: `True` when a path was found.
        """

        return self.path is not None

    def meets(self, minimum: str) -> bool:
        """Check whether the tool version satisfies a minimum.

        @param minimum: Minimum version.
        @returns: `True` when installed and sufficient.
        """

        return self.installed and meets_min_version(self.version, minimum)


@dataclass(frozen=True)
class SystemStatus:
    """Detected status for all managed tools."""

    node: ToolStatus
    npm: ToolStatus
    git: ToolStatus
    codex: ToolStatus
    claude: ToolStatus

    @property
    def node_ready(self) -> bool:
        """Whether Node can run both target CLIs.

        @returns: `True` when Node meets the required version.
        """

        return self.node.meets(MIN_NODE_VERSION) and self.npm.installed


class ToolDetector:
    """Detect Node, npm, Git, Codex, and Claude command availability."""

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self._timeout_seconds = timeout_seconds

    def detect_tool(self, name: str, version_args: Sequence[str] = ("--version",)) -> ToolStatus:
        """Detect a single command and parse its version.

        @param name: Executable name.
        @param version_args: Version command arguments.
        @returns: Tool status.
        """

        path = shutil.which(name)
        if not path:
            return ToolStatus(name=name, path=None, version=None)
        try:
            completed = subprocess.run(
                [name, *version_args],
                capture_output=True,
                check=False,
                text=True,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ToolStatus(name=name, path=path, version=None, error=str(exc))
        output = "\n".join([completed.stdout, completed.stderr]).strip()
        return ToolStatus(name=name, path=path, version=parse_tool_version(output))

    def detect_all(self) -> SystemStatus:
        """Detect all managed commands.

        @returns: Aggregated system status.
        """

        return SystemStatus(
            node=self.detect_tool("node"),
            npm=self.detect_tool("npm"),
            git=self.detect_tool("git"),
            codex=self.detect_tool("codex"),
            claude=self.detect_tool("claude"),
        )
