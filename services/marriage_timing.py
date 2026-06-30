"""
Marriage Timing Engine — WHEN marriage is likely, from the dasha of marriage significators.

Classical method (BPHS Ch.18; B.V. Raman; K.N. Rao): marriage fructifies in the
mahadasha/antardasha of a MARRIAGE SIGNIFICATOR — the 7th lord, Venus (karaka), Jupiter,
the 2nd lord, the Darakaraka, the Upapada lord, the dispositor of the 7th lord, or any
planet in/aspecting the 7th. The antardasha (sub-period) is the actual trigger; the
mahadasha sets the stage. "Dasha decides WHETHER, transit decides the exact WHEN."

This engine reads Prokerala's own nested dasha tree (already stored on the chart — no new
API call, no local dasha math), flattens it to maha/antar windows, and scores each future
window by how many marriage significators rule it. The Jupiter–Saturn double transit is the
classical confirmation of the exact month; we flag it as the confirmation step rather than
computing future transits (which would cost API credits).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from models.chart import NormalizedChart
from services.rule_engine.engine import RuleEngineResult
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS
from utils.jaimini import darakaraka


@dataclass
class MarriageWindow:
    maha_lord: str
    antar_lord: str
    start: datetime
    end: datetime
    score: float
    activators: list[str] = field(default_factory=list)
    flavor: str = ""


def _idx(sign: str) -> int:
    return ZODIAC_SIGNS.index(sign) if sign in ZODIAC_SIGNS else 0


def _arudha_idx(house_idx: int, lord_idx: int) -> int:
    arudha = (2 * lord_idx - house_idx) % 12
    if arudha == house_idx or arudha == (house_idx + 6) % 12:
        arudha = (arudha + 9) % 12
    return arudha


def marriage_significators(chart: NormalizedChart, rules: RuleEngineResult) -> dict[str, str]:
    """planet → the reason it activates marriage (first/strongest reason wins)."""
    sig: dict[str, str] = {}
    lagna_idx = _idx(chart.lagna_sign)
    seventh = ZODIAC_SIGNS[(lagna_idx + 6) % 12]
    second = ZODIAC_SIGNS[(lagna_idx + 1) % 12]
    l7 = SIGN_RULERS.get(seventh, "")
    l2 = SIGN_RULERS.get(second, "")

    if l7:
        sig[l7] = "the 7th lord (lord of the marriage house)"
    if l2:
        sig.setdefault(l2, "the 2nd lord (family expansion)")
    sig.setdefault("Venus", "Venus, the natural karaka of marriage")
    sig.setdefault("Jupiter", "Jupiter (karaka of husband / general blessing on marriage)")
    dk = darakaraka(chart)
    if dk:
        sig.setdefault(dk, "the Darakaraka (Jaimini significator of the spouse)")
    # Dispositor of the 7th lord
    l7pos = chart.planets.get(l7)
    if l7pos:
        disp = SIGN_RULERS.get(l7pos.sign, "")
        if disp:
            sig.setdefault(disp, "the dispositor of the 7th lord")
    # Upapada Lagna lord
    tl = SIGN_RULERS.get(ZODIAC_SIGNS[(lagna_idx + 11) % 12], "")
    tlpos = chart.planets.get(tl)
    if tlpos:
        ul_idx = _arudha_idx((lagna_idx + 11) % 12, _idx(tlpos.sign))
        ul_lord = SIGN_RULERS.get(ZODIAC_SIGNS[ul_idx], "")
        if ul_lord:
            sig.setdefault(ul_lord, "the Upapada Lagna lord (marriage as an institution)")
    # Planets in / aspecting the 7th
    for n, p in chart.planets.items():
        if p.house == 7:
            sig.setdefault(n, "a planet occupying the 7th house")
    for p in rules.planets_aspecting_house.get(7, []):
        sig.setdefault(p, "a planet aspecting the 7th house")
    return sig


def _flavor(maha_lord: str, antar_lord: str, l7: str) -> str:
    lords = {maha_lord, antar_lord}
    notes = []
    if "Venus" in lords or l7 in lords:
        notes.append("a timely, favourable opening for marriage")
    if "Jupiter" in lords:
        notes.append("Jupiter blesses the period, classically auspicious for marriage")
    if "Saturn" in lords:
        notes.append("Saturn can delay the timing but tends to make the union mature and lasting")
    if "Rahu" in lords:
        notes.append("Rahu can bring a sudden, unconventional, or cross-cultural match")
    if "Ketu" in lords:
        notes.append("Ketu can make the timing karmic or detached")
    return "; ".join(notes)


def _parse(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _windows(chart: NormalizedChart):
    raw = chart.raw_prokerala_response or {}
    data = raw.get("data", raw)
    for md in data.get("dasha_periods", []) or []:
        md_lord = str(md.get("name", ""))
        for ad in md.get("antardasha", []) or []:
            yield md_lord, str(ad.get("name", "")), _parse(ad.get("start", "")), _parse(ad.get("end", ""))


def build_marriage_timing(
    chart: NormalizedChart, rules: RuleEngineResult, now: datetime, horizon_years: int = 22
) -> list[MarriageWindow]:
    """Future maha/antar windows ruled by a marriage significator, strongest-supported first.
    The antardasha lord is weighted higher than the mahadasha lord (it is the actual trigger)."""
    sig = marriage_significators(chart, rules)
    lagna_idx = _idx(chart.lagna_sign)
    l7 = SIGN_RULERS.get(ZODIAC_SIGNS[(lagna_idx + 6) % 12], "")
    horizon = now.replace(year=now.year + horizon_years)
    out: list[MarriageWindow] = []
    for md_lord, ad_lord, start, end in _windows(chart):
        if not end or end < now or (start and start > horizon):
            continue
        score, acts = 0.0, []
        if ad_lord in sig:
            score += 2.0
            acts.append(f"{ad_lord} antardasha — {sig[ad_lord]}")
        if md_lord in sig:
            score += 1.0
            acts.append(f"{md_lord} mahadasha — {sig[md_lord]}")
        if score <= 0:
            continue
        out.append(MarriageWindow(md_lord, ad_lord, start, end, score,
                                  acts, _flavor(md_lord, ad_lord, l7)))
    out.sort(key=lambda w: w.start or now)   # chronological
    return out


def format_marriage_timing_for_prompt(windows: list[MarriageWindow], now: datetime) -> str:
    if not windows:
        return ""
    # The leading candidate: earliest window with a strong score (antar lord is a significator).
    strong = [w for w in windows if w.score >= 2.0]
    ordered = (strong or windows)[:4]
    lines = [
        "[MARRIAGE TIMING — derived from the dasha of marriage significators (deterministic; "
        "the antardasha sub-period is the trigger). Present the EARLIEST strongly-activated "
        "window as the most likely period, give the date range, and explain WHY (the named "
        "significators). Frame it as a window of months, not an exact date. Add that the exact "
        "month is classically confirmed when Jupiter and Saturn both transit/aspect the 7th "
        "house or 7th lord during the window.]",
    ]
    for w in ordered:
        sd = w.start.strftime("%b %Y") if w.start else "—"
        ed = w.end.strftime("%b %Y") if w.end else "—"
        tag = "STRONG" if w.score >= 3 else "likely" if w.score >= 2 else "supporting"
        lines.append(
            f"- {sd} – {ed} ({w.maha_lord} MD / {w.antar_lord} AD) [{tag}]: "
            + "; ".join(w.activators) + (f". {w.flavor}." if w.flavor else ".")
        )
    return "\n".join(lines)
