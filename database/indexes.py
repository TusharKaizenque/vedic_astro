"""Create standard MongoDB indexes.

The Atlas ``knowledge_vector_index`` must be created in the Atlas UI with a
1536-dimensional cosine ``knnVector`` field at ``embedding`` and filter fields
matching ``models.knowledge.KnowledgeChunk``.
"""

import asyncio
import logging

from pymongo import ASCENDING, TEXT

from database.mongodb import close_db, connect_db, get_db

logger = logging.getLogger(__name__)


async def create_indexes() -> None:
    await connect_db()
    try:
        db = get_db()
        await db["charts"].create_index([("user_id", ASCENDING)], unique=True)
        await db["charts"].create_index([("birth_data.date", ASCENDING)])
        await db["knowledge"].create_index([("content", TEXT)])
        for field in ("chunk_type", "planets_primary", "houses_primary", "topics"):
            await db["knowledge"].create_index([(field, ASCENDING)])
        await db["conversations"].create_index(
            [("user_id", ASCENDING), ("session_id", ASCENDING)]
        )
        await db["conversations"].create_index(
            [("updated_at", ASCENDING)], expireAfterSeconds=2_592_000
        )
        await db["session_summaries"].create_index([("user_id", ASCENDING)])
        await db["session_summaries"].create_index([("date", ASCENDING)])
        await db["user_memory"].create_index([("user_id", ASCENDING)], unique=True)
        await db["users"].create_index([("email", ASCENDING)], unique=True)
        await db["users"].create_index([("user_id", ASCENDING)], unique=True)
        logger.info("All MongoDB indexes created successfully")
    finally:
        await close_db()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(create_indexes())
