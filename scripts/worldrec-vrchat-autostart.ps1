param(
    [int]$PollSeconds = 60
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$WorldRecExe = Join-Path $ProjectRoot 'WorldRec.exe'

function Get-WorldRecPython {
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

function Test-VRChatRunning {
    return [bool](Get-Process -Name 'VRChat' -ErrorAction SilentlyContinue)
}

function Test-WorldRecRunning {
    if (Test-Path $WorldRecExe) {
        if (Get-Process -Name 'WorldRec' -ErrorAction SilentlyContinue) {
            return $true
        }
    }

    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'py.exe'"
    foreach ($p in $procs) {
        $cmd = [string]$p.CommandLine
        if ($cmd -match 'app\.main') {
            return $true
        }
    }
    return $false
}

function Start-WorldRec {
    if (Test-Path $WorldRecExe) {
        Start-Process -FilePath $WorldRecExe -ArgumentList '--start-minimized' -WorkingDirectory $ProjectRoot | Out-Null
        return
    }

    $pythonExe = Get-WorldRecPython

    if ($pythonExe -eq 'py') {
        Start-Process -FilePath 'py' -ArgumentList '-3', '-m', 'app.main', '--start-minimized' -WorkingDirectory $ProjectRoot | Out-Null
        return
    }

    Start-Process -FilePath $pythonExe -ArgumentList '-m', 'app.main', '--start-minimized' -WorkingDirectory $ProjectRoot | Out-Null
}

while ($true) {
    try {
        if (Test-VRChatRunning) {
            if (-not (Test-WorldRecRunning)) {
                Start-WorldRec
            }
        }
    } catch {
        # Keep watcher alive; continue loop even if one iteration fails.
    }

    Start-Sleep -Seconds $PollSeconds
}
