# Compute & Containers: EC2, ECS, EKS, Fargate, Batch

> **Track:** C-AWS AWS Atlas · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `C-AWS-compute` · **Tags:** compute

## Why this gets asked

Almost every principal-level system design question eventually asks "how does this run" and the honest answer is never "we picked the trendiest orchestrator." The interviewer has lived through a team choosing EKS because it looked resume-worthy and then discovering nobody on the team could debug a `CrashLoopBackOff` at 2am, or the inverse — choosing the "simple" option and outgrowing it in six months. They want to see you reason about the actual axes that matter: who carries the operational burden, what the ecosystem gives you for free, what it costs at your actual scale, and how fast you can recover capacity when something dies. Cross-reference: this module assumes you've also read `T12-eks-ecs-ecr` for the ECS/EKS/ECR mechanics in depth; this module is the decision layer on top of that.

---

## Lineage: past → present → future

**What came before.** Pre-2013, "compute" on AWS meant EC2 instances you provisioned, patched, and load-balanced yourself, with Auto Scaling Groups as the only elasticity primitive. Deploying a new version meant either in-place mutation (risky, hard to roll back) or a blue/green fleet swap you built by hand. Docker (2013) made packaging portable but didn't solve placement or scheduling — you still needed something deciding which host ran which container. That gap is what ECS (2014) and later EKS (2018) filled, and what Fargate (2017, ECS; 2019, EKS) then abstracted away entirely by removing the "which host" question altogether.

**Where it stands now.** The real split isn't "containers vs VMs" anymore — it's how much control-plane and node-management burden a team is willing to carry versus buy down. ECS on Fargate is AWS's own recommended default for teams without an existing Kubernetes investment: zero control-plane fee, two-command deploys, no node patching. EKS earns its complexity when there's a concrete trigger — multi-cloud/hybrid strategy, a Kubernetes-native tool dependency, or a platform team serving many internal tenants who already live in `kubectl`. The live disagreement is whether EKS's ecosystem gravity (Helm charts, operators, the hiring pool of people who already know Kubernetes) outweighs its control-plane cost and operational surface for a mid-size team — reasonable engineers land differently depending on team composition, not workload shape alone.

**Where it's heading.** Fargate is absorbing more of what used to require EC2 launch type (GPU support remains a hard gap as of 2026), and Karpenter has become the de facto EKS node-provisioning answer, replacing hand-tuned Cluster Autoscaler configs with bin-packing-aware, spot-integrated node lifecycle management. Direction of travel, moderate confidence: further blurring of "serverless containers" and "Kubernetes" as EKS Auto Mode and similar managed-node offerings reduce the node-operations gap that used to be EKS's biggest tax.

---

## Mental model

Two independent axes, frequently conflated:

```
                  ORCHESTRATOR (decides WHERE containers run / scheduling logic)
                  ┌─────────────┬─────────────┐
                  │     ECS     │     EKS      │
                  │ AWS-native, │ Kubernetes,  │
                  │ simple API  │ full K8s API │
  ┌───────────────┼─────────────┼──────────────┤
  │   Fargate     │  ECS+Fargate│  EKS+Fargate │  <- serverless compute,
  │ (WHAT runs on,│  (most common│ (per-pod,   │     no node management
COMPUTE│serverless) │   default)  │  GPU: no)   │
  │───────────────┼─────────────┼──────────────┤
  │      EC2      │  ECS+EC2    │  EKS+EC2     │  <- you manage nodes,
  │ (you manage   │ (full control,│(full K8s + │     full instance-type
  │  the fleet)   │  GPU: yes)  │  GPU: yes)   │     and GPU flexibility
  └───────────────┴─────────────┴──────────────┘
```

ECS and EKS are orchestrators; Fargate and EC2 are compute engines underneath either orchestrator. The decision is genuinely two separate questions: "which scheduler API" and "who manages the hosts."

---

## How it actually works

### EC2 instance families — reading a name

Format: `[family][generation][additional capabilities].[size]`. Family letter indicates workload class (`c` compute, `m` general purpose, `r` memory, `i`/`d` storage, `p`/`g`/`inf`/`trn` accelerated), generation is a number, and trailing letters are options: `g` = Graviton (ARM), `n` = enhanced networking, `d` = local NVMe instance store, `e` = extra (usually more memory or storage per vCPU). Example: `c6i.2xlarge` = compute-optimized, 6th gen, Intel, 2xlarge size. `m7g.xlarge` = general purpose, 7th gen, Graviton. `p5en.48xlarge` = 5th-gen P-series (GPU) with extra and enhanced networking. [EC2 instance type naming — AWS docs](https://docs.aws.amazon.com/ec2/latest/instancetypes/instance-type-names.html) — accessed 2026-08-01.

### Purchase options and discount ranges

| Option | Discount vs on-demand | Commitment | Risk |
|---|---|---|---|
| On-Demand | 0% (baseline) | None | None, most expensive |
| Spot | **up to ~90%** | None, but reclaimable | AWS can reclaim with 2-minute notice |
| Savings Plans (Compute) | up to ~66% | 1 or 3yr, $/hr commitment, flexible across instance family/region/compute type (EC2, Fargate, Lambda) | Underutilization risk if commitment sized wrong |
| Savings Plans (EC2 Instance) | up to ~72% | 1 or 3yr, locked to instance family in a region | Higher discount, less flexibility |
| Reserved Instances (Standard) | up to ~72% | 1 or 3yr | Least flexible; can modify AZ/size within family, not instance family itself |

[EC2 Pricing Guide 2026](https://www.usage.ai/blogs/aws/ec2/pricing-and-cost-optimization-guide/) — accessed 2026-08-01. The practical hierarchy for a steady-state fleet: Savings Plans first (flexibility to also cover Fargate/Lambda spend under the same commitment), Spot for anything interruption-tolerant, Reserved Instances only when you need the absolute highest discount and know the exact instance family won't change for the term.

### Placement groups, EBS-optimized, Nitro

- **Cluster placement group** — packs instances physically close for low-latency, high-throughput networking between them (HPC, tightly-coupled distributed training).
- **Spread placement group** — each instance on distinct underlying hardware, for small numbers of critical instances that must not share a failure domain.
- **Partition placement group** — groups of instances spread across logical partitions with isolated failure domains, used by distributed systems like HDFS/Cassandra that already have partition-aware replication.
- **EBS-optimized** — dedicated throughput to EBS separate from general network traffic; default and included at no extra cost on current-generation instance types, was an extra charge/opt-in on older generations.
- **Nitro** — the underlying hypervisor/hardware architecture on all current-generation instances, offloading virtualization overhead (networking, storage) to dedicated hardware, which is why current-gen instances get near-bare-metal performance and finer-grained instance sizes than the Xen-based predecessors.

### ECS vs EKS vs Fargate — the decision matrix

| Axis | ECS (any compute) | EKS |
|---|---|---|
| Control plane cost | $0 | ~$0.10/hr per cluster (~$73/mo) [ECS vs EKS vs Fargate 2026](https://tech-insider.org/ecs-vs-eks-vs-fargate-2026/) — accessed 2026-08-01 |
| Learning curve | Low — AWS-native task/service model | Steep — full Kubernetes API surface |
| Ecosystem | AWS-only tooling, smaller | Enormous — Helm, operators, the entire CNCF landscape |
| Multi-cloud portability | None, AWS-specific | High — same manifests largely run on any K8s |
| Cold start (Fargate) | Tens of seconds, generally faster than EKS Fargate | Tens of seconds, typically slightly slower due to kubelet/CNI overhead |
| Per-pod isolation | Task-level (similar granularity) | Pod-level, with richer network policy tooling (Cilium, Calico) available |
| Team fit | Small-to-mid teams, no existing K8s investment | Platform teams, multi-tenant internal platforms, K8s-native dependencies |

For the majority of new AWS-only projects in 2026, ECS on Fargate remains the pragmatic default: no control-plane fee, minimal ops, fast to stand up. Choose EKS deliberately for a concrete trigger, not by default — multi-cloud strategy, a tool that only ships as a Kubernetes operator, or a platform team already fluent in `kubectl` serving many internal tenants.

### Fargate's limits vs EC2 launch type

Fargate: fixed CPU/memory combinations only, Linux (and Windows, limited) containers only, **no GPU support at all**, no direct host access, no custom AMIs or kernel tuning. EC2 launch type: full instance-type flexibility including GPU families, custom AMIs, host-level tuning, but you own patching and capacity management. **If the workload needs a GPU, Fargate is not an option — EC2 launch type only**, on both ECS and EKS. [Fargate vs EC2 launch types](https://dev.to/aws-builders/amazon-ecs-vs-aws-fargate-5-most-important-differences-explained-1bab) — accessed 2026-08-01.

### AWS Batch and array jobs

Batch handles the "I have 50,000 independent, embarrassingly parallel units of work" problem without hand-building a queue-and-worker system: an **array job** can spawn up to a hard limit of **10,000 child jobs** from a single submission, each processing a slice of the work (commonly via an environment variable index into a dataset), with per-child retry handling and automatic scaling of the underlying compute environment (EC2, Spot, or Fargate). [AWS Batch array jobs](https://docs.aws.amazon.com/batch/latest/userguide/array_jobs.html) — accessed 2026-08-01. This is the right tool for Monte Carlo sweeps, parametric simulation, bulk file transforms — anything shaped like "same code, many independent inputs, no coordination between units" — and the wrong tool for anything needing inter-task communication or strict ordering, which belongs in Step Functions or a proper workflow engine instead.

### ASG, warm pools, lifecycle hooks

Auto Scaling Groups remain the EC2-launch-type scaling primitive underneath ECS/EKS node groups. **Warm pools** keep pre-initialized instances in a `Stopped` (cheap — only EBS storage cost while stopped) or `Running` state alongside the ASG, so a scale-out event can pull from the warm pool instead of booting cold, cutting scale-out latency from minutes to seconds for workloads with slow bootstrap (large AMI, heavy config management). **Lifecycle hooks** pause an instance in a `Pending:Wait` or `Terminating:Wait` state so custom automation (config pull, log flush, connection draining) can run before the instance is marked in-service or actually terminated — without a lifecycle hook, ASG considers an instance "ready" the moment EC2 reports it running, which is often before your application has actually finished bootstrapping.

### Spot interruption handling

AWS gives a **2-minute interruption notice** before reclaiming a Spot instance, available via instance metadata and EventBridge. Separately, a **rebalance recommendation** signal fires *earlier* — commonly cited as 10-20 minutes ahead in practice, though not guaranteed — when an instance is at *elevated risk* of interruption, giving more lead time to proactively move workload before the hard 2-minute notice arrives; the two signals aren't always both present with the same lead time. [EC2 spot interruption docs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-instance-termination-notices.html) — accessed 2026-08-01. Production handling means: an interruption handler (AWS's own `node-termination-handler` for Kubernetes, or a custom SQS-based listener) that drains connections and reschedules work within that window, and diversifying across multiple instance types/AZs in a Spot Fleet or ASG mixed-instances-policy so a single capacity pool's interruption doesn't take the whole fleet down at once.

---

## Build it from scratch

Minimal AWS Batch array job submission, the shape you'd sketch on a whiteboard for "run this transform over 5,000 files":

```python
# untested sketch
import boto3

batch = boto3.client("batch")

response = batch.submit_job(
    jobName="transform-batch",
    jobQueue="my-job-queue",
    jobDefinition="transform-job-def",
    arrayProperties={"size": 5000},   # spawns 5000 child jobs, indices 0..4999
)

# Inside the container, each child reads its own index:
# import os; idx = int(os.environ["AWS_BATCH_JOB_ARRAY_INDEX"])
# process(file_list[idx])
```

Three things this gets right that a hand-rolled SQS-worker version has to build itself: per-child retry without extra code, automatic compute-environment scaling to the array size, and a single job ARN that reports aggregate array status rather than tracking 5,000 individual queue messages by hand.

---

## How it's done in production

A typical AWS-only platform team runs: **ECS on Fargate** for stateless services with no GPU need, **EKS with EC2 (Karpenter-managed) node groups** for GPU inference workloads and anything needing Kubernetes-native tooling, **AWS Batch on Spot** for offline/batch ML preprocessing and parametric jobs, and **ASGs with warm pools** for the rare EC2-direct workload with slow bootstrap that isn't containerized at all.

| Symptom | Cause | Fix |
|---|---|---|
| ECS tasks stuck in `PENDING`, never reach `RUNNING` | No EC2 capacity matching the task definition's placement constraints, or Fargate hitting account vCPU quota | Check capacity provider strategy, request a quota increase, verify subnet has available IPs |
| EKS pod `CrashLoopBackOff` immediately on GPU nodes | Missing NVIDIA device plugin or GPU-enabled AMI, container doesn't see the GPU | Verify GPU-optimized AMI, device plugin DaemonSet deployed, `nvidia-smi` inside the container |
| Spot-backed ASG loses half its capacity simultaneously | Single instance type/AZ pool getting reclaimed together — a Spot capacity pool exhaustion event | Diversify instance types and AZs via mixed-instances-policy or Spot Fleet allocation strategy |
| Batch array job's compute environment never scales past a handful of running children | `maxvCpus` on the compute environment set too low for the array size × per-child vCPU need | Raise `maxvCpus` to cover the desired parallelism, not just the total workload |
| ASG scale-out takes 4+ minutes to serve traffic despite "fast" instance launch | No warm pool, slow bootstrap (config management, large AMI) happening cold every scale-out | Warm pool in `Stopped` state pre-initialized to the point just before traffic-serving |
| ECS Fargate service can't run a workload needing a specific GPU family | Fargate has zero GPU support | Move that specific workload to EC2 launch type (ECS or EKS), keep the rest on Fargate |

---

## Tradeoffs & when NOT to use it

- **Don't choose EKS by default.** Its control-plane cost and operational surface only pay for themselves against a concrete trigger — multi-cloud, a K8s-native tool dependency, or an existing platform team. Choosing it for resume value or because "everyone uses Kubernetes" is a real anti-pattern the interviewer has watched play out badly.
- **Don't use Fargate for GPU workloads** — it's not a matter of configuration, it's architecturally unsupported; EC2 launch type is the only path.
- **Don't use Spot for stateful, hard-to-checkpoint work without an interruption-handling strategy** — a database primary or a long single-threaded job with no checkpointing on Spot is asking for silent data loss or wasted compute on reclaim.
- **Don't use AWS Batch for workloads needing inter-task coordination** — array jobs assume independence; anything needing ordering or communication between units belongs in Step Functions or a real workflow engine.
- **Reserved Instances lock you into an instance family for the term** — in a fast-moving ML/inference environment where instance-family choices change with new hardware generations, Savings Plans' flexibility is usually worth the slightly narrower discount range.

---

## Interview questions

### Q1 — What's actually different between an orchestrator and a compute engine, using ECS/EKS/Fargate/EC2 as examples?
**Testing:** whether the candidate conflates two independent decisions into one.
**Answer:** ECS and EKS are orchestrators — they decide scheduling, placement, and service lifecycle. Fargate and EC2 are compute engines — they decide what physical/virtual capacity actually runs the containers. You can pair either orchestrator with either compute engine: ECS+Fargate, ECS+EC2, EKS+Fargate, EKS+EC2 are all valid combinations, and conflating "Fargate vs EKS" as if they're the same axis is the most common mistake.
**Follow-up trap:** *"So why do people talk about 'Fargate vs EKS' as if they're alternatives?"* — because the most common real-world comparison is ECS+Fargate (simple, serverless) versus EKS+EC2 (full control, full complexity), which conflates both axes changing at once; the cleaner comparison holds one axis fixed.

### Q2 — Decode `r7i.4xlarge` and explain what workload it's suited for.
**Testing:** basic fluency reading instance names, a quick warmup.
**Answer:** `r` = memory-optimized family, `7` = 7th generation, `i` = Intel processor, `4xlarge` = size tier. Suited for memory-bound workloads — in-memory caches, large in-memory databases, memory-heavy analytics — where vCPU count matters less than RAM per instance.
**Follow-up trap:** *"What would change if it were `r7g.4xlarge` instead?"* — `g` means Graviton (ARM) instead of Intel, typically better price/performance for workloads whose dependencies are ARM-compatible, at the cost of needing to verify any native binaries or compiled dependencies support ARM64.

### Q3 — Walk through the purchase-option discount hierarchy and when you'd combine them.
**Testing:** cost fluency beyond "spot is cheap."
**Answer:** On-demand is the baseline. Spot offers up to ~90% off but is reclaimable with a 2-minute notice. Compute Savings Plans give up to ~66% with maximum flexibility (covers EC2, Fargate, and Lambda spend under one commitment). EC2 Instance Savings Plans and Standard Reserved Instances both reach up to ~72% but lock to a specific instance family. A mature cost strategy layers them: Savings Plans covering the steady-state baseline across compute types, Spot absorbing interruption-tolerant burst/batch work, and Reserved Instances only for workloads with a long, certain instance-family commitment.
**Follow-up trap:** *"Why not just use Reserved Instances everywhere for the highest discount?"* — RIs lock you to an instance family for 1-3 years; in an environment where instance generations and ML-hardware choices change frequently, that inflexibility can cost more in forced suboptimal instance choice than the extra few percent of discount is worth.

### Q4 — A team wants to run a GPU-based inference service. Walk through the compute decision.
**Testing:** whether the GPU/Fargate gap is actually known, not assumed away.
**Answer:** Fargate is immediately eliminated regardless of orchestrator choice, since Fargate has no GPU support at all on either ECS or EKS. That leaves EC2 launch type with either ECS or EKS. If the team has no existing Kubernetes investment and doesn't need the broader ecosystem, ECS+EC2 with a GPU-family instance (p/g series) is simpler operationally. If they need Kubernetes-native GPU scheduling tools (like the NVIDIA GPU Operator, node feature discovery), EKS+EC2 is the better fit despite the added control-plane cost and complexity.
**Follow-up trap:** *"Could you use SageMaker instead and skip this decision entirely?"* — yes for many inference use cases, and it's worth naming as an alternative; SageMaker endpoints abstract the compute-orchestration question away entirely at the cost of some flexibility and potentially higher per-hour cost versus self-managed EC2/EKS at high sustained utilization.

### Q5 — Design a batch pipeline processing 20,000 independent video files. Why AWS Batch over a hand-rolled SQS worker fleet?
**Testing:** recognizing the right abstraction for embarrassingly parallel work.
**Answer:** An AWS Batch array job with array size up to the 10,000-per-job limit (splitting 20,000 files across two array jobs, or one job of 10,000 pairs of files per child) gives per-child retry handling, automatic compute-environment scaling matched to the array size, and a single job ARN for aggregate status tracking — all of which a hand-rolled SQS-plus-worker-fleet system has to build and maintain itself. Batch is purpose-built for "same code, many independent inputs, no coordination needed."
**Follow-up trap:** *"What if 5% of files depend on the output of a prior step?"* — that breaks the "embarrassingly parallel, no coordination" assumption Batch array jobs are built for; that dependency structure belongs in Step Functions orchestrating Batch jobs (or Lambda) as steps, not inside a single flat array job.

### Q6 — Explain warm pools and why they exist given ASGs already auto-scale.
**Testing:** the specific problem warm pools solve versus plain ASG scaling.
**Answer:** Plain ASG scale-out launches a cold instance from the AMI and runs the full bootstrap (OS boot, config management, application startup) synchronously with the traffic need, which for slow-bootstrapping workloads can take minutes — too slow for a sudden spike. A warm pool keeps instances pre-initialized in a `Stopped` (cheap, storage-only cost) or `Running` state alongside the ASG, so scale-out pulls a nearly-ready instance instead of booting cold, cutting that latency from minutes to seconds.
**Follow-up trap:** *"Why not just keep the ASG's minimum size higher instead of using a warm pool?"* — that keeps instances fully running and billed at compute rates continuously; a warm pool in `Stopped` state only incurs EBS storage cost while idle, capturing most of the latency benefit at a fraction of the cost.

### Q7 — What's the difference between a Spot interruption notice and a rebalance recommendation?
**Testing:** precision on the two distinct signals, a common point of confusion.
**Answer:** The interruption notice is a hard 2-minute warning before AWS actually reclaims the instance — fixed, always exactly that short window once it fires. The rebalance recommendation is a separate, earlier signal indicating *elevated risk* of interruption, commonly with more lead time in practice, meant to let you proactively move workload before the hard 2-minute notice arrives — but it's not guaranteed to always precede the interruption notice by a fixed amount, and sometimes both arrive together.
**Follow-up trap:** *"If you only handle the 2-minute interruption notice and ignore rebalance recommendations, what do you lose?"* — you lose the ability to proactively rebalance before the last-minute scramble; Capacity Rebalancing in ASG/EC2 Fleet specifically listens for rebalance recommendations to launch replacement capacity ahead of the hard interruption, which a system reacting only to the 2-minute notice can't do as gracefully.

### Q8 — Your ECS Fargate tasks are stuck in PENDING and never transition to RUNNING. Debug it.
**Testing:** the failure-mode table applied live.
**Answer:** Check the account's Fargate vCPU/memory quota for the region first — a common silent cap. Then check subnet IP availability, since each Fargate task needs an ENI and IP from the subnet; an exhausted subnet blocks scheduling identically to a quota issue. Then verify the capacity provider strategy and any placement constraints aren't impossible to satisfy simultaneously (e.g., conflicting AZ or capacity provider requirements).
**Follow-up trap:** *"The quota looks fine and the subnet has plenty of IPs. What else?"* — check the task's IAM execution role for permission to pull the container image (especially from a private ECR repo or a cross-account registry) and check security group rules blocking the ECS agent's required outbound calls; a task that can't authenticate to pull its image also sits in PENDING with a non-obvious error.

### Q9 — When would you deliberately choose ECS over EKS for a platform team that already knows Kubernetes well?
**Testing:** whether "the team already knows K8s" is treated as automatically decisive, which it shouldn't be.
**Answer:** If the workload is a small number of straightforward services with no need for the broader Kubernetes ecosystem (custom operators, service mesh, multi-cloud portability), the team's existing K8s fluency doesn't offset ECS's lower operational surface and zero control-plane cost — familiarity with a tool isn't the same as the tool being the right fit for this specific workload's actual requirements. The decision should still be driven by whether a concrete EKS-specific need exists, not by team background alone.
**Follow-up trap:** *"Isn't that wasting the team's expertise?"* — expertise is still useful for evaluating the tradeoff correctly and for the (likely) other services in the org that do need EKS; it doesn't obligate using EKS everywhere, and a senior engineer should push back on sunk-cost-style tool selection.

### Q10 — Design the compute layer for a service with unpredictable, spiky traffic that occasionally needs to burst 20x for a few minutes at a time.
**Testing:** synthesizing purchase options, scaling primitives, and orchestrator choice into one coherent answer.
**Answer:** ECS on Fargate (or EKS+Fargate if already on Kubernetes) removes node-capacity planning entirely for the baseline and absorbs the burst without pre-provisioning EC2 capacity, at the cost of paying Fargate's per-task rate rather than a Savings-Plan-discounted EC2 rate. If cost at the burst multiplier matters more than operational simplicity, an EC2-backed ASG with a warm pool sized to the typical burst plus Capacity Rebalancing-aware Spot for the least latency-sensitive portion of that burst traffic is the alternative, accepting more operational surface for lower steady-state cost.
**Follow-up trap:** *"How do you decide between those two designs without just guessing?"* — model the actual cost at expected burst frequency/duration under each option, including Fargate's premium over EC2 Savings-Plan pricing versus the warm pool's storage cost and the operational cost of maintaining ASG scaling policies; for infrequent, short bursts Fargate usually wins on total cost of ownership once engineering time is priced in, and the crossover point is calculable, not assumed.

---

## Red flags that fail you

- Treating "Fargate vs EKS" as a single axis instead of two independent decisions (orchestrator vs compute engine).
- Recommending EKS by default without naming a concrete trigger for the added complexity.
- Not knowing Fargate has zero GPU support.
- Confusing the Spot 2-minute interruption notice with the (separate, earlier) rebalance recommendation.
- Recommending AWS Batch for workloads needing inter-task coordination.
- Not knowing Reserved Instances lock to an instance family while Savings Plans don't.
- Sizing a warm pool or ASG without referencing actual scale-out latency requirements.

---

## Cheat card

```
TWO AXES: orchestrator (ECS/EKS = scheduling) x compute engine (Fargate/EC2 = where it runs)
  Fargate: GPU = NO, ever, on either ECS or EKS. GPU work -> EC2 launch type only.

EC2 NAME: [family][gen][options].[size]  e.g. c6i.2xlarge = compute,gen6,Intel,2xl
  options: g=Graviton(ARM) n=enhanced networking d=local NVMe e=extra mem/storage

PURCHASE DISCOUNTS (vs on-demand):
  Spot                    up to ~90%   reclaimable, 2-min notice
  Compute Savings Plan    up to ~66%   most flexible (EC2+Fargate+Lambda)
  EC2 Instance Sav. Plan  up to ~72%   locked to instance family
  Reserved Instance       up to ~72%   locked to instance family, least flexible

ECS vs EKS:
  ECS control plane: $0        EKS control plane: ~$0.10/hr (~$73/mo)
  ECS: low learning curve, AWS-only tooling, faster Fargate cold start
  EKS: steep curve, huge ecosystem, multi-cloud portable
  Default for new AWS-only projects: ECS+Fargate. EKS needs a concrete trigger.

BATCH: array job max size = 10,000 children/job. Embarrassingly parallel ONLY
  (no inter-task coordination -> use Step Functions instead)

ASG:
  Warm pool: pre-init instances, Stopped state = storage-cost only, cuts scale-out to seconds
  Lifecycle hooks: Pending:Wait / Terminating:Wait -- run custom code before in-service/terminate

SPOT INTERRUPTION:
  Hard interruption notice: 2 minutes, fixed, via metadata + EventBridge
  Rebalance recommendation: earlier, elevated-risk signal, NOT guaranteed lead time
  Handle: node-termination-handler / SQS listener + diversify instance types & AZs

NITRO: current-gen hypervisor, near-bare-metal perf, EBS-optimized default on current gen.
```

## Sources

- [Amazon EC2 instance type naming conventions — AWS docs](https://docs.aws.amazon.com/ec2/latest/instancetypes/instance-type-names.html) — accessed 2026-08-01
- [Amazon EC2 Pricing 2026 Guide — Usage.ai](https://www.usage.ai/blogs/aws/ec2/pricing-and-cost-optimization-guide/) — accessed 2026-08-01
- [ECS vs EKS vs Fargate: control plane cost — tech-insider.org](https://tech-insider.org/ecs-vs-eks-vs-fargate-2026/) — accessed 2026-08-01
- [Amazon ECS vs AWS Fargate launch types — dev.to](https://dev.to/aws-builders/amazon-ecs-vs-aws-fargate-5-most-important-differences-explained-1bab) — accessed 2026-08-01
- [AWS Batch array jobs — AWS docs](https://docs.aws.amazon.com/batch/latest/userguide/array_jobs.html) — accessed 2026-08-01
- [Prepare for Spot Instance interruptions — AWS docs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/prepare-for-interruptions.html) — accessed 2026-08-01
- [EC2 instance rebalance recommendations — AWS docs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/rebalance-recommendations.html) — accessed 2026-08-01
- [Decrease latency for applications with long boot times using warm pools — AWS docs](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-warm-pools.html) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created

## The 30-second version

Compute choice on AWS is two independent decisions, not one: which orchestrator (ECS's simpler AWS-native model or EKS's full Kubernetes API), and which compute engine underneath it (Fargate's serverless, no-node-management model or EC2's full control and GPU access). Fargate has zero GPU support on either orchestrator, full stop — that alone eliminates it for inference or training workloads. ECS on Fargate is the pragmatic default for new AWS-only projects because EKS's control-plane cost and operational surface only pay for themselves against a concrete trigger like multi-cloud strategy or an existing Kubernetes-native platform team. Purchase options layer: Savings Plans for flexible steady-state discount, Spot for interruption-tolerant burst work at up to 90% off with a 2-minute reclaim notice, Reserved Instances only when an instance family commitment is genuinely stable. AWS Batch array jobs handle embarrassingly parallel work up to 10,000 children per job; anything needing coordination between units belongs in Step Functions instead.
