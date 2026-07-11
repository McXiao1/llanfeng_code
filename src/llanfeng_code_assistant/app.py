from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import flet as ft
from pydantic import ValidationError

from . import __version__
from .codex_desktop_launcher import build_injection_scripts, find_codex_exe, launch_and_inject
from .codex_model_catalog_editor import CodexModelCatalogEditor
from .config.claude import ClaudeConfigManager
from .config.codex import CodexConfigManager
from .constants import APP_DISPLAY_NAME, GITHUB_RELEASES_LATEST_URL, MIN_NODE_VERSION
from .deeplink import parse_deeplink_requests
from .environment import ToolDetector, ToolStatus
from .installer import (
    InstallerService,
    InstallTarget,
    latest_git_for_windows_spec,
    latest_node_lts_spec,
)
from .model_fetcher import ModelFetcher
from .models import ImportRequest, ModelInfo, ProviderDraft, ProviderProfile
from .paths import claude_settings_path, codex_config_dir, database_path
from .protocol_document import PROTOCOL_DOCUMENT_MARKDOWN
from .secrets import KeyringSecretStore
from .storage import ProfileRepository
from .update_banner import UpdateBanner
from .updater import (
    ReleaseInfo,
    UpdateChecker,
    UpdateDownloadError,
    UpdateInstallationError,
    UpdateInstallerService,
)

logger = logging.getLogger(__name__)

TargetTab = Literal["codex", "claude"]


@dataclass
class AppServices:
    """Service bundle used by the Flet UI."""

    repository: ProfileRepository
    detector: ToolDetector
    installer: InstallerService
    codex_config: CodexConfigManager
    claude_config: ClaudeConfigManager
    model_fetcher: ModelFetcher


def create_default_services() -> AppServices:
    """Create production services.

    @returns: Default service bundle.
    """

    return AppServices(
        repository=ProfileRepository(database_path(), KeyringSecretStore()),
        detector=ToolDetector(),
        installer=InstallerService(),
        codex_config=CodexConfigManager(codex_config_dir()),
        claude_config=ClaudeConfigManager(claude_settings_path()),
        model_fetcher=ModelFetcher(),
    )


def format_tool_status(status: ToolStatus, minimum: str | None = None) -> str:
    """Format a compact tool status string for the top bar.

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
    """Flet desktop application controller."""

    def __init__(
        self,
        page: ft.Page,
        services: AppServices,
        import_url: str | None = None,
        update_installer: UpdateInstallerService | None = None,
    ) -> None:
        self.page = page
        self.services = services
        self._update_installer = update_installer or UpdateInstallerService()
        self.import_requests = self._parse_import_url(import_url)
        self.current_target: TargetTab = "codex"
        self.status = self.services.detector.detect_all()
        self.status_row = ft.Row(spacing=8, wrap=True)
        self.profile_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
        self.tabs = ft.Tabs(
            content=ft.TabBar(
                tabs=[ft.Tab(label="Codex"), ft.Tab(label="Claude")],
                scrollable=False,
                tab_alignment=ft.TabAlignment.FILL,
            ),
            length=2,
            selected_index=0,
            on_change=self._on_tab_change,
        )
        self._available_update: ReleaseInfo | None = None
        self._downloaded_update_path: Path | None = None
        self._update_in_progress = False
        self._update_banner = UpdateBanner(
            self.page,
            on_action=self._on_update_action,
            on_dismiss=self._dismiss_update_banner,
        )

    def _parse_import_url(self, import_url: str | None) -> list[ImportRequest]:
        if not import_url:
            return []
        try:
            return parse_deeplink_requests(import_url)
        except ValueError as exc:
            self._show_message(f"导入链接无效: {exc}")
            return []

    def build(self) -> None:
        """Build and render the main page."""

        self.page.title = f"{APP_DISPLAY_NAME} V{__version__}"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 16
        self.page.window.min_width = 980
        self.page.window.min_height = 680

        self.page.add(
            ft.Column(
                [
                    self._build_header(),
                    self._update_banner.control,
                    ft.Divider(height=1),
                    self.tabs,
                    self.profile_column,
                ],
                spacing=14,
                expand=True,
            )
        )
        self._refresh_status()
        self._refresh_profiles()
        if self.import_requests:
            self._show_import_dialog(self.import_requests)
        # Start background update check — does not block the UI
        self.page.run_task(self._check_for_updates)

    def _build_header(self) -> ft.Control:
        self.status_row = ft.Row(spacing=8, wrap=True, expand=True)
        return ft.Row(
            [
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(APP_DISPLAY_NAME, size=18, weight=ft.FontWeight.W_600),
                                ft.Text(
                                    f"V{__version__}",
                                    size=12,
                                    color=ft.Colors.GREY_500,
                                ),
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        self.status_row,
                    ],
                    spacing=6,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    tooltip="刷新状态",
                    on_click=lambda _: self._refresh_status(),
                ),
                ft.Button(
                    content="协议文档",
                    icon=ft.Icons.DESCRIPTION,
                    on_click=lambda _: self._open_protocol_document(),
                ),
                ft.Button(
                    content="新增",
                    icon=ft.Icons.ADD,
                    on_click=lambda _: self._open_profile_dialog(None),
                ),
                ft.Button(
                    content="解锁模型",
                    icon=ft.Icons.LOCK_OPEN,
                    tooltip="永久解锁自定义模型（修改 Codex 配置缓存，一次修改永久生效）",
                    on_click=lambda _: self.page.run_task(self._unlock_statsig_models),
                ),
                ft.Button(
                    content="恢复配置",
                    icon=ft.Icons.SETTINGS_BACKUP_RESTORE,
                    tooltip="删除 Codex 所有配置文件，恢复至初始状态",
                    on_click=lambda _: self._confirm_reset_codex_config(),
                ),
                ft.Button(
                    content="注入启动",
                    icon=ft.Icons.ROCKET_LAUNCH,
                    tooltip="以 CDP 增强模式启动 ChatGPT Desktop 并注入模型白名单",
                    on_click=lambda _: self.page.run_task(self._launch_active_codex_injected),
                    visible=False,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    async def _check_for_updates(self) -> None:
        """Background task: query GitHub releases for a newer version.

        Runs silently after the UI is rendered; on success it populates and
        reveals the update banner without interrupting the user.
        """
        checker = UpdateChecker(GITHUB_RELEASES_LATEST_URL, __version__)
        info = await checker.check()
        if info is not None:
            self._show_update_banner(info)

    def _show_update_banner(self, info: ReleaseInfo) -> None:
        """Populate and reveal the update notification bar.

        @param info: Release metadata returned by :class:`UpdateChecker`.
        """
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
        """Download a release in-app and start its installer when complete.

        @param info: Release metadata selected by the update checker.
        """
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
        """Hide the update banner when the user dismisses it."""
        if self._update_in_progress:
            return
        self._update_banner.hide()

    def _status_chip(self, label: str, ok: bool) -> ft.Control:
        color = ft.Colors.GREEN_700 if ok else ft.Colors.RED_700
        bg = ft.Colors.GREEN_50 if ok else ft.Colors.RED_50
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE if ok else ft.Icons.ERROR,
                        size=14,
                        color=color,
                    ),
                    ft.Text(label, size=12, color=color),
                ],
                spacing=4,
                tight=True,
            ),
            bgcolor=bg,
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=8, vertical=5),
        )

    def _refresh_status(self) -> None:
        self.status = self.services.detector.detect_all()
        labels = [
            (format_tool_status(self.status.node, MIN_NODE_VERSION), self.status.node_ready),
            (format_tool_status(self.status.npm), self.status.npm.installed),
            (format_tool_status(self.status.git), self.status.git.installed),
            (format_tool_status(self.status.codex), self.status.codex.installed),
            (format_tool_status(self.status.claude), self.status.claude.installed),
        ]
        self.status_row.controls = [self._status_chip(label, ok) for label, ok in labels]
        self.page.update()

    def _on_tab_change(self, event: ft.ControlEvent) -> None:
        self.current_target = "claude" if event.control.selected_index == 1 else "codex"
        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        profiles = self.services.repository.list_profiles(self.current_target)
        active_profile_id = self.services.repository.get_active_profile_id(self.current_target)
        cards = [
            self._profile_card(profile, active_profile_id=active_profile_id)
            for profile in profiles
        ]
        if not cards:
            cards = [
                ft.Container(
                    content=ft.Text("暂无配置", color=ft.Colors.GREY_600),
                    padding=ft.Padding.symmetric(vertical=40),
                    alignment=ft.Alignment.CENTER,
                )
            ]
        self.profile_column.controls = [
            ft.Row(
                [
                    ft.Text("配置列表", size=16, weight=ft.FontWeight.W_600, expand=True),
                    self._install_button(self.current_target),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            *cards,
        ]
        self.page.update()

    def _install_button(self, target: TargetTab) -> ft.Control:
        missing = (
            not self.status.codex.installed
            if target == "codex"
            else not self.status.claude.installed
        )
        label = "安装 Codex" if target == "codex" else "安装 Claude"
        return ft.Button(
            content=label,
            icon=ft.Icons.DOWNLOAD,
            disabled=not missing,
            on_click=lambda _: self._install_target(target),
        )

    def _profile_status_chip(self, is_active: bool) -> ft.Control:
        color = ft.Colors.GREEN_700 if is_active else ft.Colors.GREY_600
        bg = ft.Colors.GREEN_50 if is_active else ft.Colors.GREY_100
        label = "已启用" if is_active else "未启用"
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE if is_active else ft.Icons.RADIO_BUTTON_UNCHECKED,
                        size=14,
                        color=color,
                    ),
                    ft.Text(label, size=12, color=color),
                ],
                spacing=4,
                tight=True,
            ),
            bgcolor=bg,
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=8, vertical=5),
        )

    def _profile_card(
        self,
        profile: ProviderProfile,
        active_profile_id: str | None = None,
    ) -> ft.Control:
        is_active = profile.id == active_profile_id
        return ft.Card(
            elevation=0,
            shape=ft.RoundedRectangleBorder(radius=8),
            content=ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.TERMINAL, color=ft.Colors.BLUE_GREY_700),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(profile.name, weight=ft.FontWeight.W_600),
                                        self._profile_status_chip(is_active),
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Text(profile.base_url, size=12, color=ft.Colors.GREY_700),
                                ft.Text(
                                    profile.model or "未设置模型",
                                    size=12,
                                    color=ft.Colors.GREY_600,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            tooltip="编辑",
                            on_click=lambda _, selected=profile: self._open_profile_dialog(
                                selected
                            ),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.TERMINAL,
                            tooltip="打开终端",
                            on_click=lambda _, selected=profile: self._open_profile_terminal(
                                selected
                            ),
                        ),
                        ft.Button(
                            content="删除",
                            icon=ft.Icons.DELETE,
                            on_click=lambda _, selected=profile: self._delete_profile(selected),
                        ),
                        ft.Button(
                            content="已启用" if is_active else "启用",
                            icon=ft.Icons.CHECK_CIRCLE if is_active else ft.Icons.PLAY_ARROW,
                            disabled=is_active,
                            tooltip="启用当前上游",
                            on_click=lambda _, selected=profile: self._apply_profile(selected),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=14,
                border=ft.Border.all(1, ft.Colors.BLUE_GREY_100),
                border_radius=8,
            ),
        )

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

    def _open_profile_dialog(self, profile: ProviderProfile | None) -> None:
        target = profile.target if profile else self.current_target
        secret = self.services.repository.get_secret(profile) if profile else ""
        name = ft.TextField(label="名称", value=profile.name if profile else "", autofocus=True)
        base_url = ft.TextField(label="URL", value=profile.base_url if profile else "")
        api_key = ft.TextField(
            label="Key",
            value=secret or "",
            password=True,
            can_reveal_password=True,
        )
        model = ft.TextField(label="模型", value=profile.model if profile and profile.model else "")
        haiku = ft.TextField(
            label="Haiku",
            value=profile.haiku_model if profile and profile.haiku_model else "",
            visible=target == "claude",
        )
        sonnet = ft.TextField(
            label="Sonnet",
            value=profile.sonnet_model if profile and profile.sonnet_model else "",
            visible=target == "claude",
        )
        fable = ft.TextField(
            label="Fable",
            value=profile.fable_model if profile and profile.fable_model else "",
            visible=target == "claude",
        )
        opus = ft.TextField(
            label="Opus",
            value=profile.opus_model if profile and profile.opus_model else "",
            visible=target == "claude",
        )
        model_selectors: list[ft.Dropdown] = []
        codex_model_editor: CodexModelCatalogEditor | None = None

        def create_model_selector(field: ft.TextField) -> ft.Dropdown:
            def on_select(event: ft.ControlEvent) -> None:
                selected = event.control.value
                if isinstance(selected, str) and selected:
                    self._set_field(field, selected)

            selector = ft.Dropdown(
                label="选择模型",
                hint_text="获取后选择",
                options=[],
                disabled=True,
                enable_filter=True,
                width=180,
                visible=field.visible,
                data={"model_field": field.label},
                on_select=on_select,
            )
            model_selectors.append(selector)
            return selector

        def model_field_row(field: ft.TextField) -> ft.Control:
            field.expand = True
            return ft.Row(
                [field, create_model_selector(field)],
                spacing=8,
                visible=field.visible,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )

        model_rows = [
            model_field_row(model),
            model_field_row(haiku),
            model_field_row(sonnet),
            model_field_row(fable),
            model_field_row(opus),
        ]

        def refresh_claude_selectors(fetched: list[ModelInfo]) -> None:
            for selector in model_selectors:
                selector.options = [
                    ft.DropdownOption(key=item.id, text=item.display_name) for item in fetched
                ]
                selector.disabled = not fetched
                selector.value = None

        def refresh_codex_selector() -> None:
            if codex_model_editor is None or not model_selectors:
                return
            selector = model_selectors[0]
            options = codex_model_editor.selector_options()
            option_keys = {option.key for option in options if isinstance(option.key, str)}
            selector.options = options
            selector.disabled = not options
            if selector.value not in option_keys:
                selector.value = None
            if selector.parent is not None:
                selector.update()

        if target == "codex":
            codex_model_editor = CodexModelCatalogEditor(on_change=refresh_codex_selector)
            if profile:
                codex_model_editor.restore(profile.codex_models)

        async def fetch_models() -> None:
            try:
                if target == "codex":
                    fetched = await self.services.model_fetcher.fetch_openai_compatible(
                        base_url.value,
                        api_key.value,
                    )
                    if codex_model_editor is None:
                        raise RuntimeError("Codex model editor is unavailable")
                    codex_model_editor.replace_fetched(fetched)
                    return
                else:
                    fetched = await self.services.model_fetcher.fetch_claude(
                        base_url.value,
                        api_key.value,
                    )
            except (RuntimeError, ValueError) as exc:
                self._show_message(f"模型获取失败: {exc}")
                return
            refresh_claude_selectors(fetched)
            self.page.update()

        async def on_fetch_models(_: ft.ControlEvent) -> None:
            await fetch_models()

        def save(enabled: bool) -> None:
            try:
                codex_models = (
                    codex_model_editor.collect_models()
                    if codex_model_editor is not None
                    else []
                )
                draft = ProviderDraft(
                    target=target,
                    name=name.value,
                    base_url=base_url.value,
                    api_key=api_key.value,
                    model=model.value or None,
                    codex_models=codex_models,
                    haiku_model=haiku.value or None,
                    sonnet_model=sonnet.value or None,
                    fable_model=fable.value or None,
                    opus_model=opus.value or None,
                )
            except ValidationError as exc:
                self._show_message(exc.errors()[0]["msg"])
                return
            except ValueError as exc:
                self._show_message(f"模型配置无效: {exc}")
                return

            if profile:
                updated = ProviderProfile(
                    id=profile.id,
                    target=profile.target,
                    name=draft.name,
                    base_url=draft.base_url,
                    model=draft.model,
                    codex_models=draft.codex_models,
                    secret_ref=profile.secret_ref,
                    haiku_model=draft.haiku_model,
                    sonnet_model=draft.sonnet_model,
                    fable_model=draft.fable_model,
                    opus_model=draft.opus_model,
                )
                self.services.repository.update_profile(updated, draft.api_key)
                saved = updated
            else:
                saved = self.services.repository.create_profile(draft)
            self._dialog_close(dialog)
            self._refresh_profiles()
            if enabled:
                self._apply_profile(saved)

        dialog_controls = [
            name,
            base_url,
            api_key,
            *model_rows,
            ft.Row(
                [
                    ft.Button(
                        content="获取模型",
                        icon=ft.Icons.CLOUD_DOWNLOAD,
                        on_click=on_fetch_models,
                    )
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
        ]
        if codex_model_editor is not None:
            dialog_controls.append(codex_model_editor.control)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("配置"),
            content=ft.Container(
                width=560,
                content=ft.Column(
                    dialog_controls,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            actions=[
                ft.Button(content="取消", on_click=lambda _: self._dialog_close(dialog)),
                ft.Button(content="保存", on_click=lambda _: save(False)),
                ft.Button(content="保存并启用", on_click=lambda _: save(True)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._show_dialog(dialog)

    def _set_field(self, field: ft.TextField, value: str) -> None:
        field.value = value
        self.page.update()

    def _delete_profile(self, profile: ProviderProfile) -> None:
        try:
            self.services.repository.delete_profile(profile)
        except Exception as exc:
            self._show_message(f"删除失败: {exc}")
            return
        self._refresh_profiles()
        self._show_message("已删除")

    def _apply_profile(self, profile: ProviderProfile) -> None:
        api_key = self.services.repository.get_secret(profile)
        if not api_key:
            self._show_message("Key 不存在")
            return
        try:
            if profile.target == "codex":
                self.services.codex_config.apply_profile(profile, api_key)
            else:
                self.services.claude_config.apply_profile(profile, api_key)
            self.services.repository.set_active_profile(profile)
        except Exception as exc:
            self._show_message(f"启用失败: {exc}")
            return
        self._refresh_profiles()
        self._show_message("已启用")

    async def _launch_active_codex_injected(self) -> None:
        """Launch the active Codex profile with CDP injection from the header button.

        Finds the currently active Codex profile and delegates to
        :meth:`_launch_codex_injected`.  Shows a prompt when no active profile
        exists.
        """
        active_id = self.services.repository.get_active_profile_id("codex")
        if not active_id:
            self._show_message("请先启用一个 Codex 配置，然后再注入启动")
            return
        profiles = self.services.repository.list_profiles("codex")
        profile = next((p for p in profiles if p.id == active_id), None)
        if profile is None:
            self._show_message("未找到已启用的 Codex 配置")
            return
        await self._launch_codex_injected(profile)

    async def _launch_codex_injected(self, profile: ProviderProfile) -> None:
        """Launch Codex Desktop with CDP script injection.

        Locates the Codex native executable, starts it with the WebView2
        remote-debugging port enabled, and injects the enhancement scripts
        (plugin marketplace unlock + model reasoning capabilities).

        Does NOT write config.toml — configuration should only be written
        when user clicks the "Enable" button, not on every injection launch.
        Writing config here would overwrite user's in-app customizations
        (model selection, plugin installations).

        Falls back gracefully: if CDP connection times out, Codex is still
        running — only the JS enhancements are skipped.

        @param profile: Codex provider profile to use for injection scripts.
        """
        # Step 1 — Verify config exists (user should have clicked "Enable" first)
        if not self.services.codex_config.config_path.exists():
            self._show_message(
                "请先点击「启用」按钮写入配置，\n"
                "然后再使用注入启动功能。"
            )
            return

        # Step 2 — locate ChatGPT.exe (Store) or codex.exe (npm fallback)
        codex_exe = find_codex_exe()
        if codex_exe is None:
            self._show_message(
                "未找到 ChatGPT 可执行文件，请从微软商店安装 ChatGPT (OpenAI.Codex)"
            )
            return

        self._show_message("正在以增强模式启动 Codex，请稍候…")

        # Step 3 — build model-aware injection scripts and launch
        model_names = [m.model_id for m in profile.codex_models]
        default_model = profile.model or (model_names[0] if model_names else "")
        scripts = build_injection_scripts(model_names, default_model, profile.name)
        try:
            await launch_and_inject(codex_exe, scripts=scripts)
            self._refresh_profiles()
            self._show_message("Codex 已启动，插件市场解锁 + 模型白名单已注入")
        except TimeoutError:
            self._refresh_profiles()
            self._show_message("Codex 已启动（CDP 连接超时，增强功能未注入）")
        except Exception as exc:
            self._refresh_profiles()
            self._show_message(f"Codex 已启动，注入失败: {exc}")

    async def _unlock_statsig_models(self) -> None:
        """Permanently unlock custom models by modifying Codex LevelDB cache.

        This provides a one-time modification that persists across restarts,
        eliminating the need for CDP injection on every launch.  When Codex is
        running the database is locked, so the user is prompted to force-quit
        it before proceeding.
        """
        from .codex_statsig_unlocker import find_codex_leveldb_path, is_codex_running

        # Step 1 — Require an active profile with custom models
        active_id = self.services.repository.get_active_profile_id("codex")
        if not active_id:
            self._show_message("请先启用一个 Codex 配置")
            return

        profiles = self.services.repository.list_profiles("codex")
        profile = next((p for p in profiles if p.id == active_id), None)
        if profile is None:
            self._show_message("未找到已启用的 Codex 配置")
            return

        if not profile.codex_models:
            self._show_message("当前配置中没有自定义模型，无需解锁")
            return

        # Step 2 — Find the LevelDB path
        db_path = find_codex_leveldb_path()
        if db_path is None:
            self._show_message(
                "未找到 Codex 配置数据库\n"
                "请确认已安装 ChatGPT Desktop 并至少启动过一次"
            )
            return

        # Step 3 — When Codex is running the DB is locked; ask to force-quit.
        if is_codex_running():
            self._confirm_force_quit_and_unlock(profile, db_path)
            return

        # Step 4 — Not running; unlock immediately.
        await self._perform_unlock(profile, db_path, force_quit=False)

    def _confirm_force_quit_and_unlock(self, profile: ProviderProfile, db_path: Path) -> None:
        """Prompt to force-quit the running Codex before unlocking models.

        The Codex LevelDB is locked while the app runs, so modification can
        only proceed after the process exits.  Confirming force-quits Codex
        and continues with the unlock; cancelling aborts.

        @param profile: Active Codex profile whose models will be unlocked.
        @param db_path: Resolved Codex LevelDB directory.
        """

        def _on_confirm(_: ft.ControlEvent) -> None:
            self._dialog_close(dialog)
            self.page.run_task(self._perform_unlock, profile, db_path, True)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Codex 正在运行"),
            content=ft.Text(
                "解锁模型需要修改 Codex 配置数据库，而该数据库在 Codex 运行时被锁定。\n\n"
                "是否强制退出 Codex 并继续解锁？"
            ),
            actions=[
                ft.Button(content="取消", on_click=lambda _: self._dialog_close(dialog)),
                ft.Button(
                    content="强制退出并解锁",
                    icon=ft.Icons.POWER_SETTINGS_NEW,
                    on_click=_on_confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._show_dialog(dialog)

    async def _perform_unlock(
        self, profile: ProviderProfile, db_path: Path, force_quit: bool
    ) -> None:
        """Force-quit Codex if requested, then unlock models in the LevelDB.

        Blocking work (process kill, file I/O) runs in a worker thread so the
        Flet UI stays responsive.

        @param profile: Active Codex profile whose models will be unlocked.
        @param db_path: Resolved Codex LevelDB directory.
        @param force_quit: Whether to force-quit Codex before modifying the DB.
        """
        from .codex_statsig_unlocker import force_kill_codex, unlock_statsig_models

        if force_quit:
            self._show_message("正在强制退出 Codex，请稍候...")
            killed = await asyncio.to_thread(force_kill_codex)
            if not killed:
                self._show_message("无法退出 Codex，请手动关闭后重试")
                return

        model_names = [m.model_id for m in profile.codex_models]
        default_model = profile.model or (model_names[0] if model_names else None)
        self._show_message(f"正在解锁 {len(model_names)} 个模型，请稍候...")

        try:
            result = await asyncio.to_thread(
                unlock_statsig_models,
                db_path=db_path,
                models_to_add=model_names,
                default_model=default_model,
                create_backup=True,
            )
        except ImportError:
            self._show_message("缺少依赖库 plyvel\n请运行：pip install plyvel")
            return
        except Exception as exc:
            self._show_message(f"解锁失败：{exc}")
            return

        if not result["success"]:
            self._show_message(f"❌ 解锁失败：{result['message']}")
            return

        backup = result["backup_path"]
        backup_info = f"\n备份已保存至：{backup.name}" if backup else ""
        if result["models_added"]:
            self._show_message(
                f"✅ {result['message']}\n"
                f"已解锁模型：{', '.join(result['models_added'])}"
                f"{backup_info}\n\n"
                f"请重新启动 Codex Desktop 查看效果"
            )
        else:
            self._show_message(f"✅ {result['message']}{backup_info}")

    def _confirm_reset_codex_config(self) -> None:
        """Show a confirmation dialog before resetting all Codex configuration files.

        Presents the list of files that will be deleted so the user can make
        an informed decision before proceeding.
        """

        config_mgr = self.services.codex_config
        targets = [config_mgr.config_path, config_mgr.auth_path, config_mgr.model_catalog_path]
        existing = [p for p in targets if p.exists()]

        if not existing:
            self._show_message("Codex 配置文件不存在，无需恢复")
            return

        file_list = "\n".join(f"• {p.name}" for p in existing)

        def _on_confirm(_: ft.ControlEvent) -> None:
            self._dialog_close(dialog)
            self._reset_codex_config()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("恢复配置"),
            content=ft.Text(
                f"以下 Codex 配置文件将被删除，Codex 将恢复至初始状态：\n\n"
                f"{file_list}\n\n"
                "此操作不可撤销，是否继续？"
            ),
            actions=[
                ft.Button(content="取消", on_click=lambda _: self._dialog_close(dialog)),
                ft.Button(
                    content="确认恢复",
                    icon=ft.Icons.SETTINGS_BACKUP_RESTORE,
                    on_click=_on_confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._show_dialog(dialog)

    def _reset_codex_config(self) -> None:
        """Delete all Codex configuration files to restore the initial state.

        Removes ``config.toml``, ``auth.json``, and ``models.json`` from the
        Codex config directory.  Also clears the active profile selection so
        the UI reflects the reset state.
        """

        try:
            removed = self.services.codex_config.reset()
        except Exception as exc:
            self._show_message(f"恢复失败: {exc}")
            return

        # Clear the active profile marker so the profile list reflects the reset
        try:
            self.services.repository.clear_active_profile("codex")
        except Exception:
            pass  # Best-effort; don't fail the reset over this

        self._refresh_profiles()
        if removed:
            names = "、".join(p.name for p in removed)
            self._show_message(f"已删除：{names}\nCodex 配置已恢复至初始状态")
        else:
            self._show_message("配置文件不存在，无需恢复")

    def _open_profile_terminal(self, profile: ProviderProfile) -> None:
        try:
            self.services.installer.open_cli(profile.target)
        except Exception as exc:
            self._show_message(f"终端启动失败: {exc}")
            return
        self._show_message("已打开终端")

    def _install_target(self, target: TargetTab) -> None:
        target_enum = InstallTarget.CODEX if target == "codex" else InstallTarget.CLAUDE

        def confirm_after_external_installers() -> None:
            self._dialog_close(dialog)
            self._run_cli_install(target_enum)

        required = self.services.installer.required_external_installers(self.status, target_enum)
        if required:
            actions: list[ft.Control] = [
                ft.Button(content="取消", on_click=lambda _: self._dialog_close(dialog)),
                ft.Button(
                    content="已安装, 继续",
                    on_click=lambda _: confirm_after_external_installers(),
                ),
            ]
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("安装依赖"),
                content=ft.Text("、".join(required)),
                actions=actions,
                actions_alignment=ft.MainAxisAlignment.END,
            )
            self._show_dialog(dialog)
            self._download_external_installers(required)
            return
        self._run_cli_install(target_enum)

    def _download_external_installers(self, required: list[str]) -> None:
        for item in required:
            try:
                spec = latest_node_lts_spec() if item == "node" else latest_git_for_windows_spec()
                path = self.services.installer.download(spec)
                self.services.installer.open_installer(path)
            except Exception as exc:
                self._show_message(f"{item} 安装包处理失败: {exc}")

    def _run_cli_install(self, target: InstallTarget) -> None:
        self.services.installer.ensure_npm_registry()
        result = self.services.installer.install_cli(target)
        if result.returncode != 0:
            self._show_message(result.stderr.strip() or result.stdout.strip() or "安装失败")
            return
        self.services.installer.launch_and_close(target.value)
        self._refresh_status()
        self._show_message("安装完成")

    def _open_protocol_document(self) -> None:
        """Open the complete Web integration protocol document."""

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("协议文档"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Markdown(
                            PROTOCOL_DOCUMENT_MARKDOWN,
                            selectable=True,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                            auto_follow_links=True,
                            auto_follow_links_target=ft.UrlTarget.BLANK,
                            shrink_wrap=True,
                        )
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
                width=760,
                height=560,
            ),
            actions=[
                ft.Button(content="关闭", on_click=lambda _: self._dialog_close(dialog)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._show_dialog(dialog)

    def _show_import_dialog(self, requests: list[ImportRequest]) -> None:
        def import_now(enabled: bool) -> None:
            profiles = [
                self.services.repository.create_profile(
                    ProviderDraft(
                        target=request.target,
                        name=request.name,
                        base_url=request.base_url,
                        api_key=request.api_key,
                        model=request.model,
                    )
                )
                for request in requests
            ]
            self._dialog_close(dialog)
            self.current_target = profiles[0].target
            self.tabs.selected_index = 0 if profiles[0].target == "codex" else 1
            self._refresh_profiles()
            if enabled:
                self._apply_profile(profiles[0])

        def preview_rows() -> list[ft.Control]:
            return [
                ft.Text(f"{request.target} / {request.name} / {request.model or '未设置模型'}")
                for request in requests
            ]

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("导入配置" if len(requests) == 1 else f"导入 {len(requests)} 个配置"),
            content=ft.Column(
                preview_rows(),
                tight=True,
            ),
            actions=[
                ft.Button(content="取消", on_click=lambda _: self._dialog_close(dialog)),
                ft.Button(content="导入全部", on_click=lambda _: import_now(False)),
                ft.Button(content="导入全部并启用第一项", on_click=lambda _: import_now(True)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._show_dialog(dialog)
        self.page.update()


def run_app(import_url: str | None = None, services: AppServices | None = None) -> None:
    """Run the Flet desktop app.

    @param import_url: Optional deep-link URL to confirm on startup.
    @param services: Optional service bundle for tests.
    """

    def main(page: ft.Page) -> None:
        AssistantApp(page, services or create_default_services(), import_url).build()

    ft.app(target=main)



