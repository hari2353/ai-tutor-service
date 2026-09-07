# Production notes — harness evals

## Attacking your own harness

The four attack classes in this lab are the ones that surface in real agent
incidents: prompt injection through tool results (the OWASP LLM L01 family),
hung tools without deadlines, runaway tool loops, and silent cost blowups.

## What production adds

| Concern | Production answer |
|---|---|
| Injection | Sanitizers + structural separation (tool results in a distinct channel the model treats as quoted); capability-scoped tools; canary strings (Simon Willison's marklitkas) |
| Timeouts | Per-tool deadlines enforced by the sandbox (process kill), not by cooperative checks; dead-man timers on the whole run |
| Over-tooling | Trajectory metrics in CI: tools/step thresholds block deploys |
| Cost | Per-request metering at the gateway; hard caps per run + budget alerts; model routing on cost |

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Injection test passes, prod still pops | Sanitizer covers English only | Structural isolation > pattern lists; fuzz with encodings/homoglyphs |
| Hung tool never dies | Cooperative deadline only fn can see | External kill (subprocess timeout, container kill) |
| Cost guard trips AFTER the damage | Charged after execution | Pre-check + post-charge; reserve before the call |
