"""Foundry Ontology persistence — writes chat history to backing datasets.

Appends rows to the Foundry datasets that back the lobster-conversation and
lobster-message object types via the Foundry Dataset Transaction API.

Foundry incremental builds pick up new files automatically if the datasets
have a scheduled or incremental build configured. Until then, trigger a
manual build from the dataset page to see objects in Ontology Viewer.
"""
from __future__ import annotations

import datetime
import json
import logging
import uuid

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_client = httpx.AsyncClient(
    timeout=httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=5.0),
)

# Backing dataset RIDs from foundry-objects.json
_DATASETS = {
    "conversation": "ri.foundry.main.dataset.a41cdaa5-a6e0-4314-bc75-a533042a7d2f",
    "message":      "ri.foundry.main.dataset.c8ef81bd-515f-4eff-9796-9806b173f08a",
}


async def _append_row(dataset_rid: str, token: str, row: dict) -> None:
    """Open an APPEND transaction, upload a single-row JSONL file, commit."""
    settings = get_settings()
    base = settings.foundry_url
    auth = {"Authorization": f"Bearer {token}"}

    resp = await _client.post(
        f"{base}/api/v1/datasets/{dataset_rid}/transactions",
        json={"type": "APPEND"},
        headers=auth,
    )
    resp.raise_for_status()
    txn_rid = resp.json()["rid"]

    content = (json.dumps(row) + "\n").encode()
    file_name = f"{uuid.uuid4()}.jsonl"
    await _client.put(
        f"{base}/api/v1/datasets/{dataset_rid}/transactions/{txn_rid}/files/upload",
        params={"filePath": file_name},
        content=content,
        headers={**auth, "Content-Type": "application/octet-stream"},
    )

    await _client.post(
        f"{base}/api/v1/datasets/{dataset_rid}/transactions/{txn_rid}/commit",
        headers=auth,
    )
    logger.debug("ontology append txn=%s file=%s", txn_rid, file_name)


async def upsert_conversation(
    conversation_id: str,
    token: str,
    title: str = "",
) -> None:
    """Write (or overwrite) a lobster-conversation row."""
    try:
        await _append_row(
            _DATASETS["conversation"],
            token,
            {
                "conversationId": conversation_id,
                "title": title or conversation_id[:32],
                "createdAt": _now(),
            },
        )
    except Exception:
        logger.warning("upsert_conversation failed cid=%s", conversation_id[:8], exc_info=True)


async def append_message(
    conversation_id: str,
    role: str,
    content: str,
    token: str,
    message_id: str | None = None,
) -> str:
    """Append a lobster-message row linked to a conversation. Returns message_id."""
    mid = message_id or str(uuid.uuid4())
    try:
        await _append_row(
            _DATASETS["message"],
            token,
            {
                "messageId": mid,
                "conversationId": conversation_id,
                "role": role,
                "content": content,
                "createdAt": _now(),
            },
        )
    except Exception:
        logger.warning(
            "append_message failed cid=%s role=%s", conversation_id[:8], role, exc_info=True
        )
    return mid


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


async def close_client() -> None:
    await _client.aclose()
