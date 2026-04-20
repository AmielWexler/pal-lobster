import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import chat, health, llm_proxy_passthrough
from app.services import ontology
from app.services.llm_proxy import close_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_client()
    await ontology.close_client()


app = FastAPI(title="Lobster Backend", lifespan=lifespan)

# CORS — only added when cors_origins is configured (local dev only).
# In production the frontend calls the CM function endpoint, not FastAPI directly.
_settings = get_settings()
if _settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
    logging.getLogger(__name__).info(
        "CORS enabled for origins: %s", _settings.cors_origins
    )

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(llm_proxy_passthrough.router)
