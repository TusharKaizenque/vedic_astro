"""
Children / Progeny Timing Engine — WHEN childbirth is supported, from the dasha of the
significators of the 5th house (Putra Bhava).

Orthogonal to any "how is the 5th house" verdict: this answers the timing question — the
periods when progeny is classically supported. Significators of putra timing (BPHS/Phaladeepika):
the 5th lord, Jupiter (the karaka of children), the Jaimini Putrakaraka, the 9th lord (the
5th-from-5th, secondary progeny house), the dispositor of the 5th lord, the 5th lord from the
Moon, and planets in / aspecting the 5th. The antardasha is the trigger. Jupiter's transit and
the D7 (Saptamsa) are the classical confirmations, applied elsewhere.

Reads Prokerala's OWN stored dasha tree (no API call, no local dasha math).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from models.chart import NormalizedChart
from services.rule_engine.engine import RuleEngineResult
from services.rule_engine.varga_engine import varga_dignity
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS
from utils.jaimini import putrakaraka

_STRONG_VARGA = {"exalted", "moolatrikona", "own sign", "friendly sign"}
_WEAK_VARGA = {"debilitated", "enemy sign"}


@dataclass
class ChildWindow:
    maha_lord: str
    antar_lord: str
    start: datetime
    end: datetime
    score: float
    activators: list[str] = field(default_factory=list)
    flavor: str = ""


def children_significators(chart: NormalizedChart, rules: RuleEngineResult) -> dict[str, str]:
    sig: dict[str, str] = {}
    lagna_idx = ZODIAC_SIGNS.index(chart.lagna_sign) if chart.lagna_sign in ZODIAC_SIGNS else 0

    def lord(h: int) -> str:
        return SIGN_RULERS.get(ZODIAC_SIGNS[(lagna_idx + h - 1) % 12], "")

    l5, l9 = lord(5), lord(9)
    if l5:
        sig[l5] = "the 5th lord (children & progeny)"
    sig.setdefault("Jupiter", "Jupiter, the karaka of children")
    pk = putrakaraka(chart)
    if pk:
        sig.setdefault(pk, "the Putrakaraka (Jaimini significator of children)")
    if l9:
        sig.setdefault(l9, "the 9th lord (the 5th-from-5th, secondary progeny house)")
    # Dispositor of the 5th lord.
    p5 = chart.planets.get(l5)
    if p5:
        disp = SIGN_RULERS.get(p5.sign, "")
        if disp:
            sig.setdefault(disp, "the dispositor of the 5th lord")
    # 5th lord from the Moon.
    moon = chart.planets.get("Moon")
    if moon and moon.sign in ZODIAC_SIGNS:
        midx = ZODIAC_SIGNS.index(moon.sign)
        l5m = SIGN_RULERS.get(ZODIAC_SIGNS[(midx + 4) % 12], "")
        if l5m:
            sig.setdefault(l5m, "the 5th lord from the Moon")
    # Planets in / aspecting the 5th.
    for n, p in chart.planets.items():
        if p.house == 5:
            sig.setdefault(n, "a planet in the 5th house of children")
    for p in rules.planets_aspecting_house.get(5, []):
        sig.setdefault(p, "a planet aspecting the 5th house of children")
    return sig


def _flavor(maha_lord: str, antar_lord: str) -> str:
    lords = {maha_lord, antar_lord}
    notes = []
    if "Jupiter" in lords:
        notes.append("the classical window for progeny — Jupiter blessing the 5th")
    if "Moon" in lords or "Venus" in lords:
        notes.append("fertility and family growth favoured")
    if "Saturn" in lords:
        notes.append("possible after some delay or effort")
    if "Rahu" in lords or "Ketu" in lords:
        notes.append("an unconventional route (e.g. treatment, adoption) may feature")
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


def build_children_timing(
    chart: NormalizedChart, rules: RuleEngineResult, now: datetime, horizon_years: int = 20
) -> list[ChildWindow]:
    sig = children_significators(chart, rules)
    horizon = now.replace(year=now.year + horizon_years)
    out: list[ChildWindow] = []
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
        out.append(ChildWindow(md_lord, ad_lord, start, end, score, acts, _flavor(md_lord, ad_lord)))
    out.sort(key=lambda w: w.start or now)
    return out


def saptamsa_confirmation(chart: NormalizedChart) -> str:
    """Confirm the progeny promise in the D7 Saptamsa (the varga of children): a promise strong
    in D1 but weak in D7 does not deliver cleanly. Weigh the 5th lord, Jupiter and Putrakaraka."""
    lagna_idx = ZODIAC_SIGNS.index(chart.lagna_sign) if chart.lagna_sign in ZODIAC_SIGNS else 0
    l5 = SIGN_RULERS.get(ZODIAC_SIGNS[(lagna_idx + 4) % 12], "")
    key = [p for p in (l5, "Jupiter", putrakaraka(chart)) if p]
    strong = weak = 0
    for p in set(key):
        pos = chart.planets.get(p)
        if not pos:
            continue
        dig = varga_dignity(p, pos.longitude, "D7")
        strong += dig in _STRONG_VARGA
        weak += dig in _WEAK_VARGA
    if strong > weak and strong:
        return ("D7 Saptamsa CONFIRMS the promise of children (its key significators hold "
                "dignity in the progeny varga).")
    if weak > strong and weak:
        return ("D7 Saptamsa is WEAK (key progeny significators lose dignity there) — children "
                "may come with delay or difficulty despite the dasha window.")
    return "D7 Saptamsa is mixed on progeny — neither a clear confirmation nor a denial."


def format_children_timing_for_prompt(
    windows: list[ChildWindow], now: datetime, chart: NormalizedChart | None = None
) -> str:
    if not windows:
        return ""
    strong = [w for w in windows if w.score >= 2.0]
    ordered = (strong or windows)[:4]
    lines = [
        "[CHILDREN TIMING — the dasha periods that support progeny (deterministic; the antardasha "
        "sub-period is the trigger). ADDITIONAL to the 5th-house reading, not a re-judging of it. "
        "Present the strongest upcoming window(s) with date ranges and WHY (the named putra "
        "significators), as windows of months/years, and note it is confirmed classically when "
        "Jupiter transits/aspects the 5th and the D7 Saptamsa is supportive.]",
    ]
    for w in ordered:
        sd = w.start.strftime("%b %Y") if w.start else "—"
        ed = w.end.strftime("%b %Y") if w.end else "—"
        tag = "STRONG" if w.score >= 3 else "likely" if w.score >= 2 else "supporting"
        lines.append(
            f"- {sd} – {ed} ({w.maha_lord} MD / {w.antar_lord} AD) [{tag}]: "
            + "; ".join(w.activators) + (f". {w.flavor}." if w.flavor else ".")
        )
    if chart is not None:
        lines.append(f"  {saptamsa_confirmation(chart)}")
    return "\n".join(lines)
