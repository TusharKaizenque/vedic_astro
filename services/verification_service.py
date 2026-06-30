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

import json
import logging
from dataclasses import dataclass

from config import settings
from utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)

_REVIEW_SYSTEM = """You are the senior reviewer for a Vedic astrology reading. You are given
the deterministic ANALYSIS BLOCKS (the ground truth) and a DRAFT reading written from them.

Judge the draft on two axes:
1. GROUNDING — does every astrological claim trace to a specific factor in the blocks (a named
   planet, house, dignity, yoga, planetary state, bhava-lord placement, or dasha)? Any claim
   not supported by the blocks, or that contradicts the locked chart facts, is a defect.
2. SPECIFICITY — is it about THIS chart, or is it generic horoscope filler that would fit
   anyone ("you are hardworking", "life has ups and downs", "stay positive")? Generic padding
   is a defect.

Also verify it still answers the user's actual question (timing questions must lead with the
time window) and keeps the same verdict/direction as the blocks.

Return ONLY JSON:
{"ok": true}                       if the draft is well-grounded AND specific — no changes needed
{"ok": false, "refined": "<the full corrected reading>"}   otherwise

When refining: keep everything the draft got right, keep the EXACT two-section format with the
same bold headers, cut the generic sentences, replace them with specific block-grounded ones,
fix contradictions, and never introduce a claim absent from the blocks. Do not mention this
review, the blocks, or bracket labels in the refined text."""


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
            temperature=0.2,
            max_tokens=2600,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception as exc:
        logger.warning("Verification pass failed (passing draft through): %s", exc)
        return ReviewResult(ok=True, text=draft, refined=False)

    if data.get("ok") is True:
        return ReviewResult(ok=True, text=draft, refined=False)
    refined = data.get("refined")
    if isinstance(refined, str) and len(refined) >= 40:
        logger.info("Verification pass refined the reading for specificity/grounding.")
        return ReviewResult(ok=False, text=refined, refined=True)
    # Malformed reviewer output → keep the draft rather than risk a worse/empty reply.
    return ReviewResult(ok=True, text=draft, refined=False)
