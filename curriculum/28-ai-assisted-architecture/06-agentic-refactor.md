# Large-Scale Refactors With Agents: Sequencing, Guardrails, Rollback

> **Track:** T28 AI-Assisted Architecture · **Time:** 2.5h · **Prereqs:** `T28-spec-driven-dev`, `T28-subagent-architecture`, `T19-testing-quality` · **Updated:** 2026-07-26
> **Module id:** `T28-agentic-refactor` · **Tags:** workflow

## The 30-second version

A large refactor with an agent fails for a reason that has nothing to do with the agent's coding ability: the transformation is 85% mechanical and 15% judgment, and the agent will make the 15% look exactly like the 85%, so a uniform-looking 4,000-line diff hides a dozen decisions nobody made. The sequencing rule that follows is one mechanical transformation per commit, machine-verifiable, with the build green at every commit, and the judgment cases pulled out into a separate explicitly-human pass *first*. Guardrails are the part that makes this survivable and they are all cheap: a green baseline recorded before the agent touches anything, an architecture fitness function in CI (`import-linter` or equivalent) so the invariant the refactor exists to establish is asserted rather than described, a diff-size cap that forces splitting, and a scope check that fails a PR touching files the plan did not name. Rollback should be a property of the sequencing, not a heroic recovery: expand-contract and branch-by-abstraction mean every intermediate state is shippable and every step is one `git revert`. And the delivery data says the review side is where this actually breaks: agentic PRs run 2.6× larger and wait 5.3× longer for a reviewer, median review time is up 441%, and 31% more PRs merge with no review at all, so a big diff does not get reviewed harder, it gets skimmed.

## Why this gets asked

Because it is the first task where agents look spectacular and then quietly cost you a quarter. Every interviewer at this level has approved or inherited one: a rename-and-restructure that touched 300 files, passed CI, and turned out to have silently changed behaviour in the eleven call sites that were not like the other 289. They want to know whether you sequence for reviewability and rollback or sequence for speed, because the second is what an agent naturally optimizes for and someone has to supply the first. There is also a specific tell they listen for: whether you talk about the *build being green at every commit* or about the build being green *at the end*. Those are different engineering practices and only one of them lets you bisect.

---

## Lineage: past → present → future

**What came before.** Three approaches, and the modern practice is a synthesis rather than a replacement. **Manual refactoring with IDE support, from Fowler's *Refactoring* (1999) onward:** small behaviour-preserving steps, tests green throughout, each step individually reversible. The discipline was excellent and it did not scale past what one person could hold, which is why cross-cutting changes to a large codebase simply did not happen; they were priced out. **Codemods and mechanical rewriting, roughly 2013 onward** (Facebook's jscodeshift, Google's Rosie and the large-scale-change process described in *Software Engineering at Google*, later `comby` and `ast-grep`): parse to an AST, apply a deterministic transformation, produce a reviewable and *provably uniform* diff. The pain that limited these was expressiveness: writing the codemod is a real programming task, and any transformation needing semantic understanding or per-site judgment cannot be expressed as a rewrite rule at all. Google's answer was organizational rather than technical: shard the change into thousands of small independently-reviewable and independently-revertable commits, each owned by the relevant team. That sharding insight is the single most transferable idea in this module and it long predates agents. **Then the 2024-2025 agentic phase:** hand the whole refactor to an agent and let it work. The pain that is killing that right now is measured: agentic PRs run **2.6× larger** and wait **5.3× longer** for a reviewer, median PR review time is up **441%**, **31% more PRs merge with no review at all**, and median batch size roughly doubled between Q1 2025 and Q1 2026, growing about 2.5× faster from October onward as agent adoption went mainstream. The refactor got cheap to *produce* and no cheaper to *review*, and review is where correctness is established.

**Where it stands now.** The working practice is codemod discipline with an agent as the transformation engine, plus git as the checkpoint substrate. Concretely: a green baseline recorded before handoff; worktree isolation so parallel agents cannot collide (Claude Code ships `--worktree`, an `isolation: worktree` frontmatter field for subagents, and `isolation: "worktree"` on the `Agent` tool; JetBrains shipped first-class worktree support in 2026.1, March 2026); one transformation per commit; and fitness functions in CI. The most instructive public data point is Scott Chacon's Grit, a from-scratch rewrite of Git in Rust done with agents, the most publicly documented large-scale parallel-agent project as of mid-2026, consuming roughly **45 billion tokens**. The reported failure is the one worth memorizing: a parallel agent broke a fundamental part of the testing harness, and the cause was **uncoordinated parallel writes**, with the retrospective conclusion that worktree discipline plus more frequent merge checkpoints would have contained the damage to one branch. The **live disagreements** are two and both are real. **Agent versus codemod:** an agent handles semantic variation a rewrite rule cannot express, and it gives you *no uniformity guarantee*, whereas `ast-grep` gives you a proof that all 289 sites were transformed identically. The strong position, which I hold, is that these compose: use the agent to *write the codemod* and to triage the exceptions, and let the deterministic tool do the bulk. **And how big a PR may be:** teams capping at 200-400 lines report better review outcomes and slower nominal throughput, and the counter-argument that artificial caps produce meaningless slicing is not stupid, it is just usually wrong about which slices are meaningless.

**Where it's heading.** **High confidence: worktree isolation becomes the default rather than a technique.** It already is in some surfaces (every new session in the Claude Code desktop app gets its own worktree; subagent worktrees are locked with `git worktree lock` while the agent runs and swept afterwards). **High confidence: scope and size gates become standard CI furniture,** because they are the only mechanism that actually addresses the 31%-merged-unreviewed number, and a spec-file-scope check is about twenty lines. **Medium confidence: agents get first-class support for producing stacked/sharded changes** rather than one diff, which is Google's Rosie insight arriving in the tooling. **Speculative: semantic diff review, where the reviewer is shown behaviour deltas rather than text deltas,** which is the only thing that would genuinely make a 4,000-line uniform change reviewable. Prototypes exist; nothing is production. Label that a hope.

---

## Mental model

The 85/15 split is the whole module. Everything else is a consequence.

```
  A "SIMPLE" CROSS-CUTTING REFACTOR: 312 call sites
  ┌────────────────────────────────────────────────────────────────┐
  │████████████████████████████████████████████████████░░░░░░░░░░░│
  │  265 sites: purely mechanical                    47 sites:     │
  │  same shape, same semantics                      NEED A HUMAN  │
  │                                                  DECISION      │
  └────────────────────────────────────────────────────────────────┘
        ▲                                                  ▲
        │                                                  │
   agent/codemod does this perfectly            the agent will make
   in one commit, machine-verified              THESE LOOK LIKE THOSE
                                                and you will find out
                                                in production

  THE SEQUENCING THAT FOLLOWS:
   PASS 0  inventory: enumerate all 312. classify. commit the classification.
   PASS 1  the 47 judgment sites — HUMAN DECIDES, one commit per cluster
   PASS 2  the 265 mechanical sites — agent/codemod, ONE commit, verified uniform
   PASS 3  contract: delete the old path once nothing references it
   NEVER   one pass over 312 sites
```

Second picture: three independent checkpoint layers, which people conflate and then discover are not interchangeable.

```
  LAYER          GRANULARITY      SURVIVES        USE FOR
  ─────────────────────────────────────────────────────────────────────────
  Claude          per user         session resume  "undo the last 10 minutes"
  checkpoints     prompt           (100 most       Esc Esc / /rewind
                  (file snapshots  recent per      NOT git. skips symlinked and
                   only)           session, 30d)   hard-linked paths on restore.
                                                   cannot cover external side effects.
  ─────────────────────────────────────────────────────────────────────────
  git commits     per logical      forever         bisect, revert, review, blame
                  transformation                   THE ONLY LAYER THAT MATTERS
                                                   FOR ROLLBACK
  ─────────────────────────────────────────────────────────────────────────
  worktrees       per parallel     until removed   isolation between concurrent
                  agent / branch                   agents. NOT a checkpoint.
  ─────────────────────────────────────────────────────────────────────────
  A refactor whose rollback plan is "Esc Esc" has no rollback plan.
```

---

## How it actually works

### Pass 0: the inventory, which is the step everyone skips

Before any transformation, produce and **commit** a machine-generated inventory. This is the artifact that turns a refactor from a hope into a project.

```bash
# runs. enumerate every call site, then classify with structural search.
# ast-grep gives you a UNIFORM guarantee that a prompt cannot.
ast-grep --pattern 'get_tenant_config($$$ARGS)' --json=stream src/ \
  | jq -r '[.file, .range.start.line, (.metaVariables.multi.ARGS | length)] | @tsv' \
  | sort > inventory/raw.tsv
wc -l inventory/raw.tsv          # 312

# the classification is the valuable part, and it is a HUMAN artifact
# even when an agent drafts it.
awk -F'\t' '$3 == 1 {print}' inventory/raw.tsv > inventory/mechanical.tsv   # 265
awk -F'\t' '$3 != 1 {print}' inventory/raw.tsv > inventory/judgment.tsv     #  47
```

Then delegate the *classification review* to an agent with a structured return: for each of the 47, why it differs and what decision is needed. Read all 47 yourself. This is 40 minutes and it is the difference between a refactor and an incident.

The reason this pass exists: **the agent cannot tell you what it does not know it does not know.** A site that passes `None` where every other site passes a config object is not a syntax variation, it is a behavioural question ("what did the previous author intend by omitting this?"), and an agent optimizing for a uniform diff will resolve it plausibly and silently.

### Sequencing: expand, migrate, contract

The pattern is old (parallel change / expand-contract, and branch-by-abstraction for the larger version) and it is what makes every intermediate state shippable, which is what makes rollback trivial.

```
  STEP 1  EXPAND     add the new interface alongside the old. no callers change.
                     ┌─ old_api()  ← 312 callers
                     └─ new_api()  ← 0 callers
                     ✅ shippable. ✅ revert = delete new code. ZERO RISK.

  STEP 2  BRIDGE     old_api delegates to new_api. behaviour identical.
                     old_api() ──► new_api()   ← 312 callers still on old
                     ✅ shippable. ✅ revert = one commit.
                     ← THIS is where you validate equivalence (see below)

  STEP 3  MIGRATE    move callers. THE JUDGMENT SITES FIRST, then mechanical.
                     3a: 47 judgment sites, human-decided, ~5 commits
                     3b: 265 mechanical sites, ONE commit, uniformity-verified
                     ✅ each commit shippable. ✅ each revert independent.

  STEP 4  CONTRACT   delete old_api once `ast-grep` proves zero references.
                     ✅ the only step that is not trivially reversible,
                        which is why it is LAST and SEPARATE.
```

Two things to notice. **Step 2 is where you get equivalence evidence for free**, because both paths exist simultaneously: you can run them side by side on real traffic (the GitHub Scientist pattern), diff the outputs, and only proceed when the mismatch rate is zero. That is worth far more than a test suite for a behaviour-preserving refactor, because the test suite only covers cases somebody thought of. **Step 4 being separate and last is not tidiness**, it is the rollback design: deletion is the one irreversible act, so it gets its own PR, after the new path has been live long enough to trust.

### Keeping the build green: a baseline, then per-step gates

The single highest-value habit, and it takes two minutes:

```bash
# BEFORE the agent touches anything. in the worktree it will work in.
claude --worktree refactor-tenant-config     # isolated checkout, own branch
cd .claude/worktrees/refactor-tenant-config
uv sync --all-extras
ruff check . && mypy --strict src/ && pytest -q | tee ../../baseline.txt
git rev-parse HEAD > ../../baseline.sha
```

Why this matters more than it sounds: without a recorded green baseline, every failure during the refactor triggers the same 20-minute investigation, *is this a regression or a pre-existing flake?* With it, any new failure is attributable to the agent's changes by construction, and you stop paying that tax dozens of times. Record flaky tests explicitly in the baseline, because a refactor is exactly when a flake gets blamed on the refactor.

Then per-step. The `CLAUDE.md` entry that actually changes agent behaviour here:

```markdown
## Refactor protocol (active while `docs/specs/refactor-*.md` is open)
- One transformation per commit. Never bundle a mechanical pass with a judgment fix.
- Before every commit: `ruff check . && mypy --strict src/ && pytest -q -x`.
  If it is not green, do NOT commit. Report and stop.
- Commit message: `refactor(step N/M): <transformation>` plus the site count.
- Never delete the old code path in the same commit that migrates callers.
- If a call site does not fit the mechanical pattern, do NOT adapt it.
  Add it to `inventory/judgment.tsv` and continue.
```

That last rule is the important one, and it is the whole 85/15 defence expressed as an instruction: **the agent's default is to make the exception fit, and you want it to file the exception instead.** Note also that this is a Level 1 instruction, so you back it with a Level 3 gate: a `PreToolUse` hook or a CI check that rejects a commit whose diff touches both `inventory/judgment.tsv` sites and mechanical ones.

### Checkpointing: what each layer can actually do

**Claude Code checkpoints** capture file state before each user prompt, keep snapshots for the **100 most recent checkpoints per session**, persist with the conversation so a resumed session can still `/rewind`, and are cleaned up with sessions after 30 days (`cleanupPeriodDays`). `/rewind` (or `Esc Esc` on an empty prompt) offers restore-code, restore-conversation, restore-both, and two targeted summarize options. This is excellent for "that last approach was wrong, back it out." It is **not** version control: it covers file changes only, restore skips symlinked and hard-linked paths, and it cannot cover anything with an external side effect, which is why the harness asks before commands touching databases, APIs, or deployments.

**Git commits** are the only rollback layer that matters. One logical transformation per commit gives you three things nothing else does: `git bisect` on a behavioural regression, `git revert` of exactly one decision, and a reviewable unit. A 4,000-line single commit forfeits all three simultaneously, and that is the actual cost of the big diff, not reviewer fatigue.

**Worktrees** are isolation, not checkpointing, and conflating them is a real error. `claude --worktree <name>` creates `.claude/worktrees/<name>/` on branch `worktree-<name>`, branched from the repository's **default branch** by default (`worktree.baseRef: "fresh"`), or from local `HEAD` with `"head"`, which is what you want when isolating subagents that must operate on in-progress work. A fresh checkout has no gitignored files, so `.worktreeinclude` (gitignore syntax, copies only files that match *and* are gitignored) is how `.env` gets there. Worktrees share the `.git` directory, project-scope plugins, and (v2.1.211+) saved permission approvals with the main checkout. For parallel agents: `isolation: worktree` in a subagent's frontmatter makes it permanent, Claude Code runs `git worktree lock` while the agent is running so concurrent cleanup cannot remove it, and a periodic sweep removes agent worktrees older than `cleanupPeriodDays` while **skipping any that still hold work** (changed or untracked files, unpushed commits) and never touching ones you created with `--worktree`.

This is the direct mitigation for the Grit failure: parallel agents in the same checkout produce uncoordinated writes, and the specific damage there was a broken test harness, which is the worst possible thing to break because it disables the mechanism that would have caught it.

### Guardrails: four gates, in descending order of value

**1. The fitness function for the invariant the refactor exists to establish.** If the refactor's purpose is "the domain layer must not import adapters," then the deliverable is not the moved code, it is the CI contract:

```ini
# .importlinter — runs in CI. this is the refactor's actual product.
[importlinter]
root_package = src

[importlinter:contract:layers]
name = Layered architecture
type = layers
layers =
    src.api
    src.domain
    src.adapters

[importlinter:contract:domain-purity]
name = Domain does no I/O
type = forbidden
source_modules = src.domain
forbidden_modules = requests, httpx, sqlalchemy, boto3, redis
```

Write this **before** the refactor, watch it fail with N violations, and treat the refactor as done when N reaches zero. That converts a subjective architectural goal into a monotonically decreasing number, which is the only way a multi-week refactor stays honest. It also permanently prevents the regression, which is the part that makes it worth more than the refactor itself.

**2. Diff-size cap.** Blunt, unpopular, effective:

```yaml
# .github/workflows/pr-size.yml — runs. adjust the threshold per repo.
- name: Enforce diff size
  run: |
    LINES=$(git diff --numstat origin/${{ github.base_ref }}...HEAD \
            -- . ':(exclude)*.lock' ':(exclude)*.snap' ':(exclude)**/generated/**' \
            | awk '{a+=$1+$2} END {print a+0}')
    echo "diff lines: $LINES"
    if [ "$LINES" -gt 400 ] && ! git log -1 --pretty=%B | grep -q '^refactor-bulk:'; then
      echo "::error::PR is $LINES lines (cap 400). Split it, or prefix the commit"
      echo "::error::with 'refactor-bulk:' AND attach uniformity proof (see CONTRIBUTING)."
      exit 1
    fi
```

The escape hatch matters: a genuinely uniform 2,000-line mechanical pass is *fine* and is not what the cap is for. But it has to be labelled and it has to carry a uniformity proof, which is the next gate.

**3. Uniformity proof for bulk passes.** This is what makes a large mechanical diff reviewable in five minutes instead of unreviewable in two hours:

```bash
# runs. prove the bulk pass did exactly one thing, 265 times.
git diff -U0 HEAD~1 -- src/ | grep '^[-+]' | grep -v '^[-+][-+]' \
  | sed 's/[0-9]\+/N/g' \
  | sort | uniq -c | sort -rn | head -20
# EXPECT: two dominant shapes (one removed form, one added form) and nothing else.
# ANY third shape is a site that was not mechanical. Read it.
```

Attach that output to the PR. A reviewer then reviews *one* transformation and *one* count, not 265 hunks. This is the concrete answer to "how do you review a 4,000-line diff": you do not, you review the transformation and verify the diff contains only that transformation.

**4. Scope check.** Fail the PR if it touched files the linked spec did not name. Roughly twenty lines, and it catches scope leakage, dead-code accumulation, and opportunistic refactors in one rule.

### Rollback strategy, by class of change

Rollback is a property of the sequencing. Design it in.

| Change class | Rollback mechanism | Cost | Preconditions |
|---|---|---|---|
| Expand (add new path) | delete the new code | trivial | none |
| Bridge (old delegates to new) | one `git revert` | trivial | one commit, no bundling |
| Migrate mechanical | one `git revert` of the bulk commit | low | the bulk pass is its own commit |
| Migrate judgment | `git revert` of that cluster's commit | low | judgment sites are grouped, not scattered through the bulk commit |
| Contract (delete old path) | **re-add code, which is a forward fix** | **high** | do this last, separately, after the new path has soaked |
| Behaviour-changing refactor | feature flag; toggle off | medium | flag added in the expand step, not retrofitted |
| Data-shape change | expand-contract on the schema: add column, dual-write, backfill, read-new, drop old | high per step, trivial per step in isolation | every step independently reversible; migrations have tested `downgrade` |

The rule to say out loud: **if the answer to "how do we undo this" is "revert several commits and hope," the sequencing is wrong, not the rollback plan.** And a `git revert` you have never executed is a theory: for a refactor of consequence, actually run the revert on a branch and confirm the build is green, because a revert that conflicts is not a rollback.

### Avoiding the 4,000-line diff

Five mechanisms, roughly in order of impact:

1. **One transformation per commit, one concern per PR.** The Rosie insight from Google: shard into small independently-reviewable and independently-revertable changes, routed to the people who own the code. This predates agents by a decade and agents make it more necessary, not less.
2. **Stacked PRs.** Expand → bridge → judgment clusters → bulk → contract, as a stack, each reviewable alone and mergeable in order. Reviewers get 200-line units; you get one logical change.
3. **Uniformity proof for the one genuinely big commit**, so its size is not a review burden.
4. **Delegate to a codemod where the transformation is expressible.** `ast-grep` or `comby` gives a guarantee an agent cannot: the same rule applied everywhere, verifiable by re-running it and getting an empty diff. The strongest workflow is *the agent writes the codemod*, you review the rule (twenty lines instead of 4,000), and the tool applies it. Reviewing a transformation rule is a fundamentally cheaper cognitive task than reviewing its output.
5. **Cap it in CI**, because instructions do not survive deadline pressure and gates do.

And know the number that makes this urgent rather than aesthetic: a 200-line PR reviewed properly beats a 2,000-line PR skimmed, and the skim is what is actually happening in the 31% of PRs merging with no review at all.

---

## Build it from scratch

`(lab pending)` ships a 40-file service with a cross-cutting change to make: replace a positional-args config lookup with a typed config object, 312 call sites, 47 of them not mechanical.

**Part 1 (30 min): inventory and classify.** Write the `ast-grep` query, produce `raw.tsv`, split mechanical from judgment. Graded on how many of the 47 you find; the seeded exceptions include a site passing `None`, one inside a `try/except` that swallows the error, two in a hot loop where the object allocation matters, one in a test that asserts the *old* signature, and one behind a feature flag that is off in production. Miss the last one and the "refactor" silently enables a dormant code path.

**Part 2 (20 min): write the fitness function first.** An `import-linter` contract, or a test asserting zero references to the old symbol. Watch it fail with 312 violations. That number is your progress bar.

**Part 3 (60 min): sequence it.** Expand, bridge, judgment clusters, bulk, contract, as five or six commits in a worktree, green at every commit. Then run `git bisect` against a seeded behavioural regression and see whether your commit granularity lets you find it in three steps or twenty.

**Part 4 (20 min): the anti-pattern, on purpose.** Same refactor, one prompt, one commit. It will pass CI, because the seeded regression is not covered by an existing test. Now try to review it, and time yourself. Then produce the uniformity proof on your own bulk commit and time *that*. The delta is the lesson, and it is usually 40 minutes versus 4.

**Part 5 (20 min): rollback drill.** Actually revert the bulk commit and confirm green. Then revert the *bridge* commit while the bulk commit is still applied and watch what breaks. That teaches ordering constraints better than any diagram.

**Part 6 (20 min): parallel and collide.** Run two agents on overlapping file sets in the same checkout, then repeat with `--worktree` for each. Reproduce the Grit failure class deliberately: the first run corrupts shared state, the second does not.

---

## How it's done in production

The setup that survives a multi-week refactor:

```
docs/specs/refactor-tenant-config.md   # the spec, with the site inventory linked
inventory/
  raw.tsv                              # committed. machine-generated.
  mechanical.tsv                       # 265
  judgment.tsv                         # 47 + the decision made for each
.importlinter                          # the fitness function. the real deliverable.
bench/baselines/                       # perf baselines for the non-regression gate
baseline.txt, baseline.sha             # the recorded green state
.claude/
  agents/refactorer.md                 # isolation: worktree, narrow tools
  settings.json                        # PreToolUse hook: reject mixed-concern commits
.worktreeinclude                       # .env etc. into every agent worktree
.github/workflows/pr-size.yml          # diff cap + uniformity-proof escape hatch
```

The subagent definition is short and its restrictions are the point:

```markdown
---
name: refactorer
description: Applies ONE mechanical transformation across the sites listed in
  inventory/mechanical.tsv. Use only for a bulk pass in a sequenced refactor.
isolation: worktree
tools: Read, Edit, Grep, Glob, Bash
model: sonnet
---

Apply exactly the transformation described in the linked spec, to exactly the sites
in `inventory/mechanical.tsv`, and nothing else.

If a site does not fit the pattern, do NOT adapt it. Append it to
`inventory/judgment.tsv` with a one-line reason and move on.

Before finishing: run `ruff check . && mypy --strict src/ && pytest -q`, and produce
the uniformity proof (`scripts/uniformity_proof.sh`). Report the site count, the
proof output verbatim, and the contents of any lines you added to judgment.tsv.
```

**Failure-mode table**

| Symptom | Cause | Fix |
|---|---|---|
| 4,000-line diff, CI green, behaviour changed in 11 places | The 15% judgment sites were made to look like the 85% mechanical ones | Inventory and classify before transforming; instruct the agent to *file* exceptions rather than adapt them; back it with a mixed-concern commit gate |
| Cannot tell whether a failing test is a regression or a pre-existing flake | No recorded green baseline | Record `ruff`/`mypy`/`pytest` output and the SHA before handoff, in the worktree the agent will use, and list known flakes explicitly |
| `git bisect` useless | One giant commit, or commits that are not individually green | One transformation per commit, green at every commit, enforced by a pre-commit gate |
| Two parallel agents corrupted shared state; the test harness broke | Uncoordinated parallel writes in one checkout (the documented Grit failure) | Worktree per agent (`--worktree`, `isolation: worktree`); frequent merge checkpoints |
| Agent worktree vanished with work in it | Manual `git worktree remove` without `--force` awareness, or a hook-created worktree the sweep does not manage | The sweep skips worktrees holding changes or unpushed commits and never removes `--worktree` ones; commit early inside the worktree |
| Refactor "done," architecture regressed within two sprints | The invariant was described in prose, never asserted | The fitness function *is* the deliverable. `import-linter` contract in CI, violations count as the progress bar |
| Reviewer approved a bulk pass without reading it | Nothing made it cheap to review. Agentic PRs run 2.6× larger and wait 5.3× longer, and 31% more merge unreviewed | Uniformity proof attached; diff cap with a labelled escape hatch; review the *transformation*, not the output |
| Revert conflicted; rollback took four hours | Commits bundled multiple concerns; revert never rehearsed | One concern per commit; rehearse the revert on a branch and confirm green before shipping the step |
| Old code path deleted, then a bug surfaced | Contract step bundled with migration | Contract is its own PR, last, after the new path has soaked |
| Perf regressed 30% and nobody noticed for a month | Only correctness was gated | Perf baselines in `bench/baselines/` and a non-regression gate as an acceptance criterion, with an explicit budget (for example 5%) |
| Refactor stalled at 70% and lived on a branch for six weeks | Not sequenced for shippable intermediate states | Expand-contract: every step ships. A refactor that cannot be paused is a refactor that will be abandoned |
| Agent "helpfully" reformatted 200 unrelated files | Formatter or import-sorter run repo-wide as a side effect | Scope check in CI; separate any formatting change into its own commit, never mixed with a semantic change |

---

## Tradeoffs & when NOT to use it

- **Do not use an agent where a codemod is expressible.** If the transformation can be written as an `ast-grep` or `comby` rule, do that: you get a uniformity guarantee, a twenty-line reviewable artifact instead of a 4,000-line one, and idempotence (re-run it and get an empty diff). The genuinely good hybrid is having the agent *write* the rule and triage the exceptions. Reaching for the agent to do the bulk transformation directly trades a proof for a probability.
- **Do not refactor and change behaviour in the same change.** This is the oldest rule in refactoring and agents make it easier to break, because the agent will happily "fix" a bug it notices mid-transformation. Now your diff is neither behaviour-preserving nor reviewable, and a bisect points at a commit that did two things.
- **Do not start a large refactor without a fitness function.** If you cannot express the target state as a check, you cannot tell when you are done, and "the code looks better" does not survive contact with a deadline. If the invariant is not assertable, reconsider whether it is real.
- **Do not refactor a subsystem with no test coverage using an agent.** The agent optimizes toward green, so if the suite is the oracle and the suite is absent, you have no oracle and high confidence. The correct first project is *characterization tests*, which is itself excellent agent work: pin current behaviour, including behaviour you consider wrong, then refactor against the pins.
- **Do not parallelize writes across agents without worktree isolation.** The documented failure is uncoordinated parallel writes breaking the test harness, which is the worst target because it disables detection. Read-only fan-out is safe; write fan-out needs isolation plus merge checkpoints.
- **Do not do a big-bang refactor because the agent makes it feel cheap.** Cheap to produce is not cheap to *own*. The cost lands on review (2.6× larger, 5.3× longer wait, 441% longer median review time), on incident response (no bisectable history), and on the person who has to reason about the resulting code in six months.
- **Sometimes the right answer is not to refactor.** If the module is stable, rarely touched, and works, a cross-cutting cleanup buys aesthetics and risks behaviour, and "the agent could do it easily" is not a business case. The strangler-fig alternative, where new code uses the new pattern and old code is only converted when you have to touch it, has a worse-looking codebase and a much better risk profile, and it is frequently correct.
- **The counter-argument to state:** a serious camp argues that all this sequencing ceremony is a hangover from when refactors were expensive to produce, and that with cheap generation the right move is to regenerate the subsystem from a spec rather than transform it incrementally. That is genuinely compelling for a self-contained module with good tests and a clear contract, and it is how Grit was built. It fails on anything with unwritten invariants, live data, or consumers you do not control, and it converts a reviewable sequence of small deltas into one unreviewable artifact where the only verification is the test suite you already know is incomplete. The discriminator is whether the module's contract is fully captured externally. Usually it is not.

---

## Interview questions

### Q1 — Walk me through a 300-file refactor with an agent.
**Testing:** whether you sequence for reviewability and rollback or for speed.
**Answer:** Five passes. Pass 0, inventory: `ast-grep` every call site, commit the raw list, classify into mechanical and judgment, and read every judgment case myself. Pass 1, the fitness function: write the CI contract that asserts the target state (`import-linter`, or a test asserting zero references to the old symbol), watch it fail with N violations, and treat N as the progress bar. Then expand (add the new interface, nothing changes), bridge (old delegates to new, behaviour identical, and this is where I can validate equivalence on real traffic because both paths exist), migrate with the judgment sites first as small human-decided commits and then the mechanical sites as one uniformity-verified bulk commit, and finally contract, deleting the old path in its own PR after the new one has soaked. Green at every commit, one transformation per commit.
**Follow-up trap:** *"Why judgment sites before mechanical?"* Because if the bulk pass runs first, the exceptions are already buried in a 3,000-line diff and I will never find them. Doing them first also means each one is a small reviewable commit with a decision recorded in the message, and it front-loads discovering that the refactor is harder than I thought, which is when cancelling is still cheap. The general principle: **do the part that requires thinking while thinking is still cheap.**

### Q2 — What breaks that has nothing to do with the agent's coding ability?
**Testing:** the 85/15 insight, which is the core of the module.
**Answer:** The transformation is not uniform, and the agent will make the exceptions look like the rule. Out of 312 sites, maybe 265 are purely mechanical and 47 need a decision: one passes `None` where everyone else passes an object, one is inside a `try/except` that swallows the error, two are in a hot loop where the allocation matters, one is a test asserting the old signature, one is behind a feature flag that is off in production. The agent produces a beautifully uniform diff and I cannot see which eleven of those it silently decided. That is not a capability failure; asked directly about any single site, it would answer well. It is that nothing in its objective function distinguishes "apply the rule" from "resolve an ambiguity," and a uniform diff is what it was optimizing for.
**Follow-up trap:** *"How do you make the agent surface them instead?"* An explicit instruction that inverts the default: if a site does not fit the pattern, do not adapt it, append it to `inventory/judgment.tsv` with a one-line reason, and continue. That works reasonably well and it is Level 1, so I back it with Level 3: a commit gate rejecting a diff that touches both judgment-listed and mechanical sites, plus the uniformity proof, which surfaces exceptions mechanically because any third diff shape in a bulk pass is by definition a site that was not mechanical.

### Q3 — How do you review a 4,000-line diff?
**Testing:** whether you know the honest answer.
**Answer:** You do not, and pretending otherwise is how 31% of PRs end up merging with no review at all. Two moves instead. If the change is genuinely uniform, do not review the output, review the *transformation*: attach a uniformity proof (normalize the diff by replacing numbers, then count distinct hunk shapes) and expect exactly two dominant shapes, one removed and one added, with any third shape being a site that was not mechanical and needing a human read. That turns four hours into five minutes. If the change is not uniform, it must be split, and the CI cap forces that: 400 lines unless the commit is labelled a bulk pass and carries the proof. The framing I would use is that a 200-line PR reviewed properly beats a 2,000-line PR skimmed, and the data says skimming is what actually happens: agentic PRs run 2.6× larger and wait 5.3× longer for a reviewer, with median review time up 441%.
**Follow-up trap:** *"Isn't a diff cap arbitrary and gameable?"* Partly, yes: people pad exclusion lists and split along meaningless lines, and I would rather have the cap and police the gaming than not have it, because the alternative is a policy that only holds when nobody is under pressure. Two things make it less arbitrary. Exclude generated files, lockfiles, and snapshots from the count, since those are noise and inflating the number destroys trust in the gate. And provide the labelled escape hatch, because a genuinely uniform 2,000-line mechanical pass is *good* and blocking it teaches people the gate is stupid. The cap is not there to make changes small, it is there to make unreviewable changes visible.

### Q4 — Claude Code checkpoints versus git. When do you use each?
**Testing:** whether you conflate them, which is a common and expensive error.
**Answer:** Different jobs. Checkpoints capture file state before each user prompt, keep snapshots for the 100 most recent per session, persist with the conversation so a resumed session can still `/rewind`, and clean up with sessions after 30 days. They are for "that approach was wrong, back out the last ten minutes," via `Esc Esc` or `/rewind`, which also offers restore-conversation-only, restore-code-only, and two targeted summarize options. Git commits are for rollback, bisect, review, and blame. The distinction that matters: checkpoints cover *file changes only*, restore skips symlinked and hard-linked paths, and they cannot cover anything with an external side effect, which is why the harness prompts before commands touching databases, APIs, or deployments. So a refactor whose rollback plan is `Esc Esc` has no rollback plan.
**Follow-up trap:** *"And worktrees?"* Isolation, not checkpointing, and conflating those is the third version of the same error. A worktree is a separate working directory with its own branch sharing the repository's `.git`, so parallel agents cannot overwrite each other. Details that matter operationally: by default it branches from the repo's default branch (`worktree.baseRef: "fresh"`), so set `"head"` when the agent must work on your in-progress commits; a fresh checkout has no gitignored files, so `.worktreeinclude` is how `.env` gets there; Claude Code holds a `git worktree lock` while an agent is running; and the periodic sweep skips any worktree holding changed files or unpushed commits and never removes ones you created with `--worktree`.

### Q5 — Two agents in parallel corrupted the repo. What went wrong and what do you change?
**Testing:** whether you know the documented failure.
**Answer:** Uncoordinated parallel writes in a shared checkout. The public case is Grit, Scott Chacon's Git rewrite in Rust, roughly 45 billion tokens and the most documented large-scale parallel-agent project as of mid-2026, where a parallel agent broke a fundamental part of the testing harness. That target is the worst possible one, because breaking the test harness disables the mechanism that would have caught everything else. The retrospective conclusion was that worktree discipline plus more frequent merge checkpoints would have contained the damage to one branch. So: one worktree per agent (`--worktree`, or `isolation: worktree` in the subagent frontmatter, or `isolation: "worktree"` on the `Agent` tool), merge checkpoints at defined points rather than at the end, and a rule that shared infrastructure like the test harness and CI config is single-writer and human-owned.
**Follow-up trap:** *"Would you parallelize at all?"* For reads, freely, since that is where fan-out is safe and the ratio is best. For writes, only across genuinely disjoint file sets, with a worktree each, and with the number bounded by how many results I can *review*, not how many I can spawn. The trap in write fan-out is that it parallelizes generation and serializes review, and review is the bottleneck, so five parallel agents produce five things I integrate sequentially anyway while adding merge conflicts. One subagent per independently reviewable artifact is the rule I would state.

### Q6 — How do you keep the build green throughout?
**Testing:** whether you have the baseline habit.
**Answer:** Record the green state before the agent touches anything, in the worktree it will actually work in: `ruff`, `mypy --strict`, `pytest -q` output plus the SHA, with known flakes listed explicitly. That single artifact means every subsequent failure is attributable to the agent's changes by construction, so I stop paying the twenty-minute "is this a regression or a pre-existing flake" tax dozens of times. Then a per-commit gate: lint, types, and fast tests must pass before every commit, and if they do not, the agent reports and stops rather than committing. And a hard rule that no commit bundles a mechanical pass with a behaviour fix, so a bisect result points at one decision.
**Follow-up trap:** *"The suite takes 40 minutes. Now what?"* Tier it. A fast gate per commit (lint, types, unit, and the specific integration tests covering the touched area, targeting under two minutes) and the full suite per PR or per merge checkpoint. That is a deliberate risk trade and I would say so: I am accepting that a slow-test regression is found at the PR boundary rather than the commit boundary, which is acceptable because the commits are small enough that bisecting within the PR is cheap. What I would not accept is no per-commit gate at all, because then every commit is untrustworthy and bisect returns a commit that was already broken.

### Q7 — Agent or codemod?
**Testing:** whether you reach for the deterministic tool when it applies.
**Answer:** Codemod whenever the transformation is expressible, because `ast-grep` or `comby` gives me three things the agent cannot: a uniformity guarantee that all 265 sites got the identical treatment, a twenty-line reviewable artifact instead of a 4,000-line one, and idempotence, so re-running it produces an empty diff and I know it is complete. The agent's advantage is semantic variation a rewrite rule cannot express, which is exactly the 15%. So the composition I actually use: the agent *writes* the codemod rule, I review the rule, the tool applies it to the mechanical set, and the agent helps me triage the exceptions one at a time with the reasoning visible.
**Follow-up trap:** *"Why is reviewing the rule better than reviewing the diff?"* Because it is a categorically cheaper cognitive task with a stronger guarantee. Reviewing 265 hunks means reading 265 things and hoping to notice the one that differs, which is exactly the task humans are worst at and which the data on skimmed large PRs confirms we fail. Reviewing one rule plus a count plus a uniformity proof means checking one piece of logic and then verifying mechanically that only that logic was applied. That is the same reason `import-linter` beats a paragraph in `CLAUDE.md`: it moves the guarantee from "somebody read carefully" to "the build fails otherwise."

### Q8 — Design the rollback plan for a refactor that touches a database schema.
**Testing:** whether you know that some steps are not reversible and design accordingly.
**Answer:** Expand-contract on the schema, so no single step is irreversible. Add the new column nullable, deploy. Dual-write to old and new, deploy, with a revert that is one commit. Backfill in batches, idempotent and resumable, and note that backfill is *forward-only*, so it must be written to be safe to re-run. Switch reads to the new column behind a flag, so rollback is a flag toggle rather than a deploy. Stop writing the old column, deploy. Then drop it, in its own change, weeks later, after the new path has soaked. Every migration has a tested `downgrade`, enforced by a migration-lint CI check, and I rehearse the revert on a branch and confirm green before shipping each step, because a revert that conflicts is not a rollback.
**Follow-up trap:** *"Which step can't you roll back, and what do you do about it?"* Two. The backfill, because the data has been written, so the mitigation is idempotence, batching, and the fact that the old column is still authoritative until the read switch. And the drop, which is a forward fix only, so it goes last, alone, after soak, with a verified backup and a pre-drop check that the column has had zero reads for the retention window. That is also the general shape of the rule: isolate the irreversible act into its own change, do it as late as possible, and make everything before it a toggle.

### Q9 — When would you not refactor?
**Testing:** whether cheap generation has distorted your judgment.
**Answer:** When the module is stable, rarely touched, and works. Cross-cutting cleanup there buys aesthetics and risks behaviour, and "the agent could do it easily" is not a business case, it is a cost estimate for the cheapest part of the work. Also when there is no test coverage, because the agent optimizes toward green and with no oracle I get high confidence and no evidence, so the correct first project is characterization tests that pin current behaviour including behaviour I consider wrong. Also when I cannot express the target state as a check, because then I cannot tell when I am done and the refactor will stall at 70% on a branch. The alternative I would usually propose is strangler fig: new code uses the new pattern, old code converts only when I have to touch it. Worse-looking codebase, much better risk profile.
**Follow-up trap:** *"That leaves you with two patterns forever."* Often yes, and that is a real cost I would name rather than hide: two patterns means more to learn, more to get wrong, and a lint rule to stop new code using the old one. What makes it the right trade is that the alternative is not "one pattern," it is "one pattern plus a behavioural risk taken on code nobody has needed to think about in two years." I would put a deadline and a fitness function on it (violations must be monotonically decreasing, new violations blocked in CI) so it converges instead of becoming permanent, and I would accept convergence over eighteen months instead of a big bang over two weeks.

### Q10 — Your refactor is 70% done and living on a branch for six weeks. Diagnose.
**Testing:** whether you recognize the sequencing failure.
**Answer:** It was not sequenced for shippable intermediate states, so nothing could merge until everything was finished, and now it is accumulating conflicts against a moving main branch faster than it is progressing. The fix is structural, not effort: re-sequence into expand-bridge-migrate-contract, where expand and bridge are behaviour-neutral and can merge today, then migrate in slices. Even mid-refactor, this usually salvages the work: land the additive parts immediately, land the completed migration slices, and leave only the genuinely unfinished sites on the branch. If it cannot be re-sequenced that way, that is itself a finding, usually meaning the change is behaviour-modifying rather than behaviour-preserving and needs a feature flag.
**Follow-up trap:** *"What if a partial state leaves the codebase in two patterns?"* Accept it, and make it visible rather than hidden. Two patterns during migration is the normal state of every non-trivial refactor, and pretending otherwise is what produces six-week branches. What makes it safe is the fitness function, with the violation count as a public progress bar, plus a lint rule blocking *new* uses of the old pattern so the number cannot go up. That converts "we are mid-refactor" from an embarrassing state into a tracked one, and it is the same reason expand-contract works: the intermediate state is a designed state, not a mess you are hiding on a branch.

### Q11 — What's the actual deliverable of a refactor?
**Testing:** the senior reframe.
**Answer:** The CI check, not the moved code. If the refactor exists to establish "the domain layer does no I/O," the durable artifact is the `import-linter` contract that fails the build when that becomes false, because that is what prevents the regression I will otherwise be doing again in eighteen months. The moved code is the one-time consequence. This also solves the "when is it done" problem: the violation count is the progress bar, it goes to zero, and it stays at zero because the build enforces it. And it is the honest test of whether the goal was real: if I cannot express the target state as a check, I should be suspicious that I have an aesthetic preference rather than an architectural invariant.
**Follow-up trap:** *"What if the invariant genuinely isn't checkable?"* Then I would look harder before accepting that, because most are: layering is `import-linter`, purity is a forbidden-imports contract, "no raising across this boundary" is a return type, coupling is a dependency-count budget, complexity is a threshold, and "one owner per table" is a grep over migration files. If it truly is not checkable, I would downgrade it from an invariant to a documented preference and reconsider the refactor's value, because an unenforceable invariant regresses by default. That is the same discipline as context files: if a claim is not worth asserting in CI, it should not be stated as a rule.

---

## Red flags that fail you

- Treating the refactor as uniform; no inventory, no classification of exceptions.
- Build green at the end rather than at every commit.
- Rollback plan is "Esc Esc" or "revert several commits and hope."
- Bundling behaviour changes with a behaviour-preserving refactor.
- Deleting the old path in the same change that migrates callers.
- No fitness function, so no definition of done.
- Parallel write agents in one checkout.
- Refactoring untested code with an agent.
- Reaching for the agent when the transformation is a twenty-line codemod rule.
- Defending a 4,000-line diff as reviewable.
- Never having rehearsed the revert.
- Six-week branch with no shippable intermediate state.

## Cheat card

```
THE 85/15 SPLIT (the whole module)
  a 312-site refactor ≈ 265 mechanical + 47 needing a DECISION
  the agent will MAKE THE 47 LOOK LIKE THE 265 → uniform diff, silent decisions
  seeded exception shapes: passes None · inside a swallowing try/except ·
    in a hot loop (allocation) · a test asserting the OLD signature ·
    behind a feature flag that is OFF in prod

SEQUENCE   PASS 0 inventory+classify (COMMIT IT) → PASS 1 fitness function (watch
  it fail with N) → EXPAND → BRIDGE → MIGRATE (judgment FIRST, then bulk) → CONTRACT
  judgment first: exceptions buried in a 3,000-line diff are never found; and
    discovering it's harder is cheapest early
  BRIDGE is where equivalence is free: both paths exist → run side by side on real
    traffic (Scientist pattern), proceed at zero mismatch
  CONTRACT is the ONLY irreversible step → last, alone, after soak

THREE CHECKPOINT LAYERS (do not conflate)
  Claude checkpoints  per prompt · 100 most recent/session · persist with the
    conversation · 30d (cleanupPeriodDays) · /rewind or Esc Esc (empty prompt) ·
    restore code / conversation / both + 2 targeted summarize options
    FILE CHANGES ONLY · restore SKIPS symlinked+hard-linked paths · cannot cover
    external side effects.  NOT VERSION CONTROL.
  git commits         one transformation each, green at each → bisect, revert, review
    THE ONLY ROLLBACK LAYER
  worktrees           ISOLATION, not checkpointing

WORKTREES  claude --worktree <name> → .claude/worktrees/<name>/ on worktree-<name>
  worktree.baseRef "fresh"(default, repo default branch) | "head"(your unpushed work)
  fresh checkout has NO gitignored files → .worktreeinclude (gitignore syntax,
    copies only files that match AND are gitignored)
  shares .git, project-scope plugins, and (v2.1.211+) saved permission approvals
  subagents: `isolation: worktree` frontmatter · Agent tool isolation:"worktree"
  git worktree lock held while the agent runs · sweep removes agent worktrees older
    than cleanupPeriodDays but SKIPS any holding changes/unpushed commits and NEVER
    removes --worktree ones
  gitignore .claude/worktrees/

FOUR GUARDRAILS (descending value)
  1 FITNESS FUNCTION = the real deliverable. import-linter layers + forbidden
    contracts. violations count = the progress bar. prevents the REGRESSION.
  2 DIFF-SIZE CAP in CI (~400 lines, excluding lockfiles/snapshots/generated)
    with a LABELLED escape hatch for genuinely uniform bulk passes
  3 UNIFORMITY PROOF   git diff -U0 | grep '^[-+]' | sed 's/[0-9]\+/N/g' |
      sort | uniq -c | sort -rn
    EXPECT exactly 2 dominant shapes. ANY THIRD SHAPE = a non-mechanical site.
    turns a 4h review into 5 min: review the TRANSFORMATION, not the output
  4 SCOPE CHECK   fail a PR touching files the linked spec didn't name (~20 lines)

GREEN BASELINE (2 minutes, saves hours)
  in the worktree the agent will use: ruff + mypy --strict + pytest -q | tee
  baseline.txt, plus baseline.sha, plus KNOWN FLAKES listed
  ⇒ every later failure is attributable BY CONSTRUCTION

CLAUDE.md REFACTOR PROTOCOL
  one transformation per commit · green before every commit or STOP and report ·
  never delete the old path in the migrating commit ·
  IF A SITE DOESN'T FIT, DO NOT ADAPT IT — append to inventory/judgment.tsv
    (the default is to make the exception fit; you want it FILED)
  back it with a Level 3 gate rejecting mixed-concern commits

ROLLBACK BY CLASS
  expand → delete new code · bridge/mechanical/judgment → one git revert
  behaviour change → FEATURE FLAG (added in expand, never retrofitted)
  contract → FORWARD FIX ONLY → last, alone, after soak
  schema → add nullable · dual-write · BACKFILL (forward-only: idempotent, batched,
    resumable) · read-new behind a flag · stop old write · DROP weeks later
  a git revert you have never RUN is a theory. rehearse it, confirm green.

THE NUMBERS   agentic PRs 2.6× LARGER, wait 5.3× LONGER for a reviewer
  median PR review time +441% · 31% more PRs merge with NO REVIEW
  median batch size ~2× Q1'25→Q1'26, growing ~2.5× faster from Oct as agents
    went mainstream
  Grit (Git rewrite in Rust, agents, ~45B TOKENS): a parallel agent BROKE THE TEST
    HARNESS — uncoordinated parallel writes. worktrees + frequent merge checkpoints.
  JetBrains shipped first-class worktree support in 2026.1 (March 2026)

AGENT vs CODEMOD   codemod (ast-grep/comby) gives UNIFORMITY GUARANTEE +
  20-line reviewable artifact + IDEMPOTENCE (re-run → empty diff)
  agent handles semantic variation a rule cannot express (= the 15%)
  BEST: the agent WRITES the codemod, you review the RULE, the tool applies it,
  the agent helps triage exceptions one at a time

DON'T   refactor untested code (no oracle; write characterization tests first) ·
  refactor stable rarely-touched working code · bundle behaviour with refactor ·
  start without a fitness function · parallel WRITES without worktrees ·
  big-bang because generation is cheap (cheap to produce ≠ cheap to own)
  ALTERNATIVE: strangler fig — new code new pattern, convert on touch, lint blocks
  new violations, count monotonically decreasing
```

## Sources

- [Run parallel sessions with worktrees](https://code.claude.com/docs/en/worktrees) — `--worktree`, the `.claude/worktrees/<name>/` layout and `worktree-<name>` branch, `worktree.baseRef` `"fresh"` versus `"head"`, `.worktreeinclude` semantics, `isolation: worktree` for subagents, `git worktree lock` while an agent runs, the periodic sweep and what it skips, what worktrees share with the main checkout, and the `WorktreeCreate` hook; accessed 2026-07-26
- [Checkpointing](https://code.claude.com/docs/en/checkpointing) — checkpoints per user prompt, snapshots for the 100 most recent per session, persistence with the conversation, 30-day cleanup via `cleanupPeriodDays`, and the `/rewind` restore and summarize options; accessed 2026-07-26
- [How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) — checkpoints being separate from git, covering file changes only, skipping symlinked and hard-linked files on restore, and not covering external side effects; accessed 2026-07-26
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents) — `isolation: worktree` frontmatter and tool-restricted subagent definitions; accessed 2026-07-26
- [Multi-Agent AI Coding Workflow: Git Worktrees That Scale](https://blog.appxlab.io/2026/03/31/multi-agent-ai-coding-workflow-git-worktrees/) — the Grit case (Git rewritten in Rust with agents, roughly 45 billion tokens, a parallel agent breaking the test harness through uncoordinated parallel writes, and the worktree-plus-merge-checkpoints conclusion), and JetBrains shipping first-class worktree support in 2026.1 (March 2026); accessed 2026-07-26
- [How to Use Git Worktrees for Parallel AI Agent Execution](https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution) — the clean-green-baseline-before-handoff practice and why it makes failures attributable; accessed 2026-07-26
- [Key Takeaways from the DORA Report 2025](https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025) — Faros AI; agentic PRs 2.6× larger and waiting 5.3× longer for a reviewer, median PR review time up 441%, 31% more PRs merging with no review, and median batch size roughly doubling between Q1 2025 and Q1 2026; accessed 2026-07-26
- [DORA 2025 State of DevOps Report](https://dora.dev/research/2025/dora-report/) — AI as an amplifier of existing practice, and the throughput-versus-stability trade-offs; accessed 2026-07-26
- [Large-Scale Changes — Software Engineering at Google](https://abseil.io/resources/swe-book/html/ch22.html) — the Rosie process: shard a cross-cutting change into small independently reviewable and independently revertable commits routed to code owners; accessed 2026-07-26
- [ast-grep](https://ast-grep.github.io/) — structural search and rewrite with pattern and rule files, used here for the inventory query and the deterministic bulk pass; accessed 2026-07-26
- [import-linter](https://import-linter.readthedocs.io/) — layered and forbidden-module contracts as executable architecture fitness functions; accessed 2026-07-26
- [ParallelChange](https://martinfowler.com/bliki/ParallelChange.html) — Martin Fowler; the expand-migrate-contract pattern that makes every intermediate state shippable; accessed 2026-07-26
- [BranchByAbstraction](https://martinfowler.com/bliki/BranchByAbstraction.html) — Martin Fowler; the larger-scale version for replacing a subsystem while shipping continuously; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
