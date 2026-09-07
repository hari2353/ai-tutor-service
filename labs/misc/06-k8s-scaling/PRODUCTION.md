# Production notes — K8s scaling

## The real knobs the lab simplifies

| Lab | Production reality |
|---|---|
| HPA formula | Real HPA: 15s sync period, 10% tolerance (desires within ±10% of current don't trigger), downscale stabilization window (default 5m so flapping doesn't thrash), multi-metric = max-of (worst metric wins) |
| VPA | Runs in recommendation mode by default (actual autoscaling restarts pods!); HPA-on-CPU + VPA-on-CPU conflict → VPA must run Off or on memory only |
| KEDA | Event sources (SQS, Kafka lag) → scaler bridges; scale-to-zero with a cold-start cost |
| Cluster autoscaler | Bin-packing + node group constraints; consolidation is separate (e.g. Descheduler); scale-in respects PodDisruptionBudgets |
| Error budgets | The multiplier chart is the actual SRE on-call tool: >1 sustained = freeze deploys, burn the page |

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| HPA and VPA fight (replicas up, sizes down) | Both scaling on CPU | VPA memory-only or Off; HPA owns CPU |
| Thrashing replicas | No stabilization window | Downscale stabilization 5m+; tolerance > metric noise |
| KEDA scale-to-zero cold starts | Queue spike from 0 pods | minReplicas=1 on latency-sensitive paths |
| Scale-in never removes nodes | Pods pinned / spread thin | PodDisruptionBudgets + topology spread aware consolidation |
