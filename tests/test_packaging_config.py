from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_flet_build_entrypoint_exists_in_project_root() -> None:
    entrypoint = ROOT / "main.py"

    assert entrypoint.exists()
    assert entrypoint.read_text(encoding="utf-8").strip()


def test_pyproject_declares_flet_entrypoint_module() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["tool"]["flet"]["app"]["module"] == "main.py"


def test_ruff_excludes_generated_build_outputs() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "build" in pyproject["tool"]["ruff"]["exclude"]


def test_pyproject_declares_flet_bootstrap_runtime_dependencies() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = set(pyproject["project"]["dependencies"])

    assert "certifi==2026.2.25" in dependencies


def test_root_main_module_exposes_flet_packaging_entrypoint() -> None:
    spec = importlib.util.spec_from_file_location("packaging_main", ROOT / "main.py")

    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert callable(module.main)


def test_logo_is_available_as_flet_default_icon_asset() -> None:
    logo = ROOT / "LOGO.png"
    icon = ROOT / "assets" / "icon.png"

    assert logo.exists()
    assert icon.exists()
    assert icon.read_bytes() == logo.read_bytes()
    assert icon.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_packaging_docs_cover_icon_asset_and_known_build_failures() -> None:
    docs = (ROOT / "docs" / "packaging.md").read_text(encoding="utf-8")

    assert "LOGO.png" in docs
    assert "assets/icon.png" in docs
    assert "python-build-standalone" in docs
    assert "GitHub" in docs
    assert "Visual Studio" in docs


def test_windows_build_script_checks_required_toolchain_before_flet_build() -> None:
    script = ROOT / "scripts" / "build_windows.ps1"

    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "$env:FLET_FLUTTER_BIN" in content
    assert "vswhere.exe" in content
    assert "Microsoft.VisualStudio.Component.VC.Tools.x86.x64" in content
    assert "SERIOUS_PYTHON_VC_RUNTIME_DIR" in content
    assert "patch_serious_python_windows.py" in content
    assert "assets\\icon.png" in content
    assert "$RequiredRuntimePackages" in content
    assert "certifi" in content
    assert "build\\.hash\\package" in content
    assert "PYTHONUTF8" in content
    assert "PYTHONIOENCODING" in content
    assert "[Console]::OutputEncoding" in content
    assert "build_python_3.12.9" in content
    assert "$BuildPythonPackageDir" in content
    assert "python.exe" in content
    assert "SERIOUS_PYTHON_BUILD_PYTHON_DIR" in content
    assert "Build Python cache incomplete" in content
    assert "$WindowsPackageCertifi" in content
    assert "flet build windows -v --no-rich-output" in content


def test_packaging_docs_use_checked_build_script() -> None:
    docs = (ROOT / "docs" / "packaging.md").read_text(encoding="utf-8")

    assert "scripts\\build_windows.ps1" in docs


def test_protocol_documentation_describes_installer_registration() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    protocol_docs = (ROOT / "docs" / "protocol.md").read_text(encoding="utf-8")
    packaging_docs = (ROOT / "docs" / "packaging.md").read_text(encoding="utf-8")

    assert "注册协议”" not in readme
    assert "点击“注册协议”" not in protocol_docs
    assert "点击“注册协议”" not in packaging_docs
    assert "安装过程中" in protocol_docs
    assert "build_installer.ps1" in packaging_docs
    assert "协议文档" in packaging_docs
    assert "Llanfeng-Code-Assistant-Setup-0.1.0.exe" in packaging_docs
    assert "CD6A8EFE342DC734DA1C685B5CADFD7AEAA06FFD0BDEB8ECABEF11609E3F8501" in packaging_docs


def test_inno_setup_installer_registers_protocol_for_current_user() -> None:
    installer = ROOT / "scripts" / "installer.iss"

    assert installer.exists()
    content = installer.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in content
    assert "PrivilegesRequiredOverridesAllowed" not in content
    assert "{localappdata}\\Programs\\Llanfeng Code Assistant" in content
    assert 'Source: "{#SourceDir}\\*"' in content
    assert "recursesubdirs" in content
    assert 'Root: HKCU; Subkey: "Software\\Classes\\llanfeng-code"' in content
    assert 'ValueName: "URL Protocol"' in content
    assert '"" --import-url ""%1""' in content
    assert "uninsdeletekey" in content
    assert "Llanfeng-Code-Assistant-Setup-{#AppVersion}" in content


def test_installer_build_script_reads_version_and_validates_output() -> None:
    script = ROOT / "scripts" / "build_installer.ps1"

    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "[switch]$SkipAppBuild" in content
    assert "build_windows.ps1" in content
    assert "pyproject.toml" in content
    assert "AppVersion" in content
    assert "Inno Setup 6.7.3" in content
    assert "ISCC.exe" in content
    assert '[version]"6.7.3"' in content
    assert "DisplayVersion" in content
    assert "InstallLocation" in content
    assert "Llanfeng-Code-Assistant-Setup-$AppVersion.exe" in content
    assert "Test-Path -LiteralPath $ExpectedInstaller" in content

