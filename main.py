import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database.mongodb import close_db, connect_db
from routers import chart, chat, user

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — connecting to MongoDB")
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(chart.router, prefix="/api/v1/chart", tags=["chart"])
app.include_router(user.router, prefix="/api/v1/user", tags=["user"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.app_name}
