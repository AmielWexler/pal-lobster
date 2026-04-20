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
│   ├── [priority 15]  OpenClaw :18789  ← agent gateway (Node 22)
│   └── [priority 20]  CM handler       ← Foundry polling loop → FastAPI

LLM flow (OpenClaw → Foundry proxy):
  OpenClaw  →  POST localhost:8080/llm/proxy/anthropic/v1/messages
            →  FastAPI injects MODULE_AUTH_TOKEN
            →  Foundry /api/v2/llm/proxy/anthropic/v1/messages

Chat flow (user → CM function):
  Frontend OSDK  →  Foundry CM function "chat"
                 →  handler.py (extracts context.auth_token)
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
│   └── src/                               # React 18 + Vite + Tailwind (Phase 3)
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

- Python 3.11+
- Node.js 22+ and pnpm 10 (for OpenClaw build)
- Docker (for container build / deployment)
- Access to `accenture.palantirfoundry.com` with a valid token

---

## Local Development (without Docker)

### 1. Backend only (no OpenClaw, direct LLM proxy mode)

```bash
cd backend
pip install -e .

# Create .env (copy from .env.example or set manually)
cat > .env <<EOF
FOUNDRY_URL=https://accenture.palantirfoundry.com
USE_OPENCLAW_GATEWAY=false
EOF

uvicorn app.main:app --reload --port 8080
```

Test the health endpoint:
```bash
curl http://localhost:8080/health
# {"status":"ok"}
```

Test the chat endpoint (requires a valid Foundry token):
```bash
TOKEN=<your-foundry-personal-token>
curl -N -X POST http://localhost:8080/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hello"}]}'
# streams: data: {"delta":"Hello","done":false,...}
# ...
# data: {"delta":"","done":true,...}
```

### 2. Run OpenClaw locally alongside FastAPI

```bash
# Build OpenClaw first
cd backend/openclaw-src
pnpm install && pnpm build && pnpm prune --prod
cd ..

# Terminal 1 — FastAPI
uvicorn app.main:app --port 8080

# Terminal 2 — OpenClaw
ANTHROPIC_BASE_URL=http://localhost:8080/llm/proxy/anthropic/v1 \
ANTHROPIC_API_KEY=foundry-proxied \
OPENCLAW_GATEWAY_TOKEN=dev-token-123 \
OPENCLAW_STATE_DIR=/tmp/openclaw-state \
OPENCLAW_SKIP_CHANNELS=1 \
  node openclaw-src/openclaw.mjs gateway --port 18789 --allow-unconfigured
```

Then set `USE_OPENCLAW_GATEWAY=true` in `.env` and restart FastAPI.

### 3. Run the CM handler locally

```bash
# In a third terminal, with FastAPI already running
cd backend
python compute_module/handler.py
```

The handler waits for FastAPI health (15 × 2s retries) before connecting to Foundry.

### 4. Frontend (React dev server)

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

On first load you'll see a "Sign in with Foundry" button. After clicking, Foundry OAuth redirects back to `http://localhost:5173/?code=...` and the app processes the token automatically.

**Note:** If the CM function invocation returns 404, the endpoint in `src/api/chat.ts` (`CM_CHAT_URL`) may need adjustment for your Foundry instance's routing. Check the Developer Console for the correct CM function invocation URL.

For local end-to-end testing (frontend → backend without full Foundry deployment), you can temporarily point `CM_CHAT_URL` at `http://localhost:8080/chat` and pass any token — this bypasses the CM layer and hits FastAPI directly.

---

## Docker Build

```bash
# From repo root — must have openclaw-src submodule checked out
git submodule update --init --recursive

cd backend
docker build -t lobster-backend .
```

Run locally:
```bash
docker run --rm -p 8080:8080 \
  -e FOUNDRY_URL=https://accenture.palantirfoundry.com \
  -e USE_OPENCLAW_GATEWAY=false \
  -e MODULE_AUTH_TOKEN=<token> \
  lobster-backend
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
| 3 | Frontend React/OSDK app | ✅ Complete |
| 4 | OpenClaw gateway integration | ✅ Complete |
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
