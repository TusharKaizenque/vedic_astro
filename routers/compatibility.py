"""Compatibility — match the logged-in user's chart against a partner's birth details."""
import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from models.chart import BirthData
from models.response import ChartRequest
from services import chart_service
from services.compatibility import assess_compatibility

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/{user_id}")
async def compatibility(user_id: str, request: ChartRequest):
    """Ashtakoot + Mangal compatibility between the user's stored chart and a partner
    (the partner's chart is computed transiently from the supplied birth data)."""
    chart_a = await chart_service.get_chart(user_id)
    if not chart_a:
        raise HTTPException(status_code=404, detail="Generate your own chart first.")
    try:
        chart_b = await chart_service.build_partner_chart(BirthData(**request.model_dump()))
    except Exception as exc:
        logger.exception("Partner chart computation failed for compatibility")
        raise HTTPException(status_code=502, detail="Could not compute the partner's chart.") from exc
    return asdict(assess_compatibility(chart_a, chart_b))
