from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationInfo, field_validator

TargetName = Literal["codex", "claude"]
DEFAULT_CODEX_CONTEXT_WINDOW = 1_000_000


def _without_leading_gpt_prefix(display_name: str) -> str:
    """Remove the provider's redundant leading GPT label from a display name."""

    if not display_name.casefold().startswith("gpt-"):
        return display_name
    return display_name[4:].lstrip()


class CodexModel(BaseModel):
    """Typed Codex model metadata.

    @param model_id: Provider model identifier.
    @param display_name: User-facing model name, defaulting to the model id.
    @param context_window: Positive model context size.
    @param position: Non-negative display position.
    @returns: Validated Codex model metadata.
    @throws ValidationError: If an identifier, context size, or position is invalid.
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    model_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(default="", max_length=200)
    context_window: int = Field(default=DEFAULT_CODEX_CONTEXT_WINDOW, gt=0)
    position: StrictInt = Field(default=0, ge=0)

    @field_validator("display_name")
    @classmethod
    def default_display_name(cls, value: str, info: ValidationInfo) -> str:
        """Use the model identifier when no display name is provided.

        @param value: Normalized display name.
        @param info: Previously validated field data.
        @returns: Display name or model identifier fallback.
        """

        model_id = info.data.get("model_id")
        fallback = model_id if isinstance(model_id, str) else ""
        if not value:
            return fallback
        return _without_leading_gpt_prefix(value) or fallback

    @field_validator("context_window", mode="before")
    @classmethod
    def normalize_context_window(cls, value: object) -> int:
        """Normalize supported context-window inputs.

        @param value: Raw integer, numeric string, or empty value.
        @returns: Positive context-window size or the project default.
        @throws ValueError: If the value is not a positive integer.
        """

        if value is None:
            return DEFAULT_CODEX_CONTEXT_WINDOW
        if isinstance(value, bool):
            raise ValueError("context_window must be a positive integer")
        if isinstance(value, int):
            if value <= 0:
                raise ValueError("context_window must be a positive integer")
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return DEFAULT_CODEX_CONTEXT_WINDOW
            if normalized.isdecimal():
                parsed = int(normalized)
                if parsed > 0:
                    return parsed
        raise ValueError("context_window must be a positive integer")


class ProviderDraft(BaseModel):
    """User input for a new provider profile.

    @param target: Target CLI application.
    @param name: User-facing profile name.
    @param base_url: API base URL.
    @param api_key: Secret token stored outside SQLite.
    @param model: Default model identifier.
    @param codex_models: Typed Codex model metadata.
    @returns: Validated draft model.
    @throws ValueError: If required fields are blank.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    target: TargetName
    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=2048)
    api_key: str = Field(min_length=1)
    model: str | None = Field(default=None, max_length=200)
    codex_models: list[CodexModel] = Field(default_factory=list)
    haiku_model: str | None = Field(default=None, max_length=200)
    sonnet_model: str | None = Field(default=None, max_length=200)
    fable_model: str | None = Field(default=None, max_length=200)
    opus_model: str | None = Field(default=None, max_length=200)

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        """Normalize API base URLs.

        @param value: Raw URL.
        @returns: URL without trailing slash.
        @throws ValueError: If URL is not HTTP(S).
        """

        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("https://", "http://")):
            raise ValueError("base_url must start with http:// or https://")
        return normalized


class ProviderProfile(BaseModel):
    """Persisted provider metadata.

    @param id: Stable profile identifier.
    @param target: Target CLI application.
    @param name: User-facing profile name.
    @param base_url: API base URL.
    @param model: Default model identifier.
    @param codex_models: Typed Codex model metadata.
    @param secret_ref: Keyring lookup key.
    @returns: Persisted profile model.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    target: TargetName
    name: str
    base_url: str
    model: str | None = None
    codex_models: list[CodexModel] = Field(default_factory=list)
    secret_ref: str | None = None
    haiku_model: str | None = None
    sonnet_model: str | None = None
    fable_model: str | None = None
    opus_model: str | None = None

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        """Normalize API base URLs.

        @param value: Raw URL.
        @returns: URL without trailing slash.
        @throws ValueError: If URL is not HTTP(S).
        """

        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("https://", "http://")):
            raise ValueError("base_url must start with http:// or https://")
        return normalized


class ImportRequest(BaseModel):
    """Parsed browser deep-link import request.

    @param target: Target CLI application.
    @param name: Profile name.
    @param base_url: API base URL.
    @param api_key: API key from the import URL.
    @param model: Optional default model.
    @param enabled: Whether to apply immediately after import.
    @returns: Parsed import request.
    """

    target: TargetName
    name: str
    base_url: str
    api_key: str
    model: str | None = None
    enabled: bool = False


class ModelInfo(BaseModel):
    """Model item fetched from a provider.

    @param id: Provider model id.
    @param display_name: User-facing model name.
    @param context_window: Optional positive model context size.
    @param owned_by: Optional owner metadata.
    @returns: Model metadata.
    @throws ValidationError: If the model metadata is invalid.
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    id: str = Field(min_length=1, max_length=200)
    display_name: str = ""
    context_window: StrictInt | None = Field(default=None, gt=0)
    owned_by: str | None = None

    @field_validator("display_name")
    @classmethod
    def default_display_name(cls, value: str, info: ValidationInfo) -> str:
        """Use the model identifier when no display name is provided.

        @param value: Normalized display name.
        @param info: Previously validated field data.
        @returns: Display name or model identifier fallback.
        """

        model_id = info.data.get("id")
        fallback = model_id if isinstance(model_id, str) else ""
        if not value:
            return fallback
        return _without_leading_gpt_prefix(value) or fallback
