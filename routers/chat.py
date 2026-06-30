import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from models.response import ChatRequest
from services import (
    chart_service, coverage, faithfulness, gap_logger, intent_classifier, memory_service,
    prompt_builder, synthesis_service,
)
from services.chart_signatures import select_signatures
from services.retrieval import retrieval_service
from services.rule_engine.engine import run_rule_engine
from services.rule_engine.strength_engine import compute_all_strengths
from services.topic_pipeline import analyze_topics
from services.life_overview import build_life_overview, format_life_overview_for_prompt
from services.spouse_engine import build_spouse_profile, format_spouse_profile_for_prompt
from services.marriage_timing import build_marriage_timing, format_marriage_timing_for_prompt
from services.transit_engine import (
    gochara_report, parse_transit_positions, resolve_transit_date,
)
from services.dasha_analyzer import analyze_projected_dasha
from services.dasha_projection import project_dasha
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter()

# Hold strong refs to fire-and-forget tasks so the event loop can't GC them mid-flight.
_background_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


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
        completed = False
        required_signatures = []  # very-high + high signatures the narration must cover
        try:
            history = await memory_service.get_conversation_history(user_id, request.session_id)
            intent = await intent_classifier.classify_intent(request.message, history[-4:])
            chart = await chart_service.get_chart(user_id) if intent.requires_chart else None
            # The question needs a chart but none exists — guide the user instead of
            # silently answering from generic knowledge (which reads as a wrong/vague reply).
            if intent.requires_chart and chart is None:
                yield {"data": json.dumps({"type": "content", "content": (
                    "I don't have your birth chart yet. Please generate it first by sharing your "
                    "birth date, exact time, and place — then I can give you an accurate reading."
                )})}
                yield {"data": json.dumps({"type": "done"})}
                return
            rules = run_rule_engine(chart) if chart else None
            # Multi-topic deterministic pipeline: per topic → significators → retrieval →
            # reasoning report → verdict → dasha timing → deeper structure. The verdict is
            # computed deterministically (classical strength), so the LLM only narrates it.
            topic_bundles = None
            chunks = []
            transit_report = None
            future_dasha = ""
            life_overview_text = ""
            spouse_text = ""
            marriage_timing_text = ""
            if chart and rules:
                strengths = compute_all_strengths(chart)
                # Broad life questions → whole-chart synthesis across all domains.
                if intent_classifier.is_life_overview_query(request.message):
                    overview = build_life_overview(
                        chart, rules, strengths, datetime.now(timezone.utc)
                    )
                    life_overview_text = format_life_overview_for_prompt(overview)
                    # The strongly-supported signatures (very-high + high) MUST appear in the
                    # reading (coverage backstop); a dropped one triggers a continuation.
                    required_signatures = [
                        s for s in select_signatures(overview.signatures)
                        if s.confidence in ("very high", "high")
                    ]
                    # Use all prominent domains (already capped at 4 upstream) so the grounded
                    # bundles match the breadth the overview leads with — don't re-narrow to 3.
                    prominent = [t for t, _ in overview.prominent_domains]
                    topic_bundles = await analyze_topics(
                        intent, chart, rules, strengths, request.message, topics=prominent
                    )
                else:
                    topic_bundles = await analyze_topics(
                        intent, chart, rules, strengths, request.message
                    )
                # Record any ungrounded factors so KB growth is data-driven (fire-and-forget).
                for _b in topic_bundles:
                    if _b.report:
                        _spawn(gap_logger.log_gaps(_b.report, _b.significators, _b.topic))
                # Deep, individualized spouse portrait when the question touches marriage.
                _is_marriage = any(
                    _b.topic in {"marriage", "spouse", "relationship", "partner", "love"}
                    for _b in topic_bundles
                )
                if _is_marriage:
                    spouse_text = format_spouse_profile_for_prompt(
                        build_spouse_profile(chart, rules, strengths)
                    )
                    # Marriage timing windows — for "when/will" questions (not pure spouse
                    # descriptions), from the dasha of marriage significators.
                    if not intent_classifier.is_descriptive_query(request.message):
                        marriage_timing_text = format_marriage_timing_for_prompt(
                            build_marriage_timing(chart, rules, datetime.now(timezone.utc)),
                            datetime.now(timezone.utc),
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
                life_overview_text, spouse_text, marriage_timing_text,
            )
            async for token in synthesis_service.stream_response(messages):
                full_response += token
                yield {"data": json.dumps({"type": "content", "content": token})}
            # Coverage guarantee: if a very-high signature was dropped from the narration,
            # stream a short continuation so a strongly-indicated theme is never omitted.
            if required_signatures and full_response:
                missing = coverage.missing_signatures(full_response, required_signatures)
                if missing:
                    logger.info("Coverage: continuing for %d dropped signature(s): %s",
                                len(missing), [s.label for s in missing])
                    addendum = await coverage.generate_addendum(missing)
                    if addendum:
                        block = "\n\n" + addendum
                        full_response += block
                        yield {"data": json.dumps({"type": "content", "content": block})}
            yield {"data": json.dumps({"type": "done"})}
            completed = True
            # Anti-hallucination metric: flag any placement claim that contradicts the
            # locked chart facts (the prompt grounds these, this verifies them).
            if chart is not None and full_response:
                contradictions = faithfulness.verify_response(full_response, chart)
                if contradictions:
                    logger.warning(
                        "Faithfulness: %d contradiction(s) for user %s — %s",
                        len(contradictions), user_id,
                        "; ".join(f"said '{c.claim}' but {c.actual}" for c in contradictions),
                    )
        except Exception:
            logger.exception("Chat pipeline failed for user %s", user_id)
            yield {"data": json.dumps({"type": "error", "error": "An error occurred. Please try again."})}
        finally:
            # Only persist a fully-streamed answer — never a partial response left by an error.
            if completed and full_response:
                _spawn(
                    memory_service.save_turn(
                        user_id, request.session_id, request.message, full_response
                    )
                )
    return EventSourceResponse(event_generator())


@router.post("/{user_id}/session/end")
async def end_session(user_id: str, session_id: str):
    _spawn(memory_service.summarize_session(user_id, session_id))
    return {"status": "summarization_queued", "session_id": session_id}


@router.get("/{user_id}/history/{session_id}")
async def get_history(user_id: str, session_id: str):
    return {
        "session_id": session_id,
        "turns": await memory_service.get_conversation_history(user_id, session_id),
    }
