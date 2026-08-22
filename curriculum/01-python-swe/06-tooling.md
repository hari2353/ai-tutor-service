# Modern Python Tooling: uv, ruff, mypy --strict, pre-commit, and Packaging

> **Track:** T01 Python & SWE Craft · **Time:** 1.5h · **Prereqs:** T01-typing · **Updated:** 2026-08-03
> **Module id:** `T01-tooling` · **Tags:** tooling

## The 30-second version

`uv` (Astral, written in Rust) replaced the fragmented pip/pipenv/pyenv/virtualenv/poetry toolchain with a single binary that does dependency resolution, virtual environment management, Python version installation, and lockfile generation — its defining property is raw speed (dependency installs measured in the tens-to-hundreds of milliseconds versus pip's seconds-to-tens-of-seconds for the same resolution, via aggressive caching and a Rust-based resolver), and as of 2026 it's the default recommendation for new Python projects specifically because it collapses what used to be four or five separate tools with inconsistent interfaces into one consistent one. `ruff` (also Astral, also Rust) replaced the historical linting stack (`flake8` plus a dozen plugins, `isort`, `pyupgrade`, and increasingly `black` for formatting too) with a single binary fast enough (commonly cited around 200ms for a 100k-line-of-code repository) to run on every keystroke or every commit without friction, which changed the practical calculus of how strict a team's linting configuration can be — strict, comprehensive linting only survives in practice if it's fast enough to not be routinely skipped or disabled. `mypy --strict` enables every one of mypy's optional stricter checks at once (disallowing untyped function bodies, implicit `Any`, missing return type annotations, and more) and is meaningfully more likely to catch a real bug than mypy's lenient default mode, at the cost of requiring genuinely complete type coverage across a codebase, including third-party stub coverage — partial adoption (some modules strict, others not) is the normal, practical migration path rather than a flag-day switch. `pre-commit` runs a configured set of checks (ruff, mypy, and others) automatically before a commit is allowed to complete, which matters specifically because a check that only runs in CI, minutes after code was written, is caught far later and far more expensively (context-switched away, PR round-trip) than the same check failing instantly at commit time. Packaging in 2026 centers on `pyproject.toml` as the single source of project metadata, dependencies, and tool configuration, with the build backend (what actually produces a wheel/sdist) a separate, pluggable concern from the dependency-management tool (`uv`) that consumes that metadata.

## Why this gets asked

Because tooling choices are one of the fastest, lowest-effort signals of whether a candidate has shipped and maintained a real Python codebase recently versus learned Python at some earlier point and not kept current — the specific tools in this module (`uv`, `ruff`, `mypy --strict`) largely displaced an entire previous generation of tooling (`pip`+`virtualenv`, `flake8`+`black`+`isort`) within the last two to three years, and an interviewer asking "what's your Python toolchain" is checking whether that migration has actually happened for this candidate, not just whether they've heard the names. It's also a practical, low-drama way to probe engineering judgment: someone who can articulate *why* `ruff`'s speed specifically changes what linting rules are practical to enforce, or *why* `mypy --strict` adoption is normally incremental rather than all-at-once, demonstrates real hands-on experience with the tradeoffs, not just tool-name recognition.

---

## Lineage: past → present → future

**What came before.** Python's packaging and environment-management story was, for most of the language's history, a genuinely fragmented, multi-tool problem: `pip` for installing packages (with no built-in environment isolation), `virtualenv`/`venv` for creating isolated environments, `pyenv` for managing multiple Python interpreter versions, and separately, `pipenv` or `poetry` attempting to unify dependency resolution and lockfile generation with mixed community adoption and, in `pipenv`'s case specifically, well-documented performance and reliability complaints that never fully resolved. Linting had a similar multi-tool sprawl — `flake8` (itself a wrapper combining `pyflakes`, `pycodestyle`, and `mccabe`) plus a long tail of plugins for additional rule categories, `isort` for import sorting, `pyupgrade` for modernizing syntax, and `black` for formatting, each a separate dependency with its own configuration surface and its own (often noticeably slower, pure-Python) execution speed — a full lint pass on a large codebase could take long enough that many teams only ran the full suite in CI, not locally on every save or commit, which meant slow feedback loops and linting violations routinely discovered only after a PR was already open.

**Where it stands now.** `uv` (Astral, first released 2024) has become the dominant recommendation for new Python projects specifically because it consolidates dependency resolution, virtual environment creation, Python interpreter installation, and lockfile management into one Rust-based tool with dramatically faster performance than the tools it replaces — `uv init` scaffolds a `pyproject.toml`-based project, `uv add` updates dependencies and regenerates a `uv.lock` lockfile while also managing the virtual environment automatically, collapsing what used to require coordinating three or four separate tools into one consistent interface. `ruff` has similarly become the dominant linter/formatter choice, having absorbed the functionality of `flake8` plus most of its common plugins, `isort`, `pyupgrade`, and (via `ruff format`) increasingly `black`'s formatting role as well, all in one binary fast enough to run on every save without perceptible delay. `mypy` remains the most widely-used static type checker, though Astral's `ty` (a newer, Rust-based type checker following the same speed-focused pattern as `uv` and `ruff`) and Microsoft's `pyright` are both gaining adoption specifically as faster alternatives for very large codebases where `mypy`'s pure-Python implementation has a measurable check-time cost. `pre-commit` (the framework, not any single check) remains the standard way to wire these tools into the commit workflow, ensuring fast, cheap checks run locally before code is even committed, with slower or more expensive checks (a full test suite, a more exhaustive security scan) reserved for CI.

**Where it's heading.** The consolidation trend (fewer, faster, Rust-based tools replacing many slower, narrower Python-based ones) is likely to continue rather than reverse, with continued competition specifically in the type-checker space (`mypy` vs `pyright` vs `ty`) on check-time performance for large codebases — this is an area where switching costs are real (different checkers have historically had subtly different rule interpretations and edge-case behavior) but the performance gap is large enough to keep driving migration interest. Packaging standardization around `pyproject.toml` as the single metadata source (rather than a mix of `setup.py`, `setup.cfg`, and ad hoc configuration files) is a settled, mature direction with no indication of reversing, and the build-backend-versus-dependency-manager separation (a project can use `uv` for dependency management while any PEP 517-compliant backend actually builds the distributable package) is expected to remain the stable architectural pattern going forward.

---

## Mental model

```
OLD STACK (fragmented, multiple slow, pure-Python tools):
  pip (install, no env isolation) + virtualenv/venv (isolation) + pyenv (interpreter
  versions) + pipenv/poetry (dependency resolution + lockfiles, inconsistent adoption)
  flake8 (+ many plugins) + isort + pyupgrade + black -- 4-5 separate config surfaces,
  full lint pass slow enough that many teams only ran it in CI, not on every save

NEW STACK (consolidated, Rust-based, fast enough to run constantly):
  uv  = pip + virtualenv + pyenv + poetry/pipenv, ONE binary, ONE lockfile (uv.lock)
        install speed: ~100ms vs pip's ~30s for equivalent resolution (order of magnitude+)
  ruff = flake8 + isort + pyupgrade + (ruff format =~ black), ONE binary
        100k LOC repo lint: ~200ms -- fast enough for on-save/on-commit, every time

  SPEED IS NOT COSMETIC: a check that takes 30s only runs in CI, minutes after the
  code was written and the developer has context-switched away. A check that takes
  200ms runs on EVERY SAVE or EVERY COMMIT, catching the issue while context is still
  warm -- this is why ruff's speed changed how STRICT teams are willing to configure
  linting: strict rules are only practical if the cost of checking them is near-zero.

FEEDBACK LOOP SPEED, fastest to slowest (cheapest, most frequent checks first):
  editor/IDE (real-time)  -->  pre-commit hook (on commit, LOCAL, seconds)
       -->  CI (on push/PR, MINUTES, more expensive checks: full test suite, mypy --strict
            across the whole repo, security scans)
  put FAST checks as early/local as possible; SLOW checks belong in CI, not blocking
  every local commit
```

The one-line mental model: **the entire 2024-2026 Python tooling shift is fundamentally about raw execution speed removing the tradeoff between "strict/comprehensive checking" and "fast enough to run constantly" — tools that used to force a choice between the two no longer do, which is why teams that adopted this stack tend to run meaningfully stricter checks, more often, than teams still on the older, slower tools.**

---

## How it actually works

### `uv`: unified dependency management, and why the lockfile matters

`uv init` scaffolds a new project with a `pyproject.toml`; `uv add <package>` resolves and installs a dependency, updates `pyproject.toml`'s dependency list, and regenerates `uv.lock` — a lockfile pinning exact resolved versions (including transitive dependencies) for fully reproducible installs across machines and CI runners, a property `pip` alone (installing directly from a loosely-versioned `requirements.txt`) doesn't guarantee, since the same `requirements.txt` can resolve to different transitive dependency versions at different times as upstream packages release new versions. `uv` also manages Python interpreter installation directly (replacing `pyenv`'s role) and creates/manages the virtual environment automatically as part of the same workflow, rather than requiring a separate, manually-invoked `venv`/`virtualenv` step — the practical effect is that a new contributor to a `uv`-based project can go from a fresh clone to a fully reproducible, correctly-versioned working environment with a single command, rather than manually coordinating several distinct tools in the correct order.

### `ruff`: consolidated linting/formatting, and the specific tools it replaced

`ruff` reimplements the rule sets of `flake8` (and by extension `pyflakes`/`pycodestyle`), `isort` (import sorting), `pyupgrade` (modernizing syntax to use newer language features where applicable), and a large fraction of the broader `flake8` plugin ecosystem's common rules, all as native, compiled checks in one Rust binary — and `ruff format` additionally provides `black`-compatible code formatting in the same tool. This consolidation matters beyond convenience: a single tool with a single configuration section (`[tool.ruff]` in `pyproject.toml`) avoids the coordination problems of multiple separate tools potentially disagreeing with each other (an `isort`-preferred import order that a separate linter's rule doesn't recognize, for instance) and the meaningfully faster execution (commonly cited around 200ms for a 100k-line-of-code repository) is what makes running the *full* rule set on *every* save or commit practical, rather than needing to selectively enable only a subset of rules to keep check time tolerable.

### `mypy --strict`: what it actually enables, and why adoption is normally incremental

`mypy`'s default mode is deliberately permissive — it tolerates untyped function bodies, implicit `Any` in various positions, and several other gaps specifically to make initial adoption on an existing, partially-or-untyped codebase feasible without requiring a complete rewrite. `--strict` enables a substantial bundle of additional checks simultaneously (disallowing untyped function definitions, disallowing implicit `Any` from an unannotated import, requiring explicit `Optional` rather than implicit `None` defaults, and more), each individually toggleable but bundled together under `--strict` as the recommended "maximally safe" configuration. Because `--strict` requires genuinely complete type coverage (a single untyped function, or a third-party dependency lacking type stubs, can produce a cascade of new errors once strict mode is enabled), the standard practical adoption path is incremental: enable `--strict` scoped to specific, already-well-typed modules or a `mypy.ini`/`pyproject.toml` per-module override configuration, expanding strict coverage module by module as the codebase's type coverage genuinely improves, rather than flipping strict mode on for an entire large, partially-typed codebase all at once and being confronted with an overwhelming, undifferentiated error list.

### `pre-commit`: local, fast checks before code ever reaches CI

The `pre-commit` framework runs a configured list of hooks (typically including `ruff check`, `ruff format --check`, and often a scoped/fast subset of `mypy`) automatically whenever a developer runs `git commit`, blocking the commit if any hook fails — the core value proposition is catching a fixable issue (a lint violation, a formatting inconsistency) at the earliest, cheapest possible point in the feedback loop, before it's even committed, let alone pushed to a shared branch or reviewed by another engineer. This matters specifically because the cost of fixing an issue grows substantially the later it's caught: a lint error caught by an editor's real-time integration or a pre-commit hook costs seconds and zero context-switch; the same error caught only in CI minutes later costs a context switch back to code the developer has mentally moved on from, and if caught only in code review, it costs a reviewer's time and a round-trip delay as well. `pre-commit` hooks should generally be restricted to genuinely fast checks (linting, formatting, perhaps a narrowly-scoped type check) — a full test suite or an exhaustive `mypy --strict` pass across an entire large codebase is usually too slow for a per-commit hook and belongs in CI instead, where the slower feedback loop is an acceptable tradeoff for more comprehensive coverage.

### Packaging: `pyproject.toml` as the single metadata source, and the build-backend/dependency-manager split

`pyproject.toml` (standardized via PEP 518 and subsequently PEP 621 for project metadata specifically) consolidated what used to be split across `setup.py` (executable, imperative build/metadata logic), `setup.cfg` (declarative configuration), and various tool-specific config files, into one declarative file with well-defined sections (`[project]` for metadata and dependencies, `[build-system]` specifying which backend actually builds the distributable package, `[tool.ruff]`/`[tool.mypy]`/etc. for individual tool configuration). A useful distinction worth being precise about: the **build backend** (e.g., `setuptools`, `hatchling`, `flit-core`) is what actually produces a wheel or sdist from your source code and metadata, following the PEP 517 build-backend interface, while a **dependency management tool** like `uv` (or `poetry`) is a separate concern — resolving, installing, and locking dependencies for development — that reads and writes `pyproject.toml`'s `[project]` metadata but delegates the actual package-building step to whichever backend is configured in `[build-system]`; a project can freely mix, e.g., `uv` for day-to-day dependency management with `hatchling` as the configured build backend, since these are genuinely independent, pluggable pieces of the packaging story, not a single monolithic tool.

---

## Build it from scratch

```toml
# pyproject.toml -- a representative modern Python project configuration

[project]
name = "my-service"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "pydantic>=2.9",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "mypy>=1.13",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]   # pycodestyle, pyflakes, isort, pyupgrade,
                                              # bugbear, simplify -- ONE tool, ONE config
ignore = ["E501"]                            # line length handled by ruff format instead

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
strict = true
# per-module override for incremental strict-mode adoption -- the normal migration path:
[[tool.mypy.overrides]]
module = "legacy_module.*"
strict = false
disallow_untyped_defs = false
```

```yaml
# .pre-commit-config.yaml -- fast, local checks before every commit

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff          # lint
        args: [--fix]
      - id: ruff-format    # format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic]   # stubs/deps mypy needs to see for accurate checking
        files: ^src/                          # scope to fast-to-check, well-typed source only
```

```bash
# uv workflow -- one tool, one lockfile, from clone to running environment
uv init my-service                  # scaffold pyproject.toml
uv add fastapi pydantic             # resolve, install, update pyproject.toml + uv.lock
uv add --dev pytest mypy            # dev-only dependency group
uv run pytest                       # runs inside the managed venv automatically, no manual activate
uv lock --check                     # verify uv.lock is up to date with pyproject.toml (CI check)
```
The lab exercise sets up this exact configuration on a small sample project, then deliberately introduces a lint violation, a formatting inconsistency, and an untyped function to demonstrate each tool catching its respective category of issue at commit time via the configured `pre-commit` hooks, followed by scoping `mypy --strict` to only the `src/` directory and adding a per-module override for a deliberately "legacy" untyped module, to make the incremental-strict-adoption pattern concrete.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Enabling `mypy --strict` on an existing codebase produces hundreds of errors immediately, and the team abandons the effort | Strict mode was enabled globally, all at once, on a codebase without existing, comprehensive type coverage | Scope `--strict` to specific, already-well-typed modules first via per-module overrides in `pyproject.toml`, expanding strict coverage incrementally as more of the codebase is genuinely typed, rather than a flag-day switch |
| CI takes many minutes and developers routinely skip running checks locally before pushing, leading to a high rate of CI failures for basic, easily-fixable issues | Fast, cheap checks (linting, formatting) aren't wired into a local pre-commit hook, so they're only ever caught in the slower, later CI feedback loop | Add `pre-commit` with `ruff check` and `ruff format --check` as fast local hooks, reserving CI for genuinely slower checks (full test suite, comprehensive `mypy --strict` across the whole repo) |
| Two developers' machines produce different resolved dependency versions for "the same" `requirements.txt`, causing "works on my machine" bugs | No lockfile — `pip install -r requirements.txt` re-resolves transitive dependencies at install time, which can differ across time or machine even for an identical top-level requirements list | Migrate to `uv` (or another lockfile-based tool) and commit `uv.lock`, ensuring every install resolves to the exact same pinned versions regardless of when or where it runs |
| A `pre-commit` hook configuration includes the full test suite, and commits take 30+ seconds, leading developers to routinely use `--no-verify` to skip it | A slow, comprehensive check (a full test suite) was placed in the fast, local, per-commit feedback loop where only cheap checks belong | Move the full test suite to CI; keep `pre-commit` scoped to genuinely fast checks (sub-second linting/formatting, perhaps a narrowly-scoped type check on changed files only) |
| A build fails with confusing errors about "no build backend" or a wheel isn't produced correctly despite `uv` managing dependencies fine | `[build-system]` is missing or misconfigured in `pyproject.toml` — `uv` (or any dependency manager) manages dependencies but delegates actual package building to whatever backend is configured there | Explicitly configure `[build-system]` with a real backend (`hatchling`, `setuptools`, `flit-core`), understanding that dependency management and package building are separate, independently-configured concerns |

---

## Tradeoffs & when NOT to use it

- **Don't flip `mypy --strict` on for an entire large, partially-typed codebase in one commit.** The resulting error volume is typically too large to meaningfully triage at once, and teams routinely abandon the effort entirely after this experience — incremental, per-module adoption is the practically sustainable path, not a matter of preference.
- **Don't put slow checks (a full test suite, an exhaustive security scan) into a `pre-commit` hook.** This defeats the entire purpose of a fast local feedback loop, and developers will predictably start using `--no-verify` to bypass it once commits become annoyingly slow, which is a worse outcome (checks silently skipped entirely) than simply reserving slow checks for CI where they belong.
- **Don't skip committing a lockfile (`uv.lock` or equivalent) for anything beyond a throwaway script.** Reproducibility across developer machines, CI runners, and production deployments depends on it; a loosely-pinned `requirements.txt` alone reintroduces exactly the "works on my machine" class of bug lockfiles exist to eliminate.
- **Don't assume switching to `ruff`/`uv` is purely a drop-in replacement with zero migration cost for a codebase with substantial custom `flake8` plugin usage or `poetry`-specific configuration.** While `ruff` covers the large majority of common linting needs, a codebase relying on a specific, less-common `flake8` plugin without a `ruff`-native equivalent may need adjustment, and `poetry`-to-`uv` migration, while generally straightforward, still warrants verifying dependency resolution produces an equivalent lockfile before fully cutting over a critical production project.
- **Don't conflate the build backend with the dependency-management tool as if they were the same choice.** They're independently configurable, and confusing them (e.g., assuming switching dependency managers requires also switching build backends, or vice versa) can lead to unnecessary migration churn when only one half actually needed to change.

---

## Interview questions

### Q1 — Why does `ruff`'s raw execution speed matter beyond just "it's more convenient," in terms of what linting configuration a team is actually willing to enforce?
**Testing:** the causal link between tool speed and organizational linting strictness, not just "faster is nicer."
**Answer:** A linter slow enough that a full pass takes many seconds to tens of seconds effectively can only run in CI, minutes after code is written — this creates pressure to keep the enabled rule set narrower (to keep even that slower CI-only check tolerable) and means violations are caught late, after the developer's context has already moved on. A linter fast enough (roughly 200ms for 100k lines of code) to run on every save or every commit removes this pressure entirely — teams running `ruff` at this speed routinely enable a much broader, stricter rule set than they would have found tolerable under the older, slower tools, specifically because the cost of checking those additional rules is now close to zero regardless of how many are enabled.
**Follow-up trap:** *"Does this mean a team should always enable ruff's maximum possible rule set, given the speed is no longer a constraint?"* — not necessarily; while execution speed is no longer the limiting factor, some rules are genuinely more opinionated or contentious than others (some `flake8` plugin-derived rules have real disagreement about whether they represent good practice universally), so rule *selection* should still be a deliberate team decision based on actual value, not simply "enable everything because it's free" — removing the speed constraint expanded what's *practical*, not what's automatically *correct* for every team's style preferences.

### Q2 — Why does `mypy --strict` typically require an incremental, per-module adoption path rather than a single flag-day switch, mechanically?
**Testing:** understanding the specific way strict mode's bundled checks interact with partial type coverage.
**Answer:** `--strict` bundles many individually-toggleable checks (disallowing untyped function bodies, implicit `Any`, and others) that each depend on the codebase already having comprehensive, accurate type annotations to pass cleanly — a single untyped function, an untyped third-party dependency without stubs, or an existing loosely-typed module can each trigger a cascade of new errors once these checks are all enabled simultaneously, producing an error count large enough that meaningfully triaging all of them at once is often impractical. Scoping `--strict` to specific, already-well-typed modules (via per-module overrides) lets a team apply the stricter bar exactly where the codebase is ready for it, expanding coverage deliberately over time as more modules genuinely reach that bar.
**Follow-up trap:** *"If a team has the engineering time to do a full, one-time push to add complete type coverage everywhere, is a flag-day switch to --strict then reasonable?"* — yes, in that specific scenario the incremental path is a practical accommodation for limited time/resources, not a universal law — if a team can genuinely and correctly type the entire codebase in one coordinated effort (verified, not just attempted), enabling `--strict` globally afterward is entirely reasonable; the incremental approach exists specifically to handle the much more common case where that full-coverage effort isn't feasible all at once, not because incremental adoption is inherently superior in every circumstance.

### Q3 — What specific problem does a lockfile (`uv.lock`) solve that a loosely-versioned `requirements.txt` alone does not?
**Testing:** the reproducibility guarantee, precisely, not just "lockfiles are good practice."
**Answer:** A `requirements.txt` listing top-level dependencies with loose or no version pins (or even with top-level pins but no pinning of *transitive* dependencies) can resolve to different actual installed versions at different times or on different machines, since upstream packages continue releasing new versions that satisfy the same loose constraint — this produces the classic "works on my machine" class of bug, where two developers (or a developer and CI) end up with subtly different dependency trees despite believing they installed "the same" requirements. A lockfile pins the *exact* resolved version of every dependency, direct and transitive, guaranteeing that installing from the lockfile produces an identical dependency tree regardless of when or where the install happens, until the lockfile itself is deliberately regenerated.
**Follow-up trap:** *"If a security vulnerability is discovered in a transitive dependency, doesn't a lockfile make it harder to get the fix quickly, since versions are pinned?"* — this is a real, genuine tradeoff — a lockfile trades automatic pickup of new (potentially fixed) versions for reproducibility, meaning a security fix in a transitive dependency requires an explicit lockfile update (`uv lock --upgrade` or equivalent) rather than happening automatically on the next install — the correct practice is combining lockfiles with active dependency vulnerability scanning/alerting (e.g., Dependabot-style tooling) that prompts an explicit, reviewed lockfile update when a fix is available, rather than treating pinning as a reason to never update, or removing pinning as a way to "auto-fix" vulnerabilities at the cost of losing reproducibility.

### Q4 — Why should a full test suite generally not be included in a `pre-commit` hook, even though "more checks before commit" sounds strictly safer?
**Testing:** the local-fast-checks vs. CI-slow-checks tradeoff, and the actual behavioral consequence of getting it wrong.
**Answer:** `pre-commit` hooks run synchronously, blocking every single commit until they complete — a full test suite is typically far slower than a linter/formatter pass, and once commits become slow and annoying enough, developers predictably start using `git commit --no-verify` to bypass the hooks entirely, which means *all* the hooks (including the genuinely fast, valuable ones) get silently skipped, not just the slow test suite specifically — the actual outcome of over-loading pre-commit is often "checks stop running altogether in practice," a worse result than simply keeping pre-commit fast and reserving the test suite for CI, where a slower feedback loop is an acceptable, expected tradeoff.
**Follow-up trap:** *"Is there ever a legitimate case for including a subset of tests in a pre-commit hook?"* — yes, if the subset is genuinely fast (e.g., a small number of pure unit tests with no I/O, completing in well under a second) and specifically scoped to changed files, this can be reasonable — the actual principle isn't "tests never belong in pre-commit," it's "whatever is in pre-commit must stay fast enough that developers never feel compelled to bypass it," which is a speed threshold, not a strict prohibition on any particular category of check.

### Q5 — Explain the distinction between a build backend and a dependency management tool, with a concrete example of how they compose.
**Testing:** the packaging architecture split, precisely, since this is a common point of confusion.
**Answer:** A build backend (e.g., `hatchling`, `setuptools`, `flit-core`) is the component that actually transforms your source code and `pyproject.toml` metadata into a distributable artifact (a wheel or sdist), following the PEP 517 build-backend interface — this is specified in `pyproject.toml`'s `[build-system]` section. A dependency management tool (`uv`, or `poetry`) handles a separate concern: resolving, installing, and locking dependencies for local development and CI, reading/writing the `[project]` section's metadata — but when it comes time to actually *build* a distributable package, it delegates that work to whatever backend `[build-system]` specifies, rather than doing the building itself. A project can freely use `uv` for all its day-to-day dependency management while configuring `hatchling` as the build backend, since these are independent, composable pieces of the packaging pipeline.
**Follow-up trap:** *"If a team wants to switch from uv to poetry (or vice versa) for dependency management, does that require also changing the build backend?"* — no, not necessarily; since the two concerns are independently configured, switching the dependency-management tool doesn't inherently require switching `[build-system]`'s backend, provided the new dependency-management tool is compatible with reading/writing standard `pyproject.toml` `[project]` metadata (which both `uv` and `poetry` are, broadly) — conflating the two as a single, coupled choice can lead to unnecessary migration work when only the dependency-management half actually needed to change.

### Q6 — A team migrating from `pip`/`requirements.txt` to `uv` finds that `uv`'s dependency resolution produces a different set of transitive dependency versions than their old, manually-curated `requirements.txt` had pinned. Is this a bug in `uv`, and how should the team handle it?
**Testing:** understanding that a resolver producing different results than a previously hand-maintained file isn't inherently wrong, and the correct verification process.
**Answer:** Not necessarily a bug — a hand-curated or previously-`pip`-resolved `requirements.txt` reflects whatever versions happened to resolve at some point in the past (or were manually adjusted over time), while `uv`'s resolver, run fresh, will resolve to whatever versions currently satisfy the declared constraints, which can legitimately differ, especially if the constraints themselves were loose. The correct handling is to review the newly-generated `uv.lock` deliberately (checking for genuinely breaking version changes, not just "it's different from before"), run the full test suite against the new resolution, and only then commit the new lockfile as the going-forward source of truth — treating "different from the old file" as automatically wrong skips the actual verification step that matters.
**Follow-up trap:** *"What if the team wants to guarantee the exact same versions as the old requirements.txt for a lower-risk migration, rather than accepting a fresh resolution?"* — `uv` can be pointed at the existing pinned versions as constraints during an initial migration (treating the old `requirements.txt`'s pins as the starting resolution target) to produce a lockfile matching the prior known-working state as closely as possible, decoupling the tooling migration itself from any dependency-version changes — this is a reasonable, lower-risk approach for a critical production system where the team wants to validate the tooling change in isolation before separately, deliberately choosing to also pick up newer dependency versions.

### Q7 — Why does `pyproject.toml` consolidate configuration that used to live in `setup.py`, `setup.cfg`, and various tool-specific files, and what real problem did the older fragmented approach cause?
**Testing:** the motivation behind `pyproject.toml` standardization (PEP 518/621), not just "it's the new way."
**Answer:** `setup.py` being an executable Python script (rather than static, declarative data) meant tools needed to actually *execute* arbitrary code just to discover a package's basic metadata or dependencies, which is slow, potentially unsafe (arbitrary code execution as a side effect of just inspecting metadata), and made static analysis/tooling around package metadata unreliable, since the same script could produce different metadata depending on the environment it happened to run in. `setup.cfg` improved on this for some cases by being declarative, but the ecosystem still had metadata and tool configuration scattered across multiple files with inconsistent conventions between different tools' expectations. `pyproject.toml`, standardized as a single, purely declarative, static TOML file, gives every tool a single, predictable place to read project metadata and its own configuration from, without needing to execute any code, which is both safer and dramatically faster for tooling to consume.
**Follow-up trap:** *"Does the move to pyproject.toml mean setup.py is now always wrong to have in a project?"* — not entirely; some packages still include a minimal `setup.py` for specific, legitimate dynamic-build-step needs (e.g., compiling a C extension with build steps genuinely difficult to express declaratively) — but for the overwhelming majority of pure-Python packages, a `setup.py` is no longer necessary at all and its presence in a modern project is more often legacy carryover than a deliberate, justified choice, worth questioning rather than assuming it's still required by default.

### Q8 — Design question: you're setting up a new Python project from scratch for a small team, and want to establish a tooling baseline (dependency management, linting, type checking, pre-commit) that balances strictness with practical day-to-day friction. Walk through your choices and reasoning.
**Testing:** applying the whole module's set of tradeoffs to a coherent, justified initial setup, not just listing tool names.
**Answer:** Use `uv` for dependency management (fast, single-tool, lockfile-based reproducibility from day one, no migration debt later). Configure `ruff` with a reasonably broad rule selection (`E`, `F`, `I`, `UP`, `B` at minimum — pycodestyle, pyflakes, isort, pyupgrade, bugbear) plus `ruff format`, wired into `pre-commit` so both run on every commit given their near-zero cost. For `mypy`, start with `--strict` enabled by default for all *new* code going forward (since there's no existing partially-typed codebase burden to work around at project inception — the flag-day-versus-incremental tradeoff mostly applies to *existing* codebases, not greenfield ones), keeping the `mypy` pre-commit hook scoped to fast enough execution that it doesn't meaningfully slow commits, with a full-repo `mypy --strict` pass also running in CI as a backstop. Keep the full test suite out of `pre-commit` entirely, running it in CI on every push/PR instead.
**Follow-up trap:** *"If the team later brings in a large, less-strictly-typed third-party codebase as a git submodule or vendored dependency, does this baseline configuration still work cleanly?"* — likely not without adjustment; the newly-added code probably won't satisfy the project's established `--strict` bar immediately, so it would need an explicit per-module override (excluding or relaxing strictness for that specific vendored path) rather than either failing CI on code the team doesn't control, or weakening the whole project's strictness bar to accommodate it — this is exactly the kind of situation the per-module override mechanism exists for, and recognizing it as a scoping problem (not a reason to abandon strict mode project-wide) is the correct response.

### Q9 — Why might a team choose `pyright` or `ty` over `mypy` specifically for a very large codebase, and is this purely a speed decision?
**Testing:** recognizing the performance motivation while also acknowledging real switching-cost considerations, not treating it as a purely one-sided choice.
**Answer:** `mypy`'s pure-Python implementation has a measurable check-time cost that scales with codebase size, and for very large codebases this can meaningfully slow both local development feedback and CI — `pyright` (TypeScript-based, from Microsoft) and `ty` (Astral's newer, Rust-based checker following the same speed-focused pattern as `uv`/`ruff`) both offer substantially faster check times, which is the primary driver for considering a switch. It's not purely a speed decision, though — different type checkers have historically had subtly different interpretations of ambiguous or edge-case typing scenarios (a program that passes one checker cleanly might surface new warnings under another), so switching checkers on an existing, sizeable codebase carries real migration risk and effort (re-triaging any newly-surfaced differences), not just a drop-in speed upgrade.
**Follow-up trap:** *"If pyright and ty both check a codebase and disagree on whether a specific piece of code is correctly typed, how would you resolve which one is 'right'?"* — check both checkers' interpretation against the actual PEP-defined typing specification (PEP 484 and its extensions) for the specific construct in question, since type-checker behavior is ultimately supposed to conform to that shared specification, not to either tool's independent judgment — in genuinely ambiguous or under-specified areas of the typing spec, this can be a legitimate area of disagreement between checkers with no single definitive answer, in which case the practical resolution is picking one checker as the team's source of truth and being consistent about it, rather than trying to satisfy every checker's interpretation simultaneously.

### Q10 — A team's `pre-commit` configuration includes `mypy --strict` scoped to the entire repository, and commits have become slow enough that engineers are frustrated. What specific changes would you make, and in what order would you try them?
**Testing:** the practical remediation process, correctly prioritized (least disruptive first).
**Answer:** First, scope the `mypy` pre-commit hook to only changed files (many `pre-commit` hook configurations support this via `files`/`types` filtering, or by relying on `pre-commit`'s own changed-file detection) rather than re-checking the entire repository on every commit, which is often the single largest, least disruptive fix. Second, if per-file scoping alone isn't sufficient (e.g., `mypy`'s own incremental-mode caching isn't being leveraged effectively), verify `mypy`'s incremental cache is actually being used and persisted between runs rather than being invalidated unnecessarily. Third, and only if the above don't bring commit time to an acceptable level, move the full-repository `mypy --strict` pass out of `pre-commit` entirely and into CI, keeping only a fast, scoped subset (or none at all) as a local pre-commit check — this is the most disruptive option (losing local, pre-commit-time type-check feedback for the full repo) and should be the last resort, not the first response.
**Follow-up trap:** *"If moving mypy out of pre-commit entirely is the last resort, why not just start there since it definitively solves the slow-commit problem?"* — because it also removes real, valuable feedback (a genuine type error surfaced at commit time, before the code is even pushed) that developers would otherwise lose, pushing that feedback to the slower CI loop where it costs a context switch to address — trying the less disruptive scoping/caching fixes first preserves as much of the fast local feedback loop's value as possible, and jumping straight to "remove it from pre-commit" sacrifices that value more readily than the problem actually requires, if a scoping fix would have sufficiently solved the speed issue on its own.

---

## Red flags that fail you

- Cannot explain why `ruff`'s speed specifically enabled teams to run stricter linting than the older, slower tool stack allowed in practice.
- Recommends flipping `mypy --strict` on for an entire existing codebase in one step, without mentioning incremental, per-module adoption.
- Doesn't know what a lockfile solves versus a loosely-versioned `requirements.txt`, or can't explain the reproducibility gap concretely.
- Puts (or defends putting) a full test suite inside a `pre-commit` hook without acknowledging the fast-local/slow-CI tradeoff.
- Conflates the build backend with the dependency-management tool as if switching one requires switching the other.
- Cannot name what specific older tools `uv` and `ruff` each replaced, or treats them as arbitrary brand preferences rather than consolidations with a specific rationale.

---

## Cheat card

```
UV (Astral, Rust): replaces pip+virtualenv+pyenv+poetry/pipenv -- ONE binary, ONE lockfile
  (uv.lock). uv init/add/run -- manages venv + interpreter version automatically.
  install speed ~100ms vs pip's ~30s for equivalent resolution -- ORDER OF MAGNITUDE+ faster
  LOCKFILE solves: reproducible EXACT transitive dependency versions across machines/time
  (loose requirements.txt can silently re-resolve differently) -- tradeoff: security fixes
  in transitive deps need explicit lockfile regen, not automatic pickup

RUFF (Astral, Rust): replaces flake8(+plugins)+isort+pyupgrade+(ruff format ~ black)
  ~200ms for 100k LOC -- fast enough for EVERY save/commit, not just CI
  SPEED IS CAUSAL, not cosmetic: removes the old tradeoff between "strict rules" and
  "fast enough to run constantly" -- teams on ruff run stricter configs as a direct result

MYPY --STRICT: bundles many checks (no untyped defs, no implicit Any, etc.) -- requires
  COMPLETE type coverage to pass cleanly. Flag-day switch on an existing partially-typed
  codebase = error avalanche, commonly abandoned. NORMAL path: per-module overrides in
  pyproject.toml, incremental strict-coverage expansion. Greenfield projects: strict from
  day one is fine (no existing-code burden to work around).
  ALTERNATIVES: pyright (Microsoft), ty (Astral, Rust) -- faster on very large codebases,
  but real switching cost (subtly different edge-case rule interpretations)

PRE-COMMIT: fast LOCAL checks (ruff, scoped mypy) BEFORE commit -- catches issues while
  context is warm, cheapest point in the feedback loop. NEVER put a full test suite or
  slow exhaustive scan here -- devs will start using --no-verify, silently skipping
  ALL hooks, not just the slow one. Slow/comprehensive checks belong in CI.
  Feedback loop, fastest->slowest: editor (realtime) -> pre-commit (seconds, LOCAL) -> CI (minutes)

PACKAGING: pyproject.toml = single declarative metadata source (PEP 518/621), replaced
  setup.py's execute-code-to-get-metadata problem (slow, unsafe, environment-dependent)
  BUILD BACKEND (hatchling/setuptools/flit-core, in [build-system]) = builds the wheel/sdist
  DEPENDENCY MANAGER (uv/poetry) = resolves/installs/locks deps, delegates BUILDING to backend
  these are INDEPENDENT, composable choices -- switching one doesn't require switching the other
```

## Sources

- [uv — Astral documentation](https://docs.astral.sh/uv/) — accessed 2026-08-03
- [ruff — Astral documentation](https://docs.astral.sh/ruff/) — accessed 2026-08-03
- [mypy: The mypy command line — strict mode documentation](https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict) — accessed 2026-08-03
- [pre-commit documentation](https://pre-commit.com/) — accessed 2026-08-03
- [PEP 621 — Storing project metadata in pyproject.toml](https://peps.python.org/pep-0621/) — accessed 2026-08-03
- [Modern Python Tooling 2026: uv, Ruff, mypy Complete Guide](https://softaims.com/blog/modern-python-tooling-uv-ruff-mypy-2026) — accessed 2026-08-03
- [Modern Python Tooling in 2026 — uv, Ruff, ty, and the New Toolchain](https://blog.rajpoot.dev/posts/python/modern-python-tooling-uv-ruff-2026/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
