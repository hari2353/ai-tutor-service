# Placement Aptitude: Seating, Blood Relations, Direction Sense, Ranking, Series Tricks

> **Track:** T15 Interview Simulator · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-09-04
> **Module id:** `T15-aptitude-puzzles` · **Tags:** aptitude

**Runs under `tutor-mock` as round type `aptitude`. Not a boss round in the STAR sense: this is the written/online aptitude screen that Indian mass recruiters (TCS NQT, Infosys, Wipro, Accenture, Capgemini) and many product-company loops put BEFORE any technical round. It kills more candidacies than the technical rounds do, silently, at scale.**

## The round in 30 seconds

Thirty to sixty minutes of logic puzzles — seating arrangements, blood relations, direction sense, ranking/ordering, syllogisms, number series — where the test is speed and a fixed method, not intelligence. Every puzzle type has a canonical diagram technique that turns a five-minute head-scratcher into a ninety-second mechanical solve. A pass looks like: read the question once, draw the standard diagram for its type, fill in constraints in the order that fixes the most entities first, and never solve in your head what can live on paper. A fail looks like re-reading the question three times, working without a diagram, or running out of time at question 20 of 30. The clock is the opponent; the puzzles are just the medium.

## Format

- **30–60 minutes, 20–35 questions**, multiple choice, negative marking on some (TCS NQT: no negative; Infosys: varies by year; always check the pattern announced that cycle).
- **Question mix:** roughly 40% arrangement puzzles (linear/circular seating), 20% blood relations + direction sense, 20% series/coding-decoding, 20% syllogisms, ranking, misc.
- **What the test does:** filters at scale. A 30%-correct cutoff sounds low until you account for the time pressure — most candidates finish 60% of the paper.
- **What the test does not do:** measure anything technical. No follow-up, no partial credit for method.
- **The scoring is sectional in some exams** (quant / logical / verbal separately) — a zero on one section can void a strong other two.

## What is actually being tested

1. **Diagram discipline.** Whether the candidate can externalize constraints onto paper instead of holding them in working memory. This single habit is worth more than any cleverness in this round.
2. **Fix-first ordering.** Whether constraints get applied in the order that pins down the most entities earliest ("Q sits at position 3" before "R is somewhere left of S").
3. **Speed via pattern recognition.** Whether the solver recognizes the puzzle TYPE in the first five seconds and deploys the canned diagram, versus discovering the method fresh per question.
4. **Option elimination as a first resort.** Whether the solver checks options against partial constraints before completing the full arrangement — many questions die after half a diagram.
5. **Clock triage.** Whether the solver leaves a stalled puzzle at the 2-minute mark instead of defending sunk cost.

## Question bank

The canon types, each with the method, a worked example, and the trap.

### Type 1: Linear seating arrangement

**Q1 — P, Q, R, S, T sit in a row facing north. Q is to the left of R but to the right of P. Who is at the extreme left?**
- **Method (the line diagram):** Draw 5 slots `_ _ _ _ _`, mark the facing direction ABOVE the line (north = away from solver). Translate each clue to positional constraints immediately: "left of R, right of P" ⇒ P < Q < R in position order. S and T fill the remaining slots per their clues.
- **Strong:** Sketches slots, writes the inequality chain under it, answers P in ~40 seconds.
- **Weak:** Holds the chain in their head, re-reads the question twice, guesses.
- **Follow-up trap:** **Facing direction flips left/right.** A row facing SOUTH reverses every "left of" clue. The single most common systematic error; the diagram must carry the facing arrow, always.

**Q2 — Same row, but two people face north and three face south.**
- **Method (the facing-mix diagram):** Every seat gets an arrow (↑ or ↓) as its FIRST annotation. "Left of X" is evaluated from X's facing, not the solver's.
- **Strong:** Draws arrows before processing any positional clue.
- **Weak:** Treats left/right from the page's perspective — three of five clues silently inverted.
- **Follow-up trap:** "Immediate left" is X-relative; "second to the left of the north-facing end" is page-relative. Mixed frames in one question are designed to catch solvers who never wrote the arrows.

### Type 2: Circular seating

**Q3 — Six friends sit around a circular table facing the center. A is to the immediate right of B; C is opposite D.**
- **Method (the circle fix):** Draw the circle, ONE dot per person, and fix ONE person at the top position immediately — a circle has no anchor, so you must create one. "Facing center" ⇒ right of B = anticlockwise from B; left = clockwise.
- **Strong:** Fixes A at 12 o'clock arbitrarily, places B, uses "opposite" (3-seat gap on a 6-circle) as the second anchor, fills the rest.
- **Weak:** Draws no circle, or draws it but never fixes an anchor — every subsequent clue is relative to nothing.
- **Follow-up trap:** **Facing outward inverts the hands.** Everyone facing OUT ⇒ right becomes clockwise. The fix is identical to Q2: write the facing on the diagram before any positional clue.

**Q4 — Eight people, mixed facing (some toward center, some away).**
- **Strong:** Arrow per seat, then fix, then clues — the arrows are non-negotiable at this complexity.
- **Weak:** Even strong solvers lose this if they skip arrows; this is where the section's time dies.
- **Follow-up trap:** The question asks "who is to B's left" where B faces out and the solver's reference faces in — the answer options include the clockwise answer precisely to catch this.

### Type 3: Blood relations

**Q5 — A is B's father. C is B's sister. D is C's son. How is D related to A?**
- **Method (the family tree):** Standard symbols — square for male, circle for female (or +/−), horizontal line for marriage, vertical lines for children, one generation per horizontal row. Draw WHILE reading, one clause at a time; never solve relations in your head.
- **Strong:** Tree: A(+ above B), B and C siblings, C above D. D is two rows below A ⇒ grandson.
- **Weak:** Verbally chains "D is C's son, C is B's sister, so D is... B's nephew, and A is B's father so..." — one mis-step, no diagram to check against.
- **Follow-up trap:** **Paternal/maternal branch questions** ("how is D related to A's WIFE?") require the tree to include A's wife even though she was never a named clue — draw mentioned-but-unplaced relatives as empty nodes, don't drop them.

**Q6 — Pointing puzzles: "Pointing to a photo, X says: 'He is the son of my grandfather's only son.'**
- **Method:** Parse inside-out: "my grandfather's only son" = X's father (if X's grandfather has only one son, and X's father is a son, it must be him — UNLESS X's father has a brother, which "only son" excludes). Then "son of X's father" = X or X's brother. Photo shows a male ⇒ X's brother or X himself.
- **Strong:** Unwinds the possessive chain one hop at a time on paper.
- **Weak:** Solves pronoun chains verbally; gender errors ("he" heard as "she" under time pressure) are the standard killer.
- **Follow-up trap:** "Only son" is a constraint, not decoration — it excludes uncles. Options include the uncle answer for solvers who skipped it.

### Type 4: Direction sense

**Q7 — Ravi walks 10m north, turns right, walks 6m, turns left, walks 4m. Which direction is he facing?**
- **Method (the compass path):** Always draw. Start with a N-arrow at the start point. North → right turn = East → left turn = North. Mark each segment's direction as drawn.
- **Strong:** Path sketch takes 15 seconds, answer (North) is readable off the last arrow.
- **Weak:** Rotates mentally and answers South — the classic mental-rotation error that the answer options are built around.
- **Follow-up trap:** **The question asks the facing, not the displacement.** Options include the displacement direction (North-East-ish) for solvers who answered a different question than asked. Also: "starts facing north unless stated" is the convention — but verify the stem didn't state otherwise.

**Q8 — Distance/displacement variant: how far is Ravi from the start?**
- **Method:** Same path sketch, then coordinate math: net (x,y) displacement from segment vectors, distance = √(x²+y²). Recognize the 3-4-5 / 6-8-10 triples — setters love them.
- **Strong:** Writes (0,10) → (6,10) → (6,14), computes √(6²+14²), checks options.
- **Weak:** Adds the lengths (10+6+4=20m) — the always-wrong option that's always present.
- **Follow-up trap:** "Turns right" relative to CURRENT heading, not to north — each turn rotates with the walker.

### Type 5: Ranking and ordering

**Q9 — In a class, A ranks 7th from the top, 34th from the bottom. How many students?**
- **Method:** Total = rank_from_top + rank_from_bottom − 1 (A counted twice). 7+34−1 = 40. Write the formula ON the diagram as you use it — it prevents the +1/−1 error under time pressure.
- **Strong:** Formula, answer, done — 10 seconds.
- **Weak:** Draws 40 stick figures or guesses 41 (the classic off-by-one, which is always an option).
- **Follow-up trap:** Interchange variant ("A is 7th from top; B is 3 ranks below A; how many between B and the 40th-from-bottom student") — two formula applications chained; keep each on paper.

### Type 6: Number series & coding-decoding

**Q10 — 2, 6, 12, 20, 30, ?**
- **Method (the difference engine):** Write first differences under the series: 4, 6, 8, 10 ⇒ next diff 12 ⇒ 42. If first differences are not constant, second differences. This resolves 80% of series questions mechanically.
- **Strong:** Diffs on paper immediately.
- **Weak:** Stares at the series looking for the "pattern" as gestalt.
- **Follow-up trap:** Alternating/twin series (2, 3, 6, 7, 14, 15, ?) — odd and even positions are two interleaved series; first differences that oscillate wildly are the tell.

**Q11 — Coding: If FRIEND is coded as GSJFOE, how is CODED written?**
- **Method:** Compute the cipher from the pair FIRST (+1 per letter here), apply to the target. Never guess the rule from the answer options.
- **Strong:** Writes F→G, R→S under each letter pair, then applies +1 to C,O,D,E,D.
- **Weak:** Tries options against intuition.
- **Follow-up trap:** Position-based codes (letter value, reversed alphabet A↔Z) hide behind the same surface form; deriving from the given pair always beats pattern-guessing.

### Type 7: Syllogisms & Venn

**Q12 — All engineers are graduates. Some graduates are managers. Conclusions: (I) some engineers are managers. (II) All managers are graduates.**
- **Method (the minimal Venn):** Draw the smallest legal Venn: engineers ⊂ graduates, managers overlapping graduates but possibly NOT engineers. Check each conclusion against the drawn minimum: (I) not necessarily true (overlap may miss engineers entirely) ⇒ follows only if "some" can be zero ⇒ NO. (II) definitely false.
- **Strong:** Draws minimum-diagram, tests each conclusion mechanically.
- **Weak:** Judges by plausibility ("well, some engineer somewhere is probably a manager") — this is precisely the reasoning error the format tests.
- **Follow-up trap:** "Some X are Y" does NOT imply "some Y are X's complement" — minimal-diagram discipline catches what intuition misses.

### Type 8: Clocks, calendars, time

**Q13 — An angle-between-hands question (e.g., at 3:40).**
- **Method:** H = 30·h − 11·m/2 (with h=3, m=40: 90 − 220 = −130 ⇒ 130°). Memorize the two formulas (this and the coincidence schedule: hands coincide 22 times/day, at 12:00 then every ~65:27).
- **Strong:** Formula, plug, done.
- **Weak:** Draws the clock and estimates the angle visually — the options are spaced to punish estimation.
- **Follow-up trap:** The formula gives the SIGNED angle; the reflexive supplement (180−θ) is the other option. Check which is asked.

## Rubric

Score across the puzzle types: **2** = solves with the canonical diagram under 90s; **1** = solves slow or via options only; **0** = fails or skips.

| Type | Weight | The one thing that decides it |
|---|---|---|
| Arrangements (linear + circular) | ×3 | Facing-arrows written before any clue |
| Blood relations | ×2 | Tree drawn per clause; gender marks |
| Direction sense | ×2 | Path sketch; facing ≠ displacement |
| Series/coding | ×2 | Differences on paper; cipher derived from pair |
| Syllogisms/Venn | ×1.5 | Minimum-diagram, not plausibility |
| Ranking/time | ×1.5 | Formulas memorized (top+bottom−1, angle) |

**Passing bar:** weighted ≥ 60% AND at least one arrangement type at 2 — the arrangement family is 40% of every real paper.

## Score bands

- **80–100%** — Finish-with-15-minutes-left territory; the screen is a formality.
- **60–79%** — Passes typical cutoffs; time-triage is what's costing the tail of the paper.
- **40–59%** — Below most mass-recruiter cutoffs; diagram discipline is usually the whole gap.
- **<40%** — Method not yet learned; this is the most coachable round in the entire loop.

## Red flags

- **Solving without paper** — the head is not a valid diagram; every type exists to overflow working memory.
- **No facing-arrows on mixed-direction seating** — guaranteed inversion error on at least one clue.
- **Reading the question twice before drawing anything** — the re-read is the symptom; the missing diagram is the disease.
- **Defending a stalled puzzle past 2 minutes** — one stall costs three questions at the tail.
- **Answering displacement when facing was asked** — the options are built for this confusion.

## Time-management failures

- **30 minutes on the first big seating puzzle.** The paper's point distribution means three medium questions beat one hard one, every time.
- **Solving fully when options could eliminate.** Half a diagram plus options often answers the question; completion is a luxury.
- **Leaving syllogisms/series for "later" and never returning** — those are the FAST questions; leaving the fast ones last is backwards triage.

## Cheat card

- **Facing arrows first** on every seating/direction puzzle; left/right is always from the SITTER's perspective.
- **Fix one entity** in circulars; draw slots for linears; the inequality chain for relatives (P < Q < R) beats sentences.
- **Family tree:** one generation per row, +/− for gender, draw while reading clause-by-clause.
- **Direction:** path sketch, net-displacement coordinates, facing ≠ displacement, know 3-4-5.
- **Ranking:** total = top + bottom − 1.
- **Series:** first differences, then second; oscillating diffs ⇒ interleaved series.
- **Clock:** θ = |30h − 11m/2|; hands coincide 22×/day.
- **Syllogism:** draw the MINIMUM legal Venn; "some" never implies "all."
- **2-minute rule:** any puzzle past 120 seconds gets abandoned for options-elimination or skipped — the tail of the paper is worth more than this stall.

## Sources

- Puzzle-type taxonomy, canonical diagrams, and the facing-inversion traps: mined from the corpus's aptitude cluster (×116 crowd-weight, @pythonlifetelugu "Puzzle Solving Tricks", OCR-verified, mining/posts/DcSDgPFCZkt/; ×100-question companion set, mining/posts/DbQQEXuiSl6/), accessed 2026-09-04.
- Clock formulas and coincidence schedule: standard results, verifiable by derivation.
- Negative-marking and sectional patterns: company-cycle dependent — verify against the current year's announced pattern (e.g., TCS NQT pattern pages) before relying.

## Changelog

- 2026-09-04: First version, written from the mined aptitude cluster; eight canonical types with diagram methods. Boss profile.
