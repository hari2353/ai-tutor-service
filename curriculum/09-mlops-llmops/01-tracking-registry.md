# MLflow/W&B, Model + Prompt Registries, DVC/LakeFS

> **Track:** T09 MLOps / LLMOps · **Time:** 2.5h · **Prereqs:** none
> **Module id:** `T09-tracking-registry` · **Tags:** mlops,experiment-tracking,registry,critical

## The 30-second version

Experiment tracking, model registries, and data versioning solve three different reproducibility gaps, and conflating them is the first thing that gives away a candidate hasn't run these in production. Experiment tracking (MLflow, W&B) answers "what hyperparameters/code/metrics produced this specific run" — MLflow is free, Apache 2.0, self-hosted on a Postgres-backed tracking server plus S3-style artifact store for the cost of infrastructure (roughly $150-500/month for a small deployment) and owns the full open-source lifecycle now (tracking, registry, prompt registry, deployment), while W&B is a polished managed SaaS at ~$50/user/month for Teams (self-hosted only at enterprise tier, $1,500-5,000+/month minimum) that wins on visualization, sweep orchestration, and team collaboration UX out of the box. A model registry answers a different question — "which specific artifact is approved for which environment" — and MLflow deprecated its four fixed stages (None/Staging/Production/Archived) as of 2.9 in favor of mutable, multi-assignable aliases (`champion`, `candidate`) precisely because a single-stage-per-version model couldn't express canary/shadow states or multiple simultaneous candidates. Prompt registries are the LLM-era analog of a model registry: a prompt is now a versioned, reviewable, rollback-able artifact with its own lineage to the evaluation runs that validated it, because a one-line prompt edit can silently change output behavior as much as a full model swap — MLflow's Prompt Registry (built on the same versioning primitives as the model registry) is the current concrete example. Data versioning solves the third gap — "what exact data produced this artifact" — and DVC (Git-adjacent, requires a local checkout, ML-project-scoped) versus LakeFS (object-storage-native, zero-copy branching directly on S3-scale data, works for any data lake, not just ML) is a real architectural fork, made more interesting by lakeFS acquiring the DVC open-source project from Iterative.ai in November 2025, with DVC continuing as the lightweight small-dataset tool and lakeFS as the enterprise-scale infrastructure layer under one company.

## Why this gets asked

The interviewer has almost certainly inherited a project where "reproduce last quarter's model" turned into a multi-day archaeology exercise: the training script was in a stale branch, the hyperparameters lived in someone's terminal history, the training data had been silently overwritten in the same S3 prefix, and the "production" model tag in a spreadsheet didn't match what was actually deployed. They want to know whether you treat tracking/registry/versioning as one blob called "MLOps tooling" or whether you can name which specific gap each tool closes, because teams that conflate them end up with partial solutions — great experiment tracking and zero data versioning, so the experiment is reproducible except the data underneath it changed. At the LLM-specific layer, they've likely watched a "harmless" prompt tweak ship straight to production with no review, no eval run, and no rollback path, and want to hear you treat that as a governance failure, not a one-off mistake.

---

## Lineage: past → present → future

**What came before.** Before dedicated experiment tracking, ML teams tracked runs in spreadsheets, directory-naming conventions (`model_v3_final_FINAL.pkl`), or nothing at all — reproducibility depended entirely on someone's memory and discipline, and it reliably failed once more than one person touched a project or more than a few weeks passed. Model deployment meant manually copying an artifact to a server and hoping someone documented which one was live. Data versioning didn't exist as a category; teams either kept full dataset snapshots (expensive, unwieldy at scale) or accepted that "the data" was whatever happened to be in the bucket that day — a specific, recurring failure being a training pipeline silently re-reading a source table that had been updated since the model was trained, producing a model nobody could explain or reproduce. MLflow (Databricks, open-sourced 2018) and W&B (founded 2018) both emerged directly to close the "which run produced this number" gap; DVC (Iterative.ai, 2017) emerged to close the parallel data-versioning gap by extending Git's mental model to large files it can't handle natively.

**Where it stands now.** MLflow has expanded well past experiment tracking into a full lifecycle platform — tracking, model registry, prompt registry, evaluation, deployment/serving, and an AI gateway layer — while remaining free and self-hostable, which is why it's the default choice for teams that want to own their infrastructure or avoid per-seat SaaS costs at scale. W&B remains the more polished, faster-to-adopt managed experience, particularly strong for hyperparameter sweep orchestration and rich run comparison visualizations, and is frequently the right call for a smaller team or a research-heavy org that values engineer time over a few hundred dollars a month. The **live disagreement** is really about where the line between "cheap enough to just pay for" and "expensive/proprietary enough to justify self-hosting" sits — a 10-person team on W&B Teams is roughly $500/month, trivial against engineer salaries, but jumps to $200K/year+ at enterprise scale, at which point MLflow's zero licensing cost (offset by the ops burden of running your own tracking server and Postgres) becomes a serious line item in the build-vs-buy conversation. Model registries have converged on **alias-based, not stage-based** promotion — MLflow deprecated its historical four-stage model (None → Staging → Production → Archived) as of MLflow 2.9 in favor of mutable, multi-assignable aliases like `champion`/`candidate`, specifically because a version could only ever hold one stage, which couldn't express "this version is a canary AND still tagged staging" or two simultaneous production candidates during an A/B test. **Prompt registries are the newest layer**, and MLflow's Prompt Registry (current in the MLflow 3.x line) is the most visible concrete implementation: prompts get Git-like versioning, commit messages, environment aliases (`production`, `staging`) for safe promotion, and linkage to the evaluation runs that validated each version — explicitly modeling prompts as first-class artifacts with the same rigor as model weights, not as inline strings in application code. Data versioning had its own consolidation event: **lakeFS acquired the DVC open-source project from Iterative.ai on November 18, 2025**, with DVC continuing as the lightweight, Git-adjacent tool for individual data-scientist workflows and smaller datasets, and lakeFS continuing as the enterprise-scale, object-storage-native infrastructure layer — both now under one company's roadmap rather than two competing philosophies [DVC Joins lakeFS: Your Questions Answered — DVC](https://dvc.org/blog/dvc-joins-lakefs-your-questions-answered/) — accessed 2026-08-03.

**Where it's heading.** High confidence: prompt-as-artifact tooling keeps maturing and converging with model registry patterns (environment aliases, evaluation-linked promotion, rollback) because the underlying problem — a small text change silently altering system behavior with no review gate — is structurally identical to a model weight change, and the tooling ecosystem (MLflow, Langfuse, PromptLayer, Humanloop) is actively building toward that convergence rather than treating prompts as a separate, lesser artifact class. Medium confidence: the DVC/lakeFS consolidation signals further blurring between "ML data versioning" and "general data lake version control" — expect lakeFS's zero-copy branching model to keep absorbing use cases that used to require separate tooling (data quality gates, provenance tracking) as it becomes the shared infrastructure layer for both camps. Speculative but worth flagging: unified "AI asset registries" that version model weights, prompts, evaluation datasets, and fine-tuning data together as one lineage graph rather than as separate registries queried independently — several vendors are moving this direction but no single tool has clearly won that consolidation yet.

---

## Mental model

```
THREE DIFFERENT QUESTIONS, THREE DIFFERENT TOOLS

  "What hyperparameters/code/metrics produced RUN #4231?"
        -> EXPERIMENT TRACKING (MLflow Tracking, W&B Runs)
        -> answers: reproducibility of a single training run

  "Which specific model ARTIFACT is approved for staging/prod
   right now, and what's its lineage back to the run that made it?"
        -> MODEL REGISTRY (MLflow Model Registry)
        -> answers: governance and promotion of trained artifacts

  "Which PROMPT VERSION is live in production, who approved it,
   and what eval scores justified promoting it?"
        -> PROMPT REGISTRY (MLflow Prompt Registry, Langfuse, PromptLayer)
        -> answers: governance of the LLM-era equivalent artifact

  "What exact DATA produced this training run, and can I get
   back to that exact snapshot months later?"
        -> DATA VERSIONING (DVC, LakeFS)
        -> answers: reproducibility of the INPUT, not the run itself

ARCHITECTURAL FORK: DVC vs LakeFS
  DVC:     Git repo ---points to---> .dvc pointer files ---resolve to---> S3/GCS objects
           requires: `dvc checkout` materializes real files locally, git-adjacent workflow
           scope:    ML-project-shaped (train/test splits, model artifacts)

  LakeFS:  S3 bucket bytes UNCHANGED, LakeFS is a metadata/versioning layer IN FRONT
           branches/commits/merges happen at the OBJECT STORE level, zero-copy
           (a "branch" is cheap pointer manipulation, not a data copy)
           scope:    any data lake workload, ML is one consumer among many

  The consolidation: lakeFS acquired the DVC open-source project (Nov 2025).
  DVC = lightweight tool for individual/small-dataset workflows.
  LakeFS = enterprise-scale infrastructure layer. Same company, different tiers now.

MODEL REGISTRY: STAGES (deprecated, MLflow 2.9+) -> ALIASES (current)
  OLD: version 7 --stage--> "Production"   (one stage per version, exclusive)
  NEW: version 7 --alias--> "champion"     (many aliases per version, non-exclusive)
       version 8 --alias--> "candidate"    (both can be tagged simultaneously,
                                             enabling real A/B / canary states)
```

---

## How it actually works

### Experiment tracking: what's actually being recorded, and the cost delta that matters

Both MLflow and W&B record the same conceptual triple per run — parameters (hyperparameters, config), metrics (loss curves, eval scores, logged at each step), and artifacts (model checkpoints, plots, datasets) — tagged with the exact git commit, environment, and (ideally) data version that produced them. The mechanical difference that actually matters in a cost/ops conversation:

- **MLflow**: a tracking server (a Flask/FastAPI-style process) backed by a relational database (Postgres in any real deployment; SQLite only for local single-user use) for run metadata, plus a separate artifact store (S3, GCS, Azure Blob, or local disk) for the large binary payloads. You run and patch this yourself. Apache 2.0 licensed, genuinely free — the cost is entirely infrastructure and the engineer-hours to operate it, commonly estimated at $150-500/month in raw infra for a small deployment, with personnel time for setup/maintenance/troubleshooting often exceeding that infra cost [MLflow vs Weights & Biases vs Neptune: 2026 Comparison — reintech.io](https://reintech.io/blog/mlflow-vs-weights-and-biases-vs-neptune-experiment-tracking-comparison) — accessed 2026-08-03.
- **W&B**: fully managed SaaS. Teams plan runs roughly $50/user/month (a 10-person team ≈ $500/month), free tier caps at 5 seats and 5GB/month storage, and enterprise self-hosting (if you need data to stay on-prem) starts around $1,500-5,000/month minimum, with full enterprise contracts commonly quoted around $200K/year for larger orgs [Weights & Biases vs Mlflow (2026): Honest Comparison — Noizz](https://noizz.io/compare/weights-and-biases-vs-mlflow) — accessed 2026-08-03.

The decision in practice: below roughly a dozen engineers and without hard data-residency requirements, W&B's managed convenience (sweep orchestration, polished run-comparison UI, near-zero setup) usually wins on total cost including engineer time. Past that, or with strict self-hosting requirements, MLflow's zero licensing cost plus full control becomes the more defensible call, provided the team is willing to own a Postgres-backed service as production infrastructure — the same "who's on call for this" question you'd ask about any self-hosted dependency.

### Model registry: why stage-based promotion broke, mechanically

MLflow's original model registry gave every registered model version exactly one **stage** — `None`, `Staging`, `Production`, or `Archived` — a hard, exclusive, single-valued field. This looked adequate until real deployment patterns needed to express states the four-stage model structurally couldn't: a canary version serving 5% of traffic while the previous version still serves the rest (both are, in a real sense, "in production" simultaneously); two candidate versions running a live A/B test where neither has "won" yet; a rollback that needs to demote the current production version without first promoting a replacement. Because a version could only ever be in one stage, none of these could be represented without either abusing tags as an unofficial side channel or accepting the model didn't fit reality.

MLflow deprecated stages as of version 2.9, replacing them with **aliases** — named, mutable pointers (`champion`, `candidate`, or any custom name) that can be assigned to multiple model versions simultaneously and reassigned atomically [Model stages deprecation — MLflow docs](https://mlflow.org/docs/3.0.0rc3/model-registry/) — accessed 2026-08-03. The mechanical improvement: `mlflow.set_registered_model_alias("fraud-model", "champion", version=7)` and `mlflow.set_registered_model_alias("fraud-model", "candidate", version=8)` can coexist, your serving code resolves `models:/fraud-model@champion` at load time, and promoting version 8 to champion is a single alias reassignment — no version needs to be demoted first, and the same version can hold multiple aliases if that's meaningful (e.g., `champion` and `stable-for-region-eu` simultaneously). The old stage-transition API still works for backward compatibility, but is implemented as aliases underneath now, and some integrations (ZenML) explicitly document the mapping: Staging → `staging`, Production → `champion`, Archived → `archived`.

```python
# untested sketch — alias-based promotion, current MLflow pattern
import mlflow
from mlflow import MlflowClient

client = MlflowClient()

# register a new version from a completed run's artifact
result = mlflow.register_model(
    model_uri=f"runs:/{run_id}/model",
    name="fraud-detector",
)

# tag it as a candidate — does NOT touch whatever currently holds "champion"
client.set_registered_model_alias("fraud-detector", "candidate", result.version)

# after eval gate passes: promote by reassigning the alias, atomic, no
# separate "demote current champion first" step required
client.set_registered_model_alias("fraud-detector", "champion", result.version)

# serving code resolves the alias, never a hardcoded version number
model = mlflow.pyfunc.load_model("models:/fraud-detector@champion")
```

**Lineage** in a real registry isn't just "which run produced this version" — it's the full chain: training data version (from DVC/LakeFS) → code commit → run ID and its logged params/metrics → registered model version → alias history (who promoted it, when, and ideally linked to which eval run justified the promotion). A registry that stores the model artifact but not this chain is only solving half the reproducibility problem; when a model misbehaves in production, the actual debugging question is "what changed since the last version that didn't misbehave," and that question needs the full chain, not just the artifact.

### Prompt registries: the LLM-era equivalent, and why it's not optional

A prompt template is functionally a model parameter now — a one-line wording change (adding an example, changing an instruction's phrasing, reordering a system prompt's sections) can shift output quality, safety behavior, or cost (via token count) as significantly as a full model swap, and unlike a model swap, a prompt edit is trivially easy to make directly in application code with zero review gate, which is exactly how it usually goes wrong. MLflow's Prompt Registry treats a prompt the same way the model registry treats a model artifact: Git-like versioning with commit messages, environment aliases (`production`, `staging`) for controlled promotion, a UI that lets non-engineers (PMs, prompt engineers without commit access) edit and propose changes without a code deploy, and — the part that actually matters for production safety — linkage to the evaluation runs that validated each version before promotion [Prompt Registry — MLflow AI Platform](https://mlflow.org/docs/latest/genai/prompt-registry/) — accessed 2026-08-03.

```python
# untested sketch — prompt as a versioned, evaluated artifact
import mlflow

# register a new prompt version with a commit message, same discipline as code
mlflow.genai.register_prompt(
    name="support-ticket-classifier",
    template="Classify this support ticket into one of {categories}...\n\nTicket: {ticket_text}",
    commit_message="add explicit 'ambiguous' category after eval showed 12% misclassification on edge cases",
)

# resolve by alias at inference time, exactly like a model version
prompt = mlflow.genai.load_prompt("prompts:/support-ticket-classifier@production")
```

The governance failure mode this closes: a prompt change that ships straight to production with no eval run and no rollback path is structurally identical to deploying an unvalidated model version, and teams that would never skip a canary for a model change routinely skip it for "just a prompt tweak" — because the tooling historically made prompts invisible as artifacts (inline strings, no version history, no diff). Treating prompts with the same registry discipline (version, alias, eval-gated promotion, rollback) is the single highest-leverage LLMOps practice most teams under-invest in relative to how often prompt regressions actually cause production incidents.

### Data versioning: DVC's Git-adjacent model vs LakeFS's storage-native model

**DVC** extends Git's mental model to data it can't handle natively: large files are replaced in the Git repo by small `.dvc` pointer files (containing a content hash and remote location), the actual bytes live in a separate remote (S3, GCS, Azure, or a plain filesystem), and `dvc checkout` materializes the real files locally by resolving the pointer. This means DVC's workflow is genuinely Git-adjacent — you commit `.dvc` files alongside code, branch and merge the pointers with normal Git semantics, and reproducibility comes from Git's own history plus DVC's content-addressed remote storage. The real cost: every checkout needs to *copy* data locally (no zero-copy branching), which is fine for GB-scale ML datasets and becomes a real bottleneck at data-lake scale (TBs to PBs).

**LakeFS** doesn't touch the underlying bytes at all — it's a versioning layer sitting in front of an existing S3-compatible bucket, exposing Git-like branch/commit/merge semantics implemented as metadata operations over the same immutable object storage. Because a "branch" is a cheap pointer structure rather than a data copy, LakeFS gives **zero-copy branching** — creating an isolated environment for an experimental data transformation is instant and free of storage duplication, and merging or discarding that branch is equally cheap [Scalable Data Version Control — lakeFS](https://lakefs.io/blog/scalable-data-version-control-getting-the-best-of-both-worlds-with-lakefs/) — accessed 2026-08-03. This makes LakeFS the natural fit for data-lake-scale workloads where DVC's copy-on-checkout model would be prohibitively slow or expensive, at the cost of running (or paying for) LakeFS as infrastructure sitting between every consumer and the object store, versus DVC's much lighter Git-plus-remote footprint.

The practical decision rule: DVC for ML-project-scoped versioning where datasets are GB-scale and the team is already Git-native (train/test splits, model checkpoints, small-to-medium feature datasets); LakeFS for data-lake-scale versioning where the data is shared across many consumers beyond just ML (a company-wide data lake, TB-to-PB scale, multiple teams reading the same tables), where zero-copy branching and object-store-native semantics actually pay for the extra infrastructure layer. lakeFS's 2025 acquisition of the DVC open-source project makes this less of a competitive choice than it used to be — DVC continues as the lightweight small-dataset tool, LakeFS as the enterprise infrastructure layer, both under the same roadmap now, so the practical question shifts from "which vendor" to "which scale tier do I actually need."

---

## Build it from scratch

A minimal end-to-end lineage chain — data version, training run, model registration, alias promotion — the shape of what "full reproducibility" actually requires wired together:

```python
# untested sketch — minimal lineage chain across data version -> run -> registry
import subprocess
import mlflow
from mlflow import MlflowClient

# 1. Data version: resolve the exact DVC-tracked data revision used for training
data_rev = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
# in a real pipeline: `dvc checkout` first to materialize the exact tracked data

mlflow.set_experiment("fraud-detector-training")
with mlflow.start_run() as run:
    mlflow.set_tag("data_git_rev", data_rev)   # <- the link back to the exact data snapshot
    mlflow.log_params({"learning_rate": 0.01, "n_estimators": 200})

    model = train_model(...)  # your actual training code
    metrics = evaluate_model(model, eval_set)
    mlflow.log_metrics(metrics)
    mlflow.sklearn.log_model(model, artifact_path="model")

    run_id = run.info.run_id

# 2. Register the artifact from this specific run as a new model version
result = mlflow.register_model(model_uri=f"runs:/{run_id}/model", name="fraud-detector")

# 3. Gate promotion on an explicit eval threshold, not a manual judgment call
client = MlflowClient()
if metrics["eval_auc"] >= 0.92:
    client.set_registered_model_alias("fraud-detector", "candidate", result.version)
else:
    print(f"version {result.version} failed eval gate (AUC {metrics['eval_auc']:.3f} < 0.92), not promoted")
```

Every link in this chain (data revision tag -> run -> registered version -> alias) is what makes "reproduce last quarter's model" a five-minute lookup instead of a multi-day archaeology exercise — the failure mode this whole module exists to prevent.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| "Reproduce the model from Q2" turns into a multi-day search | No link recorded between the training data snapshot and the run that used it — data was versioned nowhere, or the link wasn't logged as a run tag | Tag every run with the exact data version (DVC commit hash / LakeFS commit ID) used, not just the code commit; treat missing data lineage as a blocking gap, not a nice-to-have |
| Two people are confused about which model version is "actually in production" | Stage-based registry with informal side-channel communication (Slack message: "v7 is prod now") instead of a queryable alias | Migrate to alias-based promotion (`champion`/`candidate`); serving code resolves the alias at load time so the registry itself is the single source of truth |
| A prompt change shipped straight to production causes a quality regression with no rollback path | Prompt was an inline string in application code, no version history, no eval gate before the change went live | Move prompts into a prompt registry (MLflow Prompt Registry or equivalent) with eval-gated promotion and an alias for the live version, so rollback is an alias reassignment, not a code revert and redeploy |
| DVC checkout of a large dataset takes minutes and duplicates storage across every branch | DVC's copy-on-checkout model applied to data-lake-scale (TB+) datasets it wasn't designed for | Move that dataset to LakeFS-managed storage for zero-copy branching, keep DVC for genuinely project-scoped smaller datasets |
| W&B bill grows sharply with no headcount change | Storage overage past the free/base tier from large artifact logging (full model checkpoints logged every epoch instead of only the best) | Log artifacts selectively (best checkpoint, not every epoch), or move large artifacts to a cheaper store (S3) with only a reference logged to W&B |
| Self-hosted MLflow tracking server becomes a production incident (it goes down, experiment logging blocks training jobs) | Treated the tracking server as a side tool rather than production infrastructure — no HA, no monitoring, no on-call | Run the tracking server with the same operational rigor as any other production service (HA Postgres, health checks, alerting) if training pipelines depend on it not blocking |
| A model registry has the artifact but nobody can say why it was promoted | Alias reassignment happened with no linkage to the eval run or approver that justified it | Log the eval run ID and gate threshold as part of the promotion action (commit message equivalent), not just the bare alias change |

---

## Tradeoffs & when NOT to use it

- **Don't default to W&B for a large team with strict data-residency requirements without pricing the enterprise self-hosted tier first.** $1,500-5,000+/month minimum for self-hosted W&B can exceed a self-hosted MLflow deployment's infra cost by a wide margin once you're past a small team; run the actual numbers rather than assuming "managed is always worth it."
- **Don't self-host MLflow for a small team without accounting for the ops burden as a real cost.** A Postgres-backed tracking server plus artifact store is genuine production infrastructure someone has to patch, back up, and be on call for — "MLflow is free" is only true if you're also willing to absorb that operational cost, which for a 3-person team is often not worth it versus paying for W&B's managed tier.
- **Don't use DVC for data-lake-scale (multi-TB, multi-team) datasets.** Its copy-on-checkout model doesn't scale the way LakeFS's zero-copy branching does; forcing DVC onto that scale produces slow checkouts and duplicated storage.
- **Don't use LakeFS for a small, single-team ML project's train/test splits.** It's infrastructure overhead (a versioning layer in front of your object store) that a Git-adjacent DVC workflow handles more simply at that scale.
- **Don't skip prompt versioning because "it's just a string."** A prompt change has the same blast radius as a model weight change in terms of output behavior shift, and skipping review/eval-gating for prompts while enforcing it for model deploys is an inconsistent, easily-exploited gap in a team's governance.
- **Don't keep using stage-based model registry transitions in a new MLflow deployment.** They're deprecated, can't express canary/multi-candidate states, and the alias-based replacement solves the same problem more flexibly with no real downside for new projects.
- **Don't treat the tracking server or registry as optional tooling for "quick experiments."** The failures this module exists to prevent (unreproducible runs, ambiguous production model identity, silent prompt regressions) all originate from someone deciding a specific run/change was too small to bother tracking.

---

## Interview questions

### Q1 — What's the actual difference between experiment tracking and a model registry? Why do you need both?
**Testing:** whether the candidate conflates two tools that solve different problems.
**Answer:** Experiment tracking (MLflow Tracking, W&B) answers "what code/params/data produced this specific run's metrics" — it's about reproducibility of a training run. A model registry answers "which artifact is approved for which environment right now, and what's its promotion history" — it's about governance of trained artifacts moving toward production. A run can exist and never be registered (most experiments never ship); a registered model version always traces back to the run that produced it, but the registry adds a promotion/approval layer tracking doesn't have.
**Follow-up trap:** *"Could you build a registry on top of just tracking data, with no dedicated registry tool?"* — technically yes (tags and a spreadsheet), but you lose atomic alias reassignment, built-in access control on promotion actions, and a queryable single source of truth for "what's live right now" — which is exactly the ambiguity a real registry exists to eliminate.

### Q2 — Why did MLflow deprecate registry stages in favor of aliases? What could stages not express?
**Testing:** understanding the actual mechanical limitation, not just "aliases are newer."
**Answer:** A model version could hold exactly one stage (None/Staging/Production/Archived) — a hard, exclusive field. That structurally couldn't express a canary serving a small percentage of traffic alongside the existing production version (both are "in production" simultaneously), or two candidate versions in a live A/B test, or demoting a production version without first promoting a replacement. Aliases are mutable, multi-assignable, named pointers — multiple aliases can point at the same version, and the same conceptual role (`champion`) can be reassigned atomically without needing a two-step demote-then-promote.
**Follow-up trap:** *"Is the old stage-transition API still usable at all?"* — yes, for backward compatibility, but it's implemented as aliases underneath now (e.g., Production maps to a `champion`-style alias in some integrations) — a new project should use aliases directly rather than the deprecated stage API.

### Q3 — Why treat a prompt as a versioned registry artifact instead of an inline string in application code?
**Testing:** whether the candidate understands prompts as a governance gap, not a style preference.
**Answer:** A prompt wording change can shift output quality, safety behavior, and token cost as significantly as swapping model weights, but an inline string has no version history, no diff, no eval gate, and no rollback path beyond a code revert and redeploy. Registering prompts the way you register models — versioned, alias-promoted, linked to the eval run that validated the change — closes exactly the same governance gap for prompts that already exists for models, and lets rollback be an alias reassignment instead of a full deployment.
**Follow-up trap:** *"A PM wants to tweak a prompt without waiting for an engineer to deploy. How does a prompt registry help with that specifically?"* — a prompt registry with a UI (MLflow's Prompt Registry supports this) lets a non-engineer edit and propose a new prompt version directly, gated by the same eval/promotion workflow, without needing write access to the application codebase or a full deploy cycle — solving the "waiting on an engineer for a one-line change" friction without also removing the review gate.

### Q4 — Compare DVC and LakeFS architecturally. When would you pick one over the other?
**Testing:** whether the candidate knows the actual mechanical difference (copy vs zero-copy) rather than treating them as interchangeable "data versioning tools."
**Answer:** DVC is Git-adjacent: large files become `.dvc` pointer files committed to Git, with the real bytes in a separate remote, and `dvc checkout` materializes actual local copies — fine at GB-scale, ML-project-shaped. LakeFS is storage-native: it sits in front of an existing object store and implements branch/commit/merge as metadata operations with no data copy, giving zero-copy branching that scales to TB/PB data-lake workloads shared across many consumers, not just ML. Pick DVC for a Git-native team with project-scoped, moderate-size datasets; pick LakeFS when the data is lake-scale or shared broadly enough that copy-on-checkout would be too slow or expensive.
**Follow-up trap:** *"lakeFS acquired the DVC project in late 2025 — does that change the recommendation?"* — not the underlying architectural tradeoff, but it changes the practical framing: DVC continues as the lightweight small-dataset tool and LakeFS as the enterprise-scale layer, both under one company's roadmap now, so the choice is really about which scale tier fits the workload rather than betting on two competing, potentially-diverging projects.

### Q5 — Your team's MLflow bill is "free" but a self-hosted tracking server just caused a training pipeline outage. What does that reveal about the cost comparison against W&B?
**Testing:** whether the candidate accounts for operational cost, not just licensing cost.
**Answer:** "MLflow is free" only accounts for licensing — the tracking server, its Postgres backend, and the artifact store are genuine production infrastructure, and if training pipelines depend on the tracking server not blocking, it needs the same HA/monitoring/on-call rigor as any other production dependency. That operational cost (engineer time, on-call burden) is real and should be weighed against W&B's managed-service price, not treated as free just because no invoice arrives for it.
**Follow-up trap:** *"At what team size does that math flip in favor of self-hosting?"* — there's no universal number, but the honest framing is: below the point where a team already has spare platform-engineering capacity to operate shared infrastructure well, self-hosting's "free" licensing is a false economy; once a team is large enough that the per-seat SaaS cost materially exceeds the marginal ops cost of infrastructure they're already running competently, self-hosting starts winning — the same utilization-adjusted logic as the Bedrock-vs-self-hosted arithmetic in `T09-bedrock-vs-sagemaker`.

### Q6 — What specific lineage information does a registered model version need beyond the artifact itself?
**Testing:** whether the candidate treats "registry" as just artifact storage or understands the lineage graph it needs to support.
**Answer:** The data version (DVC commit / LakeFS commit) used for training, the code commit that produced the training script, the run ID and its logged params/metrics, the eval results that justified promotion, and the promotion history itself (who moved which alias, when, referencing which eval run). Without this chain, debugging "why did this model start misbehaving" degrades into guesswork about what actually changed between the last-known-good version and the current one.
**Follow-up trap:** *"Which single piece of that chain is most commonly missing in real deployments, in your experience?"* — the data version link, specifically — most teams log code commit and hyperparameters reflexively (it's the "obvious" reproducibility need) but treat the training data as a fixed, unchanging thing not worth tagging per-run, until a silently-updated source table breaks reproducibility months later and nobody can say what data actually trained the deployed model.

### Q7 — Walk through what happens, mechanically, when you resolve `models:/fraud-detector@champion` at serving load time versus hardcoding a version number.
**Testing:** whether the candidate can reason about why alias resolution is the safer default, not just recite that it exists.
**Answer:** Resolving by alias means the serving code queries the registry at load time for whichever version currently holds the `champion` alias — promoting a new version is a single atomic alias reassignment with zero code change and zero redeploy of the serving layer, and rollback is equally just reassigning the alias back to the previous version. Hardcoding a version number means every promotion or rollback requires a code change and redeploy of the serving path itself, coupling model lifecycle to application deployment lifecycle unnecessarily.
**Follow-up trap:** *"What's a legitimate reason to hardcode a version number anyway?"* — reproducing an exact historical inference result for audit/debugging purposes, where you deliberately want to bypass whatever alias currently points where and pin to the literal version that produced a specific past output — a narrow, deliberate exception, not a general serving pattern.

### Q8 — A prompt registry shows `production` pointing at version 14, but the actual deployed service is visibly using different output behavior. What do you check first?
**Testing:** whether the candidate can debug a registry/deployment drift issue methodically.
**Answer:** First, whether the serving code is actually resolving the alias at request/load time versus having cached or hardcoded an earlier prompt version at deploy time and never picking up the reassignment (a stale-cache class of bug identical in shape to any config-not-hot-reloaded issue). Second, whether there's a second code path (a fallback, a different service instance, a different environment) still pointed at a different alias or a pinned older version. Third, whether the "production" alias itself was reassigned correctly, versus a promotion action failing partway or targeting the wrong registered prompt name.
**Follow-up trap:** *"Assume it's confirmed the alias resolves correctly at request time and points at v14. What else could explain different behavior?"* — the underlying model serving that prompt changed (a Bedrock alias moved to a new model version, matching the `T09-model-cicd` model-behind-a-pinned-alias problem), or non-determinism in the model itself (temperature > 0) is being mistaken for a prompt-driven regression — rule out the model layer before assuming the prompt registry is at fault.

### Q9 — Design the full reproducibility chain for "recreate the exact model that was in production on a specific date, six months ago." What has to have been tracked at the time for this to be possible?
**Testing:** synthesis across tracking, registry, and data versioning as one system, the actual staff-level framing of this module.
**Answer:** You need: (1) the model registry's alias history showing which version held `champion` on that date, (2) that version's originating run in the experiment tracker, giving code commit and hyperparameters, (3) the data version tag on that run pointing to the exact DVC/LakeFS snapshot used for training, and (4) if the model consumed a prompt, the prompt registry's alias history for what was live on that date too. Missing any one link breaks the chain — a registered model with no data-version tag on its run, for instance, gives you the weights but not a reproducible path to retrain them from the same data if the artifact itself is somehow lost or you need to explain *why* it behaves as it does.
**Follow-up trap:** *"The model artifact itself still exists in the registry. Do you even need the rest of the chain?"* — depends on what "recreate" means: if you just need to *serve* the same model, the artifact alone suffices; if you need to *explain, audit, or retrain* it (a compliance request, a bug investigation, an unlearning requirement), you need the full lineage chain, and an artifact with no reconstructable lineage is a liability in exactly those higher-stakes situations, not a minor gap.

### Q10 — At staff level: a team wants to skip a prompt registry entirely because "we deploy so often anyway, versioning prompts feels like overhead." How do you respond?
**Testing:** whether the candidate can make the governance argument plainly rather than deferring to the team's instinct.
**Answer:** Frequent deploys are exactly the scenario where prompt regressions are hardest to catch after the fact — without a registry, there's no diff between "the prompt that worked" and "the prompt that shipped an hour ago," and rollback means finding the right prior commit in application code history rather than reassigning an alias. The overhead of a prompt registry is genuinely small (a registration call plus an alias reassignment) relative to the cost of an unreviewed, unevaluated prompt regression reaching production users, which is the actual failure this practice prevents. The honest counter-argument, stated plainly: if the team's prompts truly never change behavior meaningfully (rare, and worth verifying rather than assuming) and deploys are trivially revertible with equivalent speed to an alias reassignment, the marginal safety benefit shrinks — but that's a claim to verify with actual incident history, not to assume.
**Follow-up trap:** *"What evidence would actually change your mind and let the team skip it?"* — a track record showing prompt changes in this specific system have never caused a measurable quality or safety regression across a meaningful sample of past changes — and even then, recommend keeping at minimum a lightweight version history (even just Git-tracked prompt files with commit messages) rather than fully unversioned inline strings, since the cost of that minimal version is close to zero.

### Q11 — What's the concrete cost difference between W&B Teams and W&B's enterprise self-hosted tier, and when does that gap actually matter for a real decision?
**Testing:** whether the candidate has real numbers, not just "W&B has different tiers."
**Answer:** W&B Teams runs roughly $50/user/month (a 10-person team around $500/month), with a free tier capped at 5 seats and 5GB/month storage. Enterprise self-hosting (needed for strict data-residency requirements) jumps to roughly $1,500-5,000+/month minimum, and full enterprise contracts for larger orgs are commonly quoted around $200K/year. The gap matters concretely once data-residency or compliance requirements force self-hosting — at that point W&B's cost profile changes from "cheap managed convenience" to "expensive enough that self-hosted MLflow's zero licensing cost, offset by ops burden, becomes a genuinely competitive alternative."
**Follow-up trap:** *"Are those figures something you'd quote to a VP planning next year's budget?"* — no, flag them explicitly as directional estimates from public comparison sources rather than confirmed current vendor quotes, and recommend getting an actual quote from the vendor before committing to a number in a real budget conversation — pricing pages and tier minimums change, and a stale number stated as current is a real credibility risk in front of leadership.

### Q12 — Explain why "the data pipeline hasn't changed" is not the same claim as "the data hasn't changed," and how data versioning specifically closes that gap.
**Testing:** the actual production failure mode this whole data-versioning half of the module exists to name.
**Answer:** A training pipeline reading from a live source table (a production database table, an updated data lake partition) can produce a completely unchanged *pipeline* (same code, same query) while the *data* underneath it silently changes between runs — a schema migration, a backfill, a correction to historical records, or simply new rows landing in a table the pipeline treats as a fixed snapshot. Without an explicit, immutable data version (a DVC commit hash, a LakeFS commit ID) captured per training run, "we didn't change anything" is a claim about the code, not the data, and a model trained today from "the same query" against a table that's since been updated is not reproducible even though nothing about the pipeline itself changed.
**Follow-up trap:** *"How would you retrofit data versioning onto a pipeline that's been reading live tables with no versioning for years?"* — start by snapshotting the source table (or the relevant partition) into an immutable, versioned location (a LakeFS-managed path, or a dated S3 prefix tracked via DVC) at the moment each training run reads it, tagging the run with that snapshot's identifier going forward — you can't retroactively version historical runs that already happened, but you can stop the bleeding for every run from that point on, and that's usually the pragmatic, honestly-stated answer rather than promising full historical reconstruction that isn't actually possible.

---

## Red flags that fail you

- Treating "MLOps tooling" as one blob without being able to name which specific gap tracking, registry, and data versioning each close.
- Recommending W&B or MLflow reflexively without mentioning the actual cost/ops tradeoff (managed convenience vs licensing-free-but-you-run-it).
- Not knowing MLflow deprecated stage-based model promotion in favor of aliases, or being unable to explain what stages structurally couldn't express.
- Treating a prompt as "just a string" not worth versioning, review-gating, or linking to eval results.
- Confusing DVC and LakeFS as interchangeable "data versioning tools" without knowing the copy-vs-zero-copy architectural difference.
- Quoting specific pricing figures as confirmed current facts rather than caveating them as estimates to verify.
- Missing the data-version link as part of a model's lineage chain, treating code commit and hyperparameters as sufficient for reproducibility.
- Not recognizing that "the pipeline didn't change" and "the data didn't change" are different claims.

---

## Cheat card

```
THREE GAPS, THREE TOOLS
  Experiment tracking (MLflow / W&B)  -> reproduce a RUN
  Model registry (MLflow Registry)    -> govern which ARTIFACT is live where
  Prompt registry (MLflow Prompt Reg) -> govern which PROMPT is live where
  Data versioning (DVC / LakeFS)      -> reproduce the exact INPUT DATA

MLFLOW vs W&B (verify current pricing before quoting)
  MLflow: Apache 2.0, free, self-hosted (Postgres + S3), ~$150-500/mo infra
          for small deployment, + real ops burden (patch/monitor/on-call)
  W&B:    managed SaaS, Teams ~$50/user/mo (10 ppl ~$500/mo), free tier
          5 seats/5GB, self-hosted enterprise ~$1.5-5K+/mo min, ~$200K/yr
          full enterprise contracts

MODEL REGISTRY: stages DEPRECATED (MLflow 2.9+) -> ALIASES current
  stage = exclusive, one per version, can't express canary/multi-candidate
  alias = mutable, multi-assignable (champion/candidate), atomic reassignment
  serving code resolves models:/name@alias, never hardcode version number

PROMPT REGISTRY = model registry discipline applied to prompts
  wording change = same blast radius as weight change on behavior/cost/safety
  version + commit message + eval-gated alias promotion + rollback via
  alias reassignment, NOT a code revert and redeploy

DVC vs LAKEFS (architectural fork, not just brand choice)
  DVC:    Git-adjacent, .dvc pointer files, COPY on checkout, ML-project scale
  LakeFS: storage-native, branch/commit/merge = metadata ops, ZERO-COPY,
          data-lake scale, any consumer not just ML
  Nov 2025: lakeFS acquired DVC OSS project (Iterative.ai) -- DVC = small/
          lightweight tier, LakeFS = enterprise infra tier, same roadmap now

LINEAGE CHAIN a real registry needs: data version -> code commit -> run ID
  (params/metrics) -> registered version -> eval run -> alias/promotion
  history. Missing the DATA VERSION link is the most common gap in practice.

FAILURE MODE: "pipeline didn't change" != "data didn't change" -- a live
  source table can silently mutate under an unchanged pipeline; only an
  explicit immutable data version (DVC/LakeFS commit) closes this gap.
```

## Sources
- [MLflow vs Weights & Biases vs Neptune: 2026 Comparison Guide — reintech.io](https://reintech.io/blog/mlflow-vs-weights-and-biases-vs-neptune-experiment-tracking-comparison) — accessed 2026-08-03
- [Weights & Biases vs Mlflow (2026): Honest Comparison — Noizz](https://noizz.io/compare/weights-and-biases-vs-mlflow) — accessed 2026-08-03
- [MLflow Model Registry — mlflow.org (3.0.0rc3 docs)](https://mlflow.org/docs/3.0.0rc3/model-registry/) — accessed 2026-08-03
- [Prompt Registry — MLflow AI Platform](https://mlflow.org/docs/latest/genai/prompt-registry/) — accessed 2026-08-03
- [Top 3 LLM Prompt Versioning Platforms 2026 — MLflow](https://mlflow.org/articles/top-llm-prompt-versioning-platforms-3/) — accessed 2026-08-03
- [DVC Joins lakeFS: Your Questions Answered — DVC](https://dvc.org/blog/dvc-joins-lakefs-your-questions-answered/) — accessed 2026-08-03
- [Scalable Data Version Control with local checkout capability — lakeFS](https://lakefs.io/blog/scalable-data-version-control-getting-the-best-of-both-worlds-with-lakefs/) — accessed 2026-08-03
- [Best Data Version Control Tools in 2026 — lakeFS](https://lakefs.io/data-version-control/dvc-tools/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
