param(
    [string]$TaskName = 'WorldRec-VRChat-Autostart'
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-InstallRoot {
    $scriptParent = Split-Path -Parent $ScriptDir
    $candidates = @(
        $scriptParent,
        (Split-Path -Parent $scriptParent)
    )

    foreach ($root in $candidates) {
        if (-not $root) {
            continue
        }
        if (Test-Path (Join-Path $root 'WorldRec.exe')) {
            return $root
        }
    }

    return $scriptParent
}

$InstallRoot = Get-InstallRoot
$VenvPythonw = Join-Path $InstallRoot '.venv\Scripts\pythonw.exe'
$WorldRecExe = Join-Path $InstallRoot 'WorldRec.exe'
$MainScript = Join-Path $InstallRoot 'app\main.py'

function Get-WorldRecRuntime {
    if (Test-Path $WorldRecExe) {
        return @{
            FilePath = $WorldRecExe
            ArgumentList = @('--start-minimized')
        }
    }

    if (Test-Path $VenvPythonw) {
        if (-not (Test-Path $MainScript)) {
            throw "Main script not found: $MainScript"
        }
        return @{
            FilePath = $VenvPythonw
            ArgumentList = @($MainScript, '--start-minimized')
        }
    }

    $pyw = Get-Command pyw -ErrorAction SilentlyContinue
    if ($pyw) {
        if (-not (Test-Path $MainScript)) {
            throw "Main script not found: $MainScript"
        }
        return @{
            FilePath = $pyw.Source
            ArgumentList = @('-3', $MainScript, '--start-minimized')
        }
    }

    $pythonw = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($pythonw) {
        if (-not (Test-Path $MainScript)) {
            throw "Main script not found: $MainScript"
        }
        return @{
            FilePath = $pythonw.Source
            ArgumentList = @($MainScript, '--start-minimized')
        }
    }

    throw 'WorldRec runtime not found. Install WorldRec.exe or create .venv.'
}

function Quote-ForTask {
    param([string]$Value)
    return '"' + $Value.Replace('"', '""') + '"'
}

function Build-TaskCommand {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList
    )

    $segments = @((Quote-ForTask -Value $FilePath))
    foreach ($arg in $ArgumentList) {
        $segments += (Quote-ForTask -Value $arg)
    }
    return ($segments -join ' ')
}

$runtime = Get-WorldRecRuntime
$taskCommand = Build-TaskCommand -FilePath $runtime.FilePath -ArgumentList $runtime.ArgumentList

# Security log Event ID 4688 (process creation). Task fires when NewProcessName contains \VRChat.exe.
$eventFilter = "*[System[EventID=4688]] and *[EventData[Data[@Name='NewProcessName'] and (contains(Data,'\\VRChat.exe') or contains(Data,'\\vrchat.exe'))]]"

schtasks /Query /TN $TaskName 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    schtasks /Delete /F /TN $TaskName | Out-Null
    Write-Host "Existing task deleted: $TaskName"
}

schtasks /Create /F /SC ONEVENT /EC Security /MO $eventFilter /RL LIMITED /TN $TaskName /TR $taskCommand | Out-Null
Write-Host "Task registered: $TaskName"
