import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from config import settings
from database.mongodb import charts_collection
from models.chart import BirthData, NormalizedChart
from utils.chart_normalizer import build_chart_summary, normalize_prokerala_response

logger = logging.getLogger(__name__)
_prokerala_token: dict[str, str | float] = {}
_token_lock = asyncio.Lock()


async def _get_prokerala_token() -> str:
    async with _token_lock:
        now = datetime.now(timezone.utc).timestamp()
        if _prokerala_token.get("token") and float(_prokerala_token.get("expires_at", 0)) > now + 60:
            return str(_prokerala_token["token"])
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                settings.prokerala_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.prokerala_client_id,
                    "client_secret": settings.prokerala_client_secret,
                },
            )
            response.raise_for_status()
            payload = response.json()
        _prokerala_token.update(
            token=payload["access_token"], expires_at=now + int(payload.get("expires_in", 3600))
        )
        return str(payload["access_token"])


async def _call_prokerala(endpoint: str, params: dict, token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{settings.prokerala_base_url}/{endpoint}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()


async def fetch_full_chart(birth_data: BirthData) -> dict:
    # TODO: ASTROLOGY EXPERT REQUIRED — Verify endpoint names and response fields live.
    token = await _get_prokerala_token()
    local_dt = datetime.fromisoformat(f"{birth_data.date}T{birth_data.time}:00").replace(
        tzinfo=ZoneInfo(birth_data.timezone)
    )
    params = {
        "ayanamsa": 1,
        "coordinates": f"{birth_data.latitude},{birth_data.longitude}",
        "datetime": local_dt.isoformat(),
    }
    planets_task = _call_prokerala("planet-position", params, token)
    kundli_task = _call_prokerala("kundli/advanced", params, token)
    planets, kundli = await asyncio.gather(planets_task, kundli_task)
    merged = {**planets.get("data", planets)}
    kundli_data = kundli.get("data", kundli)
    merged["dasha_periods"] = kundli_data.get("dasha_periods", [])
    merged["dasha_balance"] = kundli_data.get("dasha_balance", {})
    merged.setdefault("yoga_details", kundli_data.get("yoga_details", []))
    merged.setdefault("nakshatra", kundli_data.get("nakshatra_details", {}))
    return merged


async def fetch_transit_positions(target_dt: datetime, latitude: float, longitude: float) -> dict:
    """Fetch planet positions for a target datetime (for gochara/transits).

    Uses the same Prokerala endpoint + ayanamsa (Lahiri, ayanamsa=1) as the natal chart,
    so transit signs are directly comparable to natal positions. Best-effort: callers
    should handle a {} return on failure."""
    try:
        token = await _get_prokerala_token()
        params = {
            "ayanamsa": 1,
            "coordinates": f"{latitude},{longitude}",
            "datetime": target_dt.isoformat(),
        }
        return await _call_prokerala("planet-position", params, token)
    except Exception:
        logger.exception("Transit position fetch failed")
        return {}


async def get_chart(user_id: str) -> NormalizedChart | None:
    document = await charts_collection().find_one({"user_id": user_id})
    if not document:
        return None
    document.pop("_id", None)
    return NormalizedChart(**document)


async def save_chart(chart: NormalizedChart) -> None:
    document = chart.model_dump()
    # BSON document keys must be strings; Pydantic converts these back to ints
    # when the chart is loaded into ``NormalizedChart``.
    document["houses"] = {str(number): value for number, value in document["houses"].items()}
    await charts_collection().update_one(
        {"user_id": chart.user_id}, {"$set": document}, upsert=True
    )


async def generate_and_save_chart(user_id: str, birth_data: BirthData) -> NormalizedChart:
    chart = normalize_prokerala_response(await fetch_full_chart(birth_data), user_id, birth_data)
    await save_chart(chart)
    return chart


def get_chart_summary_cached(chart: NormalizedChart) -> str:
    return build_chart_summary(chart)
