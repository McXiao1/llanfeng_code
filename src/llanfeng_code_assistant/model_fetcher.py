from __future__ import annotations

from collections.abc import Iterable

import httpx

from .constants import ANTHROPIC_VERSION
from .models import ModelInfo

KNOWN_COMPAT_SUFFIXES = (
    "/api/claudecode",
    "/api/anthropic",
    "/apps/anthropic",
    "/api/coding",
    "/claudecode",
    "/anthropic",
    "/step_plan",
    "/coding",
    "/claude",
)


def redact_secret(message: str, secret: str) -> str:
    """Remove secret text from an error string.

    @param message: Error message.
    @param secret: Secret to redact.
    @returns: Redacted message.
    """

    return message.replace(secret, "***") if secret else message


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _ends_with_version_segment(url: str) -> bool:
    last = url.rsplit("/", 1)[-1]
    return len(last) > 1 and last.startswith("v") and last[1:].isdigit()


def _strip_compat_suffix(url: str) -> str | None:
    for suffix in KNOWN_COMPAT_SUFFIXES:
        if url.endswith(suffix):
            return url[: -len(suffix)]
    return None


def build_model_url_candidates(
    base_url: str,
    is_full_url: bool = False,
    override: str | None = None,
) -> list[str]:
    """Build OpenAI-compatible model endpoint candidates.

    @param base_url: Provider base URL or full chat endpoint.
    @param is_full_url: Whether `base_url` is a full request endpoint.
    @param override: Explicit models endpoint.
    @returns: Candidate URLs in retry order.
    @throws ValueError: If a candidate cannot be derived.
    """

    if override and override.strip():
        return [override.strip()]
    trimmed = base_url.strip().rstrip("/")
    if not trimmed:
        raise ValueError("base_url is required")

    candidates: list[str] = []
    if is_full_url:
        if "/v1/" in trimmed:
            root = trimmed.split("/v1/", 1)[0]
            candidates.append(f"{root}/v1/models")
        else:
            root = trimmed.rsplit("/", 1)[0]
            if "://" in root:
                candidates.append(f"{root}/v1/models")
        if not candidates:
            raise ValueError("Cannot derive models endpoint from full URL")
        return _dedupe(candidates)

    if _ends_with_version_segment(trimmed):
        candidates.append(f"{trimmed}/models")
        if not trimmed.endswith("/v1"):
            candidates.append(f"{trimmed}/v1/models")
    else:
        candidates.append(f"{trimmed}/v1/models")

    stripped = _strip_compat_suffix(trimmed)
    if stripped and "://" in stripped:
        root = stripped.rstrip("/")
        candidates.extend([f"{root}/v1/models", f"{root}/models"])
    return _dedupe(candidates)


def _normalized_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _positive_integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.isdecimal():
            parsed = int(normalized)
            return parsed if parsed > 0 else None
    return None


def _parse_models(payload: object) -> list[ModelInfo]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    models: list[ModelInfo] = []
    seen_ids: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = _normalized_string(item.get("id"))
        if model_id is None or len(model_id) > 200 or model_id in seen_ids:
            continue
        seen_ids.add(model_id)
        display_name = (
            _normalized_string(item.get("display_name"))
            or _normalized_string(item.get("name"))
            or model_id
        )
        context_window = _positive_integer(item.get("context_window"))
        if context_window is None:
            context_window = _positive_integer(item.get("max_context_window"))
        if context_window is None:
            context_window = _positive_integer(item.get("input_token_limit"))
        if context_window is None:
            context_window = _positive_integer(item.get("max_input_tokens"))
        models.append(
            ModelInfo(
                id=model_id,
                display_name=display_name,
                context_window=context_window,
                owned_by=_normalized_string(item.get("owned_by")),
            )
        )
    return models


class ModelFetcher:
    """Fetch provider model lists with redacted errors.

    @param client: Optional shared asynchronous HTTP client.
    @param timeout_seconds: Timeout used when creating an HTTP client.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def _client_or_new(self) -> tuple[httpx.AsyncClient, bool]:
        if self._client:
            return self._client, False
        return httpx.AsyncClient(timeout=self._timeout_seconds), True

    async def fetch_openai_compatible(
        self,
        base_url: str,
        api_key: str,
        is_full_url: bool = False,
        override: str | None = None,
    ) -> list[ModelInfo]:
        """Fetch models from OpenAI-compatible endpoints.

        @param base_url: Provider base URL.
        @param api_key: API key.
        @param is_full_url: Whether `base_url` is a full endpoint.
        @param override: Optional explicit `/models` URL.
        @returns: Model list in provider response order.
        @throws ValueError: If the API key or endpoint input is invalid.
        @throws RuntimeError: If every endpoint fails or returns invalid model data.
        """

        if not api_key.strip():
            raise ValueError("api_key is required")
        candidates = build_model_url_candidates(base_url, is_full_url, override)
        client, should_close = await self._client_or_new()
        candidate_errors: list[str] = []
        try:
            for url in candidates:
                try:
                    response = await client.get(
                        url,
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                except httpx.HTTPError as exc:
                    candidate_errors.append(str(exc))
                    continue
                if response.status_code >= 400:
                    candidate_errors.append(
                        f"HTTP {response.status_code}: {response.text[:256]}"
                    )
                    continue
                try:
                    payload = response.json()
                except ValueError as exc:
                    candidate_errors.append(f"invalid JSON from {url}: {exc}")
                    continue
                models = _parse_models(payload)
                if models:
                    return models
                candidate_errors.append(f"no valid models returned by {url}")
        finally:
            if should_close:
                await client.aclose()
        error_details = "; ".join(candidate_errors) or "no response"
        raise RuntimeError(
            redact_secret(f"All model endpoints failed: {error_details}", api_key)
        )

    async def fetch_claude(self, base_url: str, api_key: str) -> list[ModelInfo]:
        """Fetch models from a Claude/Anthropic-compatible endpoint.

        @param base_url: Provider base URL.
        @param api_key: API key.
        @returns: Model list in provider response order.
        @throws ValueError: If the API key is blank.
        @throws RuntimeError: If the request or response data is invalid.
        """

        if not api_key.strip():
            raise ValueError("api_key is required")
        url = f"{base_url.strip().rstrip('/')}/v1/models"
        client, should_close = await self._client_or_new()
        try:
            response = await client.get(
                url,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "Authorization": f"Bearer {api_key}",
                },
            )
            if response.status_code >= 400:
                message = f"HTTP {response.status_code}: {response.text}"
                raise RuntimeError(redact_secret(message, api_key))
            try:
                payload = response.json()
            except ValueError as exc:
                message = f"invalid JSON response from {url}: {exc}"
                raise RuntimeError(redact_secret(message, api_key)) from exc
            models = _parse_models(payload)
            if not models:
                raise RuntimeError("Provider returned no valid models")
            return models
        except httpx.HTTPError as exc:
            raise RuntimeError(redact_secret(str(exc), api_key)) from exc
        finally:
            if should_close:
                await client.aclose()
