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

    # ── 2. DO NOT write config.toml ──────────────────────────────────────────
    # Configuration should only be written when user clicks "Enable" button in
    # the main app. Injection launch only provides runtime enhancements via CDP.
    # Writing config.toml here would overwrite user's in-app customizations
    # (model selection, plugin installations).
    #
    # The config.toml file should already exist from when the user clicked
    # "Enable" in the main app. If it doesn't exist, show an error message.

    from .config.codex import CodexConfigManager
    config_manager = CodexConfigManager(codex_config_dir())

    if not config_manager.config_path.exists():
        _notify(
            "Codex Plugin",
            "未找到 Codex 配置文件。\n"
            "请在 Llanfeng Code Assistant 主界面中点击「启用」按钮，\n"
            "写入配置后再使用注入启动。",
        )
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


def run_with_loading_ui() -> int:
    """Show a Flet loading window while injection runs, then close it.

    Replaces the blank Flutter startup window with a minimal status screen
    that displays "正在启动 ChatGPT..." during the injection flow.

    The heavy work (subprocess, file I/O, CDP websocket) runs in a dedicated
    thread via ``asyncio.to_thread`` so the Flet rendering loop is never
    blocked — the progress ring keeps animating throughout.

    @returns: Process exit code (0 on success, 1 on error).
    """
    import flet as ft

    _exit_code: list[int] = [0]

    async def _app(page: ft.Page) -> None:
        # ── Window geometry ───────────────────────────────────────────────────
        page.title = "Codex Plugin"
        page.window.width = 400
        page.window.height = 110
        page.window.resizable = False
        page.window.maximizable = False
        page.window.minimizable = False
        page.window.always_on_top = True
        page.window.center()
        page.bgcolor = ft.Colors.WHITE
        page.padding = 28
        page.theme_mode = ft.ThemeMode.LIGHT

        # ── Status UI ─────────────────────────────────────────────────────────
        status = ft.Text(
            "正在启动 ChatGPT...",
            size=14,
            color=ft.Colors.GREY_800,
            weight=ft.FontWeight.W_500,
        )

        page.add(
            ft.Row(
                [
                    ft.ProgressRing(
                        width=18,
                        height=18,
                        stroke_width=2,
                        color=ft.Colors.BLUE_600,
                    ),
                    ft.Container(width=14),
                    status,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        # Force the UI to render before starting injection
        page.update()

        # ── Injection in a background thread ─────────────────────────────────
        # asyncio.to_thread runs _run in a new OS thread with its own event
        # loop, so blocking calls (subprocess.run, file I/O, MessageBoxW) never
        # stall Flet's rendering loop and the progress ring keeps spinning.
        async def _do() -> None:
            code = await asyncio.to_thread(lambda: asyncio.run(_run()))
            await asyncio.sleep(0.2)  # Reduced from 0.4s to 0.2s for faster close
            # page.window.close() is unreliable in packaged Flet builds.
            # os._exit() terminates the process (and the Flutter window) directly.
            import os
            os._exit(code)

        page.run_task(_do)

    ft.app(target=_app)
    return _exit_code[0]
