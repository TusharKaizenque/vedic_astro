"""
Topic Pipeline (C1) — multi-topic orchestration.

A single question may touch more than one topic ("career and marriage"). This module
resolves all topics, then builds a full deterministic bundle per topic: significators →
retrieval → reasoning report → verdict → dasha timing → deeper structure. Retrieval
for each topic runs concurrently.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from models.chart import NormalizedChart
from models.intent import IntentResult
from services.assessment_engine import TopicAssessment, assess_topic
from services.dasha_analyzer import DashaLordAnalysis, analyze_dasha
from services.outcome_engine import LifeOutcome, derive_outcome
from services.reasoning_assembler import ReasoningReport, assemble
from services.retrieval import retrieval_service
from services.rule_engine.dispositor_engine import ChainAnalysis, analyze_house_chain
from services.rule_engine.engine import RuleEngineResult
from services.rule_engine.strength_engine import PlanetStrength
from services.significator_engine import (
    SignificatorResult, get_significators, resolve_topics,
)


@dataclass
class TopicBundle:
    topic: str
    significators: SignificatorResult
    report: ReasoningReport
    assessment: TopicAssessment
    dasha_analysis: list[DashaLordAnalysis]
    chain_analysis: ChainAnalysis | None
    outcome: LifeOutcome | None = None


async def analyze_topics(
    intent: IntentResult,
    chart: NormalizedChart,
    rules: RuleEngineResult,
    strengths: dict[str, PlanetStrength],
    message: str,
) -> list[TopicBundle]:
    topics = resolve_topics(intent)

    # Significators are deterministic + fast — compute all up front.
    sigs = {t: get_significators(intent, chart, rules, topic=t) for t in topics}

    # Retrieval is I/O-bound — run all topics concurrently.
    chunk_lists = await asyncio.gather(*(
        retrieval_service.retrieve(intent, sigs[t], chart, message, rules)
        for t in topics
    ))

    bundles: list[TopicBundle] = []
    for topic, chunks in zip(topics, chunk_lists):
        sig = sigs[topic]
        report = assemble(sig, chunks, rules)
        grounded = (
            report.grounded_count / report.total_factors
            if report.total_factors else 0.0
        )
        assessment = assess_topic(sig, strengths, rules, grounded, chart=chart)
        dasha = analyze_dasha(
            chart, rules, strengths, topic, sig.primary_houses, sig.karaka_planets
        )
        chain = analyze_house_chain(chart, sig.primary_houses[0]) if sig.primary_houses else None
        outcome = derive_outcome(topic, sig, assessment, strengths, chart, rules)
        bundles.append(TopicBundle(topic, sig, report, assessment, dasha, chain, outcome))
    return bundles
