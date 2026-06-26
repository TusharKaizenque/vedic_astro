"""
Assessment Engine (A2) — the deterministic verdict.

This is the piece that stops the LLM from doing the reasoning. It consumes the
SignificatorResult (which factors are relevant + supporting/afflicting/neutral)
and the classical strength scores (Shadbala-lite), and produces a TopicAssessment:
a graded direction, the dominant factors, the key tension, and a timing read.

The weighting is classical, not arbitrary:
  - factor magnitude = planet's Shadbala-lite strength (0..1)
  - role weight = classical significator hierarchy (house lord > karaka > occupant > aspector)
  - direction sign = supporting (+) / afflicting (-) / neutral (0), already decided
    by the significator engine from dignity + functional nature + house type.

The LLM then only narrates this verdict. It does not re-weigh.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from services.rule_engine.ashtakavarga_engine import compute_sav, sav_band, sav_for_house
from services.rule_engine.engine import RuleEngineResult
from services.rule_engine.strength_engine import PlanetStrength
from services.significator_engine import SignificatorFactor, SignificatorResult

# Classical significator hierarchy → how much a factor counts.
# Checked in order; first match wins. Each entry: (required substrings, weight).
_ROLE_WEIGHTS: list[tuple[tuple[str, ...], float]] = [
    (("lord", "karaka"), 1.0),   # house lord that is ALSO the karaka — strongest
    (("karaka",), 0.8),
    (("lord",), 1.0),            # "Nth lord"
    (("occupies",), 0.7),
    (("aspects",), 0.5),
]

# Direction thresholds on the normalized margin.
_FAVOURABLE = 0.20
_CHALLENGED = -0.20


@dataclass
class WeightedFactor:
    planet: str
    role: str
    kind: str               # supporting | afflicting | neutral
    strength: float         # planet Shadbala-lite relative (0..1)
    band: str               # strong | moderate | weak
    role_weight: float
    magnitude: float        # role_weight * strength (unsigned importance)
    signed: float           # +/- magnitude (0 for neutral)


@dataclass
class TopicAssessment:
    topic: str
    direction: str                  # favourable | mixed | challenged
    confidence: str                 # high | moderate | low
    support_score: float
    afflict_score: float
    neutral_score: float
    margin: float                   # (support - afflict) / (support + afflict)
    dominant_supporting: list[WeightedFactor] = field(default_factory=list)
    dominant_afflicting: list[WeightedFactor] = field(default_factory=list)
    key_tension: str = ""
    dasha_timing: str = ""
    timing_favours_now: str = "neutral"   # favourable | challenged | neutral
    summary_line: str = ""
    # Phase D corroboration signals
    sav_primary_house: int = 0      # Sarvashtakavarga bindus in the primary topic house
    sav_band: str = ""              # strong | average | weak
    varga: str = ""                 # relevant divisional chart (D9, D10, ...)
    varga_notes: list[str] = field(default_factory=list)


def _role_weight(role: str) -> float:
    role_l = role.lower()
    for required, weight in _ROLE_WEIGHTS:
        if all(part in role_l for part in required):
            return weight
    return 0.5


def _weight_factor(factor: SignificatorFactor, strengths: dict[str, PlanetStrength]) -> WeightedFactor:
    st = strengths.get(factor.planet)
    strength = st.relative if st else 0.3
    band = st.band if st else "weak"
    rw = _role_weight(factor.role)
    magnitude = rw * strength
    if factor.kind == "supporting":
        signed = magnitude
    elif factor.kind == "afflicting":
        signed = -magnitude
    else:
        signed = 0.0
    return WeightedFactor(
        planet=factor.planet, role=factor.role, kind=factor.kind,
        strength=round(strength, 3), band=band, role_weight=rw,
        magnitude=round(magnitude, 3), signed=round(signed, 3),
    )


def _confidence(margin: float, neutral_score: float, total_score: float, grounded_ratio: float) -> str:
    """High when the verdict is clear, structurally decisive, and source-backed."""
    clear = abs(margin) >= 0.35
    decisive = total_score > 0 and (neutral_score / (total_score + neutral_score + 1e-9)) < 0.35
    sourced = grounded_ratio >= 0.5
    score = sum([clear, decisive, sourced])
    return "high" if score == 3 else "moderate" if score == 2 else "low"


def _dasha_timing(
    significators: SignificatorResult,
    strengths: dict[str, PlanetStrength],
) -> tuple[str, str]:
    """Read whether the current dasha activates the topic favourably or not."""
    d = significators.dasha_activation
    if not d.maha_lord:
        return "neutral", "No active dasha data."

    def _lord_read(lord: str, fn: str, is_sig: bool) -> str | None:
        if not lord:
            return None
        st = strengths.get(lord)
        strength_word = st.band if st else "unknown-strength"
        if is_sig:
            if fn in ("benefic", "yogakaraka"):
                return f"{lord} ({strength_word}, functional {fn}, topic significator) — supports the topic now"
            if fn == "malefic":
                return f"{lord} ({strength_word}, functional malefic but topic significator) — activates the topic with friction"
            return f"{lord} ({strength_word}, topic significator) — activates the topic"
        return None

    reads = [
        _lord_read(d.maha_lord, d.maha_functional_nature, d.maha_is_significator),
        _lord_read(d.antar_lord, d.antar_functional_nature, d.antar_is_significator),
    ]
    reads = [r for r in reads if r]

    if not reads:
        return "neutral", (
            f"{d.maha_lord} Mahadasha, currently its {d.antar_lord} Antardasha sub-period — "
            f"neither lord is a primary significator for this topic, so the period does not "
            f"strongly activate it."
        )

    # Decide favour: benefic significator dasha → favourable; malefic significator → challenged-ish
    favourable = any("supports the topic" in r for r in reads)
    friction = any("friction" in r for r in reads)
    verdict = "favourable" if favourable and not friction else "challenged" if friction and not favourable else "mixed"
    from utils.formatting import format_date
    # Distinguish the long Mahadasha span from the short Antardasha (sub-period) within it,
    # so "ends <date>" is never mistaken for the whole Mahadasha ending.
    maha_span = f" (through {format_date(d.maha_end)})" if d.maha_end else ""
    antar_span = f" (until {format_date(d.antar_end)})" if d.antar_end else ""
    text = (
        f"{d.maha_lord} Mahadasha{maha_span}, currently its {d.antar_lord} "
        f"Antardasha sub-period{antar_span}; activation {d.activation_strength}. "
        + " ".join(reads)
    )
    return verdict, text


_VARGA_STRONG = {"exalted", "own sign", "moolatrikona"}
_VARGA_WEAK = {"debilitated", "enemy sign"}


def _varga_cross_check(significators: SignificatorResult) -> tuple[list[str], int]:
    """Assess the varga (D-9/D-10/...) strength of each meaningful significator.

    Classical principle: a significator should be strong in the relevant varga, not only
    in the Rasi. Net > 0 means the varga corroborates the topic; net < 0 undermines it.
    The signal is `kind`-aware: a strong varga helps a supporter but deepens an afflicter,
    and a weak varga undermines a supporter but eases an afflicter."""
    varga = significators.relevant_varga
    notes: list[str] = []
    net = 0
    for f in significators.factors:
        if f.kind == "neutral" or not f.varga_dignity:
            continue
        v_strong = f.varga_dignity in _VARGA_STRONG
        v_weak = f.varga_dignity in _VARGA_WEAK
        if not (v_strong or v_weak):
            continue
        if f.kind == "supporting":
            if v_strong:
                net += 1
                notes.append(f"{f.planet} supports and is {f.varga_dignity} in {varga} — confirmed in the divisional chart.")
            else:
                net -= 1
                notes.append(f"{f.planet} supports in D-1 but is {f.varga_dignity} in {varga} — the support is shakier on closer inspection.")
        else:  # afflicting
            if v_weak:
                net += 1
                notes.append(f"{f.planet} afflicts but is {f.varga_dignity} in {varga} — the affliction softens in the divisional chart.")
            else:
                net -= 1
                notes.append(f"{f.planet} afflicts and is {f.varga_dignity} in {varga} — the difficulty deepens in the divisional chart.")
    return notes, net


def assess_topic(
    significators: SignificatorResult,
    strengths: dict[str, PlanetStrength],
    rule_result: RuleEngineResult,
    grounded_ratio: float = 0.0,
    chart: NormalizedChart | None = None,
) -> TopicAssessment:
    weighted = [_weight_factor(f, strengths) for f in significators.factors]

    support_score = round(sum(w.signed for w in weighted if w.signed > 0), 3)
    afflict_score = round(-sum(w.signed for w in weighted if w.signed < 0), 3)
    neutral_score = round(sum(w.magnitude for w in weighted if w.kind == "neutral"), 3)

    denom = support_score + afflict_score
    margin = round((support_score - afflict_score) / denom, 3) if denom > 0 else 0.0

    # Yogas shift the structural reading: each relevant benefic yoga nudges favourable.
    yoga_boost = 0.10 * len(significators.relevant_yogas)
    dosha_drag = 0.08 * len(significators.relevant_doshas)

    # --- Phase D corroboration: Ashtakavarga (SAV) of the primary house ---
    primary_house = significators.primary_houses[0] if significators.primary_houses else 1
    sav_h = 0
    sav_b = ""
    sav_adj = 0.0
    if chart is not None:
        sav_h = sav_for_house(chart, primary_house, compute_sav(chart))
        sav_b = sav_band(sav_h)
        sav_adj = 0.08 if sav_b == "strong" else -0.08 if sav_b == "weak" else 0.0

    # --- Phase D corroboration: varga (D-9/D-10/...) cross-check ---
    varga_notes, varga_net = _varga_cross_check(significators)
    varga_adj = 0.05 * max(-1, min(1, varga_net))

    adjusted_margin = round(margin + yoga_boost - dosha_drag + sav_adj + varga_adj, 3)

    if adjusted_margin >= _FAVOURABLE:
        direction = "favourable"
    elif adjusted_margin <= _CHALLENGED:
        direction = "challenged"
    else:
        direction = "mixed"

    dominant_supporting = sorted(
        [w for w in weighted if w.signed > 0], key=lambda w: w.magnitude, reverse=True
    )[:3]
    dominant_afflicting = sorted(
        [w for w in weighted if w.signed < 0], key=lambda w: w.magnitude, reverse=True
    )[:3]

    # Key tension: strongest supporting vs strongest afflicting.
    key_tension = ""
    if dominant_supporting and dominant_afflicting:
        s, a = dominant_supporting[0], dominant_afflicting[0]
        key_tension = (
            f"{s.planet} ({s.role}, {s.band}) supports while "
            f"{a.planet} ({a.role}, {a.band}) afflicts — "
            + ("support is stronger" if s.magnitude > a.magnitude
               else "affliction is stronger" if a.magnitude > s.magnitude
               else "they are evenly matched")
        )
    elif dominant_supporting:
        key_tension = "No significant afflicting factor — the topic is largely unobstructed."
    elif dominant_afflicting:
        key_tension = "No significant supporting factor — the topic lacks structural support."

    timing_favours_now, dasha_timing = _dasha_timing(significators, strengths)

    confidence = _confidence(adjusted_margin, neutral_score, denom, grounded_ratio)
    # Varga + SAV corroboration sharpens or softens confidence.
    if varga_net <= -2 or (varga_net < 0 and sav_b == "weak"):
        confidence = _downgrade(confidence)
    elif varga_net >= 2 and sav_b == "strong":
        confidence = _upgrade(confidence)

    summary = _summary_line(significators.topic, direction, timing_favours_now, confidence)

    return TopicAssessment(
        topic=significators.topic,
        direction=direction,
        confidence=confidence,
        support_score=support_score,
        afflict_score=afflict_score,
        neutral_score=neutral_score,
        margin=adjusted_margin,
        dominant_supporting=dominant_supporting,
        dominant_afflicting=dominant_afflicting,
        key_tension=key_tension,
        dasha_timing=dasha_timing,
        timing_favours_now=timing_favours_now,
        summary_line=summary,
        sav_primary_house=sav_h,
        sav_band=sav_b,
        varga=significators.relevant_varga,
        varga_notes=varga_notes,
    )


def _downgrade(confidence: str) -> str:
    return {"high": "moderate", "moderate": "low", "low": "low"}[confidence]


def _upgrade(confidence: str) -> str:
    return {"low": "moderate", "moderate": "high", "high": "high"}[confidence]


def _summary_line(topic: str, direction: str, timing: str, confidence: str) -> str:
    direction_word = {
        "favourable": "structurally supported",
        "mixed": "mixed — real support offset by real obstacles",
        "challenged": "structurally challenged",
    }[direction]
    timing_word = {
        "favourable": "the current period activates it favourably",
        "challenged": "the current period brings friction",
        "neutral": "the current period does not strongly activate it",
        "mixed": "the current period activates it with mixed effect",
    }[timing]
    return (
        f"{topic.capitalize()} is {direction_word}; {timing_word} "
        f"(confidence: {confidence})."
    )


def _balance_phrase(a: TopicAssessment) -> str:
    """Qualitative description of support-vs-affliction — no raw numbers to leak."""
    m = a.margin
    if m >= 0.35:
        return "Supporting factors clearly outweigh the afflicting ones"
    if m >= 0.12:
        return "Supporting factors modestly outweigh the afflicting ones"
    if m > -0.12:
        return "Supporting and afflicting factors are roughly balanced"
    if m > -0.35:
        return "Afflicting factors modestly outweigh the supporting ones"
    return "Afflicting factors clearly outweigh the supporting ones"


def format_assessment_for_prompt(assessment: TopicAssessment) -> str:
    a = assessment
    lines = [
        f"[VERDICT — {a.topic} (deterministic; narrate, do not re-weigh)]",
        f"Direction: {a.direction.upper()}  |  Confidence: {a.confidence}",
        f"{_balance_phrase(a)}.",
    ]
    if a.dominant_supporting:
        lines.append("Dominant supporting factors:")
        for w in a.dominant_supporting:
            lines.append(f"  + {w.planet} ({w.role}) — {w.band} strength")
    if a.dominant_afflicting:
        lines.append("Dominant afflicting factors:")
        for w in a.dominant_afflicting:
            lines.append(f"  - {w.planet} ({w.role}) — {w.band} strength")
    if a.key_tension:
        lines.append(f"Key tension: {a.key_tension}")
    if a.sav_band:
        line = (
            f"Ashtakavarga: the primary house has {a.sav_primary_house} SAV bindus "
            f"({a.sav_band}; >=30 strong, <=25 weak). This strength is ALREADY weighed into "
            f"the direction above — do not treat it as a separate or contradicting verdict."
        )
        # When SAV and the lordship verdict diverge, tell the narrator how to reconcile.
        if a.sav_band == "strong" and a.direction == "challenged":
            line += (" Here the house itself is well-fortified, but its lords/karakas are "
                     "afflicted — so the foundation is sound while the activating planets struggle.")
        elif a.sav_band == "weak" and a.direction == "favourable":
            line += (" Here the lords/karakas are supportive, but the house itself is thinly "
                     "fortified — so the promise is real but the base is modest.")
        lines.append(line)
    if a.varga_notes:
        lines.append(f"Divisional ({a.varga}) cross-check:")
        for note in a.varga_notes[:4]:
            lines.append(f"  - {note}")
    lines.append(f"Timing: {a.dasha_timing}")
    lines.append(f"One-line verdict: {a.summary_line}")
    return "\n".join(lines)
