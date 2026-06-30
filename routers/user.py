import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pymongo.errors import DuplicateKeyError

from database.mongodb import (
    charts_collection, conversations_collection, session_summaries_collection,
    user_memory_collection, users_collection,
)
from models.response import UserCreateRequest

router = APIRouter()


@router.get("")
async def list_users():
    """All accounts (newest first), each flagged with whether a chart has been generated —
    powers the sidebar account switcher."""
    docs = await users_collection().find(
        {}, {"_id": 0, "user_id": 1, "name": 1, "email": 1, "created_at": 1}
    ).sort("created_at", -1).to_list(length=500)
    with_charts = set(await charts_collection().distinct("user_id"))
    users = [
        {"user_id": d["user_id"], "name": d.get("name", ""), "email": d.get("email", ""),
         "has_chart": d["user_id"] in with_charts}
        for d in docs
    ]
    return {"users": users}


@router.post("/register")
async def register_user(request: UserCreateRequest):
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    document = {
        "user_id": user_id, "email": request.email.strip().lower(),
        "name": request.name.strip(), "created_at": now, "updated_at": now,
    }
    try:
        await users_collection().insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Email already registered.") from exc
    return {key: document[key] for key in ("user_id", "email", "name")}


@router.get("/{user_id}")
async def get_user(user_id: str):
    document = await users_collection().find_one(
        {"user_id": user_id}, {"_id": 0, "user_id": 1, "email": 1, "name": 1}
    )
    if not document:
        raise HTTPException(status_code=404, detail="User not found.")
    return document


@router.delete("/{user_id}")
async def delete_user(user_id: str):
    """Delete an account and cascade-remove all of its data (chart, conversations,
    session summaries, extracted memory)."""
    result = await users_collection().delete_one({"user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found.")
    for coll in (charts_collection, conversations_collection,
                 session_summaries_collection, user_memory_collection):
        await coll().delete_many({"user_id": user_id})
    return {"status": "deleted", "user_id": user_id}
