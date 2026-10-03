# Lab 33: Selective Multi-Agent Orchestration

**Track:** T07 Agentic AI · **Time:** 2h · **XP:** 50
**Module:** `T07-selective-orchestration`

**You will build:** a deterministic router that selects from a bounded candidate set, abstains when confidence is insufficient, falls back after an availability failure, and accounts for every attempted candidate's cost and latency.

**You will be able to answer:** *"How would you route a request across specialists without turning routing into an unbounded, unmeasured second agent?"*

## Setup

```bash
cd labs/py/33-selective-orchestration
python -m venv .venv && .venv/Scripts/activate
pip install pytest
```

The implementation under test uses only the Python standard library. `pytest` is used only to run the lab tests.

## The spec

Implement `orchestration.py`:

1. `Candidate` describes a named worker, its normalized skill set, per-token cost, and fixed latency in milliseconds.
2. `SelectiveRouter(candidates, max_candidates, min_confidence)` keeps a copied candidate registry, rejects duplicate names and invalid limits, and never considers more than `max_candidates` workers for one request.
3. `rank(required_skills)` returns positive-overlap candidates in deterministic order: highest overlap first, then candidate name. It returns at most the configured bound.
4. Route confidence is deterministic: coverage is `top_overlap / required_skill_count`; if there is a second candidate, multiply coverage by `(top_overlap - second_overlap) / top_overlap`. A request with no matching skills has zero confidence.
5. `dispatch(required_skills, token_count, call)` abstains before invoking `call` when there is no match or confidence is below `min_confidence`. An abstention has no attempts, cost, or latency.
6. On a confident route, invoke `call(candidate, required_skills)`. `CandidateUnavailable` is an availability failure and permits trying the next ranked candidate in the bounded set. Other exceptions propagate as programming errors.
7. The result records the selected worker, confidence, abstention, fallback use, bounded candidate set, attempts, output, status, total cost, and total latency. Every attempted candidate is charged `token_count * cost_per_token` and its fixed latency, including failed attempts.
8. If every confident candidate is unavailable, return a failed result rather than pretending the request was answered. Do not retry outside the bounded candidate set.
9. The module must not sleep, use wall-clock time, read files, access a network, or import third-party packages.

## Run the tests

```bash
pytest tests/ -q                 # starter: MUST FAIL
pytest tests/ -q --solution      # reference: MUST PASS
```

## Stretch goals

1. Add a calibration helper that chooses `min_confidence` from a labeled validation set. *(Interview: "Where did your confidence threshold come from?")*
2. Add a per-tenant cost budget that turns a fallback into an explicit budget abstention. *(Interview: "Can a fallback chain violate a spend limit?")*
3. Add route-distribution and route-accuracy reporting against golden labels. *(Interview: "How do you detect silent misrouting?")*
4. Add a version to the candidate catalog and include it in every result. *(Interview: "How do you reproduce a route after a catalog change?")*
