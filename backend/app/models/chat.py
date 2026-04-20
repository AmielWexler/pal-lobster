from typing import Literal, Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: Optional[str] = None
    conversation_id: Optional[str] = None
    max_tokens: int = 4096


class ChatChunk(BaseModel):
    """Single SSE chunk sent to the client."""
    delta: str
    conversation_id: Optional[str] = None
    done: bool = False
