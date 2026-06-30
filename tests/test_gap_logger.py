"""Test the gap logger records ungrounded factors with the right keys."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.gap_logger import log_gaps
from services.reasoning_assembler import DashaLine, ReasoningReport, ReportLine
from services.significator_engine import (
    DashaActivation, SignificatorFactor, SignificatorResult,
)


def _significators():
    factor = SignificatorFactor(
        role="aspects 11th house", planet="Jupiter", placed_house=3, sign="Gemini",
        dignity="enemy sign", functional_nature="benefic", dig_bala=False,
        aspects_topic_house=True, kind="supporting",
    )
    return SignificatorResult(
        topic="career", primary_houses=[10], karaka_planets=["Saturn"], relevant_varga="D10",
        factors=[factor], dasha_activation=DashaActivation(
            maha_lord="Ketu", antar_lord="Ketu", maha_end="", antar_end="",
            maha_is_significator=False, antar_is_significator=False,
            maha_functional_nature="neutral", antar_functional_nature="neutral",
            activation_strength="weak"),
        relevant_yogas=[], relevant_doshas=[], planets_in_topic_houses={},
        aspects_on_topic_houses={},
    )


def _report():
    ungrounded = ReportLine(statement="Jupiter (aspects 11th house)...", planet="Jupiter",
                            role="aspects 11th house", kind="supporting", grounded=False)
    return ReasoningReport(
        topic="career", supporting=[ungrounded],
        dasha=DashaLine(statement="Ketu/Ketu", maha_lord="Ketu", antar_lord="Ketu",
                        activation_strength="weak", grounded=False),
        yogas=[],
    )


@pytest.mark.asyncio
async def test_log_gaps_records_factor_and_dasha():
    coll = MagicMock()
    coll.update_one = AsyncMock()
    with patch("services.gap_logger.knowledge_gaps_collection", return_value=coll):
        await log_gaps(_report(), _significators(), "career")

    # One call for the ungrounded factor, one for the ungrounded dasha.
    assert coll.update_one.await_count == 2
    keys = {call.args[0]["_id"] for call in coll.update_one.await_args_list}
    assert "factor:Jupiter:h3:career" in keys
    assert "dasha:Ketu/Ketu:career" in keys


@pytest.mark.asyncio
async def test_log_gaps_skips_grounded():
    coll = MagicMock()
    coll.update_one = AsyncMock()
    report = _report()
    report.supporting[0].grounded = True          # now grounded
    report.dasha.grounded = True
    with patch("services.gap_logger.knowledge_gaps_collection", return_value=coll):
        await log_gaps(report, _significators(), "career")
    coll.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_log_gaps_never_raises():
    # A broken collection must not bubble up (best-effort logging).
    with patch("services.gap_logger.knowledge_gaps_collection", side_effect=RuntimeError):
        await log_gaps(_report(), _significators(), "career")   # should swallow
