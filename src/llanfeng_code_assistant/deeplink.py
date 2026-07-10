from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from .constants import PROTOCOL_SCHEME
from .models import ImportRequest


def _single(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key)
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _parse_bool(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "on"}


def _request_from_values(
    *,
    target: Any,
    name: Any,
    base_url: Any,
    api_key: Any,
    model: Any = None,
    enabled: Any = False,
) -> ImportRequest:
    if target not in {"codex", "claude"}:
        raise ValueError("target must be codex or claude")
    if not isinstance(name, str) or not isinstance(base_url, str) or not isinstance(api_key, str):
        raise ValueError("name, url, and key are required")
    if not name.strip() or not base_url.strip() or not api_key.strip():
        raise ValueError("name, url, and key are required")
    return ImportRequest(
        target=target,
        name=name.strip(),
        base_url=base_url.strip().rstrip("/"),
        api_key=api_key.strip(),
        model=model.strip() if isinstance(model, str) and model.strip() else None,
        enabled=enabled if isinstance(enabled, bool) else _parse_bool(str(enabled)),
    )


def _decode_payload(payload: str) -> Any:
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(f"{payload}{padding}".encode())
        return json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("payload must be base64url encoded JSON") from exc


def _request_from_mapping(item: Any) -> ImportRequest:
    if not isinstance(item, dict):
        raise ValueError("profile list items must be objects")
    return _request_from_values(
        target=item.get("target"),
        name=item.get("name"),
        base_url=item.get("url") or item.get("base_url"),
        api_key=item.get("key") or item.get("api_key"),
        model=item.get("model"),
        enabled=item.get("enabled", False),
    )


def parse_deeplink(url: str) -> ImportRequest:
    """Parse a `llanfeng-code://` provider import URL.

    @param url: Deep link URL.
    @returns: Parsed import request.
    @throws ValueError: If protocol or required fields are invalid.
    """

    parsed = urlparse(url)
    if parsed.scheme != PROTOCOL_SCHEME:
        raise ValueError("Unsupported protocol")
    if parsed.netloc != "v1" or parsed.path.rstrip("/") != "/import":
        raise ValueError("Unsupported deep link path")

    params = parse_qs(parsed.query, keep_blank_values=False)
    return _request_from_values(
        target=_single(params, "target"),
        name=_single(params, "name"),
        base_url=_single(params, "url"),
        api_key=_single(params, "key"),
        model=_single(params, "model"),
        enabled=_parse_bool(_single(params, "enabled")),
    )


def parse_deeplink_requests(url: str) -> list[ImportRequest]:
    """Parse a single-profile or list-profile import URL.

    @param url: Deep link URL.
    @returns: One or more parsed import requests.
    @throws ValueError: If protocol, path, payload, or fields are invalid.
    """

    parsed = urlparse(url)
    if parsed.scheme != PROTOCOL_SCHEME:
        raise ValueError("Unsupported protocol")
    if parsed.netloc == "v1" and parsed.path.rstrip("/") == "/import":
        return [parse_deeplink(url)]
    if parsed.netloc != "v1" or parsed.path.rstrip("/") != "/import-list":
        raise ValueError("Unsupported deep link path")

    params = parse_qs(parsed.query, keep_blank_values=False)
    payload = _single(params, "payload")
    if not payload:
        raise ValueError("payload is required")

    decoded = _decode_payload(payload)
    profiles = decoded.get("profiles") if isinstance(decoded, dict) else decoded
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("payload must contain a non-empty profile list")
    return [_request_from_mapping(item) for item in profiles]
