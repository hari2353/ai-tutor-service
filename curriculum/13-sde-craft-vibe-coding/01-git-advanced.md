# Git: Rebase, Bisect, Worktrees, Trunk-Based Dev

> **Track:** T13 SDE Craft & Vibe Coding · **Time:** 2h · **Prereqs:** `T27-git-mastery` · **Updated:** 2026-08-03
> **Module id:** `T13-git-advanced` · **Tags:** git, workflow, critical

## The 30-second version

Trunk-based development — everyone commits to (or merges into) `main` at least daily, feature branches live under 24 hours, incomplete work ships dark behind a feature flag — is what every DORA-elite team actually runs, and GitFlow's long-lived `develop`/`release`/`hotfix` branch topology is now a legacy pattern appropriate mainly to shrink-wrapped software with multiple supported versions in the field simultaneously, not to a service you deploy continuously. The rebase-vs-merge argument is not a syntax question, it's a team-culture question about whether history should read as "what we intended" (rebase, linear, bisectable) or "what actually happened, interleaved" (merge, true chronology) — and the mechanics of each (covered in `T27-git-mastery`) matter less here than picking one convention and enforcing it, because a repo with both styles mixed inconsistently is the worst of both. Worktrees solve a problem that didn't used to exist at this scale: one AI coding agent per worktree, each on its own branch, sharing one object database, running in parallel without index/lock contention or context bleed between sessions — this is now a mainstream pattern specifically because of agentic coding, not a niche trick for humans juggling two hotfixes. Bisect is a discipline, not a command: it only converges to the right answer given a deterministic repro and a linear history, which is itself an argument for trunk-based development, since a heavily-merged branch-and-release topology makes "the midpoint" ambiguous across parallel lines of work.

## Why this gets asked

Because a candidate's git workflow opinions are a proxy for whether they've actually operated a fast-moving team, or only ever worked inside whatever branching convention was already set up when they joined. The interviewer has almost certainly either migrated a team off GitFlow after watching merge-hell eat a sprint, or inherited a trunk-based team that skipped the actual prerequisites (feature flags, a merge queue, fast CI) and calls the resulting chaos "trunk-based" incorrectly. They want a candidate who can argue the tradeoff at the workflow level — not recite `git rebase -i` syntax — and who has an opinion about running multiple AI agents against the same repo without them stepping on each other, since that's now a real day-to-day problem at a growing number of shops.

---

## Lineage: past → present → future

**What came before.** Vincent Driessen's "A successful Git branching model" (2010) — retroactively named GitFlow — formalized long-lived `develop` and `main` branches, per-feature branches merged into `develop`, and `release`/`hotfix` branches cut for shipping and cherry-picked back. It was a genuine improvement over the ad hoc branching chaos of the mid-2000s, and it fit its moment: teams shipping desktop software or infrequent releases, where "cut a release branch, stabilize it for two weeks, ship" was the actual cadence. The pain that killed it for continuously-deployed services was structural: every long-lived branch is a growing pile of merge conflicts waiting to happen, `develop` drifts from `main` in ways nobody notices until a release branch is cut and everything collides at once, and the whole model assumes releases are infrequent, discrete events — which stops being true the moment a team can deploy ten times a day and wants to.

**Where it stands now.** Trunk-based development, in DORA's own operational definition, means branches live under a day and merge into a shared trunk at least daily, with incomplete work shipped dark behind feature flags rather than isolated on a branch — and DORA's own research finds this is what elite performers actually do, correlating with dramatically higher deployment frequency and lead time versus low performers, alongside lower change failure rate, not a tradeoff against it. Even Driessen himself has said GitFlow shouldn't be the default choice for teams doing continuous delivery anymore. The live disagreement that remains, genuinely unresolved, is rebase-vs-merge for individual feature work landing on that trunk: Linus Torvalds has argued publicly against rebasing already-published history because it destroys the true chronological record, while GitHub's own UI nudges toward squash-merge (which is really "discard the feature branch's internal history, keep trunk linear") — both camps have real, defensible reasoning, and a team's choice here is a culture decision as much as a technical one. What's also now firmly deployed, not aspirational: git worktrees as the standard mechanism for running multiple AI coding agents against one repository in parallel, each in an isolated working directory and index, sharing one object store — JetBrains shipped first-class worktree UI in the 2026.1 release and VS Code added it mid-2025, both timed to this exact use case.

**Where it's heading.** Trunk-based development's three real prerequisites — fast, reliable CI; a merge queue keeping trunk green under concurrent merges; and feature-flag discipline to decouple "merged" from "released" — are becoming productized rather than assembled by hand (GitHub's native merge queue, LaunchDarkly/Unleash-style flag platforms as a default dependency rather than a mature-org luxury), which should keep lowering the bar to running trunk-based correctly rather than in name only; this is a confident, already-happening trend. More speculative: purpose-built worktree-and-agent orchestration tooling (agent-aware worktree CLIs with MCP integration, status dashboards across dozens of simultaneously-running agent sessions) is proliferating fast in 2026 but hasn't consolidated around a standard yet — expect churn in this specific tooling layer for another year or two before something wins the way Testcontainers won for integration testing.

---

## Mental model

```
GITFLOW (release-train shaped)                  TRUNK-BASED (continuous-flow shaped)

main -----o--------------o----------            main --o--o--o--o--o--o--o--o--o-->
           \              \                            |  |  |  |  |  |  |  |  |
develop ----o---o---o---o--o----o----                short-lived branches (<24h),
             \       \    /                           merged (or rebased) back FAST,
feature/A ----o---o---o--/                            incomplete work hidden behind
                                                        FEATURE FLAGS, not a branch
release/1.2 --------o---o----> tag v1.2
                        \                              main is ALWAYS deployable.
hotfix/1.2.1 -----------o----> cherry-picked           there is no "develop" to merge
                          back into develop AND main    into later — main IS the
                                                         integration branch, continuously.

  correct for: shrink-wrapped software, multiple      correct for: continuously deployed
  supported versions live simultaneously,             services, one version running in
  infrequent scheduled releases                       production, deploy cadence measured
                                                        in hours not weeks

WORKTREES FOR PARALLEL AGENTS (one object store, N isolated checkouts)

  .git/  (ONE shared object database + refs)
    |
    +-- main worktree:      /repo            (branch: main)
    +-- worktree A:         /repo-agent-1     (branch: feature/rate-limiter)  <- agent 1
    +-- worktree B:         /repo-agent-2     (branch: feature/cache-evict)  <- agent 2
    +-- worktree C:         /repo-agent-3     (branch: fix/flaky-test-314)   <- agent 3

  each has its OWN index and HEAD -> no lock contention, no stashing,
  no context bleed between agents. one branch still can't be checked
  out in two worktrees at once -- same constraint as human use.
```

## How it actually works

### Trunk-based development, mechanically, and what breaks if you skip a prerequisite

Trunk-based development is not "everyone pushes straight to main with no review" — it's short-lived branches (hours, not days), fast integration, and — the part teams skip — **decoupling merge from release** via feature flags, so a half-finished feature can sit merged into `main`, dark, without blocking anyone else's work or requiring its own long-lived branch. Skip the flag discipline and trunk-based degrades into "GitFlow with extra steps": people keep features on branches longer because there's no other way to hide incomplete work, and you're back to long-lived branches with all of GitFlow's merge-conflict pain, just without the branch names to show for it. Skip a merge queue at any real team size and concurrent merges to `main` produce a specific, observable failure: two PRs each pass CI independently against the `main` they branched from, both merge, and the *combination* breaks `main` in a way neither PR's CI run ever saw — the fix is a merge queue (GitHub's native one, or Bors/Mergify-style tooling) that re-tests each PR against the *actual* resulting `main` state serially, not just its state at branch time. Skip fast CI and short-lived branches become long-lived by necessity, because nobody wants to merge into a trunk that takes 40 minutes to tell you if you broke it.

### Rebase vs merge as a team decision, not a mechanics question

The mechanics (a rebase replays commits onto a new base, producing new SHAs; a merge commit has two parents and preserves both histories unchanged) are covered in `T27-git-mastery` — what matters at the team-practice level is which one your team standardizes on for landing a feature branch onto trunk, and why. **Rebase-then-fast-forward** (or squash-merge, which is rebase's more aggressive cousin — the whole branch collapses to one commit) gives a linear, `git bisect`-friendly history where every commit on `main` is presumed to build and pass tests independently; it costs you the true chronological record of how the feature was actually developed, including false starts and the exact order things happened. **Merge commits** preserve that true record and never rewrite history that's already been pushed (categorically avoiding the "already-shared branch got rebased" incident class covered in `T27-git-mastery`), at the cost of a `main` history where an individual commit might not build or pass tests on its own, only in combination with its merge — which actively degrades bisect's usefulness, since bisect's binary search assumes each point in history is a coherent, testable state. Most trunk-based-development shops land on squash-merge specifically *because* linear, atomic-per-commit history is what makes both bisect and blame useful at speed, and accept the lost intra-feature history as the cost — but a team with genuine reasons to preserve full development history (regulated environments needing an unaltered audit trail, or teams that bisect *within* a feature's own commits routinely) legitimately choose merge commits instead, and both are defensible if applied consistently.

### Worktrees for parallel work — human multitasking and multi-agent orchestration

`git worktree add <path> <branch>` creates a second working directory sharing the same `.git` object database and refs as the original, with its own independent `HEAD` and index (mechanics in `T27-git-mastery`). At the practice level, the reason this matters now more than it did five years ago: running several AI coding agents against one repository simultaneously is normal in 2026, and each agent needs its own working directory so its file edits, its running dev server, and its `git status` don't collide with another agent's — a single shared checkout with agents context-switching branches in and out is a recipe for one agent reading a half-edited file mid-write by another. The pattern that's emerged: one worktree per agent, each on its own branch, each with its own copy of anything environment-specific (`.env`, a locally-running dev server on its own port) that a naive worktree setup doesn't automatically duplicate — the newer worktree-aware CLIs specifically automate that copying step, because a worktree by itself only clones the git-tracked files, not untracked local state.

### Bisect as a discipline

`git bisect` mechanically halves an `O(N)` search space to `O(log2 N)` checkouts (mechanics in `T27-git-mastery`), but the discipline that actually makes it reliable is upstream of the tool: a **deterministic, fast repro** you trust before you start (a flaky repro makes bisect converge on a random, wrong commit, confidently), and a **linear history to search** — which is the direct payoff of trunk-based development's short-lived branches and (typically) squash-merged, atomic commits on `main`. Bisecting a GitFlow-style history with long-lived branches and multiple merge commits is meaningfully harder: the binary search's "midpoint" can land inside a merge commit or on a branch that was later reverted, states that were never actually deployed in that exact form, which is why teams doing serious bisect-driven regression hunting often rebase a suspect range onto a synthetic linear line *before* bisecting it, specifically to restore the property bisect assumes.

## Build it from scratch

A minimal trunk-based workflow with the three real prerequisites made concrete, plus a worktree-per-agent setup:

```bash
# --- Trunk-based: short-lived branch, feature flag, fast merge ---
git checkout -b feat/new-ranking main
# ... work, keep the branch under a day ...
# hide incomplete behavior behind a flag rather than a long-lived branch:
#   if feature_flags.is_enabled("new_ranking", tenant=tenant_id): ...
git push -u origin feat/new-ranking
# open PR -> CI (must be fast, ideally < 10 min) -> merge queue re-tests
# against the ACTUAL current main, not main-at-branch-time -> squash-merge

# --- Worktrees, one per agent, isolated but sharing one object store ---
git worktree add ../repo-agent-1 -b agent/rate-limiter main
git worktree add ../repo-agent-2 -b agent/cache-evict main
git worktree add ../repo-agent-3 -b fix/flaky-test-314 main

# copy untracked local state each agent needs (worktree only clones tracked files)
for d in ../repo-agent-1 ../repo-agent-2 ../repo-agent-3; do
  cp .env "$d/.env"
done

git worktree list                       # audit what's active
git worktree remove ../repo-agent-1     # after that agent's branch merges

# --- Bisect, but only after confirming the repro is deterministic ---
for i in 1 2 3 4 5; do ./repro.sh || echo "reproduced ($i)"; done  # run 5x first
git bisect start HEAD v2.3.0
git bisect run ./repro.sh
git bisect reset
```

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Team calls itself "trunk-based" but feature branches routinely live 1-2 weeks | No feature-flag discipline — incomplete work has nowhere to hide except a long-lived branch | Adopt a flag platform (LaunchDarkly, Unleash, or an in-house flag table) as a hard dependency of the workflow, not an optional nicety |
| Two PRs each pass CI, merge back-to-back, and `main` breaks | No merge queue — each PR was tested against `main`-at-branch-time, not the actual resulting state after the other PR landed | Adopt a merge queue (GitHub native, Mergify, Bors-style) that serially re-tests each PR against the real current `main` before it lands |
| `git bisect` converges on a commit that "shouldn't" be the cause | Non-deterministic repro, or a heavily-merged history where the "midpoint" commit was never actually a coherent deployed state | Confirm the repro 5x before bisecting; for a messy merge-heavy range, rebase it onto a synthetic linear line first, specifically to restore bisect's linearity assumption |
| Two AI agents editing the same repo checkout stomp on each other's files or read a half-written file mid-edit | Single shared working directory/index for multiple concurrent agent sessions | One `git worktree` per agent, each on its own branch, sharing one object database — no index/lock contention |
| Rebase-vs-merge argued fresh on every PR, inconsistently applied | No team-level convention decided and enforced | Pick one (usually squash-merge for bisect-friendliness) and enforce it in the merge-queue/branch-protection config, not by asking politely in review |
| `main`'s history is unbisectable because commits are all merge commits from long-lived branches | GitFlow-style topology, or trunk-based in name only with de facto long-lived branches | Move to genuinely short-lived branches and squash-merge; the bisectability is a *side effect* of the branching discipline, not a separate tool choice |
| A worktree-based agent workflow silently uses stale `.env`/local config | Worktree only clones git-tracked files; untracked local state isn't duplicated automatically | Script the copy step for every new worktree, or use a worktree-aware CLI (agentree, worktree-cli-style tools) that automates it |

## Tradeoffs & when NOT to use it

- **Don't adopt trunk-based development without its three prerequisites.** Fast CI, a merge queue, and feature-flag discipline aren't optional refinements — skip any one and you quietly regress to long-lived branches with extra ceremony, which is worse than honestly running GitFlow.
- **Don't force trunk-based onto a team shipping shrink-wrapped software with multiple supported versions live simultaneously.** GitFlow's release/hotfix branches solve a real problem (patching v1.2 while v1.4 is in active development) that trunk-based development doesn't address at all — this is a genuinely different problem shape, not a maturity gap.
- **Don't mandate rebase or merge without picking one and enforcing it consistently.** A repo with both styles mixed by individual preference is harder to read than either style applied uniformly — the choice matters less than the consistency.
- **Don't treat worktrees as a substitute for actually deciding your branching strategy.** They solve "I need N isolated checkouts at once," not "our branches live too long" — a pile of stale, unregistered worktrees (`git worktree prune` needed) is its own maintenance burden if the underlying branching discipline is still a mess.
- **Don't bisect a non-deterministic bug without accepting the result is unreliable.** A flaky repro will make bisect confidently converge on the wrong commit; verify determinism first or don't trust the output.

---

## Interview questions

### Q1 — What does DORA's research actually say about trunk-based development versus GitFlow?
**Testing:** whether the candidate has data behind the opinion, not just a preference.
**Answer:** DORA's own operational definition of trunk-based development is branches living under a day, merging into a shared trunk at least daily, with incomplete work shipped dark behind feature flags. Elite performers by DORA's own metrics (deployment frequency, lead time, change failure rate) are disproportionately trunk-based; GitFlow's long-lived branch topology correlates with lower performance on exactly those metrics, primarily because it structurally delays integration.
**Follow-up trap:** *"So GitFlow is just wrong?"* — no; GitFlow solves a real problem trunk-based development doesn't address: multiple supported versions of shrink-wrapped software live in the field simultaneously, needing independent patching. The DORA data applies specifically to continuously-deployed services with one production version, which is most but not all software.

### Q2 — What are the three things that have to be true for trunk-based development to actually work?
**Testing:** whether "trunk-based" is understood as a system with prerequisites, not just a slogan.
**Answer:** Fast, reliable CI (nobody wants to merge into a trunk that takes 40 minutes to validate); a merge queue that re-tests each PR against the actual resulting `main` state, not just its state at branch time; and feature-flag discipline to decouple "merged" from "released," so incomplete work can live on `main`, dark, without needing its own long-lived branch.
**Follow-up trap:** *"What happens if you skip just the merge queue?"* — two PRs can each pass CI independently against their own branch-time state of `main`, both merge back-to-back, and the *combination* breaks `main` in a way neither PR's own CI run ever saw — this is a specific, observable, common failure mode at any real team size without one.

### Q3 — Rebase or merge for landing a feature branch — what's your team's convention, and why?
**Testing:** whether the candidate treats this as a culture decision with tradeoffs, not a right-answer question.
**Answer:** Most trunk-based-development teams land on squash-merge (rebase's more aggressive cousin) specifically because a linear, atomic-per-commit `main` is what makes both `git bisect` and `git blame` fast and reliable — every point in history is presumed to be a coherent, independently-testable state. The cost is losing the true chronological record of how a feature was actually built, including false starts.
**Follow-up trap:** *"When would you choose merge commits instead?"* — a regulated environment needing an unaltered audit trail of what actually happened and when, or a team that genuinely bisects within a feature's own development history routinely — both are legitimate, and the wrong answer is picking one dogmatically without naming what it costs.

### Q4 — Why does a heavily-merged, long-lived-branch history make `git bisect` less reliable, mechanically?
**Testing:** connecting branching strategy to a concrete downstream tool failure.
**Answer:** Bisect's binary search assumes each candidate commit represents a single, coherent, testable state that could plausibly have existed in production. A history with many merge commits and long-lived branches has ancestry that splits and rejoins — the "midpoint" of a bisect range can land inside a merge commit or on a branch state that was never actually deployed in that exact form, producing a result that doesn't causally make sense.
**Follow-up trap:** *"What would you do if you had to bisect a genuinely messy merge-heavy range anyway?"* — rebase the suspect range onto a synthetic linear line before bisecting, specifically to restore the linearity assumption bisect depends on, and treat the result with appropriate skepticism if the rebase itself required non-trivial conflict resolution.

### Q5 — Why do teams now use git worktrees for running multiple AI coding agents, and what problem does a single shared checkout create?
**Testing:** current, practical understanding of an emerging workflow pattern.
**Answer:** A single shared checkout means every concurrent agent is editing the same working directory and index — one agent's file write can be read mid-edit by another, `git status` becomes meaningless with concurrent changes from multiple sources, and there's real lock contention on the index. A worktree per agent gives each one an isolated working directory and index while sharing one object database, so agents run genuinely in parallel without stepping on each other.
**Follow-up trap:** *"What's the one thing a naive worktree setup misses?"* — untracked local state. `git worktree add` only clones git-tracked files; `.env` files, locally-running dev-server config, and anything else outside version control has to be copied to each new worktree explicitly, which is exactly what the newer worktree-aware agent CLIs automate.

### Q6 — A team says they've adopted trunk-based development, but branches routinely live one to two weeks. Diagnose.
**Testing:** recognizing trunk-based-in-name-only.
**Answer:** Almost certainly missing feature-flag discipline — without a way to ship incomplete work dark, a long branch is the only place to hide unfinished features, which reproduces GitFlow's merge-conflict pain under a different name. The fix isn't a git command, it's adopting a flag platform as a hard workflow dependency.
**Follow-up trap:** *"Would enforcing a branch-age limit in CI fix this on its own?"* — no, and it would just push the problem sideways: teams would rush half-finished, unflagged work onto `main` to avoid the CI check, which is worse than the long branch it replaced. The flag discipline has to come first; the age limit only works once there's somewhere else for incomplete work to live.

### Q7 — What's the actual argument for and against squash-merge specifically, beyond "it's cleaner"?
**Testing:** whether "cleaner" is backed by a mechanism.
**Answer:** For: every commit on `main` is atomic and independently testable, which is what makes bisect converge reliably and blame attribute cleanly to one logical change. Against: it destroys the actual development history of the feature — if a bug was introduced and then fixed within the same feature branch before merge, that entire story collapses into one commit, and if the collapsed commit itself has a bug, you've lost the finer-grained history that might have shown you exactly which internal step introduced it.
**Follow-up trap:** *"Does squash-merge lose the reflog too?"* — no; the reflog is local to whoever had the pre-squash branch checked out and is unrelated to squash-merge's effect on the shared, pushed history — a developer who still has their original unsquashed branch locally (or in their own reflog) can still recover the fine-grained history for their own debugging even after the squashed version lands on `main`.

### Q8 — Why is Linus Torvalds's objection to rebasing published history not just a style preference?
**Testing:** understanding the object-model consequence, not just repeating a famous opinion.
**Answer:** Rebasing already-pushed commits produces entirely new commit objects with new SHAs (same resulting tree, different parent, different hash) — anyone who already has the pre-rebase commits now has a genuinely diverged history with no shared ancestor relationship to the new one at those points, and their next pull either silently duplicates commits or fails outright. It's a correctness argument about shared state, not just a preference about how history should read.
**Follow-up trap:** *"Does that argument apply to rebasing your own unpushed local branch?"* — no, and this is the actual scoping of the rule: rebase freely on a branch nobody else has pulled, because there's no diverged shared state to break; the objection is specifically about rewriting history that's already been shared, which is exactly why "never rebase a branch others have pulled" (from `T27-git-mastery`) and "rebase your own WIP branch as much as you want" are both true simultaneously.

### Q9 — Design the workflow for a team of 40 engineers plus a dozen AI coding agents all working against one repository, avoiding both merge chaos and agent-collision chaos.
**Testing:** synthesizing branching strategy and worktree practice at a realistic scale.
**Answer:** Trunk-based with the three prerequisites (fast CI, merge queue, feature flags) for the human-authored branching strategy; each AI agent gets its own worktree on its own short-lived branch, sharing the team's single object database, so agent work integrates through the exact same merge-queue-and-flag pipeline as human work rather than a separate process. Branch age limits enforced in CI catch both humans and agents drifting toward long-lived branches. Squash-merge for bisectability given the volume of agent-generated commits that would otherwise clutter `main`'s history.
**Follow-up trap:** *"What breaks first at this scale if the merge queue is missing?"* — with a dozen agents plus 40 humans all merging frequently, the back-to-back-merge-breaks-main failure mode (Q2) stops being an occasional annoyance and becomes near-constant, because the rate of concurrent merges is high enough that "tested against branch-time `main`" is stale by the time almost any merge lands — this is the scale at which skipping a merge queue goes from "risky" to "guaranteed."

### Q10 — Staff-level: your org's `git bisect` results have been unreliable for months, and nobody trusts them anymore. Where do you look first, and how do you fix the actual root cause rather than the symptom?
**Testing:** diagnosing a systemic branching-discipline problem via its bisect symptom.
**Answer:** First check whether the branching topology has quietly drifted from trunk-based into long-lived-branches-with-merge-commits — this is the most common root cause of chronically unreliable bisect, since it breaks the linearity assumption bisect depends on. Second, audit whether repro scripts used in `bisect run` are actually deterministic (rerun 5x on a known commit before trusting any bisect result). The symptom-level fix (rebase a suspect range before bisecting, as in Q4) treats one bisect at a time; the root-cause fix is restoring genuinely short-lived branches and consistent squash-merging so every future bisect on `main` is reliable without per-instance rescue.
**Follow-up trap:** *"The team resists shortening branch lifetimes because 'our features are just bigger than a day.'"* — that's usually a feature-flag gap wearing a branch-lifetime costume: a large feature can still merge incrementally, dark behind a flag, in small daily pieces, with the flag flipped on only when the whole thing is ready — "the feature is big" argues for flagging, not for a long branch, and conflating the two is exactly how trunk-based-in-name-only happens.

---

## Red flags that fail you

- Calling a team "trunk-based" while branches routinely live more than a day, with no mention of feature flags as the reason it's supposed to work.
- Treating rebase-vs-merge as a right-answer question rather than a team convention with real tradeoffs on both sides.
- Not knowing that a merge queue exists specifically to catch the back-to-back-merge-breaks-main failure a per-branch CI run cannot see.
- Recommending GitFlow or trunk-based development universally without naming the release-cadence shape (continuous service vs. multi-version shrink-wrapped software) that decides which fits.
- Bisecting a flaky repro without checking determinism first, or trusting a bisect result from a heavily-merged history without reservation.
- Not knowing why worktrees matter for running multiple AI agents against one repo, or proposing a single shared checkout for concurrent agent sessions.

## Cheat card

```
TRUNK-BASED (DORA def.): branches <24h, merge to main >=daily, incomplete
  work hidden behind FEATURE FLAGS not branches. Elite performers'
  default; correlates with higher deploy freq + lower change failure rate.
PREREQUISITES (all three, or it degrades to GitFlow-with-extra-steps):
  1. fast/reliable CI   2. merge queue (re-tests vs ACTUAL current main)
  3. feature-flag discipline (decouples merged from released)

GITFLOW: long-lived develop/release/hotfix branches. Right for: shrink-
  wrapped software, multiple supported versions live simultaneously.
  Wrong for: continuously deployed services (even its author says so now).

REBASE/SQUASH vs MERGE COMMIT — team convention, not a right answer:
  squash/rebase: linear, atomic, BISECT- and BLAME-friendly. Loses
    intra-feature history. NEVER rebase an already-pushed shared branch
    (new SHAs = diverged history for anyone who already pulled it).
  merge commit: preserves true chronology, never rewrites pushed history.
    Costs bisect reliability (midpoint may land in an incoherent state).

WORKTREES for parallel AI agents: one .git object DB, N isolated
  working dirs + indexes. One branch still can't be checked out in 2
  worktrees at once. Worktree clones TRACKED files only -- copy .env /
  untracked local state to each new worktree yourself.
  JetBrains 2026.1 + VS Code (mid-2025): native worktree UI, agent-driven.

BISECT DISCIPLINE: O(log2 N) checkouts, but ONLY reliable given
  (a) a deterministic repro (verify 5x before trusting a result) and
  (b) a LINEAR history (trunk-based's short branches are what make this
  true; heavily-merged GitFlow-style history breaks the midpoint
  assumption -- rebase a messy range onto a synthetic line before
  bisecting it if you must).
```

## Sources

- [Trunk-Based Development vs. Gitflow — Flagsmith](https://www.flagsmith.com/blog/trunk-based-development-vs-gitflow) — accessed 2026-08-03
- [GitFlow vs Trunk-Based: How Branching Strategy Impacts DORA Metrics — CodePulseHQ](https://codepulsehq.com/guides/git-branching-strategy-impact) — accessed 2026-08-03
- [How to Use Git Worktrees for Parallel AI Agent Execution — Augment Code](https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution) — accessed 2026-08-03
- [Git Worktrees for AI Coding: How to Run Multiple Agents Without Conflicts — MindStudio](https://www.mindstudio.ai/blog/git-worktrees-parallel-ai-coding-agents) — accessed 2026-08-03
- [Claude Code Git Worktrees: Run 5 AI Agents in Parallel (2026 Guide) — DevToolLab](https://devtoollab.com/blog/claude-code-git-worktrees-parallel-agents-guide-2026) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
