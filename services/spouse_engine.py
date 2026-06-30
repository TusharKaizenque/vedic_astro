"""
Spouse Engine — a multi-dimensional, chart-specific portrait of the spouse/marriage.

Generic marriage readings fail because they lean on ONE factor (Venus / 7th lord), so every
chart gets the same adjectives. Classical Jyotish (BPHS, Jaimini, Phaladeepika, Saravali)
instead triangulates the spouse from several INDEPENDENT significators, each describing a
different dimension:

  • Inner nature / soul        ← Jaimini Darakaraka (the lowest-degree planet — unique per chart)
  • Outer character            ← the specific planets occupying / aspecting the 7th ("stamps")
  • Appearance & lived nature  ← Navamsa (D9) 7th house + its occupants ("the spouse's lagna")
  • Disposition & refinement   ← the 7th lord's sign, nakshatra, house and dignity
  • Family / social background ← the Upapada Lagna lord's dignity (Jaimini)
  • Origin / distance          ← 7th-lord & D9-7th sign modality, Rahu/12th links
  • Profession                 ← 10th-from-7th (the 4th house) + planets touching the 7th
  • Stability / longevity      ← 2nd-from-Upapada + D9 7th-lord placement

Because the Darakaraka, 7th-lord sign, D9-7th and Upapada all differ between people, the
combined portrait is individual — and where the factors CONVERGE the engine says so with
confidence; where they DIVERGE it presents them as distinct facets rather than averaging
them into mush. Fully deterministic; the LLM only narrates the result.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models.chart import NormalizedChart
from services.rule_engine.engine import RuleEngineResult
from services.rule_engine.strength_calculator import get_planet_strength
from services.rule_engine.strength_engine import PlanetStrength
from services.rule_engine.varga_engine import varga_sign
from utils.astro_constants import (
    NATURAL_BENEFICS, NATURAL_MALEFICS, SIGN_RULERS, ZODIAC_SIGNS,
)
from utils.jaimini import darakaraka
from utils.nakshatras import nakshatra_lord, nakshatra_of, traits_of
from utils.significations import PLANET_PROFESSIONS, SIGN_NATURE

# Darakaraka archetypes — the spouse's inner/soul nature. Richer than adjective lists so the
# narration has specific, non-interchangeable material to draw on.
_DK_ARCHETYPE = {
    "Sun": "authoritative, principled and proud at the core — a partner with a strong sense of "
           "self and status, often connected to leadership, government or a prominent family; "
           "self-respect matters greatly to them",
    "Moon": "emotionally attuned, nurturing and changeable within — a caring, home-oriented, "
            "sensitive partner whose moods and feelings shape the relationship's weather",
    "Mars": "driven, courageous and strong-willed within — a partner of physical energy and "
            "directness, often in a technical, athletic, defence or disciplined field; passion "
            "runs hot and friction is possible when wills clash",
    "Mercury": "youthful, clever and communicative at heart — a witty, intellectually restless "
               "partner, often younger-seeming, drawn to words, trade, analysis or business",
    "Jupiter": "wise, dignified and ethical at the core — a learned, generous, advisor-type "
               "partner, frequently well-educated or from a cultured, religious or principled "
               "background; values meaning and growth",
    "Venus": "refined, affectionate and aesthetic within — a charming, pleasure-loving, "
             "artistically inclined partner who prizes harmony, beauty and romance",
    "Saturn": "mature, serious and duty-bound at the core — a responsible, loyal, often older or "
              "old-souled partner, sometimes from a humbler or traditional background; love is "
              "shown through commitment and endurance rather than display",
}

# What a planet IN or ASPECTING the 7th "stamps" onto the spouse's visible character.
_SEVENTH_STAMP = {
    "Sun": "authority and pride — a commanding, status-conscious, somewhat ego-strong partner",
    "Moon": "softness and emotional expressiveness — attractive, moody, family-minded",
    "Mars": "force and heat — energetic and assertive but argument-prone; a strong-willed partner",
    "Mercury": "youth and wit — talkative, clever, business-minded, young at heart",
    "Jupiter": "wisdom and ethics — a dignified, well-meaning, generous, principled partner",
    "Venus": "beauty and refinement — attractive, romantic, pleasure-loving and sociable",
    "Saturn": "seriousness and maturity — dutiful and reserved, possibly older; can cool or delay",
    "Rahu": "unconventionality — a foreign, unusual, ambitious or boundary-crossing partner",
    "Ketu": "detachment — a spiritual, elusive or emotionally private partner",
}

_KENDRA = (1, 4, 7, 10)
_TRIKONA = (1, 5, 9)
_DUSTHANA = (6, 8, 12)


@dataclass
class Facet:
    label: str
    factor: str        # the chart factor it is grounded in
    text: str


@dataclass
class SpouseProfile:
    darakaraka: str = ""
    facets: list[Facet] = field(default_factory=list)
    convergence: str = ""
    profession_hints: list[str] = field(default_factory=list)


def _ord(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _idx(sign: str) -> int:
    return ZODIAC_SIGNS.index(sign) if sign in ZODIAC_SIGNS else 0


def _house_sign(lagna_idx: int, house: int) -> str:
    return ZODIAC_SIGNS[(lagna_idx + house - 1) % 12]


def _lord(sign: str) -> str:
    return SIGN_RULERS.get(sign, "")


def _dignity(planet: str, chart: NormalizedChart) -> str:
    pos = chart.planets.get(planet)
    if not pos:
        return ""
    return get_planet_strength(planet, pos.sign, pos.degree_in_sign)


def _dignity_phrase(dignity: str) -> str:
    d = dignity or ""
    if "exalt" in d or "own sign" in d or "moolatrikona" in d:
        return "well-disposed (this nature comes through cleanly and is a source of strength)"
    if "debilitat" in d:
        return "debilitated (this nature is present but strained — it can bring difficulty or a sense of something unfulfilled)"
    if "combust" in d:
        return "combust (the quality is somewhat eclipsed or under pressure)"
    if "enemy" in d:
        return "in an unfriendly sign (the quality is a little compromised)"
    return "moderately placed"


def _modality(sign: str) -> str:
    return SIGN_NATURE.get(sign, {}).get("modality", "")


def _arudha_idx(house_idx: int, lord_idx: int) -> int:
    """Arudha Pada (Jaimini): the sign as far from the lord as the lord is from the house.
    Exception: if it lands on the house itself or the 7th from it, take the 10th from there."""
    arudha = (2 * lord_idx - house_idx) % 12
    if arudha == house_idx or arudha == (house_idx + 6) % 12:
        arudha = (arudha + 9) % 12
    return arudha


def build_spouse_profile(
    chart: NormalizedChart, rules: RuleEngineResult, strengths: dict[str, PlanetStrength]
) -> SpouseProfile:
    prof = SpouseProfile()
    lagna_idx = _idx(chart.lagna_sign)
    lagna_long = lagna_idx * 30 + chart.lagna_degree

    # ── 1. Darakaraka — inner/soul nature ──────────────────────────────────────────────
    dk = darakaraka(chart)
    prof.darakaraka = dk
    if dk and dk in _DK_ARCHETYPE:
        dkp = chart.planets.get(dk)
        dignity = _dignity(dk, chart)
        nak = nakshatra_of(dkp.longitude) if dkp else ""
        nak_trait = traits_of(nak) if nak else ""
        dk_d9 = varga_sign(dkp.longitude, "D9") if dkp else ""
        d9_note = ""
        if dk_d9:
            dk_d9_dig = get_planet_strength(dk, dk_d9, 0.0)
            if "exalt" in dk_d9_dig or "own sign" in dk_d9_dig:
                d9_note = " In the Navamsa the Darakaraka is strong, so the bond is stable and matures well."
            elif "debilitat" in dk_d9_dig:
                d9_note = " In the Navamsa the Darakaraka is weak, so this nature is tested over the course of the marriage."
        txt = (f"The spouse's core nature is {_DK_ARCHETYPE[dk]} — this Darakaraka is "
               f"{_dignity_phrase(dignity)}.")
        if nak_trait:
            txt += f" Its nakshatra colours this with {nak_trait} qualities."
        txt += d9_note
        prof.facets.append(Facet("Inner nature (soul)", f"Darakaraka = {dk}", txt))

    # ── 2. The 7th house — outer character "stamps" ────────────────────────────────────
    seventh_sign = _house_sign(lagna_idx, 7)
    occupants = [n for n, p in chart.planets.items() if p.house == 7]
    aspectors = [p for p in rules.planets_aspecting_house.get(7, []) if p not in occupants]
    stamps = []
    for p in occupants:
        if p in _SEVENTH_STAMP:
            stamps.append(f"{p} sits in the 7th — {_SEVENTH_STAMP[p]}")
    for p in aspectors:
        if p in _SEVENTH_STAMP:
            stamps.append(f"{p} aspects the 7th — {_SEVENTH_STAMP[p]}")
    if stamps:
        prof.facets.append(Facet(
            "Outer character (7th-house stamps)",
            f"planets on the 7th ({seventh_sign})",
            "The visible personality of the partner is stamped by: " + "; ".join(stamps) + ".",
        ))
    else:
        prof.facets.append(Facet(
            "Outer character (7th-house stamps)", f"7th house ({seventh_sign}) empty",
            f"The 7th house ({seventh_sign}) is unoccupied and unaspected by planets, so the "
            f"partner's character is read mainly from the 7th lord and the Navamsa below — the "
            f"sign itself lends a {SIGN_NATURE.get(seventh_sign, {}).get('keywords', '')} tone.",
        ))

    # ── 3. The 7th lord — disposition & refinement ─────────────────────────────────────
    l7 = _lord(seventh_sign)
    l7p = chart.planets.get(l7)
    if l7 and l7p:
        l7_nak = nakshatra_of(l7p.longitude)
        l7_nl = nakshatra_lord(l7p.longitude)
        l7_keywords = SIGN_NATURE.get(l7p.sign, {}).get("keywords", "")
        house_note = ""
        if l7p.house in _DUSTHANA:
            house_note = (f" Placed in the {_ord(l7p.house)} (a difficult house), it can bring "
                          f"distance, delay or strain to the partnership.")
        elif l7p.house in _KENDRA or l7p.house in _TRIKONA:
            house_note = f" Placed in the {_ord(l7p.house)} (a supportive house), the partnership is well-anchored."
        prof.facets.append(Facet(
            "Disposition (7th lord)", f"{l7} in {l7p.sign}, house {l7p.house}",
            f"The 7th lord {l7} sits in {l7p.sign} ({l7_keywords}), so the partner carries that "
            f"colouring; it is {_dignity_phrase(_dignity(l7, chart))}. Its nakshatra ({l7_nak}, "
            f"ruled by {l7_nl}) flavours how the relationship unfolds.{house_note}",
        ))

    # ── 4. Navamsa (D9) 7th — appearance & lived nature ────────────────────────────────
    d9_lagna = varga_sign(lagna_long, "D9")
    if d9_lagna:
        d9_lagna_idx = _idx(d9_lagna)
        d9_7th_sign = ZODIAC_SIGNS[(d9_lagna_idx + 6) % 12]
        d9_7th_planets = [
            n for n, p in chart.planets.items()
            if n in _SEVENTH_STAMP and varga_sign(p.longitude, "D9") == d9_7th_sign
        ]
        d9_kw = SIGN_NATURE.get(d9_7th_sign, {}).get("keywords", "")
        occ = ("; ".join(f"{p} ({_SEVENTH_STAMP[p].split(' — ')[0]})" for p in d9_7th_planets)
               if d9_7th_planets else "no planets")
        d9_7th_lord = _lord(d9_7th_sign)
        lord_pos = chart.planets.get(d9_7th_lord)
        lord_note = ""
        if lord_pos:
            if lord_pos.house in _DUSTHANA:
                lord_note = " Its lord is in a difficult house, hinting at challenges in the lived day-to-day of marriage."
            elif lord_pos.house in _KENDRA or lord_pos.house in _TRIKONA:
                lord_note = " Its lord is well-placed, supporting a stable married life."
        prof.facets.append(Facet(
            "Appearance & lived nature (Navamsa D9 7th)", f"D9 7th = {d9_7th_sign}",
            f"Treating the Navamsa 7th as the spouse's own ascendant: it falls in {d9_7th_sign} "
            f"({d9_kw}), with {occ} there — this shapes the partner's appearance and the felt, "
            f"day-to-day nature of the marriage.{lord_note}",
        ))

    # ── 5. Upapada Lagna — family / social background ──────────────────────────────────
    twelfth_idx = (lagna_idx + 11) % 12
    twelfth_lord = _lord(ZODIAC_SIGNS[twelfth_idx])
    tl_pos = chart.planets.get(twelfth_lord)
    if tl_pos:
        ul_idx = _arudha_idx(twelfth_idx, _idx(tl_pos.sign))
        ul_sign = ZODIAC_SIGNS[ul_idx]
        ul_lord = _lord(ul_sign)
        ul_dig = _dignity(ul_lord, chart)
        if "exalt" in ul_dig or "own sign" in ul_dig or "moolatrikona" in ul_dig:
            bg = "a respectable, well-established, or higher-status family"
        elif "debilitat" in ul_dig:
            bg = "a humble, modest, or struggling family background"
        else:
            bg = "an ordinary, middle-standing family background"
        # 2nd-from-UL → sustenance / longevity of the marriage
        second_ul = ZODIAC_SIGNS[(ul_idx + 1) % 12]
        sec_occ = [n for n, p in chart.planets.items() if p.sign == second_ul]
        ben = [p for p in sec_occ if p in NATURAL_BENEFICS]
        mal = [p for p in sec_occ if p in NATURAL_MALEFICS]
        if ben and not mal:
            longevity = "benefics support the 2nd-from-Upapada, favouring a lasting, well-sustained bond"
        elif mal and not ben:
            longevity = f"malefics ({', '.join(mal)}) fall in the 2nd-from-Upapada, a classical caution about strain or distance in the bond"
        else:
            longevity = "the 2nd-from-Upapada is mixed, so longevity depends on effort"
        prof.facets.append(Facet(
            "Family / background (Upapada Lagna)", f"UL = {ul_sign}, lord {ul_lord}",
            f"The Upapada (marriage as a social institution) is {ul_sign}; its lord {ul_lord} is "
            f"{_dignity_phrase(ul_dig)}, pointing to a spouse from {bg}. On longevity: {longevity}.",
        ))

    # ── 6. Origin / distance ───────────────────────────────────────────────────────────
    l7_mod = _modality(seventh_sign)
    rahu_pos = chart.planets.get("Rahu")
    foreign = (rahu_pos and rahu_pos.house in (7, 12)) or l7_mod == "movable"
    if foreign:
        dist = ("Movable/Rahu links on the 7th suggest a spouse from a different town, region or "
                "background to your own — possibly a distant or cross-cultural match.")
    elif l7_mod == "fixed":
        dist = "Fixed signs on the 7th suggest a spouse from nearby — the same region or community."
    else:
        dist = "Dual signs on the 7th suggest a moderate distance — neither next-door nor far away."
    prof.facets.append(Facet("Origin / distance", f"7th sign modality ({l7_mod})", dist))

    # ── 7. Profession leanings ─────────────────────────────────────────────────────────
    fourth_sign = _house_sign(lagna_idx, 4)            # 10th-from-7th = the 4th house
    contributors = [p for p in (occupants + [l7, _lord(fourth_sign)]) if p]
    hints: list[str] = []
    for p in contributors:
        for job in PLANET_PROFESSIONS.get(p, [])[:2]:
            if job not in hints:
                hints.append(job)
    prof.profession_hints = hints[:5]
    if hints:
        prof.facets.append(Facet(
            "Likely field / work", "10th-from-7th + planets on the 7th",
            "The partner's work likely leans toward: " + ", ".join(prof.profession_hints) + ".",
        ))

    # ── 8. Convergence / confidence ────────────────────────────────────────────────────
    prof.convergence = _convergence(dk, occupants, aspectors, l7)
    return prof


_TONE = {
    "Saturn": "serious / mature / dutiful", "Mars": "strong / fiery / assertive",
    "Venus": "refined / romantic / sociable", "Jupiter": "wise / dignified / ethical",
    "Mercury": "youthful / clever / talkative", "Moon": "emotional / caring / changeable",
    "Sun": "proud / authoritative",
}


def _convergence(dk, occupants, aspectors, l7) -> str:
    """Vote a 'tone' from the independent significators; agreement → confident, single portrait.
    Each significator counts once (the 7th lord IS the 7th-sign lord, so it's not double-voted)."""
    votes: dict[str, int] = {}
    for p in [dk, l7, *occupants, *aspectors]:
        if p in _TONE:
            votes[p] = votes.get(p, 0) + 1
    if not votes:
        return ""
    top = max(votes.values())
    leaders = [p for p, v in votes.items() if v == top]
    if top >= 2 and len(leaders) == 1:
        return (f"CONVERGENCE: several independent significators agree on a "
                f"{_TONE[leaders[0]]} partner — describe this with confidence as the dominant theme.")
    if len(votes) >= 2:
        names = " + ".join(_TONE[p] for p in list(votes)[:3])
        return (f"DIVERGENCE: the significators point to a BLEND ({names}) — present these as "
                f"different facets (inner nature vs outer persona vs background), not a single label.")
    return ""


def format_spouse_profile_for_prompt(profile: SpouseProfile) -> str:
    if not profile.facets:
        return ""
    dk = profile.darakaraka or "the Darakaraka"
    lines = [
        f"[SPOUSE PROFILE — specific to THIS chart. AUTHORITATIVE for the spouse description; it "
        f"overrides every generic spouse rule. The spouse significator HERE is the Darakaraka "
        f"({dk}) plus the factors below — do NOT default to 'Venus = wife/spouse', and do NOT "
        f"describe Venus's sign/placement unless a facet explicitly names Venus. Rules:\n"
        f"1. LEAD the description with the 'Inner nature (soul)' facet — the {dk} Darakaraka IS "
        f"the spouse's essential character; the opening sentences must centre on it.\n"
        f"2. Then layer appearance, disposition, family/background, origin and work from the other "
        f"facets, in that priority. Honour the CONVERGENCE/DIVERGENCE note at the end.\n"
        f"3. Use ONLY the planets, signs, houses and aspects named in THIS profile. Do NOT name "
        f"the 7th house's sign or 7th lord unless a facet states it, and never invent a planet "
        f"being 'in/on/aspecting the 7th'.\n"
        f"4. No generic adjectives that would fit anyone; tie every trait to its named factor.]",
    ]
    for f in profile.facets:
        lines.append(f"- {f.label} [{f.factor}]: {f.text}")
    if profile.convergence:
        lines.append(profile.convergence)
    return "\n".join(lines)
