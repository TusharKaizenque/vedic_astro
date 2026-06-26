"""
Transit (Gochara) Engine — D2 of Phase D.

Answers "what about <future time>?" questions. Transit positions are fetched from
Prokerala's own planet-position endpoint for the target date, so the ayanamsa (Lahiri)
stays identical to the natal chart — no ephemeris dependency, no ayanamsa mismatch.

The gochara interpretation is a pure function (testable without the network):
  - Sade Sati: Saturn transiting 12th / 1st / 2nd from natal Moon.
  - Saturn / Jupiter gochara from the natal Moon (classical favourable houses).
  - Slow-planet (Saturn, Jupiter, Rahu, Ketu) transit over the topic's primary house.
  - Slow-planet transit conjoining the active dasha lord's natal sign (activation).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from models.chart import NormalizedChart
from utils.astro_constants import NATURAL_BENEFICS, SANSKRIT_TO_ENGLISH, ZODIAC_SIGNS

logger = logging.getLogger(__name__)

SLOW_PLANETS = ["Saturn", "Jupiter", "Rahu", "Ketu"]
# Classical favourable transit houses counted from the natal Moon.
_JUPITER_GOOD_FROM_MOON = {2, 5, 7, 9, 11}
_SATURN_GOOD_FROM_MOON = {3, 6, 11}


@dataclass
class TransitReport:
    target_label: str
    sade_sati: bool = False
    sade_sati_phase: str = ""
    notes: list[str] = field(default_factory=list)
    favourable: int = 0
    unfavourable: int = 0


def _sign_index(sign: str) -> int | None:
    return ZODIAC_SIGNS.index(sign) if sign in ZODIAC_SIGNS else None


def _house_from(reference_sign_idx: int, planet_sign_idx: int) -> int:
    return ((planet_sign_idx - reference_sign_idx) % 12) + 1


def resolve_transit_date(time_references: list[str], now: datetime) -> datetime:
    """Best-effort resolution of a free-form time reference to a concrete date.

    Handles an explicit 4-digit year, "next year", "this year". Falls back to `now`.
    A year resolves to its mid-point (Jul 1) as a representative transit date."""
    blob = " ".join(time_references).lower()
    year_match = re.search(r"\b(20\d{2})\b", blob)
    if year_match:
        return datetime(int(year_match.group(1)), 7, 1, tzinfo=timezone.utc)
    if "next year" in blob:
        return datetime(now.year + 1, 7, 1, tzinfo=timezone.utc)
    if "this year" in blob:
        return datetime(now.year, 7, 1, tzinfo=timezone.utc)
    return now


def parse_transit_positions(prokerala_data: dict) -> dict[str, str]:
    """Extract {planet: english_sign} from a Prokerala planet-position response."""
    data = prokerala_data.get("data", prokerala_data)
    source = data.get("planets", data.get("planet_position", []))
    if isinstance(source, dict):
        source = list(source.values())
    positions: dict[str, str] = {}
    for item in source or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).title()
        rasi = item.get("rasi", item.get("sign", {}))
        sign = rasi.get("name", "") if isinstance(rasi, dict) else str(rasi)
        sign = SANSKRIT_TO_ENGLISH.get(sign, sign)
        if name and sign in ZODIAC_SIGNS:
            positions[name] = sign
    return positions


def gochara_report(
    natal_chart: NormalizedChart,
    transit_positions: dict[str, str],
    target_label: str,
    topic_houses: list[int] | None = None,
    dasha_lords: list[str] | None = None,
) -> TransitReport:
    """Pure gochara interpretation. `transit_positions` maps planet → current sign."""
    report = TransitReport(target_label=target_label)
    moon_idx = _sign_index(natal_chart.moon_sign)
    lagna_idx = _sign_index(natal_chart.lagna_sign)
    topic_houses = topic_houses or []
    dasha_lords = [d for d in (dasha_lords or []) if d]

    # --- Saturn: Sade Sati + gochara from Moon ---
    sat_sign = transit_positions.get("Saturn")
    sat_idx = _sign_index(sat_sign) if sat_sign else None
    if moon_idx is not None and sat_idx is not None:
        h = _house_from(moon_idx, sat_idx)
        if h in (12, 1, 2):
            report.sade_sati = True
            report.sade_sati_phase = {12: "rising (first phase)", 1: "peak (second phase)",
                                      2: "setting (third phase)"}[h]
            report.unfavourable += 1
            report.notes.append(
                f"Saturn transits the {h}th from your natal Moon — Sade Sati is active, "
                f"{report.sade_sati_phase}: a demanding, maturing period."
            )
        elif h in _SATURN_GOOD_FROM_MOON:
            report.favourable += 1
            report.notes.append(f"Saturn transits the {h}th from your natal Moon — a classically supportive Saturn gochara.")
        elif h in (4, 8):
            report.unfavourable += 1
            kind = "Ashtama Shani (8th)" if h == 8 else "Ardhashtama Shani (4th)"
            report.notes.append(f"Saturn transits the {h}th from your natal Moon — {kind}, a period calling for care.")

    # --- Jupiter: gochara from Moon ---
    jup_sign = transit_positions.get("Jupiter")
    jup_idx = _sign_index(jup_sign) if jup_sign else None
    if moon_idx is not None and jup_idx is not None:
        h = _house_from(moon_idx, jup_idx)
        if h in _JUPITER_GOOD_FROM_MOON:
            report.favourable += 1
            report.notes.append(f"Jupiter transits the {h}th from your natal Moon — a favourable, expansive Jupiter gochara.")
        else:
            report.notes.append(f"Jupiter transits the {h}th from your natal Moon — a quieter Jupiter gochara.")

    # --- Slow planets over the topic's primary house (from lagna) ---
    if lagna_idx is not None and topic_houses:
        primary = topic_houses[0]
        for planet in SLOW_PLANETS:
            sign = transit_positions.get(planet)
            idx = _sign_index(sign) if sign else None
            if idx is None:
                continue
            if _house_from(lagna_idx, idx) == primary:
                benefic = planet in NATURAL_BENEFICS
                if benefic:
                    report.favourable += 1
                    report.notes.append(f"{planet} transits your {primary}th house — a benefic transit over the topic's primary house.")
                else:
                    report.unfavourable += 1
                    report.notes.append(f"{planet} transits your {primary}th house — a testing transit over the topic's primary house.")

    # --- Slow planet conjoining the active dasha lord's natal sign (activation) ---
    for lord in dasha_lords:
        natal = natal_chart.planets.get(lord)
        if not natal:
            continue
        natal_sign = natal.sign
        for planet in ("Saturn", "Jupiter"):
            if transit_positions.get(planet) == natal_sign:
                report.notes.append(
                    f"{planet} transits over your natal {lord} (the active dasha lord) — "
                    f"this activates {lord}'s results during this window."
                )
    return report


def format_transit_for_prompt(report: TransitReport) -> str:
    if not report.notes:
        return ""
    lines = [f"[TRANSIT — gochara for {report.target_label}]"]
    lines.extend(f"  - {n}" for n in report.notes)
    net = report.favourable - report.unfavourable
    tone = "net supportive" if net > 0 else "net testing" if net < 0 else "mixed"
    lines.append(f"  Overall transit tone: {tone}.")
    return "\n".join(lines)
