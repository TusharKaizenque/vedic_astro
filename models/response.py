import re
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")
# Offset (+05:30 / -08:00 / Z) or IANA-ish name (Asia/Kolkata, UTC).
_TZ_RE = re.compile(r"^(Z|[+-]\d{2}:\d{2}|[A-Za-z][A-Za-z0-9_+\-/]{1,63})$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)
    session_id: str = Field(min_length=1, max_length=200)


class ChatResponse(BaseModel):
    session_id: str
    response: str
    intent: str


class StreamChunk(BaseModel):
    type: str
    content: str | None = None
    error: str | None = None


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    code: str = "INTERNAL_ERROR"


class ChartRequest(BaseModel):
    date: str
    time: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = Field(min_length=1, max_length=64)
    place_name: str = Field(min_length=1, max_length=200)

    @field_validator("date")
    @classmethod
    def _valid_date(cls, v: str) -> str:
        v = v.strip()
        if not _DATE_RE.match(v):
            raise ValueError("date must be ISO format YYYY-MM-DD")
        try:
            parsed = datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError("date is not a real calendar date")
        if parsed > datetime.now(timezone.utc):
            raise ValueError("birth date cannot be in the future")
        return v

    @field_validator("time")
    @classmethod
    def _valid_time(cls, v: str) -> str:
        v = v.strip()
        if not _TIME_RE.match(v):
            raise ValueError("time must be 24-hour HH:MM or HH:MM:SS")
        fmt = "%H:%M:%S" if v.count(":") == 2 else "%H:%M"
        try:
            datetime.strptime(v, fmt)
        except ValueError:
            raise ValueError("time is not a valid 24-hour clock value")
        return v

    @field_validator("timezone")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        v = v.strip()
        if not _TZ_RE.match(v):
            raise ValueError("timezone must be an offset (+05:30) or IANA name (Asia/Kolkata)")
        return v


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email address")
        return v.lower()
