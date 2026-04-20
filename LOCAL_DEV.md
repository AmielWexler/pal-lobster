# Local Development Guide

Run the full Lobster stack locally — backend (FastAPI) + frontend (React) — without a Foundry deployment.

---

## What runs where

| Component | Process | Port | Notes |
|---|---|---|---|
| FastAPI backend | Docker or bare Python | 8080 | LLM proxy, chat SSE, ontology writes |
| React frontend | `npm run dev` (Vite) | 5173 | Hits `localhost:8080/chat` directly |
| OpenClaw gateway | **Not started locally** | 18789 | Only needed when `USE_OPENCLAW_GATEWAY=true` |
| CM handler | **Not started locally** | — | Only runs inside Foundry |

In local mode, the frontend skips the Foundry Compute Module and calls FastAPI directly.
The LLM proxy still calls Foundry (`accenture.palantirfoundry.com`) — you need a valid token.

---

## Prerequisites

- **Foundry personal access token** — [Get one here](https://accenture.palantirfoundry.com/workspace/settings/developer-settings/personal-access-tokens)
- **Docker Desktop** (for the Docker path) or **Python 3.11+** (for the bare Python path)
- **Node.js 22+** + npm (for the frontend dev server)
- **git submodule** checked out (for the Docker build only):
  ```bash
  git submodule update --init --recursive
  ```

---

## Option A — Docker Compose (recommended)

This builds the production Docker image and runs FastAPI inside it. Closest to how Foundry runs it.

### 1. Configure the backend

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and set:

```bash
MODULE_AUTH_TOKEN=your-foundry-personal-token-here
```

Everything else has working defaults for local dev.

### 2. Start the backend

```bash
docker compose up --build
```

First build takes ~3–5 minutes (installs Node 22 + builds OpenClaw). Subsequent starts use the Docker cache and take seconds.

Verify it's healthy:
```bash
curl http://localhost:8080/health
# {"status":"ok"}
```

### 3. Configure the frontend

```bash
cp frontend/.env.local.example frontend/.env.local
```

The default value (`VITE_DIRECT_BACKEND_URL=http://localhost:8080`) is correct — leave it as-is.

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 5. Sign in and chat

Open http://localhost:5173 in your browser.

Click **Sign in with Foundry** — this redirects to `accenture.palantirfoundry.com` for OAuth.
After signing in, you're redirected back to `localhost:5173` with a token.

The frontend uses the OAuth token to call `localhost:8080/chat` directly (not through Foundry CM).

### Stop everything

```bash
docker compose down
```

---

## Option B — Bare Python (fastest for backend iteration)

No Docker needed. Run FastAPI directly on your machine.

### 1. Install backend deps

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install "httpx[http2]" fastapi uvicorn pydantic pydantic-settings websockets cryptography
```

> Note: `compute-modules` (the Foundry SDK package) is in `pyproject.toml` but not needed for local dev — the CM handler is not started here.

### 2. Create `.env`

```bash
cp .env.example .env
# Edit .env and set MODULE_AUTH_TOKEN=your-foundry-personal-token-here
```

### 3. Start FastAPI

```bash
# Still inside backend/
uvicorn app.main:app --reload --port 8080 --log-level info
```

`--reload` watches for file changes and hot-restarts — useful for backend iteration.

### 4. Frontend — same as Docker path

```bash
cp frontend/.env.local.example frontend/.env.local
cd frontend && npm install && npm run dev
```

---

## Testing the chat endpoint directly (no browser)

Once FastAPI is running, you can test chat with `curl` using your Foundry token:

```bash
TOKEN=your-foundry-personal-token-here

curl -N -s \
  -X POST http://localhost:8080/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"messages": [{"role": "user", "content": "Hello, who are you?"}]}'
```

You should see SSE lines streaming back:
```
data: {"delta":"Hello","done":false,"conversation_id":"..."}
data: {"delta":"!","done":false,"conversation_id":"..."}
...
data: {"delta":"","done":true,"conversation_id":"..."}
```

---

## Environment variable reference

All settings live in `backend/.env`. Here's what matters for local dev:

| Variable | Required | Default | Description |
|---|---|---|---|
| `MODULE_AUTH_TOKEN` | ✅ Yes | — | Your Foundry personal token. Used as fallback for LLM proxy auth and ontology writes. |
| `FOUNDRY_URL` | No | `https://accenture.palantirfoundry.com` | Foundry instance URL |
| `DEFAULT_MODEL` | No | `claude-3-5-sonnet` | LLM model short name |
| `USE_OPENCLAW_GATEWAY` | No | `false` | Keep `false` locally unless you also start OpenClaw |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Allow Vite dev server to call FastAPI directly |
| `LLM_PROXY_ANTHROPIC_TRANSLATE` | No | `false` | Set `true` if Foundry 404s on `/anthropic/v1` |

Frontend (in `frontend/.env.local`):

| Variable | Default | Description |
|---|---|---|
| `VITE_DIRECT_BACKEND_URL` | `http://localhost:8080` | When set, bypasses Foundry CM and calls FastAPI directly |

---

## Common issues

### `401 Unauthorized` from `/chat`
The Bearer token is missing or expired. Make sure `FOUNDRY_URL` is set in `backend/.env` and you're passing a valid token in the `Authorization` header.

### LLM proxy returns `404`
Foundry's LLM proxy path might differ. Try setting `LLM_PROXY_ANTHROPIC_TRANSLATE=true` in `backend/.env` — this falls back to the OpenAI-compatible endpoint.

### OAuth redirect fails (`redirect_uri_mismatch`)
Foundry only allows `http://localhost:5173` as a redirect URI for this app. Make sure the frontend dev server is running on port 5173 (it is by default).

### Docker build fails with `missing openclaw-src`
The OpenClaw submodule isn't checked out. Run:
```bash
git submodule update --init --recursive
```

### Frontend shows `CM chat failed: HTTP 404`
You have `VITE_DIRECT_BACKEND_URL` **not** set but the app is still trying to call the Foundry CM endpoint. Check that `frontend/.env.local` exists and contains:
```
VITE_DIRECT_BACKEND_URL=http://localhost:8080
```
Then restart `npm run dev` (Vite doesn't hot-reload `.env.local` changes).

### Ontology writes fail silently
This is expected locally — the Foundry dataset RIDs exist in production only. Ontology failures are caught and logged as warnings; chat still works. You'll see lines like:
```
WARNING  app.services.ontology upsert_conversation failed cid=...
```
This is safe to ignore during local dev.
