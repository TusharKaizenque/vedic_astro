"""Geocoding — turn a place name into coordinates + timezone, so users don't hand-enter
lat/lon or have to know the IANA timezone for their birthplace.

Uses OpenStreetMap Nominatim (free, no key) for place → coordinates, and `timezonefinder`
(offline, accurate per-coordinate) to derive the precise IANA timezone — so "Seattle"
resolves to America/Los_Angeles without the user knowing that name.
"""
import logging

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
logger = logging.getLogger(__name__)

_NOMINATIM = "https://nominatim.openstreetmap.org/search"

_tf = None


def _finder():
    """Lazily build the TimezoneFinder (its data load is deferred off server startup)."""
    global _tf
    if _tf is None:
        from timezonefinder import TimezoneFinder
        _tf = TimezoneFinder()
    return _tf


@router.get("/geocode")
async def geocode(q: str = Query(min_length=2, max_length=200)):
    """Return up to 6 place matches with coordinates for the query string."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                _NOMINATIM,
                params={"q": q, "format": "json", "limit": 6, "addressdetails": 0},
                # Nominatim's usage policy requires an identifying User-Agent.
                headers={"User-Agent": "vedic-astro-backend/1.0 (birth-chart geocoding)"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Geocoding failed for %r: %s", q, exc)
        raise HTTPException(status_code=502, detail="Geocoding service unavailable") from exc

    tf = _finder()
    results = []
    for d in data if isinstance(data, list) else []:
        try:
            lat = round(float(d["lat"]), 6)
            lon = round(float(d["lon"]), 6)
        except (KeyError, ValueError, TypeError):
            continue
        try:
            tz = tf.timezone_at(lat=lat, lng=lon) or ""
        except Exception:
            tz = ""
        results.append({
            "display_name": d.get("display_name", ""),
            "latitude": lat, "longitude": lon, "timezone": tz,
        })
    return {"results": results}
