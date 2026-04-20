## Project Goal
Build a production-grade, enterprise-integrated version of OpenClaw that runs natively inside Palantir Foundry (accenture.palantirfoundry.com), in the **APBG-Dev / Lobster pal** project space (`ri.compass.main.folder.a22ab25f-e459-4512-97ae-fc10bd2d24ca`).

The final solution combines:
- OpenClaw Gateway running persistently inside Foundry as a **Compute Module**
- Rich web UI (chat + agent dashboard + settings) — React/OSDK, Workshop-embeddable
- Deep integration with Foundry's Ontology, LLM proxy, and Workshop
- Slack connectivity via Socket Mode

---

## Architecture

### Runtime Pattern
The Compute Module container runs **two processes** managed by `supervisord`:
1. **CM polling loop** — Foundry's event-polling SDK (`compute-modules` Python package), bridges Foundry function invocations to the internal FastAPI server
2. **FastAPI server** — `uvicorn app.main:app --port 8080`, the actual application server

The frontend (OSDK React app) calls the Compute Module's public function endpoint using Foundry OAuth tokens. Foundry invokes the CM handler, which proxies the request to FastAPI internally over localhost.

### LLM Calls
All model calls go through Foundry's native LLM proxy — **no external API keys**. The `llm_proxy.py` service uses the Compute Module's `context.auth_token` (a `RefreshingOauthToken`) to call the proxy. OpenClaw's LLM adapter is patched to route through `http://localhost:8080/llm/proxy/...` which forwards with Foundry auth.

### Feature Flag
`USE_OPENCLAW_GATEWAY` in `config.py` — defaults to `false` (direct LLM calls). Flip to `true` in Phase 4 to route through the full OpenClaw subprocess.

---

## Technology Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, uvicorn, httpx, Foundry Compute Module SDK |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, OSDK |
| Real-time | SSE (`text/event-stream`) via POST + `ReadableStream` |
| Container | Python 3.11 + Node.js 20, supervisord |
| Storage | Foundry Ontology (OSDK Python client) |
| Slack | Slack Bolt SDK, Socket Mode (no inbound webhook needed) |

---

## Repository Structure

pal-lobster/
├── backend/
│   ├── Dockerfile                    # Python 3.11 + Node.js 20, supervisord
│   ├── supervisord.conf
│   ├── pyproject.toml
│   ├── compute_module/handler.py     # @function handlers → internal HTTP
│   └── app/
│       ├── main.py
│       ├── config.py                 # USE_OPENCLAW_GATEWAY flag + Foundry URLs
│       ├── auth.py
│       ├── routers/
│       │   ├── chat.py               # POST /chat → SSE stream
│       │   ├── agents.py
│       │   ├── tasks.py
│       │   ├── memory.py
│       │   └── health.py
│       ├── services/
│       │   ├── llm_proxy.py          # Foundry LLM proxy, no external keys
│       │   ├── ontology.py           # OSDK wrapper
│       │   ├── openclaw_gateway.py   # Subprocess IPC
│       │   └── slack.py              # Socket Mode client
│       └── models/
├── backend/openclaw/
│   ├── package.json
│   ├── index.js                      # OpenClaw Gateway entrypoint
│   └── patches/llm_adapter.js        # Shim: OpenClaw → Foundry proxy
├── frontend/
│   ├── foundry.config.json           # OSDK app registration + OAuth
│   └── src/
│       ├── api/{client,chat}.ts
│       ├── components/{chat,agents,settings,layout}/
│       └── hooks/{useChat,useAgents,useFoundryAuth}.ts
├── ontology/
│   ├── object-types/                 # See ontology/README.md for setup
│   └── link-types/
├── slack/manifest.json
├── infra/
│   ├── compute-module.json
│   ├── foundry-app.json
│   └── workshop-page.json
└── docs/

---

## Ontology Object Types

All registered under `lobster-` prefix in Foundry Ontology Manager:

| API Name | Purpose |
|---|---|
| `lobster-conversation` | Chat session; keyed by `conversationId` |
| `lobster-message` | Individual turn; linked to conversation |
| `lobster-agent-state` | Agent config + runtime status |
| `lobster-skill` | Tool/skill definition available to agents |
| `lobster-memory-chunk` | Long-term memory; enable **semantic search** on `content` field |

Link types: `lobster-conversation-messages` (1:many), `lobster-agent-skills` (many:many), `lobster-agent-memory` (1:many).

---

## Implementation Phases

### Phase 1 — Backend Skeleton + LLM Proxy *(do first)*
Prove `Foundry token → LLM proxy → SSE stream` works before anything else.
- `backend/Dockerfile`, `supervisord.conf`, `compute_module/handler.py`
- `app/services/llm_proxy.py` — highest-risk; validates entire auth chain
- `app/routers/chat.py` (SSE), `app/routers/health.py`
- **Validation**: Call from Foundry CM Test panel, confirm streamed tokens

### Phase 2 — Ontology Integration
- Register object types from `ontology/` in Foundry Ontology Manager
- `app/services/ontology.py` — `create_conversation`, `append_message`, etc.
- Wire `chat.py` to persist each turn
- **Validation**: Restart CM, confirm history in Ontology Viewer

### Phase 3 — Frontend React App
- Bootstrap with `npm create @osdk/app@latest` in `frontend/`
- SSE via `fetch` + `ReadableStream` (POST-based)
- Host on Foundry Developer Console; embed in Workshop via URL widget
- **Validation**: Stream response in browser; see objects in Ontology

### Phase 4 — OpenClaw Gateway Integration
- `backend/openclaw/patches/llm_adapter.js` — shim for Foundry LLM proxy
- `app/services/openclaw_gateway.py` — subprocess + HTTP IPC
- Ontology memory adapter (pre-load on startup, write-back on save)
- Flip `USE_OPENCLAW_GATEWAY=true`
- **Validation**: Multi-step task, tool-use loop, state survives restart

### Phase 5 — Slack
- `slack/manifest.json`, Socket Mode client in `app/services/slack.py`
- Route Slack messages to OpenClaw; persist under Ontology `Conversation`
- Foundry secrets for `SLACK_APP_TOKEN` (not env vars)

### Phase 6 — Observability + Hardening
- SLS-format structured logging
- Circuit breakers in `llm_proxy.py` (429/503)
- Token validation middleware on all FastAPI endpoints

---

## Critical Files (build in this order)

1. `backend/Dockerfile` — Python + Node.js co-existence
2. `backend/app/services/llm_proxy.py` — entire system depends on this
3. `backend/compute_module/handler.py` — Foundry invocation bridge
4. `backend/openclaw/patches/llm_adapter.js` — makes OpenClaw work without external keys
5. `frontend/src/api/client.ts` — frontend-backend contract

---

## Non-Functional Requirements

- Respect Foundry permission model — no data leaves the stack
- Foundry secrets for all tokens (never env vars in prod)
- Structured SLS logging throughout
- Clean separation: backend (CM) ↔ frontend (OSDK app)
- Maintainable: feature-flagged phases, no speculative abstractions

---

## Developer Notes: Palantir MCP Integration

The MCP server can be run as a subprocess via Python communicating over JSON-RPC (stdio). The package works via `npx palantir-mcp`.

**Working invocation pattern:**
```python
import subprocess, json, os

token = json.load(open('.palantir/mcp-config.json'))['token']
proc = subprocess.Popen(
    ['npx', 'palantir-mcp', '--foundry-api-url', '[https://accenture.palantirfoundry.com](https://accenture.palantirfoundry.com)'],
    stdin=subprocess.PIPE, 
    stdout=subprocess.PIPE, 
    stderr=subprocess.PIPE,
    env={**os.environ, 'FOUNDRY_TOKEN': token}
)
# Send initialize first, then tool calls