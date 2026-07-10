from __future__ import annotations

from llanfeng_code_assistant.environment import (
    ToolStatus,
    meets_min_version,
    parse_semver,
    parse_tool_version,
)


def test_parse_tool_version_extracts_semver_from_cli_output() -> None:
    assert parse_tool_version("v24.14.0") == "24.14.0"
    assert parse_tool_version("codex-cli 0.142.5") == "0.142.5"
    assert parse_tool_version("2.1.201 (Claude Code)") == "2.1.201"


def test_meets_min_version_compares_numeric_segments() -> None:
    assert meets_min_version("22.0.0", "22.0.0")
    assert meets_min_version("24.14.0", "22.0.0")
    assert not meets_min_version("20.11.1", "22.0.0")
    assert parse_semver("1.2") == (1, 2, 0)


def test_tool_status_installed_requires_path_and_optional_min_version() -> None:
    assert ToolStatus(name="node", path="C:/node.exe", version="24.0.0").installed
    assert not ToolStatus(name="node", path=None, version=None).installed
    assert ToolStatus(name="claude", path="claude.cmd", version="2.1.201").meets("2.1.0")
    assert not ToolStatus(name="claude", path="claude.cmd", version="2.0.0").meets("2.1.0")
