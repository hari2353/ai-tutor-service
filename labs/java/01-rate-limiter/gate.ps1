# Gate script: compile lib + (starter|solution) + tests, run the harness.
#   powershell -File gate.ps1            # starter  → must FAIL
#   $env:LAB_IMPL='solution'; gate.ps1   # solution → must PASS
param(
    [string]$Impl = ""
)
$ErrorActionPreference = "Stop"
if (-not $Impl) { $Impl = if ($env:LAB_IMPL -eq "solution") { "solution" } else { "starter" } }

if (-not (Get-Command javac -ErrorAction SilentlyContinue)) {
    Write-Host "SKIPPED - javac not installed"
    exit 3
}

$build = Join-Path $env:TEMP ("rate-limiter-build-" + $Impl)
if (Test-Path $build) { Remove-Item $build -Recurse -Force }
New-Item -ItemType Directory -Force -Path $build | Out-Null

$srcs = @(Get-ChildItem "lib", $Impl, "tests" -Recurse -Filter *.java | ForEach-Object { $_.FullName })
javac -encoding UTF-8 -d $build @srcs
if ($LASTEXITCODE -ne 0) { Write-Host "COMPILE FAILED ($impl)"; exit 1 }

java -cp $build com.tutor.ratelimit.test.RateLimitTest
exit $LASTEXITCODE
