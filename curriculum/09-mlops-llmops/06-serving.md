# SageMaker, Bedrock, Vertex, KServe, Ray Serve, BentoML

> **Track:** T09 MLOps / LLMOps · **Time:** 2.0h · **Prereqs:** T05-inference-serving, T09-bedrock-vs-sagemaker · **Updated:** 2026-08-05
> **Module id:** `T09-serving` · **Tags:** serving,kubernetes,cost,critical

## The 30-second version

Every one of these platforms is a control plane wrapped around the same three or four inference engines, so the choice is never "which serves faster" but "which control plane's failure modes and markup do I want." SageMaker Real-Time endpoints charge a flat ~25% over the equivalent EC2 on-demand rate (ml.g5.24xlarge $10.18/hr vs g5.24xlarge $8.144/hr) and forbid spot, which is roughly a 2.6x penalty against the spot price you could be paying; you buy managed rollout, IAM, and CloudWatch integration with that. KServe is the right answer when you already run Kubernetes and want scale-to-zero on GPU plus prefix-cache-aware routing, and its `LLMInferenceService` CRD (production-ready since v0.17) is now the serious path while the old `InferenceService` predictor spec is the classical-ML path. Ray Serve earns its keep only when a request genuinely fans out across heterogeneous replicas with different hardware and scaling curves, because everything simpler than that is a worse deal than a plain Deployment. BentoML solves packaging, not scale, and its OSS release cadence has been quiet since the Modular acquisition, so treat it as a build tool rather than a platform bet. Underneath all six, the thing actually generating tokens is vLLM or SGLang, and almost every performance number you care about is a property of that layer, not of the box it sits in.

## Why this gets asked

The interviewer has watched a team pick a serving platform for a reason that turned out to be irrelevant. The two canonical scars: someone enabled SageMaker scale-to-zero to save money and discovered that the scale-out trigger is a CloudWatch alarm on `NoCapacityInvocationFailures`, meaning production requests must fail before AWS starts an instance, and then several minutes of provisioning pass while they keep failing. Or someone adopted Ray Serve for "model composition" on a service that was one model behind one endpoint, and inherited a Ray head node, a GCS failure domain, and an autoscaler with a 600-second default downscale delay in exchange for nothing.

They are probing whether you understand that a serving platform is a scheduling and lifecycle policy, and that its cost is measured in cold-start seconds, markup percent, and new failure domains. At principal level the tell is whether you can name what each platform actually does *differently* at the pod/instance level, rather than repeating the feature matrix from a vendor comparison page.

---

## Lineage: past → present → future

**What came before.** The original serving story was per-framework model servers: TensorFlow Serving (2016), TorchServe (2020, jointly by AWS and Meta), and NVIDIA Triton. Each solved "load a graph, expose gRPC/HTTP, batch a bit," and each was a separate operational animal with its own config format. The pain that killed the pattern was heterogeneity: a platform team running scikit-learn, XGBoost, PyTorch, and a Hugging Face encoder ended up with four servers, four autoscaling stories, four metrics namespaces, and no shared rollout mechanism. KFServing (2019, under Kubeflow) was the direct response, renamed KServe in 2021 when it left Kubeflow: one `InferenceService` CRD, one v1/v2 inference protocol, framework-specific runtimes swapped underneath. The LLM era then killed the assumptions of that generation outright. TensorFlow Serving and TorchServe assume a request is stateless and short; a decode loop is neither, and a model server with no KV cache and no continuous batching leaves 5-10x throughput on the floor. TorchServe is now formally dead: the `pytorch/serve` repository is archived, the README states the project "is no longer actively maintained," with no planned bug fixes or security patches, and the last push was 2025-08-06 [pytorch/serve README](https://github.com/pytorch/serve) — accessed 2026-08-05. If a candidate proposes TorchServe in 2026, that alone is disqualifying.

**Where it stands now.** The consensus that has actually settled: vLLM and SGLang won the engine layer, and everything above them is scheduling. KServe ships vLLM as a first-class runtime and shipped vLLM v0.19.0 inside its own v0.18 release [KServe v0.18 release notes](https://kserve.github.io/website/blog/kserve-0.18-release) — accessed 2026-08-05. SageMaker's LMI containers wrap vLLM. Ray Serve ships `ray.serve.llm` which is a vLLM wrapper. The disagreements that are genuinely live: (1) **Whether the Kubernetes-native stack is worth its complexity for anything under ~10 GPUs.** The KServe + llm-d + Gateway API Inference Extension stack is real and delivers measured wins (Tesla and Red Hat report 3x output tokens/s and 2x lower TTFT after enabling prefix-cache-aware routing, serving Llama 3.1 70B on 4x MI300X with `tensor-parallel-size=4`, `gpu-memory-utilization=0.90`, `--max-model-len=65536` [Production-Grade LLM Inference at Scale with KServe, llm-d, and vLLM](https://kserve.github.io/website/blog/production-grade-llm-inference-kserve-llm-d-vllm) — accessed 2026-08-05), but that is a fleet with hundreds of models. At three models on two nodes, a Deployment plus a Service beats it. (2) **Whether multi-model density is a solved problem or a dead idea for LLMs.** ModelMesh, KServe's answer to hosting thousands of small models with intelligent load/unload, is over: both `kserve/modelmesh` and `kserve/modelmesh-serving` were archived on 2026-04-14, their last release was v0.12.0 in July 2024, and the `admin-guide/modelmesh` documentation page still exists for docs versions 0.16 and 0.17 but 404s on 0.18 and 0.19. The KServe landing page nonetheless still advertises "high scalability, density packing and intelligent routing using ModelMesh," which is a trap for anyone who reads marketing pages instead of release history. (3) **Whether managed scale-to-zero is usable.** SageMaker's implementation triggers on failed invocations; KServe's Knative path costs ~10s+ of cold start; nobody has made this transparent for a 140GB model.

**Where it's heading.** High confidence: routing becomes cache-aware everywhere. Prefix-cache-aware and session-sticky routing is the single highest-leverage change available at the control plane, and it is showing up simultaneously in KServe via the Gateway API Inference Extension endpoint picker, and in Ray Serve via `ConsistentHashRouter` and `CapacityQueueRouter`, both new in Ray 2.56.0 [Ray 2.56.0 release notes](https://github.com/ray-project/ray/releases/tag/ray-2.56.0) — accessed 2026-08-05. Round-robin in front of vLLM is going to look as dated as static batching does now. High confidence: disaggregated prefill/decode moves from research to default. llm-d exists specifically to schedule it, KServe integrates llm-d v0.6, and the economics are compelling because prefill is compute-bound and decode is bandwidth-bound, so putting them on the same GPU wastes one of the two. Medium confidence: the Ray dependency drops out of multi-node inference entirely. KServe v0.18 already added multi-node without Ray by using vLLM's `mp` distributed executor backend, switched via a `multinode/executor-backend` annotation, with node count derived from pipeline parallelism and GPUs-per-node from tensor parallelism. Speculative: managed endpoints converge on per-token billing for open-weight models too, collapsing the SageMaker-vs-Bedrock distinction for anything in a model catalog, which would make self-hosting a decision about latency control and model choice rather than cost.

---

## Mental model

Every serving platform is three layers. Interviewers who have run this in production are asking about layer 2, and candidates keep answering about layer 3.

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │ LAYER 3  PACKAGING            what goes in the image                 │
 │          BentoML · Docker · SageMaker model.tar.gz · ServingRuntime  │
 │          "how do weights + code + deps become one artifact"          │
 └──────────────────────────────────────────────────────────────────────┘
                                    │
 ┌──────────────────────────────────────────────────────────────────────┐
 │ LAYER 2  CONTROL PLANE        <-- the interview lives here           │
 │          SageMaker Endpoint · KServe InferenceService/LLMISVC ·      │
 │          Ray Serve Deployment · Vertex Endpoint                      │
 │                                                                      │
 │   decides:  how many replicas       (autoscaler + metric + window)   │
 │             which replica gets it   (round-robin? prefix-aware?)     │
 │             what happens at zero    (cold start path & who fails)    │
 │             how a rollout happens   (canary? blue/green? in-place?)  │
 │             where the failure domain boundaries are                  │
 └──────────────────────────────────────────────────────────────────────┘
                                    │
 ┌──────────────────────────────────────────────────────────────────────┐
 │ LAYER 1  ENGINE               vLLM · SGLang · TensorRT-LLM           │
 │          PagedAttention, continuous batching, prefix cache           │
 │          ~every throughput/latency number you quote comes from here  │
 └──────────────────────────────────────────────────────────────────────┘
```

The corollary that catches people: **swapping layer 2 rarely changes your p50.** If you move from SageMaker+vLLM to KServe+vLLM, your token throughput is identical, because it is the same engine on the same GPU. What changes is your bill, your cold-start behaviour, your routing quality, and the set of things that can page you at 3am.

The second model, for the cold-start question specifically. Scale-to-zero is not one number, it is a chain, and the platforms differ in *which link they make you own*:

```
 request arrives at a scaled-to-zero service
   │
   ├─ (a) DETECT       who notices there is no capacity?
   │        KServe/Knative: activator buffers the request      ~ms
   │        SageMaker:      CloudWatch alarm on FAILED calls   ~60s + alarm eval
   │        Ray Serve:      router queues, autoscaler polls    ~10s metric interval
   │
   ├─ (b) SCHEDULE     get a node with a GPU
   │        already-warm node in pool                          ~0s
   │        Karpenter/ASG must launch a GPU instance           ~90-180s
   │
   ├─ (c) PULL IMAGE   vLLM CUDA images are 8-15 GB
   │        cached on node                                     ~0s
   │        cold pull                                          ~60-200s
   │
   ├─ (d) FETCH WEIGHTS  8B fp16 = 16 GB · 70B fp16 = 140 GB
   │        local NVMe / LocalModelCache                       ~10-30s
   │        S3 → EBS at ~1 GB/s                                ~20s / 140s
   │
   └─ (e) LOAD + WARM   CUDA graph capture, KV pool alloc      ~20-90s
                                                     ─────────────────
   realistic cold path, 8B, warm node, cached image:      ~30-60s
   realistic cold path, 70B, cold node, cold image:      ~8-15 min
```

Anyone who says "scale-to-zero, so it's free when idle" without pricing link (b) through (e) has not run it.

---

## How it actually works

### The managed markup, measured

This is the number to have memorised, because it converts a vague "managed is more expensive" into a defensible position. Same silicon, three purchase paths, us-east-1:

| Purchase path | Instance | $/hr | Ratio |
|---|---|---|---|
| EC2 on-demand | `g5.24xlarge` (4x A10G, 96 GB VRAM) | $8.144 | 1.00x |
| EC2 spot | `g5.24xlarge` | $3.955 | 0.49x |
| SageMaker Real-Time | `ml.g5.24xlarge` | $10.18 | 1.25x |

And the small end, which reproduces the same ratio:

| Purchase path | Instance | $/hr | Ratio |
|---|---|---|---|
| EC2 on-demand | `g5.2xlarge` (1x A10G, 24 GB) | $1.212 | 1.00x |
| EC2 spot | `g5.2xlarge` | $0.595 | 0.49x |
| SageMaker Real-Time | `ml.g5.2xlarge` | $1.52 | 1.25x |

EC2 rates from [ec2.shop pricing API](https://ec2.shop) — accessed 2026-08-05; SageMaker hosting rates from [Amazon SageMaker AI Pricing](https://aws.amazon.com/sagemaker/ai/pricing/) — accessed 2026-08-05. Larger reference points for sizing a 70B: `p4d.24xlarge` (8x A100 40GB) $32.77/hr on-demand, $13.07 spot; `p5.48xlarge` (8x H100) $98.32/hr on-demand, $57.76 spot.

So SageMaker Real-Time endpoints run **a consistent ~25% premium over EC2 on-demand**, and because SageMaker Real-Time does not offer spot for inference endpoints, the honest comparison against a spot-tolerant self-hosted fleet is closer to **2.6x**. Against that you get: managed rollout with automatic variant traffic shifting, IAM-native invoke authorization, endpoint-level CloudWatch metrics, and no cluster to patch. On EKS you pay $0.10/cluster/hour for the control plane on a supported Kubernetes version, rising to $0.60/cluster/hour once the version enters extended support [Amazon EKS Pricing](https://aws.amazon.com/eks/pricing/) — accessed 2026-08-05, which is noise next to a single GPU node and is not the reason anyone picks or avoids EKS.

The arithmetic that follows: at one `g5.24xlarge`-equivalent running 24/7, SageMaker costs $10.18 × 730 = $7,431/month versus $5,945 on EC2 on-demand, a $1,486/month delta. One node is not worth a platform migration. At 20 nodes it is $29,700/month, which pays for an engineer, and the calculus flips.

### SageMaker: what "scale to zero" actually does

This is the part almost nobody gets right, and it is a genuinely good interview weapon.

Real-Time endpoints can scale to zero instances, but **only if the endpoint hosts inference components** and you set `ManagedInstanceScaling.MinInstanceCount = 0` on the production variant. Then, per model:

```bash
# scale IN to zero: register the inference component as a scalable target
aws application-autoscaling register-scalable-target \
  --service-namespace sagemaker \
  --resource-id inference-component/my-ic \
  --scalable-dimension sagemaker:inference-component:DesiredCopyCount \
  --min-capacity 0 --max-capacity 8

# target-tracking on invocations-per-copy handles 1..n
# {"PredefinedMetricSpecification":
#    {"PredefinedMetricType":"SageMakerInferenceComponentInvocationsPerCopy"},
#  "TargetValue":1, "ScaleInCooldown":300, "ScaleOutCooldown":300}
```

Getting back **out** of zero is a separate mechanism, and here is the sharp edge:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name ic-step-scaling-alarm \
  --metric-name NoCapacityInvocationFailures \
  --namespace AWS/SageMaker \
  --dimensions "Name=InferenceComponentName,Value=my-ic" \
  --statistic Sum --period 60 --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 --datapoints-to-alarm 1 \
  --alarm-actions <step-scaling-policy-arn>
```

Read the metric name again: `NoCapacityInvocationFailures`. **The trigger to scale out from zero is a counter of requests that already failed.** AWS's own documentation states it plainly: "the provisioning process takes several minutes. During that time, any attempts to invoke the endpoint will produce an error" [Scale an endpoint to zero instances](https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling-zero-instances.html) — accessed 2026-08-05.

So the real cold path is: request fails → up to 60s of CloudWatch period → alarm evaluates → step scaling policy fires → instance provisions (minutes) → container starts → weights download → engine warms. Every request in that window returns an error, not a slow success. There is no activator buffering the request the way Knative does. If you put this in front of a user-facing endpoint without a client-side retry-with-backoff budget of several minutes, you have built an outage generator. It is correct for internal batch-ish or dev endpoints, and wrong for anything with an SLO.

### SageMaker Serverless Inference is not for LLMs, and the reason is one line

The documented feature exclusions for Serverless Inference are: "GPUs, AWS marketplace model packages, private Docker registries, Multi-Model Endpoints, VPC configuration, network isolation, data capture, multiple production variants, Model Monitor, and inference pipelines" [Serverless Inference](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html) — accessed 2026-08-05.

**No GPUs.** That ends the conversation for transformer inference above toy size. The rest of the envelope: RAM configurable in 1024 MB steps from 1024 MB to 6144 MB, max container image 10 GB, 5 GB ephemeral storage, max concurrency 200 per endpoint against a shared per-region account quota. It is a good fit for a scikit-learn or small ONNX model with bursty traffic, and only that.

The pricing detail worth knowing, because it produces a clean derived threshold. On-demand serverless bills $0.00004/sec of inference duration (at the 2 GB configuration) plus $0.016/GB data processed. Provisioned Concurrency bills $0.000010/sec per PC unit as a standing charge, but drops the duration rate to $0.000023/sec [Amazon SageMaker AI Pricing](https://aws.amazon.com/sagemaker/ai/pricing/) — accessed 2026-08-05. Set utilization `u` = fraction of wall-clock a PC unit is busy:

```
cost_PC(u)        = 0.000010 + 0.000023·u   per second
cost_ondemand(u)  =            0.000040·u   per second
break-even: 0.000010 = (0.000040 - 0.000023)·u = 0.000017·u
            u = 0.588
```

**Provisioned Concurrency pays for itself above ~59% utilization** and is a pure loss below it. Nobody quotes that number; deriving it live is a strong signal.

### Multi-model endpoints: what they were for, and why LLMs broke them

SageMaker Multi-Model Endpoints (MME) put N models behind one endpoint on one fleet, loading each into container memory on first invocation and evicting under memory pressure; evicted models stay on the instance's EBS volume so a re-load skips the S3 download. It works on CPU and GPU instances. The economics are compelling for the long tail: 500 per-tenant XGBoost models at 50 MB each fit comfortably on one `ml.m5.2xlarge` at $0.46/hr instead of 500 endpoints.

The load-bearing assumption is **that a model load is cheap relative to a request**. For a 50 MB tree ensemble, load is ~100ms and an invocation is ~5ms, so a 20:1 penalty on a cache miss is survivable. For an 8B fp16 LLM the weights are 16 GB, the load is tens of seconds, and you cannot fit two of them plus their KV pools on a 24 GB A10G at all. Density packing and KV caching are in direct competition for the same VRAM: vLLM wants `gpu_memory_utilization=0.90` precisely so the KV pool is large, and a multi-model scheduler wants that VRAM free to swap. That is why the correct multi-model answer for LLMs is not MME, it is **multi-LoRA**: one base model resident, adapters swapped per request, which vLLM supports natively and which KServe now auto-detects (its v0.20 line auto-enables a `lora-affinity-scorer` when LoRA adapters are present). The generalisation to state in an interview: *multi-model density works when the models are small relative to the accelerator; for LLMs you keep one base model resident and vary the adapter, not the model.*

The same reasoning killed ModelMesh, which was the Kubernetes-side answer to the identical problem: intelligent load/unload of thousands of models across a fleet, an IBM contribution to KServe. It is archived (both repositories, 2026-04-14), its last release was v0.12.0 in July 2024, and its documentation is gone from KServe docs 0.18 and 0.19. If you say "ModelMesh" in an interview as a current recommendation, you have dated yourself by two years.

### KServe: two CRDs, and which one you should actually be using

KServe is at v0.19.0 (released 2026-06-14) with v0.20.0-rc1 cut 2026-08-03 [kserve/kserve releases](https://github.com/kserve/kserve/releases) — accessed 2026-08-05, and became a CNCF incubating project in November 2025.

**`InferenceService` (v1beta1)** is the classical-ML CRD, and the one every tutorial shows:

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: flowers-sample
spec:
  predictor:
    scaleTarget: 1
    scaleMetric: concurrency      # or qps, cpu, memory
    minReplicas: 0                # 0 = scale to zero; DEFAULT IS 1
    containerConcurrency: 10      # HARD limit; surplus requests queue
    model:
      modelFormat: {name: tensorflow}
      storageUri: "gs://kfserving-examples/models/tensorflow/flowers"
```

Three things here are load-bearing and routinely missed:

- **`minReplicas` defaults to 1.** You do not get scale-to-zero unless you ask, which is the right default and the opposite of what people assume.
- **`scaleTarget` is a soft limit; `containerConcurrency` is a hard one.** `autoscaling.knative.dev/target` is advisory: a burst can and will exceed it. `containerConcurrency` is enforced, and surplus requests buffer rather than being dispatched.
- **The autoscaler class depends on the deployment mode, and they are mutually exclusive.** Knative Pod Autoscaler (KPA) works *only* in Knative deployment mode. KEDA works *only* in Raw/Standard deployment mode. HPA works in Raw. Choosing "Standard" deployment mode to avoid the Knative dependency silently forfeits KPA's concurrency-based scaling and the activator that buffers cold-start requests [KServe autoscaling docs](https://kserve.github.io/website/docs/model-serving/predictive-inference/autoscaling/kpa-autoscaler) — accessed 2026-08-05.

KPA's control loop, in numbers you should know: it averages concurrency over a **60-second stable window**, plus a **6-second panic window**; if the panic window sees **2x the target concurrency** it enters panic mode and scales on the short window; it leaves panic mode after **60 seconds** of the panic condition not holding. KServe's own docs measure ~10s of cold start in their trivial TensorFlow example just to spawn the pod and pull the model, "longer if the image is not cached on the node."

**`LLMInferenceService` (v1alpha2)** is the CRD that matters for anything generative. It went production-ready in KServe v0.17 and is where all the current investment goes:

```yaml
apiVersion: serving.kserve.io/v1alpha2
kind: LLMInferenceService
metadata:
  name: llama3-70b-autoscaled
spec:
  model:
    uri: hf://meta-llama/Llama-3.1-70B-Instruct
    name: meta-llama--Llama-3.1-70B-Instruct
  parallelism:
    tensor: 4
    data: 8
    dataLocal: 4
  scaling:
    minReplicas: 1
    maxReplicas: 4
    wva: {variantCost: "15.0"}          # Workload Variant Autoscaler
    keda:
      pollingInterval: 30
      cooldownPeriod: 300
      idleReplicaCount: 0               # this is your scale-to-zero
  template:
    containers: [{name: vllm, resources: {limits: {nvidia.com/gpu: "4"}}}]
  worker:
    containers: [{name: vllm, resources: {limits: {nvidia.com/gpu: "4"}}}]
  router:
    gateway: {managed: {}}
    route: {httpRoute: {}}
    scheduler: {pool: {}}
```

What this buys that a Deployment does not: the `router.scheduler.pool` block wires an `InferencePool` and an endpoint picker (EPP) from the Gateway API Inference Extension, which is what performs **prefix-cache-aware routing**: sending a request to the vLLM replica that already holds its prompt prefix in KV cache rather than round-robining it. That is the 3x/2x result cited earlier. It also gives you multi-node inference as a unit: since v0.18 the autoscaling target can be a `LeaderWorkerSet`, so a replica spanning 4 nodes scales as one group instead of as 4 independent pods, and multi-node no longer requires a Ray head node because vLLM's `mp` distributed executor backend can be selected with the `multinode/executor-backend` annotation. `LocalModelCache` (cluster-scoped) and `LocalModelNamespaceCache` (namespace-scoped, new in v0.18) pre-stage weights on node-local disk, which is the single most effective cold-start fix available: it removes link (d) from the chain above.

### Ray Serve: the deployment graph is not what you remember

If your mental model of Ray Serve composition is `DAGDriver`, `InputNode`, and `serve.build`, it is stale. That DSL is gone. Composition in current Ray Serve is plain Python: you `.bind()` deployments into each other's constructors, Ray converts the arguments into `DeploymentHandle` objects, and you call methods on them with `.remote()` and `await` the `DeploymentResponse` [Deploy Compositions of Models](https://docs.ray.io/en/latest/serve/model_composition.html) — accessed 2026-08-05.

```python
# untested sketch -- structure is verbatim from Ray 2.56 docs
from ray import serve
from ray.serve.handle import DeploymentHandle

@serve.deployment(ray_actor_options={"num_gpus": 1})
class Reranker:
    def score(self, q: str, docs: list[str]) -> list[float]: ...

@serve.deployment(ray_actor_options={"num_cpus": 2})
class Retriever:
    def search(self, q: str) -> list[str]: ...

@serve.deployment
class Pipeline:
    def __init__(self, retriever: DeploymentHandle, reranker: DeploymentHandle):
        self.retriever, self.reranker = retriever, reranker

    async def __call__(self, http_request):
        q = (await http_request.json())["q"]
        docs = await self.retriever.search.remote(q)       # CPU pool
        scores = await self.reranker.score.remote(q, docs) # GPU pool
        return sorted(zip(docs, scores), key=lambda t: -t[1])[:5]

app = Pipeline.bind(Retriever.bind(), Reranker.bind())
```

The reason this is more than syntactic sugar: `Retriever` and `Reranker` are **independently scaled processes on independently chosen hardware**. The retriever scales on CPU and the reranker on GPU, and Ray schedules them on different node types. Expressing that with plain Kubernetes means two Deployments, two Services, two HPAs, and an HTTP hop with its own serialization cost; Ray gives you one deployable app with in-process-typed calls over its object store. That is the *only* thing Ray Serve is uniquely good at. Every Ray Serve adoption for a single-model endpoint is a mistake.

The defaults you must know, because they are unintuitive and two of them changed:

| Parameter | Default | Note |
|---|---|---|
| `num_replicas` | 1 | or `"auto"` for autoscaling |
| `target_ongoing_requests` | 2 | was 1.0 before Ray 2.32.0 |
| `max_ongoing_requests` | 5 | **was 100 before Ray 2.32.0** |
| `min_replicas` / `max_replicas` | 1 / 1 | set `min_replicas=0` for scale-to-zero |
| `upscale_delay_s` | 30 | |
| `downscale_delay_s` | 600 | also governs the 1→0 transition |
| `metrics_interval_s` | 10 | how often replicas report |
| `look_back_period_s` | 30 | averaging window |
| `max_queued_requests` | -1 (unbounded) | on limit: `BackPressureError` / HTTP 503 |
| `health_check_period_s` / `_timeout_s` | 10 / 30 | |
| `graceful_shutdown_wait_loop_s` / `_timeout_s` | 2 / 20 | |

Source: [Ray Serve autoscaling guide](https://docs.ray.io/en/latest/serve/advanced-guides/advanced-autoscaling.html) and [Configure Ray Serve deployments](https://docs.ray.io/en/latest/serve/configure-serve-deployment.html) — accessed 2026-08-05.

Two traps live in that table. The `max_ongoing_requests` change from 100 to 5 in Ray 2.32.0 is a 20x reduction in per-replica queue depth: an upgrade across that boundary can turn a working service into one shedding 503s under the same traffic, and the symptom is `BackPressureError` in caller logs, not a latency regression. And `downscale_delay_s=600` combined with `max_queued_requests=-1` means the default configuration will happily hold GPU replicas for ten minutes after traffic stops while queueing an unbounded number of requests in the meantime. Ray 2.56.0 is current (2026-07-17) and adds `ConsistentHashRouter` for session-sticky routing via consistent hashing, `CapacityQueueRouter` for token-based routing, and an experimental HAProxy ingress path behind `RAY_SERVE_EXPERIMENTAL_PIP_HAPROXY`.

### BentoML: a build tool that is honest about being a build tool

BentoML's current API (1.4.x) is a decorator over a class, with the container spec inline rather than in a separate `bentofile.yaml`:

```python
import bentoml

@bentoml.service(
    image=bentoml.images.Image(python_version="3.11").python_packages("torch", "transformers"),
    resources={"gpu": 1},
    traffic={"timeout": 600},
    workers=4,
)
class Summarization:
    def __init__(self) -> None:
        from transformers import pipeline
        self.pipeline = pipeline("summarization", device="cuda")

    @bentoml.api(batchable=True)
    def summarize(self, texts: list[str]) -> list[str]:
        return [r["summary_text"] for r in self.pipeline(texts)]
```

`bentoml serve` runs it locally on port 3000; `bentoml build` produces a **Bento**, which is a versioned directory containing code, the resolved dependency set, model references, and the service spec; `bentoml containerize summarization:latest` turns the Bento into an OCI image [bentoml/BentoML README](https://github.com/bentoml/BentoML) — accessed 2026-08-05. The genuinely useful bits are `batchable=True`, which turns on adaptive server-side batching without you writing a batching loop, and the fact that the image spec is code, so dependency drift between local and deployed is caught at build time rather than at 2am.

The thing to say out loud in an interview: **BentoML competes with your Dockerfile, not with KServe.** A Bento is an artifact; it still needs something to schedule it. That something is BentoCloud (their commercial platform), or Kubernetes, or a SageMaker endpoint running the containerized Bento. Picking BentoML does not answer the autoscaling, routing, or rollout question at all.

The governance fact that belongs in a 2026 selection decision: **BentoML was acquired by Modular.** The BentoML README's community forum link now points at `forum.modular.com`, which hosts a "BentoML + Modular: Acquisition Roundup & Resources" thread dated 2026-03-01, and the last OSS release is v1.4.39 on 2026-05-07, roughly three months of quiet as of this writing [forum.modular.com BentoML category](https://forum.modular.com/c/bento/31) — accessed 2026-08-05. That is not a reason to rip it out; it is a reason not to build a platform strategy on it. (I could not find a primary Modular press release with deal terms or a formal date; the acquisition itself is attested by the forum thread and the README link change.)

### Where vLLM and SGLang actually sit

Underneath all of it. vLLM is at v0.26.0 (2026-07-27) and SGLang at v0.5.16 (2026-07-25). KServe's v0.18 ships vLLM v0.19.0 as its bundled runtime; SageMaker's LMI deep learning containers wrap vLLM; `ray.serve.llm` wraps vLLM; a BentoML LLM service imports vLLM directly.

Two consequences that matter for an interview answer:

1. **Your throughput numbers do not belong to the platform.** If a vendor benchmark claims their platform is 2x faster, ask which vLLM version each side ran. The delta is almost always an engine version or a flag (`--enable-prefix-caching`, `--max-num-batched-tokens`, `gpu_memory_utilization`), not the control plane.
2. **Platform version lag is a real cost.** KServe v0.18 pins vLLM v0.19.0 while upstream vLLM is at v0.26.0. If a vLLM release lands a feature you need, a managed or bundled runtime makes you wait for the platform's next release, and on SageMaker you either wait for the next LMI container or build and maintain your own BYOC image, which is a non-trivial standing cost.

---

## Build it from scratch

The point of building it is to see that a "serving platform" is a scale decision plus a routing decision, and that both are about 60 lines. Reference lab: `(lab pending)`.

### A prefix-aware router in 40 lines

This is the mechanism behind the 3x throughput result, minus the Kubernetes. It routes a request to whichever vLLM replica most likely already holds its prompt prefix in KV cache, falling back to least-loaded when no replica has an affinity.

```python
# untested sketch -- illustrates the routing decision, not a production proxy
import hashlib
from dataclasses import dataclass, field

PREFIX_CHARS = 512  # approx first ~128 tokens; tune to your system-prompt length

@dataclass
class Replica:
    url: str
    inflight: int = 0
    # prefix hashes this replica has recently served -> assume still cached
    seen: set[str] = field(default_factory=set)

def prefix_key(prompt: str) -> str:
    return hashlib.blake2b(prompt[:PREFIX_CHARS].encode(), digest_size=8).hexdigest()

def choose(replicas: list[Replica], prompt: str, max_inflight: int = 64) -> Replica:
    key = prefix_key(prompt)
    # 1. affinity: a replica that has served this prefix and is not saturated
    affine = [r for r in replicas if key in r.seen and r.inflight < max_inflight]
    if affine:
        return min(affine, key=lambda r: r.inflight)
    # 2. fall back to least-loaded. NOT round-robin: decode length varies 100x,
    #    so request count is a terrible proxy for load; in-flight count is better,
    #    and queued-tokens is better still if the engine exposes it.
    return min(replicas, key=lambda r: r.inflight)

def dispatch(replicas, prompt):
    r = choose(replicas, prompt)
    r.inflight += 1
    r.seen.add(prefix_key(prompt))     # real impl: bounded LRU sized to KV pool
    try:
        return post(r.url, prompt)     # your HTTP call
    finally:
        r.inflight -= 1
```

Three things this makes obvious that the YAML hides. **Round-robin is actively harmful in front of vLLM**, because a request that lands on a replica without the prefix pays full prefill, and prefill is the expensive half. **`seen` must be bounded and sized to the actual KV pool**, or you route to a replica that evicted the prefix twenty requests ago and get a cache miss plus a load imbalance. **In-flight request count is a mediocre load signal** because decode lengths vary by two orders of magnitude; the production version scores on queued tokens or `vllm:num_requests_waiting` scraped from the engine's `/metrics`. That is precisely what the Gateway API Inference Extension's endpoint picker does, and why KServe delegates to it rather than reimplementing it.

### A scale-to-zero controller in 30 lines

```python
# untested sketch -- the whole idea of scale-to-zero, minus the cloud API
import time

class ScaleToZero:
    def __init__(self, scale_fn, idle_seconds=600, cold_start_budget=45.0):
        self.scale_fn = scale_fn          # scale_fn(n) -> provisions n replicas
        self.idle_seconds = idle_seconds  # cf. Ray downscale_delay_s default 600
        self.cold_start_budget = cold_start_budget
        self.replicas, self.last_request, self.queue = 0, 0.0, []

    def on_request(self, req):
        self.last_request = time.time()
        if self.replicas == 0:
            # THE decision: buffer (Knative activator) or fail (SageMaker).
            # Buffering means holding an open connection for cold_start_budget
            # seconds; failing means the caller needs a retry budget that long.
            self.queue.append(req)
            self.scale_fn(1)
            self.replicas = 1
            return "queued"
        return "dispatched"

    def tick(self):
        idle = time.time() - self.last_request
        if self.replicas > 0 and not self.queue and idle > self.idle_seconds:
            self.scale_fn(0)
            self.replicas = 0
```

The `on_request` branch at `self.replicas == 0` is the entire architectural difference between the platforms. Knative (and therefore KServe in Knative mode) puts an **activator** in the data path that holds the request open while the pod starts, so a cold start is a slow 200. SageMaker has no such component: the request returns an error, that error increments `NoCapacityInvocationFailures`, and the alarm on that metric is what starts the machine. Ray Serve queues in the router. Same feature name, three different contracts with your caller.

The second thing this exposes: `idle_seconds` is a pure cost-versus-latency dial with a closed-form break-even. If a cold start costs `C` seconds of GPU-equivalent (image pull plus weight load plus warm-up) and requests arrive with mean gap `g`, holding a replica idle for `T` seconds is cheaper than paying cold starts whenever `T < C · (probability the next request arrives within T)`. In practice: with a 45-second cold start and traffic gaps averaging 5 minutes, a 600-second idle timeout means you almost never actually scale to zero, and you have paid the complexity without the saving. Measure the arrival-gap distribution before setting the dial.

---

## How it's done in production

### The selection matrix that actually holds up

| If this is true | Use | Because |
|---|---|---|
| Model is only in a vendor catalog | Bedrock / Vertex | Nothing else can serve it. Cost analysis is moot. |
| < 3 models, no existing K8s, team ≤ 5 | SageMaker Real-Time | The 25% markup is cheaper than the first on-call rotation. |
| Already on EKS/GKE, GPU fleet, many models | KServe `LLMInferenceService` | Prefix-aware routing and node-local weight cache are worth real money at fleet scale. |
| One request fans out to models on different hardware | Ray Serve | The one thing it is uniquely good at. |
| Bursty CPU-only classical ML, long idle periods | SageMaker Serverless | Genuinely scales to zero, genuinely cheap, no GPU. |
| Payloads > 6 MB or inference > 60s | SageMaker Async | Up to 1 GB payload, up to 1 hour processing, scales to zero. |
| Nightly re-scoring, no live endpoint needed | Batch Transform / Bedrock batch | ~50% cheaper than the interactive path. |
| Need reproducible images, not a scheduler | BentoML | It is a build tool. Pair it with one of the above. |
| Traffic steady enough for > 60% GPU utilization | Self-hosted vLLM on EC2/EKS | At 2.6x versus spot, the markup stops being defensible. |

### The observability contract, per platform

A thing candidates forget: whatever you pick, the metrics you need are engine metrics, and the platform either forwards them or hides them.

| Platform | What you can scale on | What you can see |
|---|---|---|
| SageMaker RT | `InvocationsPerInstance`, `SageMakerInferenceComponentInvocationsPerCopy`, custom CloudWatch | Endpoint-level CW metrics. vLLM's own `/metrics` needs a sidecar or a custom container that pushes. |
| KServe + Knative | concurrency, QPS (KPA) | Knative Serving scaling dashboards; engine metrics via Prometheus scrape of the pod. |
| KServe + KEDA | any Prometheus/OTel metric, including `vllm:num_requests_waiting`, `vllm:gpu_cache_usage_perc` | Full. This is the reason to run Raw mode. |
| Ray Serve | `serve_autoscaling_target_ongoing_requests`, replica processing latency, objref resolution latency | Ray dashboard plus Prometheus; recently-stopped replica logs retained since 2.56. |

The KEDA row is the actionable one. Scaling GPU LLM serving on CPU utilization or request count is wrong: a vLLM replica at 95% GPU utilization with an empty waiting queue is *healthy and should not scale out*, while one at 40% GPU with 200 waiting requests is *saturated on KV cache and must*. The correct signal is `vllm:num_requests_waiting` or KV-cache-pool occupancy, and only the KEDA/Prometheus path lets you scale on it. KServe supports this both via a direct Prometheus scaler and via the `keda-otel-add-on` gRPC external scaler for pod-level OTel metrics.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| First request after an idle period returns HTTP 5xx, then requests succeed a few minutes later | SageMaker scale-from-zero: the CloudWatch alarm fires on `NoCapacityInvocationFailures`, so requests must fail before provisioning starts, and provisioning takes minutes | Keep `MinInstanceCount ≥ 1` for anything with an SLO; if you must scale to zero, give callers a retry budget longer than the full provisioning path and surface it as a documented contract, not a surprise |
| Endpoint bill unchanged after enabling scale-to-zero | Idle timeout longer than the traffic gap, so the service never actually reaches zero (Ray `downscale_delay_s=600` by default; KEDA `cooldownPeriod: 300`) | Plot the inter-arrival-gap distribution; set idle timeout below p50 gap or accept that you have bought complexity with no saving |
| p99 doubles after adding a second replica; p50 unchanged | Round-robin routing splits a shared system prompt across replicas, halving prefix-cache hit rate so every other request pays full prefill | Enable prefix-cache-aware routing (KServe InferencePool/EPP, Ray `ConsistentHashRouter`); confirm with `vllm:prefix_cache_hit_rate` before and after |
| Callers see `BackPressureError` / HTTP 503 with GPUs at 30% utilization | Ray Serve `max_ongoing_requests` default dropped 100 → 5 in Ray 2.32.0; per-replica queue is now 20x shallower than the version you tuned against | Set `max_ongoing_requests` explicitly, 20-50% above `target_ongoing_requests`; never rely on the default across a version upgrade |
| KServe pods scale on CPU while GPU sits idle or vice versa; scaling oscillates | Scaling on CPU/memory or request count instead of engine queue depth; or KPA panic mode (6s window, 2x target) flapping against a slow-starting pod | Switch to Raw mode + KEDA scaling on `vllm:num_requests_waiting`; raise `containerConcurrency` so the hard limit is not doing your scaling for you |
| Cold start ~4 minutes for a 70B despite a warm node pool | Weights pulled from S3/HF per pod start; 140 GB at ~1 GB/s is ~140s before the engine even begins loading | Pre-stage weights with KServe `LocalModelCache` / `LocalModelNamespaceCache` on node-local NVMe; pre-pull the 8-15 GB CUDA image via a DaemonSet |
| Multi-model endpoint p99 spikes on a specific tenant, others fine | MME evicted that tenant's model under memory pressure; the next invocation pays a full load from the instance's EBS volume | For small models, right-size instance memory to working set and watch `ModelCacheHit`; for LLMs, stop using MME and switch to one base model plus per-tenant LoRA adapters |
| Two vLLM replicas on one GPU both OOM at startup | Density packing fighting the KV cache: `gpu_memory_utilization=0.90` means one replica claims 90% of VRAM by design | One engine process per GPU; achieve multi-tenancy with LoRA adapters or tensor parallelism, not co-located engines |
| Platform upgrade regresses throughput 20% with no config change | Bundled engine version moved (KServe v0.18 pins vLLM v0.19.0), changing a scheduler default such as chunked-prefill size or prefix-cache behaviour | Pin the runtime image explicitly rather than tracking the platform's default; diff engine flags across versions as part of upgrade validation |
| `kubectl get isvc` shows Ready but traffic 404s at the gateway | `LLMInferenceService` HTTPRoute attached to the wrong Gateway listener; a shared Gateway exposes several and the route needs `sectionName` | Set `sectionName` on the gateway ref (supported since v0.18); check `HTTPRoute` parent status filtered by gateway name |
| Model was fine in staging, refuses to schedule in prod | `LLMInferenceService` defaults to the Pod Security Standards **restricted** profile since v0.18: no root, dropped capabilities, no privilege escalation | Fix the image to run non-root rather than relaxing the namespace PSS label |

### What a real deployment adds beyond the YAML

- **Weight pre-staging is the highest-leverage cold-start fix**, ahead of any autoscaler tuning. Moving weights from S3 to node-local NVMe removes 20-140 seconds from every pod start, and it is the difference between scale-to-zero being viable and theoretical.
- **Two-tier capacity.** A steady base of on-demand or reserved instances sized to p50 traffic, with burst capacity on spot at roughly half the price (`g5.24xlarge` $3.96 spot vs $8.14 on-demand) and a managed endpoint or Bedrock as the overflow valve when spot is reclaimed. This is the configuration that actually beats both extremes on cost.
- **Rollout is where managed platforms earn their markup.** SageMaker production variants shift traffic between model versions with a one-line API call. KServe canary rollout does the same via Knative traffic splitting or Gateway API weights. Ray Serve rolls replicas with a configurable rolling-update percentage. Doing this yourself on plain Deployments means you own the traffic-shifting and the rollback trigger, and rollback trigger design is where homegrown rollout usually fails: teams shift traffic on pod readiness, which for an LLM is "the process is up," not "the model produces sane output."
- **Disaggregated prefill/decode** (llm-d, integrated into KServe at v0.6) puts prefill on compute-dense GPUs and decode on bandwidth-dense ones, because the two phases have opposite bottlenecks. KServe's `InferencePool` readiness now evaluates both prefill and decode pools separately. This is production at a handful of large shops and premature almost everywhere else.

---

## Tradeoffs & when NOT to use it

The senior signal on this topic is being willing to say a popular tool is usually wrong. Here is where each one is.

**Do not use KServe if you are not already running Kubernetes.** This is the biggest one and people hate hearing it. KServe in Knative mode drags in Knative Serving, an Istio or Kourier or Gateway API networking layer, cert-manager, and a cluster autoscaler. Running it well means someone who can debug a Knative activator, an Envoy config dump, and a `HTTPRoute` parent status. If your alternative is a SageMaker endpoint, the 25% markup buys you all of that, and the crossover is not close until you have roughly ten GPU nodes or a fleet of models. Adopt Kubernetes for reasons that have nothing to do with serving, then put KServe on it.

**Do not use Ray Serve for a single model behind a single endpoint.** You inherit a Ray head node (a new single point of coordination with its own GCS state), a second scheduler that disagrees with Kubernetes about what is running where, and an autoscaler whose defaults are tuned for a different shape of workload. A `Deployment` plus an `HPA` plus vLLM's own OpenAI-compatible server does the same job with one fewer failure domain. Ray Serve is correct when your request graph genuinely fans out across heterogeneous hardware. It is defensible when you already run Ray for training or data and want one cluster. It is wrong when the argument is "we might need composition later."

**Do not use SageMaker Serverless Inference for anything with a GPU.** It is documented as unsupported, not just slow. Also excluded: VPC configuration, network isolation, Model Monitor, data capture, and multiple production variants, which between them disqualify most regulated deployments regardless of model size.

**Do not enable SageMaker scale-to-zero on a user-facing endpoint.** Restating because it is the single most expensive mistake in this module: the scale-out trigger is a failure counter. The first requests after idle do not wait, they error, and they keep erroring for the several minutes AWS takes to provision. This is fine for internal tools, dev endpoints, and anything with a job-queue caller. It is an availability incident on a synchronous user path.

**Do not use SageMaker Multi-Model Endpoints for LLMs.** Density packing and KV caching want the same VRAM. Use one resident base model plus LoRA adapters. MME remains a good answer for hundreds of small CPU models, which is what it was built for.

**Do not reach for ModelMesh at all.** Archived April 2026, last release July 2024, documentation removed from KServe 0.18 and 0.19. The landing page still advertises it; the release history is the source of truth.

**Do not make BentoML a platform decision.** It is a packaging tool and a good one, but it does not answer autoscaling, routing, or rollout. Combined with its acquisition by Modular and a three-month gap since the last OSS release, treat it as a build-time dependency you could replace with a Dockerfile in a week, and make sure that stays true.

**Do not self-host below ~60% sustained GPU utilization.** Fixed instance-hours amortized over low throughput lose to per-token pricing every time. The relevant question is not requests per day, it is the shape of the traffic: a workload with a 10x peak-to-average ratio needs capacity sized to the peak, and at that sizing your average utilization is 10%, which is a terrible trade no matter what the daily total is. Sibling module `T09-bedrock-vs-sagemaker` works the managed-versus-self-hosted cost model in full.

**Do not port a serving platform to chase a benchmark.** Because the engine is the same underneath, a platform migration typically moves your p50 by single-digit percent. Migrate for cost, for routing quality, or for operational fit. Migrating for throughput usually means someone benchmarked two different vLLM versions and attributed the difference to the wrapper.

**Where reasonable people still disagree.** Whether the Kubernetes-native stack's complexity is worth it in the 3-to-10 GPU range is genuinely unsettled, and the answer depends almost entirely on whether your organization already has Kubernetes expertise on staff. Whether disaggregated prefill/decode is worth its scheduling complexity outside very large fleets is also open: the theoretical argument is strong and the operational evidence is currently concentrated in a handful of shops. Say which side you land on and why, rather than presenting either as settled.

---

## Interview questions

### Q1 — Walk me through what happens when a request hits a SageMaker endpoint that has scaled to zero.
**Testing:** whether you have actually operated scale-to-zero rather than read the feature bullet.
**Answer:** The request fails. SageMaker has no activator or buffering layer in the data path. The failed invocation increments the CloudWatch metric `NoCapacityInvocationFailures` in the `AWS/SageMaker` namespace. An alarm on that metric (typically `period=60`, `threshold=1`, `evaluation-periods=1`) fires a step scaling policy against the inference component's `DesiredCopyCount`, and SageMaker then provisions instances, which AWS documents as taking several minutes. Every request during that window errors. Prerequisites: the endpoint must host inference components, and the production variant must have `ManagedInstanceScaling.MinInstanceCount = 0`.
**Follow-up trap:** *"So how do you make it usable for a user-facing API?"* — you generally do not. Either keep `MinInstanceCount ≥ 1` and accept the standing cost, or put an async queue between the user and the endpoint so the retry happens out of band. If you must, the client needs a documented retry-with-backoff budget exceeding the full provisioning path, which for a large model is minutes; presenting that as a normal client contract is the honest framing. Do not claim you would "warm it with a cron ping," because a keepalive that prevents scale-in defeats the entire feature.

### Q2 — How much more does SageMaker cost than running the same model on EC2, and what do you get for it?
**Testing:** whether you carry real numbers or adjectives.
**Answer:** About 25% over EC2 on-demand for the same silicon: `ml.g5.24xlarge` at $10.18/hr against `g5.24xlarge` at $8.144/hr, and `ml.g5.2xlarge` at $1.52 against `g5.2xlarge` at $1.212, both us-east-1. Since SageMaker Real-Time does not offer spot for inference, the comparison against a spot-tolerant self-hosted fleet is roughly 2.6x ($10.18 vs $3.955). For that you get managed rollout via production variants, IAM-native invoke authorization, endpoint CloudWatch metrics, and no cluster to patch. At one node the delta is about $1,500/month, which is nobody's migration. At twenty nodes it is roughly $30,000/month, which is an engineer.
**Follow-up trap:** *"Your team says EKS is cheaper because the control plane is only $0.10/hour. Is that the right comparison?"* — no, and the fact that they framed it that way is the tell. The EKS control plane is $0.10/cluster/hour on a supported Kubernetes version, $0.60 once it enters extended support, and either way it is rounding error next to one GPU node. The real self-hosted cost is the engineer-hours for autoscaling, node lifecycle, driver and CUDA compatibility, and the on-call rotation. Compare fully-loaded costs or do not compare.

### Q3 — Your p99 latency doubled after you scaled from one replica to two. p50 is unchanged. What happened?
**Testing:** whether you understand that LLM serving is stateful in a way classical serving is not.
**Answer:** Prefix cache fragmentation from round-robin routing. With one replica, every request shares the same KV cache, so a common system prompt or retrieved-context boilerplate is prefilled once and reused. With two replicas behind round-robin, a given prefix is resident on one of them and roughly half of requests land on the replica that does not have it, paying full prefill. p50 barely moves because the median request was cheap anyway; p99 doubles because the long-prompt tail now pays prefill twice as often. Confirm by comparing `vllm:prefix_cache_hit_rate` before and after.
**Follow-up trap:** *"Fix it."* — prefix-cache-aware routing, not more replicas. On KServe that means the `LLMInferenceService` router with an `InferencePool` and the Gateway API Inference Extension endpoint picker; on Ray Serve 2.56+ it is `ConsistentHashRouter` for session-sticky hashing. The reported win from Tesla and Red Hat on Llama 3.1 70B across 4 MI300X was 3x output tokens/s and 2x lower TTFT purely from enabling this. If you cannot change the router, the crude fallback is hashing on session or tenant ID at the application layer, which captures most of the benefit for chat workloads.

### Q4 — Compare KServe's `InferenceService` and `LLMInferenceService`. When would you use each?
**Testing:** whether your KServe knowledge is current or from a 2022 tutorial.
**Answer:** `InferenceService` (v1beta1) is the classical-ML CRD: a `predictor` block with a `modelFormat`, a `storageUri`, and optional `transformer` and `explainer` components, autoscaled by KPA on concurrency or QPS. It is right for sklearn, XGBoost, ONNX, and small encoders. `LLMInferenceService` (v1alpha2) is the generative CRD, production-ready since KServe v0.17. It models what LLM serving actually needs: a `parallelism` block for tensor and data parallelism, a `worker` spec for multi-node replicas, a `router` block wiring a managed Gateway plus an `InferencePool` scheduler for cache-aware routing, and a `scaling` block that can target KEDA with `idleReplicaCount: 0` or the Workload Variant Autoscaler with a `variantCost`. If you are serving an LLM in 2026 and writing a `predictor` block, you are on the wrong CRD.
**Follow-up trap:** *"You need scale-to-zero and Prometheus-based scaling on vLLM queue depth. Which deployment mode?"* — Raw/Standard with KEDA, not Knative. KPA is only supported in Knative mode and scales on concurrency or QPS; KEDA is only supported in Raw mode but can scale on any Prometheus or OTel metric including `vllm:num_requests_waiting`, which is the signal you actually want. The cost of choosing Raw is that you lose the Knative activator, so your cold start is a hard failure rather than a buffered request, and you have to handle that at the caller.

### Q5 — Why is scaling an LLM endpoint on GPU utilization a bad idea?
**Testing:** whether you know what saturation means for a batching inference engine.
**Answer:** Because GPU utilization is nearly binary for a continuously-batching engine and does not track headroom. A vLLM replica running one request can show high GPU utilization during decode, and a replica running sixty shows about the same, because decode is memory-bandwidth-bound and the SM occupancy metric does not reflect how much KV cache is left. The two states you actually need to distinguish are "95% GPU, empty waiting queue" (healthy, do not scale) and "40% GPU, 200 requests waiting because the KV pool is full" (saturated, must scale). The correct signals are `vllm:num_requests_waiting` and KV-cache pool occupancy (`vllm:gpu_cache_usage_perc`), or in-flight requests per replica as a cruder proxy.
**Follow-up trap:** *"Your platform only exposes CPU and request-count metrics. Now what?"* — request count is a bad proxy because output lengths vary by two orders of magnitude, so ten summarization requests and ten one-token classifications are the same number and wildly different load. Either export engine metrics yourself (a sidecar scraping vLLM's `/metrics` into Prometheus, then KEDA on that) or scale on a token-weighted signal you compute at the router. If neither is possible, that is a real argument against the platform, and saying so is a better answer than pretending request count is fine.

### Q6 — When is Ray Serve the right choice, and when is it a mistake?
**Testing:** whether you can articulate the one thing it does uniquely, and refuse it otherwise.
**Answer:** Right when a single logical request fans out across models with different hardware needs and different scaling curves: a CPU retriever, a GPU cross-encoder reranker, a GPU generator, each an independently scaled deployment composed with `.bind()` and called through `DeploymentHandle.remote()`. Ray schedules them onto different node types within one application, which in plain Kubernetes would be three Deployments, three Services, three HPAs, and two extra network hops. It is also defensible if you already run Ray for training and want one cluster. It is a mistake for a single model behind a single endpoint: you take on a Ray head node as a new coordination failure domain and a second scheduler that disagrees with Kubernetes, in exchange for nothing a Deployment plus vLLM's OpenAI server does not already give you.
**Follow-up trap:** *"Describe the deployment graph API."* — this is a staleness check. There is no DAG DSL any more; `DAGDriver`, `InputNode`, and `serve.build` are gone. Composition is ordinary Python: `.bind()` deployments into each other's constructors, Ray converts them to `DeploymentHandle`s, you call `.remote()` and `await` a `DeploymentResponse`. If you describe the old graph API confidently, the interviewer learns you last touched Ray Serve around 2.5.

### Q7 — You have 400 per-tenant fine-tuned models. Design the serving layer.
**Testing:** whether you know the multi-model story diverged for LLMs.
**Answer:** First question back: how big is a model and what is the base? If these are 400 small classical models (tree ensembles, small encoders under ~200 MB), a SageMaker Multi-Model Endpoint is exactly the intended shape: one fleet, models loaded into container memory on first invocation, evicted under pressure but retained on the instance's EBS volume so a re-load skips the S3 fetch. Right-size instance memory to the working set and watch cache-hit metrics. If these are 400 LLM fine-tunes of a common base, the answer is completely different: one resident base model per GPU plus **per-tenant LoRA adapters**, swapped per request. Adapters are tens to hundreds of MB against a 16 GB base, so 400 of them are tractable where 400 full models are not. vLLM serves multi-LoRA natively; KServe auto-enables a LoRA affinity scorer in its router when adapters are present.
**Follow-up trap:** *"Why not just use MME on GPU instances for the LLM case? It supports GPU."* — because density packing and KV caching compete for the same VRAM. vLLM claims `gpu_memory_utilization=0.90` deliberately, to make the KV pool large, which is where the throughput comes from. An MME scheduler wants that VRAM free so it can swap models in. Two 8B fp16 models are 32 GB of weights before any KV cache, which does not fit on a 24 GB A10G at all. Full-model swapping on GPU also costs tens of seconds per miss against single-digit-millisecond misses for a small CPU model, so the cache-miss penalty that MME's design tolerates becomes intolerable.

### Q8 — What is ModelMesh and would you use it?
**Testing:** whether your knowledge has an expiry date on it.
**Answer:** ModelMesh was KServe's high-density multi-model layer, originally an IBM contribution, designed to intelligently load and unload thousands of models across a fleet to trade responsiveness against memory footprint. I would not use it: both `kserve/modelmesh` and `kserve/modelmesh-serving` were archived on 2026-04-14, the last release was v0.12.0 in July 2024, and the `admin-guide/modelmesh` documentation page exists for KServe docs 0.16 and 0.17 but returns 404 on 0.18 and 0.19. The KServe landing page still advertises "density packing and intelligent routing using ModelMesh," which is stale marketing copy, not a signal of support.
**Follow-up trap:** *"Then what replaced it?"* — nothing replaced it as a general density layer, and that is the honest answer. The problem bifurcated. For small classical models, people either use MME-style managed density or just run more pods, because small models are cheap. For LLMs, the density problem is solved by multi-LoRA rather than by model swapping, and KServe's investment went entirely into `LLMInferenceService`, InferencePool routing, and llm-d integration. Claiming a successor exists is a worse answer than saying the category dissolved.

### Q9 — Break down the cold-start budget for a 70B model on a scaled-to-zero Kubernetes endpoint. Where do you optimize first?
**Testing:** whether you can decompose a latency budget instead of quoting one number.
**Answer:** Five stages. Detect (activator or autoscaler notices), roughly milliseconds on Knative, tens of seconds on a polling autoscaler. Schedule (get a node with 4-8 free GPUs), zero if the pool is warm, 90-180 seconds if a cluster autoscaler must launch a GPU instance. Image pull, zero if cached, 60-200 seconds for an 8-15 GB CUDA image on a cold node. Weight fetch: 70B at fp16 is ~140 GB, so at ~1 GB/s from S3 that is over two minutes. Load and warm: CUDA graph capture and KV pool allocation, another 20-90 seconds. Realistic cold path on a cold node is 8-15 minutes. I optimize weight fetch and image pull first, because they are the largest terms and both have clean fixes: pre-stage weights on node-local NVMe with KServe's `LocalModelCache` or the namespace-scoped `LocalModelNamespaceCache`, and pre-pull the runtime image with a DaemonSet. Autoscaler tuning is last; shaving the detect stage from 30s to 10s is irrelevant against a 140-second weight fetch.
**Follow-up trap:** *"After all that you are still at 3 minutes. Product wants sub-second. What do you tell them?"* — that scale-to-zero and sub-second first-response are mutually exclusive for a 70B, and the decision is which to give up. Options in order of honesty: keep `minReplicas=1` and pay for one warm replica (a `p4d.24xlarge` at $32.77/hr on-demand or $13.07 spot), which is the only way to get sub-second; or keep a small model warm to serve while the large one loads, accepting a quality step-change; or move the workload behind a queue and change the product contract from synchronous to asynchronous. Pretending a tuning exercise closes a 3-minute-to-1-second gap is the failure mode here.

### Q10 — Where does BentoML fit relative to KServe and SageMaker, and would you bet a platform on it?
**Testing:** whether you can distinguish packaging from orchestration, and whether you track project health.
**Answer:** BentoML is layer 3, packaging. `@bentoml.service` and `@bentoml.api` define the service; `bentoml build` produces a Bento containing code, resolved dependencies, model references, and the service spec; `bentoml containerize` turns it into an OCI image. Its real value is that the image spec is code (`bentoml.images.Image(python_version="3.11").python_packages(...)`), so dependency drift is caught at build time, plus `batchable=True` giving adaptive server-side batching for free. It is not a scheduler: it does not decide replica counts, routing, or rollout. So it composes with KServe or SageMaker rather than competing with them. I would not bet a platform on it: BentoML was acquired by Modular (its README's community forum now points at forum.modular.com, which hosts an acquisition roundup thread dated 2026-03-01), and the last OSS release was v1.4.39 on 2026-05-07, about three months quiet. That is a reason to keep it replaceable, not to avoid it.
**Follow-up trap:** *"So what would you use instead?"* — a Dockerfile, in most cases, and I would say that plainly. BentoML's advantages over a well-maintained Dockerfile plus FastAPI are adaptive batching and the code-as-image-spec ergonomics, both real but both reproducible in a day or two. The test I would apply: if replacing BentoML would take more than a week, we have coupled to it too hard given its current governance situation.

### Q11 — You inherit a Ray Serve service that started returning 503s after a Ray upgrade. Traffic is unchanged and GPUs are at 30%. Diagnose.
**Testing:** whether you know the specific default change, and more generally whether you check defaults across upgrades.
**Answer:** Almost certainly `max_ongoing_requests`. Its default dropped from 100 to 5 in Ray 2.32.0, a 20x reduction in how many concurrent requests a replica accepts. If the service was tuned before that boundary and relied on the default, each replica now admits 5 instead of 100, the router's queue backs up, and once `max_queued_requests` is exceeded callers get `BackPressureError` on handles or HTTP 503 on the proxy. GPUs sit at 30% because the bottleneck is admission control, not compute. The related change in the same release: `target_ongoing_requests` moved from 1.0 to 2.0. Fix by setting both explicitly, with `max_ongoing_requests` about 20-50% above `target_ongoing_requests` for heavyweight deployments and considerably higher for lightweight ones.
**Follow-up trap:** *"How would you have caught this before it hit production?"* — pin and assert on defaults, not just versions. Any parameter you rely on implicitly is an unversioned dependency. Concretely: set every autoscaling and concurrency parameter explicitly in the Serve config rather than inheriting it, and add a load test to the upgrade gate that drives past the previous saturation point and asserts on 503 rate rather than on average latency, since the average looked fine here.

### Q12 — Design the serving architecture for a RAG chat product: 5,000 requests/hour at peak, 300/hour overnight, heavy shared system prompt, p95 TTFT target of 800ms, one 8B open-weight model.
**Testing:** whether you size from traffic shape rather than pattern-matching to a favourite tool.
**Answer:** Peak-to-average is about 16:1, which is the number that drives everything. An 8B at fp16 is 16 GB of weights, so a single A10G (`g5.2xlarge`, 24 GB, $1.212/hr on-demand) holds it with a modest KV pool; a `g5.12xlarge` at $5.672/hr gives four for the peak. The 800ms p95 TTFT target rules out scale-to-zero on the user path outright, so `minReplicas=1` non-negotiable, sized to overnight traffic. Heavy shared system prompt means prefix caching is the dominant lever: enable vLLM prefix caching and put prefix-cache-aware routing in front, because with a shared prefix, round-robin across peak replicas is exactly the p99 failure from Q3. Scale on `vllm:num_requests_waiting` via KEDA, not GPU utilization. Peak burst goes on spot at roughly half price ($0.595 vs $1.212) with the baseline on-demand, and a managed endpoint or hosted API as the overflow valve when spot is reclaimed. Platform: if the org already runs Kubernetes, KServe `LLMInferenceService`; if not, a SageMaker Real-Time endpoint with an LMI/vLLM container and application-layer session-sticky routing, accepting the 25% markup because at this scale it is roughly $300-1,500/month and cheaper than building cluster competence.
**Follow-up trap:** *"Overnight you are paying for a mostly-idle GPU. Justify it to finance."* — quantify it rather than defending it. One `g5.2xlarge` running 8 overnight hours is 8 × $1.212 = $9.70/night, about $295/month, and roughly two thirds of that is genuinely idle capacity, so about $200/month is the cost of the 800ms TTFT guarantee overnight. Then offer the alternative explicitly: scale to zero overnight and the first request after idle takes 30-60 seconds (warm node, cached image, 16 GB weight load), which is a product decision about whether an overnight user waits a minute. Presenting it as a $200/month line item against a named product behaviour is what gets a decision; arguing for the GPU on principle does not.

### Q13 — Staff level: you own serving for 30 models across 3 teams. Two teams want KServe, one wants to stay on SageMaker. Make the call.
**Testing:** platform judgment and the willingness to accept a non-uniform answer.
**Answer:** I would not force uniformity for its own sake, and I would say so. The questions that decide it: how many of the 30 models are LLMs versus classical, what the aggregate GPU footprint is, and whether the org has Kubernetes on-call capability today. If the GPU fleet is above roughly ten nodes, the SageMaker markup is $25,000+/month against EC2 on-demand and considerably more against spot, and consolidating on KServe pays for the platform work. If it is three nodes, it does not, and the two teams wanting KServe are optimizing for résumé rather than for cost. The likely correct outcome is split by workload rather than by team: LLM serving on KServe where prefix-aware routing and node-local weight caching produce measurable wins, classical models on SageMaker endpoints or MME where the operational simplicity is worth 25%. What I would insist on regardless of platform is a common contract: OpenAI-compatible HTTP surface, engine metrics in one Prometheus, model artifacts in one registry, so the platform under a model can change without the callers noticing.
**Follow-up trap:** *"Your VP says two platforms is unacceptable operational overhead. Respond."* — agree with the concern and reframe where the overhead actually lives. The overhead is not "two platforms," it is two on-call rotations, two metrics stacks, and two rollout mechanisms. If the abstraction contract above holds (one metrics pipeline, one registry, one API shape), the marginal cost of a second scheduler is small and bounded. If it does not hold, the VP is right and one platform is correct even at a cost premium. Then give the number: consolidating everything on SageMaker costs approximately X per month in markup, consolidating on KServe costs approximately Y engineer-months of platform work plus an on-call rotation, and pick. Refusing to name the numbers is what makes this conversation go badly.

### Q14 — Someone proposes TorchServe for a new PyTorch model. Respond.
**Testing:** whether you track project health as part of technology selection.
**Answer:** No. The `pytorch/serve` repository is archived and its README states the project "is no longer actively maintained," with no planned updates, bug fixes, new features, or security patches, and it explicitly warns that vulnerabilities may not be addressed. Last push was August 2025. For a classical PyTorch model, the current options are a KServe `InferenceService` with a PyTorch or Triton runtime, or a plain FastAPI container. For anything generative, vLLM or SGLang.
**Follow-up trap:** *"We already run TorchServe for four models in production. Do we migrate?"* — not urgently, and I would separate the two decisions. Do not start anything new on it, and treat the security posture as the forcing function rather than the feature set: an unmaintained model server that terminates HTTP and loads user-supplied model archives is a real exposure, so the migration priority is driven by whether those endpoints are internet-facing and what they deserialize. If they are internal and behind auth, this is a planned quarter of work; if any of them are exposed, it moves up. Naming the security rationale rather than "it is deprecated" is the difference between a plan and a preference.

---

## Red flags that fail you

- Saying "we'll use scale-to-zero to save money" without being able to describe the cold-start chain or which link the platform makes you own.
- Not knowing that SageMaker's scale-out-from-zero triggers on `NoCapacityInvocationFailures`, i.e. on requests that already failed.
- Proposing SageMaker Serverless Inference for a GPU model. It does not support GPUs at all.
- Recommending ModelMesh, or TorchServe, in 2026.
- Describing Ray Serve composition with `DAGDriver` / `InputNode` / `serve.build`.
- Adopting Ray Serve for a single model behind a single endpoint and calling it "future-proofing for composition."
- Claiming a platform migration will improve throughput, without noting that the engine underneath is the same vLLM.
- Scaling LLM replicas on GPU utilization or raw request count instead of queue depth or KV-cache occupancy.
- Quoting instance prices with no region, no date, and no acknowledgment that they move.
- Proposing multi-model endpoints for LLMs without addressing the VRAM contention between density packing and the KV cache.
- Treating BentoML as an alternative to KServe rather than as a packaging layer that still needs a scheduler.
- Being unable to name a single default value for the platform you claim to run in production.

---

## Cheat card

```
LAYERS      3 packaging (BentoML/Dockerfile) · 2 control plane (the interview)
            1 engine (vLLM v0.26.0 / SGLang v0.5.16) <- all perf numbers live here
            swapping layer 2 does NOT change your p50

MANAGED MARKUP (us-east-1, verify before quoting)
  g5.24xlarge  EC2 on-demand $8.144/hr · EC2 spot $3.955 · SageMaker $10.18
  g5.2xlarge   EC2 on-demand $1.212/hr · EC2 spot $0.595 · SageMaker $1.52
  => SageMaker Real-Time = ~1.25x EC2 on-demand, ~2.6x spot; NO spot for RT endpoints
  p4d.24xlarge $32.77 on-demand / $13.07 spot · p5.48xlarge $98.32 / $57.76
  EKS control plane $0.10/cluster/hr (std), $0.60 (extended support) = noise

SAGEMAKER SCALE-TO-ZERO   requires inference components + MinInstanceCount=0
  scale in : target-track SageMakerInferenceComponentInvocationsPerCopy, cooldown 300s
  scale OUT: CloudWatch alarm on NoCapacityInvocationFailures (period 60, threshold 1)
  => REQUESTS MUST FAIL FIRST, then several minutes of provisioning. No activator.

SAGEMAKER SERVERLESS   NO GPU. 1024-6144MB RAM, 10GB image, 5GB ephemeral, 200 concurrency
  also excluded: MME, VPC config, network isolation, data capture, Model Monitor
  on-demand $0.00004/s duration · PC $0.00001/s standing + $0.000023/s duration
  => Provisioned Concurrency break-even at u = 0.00001/0.000017 = ~59% utilization

KSERVE   v0.19.0 (2026-06-14) · CNCF incubating since Nov 2025 · v0.20.0-rc1 2026-08-03
  InferenceService v1beta1  = classical ML (predictor/transformer/explainer)
  LLMInferenceService v1alpha2 = LLMs, production-ready since v0.17. USE THIS.
  minReplicas DEFAULT 1 (set 0 for scale-to-zero) · scaleTarget soft, containerConcurrency hard
  KPA only in Knative mode · KEDA only in Raw/Standard mode · they are mutually exclusive
  KPA: 60s stable window, 6s panic window, panic at 2x target, exit after 60s calm
  v0.18: multi-node WITHOUT Ray via vLLM mp executor backend (multinode/executor-backend)
         LeaderWorkerSet as scale target · llm-d v0.6 · /v1/responses · PSS restricted
         LocalModelNamespaceCache (node-local weight pre-stage = biggest cold-start win)
  MODELMESH IS DEAD: both repos archived 2026-04-14, last release v0.12.0 Jul-2024,
         docs 404 on 0.18/0.19 (landing page still advertises it — ignore that)

RAY SERVE   Ray 2.56.1 (2026-07-17). Composition = .bind() + DeploymentHandle + .remote()
  DAGDriver / InputNode / serve.build ARE GONE
  defaults: num_replicas 1 · target_ongoing_requests 2 (was 1.0 pre-2.32)
            max_ongoing_requests 5 (WAS 100 pre-2.32 — 20x cut, causes 503s on upgrade)
            min/max_replicas 1/1 · upscale_delay_s 30 · downscale_delay_s 600
            metrics_interval_s 10 · look_back_period_s 30 · max_queued_requests -1
            health_check 10s/30s · graceful_shutdown 2s/20s
  2.56 adds ConsistentHashRouter (session-sticky), CapacityQueueRouter, HAProxy ingress
  WORTH IT ONLY when one request fans out across heterogeneous hardware

BENTOML   v1.4.39 (2026-05-07), acquired by Modular (~Feb/Mar 2026), ~3mo quiet
  @bentoml.service(image=bentoml.images.Image(...)) · @bentoml.api(batchable=True)
  bentoml build -> Bento · bentoml containerize -> OCI · serves on :3000
  IT IS A BUILD TOOL. Competes with your Dockerfile, not with KServe.

ROUTING     round-robin in front of vLLM is actively harmful (splits prefix cache)
  prefix-cache-aware routing: 3x output tok/s, 2x lower TTFT (Tesla/Red Hat,
  Llama 3.1 70B on 4x MI300X, TP=4, gpu-mem-util=0.90, max-model-len=65536)

SCALE ON    vllm:num_requests_waiting or KV-cache occupancy
  NOT GPU util (95% + empty queue = healthy), NOT request count (output len varies 100x)

COLD START  8B, warm node, cached image: ~30-60s · 70B, cold node: ~8-15 min
  stages: detect / schedule node (90-180s) / image pull 8-15GB (60-200s)
          / weights (16GB=~20s, 140GB=~140s) / CUDA graph + KV alloc (20-90s)
  optimize weight pre-stage and image pre-pull FIRST; autoscaler tuning is noise

MULTI-MODEL small models -> MME (load on invoke, evict under pressure, EBS-backed)
            LLMs -> ONE base model + LoRA adapters. Density packing fights the KV cache.

DEAD        TorchServe (pytorch/serve archived, "no longer actively maintained", Aug 2025)
            ModelMesh (archived Apr 2026)
```

## Sources

- [Amazon SageMaker AI Pricing](https://aws.amazon.com/sagemaker/ai/pricing/) — accessed 2026-08-05
- [Scale an endpoint to zero instances — SageMaker Developer Guide](https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling-zero-instances.html) — accessed 2026-08-05
- [Serverless Inference — SageMaker Developer Guide](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html) — accessed 2026-08-05
- [Multi-model endpoints — SageMaker Developer Guide](https://docs.aws.amazon.com/sagemaker/latest/dg/multi-model-endpoints.html) — accessed 2026-08-05
- [Amazon EKS Pricing](https://aws.amazon.com/eks/pricing/) — accessed 2026-08-05
- [ec2.shop EC2 on-demand and spot pricing API](https://ec2.shop) — accessed 2026-08-05
- [KServe releases (v0.19.0, v0.20.0-rc1)](https://github.com/kserve/kserve/releases) — accessed 2026-08-05
- [Announcing KServe v0.18 — Multi-Node Inference, OpenAI Responses API, and LLM-D v0.6](https://kserve.github.io/website/blog/kserve-0.18-release) — accessed 2026-08-05
- [Production-Grade LLM Inference at Scale with KServe, llm-d, and vLLM](https://kserve.github.io/website/blog/production-grade-llm-inference-kserve-llm-d-vllm) — accessed 2026-08-05
- [KServe — Autoscaling with Knative Pod Autoscaler](https://kserve.github.io/website/docs/model-serving/predictive-inference/autoscaling/kpa-autoscaler) — accessed 2026-08-05
- [KServe — Autoscaling with KEDA](https://kserve.github.io/website/docs/model-serving/predictive-inference/autoscaling/keda-autoscaler) — accessed 2026-08-05
- [kserve/modelmesh-serving (archived)](https://github.com/kserve/modelmesh-serving) — accessed 2026-08-05
- [Ray 2.56.0 release notes](https://github.com/ray-project/ray/releases/tag/ray-2.56.0) — accessed 2026-08-05
- [Ray Serve — Advanced autoscaling guide](https://docs.ray.io/en/latest/serve/advanced-guides/advanced-autoscaling.html) — accessed 2026-08-05
- [Ray Serve — Configure Ray Serve deployments](https://docs.ray.io/en/latest/serve/configure-serve-deployment.html) — accessed 2026-08-05
- [Ray Serve — Deploy Compositions of Models](https://docs.ray.io/en/latest/serve/model_composition.html) — accessed 2026-08-05
- [bentoml/BentoML README and releases](https://github.com/bentoml/BentoML) — accessed 2026-08-05
- [Modular community forum, BentoML category](https://forum.modular.com/c/bento/31) — accessed 2026-08-05
- [pytorch/serve (archived, limited maintenance notice)](https://github.com/pytorch/serve) — accessed 2026-08-05
- [vLLM releases (v0.26.0)](https://github.com/vllm-project/vllm/releases) — accessed 2026-08-05
- [SGLang releases (v0.5.16)](https://github.com/sgl-project/sglang/releases) — accessed 2026-08-05

## Changelog
- 2026-08-05 — created

