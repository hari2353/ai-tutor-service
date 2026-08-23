#!/usr/bin/env bash
# One-time setup, per clone. Run this after cloning, and after your friend clones.
#
# Git deliberately does not transmit hooks or merge drivers over the wire --
# they execute code, so every clone must opt in locally. Skipping this is why
# a merge would dump conflict markers into a 2.7 MB JSON file.
set -e
cd "$(dirname "$0")/.."

# `true` exits 0 and leaves the "ours" side in place, so git records a clean
# merge instead of writing conflict markers. The post-merge hook then reruns
# build_data.py, which rebuilds the aggregates from every fragment on disk --
# so the result is correct, not merely conflict-free.
git config merge.regen.name "regenerated from fragments by build_data.py"
git config merge.regen.driver "true"
git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true

echo "ok: merge driver 'regen' registered"
echo "ok: hooks path set to .githooks"
echo
echo "Generated files now merge without conflicts and rebuild automatically"
echo "after every pull. The fragments in app/data/cards and app/data/drillsets"
echo "remain the source of truth -- never hand-edit a generated file."
