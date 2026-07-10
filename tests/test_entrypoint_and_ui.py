from __future__ import annotations

import inspect
from collections.abc import Callable
from types import SimpleNamespace

import flet as ft
import pytest

from llanfeng_code_assistant.environment import SystemStatus, ToolStatus
from llanfeng_code_assistant.models import (
    CodexModel,
    ModelInfo,
    ProviderDraft,
    ProviderProfile,
)


class _FakeDetector:
    def detect_all(self) -> SystemStatus:
        return SystemStatus(
            node=ToolStatus("node", None, None),
            npm=ToolStatus("npm", None, None),
            git=ToolStatus("git", None, None),
            codex=ToolStatus("codex", None, None),
            claude=ToolStatus("claude", None, None),
        )


class _FakeRepository:
    def __init__(self, profiles: list[ProviderProfile] | None = None) -> None:
        self.profiles = profiles or []
        self.created_drafts: list[ProviderDraft] = []
        self.deleted_profiles: list[ProviderProfile] = []
        self.updated_profiles: list[ProviderProfile] = []
        self.active_profile_ids: dict[str, str] = {}
        self.target: str | None = None

    def list_profiles(self, target: str) -> list[ProviderProfile]:
        self.target = target
        return [profile for profile in self.profiles if profile.target == target]

    def create_profile(self, draft: ProviderDraft) -> ProviderProfile:
        profile_id = f"profile-{len(self.profiles) + 1}"
        profile = ProviderProfile(
            id=profile_id,
            secret_ref=f"{draft.target}:{profile_id}",
            **draft.model_dump(exclude={"api_key"}),
        )
        self.created_drafts.append(draft)
        self.profiles.append(profile)
        return profile

    def delete_profile(self, profile: ProviderProfile) -> None:
        self.deleted_profiles.append(profile)
        self.profiles = [item for item in self.profiles if item.id != profile.id]

    def update_profile(self, profile: ProviderProfile, _api_key: str | None = None) -> None:
        self.updated_profiles.append(profile)
        self.profiles = [item if item.id != profile.id else profile for item in self.profiles]

    def get_secret(self, profile: ProviderProfile) -> str:
        return "sk-secret"

    def set_active_profile(self, profile: ProviderProfile) -> None:
        self.active_profile_ids[profile.target] = profile.id

    def get_active_profile_id(self, target: str) -> str | None:
        return self.active_profile_ids.get(target)


class _FakeConfigManager:
    def __init__(self) -> None:
        self.applied: list[tuple[object, str]] = []

    def apply_profile(self, profile: object, api_key: str) -> None:
        self.applied.append((profile, api_key))


class _FakeInstaller:
    def __init__(self) -> None:
        self.opened: list[str] = []

    def open_cli(self, command: str) -> None:
        self.opened.append(command)


class _FakeModelFetcher:
    def __init__(self, openai_result: list[ModelInfo] | None = None) -> None:
        self.claude_calls: list[tuple[str, str]] = []
        self.openai_calls: list[tuple[str, str]] = []
        self.openai_result = (
            openai_result
            if openai_result is not None
            else [ModelInfo(id="gpt-a"), ModelInfo(id="gpt-b")]
        )
        self.openai_error: RuntimeError | ValueError | None = None

    async def fetch_claude(self, base_url: str, api_key: str) -> list[ModelInfo]:
        self.claude_calls.append((base_url, api_key))
        return [
            ModelInfo(id="claude-a"),
            ModelInfo(id="claude-b"),
        ]

    async def fetch_openai_compatible(self, base_url: str, api_key: str) -> list[ModelInfo]:
        self.openai_calls.append((base_url, api_key))
        if self.openai_error is not None:
            raise self.openai_error
        return self.openai_result


def _walk_controls(control: object) -> list[object]:
    controls = [control]
    for attr in ("controls", "actions"):
        children = getattr(control, attr, None)
        if children:
            for child in children:
                controls.extend(_walk_controls(child))
    child = getattr(control, "content", None)
    if child is not None:
        controls.extend(_walk_controls(child))
    return controls


def _catalog_text_fields(control: object, field_name: str) -> list[ft.TextField]:
    return [
        child
        for child in _walk_controls(control)
        if isinstance(child, ft.TextField)
        and isinstance(child.data, dict)
        and child.data.get("catalog_field") == field_name
    ]


class _FakePage(SimpleNamespace):
    def __init__(self) -> None:
        super().__init__(window=SimpleNamespace())
        self.controls: list[object] = []
        self.opened_dialogs: list[object] = []
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

    def run_task(self, coro: object, *args: object) -> None:
        """Stub for async task scheduling used by CDP launch buttons."""


def _fake_services(
    repository: _FakeRepository | None = None,
    model_fetcher: _FakeModelFetcher | None = None,
    codex_config: _FakeConfigManager | None = None,
    claude_config: _FakeConfigManager | None = None,
    installer: _FakeInstaller | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        detector=_FakeDetector(),
        repository=repository or _FakeRepository(),
        model_fetcher=model_fetcher or _FakeModelFetcher(),
        codex_config=codex_config or _FakeConfigManager(),
        claude_config=claude_config or _FakeConfigManager(),
        installer=installer or _FakeInstaller(),
    )


def test_parse_args_accepts_import_url() -> None:
    from llanfeng_code_assistant.__main__ import parse_args

    args = parse_args(["--import-url", "llanfeng-code://v1/import?target=codex"])

    assert args.import_url == "llanfeng-code://v1/import?target=codex"


def test_main_does_not_start_app_when_another_instance_is_running(monkeypatch) -> None:
    import llanfeng_code_assistant.__main__ as entrypoint

    class LockedInstance:
        acquired = False

        def __enter__(self) -> LockedInstance:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    launched: list[str | None] = []
    monkeypatch.setattr(entrypoint, "SingleInstance", LockedInstance)
    monkeypatch.setattr(entrypoint, "run_app", lambda import_url=None: launched.append(import_url))

    assert entrypoint.main([]) == 0
    assert launched == []


def test_main_starts_app_when_single_instance_lock_is_acquired(monkeypatch) -> None:
    import llanfeng_code_assistant.__main__ as entrypoint

    class AcquiredInstance:
        acquired = True

        def __enter__(self) -> AcquiredInstance:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    launched: list[str | None] = []
    monkeypatch.setattr(entrypoint, "SingleInstance", AcquiredInstance)
    monkeypatch.setattr(entrypoint, "run_app", lambda import_url=None: launched.append(import_url))

    assert entrypoint.main(["--import-url", "llanfeng-code://v1/import?target=codex"]) == 0
    assert launched == ["llanfeng-code://v1/import?target=codex"]


def test_format_tool_status_reports_missing_installed_and_version_floor() -> None:
    from llanfeng_code_assistant.app import format_tool_status

    assert format_tool_status(ToolStatus("node", None, None), "22.0.0") == "node: 未安装"
    assert (
        format_tool_status(ToolStatus("node", "node.exe", "20.0.0"), "22.0.0")
        == "node: 20.0.0, 需要 >= 22.0.0"
    )
    assert format_tool_status(ToolStatus("codex", "codex.cmd", "0.142.5"), None) == (
        "codex: 0.142.5"
    )


def test_assistant_app_constructs_tabs_with_current_flet_api() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    app = AssistantApp(SimpleNamespace(), _fake_services())

    assert app.tabs.length == 2
    assert app.tabs.selected_index == 0
    assert isinstance(app.tabs.content, ft.TabBar)
    assert [tab.label for tab in app.tabs.content.tabs] == ["Codex", "Claude"]


def test_assistant_app_builds_with_current_flet_button_api() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    page = _FakePage()
    app = AssistantApp(page, _fake_services())

    app.build()

    assert page.controls
    assert page.update_count >= 2


def test_assistant_app_opens_profile_dialog_with_current_flet_api() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    page = _FakePage()
    app = AssistantApp(page, _fake_services())

    app._open_profile_dialog(None)

    assert len(page.opened_dialogs) == 1
    dialog = page.opened_dialogs[0]
    assert dialog.open is True
    assert all(isinstance(action, ft.Button) for action in dialog.actions)


def test_new_button_click_opens_profile_dialog() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    page = _FakePage()
    app = AssistantApp(page, _fake_services())
    header = app._build_header()
    # "新增" button is now second-to-last (rightmost is "注入启动")
    new_button = next(
        c for c in header.controls if isinstance(c, ft.Button) and c.content == "新增"
    )

    new_button.on_click(SimpleNamespace())

    assert len(page.opened_dialogs) == 1


def test_editing_profile_preserves_existing_codex_models() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    codex_models = [
        CodexModel(
            model_id="gpt-5-codex",
            display_name="GPT-5 Codex",
            context_window=400_000,
            position=0,
        )
    ]
    profile = ProviderProfile(
        id="profile-1",
        target="codex",
        name="Relay",
        base_url="https://api.example.com/v1",
        model="gpt-5-codex",
        codex_models=codex_models,
        secret_ref="codex:profile-1",
    )
    repository = _FakeRepository([profile])
    page = _FakePage()
    app = AssistantApp(page, _fake_services(repository=repository))

    app._open_profile_dialog(profile)
    dialog = page.opened_dialogs[0]
    save_button = next(
        control
        for control in _walk_controls(dialog)
        if isinstance(control, ft.Button) and control.content == "保存"
    )
    save_button.on_click(SimpleNamespace())

    assert len(repository.updated_profiles) == 1
    assert repository.updated_profiles[0].codex_models == codex_models


async def test_codex_fetch_populates_full_editable_catalog_and_display_name_selector() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    fetcher = _FakeModelFetcher(
        [
            ModelInfo(id=f"provider-{index}", display_name=f"Model {index}")
            for index in range(31)
        ]
    )
    page = _FakePage()
    app = AssistantApp(page, _fake_services(model_fetcher=fetcher))

    app._open_profile_dialog(None)
    dialog = page.opened_dialogs[0]
    controls = _walk_controls(dialog)
    base_url = next(
        control
        for control in controls
        if isinstance(control, ft.TextField) and control.label == "URL"
    )
    api_key = next(
        control
        for control in controls
        if isinstance(control, ft.TextField) and control.label == "Key"
    )
    model = next(
        control
        for control in controls
        if isinstance(control, ft.TextField) and control.label == "模型"
    )
    model_selector = next(
        control
        for control in controls
        if isinstance(control, ft.Dropdown)
        and isinstance(control.data, dict)
        and control.data.get("model_field") == "模型"
    )
    base_url.value = "https://codex.example.com/v1"
    api_key.value = "sk-codex"

    fetch_button = next(
        control
        for control in controls
        if isinstance(control, ft.Button) and control.content == "获取模型"
    )
    await fetch_button.on_click(SimpleNamespace())

    assert fetcher.openai_calls == [("https://codex.example.com/v1", "sk-codex")]
    assert len(_catalog_text_fields(dialog, "model_id")) == 31
    assert [
        (option.key, option.text) for option in model_selector.options[:2]
    ] == [("provider-0", "Model 0"), ("provider-1", "Model 1")]
    assert page.update_count == 0

    model_selector.value = "provider-1"
    model_selector.on_select(SimpleNamespace(control=model_selector))

    assert model.value == "provider-1"
    remove_button = next(
        control
        for control in _walk_controls(dialog)
        if isinstance(control, ft.IconButton)
        and isinstance(control.data, dict)
        and control.data.get("catalog_model_id") == "provider-1"
        and control.data.get("catalog_field") == "remove"
    )
    remove_button.on_click(SimpleNamespace())

    assert model_selector.value is None


async def test_codex_save_collects_edited_catalog_models() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    fetcher = _FakeModelFetcher(
        [ModelInfo(id="provider-id", display_name="5.6 Sol", context_window=None)]
    )
    repository = _FakeRepository()
    page = _FakePage()
    app = AssistantApp(
        page,
        _fake_services(repository=repository, model_fetcher=fetcher),
    )

    app._open_profile_dialog(None)
    dialog = page.opened_dialogs[0]
    controls = _walk_controls(dialog)
    name = next(
        control
        for control in controls
        if isinstance(control, ft.TextField) and control.label == "名称"
    )
    base_url = next(
        control
        for control in controls
        if isinstance(control, ft.TextField) and control.label == "URL"
    )
    api_key = next(
        control
        for control in controls
        if isinstance(control, ft.TextField) and control.label == "Key"
    )
    name.value = "Codex Relay"
    base_url.value = "https://codex.example.com/v1"
    api_key.value = "sk-codex"
    fetch_button = next(
        control
        for control in controls
        if isinstance(control, ft.Button) and control.content == "获取模型"
    )
    await fetch_button.on_click(SimpleNamespace())

    display_name = _catalog_text_fields(dialog, "display_name")[0]
    context_window = _catalog_text_fields(dialog, "context_window")[0]
    display_name.value = "5.6 Sol Custom"
    context_window.value = ""
    display_name.on_change(SimpleNamespace())
    context_window.on_change(SimpleNamespace())
    save_button = next(
        control
        for control in _walk_controls(dialog)
        if isinstance(control, ft.Button) and control.content == "保存"
    )

    save_button.on_click(SimpleNamespace())

    assert repository.created_drafts[0].codex_models == [
        CodexModel(
            model_id="provider-id",
            display_name="5.6 Sol Custom",
            context_window=1_000_000,
            position=0,
        )
    ]


@pytest.mark.parametrize(
    "fetch_error",
    [
        pytest.param(RuntimeError("provider unavailable"), id="runtime-error"),
        pytest.param(ValueError("provider unavailable"), id="value-error"),
        pytest.param(
            RuntimeError("Model endpoint returned no valid models"),
            id="no-valid-models",
        ),
    ],
)
async def test_codex_fetch_failure_preserves_edited_catalog(
    fetch_error: RuntimeError | ValueError,
) -> None:
    from llanfeng_code_assistant.app import AssistantApp

    fetcher = _FakeModelFetcher([ModelInfo(id="provider-id", display_name="Provider Name")])
    page = _FakePage()
    app = AssistantApp(page, _fake_services(model_fetcher=fetcher))

    app._open_profile_dialog(None)
    dialog = page.opened_dialogs[0]
    controls = _walk_controls(dialog)
    fetch_button = next(
        control
        for control in controls
        if isinstance(control, ft.Button) and control.content == "获取模型"
    )
    await fetch_button.on_click(SimpleNamespace())
    display_name = _catalog_text_fields(dialog, "display_name")[0]
    display_name.value = "Edited Name"
    display_name.on_change(SimpleNamespace())
    fetcher.openai_error = fetch_error

    await fetch_button.on_click(SimpleNamespace())

    assert display_name.value == "Edited Name"


def test_editing_codex_profile_restores_catalog_and_saves_collected_models() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    profile = ProviderProfile(
        id="profile-1",
        target="codex",
        name="Relay",
        base_url="https://api.example.com/v1",
        model="provider-id",
        codex_models=[
            CodexModel(
                model_id="provider-id",
                display_name="Provider Display Name",
                context_window=800_000,
                position=0,
            )
        ],
        secret_ref="codex:profile-1",
    )
    repository = _FakeRepository([profile])
    page = _FakePage()
    app = AssistantApp(page, _fake_services(repository=repository))

    app._open_profile_dialog(profile)
    dialog = page.opened_dialogs[0]
    catalog_ids = _catalog_text_fields(dialog, "model_id")
    display_name = _catalog_text_fields(dialog, "display_name")[0]
    context_window = _catalog_text_fields(dialog, "context_window")[0]
    model_selector = next(
        control
        for control in _walk_controls(dialog)
        if isinstance(control, ft.Dropdown)
        and isinstance(control.data, dict)
        and control.data.get("model_field") == "模型"
    )

    assert [field.value for field in catalog_ids] == ["provider-id"]
    assert display_name.value == "Provider Display Name"
    assert context_window.value == "800000"
    assert [(option.key, option.text) for option in model_selector.options] == [
        ("provider-id", "Provider Display Name")
    ]
    assert page.update_count == 0

    display_name.value = "Edited Provider Name"
    display_name.on_change(SimpleNamespace())
    save_button = next(
        control
        for control in _walk_controls(dialog)
        if isinstance(control, ft.Button) and control.content == "保存"
    )
    save_button.on_click(SimpleNamespace())

    assert repository.updated_profiles[0].codex_models == [
        CodexModel(
            model_id="provider-id",
            display_name="Edited Provider Name",
            context_window=800_000,
            position=0,
        )
    ]


def test_fetch_models_button_uses_async_event_handler() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    page = _FakePage()
    app = AssistantApp(page, _fake_services())

    app._open_profile_dialog(None)
    dialog = page.opened_dialogs[0]
    fetch_button = next(
        control
        for control in _walk_controls(dialog)
        if isinstance(control, ft.Button) and control.content == "获取模型"
    )

    assert inspect.iscoroutinefunction(fetch_button.on_click)


async def test_codex_fetch_reports_unavailable_catalog_editor(monkeypatch) -> None:
    import llanfeng_code_assistant.app as app_module

    def unavailable_editor_factory(on_change: Callable[[], None]) -> None:
        del on_change

    monkeypatch.setattr(app_module, "CodexModelCatalogEditor", unavailable_editor_factory)
    page = _FakePage()
    app = app_module.AssistantApp(page, _fake_services())

    app._open_profile_dialog(None)
    dialog = page.opened_dialogs[0]
    fetch_button = next(
        control
        for control in _walk_controls(dialog)
        if isinstance(control, ft.Button) and control.content == "获取模型"
    )
    await fetch_button.on_click(SimpleNamespace())

    message_texts = [
        control.value
        for opened_dialog in page.opened_dialogs[1:]
        for control in _walk_controls(opened_dialog)
        if isinstance(control, ft.Text)
    ]
    assert "模型获取失败: Codex model editor is unavailable" in message_texts


def test_codex_editor_early_change_callback_does_not_update_page(monkeypatch) -> None:
    import llanfeng_code_assistant.app as app_module

    class EarlyCallbackEditor:
        def __init__(self, on_change: Callable[[], None]) -> None:
            self.control: ft.Control = ft.Column()
            on_change()

    monkeypatch.setattr(app_module, "CodexModelCatalogEditor", EarlyCallbackEditor)
    page = _FakePage()
    app = app_module.AssistantApp(page, _fake_services())

    app._open_profile_dialog(None)

    assert len(page.opened_dialogs) == 1
    assert page.update_count == 0


def test_claude_profile_dialog_contains_fable_field_and_model_selectors() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    page = _FakePage()
    app = AssistantApp(page, _fake_services())
    app.current_target = "claude"

    app._open_profile_dialog(None)

    dialog = page.opened_dialogs[0]
    visible_text_labels = [
        control.label
        for control in _walk_controls(dialog)
        if isinstance(control, ft.TextField) and control.visible
    ]
    visible_selectors = [
        control
        for control in _walk_controls(dialog)
        if isinstance(control, ft.Dropdown) and control.visible
    ]

    assert visible_text_labels == ["名称", "URL", "Key", "模型", "Haiku", "Sonnet", "Fable", "Opus"]
    assert len(visible_selectors) == 5


async def test_fetch_models_populates_selectors_without_model_buttons() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    fetcher = _FakeModelFetcher()
    page = _FakePage()
    app = AssistantApp(page, _fake_services(model_fetcher=fetcher))
    app.current_target = "claude"

    app._open_profile_dialog(None)
    dialog = page.opened_dialogs[0]
    controls = _walk_controls(dialog)
    base_url = next(
        control
        for control in controls
        if isinstance(control, ft.TextField) and control.label == "URL"
    )
    api_key = next(
        control
        for control in controls
        if isinstance(control, ft.TextField) and control.label == "Key"
    )
    base_url.value = "https://claude.example.com"
    api_key.value = "sk-ant"

    fetch_button = next(
        control
        for control in controls
        if isinstance(control, ft.Button) and control.content == "获取模型"
    )
    await fetch_button.on_click(SimpleNamespace())

    refreshed_controls = _walk_controls(dialog)
    model_buttons = [
        control
        for control in refreshed_controls
        if isinstance(control, ft.Button) and control.content in {"claude-a", "claude-b"}
    ]
    selectors = [
        control
        for control in refreshed_controls
        if isinstance(control, ft.Dropdown) and control.visible
    ]
    fable = next(
        control
        for control in refreshed_controls
        if isinstance(control, ft.TextField) and control.label == "Fable"
    )
    fable_selector = next(
        control
        for control in selectors
        if isinstance(control.data, dict) and control.data.get("model_field") == "Fable"
    )

    assert fetcher.claude_calls == [("https://claude.example.com", "sk-ant")]
    assert model_buttons == []
    assert all(
        [option.key for option in selector.options] == ["claude-a", "claude-b"]
        for selector in selectors
    )

    fable_selector.value = "claude-b"
    fable_selector.on_select(SimpleNamespace(control=fable_selector))

    assert fable.value == "claude-b"


def test_assistant_app_creates_profile_card_with_current_flet_api() -> None:
    from llanfeng_code_assistant.app import AssistantApp
    from llanfeng_code_assistant.models import ProviderProfile

    app = AssistantApp(SimpleNamespace(), _fake_services())
    profile = ProviderProfile(
        id="profile-1",
        target="codex",
        name="Relay",
        base_url="https://api.example.com/v1",
        model="gpt-5",
        secret_ref="codex:profile-1",
    )

    card = app._profile_card(profile)

    assert isinstance(card, ft.Card)


def test_profile_card_delete_button_removes_profile_and_refreshes() -> None:
    from llanfeng_code_assistant.app import AssistantApp
    from llanfeng_code_assistant.models import ProviderProfile

    profile = ProviderProfile(
        id="profile-1",
        target="codex",
        name="Relay",
        base_url="https://api.example.com/v1",
        model="gpt-5",
        secret_ref="codex:profile-1",
    )
    repository = _FakeRepository([profile])
    page = _FakePage()
    app = AssistantApp(page, _fake_services(repository))
    card = app._profile_card(profile)
    delete_button = next(
        control
        for control in _walk_controls(card)
        if isinstance(control, ft.Button) and control.content == "删除"
    )

    delete_button.on_click(SimpleNamespace())

    assert repository.deleted_profiles == [profile]
    assert repository.list_profiles("codex") == []
    assert page.update_count >= 1


def test_apply_profile_writes_config_marks_active_and_does_not_open_terminal() -> None:
    from llanfeng_code_assistant.app import AssistantApp
    from llanfeng_code_assistant.models import ProviderProfile

    profile = ProviderProfile(
        id="profile-1",
        target="codex",
        name="Relay",
        base_url="https://api.example.com/v1",
        model="gpt-5",
        secret_ref="codex:profile-1",
    )
    repository = _FakeRepository([profile])
    codex_config = _FakeConfigManager()
    installer = _FakeInstaller()
    page = _FakePage()
    app = AssistantApp(
        page,
        _fake_services(
            repository=repository,
            codex_config=codex_config,
            installer=installer,
        ),
    )

    app._apply_profile(profile)

    assert codex_config.applied == [(profile, "sk-secret")]
    assert installer.opened == []
    assert repository.get_active_profile_id("codex") == "profile-1"


def test_profile_card_shows_enabled_state_and_terminal_button_opens_cli() -> None:
    from llanfeng_code_assistant.app import AssistantApp
    from llanfeng_code_assistant.models import ProviderProfile

    profile = ProviderProfile(
        id="profile-1",
        target="codex",
        name="Relay",
        base_url="https://api.example.com/v1",
        model="gpt-5",
        secret_ref="codex:profile-1",
    )
    repository = _FakeRepository([profile])
    repository.set_active_profile(profile)
    installer = _FakeInstaller()
    page = _FakePage()
    app = AssistantApp(page, _fake_services(repository=repository, installer=installer))

    app._refresh_profiles()

    controls = _walk_controls(app.profile_column)
    edit_index = next(
        index
        for index, control in enumerate(controls)
        if isinstance(control, ft.IconButton) and control.tooltip == "编辑"
    )
    terminal_button = next(
        control
        for control in controls[edit_index + 1 :]
        if isinstance(control, ft.IconButton) and control.tooltip == "打开终端"
    )
    active_button = next(
        control
        for control in controls
        if isinstance(control, ft.Button) and control.content == "已启用"
    )
    status_text = next(
        control
        for control in controls
        if isinstance(control, ft.Text) and control.value == "已启用"
    )

    terminal_button.on_click(SimpleNamespace())

    assert terminal_button.icon == ft.Icons.TERMINAL
    assert active_button.disabled is True
    assert status_text.value == "已启用"
    assert installer.opened == ["codex"]


def test_header_replaces_protocol_registration_with_document_button() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    page = _FakePage()
    app = AssistantApp(page, _fake_services())
    header = app._build_header()
    buttons = [control for control in header.controls if isinstance(control, ft.Button)]

    assert [button.content for button in buttons] == ["协议文档", "新增", "注入启动"]
    assert all(button.content != "注册协议" for button in buttons)
    assert buttons[0].icon == ft.Icons.DESCRIPTION


def test_protocol_document_button_opens_scrollable_complete_document_dialog() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    page = _FakePage()
    app = AssistantApp(page, _fake_services())
    header = app._build_header()
    document_button = next(
        control
        for control in header.controls
        if isinstance(control, ft.Button) and control.content == "协议文档"
    )

    document_button.on_click(SimpleNamespace())

    assert len(page.opened_dialogs) == 1
    dialog = page.opened_dialogs[0]
    assert isinstance(dialog.title, ft.Text)
    assert dialog.title.value == "协议文档"
    assert isinstance(dialog.content, ft.Container)
    assert dialog.content.width == 760
    assert dialog.content.height == 560
    content_column = dialog.content.content
    assert isinstance(content_column, ft.Column)
    assert content_column.scroll == ft.ScrollMode.AUTO
    markdown = next(
        control for control in _walk_controls(dialog) if isinstance(control, ft.Markdown)
    )
    assert markdown.selectable is True
    assert markdown.auto_follow_links is True
    assert markdown.auto_follow_links_target == ft.UrlTarget.BLANK
    assert "https://lanfengai.cn" in markdown.value
    assert "llanfeng-code://v1/import?" in markdown.value
    assert "llanfeng-code://v1/import-list?payload=" in markdown.value
    assert "HTML / JavaScript 示例" in markdown.value
    assert "安全与兼容性注意事项" in markdown.value
    assert [action.content for action in dialog.actions] == ["关闭"]



async def test_codex_fetch_and_save_then_apply_uses_catalog_without_undefined_selector_state() -> None:
    from llanfeng_code_assistant.app import AssistantApp

    fetcher = _FakeModelFetcher(
        [
            ModelInfo(id="gpt-5-codex", display_name="GPT-5 Codex", context_window=400_000),
            ModelInfo(id="gpt-5.1", display_name="GPT-5.1", context_window=500_000),
        ]
    )
    repository = _FakeRepository()
    codex_config = _FakeConfigManager()
    page = _FakePage()
    app = AssistantApp(
        page,
        _fake_services(
            repository=repository,
            model_fetcher=fetcher,
            codex_config=codex_config,
        ),
    )

    app._open_profile_dialog(None)
    dialog = page.opened_dialogs[0]
    controls = _walk_controls(dialog)
    name = next(
        control
        for control in controls
        if isinstance(control, ft.TextField) and control.label == "名称"
    )
    base_url = next(
        control
        for control in controls
        if isinstance(control, ft.TextField) and control.label == "URL"
    )
    api_key = next(
        control
        for control in controls
        if isinstance(control, ft.TextField) and control.label == "Key"
    )
    model = next(
        control
        for control in controls
        if isinstance(control, ft.TextField) and control.label == "模型"
    )
    selector = next(
        control
        for control in controls
        if isinstance(control, ft.Dropdown)
        and isinstance(control.data, dict)
        and control.data.get("model_field") == "模型"
    )
    fetch_button = next(
        control
        for control in controls
        if isinstance(control, ft.Button) and control.content == "获取模型"
    )
    save_and_apply = next(
        control
        for control in _walk_controls(dialog)
        if isinstance(control, ft.Button) and control.content == "保存并启用"
    )

    name.value = "Relay"
    base_url.value = "https://api.example.com/v1"
    api_key.value = "sk-secret"

    await fetch_button.on_click(SimpleNamespace())

    selector.value = "gpt-5.1"
    selector.on_select(SimpleNamespace(control=selector))
    assert model.value == "gpt-5.1"
    assert [option.text for option in selector.options] == ["5 Codex", "5.1"]
    assert all(isinstance(option.key, str) for option in selector.options)

    save_and_apply.on_click(SimpleNamespace())

    assert len(repository.created_drafts) == 1
    draft = repository.created_drafts[0]
    assert draft.model == "gpt-5.1"
    assert [item.model_dump() for item in draft.codex_models] == [
        {
            "model_id": "gpt-5-codex",
            "display_name": "5 Codex",
            "context_window": 400_000,
            "position": 0,
        },
        {
            "model_id": "gpt-5.1",
            "display_name": "5.1",
            "context_window": 500_000,
            "position": 1,
        },
    ]
    assert len(codex_config.applied) == 1
    applied_profile, applied_secret = codex_config.applied[0]
    assert isinstance(applied_profile, ProviderProfile)
    assert applied_profile.model == "gpt-5.1"
    assert [item.display_name for item in applied_profile.codex_models] == ["5 Codex", "5.1"]
    assert applied_secret == "sk-secret"
    assert repository.get_active_profile_id("codex") == applied_profile.id
