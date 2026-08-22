---
name: tutor-lab
description: Generate a from-scratch, test-driven lab for the AI Tutor Service — starter stubs that fail, a reference solution that passes, a real pytest/go test/cargo test suite with an injectable clock, a README spec, and a PRODUCTION.md on how it is really done. Use when the user says /tutor-lab, "build a lab for X", "give me a hands-on exercise", or wants to implement a module's topic rather than read about it.
---

# tutor-lab

Reading a module teaches you the vocabulary. The lab is what makes you able to answer *"walk me through your implementation"* without hedging.

**Repo root** (`$ROOT`): the directory containing `CONTENT-STATUS.md`. Find it by walking up from your current working directory until that file appears; if you never find it, ask the user where the repo lives — do not guess a path.

## 1. Read the exemplar

`$ROOT/labs/py/01-circuit-breaker/` is the bar. Read `README.md`, `tests/conftest.py`, and `tests/test_resilience.py` before writing anything. Match its structure exactly.

## 2. Layout

```
labs/<lang>/<NN>-<slug>/
  README.md              what you build, the spec, setup, how to run, stretch goals
  starter/<file>         signatures + docstrings + `raise NotImplementedError`
  solution/<file>        the reference implementation
  tests/conftest.py      imports starter/ by default, solution/ with --solution
  tests/test_<file>.py   the suite
  PRODUCTION.md          how the real library does it, and what it adds
```

`<lang>` is one of `py java go rust ts infra`. `<NN>` is the next free number **within that language directory**, zero-padded.

## 3. The rules that make it a lab and not a tutorial

**The starter must fail and the solution must pass.** Both run against the same suite, selected at collection time. The Python pattern:

```python
def pytest_addoption(parser):
    parser.addoption("--solution", action="store_true")

def pytest_configure(config):
    which = "solution" if config.getoption("--solution") else "starter"
    path = ROOT / which / "<file>.py"
    spec = importlib.util.spec_from_file_location("<mod>", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["<mod>"] = mod
    spec.loader.exec_module(mod)
```

**No sleeping in tests.** Anything time-dependent takes an injectable clock — `SystemClock` and `FakeClock(t=0).advance(dt)` — and nothing calls `time.monotonic()` directly. A suite that sleeps is a broken suite; it is also the single most common thing an interviewer will poke at.

**No paid cloud, ever.** Local stack only:

| Need | Use |
|---|---|
| LLM | `ollama pull llama3.2`, `nomic-embed-text` |
| Vector / SQL | `pgvector/pgvector:pg17`, `qdrant/qdrant` |
| Docs / OLAP / cache | `mongo:7`, `clickhouse/clickhouse-server`, `redis:7` |
| AWS APIs | `localstack/localstack` |
| GPU work | local GPU or Colab free tier — state which, and how to shrink it |

**Tests assert behaviour, not implementation.** Test the state transitions, not the private attribute that stores them.

## 4. README.md contract

Open with, in this order:

```markdown
# Lab NN: <Title>

**Track:** <Tn Name> · **Time:** <N>h · **XP:** 50
**Module:** `<module-id>`

**You will build:** <one sentence>

**You will be able to answer:** *"<the actual interview question this unlocks>"*
```

Then: **Setup** (copy-pasteable, one dependency where possible) · **The spec** (numbered requirements, each independently testable) · **Run the tests** · **Stretch goals** (2-4, each tagged with the interview question it answers).

The spec is the contract. Write it so someone could implement from the spec alone with the tests hidden.

## 5. Verify by running it

```bash
cd labs/<lang>/<NN>-<slug>
python -m pytest tests/ -q                 # MUST fail — that is the point
python -m pytest tests/ -q --solution      # MUST pass
```

Do not report the lab done until you have seen both results. A lab whose solution fails is worse than no lab.

For Go: `go test ./...` with build tags or a `solution` package selector. For Rust: `cargo test` with a feature flag. Same contract, idiomatic mechanism.

## 6. Wire it up

- Add the `**Lab:** \`labs/<lang>/<NN>-<slug>/\`` line to the module's header in `curriculum/`.
- Labs are worth 50 XP (`XP["lab"]`); mention it so the user logs it in the app.
- If the lab earns one of the badges in `build_data.py` (`half-open`, `bulkheaded`, `hnsw-tuner`, `oom-slayer`, …), say which.

No rebuild is needed — labs are not in the index.

## Report

The paths written, the two pytest results verbatim, and any dependency the user must install.
