import json
import logging

from config import settings
from utils.llm_client import get_llm_client
from models.chart import NormalizedChart
from models.intent import IntentResult
from services.rule_engine.engine import RuleEngineResult
from utils.chart_normalizer import build_chart_summary

logger = logging.getLogger(__name__)
_SYSTEM_PROMPT = """Identify only the chart factors relevant to the question; do not
predict. Return JSON containing relevant_placements, active_dasha,
relevant_yogas, topic_significators, key_tensions, and overall_chart_direction."""


async def analyze_chart_for_question(
    chart: NormalizedChart,
    rule_result: RuleEngineResult,
    question: str,
    intent: IntentResult,
) -> dict:
    content = (
        f"Chart:\n{build_chart_summary(chart)}\n"
        f"Yogas: {rule_result.yogas_present}\nDoshas: {rule_result.doshas_present}\n"
        f"Strengths: {json.dumps(rule_result.planet_strengths)}\n"
        f"Question: {question}\nIntent: {intent.intent.value}"
    )
    client = get_llm_client()
    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model=settings.openai_reasoning_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                temperature=0.1,
                max_tokens=800,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content or "{}")
        except Exception as exc:
            logger.warning("Chart reasoning attempt %s failed: %s", attempt + 1, exc)
    return {}


def format_chart_analysis_for_prompt(analysis: dict) -> str:
    if not analysis:
        return ""
    lines = ["[CHART ANALYSIS — question-relevant factors]"]
    raw_placements = analysis.get("relevant_placements", [])
    placements = list(raw_placements.values()) if isinstance(raw_placements, dict) else raw_placements
    for placement in (placements or []):
        if not isinstance(placement, dict):
            continue
        lines.append(
            f"• {placement.get('planet')} in house {placement.get('house')} "
            f"({placement.get('sign')}, {placement.get('strength')}): "
            f"{placement.get('why_relevant', '')}"
        )
    dasha = analysis.get("active_dasha", {})
    if dasha:
        lines.append(f"Dasha: {dasha.get('maha')}/{dasha.get('antar')} — {dasha.get('relevance', '')}")
    raw_yogas = analysis.get("relevant_yogas", [])
    yogas = list(raw_yogas.values()) if isinstance(raw_yogas, dict) else raw_yogas
    for yoga in (yogas or []):
        if isinstance(yoga, dict):
            lines.append(f"• {yoga.get('yoga')}: {yoga.get('relevance', '')}")
        elif isinstance(yoga, str):
            lines.append(f"• {yoga}")
    tensions = analysis.get("key_tensions", [])
    if tensions and isinstance(tensions, list):
        lines.append(f"Tensions: {'; '.join(str(t) for t in tensions)}")
    if analysis.get("overall_chart_direction"):
        lines.append(f"Direction: {analysis['overall_chart_direction']}")
    return "\n".join(lines)
