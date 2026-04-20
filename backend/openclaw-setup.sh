#!/bin/bash
# Initialize OpenClaw agent config for Foundry LLM proxy.
# Run before the gateway starts; safe to re-run.
set -euo pipefail

STATE_DIR="${OPENCLAW_STATE_DIR:-${HOME}/.openclaw}"
AGENT_DIR="${STATE_DIR}/agents/main/agent"
mkdir -p "${AGENT_DIR}"

# Write provider catalog — routes LLM calls through FastAPI → Foundry proxy
cat > "${AGENT_DIR}/models.json" << 'MODELS_EOF'
{
  "providers": {
    "openai": {
      "baseUrl": "http://localhost:8080/llm/proxy/openai/v1",
      "apiKey": "foundry-proxied",
      "api": "openai-completions",
      "models": [
        {
          "id": "gpt-4o",
          "name": "GPT-4o (Foundry)",
          "api": "openai-completions",
          "reasoning": false,
          "input": ["text", "image"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 128000,
          "maxTokens": 4096
        }
      ]
    }
  }
}
MODELS_EOF

# Write auth-profiles.json — add openai api_key profile (key ignored; proxy does auth)
python3 - << PYEOF
import json, os
auth_file = '${AGENT_DIR}/auth-profiles.json'
store = {"version": 1, "profiles": {}}
if os.path.exists(auth_file):
    with open(auth_file) as f:
        store = json.load(f)
store.setdefault("profiles", {})["foundry-openai"] = {
    "type": "api_key",
    "provider": "openai",
    "key": "foundry-proxied",
    "displayName": "Foundry Proxy (GPT-4o)"
}
with open(auth_file, 'w') as f:
    json.dump(store, f, indent=2)
PYEOF

# Set default model in openclaw.json — preserve existing gateway auth token
python3 - << PYEOF
import json, os
cfg_file = '${STATE_DIR}/openclaw.json'
cfg = {}
if os.path.exists(cfg_file):
    with open(cfg_file) as f:
        cfg = json.load(f)
cfg.setdefault('agents', {}).setdefault('defaults', {})['model'] = 'openai/gpt-4o'
with open(cfg_file, 'w') as f:
    json.dump(cfg, f, indent=2)
PYEOF

echo "OpenClaw configured: openai/gpt-4o via Foundry proxy"
