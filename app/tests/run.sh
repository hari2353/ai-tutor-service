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
echo; echo "── lab pointers ──"
"$PY" "$ROOT/app/tests/link_check.py" | sed 's/^/  /' || fail=1

echo; echo "── labs ──"
if ! "$PY" -m pytest --version >/dev/null 2>&1; then
  # do NOT let a missing dependency read as a pass. This step used to swallow
  # stderr and pipe to tail, so an absent pytest produced a silent ALL GREEN.
  # Not a pass and not a failure: the labs were never exercised. Track it
  # separately so the summary can never claim green for untested labs.
  echo "  SKIPPED — pytest not installed ($PY -m pip install pytest)"
  skipped=1
else
  for d in "$ROOT"/labs/*/*/; do
    [ -d "$d/tests" ] || continue
    echo "  $(basename "$(dirname "$d")")/$(basename "$d")"
    out="$( cd "$d" && "$PY" -m pytest tests/ -q --solution 2>&1 )"; rc=$?
    echo "$out" | tail -2 | sed 's/^/    /'
    [ $rc -eq 0 ] || fail=1
  done
fi
echo; if [ $fail -ne 0 ]; then echo "FAILURES — see above";
elif [ "${skipped:-0}" -ne 0 ]; then echo "GREEN except labs (SKIPPED — pytest missing)";
else echo "ALL GREEN"; fi
exit $fail
