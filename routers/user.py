import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pymongo.errors import DuplicateKeyError

from database.mongodb import users_collection
from models.response import UserCreateRequest

router = APIRouter()


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
