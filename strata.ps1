<#
  Windows task runner, mirrors the Makefile so the project runs the same way on
  any machine. Usage:

      ./strata.ps1 up        # gen + deps + build + report, from clean
      ./strata.ps1 build
      ./strata.ps1 report

  Prefers the local .venv if present, otherwise falls back to python/dbt on PATH.
#>
param([Parameter(Position = 0)][string]$Task = "up")

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$dbt = Join-Path $PSScriptRoot ".venv\Scripts\dbt.exe"
if (-not (Test-Path $py)) { $py = "python" }
if (-not (Test-Path $dbt)) { $dbt = "dbt" }
$dbtFlags = @("--project-dir", "dbt", "--profiles-dir", "dbt")

function Run([string]$file, [string[]]$argList) {
    & $file @argList
    if ($LASTEXITCODE -ne 0) { throw "$file exited with $LASTEXITCODE" }
}

function Invoke-Clean {
    $targets = @(
        "data\raw", "data\strata.duckdb", "data\strata.duckdb.wal",
        "dbt\target", "dbt\dbt_packages", "dbt\logs", "logs"
    )
    foreach ($t in $targets) {
        if (Test-Path $t) { Remove-Item -Recurse -Force $t }
    }
    Write-Host "cleaned"
}

switch ($Task) {
    "install" { Run $py @("-m", "pip", "install", "-e", ".") }
    "gen"     { Run $py @("-m", "generate") }
    "deps"    { Run $dbt (@("deps") + $dbtFlags) }
    "build"   { Run $dbt (@("build") + $dbtFlags) }
    "test"    { Run $dbt (@("test") + $dbtFlags) }
    "report"  { Run $py @("scripts/show_reports.py") }
    "docs"    { Run $dbt (@("docs", "generate") + $dbtFlags) }
    "clean"   { Invoke-Clean }
    "up" {
        Run $py @("-m", "generate")
        Run $dbt (@("deps") + $dbtFlags)
        Run $dbt (@("build") + $dbtFlags)
        Run $py @("scripts/show_reports.py")
    }
    default {
        Write-Host "Unknown task '$Task'."
        Write-Host "Try: install gen deps build test report docs up clean"
        exit 1
    }
}
