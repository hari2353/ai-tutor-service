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

# ---- security gate (always runs; stdlib-only) --------------------------------
Write-Host ""; Write-Host "-- security & privacy gate --"
& $PY "$ROOT\scripts\security_check.py"
if ($LASTEXITCODE -ne 0) { $fail = $true }

# ---- unit + integration tests (pytest) ---------------------------------------
& $PY -m pytest --version >$null 2>&1
if ($LASTEXITCODE -eq 0) {
  Write-Host ""; Write-Host "-- unit: build_data pipeline --"
  Push-Location $ROOT
  & $PY -m pytest app/tests/test_build_data.py -q 2>&1 | Select-Object -Last 2 | ForEach-Object { Write-Host "    $_" }
  if ($LASTEXITCODE -ne 0) { $fail = $true }
  Pop-Location
  Write-Host ""; Write-Host "-- integration: full pipeline as subprocesses --"
  Push-Location $ROOT
  & $PY -m pytest app/tests/test_pipeline.py -q 2>&1 | Select-Object -Last 3 | ForEach-Object { Write-Host "    $_" }
  if ($LASTEXITCODE -ne 0) { $fail = $true }
  Pop-Location
} else {
  # a missing pytest is NOT a pass and NOT a failure: these suites were never
  # exercised. Tracked separately so green can never cover untested code.
  Write-Host ""; Write-Host "  SKIPPED unit+integration - pytest not installed ($PY -m pip install pytest)"
  $skipped = $true
}

# ---- labs -------------------------------------------------------------------
# Python labs run via pytest --solution. Other languages are gated by their
# own toolchain: go.mod → go test -tags solution, Cargo.toml → cargo test
# --features solution, package.json → node --test with CHUNK_IMPL=solution,
# starter/+solution/ java dirs → per-lab gate.ps1. A missing toolchain is a
# SKIPPED line — never a pass and never covered by green.
Write-Host ""; Write-Host "-- labs --"
& $PY -m pytest --version >$null 2>&1
if ($LASTEXITCODE -ne 0) {
  # a missing pytest is NOT a pass and NOT a failure: the labs were never
  # exercised. Tracked separately so green can never cover untested code.
  Write-Host "  SKIPPED - pytest not installed ($PY -m pip install pytest)"
  $skipped = $true
}
Get-ChildItem "$ROOT\labs" -Directory | ForEach-Object {
  $lang = $_
  Get-ChildItem $lang.FullName -Directory | ForEach-Object {
    $lab = $_.FullName
    $name = "{0}/{1}" -f $lang.Name, $_.Name

    if ((Test-Path "$lab\tests") -and (Get-ChildItem "$lab\tests" -Filter *.py -ErrorAction SilentlyContinue)) {
      & $PY -m pytest --version >$null 2>&1
      if ($LASTEXITCODE -eq 0) {
        Write-Host "  $name"
        Push-Location $lab
        & $PY -m pytest tests/ -q --solution 2>&1 | Select-Object -Last 2 | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) { $fail = $true }
        Pop-Location
      }
      return
    }

    if (Test-Path "$lab\go.mod") {
      if (-not (Get-Command go -ErrorAction SilentlyContinue)) { Write-Host "  SKIPPED $name - go not installed"; $skipped = $true; return }
      Write-Host "  $name"
      Push-Location $lab
      & go test -tags solution ./... 2>&1 | Select-Object -Last 2 | ForEach-Object { Write-Host "    $_" }
      if ($LASTEXITCODE -ne 0) { $fail = $true }
      Pop-Location
      return
    }

    if (Test-Path "$lab\Cargo.toml") {
      if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { Write-Host "  SKIPPED $name - cargo not installed"; $skipped = $true; return }
      Write-Host "  $name"
      Push-Location $lab
      & cargo test --features solution --quiet 2>&1 | Select-String 'test result' | ForEach-Object { Write-Host "    $_" }
      if ($LASTEXITCODE -ne 0) { $fail = $true }
      Pop-Location
      return
    }

    if (Test-Path "$lab\package.json") {
      if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Write-Host "  SKIPPED $name - node not installed"; $skipped = $true; return }
      Write-Host "  $name"
      $env:CHUNK_IMPL = "solution"
      Push-Location $lab
      node --test --test-reporter tap tests/chunking.test.ts 2>&1 | Select-String '^# (pass|fail)' | ForEach-Object { Write-Host "    $_" }
      if ($LASTEXITCODE -ne 0) { $fail = $true }
      Pop-Location
      Remove-Item Env:\CHUNK_IMPL -ErrorAction SilentlyContinue
      return
    }

    if ((Test-Path "$lab\solution") -and (Test-Path "$lab\gate.ps1")) {
      if (-not (Get-Command javac -ErrorAction SilentlyContinue)) { Write-Host "  SKIPPED $name - javac not installed"; $skipped = $true; return }
      Write-Host "  $name"
      Push-Location $lab
      $env:LAB_IMPL = "solution"
      powershell -ExecutionPolicy Bypass -File gate.ps1 2>&1 | Select-String '^passed=' | ForEach-Object { Write-Host "    $_" }
      Remove-Item Env:\LAB_IMPL -ErrorAction SilentlyContinue
      Pop-Location
      if ($LASTEXITCODE -eq 3) { Write-Host "    SKIPPED - javac not installed"; $skipped = $true; return }
      if ($LASTEXITCODE -ne 0) { $fail = $true }
      return
    }
  }
}

Write-Host ""
if ($fail)        { Write-Host "FAILURES - see above"; exit 1 }
elseif ($skipped) { Write-Host "GREEN except SKIPPED items above (missing toolchain/pytest)" }
else              { Write-Host "ALL GREEN" }
exit 0
