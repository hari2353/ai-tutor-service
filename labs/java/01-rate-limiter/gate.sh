#!/usr/bin/env bash
# Gate script: compile lib + (starter|solution) + tests, run the harness.
#   bash gate.sh                  # starter  → must FAIL
#   LAB_IMPL=solution bash gate.sh  # solution → must PASS
set -u
IMPL="${1:-${LAB_IMPL:-starter}}"

command -v javac >/dev/null 2>&1 || { echo "SKIPPED - javac not installed"; exit 3; }

BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT

mapfile -t SRCS < <(find lib "$IMPL" tests -name '*.java')
javac -encoding UTF-8 -d "$BUILD" "${SRCS[@]}" || { echo "COMPILE FAILED ($IMPL)"; exit 1; }
java -cp "$BUILD" com.tutor.ratelimit.test.RateLimitTest
exit $?
