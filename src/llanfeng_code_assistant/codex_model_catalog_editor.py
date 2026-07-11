from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial

import flet as ft
from pydantic import ValidationError

from .models import DEFAULT_CODEX_CONTEXT_WINDOW, CodexModel, ModelInfo


class CodexModelCatalogEditor:
    """Edit an ordered Codex model catalog with Flet controls.

    @param on_change: Callback invoked after catalog content or editable values change.
    @returns: A catalog editor whose root control is available through ``control``.
    """

    def __init__(self, on_change: Callable[[], None]) -> None:
        self._on_change = on_change
        self._model_rows = ft.Column(
            spacing=6,
            height=240,
            scroll=ft.ScrollMode.AUTO,
            visible=False,
        )
        self._control = ft.Column(
            controls=[
                ft.Text("Codex 模型列表", weight=ft.FontWeight.W_600),
                self._model_rows,
            ],
            visible=False,
        )

    @property
    def control(self) -> ft.Control:
        """Return the editor's root Flet control.

        @returns: Root column containing the title and ordered model rows.
        """

        return self._control

    def replace_fetched(self, models: Sequence[ModelInfo]) -> None:
        """Replace the catalog with fetched models in provider order.

        @param models: Fetched model metadata in the order to render.
        @returns: None.
        """

        self._model_rows.controls = [
            self._build_row(
                model_id=model.id,
                display_name=model.display_name,
                context_window=model.context_window,
            )
            for model in models
        ]
        self._commit_change()

    def restore(self, models: Sequence[CodexModel]) -> None:
        """Restore persisted models sorted by position and identifier.

        @param models: Persisted model metadata to restore.
        @returns: None.
        """

        ordered_models = sorted(models, key=lambda model: (model.position, model.model_id))
        self._model_rows.controls = [
            self._build_row(
                model_id=model.model_id,
                display_name=model.display_name,
                context_window=model.context_window,
            )
            for model in ordered_models
        ]
        self._commit_change()

    def selector_options(self) -> list[ft.DropdownOption]:
        """Build dropdown options from the current editable row values.

        @returns: Options keyed by real model identifiers in current row order.
        """

        return [
            ft.DropdownOption(
                key=self._row_model_id(row),
                text=self._display_name(row),
            )
            for row in self._rows()
        ]

    def collect_models(self) -> list[CodexModel]:
        """Validate and collect models in their current display order.

        @returns: Validated models with contiguous positions starting at zero.
        @throws ValueError: If a context length or display name is invalid.
        """

        collected: list[CodexModel] = []
        for position, row in enumerate(self._rows()):
            model_id = self._row_model_id(row)
            context_value = self._field_value(row, "context_window").strip()
            try:
                collected.append(
                    CodexModel(
                        model_id=model_id,
                        display_name=self._display_name(row),
                        context_window=context_value or DEFAULT_CODEX_CONTEXT_WINDOW,
                        position=position,
                    )
                )
            except ValidationError as exc:
                if any(error["loc"] == ("context_window",) for error in exc.errors()):
                    raise ValueError(
                        f"模型 {model_id} 的上下文长度必须为正整数"
                    ) from exc
                raise ValueError(f"模型 {model_id} 的显示名称无效") from exc
        return collected

    def _build_row(
        self,
        model_id: str,
        display_name: str,
        context_window: int | None,
    ) -> ft.Row:
        row = ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.START)
        row.controls = [
            ft.TextField(
                label="模型 ID",
                value=model_id,
                read_only=True,
                dense=True,
                expand=3,
                data={
                    "catalog_model_id": model_id,
                    "catalog_field": "model_id",
                },
            ),
            ft.TextField(
                label="显示名称",
                value=display_name,
                max_length=200,
                dense=True,
                expand=3,
                data={
                    "catalog_model_id": model_id,
                    "catalog_field": "display_name",
                },
                on_change=self._handle_field_change,
            ),
            ft.TextField(
                label="上下文",
                value=str(context_window) if context_window is not None else str(DEFAULT_CODEX_CONTEXT_WINDOW),
                hint_text=str(DEFAULT_CODEX_CONTEXT_WINDOW),
                keyboard_type=ft.KeyboardType.NUMBER,
                input_filter=ft.NumbersOnlyInputFilter(),
                dense=True,
                width=130,
                data={
                    "catalog_model_id": model_id,
                    "catalog_field": "context_window",
                },
                on_change=self._handle_field_change,
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                tooltip="移除模型",
                data={
                    "catalog_model_id": model_id,
                    "catalog_field": "remove",
                },
                on_click=partial(self._remove_row, row),
            ),
        ]
        return row

    def _rows(self) -> list[ft.Row]:
        return [row for row in self._model_rows.controls if isinstance(row, ft.Row)]

    def _row_model_id(self, row: ft.Row) -> str:
        for control in row.controls:
            if not isinstance(control, ft.TextField) or not isinstance(control.data, dict):
                continue
            if control.data.get("catalog_field") != "model_id":
                continue
            model_id = control.data.get("catalog_model_id")
            if isinstance(model_id, str):
                return model_id
        raise RuntimeError("Missing catalog model id")

    def _display_name(self, row: ft.Row) -> str:
        model_id = self._row_model_id(row)
        display_name = self._field_value(row, "display_name").strip()
        return display_name or model_id

    @staticmethod
    def _field_value(row: ft.Row, field_name: str) -> str:
        for control in row.controls:
            if not isinstance(control, ft.TextField) or not isinstance(control.data, dict):
                continue
            if control.data.get("catalog_field") != field_name:
                continue
            return control.value if isinstance(control.value, str) else ""
        raise RuntimeError(f"Missing catalog field: {field_name}")

    def _remove_row(self, row: ft.Row, _event: ft.ControlEvent) -> None:
        if row not in self._model_rows.controls:
            return
        self._model_rows.controls.remove(row)
        self._commit_change()

    def _handle_field_change(self, _event: ft.ControlEvent) -> None:
        self._on_change()

    def _commit_change(self) -> None:
        has_rows = bool(self._model_rows.controls)
        self._model_rows.visible = has_rows
        self._control.visible = has_rows
        if self._control.parent is not None:
            self._control.update()
        self._on_change()
