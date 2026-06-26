"""
Query builder — builds targeted retrieval queries from SignificatorResult.

Using significators (deterministic) instead of LLM chart_analysis gives more
precise queries: we know exactly which planets/houses are relevant.
"""
from __future__ import annotations

from models.chart import NormalizedChart
from models.intent import IntentCategory, IntentResult
from services.rule_engine.engine import RuleEngineResult
from utils.astro_constants import TOPIC_HOUSE_MAP, TOPIC_PLANET_MAP


def _filter(houses: list[int], planets: list[str], topics: list[str]) -> dict:
    conditions = []
    if houses:
        conditions.append({"houses_primary": {"$in": houses}})
    if planets:
        conditions.append({"planets_primary": {"$in": planets}})
    if topics:
        conditions.append({"topics": {"$in": topics}})
    return {"$or": conditions} if conditions else {}


def build_retrieval_queries(
    intent: IntentResult,
    chart: NormalizedChart | None,
    rule_result: RuleEngineResult | None,
    original_message: str,
    significators=None,  # SignificatorResult | None
) -> list[dict]:
    queries = [{"text": original_message, "metadata_filter": {}, "weight": 0.8, "label": "direct"}]
    topics = intent.entities.topics or intent.retrieval_topics

    # --- Significator-driven queries (preferred over intent-only) ---
    if significators is not None:
        topic = significators.topic
        primary_houses = significators.primary_houses
        karakas = significators.karaka_planets

        # Query per house lord placement
        for factor in significators.factors[:4]:
            queries.append({
                "text": f"{factor.planet} in house {factor.placed_house} {factor.sign} {topic}",
                "metadata_filter": _filter(
                    [factor.placed_house],
                    [factor.planet],
                    [topic],
                ),
                "weight": 1.0,
                "label": f"factor_{factor.planet}_{factor.placed_house}",
            })

        # Topic house signification query
        if primary_houses:
            queries.append({
                "text": f"{topic} {' '.join(f'house {h}' for h in primary_houses[:3])} {' '.join(karakas[:3])}",
                "metadata_filter": _filter(primary_houses[:4], karakas[:4], [topic]),
                "weight": 1.0,
                "label": "topic_chart",
            })

        # Yoga queries
        for yoga in significators.relevant_yogas[:2]:
            queries.append({
                "text": f"{yoga} yoga meaning effects {topic}",
                "metadata_filter": {"$or": [{"chunk_type": "yoga"}, {"yoga_name": yoga}]},
                "weight": 1.0,
                "label": f"yoga_{yoga.replace(' ', '_')}",
            })

        # Dasha query
        d = significators.dasha_activation
        if d.maha_is_significator or d.antar_is_significator:
            queries.append({
                "text": f"{d.maha_lord} mahadasha {d.antar_lord} antardasha {topic} effects",
                "metadata_filter": {
                    "$or": [
                        {"chunk_type": "dasha_antardasha"},
                        {"chunk_type": "dasha_mahadasha"},
                        {"chunk_type": "dasha"},
                        {"planets_primary": {"$in": [d.maha_lord, d.antar_lord]}},
                    ]
                },
                "weight": 0.9,
                "label": "dasha",
            })

    else:
        # Fallback: intent-only queries (when no chart available)
        if chart and topics:
            topic = topics[0]
            houses = TOPIC_HOUSE_MAP.get(topic, [])
            planets = set(TOPIC_PLANET_MAP.get(topic, []))
            if chart:
                planets.update(h.lord for n, h in chart.houses.items() if n in houses)
                planets.update(p for p, pos in chart.planets.items() if pos.house in houses)
                if chart.dasha:
                    planets.add(chart.dasha.maha_dasha_lord)
            planet_list = [p for p in planets if p][:6]
            queries.append({
                "text": f"{topic} {' '.join(f'house {h}' for h in houses[:3])} {' '.join(planet_list[:3])}",
                "metadata_filter": _filter(houses, planet_list, [topic]),
                "weight": 1.0,
                "label": "topic_chart",
            })

        if chart and intent.requires_dasha and chart.dasha:
            maha = chart.dasha.maha_dasha_lord
            antar = chart.dasha.antar_dasha_lord
            queries.append({
                "text": f"{maha} mahadasha {antar} antardasha effects",
                "metadata_filter": {
                    "$or": [{"chunk_type": "dasha"}, {"planets_primary": {"$in": [maha, antar]}}]
                },
                "weight": 0.9,
                "label": "dasha",
            })

        if rule_result:
            for yoga in rule_result.yogas_present[:3]:
                queries.append({
                    "text": f"{yoga} yoga meaning effects",
                    "metadata_filter": {"$or": [{"chunk_type": "yoga"}, {"yoga_name": yoga}]},
                    "weight": 1.0,
                    "label": f"yoga_{yoga.replace(' ', '_')}",
                })

    return queries[:6]
