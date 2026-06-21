# Full project test run (stage 14) - Windows PowerShell variant.
# Equivalent of run_all_tests.sh. Messages are ASCII so the script parses
# correctly under Windows PowerShell 5.1 regardless of console codepage.
#
# Run from the Konfiguratsiya/deploy directory:
#   powershell -ExecutionPolicy Bypass -File run_all_tests.ps1
$ErrorActionPreference = "Stop"

$DeployDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$KonfigDir = (Resolve-Path (Join-Path $DeployDir "..")).Path
$MicroserviceDir = (Resolve-Path (Join-Path $KonfigDir "..\Микросервис_IRT")).Path
$Generator = Join-Path $KonfigDir "fixtures\synthetic_data_generator.py"

# Interpreter selection: uv -> local .venv -> system python.
$VenvPy = Join-Path $MicroserviceDir ".venv\Scripts\python.exe"
$VenvRuff = Join-Path $MicroserviceDir ".venv\Scripts\ruff.exe"
$VenvMypy = Join-Path $MicroserviceDir ".venv\Scripts\mypy.exe"

if (Test-Path $VenvPy) {
    $Py = $VenvPy; $Ruff = $VenvRuff; $Mypy = $VenvMypy
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    $Py = "uv"; $Ruff = "uv"; $Mypy = "uv"
} else {
    $Py = "python"; $Ruff = "ruff"; $Mypy = "mypy"
}

# Prefix used when the tool is invoked via uv ("uv run <tool>").
function Get-Prefix($Tool) {
    if ($Tool -eq "uv") { return @("run") } else { return @() }
}

Write-Output "==> Microservice: $MicroserviceDir"
Set-Location $MicroserviceDir

Write-Output "==> [1/4] ruff check"
& $Ruff @(Get-Prefix $Ruff) "check" "app" "tests"
if ($LASTEXITCODE -ne 0) { throw "ruff check failed" }

Write-Output "==> [2/4] pytest (unit + integration)"
& $Py @(Get-Prefix $Py) "-m" "pytest"
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

Write-Output "==> [3/4] mypy app (informational)"
& $Mypy @(Get-Prefix $Mypy) "app"
if ($LASTEXITCODE -ne 0) {
    Write-Output "    WARNING: mypy reported typing findings (non-blocking)."
}

Write-Output "==> [4/4] synthetic data generator smoke run"
$SmokeOut = Join-Path ([System.IO.Path]::GetTempPath()) ("irt_smoke_" + [System.Guid]::NewGuid().ToString("N"))
& $Py @(Get-Prefix $Py) $Generator "--n-users" "20" "--out" $SmokeOut
if ($LASTEXITCODE -ne 0) { throw "generator smoke run failed" }
Remove-Item -Recurse -Force $SmokeOut

Write-Output ""
Write-Output "==> Done. Automated checks passed."
Write-Output "    Run 1C xUnitFor1C scenarios manually: see $KonfigDir\tests_1c\README.md"
