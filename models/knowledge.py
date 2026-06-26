from enum import Enum

from pydantic import BaseModel, Field


class ChunkType(str, Enum):
    PLANET_IN_HOUSE = "planet_in_house"
    PLANET_IN_SIGN = "planet_in_sign"
    LORD_IN_HOUSE = "lord_in_house"
    YOGA = "yoga"
    DASHA_MAHADASHA = "dasha_mahadasha"
    DASHA_ANTARDASHA = "dasha_antardasha"
    TRANSIT = "transit"
    HOUSE_SIGNIFICATION = "house_signification"
    NAKSHATRA = "nakshatra"
    GENERAL = "general"
    # Legacy alias kept for backward compat
    PLACEMENT_INTERPRETATION = "placement_interpretation"
    DASHA = "dasha"


class SourceType(str, Enum):
    PUBLIC_DOMAIN = "public_domain"   # Sanskrit original or pre-1928 translation
    PARAPHRASE = "paraphrase"         # Our own summary of classical meaning
    LICENSED = "licensed"             # Licensed translation (must have rights)


class KnowledgeChunk(BaseModel):
    chunk_id: str
    chunk_type: ChunkType
    content: str
    planets_primary: list[str] = Field(default_factory=list)
    planets_secondary: list[str] = Field(default_factory=list)
    houses_primary: list[int] = Field(default_factory=list)
    houses_secondary: list[int] = Field(default_factory=list)
    signs: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    yoga_name: str | None = None
    dasha_pair: list[str] | None = None
    quality_signal: str | None = None
    source: str = ""
    source_type: str = ""             # SourceType value or empty
    authority: str = ""               # "primary" | "secondary"
    version: str = ""
    embedding: list[float] | None = None


class RerankedChunk(BaseModel):
    chunk: KnowledgeChunk
    relevance_score: float
    retrieval_rank: int
