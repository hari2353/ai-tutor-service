# Production notes — skill triggering

## What you'd actually use

| Layer | Tool | Trigger mechanism |
|---|---|---|
| Skills | `skill-creator` plugin (`/plugin install skill-creator@claude-plugins-official`) | evals + description tuning + blind A/B |
| Skills (raw) | `evals/evals.json` in the skill directory | committed golden queries next to the skill |
| Agent evals | `pytest` + LLM-as-judge, `langsmith`/`braintrust` eval suites | prompt-level assertions |
| Tools | MCP server with a real test suite | deterministic — normal unit tests |

## How skills actually trigger in Claude

**There is no matcher.** The mechanism is: at session start Claude Code injects a *listing* — each skill's name and `description`, nothing else — and the model itself decides, per prompt, whether one fits (semantic, not regex). Your lab's `SkillIndex.match` is a deliberate stand-in: it makes trigger quality a pure function you can pytest. The thing you are actually modeling is the *discipline* (golden queries, scored accuracy, ambiguity audit, versioned rollouts), not the mechanism.

**The hard problem is over/under-triggering**, and it fails silently: a `deploy` skill that fires because code "looked ready," or a checklist skill that has never fired since it was written. Nobody notices without measurement. Budgets make it worse: `description` + `when_to_use` capped at 1,536 chars, the whole listing at ~1% of the context window, and on overflow descriptions are **dropped from least-invoked skills first** — so a rarely-used skill silently loses the keywords that would have triggered it. Same failure mode as the lab's listing-budget stretch goal.

## What this lab models well

- **The eval-harness shape** — `evaluate(index, cases)` with should-trigger *and* should-not-trigger queries is exactly the confusion-matrix trigger test for real skills: 10 should-fire prompts, 10 must-not-fire prompts, fresh session each (leftover authoring context masks gaps — so tests get a fresh `SkillIndex` too).
- **The ambiguity audit** — `ambiguous(index, query)` is the query that two skills both claim. In production it means the model picks one arbitrarily (or both); the fix is the same as here: rewrite the losing description until the tie breaks honestly.
- **Versioned rollouts** — `bump()` + replace-only-on-increase is the rule that a description edit is a *behaviour* change with a bigger blast radius than a body edit: it changes whether the skill fires at all. Re-run trigger accuracy on every bump.
- **Word-boundary discipline** — `\btest\b` vs `test` is the regex-grade version of a real description-writing rule: name the operation precisely, or you inherit every prompt that mentions adjacent words.

## What production does differently

- **The matcher is an LLM judging fit**, so evals become *prompt evals*: each case is a fresh session, graded on whether the model invoked the skill — slower, nondeterministic, graded with evidence in `grading.json` rather than asserted with `==`. The lab's determinism is the point: it isolates the harness logic from the matcher.
- **Description A/B testing** — `skill-creator` runs blind A/B between two descriptions on the same case set, because edits that *feel* like improvements often are not. The lab equivalent is golden-set accuracy before/after a pattern change.
- **Trigger-rate monitoring** — in production you track per-skill fire rates over time (a skill that never fires is dead weight in the listing budget; one that fires on everything is hijacking the session). The lab's `evaluate` gives per-case results; production adds per-skill counters over real traffic.
- **Output quality is the second arm** — trigger accuracy alone doesn't say whether the skill helps. Production runs with-skill vs without-skill (`skillOverrides: "off"`), aggregates pass rate/time/tokens into `benchmark.json`. Deliberately out of scope here — no LLM in the loop, no output to grade.

## The 3 questions an interviewer asks after you describe this

1. *"Regexes aren't how skills trigger — so what did your lab actually test?"* — The harness, not the matcher: golden sets, should-not-trigger cases graded as misses, ambiguity surfaced instead of silently resolved, version gates on behaviour changes. The matcher is swappable; the discipline is not.
2. *"Two skills both match a query. What happens in production vs your lab?"* — Lab: `ambiguous()` surfaces the tie. Production: the model resolves it invisibly — maybe. That's why the ambiguity audit runs *before* rollout, on your own queries, not after users discover it.
3. *"You changed one word in a description. What must you re-run?"* — Trigger accuracy, always: a description edit changes whether the skill fires at all (the lab's version bump), whereas a body edit only changes what happens after it fires. Blast radius: the trigger path, not the output path.
