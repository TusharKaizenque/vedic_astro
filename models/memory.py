from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConversationTurn(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=utc_now)


class ConversationSession(BaseModel):
    user_id: str
    session_id: str
    turns: list[ConversationTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    is_summarized: bool = False


class SessionSummary(BaseModel):
    session_id: str
    user_id: str
    date: datetime = Field(default_factory=utc_now)
    topics_covered: list[str] = Field(default_factory=list)
    key_questions: list[str] = Field(default_factory=list)
    reading_summary: str = ""
    user_reactions: list[str] = Field(default_factory=list)
    follow_up_flags: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None


class UserLifeEvent(BaseModel):
    event: str
    year: int | None = None
    month: str | None = None


class AstrologyPreferences(BaseModel):
    preferred_topics: list[str] = Field(default_factory=list)
    last_consulted_dashas: dict[str, str] = Field(default_factory=dict)
    topics_history: list[str] = Field(default_factory=list)


class UserPersonalContext(BaseModel):
    relationship_status: str | None = None
    occupation: str | None = None
    current_concerns: list[str] = Field(default_factory=list)
    location: str | None = None
    life_events_mentioned: list[UserLifeEvent] = Field(default_factory=list)


class UserMemoryDocument(BaseModel):
    user_id: str
    personal_context: UserPersonalContext = Field(default_factory=UserPersonalContext)
    astrology_preferences: AstrologyPreferences = Field(default_factory=AstrologyPreferences)
    birth_data: dict | None = None
    updated_at: datetime = Field(default_factory=utc_now)
