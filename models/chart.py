from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BirthData(BaseModel):
    date: str
    time: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str
    place_name: str


class PlanetPosition(BaseModel):
    planet: str
    longitude: float
    sign: str
    house: int
    nakshatra: str
    nakshatra_pada: int
    is_retrograde: bool = False
    degree_in_sign: float
    strength: str = ""


class HouseData(BaseModel):
    house_number: int
    sign: str
    lord: str
    degree: float


class DashaData(BaseModel):
    maha_dasha_lord: str
    maha_dasha_start: str
    maha_dasha_end: str
    antar_dasha_lord: str
    antar_dasha_start: str
    antar_dasha_end: str
    pratyantara_dasha_lord: str | None = None
    pratyantara_dasha_start: str | None = None
    pratyantara_dasha_end: str | None = None
    years_remaining_maha: float | None = None


class NormalizedChart(BaseModel):
    user_id: str
    birth_data: BirthData
    lagna_sign: str
    lagna_degree: float
    moon_sign: str
    sun_sign: str
    nakshatra: str
    nakshatra_pada: int
    planets: dict[str, PlanetPosition]
    houses: dict[int, HouseData]
    dasha: DashaData
    yogas_raw: list[dict] = Field(default_factory=list)
    divisional_charts: dict = Field(default_factory=dict)
    cached_at: datetime = Field(default_factory=utc_now)
    raw_prokerala_response: dict = Field(default_factory=dict)
