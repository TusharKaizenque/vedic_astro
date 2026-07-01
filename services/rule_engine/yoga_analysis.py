"""
Yoga analysis — promote each DETECTED yoga from a bare name into a graded, chart-specific,
cited factor the narrator can speak about concretely.

The yoga_detector decides IF a yoga is present. This module decides, for the actual chart:
  - WHICH planets form it (participants),
  - HOW strong it is (from the participants' dignity, house, combustion, war),
  - WHAT it classically gives (a concise effect + source).

A yoga formed by an exalted planet in a kendra is worlds apart from the same yoga formed by a
debilitated, combust planet in a dusthana — and that distinction is exactly what makes a
reading specific instead of "you have Gajakesari, which is good." Deterministic ⇒ consistent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from models.chart import NormalizedChart
from services.rule_engine.planetary_states import PlanetState
from utils.astro_constants import (
    DUSTHANA_HOUSES, KENDRA_HOUSES, SIGN_RULERS, TRIKONA_HOUSES,
)

# name -> (concise classical effect, source). Kept tight; Phase-2 KB adds fuller passages.
YOGA_EFFECTS: dict[str, tuple[str, str]] = {
    "Gajakesari": ("lasting reputation, intelligence, prosperity and the respect of others",
                   "Brihat Parashara Hora Shastra; Phaladeepika Ch.6"),
    "Budhaditya": ("sharp intellect, communication skill, scholarship and administrative ability",
                   "Saravali"),
    "Chandra-Mangala": ("drive to earn, enterprise and accumulation of wealth, sometimes blunt",
                        "Phaladeepika"),
    "Adhi": ("leadership, dependable allies, authority, health and a respected position",
             "Brihat Parashara Hora Shastra"),
    "Neecha Bhanga Raja": ("a fall reversed into rise — early struggle turning into unexpected "
                           "elevation and status", "Brihat Parashara Hora Shastra"),
    "Viparita Raja": ("gain through adversity — rivals, crises and losses paradoxically turning "
                      "to one's advantage", "Phaladeepika; Uttara Kalamrita"),
    "Dharma Karmadhipati": ("one of the strongest raja yogas — power, career success and good "
                            "fortune acting together", "Brihat Parashara Hora Shastra"),
    "Raja Yoga": ("status, authority, success and rise above one's origins",
                  "Brihat Parashara Hora Shastra"),
    "Dhana Yoga": ("formation of wealth and steady financial gain",
                   "Brihat Parashara Hora Shastra Ch.43 (Dhana yogas)"),
    "Lakshmi": ("wealth, fortune, beauty and the favour of Lakshmi — prosperity with grace",
                "Phaladeepika"),
    "Saraswati": ("brilliance in learning, arts, speech and scholarship",
                  "Phaladeepika; Saravali"),
    "Kemadruma": ("ADVERSE — isolation, instability and lack of support, struggles despite "
                  "effort (mitigated if cancelled)", "Brihat Parashara Hora Shastra"),
    "Sunapha": ("self-earned wealth, intelligence and a good reputation",
                "Brihat Parashara Hora Shastra (Chandra yogas)"),
    "Anapha": ("good health, character, comforts and a well-regarded personality",
               "Brihat Parashara Hora Shastra (Chandra yogas)"),
    "Durudhara": ("wealth, comforts, generosity and support from both sides",
                  "Brihat Parashara Hora Shastra (Chandra yogas)"),
    "Kaal Sarp": ("intensity, delays and karmic obstacles that often release into achievement "
                  "after mid-life", "classical Nadi / modern Parashari usage"),
    "Vesi": ("balanced temperament, eloquence and a steady livelihood",
             "Brihat Parashara Hora Shastra (Surya yogas)"),
    "Vasi": ("skill, fame and gains through effort and merit",
             "Brihat Parashara Hora Shastra (Surya yogas)"),
    "Ubhayachari": ("all-round success, comforts and an influential standing",
                    "Brihat Parashara Hora Shastra (Surya yogas)"),
    "Shubha Kartari": ("protection and good fortune — benefics shielding the self",
                       "Phaladeepika"),
    "Papa Kartari": ("ADVERSE — pressure and constraint from malefics squeezing the self",
                     "Phaladeepika"),
    "Amala": ("a spotless reputation, lasting fame and ethical standing",
              "Brihat Parashara Hora Shastra; Phaladeepika"),
    "Shakata": ("ADVERSE — fluctuating fortunes, fortunes rising and falling like a cartwheel",
                "Phaladeepika"),
    "Guru-Mangala": ("disciplined drive guided by wisdom; energy applied to dharma and goals",
                     "classical Parashari"),
    "Kahala": ("courage, command, energy and the capacity to lead and build",
               "Phaladeepika"),
    "Kalanidhi": ("wealth, learning, refinement and the favour of the learned",
                  "Phaladeepika"),
    "Maha Bhagya": ("great fortune, noble character, long life and prosperity",
                    "Brihat Parashara Hora Shastra"),
    "Chatussagara": ("fame reaching the 'four oceans' — wide repute and all-round prosperity",
                     "classical Parashari"),
    "Ruchaka": ("(Mahapurusha) courage, leadership, a commanding physique and martial success",
                "Phaladeepika Ch.6 (Pancha Mahapurusha)"),
    "Bhadra": ("(Mahapurusha) intelligence, eloquence, learning and a youthful, capable nature",
               "Phaladeepika Ch.6 (Pancha Mahapurusha)"),
    "Hamsa": ("(Mahapurusha) wisdom, virtue, a righteous nature and respected standing",
              "Phaladeepika Ch.6 (Pancha Mahapurusha)"),
    "Malavya": ("(Mahapurusha) charm, comforts, refinement, vehicles and luxury",
                "Phaladeepika Ch.6 (Pancha Mahapurusha)"),
    "Shasha": ("(Mahapurusha) authority over others, discipline, leadership and influence",
               "Phaladeepika Ch.6 (Pancha Mahapurusha)"),
    "Maha Parivartana": ("a mutual sign-exchange linking two good houses — their matters "
                         "powerfully reinforce each other", "Brihat Parashara Hora Shastra"),
    "Dainya Parivartana": ("ADVERSE exchange involving a dusthana — effort meeting obstacles "
                           "in the linked areas", "Brihat Parashara Hora Shastra"),
    "Khala Parivartana": ("a mixed 3rd-house exchange — ups and downs, gains through effort",
                          "Brihat Parashara Hora Shastra"),
}

# Adverse yogas — graded on a 'severity' scale, not 'strength'.
_ADVERSE = {"Kemadruma", "Papa Kartari", "Shakata", "Dainya Parivartana", "Kaal Sarp"}

# Participant resolvers: which planets actually form the yoga in THIS chart (for the ones whose
# participants are well-defined). Strength is graded from these planets' condition.
_PANCHA = {"Ruchaka": "Mars", "Bhadra": "Mercury", "Hamsa": "Jupiter",
           "Malavya": "Venus", "Shasha": "Saturn"}


@dataclass
class YogaReading:
    name: str
    participants: list[str] = field(default_factory=list)
    strength: str = "present"          # strong | moderate | modest | present (or 'notable' adverse)
    effect: str = ""
    source: str = ""
    adverse: bool = False


def _lord_of(chart: NormalizedChart, house: int) -> str:
    return SIGN_RULERS.get(chart.houses[house].sign, "") if house in chart.houses else ""


def _participants(chart: NormalizedChart, name: str) -> list[str]:
    """Best-effort participating planets for the named yoga."""
    if name in _PANCHA:
        return [_PANCHA[name]]
    if name in ("Gajakesari", "Shakata"):
        return ["Moon", "Jupiter"]
    if name in ("Budhaditya",):
        return ["Sun", "Mercury"]
    if name in ("Chandra-Mangala",):
        return ["Moon", "Mars"]
    if name in ("Guru-Mangala",):
        return ["Jupiter", "Mars"]
    if name == "Dharma Karmadhipati":
        return [p for p in (_lord_of(chart, 9), _lord_of(chart, 10)) if p]
    if name == "Dhana Yoga":
        return [p for p in (_lord_of(chart, 2), _lord_of(chart, 11)) if p]
    if name in ("Lakshmi",):
        return [p for p in (_lord_of(chart, 9),) if p]
    if name in ("Saraswati", "Kalanidhi"):
        return ["Jupiter", "Venus", "Mercury"]
    if name == "Kahala":
        return [p for p in (_lord_of(chart, 4), _lord_of(chart, 9)) if p]
    return []


def _grade(chart: NormalizedChart, states: dict[str, PlanetState], participants: list[str]) -> str:
    """Grade strength from the participants' dignity, house and afflictions."""
    if not participants:
        return "present"
    score = 0
    n = 0
    for p in participants:
        pos = chart.planets.get(p)
        st = states.get(p)
        if not pos or not st:
            continue
        n += 1
        if st.dignity in ("exalted", "moolatrikona", "own sign"):
            score += 2
        elif st.dignity in ("friendly sign", "neutral sign"):
            score += 1
        elif st.dignity == "debilitated":
            score -= 2
        elif st.dignity == "enemy sign":
            score -= 1
        if pos.house in (KENDRA_HOUSES + TRIKONA_HOUSES):
            score += 1
        elif pos.house in DUSTHANA_HOUSES:
            score -= 1
        if st.combust:
            score -= 1
        if st.war and not st.war_won:
            score -= 1
    if not n:
        return "present"
    avg = score / n
    if avg >= 2:
        return "strong"
    if avg >= 1:
        return "moderate"
    if avg >= 0:
        return "modest"
    return "weakened"


def analyze_yogas(
    chart: NormalizedChart, yogas_present: list[str], states: dict[str, PlanetState]
) -> list[YogaReading]:
    """Grade and annotate every detected yoga for this specific chart."""
    out: list[YogaReading] = []
    for name in yogas_present:
        effect, source = YOGA_EFFECTS.get(name, ("", ""))
        adverse = name in _ADVERSE
        parts = _participants(chart, name)
        strength = "notable" if adverse else _grade(chart, states, parts)
        out.append(YogaReading(
            name=name, participants=parts, strength=strength,
            effect=effect, source=source, adverse=adverse,
        ))
    # Lead with the strongest beneficial yogas; keep adverse ones flagged at the end.
    rank = {"strong": 0, "moderate": 1, "modest": 2, "present": 3, "weakened": 4, "notable": 5}
    out.sort(key=lambda y: (y.adverse, rank.get(y.strength, 9)))
    return out


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _dasha_windows(chart: NormalizedChart):
    """Yield (maha_lord, antar_lord, start, end) from the Prokerala dasha tree."""
    data = getattr(chart, "raw_prokerala_response", None) or {}
    for md in data.get("dasha_periods", []) or []:
        md_lord = str(md.get("name", ""))
        for ad in md.get("antardasha", []) or []:
            yield (md_lord, str(ad.get("name", "")),
                   _parse_dt(ad.get("start", "")), _parse_dt(ad.get("end", "")))


def format_yoga_timing_for_prompt(
    chart: NormalizedChart, readings: list[YogaReading], now: datetime, limit: int = 4
) -> str:
    """A yoga only FRUCTIFIES in the dasha/antardasha of the planets that form it (BPHS). For
    the strongest beneficial yogas, find the next upcoming window ruled by a participant so the
    reading can say WHEN each blessing activates — not just that it exists."""
    strong = [y for y in readings
              if not y.adverse and y.participants and y.strength in ("strong", "moderate")]
    if not strong:
        return ""
    windows = list(_dasha_windows(chart))
    if not windows:
        return ""
    lines: list[str] = []
    for y in strong[:limit]:
        parts = set(y.participants)
        upcoming = [w for w in windows if w[3] and w[3] >= now and (w[0] in parts or w[1] in parts)]
        if not upcoming:
            continue
        md, ad, start, end = min(upcoming, key=lambda w: w[2] or now)
        sd = start.strftime("%b %Y") if start else "—"
        ed = end.strftime("%b %Y") if end else "—"
        lines.append(f"  • {y.name} (formed by {', '.join(y.participants)}) next activates in the "
                     f"{md} mahadasha / {ad} antardasha — {sd} to {ed}.")
    if not lines:
        return ""
    return ("[YOGA ACTIVATION TIMING — a yoga fructifies in the dasha of its forming planets; "
            "these are the upcoming windows]\n" + "\n".join(lines))


def format_yoga_analysis_for_prompt(
    readings: list[YogaReading], limit: int = 8, focus_planets: set[str] | None = None
) -> str:
    """Render the DECISION-RELEVANT yogas. A chart can throw 12+ yogas; dumping them all buries
    the few that shape the life and dilutes the reading. We keep the strongest beneficial ones
    (sorted strongest-first) up to `limit`, ALWAYS keep the adverse ones (real warnings), and
    ALWAYS keep any yoga formed by the TOPIC's significators (topic-relevant, never dropped) —
    so the cap trims only incidental yogas, never a relevant one."""
    if not readings:
        return ""
    focus = focus_planets or set()
    top = [y for y in readings if not y.adverse and y.strength != "weakened"][:limit]
    relevant = [y for y in readings if not y.adverse and focus and set(y.participants) & focus]
    adverse = [y for y in readings if y.adverse]
    # Union, preserving the original (strength-sorted) order and de-duping.
    seen = set()
    chosen = []
    for y in [*top, *relevant, *adverse]:
        if y.name not in seen:
            seen.add(y.name)
            chosen.append(y)
    chosen.sort(key=lambda y: readings.index(y))   # restore strength/adverse ordering
    if not chosen:
        return ""
    lines = ["[YOGA ANALYSIS — the yogas that most shape this chart; cite the source when named]"]
    for y in chosen:
        who = f" ({', '.join(y.participants)})" if y.participants else ""
        grade = f"[{y.strength}]"
        eff = f" — {y.effect}" if y.effect else ""
        src = f" (per {y.source})" if y.source else ""
        lines.append(f"  • {y.name}{who} {grade}{eff}{src}")
    return "\n".join(lines)
