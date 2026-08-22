# Full test suite for Windows PowerShell 5.1+. Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File app\tests\run.ps1
# Mirrors app/tests/run.sh: rebuild data -> node tests -> labs (if pytest present).
$ErrorActionPreference = "Stop"
$ROOT = (Resolve-Path "$PSScriptRoot\..\..").Path
$fail = $false
$skipped = $false

# ---- pick a python 3.9+ (py launcher, python, python3) --------------------
$PY = ""
foreach ($c in @("python", "python3", "py")) {
  if (Get-Command $c -ErrorAction SilentlyContinue) {
    & $c -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { $PY = $c; break }
  }
}
if (-not $PY) { Write-Host "no python 3.9+ on PATH"; exit 1 }
$ver = & $PY --version 2>&1
Write-Host ""
Write-Host "using $PY ($ver)"

# ---- rebuild data -----------------------------------------------------------
Write-Host ""; Write-Host "-- rebuilding data --"
& $PY "$ROOT\app\build_data.py"
if ($LASTEXITCODE -ne 0) { $fail = $true }

# ---- node tests -------------------------------------------------------------
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host "node not found - cannot run DOM/SM-2 tests"; $fail = $true
} else {
  Write-Host ""; Write-Host "-- app: DOM render + state --"
  node "$ROOT\app\tests\dom.test.js" $ROOT
  if ($LASTEXITCODE -ne 0) { $fail = $true }
  Write-Host ""; Write-Host "-- app: SM-2 scheduler --"
  node "$ROOT\app\tests\sm2.test.js" $ROOT
  if ($LASTEXITCODE -ne 0) { $fail = $true }
}

# ---- review gate ------------------------------------------------------------
Write-Host ""; Write-Host "-- review gate --"
& $PY "$ROOT\app\tests\review_gate.py" | Select-Object -Last 3
if ($LASTEXITCODE -ne 0) { $fail = $true }

# ---- labs -------------------------------------------------------------------
Write-Host ""; Write-Host "-- labs --"
& $PY -m pytest --version >$null 2>&1
if ($LASTEXITCODE -ne 0) {
  # a missing pytest is NOT a pass and NOT a failure: the labs were never
  # exercised. Tracked separately so green can never cover untested code.
  Write-Host "  SKIPPED - pytest not installed ($PY -m pip install pytest)"
  $skipped = $true
} else {
  Get-ChildItem "$ROOT\labs" -Directory | ForEach-Object {
    $lang = $_
    Get-ChildItem $lang.FullName -Directory | ForEach-Object {
      if (-not (Test-Path "$($_.FullName)\tests")) { return }
      Write-Host ("  {0}/{1}" -f $lang.Name, $_.Name)
      Push-Location $_.FullName
      & $PY -m pytest tests/ -q --solution 2>&1 | Select-Object -Last 2 | ForEach-Object { Write-Host "    $_" }
      if ($LASTEXITCODE -ne 0) { $fail = $true }
      Pop-Location
    }
  }
}

Write-Host ""
if ($fail)        { Write-Host "FAILURES - see above"; exit 1 }
elseif ($skipped) { Write-Host "GREEN except labs (SKIPPED - pytest missing)" }
else              { Write-Host "ALL GREEN" }
exit 0
