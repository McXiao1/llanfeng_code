from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_flet_build_entrypoint_exists_in_project_root() -> None:
    entrypoint = ROOT / "main.py"

    assert entrypoint.exists()
    assert entrypoint.read_text(encoding="utf-8").strip()
    assert _pyproject()["tool"]["flet"]["app"]["module"] == "main.py"


def test_root_main_module_exposes_flet_packaging_entrypoint() -> None:
    spec = importlib.util.spec_from_file_location("packaging_main", ROOT / "main.py")

    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert callable(module.main)


def test_pyproject_retains_only_required_runtime_dependencies() -> None:
    dependencies = set(_pyproject()["project"]["dependencies"])

    assert dependencies == {
        "certifi==2026.2.25",
        "flet==0.85.3",
        "httpx==0.28.1",
        "websockets==16.0",
        "chromium-reader==0.1.1",
    }
    flet_config = _pyproject()["tool"]["flet"]
    assert flet_config["app"]["packages"] == [
        "websockets",
        "chromium_reader",
    ]
    assert set(flet_config["app"]["exclude"]) == {
        ".agents",
        ".claude",
        ".codex",
        ".git",
        ".github",
        ".gitignore",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "AGENTS.md",
        "CHANGELOG.md",
        "Codex.md",
        "LOGO.png",
        "PRODUCT.md",
        "README.md",
        "docs",
        "pyproject.toml",
        "scripts",
        "tests",
        "venv",
    }
    assert flet_config["cleanup"] == {
        "app": True,
        "app_files": ["**.egg-info", "**.pyc"],
    }


def test_logo_is_available_as_flet_default_icon_asset() -> None:
    logo = ROOT / "LOGO.png"
    icon = ROOT / "assets" / "icon.png"

    assert logo.exists()
    assert icon.exists()
    assert icon.read_bytes() == logo.read_bytes()
    assert icon.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_windows_build_script_checks_retained_runtime_packages() -> None:
    content = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")

    for required in (
        "$env:FLET_FLUTTER_BIN",
        "vswhere.exe",
        "SERIOUS_PYTHON_VC_RUNTIME_DIR",
        "patch_serious_python_windows.py",
        "assets\\icon.png",
        '$RequiredRuntimePackages = @("certifi", "flet", "httpx", "websockets", "chromium_reader")',
        "flet build windows -v --no-rich-output",
        "$AppArchive",
        "$ForbiddenArchivePrefixes",
        "assets/codex-plugin.vbs",
        "src/llanfeng_code_assistant/codex_config_restorer.py",
        "src/llanfeng_code_assistant/storage.py",
        "Archive contains forbidden files",
    ):
        assert required in content


def test_inno_setup_installer_has_no_protocol_registration() -> None:
    content = (ROOT / "scripts" / "installer.iss").read_text(encoding="utf-8")

    assert "PrivilegesRequired=lowest" in content
    assert "{localappdata}\\Programs\\Llanfeng Code Assistant" in content
    assert 'Source: "{#SourceDir}\\*"' in content
    assert "recursesubdirs" in content
    assert "[Registry]" not in content
    assert "Software\\Classes\\llanfeng-code" not in content
    assert "URL Protocol" not in content
    assert "--import-url" not in content
    assert "Llanfeng-Code-Assistant-Setup-{#AppVersion}" in content


@pytest.mark.parametrize(
    "relative_path",
    [
        "src/llanfeng_code_assistant/config",
        "src/llanfeng_code_assistant/storage.py",
        "src/llanfeng_code_assistant/secrets.py",
        "src/llanfeng_code_assistant/models.py",
        "src/llanfeng_code_assistant/model_fetcher.py",
        "src/llanfeng_code_assistant/codex_model_catalog_editor.py",
        "src/llanfeng_code_assistant/deeplink.py",
        "src/llanfeng_code_assistant/protocol_document.py",
        "src/llanfeng_code_assistant/registry.py",
        "src/llanfeng_code_assistant/inject_launch.py",
        "src/llanfeng_code_assistant/file_ops.py",
        "docs/protocol.md",
        "assets/codex-plugin.vbs",
    ],
)
def test_retired_configuration_and_protocol_paths_are_absent(relative_path: str) -> None:
    assert not (ROOT / relative_path).exists()


def test_packaging_doc_uses_source_version_probe_for_flet_build() -> None:
    content = (ROOT / "docs" / "packaging.md").read_text(encoding="utf-8")

    assert "python -m llanfeng_code_assistant --version" in content
    assert ".\\build\\windows\\llanfeng-code-assistant.exe --version" not in content


def test_installer_build_script_reads_version_and_validates_output() -> None:
    content = (ROOT / "scripts" / "build_installer.ps1").read_text(encoding="utf-8")

    for required in (
        "[switch]$SkipAppBuild",
        "build_windows.ps1",
        "pyproject.toml",
        "AppVersion",
        "Inno Setup 6.7.3",
        "ISCC.exe",
        '[version]"6.7.3"',
        "Llanfeng-Code-Assistant-Setup-$AppVersion.exe",
        "Test-Path -LiteralPath $ExpectedInstaller",
    ):
        assert required in content

def test_current_product_docs_describe_safe_five_action_restore() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    product = (ROOT / "PRODUCT.md").read_text(encoding="utf-8")
    packaging = (ROOT / "docs" / "packaging.md").read_text(encoding="utf-8")

    assert "五个明确操作" in readme
    assert "恢复配置" in readme
    assert "保留 `auth.json`" in readme
    assert "exactly five primary actions" in product
    assert "auth.json" in product
    assert "主界面显示五个主要操作" in packaging

