from __future__ import annotations

import httpx
import pytest

from llanfeng_code_assistant.model_fetcher import (
    ModelFetcher,
    build_model_url_candidates,
    redact_secret,
)


def test_build_model_url_candidates_handles_roots_versions_and_full_urls() -> None:
    assert build_model_url_candidates("https://api.example.com", False, None) == [
        "https://api.example.com/v1/models"
    ]
    assert build_model_url_candidates("https://api.example.com/v1", False, None) == [
        "https://api.example.com/v1/models"
    ]
    assert build_model_url_candidates(
        "https://proxy.example.com/v1/chat/completions", True, None
    ) == ["https://proxy.example.com/v1/models"]
    assert build_model_url_candidates("https://api.deepseek.com/anthropic", False, None) == [
        "https://api.deepseek.com/anthropic/v1/models",
        "https://api.deepseek.com/v1/models",
        "https://api.deepseek.com/models",
    ]


@pytest.mark.asyncio
async def test_fetch_openai_models_tries_candidates_and_preserves_order() -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if str(request.url).endswith("/anthropic/v1/models"):
            return httpx.Response(404, json={"error": "missing"})
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "z-model", "owned_by": "relay"},
                    {"id": "a-model", "owned_by": "relay"},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = ModelFetcher(client=client)
        models = await fetcher.fetch_openai_compatible(
            "https://api.deepseek.com/anthropic", "sk-secret"
        )

    assert [model.id for model in models] == ["z-model", "a-model"]
    assert seen_urls == [
        "https://api.deepseek.com/anthropic/v1/models",
        "https://api.deepseek.com/v1/models",
    ]


@pytest.mark.asyncio
async def test_fetch_claude_models_uses_anthropic_headers() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(
            200,
            json={"data": [{"id": "claude-sonnet-4-5", "display_name": "Sonnet"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await ModelFetcher(client=client).fetch_claude(
            "https://api.anthropic.com", "sk-ant"
        )

    assert [model.id for model in models] == ["claude-sonnet-4-5"]
    assert captured_headers["x-api-key"] == "sk-ant"
    assert "anthropic-version" in captured_headers


@pytest.mark.asyncio
async def test_fetch_models_normalizes_metadata_and_deduplicates_ids() -> None:
    payload = {
        "data": [
            "invalid",
            {"id": "   ", "display_name": "blank"},
            {"id": 123, "display_name": "numeric"},
            {
                "id": " z-model ",
                "display_name": " Zed ",
                "name": "Ignored",
                "owned_by": " owner-z ",
                "context_window": 128000,
                "max_context_window": 256000,
            },
            {
                "id": "z-model",
                "display_name": "Duplicate",
                "owned_by": "duplicate-owner",
                "context_window": 999999,
            },
            {
                "id": " a-model ",
                "display_name": "   ",
                "name": " Alpha ",
                "owned_by": "owner-a",
                "context_window": True,
                "max_context_window": "64000",
            },
            {
                "id": "b-model",
                "name": " Bee ",
                "context_window": 1.5,
                "max_context_window": 0,
            },
            {
                "id": "c-model",
                "display_name": "   ",
                "name": "   ",
                "owned_by": None,
                "context_window": -1,
                "max_context_window": "invalid",
            },
            {
                "id": "d-model",
                "display_name": "Delta",
                "input_token_limit": "32000",
            },
            {
                "id": "e-model",
                "display_name": "Echo",
                "max_input_tokens": 48000,
            },
        ]
    }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await ModelFetcher(client=client).fetch_openai_compatible(
            "https://api.example.com",
            "sk-secret",
            override="https://api.example.com/models",
        )

    assert [model.model_dump() for model in models] == [
        {
            "id": "z-model",
            "display_name": "Zed",
            "context_window": 128_000,
            "owned_by": "owner-z",
        },
        {
            "id": "a-model",
            "display_name": "Alpha",
            "context_window": 64_000,
            "owned_by": "owner-a",
        },
        {
            "id": "b-model",
            "display_name": "Bee",
            "context_window": None,
            "owned_by": None,
        },
        {
            "id": "c-model",
            "display_name": "c-model",
            "context_window": None,
            "owned_by": None,
        },
        {
            "id": "d-model",
            "display_name": "Delta",
            "context_window": 32_000,
            "owned_by": None,
        },
        {
            "id": "e-model",
            "display_name": "Echo",
            "context_window": 48_000,
            "owned_by": None,
        },
    ]


@pytest.mark.asyncio
async def test_fetch_models_skips_ids_longer_than_model_info_limit() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"id": f" {'x' * 201} "}, {"id": "valid-model"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await ModelFetcher(client=client).fetch_openai_compatible(
            "https://api.example.com",
            "sk-secret",
            override="https://api.example.com/models",
        )

    assert [model.id for model in models] == ["valid-model"]


@pytest.mark.asyncio
async def test_fetch_openai_models_continues_after_success_with_no_valid_models() -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if str(request.url).endswith("/anthropic/v1/models"):
            return httpx.Response(200, json={"data": [{"id": "   "}]})
        return httpx.Response(200, json={"data": [{"id": "usable-model"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await ModelFetcher(client=client).fetch_openai_compatible(
            "https://api.example.com/anthropic",
            "sk-secret",
        )

    assert [model.id for model in models] == ["usable-model"]
    assert seen_urls == [
        "https://api.example.com/anthropic/v1/models",
        "https://api.example.com/v1/models",
    ]


@pytest.mark.asyncio
async def test_fetch_openai_models_raises_when_response_has_no_valid_models() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "   "}, {"name": "missing-id"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError, match="no valid models"):
            await ModelFetcher(client=client).fetch_openai_compatible(
                "https://api.example.com",
                "sk-secret",
                override="https://api.example.com/models",
            )


@pytest.mark.asyncio
async def test_fetch_openai_models_aggregates_empty_success_and_later_http_errors() -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if str(request.url).endswith("/anthropic/v1/models"):
            return httpx.Response(200, json={"data": [{"id": "   "}]})
        if str(request.url).endswith("/v1/models"):
            return httpx.Response(500, text="upstream failed for sk-secret")
        return httpx.Response(404, text="missing")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError) as exc_info:
            await ModelFetcher(client=client).fetch_openai_compatible(
                "https://api.example.com/anthropic",
                "sk-secret",
            )

    message = str(exc_info.value)
    assert "no valid models" in message
    assert "HTTP 500" in message
    assert "sk-secret" not in message
    assert seen_urls == [
        "https://api.example.com/anthropic/v1/models",
        "https://api.example.com/v1/models",
        "https://api.example.com/models",
    ]


@pytest.mark.asyncio
async def test_fetch_openai_models_aggregates_empty_success_and_transport_error() -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if str(request.url).endswith("/v2/models"):
            return httpx.Response(200, json={"data": [{"id": "   "}]})
        raise httpx.ConnectError("connection failed for sk-secret", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError) as exc_info:
            await ModelFetcher(client=client).fetch_openai_compatible(
                "https://api.example.com/v2",
                "sk-secret",
            )

    message = str(exc_info.value)
    assert "no valid models" in message
    assert "connection failed" in message
    assert "sk-secret" not in message
    assert seen_urls == [
        "https://api.example.com/v2/models",
        "https://api.example.com/v2/v1/models",
    ]


@pytest.mark.asyncio
async def test_fetch_openai_models_reports_transport_error_without_prior_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed for sk-secret", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError) as exc_info:
            await ModelFetcher(client=client).fetch_openai_compatible(
                "https://api.example.com",
                "sk-secret",
                override="https://api.example.com/models",
            )

    message = str(exc_info.value)
    assert "connection failed" in message
    assert "sk-secret" not in message


@pytest.mark.asyncio
async def test_fetch_openai_models_continues_after_invalid_json_response() -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if str(request.url).endswith("/v2/models"):
            return httpx.Response(200, text="invalid JSON for sk-secret")
        return httpx.Response(200, json={"data": [{"id": "usable-model"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await ModelFetcher(client=client).fetch_openai_compatible(
            "https://api.example.com/v2",
            "sk-secret",
        )

    assert [model.id for model in models] == ["usable-model"]
    assert seen_urls == [
        "https://api.example.com/v2/models",
        "https://api.example.com/v2/v1/models",
    ]


@pytest.mark.asyncio
async def test_fetch_openai_models_aggregates_invalid_json_responses() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="invalid JSON for sk-secret")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError) as exc_info:
            await ModelFetcher(client=client).fetch_openai_compatible(
                "https://api.example.com/v2",
                "sk-secret",
            )

    message = str(exc_info.value)
    assert "invalid JSON" in message
    assert "https://api.example.com/v2/models" in message
    assert "https://api.example.com/v2/v1/models" in message
    assert "sk-secret" not in message


@pytest.mark.asyncio
async def test_fetch_claude_models_wraps_invalid_json_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="invalid JSON for sk-ant")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError) as exc_info:
            await ModelFetcher(client=client).fetch_claude(
                "https://api.anthropic.com",
                "sk-ant",
            )

    message = str(exc_info.value)
    assert "invalid JSON" in message
    assert "sk-ant" not in message
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.asyncio
async def test_fetch_claude_models_raises_when_response_has_no_valid_models() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError, match="no valid models"):
            await ModelFetcher(client=client).fetch_claude(
                "https://api.anthropic.com",
                "sk-ant",
            )


def test_redact_secret_removes_sensitive_text() -> None:
    assert redact_secret("HTTP 401 for sk-secret", "sk-secret") == "HTTP 401 for ***"
