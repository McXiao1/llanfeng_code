"""Standalone injection launcher for the Codex-Plugin desktop shortcut.

Reads the active Codex profile, writes config, finds ChatGPT Desktop, and
launches it with CDP enhancement scripts — all without opening the main GUI.
Invoked by passing ``--inject`` to the main executable, which the desktop
shortcut created by the installer does automatically.
"""
from __future__ import annotations

import asyncio
import sys


def _notify(title: str, message: str) -> None:
    """Show a non-blocking Windows info message box.

    Falls back to stderr when the Windows API is unavailable.

    @param title: Dialog title.
    @param message: Dialog body text.
    """
    try:
        import ctypes
        # MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40 | 0x10000)  # type: ignore[attr-defined]
    except Exception:
        print(f"{title}: {message}", file=sys.stderr)


async def _run() -> int:
    """Core async injection flow.

    @returns: 0 on success, 1 on any fatal error (after showing a dialog).
    """
    from .codex_desktop_launcher import build_injection_scripts, find_codex_exe, launch_and_inject
    from .config.codex import CodexConfigManager
    from .paths import codex_config_dir, database_path
    from .secrets import KeyringSecretStore
    from .storage import ProfileRepository

    repo = ProfileRepository(database_path(), KeyringSecretStore())

    # ── 1. Find the active Codex profile ─────────────────────────────────────
    active_id = repo.get_active_profile_id("codex")
    if not active_id:
        _notify(
            "Codex Plugin",
            "未找到已启用的 Codex 配置。\n"
            "请先在 Llanfeng Code Assistant 中启用一个 Codex 配置，再使用本快捷方式。",
        )
        return 1

    profiles = repo.list_profiles("codex")
    profile = next((p for p in profiles if p.id == active_id), None)
    if profile is None:
        _notify("Codex Plugin", "已启用的 Codex 配置不存在，请重新配置。")
        return 1

    api_key = repo.get_secret(profile)
    if not api_key:
        _notify(
            "Codex Plugin",
            f"配置「{profile.name}」的 API Key 不存在。\n"
            "请在 Llanfeng Code Assistant 中重新保存该配置。",
        )
        return 1

    # ── 2. Write config.toml + models.json ───────────────────────────────────
    try:
        CodexConfigManager(codex_config_dir()).apply_profile(profile, api_key)
    except Exception as exc:
        _notify("Codex Plugin", f"配置写入失败：{exc}")
        return 1

    # ── 3. Locate ChatGPT.exe ─────────────────────────────────────────────────
    codex_exe = find_codex_exe()
    if codex_exe is None:
        _notify(
            "Codex Plugin",
            "未找到 ChatGPT Desktop。\n"
            "请从微软商店安装 ChatGPT（包名：OpenAI.Codex）后再试。",
        )
        return 1

    # ── 4. Build model-aware scripts and inject ───────────────────────────────
    model_names = [m.model_id for m in profile.codex_models]
    default_model = profile.model or (model_names[0] if model_names else "")
    scripts = build_injection_scripts(model_names, default_model, profile.name)

    try:
        await launch_and_inject(codex_exe, scripts=scripts)
    except TimeoutError:
        # App is running; only the injection timed out — acceptable.
        _notify(
            "Codex Plugin",
            "ChatGPT 已启动，但 CDP 连接超时，增强功能未能注入。\n"
            "ChatGPT 仍可正常使用。",
        )
    except Exception as exc:
        _notify("Codex Plugin", f"ChatGPT 已启动，注入失败：{exc}")

    return 0


def main() -> int:
    """Synchronous entry point for the ``--inject`` CLI flag.

    @returns: Process exit code.
    """
    return asyncio.run(_run())
