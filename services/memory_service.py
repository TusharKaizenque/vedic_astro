import json
import logging
from datetime import datetime, timezone

from config import settings
from database.mongodb import (
    conversations_collection, session_summaries_collection, user_memory_collection,
)
from models.memory import SessionSummary, UserLifeEvent, UserMemoryDocument
from services.synthesis_service import generate_response

logger = logging.getLogger(__name__)
_SUMMARY_PROMPT = """Summarize this astrology consultation as JSON with
topics_covered, key_questions, reading_summary, user_reactions, follow_up_flags."""
_FACTS_PROMPT = """Extract only voluntarily shared personal facts as JSON:
relationship_status, occupation, current_concerns, location, life_events,
preferred_topics. Never infer missing facts."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_conversation_history(user_id: str, session_id: str) -> list[dict]:
    # Fetch only the recent tail (not the whole array) and degrade to [] on any DB error —
    # memory is non-essential context; a DB blip must not abort the reading.
    cap = settings.max_conversation_turns * 2 + 10
    try:
        doc = await conversations_collection().find_one(
            {"user_id": user_id, "session_id": session_id},
            {"turns": {"$slice": -cap}},
        )
        turns = doc.get("turns", []) if doc else []
        return [{"role": t["role"], "content": t["content"]} for t in turns]
    except Exception:
        logger.warning("Conversation history read failed; continuing without it", exc_info=True)
        return []


async def save_turn(user_id: str, session_id: str, user_message: str, assistant_response: str) -> None:
    now = _now()
    try:
        await conversations_collection().update_one(
            {"user_id": user_id, "session_id": session_id},
            {
                # $slice caps stored turns so the doc never approaches Mongo's 16MB limit.
                "$push": {"turns": {"$each": [
                    {"role": "user", "content": user_message, "timestamp": now},
                    {"role": "assistant", "content": assistant_response, "timestamp": now},
                ], "$slice": -200}},
                "$set": {"updated_at": now},
                "$setOnInsert": {"created_at": now, "is_summarized": False},
            },
            upsert=True,
        )
    except Exception:
        logger.exception("save_turn failed for %s/%s (turn not persisted)", user_id, session_id)


async def summarize_session(user_id: str, session_id: str) -> None:
    history = await get_conversation_history(user_id, session_id)
    if len(history) < 2:
        return
    text = "\n".join(f"{item['role'].upper()}: {item['content']}" for item in history)
    try:
        data = json.loads(await generate_response([
            {"role": "system", "content": _SUMMARY_PROMPT},
            {"role": "user", "content": text},
        ]))
        summary_text = data.get("reading_summary", "")
        # Reuse the shared embeddings client (configured provider, graceful []-on-failure).
        from utils.embeddings_client import embed as _embed
        embedding_vector = await _embed(summary_text) if summary_text else []
        summary = SessionSummary(
            session_id=session_id, user_id=user_id,
            topics_covered=data.get("topics_covered", []),
            key_questions=data.get("key_questions", []),
            reading_summary=summary_text,
            user_reactions=data.get("user_reactions", []),
            follow_up_flags=data.get("follow_up_flags", []),
            embedding=embedding_vector,
        )
        await session_summaries_collection().update_one(
            {"user_id": user_id, "session_id": session_id},
            {"$set": summary.model_dump()}, upsert=True,
        )
        await conversations_collection().update_one(
            {"user_id": user_id, "session_id": session_id},
            {"$set": {"is_summarized": True}},
        )
        await extract_and_update_user_facts(user_id, history)
    except Exception:
        logger.exception("Session summarization failed for %s", session_id)


async def get_session_summaries(
    user_id: str, current_query: str, top_n: int | None = None
) -> list[SessionSummary]:
    limit = top_n or settings.max_session_summaries
    # Sort by _id (insertion order, always present & indexed) — the summaries had no reliable
    # `date` field. Degrade to [] on DB error so the reading still proceeds.
    try:
        docs = await session_summaries_collection().find(
            {"user_id": user_id}
        ).sort("_id", -1).limit(limit).to_list(length=limit)
    except Exception:
        logger.warning("Session summaries read failed; continuing without them", exc_info=True)
        return []
    result = []
    for doc in docs:
        doc.pop("_id", None)
        doc.pop("embedding", None)
        try:
            result.append(SessionSummary(**doc))
        except Exception as exc:
            logger.warning("Skipping malformed session summary: %s", exc)
    return result


async def get_user_memory(user_id: str) -> UserMemoryDocument | None:
    try:
        doc = await user_memory_collection().find_one({"user_id": user_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return UserMemoryDocument(**doc)
    except Exception:
        logger.warning("User memory read failed; continuing without it", exc_info=True)
        return None


async def extract_and_update_user_facts(user_id: str, history: list[dict]) -> None:
    text = "\n".join(f"{item['role'].upper()}: {item['content']}" for item in history)
    try:
        data = json.loads(await generate_response([
            {"role": "system", "content": _FACTS_PROMPT},
            {"role": "user", "content": text},
        ]))
        set_fields = {"updated_at": _now()}
        for field in ("relationship_status", "occupation", "location"):
            if data.get(field):
                set_fields[f"personal_context.{field}"] = data[field]
        update: dict = {"$set": set_fields, "$setOnInsert": {"user_id": user_id}}
        additions = {}
        if data.get("current_concerns"):
            additions["personal_context.current_concerns"] = {"$each": data["current_concerns"]}
        if data.get("preferred_topics"):
            additions["astrology_preferences.topics_history"] = {"$each": data["preferred_topics"]}
        events = [UserLifeEvent(**event).model_dump() for event in data.get("life_events", []) if event.get("event")]
        if events:
            additions["personal_context.life_events_mentioned"] = {"$each": events}
        if additions:
            update["$addToSet"] = additions
        await user_memory_collection().update_one({"user_id": user_id}, update, upsert=True)
    except Exception:
        logger.exception("User fact extraction failed for %s", user_id)
