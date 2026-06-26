from pydantic import BaseModel, Field


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
    timezone: str
    place_name: str


class UserCreateRequest(BaseModel):
    email: str
    name: str
