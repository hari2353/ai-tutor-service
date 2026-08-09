# EKS vs ECS vs Fargate vs ECR — the Decision Matrix

> **Track:** T12 DevOps, Infra & Security · **Time:** 2h · **Prereqs:** T12-docker, T12-k8s-core
> **Module id:** `T12-eks-ecs-ecr` · **Tags:** k8s, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

The single most common confusion in this space is treating ECS/EKS and Fargate as competing choices on the same axis — they're not, they're **orthogonal**: ECS and EKS are **orchestrators** (they decide *where* and *how* your containers are scheduled and managed), while EC2 and Fargate are **compute engines** (they decide *what* those containers actually run on) — you can pair either orchestrator with either compute option, giving four real combinations (ECS+EC2, ECS+Fargate, EKS+EC2, EKS+Fargate), not two. The cost structure that actually drives the decision: EKS charges a flat **$0.10/hour control-plane fee** (~$73/month) per cluster before running a single workload, while ECS has **no control-plane fee** at all — on a single small service that fee can be a 400%+ tax on top of the actual compute bill, but at real fleet scale (dozens of tasks/pods) it shrinks to a low single-digit percentage of total spend and stops being the deciding factor. Fargate (serverless compute for either orchestrator) trades a real, quoted **40-60% price premium over equivalent EC2 capacity** for eliminating node management entirely — no patching, no capacity planning, no cluster-autoscaler tuning — a genuinely good trade for spiky/unpredictable workloads or teams without dedicated infra headcount, and a genuinely bad one for large, steady-state fleets where that premium compounds into real money better spent on committed EC2 capacity managed by a team that already has the operational muscle. The honest default for a new AWS-only team without a hard requirement forcing Kubernetes specifically: start with **ECS + Fargate** (simplest operational model, zero control-plane fee, adequate for the large majority of container workloads), and graduate to EKS specifically when a real, named requirement shows up — genuine multi-cloud portability, a Kubernetes-specific tool/operator the team depends on, or hiring/ecosystem reasons — not because Kubernetes is the assumed "serious" choice by default.

## Why this gets asked

Because "we run everything on Kubernetes" is often a default reached without ever seriously comparing it against ECS, and the interviewer wants to know whether that was a deliberate, reasoned choice or cargo-culted from what's popular. They've likely either watched a small team take on EKS's real operational complexity (RBAC, CNI, add-on management, IAM-for-service-accounts) for a handful of services that ECS would have handled with a fraction of the setup, or watched the opposite — a team stuck on ECS hit a real, genuine ceiling (needing a specific Kubernetes operator, or multi-cloud portability) and pay a costly, avoidable migration later. This section tests judgment about matching tooling to actual requirements, not tool trivia.

---

## Lineage: past → present → future

**What came before.** AWS's own container orchestration story started with ECS (2014), built specifically as AWS's proprietary, deeply-integrated answer to "run containers on AWS" years before Kubernetes had matured into today's ubiquitous standard — ECS predates EKS by roughly four years and was, for a long stretch, the only real AWS-native option. As Kubernetes won broad industry adoption as the *de facto* container orchestration standard (multi-cloud portability, a vast ecosystem of tooling, and a large, transferable hiring pool independent of any single cloud vendor), AWS launched EKS (2018) specifically to meet that demand rather than lose customers to running self-managed Kubernetes on EC2 (a real, painful pattern teams did before EKS existed — hand-rolling `kubeadm`-based clusters, hand-managing the control plane's availability and upgrades entirely themselves). Fargate (2017, initially ECS-only, extended to EKS in 2019) addressed a separate, cross-cutting pain: even with a managed orchestrator control plane, teams still had to provision, patch, and right-size the *worker nodes* underneath it — Fargate removed that entire layer for workloads willing to pay its premium for it.

**Where it stands now.** The "ECS vs EKS" debate has stabilized around a fairly settled decision framework rather than an unresolved argument: pure control-plane cost and operational simplicity favor ECS for AWS-only teams without a specific Kubernetes requirement, while EKS is the correct default the moment genuine multi-cloud portability, Kubernetes-specific tooling/operator dependencies, or organizational Kubernetes standardization (a platform team running many clusters/services with shared tooling built around K8s primitives) are real requirements rather than aspirational ones. The live, less-settled disagreement is really about Fargate's premium threshold — teams disagree, reasonably, about exactly where "the operational savings are worth the ~40-60% compute premium" stops being true, and the honest answer depends on workload predictability (steady-state large fleets tend to favor EC2's better unit economics) and whether the team has genuine spare capacity/expertise to manage nodes well, not a fixed rule. ECR has matured alongside both — pull-through cache (letting ECR transparently proxy and cache images from Docker Hub, GHCR, Quay, and even niche upstreams like Chainguard's registry as of a 2026 feature addition) directly addresses the Docker Hub rate-limiting pain covered in the troubleshooting module, letting a cluster's actual pulls hit ECR (fast, in-region, no external rate limit) instead of the public upstream on every pull.

**Where it's heading.** Expect continued convergence on "Fargate-first, EC2 when you've proven you need the unit economics" as the default recommendation across both orchestrators, mirroring the broader industry trend (also visible in the autoscaling module's Karpenter discussion) toward faster-provisioning, less-hand-managed compute as the default, with dedicated node management reserved for teams with genuine scale and cost-optimization headroom to justify the operational investment. ECR's pull-through cache and supply-chain features (scanning, SBOM support, registry federation) continue expanding as software supply-chain security becomes a harder compliance requirement industry-wide — this is a stable, well-funded direction rather than a speculative one.

---

## Mental model

```
                    ORCHESTRATOR (where/how containers are scheduled)
                    ┌─────────────────┬─────────────────┐
                    │       ECS         │       EKS         │
                    │  AWS-proprietary   │  managed Kubernetes │
                    │  API, no k8s YAML   │  full k8s API/CRDs  │
COMPUTE   ┌─────────┼─────────────────┼─────────────────┤
(what runs│   EC2    │  ECS + EC2         │  EKS + EC2         │
 the      │          │  you manage nodes   │  you manage nodes   │
 container│          │  (patching, ASG)     │  (patching, ASG)     │
 workload)├─────────┼─────────────────┼─────────────────┤
          │ Fargate  │  ECS + Fargate      │  EKS + Fargate      │
          │          │  ~40-60% premium,    │  ~40-60% premium,    │
          │          │  ZERO node mgmt       │  ZERO node mgmt       │
          └─────────┴─────────────────┴─────────────────┘

COST SHAPE:
  EKS control plane: FLAT $0.10/hr (~$73/mo) regardless of workload size
    -> dominant cost for a tiny cluster, noise (<5%) for a large fleet
  ECS control plane: $0 always
  Fargate: real, quoted 40-60% premium vs equivalent EC2 capacity, EITHER orchestrator

DEFAULT: ECS + Fargate for AWS-only, no hard k8s requirement
  -> graduate to EKS when a REAL requirement (multi-cloud, specific k8s tooling/
     operator, hiring/ecosystem) shows up, not by default
```

---

## How it actually works

### ECS — task definitions, services, and cluster capacity providers

ECS's core unit is a **task definition** (a JSON/YAML document describing one or more containers, their images, CPU/memory, port mappings, and IAM task role — directly analogous to a Kubernetes `Pod` spec, but AWS-proprietary rather than the portable Kubernetes API), run as either a standalone **task** (analogous to a bare Pod) or managed continuously by a **service** (analogous to a `Deployment` — maintains a desired task count, handles rolling replacement, integrates with an Application Load Balancer's target group for traffic routing and health checks). A **cluster** in ECS is a logical grouping, and its actual compute comes from a **capacity provider** — either an Auto Scaling Group of EC2 instances running the ECS agent, or Fargate/Fargate Spot as a fully-managed capacity provider requiring no instances at all. ECS's IAM model is genuinely simpler than Kubernetes RBAC + IRSA for teams already fluent in IAM: a task's permissions come directly from its **task role** (a normal IAM role, assumed by the task via the container's credential provider) — no separate service-account-to-IAM-role federation layer to reason about, which is a real, concrete simplicity advantage for AWS-only teams over EKS's IAM Roles for Service Accounts (IRSA) or Pod Identity mechanism covered below.

### EKS — the managed control plane, and what "managed" actually means

EKS runs the Kubernetes control plane (API server, etcd, scheduler, controller-manager) across multiple AWS-managed, multi-AZ instances, with AWS handling its patching, upgrades (within a supported window — EKS supports a rolling set of recent minor versions, typically the last several, requiring periodic version upgrades rather than indefinite staying-put), and availability — genuinely removing the hardest, highest-blast-radius operational burden of running Kubernetes yourself (a self-managed control plane's etcd corruption or API server outage is a severe, all-hands incident; on EKS that's AWS's operational problem, not yours). What EKS does **not** manage for you by default: worker nodes (unless using Fargate profiles or EKS-managed node groups, which still require you to choose instance types/AMIs and configure scaling), most add-ons (CNI, CoreDNS, `kube-proxy`, storage/ingress controllers — increasingly offered as "EKS add-ons" with AWS-managed lifecycle, but not automatic unless explicitly enabled), and critically, IAM-for-Kubernetes-workloads, which requires either **IRSA** (IAM Roles for Service Accounts — an OIDC federation trust between the cluster's OIDC provider and IAM, letting a Kubernetes `ServiceAccount` assume a specific IAM role) or the newer, simpler **EKS Pod Identity** (a more direct association mechanism reducing some of IRSA's OIDC-trust configuration overhead) — either way, a genuinely more involved setup than ECS's direct task-role model, and a real, common source of "why can't my pod reach S3" debugging sessions when the ServiceAccount-to-IAM-role association is missing or misconfigured.

**Fargate profiles on EKS** let specific pods (matched by namespace/label selector) run on Fargate instead of EC2-backed managed node groups within the same cluster — a real, useful hybrid pattern (steady-state workloads on cost-efficient EC2 node groups, bursty or infrequent workloads on Fargate profiles within the same cluster) rather than an all-or-nothing choice per cluster. A concrete Fargate-on-EKS limitation worth naming: **DaemonSets don't run on Fargate** at all (Fargate pods each get their own isolated compute, with no concept of a shared node to run a DaemonSet's one-per-node pattern against) — a real, sometimes-surprising gap for teams expecting their node-level logging/monitoring agent DaemonSet to "just work" across a Fargate profile's pods, since it structurally can't.

### ECR — registry mechanics, IAM auth, and pull-through cache

ECR authentication for EKS worker nodes is automatic via the **node's IAM role** — for same-account, same-region image pulls, no `imagePullSecrets` are needed at all, since the node's own IAM identity (attached to the EC2 instance profile, or the Fargate task's execution role) is what authenticates the pull, a meaningfully simpler model than the private-registry-secret pattern covered in the troubleshooting module for third-party registries. **Image scanning** (basic scanning on push using Clair-based CVE detection, or "enhanced scanning" integrating with Amazon Inspector for continuous rescanning as new CVEs are published against already-pushed images, not just at push time) surfaces known vulnerabilities directly in the registry, and **lifecycle policies** (rule-based image expiration — e.g., "keep the last 10 tagged images per repository, expire untagged images after 14 days") are the standard mechanism to stop a repository from accumulating unbounded image history and storage cost, since ECR otherwise retains every pushed image indefinitely. **Pull-through cache** (a genuinely useful, more recent capability) lets ECR transparently proxy and cache images from configured upstream registries — Docker Hub, GitHub Container Registry, Quay, and as of a 2026 expansion, Chainguard's registry — so a cluster's actual pulls hit ECR (fast, same-region, not subject to the upstream's rate limits) instead of the public registry directly on every pull, which is the concrete, production fix for the Docker-Hub-rate-limiting `ImagePullBackOff` failure mode covered in the troubleshooting module, without requiring a team to run and maintain their own separate pull-through proxy infrastructure.

---

## Build it from scratch

```json
// untested sketch — minimal ECS task definition, Fargate-compatible
{
  "family": "checkout-api",
  "requiresCompatibilities": ["FARGATE"],
  "networkMode": "awsvpc",
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123456789012:role/checkoutApiTaskRole",
  "containerDefinitions": [{
    "name": "api",
    "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/checkout-api:v12",
    "portMappings": [{ "containerPort": 8080 }],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/checkout-api",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "api"
      }
    }
  }]
}
```

```yaml
# untested sketch — EKS Fargate profile restricting specific namespace/labels to Fargate
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig
metadata: { name: prod-cluster, region: us-east-1 }
fargateProfiles:
- name: batch-jobs
  selectors:
  - namespace: batch
    labels: { compute: fargate }
  # pods matching this selector run on Fargate; everything else uses the
  # cluster's regular EC2-backed managed node groups
```

```bash
# ECR: create a pull-through cache rule for Docker Hub, avoiding rate-limit pain
aws ecr create-pull-through-cache-rule \
  --ecr-repository-prefix docker-hub \
  --upstream-registry-url registry-1.docker.io

# a pod's image reference then becomes:
#   123456789012.dkr.ecr.us-east-1.amazonaws.com/docker-hub/library/redis:7
# instead of pulling redis:7 directly from Docker Hub on every node
```

---

## How it's done in production

Real AWS-native production setups near-universally attach an ECR **lifecycle policy** to every repository from day one (unbounded image retention is a genuine, easily-overlooked storage-cost leak), enable at least basic scan-on-push (with enhanced/Inspector-based continuous scanning for anything handling sensitive data or regulated workloads), and configure a pull-through cache for any heavily-used public upstream (Docker Hub especially) rather than pulling directly and accepting rate-limit risk. Teams running EKS at real scale invest specifically in IRSA/Pod Identity setup discipline (least-privilege IAM roles scoped per ServiceAccount, not one broad role shared across every workload) since this is both the most common EKS-specific debugging pain point and the most common over-permissioning risk if rushed.

| Symptom | Cause | Fix |
|---|---|---|
| A pod on EKS can't reach an AWS service (S3, DynamoDB) despite the IAM role having correct permissions | Missing or misconfigured IRSA/Pod Identity association — the ServiceAccount isn't actually federated to the IAM role, or the pod isn't using that ServiceAccount | Verify the ServiceAccount's annotation (IRSA) or Pod Identity association references the correct IAM role ARN, and that the pod spec actually references that ServiceAccount |
| A DaemonSet-based logging/monitoring agent silently doesn't cover pods running on an EKS Fargate profile | Fargate has no concept of a shared node for DaemonSets to run against — they structurally don't run on Fargate at all | Use a sidecar container pattern instead for Fargate-profile pods needing the same logging/monitoring coverage a DaemonSet would otherwise provide |
| ECR storage costs keep climbing steadily with no corresponding growth in active image usage | No lifecycle policy — ECR retains every pushed image indefinitely by default | Attach a lifecycle policy (e.g., keep last N tagged images, expire untagged images after N days) to every repository |
| Node/pod image pulls intermittently fail with `ImagePullBackOff` and Events show a rate-limit-flavored error from Docker Hub | Direct pulls from the public upstream hitting Docker Hub's rate limits, especially during a burst of simultaneous pulls (a scale-up event, a node replacement) | Configure an ECR pull-through cache rule for Docker Hub and repoint image references through it |
| A small team's monthly AWS bill shows a disproportionately large EKS line item relative to actual workload footprint | The flat $0.10/hr per-cluster control-plane fee dominates cost at small scale — running many small clusters instead of fewer, larger ones multiplies this fixed cost | Consolidate small/dev/test workloads onto fewer clusters (with namespace-level isolation) rather than one cluster per small service, or reconsider ECS for genuinely small, AWS-only workloads |
| A steady-state, predictable, large fleet's compute bill is notably higher than a cost model built around EC2 pricing suggested | Fargate's ~40-60% premium over equivalent EC2 capacity, appropriate for its zero-node-management tradeoff but compounding at scale | Evaluate migrating steady-state, predictable portions of the fleet to EC2-backed capacity (managed node groups or ECS+EC2), reserving Fargate for genuinely bursty/unpredictable workloads where its tradeoff still makes sense |

---

## Tradeoffs & when NOT to use it

- **Don't default to EKS for a new, AWS-only team without a real, named requirement forcing Kubernetes specifically.** The $73/month control-plane fee is real but usually not the deciding cost factor — the deciding factor is the added operational complexity (RBAC, IRSA/Pod Identity, CNI/add-on management, Kubernetes upgrade cadence) that ECS simply doesn't require, and taking that on without a genuine need (multi-cloud, a specific K8s-only tool, ecosystem/hiring reasons) is real, avoidable overhead.
- **Don't default to Fargate for a large, steady-state, well-understood fleet without checking the math.** The ~40-60% premium is a real, quoted number, not marketing noise — for predictable capacity at real scale, EC2-backed capacity (managed by a team that already has the operational muscle, or via Karpenter/Cluster Autoscaler from the scaling module) often has meaningfully better unit economics, and Fargate's zero-node-management value proposition matters most for bursty, unpredictable, or operationally under-resourced workloads specifically.
- **Don't assume DaemonSet-based tooling (logging agents, node-level monitoring) will "just work" on an EKS Fargate profile.** It structurally cannot — Fargate has no shared-node concept for a DaemonSet to run against, and this needs a different pattern (sidecars) planned for upfront, not discovered as a surprise gap later.
- **Don't skip ECR lifecycle policies "for now."** Unbounded image retention is a slow, easy-to-miss cost leak that compounds silently over months/years of CI pushing new tagged and untagged images continuously.
- **Don't choose ECS over EKS purely for the simpler IAM model if the team already has genuine, deep Kubernetes expertise and tooling investment elsewhere.** ECS's task-role simplicity is a real advantage for teams *without* that investment, but for a team that's already fluent in Kubernetes patterns and has shared tooling built around them, forcing a second, AWS-proprietary orchestration model onto the team for one workload can cost more in context-switching and tooling duplication than it saves in IAM simplicity.

---

## Interview questions

### Q1 — Explain why "ECS vs Fargate" is a category error, and give the actual decision axes.
**Testing:** the orchestrator-vs-compute distinction, the single most-tested fact in this module.
**Answer:** ECS is an orchestrator (decides where/how containers are scheduled); Fargate is a compute engine (decides what they physically run on). They're not competing choices — the real decision has two independent axes: orchestrator (ECS vs. EKS) and compute (EC2 vs. Fargate), giving four real combinations, not two.
**Follow-up trap:** *"So what's the actual comparison when someone says 'should we use ECS or Fargate'?"* — the question as phrased is imprecise; the real question is almost always "ECS or EKS" (orchestrator choice) combined separately with "EC2 or Fargate" (compute choice) — restating the question correctly before answering it is itself the signal an interviewer is checking for here.

### Q2 — What's the actual cost structure difference between ECS and EKS, and at what point does it stop mattering?
**Testing:** real numbers, and judgment about when a cost factor becomes noise.
**Answer:** EKS charges a flat $0.10/hour (~$73/month) control-plane fee per cluster regardless of workload size; ECS has no control-plane fee. On a single small service, that fee can be a 400%+ tax on top of actual compute spend. At real fleet scale (dozens of tasks/pods), the fixed fee shrinks to a low single-digit percentage of total spend and stops being the deciding factor — the decision at scale should be driven by operational fit, not the control-plane fee.
**Follow-up trap:** *"Does running many small EKS clusters change this calculus?"* — yes, and it's a real trap — a team running one small EKS cluster per environment/team without consolidation multiplies the fixed $73/month fee across many clusters, each individually small enough that the fee dominates, even though the team's *aggregate* workload might be large enough that a single larger cluster's fee would be genuinely negligible; consolidation onto fewer clusters (with namespace isolation) avoids this.

### Q3 — What's the quoted price premium for Fargate over equivalent EC2 capacity, and what's the actual tradeoff being purchased?
**Testing:** whether the "serverless is always simpler and worth it" instinct is checked against real numbers.
**Answer:** Commonly quoted in the 40-60% range above equivalent EC2 compute capacity, on either orchestrator. What's purchased for that premium: zero node management — no patching, no capacity planning, no autoscaler tuning, no instance-type selection — a genuinely good trade for bursty/unpredictable workloads or teams without dedicated infra capacity, and a genuinely bad one for large, steady-state, predictable fleets where that premium compounds into real, avoidable spend.
**Follow-up trap:** *"If a team is Fargate-everywhere today and wants to optimize cost, what's the right first move?"* — identify the steady-state, predictable *portion* of the fleet specifically (not a blanket migration) and move only that portion to EC2-backed capacity, keeping genuinely bursty/unpredictable workloads on Fargate where the premium is still buying real operational value — an all-or-nothing migration in either direction usually leaves value on the table.

### Q4 — Why can't a DaemonSet run on an EKS Fargate profile, and what replaces it there?
**Testing:** a specific, real, often-surprising Fargate limitation.
**Answer:** Fargate gives each pod its own isolated compute with no concept of a shared node — a DaemonSet's entire model (one pod per node) has nothing to attach to on Fargate, so it structurally cannot run there at all, not just as an unsupported configuration. Sidecar containers within each pod are the standard replacement pattern for logging/monitoring coverage that a DaemonSet would otherwise provide on EC2-backed nodes.
**Follow-up trap:** *"If a cluster uses both EC2-backed managed node groups and a Fargate profile, do you need both a DaemonSet and sidecars?"* — yes, realistically — the DaemonSet covers the EC2-backed portion of the cluster as normal, while pods running under the Fargate profile need the sidecar pattern separately, since neither mechanism alone covers both compute types; this dual-coverage requirement is a real, easy-to-miss gap when a team adds a Fargate profile to an existing EC2-node-group cluster without revisiting their logging/monitoring setup.

### Q5 — How does IAM authentication for a container's AWS API access differ between ECS and EKS, mechanically?
**Testing:** the task-role-vs-IRSA distinction, a real and common EKS debugging pain point.
**Answer:** ECS: a task's permissions come directly from its task role, a normal IAM role assumed by the container via the standard credential provider chain — no separate federation layer. EKS: a Kubernetes `ServiceAccount` has no IAM identity by default; it needs either IRSA (OIDC federation trust between the cluster's OIDC provider and IAM, letting a specific ServiceAccount assume a specific IAM role) or the newer, simpler EKS Pod Identity mechanism to get any AWS permissions at all.
**Follow-up trap:** *"A pod can't reach S3 despite the referenced IAM role clearly having s3:GetObject permission. What do you check first, given this model?"* — whether the ServiceAccount-to-IAM-role association (the IRSA annotation, or the Pod Identity association) actually exists and is correctly configured, and whether the pod spec references that specific ServiceAccount at all — a perfectly correct IAM policy is irrelevant if the federation/association linking the pod's identity to that role is missing or misconfigured, which is the most common root cause of this exact symptom.

### Q6 — Why do EKS worker nodes not need `imagePullSecrets` to pull from ECR, while pulling from a private third-party registry does?
**Testing:** cross-module synthesis with the troubleshooting module's ImagePullBackOff coverage.
**Answer:** For same-account, same-region ECR pulls, authentication happens automatically via the node's own IAM role (or the Fargate task's execution role) — the node's AWS identity itself is what authenticates the pull, no separate credential object needed. A third-party registry (Docker Hub, a private non-AWS registry) has no such native IAM integration, so it needs an explicit `imagePullSecrets`-referenced Kubernetes Secret holding registry credentials instead.
**Follow-up trap:** *"Does this mean ECR pulls can never fail for auth reasons?"* — no — cross-account ECR access (pulling from a different AWS account's repository) or cross-region considerations still require explicit repository policy/IAM configuration to permit the pull, and a misconfigured cross-account setup produces the same auth-flavored `ImagePullBackOff` Events as a misconfigured third-party registry secret would.

### Q7 — What problem does ECR pull-through cache solve, and how does it relate to the DNS/registry pain covered in the troubleshooting module?
**Testing:** whether this is understood as a real production fix, not just a feature name.
**Answer:** It lets ECR transparently proxy and cache images from configured upstream registries (Docker Hub, GHCR, Quay, and others) so a cluster's actual pulls hit ECR — fast, same-region, not subject to the upstream's own rate limits — instead of pulling directly from the public registry on every single pull. This is the concrete production fix for the Docker-Hub-rate-limit-driven `ImagePullBackOff` failure mode, without a team needing to build and maintain their own separate pull-through proxy infrastructure.
**Follow-up trap:** *"Does enabling pull-through cache change what image reference pods use?"* — yes — pods reference the ECR-proxied path (e.g., `<account>.dkr.ecr.<region>.amazonaws.com/docker-hub/library/redis:7`) rather than the original upstream path directly; this is a real, deliberate config change across manifests, not a transparent, zero-touch enablement, and needs to be planned as part of adopting it.

### Q8 — A startup asks whether they should build on ECS or EKS, with no existing Kubernetes investment and no multi-cloud requirement. What's your honest recommendation, and what would change it?
**Testing:** the senior judgment call this module is built to test.
**Answer:** Start with ECS + Fargate — simplest operational model, zero control-plane fee, adequate for the large majority of container workloads, and a materially smaller IAM/operational learning curve than EKS's RBAC + IRSA/Pod Identity model. Recommend EKS instead only if a real, named requirement is already present: genuine multi-cloud portability plans, dependency on a specific Kubernetes-only tool/operator, or a deliberate organizational bet on Kubernetes for hiring/ecosystem reasons.
**Follow-up trap:** *"The startup says they might need multi-cloud 'eventually.' Does that justify EKS now?"* — generally no — "might need it eventually" is a weak signal compared to "we have a concrete, funded plan to run on a second cloud within N months"; over-engineering for hypothetical future portability by taking on EKS's real, current operational complexity is the same class of mistake as the Terraform module's over-abstraction trap — build for the requirement you actually have, migrate when the hypothetical becomes concrete.

### Q9 — Your EKS cluster's VPC CNI keeps failing to schedule new pods with "insufficient IP addresses" even though CPU/memory headroom exists on the nodes. What's happening, and how do you fix it?
**Testing:** the specific, real EKS networking gotcha that trips up teams moving from ECS's simpler networking model.
**Answer:** The default AWS VPC CNI assigns each pod a real, routable IP address from the VPC subnet — not an overlay network — so pod density per node is bounded by how many ENI secondary IPs the instance type can hold and how much free address space the subnet has, independent of CPU/memory capacity. A large instance type in a small `/24` subnet, or a subnet that's been slowly exhausted by cumulative pod churn, hits this ceiling well before compute resources do. Fixes: size subnets with real headroom up front (a `/24` is often too small for a busy cluster), enable prefix delegation (assigning /28 IP prefixes instead of individual IPs per ENI, multiplying usable IPs per node substantially), or switch to an overlay-mode CNI if VPC-routable pod IPs aren't actually required.
**Follow-up trap:** *"Why does ECS not have this exact problem in the same way?"* — ECS's `awsvpc` mode gives each *task* an ENI too, so it has a related IP-exhaustion ceiling, but ECS task density per host is typically lower and more deliberately provisioned than Kubernetes' higher pod-per-node bin-packing default, so teams hit the ceiling less often in practice — it's the same underlying VPC-ENI constraint, just less commonly exercised at ECS's typical density.

### Q10 — Compare Cluster Autoscaler and Karpenter for EKS node provisioning — what's the actual mechanical difference, not just "Karpenter is newer"?
**Testing:** current, staff-relevant EKS infrastructure knowledge beyond the basics.
**Answer:** Cluster Autoscaler works within pre-defined node groups (ASGs) — it can only scale the size of groups you've already configured with specific instance types, so a spike needing an instance type not represented in any existing group can't be served without a human pre-provisioning that group. Karpenter provisions nodes directly, without ASGs as an intermediary — it evaluates pending pods' actual resource requests and picks the best-fit instance type and AZ from a broad allowed set at scheduling time, and can bin-pack and consolidate more aggressively (actively replacing underutilized nodes with better-fit ones, not just scaling a group up/down). The practical result: faster scale-up latency and materially better bin-packing efficiency, at the cost of a newer, less battle-tested-at-extreme-scale codebase than Cluster Autoscaler's years of production hardening.
**Follow-up trap:** *"If Karpenter picks instance types dynamically, how do you prevent it from provisioning an expensive GPU instance for a workload that doesn't need one?"* — `NodePool`/`EC2NodeClass` constraints scope which instance families, sizes, and capacity types (on-demand vs. spot) Karpenter is allowed to choose from per workload class — the dynamic selection is bounded by an explicit allow-list you define, not truly unconstrained, and a misconfigured overly-broad NodePool is a real cost-control gotcha teams hit on initial adoption.

---

## Red flags that fail you

- Treating "ECS vs Fargate" as a real, single-axis comparison rather than recognizing orchestrator and compute are orthogonal choices.
- Not knowing the actual EKS control-plane fee ($0.10/hr, ~$73/month) or that ECS has none.
- Claiming Fargate is unconditionally cheaper or more cost-effective than EC2-backed capacity without naming the real 40-60%-range premium.
- Not knowing that DaemonSets structurally cannot run on EKS Fargate profiles.
- Recommending EKS by default for a new AWS-only team without a real, named requirement.
- Not knowing the IRSA/Pod Identity mechanism exists, or conflating it with ECS's simpler task-role model.
- Being unaware ECR pull-through cache exists as the production fix for Docker Hub rate-limit-driven pull failures.

---

## Cheat card

```
ORTHOGONAL AXES: ORCHESTRATOR (ECS | EKS) x COMPUTE (EC2 | Fargate) = 4 real combos.
  "ECS vs Fargate" is a category error — restate the actual question when asked.

COST: EKS control plane = FLAT $0.10/hr (~$73/mo) per cluster, regardless of size.
  ECS control plane = $0, always.
  -> dominant cost for a tiny cluster (can be 400%+ tax), noise (<5%) at real fleet scale
  -> running MANY small EKS clusters multiplies the fixed fee — consolidate instead

FARGATE: ~40-60% price premium vs equivalent EC2 capacity (either orchestrator), for
  ZERO node management (no patching/capacity planning/autoscaler tuning). Good for
  bursty/unpredictable workloads or under-resourced infra teams. Bad default for large,
  steady-state, predictable fleets — premium compounds into real avoidable spend.

DEFAULT: ECS + Fargate for AWS-only, no hard k8s requirement. Graduate to EKS ONLY for
  a real, named requirement: multi-cloud, specific k8s-only tool/operator, deliberate
  hiring/ecosystem bet. NOT "might need it eventually."

ECS IAM: task role = normal IAM role, directly assumed by the task. SIMPLE.
EKS IAM: ServiceAccount has NO IAM identity by default -> needs IRSA (OIDC federation)
  or EKS Pod Identity (newer, simpler) to get AWS permissions at all. Common bug:
  ServiceAccount-to-role association missing/misconfigured -> "can't reach S3" despite
  a correct IAM policy.

FARGATE + DAEMONSET: DaemonSets CANNOT run on Fargate — no shared-node concept to
  attach to. Use sidecar containers instead for logging/monitoring on Fargate pods.
  Mixed EC2-nodegroup + Fargate-profile cluster needs BOTH patterns (DaemonSet for
  EC2 nodes, sidecars for Fargate pods) for full coverage.

ECR: same-account/region pulls auth via NODE's IAM role, NO imagePullSecrets needed.
  Cross-account needs explicit repo policy/IAM. Scanning: basic (scan-on-push, Clair-
  based) or enhanced (Inspector, continuous rescan as new CVEs publish). Lifecycle
  policies REQUIRED or images retained indefinitely -> silent storage cost leak.
  Pull-through cache: proxies/caches Docker Hub/GHCR/Quay/Chainguard(2026) through ECR
  -> fixes Docker Hub rate-limit ImagePullBackOff, image refs change to the ECR path.
```

## Sources

- [ECS vs EKS vs Fargate: $0 vs $73/mo Control Plane [2026]](https://tech-insider.org/ecs-vs-eks-vs-fargate-2026/) — accessed 2026-08-03
- [AWS ECS vs. EKS vs. Fargate: The Essential Guide — nOps](https://www.nops.io/blog/ecs-vs-eks-vs-fargate/) — accessed 2026-08-03
- [EKS Pricing in 2026: The $438/Month Trap and How to Avoid It — Cloud Burn](https://cloudburn.io/blog/amazon-eks-pricing) — accessed 2026-08-03
- [Sync an upstream registry with an Amazon ECR private registry — AWS documentation](https://docs.aws.amazon.com/AmazonECR/latest/userguide/pull-through-cache.html) — accessed 2026-08-03
- [Amazon ECR now supports pull through cache for Chainguard — AWS What's New](https://aws.amazon.com/about-aws/whats-new/2026/03/amazon-ecr-pull-through-cache-chainguard) — accessed 2026-08-03
- AWS documentation — ECS task definitions/services/capacity providers, EKS Fargate profiles, IRSA, EKS Pod Identity, ECR image scanning and lifecycle policies

## Changelog
- 2026-08-03 — created
