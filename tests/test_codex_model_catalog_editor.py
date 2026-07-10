from __future__ import annotations

from types import SimpleNamespace

import flet as ft
import pytest

from llanfeng_code_assistant.codex_model_catalog_editor import CodexModelCatalogEditor
from llanfeng_code_assistant.models import CodexModel, ModelInfo


def _walk_controls(control: ft.Control) -> list[ft.Control]:
    controls = [control]
    if isinstance(control, (ft.Column, ft.Row)):
        for child in control.controls:
            controls.extend(_walk_controls(child))
    return controls


def _rows(editor: CodexModelCatalogEditor) -> ft.Column:
    root = editor.control
    assert isinstance(root, ft.Column)
    rows = root.controls[1]
    assert isinstance(rows, ft.Column)
    return rows


def _field(row: ft.Row, catalog_field: str) -> ft.TextField:
    return next(
        control
        for control in row.controls
        if isinstance(control, ft.TextField)
        and isinstance(control.data, dict)
        and control.data.get("catalog_field") == catalog_field
    )


def test_replace_fetched_renders_all_models_and_selector_options() -> None:
    changes: list[str] = []
    editor = CodexModelCatalogEditor(lambda: changes.append("changed"))
    assert editor.control.visible is False
    fetched = [
        ModelInfo(
            id=f"model-{index:02d}",
            display_name=f"Display {index:02d}",
            context_window=100_000 + index,
        )
        for index in range(31)
    ]

    editor.replace_fetched(fetched)

    root = editor.control
    assert isinstance(root, ft.Column)
    assert root.visible is True
    title = root.controls[0]
    assert isinstance(title, ft.Text)
    assert title.value == "Codex 模型列表"
    assert title.weight == ft.FontWeight.W_600

    rows = _rows(editor)
    assert rows.spacing == 6
    assert rows.height == 240
    assert rows.scroll == ft.ScrollMode.AUTO
    assert rows.visible is True
    assert len(rows.controls) == 31
    assert changes == ["changed"]

    first_row = rows.controls[0]
    assert isinstance(first_row, ft.Row)
    assert first_row.spacing == 8
    assert first_row.vertical_alignment == ft.CrossAxisAlignment.START

    model_id = _field(first_row, "model_id")
    display_name = _field(first_row, "display_name")
    context_window = _field(first_row, "context_window")
    assert model_id is not display_name
    assert model_id.label == "模型 ID"
    assert model_id.value == "model-00"
    assert model_id.read_only is True
    assert model_id.dense is True
    assert model_id.expand == 3
    assert model_id.data == {
        "catalog_model_id": "model-00",
        "catalog_field": "model_id",
    }
    assert display_name.label == "显示名称"
    assert display_name.value == "Display 00"
    assert display_name.max_length == 200
    assert display_name.dense is True
    assert display_name.expand == 3
    assert display_name.data == {
        "catalog_model_id": "model-00",
        "catalog_field": "display_name",
    }
    assert callable(display_name.on_change)
    assert context_window.label == "上下文"
    assert context_window.value == "100000"
    assert context_window.hint_text == "1000000"
    assert context_window.keyboard_type == ft.KeyboardType.NUMBER
    assert isinstance(context_window.input_filter, ft.NumbersOnlyInputFilter)
    assert context_window.dense is True
    assert context_window.width == 130
    assert context_window.data == {
        "catalog_model_id": "model-00",
        "catalog_field": "context_window",
    }

    remove = next(control for control in first_row.controls if isinstance(control, ft.IconButton))
    assert remove.icon == ft.Icons.DELETE_OUTLINE
    assert remove.tooltip == "移除模型"
    assert remove.data == {
        "catalog_model_id": "model-00",
        "catalog_field": "remove",
    }
    assert callable(remove.on_click)

    options = editor.selector_options()
    assert [(option.key, option.text) for option in options[:2]] == [
        ("model-00", "Display 00"),
        ("model-01", "Display 01"),
    ]

    model_id.value = "tampered-read-only-value"
    assert editor.selector_options()[0].key == "model-00"
    assert editor.collect_models()[0].model_id == "model-00"


def test_replace_fetched_removes_gpt_prefix_from_display_name() -> None:
    editor = CodexModelCatalogEditor(lambda: None)

    editor.replace_fetched(
        [ModelInfo(id="gpt-5.6-sol", display_name="GPT-5.6 Sol")]
    )

    row = _rows(editor).controls[0]
    assert isinstance(row, ft.Row)
    assert _field(row, "model_id").value == "gpt-5.6-sol"
    assert _field(row, "display_name").value == "5.6 Sol"
    assert [(option.key, option.text) for option in editor.selector_options()] == [
        ("gpt-5.6-sol", "5.6 Sol")
    ]


def test_collect_models_uses_defaults_and_display_change_notifies() -> None:
    changes: list[str] = []
    editor = CodexModelCatalogEditor(lambda: changes.append("changed"))
    editor.replace_fetched([ModelInfo(id="gpt-5-codex")])
    row = _rows(editor).controls[0]
    assert isinstance(row, ft.Row)
    display_name = _field(row, "display_name")
    context_window = _field(row, "context_window")
    display_name.value = "   "
    context_window.value = ""

    assert callable(display_name.on_change)
    display_name.on_change(SimpleNamespace(control=display_name))

    assert changes == ["changed", "changed"]
    assert editor.selector_options()[0].text == "gpt-5-codex"
    assert editor.collect_models() == [
        CodexModel(
            model_id="gpt-5-codex",
            display_name="gpt-5-codex",
            context_window=1_000_000,
            position=0,
        )
    ]


def test_selector_options_keep_string_keys_after_empty_display_name() -> None:
    editor = CodexModelCatalogEditor(lambda: None)
    editor.replace_fetched([ModelInfo(id="gpt-5-codex")])
    row = _rows(editor).controls[0]
    assert isinstance(row, ft.Row)
    _field(row, "display_name").value = "   "

    options = editor.selector_options()

    assert len(options) == 1
    assert isinstance(options[0].key, str)
    assert options[0].key == "gpt-5-codex"
    assert options[0].text == "gpt-5-codex"


def test_context_change_notifies_once() -> None:
    changes: list[str] = []
    editor = CodexModelCatalogEditor(lambda: changes.append("changed"))
    editor.replace_fetched([ModelInfo(id="gpt-5-codex")])
    changes.clear()
    row = _rows(editor).controls[0]
    assert isinstance(row, ft.Row)
    context_window = _field(row, "context_window")

    assert callable(context_window.on_change)
    context_window.on_change(SimpleNamespace(control=context_window))

    assert changes == ["changed"]


def test_unmounted_change_skips_root_update_and_notifies(monkeypatch: pytest.MonkeyPatch) -> None:
    changes: list[str] = []
    editor = CodexModelCatalogEditor(lambda: changes.append("changed"))
    root = editor.control
    update_calls: list[str] = []

    def record_update() -> None:
        update_calls.append("update")

    monkeypatch.setattr(root, "update", record_update)
    editor.replace_fetched([ModelInfo(id="model-a")])

    assert update_calls == []
    assert changes == ["changed"]


def test_mounted_change_updates_root_once(monkeypatch: pytest.MonkeyPatch) -> None:
    editor = CodexModelCatalogEditor(lambda: None)
    root = editor.control
    attached_page = object()
    update_calls: list[str] = []

    def record_update() -> None:
        update_calls.append("update")

    monkeypatch.setattr(type(root), "parent", property(lambda _control: attached_page))
    monkeypatch.setattr(type(root), "page", property(lambda _control: attached_page))
    monkeypatch.setattr(root, "update", record_update)
    assert root.page is attached_page

    editor.replace_fetched([ModelInfo(id="model-a")])

    assert update_calls == ["update"]


def test_mounted_update_runtime_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    changes: list[str] = []
    editor = CodexModelCatalogEditor(lambda: changes.append("changed"))
    root = editor.control
    attached_page = object()

    def raise_update_error() -> None:
        raise RuntimeError("unexpected update error")

    monkeypatch.setattr(type(root), "parent", property(lambda _control: attached_page))
    monkeypatch.setattr(type(root), "page", property(lambda _control: attached_page))
    monkeypatch.setattr(root, "update", raise_update_error)

    with pytest.raises(RuntimeError, match="unexpected update error"):
        editor.replace_fetched([ModelInfo(id="model-a")])

    assert changes == []


def test_restore_sorts_then_delete_notifies_and_hides_empty_list() -> None:
    changes: list[str] = []
    editor = CodexModelCatalogEditor(lambda: changes.append("changed"))
    editor.restore(
        [
            CodexModel(model_id="model-b", display_name="B", position=1),
            CodexModel(model_id="model-c", display_name="C", position=0),
            CodexModel(model_id="model-a", display_name="A", position=0),
        ]
    )

    assert [model.model_id for model in editor.collect_models()] == [
        "model-a",
        "model-c",
        "model-b",
    ]
    assert changes == ["changed"]

    while _rows(editor).controls:
        row = _rows(editor).controls[0]
        assert isinstance(row, ft.Row)
        remove = next(control for control in row.controls if isinstance(control, ft.IconButton))
        assert callable(remove.on_click)
        remove.on_click(SimpleNamespace(control=remove))

    assert changes == ["changed", "changed", "changed", "changed"]
    assert editor.control.visible is False
    assert _rows(editor).visible is False
    assert editor.selector_options() == []
    assert editor.collect_models() == []


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "invalid"])
def test_collect_models_rejects_invalid_context_window(value: str) -> None:
    editor = CodexModelCatalogEditor(lambda: None)
    editor.replace_fetched([ModelInfo(id="invalid-context")])
    row = _rows(editor).controls[0]
    assert isinstance(row, ft.Row)
    _field(row, "context_window").value = value

    with pytest.raises(
        ValueError,
        match=r"^模型 invalid-context 的上下文长度必须为正整数$",
    ):
        editor.collect_models()


def test_collect_models_rejects_display_name_over_200_characters() -> None:
    editor = CodexModelCatalogEditor(lambda: None)
    editor.replace_fetched([ModelInfo(id="invalid-name")])
    row = _rows(editor).controls[0]
    assert isinstance(row, ft.Row)
    _field(row, "display_name").value = "x" * 201

    with pytest.raises(ValueError, match=r"^模型 invalid-name 的显示名称无效$"):
        editor.collect_models()


def test_walk_controls_returns_each_catalog_control() -> None:
    editor = CodexModelCatalogEditor(lambda: None)
    editor.replace_fetched([ModelInfo(id="model-a")])

    controls = _walk_controls(editor.control)

    assert len([control for control in controls if isinstance(control, ft.TextField)]) == 3
    assert len([control for control in controls if isinstance(control, ft.IconButton)]) == 1
