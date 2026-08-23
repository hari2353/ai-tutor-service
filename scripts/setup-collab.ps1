# One-time setup, per clone. Run this after cloning, and after your friend clones.
#
# Git deliberately does not transmit hooks or merge drivers over the wire --
# they execute code, so every clone must opt in locally. Skipping this is why
# a merge would dump conflict markers into a 2.7 MB JSON file.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# `true` exits 0 and leaves the "ours" side in place, so git records a clean
# merge instead of writing conflict markers. The post-merge hook then reruns
# build_data.py, which rebuilds the aggregates from every fragment on disk --
# so the result is correct, not merely conflict-free.
git config merge.regen.name "regenerated from fragments by build_data.py"
git config merge.regen.driver "true"
git config core.hooksPath .githooks

Write-Host "ok: merge driver 'regen' registered"
Write-Host "ok: hooks path set to .githooks"
Write-Host ""
Write-Host "Generated files now merge without conflicts and rebuild automatically"
Write-Host "after every pull. The fragments in app/data/cards and app/data/drillsets"
Write-Host "remain the source of truth -- never hand-edit a generated file."
