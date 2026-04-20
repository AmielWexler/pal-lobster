"""Foundry Compute Module handler.

Bridges Foundry function invocations to the internal FastAPI server running
on localhost:8080. The CM polling loop runs as a separate process (see
supervisord.conf); FastAPI starts first (priority 10).

Each function extracts the Foundry OAuth token from context.auth_token and
forwards it as a Bearer header so FastAPI can authenticate outbound LLM calls
without storing credentials.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional

import httpx
from compute_modules.annotations import function

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

FASTAPI_BASE = "http://localhost:8080"
FASTAPI_STARTUP_RETRIES = 15
FASTAPI_RETRY_DELAY = 2.0


def _wait_for_fastapi() -> None:
    """Block until FastAPI health endpoint responds."""
    for attempt in range(FASTAPI_STARTUP_RETRIES):
        try:
            httpx.get(f"{FASTAPI_BASE}/health", timeout=3.0).raise_for_status()
            logger.info("FastAPI is healthy")
            return
        except Exception:
            logger.info("Waiting for FastAPI... attempt %d/%d", attempt + 1, FASTAPI_STARTUP_RETRIES)
            time.sleep(FASTAPI_RETRY_DELAY)
    raise RuntimeError("FastAPI did not become healthy in time")


_fastapi_ready = False


def _ensure_ready() -> None:
    global _fastapi_ready
    if not _fastapi_ready:
        _wait_for_fastapi()
        _fastapi_ready = True


# ── Input schemas ─────────────────────────────────────────────────────────────

@dataclass
class Message:
    role: str
    content: str


@dataclass
class ChatInput:
    messages: list[Message]
    model: Optional[str] = None
    conversation_id: Optional[str] = None
    max_tokens: int = 4096


@dataclass
class EmptyInput:
    pass


# ── Functions ─────────────────────────────────────────────────────────────────

@function(streaming=True)
def chat(context, event: ChatInput) -> Iterable[str]:
    """Stream a chat completion through FastAPI → Foundry LLM proxy."""
    _ensure_ready()

    token = context.auth_token.token
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "messages": [{"role": m.role, "content": m.content} for m in event.messages],
        "model": event.model,
        "conversation_id": event.conversation_id,
        "max_tokens": event.max_tokens,
    }

    with httpx.Client(timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)) as client:
        with client.stream("POST", f"{FASTAPI_BASE}/chat", json=payload, headers=headers) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    yield line[6:]  # raw JSON chunk — CM SDK serialises back to caller


@function
def health_check(context, event: EmptyInput) -> dict:
    _ensure_ready()
    resp = httpx.get(f"{FASTAPI_BASE}/health", timeout=5.0)
    resp.raise_for_status()
    return resp.json()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from compute_modules.runner import run
    run()
