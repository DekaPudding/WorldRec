param(
    [switch]$Clean,
    [string]$DistPath,
    [switch]$SkipRuntimeStop
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$SpecPath = Join-Path $ProjectRoot 'worldrec.spec'
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$DefaultDistRoot = Join-Path $ProjectRoot 'dist'
$FallbackDistRoot = Join-Path $ProjectRoot 'dist_build'
$DefaultWorkRoot = Join-Path $ProjectRoot 'build'
$FallbackWorkRoot = Join-Path $ProjectRoot 'build_build'
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
    Get-Process -Name 'WorldRec' -ErrorAction SilentlyContinue | ForEach-Object {
        try { Stop-Process -Id $_.Id -Force -ErrorAction Stop } catch {}
    }

    $pyProcs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'py.exe' OR Name = 'pyw.exe'" -ErrorAction SilentlyContinue
    foreach ($p in $pyProcs) {
        $cmd = [string]$p.CommandLine
        if ($cmd -match 'app\.main' -or $cmd -match 'WorldRec') {
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
$effectiveWorkRoot = $DefaultWorkRoot

if (-not $SkipRuntimeStop) {
    Write-Host 'Stopping WorldRec runtime...'
    Stop-WorldRecRuntime
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

    $workCleanResult = Ensure-CleanArtifacts -PathToRemove $effectiveWorkRoot
    if (-not $workCleanResult) {
        Write-Warning "Default build work path is locked. Switching to fallback work path: $FallbackWorkRoot"
        Ensure-CleanArtifacts -PathToRemove $FallbackWorkRoot | Out-Null
        $effectiveWorkRoot = $FallbackWorkRoot
    }
}

New-Item -ItemType Directory -Path $effectiveDistRoot -Force | Out-Null
New-Item -ItemType Directory -Path $effectiveWorkRoot -Force | Out-Null

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
$buildArgs += @('--workpath', $effectiveWorkRoot)

if ($pythonExe -eq 'py') {
    & py @buildArgs
} else {
    & $pythonExe @buildArgs
}

if (($LASTEXITCODE -ne 0) -and ((-not $usingCustomDistPath) -and ($effectiveDistRoot -eq $DefaultDistRoot) -or ($effectiveWorkRoot -eq $DefaultWorkRoot))) {
    Write-Warning "PyInstaller failed on default output paths. Retrying with fallback dist/work paths."
    Ensure-CleanArtifacts -PathToRemove $FallbackDistRoot | Out-Null
    Ensure-CleanArtifacts -PathToRemove $FallbackWorkRoot | Out-Null
    New-Item -ItemType Directory -Path $FallbackDistRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $FallbackWorkRoot -Force | Out-Null

    $retryArgs = @($buildArgs)
    $distArgIndex = [Array]::IndexOf($retryArgs, '--distpath')
    if ($distArgIndex -ge 0 -and ($distArgIndex + 1) -lt $retryArgs.Count) {
        $retryArgs[$distArgIndex + 1] = $FallbackDistRoot
    }
    $workArgIndex = [Array]::IndexOf($retryArgs, '--workpath')
    if ($workArgIndex -ge 0 -and ($workArgIndex + 1) -lt $retryArgs.Count) {
        $retryArgs[$workArgIndex + 1] = $FallbackWorkRoot
    }

    if ($pythonExe -eq 'py') {
        & py @retryArgs
    } else {
        & $pythonExe @retryArgs
    }

    if ($LASTEXITCODE -eq 0) {
        $effectiveDistRoot = $FallbackDistRoot
        $effectiveWorkRoot = $FallbackWorkRoot
    }
}

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$outRoot = $effectiveDistRoot
Write-Host "Build finished: $outRoot\WorldRec\WorldRec.exe"
