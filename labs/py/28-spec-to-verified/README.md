# Lab 28: Spec → Build → Verify

**Track:** T28 AI-Assisted Architecture (Claude) · **Time:** 2h · **XP:** 50
**Module:** `T28-spec-driven-dev`

**You will build:** the spec-driven development loop as executable code — a `Spec` that parses requirements and acceptance criteria, a `verify` that judges an implementation against the spec and nothing else, and a `run_spec` loop that builds, verifies, and feeds failures back until green or out of rounds.

**You will be able to answer:** *"Why does an agent-built feature pass review and still be wrong — and what does a spec have to contain for 'done' to be falsifiable?"*

## Setup

```bash
cd labs/py/28-spec-to-verified
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

The mini spec format — headers, prose and blank lines are ignored; only `REQ`/`ACCEPT` lines with a colon are the contract:

```
REQ <id>: <description>          → spec.requirements = {id: description}
ACCEPT <req_id>: <criterion>     → spec.criteria = {req_id: [criterion, ...]}
```

1. **`Spec(text)`** — parse requirements and acceptance criteria into `.requirements` and `.criteria`. Malformed lines (no colon) drop silently. Multiple `ACCEPT` lines for one requirement append in order.
2. **`verify(requirements, criteria, implementation)`** — judge the builder's self-report (`{req_id: {criterion: bool}}`) against the spec's criteria only. Report: `{req_id: {"passed": bool, "failed_criteria": [...]}}`. A criterion the report never mentions is failed. **A requirement with NO criteria fails by default — unverifiable is not done.**
3. **`run_spec(spec, builder, max_rounds=3)`** — the loop: builder runs (round 1: `builder(requirements)`; later rounds: `builder(requirements, prev_implementation, report)` — the failure report is fed back), verify runs, repeat until all pass or rounds exhaust. Empty spec: builder never runs, `rounds == 0`, trivially passed. Returns `{"implementation", "rounds", "all_passed"}`.
4. **Hallucination guard** — any requirement id in the implementation that is not in the spec is collected under the report's `"hallucinated"` key, gets no report entry, and counts as neither pass nor fail. The agent "finished" work nobody asked for; you need to *see* it, not score it.

## Run the tests

```bash
pytest tests/ -q          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -q --solution`

## Stretch goals

1. **EARS criteria** — parse `WHEN <trigger> THE SYSTEM SHALL <response>` lines as criteria too. *(Interview: "structured requirement syntaxes — when do they pay?")*
2. **Coverage gate** — a criterion must be *bound to a test*, not a self-report: implementation values become `{criterion: test_name}` and verify executes the named tests. *(Interview: "how do you stop criteria passing vacuously?")*
3. **Mutation check** — flip each `True` in a passing implementation; if the report stays green, the criterion was vacuous. *(Interview: "what do mutation tests buy that coverage doesn't?")*
4. **Diff scope gate** — like A6 in the module: the builder returns a list of touched files, and any file not named in the spec's contract fails the round. *(Interview: "how do you catch scope leakage mechanically?")*
