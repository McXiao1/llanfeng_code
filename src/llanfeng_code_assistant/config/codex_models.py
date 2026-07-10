from __future__ import annotations

import json
from collections.abc import Sequence

from ..models import CodexModel

# Reasoning level descriptors matching the Codex catalog schema.
# Field name is "default_reasoning_level" (NOT "default_reasoning_effort").
# "supported_reasoning_levels" is an array of effort objects (NOT a string array).
SUPPORTED_REASONING_LEVELS = [
    {
        "effort": "low",
        "description": "Fast responses with lighter reasoning",
    },
    {
        "effort": "medium",
        "description": "Balances speed and reasoning depth",
    },
    {
        "effort": "high",
        "description": "Greater reasoning depth for complex problems",
    },
    {
        "effort": "xhigh",
        "description": "Extra high reasoning depth for complex problems",
    },
    {
        "effort": "ultra",
        "description": "Maximum reasoning depth, most thorough analysis",
    },
]

CUSTOM_MODEL_BASE_INSTRUCTIONS = (
    "You are Codex, a coding agent. Follow the user's instructions, use the available tools "
    "when needed, and work carefully in the current workspace."
)

# Base capability flags common to every custom model entry.
# Fields are sourced from codex-rs/models-manager/models.json and the AiHubMix
# Codex CLI integration guide — omitting required fields causes the catalog to
# be silently discarded by Codex at startup.
# NOTE: context_window, max_context_window, and truncation_policy are set
# per-model from CodexModel.context_window so they are NOT included here.
DEFAULT_MODEL_CAPABILITIES: dict[str, object] = {
    "shell_type": "shell_command",
    "visibility": "list",
    "supported_in_api": True,
    "support_verbosity": True,
    "supports_verbosity": True,
    "supports_parallel_tool_calls": True,
    "supports_streaming": True,
    "supports_structured_output": True,
    "supports_tool_choice": True,
    "supports_reasoning_summaries": True,
    # Required fields identified in the Codex catalog schema:
    "supports_search_tool": False,
    "apply_patch_tool_type": None,
    "default_verbosity": None,
    "input_modalities": ["text"],
    "experimental_supported_tools": [],
    "service_tiers": [],
    "availability_nux": None,
    "upgrade": None,
}


def build_codex_model_catalog(models: Sequence[CodexModel]) -> str:
    """Serialize custom Codex models into a deterministic catalog.

    Produces the ``{"models": [...]}`` format consumed by Codex CLI via the
    ``model_catalog_json`` config key.  Field names follow the exact schema
    from ``codex-rs/models-manager/models.json``:

    - ``default_reasoning_level`` — pre-selected reasoning effort string
    - ``supported_reasoning_levels`` — array of effort descriptor objects
    - ``max_context_window`` — hard context ceiling (set equal to context_window)
    - ``truncation_policy.limit`` — derived from the model's ``context_window``

    Omitting any field Codex treats as required causes the whole catalog to be
    discarded at startup, which is why ``DEFAULT_MODEL_CAPABILITIES`` includes
    all known required fields even when set to ``None`` / ``false`` / ``[]``.

    @param models: Typed provider models to include in the catalog.
    @returns: UTF-8-compatible JSON text terminated by a newline.
    """

    serialized_models = [
        {
            "slug": model.model_id,
            "display_name": model.display_name,
            "description": model.display_name,
            # Reasoning fields — must use "default_reasoning_level" (not "effort").
            "default_reasoning_level": "medium",
            "supported_reasoning_levels": SUPPORTED_REASONING_LEVELS,
            "priority": model.position,
            "base_instructions": CUSTOM_MODEL_BASE_INSTRUCTIONS,
            # Context / truncation — per-model values derived from context_window.
            "context_window": model.context_window,
            "max_context_window": model.context_window,
            "truncation_policy": {"mode": "tokens", "limit": model.context_window},
            **DEFAULT_MODEL_CAPABILITIES,
        }
        for model in sorted(models, key=lambda item: (item.position, item.model_id))
    ]
    return json.dumps({"models": serialized_models}, ensure_ascii=False, indent=2) + "\n"
