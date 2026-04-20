"""OpenClaw WebSocket gateway client.

Connects to the OpenClaw gateway running on localhost:18789, performs the
challenge/connect handshake, and streams agent responses back as text deltas.

Protocol (custom envelope, not JSON-RPC):
  server → {"type":"event","event":"connect.challenge","payload":{"nonce":"<uuid>"}}
  client → {"type":"req","id":"<id>","method":"connect","params":{...,"auth":{"token":"..."}}}
  server → {"type":"res","id":"<id>","ok":true,"payload":{"type":"hello-ok",...}}
  client → {"type":"req","id":"<id>","method":"chat.send","params":{"sessionKey":"...","message":"..."}}
  server → {"type":"event","event":"chat.reply","payload":{"text":"..."}}  (0..n times)
  server → {"type":"event","event":"chat.complete","payload":{...}}
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

import websockets
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import get_settings
from app.models.chat import ChatMessage

logger = logging.getLogger(__name__)

# Ephemeral device key pair generated once per process lifetime.
# OpenClaw uses this to verify device identity alongside the gateway token.
_device_private_key = ec.generate_private_key(ec.SECP256R1())
_device_public_key = _device_private_key.public_key()
_DEVICE_ID = str(uuid.uuid4())

_PUB_KEY_B64 = base64.urlsafe_b64encode(
    _device_public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
).rstrip(b"=").decode()


def _sign_nonce(nonce: str) -> str:
    sig = _device_private_key.sign(nonce.encode(), ec.ECDSA(hashes.SHA256()))
    return base64.urlsafe_b64encode(sig).rstrip(b"=").decode()


async def stream_via_openclaw(
    messages: list[ChatMessage],
    conversation_id: str | None = None,
) -> AsyncIterator[str]:
    """Connect to OpenClaw, send the latest user message, yield reply deltas."""
    settings = get_settings()
    ws_url = f"ws://localhost:{settings.openclaw_port}"
    token = settings.openclaw_gateway_token
    session_key = conversation_id or str(uuid.uuid4())

    # Extract the last user message to send as the chat input.
    # OpenClaw manages conversation history internally via sessionKey.
    last_user_message = next(
        (m.content for m in reversed(messages) if m.role == "user"), ""
    )
    if not last_user_message:
        return

    connect_req_id = str(uuid.uuid4())
    chat_req_id = str(uuid.uuid4())

    async with websockets.connect(ws_url, open_timeout=10) as ws:
        # 1. Receive challenge
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        challenge = json.loads(raw)
        nonce = challenge["payload"]["nonce"]
        logger.debug("openclaw challenge nonce=%s", nonce[:8])

        # 2. Send connect request with device identity + token auth
        await ws.send(json.dumps({
            "type": "req",
            "id": connect_req_id,
            "method": "connect",
            "params": {
                "minProtocol": 1,
                "maxProtocol": 1,
                "client": {
                    "id": "lobster-gateway",
                    "displayName": "Lobster",
                    "version": "0.1.0",
                    "platform": "server",
                    "mode": "headless",
                },
                "role": "operator",
                "scopes": [],
                "device": {
                    "id": _DEVICE_ID,
                    "publicKey": _PUB_KEY_B64,
                    "signature": _sign_nonce(nonce),
                    "signedAt": int(time.time() * 1000),
                    "nonce": nonce,
                },
                "auth": {"token": token},
            },
        }))

        # 3. Wait for hello-ok
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = json.loads(raw)
            if msg.get("type") == "res" and msg.get("id") == connect_req_id:
                if not msg.get("ok"):
                    raise RuntimeError(f"OpenClaw auth failed: {msg.get('error')}")
                logger.debug("openclaw connected session=%s", session_key[:8])
                break

        # 4. Send chat message
        await ws.send(json.dumps({
            "type": "req",
            "id": chat_req_id,
            "method": "chat.send",
            "params": {
                "sessionKey": session_key,
                "message": last_user_message,
                "injectAsRole": "user",
                "injectTimestamp": True,
            },
        }))

        # 5. Stream reply events
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") != "event":
                continue
            event = msg.get("event", "")
            payload = msg.get("payload") or {}

            if event == "chat.reply":
                delta = (payload.get("text") or payload.get("delta")
                         or payload.get("content") or "")
                if delta:
                    yield delta
            elif event == "chat.complete":
                logger.debug("openclaw chat.complete session=%s", session_key[:8])
                break
            elif event.startswith("chat.error") or event == "error":
                raise RuntimeError(f"OpenClaw error event: {payload}")
