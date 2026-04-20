import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

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

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(llm_proxy_passthrough.router)
