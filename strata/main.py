import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from strata.config import settings
from strata.core.proxy import close_client, list_models, proxy_request, proxy_stream
from strata.db import engine as db_engine
from strata.db.tables import init_tables
from strata.models.schemas import ProxyRequest

logging.basicConfig(level=settings.STRATA_LOG_LEVEL, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("strata")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Strata starting on %s:%s", settings.STRATA_HOST, settings.STRATA_PORT)
    await db_engine.connect(settings.STRATA_DB_PATH)
    await init_tables()
    logger.info("Database ready at %s", settings.STRATA_DB_PATH)
    yield
    await close_client()
    await db_engine.close()
    logger.info("Strata shut down")


app = FastAPI(title="Strata", version="0.1.0", lifespan=lifespan)

origins = [o.strip() for o in settings.STRATA_CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(content={"status": "ok"})


@app.post("/v1/chat/completions")
async def chat_completions(request: ProxyRequest):
    if request.stream:
        return StreamingResponse(
            proxy_stream(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    try:
        result = await proxy_request(request)
        return JSONResponse(content=result)
    except Exception as e:
        logger.exception("Upstream error")
        return JSONResponse(
            status_code=502,
            content={"error": {"code": "upstream_error", "message": str(e)}},
        )


@app.get("/v1/models")
async def models():
    try:
        result = await list_models()
        return JSONResponse(content=result)
    except Exception as e:
        logger.exception("Upstream models error")
        return JSONResponse(
            status_code=502,
            content={"error": {"code": "upstream_error", "message": str(e)}},
        )
