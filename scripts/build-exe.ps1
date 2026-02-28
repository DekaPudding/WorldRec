param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$SpecPath = Join-Path $ProjectRoot 'worldrec.spec'
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

function Get-BuildPython {
    if (Test-Path $VenvPython) {
        return $VenvPython
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return 'py'
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return 'python'
    }

    throw 'Python runtime not found. Create .venv or add py/python to PATH.'
}

if (-not (Test-Path $SpecPath)) {
    throw "Spec file not found: $SpecPath"
}

$pythonExe = Get-BuildPython

if ($pythonExe -eq 'py') {
    & py -3 -m pip install -r (Join-Path $ProjectRoot 'requirements-build.txt')
    $buildArgs = @('-3', '-m', 'PyInstaller')
} else {
    & $pythonExe -m pip install -r (Join-Path $ProjectRoot 'requirements-build.txt')
    $buildArgs = @('-m', 'PyInstaller')
}

if ($Clean) {
    $buildArgs += '--clean'
}

$buildArgs += @('--noconfirm', $SpecPath)

if ($pythonExe -eq 'py') {
    & py @buildArgs
} else {
    & $pythonExe @buildArgs
}

Write-Host "Build finished: $ProjectRoot\dist\WorldRec\WorldRec.exe"
