#!/usr/bin/env bash
# Full test suite. Run from anywhere:  bash app/tests/run.sh
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fail=0
skipped=0

# `python3` does not exist on a stock Windows install; `python` does. Pick
# whichever is present rather than failing at the first line on half the machines.
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || { echo "no python 3.9+ on PATH"; exit 1; }
echo "using $PY ($("$PY" --version 2>&1))"

echo; echo "── rebuilding data ──"; "$PY" "$ROOT/app/build_data.py" || fail=1
echo; echo "── app: DOM render + state ──"; node "$ROOT/app/tests/dom.test.js" "$ROOT" || fail=1
echo; echo "── app: SM-2 scheduler ──";     node "$ROOT/app/tests/sm2.test.js"  "$ROOT" || fail=1
echo; echo "── labs ──"
PY_OK=0
"$PY" -m pytest --version >/dev/null 2>&1 || PY_OK=1
if [ $PY_OK -ne 0 ]; then
  # do NOT let a missing dependency read as a pass. This step used to swallow
  # stderr and pipe to tail, so an absent pytest produced a silent ALL GREEN.
  # Not a pass and not a failure: the labs were never exercised. Track it
  # separately so the summary can never claim green for untested labs.
  echo "  SKIPPED — pytest not installed ($PY -m pip install pytest)"
  skipped=1
fi

# Non-python labs are gated by their own toolchain. A missing toolchain is a
# SKIPPED line — never a pass, never silently covered by green.
have() { command -v "$1" >/dev/null 2>&1; }

for d in "$ROOT"/labs/*/*/; do
  d="${d%/}"
  name="$(basename "$(dirname "$d")")/$(basename "$d")"

  if [ -f "$d/go.mod" ]; then
    have go || { echo "  SKIPPED $name - go not installed"; skipped=1; continue; }
    echo "  $name"
    out="$( cd "$d" && go test -tags solution ./... 2>&1 )"; rc=$?
    echo "$out" | tail -2 | sed 's/^/    /'
    [ $rc -eq 0 ] || fail=1

  elif [ -f "$d/Cargo.toml" ]; then
    have cargo || { echo "  SKIPPED $name - cargo not installed"; skipped=1; continue; }
    echo "  $name"
    out="$( cd "$d" && cargo test --features solution --quiet 2>&1 )"; rc=$?
    echo "$out" | grep 'test result' | tail -1 | sed 's/^/    /'
    [ $rc -eq 0 ] || fail=1

  elif [ -f "$d/package.json" ] && ls "$d"/tests/*.test.ts >/dev/null 2>&1; then
    have node || { echo "  SKIPPED $name - node not installed"; skipped=1; continue; }
    echo "  $name"
    entry="$(cd "$d/tests" && ls *.test.ts | head -1)"
    out="$( cd "$d" && CHUNK_IMPL=solution node --test --test-reporter tap "tests/$entry" 2>&1 )"; rc=$?
    echo "$out" | grep -E '^# (pass|fail)' | sed 's/^/    /'
    [ $rc -eq 0 ] || fail=1

  elif [ -f "$d/solution/com/tutor/ratelimit/TokenBucket.java" ] && [ -f "$d/gate.sh" ]; then
    have javac || { echo "  SKIPPED $name - javac not installed"; skipped=1; continue; }
    echo "  $name"
    out="$( cd "$d" && LAB_IMPL=solution bash gate.sh 2>&1 )"; rc=$?
    echo "$out" | grep '^passed=' | sed 's/^/    /'
    if [ $rc -eq 3 ]; then echo "    SKIPPED - javac not installed"; skipped=1
    elif [ $rc -ne 0 ]; then fail=1; fi

  elif [ -d "$d/tests" ] && ls "$d"/tests/*.py >/dev/null 2>&1; then
    [ $PY_OK -eq 0 ] || continue
    echo "  $name"
    out="$( cd "$d" && "$PY" -m pytest tests/ -q --solution 2>&1 )"; rc=$?
    echo "$out" | tail -2 | sed 's/^/    /'
    [ $rc -eq 0 ] || fail=1
  fi
done
echo; if [ $fail -ne 0 ]; then echo "FAILURES — see above";
elif [ "${skipped:-0}" -ne 0 ]; then echo "GREEN except SKIPPED items above (missing toolchain/pytest)";
else echo "ALL GREEN"; fi
exit $fail
