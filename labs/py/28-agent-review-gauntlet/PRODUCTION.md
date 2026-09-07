# Production notes — the agent review gauntlet

## Where the checks come from

The 10-point checklist idea: when an org moves to AI-assisted authorship at scale, review capacity becomes the bottleneck. The response is a tiered gate — the cheap mechanical checks run on every push, and the expensive human judgment is spent only on what machines can't see. The eight checks here are the classic tier:

1. **has_tests** — the diff-touched-tests rule (a proxy for coverage on changed lines). Agents refactor freely and never feel obligated to update tests; tying test files to source files in the diff is the cheapest possible guard.
2. **no_secrets** — the one check every org runs whether or not AI is involved.
3. **error_handling / no_magic_numbers / naming / has_docstrings / complexity_gate** — the "readable by the next human" tier. Linter territory since the 1970s.
4. **hallucinated_api** — the agent-specific failure mode. Models trained on mixed codebases invent plausible APIs (`list.push_back()`), call methods that don't exist yet on the pinned interpreter version, or rename SDK methods between releases. **The realistic mitigation is an allowlist**: your imports are pinned, so the set of methods those imports provide is knowable — flag anything outside it. That's exactly what type checkers and strict linters do mechanically.

## What automated review catches vs what still needs a human

| Automated (this lab's tier) | Still needs a human |
|---|---|
| secrets, syntax, style, complexity thresholds | **does it actually solve the problem** |
| hallucinated calls against a pinned allowlist | is the *approach* right, or just the code |
| tests exist for changed files | do the tests *assert the right thing*, or just execute lines |
| naming/lint/docstring gates | is the design where the maintainer would have put it |
| coverage % thresholds | is the coverage *meaningful* (branch vs line) |
| SAST patterns | is this the *feature the customer asked for* |

The rule of thumb worth saying in an interview: automation catches **what the agent got wrong**; humans catch **what the agent got right for the wrong reason** — code that passes every check and still isn't what anyone wanted.

## What production adds over yours

- **Linters as CI gates, not regexes** — `ruff` (rule-per-line, hundreds of rules, configurable per-project via `pyproject.toml`) and `mypy --strict` (a real type graph, which subsumes the hallucinated-API check: `list.push_back` is a type error, not a suspicion). Your regex heuristics are the toy model of both.
- **Coverage gates** — `coverage.py` / `go test -cover` with a threshold on *changed lines* (`diff-cover`), which is the honest version of has_tests: not "a test file exists" but "these lines run under test".
- **Secrets scanners with entropy detection** — `gitleaks`, `trufflehog`, AWS Secrets Manager rotation. They catch the secret split across two lines and the high-entropy random string with no keyword; your regexes don't.
- **SAST** — `semgrep`, `CodeQL`, `bandit`: dataflow-aware checks (does user input reach that `open()`?), not line-patterns.
- **AST-based review tooling** — everything in this lab is implementable in the `ast` module in about the same LOC with zero false positives on formatting; semgrep lets you write AST patterns declaratively. The regex version exists here to make you *feel* the heuristic's failure modes.

## Where this actually runs

| Stage | What | Latency |
|---|---|---|
| IDE / agent loop | ruff + mypy on save, agent self-corrects before you see it | ms |
| pre-commit | ruff, gitleaks, no-merge-to-main guards | seconds |
| CI on every push | full lint + type + test + coverage gate + SAST | minutes |
| Org scale | `stacklok/mender` / `codeql` auto-fix PRs, review slots spent only on the human tier | — |

## The 3 questions an interviewer asks after you describe this

1. *"What's your false-positive strategy? Warn fatigue kills gates."* — blockers are only checks with near-zero FP rates (regex'd secrets, allowlist'd APIs); everything soft is a warn. A gate people ignore is worse than no gate.
2. *"Where does the allowlist come from — who maintains it?"* — derived, not curated: introspect the pinned dependencies' public interfaces in CI (`pip freeze` + `dir(module)`), so the allowlist is a build artifact, not a document that rots.
3. *"A check passes. Is the code good?"* — no: all eight passing says nothing about whether the code solves the problem. That's the line between the machine tier and the human tier, and the whole design is about spending humans only below that line.
