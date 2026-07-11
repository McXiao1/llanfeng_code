from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import tomlkit

from ..file_ops import WriteResult, atomic_write_text, restore_write
from ..models import ProviderProfile
from .codex_models import build_codex_model_catalog


@dataclass(frozen=True)
class CodexApplyResult:
    """Result of applying a Codex profile.

    @param config_write: Config write metadata.
    @param auth_write: Auth write metadata, when API-key auth was written.
    @param auth_written: Whether API-key auth was written.
    @param model_catalog_write: Model catalog write metadata, when a catalog was written.
    """

    config_write: WriteResult
    auth_write: WriteResult | None
    auth_written: bool
    model_catalog_write: WriteResult | None = None


def codex_auth_has_oauth_login_material(auth: dict[str, object]) -> bool:
    """Return whether Codex auth data contains non-API-key login material.

    @param auth: Parsed `auth.json`.
    @returns: `True` when auth should be preserved.
    """

    for key, value in auth.items():
        if key in {"auth_mode", "OPENAI_API_KEY"}:
            continue
        if value in (None, "", [], {}):
            continue
        return True
    return False


def build_codex_config(
    profile: ProviderProfile,
    api_key: str,
    model_catalog_path: Path | None = None,
    model_override: str | None = None,
) -> str:
    """Build Codex `config.toml` for a provider profile.

    @param profile: Codex profile metadata.
    @param api_key: API key stored as provider-scoped bearer token.
    @param model_catalog_path: Optional custom model catalog path.
    @param model_override: Model slug to write instead of ``profile.model``.
        Use this to pass a catalog-aligned slug when the profile's model
        field is a display name rather than the actual provider model ID.
    @returns: TOML document text.
    @throws ValueError: If the target is invalid or configured models have no catalog path.
    """

    if profile.target != "codex":
        raise ValueError("profile target must be codex")
    if profile.codex_models and model_catalog_path is None:
        raise ValueError("model_catalog_path is required when codex_models are configured")
    # model_override takes precedence; fall back to the profile's stored model.
    effective_model = model_override if model_override is not None else profile.model
    doc = tomlkit.document()
    doc.add("model_provider", "OpenAI")
    if effective_model:
        doc.add("model", effective_model)
    if model_catalog_path is not None:
        doc.add("model_catalog_json", str(model_catalog_path.resolve()))
    doc.add("disable_response_storage", True)

    providers = tomlkit.table()
    custom = tomlkit.table()
    custom.add("name", profile.name)
    custom.add("base_url", profile.base_url.rstrip("/"))
    custom.add("wire_api", "responses")
    custom.add("requires_openai_auth", True)
    custom.add("experimental_bearer_token", api_key)
    providers.add("OpenAI", custom)
    doc.add("model_providers", providers)
    return tomlkit.dumps(doc)


class CodexConfigManager:
    """Write standard Codex configuration files."""

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir

    @property
    def auth_path(self) -> Path:
        """Return Codex auth path.

        @returns: `auth.json` path.
        """

        return self._config_dir / "auth.json"

    @property
    def config_path(self) -> Path:
        """Return Codex config path.

        @returns: `config.toml` path.
        """

        return self._config_dir / "config.toml"

    @property
    def model_catalog_path(self) -> Path:
        """Return Codex custom model catalog path.

        @returns: `models.json` path.
        """

        return self._config_dir / "models.json"

    def _read_auth(self) -> dict[str, object] | None:
        if not self.auth_path.exists():
            return None
        try:
            loaded: object = json.loads(self.auth_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return loaded if isinstance(loaded, dict) else None

    def apply_profile(self, profile: ProviderProfile, api_key: str) -> CodexApplyResult:
        """Apply a Codex profile to live files.

        @param profile: Codex provider profile.
        @param api_key: API key for the profile.
        @returns: Write result metadata.
        @throws ValueError: If the API key or provider target is invalid.
        @throws OSError: If a configuration file cannot be written.
        """

        if not api_key.strip():
            raise ValueError("api_key is required")

        # Only write a model catalog when the user has explicitly configured
        # custom models.  Omitting model_catalog_json lets Codex fall back to
        # its built-in model list (which includes the latest provider models)
        # instead of showing a restricted single-entry picker.
        # Auto-synthesising a catalog from profile.model would replace the
        # entire built-in list, causing newer models to disappear from the UI.
        effective_models = list(profile.codex_models)

        # Resolve the model slug written into config.toml.
        # Codex matches config's `model` against catalog `slug` values — if
        # they differ the UI shows "自定义" (custom).  When the user's model
        # field is a display alias not found in the catalog slugs, fall back
        # to the first catalog entry so Codex always shows a named selection.
        # When there is no explicit catalog, write profile.model as-is and
        # let Codex resolve it against its built-in model list.
        effective_model = profile.model
        if effective_models:
            catalog_slugs = {m.model_id for m in effective_models}
            if effective_model not in catalog_slugs:
                first = min(effective_models, key=lambda m: (m.position, m.model_id))
                effective_model = first.model_id

        catalog_text = build_codex_model_catalog(effective_models) if effective_models else ""
        catalog_path = self.model_catalog_path if catalog_text else None
        config_text = build_codex_config(profile, api_key, catalog_path, model_override=effective_model)

        self._config_dir.mkdir(parents=True, exist_ok=True)
        auth = self._read_auth()
        should_preserve_auth = bool(auth and codex_auth_has_oauth_login_material(auth))
        auth_write: WriteResult | None = None
        if not should_preserve_auth:
            auth_write = atomic_write_text(
                self.auth_path,
                json.dumps({"OPENAI_API_KEY": api_key}, ensure_ascii=False, indent=2) + "\n",
            )
        model_catalog_write: WriteResult | None = None
        if catalog_text:
            model_catalog_write = atomic_write_text(self.model_catalog_path, catalog_text)
        try:
            config_write = atomic_write_text(self.config_path, config_text)
        except Exception as config_error:
            if model_catalog_write is not None:
                try:
                    restore_write(model_catalog_write)
                except Exception as restore_error:
                    config_error.add_note(
                        "Failed to restore the model catalog after the config write failed: "
                        f"{restore_error}"
                    )
            raise
        return CodexApplyResult(
            config_write=config_write,
            model_catalog_write=model_catalog_write,
            auth_write=auth_write,
            auth_written=auth_write is not None,
        )

    def reset(self) -> list[Path]:
        """Remove all Codex configuration files written by this application.

        Deletes ``config.toml``, ``auth.json``, and ``models.json`` if they
        exist.  The config directory itself is left intact.

        @returns: List of paths that were actually removed.
        """

        targets = [self.config_path, self.auth_path, self.model_catalog_path]
        removed: list[Path] = []
        for path in targets:
            if path.exists():
                path.unlink()
                removed.append(path)
        return removed
