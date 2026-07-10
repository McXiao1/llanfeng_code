from __future__ import annotations

APP_NAME = "lanfeng_code"
APP_DISPLAY_NAME = "Codex / Claude 一键配置"
PROTOCOL_SCHEME = "llanfeng-code"

CODEX_PACKAGE = "@openai/codex"
CODEX_VERSION = "0.144.1"
CLAUDE_PACKAGE = "@anthropic-ai/claude-code"
CLAUDE_VERSION = "2.1.201"

NPM_MIRROR_REGISTRY = "https://registry.npmmirror.com/"
MIN_NODE_VERSION = "22.0.0"

ANTHROPIC_VERSION = "2023-06-01"
KEYRING_SERVICE = "llanfeng-code-assistant"

# GitHub releases API — used by the in-app update checker.
# Format: https://api.github.com/repos/{owner}/{repo}/releases/latest
GITHUB_RELEASES_LATEST_URL = (
    "https://api.github.com/repos/McXiao1/llanfeng_code/releases/latest"
)
