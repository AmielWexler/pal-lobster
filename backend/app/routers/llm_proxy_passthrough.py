"""OpenAI-format passthrough for OpenClaw.

OpenClaw is configured with baseUrl=http://localhost:8080/llm/proxy/openai/v1
and api=openai-completions, so it sends native OpenAI Chat Completions requests
here. This route injects MODULE_AUTH_TOKEN and forwards transparently to
Foundry's OpenAI-compatible LLM proxy, preserving streaming.
"""
from __future__ import annotations

import json
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

_STRIP_KEYS: frozenset[str] = frozenset()  # nothing to strip for OpenAI format

_client = httpx.AsyncClient(
    timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0),
    http2=True,
)


@router.api_route("/llm/proxy/openai/v1/{path:path}", methods=["POST", "GET"])
async def openai_passthrough(path: str, request: Request) -> StreamingResponse:
    """Inject auth and forward OpenAI-format requests to Foundry's LLM proxy."""
    settings = get_settings()
    token = settings.module_auth_token
    if not token:
        logger.warning("MODULE_AUTH_TOKEN not set — LLM proxy calls will fail auth")

    target_url = f"{settings.foundry_url}/api/v2/llm/proxy/openai/v1/{path}"
    body = await request.body()

    forward_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": request.headers.get("Accept", "application/json"),
    }

    logger.info("openai_passthrough path=%s target=%s body_len=%d", path, target_url, len(body))

    async def stream_response():
        async with _client.stream("POST", target_url, content=body,
                                  headers=forward_headers) as resp:
            if resp.status_code >= 400:
                error_body = await resp.aread()
                logger.error("Foundry LLM proxy error status=%d body=%s",
                             resp.status_code, error_body[:300])
            async for chunk in resp.aiter_bytes():
                yield chunk

    return StreamingResponse(
        stream_response(),
        media_type=request.headers.get("Accept", "application/json"),
        headers={"X-Accel-Buffering": "no"},
    )
