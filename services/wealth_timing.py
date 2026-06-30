"""
Wealth Timing Engine — WHEN wealth flows, from the dasha of wealth significators.

Orthogonal to the wealth VERDICT (which already judges "how wealthy"): this answers a
different question — the periods when finances expand — so it confirms and extends rather
than re-litigating strength. Classical method: wealth fructifies in the maha/antar of a
Dhana significator — the 2nd lord (savings), 11th lord (gains), 9th lord (fortune), 5th lord
(speculation/purva-punya), Jupiter & Venus (karakas), the dispositors of the 2nd/11th lords,
and planets in/aspecting the 2nd & 11th. The antardasha is the trigger.

Reads Prokerala's OWN stored dasha tree (no API call, no local dasha math).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from models.chart import NormalizedChart
from services.rule_engine.engine import RuleEngineResult
from utils.astro_constants import SIGN_RULERS, ZODIAC_SIGNS


@dataclass
class WealthWindow:
    maha_lord: str
    antar_lord: str
    start: datetime
    end: datetime
    score: float
    activators: list[str] = field(default_factory=list)
    flavor: str = ""


def _ord(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def wealth_significators(chart: NormalizedChart, rules: RuleEngineResult) -> dict[str, str]:
    sig: dict[str, str] = {}
    lagna_idx = ZODIAC_SIGNS.index(chart.lagna_sign) if chart.lagna_sign in ZODIAC_SIGNS else 0

    def lord(h: int) -> str:
        return SIGN_RULERS.get(ZODIAC_SIGNS[(lagna_idx + h - 1) % 12], "")

    l2, l11, l9, l5 = lord(2), lord(11), lord(9), lord(5)
    if l2:
        sig[l2] = "the 2nd lord (accumulated wealth & savings)"
    if l11:
        sig.setdefault(l11, "the 11th lord (gains & income)")
    if l9:
        sig.setdefault(l9, "the 9th lord (fortune & luck)")
    if l5:
        sig.setdefault(l5, "the 5th lord (speculation & past-life merit)")
    sig.setdefault("Jupiter", "Jupiter, the karaka of wealth & expansion")
    sig.setdefault("Venus", "Venus (affluence & luxury)")
    # Dispositors of the 2nd & 11th lords.
    for ll, label in ((l2, "2nd"), (l11, "11th")):
        p = chart.planets.get(ll)
        if p:
            disp = SIGN_RULERS.get(p.sign, "")
            if disp:
                sig.setdefault(disp, f"the dispositor of the {label} lord")
    # Planets in / aspecting the 2nd & 11th.
    for n, p in chart.planets.items():
        if p.house in (2, 11):
            sig.setdefault(n, f"a planet in the {_ord(p.house)} house of wealth")
    for h in (2, 11):
        for p in rules.planets_aspecting_house.get(h, []):
            sig.setdefault(p, f"a planet aspecting the {_ord(h)} house of wealth")
    return sig


def _flavor(maha_lord: str, antar_lord: str) -> str:
    lords = {maha_lord, antar_lord}
    notes = []
    if "Jupiter" in lords or "Venus" in lords:
        notes.append("expansion and steady financial growth")
    if "Rahu" in lords:
        notes.append("sudden gains, speculation or unconventional income")
    if "Saturn" in lords:
        notes.append("wealth built slowly through sustained effort and long-term assets")
    if "Mercury" in lords:
        notes.append("gains through business, trade or communication")
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


def build_wealth_timing(
    chart: NormalizedChart, rules: RuleEngineResult, now: datetime, horizon_years: int = 22
) -> list[WealthWindow]:
    sig = wealth_significators(chart, rules)
    horizon = now.replace(year=now.year + horizon_years)
    out: list[WealthWindow] = []
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
        out.append(WealthWindow(md_lord, ad_lord, start, end, score, acts, _flavor(md_lord, ad_lord)))
    out.sort(key=lambda w: w.start or now)
    return out


def format_wealth_timing_for_prompt(windows: list[WealthWindow], now: datetime) -> str:
    if not windows:
        return ""
    strong = [w for w in windows if w.score >= 2.0]
    ordered = (strong or windows)[:4]
    lines = [
        "[WEALTH TIMING — the dasha periods when finances expand (deterministic; the antardasha "
        "sub-period is the trigger). This is ADDITIONAL to the wealth verdict, not a re-judging of "
        "it. Present the strongest upcoming window(s) with date ranges and WHY (the named Dhana "
        "significators), as windows of months/years.]",
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
