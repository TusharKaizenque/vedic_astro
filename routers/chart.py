import logging

from fastapi import APIRouter, HTTPException

from models.chart import BirthData
from models.response import ChartRequest
from services import chart_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{user_id}/generate")
async def generate_chart(user_id: str, request: ChartRequest, force: bool = False):
    # force=true bypasses the cache and re-fetches from Prokerala (e.g. corrected birth data).
    try:
        chart = await chart_service.generate_and_save_chart(
            user_id, BirthData(**request.model_dump()), force=force
        )
        return {
            "status": "success", "lagna": chart.lagna_sign,
            "moon_sign": chart.moon_sign, "sun_sign": chart.sun_sign,
            "nakshatra": chart.nakshatra,
            "active_dasha": {
                "maha": chart.dasha.maha_dasha_lord,
                "antar": chart.dasha.antar_dasha_lord,
            },
        }
    except Exception as exc:
        logger.exception("Chart generation failed for %s", user_id)
        raise HTTPException(status_code=502, detail="Chart provider request failed") from exc


@router.get("/{user_id}")
async def get_chart(user_id: str):
    chart = await chart_service.get_chart(user_id)
    if not chart:
        raise HTTPException(status_code=404, detail="No chart found. Generate one first.")
    return chart.model_dump(exclude={"raw_prokerala_response"})


@router.get("/{user_id}/summary")
async def get_chart_summary(user_id: str):
    chart = await chart_service.get_chart(user_id)
    if not chart:
        raise HTTPException(status_code=404, detail="No chart found.")
    return {"summary": chart_service.get_chart_summary_cached(chart)}
