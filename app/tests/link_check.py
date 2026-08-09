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
incomplete = []
for d in sorted(glob.glob(str(ROOT / 'labs/*/*/'))):
    p = pathlib.Path(d)
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
