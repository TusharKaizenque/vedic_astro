# Reasoning Precision & Response Quality — Plan v3

> Goal: keep the deterministic reasoning, but (a) make it sharper and more concrete, (b)
> actually use the BPHS/Phaladeepika KB for *lived outcomes*, and (c) fix the response
> balance — today it's ~90% astrological mechanism and ~10% "what your life will look
> like." The reader should learn what their career/marriage will *be like*, supported by
> (not buried under) the technical reasoning.

---

## 1. Diagnosis — measured from the actual prompt

I dumped the real prompt the LLM receives for "what does my chart say about my career?".
It contains four technical blocks and almost no lived-outcome content:

- **[VERDICT]** — planet names, factor roles, SAV bindus, D10 cross-check
- **[DEEPER STRUCTURE]** — dispositor chain, argala, bhavat-bhavam
- **[DASHA ANALYSIS]** — "Ketu sits in 9th, lords no houses, dignity neutral…"
- **[REASONING REPORT]** — factor lines (dignity / functional nature / D10) + KB excerpts

Every block is *mechanism*. The only real-world content is inside the KB excerpts — and
those are **dasha-period chunks** ("the Mars Mahadasha spans 7 years…"), truncated, and
framed as `Source (BPHS): "…"`, which the model paraphrases as rules rather than as the
person's life.

### Root causes
1. **No life-outcome layer.** The engine outputs "Mars karaka, moderate strength" but
   never "drive and leadership; suited to competitive/technical fields." The translation
   from factor → lived meaning is left entirely to the LLM, which stays abstract.
2. **Wrong chunks dominate.** Retrieval surfaces *dasha-mahadasha* chunks (what each
   period does) over *career-nature* chunks (10th-lord-in-sign, planet-in-10th). The
   "what your career IS" content is under-weighted vs "what each dasha does."
3. **No synthesized signature.** The engine never concludes the career FIELD, NATURE,
   TRAJECTORY, or INCOME pattern — though it holds all the pieces (10th lord Saturn →
   dispositor chain → Mars in own sign; karakas; D10). The reader gets planets, not a job.
4. **No outcome vocabulary / domain maps.** There is no planet→profession,
   planet→temperament, house→life-area, or sign→nature mapping to produce concrete words.
5. **Prompt has no answer template.** Nothing forces "outcome first, mechanism as brief
   support," so the model walks the technical blocks top-to-bottom.

---

## 2. Target response (before → after)

**Before (today):**
> "The VERDICT for Career is FAVOURABLE… Mars (karaka) and Sun (karaka) modestly outweigh
> Venus (2nd lord) and Mercury (6th lord)… Ketu Mahadasha / Venus Antardasha… Venus sits
> in the 3rd house, lords the 2nd, 7th…"

**After (goal):**
> "Your career is fundamentally well-supported: you're built for competitive, hands-on or
> technical work — engineering, defense, surgery, real estate, or sport — where drive and
> initiative decide success (your strongest career planet, Mars, sits powerfully in its own
> sign). You lead rather than follow, and recognition does come.
>
> The recurring friction is around money and partnerships — earnings can be uneven and
> business relationships need care (Venus, ruling your income and partnership houses, is
> the main drag). So the pattern is: real achievement, but you'll work for the financial
> stability others get more easily.
>
> Timing: the current Ketu phase is inward and low-visibility for work — a time to build
> skill rather than launch. Career activates more directly from late 2026 (Venus
> sub-period) and especially under the Sun period. **Best concrete step: prepare now, make
> the visible moves from late 2026 onward.**"

~70% lived outcome, ~30% mechanism, every claim still traceable to the engine + KB.

---

## 3. The plan   —   STATUS: F, G, H, J done; I satisfied by the new architecture

### Phase F — Domain Knowledge Maps (the vocabulary of outcomes)   ✅ DONE
`utils/significations.py` — planet→professions, planet→traits, house→life-area, sign→nature.

### Phase G — Outcome/Signature engine   ✅ DONE
`services/outcome_engine.py` — `LifeOutcome` with field candidates, nature, trajectory,
income pattern, plain strengths/challenges, spouse traits. Deterministic; dignity-boosted
field ranking; challenges framed as friction areas (not the planet's positive traits).

### Phase H — Response composition   ✅ DONE (verified live)
`[LIFE OUTCOME]` leads the prompt as *rewrite material*; technical blocks moved under
`[THE ASTROLOGY BEHIND THIS]`. System prompt rewritten: two ~50/50 parts — **"In plain
language"** (flowing prose, NO planet/house names) + **"The astrology behind this"**
(cited technical evidence). Verified: part 1 is now jargon-free and concrete.

### Phase I — KB utilization   ✅ SATISFIED BY ARCHITECTURE
Plain outcomes come from the maps/engine (part 1); the KB supplies cited classical
passages in part 2. The assembler already prioritizes planet-in-house / lord-in-house /
planet-in-sign chunks over dasha chunks for factor grounding (Phase C3), so career-nature
content is no longer crowded out by period-effect chunks. (A future refinement: split each
chunk's "rule" vs "plain effect" text — deferred; low ROI now that G supplies plain effects.)

### Phase J — Precision   ✅ Amatyakaraka done; minor items deferred
`utils/jaimini.py` — Atmakaraka/Amatyakaraka by degree; AmK added as a career field
co-significator. Retrograde flavor + conjunction (occupant) blending already handled.
(Deferred minor: bhava-sandhi cusp blending — low value under whole-sign; combustion
severity tiers — strength already grades combustion.)

---

### Original plan detail (for reference)

### Phase F — Domain Knowledge Maps (the vocabulary of outcomes)
Deterministic maps that turn factors into concrete words. New `utils/significations.py`:
- **F1. planet → professions/fields** (Sun: government, administration, medicine; Mars:
  engineering, military, surgery, sports, real estate; Mercury: writing, commerce,
  software, accounting; …)
- **F2. planet → temperament/traits** (for personality & spouse description)
- **F3. house → life-area plain meaning** ("10th = your public work and standing", "7th =
  your spouse and close partnerships")
- **F4. sign → nature/element keywords** (Aries: assertive, pioneering; Taurus: steady,
  material; …)
All sourced from standard BPHS/Phaladeepika significations; documented.

### Phase G — Outcome / Signature Engine (synthesis precision)
New `services/outcome_engine.py` — turns the verdict + factors + maps into a structured,
plain-language `LifeOutcome` (still deterministic):
- **G1. Field/nature** — rank candidate fields from the planets influencing the topic
  house + its lord + karakas + D10 lord (career), weighted by strength.
- **G2. Trajectory** — steady-rise / late-bloom / volatile / struggle, from significator
  strength + dusthana/upachaya involvement + the dasha sequence.
- **G3. Income/result pattern** (career/wealth) — from 2nd & 11th lords and their strength.
- **G4. Strengths & challenges** in plain terms — top supporting/afflicting factors
  rendered through the maps ("drive & leadership" not "Mars karaka").
- Generalizes per topic: spouse signature (traits/background), wealth signature, etc.

### Phase H — Response Composition & Balance (the user's core ask)
- **H1. Answer template** the LLM must follow: **(1)** plain headline outcome → **(2)**
  nature/field → **(3)** strengths → **(4)** challenges/tension → **(5)** timing →
  **(6)** one concrete takeaway. Technical reasons appear as *brief parenthetical support*.
- **H2. Rewrite the synthesis prompt** to enforce outcome-first and a target balance
  (~70/30 lived/technical), with the `LifeOutcome` as the spine and the verdict/report as
  supporting evidence (not the script).
- **H3. Reorder the prompt** so `[LIFE OUTCOME]` leads and the mechanism blocks follow as
  "evidence", clearly labelled as support.

### Phase I — KB Utilization Upgrade
- **I1. Separate "rule" from "effect"** — split chunk content (or tag a `plain_effect`
  field) so the synthesizer can quote the lived effect, not the definitional rule.
- **I2. Retrieval rebalance** — for the *nature* narrative prefer planet-in-house /
  lord-in-house / planet-in-sign chunks; reserve dasha chunks for the *timing* section,
  so period-effects stop crowding out career-nature.
- **I3. Outcome grounding** — attach the best KB excerpt to each `LifeOutcome` statement
  (field, trajectory, challenge) so the plain-language claims stay cited.

### Phase J — Reasoning Precision hardening (accuracy)
- **J1. Bhava-sandhi** — flag planets near house cusps (results blend into the next house).
- **J2. Combustion severity tiers** & exact-degree avastha (deep vs marginal).
- **J3. Amatyakaraka** (Jaimini char karaka) as a co-significator for career field.
- **J4. Retrograde outcome nuance** in the maps (retro → unconventional/karmic expression).
- **J5. Conjunction blending** — when two planets conjoin a topic house, blend their field
  signatures rather than listing separately.

---

## 4. Sequencing & recommendation
1. **F → G → H first.** These directly fix the user's complaint: F gives the vocabulary,
   G synthesizes the concrete outcome, H makes the answer lead with it. After these, the
   response is balanced and concrete while staying grounded.
2. **I** next — makes the KB pull its weight for outcomes and stops dasha-chunk crowding.
3. **J** last — precision polish on top of an already-strong, readable answer.

F+G+H is the high-leverage core: it converts the existing deterministic reasoning into
lived, accurate, readable predictions without weakening the "every claim is grounded"
guarantee.
