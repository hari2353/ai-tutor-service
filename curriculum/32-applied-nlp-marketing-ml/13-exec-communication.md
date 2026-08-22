# Presenting ML to Executives: Translating Metrics into Revenue, Uncertainty Without Losing the Room, the One-Slide Result

> **Track:** T32 Applied NLP & Marketing ML · **Time:** 2h · **Prereqs:** T32-bayesian-methods, T32-experiment-design, T32-marketing-measurement · **Updated:** 2026-08-02
> **Module id:** `T32-exec-communication` · **Tags:** communication, critical

## The 30-second version

An executive does not want your AUC, your precision-recall tradeoff, or your credible interval — they want the answer to "what happens to revenue/cost/risk if we do this," and your job is translating the statistical artifact into that currency before you walk into the room, not during it. The translation has a concrete mechanical form: take the confusion matrix (or the effect-size distribution, for a continuous outcome), attach a real dollar cost or value to each cell (cost of a false positive, value of a true positive, cost of a false negative), and report the expected dollar outcome of the decision, not the abstract classification metric — a model with 0.85 AUC and a model with 0.79 AUC can have identical business value if the cost structure only cares about the top decile, and an executive who hears "0.85 beats 0.79" without that context will make a worse decision than one who never saw either number. Presenting uncertainty without losing the room means leading with the point estimate and the decision it implies, then attaching the uncertainty as a bounded range with a stated confidence, not opening with caveats that read as "we don't actually know" — the failure mode in both directions is real: hiding uncertainty gets you blamed when reality diverges from a false-precision promise, and over-hedging gets you ignored in favor of whoever in the room sounds more certain. "Can you just make it more accurate" is almost never actually a request for a better model — it's a request for a decision to feel safer, and the correct response translates the request back into the actual lever available (a different threshold, a different cost tradeoff, more data, more time) rather than either quietly promising an accuracy number you can't guarantee or shutting the conversation down with a statistics lecture.

## Why this gets asked

Expedia's Marketing Content ML Science team sits exactly at the interface where a data science team's statistical output has to become an executive's spending decision — the interviewer has personally been in the room when a well-built model's results got misread, ignored, or oversold because the presentation didn't translate the statistics into the decision-maker's actual question. They want to know you can hold both halves at once: the statistical rigor to get the number right, and the communication discipline to make sure the number survives contact with a room that has ten minutes, a P&L to protect, and zero patience for a confidence-interval tutorial.

---

## Lineage: past → present → future

**What came before.** The default failure mode in data science communication for a long time — and still common — was "results-first" academic-style reporting: methodology, then results, then a conclusion buried at the end, mirroring how a research paper is structured. This works for an audience whose job is to evaluate the rigor of the method; it fails an executive audience whose job is to make a decision quickly and who will lose attention well before the conclusion if the answer isn't stated up front. Barbara Minto's Pyramid Principle (developed at McKinsey, 1970s, still the standard reference for structured business communication) formalized the alternative: state the answer first, then the supporting structure, then the detail — "answer first" rather than "evidence first, answer eventually." Cole Nussbaumer Knaflic's *Storytelling with Data* (2015) did the same work specifically for data visualization and quantitative communication, popularizing the discipline of stripping a chart down to the one comparison that matters instead of showing every dimension a dataset supports.

**Where it stands now.** "Answer first, uncertainty attached, decision-relevant framing" is close to settled best practice among experienced data science and analytics leaders presenting to executive audiences, though execution quality varies enormously across organizations and individuals — this is a skill, not a checklist, and the gap between knowing the principle and executing it under real time pressure and real stakeholder pushback is where most of the actual difficulty lives. The live tension is between honest uncertainty communication and organizational pressure toward false precision: many executive cultures reward confident, simple answers and implicitly punish "it depends" framing even when "it depends" is the statistically correct answer, which creates real pressure on practitioners to either oversimplify (dangerous) or over-hedge defensively (ineffective) rather than finding the calibrated middle. There's no fully settled consensus on exactly how to present a range/interval to a non-technical audience without either losing them in the math or implicitly overstating certainty — practitioners differ on whether to lead with a range, a point estimate plus range, or a scenario-based framing (best case / expected / worst case), and the right choice depends heavily on the specific audience and decision at hand.

**Where it's heading.** Structured decision-support formats — one-page "decision memos" with a stated recommendation, the key number, the confidence level, and the cost of being wrong in each direction, standardized as a template within an organization — are increasingly common in mature data organizations, moderate confidence this becomes more standardized rather than left to individual presentation style. AI-assisted translation of model output directly into business-metric framing (an internal tool that takes a model's confusion matrix and a cost table and auto-generates the expected-value framing) is a plausible, lower-effort direction given how mechanical the translation actually is — speculative as a widespread practice, but the underlying mechanical translation this module teaches is exactly the kind of repeatable transformation such tooling would encode.

---

## Mental model

The translation pipeline from statistical artifact to executive decision:

```
STATISTICAL ARTIFACT              TRANSLATION STEP                    EXECUTIVE-READY OUTPUT
(AUC, precision/recall,            attach real $ cost/value            "if we ship this, expected
 confusion matrix, credible        to each outcome cell,               net impact is $X, with a
 interval, p-value)                 multiply by base rate and            range of $Y-$Z depending
                                     volume                              on assumptions we're
                                                                          least sure about"

confusion matrix:                  cost table:                         expected value:
TP: correctly targeted             TP value: $V per correct target     n_TP * $V - n_FP * $C
FP: wasted targeting spend         FP cost: $C per wasted target        (report this number,
FN: missed opportunity             FN cost: $L per missed opportunity   not the raw AUC/precision)
TN: correctly skipped              TN value: $0 (no action, no cost)
```

The "one-slide result" as a fixed shape, not a style choice: **headline number (the decision-relevant answer) → confidence/range → the one thing that would change the answer → what you're asking for**. Everything else — methodology, model architecture, full metric tables — belongs in an appendix the executive can ask for, not the slide they see first.

---

## How it actually works

### Translating AUC/precision/recall into revenue

**The mechanical process.** AUC and precision/recall are properties of a model's ranking or classification quality in the abstract — they say nothing on their own about dollars, because dollars depend on what a false positive and a false negative actually cost *in this specific business context*, which the model's training objective never saw. The translation: build a cost/value table for the four confusion-matrix cells (or, for a ranked/continuous output, for a chosen operating threshold), multiply by the base rate and volume the model will actually see in production, and report the resulting expected value.

**Worked example.** A targeting model for a retention offer: `TP value = $40` (offer correctly given to a persuadable user who stays because of it — note this is an *uplift*-informed value, not just "user converted," per the causal-inference module's core point), `FP cost = $8` (offer cost wasted on a user who would have stayed regardless, or worse, a sleeping dog who churns because of it), `FN cost = $60` (a persuadable user churns because they didn't get the offer — often the most expensive cell, since customer lifetime value typically dwarfs a single offer's cost), `TN value = $0`. At a chosen threshold, if the model produces 10,000 predicted-positive users per month with a precision of 0.62 (6,200 true positives, 3,800 false positives) against a population where the recall captured 6,200 of an estimated 9,000 true persuadables (2,800 false negatives): expected value = `6,200*$40 - 3,800*$8 - 2,800*$60 = $248,000 - $30,400 - $168,000 = $49,600/month`. This is the number an executive needs — not "AUC is 0.83" — and it immediately shows that the false-negative cost (missed persuadables) is the dominant term, which tells you exactly where model improvement effort should go (recall on the persuadable segment, not precision generally) far more usefully than the AUC alone ever could.

**Why this changes the conversation.** Once cost is attached per cell, "should we raise the threshold" or "should we lower it" becomes a direct dollar tradeoff an executive can reason about and even push back on with their own business judgment (maybe they know FN cost is actually higher than your estimate, because they know something about customer LTV your model training data doesn't capture) — this is a *better* outcome than a black-box "trust the AUC" pitch, because it invites the executive into the part of the decision that's actually theirs to own (the cost assumptions), while keeping the part that's yours (the model's ranking quality) appropriately in the background.

### Presenting uncertainty without losing the room

**Lead with the point estimate and its implication, not the caveat.** "We expect this to generate $50K/month in incremental value" lands very differently — and is not dishonest — than opening with "well, there's a lot of uncertainty here, but..." The uncertainty belongs immediately *after* the headline, as a bounded range with a stated confidence, not as a hedge that undermines the headline before it's even landed: "$50K/month, with a range of $30K-$70K depending on how the retention offer's actual uplift compares to our test estimate — we're confident in the direction and the rough magnitude, less confident in the precise number."

**Attach uncertainty to the thing that actually drives the decision, not everything.** An executive doesn't need the full posterior distribution or every source of estimation error — they need to know the one or two assumptions that, if wrong, would flip the recommendation, and roughly how likely that is. This is a filtering job: as the presenter, you've already looked at every source of uncertainty; the executive needs the one that matters for their decision, not the full inventory.

**The two failure modes, both real.** Hiding uncertainty entirely (presenting a point estimate as if it were exact) sets up a predictable failure: reality diverges from the promised number, and the practitioner's credibility — and the team's — takes the hit for overpromising, not for the model being imperfect (which everyone should have expected). Over-hedging (leading with every caveat, refusing to commit to a headline number, answering "it depends" without saying what it depends on) gets the presenter talked over by whoever in the room is willing to sound more certain, even if that person's certainty is less justified — in a room with limited time and competing voices, calibrated confidence that's honestly stated beats both false precision and reflexive hedging.

### The one-slide result

**Fixed shape.** Headline number (the decision-relevant answer, in the audience's currency — dollars, not model metrics), the confidence/range around it, the single biggest driver of uncertainty (the "one thing that would change the answer"), and a clear ask (what decision or resource you're requesting). Everything else — full metric tables, methodology, model architecture, alternative approaches considered — goes in an appendix, available if asked, absent from the primary slide.

**Why one slide, specifically.** Executive attention in a typical review is measured in minutes, often less, and a slide dense with secondary information competes with the headline for attention rather than supporting it — every additional number on the primary slide is a chance for the room's attention to land on something other than the decision-relevant answer. This isn't about dumbing down the analysis; the full rigor still exists and still gets scrutinized (in the appendix, in a follow-up technical review, in the underlying documentation) — it's about sequencing what the room needs first.

**A common mistake to name explicitly.** Presenting the model's technical journey (what was tried, what didn't work, the final architecture) before the result inverts the Pyramid Principle's "answer first" structure and reads, to an executive audience, as either padding or evasion — even when the intent was to demonstrate rigor. State the answer, then let follow-up questions pull the methodology out, rather than pushing methodology at an audience that didn't ask for it yet.

### Handling "can you just make it more accurate"

**What the question usually actually means.** Almost never a literal request for a specific higher accuracy number — it's a proxy for "I'm not comfortable with the risk this decision carries," and treating it as a literal accuracy request (either promising a number you can't guarantee, or explaining precision-recall tradeoffs at length) usually fails to address the actual underlying concern.

**The translation response.** Reflect the concern back in decision terms: "Right now, at this threshold, we're trading X dollars of missed opportunity for Y dollars of wasted spend — we can shift that tradeoff (raise or lower the threshold) if the risk balance you're worried about is specifically false positives or false negatives, but that's a different lever than 'more accurate' in the abstract, since there's no free improvement that reduces both simultaneously without more data or a genuinely better model." This does three things at once: validates the underlying concern (their risk aversion is legitimate, not dismissed), gives them an actual lever they can pull (threshold/cost tradeoff) rather than a vague promise, and is honest about the real constraint (there isn't a free lunch called "more accurate" sitting unused).

**When more accuracy actually is available.** Sometimes the honest answer is "yes, and here's the cost/timeline" (more labeled data, more features, more model iteration time) — in that case, name the actual cost (dollars, calendar time, engineering effort) and let the executive make the real tradeoff (is the marginal accuracy worth the marginal cost) rather than promising it will happen without cost or timeline attached, which sets up the exact overpromise failure mode described above.

---

## Build it from scratch

```python
# untested sketch — confusion-matrix-to-dollar-value translator for exec-facing reporting
from dataclasses import dataclass

@dataclass
class CostTable:
    tp_value: float   # value of a correctly-identified positive (e.g. persuadable retained)
    fp_cost: float     # cost of a false positive (wasted spend, or worse, a "sleeping dog")
    fn_cost: float      # cost of a missed true positive (foregone value)
    tn_value: float = 0.0

def expected_business_value(n_tp: int, n_fp: int, n_fn: int, n_tn: int, costs: CostTable) -> dict:
    net_value = (
        n_tp * costs.tp_value
        - n_fp * costs.fp_cost
        - n_fn * costs.fn_cost
        + n_tn * costs.tn_value
    )
    dominant_term = max(
        [("TP value", n_tp * costs.tp_value),
         ("FP cost", n_fp * costs.fp_cost),
         ("FN cost", n_fn * costs.fn_cost)],
        key=lambda x: abs(x[1]),
    )
    return {
        "net_expected_value": net_value,
        "dominant_driver": dominant_term[0],   # tells you where model improvement effort matters
        "components": {
            "tp_value": n_tp * costs.tp_value,
            "fp_cost": -n_fp * costs.fp_cost,
            "fn_cost": -n_fn * costs.fn_cost,
        },
    }

def one_slide_summary(net_value: float, low: float, high: float, key_driver: str, ask: str) -> str:
    return (
        f"Expected impact: ${net_value:,.0f}/month "
        f"(range ${low:,.0f}-${high:,.0f} depending on {key_driver}).\n"
        f"Ask: {ask}"
    )
```

---

## How it's done in production

Mature data science organizations formalize this translation as a required artifact, not an ad hoc presentation choice: a standard "decision memo" or "impact summary" template (headline number, range, key driver of uncertainty, explicit ask) attached to any model or experiment result headed for an executive review, produced alongside — but separate from — the full technical write-up and model documentation. Some teams build the cost-table translation directly into their model evaluation tooling, so the expected-business-value number is generated automatically alongside the standard classification metrics rather than computed manually and inconsistently each time a result needs to be presented. Review cadences at mature organizations typically separate the technical review (where AUC, precision/recall, calibration plots, and methodology get scrutinized by peers) from the executive/business review (where only the translated, decision-relevant output is presented) — conflating the two audiences in one presentation is a common structural mistake.

| Symptom | Cause | Fix |
|---|---|---|
| Executive fixates on AUC/precision number instead of the business decision | Presentation led with the statistical metric instead of the translated dollar value | Rebuild the slide around the cost-table translation; move the raw metrics to an appendix |
| Model's promised impact doesn't materialize post-launch, credibility takes a hit | Point estimate presented without a stated range, so any divergence reads as a broken promise rather than expected variation | Always present a range with a stated confidence alongside the point estimate, framed before launch, not after |
| Room stops listening / talks over the presenter | Opened with caveats and uncertainty before stating the headline answer | Restructure to answer-first: headline number, then range, then the one key driver of uncertainty |
| Stakeholder asks "can you just make it more accurate" and the conversation stalls | Question treated as a literal accuracy request instead of a proxy for risk discomfort | Reframe explicitly in cost-tradeoff terms (threshold shift, or named cost/timeline for genuine improvement) |
| Executive pushes back with their own gut-feel number for a cost/value assumption | Cost table built entirely from the data team's assumptions with no stakeholder input | Treat cost-table assumptions as a collaborative input the business stakeholder should validate, not a black-box internal constant |
| Same result gets re-explained multiple times to different stakeholders with inconsistent framing | No standardized decision-memo template; each presentation reinvents the translation | Build the cost-table-to-dollar-value translation directly into standard evaluation/reporting tooling |

---

## Tradeoffs & when NOT to use it

- **Don't reduce every result to a single dollar number for an audience that specifically needs the technical detail** (a peer technical review, a model risk/compliance audit) — the one-slide, dollars-first format is for the executive-decision context specifically, not a universal replacement for rigorous technical reporting, which still needs to exist and be available.
- **Don't build a cost table unilaterally without stakeholder input on the cost/value assumptions** — the numbers you plug in (value of a true positive, cost of a false negative) are business judgments as much as they are model outputs, and presenting them as objective facts derived purely from the model overstates your own certainty about assumptions that are properly the business stakeholder's to own or at least validate.
- **Don't over-simplify a genuinely close or ambiguous call into a falsely confident headline number** — if the range is wide enough that the sign of the expected value is itself uncertain (could be positive or negative), say that plainly rather than picking a point estimate that implies more certainty than exists; "this could go either way, and here's what would tell us which" is sometimes the honest one-slide answer.
- **Don't treat "can you just make it more accurate" as always dismissible as a proxy question** — sometimes it's a legitimate, answerable request with a real cost/timeline, and reflexively reframing every instance as risk-discomfort rather than actually checking whether more accuracy is available and worth the cost is its own communication failure.

---

## Interview questions

### Q1 — Walk through how you'd translate a model's precision and recall into a dollar figure an executive can act on.
**Answer:** Build a cost/value table for each confusion-matrix cell (value of a true positive, cost of a false positive, cost of a false negative, value/cost of a true negative), multiply each by the count of that outcome the model actually produces at the chosen operating threshold and expected volume, and sum to get net expected value. Report that number, and identify which cell dominates the total — that tells you where model improvement effort actually matters, which AUC alone cannot.
**Follow-up trap:** *"What if you don't have reliable cost estimates for each cell?"* — say so explicitly and present a range under a few plausible cost scenarios rather than picking one arbitrary set of costs and presenting it as certain; the cost assumptions themselves are often the most debatable part of the translation and should be flagged as such.

### Q2 — Why can a model with a lower AUC have equal or greater business value than one with a higher AUC?
**Answer:** AUC measures ranking quality across the entire population uniformly; business value depends on the cost/value structure at the specific operating threshold actually used, which is often concentrated in a small slice of the population (e.g., only the top decile is actually targeted). A model that ranks that top decile especially well can have equal or greater business value than a model with better average ranking quality across the whole population but a worse top-decile ranking.
**Follow-up trap:** *"So should you stop reporting AUC to technical stakeholders too?"* — no; AUC remains useful for technical model comparison and diagnosing overall ranking quality — the point isn't that AUC is wrong, it's that it's the wrong number for an executive audience whose decision depends on threshold-specific business value, not overall ranking quality.

### Q3 — Describe the fixed shape of a "one-slide result" and why the order matters.
**Answer:** Headline number (in the audience's currency, not model metrics) first, then the confidence/range around it, then the single biggest driver of uncertainty, then a clear ask. Order matters because executive attention is limited and front-loaded — leading with methodology or caveats before the answer either loses the room before the answer lands, or reads as padding/evasion even when the intent was rigor.
**Follow-up trap:** *"Isn't leading with the answer before the evidence intellectually dishonest?"* — no, as long as the evidence and methodology remain available (in an appendix, in follow-up questions, in the technical write-up); it's a sequencing choice for a time-constrained decision-making audience, not a suppression of the underlying rigor.

### Q4 — How do you present statistical uncertainty (a credible interval, a confidence interval, model error) to an executive without either losing their trust or losing their attention?
**Answer:** Lead with the point estimate and its implication, then attach the range immediately after with a stated confidence level, framed around the decision ("we're confident in the direction and rough magnitude, less certain on the precise number") rather than opening with hedges. Attach uncertainty specifically to the one or two assumptions that could flip the recommendation, not an exhaustive inventory of every source of estimation error.
**Follow-up trap:** *"What if the range is wide enough that the recommendation could flip?"* — say that plainly rather than picking a point estimate that implies more confidence than exists; a wide range with an uncertain sign is itself the honest headline in that case, and naming what evidence would resolve the ambiguity is the useful next step, not forcing false precision.

### Q5 — An executive says "can you just make it more accurate?" How do you respond?
**Answer:** Treat it first as a proxy for discomfort with the current risk tradeoff, not a literal request — reframe in cost terms: "at the current threshold we're trading $X of missed opportunity for $Y of wasted spend; we can shift that balance if the specific risk you're worried about is false positives or false negatives" — this gives them an actual lever (threshold/cost tradeoff) rather than a vague promise. If genuine additional accuracy is available (more data, more model iteration), name the real cost and timeline rather than promising it will happen for free.
**Follow-up trap:** *"What if they insist they just want a higher number, not a tradeoff conversation?"* — hold the line honestly: there's no free improvement that reduces both false positives and false negatives simultaneously without more data, more time, or a genuinely better model — promising an accuracy number without naming what it costs sets up exactly the overpromise failure this module warns against.

### Q6 — What's the risk of hiding uncertainty versus over-hedging when presenting to executives, and how do you calibrate between them?
**Answer:** Hiding uncertainty (presenting a point estimate as exact) sets up a credibility failure when reality diverges from the promised number — and it will, because it's an estimate. Over-hedging (leading with caveats, refusing to commit to a headline, exhaustive "it depends" framing) gets the presenter talked over by more confident but less-justified voices in the room. Calibration: state the headline and its practical implication first, attach a bounded range with a stated confidence immediately after, and be specific about what the range depends on rather than vague about "uncertainty" in the abstract.
**Follow-up trap:** *"How do you know if you're over-hedging in a specific case?"* — if the caveats come before the headline number, or if there's no stated range/confidence level (just a general acknowledgment that "there's uncertainty"), that's a sign of unstructured hedging rather than calibrated communication.

### Q7 — Design the cost table for a retention-offer targeting model, and explain why the false-negative cost is often the dominant term.
**Answer:** TP value = value of correctly offering to a genuinely persuadable user who stays because of it (uplift-informed, per the causal-inference framing, not just "converted"). FP cost = wasted offer cost on a sure-stay or, worse, a "sleeping dog" who churns because of the offer. FN cost = a persuadable user who churns because they didn't get the offer — often the largest cell because customer lifetime value typically dwarfs the cost of a single offer, meaning a missed persuadable costs far more than a wasted offer costs.
**Follow-up trap:** *"If FN cost dominates, does that mean you should always lower the threshold to catch more positives?"* — not automatically; lowering the threshold increases both true positives and false positives, so the right move depends on the actual FP-to-FN cost ratio and the model's precision-recall tradeoff at each threshold — state the tradeoff explicitly rather than assuming the dominant cost term alone determines the right threshold direction.

### Q8 — Why should the cost/value assumptions in your business-translation table be treated as a collaborative input from the business stakeholder, not a purely internal data-science constant?
**Answer:** The dollar values attached to true positives, false positives, and false negatives are business judgments (customer lifetime value, brand-risk cost of a bad experience, opportunity cost of a missed sale) that the data science team often has to estimate but doesn't uniquely own — presenting them as objective facts derived from the model overstates certainty about assumptions that are properly the business stakeholder's domain to validate or correct.
**Follow-up trap:** *"What if the stakeholder's gut-feel cost estimate contradicts your data-derived one?"* — that's a legitimate, useful disagreement to surface explicitly rather than resolve unilaterally — it might reveal information the model's training data doesn't capture (a strategic reason a specific segment matters more than its measured LTV suggests), and the right response is investigating the gap, not defaulting to whichever number came from the more "rigorous-sounding" source.

### Q9 — You're presenting a model result where the range of expected outcomes spans from clearly negative to clearly positive — the sign itself is uncertain. How do you handle the one-slide format?
**Testing:** synthesis under a genuinely hard communication case.
**Answer:** Don't force a falsely confident point estimate — the honest headline in this case is that the expected value is genuinely uncertain in sign, stated plainly, followed immediately by what specific piece of evidence or additional data would resolve the ambiguity and how long/costly that would be to get. This is still a one-slide, answer-first structure; the "answer" is just "we don't know yet, and here's exactly what would tell us," which is a legitimate and often more valuable answer than a confident number that doesn't reflect the actual state of knowledge.
**Follow-up trap:** *"Won't executives be frustrated by 'we don't know'?"* — less frustrated by an honest "we don't know, here's how we'd find out" than by a confident number that later turns out wrong — the frustration risk from false precision is larger and comes later, when trust is on the line, not just attention.

### Q10 — A VP challenges your range as too wide and demands a single number for the board deck. What do you do?
**Testing:** whether the candidate can flex presentation format under pressure without compressing away the uncertainty the decision actually depends on.
**Answer:** Give them the single number — the point estimate — but attach it to the decision it implies and keep one line of context: the range, the dominant assumption driving it, and what evidence would tighten it. What you don't do is silently narrow the range to make the slide cleaner; if the width changes the decision (breakeven inside the interval, sign uncertainty), that fact is the headline. Offer scenario framing (best/expected/worst case) as a board-friendly format that preserves the spread without showing a statistics interval.
**Follow-up trap:** *"Isn't the customer always right about format?"* — format flexibility is right, epistemic compression is not; adapting shape (one number plus a range footnote, scenarios) while keeping the information the decision depends on is the calibrated middle, and conflating the two is exactly how overpromise credibility failures start.

---

## Red flags that fail you

- Leading a presentation with AUC, precision, or a p-value instead of the business-relevant dollar translation.
- Opening with uncertainty/caveats before stating the headline result.
- Treating "can you just make it more accurate" as either a literal request to fulfill unconditionally or a question to shut down with a statistics lecture.
- Presenting a point estimate with no stated range or confidence, setting up a credibility failure when reality diverges.
- Building a cost-table translation unilaterally with no stakeholder validation of the underlying value/cost assumptions.
- Putting methodology and technical journey before the headline answer on an executive-facing slide.
- Forcing false precision on a result where the sign of the expected outcome is genuinely uncertain.

---

## Cheat card

```
TRANSLATION   confusion matrix (or continuous outcome distribution) + $ cost/value per cell
              -> net expected value = n_TP*value - n_FP*cost - n_FN*cost + n_TN*value
              REPORT THIS, not AUC/precision/recall directly to an exec audience
              identify DOMINANT cost term -> tells you where model improvement actually matters
LOW AUC       can beat high AUC in $ value if the cost structure concentrates on a specific
              threshold/segment AUC (averaged across the whole population) doesn't capture
ONE SLIDE     fixed shape: headline $ number -> range/confidence -> single biggest uncertainty
              driver -> explicit ask. Everything else -> appendix. ANSWER FIRST (Minto Pyramid
              Principle), not methodology-first.
UNCERTAINTY   lead with point estimate + implication, THEN attach bounded range w/ stated
              confidence -- not caveats-first. Attach uncertainty to the 1-2 assumptions that
              could flip the recommendation, not an exhaustive inventory.
              risk A: hide uncertainty -> credibility hit when reality diverges
              risk B: over-hedge -> talked over by more-confident (less-justified) voices
"MORE         usually a proxy for risk discomfort, not a literal accuracy request.
ACCURATE"     reframe as cost tradeoff: "we're trading $X missed opp for $Y wasted spend at
              this threshold -- we can shift that balance" -- give them an actual lever.
              if genuine improvement is available: name the real $ cost / timeline, don't
              promise it free.
COST TABLE    TP/FP/FN/TN dollar values are BUSINESS judgments, not model outputs -- validate
              with the stakeholder, don't present as objective internal constants.
              retention example: FN cost (missed persuadable, LTV-sized) often >> FP cost
              (wasted single offer) -- name the dominant term explicitly.
```

## Sources

- Barbara Minto, *The Pyramid Principle: Logic in Writing and Thinking*, 1st ed. (London: Pitman Publishing, 1987); later eds. (Harlow: Prentice Hall / Financial Times Prentice Hall, 2002) — print; standard reference for answer-first structured business communication
- Cole Nussbaumer Knaflic, *Storytelling with Data* (2015) — standard reference for stripping quantitative communication to the decision-relevant comparison
- [StaffEng Guides — Will Larson](https://staffeng.com/guides) — practitioner essays on senior-engineer influence, including "Present to executives"; accessed 2026-08-23

## Changelog
- 2026-08-02 — created
