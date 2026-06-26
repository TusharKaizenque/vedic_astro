"""
Dasha Projection — forward-looking Vimshottari for future-dated questions.

The dasha analyzer reads the *current* maha/antar/pratyantar. But a question like
"should I start a startup in 2027?" is about a FUTURE period — by then the current
antardasha has ended. This module deterministically projects the Vimshottari sequence
to a target date (the same maha/antar math the classics define), so the engine can say
"in 2027 you will be in Ketu Mahadasha / Venus Antardasha" and analyze THAT period.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from utils.astro_constants import VIMSHOTTARI_ORDER, VIMSHOTTARI_YEARS

_YEAR_DAYS = 365.25
_TOTAL = 120.0


@dataclass
class DashaProjection:
    target: datetime
    maha_lord: str
    antar_lord: str
    pratyantar_lord: str
    antar_start: datetime
    antar_end: datetime
    is_future: bool          # True if the projected antar differs from the current one


def _sub_periods(parent_lord: str, parent_years: float) -> list[tuple[str, float]]:
    """The ordered sub-periods (antar within maha, or praty within antar)."""
    idx = VIMSHOTTARI_ORDER.index(parent_lord)
    order = VIMSHOTTARI_ORDER[idx:] + VIMSHOTTARI_ORDER[:idx]
    return [(lord, parent_years * VIMSHOTTARI_YEARS[lord] / _TOTAL) for lord in order]


def _parse_dt(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
        return dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def project_dasha(
    maha_lord: str,
    maha_start: str,
    target: datetime,
    current_antar: str = "",
) -> DashaProjection | None:
    """Project the maha/antar/pratyantar active at `target` from the current maha start.

    Returns None if inputs can't be parsed."""
    start = _parse_dt(maha_start)
    if not start or maha_lord not in VIMSHOTTARI_YEARS:
        return None
    tgt = target.replace(tzinfo=None)

    # Advance through maha dashas until target falls inside one.
    maha = maha_lord
    m_start = start
    for _ in range(len(VIMSHOTTARI_ORDER) + 1):
        m_end = m_start + timedelta(days=VIMSHOTTARI_YEARS[maha] * _YEAR_DAYS)
        if tgt < m_end:
            break
        m_start = m_end
        maha = VIMSHOTTARI_ORDER[(VIMSHOTTARI_ORDER.index(maha) + 1) % len(VIMSHOTTARI_ORDER)]

    # Find the antardasha within the maha.
    antar, a_start, a_years = maha, m_start, VIMSHOTTARI_YEARS[maha]
    cursor = m_start
    for lord, yrs in _sub_periods(maha, VIMSHOTTARI_YEARS[maha]):
        a_end = cursor + timedelta(days=yrs * _YEAR_DAYS)
        if tgt < a_end:
            antar, a_start, a_years = lord, cursor, yrs
            break
        cursor = a_end
    else:
        a_end = cursor

    # Find the pratyantardasha within the antardasha.
    praty = antar
    cursor = a_start
    for lord, yrs in _sub_periods(antar, a_years):
        p_end = cursor + timedelta(days=yrs * _YEAR_DAYS)
        if tgt < p_end:
            praty = lord
            break
        cursor = p_end

    return DashaProjection(
        target=tgt, maha_lord=maha, antar_lord=antar, pratyantar_lord=praty,
        antar_start=a_start, antar_end=a_start + timedelta(days=a_years * _YEAR_DAYS),
        is_future=(current_antar != "" and antar != current_antar) or maha != maha_lord,
    )
