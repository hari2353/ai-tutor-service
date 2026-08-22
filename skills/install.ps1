# Install the tutor skills into the user's account so they work in any session,
# not only when the working directory is this repo.
#
#   powershell -ExecutionPolicy Bypass -File skills\install.ps1
#
# The repo is the source of truth. ~/.claude/skills is a copy — re-run this
# after editing any SKILL.md, or the account copy silently goes stale.

$ErrorActionPreference = 'Stop'
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$dst = Join-Path $env:USERPROFILE '.claude\skills'

if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Path $dst -Force | Out-Null }

$n = 0
foreach ($d in Get-ChildItem -Path $src -Directory -Filter 'tutor-*') {
    $skill = Join-Path $d.FullName 'SKILL.md'
    if (-not (Test-Path $skill)) {
        Write-Warning "$($d.Name): no SKILL.md, skipped"
        continue
    }
    $target = Join-Path $dst $d.Name
    if (-not (Test-Path $target)) { New-Item -ItemType Directory -Path $target -Force | Out-Null }
    Copy-Item -Path $skill -Destination (Join-Path $target 'SKILL.md') -Force
    Write-Host "  installed  $($d.Name)"
    $n++
}

Write-Host ""
Write-Host "$n skills installed to $dst"
Write-Host "Restart Claude Code (or start a new session) to pick them up."
