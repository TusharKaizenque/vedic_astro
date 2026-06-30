import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from config import settings

logger = logging.getLogger(__name__)
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    global _client, _db
    if _client is not None:          # idempotent: don't leak a prior client on reconnect
        _client.close()
    # Bounded timeouts + pooling so a slow/unreachable DB fails fast instead of hanging 30s
    # per request and exhausting the event loop under load.
    _client = AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=20000,
        maxPoolSize=50,
        retryWrites=True,
    )
    _db = _client[settings.mongodb_db_name]
    await _client.admin.command("ping")
    logger.info("Connected to MongoDB: %s", settings.mongodb_db_name)


async def close_db() -> None:
    global _client, _db
    if _client:
        _client.close()
        logger.info("MongoDB connection closed")
    _client = None
    _db = None


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return _db


def charts_collection():
    return get_db()["charts"]


def knowledge_collection():
    return get_db()["knowledge"]


def knowledge_gaps_collection():
    """Tracks chart factors that had no classical source — drives data-driven KB growth."""
    return get_db()["knowledge_gaps"]


def conversations_collection():
    return get_db()["conversations"]


def session_summaries_collection():
    return get_db()["session_summaries"]


def user_memory_collection():
    return get_db()["user_memory"]


def users_collection():
    return get_db()["users"]
