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

    # Only gpt-4o is registered on this Foundry workspace's Language Model Service.
    # Claude/Anthropic models return ProxyModelNotFound on this instance.
    default_model: str = "gpt-4o"

    # Injected by Foundry CM runtime in production; set manually in .env for local dev
    module_auth_token: str = ""

    # Flip to true to route /chat through the OpenClaw WS gateway subprocess
    use_openclaw_gateway: bool = False

    # ── OpenClaw gateway ──────────────────────────────────────────────────────
    openclaw_gateway_token: str = ""        # set via Foundry secret OPENCLAW_GATEWAY_TOKEN
    openclaw_port: int = 18789

    @property
    def llm_proxy_url(self) -> str:
        return f"{self.foundry_url}{self.llm_proxy_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
