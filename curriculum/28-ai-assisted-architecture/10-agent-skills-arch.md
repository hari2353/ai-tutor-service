# Skill-Mediated Agents: Architectural Patterns & Reference Architecture

> **Track:** T28 AI-Assisted Architecture (Claude) · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T28-agent-skills-arch` · **Tags:** skills

## The 30-second version

A skill-mediated architecture is a system design choice, not a single file's authoring problem: instead of one system prompt that grows with every capability you add, capability lives in a corpus of small, independently loadable units that cost nothing until the model's own judgment says one is relevant, which is why the mechanism is called progressive disclosure and why it is now the dominant pattern for production agent capability management — 30-50% fewer planning errors and 3-8x better context-budget efficiency are the reported numbers behind that claim. The architectural decision that actually matters at system scale is not "is this a skill," which `T28-skills-design` answers per-file; it's how a *corpus* of skills stays coherent as it grows past the size one person can hold in their head — composition (does skill A's output feed skill B), versioning (does an edit to one skill's description silently break a fleet of 40), and distribution (is there one source of truth, or forty accounts each with a slightly different copy). This repo's own `skills/` directory is a working answer to all three: the repo is the source of truth, `install.ps1` is the one-way sync to any account that needs the skills, and every one of the twelve `/tutor-*` skills obeys the same invariant — write fragments, never aggregates, and end by regenerating the index — which is what lets twelve independently-authored skills compose into one coherent system instead of forty engineers' worth of drift. The corpus-level failure to design against is combinatorial, not additive: value from composition grows roughly with the number of *pairs* of skills that can meaningfully chain, but so does the number of ways an ambiguous description collides with a neighboring one.

## Why this gets asked

Because by 2026 "we have forty skills" is a common answer and "do they compose into something, or are they forty unrelated files that happen to share a directory" is the question that actually distinguishes a system from a pile. The interviewer has seen both failure directions at fleet scale: a skill corpus where half the skills silently stopped firing because nobody tracked which ones were still invoked, and a corpus where two skills' descriptions overlapped just enough that the model picked the wrong one on a fair fraction of requests and nobody noticed until a customer-facing action fired from the wrong skill. They want to know if you think about a skill as a standalone artifact you write once, or as one node in a system with its own versioning, testing, and composition contract that has to hold as the corpus scales past what any one person authored.

---

## Lineage: past → present → future

**What came before.** Before skills, the two options for shipping a reusable agent capability were putting it in the system prompt (which `T28-context-files` and `T28-skills-design` both cover as the thing that grows without bound and pays a token tax on every single turn regardless of relevance) or a manual slash command, one file, invoked only when someone remembered to type it and typically containing everything inline because there was no directory to put supporting material in. Neither scaled past a handful of capabilities: system-prompt bloat degraded every request, and command files with no progressive loading meant "add a reference doc" meant "add it to every invocation's cost." The deeper problem, underneath both, was that capability had no *unit* — no independently versionable, independently testable, independently loadable piece smaller than "the whole prompt" and bigger than "one function call."

**Where it stands now.** Skills are that unit, and the convergence across the industry is the strongest evidence the abstraction is structurally correct rather than a vendor feature. Anthropic formalized Agent Skills in October 2025 and released the format as an open standard in December 2025; by 2026 it has been adopted by over 20 coding agents, and the format's cross-tool portability was discovered as much as designed — OpenAI had independently shipped a structurally identical mechanism in Codex before the open standard formalized the convergence, using the same file naming, metadata shape, and directory layout ([Agent Skills Ecosystem Report 2026, Agentman, accessed 2026-08-01](https://agentman.ai/blog/agent-skills-ecosystem-report-2026)). Microsoft's Agent Framework ships an equivalent skills provider that "discovers and progressively loads Agent Skills from the file system," independently arriving at the same shape (`T28-skills-design` covers this convergence in more depth for the single-skill mechanics). The genuinely new discipline at 2026 scale is architectural rather than mechanical: a formal paper explicitly titled *Harnessing Agent Skills: Architectural Patterns and a Reference Architecture for Skill-Mediated LLM Agents* (arXiv 2606.20631, accessed 2026-08-01) treats skill corpora as a system-design object with its own composition patterns (serial, parallel, conditional routing, recursive sub-skill invocation) rather than a bag of independent files, which is the framing this module adopts. The live disagreement is scale-shaped: the marketplace side reports explosive growth (a few thousand skills in December 2025 to 400,000+ by mid-March 2026, and separately over 800,000 community-contributed skills reported by mid-2026) which is real evidence of adoption and also a live warning, since a marketplace at that scale has no shared quality bar and `T28-skills-design`'s security notes about a checked-in skill granting itself tool access apply with more force the more skills you pull from outside your own repo.

**Where it's heading.** High confidence: composition becomes explicit rather than incidental — research prototypes (SkillComposer, arXiv 2606.06079 and 2606.32025) already resolve "which skills to load, how many, and in what order" as a joint decision rather than independent per-skill triggering, which is the mechanized version of the manual dependency-ordering this repo's skills already encode by convention (`/tutor-add` before `/tutor-deepdive` writes content, `/tutor-debrief` before `/tutor-progress` reflects a real interview). Medium confidence: fleet-level tooling (description-conflict detection across a whole corpus, not just per-skill trigger testing) becomes standard practice, the natural extension of `T28-skills-design`'s single-skill eval harness to the scale where a 40-skill corpus needs to know not just "does skill X fire correctly" but "do skills X and Y compete for the same requests." Speculative: whether the reported gains (30-50% fewer planning errors, 16+ percentage point task-completion improvement) generalize as corpora scale past the tens-of-skills range most reported figures were measured at, or whether the combinatorial collision risk this module names starts eating the gains past some corpus size nobody has published data for yet.

---

## Mental model

Two different objects, and the architecture of one constrains the other:

```
   SINGLE SKILL (T28-skills-design's object)         SKILL CORPUS (this module's object)

   ┌─────────────────────────┐                       ┌──────────────────────────────────┐
   │ description (retrieval   │                       │ N skills, each independently      │
   │  query) → body (loads    │      one of N         │ authored, versioned, tested        │
   │  on match) → supporting  │  ◀──────────────────  │                                    │
   │  files (on demand)       │                       │ COMPOSITION: does skill A's        │
   └─────────────────────────┘                       │ output become skill B's input?    │
                                                       │                                    │
   quality bar: does THIS      the corpus quality      │ CONFLICT: do two descriptions      │
   skill fire correctly?       bar is different:       │ compete for the same request?     │
                                is the CORPUS           │                                    │
                                coherent as it grows    │ INVARIANT: does every skill in     │
                                past what one person     │ the corpus obey the SAME rule      │
                                can hold in their head   │ about how it writes/reads state?  │
                                                       └──────────────────────────────────┘

   VALUE OF A CORPUS GROWS COMBINATORIALLY, RISK GROWS WITH IT:
     10 skills → up to 45 possible two-skill compositions (n·(n-1)/2)
     ...and up to 45 possible two-skill DESCRIPTION COLLISIONS, same arithmetic
```

The one-sentence version: **a single skill's quality question is "does it fire correctly"; a corpus's quality question is "does it stay one coherent system, or does it become forty files that happen to share a directory."**

---

## How it actually works

### 1. Skill vs tool vs subagent vs prompt, as a system-design decision

`T28-skills-design` gives the per-artifact decision procedure (does it always apply → rule; must it happen identically → code; etc.). At the corpus level, the same four options recur as a *portfolio* question: what should the mix look like across your whole system, not just for one capability.

| Mechanism | Cost profile | Composability | Where it belongs in a skill-mediated system |
|---|---|---|---|
| **Skill** | Near-zero until triggered (name+description in listing, ~100 tokens/skill); full body only on match | High — designed to be one node a workflow chains through | Judgment-dependent procedures: the majority of your capability surface should live here if it's genuinely conditional |
| **Tool / MCP server** | Schema cost in every session it's mounted, regardless of use | Medium — composable by the model calling several, but each call is atomic and typed | The deterministic, fragile operations a skill's body *invokes* rather than describes in prose (`T28-mcp-authoring` covers authoring these) |
| **Subagent** | A full context-isolation cold start (~3,800 tokens, `T28-subagent-architecture`) per invocation | Low across turns, high within one delegated task | Work that would flood the main context or needs a different tool scope — often what a skill delegates *to* via `context: fork`, not an alternative to a skill |
| **Prompt / rule** | Zero marginal cost (a `CLAUDE.md` line) or manual (typed each time) | None — not a callable unit | Facts that always apply, or one-off requests not worth building a unit for |

The architectural insight the single-skill decision procedure doesn't surface: **these four aren't mutually exclusive at the system level, they're layers.** A well-designed skill-mediated system typically has a skill as the entry point (judgment: which procedure applies), which invokes one or more tools (deterministic actions), which may delegate to a subagent (context isolation for a sub-task), governed by a handful of always-on rules (invariants that must never be violated regardless of which skill is active). Treating "skill vs tool" as a single either/or choice per capability, rather than "which layer does this piece of the capability belong at," is the design mistake that produces either a 400-line skill reimplementing what a tool should do, or a tool with no judgment layer in front of it forcing the model to reconstruct when-to-call-this from nothing.

### 2. The token-budget argument, with the numbers

This is the economic case for the architecture, not just the mechanism, and it's worth stating precisely because "skills save tokens" undersells what's actually being bought.

- **Listing cost is per-skill, tiny, and paid every session regardless of use:** roughly 100 tokens per skill for name+description in the standard's reference implementation, inside a listing budget capped at 1% of the context window in Claude Code specifically (`T28-skills-design`).
- **Body cost is paid only on match**, and the standard recommends keeping it under ~5,000 tokens, meaning a skill that never fires this session costs ~100 tokens, not ~5,000.
- **The reported system-level payoff:** 30-50% reduction in planning errors, a 16+ percentage-point improvement in task completion, and 3-8x context-budget efficiency versus loading equivalent capability into a monolithic system prompt ([Agent Skills Ecosystem Report 2026, accessed 2026-08-01](https://agentman.ai/blog/agent-skills-ecosystem-report-2026)). The mechanism behind the task-completion number is not mysterious: a system prompt with forty capabilities' worth of instructions competing for the model's attention on every single turn measurably degrades performance on the capability actually needed *this* turn, the same crowding effect `T28-context-files` documents for CLAUDE.md bloat, generalized to skills.
- **The corpus-scale version of the same argument:** a 40-skill corpus with progressive disclosure costs roughly `40 × 100 ≈ 4,000` tokens of listing overhead regardless of which skill fires, versus a monolithic prompt that would need to contain all forty procedures' worth of instructions on every turn — the ratio between those two numbers *is* the efficiency argument, and it gets better, not worse, as the corpus grows, provided the listing budget itself doesn't overflow (`T28-skills-design`'s overflow-drops-least-invoked-first behavior is the failure mode when it does).

The counter-consideration to state honestly: these figures are measured on corpora in the tens-of-skills range that most reported studies used. Whether the ratio holds, degrades, or improves further at hundreds of skills is not established by anything cited here — extrapolating linearly past the measured range is the same mistake as trusting a benchmark's model ranking to hold on a workload nobody tested.

### 3. Composition patterns

Treating a corpus as a system means naming how its pieces combine, not just whether each one fires:

- **Serial**: skill A's output is skill B's input, e.g. `/tutor-debrief` logs a real interview and updates `PATTERNS.md`, and a later `/tutor-start` reads that file to decide what to study next. Neither skill calls the other directly; they compose through a shared artifact on disk, which is a looser and more robust coupling than a direct call, because either skill can run independently and the composition still degrades gracefully (no debrief yet just means no pattern signal, not a broken pipeline).
- **Parallel**: independent skills contributing to the same outcome without ordering constraints, e.g. `/tutor-lab` and `/tutor-cheatsheet` can both run against the same module in either order, both reading the module file and writing to disjoint output directories.
- **Conditional routing**: one skill's description explicitly defers to another, e.g. a `deploy` skill's `when_to_use` stating "do NOT use for writing a migration from scratch" (`T28-skills-design`'s example), which is routing expressed as negative space rather than as a call.
- **Recursive / nested invocation**: a skill running in a forked subagent (`context: fork` + `agent:`) that itself preloads other skills, which `T28-subagent-architecture` documents as a full-content-injection contract different from the regular session's progressive listing — the nested skill's cost model changes the moment it's inside a subagent.

The corpus-design implication: serial composition through shared artifacts (files, not direct calls) is the pattern that scales best, because it doesn't require skill A to know skill B exists — it only requires both to agree on the shape of what they read and write, which is exactly the fragments-not-aggregates invariant in the next section.

### 4. Reference architecture: this repo's `skills/`

The twelve `/tutor-*` skills in this repo (`skills/`) are a working instance of a corpus-level architecture, and the three decisions worth extracting as general patterns are visible directly in `skills/README.md` and `skills/install.ps1`.

**Repo-as-source-of-truth, with an explicit install step.** The skills live in the repo, versioned alongside the curriculum content they operate on, and `install.ps1` copies each `SKILL.md` into `~/.claude/skills/<name>/` so they work in any session, not only when the working directory is this repo — with an explicit warning that the account copy "does not track the repo" and must be re-synced after every edit. This is a one-way, explicit, re-runnable sync rather than a live link, which is the correct tradeoff for a corpus a single person maintains: it trades "always current" for "trivially auditable" — you can diff the repo against a git history to see exactly what changed, and a stale account copy fails loudly (the old behavior, not silently-wrong behavior) rather than depending on some symlink or watch process staying alive across machine reboots.

**Each skill drives repo specs rather than restating them.** `/tutor-add`'s `SKILL.md` does not contain a copy of the module-line format, the track-dict format, or the sprint-weekend rules — it points at `app/build_data.py` as "the source of truth" and describes *how to edit it correctly*, including the specific failure mode of renaming a slug after content exists (breaks the join key between cards, drills, and the curriculum file). If the format in `build_data.py` changes, the skill's instructions about *editing* it stay correct without modification, because the skill never duplicated the format itself. This is the corpus-level version of `T28-skills-design`'s guidance to add only what the model doesn't already have: at corpus scale, it additionally means not letting any one skill fork its own copy of a fact that a dozen other skills also depend on.

**The fragments-not-aggregates invariant, obeyed identically by every skill that writes content.** `skills/README.md` states it as a repo-wide rule: content is written to `app/data/cards/<module-id>.json` and `app/data/drillsets/<module-id>.json`, one file per module, and nothing hand-edits the generated aggregates (`flashcards.json`, `drills.json`) or their `.js` twins, which `build_data.py` regenerates by merging fragments by id. Every skill that produces flashcards or drills — `/tutor-deepdive`, `/tutor-cheatsheet`, `/tutor-debrief` — obeys this identically, which is what makes twelve independently-invoked skills safe to run in any order without stepping on each other's output: two skills writing to two different fragment files can never race on the same file the way two skills hand-editing one aggregate would. This is the concrete, load-bearing version of the "compose through shared artifacts, not direct calls" pattern from the previous section — the shared artifact's *shape* (fragments, merged by a deterministic build step) is the actual contract, and it is enforced by convention plus a documented rule, not by code, which is itself worth noting honestly as the weakest link in this reference architecture (see Tradeoffs).

**The reads/writes table as an interface contract.** `skills/README.md`'s table (each skill's row: reads, writes) is a corpus-level interface declaration that lets you answer "if I change the shape of `SESSION-LOG.md`, which skills break" by reading one table instead of opening twelve files — the fleet-scale equivalent of a single skill's `description` being the one place its behavior is discoverable without opening the body.

### 5. Versioning and distribution at fleet scale

`T28-skills-design` names the single-skill gap precisely: no `version` field, no dependency declaration, no deprecation mechanism in the SKILL.md format itself. At corpus scale this gap compounds, because a description edit to skill A can silently break the trigger accuracy of skill B if their vocabularies now overlap, and nothing in the format detects that automatically.

What a fleet-scale practice actually needs, beyond the single-skill eval loop:

- **A corpus-wide description-collision check**, run whenever any skill's description changes: does the edited description now overlap with another skill's should-trigger set. This doesn't exist as tooling in the format yet (this module flags it as a real gap, per the lineage section's "medium confidence" direction), and the manual substitute is re-running the *other* skills' should-not-trigger sets whenever one skill's description changes, not just that skill's own.
- **A single source of truth with an explicit sync step**, which this repo's `install.ps1` demonstrates at the scale of one person's account; at team scale the equivalent is a plugin or managed-settings distribution (`T28-skills-design`'s enterprise > personal > project precedence), but the underlying principle — one place edits happen, one explicit step propagates them, and staleness is detectable rather than silent — is the same regardless of scale.
- **Shared invariants documented once, not per-skill.** This repo's fragments-not-aggregates rule lives in `skills/README.md`, not repeated inside each of the twelve `SKILL.md` files — a corpus-wide invariant belongs in a corpus-wide document, and any skill's body should reference it rather than restate it, for the same reason a skill's body shouldn't restate a fact `CLAUDE.md` already states.

### 6. Failure modes at corpus scale

Two failure modes are already named per-skill in `T28-skills-design` (a skill that never fires because its description is wrong; one that fires too eagerly and hijacks unrelated requests). At corpus scale they compound into a distinct, observable third failure:

**Failure mode: description collision.** As a corpus grows, two independently-authored skills' descriptions increasingly overlap in vocabulary, and the observable symptom is nondeterministic-looking behavior — the same or a very similar user request triggers skill A on one session and skill B on another, with no code change in either skill, because the model's selection is matching against a listing that now has two plausible candidates where it used to have one. This is distinct from either single-skill failure mode: both skills individually pass their own trigger-accuracy tests (each hits 9-10/10 on its own should-trigger set), and the collision is invisible until you specifically test *across* the corpus, checking whether skill A's should-trigger prompts ever fire skill B and vice versa.

---

## Build it from scratch

A minimal corpus-level check that catches description collision before shipping a new or edited skill, extending `T28-skills-design`'s single-skill trigger-accuracy harness to the fleet:

```python
# untested sketch — illustrates the corpus-level check, not a shipped tool
from dataclasses import dataclass

@dataclass
class SkillSpec:
    name: str
    description: str
    should_trigger: list[str]     # prompts that SHOULD fire this skill
    should_not_trigger: list[str] # prompts that should NOT fire this skill

def corpus_collision_check(corpus: list[SkillSpec], invoke_fresh_session) -> list[dict]:
    """For every skill's should-trigger prompt, check whether it ALSO fires
    any OTHER skill in the corpus. A well-isolated corpus has zero cross-hits."""
    collisions = []
    for skill in corpus:
        for prompt in skill.should_trigger:
            fired = invoke_fresh_session(prompt)   # returns set of skill names that loaded
            others = fired - {skill.name}
            if others:
                collisions.append({
                    "prompt": prompt,
                    "intended": skill.name,
                    "also_fired": list(others),
                })
    return collisions

def run_full_corpus_audit(corpus: list[SkillSpec], invoke_fresh_session) -> dict:
    """The fleet-scale extension of T28-skills-design's per-skill confusion
    matrix: per-skill trigger accuracy PLUS cross-corpus collision rate."""
    per_skill = {
        s.name: {
            "should_trigger_hit_rate": sum(
                s.name in invoke_fresh_session(p) for p in s.should_trigger
            ) / max(len(s.should_trigger), 1),
        }
        for s in corpus
    }
    return {
        "per_skill": per_skill,
        "collisions": corpus_collision_check(corpus, invoke_fresh_session),
    }
```

Run this whenever any skill's description changes, not just when a new skill is added — an edit to skill A's vocabulary is exactly as capable of colliding with skill B as a brand-new skill is, and `T28-skills-design`'s guidance to re-test on every description edit applies at the corpus level with an extra dimension: re-test *other* skills' should-not-trigger sets too, not just the edited skill's own.

---

## How it's done in production

| What production adds | Why it matters |
|---|---|
| **Description-collision CI check** | Runs the corpus audit above on every PR touching a `SKILL.md`, catching an overlap before it ships rather than after users report nondeterministic-seeming behavior |
| **A documented reads/writes contract per skill** (this repo's README table) | Makes "what breaks if I change this file's shape" answerable by reading one table instead of grepping every skill body |
| **A shared-invariant document, referenced not restated** | Corpus-wide rules (this repo's fragments-not-aggregates) live once; every skill's body links to it, so the rule can evolve in one place |
| **Marketplace/plugin distribution with a review gate** | At team or public scale, `T28-skills-design`'s security note (a checked-in skill can grant itself tool access via `allowed-tools`) means a marketplace of 800,000+ community skills needs a trust boundary a personal repo's twelve skills don't |
| **Fleet-level invocation telemetry** | Which skills fire, how often, and for whom — the corpus-scale version of `T28-skills-design`'s "listing budget drops least-invoked skills first," except now it's a design signal (prune the long tail) rather than a silent failure discovered by accident |

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Same or similar request fires a different skill on different sessions, no code changed | Description collision between two independently-authored skills | Corpus-wide collision audit on every description edit, not just per-skill trigger testing |
| A skill that worked for months stops firing after unrelated skills were added | Listing budget overflow, descriptions dropped least-invoked-first (`T28-skills-design`) | Track invocation counts at corpus level; prune or `disable-model-invocation` low-value skills before the budget forces it |
| Two skills both write to the same output file and one's write clobbers the other's | No fragments-not-aggregates-equivalent invariant; skills write aggregates directly | Every skill that produces content writes its own fragment; a single build step merges by id |
| An edit to one skill's shared dependency (a spec format, a file shape) silently breaks three other skills | Skills each duplicated a copy of the fact instead of referencing one source of truth | Point every skill at the single spec/source; skills describe how to use it, not what it currently says |
| A teammate's skill behaves differently than the one in the repo | Personal account copy is stale relative to the repo (no re-sync after an edit) | Explicit, documented sync step (`install.ps1`-equivalent) with a stated staleness warning, re-run on every edit |
| A marketplace-sourced skill silently gained broad tool access | No review gate on externally-sourced skills before trusting the workspace | Treat third-party skills as untrusted input; read before trusting; `skillOverrides` to disable unreviewed ones |

---

## Tradeoffs & when NOT to build a skill-mediated architecture

- **Don't reach for skills as the default container for every capability.** `T28-skills-design`'s per-artifact decision procedure still applies at every node of a corpus — a corpus of forty "skills," six of which are unconditional facts that belong in `CLAUDE.md` and four of which are fragile deterministic procedures that belong in scripts, is a corpus with ten real skills and thirty pieces of misclassified content diluting the listing budget for the ten that matter.
- **Don't build fleet-level tooling (collision detection, invocation telemetry) before you have a fleet.** A corpus of three or four skills doesn't need a CI collision check; the manual re-test `T28-skills-design` already prescribes per edit is sufficient. The fleet-scale concerns in this module earn their cost somewhere in the range of a dozen-plus actively-used skills, not from skill one.
- **Don't let composition happen implicitly through undocumented shared files.** This repo's fragments-not-aggregates pattern works because it's written down in `skills/README.md` as a rule every skill must obey, not because it emerged naturally — an undocumented convention that "just happened to work" is one skill edit away from two skills silently racing on the same file.
- **Don't trust marketplace-scale skill counts as evidence of marketplace-scale quality.** 800,000+ community skills is adoption evidence for the *format*, not a quality signal for any individual skill in that pool — the security and collision risks this module names apply with more force, not less, the larger and less-curated the source.
- **The honest counter-argument to name:** a corpus of skills with no enforced schema, no version field, and (per this section) no built-in collision detection is a weaker engineering artifact than a corpus of typed tools with the same capability, and the critics `T28-skills-design` quotes on this point are right for anything mechanical. The case for the architecture is specifically that judgment-dependent procedures don't have a schema to enforce in the first place, and progressive disclosure's token economics are real — but that case gets weaker, not stronger, as you cram non-judgment-dependent content into skills because the container is convenient.

---

## Interview questions

### Q1 — What's the difference between the single-skill design question and the corpus-level design question?
**Testing:** whether you distinguish authoring one skill from architecting a system of them.
**Answer:** A single skill's question is "does this fire correctly" — trigger accuracy and output quality, per `T28-skills-design`'s two-measurement testing model. A corpus's question is whether it stays one coherent system as it grows: does composition happen deliberately (skill A's output feeding skill B), do descriptions collide as vocabulary overlaps, and does every skill obey the same invariant about how it reads and writes shared state. A corpus can have every individual skill passing its own trigger-accuracy test and still be incoherent as a system.
**Follow-up trap:** *"At what corpus size does the distinction start to matter?"* — roughly a dozen actively-used skills, which is also where fleet-level tooling like collision detection starts earning its cost; below that, manual per-edit re-testing is sufficient and building CI infrastructure for it is premature.

### Q2 — Design the corpus architecture for a set of internal developer-productivity skills. What's your first structural decision?
**Testing:** whether you reach for composition patterns or just list skill ideas.
**Answer:** Whether skills compose through shared artifacts (files on disk with an agreed shape) or through direct invocation. Shared-artifact composition is looser coupling — either skill runs independently, and skill A not having run yet just means skill B has less signal, not a broken pipeline — which is the pattern this repo's `/tutor-debrief` → `PATTERNS.md` → `/tutor-start` chain demonstrates. I'd default to that over direct skill-calls-skill unless there's a specific reason two skills need synchronous ordering.
**Follow-up trap:** *"What if the shared artifact's shape needs to change?"* — that's exactly why the fragments-not-aggregates invariant matters: if every skill writes its own fragment and a separate build step merges them, changing the merge logic touches one place; if skills wrote directly to a shared aggregate, changing its shape means auditing every skill that touches it.

### Q3 — Your team has 40 skills. How do you know if any two of them compete for the same requests?
**Testing:** whether you know description collision as a named corpus-scale failure.
**Answer:** Run every skill's should-trigger prompt set against the *whole* corpus, not just check whether it fires its own skill — record any prompt that fires more than one skill. This is the corpus extension of `T28-skills-design`'s per-skill confusion matrix: a skill can score 9-10/10 on its own should-trigger set and still collide with a neighbor, because that test only checks "does my skill fire," never "does *only* my skill fire."
**Follow-up trap:** *"Two skills legitimately need overlapping trigger vocabulary. Now what?"* — differentiate on `paths:` if the overlap is location-dependent, or make one `user-invocable: false` (model-only background knowledge) and the other `disable-model-invocation: true` (explicit command) to remove the competition mechanically rather than through description tuning, per `T28-skills-design`'s Q7.

### Q4 — Walk me through this repo's `skills/` directory as a reference architecture. What's the load-bearing design decision?
**Testing:** whether you can extract general principles from a specific worked example.
**Answer:** Repo-as-source-of-truth with an explicit, re-runnable, one-way install step (`install.ps1` copying into `~/.claude/skills/`), each skill pointing at the actual spec (`app/build_data.py`) rather than restating its format, and a corpus-wide fragments-not-aggregates invariant every content-writing skill obeys identically. The load-bearing piece is the invariant: it's what lets twelve independently-invoked skills run in any order without racing on shared output, because they never write to the same file — they write disjoint fragments that a separate deterministic build step merges.
**Follow-up trap:** *"Where's the weakest link in that architecture?"* — the invariant is enforced by convention and documentation, not by code. Nothing stops a thirteenth skill from hand-editing the aggregate directly; the protection is a README rule, which is a Level 1 instruction in `T28-claude-architect`'s terms, not Level 3 enforcement. A stronger version would add a pre-commit or CI check that rejects a diff touching the generated aggregates directly.

### Q5 — Give me the token-budget argument for a skill-mediated architecture, with numbers.
**Testing:** whether the economic case is memorized as numbers or as a vibe.
**Answer:** Listing cost is roughly 100 tokens per skill (name + description), paid every session regardless of use, capped at 1% of the context window in Claude Code specifically. Body cost — up to the recommended ~5,000-token ceiling — is paid only on a match. The reported system-level payoff versus loading equivalent capability into a monolithic system prompt: 30-50% fewer planning errors, a 16+ percentage-point task-completion improvement, and 3-8x context-budget efficiency. At corpus scale, a 40-skill corpus costs roughly 4,000 tokens of listing overhead versus a prompt that would need all forty procedures' worth of instructions on every turn regardless of relevance.
**Follow-up trap:** *"Does that ratio hold at 400 skills?"* — not established by anything I'd cite confidently; the reported figures come from corpora in the tens-of-skills range. Extrapolating linearly past the measured range is the same mistake as trusting a benchmark ranking to generalize to an untested workload, and the listing-budget overflow behavior (`T28-skills-design`) is a concrete mechanism by which the ratio could degrade well before 400.

### Q6 — Name the composition patterns a skill corpus can use, and which one scales best.
**Testing:** whether you have a taxonomy or just "skills can work together."
**Answer:** Serial (A's output feeds B's input, ideally through a shared artifact rather than a direct call), parallel (independent skills contributing to the same outcome with no ordering constraint), conditional routing (one skill's `when_to_use` explicitly defers to another via negative space), and recursive/nested invocation (a skill forking a subagent that itself preloads other skills). Serial composition through shared artifacts scales best, because it doesn't require skill A to know skill B exists — only that both agree on the artifact's shape, which is a much weaker and more durable coupling than a direct call.
**Follow-up trap:** *"What breaks recursive/nested composition specifically?"* — the cost model changes inside a subagent: `T28-subagent-architecture` documents that a subagent's preloaded skills inject full content at startup rather than following the regular session's progressive-listing contract, so a skill that's cheap in the main session can be a real cold-start cost once nested, and treating the two contracts as identical is a common corpus-design mistake.

### Q7 — A skill that fired reliably for months just stopped. You've added twenty new skills since. Diagnose at the corpus level.
**Testing:** whether you connect a single-skill symptom to a corpus-scale cause.
**Answer:** Almost certainly listing-budget overflow: the budget is a fixed fraction of the context window, adding twenty skills increased total listing size, and `T28-skills-design`'s documented overflow behavior drops descriptions starting with the least-invoked skills first, silently. This is a corpus-scale problem wearing a single-skill symptom — the fix isn't in the affected skill's file at all, it's a corpus-level decision about which skills earn a place in the budget.
**Follow-up trap:** *"How do you decide which of the sixty skills to prune?"* — invocation telemetry at the corpus level, the fleet-scale analog of the same budget mechanism: rank by actual usage over some window and cut the zero-invocation tail first, the same prioritization `T28-skills-design` recommends for a single bloated corpus, just applied as an ongoing practice rather than a one-time cleanup.

### Q8 — Is a skill corpus with 800,000 community-contributed entries in a marketplace a sign of a mature ecosystem?
**Testing:** whether you can separate adoption evidence from quality evidence.
**Answer:** It's strong evidence the *format* won cross-tool adoption — the same open standard, the same file shape, working unmodified across 20+ coding agents. It is not evidence about the quality or safety of any individual skill in that pool. `T28-skills-design`'s security note applies with more force at that scale: a checked-in skill can grant itself broad tool access via `allowed-tools` once a workspace is trusted, and a marketplace at that size has no uniform review bar enforcing that every entry is safe to trust blindly.
**Follow-up trap:** *"So would you pull skills from that marketplace for a production system?"* — selectively, with the same review discipline `T28-skills-design` prescribes for any checked-in project skill: read it before trusting the repo, prefer skills from a curated internal marketplace or managed-settings distribution for anything with real tool access, and treat marketplace scale as a discovery mechanism, not a trust signal.

### Q9 — When is a skill-mediated architecture the wrong system design?
**Testing:** the senior "when not to" at the architecture level, not the per-file level.
**Answer:** When most of your capability is either unconditional (facts that always apply — belongs in a rules file, not a skill corpus) or deterministic and fragile (belongs in scripts and tools, invoked by a thin judgment layer, not described in prose across dozens of skills). A corpus where most entries are misclassified content dilutes the listing budget for the few genuinely judgment-dependent procedures that actually benefit from progressive disclosure. Building fleet-level tooling (collision detection, invocation telemetry, a formal versioning scheme) before you have more than a handful of actively-used skills is also premature — that overhead earns its cost somewhere past a dozen skills, not from the first one.
**Follow-up trap:** *"Your org insists on 'a skill for everything' as a policy. What's your pushback?"* — that policy misclassifies content by construction, and the honest counter-argument stands: skills have no schema, no version field, and no built-in collision detection, so anything mechanical is a weaker engineering artifact as a skill than as a typed tool. The pushback is to keep the per-artifact decision procedure (`T28-skills-design`) as the actual policy, with "skill" as one of four outcomes, not the default.

### Q10 — How would you version a skill corpus that multiple teams contribute to?
**Testing:** whether you've thought past the single-repo, single-maintainer case this module's reference architecture assumes.
**Answer:** Since the format itself has no version field or dependency declaration (a real gap `T28-skills-design` names), the practice has to live outside the format: a single source-of-truth repo per corpus (the pattern this repo demonstrates at one-person scale), a corpus-wide shared-invariants document every skill references rather than restates, a description-collision check gating any PR that adds or edits a skill, and distribution through a reviewed internal plugin or managed settings rather than each contributor syncing independently — which is the team-scale analog of this repo's `install.ps1`, except now the "explicit sync step" needs to be a review gate, not just a copy command.
**Follow-up trap:** *"What happens when two teams' skills' descriptions collide and neither team wants to change theirs?"* — that's a genuine decomposition-boundary question, not a tooling problem: per `T28-skills-design`'s Q7, if the overlap is real and both need to exist, differentiate mechanically (`paths:`, `disable-model-invocation` vs `user-invocable: false`) rather than relying on description-wording negotiation between teams, which doesn't scale and re-collides on the next edit either side makes independently.

### Q11 — What's the strongest argument against skill-mediated architectures as a whole, and how do you answer it?
**Testing:** whether you can steelman the critique, the closing-question pattern this track uses consistently.
**Answer:** A skill corpus with no schema, no enforced versioning, no built-in collision detection, and (in this repo's case) an invariant enforced only by documentation is a weaker engineering artifact, corpus-wide, than the equivalent capability built as typed tools with real interface contracts. For anything mechanical, that critique is simply correct. What the architecture buys that tools alone don't is specifically for judgment-dependent procedures — progressive disclosure means a corpus of forty skills costs a fraction of what forty procedures embedded in a system prompt would cost, and the industry-wide cross-tool convergence on the same file format is real evidence the tradeoff is structurally sound for that specific case, not just convenient.
**Follow-up trap:** *"So why not enforce the fragments-not-aggregates invariant in code instead of documentation, given you've just said documentation-only enforcement is a weakness?"* — that's the right question and the honest answer is it should be: a pre-commit or CI check rejecting a diff that touches `app/data/flashcards.json` or `drills.json` directly would convert this specific invariant from Level 1 (documented convention) to Level 3 (enforced), per `T28-claude-architect`'s distinction, and its absence in this repo's actual reference architecture is a real, nameable gap rather than a hypothetical one.

---

## Red flags that fail you

- Treating "is this a skill" as the only design question, with no corpus-level view.
- No answer for how you'd detect two skills' descriptions colliding.
- Believing an undocumented shared-file convention between skills is as safe as a documented, enforced one.
- Citing marketplace skill counts as a quality signal rather than adoption evidence.
- Building fleet-level tooling for a corpus of three skills, or having none at all for a corpus of sixty.
- Not knowing that a subagent's preloaded skills follow a different (full-injection) cost contract than the regular session's progressive listing.
- Treating skill-vs-tool-vs-subagent-vs-prompt as a single per-capability choice rather than layers that compose.
- No honest counter-argument when asked whether skills are a good corpus-scale engineering artifact.

## Cheat card

```
SKILL-MEDIATED ARCHITECTURE = progressive disclosure as a SYSTEM property, not
  a single-file trick. Corpus question != single-skill question:
    single skill: does it fire correctly (T28-skills-design)
    corpus:       does it stay ONE coherent system as it grows

CROSS-TOOL CONVERGENCE: Anthropic open standard Dec 2025, 20+ coding agents by
  2026, OpenAI/Codex independently shipped the same shape pre-formalization.
  marketplace scale: ~400K (mid-Mar 2026) to 800K+ (mid-2026) community skills
  -- ADOPTION evidence, NOT a quality signal for any one skill.

TOKEN-BUDGET NUMBERS: ~100 tok/skill listing (name+desc), body ~5,000 tok cap,
  paid only on match. Reported system payoff vs monolithic prompt:
    30-50% fewer planning errors · 16+ pp task-completion improvement
    · 3-8x context-budget efficiency
  40-skill corpus ~4,000 tok listing overhead regardless of which fires.
  NOT established past the tens-of-skills range measured -- don't extrapolate.

DECISION LAYERS (not a single either/or per capability):
  SKILL    = judgment entry point, near-zero cost until triggered
  TOOL/MCP = deterministic action the skill's body INVOKES (T28-mcp-authoring)
  SUBAGENT = context isolation the skill DELEGATES to (context:fork)
  RULE     = always-on invariant governing ALL skills, not a per-capability choice

COMPOSITION PATTERNS: serial (shared ARTIFACT, not direct call -- scales best)
  · parallel (disjoint outputs, no ordering) · conditional routing (negative
  space in when_to_use) · recursive (nested subagent, DIFFERENT cost contract:
  full injection, not progressive listing)
  value grows COMBINATORIALLY: n skills -> up to n(n-1)/2 pairwise compositions
  ...and the same arithmetic for pairwise DESCRIPTION COLLISIONS

REFERENCE ARCHITECTURE (this repo's skills/):
  repo = source of truth, install.ps1 = explicit one-way re-runnable sync
  each skill points at the REAL spec (build_data.py), never restates its format
  FRAGMENTS NOT AGGREGATES: every content-writing skill writes app/data/cards/
    <id>.json + drillsets/<id>.json, one file per module. NEVER hand-edit
    flashcards.json/drills.json -- a build step merges by id.
    -> lets 12 independently-invoked skills run in ANY order with no race
  weak link: invariant enforced by README convention, NOT code (Level 1, not
    Level 3 -- T28-claude-architect). no CI check rejects a direct aggregate edit.
  reads/writes table = corpus-level interface contract in one place

FAILURE MODE: description collision -- two skills each pass their OWN trigger
  test individually, but the SAME prompt fires a different one on different
  sessions. invisible until you test ACROSS the corpus, not just within it.
  fix: run every skill's should-trigger set against the WHOLE corpus.

WHEN NOT TO: most capability is unconditional (rule) or deterministic-fragile
  (tool/script) -- a corpus padded with misclassified content dilutes listing
  budget for the few skills that actually need it. fleet tooling before ~a
  dozen active skills is premature.
```

## Sources

- [Harnessing Agent Skills: Architectural Patterns and a Reference Architecture for Skill-Mediated LLM Agents](https://arxiv.org/pdf/2606.20631) — the formal treatment of skill corpora as a system-design object with composition patterns; accessed 2026-08-01
- [The Agent Skills Ecosystem in 2026: Who's Building, What's Working, and What's Next](https://agentman.ai/blog/agent-skills-ecosystem-report-2026) — cross-tool convergence, 20+ coding agents, the 30-50%/16pp/3-8x reported figures, marketplace growth numbers; accessed 2026-08-01
- [SkillComposer: Generative Skill Composition for LLM Agents](https://arxiv.org/pdf/2606.32025) and [SkillComposer (project page)](https://skill-composer.github.io/) — joint resolution of which skills to load, how many, and in what order; accessed 2026-08-01
- [Agent Skill Composition: The Architecture of Modular AI Capabilities](https://zylos.ai/research/2026-05-12-agent-skill-composition-modular-capability-architecture/) — serial/parallel/conditional/recursive composition taxonomy; accessed 2026-08-01
- `skills/README.md` and `skills/install.ps1` (this repo) — the reference architecture case study: repo-as-source-of-truth, the install step, the reads/writes table, and the fragments-not-aggregates invariant, read directly, not modified
- `curriculum/28-ai-assisted-architecture/03-skills-design.md` — single-skill mechanics (description budget, testing, frontmatter) this module builds on rather than repeats
- `curriculum/28-ai-assisted-architecture/04-subagent-architecture.md` — the different cost contract for skills preloaded into a forked subagent
- `curriculum/28-ai-assisted-architecture/09-claude-architect.md` — the Level 1/2/3 enforcement distinction applied here to the fragments-not-aggregates invariant's weak link

## Changelog
- 2026-08-01 — created
