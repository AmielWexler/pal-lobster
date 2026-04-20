"""Anthropic API passthrough for OpenClaw.

OpenClaw is started with ANTHROPIC_BASE_URL=http://localhost:8080/llm/proxy/anthropic/v1
so all its Claude API calls land here. This route injects MODULE_AUTH_TOKEN and
forwards transparently to Foundry's LLM proxy, preserving streaming.
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared client — reuse across requests
_client = httpx.AsyncClient(
    timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0),
    http2=True,
)


@router.api_route("/llm/proxy/anthropic/v1/{path:path}", methods=["POST", "GET"])
async def anthropic_passthrough(path: str, request: Request) -> StreamingResponse:
    """Forward Anthropic-format requests to Foundry's LLM proxy with server token.

    Uses MODULE_AUTH_TOKEN (injected by the Foundry CM runtime into every process
    in the container) rather than the per-user token — these are OpenClaw's own
    model calls, not user-delegated calls.
    """
    settings = get_settings()
    token = os.environ.get("MODULE_AUTH_TOKEN", "")
    if not token:
        logger.warning("MODULE_AUTH_TOKEN not set — LLM proxy calls will fail auth")

    target_url = f"{settings.llm_proxy_anthropic_url}/{path}"
    body = await request.body()

    forward_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": request.headers.get("Content-Type", "application/json"),
        "Accept": request.headers.get("Accept", "application/json"),
        "anthropic-version": request.headers.get("anthropic-version", "2023-06-01"),
    }

    logger.debug("anthropic_passthrough path=%s target=%s", path, target_url)

    async def stream_response():
        async with _client.stream("POST", target_url, content=body,
                                  headers=forward_headers) as resp:
            if resp.status_code >= 400:
                error_body = await resp.aread()
                logger.error("Foundry LLM proxy error status=%d body=%s",
                             resp.status_code, error_body[:200])
            async for chunk in resp.aiter_bytes():
                yield chunk

    return StreamingResponse(
        stream_response(),
        media_type=request.headers.get("Accept", "application/json"),
        headers={"X-Accel-Buffering": "no"},
    )
