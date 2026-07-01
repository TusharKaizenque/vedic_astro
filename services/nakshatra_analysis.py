"""
Nakshatra analysis — the lunar-mansion layer for the technical (part 2) section.

Surfaces the janma (Moon) nakshatra and the nakshatra-lord *linkage* of the topic's main
significator. The linkage is a genuine predictive technique: a planet placed in a nakshatra
ruled by X channels its results through X — e.g. the 10th lord in a Jupiter-ruled nakshatra
ties the career to Jupiter's significations even if Jupiter is otherwise unrelated.
"""
from __future__ import annotations

from utils.nakshatras import nakshatra_lord, nakshatra_of, pada_of, profile_of, traits_of


_VOCATION_TOPICS = {"career", "profession", "job", "business", "vocation", "work"}


def format_nakshatra_section(chart, topic_bundles=None, broad: bool = False) -> str:
    moon = chart.planets.get("Moon")
    if moon is None:
        return ""
    jn = nakshatra_of(moon.longitude)
    prof = profile_of(jn)
    lines = ["[NAKSHATRA — lunar-mansion layer]"]
    # Full deity/symbol/vocation profile is whole-chart identity → reserve for broad readings.
    # BUT the vocational leanings are directly relevant to a CAREER question, so surface those
    # (only) when the topic is career-related, even on a focused reading.
    vocation_topic = any(
        getattr(b, "topic", "") in _VOCATION_TOPICS for b in (topic_bundles or []))
    detail = ""
    if prof and broad:
        detail = (f" Deity {prof.get('deity', '')}, symbol the {prof.get('symbol', '')}; "
                  f"natural vocational leanings: {prof.get('careers', '')}.")
    elif prof and vocation_topic and prof.get("careers"):
        detail = f" Natural vocational leanings (janma nakshatra): {prof['careers']}."
    lines.append(
        f"Janma (Moon) nakshatra: {jn} pada {pada_of(moon.longitude)}, ruled by "
        f"{nakshatra_lord(moon.longitude)} — core temperament: {traits_of(jn)}.{detail}"
    )
    # Nakshatra-lord linkage for the main significator of the first topic.
    if topic_bundles:
        sig = topic_bundles[0].significators
        main = sig.primary_houses[0] if sig.primary_houses else None
        lord = next((f.planet for f in sig.factors if f.lords_house == main), None)
        if lord:
            pos = chart.planets.get(lord)
            if pos:
                nl = nakshatra_lord(pos.longitude)
                lines.append(
                    f"The {main}th lord {lord} sits in {nakshatra_of(pos.longitude)}, ruled by "
                    f"{nl} — so its results are channelled through {nl}'s significations."
                )
    return "\n".join(lines)
