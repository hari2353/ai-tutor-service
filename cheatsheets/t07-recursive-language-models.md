# Recursive Language Models - cheat sheet
> Sources: `T07-recursive-language-models` · generated 2026-09-20

## Say this first
An RLM keeps a long prompt in an external environment and lets the model inspect, search, partition, and recursively solve selected slices. It replaces one flat attention problem with selective computation, but introduces child-call cost, partial failures, and a potentially explosive call tree. Use it when measured context rot or dynamic exploration justifies the orchestration complexity.

## Numbers
| What | Value | Why it matters |
|---|---:|---|
| RLM paper input reach | up to 2 orders beyond window | external context is not all-context attention |
| Paper median vs compaction | +26% | research result, not production SLA |
| Paper median vs CodeAct subcalls | +130% | task and setup dependent |
| Paper median vs Claude Code | +13% | compare on your workload |
| Example fan-out | b=10,d=3 => 1,111 calls | recursive work grows geometrically |
| Required budgets | depth, calls, tokens, cost, time | no unbounded child tree |

## Decision rules
- **Use direct context** for modest inputs/global reasoning. **Use RAG** for stable reusable corpora. **Use RLM** for long/semi-structured inputs needing programmatic exploration.
- **Filter/grep first**, then call models on selected slices. **Never** call every chunk by default.
- **Timeout != no answer.** Retry or mark partial; never convert missing evidence into a negative claim.

## The mechanism, in one diagram
```text
external context -> peek/grep/filter -> child calls -> typed reducer -> answer
                         deterministic        bounded        evidence
```

## Failure modes
| Symptom | Cause | Fix |
|---|---|---|
| exponential cost | unconstrained fan-out | cap depth/calls/tokens/concurrency |
| fluent answer, no citation | reducer dropped ranges | require source/version/offset evidence |
| p99 equals deadline | child cancellation failed | propagate deadlines and kill detached work |
| document runs a command | untrusted data got authority | read-only tools, sandbox, egress deny |

## Traps
- Bigger context solved context engineering → capacity is not uniform reasoning quality.
- Parallel calls solve cost → parallelism reduces wall time, not total tokens or provider spend.

## Do not say
- “RLM replaces RAG.” Say: “They solve different problems and can compose.”
