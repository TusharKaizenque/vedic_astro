"""
Career Timing Engine — WHEN career events fructify, from the dasha of karma significators.

Orthogonal to the career VERDICT (which judges "how strong/favourable"): this answers a
different question — the periods of career change, rise, recognition or a new role — so it
confirms and extends rather than re-judging. Classical significators of karma timing: the
10th lord, the Jaimini Amatyakaraka (career co-significator), Sun (authority/rajya) and
Saturn (karma) as karakas, the 6th lord (service/employment), the 11th lord (gains/
promotion), the dispositor of the 10th lord, the 10th lord from the Moon, and planets in/
aspecting the 10th. The antardasha is the trigger.

Reads Prokerala's OWN stored dasha tree (no API call, no local dasha math).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from models.chart import NormalizedChart
from services.rule_engine.engine import RuleEngineResult
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS
from utils.jaimini import amatyakaraka


@dataclass
class CareerWindow:
    maha_lord: str
    antar_lord: str
    start: datetime
    end: datetime
    score: float
    activators: list[str] = field(default_factory=list)
    flavor: str = ""


def _ord(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def career_significators(chart: NormalizedChart, rules: RuleEngineResult) -> dict[str, str]:
    sig: dict[str, str] = {}
    lagna_idx = ZODIAC_SIGNS.index(chart.lagna_sign) if chart.lagna_sign in ZODIAC_SIGNS else 0

    def lord(h: int) -> str:
        return SIGN_RULERS.get(ZODIAC_SIGNS[(lagna_idx + h - 1) % 12], "")

    l10, l6, l11 = lord(10), lord(6), lord(11)
    if l10:
        sig[l10] = "the 10th lord (career & karma)"
    sig.setdefault("Sun", "Sun, the karaka of authority & status")
    sig.setdefault("Saturn", "Saturn, the karaka of karma & sustained work")
    amk = amatyakaraka(chart)
    if amk:
        sig.setdefault(amk, "the Amatyakaraka (Jaimini significator of career)")
    if l11:
        sig.setdefault(l11, "the 11th lord (gains & promotion)")
    if l6:
        sig.setdefault(l6, "the 6th lord (service & employment)")
    # Dispositor of the 10th lord.
    p10 = chart.planets.get(l10)
    if p10:
        disp = SIGN_RULERS.get(p10.sign, "")
        if disp:
            sig.setdefault(disp, "the dispositor of the 10th lord")
    # 10th lord from the Moon.
    moon = chart.planets.get("Moon")
    if moon and moon.sign in ZODIAC_SIGNS:
        midx = ZODIAC_SIGNS.index(moon.sign)
        l10m = SIGN_RULERS.get(ZODIAC_SIGNS[(midx + 9) % 12], "")
        if l10m:
            sig.setdefault(l10m, "the 10th lord from the Moon")
    # Planets in / aspecting the 10th.
    for n, p in chart.planets.items():
        if p.house == 10:
            sig.setdefault(n, "a planet in the 10th house of career")
    for p in rules.planets_aspecting_house.get(10, []):
        sig.setdefault(p, "a planet aspecting the 10th house of career")
    return sig


def _flavor(maha_lord: str, antar_lord: str) -> str:
    lords = {maha_lord, antar_lord}
    notes = []
    if "Jupiter" in lords:
        notes.append("growth, promotion or recognition")
    if "Saturn" in lords:
        notes.append("a step up earned through hard work, or a restructuring")
    if "Rahu" in lords:
        notes.append("a sudden change, foreign opportunity or unconventional move")
    if "Sun" in lords:
        notes.append("authority, status or a leadership/government role")
    if "Mercury" in lords:
        notes.append("business, commerce or communication-based work")
    if "Mars" in lords:
        notes.append("a bold move, competition or a technical/leadership push")
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


def build_career_timing(
    chart: NormalizedChart, rules: RuleEngineResult, now: datetime, horizon_years: int = 22
) -> list[CareerWindow]:
    sig = career_significators(chart, rules)
    horizon = now.replace(year=now.year + horizon_years)
    out: list[CareerWindow] = []
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
        out.append(CareerWindow(md_lord, ad_lord, start, end, score, acts, _flavor(md_lord, ad_lord)))
    out.sort(key=lambda w: w.start or now)
    return out


def format_career_timing_for_prompt(windows: list[CareerWindow], now: datetime) -> str:
    if not windows:
        return ""
    strong = [w for w in windows if w.score >= 2.0]
    ordered = (strong or windows)[:4]
    lines = [
        "[CAREER TIMING — the dasha periods that activate career change/rise (deterministic; the "
        "antardasha sub-period is the trigger). This is ADDITIONAL to the career verdict, not a "
        "re-judging of it. Present the strongest upcoming window(s) with date ranges and WHY (the "
        "named karma significators), as windows of months/years.]",
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
