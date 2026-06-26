from enum import Enum

from pydantic import BaseModel, Field


class IntentCategory(str, Enum):
    PLACEMENT_INTERPRETATION = "placement_interpretation"
    TOPIC_READING = "topic_reading"
    DASHA_QUERY = "dasha_query"
    TRANSIT_QUERY = "transit_query"
    YOGA_QUERY = "yoga_query"
    TIMING_QUERY = "timing_query"
    COMPARISON_QUERY = "comparison_query"
    CLARIFICATION = "clarification"
    GENERAL_ASTROLOGY = "general_astrology"
    OUT_OF_DOMAIN = "out_of_domain"


class IntentEntities(BaseModel):
    planets: list[str] = Field(default_factory=list)
    houses: list[int] = Field(default_factory=list)
    signs: list[str] = Field(default_factory=list)
    dashas: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    time_references: list[str] = Field(default_factory=list)


class IntentResult(BaseModel):
    intent: IntentCategory
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    entities: IntentEntities = Field(default_factory=IntentEntities)
    requires_chart: bool = True
    requires_transits: bool = False
    requires_dasha: bool = False
    retrieval_topics: list[str] = Field(default_factory=list)
    reasoning: str = ""
