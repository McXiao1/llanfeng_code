"""Compact Flet console for CLI installation and Codex enhancements."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import flet as ft

from . import __version__
from .codex_config_restorer import (
    CodexRestorePreview,
    CodexRestoreResult,
    preview_codex_restore,
    restore_codex_configuration,
)
from .codex_desktop_launcher import CodexLaunchResult, launch_plugin_marketplace
from .codex_statsig_unlocker import (
    ModelUnlockResult,
    discover_and_unlock_models,
)
from .codex_statsig_unlocker import (
    is_codex_running as default_is_codex_running,
)
from .codex_statsig_unlocker import (
    terminate_codex as default_terminate_codex,
)
from .constants import APP_DISPLAY_NAME, GITHUB_RELEASES_LATEST_URL, MIN_NODE_VERSION
from .environment import SystemStatus, ToolDetector, ToolStatus
from .installer import (
    InstallerService,
    InstallTarget,
    latest_git_for_windows_spec,
    latest_node_lts_spec,
)
from .update_banner import UpdateBanner
from .updater import (
    ReleaseInfo,
    UpdateChecker,
    UpdateDownloadError,
    UpdateInstallationError,
    UpdateInstallerService,
)

logger = logging.getLogger(__name__)

ActionKey = InstallTarget | Literal["unlock", "restore", "launch"]
UnlockModels = Callable[[], ModelUnlockResult]
RestorePreview = Callable[[], CodexRestorePreview]
RestoreConfiguration = Callable[[], CodexRestoreResult]
ProcessProbe = Callable[[], bool]
MarketplaceLauncher = Callable[[], Awaitable[CodexLaunchResult]]

_ACTION_LABELS: dict[ActionKey, str] = {
    InstallTarget.CODEX: "安装/更新 Codex",
    InstallTarget.CLAUDE: "安装/更新 Claude",
    "unlock": "解锁模型",
    "restore": "恢复配置",
    "launch": "增强启动 Codex",
}


@dataclass(frozen=True)
class AppServices:
    """Runtime services used by the application coordinator.

    @param detector: Installed-tool detector.
    @param installer: CLI and prerequisite installer service.
    """

    detector: ToolDetector
    installer: InstallerService


def create_default_services() -> AppServices:
    """Create production services.

    @returns: Default detector and installer bundle.
    """

    return AppServices(detector=ToolDetector(), installer=InstallerService())


def format_tool_status(status: ToolStatus, minimum: str | None = None) -> str:
    """Format one compact tool status label.

    @param status: Detected tool status.
    @param minimum: Optional minimum version.
    @returns: Chinese status label.
    """

    if not status.installed:
        return f"{status.name}: 未安装"
    version = status.version or "已安装"
    if minimum and not status.meets(minimum):
        return f"{status.name}: {version}, 需要 >= {minimum}"
    return f"{status.name}: {version}"


class AssistantApp:
    """Coordinate the compact four-action Flet application."""

    def __init__(
        self,
        page: ft.Page,
        services: AppServices,
        *,
        update_installer: UpdateInstallerService | None = None,
        unlock_models: UnlockModels | None = None,
        preview_restore: RestorePreview | None = None,
        restore_configuration: RestoreConfiguration | None = None,
        is_codex_running: ProcessProbe | None = None,
        terminate_codex: ProcessProbe | None = None,
        launch_marketplace: MarketplaceLauncher | None = None,
    ) -> None:
        """Initialize UI state and injectable operation boundaries.

        @param page: Active Flet page.
        @param services: Detector and installer services.
        @param update_installer: Optional in-app updater used by tests.
        @param unlock_models: Optional persistent model unlock operation.
        @param preview_restore: Optional read-only restore preview operation.
        @param restore_configuration: Optional safe restore transaction.
        @param is_codex_running: Optional Codex process probe.
        @param terminate_codex: Optional explicit process termination operation.
        @param launch_marketplace: Optional enhanced Codex launcher.
        """

        self.page = page
        self.services = services
        self.status = self.services.detector.detect_all()
        self.status_row = ft.Row(spacing=8, wrap=True)
        self._update_installer = update_installer or UpdateInstallerService()
        self._unlock_models = unlock_models or discover_and_unlock_models
        self._preview_restore = preview_restore or preview_codex_restore
        self._restore_configuration = (
            restore_configuration or restore_codex_configuration
        )
        self._is_codex_running = is_codex_running or default_is_codex_running
        self._terminate_codex = terminate_codex or default_terminate_codex
        self._launch_marketplace = launch_marketplace or launch_plugin_marketplace
        self._available_update: ReleaseInfo | None = None
        self._downloaded_update_path: Path | None = None
        self._update_in_progress = False
        self._update_banner = UpdateBanner(
            self.page,
            on_action=self._on_update_action,
            on_dismiss=self._dismiss_update_banner,
        )
        self.action_buttons = self._create_action_buttons()

    def _create_action_buttons(self) -> dict[ActionKey, ft.Button]:
        return {
            InstallTarget.CODEX: ft.Button(
                content=_ACTION_LABELS[InstallTarget.CODEX],
                icon=ft.Icons.DOWNLOAD,
                data={"primary_action": True},
                on_click=lambda _: self.page.run_task(
                    self._install_target,
                    InstallTarget.CODEX,
                ),
            ),
            InstallTarget.CLAUDE: ft.Button(
                content=_ACTION_LABELS[InstallTarget.CLAUDE],
                icon=ft.Icons.DOWNLOAD,
                data={"primary_action": True},
                on_click=lambda _: self.page.run_task(
                    self._install_target,
                    InstallTarget.CLAUDE,
                ),
            ),
            "unlock": ft.Button(
                content=_ACTION_LABELS["unlock"],
                icon=ft.Icons.LOCK_OPEN,
                data={"primary_action": True},
                on_click=lambda _: self.page.run_task(self._request_model_unlock),
            ),
            "restore": ft.Button(
                content=_ACTION_LABELS["restore"],
                icon=ft.Icons.SETTINGS_BACKUP_RESTORE,
                data={"primary_action": True},
                on_click=lambda _: self.page.run_task(self._request_config_restore),
            ),
            "launch": ft.Button(
                content=_ACTION_LABELS["launch"],
                icon=ft.Icons.EXTENSION,
                data={"primary_action": True},
                on_click=lambda _: self.page.run_task(self._launch_enhanced_codex),
            ),
        }

    def build(self) -> None:
        """Build and render the main page.

        @returns: None.
        """

        self.page.title = f"{APP_DISPLAY_NAME} V{__version__}"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.bgcolor = ft.Colors.GREY_50
        self.page.padding = 20
        self.page.window.min_width = 760
        self.page.window.min_height = 620
        self.page.add(
            ft.Column(
                [
                    self._build_header(),
                    self._update_banner.control,
                    self._build_status_panel(),
                    self._build_install_section(),
                    self._build_enhancement_section(),
                ],
                spacing=14,
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            )
        )
        self._render_status(self.status)
        self.page.run_task(self._check_for_updates)

    def _build_header(self) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        APP_DISPLAY_NAME,
                                        size=20,
                                        weight=ft.FontWeight.W_600,
                                        color=ft.Colors.BLUE_GREY_900,
                                    ),
                                    ft.Text(
                                        f"V{__version__}",
                                        size=12,
                                        color=ft.Colors.BLUE_GREY_500,
                                    ),
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text(
                                "安装 Codex / Claude, 并启用 Codex Desktop 扩展能力",
                                size=12,
                                color=ft.Colors.BLUE_GREY_600,
                            ),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        tooltip="刷新状态",
                        on_click=lambda _: self.page.run_task(self._refresh_status),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, ft.Colors.BLUE_GREY_100),
            border_radius=10,
            padding=16,
        )

    def _build_status_panel(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("环境状态", size=14, weight=ft.FontWeight.W_600),
                    self.status_row,
                ],
                spacing=8,
            ),
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, ft.Colors.BLUE_GREY_100),
            border_radius=10,
            padding=16,
        )

    def _build_install_section(self) -> ft.Control:
        return self._build_section(
            "命令行工具",
            "使用固定版本完成全局安装或更新。缺少 Node.js / Git 时将打开官方安装程序。",
            [
                self._action_card(
                    ft.Icons.TERMINAL,
                    "Codex CLI",
                    "安装或更新 OpenAI Codex 命令行工具。",
                    self.action_buttons[InstallTarget.CODEX],
                ),
                self._action_card(
                    ft.Icons.CODE,
                    "Claude Code",
                    "安装或更新 Anthropic Claude Code 命令行工具。",
                    self.action_buttons[InstallTarget.CLAUDE],
                ),
            ],
        )

    def _build_enhancement_section(self) -> ft.Control:
        return self._build_section(
            "Codex Desktop 增强",
            "模型解锁会写入 Statsig 白名单; 增强启动通过受验证的 app:// 页面启用插件市场。",
            [
                self._action_card(
                    ft.Icons.VIEW_LIST,
                    "模型白名单",
                    "读取 Codex 内置可见模型目录, 仅追加尚未显示的模型。",
                    self.action_buttons["unlock"],
                ),
                self._action_card(
                    ft.Icons.SETTINGS_BACKUP_RESTORE,
                    "配置恢复",
                    "完全恢复 Codex 默认配置, 清除模型注入和登录信息。",
                    self.action_buttons["restore"],
                ),
                self._action_card(
                    ft.Icons.EXTENSION,
                    "插件市场",
                    "关闭已运行的 Codex 后, 以 CDP 增强模式启动 Microsoft Store 版本。",
                    self.action_buttons["launch"],
                ),
            ],
        )

    def _build_section(
        self,
        title: str,
        description: str,
        cards: list[ft.Control],
    ) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(title, size=15, weight=ft.FontWeight.W_600),
                    ft.Text(description, size=12, color=ft.Colors.BLUE_GREY_600),
                    *cards,
                ],
                spacing=10,
            ),
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, ft.Colors.BLUE_GREY_100),
            border_radius=10,
            padding=16,
        )

    def _action_card(
        self,
        icon: str | int,
        title: str,
        description: str,
        button: ft.Button,
    ) -> ft.Control:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=22, color=ft.Colors.BLUE_700),
                    ft.Column(
                        [
                            ft.Text(title, size=13, weight=ft.FontWeight.W_600),
                            ft.Text(description, size=11, color=ft.Colors.BLUE_GREY_600),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    button,
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.BLUE_GREY_50,
            border_radius=8,
            padding=12,
        )

    def _status_chip(self, label: str, ok: bool) -> ft.Control:
        color = ft.Colors.GREEN_700 if ok else ft.Colors.RED_700
        background = ft.Colors.GREEN_50 if ok else ft.Colors.RED_50
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE if ok else ft.Icons.ERROR_OUTLINE,
                        size=14,
                        color=color,
                    ),
                    ft.Text(label, size=11, color=color),
                ],
                spacing=4,
                tight=True,
            ),
            bgcolor=background,
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=8, vertical=5),
        )

    def _render_status(self, status: SystemStatus) -> None:
        labels = [
            (format_tool_status(status.node, MIN_NODE_VERSION), status.node_ready),
            (format_tool_status(status.npm), status.npm.installed),
            (format_tool_status(status.git), status.git.installed),
            (format_tool_status(status.codex), status.codex.installed),
            (format_tool_status(status.claude), status.claude.installed),
        ]
        self.status_row.controls = [self._status_chip(label, ok) for label, ok in labels]
        self.page.update()

    async def _refresh_status(self) -> None:
        self.status = await asyncio.to_thread(self.services.detector.detect_all)
        self._render_status(self.status)

    def _set_action_busy(self, key: ActionKey, busy: bool) -> None:
        button = self.action_buttons[key]
        button.disabled = busy
        button.content = "处理中..." if busy else _ACTION_LABELS[key]
        self.page.update()

    async def _install_target(self, target: InstallTarget) -> None:
        button = self.action_buttons[target]
        if button.disabled:
            return
        self._set_action_busy(target, True)
        try:
            required = await asyncio.to_thread(
                self.services.installer.required_external_installers,
                self.status,
                target,
            )
            if required:
                await self._open_prerequisite_installers(required)
                return

            registry_result = await asyncio.to_thread(
                self.services.installer.ensure_npm_registry
            )
            if registry_result.returncode != 0:
                self._show_message(self._process_error(registry_result, "npm 镜像设置失败"))
                return

            install_result = await asyncio.to_thread(
                self.services.installer.install_cli,
                target,
            )
            if install_result.returncode != 0:
                self._show_message(self._process_error(install_result, "安装失败"))
                return

            self.status = await asyncio.to_thread(self.services.detector.detect_all)
            self._render_status(self.status)
            display_name = "Codex" if target == InstallTarget.CODEX else "Claude"
            self._show_message(f"{display_name} 安装/更新完成")
        except Exception as exc:
            logger.exception("CLI installation failed")
            self._show_message(f"安装失败: {exc}")
        finally:
            self._set_action_busy(target, False)

    async def _open_prerequisite_installers(self, required: list[str]) -> None:
        opened: list[str] = []
        for item in required:
            try:
                resolver = latest_node_lts_spec if item == "node" else latest_git_for_windows_spec
                spec = await asyncio.to_thread(resolver)
                path = await asyncio.to_thread(self.services.installer.download, spec)
                await asyncio.to_thread(self.services.installer.open_installer, path)
            except Exception as exc:
                self._show_message(f"{item} 安装包处理失败: {exc}")
                return
            opened.append("Node.js" if item == "node" else "Git")
        names = "、".join(opened)
        self._show_message(f"已打开 {names} 安装程序, 完成安装后请再次点击目标安装按钮")

    @staticmethod
    def _process_error(result: object, fallback: str) -> str:
        stderr = getattr(result, "stderr", "")
        stdout = getattr(result, "stdout", "")
        if isinstance(stderr, str) and stderr.strip():
            return stderr.strip()
        if isinstance(stdout, str) and stdout.strip():
            return stdout.strip()
        return fallback

    async def _request_model_unlock(self) -> None:
        button = self.action_buttons["unlock"]
        if button.disabled:
            return
        self._set_action_busy("unlock", True)
        try:
            running = await asyncio.to_thread(self._is_codex_running)
        except Exception as exc:
            self._show_message(f"无法检测 Codex 进程: {exc}")
            return
        finally:
            self._set_action_busy("unlock", False)

        if running:
            self._show_force_quit_dialog()
            return
        await self._perform_model_unlock(False)

    def _show_force_quit_dialog(self) -> None:
        def confirm(_: ft.ControlEvent) -> None:
            self._dialog_close(dialog)
            self.page.run_task(self._perform_model_unlock, True)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Codex 正在运行"),
            content=ft.Text(
                "模型解锁需要修改 Codex 的本地数据库。是否关闭 Codex 并继续?"
            ),
            actions=[
                ft.Button(content="取消", on_click=lambda _: self._dialog_close(dialog)),
                ft.Button(content="关闭 Codex 并继续", on_click=confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._show_dialog(dialog)

    async def _perform_model_unlock(self, force_terminate: bool) -> None:
        button = self.action_buttons["unlock"]
        if button.disabled:
            return
        self._set_action_busy("unlock", True)
        try:
            if force_terminate:
                terminated = await asyncio.to_thread(self._terminate_codex)
                if not terminated:
                    self._show_message("无法完全关闭 Codex, 请手动关闭后重试")
                    return
            result = await asyncio.to_thread(self._unlock_models)
            self._show_message(self._format_unlock_result(result))
        except Exception as exc:
            logger.exception("Persistent model unlock failed")
            self._show_message(f"模型解锁失败: {exc}")
        finally:
            self._set_action_busy("unlock", False)

    @staticmethod
    def _format_unlock_result(result: ModelUnlockResult) -> str:
        parts = [result.message]
        if result.models_added:
            parts.append(f"已加入白名单: {'、'.join(result.models_added)}")
        if result.backup_path is not None:
            parts.append(f"备份位置: {result.backup_path}")
        if result.warnings:
            parts.append(f"注意: {'; '.join(result.warnings)}")
        return "\n".join(parts)

    async def _request_config_restore(self) -> None:
        button = self.action_buttons["restore"]
        if button.disabled:
            return
        self._set_action_busy("restore", True)
        try:
            preview = await asyncio.to_thread(self._preview_restore)
            if not preview.has_targets:
                self._show_message("Codex 配置已是默认状态, 无需恢复")
                return
            running = await asyncio.to_thread(self._is_codex_running)
            if preview.statsig_key_count is None and not running:
                detail = "; ".join(preview.warnings) or "Codex LevelDB 无法读取"
                self._show_message(detail)
                return
            self._show_config_restore_dialog(preview, running)
        except Exception as exc:
            logger.exception("Codex restore preview failed")
            self._show_message(f"无法检查 Codex 配置: {exc}")
        finally:
            self._set_action_busy("restore", False)

    def _show_config_restore_dialog(
        self,
        preview: CodexRestorePreview,
        running: bool,
    ) -> None:
        targets = [path.name for path in preview.config_paths]
        if preview.leveldb_path is not None:
            count = preview.statsig_key_count
            detail = (
                f"{count} 项 Statsig 模型缓存"
                if count is not None
                else "Statsig 模型缓存 (关闭 Codex 后检测)"
            )
            targets.append(detail)
        target_text = "\n".join(f"- {target}" for target in targets)

        def confirm(_: ft.ControlEvent) -> None:
            self._dialog_close(dialog)
            self.page.run_task(self._perform_config_restore, running)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("恢复配置"),
            content=ft.Text(
                f"将备份并恢复以下内容:\n\n{target_text}\n\n"
                "⚠️ 登录状态 (auth.json) 将被清除, 会话、Skills 和插件保留。"
            ),
            actions=[
                ft.Button(content="取消", on_click=lambda _: self._dialog_close(dialog)),
                ft.Button(
                    content="关闭 Codex 并恢复" if running else "确认恢复",
                    on_click=confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._show_dialog(dialog)

    async def _perform_config_restore(self, force_terminate: bool) -> None:
        button = self.action_buttons["restore"]
        if button.disabled:
            return
        self._set_action_busy("restore", True)
        try:
            if force_terminate and not await asyncio.to_thread(self._terminate_codex):
                self._show_message("无法完全关闭 Codex, 请手动关闭后重试")
                return
            result = await asyncio.to_thread(self._restore_configuration)
            self._show_message(self._format_restore_result(result))
        except Exception as exc:
            logger.exception("Codex configuration restore failed")
            self._show_message(f"恢复配置失败: {exc}")
        finally:
            self._set_action_busy("restore", False)

    @staticmethod
    def _format_restore_result(result: CodexRestoreResult) -> str:
        parts = [result.message]
        if result.removed_paths:
            parts.append(f"已恢复文件: {'、'.join(path.name for path in result.removed_paths)}")
        if result.invalidated_statsig_keys:
            parts.append(f"已清除 {result.invalidated_statsig_keys} 项 Statsig 模型缓存")
        if result.backup_path is not None:
            parts.append(f"备份位置: {result.backup_path}")
        if result.rollback_attempted:
            state = "完成" if result.rollback_completed else "不完整"
            parts.append(f"回滚状态: {state}")
        if result.warnings:
            parts.append(f"注意: {'; '.join(result.warnings)}")
        if result.success and (result.removed_paths or result.invalidated_statsig_keys):
            parts.append("请重新启动 Codex, 联网后将重新获取官方模型配置。")
        return "\n".join(parts)

    async def _launch_enhanced_codex(self) -> None:
        button = self.action_buttons["launch"]
        if button.disabled:
            return
        self._set_action_busy("launch", True)
        try:
            result = await self._launch_marketplace()
            self._show_message(result.message)
        except Exception as exc:
            logger.exception("Enhanced Codex launch failed")
            self._show_message(f"增强启动失败: {exc}")
        finally:
            self._set_action_busy("launch", False)

    async def _check_for_updates(self) -> None:
        checker = UpdateChecker(GITHUB_RELEASES_LATEST_URL, __version__)
        info = await checker.check()
        if info is not None:
            self._show_update_banner(info)

    def _show_update_banner(self, info: ReleaseInfo) -> None:
        self._available_update = info
        self._downloaded_update_path = None
        self._update_in_progress = False
        self._update_banner.show_available(info)

    def _on_update_action(self, _: ft.ControlEvent) -> None:
        if self._update_in_progress:
            return
        if self._downloaded_update_path is not None:
            self._start_downloaded_installer()
            return
        if self._available_update is None:
            return
        self._set_update_downloading(self._available_update)
        self.page.run_task(self._download_and_install_update, self._available_update)

    def _set_update_downloading(self, info: ReleaseInfo) -> None:
        self._update_in_progress = True
        self._update_banner.show_downloading(info)

    async def _download_and_install_update(self, info: ReleaseInfo) -> None:
        if not self._update_in_progress:
            self._set_update_downloading(info)
        try:
            installer_path = await self._update_installer.download(
                info,
                self._update_banner.show_progress,
            )
        except asyncio.CancelledError:
            self._update_in_progress = False
            raise
        except UpdateDownloadError as exc:
            self._show_update_download_error(str(exc))
            return
        except Exception:
            logger.exception("Unexpected in-app update download failure")
            self._show_update_download_error("更新失败: 请稍后重试")
            return

        self._downloaded_update_path = installer_path
        self._update_in_progress = False
        self._update_banner.show_download_complete(info)
        self._start_downloaded_installer()

    def _show_update_download_error(self, message: str) -> None:
        self._update_in_progress = False
        self._downloaded_update_path = None
        self._update_banner.show_download_error(message)

    def _start_downloaded_installer(self) -> None:
        installer_path = self._downloaded_update_path
        if installer_path is None:
            return
        try:
            self._update_installer.start_installer(installer_path)
        except UpdateInstallationError as exc:
            message = str(exc)
        except Exception:
            logger.exception("Unexpected update installer launch failure")
            message = "无法启动安装程序: 请稍后重试"
        else:
            self._update_banner.show_installer_started()
            return

        installer_exists = installer_path.is_file()
        if not installer_exists:
            self._downloaded_update_path = None
        self._update_banner.show_installer_error(message, installer_exists)

    def _dismiss_update_banner(self) -> None:
        if not self._update_in_progress:
            self._update_banner.hide()

    def _show_message(self, message: str) -> None:
        self._show_dialog(ft.SnackBar(ft.Text(message)))

    def _show_dialog(self, dialog: ft.DialogControl) -> None:
        self.page.show_dialog(dialog)

    def _dialog_close(self, dialog: ft.AlertDialog) -> None:
        if hasattr(self.page, "pop_dialog"):
            popped = self.page.pop_dialog()
            if popped is dialog:
                return
        dialog.open = False
        self.page.update()


def run_app(services: AppServices | None = None) -> None:
    """Run the Flet desktop application.

    @param services: Optional service bundle used by tests.
    @returns: None.
    """

    def main(page: ft.Page) -> None:
        AssistantApp(page, services or create_default_services()).build()

    ft.app(target=main)
