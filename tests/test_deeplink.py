from __future__ import annotations

import base64
import json

import pytest

from llanfeng_code_assistant.deeplink import parse_deeplink, parse_deeplink_requests


def test_parse_provider_deeplink_normalizes_fields() -> None:
    request = parse_deeplink(
        "llanfeng-code://v1/import?"
        "target=codex&name=Relay&url=https%3A%2F%2Fapi.example.com%2Fv1%2F"
        "&key=sk-test&model=gpt-5-codex&enabled=true"
    )

    assert request.target == "codex"
    assert request.name == "Relay"
    assert request.base_url == "https://api.example.com/v1"
    assert request.api_key == "sk-test"
    assert request.model == "gpt-5-codex"
    assert request.enabled is True


def test_parse_deeplink_rejects_unknown_protocol_or_target() -> None:
    with pytest.raises(ValueError, match="Unsupported protocol"):
        parse_deeplink("other://v1/import?target=codex")

    with pytest.raises(ValueError, match="target"):
        parse_deeplink("llanfeng-code://v1/import?target=gemini&name=x&url=https://x&key=k")


def test_parse_deeplink_requests_accepts_base64url_profile_list() -> None:
    payload = base64.urlsafe_b64encode(
        json.dumps(
            [
                {
                    "target": "codex",
                    "name": "Codex Relay",
                    "url": "https://codex.example.com/v1/",
                    "key": "sk-codex",
                    "model": "gpt-5-codex",
                },
                {
                    "target": "claude",
                    "name": "Claude Relay",
                    "url": "https://claude.example.com",
                    "key": "sk-claude",
                    "model": "claude-sonnet-4-5",
                },
            ],
            separators=(",", ":"),
        ).encode()
    ).decode().rstrip("=")

    requests = parse_deeplink_requests(f"llanfeng-code://v1/import-list?payload={payload}")

    assert [item.target for item in requests] == ["codex", "claude"]
    assert requests[0].base_url == "https://codex.example.com/v1"
    assert requests[1].api_key == "sk-claude"
