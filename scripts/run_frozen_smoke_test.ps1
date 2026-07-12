[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ExePath,
    [Parameter(Mandatory=$true)][string]$ReportPath,
    [int]$TimeoutSeconds = 120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$exe = (Resolve-Path -LiteralPath $ExePath).Path
$report = [System.IO.Path]::GetFullPath($ReportPath)
$reportDirectory = Split-Path -Parent $report
New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue

$arguments = @(
    "--self-test",
    "--self-test-output",
    ('"{0}"' -f $report)
)
$process = Start-Process `
    -FilePath $exe `
    -ArgumentList $arguments `
    -PassThru

if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    throw "Frozen self-test exceeded $TimeoutSeconds seconds."
}

if ($process.ExitCode -ne 0) {
    $details = if (Test-Path -LiteralPath $report) {
        Get-Content -LiteralPath $report -Raw -Encoding UTF8
    } else {
        "Self-test report was not created."
    }
    throw "Frozen self-test failed with exit code $($process.ExitCode).`n$details"
}

if (-not (Test-Path -LiteralPath $report)) {
    throw "Frozen self-test report was not created: $report"
}

$payload = Get-Content -LiteralPath $report -Raw -Encoding UTF8 |
    ConvertFrom-Json
if (-not $payload.success) {
    throw "Frozen self-test report contains success=false."
}

Write-Host "Frozen self-test: OK" -ForegroundColor Green
Write-Host "Report: $report"
