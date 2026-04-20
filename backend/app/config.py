from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    foundry_url: str = "https://accenture.palantirfoundry.com"

    # CORS — comma-separated allowed origins (e.g. "http://localhost:5173").
    # Empty = CORS middleware disabled (correct for production in Foundry CM).
    cors_origins: list[str] = []

    # POST {foundry_url}/api/v2/llm/proxy/openai/v1/chat/completions
    llm_proxy_path: str = "/api/v2/llm/proxy/openai/v1/chat/completions"

    # Full RID for the model — verify in Foundry: Developer Console > Language Models
    # Example: ri.language-model-service..language-model.claude-3-5-sonnet
    default_model: str = "claude-3-5-sonnet"

    # Flip to true in Phase 4 to route through the OpenClaw subprocess
    use_openclaw_gateway: bool = False

    # ── OpenClaw gateway ──────────────────────────────────────────────────────
    openclaw_gateway_token: str = ""        # set via Foundry secret OPENCLAW_GATEWAY_TOKEN
    openclaw_port: int = 18789

    # Foundry Anthropic-compatible LLM proxy (mirrors the openai path pattern)
    # Set llm_proxy_anthropic_translate=true if Foundry only has the OpenAI endpoint
    llm_proxy_anthropic_path: str = "/api/v2/llm/proxy/anthropic/v1"
    llm_proxy_anthropic_translate: bool = False

    @property
    def llm_proxy_url(self) -> str:
        return f"{self.foundry_url}{self.llm_proxy_path}"

    @property
    def llm_proxy_anthropic_url(self) -> str:
        return f"{self.foundry_url}{self.llm_proxy_anthropic_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
