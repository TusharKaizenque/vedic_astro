"""
Verification pass (Phase 3) — a quality gate between the draft reading and the user.

A single reviewer call reads the DRAFT against the same deterministic analysis blocks the
draft was built from, and:
  - confirms every claim traces to a specific block factor (planet/house/dignity/yoga/dasha),
  - removes or rewrites generic horoscope-column filler ("you are hardworking, with ups and
    downs") that would fit anyone,
  - fixes any statement that contradicts the locked chart facts,
  - keeps the verdict and the answer-mode (timing-first, descriptive, etc.) intact.

If the draft is already specific and grounded it is passed through unchanged (cheap, common
case). Otherwise the reviewer returns a corrected final reading. This is what the user sees, so
genericness/contradictions are caught BEFORE delivery rather than logged after.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from config import settings
from utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)

# Plain-text protocol (NOT JSON): a full ~2000-token reading does not survive being embedded as
# a JSON string at a bounded max_tokens — it truncates/mis-escapes and silently falls back to
# the generic draft, defeating the pass. So the reviewer replies with either the word PASS or
# the corrected reading verbatim.
_PASS_TOKEN = "PASS"

_REVIEW_SYSTEM = """You are the senior reviewer for a Vedic astrology reading. You are given the
deterministic ANALYSIS BLOCKS (the ground truth) and a DRAFT reading written from them.

Judge the draft on two axes:
1. GROUNDING — does every astrological claim trace to a specific factor in the blocks (a named
   planet, house, dignity, yoga, planetary state, bhava-lord placement, or dasha)? Any claim not
   supported by the blocks, or that contradicts the locked chart facts, is a defect.
2. SPECIFICITY — is it about THIS chart, or generic horoscope filler that would fit anyone
   ("you are hardworking", "life has ups and downs", "stay positive")? Generic padding is a defect.

Also confirm it answers the user's actual question (a timing/"when" question must LEAD with the
time window) and keeps the SAME verdict/direction as the blocks.

OUTPUT — reply with ONE of exactly these two forms, and NOTHING else:
- If the draft is well-grounded AND specific AND answers the question: reply with the single
  word  PASS
- Otherwise: reply with the FULL corrected reading and nothing else (no preamble, no "REVISED:",
  no explanation) — start directly with the first section header.

When you correct, obey these output rules (same as the original writer):
- EXACTLY two sections, headers verbatim on their own line:
  **In plain language**   then   **The astrology behind this**
- Section 1 is plain language for a layperson: NO planet names, NO house numbers, NO Sanskrit,
  NO labels. Section 2 carries the technical detail (planets, houses, yogas, dasha, sources).
- Keep what the draft got right; cut generic sentences and replace them with specific,
  block-grounded ones; fix any contradiction with the locked facts; never add a claim absent
  from the blocks. Never print bracket labels or field names from the blocks."""


@dataclass
class ReviewResult:
    ok: bool
    text: str          # the final reading (draft if ok, else the refined version)
    refined: bool      # whether a correction was applied


async def review_reading(draft: str, analysis_blocks: str, question: str) -> ReviewResult:
    """Review the draft against the blocks; return the final (possibly corrected) reading.

    Degrades safely: on any reviewer error or empty/short draft, the original draft is returned
    unchanged so a reviewer hiccup never blocks or blanks the reading."""
    if not draft or len(draft) < 40:
        return ReviewResult(ok=True, text=draft, refined=False)
    user = (
        f"USER QUESTION:\n{question}\n\n"
        f"ANALYSIS BLOCKS (ground truth):\n{analysis_blocks}\n\n"
        f"DRAFT READING:\n{draft}"
    )
    try:
        resp = await get_llm_client().chat.completions.create(
            model=settings.openai_synthesis_model,
            messages=[{"role": "system", "content": _REVIEW_SYSTEM},
                      {"role": "user", "content": user}],
            temperature=0.0,   # deterministic review — don't reintroduce cross-ask drift
            max_tokens=3200,    # headroom for a full rewrite in plain text
        )
        out = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("Verification pass failed (passing draft through): %s", exc)
        return ReviewResult(ok=True, text=draft, refined=False)

    # PASS (allow trailing punctuation/explanation) → keep the draft unchanged.
    if not out or out.upper().startswith(_PASS_TOKEN):
        return ReviewResult(ok=True, text=draft, refined=False)
    # A real correction must look like a reading (has the section header). Otherwise keep the
    # draft rather than risk delivering reviewer chatter or a truncated fragment.
    if len(out) >= 80 and ("In plain language" in out or "**" in out):
        logger.info("Verification pass refined the reading for specificity/grounding.")
        return ReviewResult(ok=False, text=out, refined=True)
    return ReviewResult(ok=True, text=draft, refined=False)
