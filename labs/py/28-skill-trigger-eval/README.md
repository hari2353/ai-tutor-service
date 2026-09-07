# Lab 28: Skill Triggering, Tested Like Any Other Code

**Track:** T28 AI-Assisted Architecture (Claude) · **Time:** 2.5h · **XP:** 50
**Module:** `T28-skills-design`

**You will build:** a `SkillIndex` that scores skills against a query, audits ambiguity, rolls out new versions safely — and a golden-set eval harness around it, so "does this skill fire when it should?" stops being a guess.

**You will be able to answer:** *"How do you test whether a skill triggers on the right prompts — and what do you do when two skills both claim the same query?"*

## Setup

```bash
cd labs/py/28-skill-trigger-eval
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

In Claude, a skill fires when the model decides your prompt matches its `description` — semantic matching, no regex, no thresholds. This lab shrinks that to the part you can actually pin down in pytest: a skill is **name + description + trigger patterns**, and triggering becomes a scoring problem you can test like any other code.

1. **`Skill(name, description, patterns, version=1)`** — `patterns` is a list of regex **strings** describing when the skill should trigger; compile them on construction, keep the originals in `.patterns`. Skills are immutable in spirit: `bump(skill)` returns a **new** `Skill` — same name, description, patterns — with `version + 1`. Never mutate.
2. **`SkillIndex.register(skill)`** — a new name appends. Re-registering the same name **replaces** only if the version strictly increases; equal or lower version raises `RegisteringError`.
3. **`SkillIndex.match(query)`** — `(best_skill_name, score)` or `None`. A skill matches iff at least one of its patterns matches (`re.search`, case-sensitive). `score = (patterns_matched, longest_matched_span)` — a tuple compared lexicographically: more matched patterns wins; tie broken by the longest matched text; a full tie goes to the earliest-registered skill. `None` when no skill matches at all.
4. **`SkillIndex.ambiguous(query)`** — the skills tied at the best score when more than one shares it, else `[]`. Your over-triggering audit.
5. **`evaluate(index, cases)`** — `cases` is a list of `(query, expected_skill_name_or_None)`; returns an `EvalReport` with `.results` (per-case `query`/`expected`/`actual`/`passed`), `.misses`, and `.accuracy`. `None` expectations are should-not-trigger queries — over-triggering is graded exactly like under-triggering.
6. **Word boundaries are the trigger author's job.** A skill for "test" that must not fire on "testing strategy" uses `\btest\b` — and the tests keep an unguarded control pattern to show you the failure mode you are guarding against.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Confusion matrix** — split the golden set into should-trigger and should-not-trigger, report precision and recall separately. *(Interview: "over- and under-triggering are different diseases — which one did this description change cause?")*
2. **Suppressor patterns** — a `when_not` list: the skill matches only if no suppressor matches, the regex analogue of a description's "do NOT use for…" clause.
3. **Listing budget** — cap the total description characters (Claude Code: 1,536 chars per entry, ~1% of the context window for the whole listing); on overflow, drop descriptions least-recently-invoked first — then check how `match` degrades.
4. **Commit the golden set** — `evals.json` next to the skills, so "did this description edit help?" is a diff, not a debate. *(This is exactly `evals/evals.json` in `skill-creator`.)*
