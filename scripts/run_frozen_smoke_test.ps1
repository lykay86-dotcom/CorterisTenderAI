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

$runtimeRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $reportDirectory ".frozen-self-test-runtime")
)
$reportRoot = [System.IO.Path]::GetFullPath($reportDirectory)
if (-not $runtimeRoot.StartsWith(
    $reportRoot + [System.IO.Path]::DirectorySeparatorChar,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Refusing to use frozen self-test runtime outside report directory: $runtimeRoot"
}
if (Test-Path -LiteralPath $runtimeRoot) {
    Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null

$environment = @{
    "CORTERIS_DATA_DIR" = (Join-Path $runtimeRoot "data")
    "CORTERIS_CONFIG_DIR" = (Join-Path $runtimeRoot "config")
    "CORTERIS_LOG_DIR" = (Join-Path $runtimeRoot "logs")
    "CORTERIS_CACHE_DIR" = (Join-Path $runtimeRoot "cache")
    "QT_QPA_PLATFORM" = "offscreen"
}
$previousEnvironment = @{}
foreach ($name in $environment.Keys) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable(
        $name,
        [EnvironmentVariableTarget]::Process
    )
    [Environment]::SetEnvironmentVariable(
        $name,
        $environment[$name],
        [EnvironmentVariableTarget]::Process
    )
}

$arguments = @(
    "--self-test",
    "--self-test-output",
    ('"{0}"' -f $report)
)
$process = $null
try {
    $process = Start-Process `
        -FilePath $exe `
        -ArgumentList $arguments `
        -WindowStyle Hidden `
        -PassThru

    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        throw "Frozen self-test exceeded $TimeoutSeconds seconds."
    }
}
finally {
    foreach ($name in $environment.Keys) {
        [Environment]::SetEnvironmentVariable(
            $name,
            $previousEnvironment[$name],
            [EnvironmentVariableTarget]::Process
        )
    }
    if (Test-Path -LiteralPath $runtimeRoot) {
        Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
    }
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
