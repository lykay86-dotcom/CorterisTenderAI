[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipInstaller,
    [switch]$RecreateVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

try {
    [Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    chcp 65001 | Out-Null
} catch {}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$LogDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogFile = Join-Path $LogDir ("build_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

function Write-Step {
    param([Parameter(Mandatory=$true)][string]$Text)
    $line = "`n==> $Text"
    Write-Host $line -ForegroundColor Cyan
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

function Write-Ok {
    param([Parameter(Mandatory=$true)][string]$Text)
    Write-Host $Text -ForegroundColor Green
    Add-Content -LiteralPath $LogFile -Value $Text -Encoding UTF8
}

function Assert-PathExists {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Description
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing required path: $Description ($Path)"
    }
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter()][string[]]$Arguments = @(),
        [Parameter(Mandatory=$true)][string]$ErrorMessage
    )

    # Windows PowerShell 5.1 turns native stderr into ErrorRecord objects.
    # Temporarily use Continue and write every output line to UTF-8 manually.
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $allOutput = @(& $FilePath @Arguments 2>&1)
        $exitCode = $LASTEXITCODE

        foreach ($item in $allOutput) {
            $line = $item.ToString()
            Write-Host $line
            Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
        }

        if ($exitCode -ne 0) {
            throw "$ErrorMessage Exit code: $exitCode"
        }
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }
}

try {
    Write-Step "Checking project structure"
    $RequiredPaths = @(
        "app\main.py",
        "app\core\path_manager.py",
        "templates",
        "data",
        "assets",
        "requirements.txt",
        "installer\corteris_tender_ai.spec"
    )
    foreach ($relativePath in $RequiredPaths) {
        Assert-PathExists -Path (Join-Path $ProjectRoot $relativePath) -Description $relativePath
    }
    Write-Ok "Project structure: OK"

    Write-Step "Checking Python 3.12 x64"
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) {
        throw "Python was not found in PATH. Install Python 3.12 x64 and enable Add Python to PATH."
    }

    $PythonExe = $PythonCommand.Source
    $PythonVersion = (& $PythonExe -c "import sys; print('.'.join(map(str, sys.version_info[:3])))").Trim()
    $PythonBits = (& $PythonExe -c "import struct; print(struct.calcsize('P') * 8)").Trim()

    if (-not $PythonVersion.StartsWith("3.12.")) {
        throw "Python 3.12 x64 is required. Found: $PythonVersion"
    }
    if ($PythonBits -ne "64") {
        throw "64-bit Python is required. Found: $PythonBits-bit"
    }
    Write-Ok "Python $PythonVersion ($PythonBits-bit): OK"

    $VenvDir = Join-Path $ProjectRoot ".venv"
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"

    if ($RecreateVenv -and (Test-Path -LiteralPath $VenvDir)) {
        Write-Step "Removing existing virtual environment"
        Remove-Item -LiteralPath $VenvDir -Recurse -Force
    }

    if (-not (Test-Path -LiteralPath $VenvPython)) {
        Write-Step "Creating virtual environment"
        Invoke-NativeChecked -FilePath $PythonExe -Arguments @("-m","venv",$VenvDir) -ErrorMessage "Failed to create virtual environment."
    }

    Write-Step "Installing build dependencies"
    Invoke-NativeChecked -FilePath $VenvPython -Arguments @("-m","pip","install","--upgrade","pip","setuptools","wheel") -ErrorMessage "Failed to update pip tools."
    Invoke-NativeChecked -FilePath $VenvPython -Arguments @("-m","pip","install","-r","requirements.txt") -ErrorMessage "Failed to install requirements."
    Invoke-NativeChecked -FilePath $VenvPython -Arguments @("-m","pip","install","pyinstaller","pytest") -ErrorMessage "Failed to install build tools."

    Write-Step "Compiling Python modules"
    Invoke-NativeChecked -FilePath $VenvPython -Arguments @("-m","compileall","-q","app") -ErrorMessage "Python compilation failed."

    if (-not $SkipTests) {
        Write-Step "Running automated tests"
        Invoke-NativeChecked -FilePath $VenvPython -Arguments @("-m","pytest","-q") -ErrorMessage "Automated tests failed."
    }

    Write-Step "Cleaning old build artifacts"
    foreach ($folder in @("build","dist")) {
        $fullPath = Join-Path $ProjectRoot $folder
        if (Test-Path -LiteralPath $fullPath) {
            Remove-Item -LiteralPath $fullPath -Recurse -Force
        }
    }

    Write-Step "Building EXE with PyInstaller"
    $SpecFile = Join-Path $ProjectRoot "installer\corteris_tender_ai.spec"
    Invoke-NativeChecked -FilePath $VenvPython `
        -Arguments @("-m","PyInstaller","--noconfirm","--clean",$SpecFile) `
        -ErrorMessage "PyInstaller build failed."

    $Exe = Join-Path $ProjectRoot "dist\CorterisTenderAI.exe"
    Assert-PathExists -Path $Exe -Description "built EXE"
    $ExeInfo = Get-Item -LiteralPath $Exe
    $ExeHash = (Get-FileHash -LiteralPath $Exe -Algorithm SHA256).Hash
    Write-Ok ("EXE created: {0}" -f $Exe)
    Write-Ok ("EXE size: {0:N2} MB" -f ($ExeInfo.Length / 1MB))
    Write-Ok ("SHA256: {0}" -f $ExeHash)

    if (-not $SkipInstaller) {
        $SetupScript = Join-Path $ProjectRoot "installer\setup.iss"
        $InnoCandidates = @(
            "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            "C:\Program Files\Inno Setup 6\ISCC.exe"
        )
        $ISCC = $InnoCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if ((Test-Path -LiteralPath $SetupScript) -and $ISCC) {
            Write-Step "Building installer with Inno Setup"
            Invoke-NativeChecked -FilePath $ISCC -Arguments @($SetupScript) -ErrorMessage "Inno Setup build failed."
        } else {
            Write-Warning "Inno Setup or setup.iss was not found. Installer step skipped."
        }
    }

    Write-Host ""
    Write-Ok "Corteris Tender AI 1.5.1 build completed successfully."
    Write-Ok ("Build log: {0}" -f $LogFile)
    exit 0
}
catch {
    $message = $_.Exception.Message
    Write-Host ""
    Write-Host ("BUILD FAILED: {0}" -f $message) -ForegroundColor Red
    Add-Content -LiteralPath $LogFile -Value ("BUILD FAILED: {0}`n{1}" -f $message, $_.ScriptStackTrace) -Encoding UTF8
    Write-Host ("Build log: {0}" -f $LogFile) -ForegroundColor Yellow
    exit 1
}
