"""
Chart Signature Engine — the "what stands out about THIS person" layer.

Life-area prominence (life_overview) answers *which topics matter*. This module answers a
sharper question: does the chart carry a strong, specific life signature — exceptional
wealth, a struggle-laden life, a spiritual/occult bent, delayed-then-earned success,
marriage friction, public eminence, foreign settlement…?

Each signature is a CONFLUENCE: it fires only when ≥2 independent chart factors corroborate
it (multi-testimony). One weak signal is never enough — that is precisely what stops the
generic, applies-to-everyone reading. Every fired signature carries its evidence list, so
the narration leads with the conclusion AND names why the chart says it.

Fully deterministic; reuses the existing engines (Shadbala bands, yogas/doshas, house lords,
Ashtakavarga, dignities). Nothing here is fuzzy or invented.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from services.rule_engine.ashtakavarga_engine import compute_sav, sav_for_house
from services.rule_engine.engine import RuleEngineResult
from services.rule_engine.strength_calculator import get_planet_strength
from services.rule_engine.strength_engine import PlanetStrength
from utils.astro_constants import PLANETS

# A signature is emitted only when at least this many independent factors corroborate it.
_MIN_FACTORS = 2


@dataclass
class ChartSignature:
    key: str
    label: str               # user-facing theme, phrased as a conclusion
    polarity: str            # boon | challenge | neutral
    confidence: str          # very high | high | moderate
    score: float
    evidence: list[str] = field(default_factory=list)


class _Ctx:
    """Cached accessors over the chart so detectors stay short and read like astrology."""

    def __init__(self, chart, rules, strengths, sav):
        self.chart = chart
        self.rules = rules
        self.strengths = strengths
        self.sav = sav
        self.dignity = {
            n: get_planet_strength(n, p.sign, p.degree_in_sign)
            for n, p in chart.planets.items()
        }

    def band(self, planet: str) -> str:
        s = self.strengths.get(planet)
        return s.band if s else "weak"

    def is_strong(self, planet: str) -> bool:
        return self.band(planet) == "strong"

    def house_of(self, planet: str) -> int:
        p = self.chart.planets.get(planet)
        return p.house if p else 0

    def in_houses(self, planet: str, houses) -> bool:
        return self.house_of(planet) in houses

    def lord_of(self, house: int) -> str:
        return self.rules.house_lords.get(house, "")

    def planets_in(self, houses) -> list[str]:
        return [n for n, p in self.chart.planets.items() if p.house in houses]

    def has_yoga(self, *subs: str) -> bool:
        return any(any(s.lower() in y.lower() for s in subs) for y in self.rules.yogas_present)

    def has_dosha(self, *subs: str) -> bool:
        return any(any(s.lower() in d.lower() for s in subs) for d in self.rules.doshas_present)

    def sav_of(self, house: int) -> int:
        return sav_for_house(self.chart, house, self.sav)

    def is_combust(self, planet: str) -> bool:
        s = self.strengths.get(planet)
        return bool(s and getattr(s, "combustion_penalty", 0))

    def is_afflicted(self, planet: str) -> bool:
        """Debilitated or combust — the unambiguous afflictions (enemy sign is too mild)."""
        return "debilitat" in self.dignity.get(planet, "") or self.is_combust(planet)

    def is_dignified(self, planet: str) -> bool:
        """Exalted / own sign / moolatrikona — strong dignity that mitigates a hard placement."""
        return any(d in self.dignity.get(planet, "") for d in ("exalt", "own sign", "moolatrikona"))

    def afflicted_in_dusthana(self) -> list[str]:
        """Dusthana (6/8/12) occupants that are NOT dignified — i.e. the ones that genuinely
        signify difficulty. An exalted/own-sign planet in a dusthana is a mitigated case
        (often Viparita-like), so it is excluded from the struggle tally."""
        return [n for n, p in self.chart.planets.items()
                if p.house in (6, 8, 12) and not self.is_dignified(n)]

    def is_yogakaraka(self, planet: str) -> bool:
        return self.rules.functional_nature.get(planet) == "yogakaraka"

    def debilitated(self) -> list[str]:
        return [n for n in PLANETS if "debilitat" in self.dignity.get(n, "")]


# --- detectors: each returns (label, polarity, [(evidence, weight), ...]) -----------------
# Conditions are classical; weights reflect how decisive each testimony is.

def _wealth(c: _Ctx):
    f = []
    if c.has_yoga("Dhana Yoga"):
        f.append(("a wealth-giving Dhana yoga", 2.0))
    if c.has_yoga("Lakshmi"):
        f.append(("Lakshmi yoga (affluence & fortune)", 2.0))
    if c.has_yoga("Kalanidhi"):
        f.append(("Kalanidhi yoga (prosperity)", 1.5))
    if c.has_yoga("Maha Bhagya"):
        f.append(("Maha Bhagya yoga (great fortune)", 1.5))
    l2 = c.lord_of(2)
    if l2 and c.is_strong(l2):
        f.append((f"the 2nd lord of wealth ({l2}) is strong", 1.0))
    l11 = c.lord_of(11)
    if l11 and c.is_strong(l11):
        f.append((f"the 11th lord of gains ({l11}) is strong", 1.0))
    if c.sav_of(2) >= 30:
        f.append((f"the 2nd house is richly fortified ({c.sav_of(2)} Ashtakavarga bindus)", 1.0))
    if c.sav_of(11) >= 30:
        f.append((f"the 11th house is richly fortified ({c.sav_of(11)} bindus)", 1.0))
    if c.is_strong("Jupiter"):
        f.append(("Jupiter, the karaka of wealth, is strong", 1.0))
    return "exceptional wealth & material abundance", "boon", f


def _struggle(c: _Ctx):
    f = []
    lag = c.lord_of(1)
    # A weak lagna lord only counts if it is NOT strongly dignified — an exalted/own-sign
    # lagna lord (even with modest Shadbala) is not a hardship testimony.
    if lag and c.band(lag) == "weak" and not c.is_dignified(lag):
        f.append((f"the lagna lord ({lag}) is weak and undignified", 1.5))
    if lag and c.in_houses(lag, [6, 8, 12]):
        if c.is_dignified(lag):
            f.append((f"the lagna lord ({lag}) sits in a dusthana (house {c.house_of(lag)}), "
                      f"though its dignity softens this", 0.75))
        else:
            f.append((f"the lagna lord ({lag}) sits in a dusthana (house {c.house_of(lag)})", 1.5))
    if c.is_afflicted("Moon") or (c.in_houses("Moon", [6, 8, 12]) and not c.is_dignified("Moon")):
        f.append(("the Moon (mind/wellbeing) is afflicted or weakly placed in a dusthana", 1.0))
    dus = c.afflicted_in_dusthana()
    if len(dus) >= 3:
        f.append((f"{len(dus)} undignified planets fall in the dusthanas of difficulty (6/8/12)", 2.0))
    if c.has_yoga("Kemadruma"):
        f.append(("Kemadruma yoga (isolation & want)", 1.5))
    if c.has_yoga("Papa Kartari"):
        f.append(("Papa Kartari yoga (hemmed between malefics)", 1.0))
    if c.has_yoga("Dainya"):
        f.append(("a Dainya parivartana (a debilitating exchange)", 1.5))
    if c.has_dosha("Kaal Sarp"):
        f.append(("Kaal Sarp dosha", 1.0))
    if c.has_dosha("Shrapit"):
        f.append(("Shrapit dosha (a karmic burden)", 1.0))
    if len(c.debilitated()) >= 2:
        f.append((f"{len(c.debilitated())} debilitated planets", 1.0))
    return "a life that asks for struggle & resilience", "challenge", f


def _delayed_success(c: _Ctx):
    f = []
    if c.is_yogakaraka("Saturn") and c.band("Saturn") in ("strong", "moderate"):
        f.append(("Saturn is the yogakaraka and well-placed — it rewards patience", 2.0))
    if c.in_houses("Saturn", [1, 10]):
        f.append((f"Saturn sits in the {c.house_of('Saturn')}th — it delays, then delivers", 1.5))
    if c.has_yoga("Neecha Bhanga"):
        f.append(("Neecha Bhanga (an early fall redeemed over time)", 1.5))
    if c.has_yoga("Shasha"):
        f.append(("Shasha Mahapurusha yoga (Saturnine eminence, earned late)", 1.5))
    l10 = c.lord_of(10)
    if l10 and (l10 == "Saturn" or (c.house_of(l10) and c.house_of(l10) == c.house_of("Saturn"))):
        f.append(("Saturn conditions the career lord", 1.0))
    if c.chart.dasha.maha_dasha_lord == "Saturn":
        f.append(("the current Saturn mahadasha is the maturing, consolidating period", 0.5))
    return "success that arrives after delay & perseverance", "neutral", f


def _spiritual(c: _Ctx):
    f = []
    if c.in_houses("Ketu", [1, 8, 9, 12]):
        f.append((f"Ketu (the moksha karaka) in the {c.house_of('Ketu')}th", 1.5))
    moksha = c.planets_in([8, 12])
    if len(moksha) >= 2:
        f.append((f"{len(moksha)} planets in the moksha houses (8/12)", 1.5))
    l12 = c.lord_of(12)
    if l12 and c.is_strong(l12):
        f.append((f"the 12th lord of liberation ({l12}) is strong", 1.0))
    if c.in_houses("Saturn", [12]) or c.in_houses("Ketu", [12]):
        f.append(("Saturn/Ketu in the 12th (detachment & seclusion)", 1.0))
    if c.is_strong("Jupiter") and c.in_houses("Jupiter", [1, 5, 9, 12]):
        f.append(("a strong Jupiter on a dharma/moksha axis", 1.0))
    occult = [p for p in ("Mars", "Saturn", "Ketu", "Rahu") if c.house_of(p) == 8]
    if occult:
        f.append((f"{', '.join(occult)} in the 8th — occult, tantric & research depth", 1.0))
    if c.chart.dasha.maha_dasha_lord in ("Ketu", "Saturn"):
        f.append((f"the {c.chart.dasha.maha_dasha_lord} mahadasha turns life inward", 0.5))
    return "a spiritual, occult & inward-seeking nature", "boon", f


def _marriage_difficulty(c: _Ctx):
    f = []
    l7 = c.lord_of(7)
    if l7 and (c.band(l7) == "weak" or c.is_afflicted(l7) or c.in_houses(l7, [6, 8, 12])):
        f.append((f"the 7th lord of marriage ({l7}) is weak, afflicted, or in a dusthana", 1.5))
    if c.is_afflicted("Venus"):
        f.append(("Venus, the karaka of marriage, is debilitated or combust", 1.5))
    if c.has_dosha("Mangal"):
        f.append(("Mangal (Kuja) dosha", 1.5))
    malefics_7 = [p for p in ("Mars", "Saturn", "Rahu", "Ketu", "Sun") if c.house_of(p) == 7]
    if malefics_7:
        f.append((f"malefic(s) in the 7th house: {', '.join(malefics_7)}", 1.0))
    if c.house_of("Venus") and c.house_of("Venus") == c.house_of("Saturn"):
        f.append(("Venus conjunct Saturn (a cooling of desire, delay)", 1.0))
    return "friction or delay in marriage & partnership", "challenge", f


def _eminence(c: _Ctx):
    f = []
    if c.has_yoga("Raja Yoga"):
        f.append(("a Raja yoga (power & status)", 2.0))
    if c.has_yoga("Dharma Karmadhipati"):
        f.append(("Dharma-Karmadhipati yoga (the strongest yoga for career)", 2.0))
    mahapurusha = [y for y in ("Ruchaka", "Bhadra", "Hamsa", "Malavya", "Shasha") if c.has_yoga(y)]
    if mahapurusha:
        f.append((f"Panch-Mahapurusha yoga: {', '.join(mahapurusha)}", 2.0))
    l10 = c.lord_of(10)
    if l10 and c.is_strong(l10):
        f.append((f"the 10th lord of career ({l10}) is strong", 1.0))
    if c.is_strong("Sun") and c.in_houses("Sun", [1, 10, 11]):
        f.append(("a strong Sun commanding status", 1.0))
    if c.sav_of(10) >= 30:
        f.append((f"the 10th house is richly fortified ({c.sav_of(10)} bindus)", 1.0))
    if c.has_yoga("Amala"):
        f.append(("Amala yoga (a lasting, spotless reputation)", 1.0))
    return "rise to authority & public eminence", "boon", f


def _intellect(c: _Ctx):
    f = []
    if c.has_yoga("Saraswati"):
        f.append(("Saraswati yoga (scholarship & eloquence)", 2.0))
    if c.has_yoga("Budhaditya"):
        f.append(("Budh-Aditya yoga (bright intelligence)", 1.5))
    if c.has_yoga("Bhadra"):
        f.append(("Bhadra Mahapurusha yoga (Mercurial brilliance)", 2.0))
    if c.has_yoga("Gajakesari"):
        f.append(("Gajakesari yoga (wisdom & repute)", 1.5))
    l5 = c.lord_of(5)
    if l5 and c.is_strong(l5):
        f.append((f"the 5th lord of intelligence ({l5}) is strong", 1.0))
    if c.is_strong("Mercury"):
        f.append(("a strong Mercury (sharp intellect)", 1.0))
    return "a sharp intellect & scholarly mind", "boon", f


def _health_vulnerability(c: _Ctx):
    f = []
    lag = c.lord_of(1)
    if lag and c.band(lag) == "weak" and not c.is_dignified(lag):
        f.append((f"the lagna lord ({lag}) is weak (vitality)", 1.0))
    if lag and (c.is_afflicted(lag) or (c.in_houses(lag, [6, 8, 12]) and not c.is_dignified(lag))):
        f.append((f"the lagna lord ({lag}) is afflicted or weakly placed in a dusthana", 1.0))
    malefics_1 = [p for p in ("Mars", "Saturn", "Rahu", "Ketu") if c.house_of(p) == 1]
    if malefics_1:
        f.append((f"malefic(s) in the 1st house: {', '.join(malefics_1)}", 1.0))
    six_eight = c.planets_in([6, 8])
    if len(six_eight) >= 2:
        f.append((f"emphasis on the 6th/8th houses of illness ({len(six_eight)} planets)", 1.0))
    if c.is_afflicted("Sun"):
        f.append(("the Sun (vitality) is afflicted", 1.0))
    return "a constitution that needs steady care", "challenge", f


def _foreign(c: _Ctx):
    f = []
    if c.in_houses("Rahu", [7, 9, 12]):
        f.append((f"Rahu in the {c.house_of('Rahu')}th (foreign & unconventional pull)", 1.5))
    if c.house_of("Moon") == 12:
        f.append(("the Moon in the 12th (a life settled away from home)", 1.0))
    l12 = c.lord_of(12)
    if l12 and (c.is_strong(l12) or c.in_houses(l12, [1, 4, 9, 10])):
        f.append((f"the 12th lord ({l12}) is well-disposed (gains abroad)", 1.0))
    if len(c.planets_in([12])) >= 2:
        f.append((f"{len(c.planets_in([12]))} planets in the 12th of foreign lands", 1.0))
    return "foreign connections & a life away from birthplace", "neutral", f


def _viparita(c: _Ctx):
    f = []
    if c.has_yoga("Viparita"):
        f.append(("Viparita Raja yoga (gain through reversals)", 2.0))
    dusthana_lords = [h for h in (6, 8, 12) if c.lord_of(h) and c.in_houses(c.lord_of(h), [6, 8, 12])]
    if len(dusthana_lords) >= 2:
        f.append((f"dusthana lords confined to dusthanas ({len(dusthana_lords)} of 6/8/12)", 1.5))
    return "rise through adversity & crisis", "boon", f


_DETECTORS = [
    _wealth, _struggle, _delayed_success, _spiritual, _marriage_difficulty,
    _eminence, _intellect, _health_vulnerability, _foreign, _viparita,
]


def _confidence(score: float, n_factors: int) -> str:
    if score >= 5.0 and n_factors >= 3:
        return "very high"
    if score >= 3.5 or n_factors >= 3:
        return "high"
    return "moderate"


def detect_signatures(
    chart: NormalizedChart,
    rules: RuleEngineResult,
    strengths: dict[str, PlanetStrength],
    sav: dict | None = None,
) -> list[ChartSignature]:
    """Return the chart's standout signatures (≥2 corroborating factors each), strongest first."""
    if sav is None:
        sav = compute_sav(chart)
    ctx = _Ctx(chart, rules, strengths, sav)
    out: list[ChartSignature] = []
    for detector in _DETECTORS:
        label, polarity, fired = detector(ctx)
        if len(fired) < _MIN_FACTORS:
            continue  # one testimony is not a signature — this is the anti-generic guard
        score = round(sum(w for _, w in fired), 2)
        evidence = [e for e, _ in fired]
        out.append(ChartSignature(
            key=label, label=label, polarity=polarity,
            confidence=_confidence(score, len(fired)), score=score, evidence=evidence,
        ))
    out.sort(key=lambda s: s.score, reverse=True)
    return out


def select_signatures(signatures: list[ChartSignature], limit: int = 6) -> list[ChartSignature]:
    """Surface the genuinely-dominant signatures: every very-high/high one, and moderate ones
    only to reach a floor of 3 — so a rich chart shows its full picture while a flat chart
    isn't padded with weak, near-generic testimony."""
    strong = [s for s in signatures if s.confidence in ("very high", "high")]
    chosen = strong if len(strong) >= 3 else signatures[:3]
    return chosen[:limit]


def _tension_note(chosen: list[ChartSignature]) -> str:
    """When a strong boon and a strong challenge coexist, tell the narrator to synthesize the
    tension (e.g. eminence earned through hardship) rather than list contradictions."""
    boon = next((s for s in chosen if s.polarity == "boon"), None)
    challenge = next((s for s in chosen if s.polarity == "challenge"), None)
    if boon and challenge:
        return (
            f"NOTE: '{boon.label}' and '{challenge.label}' are BOTH strongly supported — this is "
            f"not a contradiction. Read them together: the gains are real but earned through the "
            f"difficulty. Name this tension explicitly; do not drop either side."
        )
    return ""


def format_signatures_for_prompt(signatures: list[ChartSignature]) -> str:
    """Render the standout signatures as authoritative raw material for the reading."""
    chosen = select_signatures(signatures)
    if not chosen:
        return ""
    lines = [
        "[STANDOUT CHART SIGNATURES — highly-supported, specific to THIS person.",
        "LEAD the reading with these. Each is backed by multiple corroborating factors; state",
        "the conclusion plainly and weave in the evidence. Do NOT water these into generic lines.]",
    ]
    for s in chosen:
        lines.append(f"- {s.label} [{s.polarity}; confidence: {s.confidence}]")
        for e in s.evidence:
            lines.append(f"    • {e}")
    note = _tension_note(chosen)
    if note:
        lines.append(note)
    return "\n".join(lines)
