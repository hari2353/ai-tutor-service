# Prompt Versioning, Registries, A/B Rollout, Auto-Revert on Regression

> **Track:** T07 Agentic AI · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T07-prompt-versioning` · **Tags:** production,critical

## The 30-second version

A prompt is not a string, it's a deployed artifact, and treating it like source code you diff and ship without an eval gate is how a one-line wording tweak becomes a production incident. A version must pin everything that determines behavior together — prompt template, model id, sampling params, the tool schema hash, and any few-shot examples — because a tool description broadened last week and a silent provider-side model update both change behavior with zero lines of prompt diff, and "the prompt version is unchanged" is not the same claim as "behavior is unchanged." A prompt change is a model change: it gets the same treatment — eval gate before rollout, canary with graduated traffic, and a decision rule that doesn't peek, because checking a live A/B test repeatedly on raw p-values inflates your false-positive rate from 5% toward 40%+. Auto-revert closes the loop: a named metric, a threshold, a time window, and a rollback that's a routing change back to the last-known-good pinned manifest, not a redeploy — with a median rollback latency in the tens of seconds once it fires. The failure this whole apparatus exists to prevent already happened in production once, publicly: three simultaneous harness-and-prompt changes degraded Claude Code's quality in April 2026 and took real time to diagnose specifically because nothing was versioned and gated independently.

## Why this gets asked

Because "we just edit the prompt in the code and redeploy" is the answer of a team that hasn't had an incident yet, and every interviewer asking this has had one: a prompt tweak that looked purely cosmetic silently changed tool-selection behavior, a rollout with no gate that regressed a metric nobody was watching until a customer complained, or an A/B test where someone eyeballed a dashboard on day one, declared a winner, and shipped a change that was actually noise. They want to know whether you treat a prompt with the same production discipline as a binary — versioned, gated, canaried, revertible — or whether "prompt engineering" in your mental model stops at getting a good answer once in a notebook.

---

## Lineage: past → present → future

**What came before.** Through 2023 and into 2024, prompts lived as string literals or f-strings in application code, versioned exactly as well as the surrounding code and no better — a prompt change shipped in the same pull request as an unrelated bug fix, with no independent eval, no independent rollback, and no record of what the prompt actually was at the time a given production response was generated. The pain that killed this was reproducibility and blast radius: when a response looked wrong six weeks later, nobody could say with confidence which prompt version produced it, and a prompt edit that regressed quality shipped with the same confidence as a null-safety fix, because nothing distinguished the two in the deploy pipeline. The first fix was moving prompts into config files or a database, which solved the "where does the current prompt live" problem and did nothing for "how do we know a change is safe" — that gap is exactly what `T07-agent-testing`'s "silent regression" failure mode describes in the broader agent-testing context, and it applies to prompts specifically with extra force, because prompts are the artifact most likely to be edited by someone who isn't running the eval suite.

**Where it stands now.** The field converged on prompt registries as dedicated infrastructure — PromptLayer, Braintrust, LangSmith's Prompt Hub, Langfuse, and others all ship the same core primitives now: a centralized store, version history with author and timestamp, git-like branching, and one-click rollback, with the market splitting into "registry as a feature bolted onto an observability platform" (Portkey, Helicone, LangSmith) versus "prompt lifecycle as the whole product" (Braintrust, Agenta, Vellum). The acquisition of Promptfoo by OpenAI in March 2026 for a reported $86M is a data point that prompt evaluation tooling is now considered core infrastructure, not a nice-to-have. The consensus mechanical point — and the one this module centers on — is that **versioning without an eval gate is just diff tracking**: you can see what changed, not whether it worked, and the gap that catches teams is that a version passing eval on a frozen test set can still degrade on live production distribution, because production traffic drifts away from whatever set you built the offline eval against. The live disagreement is where the gate sits: attach evaluators to a prompt version id and run continuously against sampled live traffic (write scores back to individual spans, not an aggregate dashboard), versus a heavier pre-merge gate against a curated golden set (`T07-agent-testing`'s CI-tier framing) before anything reaches canary at all. Most mature setups do both, in sequence.

**Where it's heading.** High confidence: the deployment manifest — not the prompt string alone — becomes the unit of versioning, because prompt text, model id, RAG index snapshot, and tool schema hash all independently determine behavior and any one changing without the others is an unreproducible deploy. This is already shipping as "prompt canaries" pinning all four together. Medium confidence: sequential/always-valid statistical methods (mSPRT-style, as GrowthBook and Statsig ship) replace fixed-horizon A/B analysis as the default for prompt rollouts specifically, because prompt experiments are exactly the kind of low-traffic, high-stakes, "someone will check the dashboard daily" experiment that peeking destroys. Speculative: fully automated prompt promotion with no human review step at all — several platforms describe eval-gated auto-promotion, but the honest current state is that auto-revert (catching a regression and rolling back) is more mature and more trusted than auto-promote (deciding a new version won without a human looking), and conflating the two overstates what's actually safe to automate today.

---

## Mental model

```
  A PROMPT VERSION IS A MANIFEST, NOT A STRING
  ──────────────────────────────────────────────────────────────────
    prompt_version:   v4.7                       ← the template + few-shot examples
    model:             claude-sonnet-4-6           ← exact model id, not "the model"
    params:            {temperature: 0.2, top_p: 1, max_tokens: 2048, stop: [...]}
    tools:             tool_schema_hash: a3f9c2d   ← a broadened tool description
                                                      changes behavior with ZERO
                                                      lines of prompt diff
    rag_index:         2026-04-15T08:00:00Z         ← a reindex changes retrieved
                                                      context with ZERO prompt diff

    ⇒ "the prompt is unchanged" is NOT the same claim as "behavior is unchanged."
      Any ONE of these five drifting independently is an unreproducible deploy.

  THE GATE SEQUENCE (a prompt change gets the SAME treatment as a model change)
  ──────────────────────────────────────────────────────────────────
    edit  →  offline eval (golden set, T07-agent-testing's CI tier)
          →  canary: 1% → 5% → 20% → 50% → 100%, manifest pinned at each stage
          →  online eval on SAMPLED LIVE traffic, scored per-span not per-dashboard
          →  decide a winner WITHOUT PEEKING (sequential test or pre-registered N)
          →  promote,  OR  auto-revert on a named metric/threshold/window

  ROLLBACK = A ROUTING CHANGE, NOT A REDEPLOY
  ──────────────────────────────────────────────────────────────────
    100% traffic ──▶ v4.7 (canary)          on breach: flip the router back to
                                             v4.6 (last-known-good manifest).
    v4.7 stays deployed, gets ZERO traffic, is now your debugging artifact.
```

The one thing to internalize: **a prompt is not special-cased relative to a model swap.** Every discipline that applies to shipping a new model version — eval before rollout, gradual exposure, a decision rule immune to peeking, and a fast, reversible rollback — applies identically to a wording change, because from the system's behavior the two are indistinguishable.

---

## How it actually works

### 1. What a version must pin, and why each piece is independently load-bearing

Five things, and the discipline is that changing any one of them, even if the others are byte-identical, is a new version:

- **Template.** The literal prompt text and structure, including few-shot examples if any are embedded — this is what people mean by "the prompt" and it's the smallest part of the story.
- **Model id.** Not "Claude" or "GPT" — the exact model identifier, because point releases change behavior and a silent provider-side update to a model alias (e.g. a `-latest` tag) is drift you didn't author but still shipped.
- **Sampling params.** Temperature, `top_p`, `max_tokens`, stop sequences. A temperature change from 0.2 to 0.7 is a behavior change of the same magnitude as a template edit, and it's the parameter most likely to get changed casually "just for this test" and forgotten.
- **Tool schema hash.** A tool description broadened or a parameter enum widened changes agent behavior with zero lines of prompt diff — this is the gap that catches teams who version the prompt file and nothing else, because their diff tool shows nothing changed.
- **Examples / retrieval snapshot.** Few-shot examples baked into the template are covered by the template hash, but externally retrieved examples or a RAG index snapshot are not — a reindex is a silent behavior change exactly like a tool schema change, and it needs its own pin (an index timestamp or a content hash) in the manifest.

The manifest, concretely:

```python
# untested sketch - the unit of deployment, not the prompt string alone
@dataclass(frozen=True)
class PromptManifest:
    prompt_version: str          # "v4.7" -- template + embedded few-shot hash
    model: str                   # exact id, e.g. "claude-sonnet-4-6", never an alias
    params: dict                 # {"temperature": 0.2, "top_p": 1, "max_tokens": 2048, ...}
    tool_schema_hash: str        # hash of the full bound-tool schema set
    rag_index_snapshot: str      # index id/timestamp, "" if no retrieval
    created_at: str
    created_by: str
```

Two of these five are the ones people skip, and skipping them is the named failure mode: **a tool description edit or a RAG reindex ships as an "unrelated" change in a different PR, the prompt version number never bumps, and a behavior regression traces to nothing in the prompt-diff history** — the observable symptom is a quality regression with a clean prompt-version git blame and no obvious culprit, exactly the shape of Anthropic's own April 2026 postmortem (`T07-harness-engineering`), where three independent harness-level changes — a reasoning-effort default, a caching bug dropping thinking history, and a verbosity-limiting system prompt tweak — degraded quality together and took real time to diagnose because nothing was versioned and gated as one unit.

### 2. Why versioning without evals is diff tracking

A registry with branching, diffing, and rollback answers "what changed and when." It does not answer "did the change help," and that second question is the entire point of iterating on a prompt at all. The gap that bites in practice: **a version that passes eval on a frozen offline test set can degrade on live production distribution, and no offline eval catches it**, because the test set was built against yesterday's traffic shape and production has since drifted — this is the same coverage-gap failure `T07-agent-testing` names for golden trajectories going stale, applied to prompts specifically.

The fix is attaching evaluators to the prompt version id itself and running them continuously against a sample of live traffic, writing scores back to individual spans rather than an aggregate dashboard number. "0.82 average score on yesterday's traffic" tells you nothing about which specific decisions failed; a per-span score lets you pull the actual failing traces and read them, the same "assert invariants you can inspect, not an opaque aggregate" principle that runs through `T07-agent-testing` and `T08-agent-eval`. Comparing a new version against current production on production samples — tens to a few hundred traces per version per metric is a realistic starting scale — beats comparing against a synthetic or frozen test set, precisely because production distribution is the thing you actually care about matching.

### 3. Canary rollout: what ramps, what gates, what timescale

Traffic ramps in stages — a common shape is **1% → 5% → 20% → 50% → 100%** — with the manifest fully pinned at every stage so a regression is attributable to exactly one deployed configuration. Two categories of signal gate advancement, and they operate on genuinely different timescales, which is the detail people get wrong by treating all metrics as equally fast:

- **Fast, continuous signals**: error rate, p99 latency, guardrail trip rate. These surface within minutes and can gate automatically on a short window — a guardrail trip rate above roughly 1.5x baseline in a 15-minute window is a realistic automated trigger.
- **Slow, statistical signals**: output-length distribution, sentiment distribution, refusal rate, session-abandonment rate, re-query rate, edit-to-accept ratio, and semantic drift via embedding cosine similarity or LLM-as-judge scoring against a baseline. These need enough samples to be trustworthy, and at 1-5% traffic routing with typical request volumes, reaching statistical confidence on a distribution shift can genuinely take **12-24 hours**, not minutes. A team that ramps from 5% to 100% in an hour because "nothing looks wrong yet" hasn't waited long enough for the signal that actually would have looked wrong to accumulate.

Rollback thresholds worth having as reference numbers, understanding they're illustrative defaults to calibrate against your own baseline noise, not universal constants: error-rate increase greater than roughly 1 percentage point, p99 latency increase greater than roughly 20%, automated eval score decrease greater than roughly 5%, and a semantic/coherence score drop below the measured noise floor of the metric itself — a threshold set below your own metric's baseline variance will auto-revert on noise, which is a foot-gun as real as no threshold at all.

### 4. Deciding a winner without peeking

This is the section every prompt-A/B setup gets wrong at least once. Checking a live experiment's raw p-value repeatedly and stopping the moment it crosses significance inflates your false-positive rate dramatically — checking roughly 20 times instead of committing to one look can push a nominal 5% false-positive rate toward 40% or higher, because each additional look is another chance for noise to cross the threshold, and the naive fixed-horizon test assumes exactly one look. Two disciplined options, and the wrong move is picking neither:

- **Fixed-horizon, pre-registered.** Decide the sample size (or duration) needed for your minimum detectable effect *before* the experiment starts, based on your metric's baseline variance, and commit to looking exactly once, at the end. Simple, statistically clean, and the discipline that's hardest to actually hold to when a dashboard is sitting right there.
- **Sequential / always-valid testing** (mSPRT-style, as shipped by GrowthBook and Statsig). Designed for continuous monitoring: the significance threshold adjusts dynamically as more data arrives, so checking the dashboard every hour doesn't inflate the false-positive rate the way naive repeated peeking does. This is the better fit for prompt experiments specifically, because "someone checks daily" is the realistic operating mode and pretending otherwise is how the peeking problem happens in practice rather than in theory.

The rule to state explicitly and hold to: **choose the method before the experiment starts, and don't switch mid-flight.** Switching from "we'll wait for the pre-registered sample size" to "it looks significant, let's ship it now" the moment an early result looks good is the single most common way a legitimate experiment design gets defeated by impatience.

### 5. Auto-revert: metric, threshold, window, mechanism

Auto-revert is the closed loop that makes canary rollout actually safe unassisted, and it needs all four pieces named explicitly or it's not a real control:

- **Metric.** One primary metric per rollout decision, chosen in advance — not "quality felt worse," a specific number: task-completion rate against ground truth (`T08-agent-eval`'s "never grade the agent's own summary" principle applies to prompt evals too), guardrail trip rate, or a calibrated LLM-judge score with a validated discriminating power.
- **Threshold.** A magnitude below which the change is noise and above which it's a real regression, calibrated against the metric's own measured baseline variance, not a round number picked for looking rigorous.
- **Window.** How long the metric must stay past threshold before it fires, balancing false-positive suppression (too short reacts to noise) against blast radius (too long ships a regression to more users for longer). A 15-minute window on a fast signal and a multi-hour window on a slow statistical one are both defensible for their respective signal types; using the same window for both is the mistake.
- **Rollback mechanism.** A routing change back to the last-known-good pinned manifest, not a redeploy — the previous version's artifact never left production, so recovery is flipping which manifest gets traffic, with a realistic **median rollback latency in the tens of seconds** once the threshold fires. The regressed version stays deployed with zero traffic, which converts it from an incident into a debugging artifact you can inspect without it hurting anyone.

### 6. Registry-vs-repo drift, and audit trail

A prompt registry (PromptLayer, Braintrust, LangSmith Prompt Hub) and your application's source repo are two systems of record for the same artifact, and drift between them is a specific, recurring failure: someone edits a prompt live in the registry UI for a fast fix, and the repo's copy — the one that gets deployed on the next full release — is now stale and silently reverts the fix on the next deploy. The fix is picking one source of truth and treating the other as a read-only mirror: either the registry is authoritative and deploys pull from it at build time, or the repo is authoritative and the registry is purely an observability/eval surface with no live-edit capability in production. Whichever you pick, the audit trail needs to answer, for any production response: which prompt version, which model id, which params, which tool schema hash, and which eval gate it passed before reaching that traffic percentage — the same fields `T07-human-oversight`'s audit-record design asks for, applied to a prompt promotion instead of an agent action.

---

## Build it from scratch

A minimal manifest-based rollout controller: pin, gate, ramp, decide without peeking, auto-revert.

```python
# untested sketch - illustrates the mechanism, not a production library
from dataclasses import dataclass, field
from collections import deque
import time

@dataclass(frozen=True)
class PromptManifest:
    version: str
    model: str
    params: dict
    tool_schema_hash: str
    rag_index_snapshot: str = ""

@dataclass
class RolloutStage:
    manifest: PromptManifest
    traffic_pct: int
    started_at: float = field(default_factory=time.monotonic)

class AutoRevertController:
    """One primary metric, one threshold, one window. Rollback = routing change."""
    STAGES = [1, 5, 20, 50, 100]

    def __init__(self, stable: PromptManifest, candidate: PromptManifest,
                 metric_threshold: float, window_s: float, min_samples: int):
        self.stable, self.candidate = stable, candidate
        self.threshold, self.window_s, self.min_samples = metric_threshold, window_s, min_samples
        self.stage_idx = 0
        self.current = RolloutStage(candidate, self.STAGES[0])
        self.window: deque[tuple[float, float]] = deque()   # (timestamp, metric_value)
        self.reverted = False

    def route(self) -> PromptManifest:
        """Deterministic routing: NOT a live coin flip re-decided every call."""
        return self.stable if self.reverted else self.current.manifest

    def record(self, metric_value: float):
        now = time.monotonic()
        self.window.append((now, metric_value))
        while self.window and now - self.window[0][0] > self.window_s:
            self.window.popleft()
        if len(self.window) < self.min_samples:
            return  # not enough samples yet -- do NOT decide on noise
        avg = sum(v for _, v in self.window) / len(self.window)
        if avg < self.threshold:
            self._revert(reason=f"metric {avg:.3f} below threshold {self.threshold}")

    def _revert(self, reason: str):
        self.reverted = True   # routing flips immediately; candidate manifest untouched
        # audit: record reason, window contents, stage at time of revert
        print(f"AUTO-REVERT: {reason} at stage {self.current.traffic_pct}% "
              f"-> routing 100% back to {self.stable.version}")

    def advance_stage(self):
        """Call only after the SLOW statistical signal has cleared for this stage's
        window -- do not advance on a fast signal alone."""
        if self.reverted:
            raise RuntimeError("cannot advance a reverted rollout")
        self.stage_idx += 1
        if self.stage_idx < len(self.STAGES):
            self.current = RolloutStage(self.candidate, self.STAGES[self.stage_idx])


if __name__ == "__main__":
    stable = PromptManifest("v4.6", "claude-sonnet-4-6", {"temperature": 0.2}, "a1b2c3")
    candidate = PromptManifest("v4.7", "claude-sonnet-4-6", {"temperature": 0.2}, "a1b2c3")
    ctrl = AutoRevertController(stable, candidate, metric_threshold=0.80,
                                 window_s=900, min_samples=30)
    for score in [0.85, 0.83, 0.81, 0.79, 0.76, 0.74]:   # simulated regression appearing
        ctrl.record(score)
    print("final route:", ctrl.route().version)
```

Two properties worth defending in an interview: routing is a **pure function of `reverted`**, not a live re-decision on every call, so a revert can't flap; and `record()` refuses to decide until `min_samples` is met, which is the code-level enforcement of "don't auto-revert on noise before you have enough data to distinguish signal from it."

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Quality regression traces to nothing in prompt-diff history | Tool schema or RAG index changed independently, prompt version never bumped | Pin all five manifest fields as one deployable unit; version bumps whenever ANY of them changes |
| A/B test declared a winner on day one, shipped, and quality didn't actually improve | Peeked at raw p-values repeatedly, stopped at the first significant-looking read | Pre-register sample size and look once, or use sequential/always-valid testing designed for continuous monitoring |
| New prompt version passes eval, degrades in production anyway | Offline eval ran against a frozen/stale test set, not live traffic | Attach evaluators to the version id, run continuously against sampled live traffic, score at the span level |
| Live registry edit got silently reverted on the next deploy | Registry and repo both treated as sources of truth, no sync discipline | Pick one system of record; the other is a read-only mirror |
| Auto-revert fires on ordinary noise | Threshold set below the metric's own baseline variance, or window too short for a slow signal | Calibrate threshold against measured baseline noise; use a longer window for statistical (not fast) signals |
| Canary ramped to 100% in under an hour, regression surfaced afterward | Distribution-shift signals need 12-24h at low traffic to reach confidence; team advanced on fast signals alone | Gate stage advancement on the slow statistical signal's confidence, not just error rate and latency |
| Nobody can say which prompt version produced a specific bad production response | No audit trail linking response to manifest | Tag every trace/span with the full manifest (version, model, params, tool hash, index snapshot) |
| Rollback took twenty minutes and required a redeploy | Rollback implemented as "revert the commit and redeploy" instead of a routing flip | Keep the last-known-good manifest live and route to it; rollback should be a config/router change, target tens of seconds |

---

## Tradeoffs & when NOT to use the full apparatus

- **A prototype with no production traffic doesn't need a registry, canaries, or auto-revert.** Versioning-as-diff-tracking (a git-tracked prompt file) is entirely sufficient until real users are affected by a regression; building the full manifest-and-canary machinery for an internal tool with five users is solving a problem you don't have.
- **Fixed-horizon testing is the wrong default when the realistic operating mode is daily peeking.** If you know a stakeholder will check the dashboard every morning, design for that with sequential testing rather than pretending you'll hold to a single-look discipline you won't actually keep.
- **Auto-revert without a validated metric is worse than no auto-revert.** An LLM-judge score that hasn't been checked for discriminating power (does it actually distinguish good from bad, per `T08-agent-eval`'s judge-calibration guidance) will auto-revert on judge noise as often as on real regressions, and a system that reverts unpredictably erodes trust in the mechanism faster than a manual process would.
- **Don't gate every prompt change with the full canary ramp.** A genuinely low-risk change — fixing a typo with no semantic content difference — doesn't need 1%→100% over 24 hours; reserve the full ramp for changes that could plausibly shift behavior, and use judgment (backed by the eval gate, always) for the rest. The discipline that must never be skipped is the eval gate itself; the canary ramp's *speed* is a risk-calibrated choice.
- **Don't treat the registry as a substitute for the eval gate.** A registry with beautiful branching and rollback and zero evaluators attached is diff tracking with a nice UI, not a safety system — the module's whole point is that versioning and evaluation are two different investments and you need both.

---

## Interview questions

### Q1 — Why is a prompt version more than the prompt string?
**Testing:** whether the manifest concept is understood or just the word "versioning."
**Answer:** Five things independently determine behavior: the template, the exact model id, sampling params, the tool schema hash, and any retrieval/example snapshot. A tool description broadened in an unrelated PR, or a silent provider-side model update, changes behavior with zero lines of prompt diff — so "the prompt version is unchanged" is a different claim from "behavior is unchanged," and only pinning all five together makes a deploy reproducible.
**Follow-up trap:** *"Isn't that overkill for most teams?"* — it's exactly the corrective for the specific failure that actually happens: a regression that traces to nothing in the prompt-diff history because the real cause was a tool schema change nobody thought to version alongside the prompt. Anthropic's own April 2026 postmortem was three simultaneous harness-level changes degrading quality together, undiagnosable quickly precisely because they weren't versioned as one unit.

### Q2 — Why is prompt versioning without evals "just diff tracking"?
**Answer:** A registry answers "what changed and when." It doesn't answer "did the change help," which is the actual question behind iterating on a prompt. The specific gap: a version can pass eval against a frozen offline test set and still degrade on live production traffic, because production distribution drifts away from whatever set the offline eval was built against, and no offline-only eval catches that.
**Follow-up trap:** *"So run the eval more often on the same test set?"* — doesn't fix it. The fix is attaching evaluators to the version id and running them continuously against *sampled live traffic*, scoring individual spans rather than an aggregate dashboard number, so you can pull the actual failing traces rather than staring at "0.82 average" and learning nothing.

### Q3 — Explain the peeking problem and why it matters specifically for prompt A/B tests.
**Answer:** Checking a live experiment's raw p-value repeatedly and stopping at the first significant-looking read inflates the false-positive rate well beyond the nominal significance level — roughly 20 casual looks can push a 5% false-positive rate toward 40% or higher, because a fixed-horizon test's validity assumes exactly one look at the end. It matters especially for prompts because the realistic operating mode is a stakeholder checking a dashboard daily, which is precisely the repeated-peeking scenario that destroys a naive test's validity.
**Follow-up trap:** *"How do you let people monitor daily without breaking the test?"* — sequential or always-valid testing (mSPRT-style), which adjusts the significance threshold dynamically so continuous monitoring doesn't inflate the false-positive rate the way naive peeking does. The discipline that still matters: pick the method (fixed-horizon or sequential) before the experiment starts and don't switch mid-flight.

### Q4 — Design auto-revert for a prompt canary. What are the four required pieces?
**Answer:** One named metric chosen in advance (task completion against ground truth, guardrail trip rate, or a validated LLM-judge score — never the agent's own self-report), a threshold calibrated against that metric's own baseline variance rather than a round number, a time window sized to the signal's own timescale (minutes for error rate/latency, hours for distribution-shift signals), and a rollback mechanism that's a routing change back to the last-known-good pinned manifest, not a redeploy.
**Follow-up trap:** *"What if you set the threshold too tight?"* — it fires on ordinary noise, and a system that reverts unpredictably erodes trust in the mechanism itself faster than having no auto-revert at all; calibrate the threshold against measured baseline variance before turning it on, the same discipline as any anomaly-detection system.

### Q5 — Your canary reached 100% traffic within an hour with no errors, then a quality regression surfaced two days later. What went wrong in the rollout design?
**Answer:** Distribution-shift and semantic-drift signals need enough samples to reach statistical confidence, and at low traffic percentages that can genuinely take 12-24 hours — advancing the ramp on fast signals (error rate, latency) alone, before the slow statistical signal has had time to accumulate enough samples, ships a regression that the slow signal would have caught if the team had waited.
**Follow-up trap:** *"Doesn't that make rollouts too slow for a fast-moving team?"* — the ramp speed is a risk-calibrated choice, not a fixed rule; a genuinely low-risk change can move fast, but a change with real potential for a behavior shift needs the slow signal's window respected. The mistake isn't ramping fast in general, it's ramping fast *without checking which signal category you're actually relying on*.

### Q6 — What's the difference between a canary rollback and a code rollback, mechanically?
**Answer:** A canary rollback is a routing change: the load balancer or feature-flag layer flips traffic from the candidate manifest back to the stable one, which was never undeployed. Realistic rollback latency once a threshold fires is measured in tens of seconds. A code rollback that requires reverting a commit and redeploying is orders of magnitude slower and reintroduces the exact blast-radius problem the canary was designed to avoid.
**Follow-up trap:** *"What happens to the regressed version after rollback?"* — it stays deployed, receiving zero traffic, which converts it from a live incident into a debugging artifact you can inspect calmly rather than under pressure. This is the same "diagnose without the pressure of live traffic" principle that motivates keeping a bad deploy addressable rather than deleted.

### Q7 — Registry vs repo: where's the drift risk, and how do you close it?
**Answer:** A prompt registry (PromptLayer, Braintrust, LangSmith Prompt Hub) and the application repo are two systems of record for the same artifact. Someone edits a prompt live in the registry for a fast fix; the repo's stale copy is what actually deploys on the next release, silently reverting the fix. Close it by choosing exactly one source of truth — either the registry is authoritative and builds pull from it, or the repo is authoritative and the registry is a read-only observability surface with no live-edit path in production.
**Follow-up trap:** *"Which one should be authoritative?"* — depends on who edits prompts. If non-engineers (product, legal, ops) need to ship prompt changes without a code deploy, the registry should be authoritative and the deploy pipeline should read from it. If prompt changes always go through code review, the repo should be authoritative and the registry becomes purely an eval/observability layer.

### Q8 — Why is a prompt change treated the same as a model change?
**Answer:** From the system's observable behavior, the two are indistinguishable — a wording tweak can shift tool selection, output format, or task success rate exactly as much as swapping the underlying model can, and it deserves the identical discipline: eval gate before rollout, gradual canary exposure, a decision rule immune to peeking, and a fast, reversible rollback. Treating a prompt edit as "just text" while treating a model swap as "a real deployment" is an arbitrary distinction that the failure modes don't respect.
**Follow-up trap:** *"Does that mean every typo fix needs a full canary ramp?"* — no, and conflating "same discipline in kind" with "same ramp speed" is the overcorrection. The eval gate is non-negotiable for anything that could plausibly change behavior; the canary ramp's speed is a risk-calibrated judgment call, and a genuinely cosmetic fix can move fast through it.

### Q9 — What should be tagged on every production trace for prompt-related audit purposes?
**Answer:** The full manifest: prompt version, exact model id, sampling params, tool schema hash, and RAG index snapshot, plus which eval gate the version passed and at what canary traffic percentage the response was served. Without this, "why did this specific response happen" has no answer beyond "some version of the prompt, at some point."
**Follow-up trap:** *"Isn't logging the whole manifest on every trace expensive?"* — it's a handful of short fields (a version string, a model id, a param dict, two hashes), trivial relative to the cost of the LLM call itself; the actual expense concern in this space is logging full request/response payloads at scale, which is a separate and much larger cost, not the manifest metadata.

### Q10 — A stakeholder wants to declare the new prompt version a winner after one day of a 5% canary because "the numbers look great." What do you say?
**Testing:** whether you'll hold the statistical line under social pressure, the senior signal in this module.
**Answer:** At 5% traffic, one day is very likely inside the window where distribution-shift signals haven't reached statistical confidence yet — that can take 12-24 hours just to start being trustworthy, and "looks great after one look" is exactly the peeking scenario that inflates false positives. Either commit to the pre-registered sample size and wait, or if daily checking is unavoidable, make sure the experiment is running under a sequential/always-valid method designed for that, not a fixed-horizon test being checked early.
**Follow-up trap:** *"What if the business genuinely can't wait?"* — then say so honestly: shipping now is a business risk decision made with insufficient statistical confidence, not a data-backed win, and that distinction should be explicit and documented, not laundered as "the eval showed it worked."

---

## Red flags that fail you

- Treating "the prompt file diff is clean" as proof that behavior is unchanged.
- A registry with branching and rollback but zero evaluators attached to version ids.
- Declaring an A/B winner from repeated dashboard checks with no pre-registered method.
- An auto-revert threshold with no reference to the metric's own baseline variance.
- Implementing rollback as "revert the commit and redeploy" instead of a routing flip.
- No answer for what happens when the registry and the repo disagree on the current prompt.
- Claiming a canary is safe at 100% traffic after minutes, with no distinction between fast and slow signal timescales.
- Calling a prompt edit "just text" while treating a model swap as a real deployment.

## Cheat card

```
MANIFEST = the unit of versioning, not the prompt string alone
  template · model_id (EXACT, not an alias) · params (temp/top_p/max_tokens/stop)
  · tool_schema_hash · rag_index_snapshot
  ANY ONE changing independently = new version, even with a clean prompt diff

VERSIONING WITHOUT EVALS = diff tracking, not iteration
  offline eval on a frozen set can PASS while prod degrades (distribution drift)
  fix: attach evaluators to version_id, run on SAMPLED LIVE traffic,
       score PER-SPAN not per-dashboard-aggregate

CANARY RAMP: 1% -> 5% -> 20% -> 50% -> 100%, manifest pinned at every stage
  FAST signals (minutes): error rate, p99 latency, guardrail trip rate
  SLOW signals (12-24h at low traffic): output-length/sentiment distribution,
    refusal rate, session-abandon/re-query rate, semantic drift (embedding
    cosine sim, LLM-judge vs baseline)
  advancing on fast signals alone before slow signals confirm = the #1 mistake

DECIDING A WINNER WITHOUT PEEKING
  naive repeated peeking: ~20 looks can push 5% false-positive rate -> 40%+
  fixed-horizon: pre-register N, look ONCE at the end
  sequential/always-valid (mSPRT, GrowthBook/Statsig): safe for continuous checks
  RULE: pick the method BEFORE starting. never switch mid-flight.

AUTO-REVERT = 4 required pieces
  METRIC (one, named, e.g. task completion vs ground truth, NEVER self-report)
  THRESHOLD (calibrated to the metric's OWN baseline noise, not a round number)
  WINDOW (fast signal: minutes · slow signal: hours -- different windows!)
  MECHANISM: ROUTING CHANGE back to last-known-good manifest, NOT a redeploy
    realistic rollback latency: tens of seconds
    reverted version stays deployed, 0% traffic -> debugging artifact

REGISTRY vs REPO: pick ONE source of truth, other is read-only mirror
  drift failure: live registry edit silently reverted by next repo-driven deploy

AUDIT: every trace/span tagged with full manifest + eval gate passed +
  canary % served at. "prompt unchanged" != "behavior unchanged" is the
  whole reason this exists.

PROMPT CHANGE == MODEL CHANGE: same eval-gate-before-rollout discipline.
  Ramp SPEED is risk-calibrated; the EVAL GATE itself is never optional.

REFERENCE THRESHOLDS (illustrative, calibrate to your own baseline)
  error rate +1pp · p99 latency +20% · auto-eval score -5% ·
  guardrail trip rate > 1.5x baseline / 15min window
```

## Sources

- [Prompt Canaries: The Deployment Primitive Your AI Team Is Missing](https://tianpan.co/blog/2026-04-17-prompt-canaries-deployment-llm-production) — deployment manifest fields, fast/slow signal split, 12-24h confidence window at low traffic, rollback-as-routing-change; accessed 2026-08-01
- [Prompt Versioning Without Evals Is Just Diff Tracking](https://www.respan.ai/blog/prompt-versioning-iteration-loop) — the diff-tracking-vs-iteration distinction, span-level scoring, production-sample comparison practice; accessed 2026-08-01
- [Sequential testing: How to peek at A/B test results without ruining validity — Statsig](https://www.statsig.com/perspectives/sequential-testing-ab-peek) — peeking-inflated false-positive rate, mSPRT/always-valid inference; accessed 2026-08-01
- [Sequential Testing — GrowthBook Docs](https://docs.growthbook.io/statistics/sequential) — sequential testing as a shipped platform feature; accessed 2026-08-01
- [Best Prompt Versioning Tools for Production Teams (2026) — Braintrust](https://www.braintrust.dev/articles/best-prompt-versioning-tools-2025) — registry landscape, quality-gate-blocks-deployment pattern; accessed 2026-08-01
- [Best Prompt Management Tools in 2026: The Honest Field Guide — PromptLayer](https://www.promptlayer.com/blog/best-prompt-management-tools-2026-field-guide/) — registry-as-feature vs registry-as-product split, OpenAI's acquisition of Promptfoo (March 2026, ~$86M); accessed 2026-08-01
- `curriculum/07-agentic-ai/25-harness-engineering.md` (`T07-harness-engineering`) — the April 2026 Claude Code postmortem (three simultaneous unversioned harness changes) this module's Q1 cites directly
- `curriculum/07-agentic-ai/25-agent-testing.md` (`T07-agent-testing`) — CI-tier eval gating, golden-set staleness as the same coverage-gap failure applied to prompts
- `curriculum/08-eval-observability/04-agent-eval.md` (`T08-agent-eval`) — task-completion-against-state vs self-report, LLM-judge calibration this module's auto-revert metric relies on

## Changelog
- 2026-08-01 — created
