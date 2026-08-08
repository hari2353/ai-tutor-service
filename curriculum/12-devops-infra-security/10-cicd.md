# GitHub Actions, ArgoCD/GitOps, Progressive Delivery

> **Track:** T12 DevOps, Infra & Security · **Time:** 2h · **Prereqs:** T12-docker, T12-k8s-objects
> **Module id:** `T12-cicd` · **Tags:** cicd
> **Lab:** `labs/k8s/10-cicd-gitops/`

## The 30-second version

Modern Kubernetes CI/CD splits cleanly into two loops that most teams keep deliberately separate: **CI** (GitHub Actions) builds, tests, and pushes an image, then updates a manifest or Helm values file in a separate config repo — it never touches the cluster directly. **CD** is a GitOps controller (ArgoCD or Flux) running *inside* the cluster, continuously reconciling live cluster state against that config repo via a **pull-based** model — the controller polls/watches Git and applies diffs, rather than CI pushing `kubectl apply` with cluster credentials from outside. This split exists specifically to eliminate long-lived cluster credentials sitting in CI (a real, recurring source of breaches — a compromised CI pipeline with cluster-admin kubeconfig is a full cluster compromise) and to make the cluster's actual state always auditable as "whatever's currently in Git," not "whatever the last successful pipeline run happened to push." ArgoCD is the dominant choice for teams wanting a centralized dashboard, multi-cluster management from one control plane, and sync-wave-ordered deployments (running in a majority of production Kubernetes clusters doing GitOps); Flux is the CLI-first, more composable alternative with materially better native Helm lifecycle support. Neither `Deployment`'s `RollingUpdate` nor either GitOps controller does traffic-percentage canary analysis natively — that's Argo Rollouts (replaces `Deployment` with a `Rollout` CRD, tightly integrated with ArgoCD) or Flagger (sits on top of existing `Deployments`, pairs naturally with Flux), both driving gradual traffic shift gated on real Prometheus/Datadog-style metric thresholds with automated rollback, not a human watching a dashboard and pressing "proceed."

## Why this gets asked

Because "we use GitHub Actions to deploy to Kubernetes" is a sentence that hides a huge range of actual maturity — from a workflow that runs `kubectl apply` directly with a long-lived cluster secret (a real security liability) to a properly split CI/CD pipeline with a pull-based GitOps controller and metric-gated progressive delivery. The interviewer has likely either inherited a CI pipeline with an over-privileged cluster credential that terrified them once they understood the blast radius, or been on the other side — watching an automated canary correctly catch a bad deploy and roll it back before a human even noticed, and wants to know you understand *why* that's structurally safer than a person eyeballing a dashboard.

---

## Lineage: past → present → future

**What came before.** Early Kubernetes CI/CD (mid-2010s) was almost universally push-based: a CI pipeline (Jenkins, CircleCI, early GitHub Actions) built an image and then ran `kubectl apply` or `helm upgrade` directly against the cluster using a service account credential stored as a CI secret. This worked, but concentrated real risk in exactly the wrong place — every CI job needed broad cluster-write access to do its job, meaning a compromised pipeline, a leaked CI secret, or a misconfigured job with too-broad permissions was a direct path to full cluster compromise, and there was no cheap way to answer "is the cluster's actual state what Git says it should be" except by manually diffing — nothing continuously reconciled the two, so drift (someone running a manual `kubectl edit` against a live resource) went undetected until it caused a problem.

**Where it stands now.** GitOps (the term coined by Weaveworks in 2017, popularized through ArgoCD's 2018 release and CNCF graduation) inverted the model: a controller running *inside* the cluster pulls from Git and reconciles continuously, so cluster credentials never need to leave the cluster at all, and "what does the cluster actually look like right now" is answered by the controller's own continuously-updated sync status, not a point-in-time pipeline run. ArgoCD (per widely-cited 2026 adoption figures, running in a clear majority of production Kubernetes clusters doing GitOps) won mindshare largely on its dashboard, multi-cluster hub-and-spoke management (a single ArgoCD instance managing many downstream clusters, with `ApplicationSet` templating Applications dynamically across them), and native sync-wave/hook ordering for complex multi-resource rollouts. Flux remains the CLI-first, more Kubernetes-native-feeling alternative — no bundled dashboard, controllers exposed as ordinary CRDs, and materially stronger native Helm chart lifecycle fidelity (Flux-managed Helm releases stay fully visible to and interoperable with standard `helm` tooling in a way ArgoCD's Helm-as-a-rendering-engine approach doesn't quite match) — a live, real tradeoff rather than one tool being simply better. Progressive delivery on top of either — Argo Rollouts (the `Rollout` CRD replacing `Deployment` outright, deeply integrated with ArgoCD's own health checks and UI) or Flagger (sits alongside existing `Deployments` unmodified, pairs naturally with Flux) — has become the default answer to "how do you do canary in Kubernetes," since neither raw `Deployment` nor either GitOps controller alone has any native concept of gradual traffic shifting gated on live metrics.

**Where it's heading.** The CI/CD split (build-and-push-config in CI, pull-and-reconcile in cluster) is now settled consensus for anything beyond a small/early-stage team — the disagreement that remains live is ArgoCD-vs-Flux and Argo-Rollouts-vs-Flagger, both genuinely close calls decided more by ecosystem fit (do you want a dashboard, how Helm-heavy is your chart usage, are you already in the Argo or Flux family for other tooling) than a clear technical winner. Expect continued convergence on OpenTelemetry-based metrics as the common analysis backbone for progressive delivery tooling (reducing today's per-tool metric-provider integration sprawl), and continued growth of `ApplicationSet`-style templated multi-cluster/multi-tenant GitOps patterns as fleet sizes grow — both directional and reasonably confident calls, not speculative.

---

## Mental model

```
   PUSH-BASED (older, higher risk)         PULL-BASED / GITOPS (current standard)

   ┌──────────┐   kubectl apply w/          ┌──────────┐  git push (image tag/
   │    CI     │───cluster credential──────►│  cluster  │   values only)
   │ pipeline  │       (CI holds a           └──────────┘
   └──────────┘        cluster-write             ▲
                        secret — real risk)       │ pulls/watches, reconciles
                                            ┌──────────────┐  continuously
                                            │ ArgoCD/Flux    │  (NO cluster creds
                                            │ (runs INSIDE   │   ever leave the
                                            │  the cluster)  │   cluster)
                                            └──────────────┘
                                                   │
                                                   ▼
   CI never touches the cluster. It builds, tests, pushes an image,
   then updates a MANIFEST/VALUES FILE in a config repo. The GitOps
   controller notices the Git change and reconciles the cluster to match.

   PROGRESSIVE DELIVERY sits ON TOP of this — neither raw Deployment nor
   ArgoCD/Flux alone shifts traffic gradually or watches metrics:

   Rollout/Canary controller (Argo Rollouts or Flagger)
     -> shifts traffic 10% -> 25% -> 50% -> 100%, PAUSING between steps
     -> watches Prometheus/Datadog/etc. metrics at each step
     -> AUTOMATIC rollback if error rate / latency crosses a threshold
```

---

## How it actually works

### The CI half — build, test, push, update config (never touch the cluster)

A GitHub Actions workflow's job in this model ends at updating a config repo, not deploying:

```yaml
# untested sketch — CI stops at pushing an image + bumping a config repo's image tag
name: build-and-release
on: { push: { branches: [main] } }
jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      id-token: write     # for OIDC-based registry auth, no long-lived secret needed
      contents: read
    steps:
      - uses: actions/checkout@v4
      - name: Build and push image
        run: |
          docker build -t myrepo/app:${{ github.sha }} .
          docker push myrepo/app:${{ github.sha }}
      - name: Bump image tag in config repo
        run: |
          git clone https://github.com/myorg/k8s-config.git
          cd k8s-config
          yq -i '.image.tag = "${{ github.sha }}"' apps/myapp/values.yaml
          git commit -am "bump myapp to ${{ github.sha }}"
          git push
        # NOTE: this step needs write access to the CONFIG repo, not the cluster —
        # a materially smaller blast radius than a cluster-admin kubeconfig
```

**GitHub Actions-specific mechanics worth being precise about:** OIDC-based cloud/registry authentication (`permissions: id-token: write`) issues short-lived, workflow-run-scoped credentials instead of a long-lived secret sitting in the repo/org secret store — this closes a real, common leak vector (a static cloud credential exfiltrated from CI secrets and reused long after the workflow run ends). Reusable workflows and composite actions are the standard mechanism for sharing pipeline logic across many repos without copy-pasting YAML, roughly analogous in purpose to Terraform modules — same over-abstraction risk applies if a shared workflow tries to parameterize every possible team's use case at once.

### The CD half — pull-based reconciliation, precisely

ArgoCD's core loop: the `Application` CRD points at a Git repo path (and optionally a target revision), and the `application-controller` component polls that path on an interval (default **3 minutes**, configurable, plus a webhook-triggered immediate refresh on Git push if configured) — it compares the rendered manifests (plain YAML, Helm chart, Kustomize overlay, or a plugin-rendered source) against the live cluster's actual resources, computing a diff exactly like `kubectl diff` would, and reports `Synced`/`OutOfSync` status. **Sync** (applying that diff) can be automatic (`syncPolicy.automated`) or require manual approval via the UI/CLI — a deliberate control point many teams keep manual for production even with automated CI/CD everywhere else, specifically so a human confirms the diff before it lands. **Sync waves** (`argocd.argoproj.io/sync-wave` annotation) order multi-resource rollouts explicitly — a `Namespace` and `CustomResourceDefinition` in wave `-1`, application resources in wave `0`, a post-deploy `Job` in wave `1` — waiting for each wave's resources to reach a healthy state before starting the next, which raw `kubectl apply` (applying everything roughly simultaneously) has no native concept of. The **App of Apps** pattern (a root `Application` whose "manifests" are themselves a directory of other `Application` definitions) is how one ArgoCD instance manages many applications/teams/clusters from a single Git-tracked root, and `ApplicationSet` extends this further with templated generation — one template producing an `Application` per cluster in a list, per Git directory matching a glob, or per PR, without hand-writing each one.

Flux's model is architecturally more granular — no single `Application` abstraction bundling everything; instead separate CRDs (`GitRepository` as the source, `Kustomization` or `HelmRelease` as the reconciler applying it) composed explicitly, with `dependsOn` expressing ordering between them rather than ArgoCD's numeric sync waves. This is the concrete shape of the "dashboard-centric, integrated abstraction" (ArgoCD) versus "composable, CLI-first, granular CRDs" (Flux) tradeoff — neither is objectively more correct, and the choice tends to follow team preference for a bundled UI/RBAC/multi-cluster story versus a more Unix-philosophy, wire-together-yourself model, plus (concretely) how Helm-heavy the team's chart usage is, since Flux's `HelmRelease` keeps full fidelity with standard Helm lifecycle hooks and tooling in a way ArgoCD's Helm-as-a-template-renderer approach doesn't fully preserve.

### Progressive delivery — how a canary actually decides to proceed or roll back

Neither `Deployment` nor ArgoCD/Flux alone shifts traffic gradually — that requires a dedicated controller reading real metrics at each step:

```yaml
# untested sketch — Argo Rollouts canary with metric-gated automated analysis
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata: { name: checkout-api }
spec:
  replicas: 10
  strategy:
    canary:
      steps:
      - setWeight: 10                 # shift 10% of traffic to the new version
      - pause: { duration: 5m }        # hold, let the analysis below run
      - analysis:
          templates:
          - templateName: success-rate  # references an AnalysisTemplate below
      - setWeight: 50
      - pause: { duration: 10m }
      - setWeight: 100
---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata: { name: success-rate }
spec:
  metrics:
  - name: error-rate
    interval: 1m
    successCondition: result < 0.01     # <1% error rate required to proceed
    failureLimit: 3                      # 3 consecutive failed checks -> abort
    provider:
      prometheus:
        address: http://prometheus.monitoring:9090
        query: |
          sum(rate(http_requests_total{app="checkout-api",status=~"5.."}[1m]))
          /
          sum(rate(http_requests_total{app="checkout-api"}[1m]))
```

The mechanism: at each `setWeight` step, real production traffic is split between old and new versions (via a service mesh, an Ingress controller's weighted routing, or a native traffic-splitting integration), and the `AnalysisTemplate`'s Prometheus query is evaluated on the configured `interval` — if `successCondition` fails `failureLimit` times, the `Rollout` controller **automatically aborts and reverts traffic to the stable version**, no human intervention required and, critically, no human required to *notice* the regression before it's already been contained — this is the real, structural advantage over "we deploy a few pods first and eyeball a dashboard," which depends on someone watching in real time and reacting fast enough. Flagger's model is functionally equivalent (metric-gated, automated step progression and rollback) but implemented by wrapping an existing `Deployment` rather than replacing it with a new CRD, and it manages the underlying traffic-split resource (a `VirtualService`, `HTTPRoute`, or similar) on your behalf rather than you authoring the split directly.

---

## Build it from scratch

```yaml
# untested sketch — minimal ArgoCD Application, pull-based, manual sync for production
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: checkout-api
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/myorg/k8s-config.git
    targetRevision: main
    path: apps/checkout-api
  destination:
    server: https://kubernetes.default.svc
    namespace: checkout
  syncPolicy:
    automated:
      prune: true          # remove resources deleted from Git
      selfHeal: true        # revert manual kubectl edits back to match Git
    # omit `automated` entirely for production namespaces requiring manual approval
```

```bash
# App of Apps: a root Application whose source IS a directory of other Applications
argocd app create root \
  --repo https://github.com/myorg/k8s-config.git \
  --path apps-of-apps \
  --dest-server https://kubernetes.default.svc \
  --sync-policy automated
# every Application manifest committed under apps-of-apps/ is picked up automatically —
# adding a new team/service becomes a Git commit, not a new argocd CLI invocation
```

---

## How it's done in production

Production setups near-universally split config repos from application source repos (the "config repo" holding rendered/templated manifests, Helm values, or Kustomize overlays that ArgoCD/Flux actually watch, separate from the application's own source code repo that CI builds from) — this keeps the GitOps controller's Git polling load and diff surface scoped to deploy-relevant changes only, and lets deploy history be reviewed independently of application code history. `selfHeal: true` (ArgoCD) or Flux's equivalent continuous reconciliation is what actually enforces "the cluster always matches Git" as a hard guarantee rather than a best-effort convention — any manual `kubectl edit` against a GitOps-managed resource gets silently reverted on the next reconcile cycle, which is a feature (drift can't accumulate silently) but a real operational surprise the first time someone hand-edits a resource "just to test something quickly" and watches it revert within minutes.

| Symptom | Cause | Fix |
|---|---|---|
| A manual `kubectl edit` against a GitOps-managed resource reverts within minutes | `selfHeal`/continuous reconciliation working as designed — the controller detected drift from Git and corrected it | This is expected behavior, not a bug; make the change in Git instead, or temporarily disable auto-sync for that Application if a genuine emergency hotfix needs to bypass Git momentarily (and follow up by codifying it in Git immediately after) |
| ArgoCD shows `OutOfSync` indefinitely even after a sync | A resource has fields being mutated by something else in-cluster after Argo applies it (an admission webhook injecting defaults, an HPA changing replica count that Git doesn't track) | Configure `ignoreDifferences` for the specific fields legitimately owned by another controller, rather than fighting a permanent, expected diff |
| A canary rollout proceeds to 100% despite a real error-rate spike | `AnalysisTemplate`'s query or threshold is misconfigured (wrong metric name/label, threshold too loose), or the metrics provider address is unreachable and the analysis silently no-ops | Validate the Prometheus query manually against real data before trusting it in a `Rollout`; alert on `AnalysisRun` failures/errors distinctly from rollout progression itself |
| CI pipeline has a long-lived, broadly-scoped cloud/cluster credential that security flags in an audit | Push-based deploy model, or OIDC not configured for registry/cloud auth | Migrate to OIDC-based short-lived credentials for anything CI still needs (registry push), and move actual cluster deployment to a pull-based GitOps controller so CI never holds cluster credentials at all |
| Adding a new microservice to GitOps management requires manually running `argocd app create` and is frequently forgotten | No App of Apps / `ApplicationSet` pattern — each `Application` is created imperatively rather than declared in Git | Adopt App of Apps or `ApplicationSet`, so a new service's onboarding is a Git commit under a watched directory, automatically picked up |
| A progressive rollout ping-pongs between versions repeatedly | The rollback threshold and the promotion threshold are too close together, or traffic-split granularity is too coarse for the actual request volume at low weights (e.g. 1% of a low-traffic service is statistically noisy) | Widen the gap between promote/rollback thresholds, increase the analysis `interval`/sample window, or raise the minimum weight step for low-traffic services so the metric sample size is meaningful |

---

## Tradeoffs & when NOT to use it

- **Don't run GitOps auto-sync (`selfHeal`/`automated`) on production namespaces without a team explicitly agreeing to it.** It's genuinely powerful for preventing drift, but the "I hand-edited something to unblock an incident and it silently reverted" surprise is real and has caused real confusion during live incidents — either keep manual sync for production, or make sure everyone touching that cluster knows auto-heal is active.
- **Don't adopt Argo Rollouts/Flagger for a low-traffic service without accounting for statistical noise at small canary weights.** A 10% traffic split on a service doing 20 requests/minute gives you roughly 2 requests/minute of canary sample size — nowhere near enough to distinguish a real regression from noise within any reasonable analysis interval; either use a fixed small absolute request count instead of a percentage, or skip automated canary analysis for genuinely low-traffic services and rely on manual verification instead.
- **Don't pick ArgoCD purely because it's the more popular/higher-starred option** if the team is heavily invested in complex Helm charts with lifecycle hooks — Flux's native Helm fidelity is a real, concrete advantage there, not a marginal one.
- **Don't skip a config-repo/app-repo split "to keep things simple" past a small handful of services.** It works fine for a single early-stage service, but scales poorly once multiple teams/services need independent deploy cadences and audit trails — untangling a merged repo later is real, avoidable migration pain.
- **Don't treat automated progressive delivery as a substitute for good test coverage before merge.** A canary with metric-gated rollback limits *blast radius* and *time-to-detection* for a bad deploy, it doesn't prevent the bad deploy from happening or catch classes of bugs that don't show up as elevated error rate/latency (a subtly wrong business-logic result that returns 200 OK, for instance).

---

## Interview questions

### Q1 — Explain why pull-based GitOps is considered more secure than a CI pipeline running `kubectl apply` directly.
**Testing:** the core credential-blast-radius argument, not just "GitOps is the modern way."
**Answer:** Push-based deploy requires every CI job to hold a cluster-write credential, meaning a compromised pipeline or leaked CI secret is a direct path to cluster compromise. Pull-based GitOps runs the reconciling controller *inside* the cluster; it pulls from Git using its own in-cluster credentials, and cluster-write access never needs to exist outside the cluster at all — CI's blast radius is limited to whatever it can push to a config repo, materially smaller than cluster-admin.
**Follow-up trap:** *"Does this mean CI needs zero privileged access at all?"* — no, CI typically still needs registry push access and config-repo write access, both real but smaller-blast-radius credentials than cluster-write; OIDC-based short-lived tokens for registry/cloud auth further reduces even that remaining surface versus a long-lived static secret.

### Q2 — What's the actual mechanism by which ArgoCD detects and corrects drift?
**Testing:** whether "reconciliation loop" is understood mechanically.
**Answer:** The `application-controller` polls the configured Git source on an interval (default ~3 minutes, plus optional webhook-triggered immediate refresh), renders the manifests, and diffs them against live cluster state — reporting `Synced`/`OutOfSync`. With `selfHeal: true`, any detected drift (including a manual `kubectl edit` against a managed resource) is automatically corrected back to match Git on the next reconcile cycle, without waiting for a new Git commit to trigger it.
**Follow-up trap:** *"A resource shows persistent OutOfSync even right after a successful sync. Why, and is that necessarily a bug?"* — a field is likely being mutated by something else in-cluster after Argo applies it (an admission webhook injecting a default, an HPA changing replica count) — this is expected, not a bug, and the fix is `ignoreDifferences` for those specific fields rather than treating it as broken reconciliation.

### Q3 — What does a `Rollout`'s canary `AnalysisTemplate` actually do, mechanically, that a plain `Deployment` rolling update cannot?
**Testing:** the specific mechanism of metric-gated progressive delivery.
**Answer:** At each traffic-weight step, the `AnalysisTemplate` runs a real query (commonly Prometheus) against live production metrics on a defined interval, checking a `successCondition` — if it fails a configured number of times (`failureLimit`), the `Rollout` controller automatically aborts and reverts traffic to the stable version, with no human needing to notice or act. A plain `Deployment`'s `RollingUpdate` has no concept of traffic weighting or metric evaluation at all — it just replaces pods based on count and relies entirely on probe health, not real traffic-level success metrics.
**Follow-up trap:** *"If the metrics provider (Prometheus) is temporarily unreachable during a canary, what happens?"* — this is a real operational gap worth naming: depending on configuration, an unreachable metrics source can cause the analysis to error out (ideally aborting the rollout conservatively) or, in a poorly configured setup, silently fail to gate anything and let the rollout proceed unchecked — which is exactly why alerting on `AnalysisRun` failures/errors as a distinct signal from rollout progression itself matters, so a silent metrics-provider outage doesn't quietly disable your safety net.

### Q4 — Compare ArgoCD and Flux's architectural approach to GitOps at a mechanical level, not just tooling popularity.
**Testing:** whether the actual architectural difference (bundled abstraction vs. composable CRDs) is understood.
**Answer:** ArgoCD wraps everything in a single `Application` CRD abstraction with a bundled dashboard, its own RBAC, and numeric sync-wave ordering for multi-resource sequencing. Flux exposes the same underlying reconciliation loop as separate, more granular CRDs (`GitRepository` as source, `Kustomization`/`HelmRelease` as reconcilers) composed explicitly via `dependsOn`, with no bundled UI — a genuinely more Unix-philosophy, wire-it-together model.
**Follow-up trap:** *"Given ArgoCD's larger adoption, is Flux ever the objectively better choice?"* — yes, concretely for teams with heavy, complex Helm chart usage — Flux's `HelmRelease` keeps full fidelity with standard Helm lifecycle hooks and tooling in a way ArgoCD's Helm-as-a-template-renderer approach doesn't fully preserve; adoption numbers don't settle a decision that should be driven by concrete fit (Helm dependency depth, need for a bundled dashboard, existing team tooling investment).

### Q5 — What's the App of Apps pattern, and what specific operational problem does it solve?
**Testing:** whether this is understood as solving a real onboarding/scale problem, not just "it's a pattern people use."
**Answer:** A root ArgoCD `Application` whose source is itself a directory of other `Application` manifests — so one ArgoCD instance can manage many applications/teams from a single Git-tracked root, and adding a new service to GitOps management becomes a Git commit under the watched directory rather than an imperative `argocd app create` command that's easy to forget or skip.
**Follow-up trap:** *"How does `ApplicationSet` extend this further, and when would you reach for it over plain App of Apps?"* — `ApplicationSet` templates `Application` generation dynamically from a generator (a list of clusters, a Git directory glob, a pull-request list) rather than requiring each `Application` manifest to be hand-written even under App of Apps — reach for it specifically when the same application needs to be deployed with slight variation across many clusters or many near-identical services, where hand-writing each `Application` doesn't scale.

### Q6 — A canary rollout for a low-traffic internal service keeps flapping — proceeding, then rolling back, then proceeding again on subsequent deploys. What's the likely root cause?
**Testing:** the statistical-noise trap at low sample sizes, a genuinely common real issue.
**Answer:** At a small initial traffic weight (e.g., 10%) on a genuinely low-volume service, the actual request count feeding the analysis metric per interval can be small enough that normal statistical noise crosses the success/failure threshold in either direction, independent of any real regression — the analysis isn't wrong, the sample size is just too small to be a reliable signal at that weight/interval combination.
**Follow-up trap:** *"What are two concrete ways to fix this, not just 'get more traffic'?"* — use a fixed absolute request count for canary exposure instead of a percentage (guaranteeing a meaningful sample regardless of overall traffic volume), or widen the analysis interval/sample window so more requests accumulate per evaluation — both address the same root cause (insufficient sample size) without requiring the service to actually have more real traffic.

### Q7 — Why do many teams keep `syncPolicy.automated` off (manual sync) for production namespaces even when the rest of their pipeline is fully automated?
**Testing:** the deliberate-human-gate judgment call, not "automation is always better."
**Answer:** Manual sync keeps a human confirmation point between "the diff is computed and visible" and "the diff is actually applied to production" — a deliberate, low-cost safety gate specifically for the highest-blast-radius environment, even when every earlier stage (build, test, staging deploy) is fully automated. It's a considered tradeoff (slower production deploys) in exchange for a final human check on exactly what's about to change in prod.
**Follow-up trap:** *"Doesn't this undermine the whole 'GitOps as continuous reconciliation' model?"* — not really — the reconciliation loop (drift detection, `OutOfSync` reporting) still runs continuously and automatically even with manual sync; only the *application* of a detected diff requires approval, so drift is still caught and visible immediately, just not auto-corrected without a human confirming it's the intended change.

### Q8 — A security review flags that the CI pipeline's cloud credential is a long-lived static secret with broad permissions. What's the modern fix, specific to GitHub Actions?
**Testing:** OIDC-based auth as the concrete, current answer, not a vague "use secrets management."
**Answer:** Configure OIDC federation (`permissions: id-token: write` in the workflow, plus a trust relationship configured on the cloud/registry side) so the workflow run receives a short-lived, workflow-scoped credential minted just for that run instead of a long-lived static secret stored in the repo/org secret store — eliminating the risk of an exfiltrated static credential being reused long after the workflow that needed it has finished.
**Follow-up trap:** *"Does OIDC eliminate the need for GitOps's pull-based cluster access model, since CI credentials are now short-lived too?"* — no, they solve different, complementary problems — OIDC reduces the *lifetime and reuse risk* of whatever credential CI holds, but a push-based model still requires CI to hold *some* cluster-write credential during that run, with all the blast-radius concerns that implies; pull-based GitOps eliminates cluster-write credentials from CI's scope entirely, a stronger and orthogonal guarantee.

---

## Red flags that fail you

- Describing GitOps as "just automated `kubectl apply` from CI" — missing the pull-based, in-cluster-controller distinction entirely.
- Claiming `Deployment`'s `RollingUpdate`, ArgoCD, or Flux alone perform traffic-percentage canary analysis.
- Not knowing that `selfHeal`/continuous reconciliation will revert a manual `kubectl edit` against a GitOps-managed resource.
- Treating ArgoCD as unconditionally superior to Flux without naming a real, concrete axis (Helm fidelity, dashboard need) the choice actually depends on.
- Recommending automated canary analysis for a low-traffic service without acknowledging the statistical sample-size problem at low weights.
- Believing a static, long-lived CI cloud credential is an acceptable default in 2026 when OIDC-based short-lived auth is standard practice.

---

## Cheat card

```
SPLIT: CI (GitHub Actions) builds/tests/pushes IMAGE + bumps CONFIG REPO. Never touches
  cluster directly. CD (ArgoCD/Flux) runs INSIDE cluster, PULLS from Git, reconciles.
  WHY: eliminates long-lived cluster-write creds from CI's blast radius entirely.

ARGOCD: Application CRD, application-controller polls Git (~3min default + webhook),
  diffs rendered manifests vs live state -> Synced/OutOfSync
  syncPolicy.automated + selfHeal:true -> auto-reverts manual kubectl edits (drift)
  sync-wave annotation -> explicit multi-resource ordering (CRDs before app, jobs after)
  App of Apps: root Application pointing at a dir of other Applications -> onboarding =
    a git commit. ApplicationSet: templated generation across clusters/dirs/PRs.

FLUX: no bundled dashboard, granular CRDs (GitRepository=source, Kustomization/
  HelmRelease=reconciler), dependsOn for ordering (not numeric waves)
  WINS on native Helm lifecycle fidelity vs ArgoCD's Helm-as-renderer approach
  ArgoCD WINS on dashboard, multi-cluster hub-and-spoke, broader current adoption

PROGRESSIVE DELIVERY (neither raw Deployment nor ArgoCD/Flux alone does this):
  Argo Rollouts: replaces Deployment w/ Rollout CRD, tight ArgoCD integration
  Flagger: wraps EXISTING Deployment unmodified, pairs w/ Flux
  BOTH: setWeight steps + AnalysisTemplate/metric checks (Prometheus etc.) against
  successCondition + failureLimit -> AUTOMATIC abort+rollback, no human needed to notice
  TRAP: low-traffic service + small weight = noisy sample -> false flapping; fix w/
  fixed absolute request count or wider analysis interval, not percentage alone

GH ACTIONS: permissions: id-token: write -> OIDC short-lived creds, no static secret
  reusable workflows/composite actions = shared pipeline logic, same over-abstraction
  risk as Terraform modules if over-parameterized

PROD PATTERN: separate CONFIG repo from APP SOURCE repo. Manual sync (not automated)
  common for production namespace as a deliberate human-confirmation gate even in an
  otherwise fully automated pipeline.
```

## Sources

- [ArgoCD vs FluxCD in 2026: Which is Better? — OneUptime](https://oneuptime.com/blog/post/2026-02-26-argocd-vs-fluxcd-2026/view) — accessed 2026-08-03
- [Argo Rollouts vs Flagger (2026): Pick Your Progressive Delivery Controller — NomadX](https://kubernetes.ae/argo-rollouts-vs-flagger/) — accessed 2026-08-03
- [ArgoCD vs Flux: The Complete 2026 GitOps Comparison Guide — Portainer](https://www.portainer.io/blog/argocd-vs-flux) — accessed 2026-08-03
- ArgoCD official documentation — Application CRD, sync waves, App of Apps, ApplicationSet
- Flux official documentation — GitRepository, Kustomization, HelmRelease, dependsOn
- GitHub Actions documentation — OIDC cloud authentication, reusable workflows
- Argo Rollouts and Flagger official documentation — canary AnalysisTemplate / metric-gated rollout mechanics

## Changelog
- 2026-08-03 — created
