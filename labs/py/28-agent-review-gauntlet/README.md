# Lab 28: The Agent Review Gauntlet

**Track:** T28 AI-Assisted Architecture (Claude) · **Time:** 3h · **XP:** 50
**Module:** `T28-claude-architect`

**You will build:** an automated review checklist — `gauntlet.py` with eight code checks (secrets, error handling, magic numbers, naming, docstrings, complexity, hallucinated APIs, test coverage of the diff) and a `run_gauntlet(files, context)` gate where blockers fail and warns collect.

**You will be able to answer:** *"You ship with an AI writing most of the code. What do you actually check before it merges — and what can a machine check vs what still needs you?"*

## Setup

```bash
cd labs/py/28-agent-review-gauntlet
python -m pytest tests/ -q          # only dependency: pytest
```

## The spec

1. **`CheckResult`** — a dataclass (or dict) with `passed: bool`, `severity: "blocker" | "warn" | "ok"`, `note: str`. A check that flags nothing returns `passed=True, severity="ok"`.
2. **`CHECKLIST`** — an ordered list of `(check_fn, default_severity)` tuples. All eight checks below, each callable as `fn(name, code, context) -> CheckResult` where `name` is the file path, `code` its source, and `context` a dict that may carry `known_apis`.
3. **`has_tests`** — the diff must touch a test file for every source file touched: at least one path in `files` containing `test` and defining functions starting with `test_`. Source = code files (`.py`, `.js`, `.ts`, `.java`, `.go`); a README/docs-only changeset has no source files and passes. Works on the whole `files` dict at the file-set level.
4. **`no_secrets`** — hardcoded secrets: AWS key ids (`AKIA[0-9A-Z]{16}`), a password literal — `password = "..."`, `{"password": "..."}`, or the yaml-ish `password: "..."` — (a variable value like `os.environ[...]` is fine, and names merely containing "password" must not match), and PEM private key headers (`BEGIN PRIVATE KEY`, `BEGIN RSA PRIVATE KEY`, `BEGIN OPENSSH PRIVATE KEY`). Blocker.
5. **`error_handling`** — every `open(`, `requests.` call, or DB call (`sqlite3.connect`, `.execute`, `conn.cursor`) must sit inside a `with` block or a `try`. Bare call = warn.
6. **`no_magic_numbers`** — a bare numeric literal > 999 in a non-assignment position (not the RHS of `NAME = ...`, not a constant comparison against a documented constant, not a docstring or comment) = warn.
7. **`naming`** — `def` names snake_case, `class` names PascalCase. Warn.
8. **`has_docstrings`** — public functions (not `test_*`) must carry docstrings. Warn.
9. **`complexity_gate`** — functions longer than 30 lines (def line to end of body, blank lines included) or with more than 4 `return` statements = warn.
10. **`hallucinated_api`** — every attribute access `.attr` / method call `.method(` on a value must be in `context["known_apis"]` (a set of names like `{"append", "get", "connect", "execute", ...}`) or flagged as possible hallucination. Self-references (`.self.x`) and known-safe punctuation attributes (`real`, `imag`, `group`, `groups`) are exempt. Blocker. *The* agent-specific failure mode: plausible-looking APIs that don't exist — `list.push_back()`, `str.removeprefix` on an old interpreter, an SDK method renamed between versions. Bound to an allowlist.
11. **`run_gauntlet(files, context)` -> report** — `{passed: bool, findings: [{file, check, severity, note}]}`: runs the CHECKLIST for each file, blockers make `passed=False`, warns collect but never fail.
12. **Heuristics are fine** — you don't need a full parser. One honest regex-per-line pass is OK (that's how early linters worked). Document your misses in the starter docstrings. Do not document-limit-away the required cases above — all must work.

## Run the tests

```bash
pytest tests/ -v                  # against starter/ → FAILS. Make them pass.
pytest tests/ -v --solution      # against solution/ → passes
```

## Stretch goals

1. **Stacked delimiters** — allow `with` / `try` scopes to nest and continue matching (`with A:\n  with B:` where an open() under B is still guarded). *(Interview: "regex vs AST — when is a line-based tool good enough?")*
2. **Line-accurate findings** — report line numbers by tracking scope boundaries as you go; see how far you can push the no-AST heuristic before it misfires. *(Interview: "what's the false-positive cost of each approach?")*
3. **An eviction cache for the stack** — when a dedented line closes multiple scopes, pop to the right depth with O(1) whitespace math, not a search. *(Interview: "how does a text editor auto-dedent?")*
4. **Check-order priority** — make CHECKLIST priority-ordered (blockers first) and short-circuit a file once a blocker fires. Does that lose signal? *(Interview: "how do you keep a 10-point checklist fast enough to run on every push at org scale?")*
