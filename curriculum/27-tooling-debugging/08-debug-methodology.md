# Debugging as a Discipline: Bisect the Space, Not the Code

> **Track:** T27 Tooling, Docker & Debugging Mastery · **Time:** 2.0h · **Prereqs:** None — foundational for every debugging module in this track
> **Module id:** `T27-debug-methodology` · **Tags:** debugging, critical

## The 30-second version

Debugging is search over a hypothesis space, not code reading — the code is where you look for evidence, not the thing you're directly trying to understand. A reliable, minimal reproduction is the precondition for everything else; without one, you're not debugging, you're guessing with extra steps, because you can't tell a fix from a coincidence. Every hypothesis has to be falsifiable — stated so an experiment could prove it wrong — or it isn't a hypothesis, it's a hunch you'll rationalize evidence to fit. The efficient search strategy is bisection: find a variable (a commit, an input size, a time window, a code path) that splits the remaining space roughly in half, run the cheapest experiment that discriminates between "bug is in this half" and "bug is in that half," and repeat — this is why `git bisect` converges in log(n) steps on a thousand-commit range instead of a linear scan, and the same log(n) discipline applies to bisecting inputs, time, and code paths, not just commits.

## Why this gets asked

Because the interviewer has watched an engineer burn four hours "debugging" by staring at code and changing things at random hoping something works, versus a different engineer who spent ten minutes establishing a repro and then closed in on the actual cause in three sharp experiments — and they want to know which instinct the candidate defaults to under pressure, especially on a bug they've never seen before, where there's no pattern-match to lean on and the discipline is the only thing that scales.

---

## Lineage: past → present → future

**What came before.** Early debugging was overwhelmingly print-statement and inspection-based: add output, rerun, read, repeat, with no formal model of what you were doing beyond "look until you see it." This worked passably on small, single-threaded programs a single person held in their head, and broke down as systems grew — a print-statement approach doesn't scale to a bug that only reproduces under concurrent load, across a distributed system, or after a specific sequence of stateful operations, because there's no efficient strategy behind the print statements, just persistence. The formal treatment that named what good debuggers were already doing intuitively is Andreas Zeller's *Why Programs Fail* (2005, 2nd ed. 2009), which framed debugging explicitly as an application of the scientific method: observe a failure, form a hypothesis consistent with the observation, derive a testable prediction from it, run an experiment, and refine or discard the hypothesis based on the result — repeating until the hypothesis fully explains the failure. This gave debugging a name for what separates systematic practice from trial and error, and it directly underlies automated tools (delta debugging, `git bisect`) built after it.

**Where it stands now.** The scientific-debugging framing (hypothesize, predict, test, refine) is close to universal consensus among experienced engineers as the *right* model, even where they don't use Zeller's specific vocabulary — what's not universal is practice under time pressure, where the discipline is the first thing skipped. The live disagreement isn't about the method, it's about where the expensive step actually is: some argue the bottleneck is almost always reproduction (once you can reliably trigger the bug, isolating the cause is comparatively mechanical), others argue that for genuinely nondeterministic or environment-dependent bugs (a race condition that needs specific hardware timing, a memory corruption that only manifests under specific allocator behavior) reproduction itself may be permanently unreliable and the practical skill is inferring cause from a single, unrepeatable occurrence using whatever evidence (a core dump, a trace, a log) survived it — this second camp is a real and growing minority position as distributed and concurrent systems get more common, not a fringe view.
 
**Where it's heading.** LLM-assisted root-causing is being actively integrated into debugging workflows in 2026 — feeding a stack trace, recent commits, and logs to a model to generate candidate hypotheses is genuinely useful as a hypothesis-generation accelerant (the models are good at pattern-matching "bugs that look like this are usually caused by X"), and this is real, shipping, and worth using. What's overclaimed: that this reduces the need for the falsifiability discipline itself — a model-generated hypothesis is exactly as untested as one a human guesses at, and still has to be stated precisely enough to falsify and then actually checked against a real experiment; treat AI-assisted hypothesis generation as a way to get more candidate hypotheses faster, not a way to skip verifying them.

---

## Mental model

```
DEBUGGING = SEARCH OVER A HYPOTHESIS SPACE, using bisection as the search strategy

               [ALL POSSIBLE CAUSES]
                       |
        pick a splitting variable (commit / input size / time / code path)
                       |
             run the CHEAPEST experiment that
             discriminates between the two halves
                       |
              -----------------------
              |                     |
        [bug in this half]   [bug in other half]
              |                     |
        repeat on the smaller,     (discard this half,
        now-narrowed space          it's provably not it)


THE THREE PRECONDITIONS, IN ORDER -- SKIPPING ANY ONE MAKES THE REST THEATER

1. RELIABLE REPRODUCTION       Can you trigger the failure on demand? If "sometimes" is the
                                honest answer, your first job is finding what "sometimes"
                                actually depends on (load? a specific input? a race window?)
                                -- NOT jumping to hypotheses about the cause yet.

2. FALSIFIABLE HYPOTHESIS      Stated so a SPECIFIC experiment could prove it WRONG.
                                "Something's wrong with the cache" is not falsifiable.
                                "The cache returns a stale value because invalidation on
                                write doesn't fire for keys written via the batch path"
                                IS falsifiable -- you can go check the batch path's
                                invalidation call, or reproduce with only the batch path.

3. CHEAPEST DISCRIMINATING     Between two remaining hypotheses, run the experiment that
   EXPERIMENT                  costs least (time, side effects, risk) while still
                                actually distinguishing which one is true -- not the
                                experiment that's easiest to set up regardless of whether
                                it discriminates anything.

WHY BISECTION BEATS LINEAR SCAN
  log2(1000 commits) ~= 10 steps.       1000 commits linearly ~= up to 1000 steps.
  Same math applies to input size, time windows, and code-path elimination --
  it's not a git-specific trick, it's binary search applied to causality.
```

## How it actually works

**Reproduction, mechanically, before anything else.** A reproduction isn't "I can make it fail eventually" — it's the smallest, most deterministic set of conditions (input, environment, sequence of operations) that triggers the failure reliably enough to run repeated experiments against. If the failure rate is 1-in-50 tries, that's not yet a usable repro; the actual first task is finding what correlates with the 1-in-50 (a specific concurrent request pattern, a specific data shape, memory pressure, time of day tied to a cron job) and narrowing until the rate is closer to 1-in-1 or at least high enough that ten experiments don't require five hundred runs. Zeller's own framing makes this the dominant cost in practice: most of the total time spent on a hard bug is reproduction, not the hypothesis-testing that follows it, precisely because every subsequent step depends on being able to cheaply re-trigger the failure to check whether a change fixed it or a hypothesis holds.

**Falsifiability, mechanically.** A hypothesis is a candidate explanation with a stated mechanism, precise enough that a specific test could return a result incompatible with it. "The database is slow" isn't falsifiable as stated — there's no experiment whose result would make you say "no, that's not it." "The `orders` table query is slow because it's doing a full table scan due to a missing index on `customer_id`, added in migration `047`" is falsifiable: `EXPLAIN ANALYZE` the query, look for a sequential scan node, check whether `047` actually added that index. If the plan shows an index scan already, the hypothesis is dead — not "partially right," dead — and the search resumes from the next candidate, not from patching the dead hypothesis to sort-of still be true. The discipline that separates good debuggers from bad ones under pressure is exactly this: killing a hypothesis cleanly on contrary evidence instead of rationalizing around it because you'd already started explaining the fix to someone.

**Bisection, mechanically, across four different axes.** (1) *Commit history* — `git bisect` between a known-good and known-bad commit, running an automatable check script at each bisected point (`git bisect run ./repro.sh`) collapses a thousand-commit range to ~10 test runs. (2) *Input size/shape* — for a bug that reproduces on a large input, minimize by removing half the input and checking if it still reproduces (this is literally delta debugging, Zeller's own automated generalization of the same idea, formalized as `ddmin`). (3) *Time* — for an intermittent production issue, narrow the window by checking whether it reproduces before/after a specific deploy, config change, or traffic pattern shift, the same halving logic applied to a timeline instead of a commit range. (4) *Code path* — for a single execution, bisecting means picking a point roughly halfway through the call stack or data flow and checking whether the corrupted/wrong state already exists there (if yes, the bug is upstream of that point; if no, it's downstream) — this is the manual version of what a debugger's conditional breakpoint or a strategically placed assertion gives you for free.

**Choosing the cheapest discriminating experiment.** Between two live hypotheses, the right experiment is the one that costs the least time/risk while still returning a different result depending on which hypothesis is true. A production-only bug where hypothesis A predicts "fails only under concurrent load" and hypothesis B predicts "fails on a specific malformed input regardless of load" — the cheap discriminator is replaying the exact malformed input single-threaded locally, not standing up a load test, because a load test costs more and doesn't actually distinguish the two hypotheses as cleanly (both could plausibly show something under load). Engineers who default to the most familiar tool (always reach for a profiler, always add print statements) rather than the experiment that actually discriminates waste cycles on evidence that doesn't move the search forward.

## Build it from scratch

A minimal worked bisection, both automated (commit history) and manual (input minimization), to internalize the mechanics:

```bash
# --- Axis 1: commit history, automated ---
git bisect start
git bisect bad                      # current HEAD is broken
git bisect good v1.4.0               # this tag was known-good
# git bisect now checks out the midpoint commit automatically
git bisect run ./repro.sh            # repro.sh must exit 0 (good) or 1 (bad), deterministically
# ~10 automatic checkouts + runs later, on a 1000-commit range:
git bisect view                      # shows the exact first-bad commit
git bisect reset

# repro.sh has to BE the reliable reproduction from precondition #1 --
# an intermittent repro.sh (sometimes exits 0 on a bad commit) corrupts the whole bisect

# --- Axis 2: input minimization (manual delta debugging) ---
# Start: a 500-line input file triggers a parser crash.
# Step 1: does the first 250 lines alone still crash it?  yes -> narrow to first 250.
# Step 2: does the first 125 lines still crash it?        no  -> bug needs lines 125-250 too
# Step 3: bisect within 125-250 the same way ...
# Converges to a ~5-10 line minimal repro in log2(500) ~= 9 steps, not 500 one-line-removals

# --- Axis 4: code-path bisection with an assertion, not a print statement ---
# Wrong state observed at the end of a 12-function call chain. Don't add prints to all 12.
# Pick function #6 (roughly the midpoint), assert the invariant there:
assert account.balance >= 0, f"already negative at midpoint: {account.balance}"
# If it fires: bug is in functions 1-6.  If it doesn't: bug is in functions 7-12.
# Repeat the halving within whichever side is implicated. log2(12) ~= 4 checks, not 12.
```

## How it's done in production — failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Hours spent "debugging," no narrower understanding of the cause than at the start | No reliable reproduction was ever established; every attempted fix is being judged against an unreliable, inconsistent trigger | Stop hypothesizing about cause; spend the next block of time exclusively on narrowing what makes the failure reproduce more consistently (input, load, timing, environment) before touching a single line meant to "fix" it |
| A fix is deployed, the bug "seems" gone, then recurs weeks later | The original hypothesis was never actually falsified against a clean experiment — the fix coincided with the bug not recurring for unrelated reasons (lower load, different input distribution) and was mistaken for causation | Before declaring a fix confirmed, reproduce the original failure with the fix reverted (confirm it still fails) and then with the fix applied (confirm it now passes) against the SAME reproduction, not a different manual retest |
| `git bisect run` reports a "first bad commit" that turns out to be unrelated | `repro.sh` wasn't actually a deterministic pass/fail check — it passed or failed somewhat independent of the actual bug (flaky test, environment-dependent, wrong exit code semantics) | Verify repro.sh alone, repeatedly, at both the known-good and known-bad commits before trusting an automated bisect run across the full range |
| A hypothesis keeps getting "refined" instead of discarded after contrary evidence | Sunk-cost attachment to an explanation already partially communicated to others, or to the theory that took longest to form | Treat a clean falsification as final for that specific hypothesis; form a genuinely new hypothesis rather than patching the old one to still technically fit the new evidence |
| An intermittent production bug is "debugged" entirely from logs added after the fact, with no repro at all | Reproduction was deemed impossible up front (assumed too costly/rare) without seriously attempting to narrow the trigger conditions first | Before conceding a bug is unreproducible, spend real effort correlating occurrences against every available dimension (deploy time, traffic shape, specific customer/tenant, time of day, concurrent request volume) — many "unreproducible" bugs are actually under-investigated, not truly nondeterministic |
| Delta-debugging a crash-inducing input takes as long as reading the whole parser would have | Minimization done by removing one line at a time (linear) instead of halving (bisection) | Always halve the remaining candidate input/space per step; if a step doesn't roughly halve the search space, it's not actually bisection, it's a slower linear scan wearing bisection's name |

## Tradeoffs & when NOT to use it

- **Don't over-invest in reproduction-perfecting for a trivial, obviously-caused bug.** If the stack trace alone unambiguously names the cause (a null-pointer at a specific well-understood line, a config value that's obviously wrong), spending an hour building a minimal repro before fixing a one-line, low-risk change is process for its own sake — calibrate reproduction investment to how uncertain the cause actually is.
- **Don't treat every debugging session as requiring formal hypothesis notation.** The discipline matters most exactly when you're stuck or when the fix is expensive/risky to deploy and verify; for a five-minute fix to an obvious typo, "hypothesize, predict, test" is the right *shape* of thinking even if you never write it down explicitly.
- **Bisection assumes monotonicity — that the property you're checking flips exactly once across the range.** `git bisect` on a range with multiple independent bugs, where "good" and "bad" don't correspond to a single clean boundary, will report a misleading first-bad commit; check that the failure you're bisecting for is actually the same failure at both ends of the range before trusting the result.
- **For genuinely nondeterministic failures (real race conditions, hardware-timing-dependent bugs) a perfect reproduction may not be achievable at all**, and insisting on one before making any progress can stall investigation indefinitely — the fallback is inferring cause from whatever evidence a single occurrence left (a core dump, a trace, exhaustive logging added preemptively) combined with a plausible mechanism, acknowledging explicitly that the hypothesis is less rigorously confirmed than one verified by repeated reproduction.

---

## Interview questions

### Q1 — Define debugging in one sentence that a first-year CS student and a principal engineer would both find true.
**Testing:** whether the candidate has an actual model versus "finding and fixing bugs" as a non-answer.
**Answer:** Debugging is searching a space of possible causes for a failure by forming falsifiable hypotheses and running experiments that discriminate between them, using a reliable reproduction as the substrate every experiment runs against.
**Follow-up trap:** *"Where does 'reading the code carefully' fit into that definition?"* — it's how you generate hypotheses (candidate causes to test), not how you confirm one; reading code carefully without ever running an experiment against a hypothesis is closer to code review than debugging, and can produce a plausible-sounding wrong answer with the same confidence as a right one.

### Q2 — A bug reproduces "most of the time" — maybe 7 times out of 10 tries. Is that a usable reproduction? What do you do first?
**Answer:** It's usable but not ideal — 30% failure-to-reproduce means roughly 3 in 10 experiments will give a false "didn't reproduce" reading, muddying every subsequent test's interpretation. Before forming cause hypotheses, spend effort correlating the 3 misses against something (load at the time, specific input variant, timing) to see if the 70/30 split itself resolves into a cleaner deterministic condition, which usually costs less than repeatedly re-running a noisy experiment to compensate statistically.
**Follow-up trap:** *"You correlate it and find no pattern — it really is 70/30 with no discernible cause. Now what?"* — proceed with the noisy repro but compensate methodologically: run each experiment enough times to be confident about the result given the known noise rate (if a fix hypothesis predicts the failure should disappear entirely, one success isn't confirmation — run it enough times that a 70% underlying failure rate would very likely have shown up again if the fix didn't actually work).

### Q3 — Explain why "let's add some logging and see what happens" is not, by itself, hypothesis-driven debugging.
**Answer:** Adding logging without a stated prediction of what the logs should show under each candidate cause is observation without a filter — you'll get output, but without first committing to "hypothesis A predicts the log will show X, hypothesis B predicts Y," you risk post-hoc rationalizing whatever the log actually shows into support for whichever theory you already favored. The fix isn't avoiding logging, it's stating the prediction before you look.
**Follow-up trap:** *"So is logging ever the right first move, without a hypothesis yet?"* — yes, specifically for establishing a reproduction or characterizing a completely unknown failure (step 1, not step 2) — logging to understand *what's happening at all* before you have any candidate hypothesis is legitimate; logging as a substitute for stating and testing a hypothesis once you already have candidates is the actual anti-pattern.

### Q4 — Why does `git bisect` converge in roughly log2(n) steps, and what specifically has to be true about the commit range for that to hold?
**Answer:** Each bisect step eliminates half the remaining candidate commits by checking a single midpoint, the same halving logic as binary search over a sorted array — for n=1024 commits that's exactly 10 checks instead of up to 1024. It requires monotonicity: exactly one transition from "good" to "bad" across the ordered range, with no commit past the transition point reverting to good and no commit before it already exhibiting the bug.
**Follow-up trap:** *"The range contains two unrelated bugs, one introduced early and fixed later, another introduced near the end. What happens to your bisect result?"* — the monotonicity assumption is violated (good -> bad -> good -> bad, not a single clean transition), so `git bisect`'s reported "first bad commit" will be unreliable or simply wrong depending on where the midpoints happen to land; the fix is confirming, at the start, that the SAME specific failure (not just "some failure") is present at the bad end and absent at the good end before trusting an automated bisect across that range.

### Q5 — You form a hypothesis, run the falsifying experiment, and the result contradicts your hypothesis. What's the correct next action, and what's the tempting wrong one?
**Answer:** Correct: discard the hypothesis entirely and form a new one informed by the new evidence, rather than salvaging the old explanation. Tempting and wrong: patch the hypothesis with an ad hoc exception ("it's mostly that, except in this case, plus this other factor") that makes it unfalsifiable again by construction, especially once you've already started explaining the theory to a teammate or manager and feel invested in it being right.
**Follow-up trap:** *"Your manager already told the team 'we found it, it's the cache' before your falsifying experiment came back negative. How does that change what you do?"* — nothing about the debugging process changes; the social cost of being wrong publicly is real but irrelevant to whether the hypothesis is true, and continuing to search based on actual evidence (rather than defending a prematurely-announced conclusion) is the harder but only correct path — flag the correction early rather than quietly continuing to search while the wrong explanation stands uncorrected.

### Q6 — A parser crashes on a specific 3000-line config file. Walk through minimizing this to a usable bug report using delta debugging, and give the approximate number of steps.
**Answer:** Halve the file — check if the first 1500 lines alone still crash it. If yes, discard the second half and repeat on 1500; if no, the bug needs content from both halves, so try a different split (e.g., keep first 750 + last 750) or fall back to isolating which removed section mattered. Converges to a minimal reproducing subset in roughly log2(3000) ≈ 12 steps rather than up to 3000 one-line removals, assuming each step's crash/no-crash result is checked against the same deterministic repro condition each time.
**Follow-up trap:** *"After several halvings you reach a 6-line file that crashes, but removing ANY further line makes it stop crashing, and none of the 6 lines individually looks related to the actual root cause you'd guess from the stack trace. What does that tell you?"* — the minimal failing input has converged on the *minimal triggering condition*, which doesn't have to resemble the eventual root cause narratively — it's common for a minimized repro to look unrelated to the real mechanism (a specific combination of otherwise-unremarkable lines can trigger a parser edge case) — the next step is reading the parser's actual handling of that specific 6-line combination, not doubting the minimization because it "doesn't look like" the expected cause.

### Q7 — Contrast reproduction-first debugging with "read the stack trace, form a theory, patch it" for a null-pointer exception in production. When is the shortcut actually fine?
**Answer:** For a null-pointer exception where the stack trace unambiguously identifies the exact line and the missing-null-check fix is obviously safe and low-risk, spending time building a full minimal reproduction before applying an evident, low-risk fix is wasted process — the shortcut is fine specifically when the cause is unambiguous from static evidence alone and the fix carries negligible risk of being wrong or masking a deeper issue.
**Follow-up trap:** *"The null pointer is in a widely-shared utility function called from forty places. Does that change your answer?"* — yes: even though the immediate cause (missing null check) might still be obvious, the blast radius means you now need to understand why null reached this specific call site to confirm this isn't symptomatic of a upstream contract violation (something is passing null where it shouldn't be able to) rather than a genuine "sometimes this can legitimately be null" case — that broader question does need at least a lightweight reproduction/trace of the actual calling path, even if the immediate patch is one line.

### Q8 — What's the difference between "the bug is unreproducible" and "the bug is under-investigated," and how do you tell which one you're actually facing?
**Answer:** "Unreproducible" should mean you've correlated occurrences against every available dimension (deploy timing, traffic pattern, specific tenant/customer, concurrent load, time of day, upstream dependency state) and found no discriminating factor at all — a genuinely flat, unstructured occurrence pattern. "Under-investigated" means some of those correlations were never actually checked. You tell the difference by explicitly listing which dimensions you've checked before declaring it unreproducible; if the list is short (just "I tried running it locally a few times"), it's under-investigated, not unreproducible.
**Follow-up trap:** *"You've genuinely checked every available dimension and still see no pattern. Is the bug now unfixable?"* — not necessarily unfixable, but the strategy shifts: from reproduction-driven falsification to inference-from-evidence — instrument more aggressively before the next occurrence (structured logging, always-on lightweight tracing, core dumps on crash) so that the *next* occurrence, even if still not reproducible on demand, leaves enough evidence to support or falsify a hypothesis after the fact, covered in the prod-debugging and observability-debug modules.

### Q9 — How would you use an LLM to accelerate debugging without weakening the falsifiability discipline?
**Answer:** Use it specifically for hypothesis generation — feed it the stack trace, relevant recent commits, and logs, and ask for candidate mechanisms, which is a genuine strength given how much pattern-matched "bugs shaped like this are usually X" knowledge is in training data. Then treat every generated hypothesis exactly like a human-guessed one: restate it precisely enough to be falsifiable, and design and run the same discriminating experiment you would for a hypothesis you thought of yourself, before accepting or discarding it.
**Follow-up trap:** *"The model's suggested cause matches the fix that ultimately worked. Doesn't that validate skipping the falsification step next time, given the model's track record?"* — no; a single case of the model being right says nothing about its hit rate on hypothesis generation, and even a high hit rate on generating plausible candidates doesn't substitute for confirming which specific one is actually true in this instance — the model is a faster way to get candidates, not a replacement for the verification step, and treating a correct guess as validation of skipping verification is the same sunk-cost-style reasoning error as sticking with a partially-falsified human hypothesis.

### Q10 — Describe a case where bisecting on the wrong axis (say, commit history) would waste time compared to bisecting on a different axis (say, input size) for the same bug.
**Answer:** A bug that's present across every recent commit (it's old, not newly introduced) but only manifests on large inputs would show `git bisect` converging on nothing useful — every commit in a reasonable range is "bad," because the bug was never introduced recently, it was just never triggered by the inputs used in earlier testing. Bisecting on input size (or data shape) is the axis that actually discriminates here, since commit history isn't the dimension the failure varies along.
**Follow-up trap:** *"How do you recognize, before spending time on a full `git bisect` run, that commit history is the wrong axis?"* — check the two boundary conditions cheaply first: does the failure reproduce on the oldest commit you're willing to consider, using the exact same triggering input/conditions as the newest? If it reproduces at both ends with the same repro, commit history isn't the discriminating variable at all, and bisecting it further is guaranteed to waste time — verify the axis actually varies the outcome before committing to bisecting along it.

---

## Red flags that fail you

- Describing debugging as "reading the code until you find it" with no mention of hypotheses or experiments.
- Treating an unfalsifiable statement ("something's wrong with the network") as a working hypothesis instead of pushing for a specific, testable mechanism.
- Declaring a fix confirmed without re-running the original reproduction against both the reverted and applied states of the change.
- Patching a hypothesis to survive contrary evidence instead of discarding it.
- Jumping straight to bisecting commit history without checking that the failure actually varies along that axis rather than some other one.
- Claiming a bug is "unreproducible" without listing which correlating dimensions were actually checked.
- Treating an LLM-generated cause as confirmed without independently designing and running a falsifying experiment against it.

## Cheat card

```
DEBUGGING = search over a hypothesis space via bisection, not code-reading for its own sake.

THREE PRECONDITIONS, IN ORDER (skip one, the rest is theater):
  1. RELIABLE REPRO       -- can you trigger it on demand? if "sometimes," narrow what
                             "sometimes" depends on FIRST, before hypothesizing cause.
  2. FALSIFIABLE HYPOTHESIS -- stated so a SPECIFIC experiment could prove it WRONG.
                             "cache is stale because invalidation misses the batch write path"
                             NOT "something's wrong with caching"
  3. CHEAPEST DISCRIMINATING EXPERIMENT -- costs least, still distinguishes the live hypotheses

BISECTION, 4 AXES (all are log2(n), not linear):
  commit history  -> git bisect start/good/bad/run ./repro.sh   (repro.sh must be DETERMINISTIC)
  input size      -> delta debugging / ddmin: halve input, check if it still reproduces
  time window     -> halve the timeline against deploys/config/traffic changes
  code path       -> assert an invariant at the midpoint of the call chain, not prints everywhere

log2(1000) ~= 10 steps.  linear scan of 1000 ~= up to 1000 steps.

ZELLER'S SCIENTIFIC DEBUGGING LOOP: observe failure -> hypothesize -> predict -> test -> refine/discard
  Discard on contrary evidence. Don't patch a hypothesis to survive it.

Most of the TOTAL TIME on a hard bug is usually reproduction, not hypothesis testing after it.

LLM-assisted debugging (2026): good for HYPOTHESIS GENERATION (pattern-match "bugs like this
  are usually X"). Still needs the same falsification step as a human-guessed hypothesis --
  a model being right once doesn't validate skipping verification.

Before declaring "unreproducible": have you actually correlated against deploy time, traffic
  shape, specific tenant, time of day, concurrent load? Short list = under-investigated, not
  actually unreproducible.
```

## Sources

- [Why Programs Fail: A Guide to Systematic Debugging — Andreas Zeller (O'Reilly)](https://www.oreilly.com/library/view/why-programs-fail/9780123745156/) — accessed 2026-07-28
- [Why Programs Fail: A Guide to Systematic Debugging — ResearchGate summary](https://www.researchgate.net/publication/220691048_Why_Programs_Fail_A_Guide_to_Systematic_Debugging) — accessed 2026-07-28
- [Why Programs Fail — book review, DEV Community](https://dev.to/hectorw_tt/why-programs-fail-a-guide-to-systematic-debugging-by-andreas-zeller-a-book-review-24h8) — accessed 2026-07-28

## Changelog
- 2026-07-28 — created
