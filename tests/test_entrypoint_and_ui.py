from __future__ import annotations

import inspect
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import flet as ft
import pytest

from llanfeng_code_assistant.codex_config_restorer import (
    CodexRestorePreview,
    CodexRestoreResult,
)
from llanfeng_code_assistant.codex_desktop_launcher import CodexLaunchResult
from llanfeng_code_assistant.codex_statsig_unlocker import ModelUnlockResult
from llanfeng_code_assistant.environment import SystemStatus, ToolStatus
from llanfeng_code_assistant.installer import DownloadSpec, InstallTarget
from llanfeng_code_assistant.updater import DownloadProgress, ReleaseInfo


class _FakeDetector:
    def __init__(self, *, ready: bool = True) -> None:
        path = "tool.exe" if ready else None
        version = "22.0.0" if ready else None
        self.status = SystemStatus(
            node=ToolStatus("node", path, version),
            npm=ToolStatus("npm", path, version),
            git=ToolStatus("git", path, "2.50.0" if ready else None),
            codex=ToolStatus("codex", path, "0.144.1" if ready else None),
            claude=ToolStatus("claude", path, "2.1.201" if ready else None),
        )
        self.calls = 0

    def detect_all(self) -> SystemStatus:
        self.calls += 1
        return self.status


class _FakeInstaller:
    def __init__(self) -> None:
        self.required: list[str] = []
        self.calls: list[object] = []
        self.install_result = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
        self.registry_result = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
        self.observe_busy: Callable[[], None] | None = None

    def required_external_installers(
        self,
        _status: SystemStatus,
        target: InstallTarget,
    ) -> list[str]:
        self.calls.append(("required", target))
        return list(self.required)

    def ensure_npm_registry(self) -> subprocess.CompletedProcess[str]:
        if self.observe_busy is not None:
            self.observe_busy()
        self.calls.append("registry")
        return self.registry_result

    def install_cli(self, target: InstallTarget) -> subprocess.CompletedProcess[str]:
        self.calls.append(("install", target))
        return self.install_result

    def download(self, spec: DownloadSpec) -> Path:
        self.calls.append(("download", spec.filename))
        return Path("C:/downloads") / spec.filename

    def open_installer(self, path: Path) -> None:
        self.calls.append(("open", path.name))


class _FakePage(SimpleNamespace):
    def __init__(self) -> None:
        super().__init__(window=SimpleNamespace())
        self.controls: list[object] = []
        self.opened_dialogs: list[object] = []
        self.scheduled_tasks: list[tuple[object, tuple[object, ...]]] = []
        self.update_count = 0

    def add(self, *controls: object) -> None:
        self.controls.extend(controls)

    def show_dialog(self, dialog: object) -> None:
        dialog.open = True
        self.opened_dialogs.append(dialog)

    def pop_dialog(self) -> object | None:
        if not self.opened_dialogs:
            return None
        dialog = self.opened_dialogs.pop()
        dialog.open = False
        return dialog

    def update(self) -> None:
        self.update_count += 1

    def run_task(self, coroutine: object, *args: object) -> None:
        self.scheduled_tasks.append((coroutine, args))


def _services(
    detector: _FakeDetector | None = None,
    installer: _FakeInstaller | None = None,
) -> object:
    from llanfeng_code_assistant.app import AppServices

    return AppServices(
        detector=detector or _FakeDetector(),
        installer=installer or _FakeInstaller(),
    )


def _walk_controls(control: object) -> list[object]:
    controls = [control]
    for attr in ("controls", "actions"):
        children = getattr(control, attr, None)
        if children:
            for child in children:
                controls.extend(_walk_controls(child))
    child = getattr(control, "content", None)
    if child is not None and not isinstance(child, str):
        controls.extend(_walk_controls(child))
    return controls


def _all_controls(page: _FakePage) -> list[object]:
    return [child for root in page.controls for child in _walk_controls(root)]


def _messages(page: _FakePage) -> list[str]:
    return [
        child.value
        for opened in page.opened_dialogs
        for child in _walk_controls(opened)
        if isinstance(child, ft.Text) and isinstance(child.value, str)
    ]


def test_parse_args_rejects_removed_deep_link_option() -> None:
    from llanfeng_code_assistant.__main__ import parse_args

    with pytest.raises(SystemExit):
        parse_args(["--import" + "-url", "llanfeng" + "-code://v1/import?target=codex"])


def test_main_does_not_start_app_when_another_instance_is_running(monkeypatch) -> None:
    import llanfeng_code_assistant.__main__ as entrypoint

    class LockedInstance:
        acquired = False

        def __enter__(self) -> LockedInstance:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    launched: list[bool] = []
    monkeypatch.setattr(entrypoint, "SingleInstance", LockedInstance)
    monkeypatch.setattr(entrypoint, "run_app", lambda: launched.append(True))

    assert entrypoint.main([]) == 0
    assert launched == []


def test_main_starts_app_without_protocol_argument(monkeypatch) -> None:
    import llanfeng_code_assistant.__main__ as entrypoint

    class AcquiredInstance:
        acquired = True

        def __enter__(self) -> AcquiredInstance:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    launched: list[bool] = []
    monkeypatch.setattr(entrypoint, "SingleInstance", AcquiredInstance)
    monkeypatch.setattr(entrypoint, "run_app", lambda: launched.append(True))

    assert entrypoint.main([]) == 0
    assert launched == [True]
    assert inspect.signature(entrypoint.run_app).parameters == {}


def test_format_tool_status_reports_missing_installed_and_version_floor() -> None:
    from llanfeng_code_assistant.app import format_tool_status

    assert format_tool_status(ToolStatus("node", None, None), "22.0.0") == "node: 未安装"
    assert (
        format_tool_status(ToolStatus("node", "node.exe", "20.0.0"), "22.0.0")
        == "node: 20.0.0, 需要 >= 22.0.0"
    )
    assert format_tool_status(ToolStatus("codex", "codex.cmd", "0.144.1")) == (
        "codex: 0.144.1"
    )


def test_build_renders_exactly_five_primary_actions_and_no_retired_ui() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    page = _FakePage()
    app = AssistantApp(page, _services())

    app.build()

    controls = _all_controls(page)
    primary_buttons = [
        child
        for child in controls
        if isinstance(child, ft.Button)
        and isinstance(child.data, dict)
        and child.data.get("primary_action") is True
    ]
    assert [button.content for button in primary_buttons] == [
        "安装/更新 Codex",
        "安装/更新 Claude",
        "解锁模型",
        "恢复配置",
        "增强启动 Codex",
    ]
    assert not any(isinstance(child, ft.Tabs) for child in controls)
    rendered_labels = "\n".join(
        str(child.content)
        for child in controls
        if isinstance(child, ft.Button) and isinstance(child.content, str)
    )
    assert "新增" not in rendered_labels
    assert "协议文档" not in rendered_labels
    assert "启用" not in rendered_labels
    assert page.scheduled_tasks == [(app._check_for_updates, ())]


@pytest.mark.asyncio
async def test_install_runs_in_busy_state_and_restores_button() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    installer = _FakeInstaller()
    page = _FakePage()
    app = AssistantApp(page, _services(installer=installer))
    button = app.action_buttons[InstallTarget.CODEX]
    busy_observations: list[bool] = []
    installer.observe_busy = lambda: busy_observations.append(button.disabled)

    await app._install_target(InstallTarget.CODEX)

    assert busy_observations == [True]
    assert installer.calls == [
        ("required", InstallTarget.CODEX),
        "registry",
        ("install", InstallTarget.CODEX),
    ]
    assert button.disabled is False
    assert button.content == "安装/更新 Codex"
    assert any("Codex 安装/更新完成" in message for message in _messages(page))


@pytest.mark.asyncio
async def test_unlock_prompts_before_terminating_running_codex() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    page = _FakePage()
    unlock_calls: list[bool] = []
    app = AssistantApp(
        page,
        _services(),
        is_codex_running=lambda: True,
        unlock_models=lambda: unlock_calls.append(True),
    )

    await app._request_model_unlock()

    assert unlock_calls == []
    dialog = page.opened_dialogs[-1]
    assert isinstance(dialog, ft.AlertDialog)
    assert isinstance(dialog.title, ft.Text)
    assert dialog.title.value == "Codex 正在运行"
    confirm = next(
        child
        for child in _walk_controls(dialog)
        if isinstance(child, ft.Button) and child.content == "关闭 Codex 并继续"
    )
    confirm.on_click(SimpleNamespace())
    assert page.scheduled_tasks[-1] == (app._perform_model_unlock, (True,))


@pytest.mark.asyncio
async def test_model_unlock_surfaces_added_models_backup_and_warnings() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    result = ModelUnlockResult(
        True,
        "已解锁 2 个模型",
        candidate_models=("gpt-5.6-sol", "gpt-5.6-terra"),
        models_added=("gpt-5.6-sol", "gpt-5.6-terra"),
        backup_path=Path("C:/backup/leveldb-20260711"),
        modified_records=1,
        warnings=("时间戳记录格式异常",),
    )
    page = _FakePage()
    app = AssistantApp(page, _services(), unlock_models=lambda: result)

    await app._perform_model_unlock(False)

    message = "\n".join(_messages(page))
    assert "gpt-5.6-sol、gpt-5.6-terra" in message
    assert "C:\\backup\\leveldb-20260711" in message or "C:/backup/leveldb-20260711" in message
    assert "时间戳记录格式异常" in message
    assert app.action_buttons["unlock"].disabled is False


@pytest.mark.asyncio
async def test_model_unlock_stops_when_codex_cannot_be_terminated() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    unlock_calls: list[bool] = []
    page = _FakePage()
    app = AssistantApp(
        page,
        _services(),
        terminate_codex=lambda: False,
        unlock_models=lambda: unlock_calls.append(True),
    )

    await app._perform_model_unlock(True)

    assert unlock_calls == []
    assert any("无法完全关闭 Codex" in message for message in _messages(page))


@pytest.mark.asyncio
async def test_enhanced_launch_surfaces_typed_partial_result_and_restores_button() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    async def launch() -> CodexLaunchResult:
        return CodexLaunchResult(
            True,
            False,
            "Codex 已启动, 但 CDP 连接超时, 插件市场增强未生效",
            process_id=42,
            cdp_port=9317,
        )

    page = _FakePage()
    app = AssistantApp(page, _services(), launch_marketplace=launch)

    await app._launch_enhanced_codex()

    assert any("CDP 连接超时" in message for message in _messages(page))
    assert app.action_buttons["launch"].disabled is False
    assert app.action_buttons["launch"].content == "增强启动 Codex"


def test_update_banner_action_schedules_in_app_download() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    page = _FakePage()
    app = AssistantApp(page, _services())
    release = ReleaseInfo(
        version="1.3.0",
        download_url="https://github.com/example/setup.exe",
        changelog="",
        filename="Setup.exe",
        download_size=1024,
    )

    app._show_update_banner(release)
    app._update_banner.action_button.on_click(SimpleNamespace())

    assert app._update_in_progress is True
    assert app._update_banner.progress_row.visible is True
    assert app._update_banner.action_button.disabled is True
    assert page.scheduled_tasks == [(app._download_and_install_update, (release,))]


@pytest.mark.asyncio
async def test_update_download_starts_installer_after_completion() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    class FakeUpdateInstaller:
        def __init__(self) -> None:
            self.started: list[Path] = []
            self.installer_path = Path("C:/updates/Setup.exe")

        async def download(
            self,
            _release: ReleaseInfo,
            on_progress: Callable[[DownloadProgress], None] | None = None,
        ) -> Path:
            if on_progress is not None:
                on_progress(DownloadProgress(1024, 1024))
            return self.installer_path

        def start_installer(self, path: Path) -> None:
            self.started.append(path)

    page = _FakePage()
    update_installer = FakeUpdateInstaller()
    app = AssistantApp(page, _services(), update_installer=update_installer)
    release = ReleaseInfo(
        version="1.3.0",
        download_url="https://github.com/example/setup.exe",
        changelog="",
        filename="Setup.exe",
        download_size=1024,
    )
    app._show_update_banner(release)

    await app._download_and_install_update(release)

    assert update_installer.started == [update_installer.installer_path]
    assert app._update_banner.status_text.value == "安装程序已启动"


@pytest.mark.asyncio
async def test_update_download_failure_enables_retry() -> None:
    from llanfeng_code_assistant.app import AssistantApp
    from llanfeng_code_assistant.updater import UpdateDownloadError

    class FailingUpdateInstaller:
        async def download(
            self,
            _release: ReleaseInfo,
            _on_progress: Callable[[DownloadProgress], None] | None = None,
        ) -> Path:
            raise UpdateDownloadError("网络连接失败")

        def start_installer(self, _path: Path) -> None:
            raise AssertionError("failed downloads must not start the installer")

    page = _FakePage()
    app = AssistantApp(page, _services(), update_installer=FailingUpdateInstaller())
    release = ReleaseInfo(
        version="1.3.0",
        download_url="https://github.com/example/setup.exe",
        changelog="",
        filename="Setup.exe",
    )
    app._show_update_banner(release)

    await app._download_and_install_update(release)

    assert app._update_in_progress is False
    assert app._update_banner.status_text.value == "更新下载失败"
    assert app._update_banner.action_button.content == "重试下载"

@pytest.mark.asyncio
async def test_restore_preview_noop_reports_without_scheduling_mutation() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    restore_calls: list[bool] = []
    page = _FakePage()
    app = AssistantApp(
        page,
        _services(),
        preview_restore=lambda: CodexRestorePreview((), None, 0),
        restore_configuration=lambda: restore_calls.append(True),
    )

    await app._request_config_restore()

    assert restore_calls == []
    assert any("无需恢复" in message for message in _messages(page))
    assert app.action_buttons["restore"].disabled is False
    assert app.action_buttons["restore"].content == "恢复配置"


@pytest.mark.asyncio
async def test_restore_confirmation_lists_exact_targets_and_preserved_data() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    page = _FakePage()
    preview = CodexRestorePreview(
        (Path("C:/.codex/config.toml"), Path("C:/.codex/models.json")),
        Path("C:/Codex/leveldb"),
        2,
    )
    app = AssistantApp(
        page,
        _services(),
        preview_restore=lambda: preview,
        is_codex_running=lambda: False,
    )

    await app._request_config_restore()

    dialog = page.opened_dialogs[-1]
    assert isinstance(dialog, ft.AlertDialog)
    assert isinstance(dialog.title, ft.Text)
    assert dialog.title.value == "恢复配置"
    content = "\n".join(
        child.value
        for child in _walk_controls(dialog)
        if isinstance(child, ft.Text) and isinstance(child.value, str)
    )
    assert "config.toml" in content
    assert "models.json" in content
    assert "2 项 Statsig" in content
    assert "保留登录" in content
    assert "auth.json" in content
    confirm = next(
        child
        for child in _walk_controls(dialog)
        if isinstance(child, ft.Button) and child.content == "确认恢复"
    )
    confirm.on_click(SimpleNamespace())
    assert page.scheduled_tasks[-1] == (app._perform_config_restore, (False,))


@pytest.mark.asyncio
async def test_restore_confirmation_requires_closing_running_codex() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    page = _FakePage()
    preview = CodexRestorePreview((), Path("C:/Codex/leveldb"), None)
    app = AssistantApp(
        page,
        _services(),
        preview_restore=lambda: preview,
        is_codex_running=lambda: True,
    )

    await app._request_config_restore()

    dialog = page.opened_dialogs[-1]
    confirm = next(
        child
        for child in _walk_controls(dialog)
        if isinstance(child, ft.Button) and child.content == "关闭 Codex 并恢复"
    )
    confirm.on_click(SimpleNamespace())
    assert page.scheduled_tasks[-1] == (app._perform_config_restore, (True,))


@pytest.mark.asyncio
async def test_restore_success_surfaces_backup_preservation_and_restart_guidance() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    result = CodexRestoreResult(
        True,
        "Codex 配置已安全恢复, 登录和用户数据已保留",
        backup_path=Path("C:/backup/codex_restore_20260712"),
        removed_paths=(Path("C:/.codex/config.toml"), Path("C:/.codex/models.json")),
        invalidated_statsig_keys=2,
    )
    page = _FakePage()
    app = AssistantApp(
        page,
        _services(),
        restore_configuration=lambda: result,
    )

    await app._perform_config_restore(False)

    message = "\n".join(_messages(page))
    assert "config.toml、models.json" in message
    assert "2 项 Statsig" in message
    assert "codex_restore_20260712" in message
    assert "登录和用户数据已保留" in message
    assert "重新启动 Codex" in message
    assert app.action_buttons["restore"].disabled is False


@pytest.mark.asyncio
async def test_restore_stops_when_codex_cannot_be_terminated() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    restore_calls: list[bool] = []
    page = _FakePage()
    app = AssistantApp(
        page,
        _services(),
        terminate_codex=lambda: False,
        restore_configuration=lambda: restore_calls.append(True),
    )

    await app._perform_config_restore(True)

    assert restore_calls == []
    assert any("无法完全关闭 Codex" in message for message in _messages(page))
    assert app.action_buttons["restore"].disabled is False


@pytest.mark.asyncio
async def test_restore_partial_rollback_is_visible() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    result = CodexRestoreResult(
        False,
        "清除 Statsig 模型缓存失败",
        backup_path=Path("C:/backup/codex_restore_failed"),
        rollback_attempted=True,
        rollback_completed=False,
        warnings=("恢复 Codex LevelDB 失败: rollback denied",),
    )
    page = _FakePage()
    app = AssistantApp(
        page,
        _services(),
        restore_configuration=lambda: result,
    )

    await app._perform_config_restore(False)

    message = "\n".join(_messages(page))
    assert "回滚状态: 不完整" in message
    assert "codex_restore_failed" in message
    assert "rollback denied" in message
