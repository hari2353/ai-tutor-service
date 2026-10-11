# Production notes - prompt regression gates

The lab deliberately scores required phrases without a model call. Production adds prompt/model/dataset versioning, PII scrubbing, deterministic schema checks, calibrated judges for subjective criteria, held-out slices, CI annotations, canaries, and rollback policy.

| Lab concept | Production addition |
|---|---|
| `GoldenCase` | Versioned replay from production, incidents, adversarial cases, and reviewed synthetic cases |
| Required phrase scoring | JSON/schema/tool-trace checks plus calibrated rubric or judge for open-ended quality |
| Slice rate | Minimum sample counts, confidence intervals, risk-weighted slice policy |
| Baseline drop | Immutable accepted artifact and approval record |
| Gate result | CI status, report artifact, canary decision, and bounded auto-revert |

Do not count provider outages as product-quality regressions. Preserve failed reports, separate infrastructure failures, and refresh the corpus when incidents or new features change the traffic distribution.
