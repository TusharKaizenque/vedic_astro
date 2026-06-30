"""
Gap Logger — data-driven knowledge-base growth.

Every reading produces a ReasoningReport in which some factors are grounded in a classical
source and some are flagged "[NO CLASSICAL SOURCE LOADED]". This module records those
ungrounded factors (per planet/house/dasha/yoga/topic) with a running count, so the next
KB authoring effort targets exactly what users actually hit — not a guess.

Run `python scripts/show_gaps.py` to see the ranked list of what to author next.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from database.mongodb import knowledge_gaps_collection

logger = logging.getLogger(__name__)


def _factor_lookup(significators):
    return {(f.planet, f.role): f for f in significators.factors}


async def log_gaps(report, significators, topic: str) -> None:
    """Record every ungrounded factor/dasha/yoga from this report. Best-effort: never raises."""
    try:
        gaps: list[dict] = []
        by_key = _factor_lookup(significators)

        for line in (report.supporting + report.afflicting + report.neutral):
            if line.grounded:
                continue
            f = by_key.get((line.planet, line.role))
            house = f.placed_house if f else 0
            sign = f.sign if f else ""
            gaps.append({
                "_id": f"factor:{line.planet}:h{house}:{topic}",
                "type": "factor", "topic": topic, "planet": line.planet,
                "house": house, "sign": sign, "role": line.role,
                "description": f"{line.planet} in house {house} ({sign}) for '{topic}' "
                               f"— needs a planet-in-house or lord-in-house chunk",
            })

        if report.dasha and not report.dasha.grounded:
            d = report.dasha
            gaps.append({
                "_id": f"dasha:{d.maha_lord}/{d.antar_lord}:{topic}",
                "type": "dasha", "topic": topic, "maha": d.maha_lord, "antar": d.antar_lord,
                "description": f"{d.maha_lord}/{d.antar_lord} dasha for '{topic}' "
                               f"— needs a dasha chunk",
            })

        for y in report.yogas:
            if not y.grounded:
                gaps.append({
                    "_id": f"yoga:{y.yoga_name}",
                    "type": "yoga", "topic": topic, "yoga_name": y.yoga_name,
                    "description": f"{y.yoga_name} yoga — needs a yoga chunk",
                })

        if not gaps:
            return
        coll = knowledge_gaps_collection()
        now = datetime.now(timezone.utc)
        for gap in gaps:
            gap_id = gap.pop("_id")
            await coll.update_one(
                {"_id": gap_id},
                {"$inc": {"count": 1}, "$set": {**gap, "last_seen": now},
                 "$setOnInsert": {"first_seen": now}},
                upsert=True,
            )
    except Exception:
        logger.exception("Gap logging failed (non-fatal)")
