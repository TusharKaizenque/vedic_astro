# Reasoning Layer — Deep Analysis & Improvement Plan (v2)

> Goal: make the deterministic reasoning layer genuinely *strong* — Parashari-accurate,
> able to answer **any** topic (not just career), and produce a **deterministic verdict**
> so the LLM only narrates, never judges.

---

## 1. What the pipeline does today (honest map)

```
question
  → intent_classifier (LLM)         : category + entities + topics
  → run_rule_engine (deterministic) : yogas, doshas, strengths, house lords,
                                       aspects, functional nature, dig bala
  → get_significators (deterministic): factors for the topic, each tagged
                                       supporting / afflicting / neutral
  → retrieve (vector + text)        : KB chunks matched to the factors
  → assemble (deterministic)        : ReasoningReport — every factor + its citation
  → prompt_builder                  : formats report, fences the LLM
  → synthesis (LLM)                 : writes prose "weighing factors honestly"
```

This is a real RAG + rule-engine architecture. The skeleton is correct. But the
**depth of the astrological reasoning is shallow**, and the **final judgment is still
delegated to the LLM** (rule 4 of the system prompt literally tells the model to "weigh
supporting vs afflicting factors honestly" — that *is* reasoning).

---

## 2. The target: how a real Parashari astrologer reasons about any bhava

For **any** topic the classical method is the same 8-step procedure:

1. **Identify** the bhava (house), its lord, and its karaka.
2. **Examine the bhava**: occupants, aspects (benefic vs malefic), conjunctions.
3. **Examine the bhava lord**: where it sits, its dignity, its aspects, its dispositor.
4. **Examine the karaka** the same way.
5. **Cross-check the varga** (D-9 marriage, D-10 career…): the bhava must be strong in
   *both* D-1 and the divisional chart.
6. **Weigh strength** — Shadbala / Ashtakavarga bindus / Vimsopaka — to decide *who wins*
   when factors conflict.
7. **Time it** — Vimshottari dasha of the significators + Saturn/Jupiter transits.
8. **Judge** — a graded verdict (favourable / mixed / challenged) with timing windows.

Today we do **1, 2 (partial), 3 (1 level only), 4**. We do **not** do 5, 6, 7, and 8 is
handed to the LLM. That is the gap.

---

## 3. Gap analysis (what's lacking, ranked by impact)

### Tier 1 — Reasoning depth (the core of the user's complaint)

| # | Gap | Why it matters | Fix |
|---|-----|----------------|-----|
| 1 | **No deterministic verdict.** Engine lists supporting/afflicting; the LLM decides the outcome. | The judgment is the reasoning. Right now the LLM still judges. | New `assessment_engine`: produces a graded verdict per topic from a documented classical rubric. |
| 2 | **No strength weighting.** "supporting" vs "afflicting" are categorical with no winner. | Can't resolve contradictions deterministically. | Add **classical** numeric strength (Shadbala-lite + Ashtakavarga bindus + Vimsopaka), not arbitrary points. |
| 3 | **Dispositor chain only 1 level.** We look at the house lord's placement, but not *its* dispositor, nor Bhavat-Bhavam, nor Argala. | This is the heart of Parashari logic. | `chain_analyzer`: follow lord → dispositor → strength; add Argala/Bhavat-Bhavam. |
| 4 | **No conjunction analysis.** Planets treated independently. | "10th lord conjunct 6th lord" is decisive for career; invisible today. | Detect same-house/same-sign conjunctions; feed into factor kind + yoga detection. |
| 5 | **Dasha analysis is binary.** Only "is the dasha lord a significator?" No analysis of *what the dasha lord itself signifies* by placement/lordship/dignity. | Dasha is the timing engine; this is the weakest high-value area. | `dasha_analyzer`: results of a period = f(lord's house, lordship, dignity, yogas, aspects). Add pratyantar. |
| 6 | **Aspect quality flattened.** A benefic's aspect and a malefic's aspect on the topic house are scored the same. | Jupiter aspecting the 7th saves a marriage; Saturn afflicts it. | Tag each aspector by functional + natural nature; weight accordingly. |
| 7 | **Malefics-in-upachaya mislabelled.** Saturn in 10th is *good* for career (3/6/10/11 rule), but `_classify_kind` flags malefic-in-afflicting-house generically. | Produces wrong verdicts. | Encode upachaya exception + maraka/dusthana nuance in classification. |

### Tier 2 — Coverage (answer all topics, not just career)

| # | Gap | Fix |
|---|-----|-----|
| 8 | **KB is career-only (41 chunks).** Every other topic = "[NO CLASSICAL SOURCE LOADED]". | Build KB verticals: marriage, wealth, health, education, children, spirituality — same 4-file pattern per topic. |
| 9 | **Only 10th-lord-in-house chunks.** No generic Nth-lord-in-house, planet-in-sign, planet-in-house, nakshatra, or conjunction chunks. | Add general combination libraries (reused across topics). |
| 10 | **Single topic per question.** `topic = topics[0]` drops compound questions ("career *and* marriage"). | Loop significators over all extracted topics; merge reports. |

### Tier 3 — Missing engines (precision & timing)

| # | Gap | Fix |
|---|-----|-----|
| 11 | **No transit (gochara) engine.** TRANSIT_QUERY + "next year 2027" questions can't be answered. | `transit_engine`: Saturn/Jupiter transit over topic houses & dasha lords for a target date. |
| 12 | **Divisional charts empty.** `divisional_charts = {}`; `varga_dignity` always "". | Fetch D-9/D-10 from Prokerala; wire into significators (step 5 above). |
| 13 | **Ashtakavarga unused.** Constants exist; no computation. | `ashtakavarga_engine`: Bhinna + Sarva bindus → real classical numeric signal for strength weighting. |

### Tier 4 — Correctness hardening

| # | Gap | Fix |
|---|-----|-----|
| 14 | **Functional-nature tables unverified for 11 lagnas.** If wrong, every classification downstream is wrong. | Expert-verify the table; un-skip the 11 lagna tests. |
| 15 | **Neecha-bhanga not fed into kind.** A debilitated-but-cancelled planet is still flagged afflicting. | Pipe neecha-bhanga result into significator classification. |
| 16 | **No regression tests on full reasoning output.** | Golden-chart fixtures with expected verdicts. |

---

## 4. The plan (phased, vertical-slice preserved)

### Phase A — Deterministic Verdict + Strength (highest leverage)  ✅ DONE
The single biggest fix: stop the LLM from judging.
- **A1. `strength_engine`** ✅ — classical Shadbala-lite per planet: Uchcha (exaltation),
  Naisargika (natural), Dig (directional), Cheshta (retrograde/motional), Paksha (lunar
  phase) balas in virupas, minus a combustion penalty; normalized to 0..1 and banded.
  Omitted components (Ayana/Hora/Tribhaga/etc., which need exact time-of-day) documented,
  not faked. `services/rule_engine/strength_engine.py` + 8 tests.
- **A2. `assessment_engine`** ✅ — consumes significators + strengths and emits a
  `TopicAssessment`: `direction` (favourable / mixed / challenged), `confidence`,
  `dominant_supporting/afflicting`, `key_tension`, `dasha_timing`, `summary_line`.
  Weighting = Shadbala strength × classical role hierarchy (lord > karaka > occupant >
  aspector), with yoga/dosha adjustment. Pure Python, deterministic.
  `services/assessment_engine.py` + 9 tests.
- **A3. Rewire synthesis prompt** ✅ — `[VERDICT]` block is now first in the prompt; the
  system prompt tells the LLM the verdict is FIXED and to narrate (not re-weigh) it.
  Wired through `chat.py` → `prompt_builder.build(..., assessment)`. Verified end-to-end:
  the response now opens with the deterministic verdict.

### Phase B — Reasoning Depth  ✅ DONE
- **B1. `dispositor_engine`** ✅ — dispositor chains (planet → its dispositor → … until
  own-sign/cycle), Argala (intervention from 2/4/11, virodha from 12/10/3), and
  Bhavat-Bhavam (Nth-from-Nth). Surfaced to the prompt as a `[DEEPER STRUCTURE]` block.
- **B2. `conjunction_engine`** ✅ — same-house planet detection + net benefic/malefic/
  mixed influence; nudges factor classification (`_apply_conjunction`).
- **B3. `dasha_analyzer`** ✅ — full Maha/Antar/Pratyantar lord analysis (placement,
  lordship, dignity, strength, functional nature, topic-significator status, aspects,
  yogas) → `[DASHA ANALYSIS]` block. (Verified: it surfaced "Sun Pratyantardasha
  activates career" even though Ketu maha/antar does not.)
- **B4. Aspect-quality** ✅ — `aspect_quality()` classifies an aspector benefic/malefic
  by functional-then-natural nature; aspectors classified accordingly.
- **B5. Fixed `_classify_kind`** ✅ — principled rewrite: neecha-bhanga counts as
  strength (fixed the "debilitated Moon" overstatement), upachaya malefics support
  (Saturn-in-10th no longer mislabelled), primary significators judged by strength not
  flat functional-malefic status (10th lord Saturn now neutral, not afflicting).
- **Bonus: robust topic resolver** ✅ — free-form classifier output ("professional life",
  "getting married") now normalizes to canonical topic keys instead of silently
  defaulting to house [1] and producing a confident wrong-topic verdict.

### Phase C — Topic Coverage (answer everything)  ✅ MOSTLY DONE
- **C1. Multi-topic** ✅ — `topic_pipeline.analyze_topics` resolves up to 2 topics and
  builds a full bundle per topic (significators → retrieval → report → verdict → dasha →
  chain), retrievals run concurrently. `prompt_builder` renders one verdict-led block per
  topic. Verified: "career and wealth" returns two distinct verdicts.
- **C2. KB verticals** ✅ — marriage, wealth, health, education, children, spirituality —
  4 files each (house-lords, house-significations, yogas, dashas), authored in parallel.
  **229 KB chunks total** (was 41), all embedded via Jina. Verified: marriage question
  surfaces Mangal Dosha + Jupiter karaka from the new KB.
- **Assembler lordship matching** ✅ — `lord_in_house` chunks have empty `planets_primary`
  (they apply to whichever planet lords the house); the assembler now matches them by
  (lorded house, placed house), so the house-lord KB is actually used. Added `lords_house`
  to the factor.
- **Topic resolver canonicalization** ✅ — synonyms ("job"/"profession"/"work") collapse to
  one canonical topic via keyword groups, so multi-topic doesn't double-count.
- **C3. General combination KB** ✅ — 108 **planet-in-house** + 108 **planet-in-sign**
  chunks (9 planets × 12 houses/signs), topic-agnostic, authored in parallel. Together
  they complete the assembler's grounding ladder: planet+house (priority 1), lord-in-house
  (priority 2), planet+sign (priority 3) all now have real cited content for any topic.
  KB is now **445 chunks**. (Nakshatra chunks remain a future add — blocked on Prokerala
  nakshatra fields coming back empty; needs a normalizer fix first.)

### Phase D — Precision Engines  ✅ D1 + D3 DONE, D2 DEFERRED
- **D1. `varga_engine`** ✅ — computes divisional-chart signs deterministically from the
  D-1 longitude (no API/ephemeris): D2, D3, D4, D7, D9, D10, D24 with the standard BPHS
  division rules. The significator engine's `varga_dignity` now uses it (was a dead stub).
  The assessment adds a **varga cross-check**: each significator's strength in the relevant
  varga (D-10 career, D-9 marriage…) corroborates or undermines its D-1 reading — `kind`-aware
  (strong varga helps a supporter, deepens an afflicter; weak varga eases an afflicter).
- **D3. `ashtakavarga_engine`** ✅ — Bhinnashtakavarga (per-planet bindus) and
  Sarvashtakavarga (per-sign totals) per BPHS Ch.66. Validated by two invariants: SAV
  total = 337 and the seven BAV totals (48/49/39/54/56/52/39). The assessment uses the SAV
  of the primary topic house as a classical numeric corroboration (>=30 strong → +margin,
  <=25 weak → −margin). Verified live: the 10th house's 30 bindus tipped career to favourable.
- **D2. `transit_engine`** — ⏳ DEFERRED. Gochara for "in 2027?" timing needs an ephemeris
  for arbitrary future dates. No ephemeris is installed, and adding one (pyswisseph) risks an
  ayanamsa mismatch with Prokerala's Lahiri — *wrong* transit results are worse than none.
  Needs a deliberate decision: either compute transits via Prokerala's own endpoint (keeps
  ayanamsa consistent) or add pyswisseph with Lahiri ayanamsa explicitly matched. Held for
  that call rather than guessed.

### Phase E — Hardening  ✅ DONE
- **E1.** ✅ Functional-nature verified for ALL 12 lagnas against classical invariants
  (every planet valid; exactly the six canonical yogakarakas; lagna lord never malefic;
  pure-dusthana lords malefic; table yogakarakas truly lord a kendra+trikona). Fixed a
  real bug — Aries Mars was marked "yogakaraka" but lords 1+8 (it's the lagna lord →
  benefic). Added `house_lords_for_lagna()` + `is_yogakaraka()` as the deterministic basis.
  The 11 skipped lagna tests are gone — replaced by ~60 passing invariant assertions.
- **E2.** ✅ Golden-chart regression tests: the full non-LLM pipeline (rule engine →
  strengths → significators → assessment) on a fixed chart, asserting direction,
  confidence, dominant factors, SAV, margin, and byte-for-byte determinism. Any future
  change that silently alters a verdict now fails a test.

---

## Status: Phases A, B, C, D, E all complete. 445 cited KB chunks across 7 topics +
## generic planet-in-house + planet-in-sign (full grounding ladder). LLM is a strict
## scribe (no internal scores leak). Remaining optional: nakshatra KB (needs normalizer
## fix for empty Prokerala nakshatra fields first). Test suite: 224 passed, 0 skipped.

---

## 5. Recommended sequencing

1. **Phase A** first — it directly answers "the LLM is still doing the reasoning."
   After A, the verdict is deterministic and the LLM is genuinely a scribe.
2. **Phase B** — deepens the reasoning that feeds the verdict.
3. **Phase C** — unlocks all topics (most visible user-facing win).
4. **Phase D** — precision/timing (needed for "should I X in 2027?" questions).
5. **Phase E** — correctness lock-in throughout.

A and B together are what make the reasoning "very powerful and accurate." C makes it
universal. D makes timing answers real. E keeps it honest.

---

## 6. Key design principle (resolving the "no scoring" tension)

The user previously said *no arbitrary additive scoring*. That still holds. The weighting
in A1 is **classical**: Shadbala, Ashtakavarga bindus, and Vimsopaka bala are numeric
systems *defined in BPHS itself*. Every number cites a rule. We are not inventing a
point system — we are computing the strength metrics the classics already specify, and
using them only to decide *which documented factor dominates* when two conflict.
