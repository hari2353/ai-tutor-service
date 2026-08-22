# Reviewing AI-Written Code: Where LLMs Fail, the 10-Point Checklist

> **Track:** T27 Tooling, Docker & Debugging Mastery · **Time:** 2.0h · **Prereqs:** T27-pr-review
> **Module id:** `T27-reviewing-ai-code` · **Tags:** review, critical

## The 30-second version

LLM-written code fails in a specific, recurring set of ways that are different from where human-written code fails, which means a review process tuned for human mistakes (typos, forgotten edge cases from fatigue, inconsistent style) misses most of what actually goes wrong here. The ten failure modes that matter most: fabricated APIs and imports that don't exist or were removed years ago, silently swallowed exceptions (bare `except:` or empty `catch` blocks that convert a crash into silent data corruption), missing edge cases specifically on the unhappy path (empty/null/boundary/concurrent), over-abstraction (interfaces and factories built for a single call site because the pattern is statistically common in training data, not because this codebase needs it), tests that assert implementation calls instead of observable behavior, plausible-but-wrong concurrency (code that reads like correct locking but has a real race, because it pattern-matched the shape of correct code without reasoning about the actual interleaving), and confidently wrong comments that describe what the code was supposed to do rather than what it does. The reviewer's job is to stop reading AI-generated code as if fluency implies correctness — a model produces equally confident prose for a real API and a hallucinated one, so confidence carries zero evidentiary weight here, unlike with a human author whose hedging is usually informative.

## Why this gets asked

Because by 2026 a large fraction of the diffs any senior engineer reviews were AI-assisted or fully AI-generated, and interviewers who've shipped an incident traced back to unreviewed generated code (a hallucinated method that silently no-op'd, a race condition in generated async code, a test suite that had 100% coverage and caught nothing) want to know the candidate has actually adapted their review process to this, rather than reviewing AI output exactly like human output and getting surprised by a failure mode that's now common enough to have a name.

---

## Lineage: past → present → future

**What came before.** Code review assumed a human author: mistakes clustered around fatigue (typos, off-by-ones near the end of a long session), inconsistent judgment across a large diff (a check applied in one function and forgotten in a copy-pasted sibling), and knowledge gaps specific to that person (a junior engineer not knowing a footgun a senior would avoid). Review heuristics built around this — "read the newest code more carefully, it's less battle-tested," "watch for copy-paste drift," "junior authors need more scrutiny on X" — assumed the author's confidence roughly tracked their actual certainty, because a human who wasn't sure would usually hedge, ask, or leave a TODO.

**Where it stands now.** LLM code generation (Copilot, Cursor, Claude Code, Codex-based tools) is standard in most professional engineering environments as of 2026, and the empirical failure-rate data is concerning enough to have shaped review practice directly: reported security-vulnerability rates in AI-generated code cluster around 29-45% depending on study and language, and roughly one in five package/import recommendations point to a library that doesn't exist at all — a failure mode specific enough to have its own name, "slopsquatting," describing attackers registering package names LLMs are observed to hallucinate, so a hallucinated import isn't just a compile error, it's an active supply-chain attack vector if someone's registered that exact fake name. The live disagreement is how much of the review burden AI-assisted review tooling (Copilot review, dedicated hallucination-detection tools that check imports/APIs against the actual installed dependency graph) should absorb versus what stays a mandatory human check — there's real consensus that import/API existence and basic pattern-consistency checks are safe to automate, and much less consensus on whether AI review tools can reliably catch the subtler failures (over-abstraction, concurrency correctness, whether a test actually asserts behavior) that require holding the system's actual runtime semantics in mind, not just its textual patterns.

**Where it's heading.** Static verification integrated directly into the generation loop — the model or an adjacent tool checking that every import resolves and every called method actually exists on the target type before code is even shown to a human — is real and shipping in several 2026-era coding assistants, which should shrink (not eliminate) the fabricated-API failure mode over the next few years as it becomes standard rather than optional. What's more speculative: reliable automated detection of over-abstraction and subtly-wrong concurrency, both of which require reasoning about intent (what does this codebase actually need) and true runtime interleaving (not just syntactic pattern-matching against "this looks like correct locking code"), neither of which current tooling does robustly — treat any claim that AI review tooling has "solved" these two categories with real skepticism in 2026.

---

## Mental model

```
WHY LLM CODE FAILS DIFFERENTLY THAN HUMAN CODE

A human author's confidence roughly tracks their actual certainty.
  Unsure -> hedges, asks, leaves a TODO, writes a comment flagging the risk.

An LLM's confidence is a property of token-probability, not ground truth.
  A hallucinated API call and a real one are generated with the SAME fluency and
  the SAME lack of hedging -- there is no internal signal distinguishing
  "I've seen this exact API a thousand times" from "this is the statistically
  most plausible-sounding name for a method that doesn't exist."

  => The review heuristic "confident code is probably right" that mostly
     works on human authors actively fails on LLM output. Confidence is not evidence here.

THE TEN FAILURE MODES, IN THE ORDER TO CHECK THEM (cheapest/most-mechanical first):

 1. Fabricated APIs / imports        -- does this method/class/package ACTUALLY EXIST,
                                         at this version, with this signature?
 2. Deprecated/removed APIs           -- did this exist, but not anymore, or not in the
                                         version actually pinned in this repo?
 3. Silently swallowed errors         -- bare except/empty catch that converts a crash
                                         into corrupted state or a lost error
 4. Missing edge cases                -- "happy path hallucination": empty, null, zero,
                                         negative, boundary, concurrent caller, timeout
 5. Over-abstraction                  -- interface/factory/strategy built for ONE call site,
                                         because the shape is common in training data
 6. Tests assert implementation       -- mock.called_with(x) instead of asserting real
                                         output/behavior; can't fail even when code is wrong
 7. Plausible-but-wrong concurrency   -- correct-LOOKING lock/async code with a real race,
                                         pattern-matched shape without reasoned interleaving
 8. Confidently wrong comments        -- describes intent, not actual behavior; drifted or
                                         simply invented to sound authoritative
 9. Inconsistent with codebase idiom  -- reinvents a helper/pattern that already exists
                                         elsewhere in the repo, because the model didn't see it
10. Unjustified complexity for scale  -- adds caching/sharding/async for a scale that doesn't
                                         exist yet, because it's the "expected" shape of a
                                         production-grade answer, not because this needs it
```

## How it actually works

**1. Fabricated APIs and imports — mechanically verify, don't eyeball.** For any import or method call you don't personally recognize with certainty, check it against the actual installed dependency version (`pip show <pkg>`, the actual `package.json`/lockfile version, the actual Javadoc for the pinned library version) rather than against general familiarity with the library. A model trained on a mix of library versions will confidently call `requests.Session().mount_all(...)` or `pandas.DataFrame.append(...)` (removed in pandas 2.0) because both look exactly like real API shape from that library's history — the fluency is identical whether the specific call is current, deprecated, or simply invented. Around one in five hallucinated package names in generated code correspond to packages that don't exist on the real package index at all, which is not merely a build failure — an attacker who has registered that exact name ships you a malicious package the moment your build tries to install it.

**2. Deprecated/removed APIs — a version problem masquerading as a correctness problem.** This is distinct from full fabrication: the API existed, in some version, and the model's training data spans many versions without a strong recency prior. `useEffect` cleanup patterns from pre-18 React, `Optional.get()` used without `isPresent()` in a codebase that's since adopted an internal lint rule against it, boto3 calls using a signature from an SDK major version behind what's pinned — none of these fail to compile in isolation if the type-shape happens to still resemble something real, but they carry the deprecated behavior (silent, often subtly wrong) into a codebase that moved past it for a reason.

**3. Silently swallowed errors — check every except/catch/rescue block for what happens to the error, not whether one exists.** LLM-generated error handling frequently looks maximally defensive (a broad `try/except Exception` around a risky operation) while actually being the most dangerous pattern possible: catching everything, logging nothing or logging at a level nobody watches, and continuing execution with corrupted or partial state. The tell in review: an except block with `pass`, or a catch block that logs a generic message with no exception detail (no stack trace, no original exception object), or a broad exception type (`except Exception`, `catch (Exception e)`) where a narrow one (`except FileNotFoundError`, `catch (IOException e)`) would let unexpected failures propagate instead of being silently absorbed.

**4. Missing edge cases — "happy path hallucination," a named and observed pattern.** Models optimize for the statistically most likely continuation, and the most likely continuation of a function body is the path that makes the function's stated purpose work, not the path that handles what happens when an input violates an assumption. Concretely: a function processing a list rarely gets an explicit empty-list check unless the prompt or surrounding code explicitly primed for it; a function parsing a timestamp rarely handles a malformed or missing timezone; concurrent-caller behavior is essentially never considered unless concurrency was explicitly part of the request, because "handle concurrent access safely" isn't implied by "write a function that increments this counter" the way it would be understood by an engineer who's been paged for a race condition before.

**5. Over-abstraction — the shape of "production-grade" code in training data, applied regardless of actual need.** A huge fraction of code an LLM trained on demonstrates abstraction (interfaces, factories, dependency-injected strategies, plugin registries) because that code was written for systems that actually needed the flexibility, or because it's from a framework's own reference implementation which necessarily supports many callers. When a model generates a new single-call-site function, it frequently reaches for the same abstraction shape by pattern association, producing an `AbstractPaymentProcessorFactory` for a feature with exactly one payment method and zero stated plans for a second. The review question isn't "is this abstraction well-implemented" — it usually is, cleanly — it's "does anything in this PR or the near-term roadmap actually need more than one implementation," and if not, the abstraction is pure cost (an extra layer to read through, an extra interface to keep in sync) with no corresponding benefit.

**6. Tests that assert implementation, not behavior — the single most dangerous failure because it looks like safety.** A generated test suite with high coverage and green CI reads as trustworthy exactly when it shouldn't be. The pattern: `mock_dependency.assert_called_with(expected_args)` as the primary or only assertion, testing that a function called another function with certain arguments rather than testing that the system produces correct output. This happens because models are frequently trained on (and directly imitate) test-generation patterns optimized for coverage percentage or for demonstrating "how to mock X," not for catching regressions — a test suite can hit 100% line coverage and still pass unmodified against a deliberately broken implementation, which is the literal definition of mutation testing's failure case. Read every test's assertions and ask: if a specific realistic bug were introduced in the implementation, would this specific test go red? If the answer is "not necessarily," the test is theater.

**7. Plausible-but-wrong concurrency — pattern-matched correctness, not reasoned correctness.** Concurrent code has a distinctive failure signature with generated code: it looks exactly like correct code (a lock acquired, a check performed, an action taken) because that's the textual shape of correct concurrent code across the model's training data, but the actual interleaving is wrong — a check-then-act sequence with the lock released between the check and the act (TOCTOU, time-of-check-to-time-of-use), a lock acquired on the wrong granularity (per-call instead of per-resource, so two calls for different resources serialize unnecessarily while two calls for the *same* resource race), or an `async`/`await` chain that awaits inside a loop believing it's parallelizing work when it's actually sequentializing it because each `await` blocks the loop's next iteration. None of these produce a compile error or an obviously wrong unit test result under low concurrency — they surface under load, intermittently, which is exactly the profile of a bug that ships past a review that trusted the code's surface plausibility.

**8. Confidently wrong comments — describing intent or a stale prior version, not actual current behavior.** A comment saying `# retries up to 3 times with exponential backoff` above code that retries once with a fixed delay isn't a lie in the sense of intent — it's very often what an earlier draft did, or what a similar function elsewhere does, or simply the most statistically likely comment for that code shape, generated independently of whether it matches the actual implementation beneath it. Because it reads with total confidence and matches idiomatic phrasing exactly, it passes a skim far more easily than a human's uncertain or outdated comment would (which often reads slightly off, hedged, or inconsistent with current naming) — treat every comment describing behavior (not just labeling it) as a claim to verify against the code, not a trustworthy summary of it.

**9 & 10. Idiom mismatch and unjustified complexity — context the model doesn't have.** A model generating one function at a time, even with substantial repo context in the prompt, frequently reinvents a retry helper, a validation pattern, or an error type the codebase already has, because it didn't retrieve or wasn't given that specific existing code, and its training prior for "how to write this" is generic rather than specific to this repository's conventions. Similarly, generated code aimed at "how would a senior engineer solve this" frequently adds caching, batching, or async parallelism sized for a scale the actual system doesn't have yet, because that's the shape of code the model has seen labeled as high-quality, not because the PR's actual traffic or data volume justifies it.

## Build it from scratch

A minimal mechanical pass to run against any AI-generated diff before reading it for logic:

```bash
# 1. Every import/call actually resolves against the PINNED version, not "generally exists"
#    Python: confirm against the actual installed version, not general familiarity
pip show <package> | grep Version
python -c "import <package>; help(<package>.<method>)"   # does the signature even match?

# Node/TS: confirm against package.json's resolved version, not @latest docs
npm ls <package>
# then check that version's actual type definitions / changelog for the method used

# 2. Grep the diff for the swallowed-error pattern
git diff -- '*.py' | grep -nE '^\+.*except.*:$' -A2 | grep -B2 'pass$'
git diff -- '*.py' | grep -nE '^\+.*except Exception'   # broad catch -- read every hit
git diff -- '*.java' '*.kt' | grep -nE '^\+.*catch\s*\(\s*Exception'

# 3. Every test assertion -- flag mock-interaction-only tests for a manual read
git diff -- '*test*' | grep -nE 'assert.*called_with|verify\(.*\)\.|expect\(.*\)\.toHaveBeenCalled'

# 4. Every new lock/async construct gets a manual interleaving trace, not a skim
git diff | grep -nE 'Lock\(\)|synchronized|Mutex|RwLock|async def|await |Promise\.all'
# for each hit: write out two concurrent callers by hand, trace the actual interleaving

# 5. Diff every comment describing behavior against the code beneath it, don't skim past it
git diff | grep -nE '^\+\s*#.*\b(retries?|timeout|cache|lock)\b' -A5
```

None of this replaces reading the logic — it front-loads the mechanical, high-signal checks that a fluent, confident-sounding diff makes easy to skip past.

## How it's done in production — failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Build fails on a fresh install with `ModuleNotFoundError` for a plausible-sounding package | Fabricated import — the model generated a package name that doesn't exist, or exists but isn't what was intended | Verify every unfamiliar import against the actual package index and the repo's lockfile before merge, not at CI-failure time; treat unresolvable imports as an automatic block |
| A dependency install pulls in unexpected, unrelated code | "Slopsquatting" — an attacker registered the exact hallucinated package name the model tends to generate, and it happens to now exist maliciously | Pin and vet every new dependency against a known-good registry check; never let a hallucinated-then-real-seeming package name skip normal new-dependency review |
| An operation fails in production with no log line, no alert, just missing/corrupted downstream data | A broad except/catch swallowed the real exception, often with only a generic log message or none at all | Require narrow exception types and mandatory re-raise or explicit, logged, intentional handling for every catch block; broad catches need an explicit comment justifying why swallowing is correct here |
| A function works in every manual test and demo, fails only for a specific customer with an edge-case input | Happy-path hallucination — empty/null/boundary/malformed input was never handled because it wasn't implied strongly enough by the prompt | Explicitly enumerate and test edge inputs (empty, null, zero, negative, boundary, malformed, concurrent) for every new function handling external input, as a standing review checklist item |
| A new single-call-site feature ships with three new interfaces and a factory | Over-abstraction — the model generated the statistically common "production-grade" shape regardless of actual call-site count | Ask directly: how many implementations exist today, how many are planned in the next quarter; collapse to a concrete implementation if the answer is one and none |
| CI is green, coverage is 100%, a regression ships next release anyway | Tests assert mock-call structure, not real output/behavior; a mutation in the implementation wouldn't flip any test | Read test assertions for observable-behavior checks; run a mutation-testing pass (mutmut/Stryker/PIT) periodically on critical modules to catch this systematically, not just at individual PR review time |
| Async/concurrent code passes all tests, then corrupts data or deadlocks under real production load | Plausible-but-wrong concurrency — pattern-matched shape (a lock, a check, an await) without correct reasoning about the actual interleaving under contention | Manually trace at least two concurrent callers through any new lock/async code by hand at review time; load-test concurrency-sensitive paths before trusting unit-test-level confidence |
| A comment says one thing, the code beneath it does another, and nobody notices for months | Confidently wrong or stale comment — generated independently of actual implementation correctness, reads with total fluency | Treat every comment describing behavior (not just labeling) as an unverified claim during review; verify it against the code, don't skim past confident phrasing |

## Tradeoffs & when NOT to use it

- **Don't apply full ten-point scrutiny to trivial, low-risk generated code** (a one-off script, a throwaway data-exploration notebook cell) — calibrate the same way you would for human-written code: blast radius and lifespan determine review depth, not authorship alone.
- **Don't treat "AI-generated" as inherently lower-trust than "human-written" across the board** — a well-configured generation pipeline with type-checking and import-verification built into the loop can produce code with fewer fabricated-API issues than a human working from memory in an unfamiliar library; the failure modes above are about where LLM output *characteristically* fails, not a blanket trust penalty.
- **Don't rely on an AI reviewer to catch over-abstraction or concurrency correctness unsupervised in 2026** — both require holding actual intent (what does this system need) or actual runtime interleaving in mind, and current AI review tooling is meaningfully more reliable on import/API-existence and pattern-consistency checks than on these two categories; a human still owns them.
- **Don't skip the manual concurrency trace because "the tests pass."** Concurrency bugs are the single failure mode on this list least likely to be caught by any test suite, generated or human-written, because they require real contention to manifest — this is a structural limitation of testing, not a review shortcut you can take because coverage looks good.

---

## Interview questions

### Q1 — Why doesn't "the code reads confidently and fluently" carry the same evidentiary weight for AI-generated code as it does for human-written code?
**Testing:** whether the candidate understands the actual mechanism, not just "AI can be wrong."
**Answer:** A human's confidence in code they write roughly tracks their actual certainty — an unsure human hedges, asks, or leaves a TODO. An LLM's fluency is a property of token-probability, generated identically whether the underlying claim (this API exists, this comment matches the code) is true or fabricated. There's no internal signal in the output distinguishing "I've seen this exact real API a thousand times" from "this is merely the most plausible-sounding invented name" — so confidence-as-signal, a heuristic that partially works on human authors, actively misleads on LLM output.
**Follow-up trap:** *"Does this mean you should distrust ALL AI-generated code equally, regardless of how it was produced?"* — no; a pipeline that verifies imports/API existence against the real dependency graph before presenting code meaningfully reduces one specific failure mode (fabrication), but doesn't touch the others (over-abstraction, concurrency correctness, test quality) — trust should be calibrated per failure category, not as a single blanket score.

### Q2 — What is "slopsquatting" and why is a hallucinated import worse than a simple build failure?
**Answer:** Slopsquatting is attackers registering package names that LLMs are observed to hallucinate frequently, so that when generated code tries to `pip install`/`npm install` the fabricated name, it actually resolves — to malicious code the attacker controls, not a build error. Roughly one in five package recommendations in some studies point to non-existent packages, which is a large enough, predictable enough surface for this to be a real, not theoretical, supply-chain vector.
**Follow-up trap:** *"Your CI would catch a completely nonexistent package at install time regardless. So why does this matter for review specifically?"* — CI catches it when the malicious package doesn't exist yet; it does not catch it once an attacker has registered that exact name, because the install then succeeds — review has to verify new dependencies against expectation and reputation (is this a package you'd expect to exist, does its history/adoption match what a real solution to this problem would look like), not just wait for the install step to pass or fail.

### Q3 — A generated function has 100% test coverage and every test passes. Walk through exactly how you'd determine whether the tests are actually good.
**Answer:** Read every assertion, not the pass/fail result. For each test, ask: if a specific plausible bug were introduced in the implementation (a flipped conditional, a dropped null check, an off-by-one), would this exact test go red? A test asserting `mock.assert_called_with(x)` proves a call happened with certain arguments, not that the system's actual output or side effect is correct — it can't fail even against a badly broken implementation, as long as the broken implementation still makes the same call.
**Follow-up trap:** *"How would you demonstrate this gap to someone who trusts the coverage number, without just asserting it?"* — run a mutation-testing tool (mutmut for Python, Stryker for JS/TS, PIT for Java) against the module; it automatically introduces small deliberate bugs and reports which survive without any test catching them — turning the abstract argument into a concrete, numeric "mutation score" that's hard to dismiss.

### Q4 — Explain "happy-path hallucination" and give a mechanism for why it happens, not just an example.
**Answer:** Models generate the statistically most likely continuation of a function given its stated purpose, and the most likely continuation is the code that makes the stated purpose work under normal conditions — not the code that handles violations of implicit assumptions the prompt never stated. "Write a function that processes a list of orders" implies the happy path strongly; "handle an empty list, a null order, a duplicate ID, concurrent modification" isn't implied by that request the way it would be inferred by an engineer who's been paged for exactly that failure before.
**Follow-up trap:** *"If you explicitly prompt for edge-case handling, does that fully solve this?"* — it substantially reduces it for the edge cases you explicitly name, but doesn't solve the general problem, because you can't enumerate every edge case in a prompt and there will always be a case neither you nor the model thought to specify — review still has to independently walk edge inputs regardless of how the prompt was written.

### Q5 — What's specifically wrong with generated code that adds a factory and an interface for a payment processor when the PR only implements one payment method?
**Answer:** The abstraction is pure cost with no current benefit — an extra layer to read through and keep in sync — generated because that shape is statistically common in training data for "production-grade" payment code (which usually does support multiple processors), not because this specific PR's requirements call for it. The review question is whether there's a concrete, near-term second implementation planned; if not, collapse to a direct implementation.
**Follow-up trap:** *"The author argues 'we'll obviously need Stripe AND PayPal eventually, so building the abstraction now saves time later.' How do you respond?"* — "eventually" without a concrete near-term plan is exactly the pattern that produces cost without benefit; if a second processor is genuinely on the roadmap for the next quarter, that's a real justification and changes the answer — the distinguishing question is a stated, dated plan versus a generic "we'll probably need this," and only the former justifies the abstraction now.

### Q6 — Describe a plausible-but-wrong concurrency bug that would pass every unit test in a typical CI run, and explain why tests miss it.
**Answer:** A check-then-act sequence — checking a cache or a resource's existence, then acting on it — with the lock released between the check and the act (or no lock at all around the combined operation), so two concurrent callers can both pass the check before either acts, causing a double-create or double-charge. Unit tests run sequentially by default and essentially never inject real thread interleaving at exactly the check-act boundary, so the bug simply doesn't manifest until real concurrent load hits that exact timing window in production.
**Follow-up trap:** *"The code has a lock. Why isn't that sufficient to rule out this bug?"* — a lock acquired around only the check, or only the act, but not both atomically, doesn't prevent the race — it just makes each half individually thread-safe while leaving the combined check-then-act sequence exposed; reviewing "is there a lock" instead of "is the entire critical section under one lock acquisition" is exactly how this passes a shallow review.

### Q7 — A comment above a generated retry function reads "retries up to 3 times with exponential backoff." How do you verify this rather than trust it, and why might it be wrong even if the author didn't intend to deceive?
**Answer:** Read the actual retry loop's bound and delay calculation directly — count the loop's max iterations and check whether the delay is computed as a function of attempt number (exponential) or fixed. It can be wrong with zero deceptive intent because the comment is generated with the same fluency regardless of whether it matches the code beneath it — it may reflect an earlier draft, a similar function's actual behavior, or simply the most statistically expected comment for that code's shape, independent of what this specific implementation does.
**Follow-up trap:** *"This kind of comment mismatch also happens with human-written code after a refactor. What's actually different about the AI case?"* — human comment drift usually happens over time, after a code change the comment wasn't updated for, and often carries some residual signal (it was true once). A generated comment can be wrong from the moment of creation, with no prior state where it was accurate — it's not drift, it's a fresh, confident mismatch, which means "this comment looks old/stale" isn't a reliable tell the way it sometimes is for human-authored drift.

### Q8 — How do you check whether generated code duplicates an existing helper or pattern already in the codebase, and why does this happen more with AI-generated code than with a new team member's code?
**Answer:** Grep the codebase for the capability by behavior, not just by the name the new code happened to choose (a new team member would more often ask a colleague or search the codebase directly before writing something new; a model's context window may simply not include the existing implementation at generation time). Concretely: before approving a new retry/validation/error-formatting helper, search for existing utilities handling the same concern under any plausible name.
**Follow-up trap:** *"The new helper is arguably cleaner than the existing one it duplicates. Do you still ask for consolidation?"* — yes, in almost all cases: two implementations of the same concern will drift over time regardless of which is currently cleaner, and the fix is either replacing the old one with the new (if genuinely better, in a follow-up if scope doesn't allow it in this PR) or using the existing one — shipping both permanently is the actual defect, independent of which one reads better today.

### Q9 — Rank these five findings in a single AI-generated PR by review priority, and justify the order: (a) a hallucinated import, (b) an over-engineered factory pattern, (c) a swallowed exception in a payment path, (d) a stale comment, (e) a mock-only test.
**Answer:** (c) swallowed exception in a payment path first — silent data/money corruption in production is the highest-severity, hardest-to-detect-later outcome. (a) hallucinated import next — blocks the build or, worse, resolves to a malicious package; must be fixed before anything ships. (e) mock-only test next — means the payment-path fix in (c) isn't actually verified by the suite, so this compounds with (c) specifically. (b) over-abstraction and (d) stale comment last — real but lower-severity findings, appropriate as non-blocking or same-PR-fix-but-not-emergency items.
**Follow-up trap:** *"The author fixes (c) but leaves (e) as-is, arguing the mock test at least confirms the retry logic runs. Is that acceptable?"* — no, not for a payment path specifically: confirming a function was *called* says nothing about whether the corrected exception handling actually produces the right end state (payment recorded once, not twice, not lost) — for anything touching money or irreversible external side effects, insist on at least one assertion against actual observable outcome, not call structure, before treating this as resolved.

### Q10 — Your teammate says "I always read AI-generated code more carefully than my own for exactly this reason, so I don't think I need a checklist, just more attention." What's the gap in that argument?
**Answer:** General increased attention doesn't target the specific failure modes that are characteristic of generated code and differ from what "more careful reading" naturally catches — a careful read still tends to catch typos, obvious logic errors, and style issues (the things careful human review has always caught) but doesn't systematically catch fabricated-but-plausible API calls, mock-only tests, or check-then-act races unless the reviewer is specifically looking for those patterns, because none of them look wrong on a careful read; they look like ordinary correct code.
**Follow-up trap:** *"Isn't a fixed checklist itself risky — reviewers start rubber-stamping the checklist instead of actually thinking?"* — that's a real risk with any checklist, mitigated by treating it as a minimum floor of mechanical checks (import resolution, exception handling, test-assertion quality, concurrency trace) that free up attention for judgment calls (over-abstraction, design fit) rather than a replacement for judgment — the mechanical items are exactly the ones fluency makes easy to skip past without a forcing function.

---

## Red flags that fail you

- Treating fluent, confident-sounding generated code as more likely correct, without independently verifying imports/APIs against the actual pinned dependency version.
- Not knowing that hallucinated package names are an active, named supply-chain attack vector ("slopsquatting"), not just a theoretical build-failure risk.
- Approving a test suite based on coverage percentage or "tests pass" without reading what any assertion actually checks.
- Not tracing concurrent code by hand at review time, relying on "tests pass" as sufficient evidence for a race-free implementation.
- Accepting a new abstraction (factory, interface, strategy) without asking whether more than one implementation is actually planned.
- Treating a comment describing behavior as trustworthy without checking it against the code beneath it.
- Believing AI code review tooling can be trusted unsupervised for design-fit or concurrency-correctness judgment in 2026.

## Cheat card

```
WHY LLM CODE FAILS DIFFERENTLY: fluency != certainty. A hallucinated API and a real one are
  generated with IDENTICAL confidence -- "reads well" carries zero evidentiary weight here.

10-POINT CHECKLIST (cheapest/most mechanical first):
 1. Fabricated API/import       -- verify against ACTUAL pinned version, not general familiarity
 2. Deprecated/removed API      -- existed once, maybe not in the version this repo pins
 3. Silently swallowed errors   -- bare except/empty catch, broad Exception type, no re-raise
 4. Missing edge cases          -- "happy-path hallucination": empty/null/zero/neg/boundary/concurrent
 5. Over-abstraction            -- factory/interface for ONE call site, no stated 2nd implementation
 6. Tests assert implementation -- mock.called_with(x) proves a call happened, not correct output
 7. Plausible-but-wrong concurrency -- lock around check XOR act, not the whole critical section
 8. Confidently wrong comments  -- describes intent/old behavior, not what code actually does
 9. Idiom mismatch              -- reinvents a helper the repo already has (model lacked context)
10. Unjustified complexity      -- caching/sharding/async sized for scale that doesn't exist yet

~1 in 5 hallucinated package names correspond to non-existent packages ("slopsquatting" target)
AI code studies: ~29-45% reported vulnerability rate in generated code across languages/studies

MECHANICAL VERIFICATION:
  pip show <pkg> / npm ls <pkg>        -- confirm against PINNED version, not @latest docs
  grep except.*: -A2 | grep pass       -- swallowed errors
  grep assert.*called_with             -- mock-only tests, read manually
  trace 2 concurrent callers by hand for every new lock/async construct -- don't skip this
  mutmut / Stryker / PIT               -- mutation testing, proves tests catch real bugs

2026: AI review tools reliably catch import/API existence + pattern consistency.
      Over-abstraction and concurrency correctness still need a human. Don't trust either
      to an unsupervised AI reviewer yet.
```

## Sources

- [LLM Hallucinations in AI Code Review — diffray](https://diffray.ai/blog/llm-hallucinations-code-review/) — accessed 2026-07-28
- [Engineering Standards for AI-Generated Code Review: Mitigating Failure Modes — Dev|Journal](https://earezki.com/ai-news/2026-04-10-reviewing-ai-generated-work/) — accessed 2026-07-28
- [Mastering the AI Code Review: A Technical Guide to Production Safety — Dev|Journal](https://earezki.com/ai-news/2026-04-04-ai-code-review-checklist/) — accessed 2026-07-28
- [Code Review Checklist for AI-Generated Code: 12 Things to Verify — Git AutoReview](https://gitautoreview.com/blog/code-review-checklist-ai-generated-code) — accessed 2026-07-28
- [Best Practices for Reviewing and Auditing LLM-Generated Code — SPK and Associates](https://www.spkaa.com/blog/best-practices-for-reviewing-and-auditing-llm-generated-code) — accessed 2026-07-28

## Changelog
- 2026-07-28 — created
