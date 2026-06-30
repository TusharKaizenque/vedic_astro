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
        token_value = payload.get("access_token")
        if not token_value:
            raise RuntimeError("Prokerala token response did not contain access_token")
        _prokerala_token.update(
            token=token_value, expires_at=now + int(payload.get("expires_in", 3600))
        )
        return str(token_value)


async def _call_prokerala(endpoint: str, params: dict, token: str) -> dict:
    """GET a Prokerala endpoint with bounded retries: refresh-and-retry once on 401,
    exponential backoff on timeouts and 5xx. Raises if all attempts fail."""
    url = f"{settings.prokerala_base_url}/{endpoint}"
    delay = 0.5
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    url, params=params, headers={"Authorization": f"Bearer {token}"}
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401 and attempt == 0:
                _prokerala_token.clear()          # token stale/revoked — force a fresh one
                token = await _get_prokerala_token()
                continue
            if status >= 500 and attempt < 2:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            raise
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt < 2:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError(f"Prokerala call to {endpoint} failed after retries")


async def fetch_full_chart(birth_data: BirthData) -> dict:
    # TODO: ASTROLOGY EXPERT REQUIRED — Verify endpoint names and response fields live.
    token = await _get_prokerala_token()
    # Accept time as HH:MM or HH:MM:SS — append seconds only when they're absent, so a
    # caller-supplied "19:30:00" doesn't become the invalid "19:30:00:00".
    time_str = birth_data.time.strip()
    if time_str.count(":") == 1:
        time_str += ":00"
    local_dt = datetime.fromisoformat(f"{birth_data.date}T{time_str}").replace(
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


async def build_partner_chart(birth_data: BirthData) -> NormalizedChart:
    """A lightweight chart for a compatibility partner — only the planet-position endpoint
    (30 credits, not the full 330): Guna Milan + Mangal need just Moon nakshatra/sign and the
    Mars/Venus placements. NOT persisted (transient)."""
    token = await _get_prokerala_token()
    time_str = birth_data.time.strip()
    if time_str.count(":") == 1:
        time_str += ":00"
    local_dt = datetime.fromisoformat(f"{birth_data.date}T{time_str}").replace(
        tzinfo=ZoneInfo(birth_data.timezone)
    )
    params = {
        "ayanamsa": 1,
        "coordinates": f"{birth_data.latitude},{birth_data.longitude}",
        "datetime": local_dt.isoformat(),
    }
    raw = await _call_prokerala("planet-position", params, token)
    return normalize_prokerala_response(raw, "partner", birth_data)


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
    try:
        return NormalizedChart(**document)
    except Exception:
        # A corrupt cached chart should look like "no chart" (prompt to regenerate),
        # not crash the request.
        logger.exception("Cached chart for %s is corrupt; treating as missing", user_id)
        return None


async def save_chart(chart: NormalizedChart) -> None:
    document = chart.model_dump()
    # BSON document keys must be strings; Pydantic converts these back to ints
    # when the chart is loaded into ``NormalizedChart``.
    document["houses"] = {str(number): value for number, value in document["houses"].items()}
    await charts_collection().update_one(
        {"user_id": chart.user_id}, {"$set": document}, upsert=True
    )


def _time_key(t: str) -> tuple:
    """Normalize 'HH:MM' / 'HH:MM:SS' to (h, m, s) so the two formats compare equal."""
    try:
        parts = [int(x) for x in t.strip().split(":")]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except (ValueError, AttributeError):
        return (t,)  # unparseable → compare raw, so a mismatch errs toward regenerating


def _same_birth(a: BirthData, b: BirthData) -> bool:
    """Same astronomically-relevant birth inputs → the chart would be identical, so there's
    no reason to pay Prokerala again. (place_name is cosmetic and ignored.)"""
    return (
        a.date == b.date
        and _time_key(a.time) == _time_key(b.time)
        and a.timezone == b.timezone
        and round(a.latitude, 4) == round(b.latitude, 4)
        and round(a.longitude, 4) == round(b.longitude, 4)
    )


async def generate_and_save_chart(
    user_id: str, birth_data: BirthData, force: bool = False
) -> NormalizedChart:
    # Cache-first: if a chart for the SAME birth data already exists, reuse it instead of
    # re-billing Prokerala. Only call the API for a new/changed chart or an explicit force.
    if not force:
        existing = await get_chart(user_id)
        if existing is not None and _same_birth(existing.birth_data, birth_data):
            logger.info("Reusing cached chart for %s (no Prokerala call)", user_id)
            return existing
    chart = normalize_prokerala_response(await fetch_full_chart(birth_data), user_id, birth_data)
    # Don't persist a degenerate chart — normalize already gates luminaries/lagna, but
    # guard the planet set explicitly so a bad upstream response can't poison the cache.
    if not chart.planets:
        raise ValueError("Generated chart has no planets — refusing to save")
    await save_chart(chart)
    return chart


def get_chart_summary_cached(chart: NormalizedChart) -> str:
    return build_chart_summary(chart)
