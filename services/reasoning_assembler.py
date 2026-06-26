"""
Reasoning Assembler — Phase 4.

Joins SignificatorResult + retrieved KB chunks into a structured ReasoningReport.
Every claim carries a source citation, or is explicitly flagged as ungrounded.
No LLM involved. The report is what the synthesis LLM receives instead of the raw chart.
"""
from dataclasses import dataclass, field

from models.knowledge import RerankedChunk
from services.rule_engine.engine import RuleEngineResult
from services.significator_engine import DashaActivation, SignificatorFactor, SignificatorResult


@dataclass
class ReportLine:
    """One interpretable fact with its source."""
    statement: str
    planet: str
    role: str
    kind: str                       # "supporting" | "afflicting" | "neutral"
    source_text: str = ""           # classical passage retrieved from KB
    source: str = ""                # e.g. "BPHS Ch.24 v.12"
    source_type: str = ""           # "public_domain" | "paraphrase" | "licensed" | ""
    grounded: bool = False          # False = no KB chunk found for this factor


@dataclass
class DashaLine:
    statement: str
    maha_lord: str
    antar_lord: str
    activation_strength: str
    source_text: str = ""
    source: str = ""
    grounded: bool = False


@dataclass
class YogaLine:
    yoga_name: str
    source_text: str = ""
    source: str = ""
    grounded: bool = False


@dataclass
class ReasoningReport:
    topic: str
    supporting: list[ReportLine] = field(default_factory=list)
    afflicting: list[ReportLine] = field(default_factory=list)
    neutral: list[ReportLine] = field(default_factory=list)
    dasha: DashaLine | None = None
    yogas: list[YogaLine] = field(default_factory=list)
    doshas: list[str] = field(default_factory=list)
    ungrounded_factors: list[ReportLine] = field(default_factory=list)  # factors with no KB source
    total_factors: int = 0
    grounded_count: int = 0


def _build_statement(factor: SignificatorFactor, varga: str) -> str:
    parts = [f"{factor.planet} ({factor.role})"]
    parts.append(f"in house {factor.placed_house} ({factor.sign})")
    parts.append(f"dignity: {factor.dignity}")
    if factor.functional_nature not in ("unknown", ""):
        parts.append(f"functional nature: {factor.functional_nature}")
    if factor.dig_bala:
        parts.append("Dig Bala")
    if factor.varga_dignity and varga != "D1":
        parts.append(f"{varga}: {factor.varga_dignity}")
    return " | ".join(parts)


def _find_chunk_for_factor(
    factor: SignificatorFactor,
    chunks: list[RerankedChunk],
) -> RerankedChunk | None:
    """Find the best-matching KB chunk for a significator factor.

    Matching priority:
    1. Chunk with planet + house match (planet_in_house)
    2. Lord-in-house match: a `lord_in_house` chunk keyed by (lorded house, placed house).
       House-lord chunks have empty planets_primary (they apply to whichever planet lords
       the house), so they must be matched by lordship + placement, not by planet.
    3. Chunk with planet + sign match
    4. Planet match with a good chunk type
    5. Any chunk mentioning the planet
    """
    planet = factor.planet
    house = factor.placed_house
    sign = factor.sign

    # Priority 1: planet+house
    for rc in chunks:
        c = rc.chunk
        if planet in c.planets_primary and house in c.houses_primary:
            return rc

    # Priority 2: lord-in-house (lordship + placement), for house-lord factors
    if factor.lords_house is not None:
        for rc in chunks:
            c = rc.chunk
            if (
                c.chunk_type.value == "lord_in_house"
                and factor.lords_house in c.houses_primary
                and house in c.houses_primary
            ):
                return rc

    # Priority 3: planet+sign
    for rc in chunks:
        c = rc.chunk
        if planet in c.planets_primary and sign in (c.signs or []):
            return rc

    # Priority 4: planet match with a good chunk type
    good_types = {"planet_in_house", "lord_in_house", "planet_in_sign"}
    for rc in chunks:
        c = rc.chunk
        if planet in c.planets_primary and c.chunk_type.value in good_types:
            return rc

    # Priority 5: any chunk mentioning the planet
    for rc in chunks:
        c = rc.chunk
        if planet in c.planets_primary:
            return rc

    return None


def _find_chunk_for_dasha(
    dasha: DashaActivation,
    chunks: list[RerankedChunk],
) -> RerankedChunk | None:
    """Find a dasha-specific chunk for the active maha+antar combination."""
    maha = dasha.maha_lord
    antar = dasha.antar_lord

    # Priority 1: both lords in a dasha chunk
    for rc in chunks:
        c = rc.chunk
        if c.chunk_type.value == "dasha_antardasha":
            if maha in (c.dasha_pair or []) and antar in (c.dasha_pair or []):
                return rc

    # Priority 2: mahadasha chunk
    for rc in chunks:
        c = rc.chunk
        if c.chunk_type.value in ("dasha_mahadasha", "dasha_antardasha"):
            if maha in c.planets_primary:
                return rc

    # Priority 3: any chunk mentioning the maha lord
    for rc in chunks:
        c = rc.chunk
        if maha in c.planets_primary:
            return rc

    return None


def _find_chunk_for_yoga(yoga_name: str, chunks: list[RerankedChunk]) -> RerankedChunk | None:
    for rc in chunks:
        c = rc.chunk
        if c.chunk_type.value == "yoga" and (c.yoga_name or "").lower() == yoga_name.lower():
            return rc
    # Fallback: any chunk with yoga name in content
    for rc in chunks:
        if yoga_name.lower() in rc.chunk.content.lower():
            return rc
    return None


def assemble(
    significators: SignificatorResult,
    chunks: list[RerankedChunk],
    rule_result: RuleEngineResult,
) -> ReasoningReport:
    """Assemble significators + KB chunks into a ReasoningReport."""
    report = ReasoningReport(topic=significators.topic)

    # --- Factor lines ---
    for factor in significators.factors:
        statement = _build_statement(factor, significators.relevant_varga)
        chunk = _find_chunk_for_factor(factor, chunks)

        line = ReportLine(
            statement=statement,
            planet=factor.planet,
            role=factor.role,
            kind=factor.kind,
            source_text=chunk.chunk.content if chunk else "",
            source=chunk.chunk.source if chunk else "",
            source_type=chunk.chunk.source_type if chunk else "",
            grounded=chunk is not None,
        )

        if factor.kind == "supporting":
            report.supporting.append(line)
        elif factor.kind == "afflicting":
            report.afflicting.append(line)
        else:
            report.neutral.append(line)

        if not chunk:
            report.ungrounded_factors.append(line)

    # --- Dasha line ---
    d = significators.dasha_activation
    dasha_chunk = _find_chunk_for_dasha(d, chunks)
    report.dasha = DashaLine(
        statement=(
            f"{d.maha_lord} Mahadasha / {d.antar_lord} Antardasha "
            f"(ends {d.antar_end}) — activation: {d.activation_strength}"
        ),
        maha_lord=d.maha_lord,
        antar_lord=d.antar_lord,
        activation_strength=d.activation_strength,
        source_text=dasha_chunk.chunk.content if dasha_chunk else "",
        source=dasha_chunk.chunk.source if dasha_chunk else "",
        grounded=dasha_chunk is not None,
    )
    if not dasha_chunk:
        report.ungrounded_factors.append(ReportLine(
            statement=report.dasha.statement,
            planet=d.maha_lord,
            role="mahadasha lord",
            kind="neutral",
            grounded=False,
        ))

    # --- Yoga lines ---
    for yoga_name in significators.relevant_yogas:
        yoga_chunk = _find_chunk_for_yoga(yoga_name, chunks)
        report.yogas.append(YogaLine(
            yoga_name=yoga_name,
            source_text=yoga_chunk.chunk.content if yoga_chunk else "",
            source=yoga_chunk.chunk.source if yoga_chunk else "",
            grounded=yoga_chunk is not None,
        ))

    # --- Doshas ---
    report.doshas = significators.relevant_doshas

    # --- Summary counts ---
    all_lines = report.supporting + report.afflicting + report.neutral
    report.total_factors = len(all_lines)
    report.grounded_count = sum(1 for l in all_lines if l.grounded)

    return report


def format_report_for_prompt(report: ReasoningReport) -> str:
    """Format the ReasoningReport into the [REASONING REPORT] prompt section."""
    if not report.supporting and not report.afflicting and not report.neutral:
        return ""

    lines = [f"[REASONING REPORT — {report.topic}]"]
    grounded_pct = int(report.grounded_count / report.total_factors * 100) if report.total_factors else 0
    lines.append(f"({report.grounded_count}/{report.total_factors} factors have classical sources — {grounded_pct}% grounded)")
    lines.append("")

    if report.supporting:
        lines.append("SUPPORTING FACTORS:")
        for line in report.supporting:
            lines.append(f"  + {line.statement}")
            if line.grounded:
                src_label = f"[{line.source_type}] " if line.source_type else ""
                lines.append(f"    Source ({src_label}{line.source}):")
                # Trim to ~300 chars to stay within token budget
                excerpt = line.source_text[:300].rsplit(" ", 1)[0] + "..." if len(line.source_text) > 300 else line.source_text
                lines.append(f"    \"{excerpt}\"")
            else:
                lines.append("    [NO CLASSICAL SOURCE LOADED FOR THIS FACTOR]")
        lines.append("")

    if report.afflicting:
        lines.append("AFFLICTING FACTORS:")
        for line in report.afflicting:
            lines.append(f"  - {line.statement}")
            if line.grounded:
                src_label = f"[{line.source_type}] " if line.source_type else ""
                lines.append(f"    Source ({src_label}{line.source}):")
                excerpt = line.source_text[:300].rsplit(" ", 1)[0] + "..." if len(line.source_text) > 300 else line.source_text
                lines.append(f"    \"{excerpt}\"")
            else:
                lines.append("    [NO CLASSICAL SOURCE LOADED FOR THIS FACTOR]")
        lines.append("")

    if report.neutral:
        lines.append("MIXED / NEUTRAL FACTORS:")
        for line in report.neutral:
            lines.append(f"  ~ {line.statement}")
            if line.grounded and line.source_text:
                excerpt = line.source_text[:200].rsplit(" ", 1)[0] + "..." if len(line.source_text) > 200 else line.source_text
                lines.append(f"    Source ({line.source}): \"{excerpt}\"")
        lines.append("")

    if report.dasha:
        d = report.dasha
        lines.append(f"DASHA / TIMING: {d.statement}")
        if d.grounded:
            src_label = f"[{d.source}] " if d.source else ""
            excerpt = d.source_text[:300].rsplit(" ", 1)[0] + "..." if len(d.source_text) > 300 else d.source_text
            lines.append(f"  Source ({src_label}): \"{excerpt}\"")
        else:
            lines.append("  [NO CLASSICAL SOURCE LOADED FOR THIS DASHA COMBINATION]")
        lines.append("")

    if report.yogas:
        lines.append("RELEVANT YOGAS:")
        for yoga in report.yogas:
            lines.append(f"  • {yoga.yoga_name}")
            if yoga.grounded:
                excerpt = yoga.source_text[:250].rsplit(" ", 1)[0] + "..." if len(yoga.source_text) > 250 else yoga.source_text
                lines.append(f"    Source ({yoga.source}): \"{excerpt}\"")
            else:
                lines.append("    [NO CLASSICAL SOURCE LOADED FOR THIS YOGA]")
        lines.append("")

    if report.doshas:
        lines.append(f"RELEVANT DOSHAS: {', '.join(report.doshas)}")
        lines.append("")

    if report.ungrounded_factors:
        ungrounded_names = list({l.planet for l in report.ungrounded_factors})
        lines.append(f"NOTE: {len(report.ungrounded_factors)} factor(s) have no classical source loaded "
                     f"({', '.join(ungrounded_names)}). The knowledge base needs these chunks.")

    return "\n".join(lines)
