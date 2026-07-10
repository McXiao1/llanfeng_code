from __future__ import annotations

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

import llanfeng_code_assistant.config.codex as codex_module
from llanfeng_code_assistant.config.claude import ClaudeConfigManager
from llanfeng_code_assistant.config.codex import (
    CodexApplyResult,
    CodexConfigManager,
    build_codex_config,
)
from llanfeng_code_assistant.config.codex_models import (
    CUSTOM_MODEL_BASE_INSTRUCTIONS,
    DEFAULT_MODEL_CAPABILITIES,
    build_codex_model_catalog,
)
from llanfeng_code_assistant.file_ops import WriteResult, atomic_write_text
from llanfeng_code_assistant.models import CodexModel, ProviderProfile

CODEX_COMMAND = shutil.which("codex")


def _codex_profile(*, codex_models: list[CodexModel]) -> ProviderProfile:
    return ProviderProfile(
        id="catalog-profile",
        target="codex",
        name="Catalog Relay",
        base_url="https://api.example.com/v1",
        model="model-b",
        codex_models=codex_models,
    )


def _codex_profile_with_models() -> ProviderProfile:
    return _codex_profile(
        codex_models=[
            CodexModel(
                model_id="provider-model",
                display_name="5.6 Sol",
                context_window=1_000_000,
            )
        ]
    )


def _write_oauth_auth(config_dir: Path) -> None:
    (config_dir / "auth.json").write_text(
        json.dumps({"auth_mode": "chatgpt", "tokens": {"access_token": "official"}}),
        encoding="utf-8",
    )


def test_codex_apply_result_preserves_legacy_positional_signature(tmp_path: Path) -> None:
    config_write = WriteResult(path=tmp_path / "config.toml", backup_path=None)
    auth_write = WriteResult(path=tmp_path / "auth.json", backup_path=None)

    result = CodexApplyResult(config_write, auth_write, True)

    assert result.config_write is config_write
    assert result.auth_write is auth_write
    assert result.auth_written is True
    assert result.model_catalog_write is None


@pytest.mark.parametrize(
    "builder_name",
    ("build_codex_model_catalog", "build_codex_config"),
)
def test_codex_serialization_failure_precedes_all_file_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    builder_name: str,
) -> None:
    config_dir = tmp_path / ".codex"
    manager = CodexConfigManager(config_dir)
    profile = _codex_profile(
        codex_models=[CodexModel(model_id="model-a", display_name="Model A")]
    )
    serialization_error = RuntimeError(f"{builder_name} failed")
    atomic_write_paths: list[Path] = []

    def fail_serialization(*args: object, **kwargs: object) -> str:
        raise serialization_error

    def record_atomic_write(path: Path, content: str) -> WriteResult:
        atomic_write_paths.append(path)
        return WriteResult(path=path, backup_path=None)

    monkeypatch.setattr(codex_module, builder_name, fail_serialization)
    monkeypatch.setattr(codex_module, "atomic_write_text", record_atomic_write)

    with pytest.raises(RuntimeError) as exc_info:
        manager.apply_profile(profile, "sk-secret")

    assert exc_info.value is serialization_error
    assert atomic_write_paths == []
    assert not config_dir.exists()
    assert not manager.auth_path.exists()
    assert not manager.model_catalog_path.exists()
    assert not manager.config_path.exists()


def test_codex_restore_failure_rethrows_original_config_error_with_note(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    manager = CodexConfigManager(config_dir)
    _write_oauth_auth(config_dir)
    original_auth = manager.auth_path.read_text(encoding="utf-8")
    profile = _codex_profile(
        codex_models=[CodexModel(model_id="model-a", display_name="Model A")]
    )
    config_error = OSError("config write failed")
    restore_error = OSError("restore write failed")

    def fail_config_write(path: Path, content: str) -> WriteResult:
        if path == manager.config_path:
            raise config_error
        return atomic_write_text(path, content)

    def fail_restore_write(result: WriteResult) -> None:
        raise restore_error

    monkeypatch.setattr(codex_module, "atomic_write_text", fail_config_write)
    monkeypatch.setattr(codex_module, "restore_write", fail_restore_write)

    with pytest.raises(OSError) as exc_info:
        manager.apply_profile(profile, "sk-secret")

    assert exc_info.value is config_error
    assert any("restore write failed" in note for note in config_error.__notes__)
    assert manager.auth_path.read_text(encoding="utf-8") == original_auth


def test_build_codex_model_catalog_serializes_exact_sorted_utf8_shape() -> None:
    models = [
        CodexModel(
            model_id="model-c",
            display_name="GPT-5.6 Sol",
            context_window=300_000,
            position=2,
        ),
        CodexModel(
            model_id="model-b",
            display_name="模型乙",
            context_window=200_000,
            position=1,
        ),
        CodexModel(
            model_id="model-a",
            display_name="Model A",
            context_window=100_000,
            position=1,
        ),
    ]

    catalog_text = build_codex_model_catalog(models)

    assert CUSTOM_MODEL_BASE_INSTRUCTIONS == (
        "You are Codex, a coding agent. Follow the user's instructions, use the available "
        "tools when needed, and work carefully in the current workspace."
    )
    assert catalog_text.endswith("\n")
    assert "模型乙" in catalog_text
    assert catalog_text.encode("utf-8").decode("utf-8") == catalog_text
    catalog = json.loads(catalog_text)
    # Shared reasoning descriptors used across all three entries.
    reasoning_levels = [
        {"effort": "low", "description": "Fast responses with lighter reasoning"},
        {"effort": "medium", "description": "Balances speed and reasoning depth"},
        {"effort": "high", "description": "Greater reasoning depth for complex problems"},
        {"effort": "xhigh", "description": "Extra high reasoning depth for complex problems"},
        {"effort": "ultra", "description": "Maximum reasoning depth, most thorough analysis"},
    ]
    assert catalog == {
        "models": [
            {
                "slug": "model-a",
                "display_name": "Model A",
                "description": "Model A",
                "default_reasoning_level": "medium",
                "supported_reasoning_levels": reasoning_levels,
                "priority": 1,
                "base_instructions": CUSTOM_MODEL_BASE_INSTRUCTIONS,
                "context_window": 100_000,
                "max_context_window": 100_000,
                "truncation_policy": {"mode": "tokens", "limit": 100_000},
                **DEFAULT_MODEL_CAPABILITIES,
            },
            {
                "slug": "model-b",
                "display_name": "模型乙",
                "description": "模型乙",
                "default_reasoning_level": "medium",
                "supported_reasoning_levels": reasoning_levels,
                "priority": 1,
                "base_instructions": CUSTOM_MODEL_BASE_INSTRUCTIONS,
                "context_window": 200_000,
                "max_context_window": 200_000,
                "truncation_policy": {"mode": "tokens", "limit": 200_000},
                **DEFAULT_MODEL_CAPABILITIES,
            },
            {
                "slug": "model-c",
                "display_name": "5.6 Sol",
                "description": "5.6 Sol",
                "default_reasoning_level": "medium",
                "supported_reasoning_levels": reasoning_levels,
                "priority": 2,
                "base_instructions": CUSTOM_MODEL_BASE_INSTRUCTIONS,
                "context_window": 300_000,
                "max_context_window": 300_000,
                "truncation_policy": {"mode": "tokens", "limit": 300_000},
                **DEFAULT_MODEL_CAPABILITIES,
            },
        ]
    }
    # 10 explicit fields + 18 DEFAULT_MODEL_CAPABILITIES fields = 28 total
    assert all(len(model) == 28 for model in catalog["models"])


@pytest.mark.skipif(CODEX_COMMAND is None, reason="Codex CLI is not installed")
def test_installed_codex_accepts_generated_model_catalog(tmp_path: Path) -> None:
    catalog_path = tmp_path / "models.json"
    catalog_path.write_text(
        build_codex_model_catalog(_codex_profile_with_models().codex_models),
        encoding="utf-8",
    )
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    environment = {**os.environ, "CODEX_HOME": str(codex_home)}

    result = subprocess.run(
        [
            str(CODEX_COMMAND),
            "-c",
            f'model_catalog_json="{catalog_path.as_posix()}"',
            "debug",
            "models",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    models = json.loads(result.stdout)["models"]
    assert models[0]["slug"] == "provider-model"
    assert models[0]["display_name"] == "5.6 Sol"
    assert models[0]["context_window"] == 1_000_000


def test_codex_apply_profile_writes_and_references_model_catalog(tmp_path: Path) -> None:
    config_dir = tmp_path / ".codex"
    profile = _codex_profile(
        codex_models=[
            CodexModel(
                model_id="model-b",
                display_name="Model B",
                context_window=250_000,
                position=0,
            )
        ]
    )
    manager = CodexConfigManager(config_dir)

    result = manager.apply_profile(profile, "sk-secret")

    catalog_path = config_dir / "models.json"
    parsed = tomllib.loads((config_dir / "config.toml").read_text(encoding="utf-8"))
    assert manager.model_catalog_path == catalog_path
    assert catalog_path.read_text(encoding="utf-8") == build_codex_model_catalog(
        profile.codex_models
    )
    assert parsed["model_catalog_json"] == str(catalog_path.resolve())
    assert Path(parsed["model_catalog_json"]).is_absolute()
    assert result.model_catalog_write is not None
    assert result.model_catalog_write.path == catalog_path


def test_codex_apply_profile_with_no_models_omits_catalog(tmp_path: Path) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    catalog_path = config_dir / "models.json"
    original_catalog = '{"models": [{"slug": "historic"}]}\n'
    catalog_path.write_text(original_catalog, encoding="utf-8")
    # Profile has model="model-b" but no explicit codex_models list.
    # apply_profile must NOT write a catalog — omitting model_catalog_json lets
    # Codex show its built-in model list (which includes the latest provider
    # models) instead of a restricted single-entry picker.
    profile = _codex_profile(codex_models=[])

    result = CodexConfigManager(config_dir).apply_profile(profile, "sk-secret")

    parsed = tomllib.loads((config_dir / "config.toml").read_text(encoding="utf-8"))
    assert "model_catalog_json" not in parsed
    # Pre-existing catalog file must not be touched.
    assert catalog_path.read_text(encoding="utf-8") == original_catalog
    assert result.model_catalog_write is None


def test_codex_apply_profile_model_field_matches_catalog_slug(tmp_path: Path) -> None:
    """When profile.model is already a valid catalog slug, write it verbatim."""
    config_dir = tmp_path / ".codex"
    profile = _codex_profile(
        codex_models=[
            CodexModel(model_id="model-b", display_name="Model B", context_window=250_000),
            CodexModel(model_id="model-a", display_name="Model A", context_window=100_000, position=1),
        ]
    )
    # profile.model == "model-b" which IS in the catalog slugs.

    CodexConfigManager(config_dir).apply_profile(profile, "sk-secret")

    parsed = tomllib.loads((config_dir / "config.toml").read_text(encoding="utf-8"))
    assert parsed["model"] == "model-b"


def test_codex_apply_profile_model_falls_back_to_first_catalog_slug_when_mismatched(
    tmp_path: Path,
) -> None:
    """When profile.model is a display alias not found in catalog slugs, use the
    first catalog entry so Codex UI shows the model name instead of '自定义'."""
    config_dir = tmp_path / ".codex"
    # "5.4" is a display alias; the actual API model IDs are longer strings.
    profile = ProviderProfile(
        id="alias-profile",
        target="codex",
        name="Alias Test",
        base_url="https://api.example.com/v1",
        model="5.4",  # display alias — not in catalog slugs
        codex_models=[
            CodexModel(model_id="gpt-4.5-preview", display_name="5.4", context_window=1_000_000, position=0),
            CodexModel(model_id="gpt-4.5-mini", display_name="5.4-mini", context_window=1_000_000, position=1),
        ],
    )

    CodexConfigManager(config_dir).apply_profile(profile, "sk-secret")

    parsed = tomllib.loads((config_dir / "config.toml").read_text(encoding="utf-8"))
    # Must be an actual catalog slug, not the display alias "5.4".
    assert parsed["model"] == "gpt-4.5-preview"
    assert parsed["model"] != "5.4"


def test_codex_apply_profile_no_model_field_uses_first_catalog_entry(tmp_path: Path) -> None:
    """When profile.model is None but catalog models exist, write the first
    catalog slug so Codex pre-selects a model rather than showing '自定义'."""
    config_dir = tmp_path / ".codex"
    profile = ProviderProfile(
        id="no-model",
        target="codex",
        name="No Model",
        base_url="https://api.example.com/v1",
        model=None,
        codex_models=[
            CodexModel(model_id="model-z", display_name="Z", context_window=500_000, position=0),
            CodexModel(model_id="model-a", display_name="A", context_window=500_000, position=1),
        ],
    )

    CodexConfigManager(config_dir).apply_profile(profile, "sk-secret")

    parsed = tomllib.loads((config_dir / "config.toml").read_text(encoding="utf-8"))
    assert parsed["model"] == "model-z"


def test_build_codex_config_model_override_takes_precedence(tmp_path: Path) -> None:
    """model_override replaces profile.model in the generated TOML."""
    profile = ProviderProfile(
        id="p",
        target="codex",
        name="P",
        base_url="https://api.example.com/v1",
        model="old-model",
        codex_models=[],
    )

    result = build_codex_config(
        profile,
        "sk-test",
        tmp_path / "models.json",
        model_override="actual-catalog-slug",
    )

    parsed = tomllib.loads(result)
    assert parsed["model"] == "actual-catalog-slug"


def test_build_codex_config_model_override_none_falls_back_to_profile_model() -> None:
    """model_override=None leaves profile.model untouched (backward-compat)."""
    profile = ProviderProfile(
        id="p",
        target="codex",
        name="P",
        base_url="https://api.example.com/v1",
        model="profile-model",
        codex_models=[],
    )

    result = build_codex_config(profile, "sk-test", model_override=None)

    parsed = tomllib.loads(result)
    assert parsed["model"] == "profile-model"


def test_build_codex_config_requires_catalog_path_when_models_exist() -> None:
    profile = _codex_profile(
        codex_models=[CodexModel(model_id="model-a", display_name="Model A")]
    )

    with pytest.raises(ValueError, match="model_catalog_path is required"):
        build_codex_config(profile, "sk-secret")


def test_codex_catalog_failure_does_not_replace_existing_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    manager = CodexConfigManager(config_dir)
    original_config = 'model_provider = "original"\n'
    manager.config_path.write_text(original_config, encoding="utf-8")
    _write_oauth_auth(config_dir)
    profile = _codex_profile(
        codex_models=[CodexModel(model_id="model-a", display_name="Model A")]
    )
    written_paths: list[Path] = []

    def fail_catalog_write(path: Path, content: str) -> WriteResult:
        written_paths.append(path)
        if path == manager.model_catalog_path:
            raise OSError("catalog write failed")
        return atomic_write_text(path, content)

    monkeypatch.setattr(codex_module, "atomic_write_text", fail_catalog_write)

    with pytest.raises(OSError, match="catalog write failed"):
        manager.apply_profile(profile, "sk-secret")

    assert written_paths == [manager.model_catalog_path]
    assert manager.config_path.read_text(encoding="utf-8") == original_config


def test_codex_config_failure_restores_existing_model_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    manager = CodexConfigManager(config_dir)
    original_catalog = '{"models": [{"slug": "original"}]}\n'
    original_config = 'model_provider = "original"\n'
    manager.model_catalog_path.write_text(original_catalog, encoding="utf-8")
    manager.config_path.write_text(original_config, encoding="utf-8")
    _write_oauth_auth(config_dir)
    profile = _codex_profile(
        codex_models=[CodexModel(model_id="model-a", display_name="Model A")]
    )

    def fail_config_write(path: Path, content: str) -> WriteResult:
        if path == manager.config_path:
            raise OSError("config write failed")
        return atomic_write_text(path, content)

    monkeypatch.setattr(codex_module, "atomic_write_text", fail_config_write)

    with pytest.raises(OSError, match="config write failed"):
        manager.apply_profile(profile, "sk-secret")

    assert manager.model_catalog_path.read_text(encoding="utf-8") == original_catalog
    assert manager.config_path.read_text(encoding="utf-8") == original_config
    assert list(config_dir.glob("models.json.*.bak")) == []


def test_codex_config_failure_removes_new_model_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    manager = CodexConfigManager(config_dir)
    _write_oauth_auth(config_dir)
    profile = _codex_profile(
        codex_models=[CodexModel(model_id="model-a", display_name="Model A")]
    )

    def fail_config_write(path: Path, content: str) -> WriteResult:
        if path == manager.config_path:
            raise OSError("config write failed")
        return atomic_write_text(path, content)

    monkeypatch.setattr(codex_module, "atomic_write_text", fail_config_write)

    with pytest.raises(OSError, match="config write failed"):
        manager.apply_profile(profile, "sk-secret")

    assert not manager.model_catalog_path.exists()
    assert not manager.config_path.exists()


def test_codex_apply_profile_writes_provider_token_without_overwriting_existing_auth(
    tmp_path,
) -> None:
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    auth_path = config_dir / "auth.json"
    auth_path.write_text(
        json.dumps({"auth_mode": "chatgpt", "tokens": {"access_token": "official"}}),
        encoding="utf-8",
    )

    profile = ProviderProfile(
        id="p1",
        target="codex",
        name="Relay",
        base_url="https://api.example.com/v1/",
        model="gpt-5-codex",
    )

    result = CodexConfigManager(config_dir).apply_profile(profile, "sk-secret")

    assert json.loads(auth_path.read_text(encoding="utf-8"))["tokens"]["access_token"] == "official"
    parsed = tomllib.loads((config_dir / "config.toml").read_text(encoding="utf-8"))
    assert parsed["model_provider"] == "OpenAI"
    assert parsed["model"] == "gpt-5-codex"
    assert parsed["disable_response_storage"] is True
    custom = parsed["model_providers"]["OpenAI"]
    assert custom["name"] == "Relay"
    assert custom["base_url"] == "https://api.example.com/v1"
    assert custom["wire_api"] == "responses"
    assert custom["requires_openai_auth"] is True
    assert custom["experimental_bearer_token"] == "sk-secret"
    assert result.auth_written is False


def test_codex_apply_profile_can_initialize_api_key_auth_when_auth_missing(tmp_path) -> None:
    config_dir = tmp_path / ".codex"
    profile = ProviderProfile(
        id="p2",
        target="codex",
        name="Fresh",
        base_url="https://api.example.com",
        model="gpt-5-codex",
    )

    result = CodexConfigManager(config_dir).apply_profile(profile, "sk-secret")

    auth = json.loads((config_dir / "auth.json").read_text(encoding="utf-8"))
    assert auth == {"OPENAI_API_KEY": "sk-secret"}
    assert result.auth_written is True


def test_claude_apply_profile_merges_env_without_dropping_existing_settings(tmp_path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir()
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash(git:*)"]},
                "env": {"ANTHROPIC_CUSTOM_HEADERS": "x-test: 1"},
            }
        ),
        encoding="utf-8",
    )
    profile = ProviderProfile(
        id="p3",
        target="claude",
        name="Anthropic Relay",
        base_url="https://claude.example.com",
        model="claude-sonnet-4-5",
        haiku_model="claude-haiku",
        sonnet_model="claude-sonnet",
        fable_model="claude-fable",
        opus_model="claude-opus",
    )

    ClaudeConfigManager(settings_path).apply_profile(profile, "sk-ant")

    merged = json.loads(settings_path.read_text(encoding="utf-8"))
    assert merged["permissions"] == {"allow": ["Bash(git:*)"]}
    assert merged["env"]["ANTHROPIC_CUSTOM_HEADERS"] == "x-test: 1"
    assert merged["env"]["ANTHROPIC_AUTH_TOKEN"] == "sk-ant"
    assert merged["env"]["ANTHROPIC_BASE_URL"] == "https://claude.example.com"
    assert merged["env"]["ANTHROPIC_MODEL"] == "claude-sonnet-4-5"
    assert merged["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "claude-haiku"
    assert merged["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "claude-sonnet"
    assert merged["env"]["ANTHROPIC_DEFAULT_FABLE_MODEL"] == "claude-fable"
    assert merged["env"]["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "claude-opus"


def test_codex_model_capabilities_define_latest_experience_flags() -> None:
    # truncation_policy, context_window, and max_context_window are generated
    # per-model from CodexModel.context_window, so they are not in this dict.
    # All other fields match the codex-rs/models-manager/models.json schema.
    assert DEFAULT_MODEL_CAPABILITIES == {
        "shell_type": "shell_command",
        "visibility": "list",
        "supported_in_api": True,
        "supports_reasoning_summaries": True,
        "support_verbosity": True,
        "supports_verbosity": True,
        "supports_parallel_tool_calls": True,
        "supports_streaming": True,
        "supports_structured_output": True,
        "supports_tool_choice": True,
        "experimental_supported_tools": [],
        # Required fields from the Codex catalog schema:
        "supports_search_tool": False,
        "apply_patch_tool_type": None,
        "default_verbosity": None,
        "input_modalities": ["text"],
        "service_tiers": [],
        "availability_nux": None,
        "upgrade": None,
    }
