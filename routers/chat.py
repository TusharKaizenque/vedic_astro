import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from models.response import ChatRequest
from services import (
    chart_service, intent_classifier, memory_service, prompt_builder,
    synthesis_service,
)
from services.retrieval import retrieval_service
from services.rule_engine.engine import run_rule_engine
from services.rule_engine.strength_engine import compute_all_strengths
from services.topic_pipeline import analyze_topics
from services.transit_engine import (
    gochara_report, parse_transit_positions, resolve_transit_date,
)
from services.dasha_analyzer import analyze_projected_dasha
from services.dasha_projection import project_dasha
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter()


async def _build_transit_report(chart, target, topic_bundles):
    """Fetch transit positions for the target date and compute a gochara report."""
    try:
        raw = await chart_service.fetch_transit_positions(
            target, chart.birth_data.latitude, chart.birth_data.longitude
        )
        positions = parse_transit_positions(raw)
        if not positions:
            return None
        topic_houses = (
            topic_bundles[0].significators.primary_houses if topic_bundles else []
        )
        dasha_lords = [chart.dasha.maha_dasha_lord, chart.dasha.antar_dasha_lord]
        return gochara_report(chart, positions, target.strftime("%Y"), topic_houses, dasha_lords)
    except Exception:
        logger.exception("Transit report build failed")
        return None


def _build_future_dasha(chart, rules, strengths, target, topic_bundles):
    """Project the Vimshottari dasha to the target date and read it for the topic (#1)."""
    try:
        if not topic_bundles:
            return ""
        proj = project_dasha(
            chart.dasha.maha_dasha_lord, chart.dasha.maha_dasha_start, target,
            current_antar=chart.dasha.antar_dasha_lord,
        )
        b = topic_bundles[0]
        return analyze_projected_dasha(
            chart, rules, strengths, b.topic,
            b.significators.primary_houses, b.significators.karaka_planets, proj,
        )
    except Exception:
        logger.exception("Future dasha projection failed")
        return ""


@router.post("/{user_id}")
async def chat(user_id: str, request: ChatRequest):
    async def event_generator() -> AsyncGenerator[dict, None]:
        full_response = ""
        try:
            history = await memory_service.get_conversation_history(user_id, request.session_id)
            intent = await intent_classifier.classify_intent(request.message, history[-4:])
            chart = await chart_service.get_chart(user_id) if intent.requires_chart else None
            rules = run_rule_engine(chart) if chart else None
            # Multi-topic deterministic pipeline: per topic → significators → retrieval →
            # reasoning report → verdict → dasha timing → deeper structure. The verdict is
            # computed deterministically (classical strength), so the LLM only narrates it.
            topic_bundles = None
            chunks = []
            transit_report = None
            future_dasha = ""
            if chart and rules:
                strengths = compute_all_strengths(chart)
                topic_bundles = await analyze_topics(
                    intent, chart, rules, strengths, request.message
                )
                # For timing / future-dated questions: gochara transits + forward dasha.
                if intent.requires_transits or intent.entities.time_references:
                    target = resolve_transit_date(
                        intent.entities.time_references, datetime.now(timezone.utc)
                    )
                    transit_report = await _build_transit_report(chart, target, topic_bundles)
                    future_dasha = _build_future_dasha(
                        chart, rules, strengths, target, topic_bundles
                    )
            else:
                # No chart (general astrology): retrieve raw KB for the fallback path.
                chunks = await retrieval_service.retrieve(
                    intent, None, chart, request.message, rules
                )
            memory, summaries = await asyncio.gather(
                memory_service.get_user_memory(user_id),
                memory_service.get_session_summaries(user_id, request.message),
            )
            descriptive = intent_classifier.is_descriptive_query(request.message)
            messages = prompt_builder.build(
                request.message, intent, chart, rules, topic_bundles, chunks,
                memory, summaries, history, transit_report, future_dasha, descriptive,
            )
            async for token in synthesis_service.stream_response(messages):
                full_response += token
                yield {"data": json.dumps({"type": "content", "content": token})}
            yield {"data": json.dumps({"type": "done"})}
        except Exception:
            logger.exception("Chat pipeline failed for user %s", user_id)
            yield {"data": json.dumps({"type": "error", "error": "An error occurred. Please try again."})}
        finally:
            if full_response:
                asyncio.create_task(
                    memory_service.save_turn(
                        user_id, request.session_id, request.message, full_response
                    )
                )
    return EventSourceResponse(event_generator())


@router.post("/{user_id}/session/end")
async def end_session(user_id: str, session_id: str):
    asyncio.create_task(memory_service.summarize_session(user_id, session_id))
    return {"status": "summarization_queued", "session_id": session_id}


@router.get("/{user_id}/history/{session_id}")
async def get_history(user_id: str, session_id: str):
    return {
        "session_id": session_id,
        "turns": await memory_service.get_conversation_history(user_id, session_id),
    }
