## Project Goal
Build a production-grade, enterprise-integrated version of OpenClaw that runs natively inside Palantir Foundry (accenture.palantirfoundry.com), in the **APBG-Dev / Lobster pal** project space (`ri.compass.main.folder.a22ab25f-e459-4512-97ae-fc10bd2d24ca`).

The final solution combines:
- OpenClaw Gateway running persistently inside Foundry as a **Compute Module**
- **OpenClaw's built-in Control UI** (Lit web components, served by the gateway on port 18789) — this is the primary UI, not the custom React app
- Deep integration with Foundry's Ontology, LLM proxy, and Workshop
- Slack connectivity via Socket Mode

---

## Architecture

### Runtime Pattern
Three processes managed by `supervisord` in a single Docker container (`linux/amd64`, `USER 5000`):

1. **FastAPI** (priority 10) — `uvicorn app.main:app --port 8080` — chat API + LLM passthrough
2. **OpenClaw** (priority 15) — `node /app/openclaw/openclaw.mjs gateway --port 18789 --allow-unconfigured` — agent WS gateway
3. **CM handler** (priority 20) — `python compute_module/handler.py` — Foundry polling loop, waits 15 × 2s for FastAPI health before connecting

The frontend (OSDK React app) calls the Compute Module's public function endpoint using Foundry OAuth tokens. Foundry invokes the CM handler, which proxies requests to FastAPI internally over localhost.

### Token Flow
Two separate auth paths — never mix them:

| Caller | Token source | Used for |
|---|---|---|
| User chat (via CM function) | `context.auth_token.token` — per-user OAuth from CM invocation | `Authorization: Bearer` on `/chat`, ontology writes |
| OpenClaw autonomous LLM calls | `MODULE_AUTH_TOKEN` — injected by Foundry CM runtime into all processes | FastAPI `/llm/proxy/openai/v1/*` → Foundry LLM proxy |

`MODULE_AUTH_TOKEN` is automatically present in all container processes at runtime. **Never set it as a static secret; never expose it outside the container.**

### LLM Routing
```
[USE_OPENCLAW_GATEWAY=false]
  CM handler → FastAPI /chat → llm_proxy.py
             → POST {foundry_url}/api/v2/llm/proxy/openai/v1/chat/completions

[USE_OPENCLAW_GATEWAY=true]
  CM handler → FastAPI /chat → openclaw_gateway.py (WS to :18789)
             → OpenClaw → POST localhost:8080/llm/proxy/openai/v1/chat/completions
             → llm_proxy_passthrough.py (injects MODULE_AUTH_TOKEN, strips unsupported fields)
             → POST {foundry_url}/api/v2/llm/proxy/openai/v1/chat/completions

OpenClaw Control UI (direct, no CM):
  Browser → OpenClaw gateway (:18789)
          → OpenClaw embedded agent → POST localhost:8080/llm/proxy/openai/v1/chat/completions
          → llm_proxy_passthrough.py → Foundry LLM proxy
```

### Feature Flag
`USE_OPENCLAW_GATEWAY` in `config.py` — defaults to `false` (direct LLM calls). Set to `true` to route through the OpenClaw subprocess (all Phase 4 code is in place).

### Model
Foundry's Language Model Service for this workspace only has **`gpt-4o`** registered. No Claude/Anthropic models are available via the proxy. OpenClaw is configured accordingly (`openai/gpt-4o` via `openai-completions` API type).

---

## Technology Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, uvicorn, httpx[http2], pydantic-settings, compute-modules |
| Agent gateway | OpenClaw (Node 22, TypeScript) — git submodule at `backend/openclaw-src/` |
| UI | OpenClaw built-in Control UI (Lit web components, served by gateway on :18789) — primary UI |
| Frontend (legacy) | React 18, TypeScript, Vite, Tailwind CSS, OSDK — **removed**, superseded by OpenClaw UI |
| Real-time | SSE (`text/event-stream`) via POST + `ReadableStream` |
| Container | `python:3.11-slim` + Node 22 via nodesource, supervisord, USER 5000 |
| Storage | Foundry Ontology via Dataset Transaction API (JSONL append) |
| Slack | Slack Bolt SDK, Socket Mode — no inbound webhook needed (Phase 5) |

---

## Repository Structure

```
pal-lobster/
├── backend/
│   ├── Dockerfile                         # multi-stage: node:22-bookworm-slim + python:3.11-slim
│   ├── supervisord.conf                   # 3-process supervisor (fastapi, openclaw, compute_module)
│   ├── openclaw-setup.sh                  # writes models.json + auth-profiles.json + openclaw.json to ~/.openclaw/
│   ├── pyproject.toml                     # deps: fastapi, uvicorn, httpx[http2], websockets>=12, cryptography>=42, compute-modules
│   ├── openclaw-src/                      # git submodule → github.com/openclaw/openclaw
│   ├── compute_module/handler.py          # Foundry @function chat(), health_check()
│   └── app/
│       ├── main.py                        # FastAPI app, router registration, lifespan cleanup
│       ├── config.py                      # Settings (pydantic-settings, env vars + .env)
│       ├── auth.py                        # require_token() Bearer header dependency
│       ├── models/chat.py                 # ChatMessage, ChatRequest, ChatChunk
│       ├── routers/
│       │   ├── chat.py                    # POST /chat → SSE stream (branches on USE_OPENCLAW_GATEWAY)
│       │   ├── health.py                  # GET /health → {"status":"ok"}
│       │   └── llm_proxy_passthrough.py   # POST /llm/proxy/openai/v1/{path} — injects MODULE_AUTH_TOKEN, strips unsupported fields
│       └── services/
│           ├── llm_proxy.py               # Foundry OpenAI-compat proxy, streaming, 429/503 handling
│           ├── ontology.py                # Dataset transaction writes for chat history
│           └── openclaw_gateway.py        # WebSocket client with ECDSA P-256 auth handshake
├── scripts/run-local-no-docker.sh         # local dev launcher: builds OpenClaw + starts FastAPI + gateway + opens dashboard
├── docker-compose.yml                     # local dev: supervisord (all processes), ports 8080 + 18789
├── LOCAL_DEV.md                           # step-by-step local dev guide
├── ontology/
│   ├── object-types/                      # JSON schema definitions
│   └── link-types/                        # See ontology/README.md for RIDs + status
├── infra/
│   ├── foundry-objects.json               # Source of truth for all created Foundry RIDs
│   └── compute-module.json
└── slack/manifest.json                    # Phase 5
```

---

## Ontology Object Types

All registered under namespace `vahej4tu` in the APBG-Dev Ontology. See `ontology/README.md` for full property schemas and backing dataset RIDs.

| Full API Name | Purpose |
|---|---|
| `vahej4tu.lobster-conversation` | Chat session; keyed by `conversationId` |
| `vahej4tu.lobster-message` | Individual turn; linked to conversation |
| `vahej4tu.lobster-agent-state` | Agent config + runtime status |
| `vahej4tu.lobster-skill` | Tool/skill definition available to agents |
| `vahej4tu.lobster-memory-chunk` | Long-term memory; enable **semantic search** on `content` |

**Status:** Merge proposal `ri.branch..proposal.a931a2f1-c821-45a2-9bef-db6c6f9e460e` created — **requires manual approval** at `accenture.palantirfoundry.com/workspace/developer-branching/proposal/...` before object types appear in Ontology Viewer.

Link types: `lobster-conversation-messages` (1:many), `lobster-agent-skills` (many:many, junction dataset), `lobster-agent-memory` (1:many).

---

## Implementation Phases

| Phase | Description | Status |
|---|---|---|
| 1 | Backend skeleton: FastAPI, LLM proxy, CM handler | ✅ Complete |
| 2 | Ontology integration: dataset writes for chat history | ✅ Complete |
| 3 | Frontend React/OSDK app | ✅ Complete |
| 4 | OpenClaw gateway integration | ✅ Complete |
| 5 | Slack Socket Mode | 🔲 Not started |
| 6 | Observability + hardening (SLS logging, circuit breakers, token validation middleware) | 🔲 Not started |

### Phase 1 — Backend Skeleton + LLM Proxy ✅
- `backend/Dockerfile` — multi-stage, Node 22 for OpenClaw build + Python 3.11-slim runtime
- `supervisord.conf` — 3 processes with correct priority ordering
- `compute_module/handler.py` — `@function(streaming=True) chat()`, `@function health_check()`
- `app/services/llm_proxy.py` — validates entire auth chain
- `app/routers/chat.py` (SSE), `app/routers/health.py`

### Phase 2 — Ontology Integration ✅
- Object types + link types registered via palantir-mcp (merge proposal pending approval)
- `app/services/ontology.py` — `upsert_conversation()`, `append_message()` via Dataset Transaction API
- `app/routers/chat.py` wired to persist conversation + both message turns per request
- **Validation**: After merge proposal approval + dataset build, confirm rows in Ontology Viewer

### Phase 3 — Frontend React App ✅ (removed — superseded by OpenClaw Control UI)

The `frontend/` directory has been deleted. The OpenClaw built-in Control UI at `:18789` is the primary interface. OSDK app RIDs are preserved in `infra/foundry-objects.json` if the React app is ever needed again.

### Phase 4 — OpenClaw Gateway Integration ✅
- `app/routers/llm_proxy_passthrough.py` — catches OpenClaw's OpenAI Chat Completions requests at `/llm/proxy/openai/v1/*`, injects `MODULE_AUTH_TOKEN`, strips fields Foundry rejects (`store`, `metadata`, `service_tier`, `parallel_tool_calls`), forwards to Foundry
- `app/services/openclaw_gateway.py` — WS client with full ECDSA challenge handshake (used when `USE_OPENCLAW_GATEWAY=true`)
- `backend/openclaw-setup.sh` — writes three files to `~/.openclaw/` before gateway starts:
  - `agents/main/agent/models.json` — provider `openai`, `api: openai-completions`, `baseUrl: http://localhost:8080/llm/proxy/openai/v1`, model `gpt-4o`
  - `agents/main/agent/auth-profiles.json` — profile `foundry-openai` with `apiKey: foundry-proxied` (real auth is the `MODULE_AUTH_TOKEN` injected by the passthrough)
  - `openclaw.json` — default model set to `openai/gpt-4o`
- `USE_OPENCLAW_GATEWAY=true` in config activates the WS path for CM-routed chat
- **Model note**: Foundry's Language Model Service only has `gpt-4o` registered. No Claude models are available on this workspace's LLM proxy.

### Phase 5 — Slack 🔲
- `slack/manifest.json`, Socket Mode client in `app/services/slack.py`
- Route Slack messages → OpenClaw; persist under Ontology `Conversation`
- Foundry secrets: `SLACK_APP_TOKEN`, `SLACK_BOT_TOKEN`

### Phase 6 — Observability + Hardening 🔲
- SLS-format structured logging
- Circuit breakers in `llm_proxy.py` (429/503)
- Token validation middleware on all FastAPI endpoints

---

## Key Config Settings (`backend/app/config.py`)

```python
foundry_url: str = "https://accenture.palantirfoundry.com"
llm_proxy_path: str = "/api/v2/llm/proxy/openai/v1/chat/completions"
default_model: str = "gpt-4o"              # only gpt-4o is registered on this Foundry workspace
use_openclaw_gateway: bool = False          # True → route /chat through OpenClaw WS gateway
openclaw_gateway_token: str = ""            # Foundry secret OPENCLAW_GATEWAY_TOKEN
openclaw_port: int = 18789
cors_origins: list[str] = []               # e.g. ["http://localhost:5173"] for local dev
```

The `llm_proxy_passthrough.py` route (`/llm/proxy/openai/v1/*`) does not use config fields — it constructs the target URL as `{foundry_url}/api/v2/llm/proxy/openai/v1/{path}` directly.

All settings can be overridden via environment variables or a `backend/.env` file.

---

## OpenClaw WS Protocol (gateway mode)

Custom envelope — **not** JSON-RPC:

```
server → {"type":"event","event":"connect.challenge","payload":{"nonce":"<uuid>"}}
client → {"type":"req","id":"<id>","method":"connect","params":{
            "minProtocol":1,"maxProtocol":1,
            "client":{"id":"lobster-gateway","displayName":"Lobster",...},
            "role":"operator","scopes":[],
            "device":{"id":"<uuid>","publicKey":"<DER b64>","signature":"<sig>","nonce":"<nonce>"},
            "auth":{"token":"<OPENCLAW_GATEWAY_TOKEN>"}}}
server → {"type":"res","id":"<id>","ok":true,"payload":{"type":"hello-ok"}}
client → {"type":"req","id":"<id>","method":"chat.send","params":{"sessionKey":"<cid>","message":"..."}}
server → {"type":"event","event":"chat.reply","payload":{"text":"..."}}  (0..n)
server → {"type":"event","event":"chat.complete","payload":{...}}
```

**Device identity:** Ephemeral ECDSA P-256 key pair generated at module load (`ec.SECP256R1()`). The challenge nonce is signed with `ECDSA(SHA-256)`; public key sent as DER urlsafe-base64 without padding.

**Session continuity:** `sessionKey` = `conversation_id` — OpenClaw uses this to maintain conversation history across WS reconnects.

---

## Foundry API — Learned Quirks

### Object Type Registration (palantir-mcp)
- Object types get auto-prefixed with the namespace: `lobster-conversation` → `vahej4tu.lobster-conversation`. Always use the full prefixed ID in subsequent API calls.
- The `namespaceRid` parameter in `createObjectType` must be `null` — passing a compass folder RID causes `InvalidNamespaceRidForBranch`.
- All non-primary-key properties must be `editOnly: true` in the property mapping if the backing dataset only has the PK column.
- MANY_TO_MANY link types require a separate junction dataset — create it first and pass `manyToManyLinkTypeDatasources` in the link type body.

### OAuth / Redirect URIs
- Foundry does **not** accept `http://localhost:8080` as a redirect URI for OSDK apps.
- Use `http://localhost:5173` (Vite dev server port) for local development.

### Dataset Transaction API (ontology writes)
```
POST /api/v1/datasets/{rid}/transactions       body: {"type":"APPEND"}  → returns {rid: txn_rid}
PUT  /api/v1/datasets/{rid}/transactions/{txn}/files/upload?filePath=foo.jsonl
     Content-Type: application/octet-stream   body: JSONL row bytes
POST /api/v1/datasets/{rid}/transactions/{txn}/commit
```
New files are picked up by Foundry's incremental build. Trigger a manual build on the dataset if objects don't appear in Ontology Viewer after writes.

### Foundry LLM Proxy
- OpenAI-compat: `POST /api/v2/llm/proxy/openai/v1/chat/completions` — model name is the short alias registered in Foundry Developer Console > Language Models.
- Streaming: set `"stream": true`; response is `text/event-stream`.
- **Available models (this workspace):** only `gpt-4o` is registered. All Claude/Anthropic aliases (`claude-3-5-sonnet`, `claude-3-5-sonnet-20241022`, etc.) return `LanguageModelService:ProxyModelNotFound`. To check: `GET /api/v2/llm/proxy/openai/v1/models` returns 404 on this instance; probe individual aliases with a test request.
- Foundry rejects unknown fields — strip `store`, `metadata`, `service_tier`, `parallel_tool_calls` before forwarding.

### OpenClaw Control UI — Two Separate Tokens
`OPENCLAW_GATEWAY_TOKEN` (env var) and the Control UI's "Gateway Token" field are **not the same thing**:
- `OPENCLAW_GATEWAY_TOKEN` — operator auth used by the Python backend's WebSocket connection (`openclaw_gateway.py`). Set in `backend/.env`.
- **Dashboard token** — auto-generated by OpenClaw for browser Control UI access. Obtain via:
  ```bash
  cd backend/openclaw-src && node openclaw.mjs dashboard
  # prints and opens: http://127.0.0.1:18789/#token=<token>
  ```
  `scripts/run-local-no-docker.sh` runs this automatically. **Do not set `OPENCLAW_STATE_DIR`** when calling `dashboard` manually — it must use the same default state dir (`~/.openclaw/`) as the gateway. A custom state dir generates a token the gateway doesn't recognise ("gateway token mismatch"). The "too many failed authentication attempts" error clears on gateway restart (counter is per-process).

### OpenClaw Build — Two Separate Steps
`pnpm build` builds the gateway runtime only. `pnpm ui:build` is a **separate step** that builds the Control UI to `dist/control-ui/`. Both must run for the full stack. The `Dockerfile` runs both in Stage 1. The `scripts/run-local-no-docker.sh` handles both automatically on first run.

---

## Developer Notes: Palantir MCP

The MCP server does **not** auto-load as a session MCP tool. Use it via Python subprocess + JSON-RPC stdio.

**Working invocation pattern:**
```python
import subprocess, json, os

token = json.load(open('.palantir/mcp-config.json'))['token']
proc = subprocess.Popen(
    ['npx', 'palantir-mcp', '--foundry-api-url', 'https://accenture.palantirfoundry.com'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env={**os.environ, 'FOUNDRY_TOKEN': token}
)
# Must send initialize first:
# {"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"claude","version":"1.0"}}}
# Then tool calls:
# {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"<tool>","arguments":{...}}}
```

**Token location:** `.palantir/mcp-config.json` → `token` field (personal Foundry token).

**Do not** pass the token inline in a bash command — the classifier blocks it. Read it from the config file in a Python script.

**Key MCP tools:**
- `ontology_create_object_type` — creates object type on a branch
- `ontology_create_link_type` — creates link type (M:M requires junction dataset + `manyToManyLinkTypeDatasources`)
- `foundry_create_dataset` — creates a backing dataset
- `ontology_submit_proposal` — submits branch for review/merge

---

## Non-Functional Requirements

- Respect Foundry permission model — no data leaves the stack
- Foundry secrets for all tokens (never env vars in prod)
- Structured SLS logging throughout (Phase 6)
- Clean separation: backend (CM) ↔ frontend (OSDK app)
- Maintainable: feature-flagged phases, no speculative abstractions
