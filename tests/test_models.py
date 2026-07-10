from __future__ import annotations

import pytest
from pydantic import ValidationError

from llanfeng_code_assistant import models
from llanfeng_code_assistant.models import (
    CodexModel,
    ModelInfo,
    ProviderDraft,
    ProviderProfile,
)


def test_default_codex_context_window_is_one_million() -> None:
    assert models.DEFAULT_CODEX_CONTEXT_WINDOW == 1_000_000


def test_model_info_defaults_display_name_to_id_and_context_to_none() -> None:
    model = ModelInfo(id=" model-id ")

    assert model.id == "model-id"
    assert model.display_name == "model-id"
    assert model.context_window is None


def test_model_info_blank_display_name_falls_back_to_id() -> None:
    model = ModelInfo(id="model-id", display_name="   ")

    assert model.display_name == "model-id"


@pytest.mark.parametrize(
    ("display_name", "expected"),
    [
        ("GPT-5.6 Sol", "5.6 Sol"),
        ("gpt- 5.6 Terra", "5.6 Terra"),
        ("GPT-5.6", "5.6"),
        ("My GPT-5.6", "My GPT-5.6"),
    ],
)
def test_model_info_removes_only_leading_gpt_prefix(
    display_name: str,
    expected: str,
) -> None:
    model = ModelInfo(id="provider-model", display_name=display_name)

    assert model.display_name == expected


def test_model_info_display_name_is_independent_of_id_length_limit() -> None:
    display_name = "x" * 201

    model = ModelInfo(id="model-id", display_name=display_name)

    assert model.display_name == display_name


@pytest.mark.parametrize("context_window", [None, 1, 128_000])
def test_model_info_accepts_none_or_positive_integer_context_window(
    context_window: int | None,
) -> None:
    model = ModelInfo(id="model-id", context_window=context_window)

    assert model.context_window == context_window


@pytest.mark.parametrize(
    "context_window",
    [True, False, 1.0, 1.5, 0.0, -1.0, 0, -1, "128000"],
)
def test_model_info_rejects_non_strict_or_non_positive_context_window(
    context_window: object,
) -> None:
    with pytest.raises(ValidationError):
        ModelInfo(id="model-id", context_window=context_window)


def test_codex_model_uses_defaults_for_blank_optional_metadata() -> None:
    model = models.CodexModel(
        model_id=" gpt-5-codex ",
        display_name="   ",
        context_window="",
    )

    assert model.model_id == "gpt-5-codex"
    assert model.display_name == "gpt-5-codex"
    assert model.context_window == models.DEFAULT_CODEX_CONTEXT_WINDOW
    assert model.position == 0


def test_codex_model_removes_leading_gpt_prefix_from_persisted_name() -> None:
    model = CodexModel(
        model_id="gpt-5.6-sol",
        display_name="GPT-5.6 Sol",
    )

    assert model.model_id == "gpt-5.6-sol"
    assert model.display_name == "5.6 Sol"


def test_codex_model_uses_default_context_for_none() -> None:
    model = models.CodexModel(model_id="gpt-5-codex", context_window=None)

    assert model.context_window == models.DEFAULT_CODEX_CONTEXT_WINDOW


def test_codex_model_accepts_positive_numeric_context_string() -> None:
    model = models.CodexModel(model_id="gpt-5-codex", context_window="200000")

    assert model.context_window == 200_000


@pytest.mark.parametrize("position", [0, 1])
def test_codex_model_accepts_non_negative_integer_position(position: int) -> None:
    model = models.CodexModel(model_id="gpt-5-codex", position=position)

    assert model.position == position


@pytest.mark.parametrize("position", [True, 1.0, "1"])
def test_codex_model_rejects_non_strict_integer_position(position: object) -> None:
    with pytest.raises(ValidationError):
        models.CodexModel(model_id="gpt-5-codex", position=position)


@pytest.mark.parametrize(
    "context_window",
    [True, 1.5, 0, -1, "0", "-1", "1.5", "invalid"],
)
def test_codex_model_rejects_invalid_context_window(context_window: object) -> None:
    with pytest.raises(ValidationError):
        models.CodexModel(model_id="gpt-5-codex", context_window=context_window)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("model_id", ""),
        ("model_id", "x" * 201),
        ("display_name", "x" * 201),
        ("position", -1),
    ],
)
def test_codex_model_rejects_invalid_bounded_fields(field_name: str, value: object) -> None:
    values: dict[str, object] = {"model_id": "gpt-5-codex", field_name: value}

    with pytest.raises(ValidationError):
        models.CodexModel(**values)


def test_provider_draft_parses_codex_model_dictionaries() -> None:
    draft = ProviderDraft(
        target="codex",
        name="Relay",
        base_url="https://api.example.com",
        api_key="sk-secret",
        codex_models=[
            {
                "model_id": " gpt-5-codex ",
                "display_name": " Codex ",
                "context_window": "400000",
                "position": 1,
            }
        ],
    )

    assert draft.codex_models == [
        models.CodexModel(
            model_id="gpt-5-codex",
            display_name="Codex",
            context_window=400_000,
            position=1,
        )
    ]


def test_provider_models_default_to_independent_empty_lists() -> None:
    draft = ProviderDraft(
        target="codex",
        name="Relay",
        base_url="https://api.example.com",
        api_key="sk-secret",
    )
    profile = ProviderProfile(
        id="profile-id",
        target="codex",
        name="Relay",
        base_url="https://api.example.com",
    )

    assert draft.codex_models == []
    assert profile.codex_models == []
    assert draft.codex_models is not profile.codex_models
