"""Reusable Flet update banner with download and installation states."""
from __future__ import annotations

from collections.abc import Callable

import flet as ft

from .updater import DownloadProgress, ReleaseInfo


class UpdateBanner:
    """Project-level update banner used by the main application controller."""

    def __init__(
        self,
        page: ft.Page,
        on_action: Callable[[ft.ControlEvent], None],
        on_dismiss: Callable[[], None],
    ) -> None:
        """Create the hidden update banner and its reusable controls.

        @param page: Flet page refreshed after state changes.
        @param on_action: Handler for download, retry, and installer actions.
        @param on_dismiss: Handler used when the close button is selected.
        """
        self._page = page
        self.icon = ft.Icon(ft.Icons.NEW_RELEASES, color=ft.Colors.ORANGE_700, size=18)
        self.status_text = ft.Text(
            "",
            size=13,
            color=ft.Colors.ORANGE_900,
            weight=ft.FontWeight.W_500,
        )
        self.detail_text = ft.Text("", size=11, color=ft.Colors.ORANGE_800)
        self.progress = ft.ProgressBar(
            value=0,
            expand=True,
            bar_height=6,
            color=ft.Colors.ORANGE_700,
            bgcolor=ft.Colors.ORANGE_100,
            border_radius=4,
        )
        self.progress_text = ft.Text(
            "0%",
            width=48,
            size=11,
            color=ft.Colors.ORANGE_900,
            text_align=ft.TextAlign.RIGHT,
        )
        self.progress_row = ft.Row(
            [self.progress, self.progress_text],
            spacing=10,
            visible=False,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.action_button = ft.Button(
            content="下载并安装",
            icon=ft.Icons.DOWNLOAD,
            visible=False,
            on_click=on_action,
        )
        self.dismiss_button = ft.IconButton(
            icon=ft.Icons.CLOSE,
            tooltip="忽略此次更新",
            on_click=lambda _: on_dismiss(),
        )
        self.control = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            self.icon,
                            ft.Column(
                                [self.status_text, self.detail_text],
                                spacing=2,
                                expand=True,
                            ),
                            self.action_button,
                            self.dismiss_button,
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.progress_row,
                ],
                spacing=6,
            ),
            visible=False,
            bgcolor=ft.Colors.ORANGE_50,
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border=ft.Border.all(1, ft.Colors.ORANGE_200),
        )

    def show_available(self, release: ReleaseInfo) -> None:
        """Show an available release with the in-app download action.

        @param release: Release metadata displayed to the user.
        @returns: None.
        """
        self._set_message(
            ft.Icons.NEW_RELEASES,
            f"发现新版本 V{release.version}",
            "安装包将在软件内下载并在完成后自动启动",
            icon_color=ft.Colors.ORANGE_700,
            title_color=ft.Colors.ORANGE_900,
            detail_color=ft.Colors.ORANGE_800,
        )
        self._set_progress(0, "0%", visible=False, color=ft.Colors.ORANGE_700)
        self._set_action("下载并安装", ft.Icons.DOWNLOAD, disabled=False)
        self.dismiss_button.disabled = False
        self.control.visible = True
        self._refresh()

    def show_downloading(self, release: ReleaseInfo) -> None:
        """Switch the banner to the active download state.

        @param release: Release currently being downloaded.
        @returns: None.
        """
        self._set_message(
            ft.Icons.DOWNLOADING,
            f"正在下载 V{release.version}",
            "正在连接下载服务器...",
            icon_color=ft.Colors.ORANGE_700,
            title_color=ft.Colors.ORANGE_900,
            detail_color=ft.Colors.ORANGE_800,
        )
        self._set_progress(0, "0%", visible=True, color=ft.Colors.ORANGE_700)
        self._set_action("下载中", ft.Icons.DOWNLOADING, disabled=True)
        self.dismiss_button.disabled = True
        self._refresh()

    def show_progress(self, progress: DownloadProgress) -> None:
        """Render the latest byte progress from the update downloader.

        @param progress: Downloaded and total byte snapshot.
        @returns: None.
        """
        fraction = progress.fraction
        self.progress.value = fraction
        if fraction is None:
            self.progress_text.value = "--"
            self.detail_text.value = f"已下载 {self._format_size(progress.downloaded_bytes)}"
        else:
            self.progress_text.value = f"{int(fraction * 100)}%"
            self.detail_text.value = (
                f"{self._format_size(progress.downloaded_bytes)} / "
                f"{self._format_size(progress.total_bytes or 0)}"
            )
        self._refresh()

    def show_download_complete(self, release: ReleaseInfo) -> None:
        """Show a verified download while the installer is being started.

        @param release: Release whose installer finished downloading.
        @returns: None.
        """
        self._set_message(
            ft.Icons.DOWNLOAD_DONE,
            f"V{release.version} 下载完成",
            "正在启动安装程序...",
            icon_color=ft.Colors.GREEN_700,
            title_color=ft.Colors.GREEN_800,
            detail_color=ft.Colors.GREEN_700,
        )
        self._set_progress(1, "100%", visible=True, color=ft.Colors.GREEN_700)
        self.dismiss_button.disabled = False
        self._refresh()

    def show_download_error(self, message: str) -> None:
        """Show a download failure and enable a retry action.

        @param message: Safe user-facing error description.
        @returns: None.
        """
        self._set_message(
            ft.Icons.ERROR_OUTLINE,
            "更新下载失败",
            message,
            icon_color=ft.Colors.RED_700,
            title_color=ft.Colors.RED_800,
            detail_color=ft.Colors.RED_700,
        )
        self._set_progress(0, "0%", visible=False, color=ft.Colors.RED_700)
        self._set_action("重试下载", ft.Icons.REFRESH, disabled=False)
        self.dismiss_button.disabled = False
        self._refresh()

    def show_installer_started(self) -> None:
        """Show that the local setup program was successfully started.

        @returns: None.
        """
        self._set_message(
            ft.Icons.INSTALL_DESKTOP,
            "安装程序已启动",
            "请按安装向导完成更新 · 安装时软件可能自动关闭",
            icon_color=ft.Colors.GREEN_700,
            title_color=ft.Colors.GREEN_800,
            detail_color=ft.Colors.GREEN_700,
        )
        self._set_action("重新打开安装程序", ft.Icons.INSTALL_DESKTOP, disabled=False)
        self.dismiss_button.disabled = False
        self._refresh()

    def show_installer_error(self, message: str, installer_exists: bool) -> None:
        """Show an installer launch failure with the appropriate retry action.

        @param message: Safe user-facing launch error.
        @param installer_exists: Whether setup can be retried without downloading again.
        @returns: None.
        """
        self._set_message(
            ft.Icons.ERROR_OUTLINE,
            "安装程序启动失败",
            message,
            icon_color=ft.Colors.RED_700,
            title_color=ft.Colors.RED_800,
            detail_color=ft.Colors.RED_700,
        )
        self._set_action(
            "重试安装" if installer_exists else "重新下载",
            ft.Icons.INSTALL_DESKTOP if installer_exists else ft.Icons.REFRESH,
            disabled=False,
        )
        self.dismiss_button.disabled = False
        self._refresh()

    def hide(self) -> None:
        """Hide the update banner.

        @returns: None.
        """
        self.control.visible = False
        self._refresh()

    def _set_message(
        self,
        icon: str | int,
        title: str,
        detail: str,
        *,
        icon_color: str | ft.Colors,
        title_color: str | ft.Colors,
        detail_color: str | ft.Colors,
    ) -> None:
        self.icon.icon = icon
        self.icon.color = icon_color
        self.status_text.value = title
        self.status_text.color = title_color
        self.detail_text.value = detail
        self.detail_text.color = detail_color

    def _set_action(
        self,
        label: str,
        icon: str | int,
        *,
        disabled: bool,
    ) -> None:
        self.action_button.content = label
        self.action_button.icon = icon
        self.action_button.disabled = disabled
        self.action_button.visible = True

    def _set_progress(
        self,
        value: float | int | None,
        label: str,
        *,
        visible: bool,
        color: str | ft.Colors,
    ) -> None:
        self.progress.value = value
        self.progress.color = color
        self.progress_text.value = label
        self.progress_row.visible = visible

    def _refresh(self) -> None:
        self._page.update()

    @staticmethod
    def _format_size(byte_count: int) -> str:
        size = float(max(byte_count, 0))
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return "0 B"
