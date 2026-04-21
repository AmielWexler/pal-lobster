#!/usr/bin/env bash
# Local dev launcher — starts FastAPI + OpenClaw gateway without Docker.
# Usage: ./scripts/run-local-no-docker.sh
#
# Prerequisites:
#   - Python 3.11+, Node 22+, pnpm
#   - backend/.env with MODULE_AUTH_TOKEN and OPENCLAW_GATEWAY_TOKEN set
#   - git submodule checked out: git submodule update --init --recursive
#
# First run builds OpenClaw (~2 min). Subsequent runs are instant.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPENCLAW_SRC="$REPO_ROOT/backend/openclaw-src"
OPENCLAW_MJS="$OPENCLAW_SRC/openclaw.mjs"
OPENCLAW_DIST="$OPENCLAW_SRC/dist"
BACKEND_DIR="$REPO_ROOT/backend"
ENV_FILE="$BACKEND_DIR/.env"

# ── Colour helpers ─────────────────────────────────────────────────────────────
green()  { echo -e "\033[0;32m$*\033[0m"; }
yellow() { echo -e "\033[0;33m$*\033[0m"; }
red()    { echo -e "\033[0;31m$*\033[0m"; }

# ── Prereq checks ─────────────────────────────────────────────────────────────
if [ ! -f "$OPENCLAW_MJS" ]; then
  red "ERROR: openclaw-src submodule not found at $OPENCLAW_SRC"
  echo "Run: git submodule update --init --recursive"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  red "ERROR: $ENV_FILE not found."
  echo "Run: cp backend/.env.example backend/.env  and fill in MODULE_AUTH_TOKEN"
  exit 1
fi

# ── Build OpenClaw if needed ───────────────────────────────────────────────────
if [ ! -d "$OPENCLAW_DIST/control-ui" ]; then
  yellow "Building OpenClaw (first run — takes ~2 min)..."
  cd "$OPENCLAW_SRC"
  pnpm install --frozen-lockfile
  pnpm build
  pnpm ui:build
  green "OpenClaw build complete."
  cd "$REPO_ROOT"
fi

# ── OpenClaw env (don't source .env — shell mangles JSON values like CORS_ORIGINS)
# pydantic-settings reads backend/.env directly. We only need these two for OpenClaw.
# Override by exporting in your shell before running this script.
export OPENCLAW_GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN:-local-dev-secret}"

# ── Configure OpenClaw for Foundry LLM proxy ──────────────────────────────────
green "Configuring OpenClaw agent for Foundry LLM proxy..."
bash "$REPO_ROOT/backend/openclaw-setup.sh"

# ── Python venv ───────────────────────────────────────────────────────────────
VENV="$BACKEND_DIR/.venv"
if [ ! -d "$VENV" ]; then
  yellow "Creating Python venv..."
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1090
source "$VENV/bin/activate"
pip install -q -r "$BACKEND_DIR/requirements.txt"

# ── Trap: kill children on exit ───────────────────────────────────────────────
PIDS=()
cleanup() {
  yellow "\nStopping processes..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait
  green "Done."
}
trap cleanup EXIT INT TERM

# ── Start FastAPI ─────────────────────────────────────────────────────────────
green "Starting FastAPI on :8080 ..."
cd "$BACKEND_DIR"
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload --log-level info &
PIDS+=($!)

# ── Wait for FastAPI ──────────────────────────────────────────────────────────
echo -n "Waiting for FastAPI"
for i in $(seq 1 20); do
  if curl -sf http://localhost:8080/health >/dev/null 2>&1; then
    echo " ready."
    break
  fi
  echo -n "."
  sleep 1
done

# ── Start OpenClaw gateway ────────────────────────────────────────────────────
green "Starting OpenClaw gateway on :18789 ..."
cd "$OPENCLAW_SRC"
OPENAI_BASE_URL="http://localhost:8080/llm/proxy/openai/v1" \
openai_API_KEY="foundry-proxied" \
OPENCLAW_GATEWAY_TOKEN="$OPENCLAW_GATEWAY_TOKEN" \
OPENCLAW_SKIP_CHANNELS="1" \
node openclaw.mjs gateway --port 18789 --allow-unconfigured &
PIDS+=($!)

# ── Wait for OpenClaw gateway to be ready ─────────────────────────────────────
echo -n "Waiting for OpenClaw"
for i in $(seq 1 15); do
  if curl -sf http://127.0.0.1:18789/ >/dev/null 2>&1; then
    echo " ready."
    break
  fi
  echo -n "."
  sleep 1
done

# ── Open dashboard (prints tokenized URL + opens browser) ─────────────────────
echo ""
green "Stack is up — opening Control UI..."
cd "$OPENCLAW_SRC"
node openclaw.mjs dashboard || true
echo ""
echo "Press Ctrl+C to stop everything."

# ── Wait ──────────────────────────────────────────────────────────────────────
wait
