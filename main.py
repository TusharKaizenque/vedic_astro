import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database.mongodb import close_db, connect_db
from routers import chart, chat, compatibility, geo, user

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)


def _warn_missing_config() -> None:
    """Surface soft-optional config gaps at startup rather than silently degrading later."""
    is_prod = settings.app_env.lower() in {"production", "prod"}
    if not settings.jina_api_key:
        logger.warning("JINA_API_KEY not set — reranking/embeddings degrade to fallback order")
    if not settings.llm_base_url and not settings.openai_api_key:
        logger.warning("No LLM endpoint configured (LLM_BASE_URL / OPENAI_API_KEY) — synthesis will fail")
    if is_prod and settings.cors_origins_list == ["*"]:
        logger.warning(
            "CORS is open to all origins in production — set CORS_ALLOW_ORIGINS to your real "
            "frontend origin(s); credentials are disabled while the wildcard is in effect"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — connecting to MongoDB")
    _warn_missing_config()
    database_connected = False
    try:
        await connect_db()
        database_connected = True
    except Exception:
        if settings.app_env.lower() in {"production", "prod"}:
            raise
        logger.exception(
            "MongoDB is unavailable; starting in degraded development mode. "
            "Database-backed endpoints will fail until MONGODB_URI is corrected."
        )
    try:
        yield
    finally:
        if database_connected:
            logger.info("Shutting down — closing MongoDB connection")
            await close_db()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
_cors_origins = settings.cors_origins_list
_cors_allow_all = _cors_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # A wildcard origin with credentials is rejected by browsers and unsafe — only enable
    # credentials when origins are explicitly pinned.
    allow_credentials=not _cors_allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(chart.router, prefix="/api/v1/chart", tags=["chart"])
app.include_router(user.router, prefix="/api/v1/user", tags=["user"])
app.include_router(geo.router, prefix="/api/v1", tags=["geo"])
app.include_router(compatibility.router, prefix="/api/v1/compatibility", tags=["compatibility"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.app_name}


# Serve the single-page frontend at "/" (same-origin → no CORS). Mounted LAST so the API
# routes and /health are matched first; StaticFiles(html=True) serves index.html for "/".
_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
else:
    logger.warning("static/ directory not found — frontend will not be served")
