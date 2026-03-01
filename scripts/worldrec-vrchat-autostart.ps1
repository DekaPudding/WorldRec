param(
    [int]$PollSeconds = 60
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$VenvPythonw = Join-Path $ProjectRoot '.venv\Scripts\pythonw.exe'
$WorldRecExe = Join-Path $ProjectRoot 'WorldRec.exe'

function Get-WorldRecRuntime {
    if (Test-Path $VenvPythonw) {
        return @{
            FilePath = $VenvPythonw
            ArgumentList = @('-m', 'app.main', '--start-minimized')
        }
    }

    $pyw = Get-Command pyw -ErrorAction SilentlyContinue
    if ($pyw) {
        return @{
            FilePath = 'pyw'
            ArgumentList = @('-3', '-m', 'app.main', '--start-minimized')
        }
    }

    $pythonw = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($pythonw) {
        return @{
            FilePath = 'pythonw'
            ArgumentList = @('-m', 'app.main', '--start-minimized')
        }
    }

    throw 'Windowless Python runtime not found. Create .venv or add pyw/pythonw to PATH.'
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

    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'py.exe' OR Name = 'pyw.exe'"
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
        Start-Process -FilePath $WorldRecExe -ArgumentList '--start-minimized' -WorkingDirectory $ProjectRoot -WindowStyle Hidden | Out-Null
        return
    }

    $runtime = Get-WorldRecRuntime
    Start-Process -FilePath $runtime.FilePath -ArgumentList $runtime.ArgumentList -WorkingDirectory $ProjectRoot -WindowStyle Hidden | Out-Null
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
