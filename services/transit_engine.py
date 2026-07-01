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
from services.rule_engine.ashtakavarga_engine import compute_bav
from utils.astro_constants import NATURAL_BENEFICS, SANSKRIT_TO_ENGLISH, ZODIAC_SIGNS

logger = logging.getLogger(__name__)

SLOW_PLANETS = ["Saturn", "Jupiter", "Rahu", "Ketu"]
# Classical favourable transit houses counted from the natal Moon.
_JUPITER_GOOD_FROM_MOON = {2, 5, 7, 9, 11}
_SATURN_GOOD_FROM_MOON = {3, 6, 11}
# Sign-offsets a planet transits-or-aspects (0 = conjunction). Jupiter's special aspects are the
# 5th/7th/9th; Saturn's are the 3rd/7th/10th (BPHS graha-drishti).
_JUP_ASPECT_OFFSETS = {0, 4, 6, 8}
_SAT_ASPECT_OFFSETS = {0, 2, 6, 9}
# Ashtakavarga transit rule of thumb: a planet transiting a sign where it holds >=4 of its own
# bindus gives results; fewer signals obstruction.
_AV_GOOD_BINDU = 4


@dataclass
class TransitReport:
    target_label: str
    sade_sati: bool = False
    sade_sati_phase: str = ""
    double_transit: bool = False
    notes: list[str] = field(default_factory=list)
    favourable: int = 0
    unfavourable: int = 0


def _sign_index(sign: str) -> int | None:
    return ZODIAC_SIGNS.index(sign) if sign in ZODIAC_SIGNS else None


def _house_from(reference_sign_idx: int, planet_sign_idx: int) -> int:
    return ((planet_sign_idx - reference_sign_idx) % 12) + 1


def _ord(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _hits(planet_idx: int, target_idx: int, offsets: set[int]) -> bool:
    """Whether a planet in `planet_idx` transits or aspects the sign `target_idx`."""
    return ((target_idx - planet_idx) % 12) in offsets


def _bindu_note(bav: dict, planet: str, sign_idx: int) -> str:
    """A short Ashtakavarga strength clause for a planet transiting a sign."""
    n = bav.get(planet, [0] * 12)[sign_idx] if 0 <= sign_idx < 12 else 0
    kind = "well-supported" if n >= _AV_GOOD_BINDU else "obstructed"
    return f" (Ashtakavarga: {n}/8 bindus here — {kind})"


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
    bav = compute_bav(natal_chart)   # personalised Ashtakavarga bindus per planet per sign

    # --- Saturn: Sade Sati + gochara from Moon (+ Ashtakavarga strength) ---
    sat_sign = transit_positions.get("Saturn")
    sat_idx = _sign_index(sat_sign) if sat_sign else None
    if moon_idx is not None and sat_idx is not None:
        h = _house_from(moon_idx, sat_idx)
        av = _bindu_note(bav, "Saturn", sat_idx)
        if h in (12, 1, 2):
            report.sade_sati = True
            report.sade_sati_phase = {12: "rising (first phase)", 1: "peak (second phase)",
                                      2: "setting (third phase)"}[h]
            report.unfavourable += 1
            report.notes.append(
                f"Saturn transits the {_ord(h)} from your natal Moon — Sade Sati is active, "
                f"{report.sade_sati_phase}: a demanding, maturing period.{av}"
            )
        elif h in _SATURN_GOOD_FROM_MOON:
            report.favourable += 1
            report.notes.append(f"Saturn transits the {_ord(h)} from your natal Moon — a classically supportive Saturn gochara.{av}")
        elif h in (4, 8):
            report.unfavourable += 1
            kind = "Ashtama Shani (8th)" if h == 8 else "Ardhashtama Shani (4th)"
            report.notes.append(f"Saturn transits the {_ord(h)} from your natal Moon — {kind}, a period calling for care.{av}")

    # --- Jupiter: gochara from Moon (+ Ashtakavarga strength) ---
    jup_sign = transit_positions.get("Jupiter")
    jup_idx = _sign_index(jup_sign) if jup_sign else None
    if moon_idx is not None and jup_idx is not None:
        h = _house_from(moon_idx, jup_idx)
        av = _bindu_note(bav, "Jupiter", jup_idx)
        if h in _JUPITER_GOOD_FROM_MOON:
            report.favourable += 1
            report.notes.append(f"Jupiter transits the {_ord(h)} from your natal Moon — a favourable, expansive Jupiter gochara.{av}")
        else:
            report.notes.append(f"Jupiter transits the {_ord(h)} from your natal Moon — a quieter Jupiter gochara.{av}")

    # --- DOUBLE TRANSIT — the strongest classical confirmation: Jupiter AND Saturn both
    # transiting or aspecting the topic's primary house at the same time. ---
    if lagna_idx is not None and topic_houses and jup_idx is not None and sat_idx is not None:
        target_idx = (lagna_idx + topic_houses[0] - 1) % 12
        if _hits(jup_idx, target_idx, _JUP_ASPECT_OFFSETS) and _hits(sat_idx, target_idx, _SAT_ASPECT_OFFSETS):
            report.double_transit = True
            report.favourable += 2
            report.notes.append(
                f"DOUBLE TRANSIT: both Jupiter and Saturn currently transit or aspect your "
                f"{topic_houses[0]}th house — the classical 'double confirmation' that strongly "
                f"activates this area of life in this window."
            )

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
                    report.notes.append(f"{planet} transits your {_ord(primary)} house — a benefic transit over the topic's primary house.")
                else:
                    report.unfavourable += 1
                    report.notes.append(f"{planet} transits your {_ord(primary)} house — a testing transit over the topic's primary house.")

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
