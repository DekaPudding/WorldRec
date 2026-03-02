param(
    [switch]$Clean,
    [string]$DistPath,
    [string]$AutostartTaskName = 'WorldRec-VRChat-Autostart',
    [switch]$SkipRuntimeStop
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$SpecPath = Join-Path $ProjectRoot 'worldrec.spec'
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$DefaultDistRoot = Join-Path $ProjectRoot 'dist'
$FallbackDistRoot = Join-Path $ProjectRoot 'dist_build'
$usingCustomDistPath = [bool]$DistPath

function Ensure-CleanArtifacts {
    param([string]$PathToRemove)
    if (Test-Path $PathToRemove) {
        $maxRetries = 5
        for ($i = 1; $i -le $maxRetries; $i++) {
            try {
                Remove-Item -Recurse -Force $PathToRemove -ErrorAction Stop
                return $true
            } catch {
                if ($i -ge $maxRetries) {
                    Write-Warning "Cannot fully remove path: $PathToRemove"
                    return $false
                }
                Write-Warning "Cleanup failed (attempt $i/$maxRetries): $PathToRemove. Waiting 2s and retrying..."
                Start-Sleep -Seconds 2
            }
        }
    }
    return $true
}

function Stop-WorldRecRuntime {
    param([string]$TaskName)

    if ($TaskName) {
        schtasks /End /TN $TaskName 2>$null | Out-Null
    }

    Get-Process -Name 'WorldRec' -ErrorAction SilentlyContinue | ForEach-Object {
        try { Stop-Process -Id $_.Id -Force -ErrorAction Stop } catch {}
    }

    $pyProcs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'py.exe' OR Name = 'pyw.exe'" -ErrorAction SilentlyContinue
    foreach ($p in $pyProcs) {
        $cmd = [string]$p.CommandLine
        if ($cmd -match 'app\.main' -or $cmd -match 'worldrec-vrchat-autostart\.ps1' -or $cmd -match 'WorldRec') {
            try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
        }
    }
}

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

$effectiveDistRoot = if ($usingCustomDistPath) { $DistPath } else { $DefaultDistRoot }

if (-not $SkipRuntimeStop) {
    Write-Host 'Stopping WorldRec runtime...'
    Stop-WorldRecRuntime -TaskName $AutostartTaskName
    Start-Sleep -Seconds 2
}

if ($Clean) {
    $cleanResult = Ensure-CleanArtifacts -PathToRemove $effectiveDistRoot
    if (-not $cleanResult) {
        if ($usingCustomDistPath) {
            throw "Cannot clean dist path: $effectiveDistRoot"
        }
        Write-Warning "Default dist is locked. Switching to fallback dist path: $FallbackDistRoot"
        Ensure-CleanArtifacts -PathToRemove $FallbackDistRoot | Out-Null
        $effectiveDistRoot = $FallbackDistRoot
    }
}

New-Item -ItemType Directory -Path $effectiveDistRoot -Force | Out-Null

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
$buildArgs += @('--distpath', $effectiveDistRoot)

if ($pythonExe -eq 'py') {
    & py @buildArgs
} else {
    & $pythonExe @buildArgs
}

if (($LASTEXITCODE -ne 0) -and (-not $usingCustomDistPath) -and ($effectiveDistRoot -eq $DefaultDistRoot)) {
    Write-Warning "PyInstaller failed on default dist path. Retrying with fallback: $FallbackDistRoot"
    Ensure-CleanArtifacts -PathToRemove $FallbackDistRoot | Out-Null
    New-Item -ItemType Directory -Path $FallbackDistRoot -Force | Out-Null

    $retryArgs = @($buildArgs)
    $distArgIndex = [Array]::IndexOf($retryArgs, '--distpath')
    if ($distArgIndex -ge 0 -and ($distArgIndex + 1) -lt $retryArgs.Count) {
        $retryArgs[$distArgIndex + 1] = $FallbackDistRoot
    }

    if ($pythonExe -eq 'py') {
        & py @retryArgs
    } else {
        & $pythonExe @retryArgs
    }

    if ($LASTEXITCODE -eq 0) {
        $effectiveDistRoot = $FallbackDistRoot
    }
}

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$outRoot = $effectiveDistRoot
Write-Host "Build finished: $outRoot\WorldRec\WorldRec.exe"
