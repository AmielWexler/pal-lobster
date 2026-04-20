"""Foundry LLM proxy — streams OpenAI-compatible completions using Foundry OAuth."""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.config import get_settings
from app.models.chat import ChatMessage

logger = logging.getLogger(__name__)

# Reuse a single async client across requests
_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0),
            http2=True,
        )
    return _client


async def close_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()


async def stream_chat(
    token: str,
    messages: list[ChatMessage],
    model: str | None = None,
) -> AsyncIterator[str]:
    """Yield raw SSE lines from the Foundry LLM proxy.

    Foundry's LLM proxy mirrors the OpenAI chat completions API with
    streaming. Each yielded string is a decoded text/event-stream line.
    """
    settings = get_settings()
    resolved_model = model or settings.default_model

    payload = {
        "model": resolved_model,
        "messages": [m.model_dump() for m in messages],
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    logger.info("llm_proxy stream_chat model=%s messages=%d", resolved_model, len(messages))

    async with get_client().stream(
        "POST",
        settings.llm_proxy_url,
        json=payload,
        headers=headers,
    ) as response:
        if response.status_code == 429:
            raise LLMRateLimitError(response.headers.get("Retry-After"))
        if response.status_code == 503:
            raise LLMUnavailableError()
        response.raise_for_status()

        async for line in response.aiter_lines():
            if not line or line == "data: [DONE]":
                continue
            if line.startswith("data: "):
                raw = line[6:]
                try:
                    chunk = json.loads(raw)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError, IndexError):
                    logger.debug("unparseable chunk: %s", raw)


class LLMRateLimitError(Exception):
    def __init__(self, retry_after: str | None = None):
        self.retry_after = retry_after


class LLMUnavailableError(Exception):
    pass
