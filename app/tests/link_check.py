#!/usr/bin/env python3
"""Every `**Lab:** `path`` pointer in a module must resolve to a directory that
exists, and every lab must have the full five-part structure.

143 pointers once aimed at labs that were never built. A student clicking one
got nothing, and the repo read as more finished than it was. This check makes
that state impossible to commit silently.
"""
import glob, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
fail = 0

broken = []
for f in glob.glob(str(ROOT / 'curriculum/**/*.md'), recursive=True):
    txt = pathlib.Path(f).read_text(encoding='utf-8')
    for m in re.finditer(r'\*\*Lab:\*\* `([^`]+)`', txt):
        target = ROOT / m.group(1).rstrip('/')
        if not target.is_dir():
            broken.append((pathlib.Path(f).relative_to(ROOT), m.group(1)))

print(f"lab pointers: {len(broken)} broken")
for mod, tgt in broken[:20]:
    print(f"  BROKEN  {mod} -> {tgt}")
if broken:
    fail = 1

REQUIRED = ['README.md', 'PRODUCTION.md', 'starter', 'tests', 'solution']
# Each language keeps its five-part structure in its own idiomatic shape,
# mirroring how app/tests/run.ps1 discovers and runs them:
#   py       starter/ solution/ tests/conftest.py
#   go       starter.go+solution.go at root (build tags) OR starter/ solution/
#            subpackages, tests as root *_test.go
#   rust     src/starter.rs + src/solution.rs (features), tests/*.rs
#   ts       src/starter.ts + src/solution.ts, tests/*.test.ts
#   java     starter/ solution/ source trees, root gate.ps1 runs the tests
#   review-  a DIFF.md + EXPECTED-FINDINGS.md exercise, not a build lab:
#           exempt from the lab structure
GO_COMMON = ['README.md', 'PRODUCTION.md']
incomplete = []
for d in sorted(glob.glob(str(ROOT / 'labs/*/*/'))):
    p = pathlib.Path(d)
    lang = p.parent.name
    if lang == 'review-exercises':
        if not (p / 'DIFF.md').exists() or not (p / 'EXPECTED-FINDINGS.md').exists():
            incomplete.append((p.relative_to(ROOT), ['DIFF.md + EXPECTED-FINDINGS.md']))
        continue
    if (p / 'go.mod').exists():
        missing = [r for r in GO_COMMON if not (p / r).exists()]
        split_ok = ((p / 'starter.go').exists() and (p / 'solution.go').exists()) or \
                   ((p / 'starter').is_dir() and (p / 'solution').is_dir())
        if not split_ok:
            missing.append('starter/solution (root .go pair or subpackages)')
        if not list(p.glob('*_test.go')):
            missing.append('*_test.go (root-level Go tests)')
        if missing:
            incomplete.append((p.relative_to(ROOT), missing))
        continue
    if (p / 'Cargo.toml').exists():
        missing = [r for r in ('README.md', 'PRODUCTION.md') if not (p / r).exists()]
        src = p / 'src'
        if not ((src / 'starter.rs').exists() and (src / 'solution.rs').exists()):
            missing.append('src/starter.rs + src/solution.rs')
        if not list((p / 'tests').glob('*_test.rs')):
            missing.append('tests/*_test.rs')
        if missing:
            incomplete.append((p.relative_to(ROOT), missing))
        continue
    if (p / 'package.json').exists():
        missing = [r for r in ('README.md', 'PRODUCTION.md') if not (p / r).exists()]
        src = p / 'src'
        if not ((src / 'starter.ts').exists() and (src / 'solution.ts').exists()):
            missing.append('src/starter.ts + src/solution.ts')
        if not list((p / 'tests').glob('*.test.ts')):
            missing.append('tests/*.test.ts')
        if missing:
            incomplete.append((p.relative_to(ROOT), missing))
        continue
    if (p / 'gate.ps1').exists():  # java: gate.ps1 compiles starter|solution + runs tests
        missing = [r for r in ('README.md', 'PRODUCTION.md') if not (p / r).exists()]
        if not (p / 'starter').is_dir() or not (p / 'solution').is_dir():
            missing.append('starter/ + solution/ trees')
        if not (p / 'tests').is_dir():
            missing.append('tests/')
        if missing:
            incomplete.append((p.relative_to(ROOT), missing))
        continue
    missing = [r for r in REQUIRED if not (p / r).exists()]
    if missing:
        incomplete.append((p.relative_to(ROOT), missing))
    elif not list((p / 'tests').glob('conftest.py')):
        incomplete.append((p.relative_to(ROOT), ['tests/conftest.py']))

n_labs = len(glob.glob(str(ROOT / 'labs/*/*/')))
print(f"labs: {n_labs} total, {len(incomplete)} incomplete")
for lab, missing in incomplete:
    print(f"  INCOMPLETE  {lab} missing {', '.join(missing)}")
if incomplete:
    fail = 1

print("OK" if not fail else "FAIL")
sys.exit(fail)
