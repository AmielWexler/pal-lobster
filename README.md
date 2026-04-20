# pal-lobster

Production-grade deployment of [OpenClaw](https://github.com/openclaw/openclaw) running natively inside Palantir Foundry as a Compute Module — no external API keys, all LLM calls route through Foundry's built-in proxy.

**Foundry instance:** `accenture.palantirfoundry.com`
**Project folder:** `ri.compass.main.folder.a22ab25f-e459-4512-97ae-fc10bd2d24ca` (APBG-Dev / Lobster pal)

---

## Architecture

```
Container (linux/amd64, USER 5000)
├── supervisord
│   ├── [priority 10]  FastAPI  :8080   ← chat API + LLM passthrough
│   ├── [priority 15]  OpenClaw :18789  ← agent gateway + built-in Control UI (Node 22)
│   └── [priority 20]  CM handler       ← Foundry polling loop → FastAPI

UI: OpenClaw's built-in Control UI served at :18789 (Lit web components — no separate frontend needed)

LLM flow (OpenClaw → Foundry proxy):
  OpenClaw  →  POST localhost:8080/llm/proxy/anthropic/v1/messages
            →  FastAPI injects MODULE_AUTH_TOKEN
            →  Foundry /api/v2/llm/proxy/anthropic/v1/messages

Chat flow (user → CM function):
  CM function "chat"  →  handler.py (extracts context.auth_token)
                      →  POST localhost:8080/chat  Bearer <user-token>
                      →  FastAPI streams SSE
                      →  [USE_OPENCLAW_GATEWAY=false] Foundry LLM proxy (OpenAI-compat)
                      →  [USE_OPENCLAW_GATEWAY=true]  OpenClaw WS gateway
```

---

## Repository Structure

```
pal-lobster/
├── backend/
│   ├── Dockerfile                         # multi-stage: Node22 build + Python3.11 runtime
│   ├── supervisord.conf                   # 3-process: fastapi, openclaw, compute_module
│   ├── pyproject.toml
│   ├── openclaw-src/                      # git submodule → github.com/openclaw/openclaw
│   ├── compute_module/
│   │   └── handler.py                     # @function chat(), health_check()
│   └── app/
│       ├── main.py                        # FastAPI app, lifespan cleanup
│       ├── config.py                      # Settings (pydantic-settings, env vars)
│       ├── auth.py                        # require_token() dependency
│       ├── models/chat.py                 # ChatMessage, ChatRequest, ChatChunk
│       ├── routers/
│       │   ├── chat.py                    # POST /chat → SSE stream
│       │   ├── health.py                  # GET /health
│       │   └── llm_proxy_passthrough.py   # POST /llm/proxy/anthropic/v1/{path}
│       └── services/
│           ├── llm_proxy.py               # Foundry OpenAI-compat proxy, streaming
│           ├── ontology.py                # Dataset transaction writes for chat history
│           └── openclaw_gateway.py        # WebSocket client, ECDSA auth handshake
├── frontend/
│   ├── foundry.config.json                # OSDK app registration + OAuth config
│   ├── .env.local.example                 # copy → .env.local for local dev bypass
│   └── src/
│       ├── foundry.ts                     # auth client, app RID, Foundry URL
│       ├── api/chat.ts                    # streamChat() — CM or direct backend
│       ├── hooks/                         # useFoundryAuth, useChat
│       └── components/                    # ChatWindow, MessageList, MessageInput, Layout
├── scripts/dev.sh                         # local dev launcher (no Docker): builds + starts FastAPI + OpenClaw
├── docker-compose.yml                     # local dev: supervisord (FastAPI + OpenClaw), ports 8080 + 18789
├── LOCAL_DEV.md                           # full local dev guide
├── ontology/
│   ├── object-types/                      # JSON schema definitions
│   └── link-types/
├── infra/
│   ├── compute-module.json
│   ├── foundry-objects.json               # All created Foundry RIDs
│   └── foundry-app.json
└── slack/
    └── manifest.json                      # Phase 5
```

---

## Prerequisites

- **Foundry personal access token** — [Developer Settings → Personal Access Tokens](https://accenture.palantirfoundry.com/workspace/settings/developer-settings/personal-access-tokens)
- Python 3.11+ (bare-Python local dev path)
- Node.js 22+ and npm (frontend dev server)
- pnpm 10 (only needed to build OpenClaw from source — required for the Docker build)
- Docker Desktop (for the `docker-compose` path)
- The OpenClaw git submodule (`git submodule update --init --recursive`) — required for Docker builds only

---

## Local Development

> **Full guide:** see [`LOCAL_DEV.md`](LOCAL_DEV.md) — script, Docker, and manual options, plus troubleshooting.

### Quick start (no Docker)

```bash
git submodule update --init --recursive
cp backend/.env.example backend/.env
# Edit backend/.env — set MODULE_AUTH_TOKEN=<your Foundry personal token>

./scripts/dev.sh
```

First run builds OpenClaw (~2 min). Then open **http://localhost:18789** for the Control UI.

Get the dashboard token to connect:
```bash
cd backend/openclaw-src && node openclaw.mjs dashboard
# → prints http://localhost:18789/?token=<token>  (open directly, or paste token into the UI)
```

> **Token note:** The Control UI's "Gateway Token" field is an auto-generated dashboard token, **not** `OPENCLAW_GATEWAY_TOKEN` from `.env`. Run `node openclaw.mjs dashboard` to get it.

### With Docker Compose

```bash
git submodule update --init --recursive
cp backend/.env.example backend/.env
# Edit backend/.env — set MODULE_AUTH_TOKEN

docker compose up --build
```

Access Control UI at **http://localhost:18789**, FastAPI at **http://localhost:8080**.

---

## Docker Image (standalone)

```bash
cd backend
docker build -t lobster-backend .

# Full stack via supervisord (FastAPI + OpenClaw UI)
docker run --rm -p 8080:8080 -p 18789:18789 \
  -e MODULE_AUTH_TOKEN=<token> \
  -e OPENCLAW_GATEWAY_TOKEN=local-dev-secret \
  lobster-backend

# FastAPI only (no OpenClaw)
docker run --rm -p 8080:8080 \
  -e MODULE_AUTH_TOKEN=<token> \
  lobster-backend \
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

---

## Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `FOUNDRY_URL` | `https://accenture.palantirfoundry.com` | Foundry instance base URL |
| `USE_OPENCLAW_GATEWAY` | `false` | `true` routes chat through OpenClaw WS |
| `OPENCLAW_GATEWAY_TOKEN` | `""` | Shared secret for OpenClaw WS auth (use Foundry secret `OPENCLAW_GATEWAY_TOKEN`) |
| `OPENCLAW_PORT` | `18789` | OpenClaw gateway listen port |
| `DEFAULT_MODEL` | `claude-3-5-sonnet` | Model RID or name for the Foundry LLM proxy |
| `LLM_PROXY_PATH` | `/api/v2/llm/proxy/openai/v1/chat/completions` | Foundry OpenAI-compat endpoint |
| `LLM_PROXY_ANTHROPIC_PATH` | `/api/v2/llm/proxy/anthropic/v1` | Foundry Anthropic-compat endpoint |
| `LLM_PROXY_ANTHROPIC_TRANSLATE` | `false` | Translate Anthropic→OpenAI if Foundry lacks native Anthropic endpoint |
| `MODULE_AUTH_TOKEN` | *(injected by Foundry CM runtime)* | Server-side token for LLM proxy passthrough — do NOT set manually in prod |
| `CORS_ORIGINS` | `""` (disabled) | Comma-separated allowed origins — set `http://localhost:5173` for local dev; leave empty in prod |

In production, `MODULE_AUTH_TOKEN` is injected automatically by the Foundry CM runtime into every process in the container. Never set it as a static secret.

---

## Deploying to Foundry

1. Push image to the Foundry container registry (via Foundry Developer Console → Compute Modules → Upload Image).
2. Set the following Foundry Secrets on the Compute Module:
   - `OPENCLAW_GATEWAY_TOKEN` — random string, shared between OpenClaw and the Python gateway client
3. Deploy from Foundry Developer Console.
4. Test via the **CM Test Panel** — call the `chat` function with a sample payload.

---

## Implementation Status

| Phase | Description | Status |
|---|---|---|
| 1 | Backend skeleton: FastAPI, LLM proxy, CM handler | ✅ Complete |
| 2 | Ontology integration: dataset writes for chat history | ✅ Complete |
| 3 | Frontend React/OSDK app | ✅ Complete (superseded by OpenClaw UI) |
| 4 | OpenClaw gateway integration + built-in Control UI | ✅ Complete |
| 5 | Slack Socket Mode | 🔲 Not started |
| 6 | Observability + hardening | 🔲 Not started |

> **Ontology note:** The 5 object types and 3 link types were registered via palantir-mcp. The merge proposal (`ri.branch..proposal.a931a2f1-c821-45a2-9bef-db6c6f9e460e`) must be approved in the Foundry UI before objects appear in Ontology Viewer. After approval, trigger a dataset build on each backing dataset so Foundry indexes the rows.

---

## Key Foundry Resource IDs

See `infra/foundry-objects.json` for the full list. Quick reference:

| Resource | RID |
|---|---|
| Ontology | `ri.ontology.main.ontology.a4c72975-6b1e-4c42-88b0-523b9870ad84` |
| CM Deployed App | `ri.foundry.main.deployed-app.32456382-2f97-4ad6-95df-8464ab511118` |
| OSDK Application | `ri.third-party-applications.main.application.2409e8b8-feb9-4107-97ff-ba9244963033` |
| OSDK Client ID | `f70ee0f0dcdc17bef7d64a27efef6188` |
