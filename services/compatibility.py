"""
Compatibility Engine — Ashtakoot Guna Milan + Mangal Dosha + chart-level checks.

Per the classical sources and experienced practice, the 36-point Guna Milan total is a FIRST
FILTER, not the verdict. The distribution matters more than the sum: Nadi (8 pts, genetics/
progeny) and Bhakoot (7 pts, emotional/financial) are the heavy hitters and have classical
cancellation rules; Mangal (Kuja) Dosha is checked SEPARATELY for both charts (also with
cancellations). A 20 with clean Nadi/Bhakoot beats a 24 that lost them.

Deterministic; uses each person's Moon nakshatra + Moon sign (and Mars for Mangal). No API.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from services.rule_engine.dosha_detector import detect_mangal_dosha
from services.rule_engine.strength_calculator import get_planet_strength
from services.rule_engine.strength_engine import compute_all_strengths
from utils.astro_constants import (
    NATURAL_ENEMIES, NATURAL_FRIENDS, SIGN_RULERS, ZODIAC_SIGNS,
)
from utils.nakshatras import NAKSHATRAS, nakshatra_index

# ── Nakshatra attribute tables (index 0=Ashwini … 26=Revati) ─────────────────────────────
# Nadi: same Nadi → 0/8 (the most heavily weighted defect).
_NADI = [
    "aadi", "madhya", "antya", "antya", "madhya", "aadi", "aadi", "madhya", "antya",   # 0-8
    "antya", "madhya", "aadi", "aadi", "madhya", "antya", "antya", "madhya", "aadi",    # 9-17
    "aadi", "madhya", "antya", "antya", "madhya", "aadi", "aadi", "madhya", "antya",    # 18-26
]
# Gana: temperament — Deva / Manushya / Rakshasa.
_GANA = [
    "deva", "manushya", "rakshasa", "manushya", "deva", "manushya", "deva", "deva", "rakshasa",
    "rakshasa", "manushya", "manushya", "deva", "rakshasa", "deva", "rakshasa", "deva", "rakshasa",
    "rakshasa", "manushya", "manushya", "deva", "rakshasa", "rakshasa", "manushya", "manushya", "deva",
]
# Yoni: animal — same → 4, mortal enemy → 0, otherwise neutral (2). (Friend/enemy nuance simplified.)
_YONI = [
    "horse", "elephant", "sheep", "serpent", "serpent", "dog", "cat", "sheep", "cat",
    "rat", "rat", "cow", "buffalo", "tiger", "buffalo", "tiger", "deer", "deer",
    "dog", "monkey", "mongoose", "monkey", "lion", "horse", "lion", "cow", "elephant",
]
_YONI_MORTAL = {
    frozenset(("horse", "buffalo")), frozenset(("elephant", "lion")),
    frozenset(("sheep", "monkey")), frozenset(("serpent", "mongoose")),
    frozenset(("dog", "deer")), frozenset(("cat", "rat")), frozenset(("cow", "tiger")),
}

# ── Sign attribute tables ────────────────────────────────────────────────────────────────
# Varna by Moon-sign element: water=Brahmin(4) > fire=Kshatriya(3) > earth=Vaishya(2) > air=Shudra(1)
_VARNA_RANK = {
    "Cancer": 4, "Scorpio": 4, "Pisces": 4,
    "Aries": 3, "Leo": 3, "Sagittarius": 3,
    "Taurus": 2, "Virgo": 2, "Capricorn": 2,
    "Gemini": 1, "Libra": 1, "Aquarius": 1,
}
# Vashya group by Moon sign (whole-sign simplification).
_VASHYA = {
    "Aries": "quadruped", "Taurus": "quadruped", "Leo": "wild", "Sagittarius": "quadruped",
    "Capricorn": "quadruped", "Gemini": "human", "Virgo": "human", "Libra": "human",
    "Aquarius": "human", "Cancer": "water", "Pisces": "water", "Scorpio": "insect",
}


@dataclass
class KootaScore:
    name: str
    score: float
    maximum: float
    note: str = ""


@dataclass
class CompatibilityReport:
    total: float
    kootas: list[KootaScore] = field(default_factory=list)
    mangal_a: bool = False
    mangal_b: bool = False
    mangal_note: str = ""
    chart_level: str = ""          # the 7th-house/Venus reading — the "real verdict" layer
    verdict: str = ""
    cautions: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    max_total: int = 36


def _seventh_quality(chart: NormalizedChart):
    """How sound is THIS chart's own 7th house — the marriage foundation (independent of the
    other chart). Returns (7th_lord, afflicted?, venus_afflicted?)."""
    strengths = compute_all_strengths(chart)
    lagna_idx = ZODIAC_SIGNS.index(chart.lagna_sign) if chart.lagna_sign in ZODIAC_SIGNS else 0
    l7 = SIGN_RULERS.get(ZODIAC_SIGNS[(lagna_idx + 6) % 12], "")
    pos = chart.planets.get(l7)
    dig = get_planet_strength(l7, pos.sign, pos.degree_in_sign) if pos else ""
    band = strengths[l7].band if l7 in strengths else "weak"
    afflicted = bool(pos and pos.house in (6, 8, 12)) or "debilitat" in dig or (band == "weak")
    v = chart.planets.get("Venus")
    vdig = get_planet_strength("Venus", v.sign, v.degree_in_sign) if v else ""
    venus_aff = "debilitat" in vdig or bool(
        strengths.get("Venus") and getattr(strengths["Venus"], "combustion_penalty", 0)
    )
    return l7, afflicted, venus_aff


def _chart_level(chart_a: NormalizedChart, chart_b: NormalizedChart, rep: CompatibilityReport) -> bool:
    """Compare the two charts' own marriage promise (7th house + Venus). Per practitioner
    consensus this OUTWEIGHS the guna score. Returns True if the chart-level reading is sound."""
    _, aff_a, va = _seventh_quality(chart_a)
    _, aff_b, vb = _seventh_quality(chart_b)
    if not aff_a and not aff_b:
        rep.strengths.append("Both charts independently have a well-placed 7th house — a sound "
                             "marital foundation, which weighs more than the guna score.")
        sound = True
    else:
        who = " and ".join(w for w, a in (("the first", aff_a), ("the second", aff_b)) if a)
        rep.cautions.append(f"The 7th house/lord is weak or afflicted in {who} chart — at the "
                            f"chart level (which outweighs the guna total) this calls for care "
                            f"around marital harmony and stability.")
        sound = False
    if va or vb:
        rep.cautions.append("Venus (affection & marital harmony) is afflicted in one chart — "
                            "tend consciously to romance, warmth and patience.")
    rep.chart_level = (
        "Both 7th houses are sound." if sound
        else "At least one chart's 7th house is afflicted — the deeper reading is cautionary."
    )
    return sound


def _moon_nak(chart: NormalizedChart) -> int:
    moon = chart.planets.get("Moon")
    return nakshatra_index(moon.longitude) if moon else 0


def _rel(a: str, b: str) -> str:
    if b in NATURAL_FRIENDS.get(a, []):
        return "friend"
    if b in NATURAL_ENEMIES.get(a, []):
        return "enemy"
    return "neutral"


# ── koota scorers (a = first person, b = second) ─────────────────────────────────────────

def _varna(sa, sb) -> KootaScore:
    # Auspicious if the husband's (here: person A's) varna is >= the wife's.
    ok = _VARNA_RANK.get(sa, 1) >= _VARNA_RANK.get(sb, 1)
    return KootaScore("Varna (ego/spiritual)", 1.0 if ok else 0.0, 1,
                      "work ethic & ego align" if ok else "a minor ego/values mismatch")


def _vashya(sa, sb) -> KootaScore:
    ga, gb = _VASHYA.get(sa, ""), _VASHYA.get(sb, "")
    if ga == gb:
        s = 2.0
    elif {ga, gb} == {"insect", "wild"} or {ga, gb} == {"quadruped", "wild"}:
        s = 0.0
    else:
        s = 1.0
    return KootaScore("Vashya (mutual attraction)", s, 2,
                      "natural pull & influence" if s >= 1.5 else "moderate mutual influence")


def _tara(na, nb) -> KootaScore:
    def good(frm, to):
        return ((to - frm) % 27 + 1) % 9 not in (3, 5, 7)
    a_ok, b_ok = good(na, nb), good(nb, na)
    s = 3.0 if (a_ok and b_ok) else 1.5 if (a_ok or b_ok) else 0.0
    return KootaScore("Tara (destiny/health)", s, 3,
                      "mutually auspicious birth-stars" if s == 3 else "one-sided star support" if s == 1.5 else "star positions strain each other")


def _yoni(na, nb) -> KootaScore:
    ya, yb = _YONI[na], _YONI[nb]
    if ya == yb:
        s, note = 4.0, "same yoni — strong physical/sexual harmony"
    elif frozenset((ya, yb)) in _YONI_MORTAL:
        s, note = 0.0, f"{ya} vs {yb} are antagonistic yonis — friction in intimacy"
    else:
        s, note = 2.0, "neutral physical compatibility"
    return KootaScore("Yoni (intimacy)", s, 4, note)


def _graha_maitri(sa, sb) -> KootaScore:
    la, lb = SIGN_RULERS.get(sa, ""), SIGN_RULERS.get(sb, "")
    if la == lb:
        s = 5.0
    else:
        r1, r2 = _rel(la, lb), _rel(lb, la)
        rels = {r1, r2}
        if rels == {"friend"}:
            s = 5.0
        elif "friend" in rels and "neutral" in rels:
            s = 4.0
        elif rels == {"neutral"}:
            s = 3.0
        elif "friend" in rels and "enemy" in rels:
            s = 1.0
        elif "neutral" in rels and "enemy" in rels:
            s = 0.5
        else:
            s = 0.0
    return KootaScore("Graha Maitri (mental rapport)", s, 5,
                      "strong intellectual & friendship bond" if s >= 4 else "mental rapport needs effort" if s <= 1 else "workable mental rapport")


_GANA_SCORE = {
    ("deva", "deva"): 6, ("manushya", "manushya"): 6, ("rakshasa", "rakshasa"): 6,
    ("deva", "manushya"): 5, ("manushya", "deva"): 6,
    ("deva", "rakshasa"): 1, ("rakshasa", "deva"): 0,
    ("manushya", "rakshasa"): 0, ("rakshasa", "manushya"): 0,
}


def _gana(na, nb) -> KootaScore:
    ga, gb = _GANA[na], _GANA[nb]
    s = float(_GANA_SCORE.get((ga, gb), 0))
    return KootaScore("Gana (temperament)", s, 6,
                      "temperaments match well" if s >= 5 else f"{ga} vs {gb} temperaments can clash")


def _bhakoot(sa, sb) -> KootaScore:
    c = (ZODIAC_SIGNS.index(sb) - ZODIAC_SIGNS.index(sa)) % 12 + 1
    dosha = c in (2, 5, 6, 8, 9, 12)
    axis = f"{min(c, 14 - c)}/{max(c, 14 - c)}"   # 2/12, 5/9 or 6/8
    return KootaScore("Bhakoot (emotional/finances)", 0.0 if dosha else 7.0, 7,
                      f"{axis} Moon-sign axis — a Bhakoot caution (emotional/financial friction)"
                      if dosha else "Moon signs support each other emotionally & materially")


def _nadi(na, nb) -> KootaScore:
    same = _NADI[na] == _NADI[nb]
    return KootaScore("Nadi (health/progeny)", 0.0 if same else 8.0, 8,
                      f"BOTH have {_NADI[na].capitalize()} Nadi — the most weighted defect (health/progeny); check cancellation"
                      if same else "different Nadi — healthy for progeny & vitality")


def _nadi_cancelled(na, nb, sa, sb) -> str:
    """Classical Nadi-dosha exceptions: same nakshatra but different rashi, or same rashi but
    different nakshatra, or same nakshatra-lord pair across the two."""
    if _NADI[na] != _NADI[nb]:
        return ""
    if na == nb and sa != sb:
        return "Nadi dosha is cancelled (same nakshatra, different Moon sign)."
    if sa == sb and na != nb:
        return "Nadi dosha is cancelled (same Moon sign, different nakshatra)."
    return ""


def assess_compatibility(chart_a: NormalizedChart, chart_b: NormalizedChart) -> CompatibilityReport:
    na, nb = _moon_nak(chart_a), _moon_nak(chart_b)
    sa, sb = chart_a.moon_sign, chart_b.moon_sign

    kootas = [
        _varna(sa, sb), _vashya(sa, sb), _tara(na, nb), _yoni(na, nb),
        _graha_maitri(sa, sb), _gana(na, nb), _bhakoot(sa, sb), _nadi(na, nb),
    ]
    total = round(sum(k.score for k in kootas), 1)
    rep = CompatibilityReport(total=total, kootas=kootas)

    nadi = next(k for k in kootas if k.name.startswith("Nadi"))
    bhakoot = next(k for k in kootas if k.name.startswith("Bhakoot"))
    gana = next(k for k in kootas if k.name.startswith("Gana"))

    # Nadi cancellation
    cancel = _nadi_cancelled(na, nb, sa, sb)
    nadi_ok = nadi.score > 0 or bool(cancel)
    if cancel:
        rep.strengths.append(cancel)
    elif nadi.score == 0:
        rep.cautions.append("Nadi dosha is active (same Nadi) — classically the most serious; "
                            "weigh progeny/health support in both charts before deciding.")
    if bhakoot.score == 0:
        rep.cautions.append("Bhakoot dosha (Moon-sign axis) — check if the sign lords are friends, "
                            "which cancels it; otherwise watch emotional & financial harmony.")
    if gana.score <= 1:
        rep.cautions.append("Gana mismatch — temperaments differ; needs patience and tolerance.")

    # Mangal Dosha — checked separately for both, with the 'both Manglik' cancellation.
    rep.mangal_a = detect_mangal_dosha(chart_a)
    rep.mangal_b = detect_mangal_dosha(chart_b)
    if rep.mangal_a and rep.mangal_b:
        rep.mangal_note = "Both are Manglik — the dosha cancels out (a widely-accepted match)."
        rep.strengths.append(rep.mangal_note)
    elif rep.mangal_a or rep.mangal_b:
        who = "the first" if rep.mangal_a else "the second"
        rep.mangal_note = (f"Only {who} chart is Manglik — a one-sided Mangal Dosha. Look for a "
                           f"classical cancellation (Mars own/exalted, Jupiter's aspect, etc.) "
                           f"before treating it as a barrier.")
        rep.cautions.append(rep.mangal_note)
    else:
        rep.mangal_note = "Neither chart is Manglik."

    # Chart-level comparison (7th house + Venus) — the practitioner-level "real verdict".
    chart_sound = _chart_level(chart_a, chart_b, rep)

    # Verdict — distribution first, total second, and the CHART LEVEL outweighs both.
    heavy_clean = nadi_ok and bhakoot.score > 0
    one_sided_mangal = rep.mangal_a != rep.mangal_b
    if total >= 18 and heavy_clean and not one_sided_mangal and chart_sound:
        rep.verdict = ("Strong, supportive match — the heavy kootas (Nadi, Bhakoot) are clean and "
                       "both charts' 7th houses are sound.")
        rep.strengths.append("The high-weight kootas AND the chart-level 7th houses align — the "
                             "most reliable kind of match.")
    elif not chart_sound and (total >= 18):
        rep.verdict = ("Decent on paper, but the deciding layer — the 7th house in the chart(s) "
                       "below — is afflicted. Practitioners weight this over the guna score, so "
                       "treat it as a cautious match needing conscious effort.")
    elif total >= 24 and not heavy_clean:
        rep.verdict = ("High aggregate but a key koota (Nadi/Bhakoot) fails — do NOT treat the "
                       "number alone as a green light; weigh the cautions and chart-level checks.")
    elif total < 18:
        rep.verdict = ("Below the classical 18-point threshold — challenging on paper; only a "
                       "strong, mutually supportive 7th house in both charts could redeem it"
                       + (", which here is partly present." if chart_sound else "."))
    else:
        rep.verdict = "Workable match — solid where it counts, with a few areas to navigate consciously."
    return rep


def format_compatibility_for_prompt(rep: CompatibilityReport) -> str:
    lines = [
        "[COMPATIBILITY — Ashtakoot Guna Milan + Mangal. Lead with the VERDICT and explain it "
        "from the BREAKDOWN (the heavy kootas Nadi/Bhakoot/Mangal matter more than the total). "
        "Do NOT present the number as a pass/fail; name the specific strengths and cautions.]",
        f"Total: {rep.total}/{rep.max_total} guna.",
        f"Verdict: {rep.verdict}",
        "Breakdown:",
    ]
    for k in rep.kootas:
        lines.append(f"  - {k.name}: {k.score}/{k.maximum} — {k.note}")
    lines.append(f"Mangal: {rep.mangal_note}")
    if rep.chart_level:
        lines.append(f"Chart-level (7th house — the deciding layer): {rep.chart_level}")
    if rep.strengths:
        lines.append("Strengths: " + " ".join(rep.strengths))
    if rep.cautions:
        lines.append("Cautions: " + " ".join(rep.cautions))
    return "\n".join(lines)
