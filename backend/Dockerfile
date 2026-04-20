# ── Stage 1: build OpenClaw ──────────────────────────────────────────────────
FROM --platform=linux/amd64 node:22-bookworm-slim AS openclaw-build

RUN npm install -g pnpm@10

WORKDIR /openclaw
# Install deps before copying source for better layer caching
COPY openclaw-src/package.json openclaw-src/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY openclaw-src/ .
RUN pnpm build && pnpm ui:build && pnpm prune --prod

# ── Stage 2: Python + Node runtime ───────────────────────────────────────────
FROM --platform=linux/amd64 python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl supervisor \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

# Pull in the built OpenClaw artifacts from stage 1
COPY --from=openclaw-build /openclaw/dist          /app/openclaw/dist
COPY --from=openclaw-build /openclaw/openclaw.mjs  /app/openclaw/openclaw.mjs
COPY --from=openclaw-build /openclaw/package.json  /app/openclaw/package.json
COPY --from=openclaw-build /openclaw/node_modules  /app/openclaw/node_modules

# Non-root numeric user required by Foundry CM runtime
RUN useradd -u 5000 -m appuser && chown -R 5000:5000 /app
USER 5000

EXPOSE 8080 18789

CMD ["/usr/bin/supervisord", "-n", "-c", "/app/supervisord.conf"]
