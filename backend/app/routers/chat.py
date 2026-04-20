import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.auth import require_token
from app.config import get_settings
from app.models.chat import ChatRequest
from app.services.llm_proxy import LLMRateLimitError, LLMUnavailableError, stream_chat
from app.services.openclaw_gateway import stream_via_openclaw

logger = logging.getLogger(__name__)
router = APIRouter()


async def _sse_stream(
    token: str,
    request: ChatRequest,
) -> AsyncIterator[str]:
    """Format LLM delta chunks as SSE events."""
    settings = get_settings()
    full_text = []
    try:
        if settings.use_openclaw_gateway:
            source = stream_via_openclaw(request.messages, request.conversation_id)
        else:
            source = stream_chat(token, request.messages, request.model)

        async for delta in source:
            full_text.append(delta)
            payload = json.dumps({"delta": delta, "done": False,
                                  "conversation_id": request.conversation_id})
            yield f"data: {payload}\n\n"
    except LLMRateLimitError as e:
        err = json.dumps({"error": "rate_limited", "retry_after": e.retry_after})
        yield f"event: error\ndata: {err}\n\n"
        return
    except LLMUnavailableError:
        err = json.dumps({"error": "llm_unavailable"})
        yield f"event: error\ndata: {err}\n\n"
        return
    except Exception:
        logger.exception("stream_chat failed")
        err = json.dumps({"error": "internal_error"})
        yield f"event: error\ndata: {err}\n\n"
        return

    done_payload = json.dumps({"delta": "", "done": True,
                               "conversation_id": request.conversation_id})
    yield f"data: {done_payload}\n\n"
    logger.info("chat completed tokens_approx=%d via=%s",
                sum(len(t) for t in full_text) // 4,
                "openclaw" if settings.use_openclaw_gateway else "llm_proxy")


@router.post("/chat")
async def chat(
    request: ChatRequest,
    token: str = Depends(require_token),
) -> StreamingResponse:
    if not request.messages:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="messages must not be empty")

    return StreamingResponse(
        _sse_stream(token, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
