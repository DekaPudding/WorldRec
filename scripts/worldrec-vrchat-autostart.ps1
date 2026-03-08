param(
    [int]$PollSeconds = 60
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

$ProjectRoot = Get-InstallRoot
$VenvPythonw = Join-Path $ProjectRoot '.venv\Scripts\pythonw.exe'
$WorldRecExe = Join-Path $ProjectRoot 'WorldRec.exe'
$PrimaryLogDir = if ($env:LOCALAPPDATA) {
    Join-Path $env:LOCALAPPDATA 'WorldRec\logs'
} else {
    Join-Path $ProjectRoot 'local\logs'
}
$FallbackLogDir = Join-Path $ProjectRoot 'local\logs'
$ResolvedLogDir = $null
$lastVrchatRunning = $null
$lastWorldRecRunning = $null

function Get-WeeklyLogFilePath {
    param([string]$BaseLogDir)

    $now = Get-Date
    $daysSinceMonday = (([int]$now.DayOfWeek + 6) % 7)
    $monday = $now.Date.AddDays(-$daysSinceMonday)

    if (-not (Test-Path $BaseLogDir)) {
        New-Item -ItemType Directory -Path $BaseLogDir -Force | Out-Null
    }

    return (Join-Path $BaseLogDir ("worldrec-autostart-{0}.log" -f $monday.ToString('yyyyMMdd')))
}

function Resolve-LogDir {
    if ($ResolvedLogDir) {
        return $ResolvedLogDir
    }

    foreach ($candidate in @($PrimaryLogDir, $FallbackLogDir)) {
        try {
            $logPath = Get-WeeklyLogFilePath -BaseLogDir $candidate
            Add-Content -Path $logPath -Value '' -Encoding UTF8
            $ResolvedLogDir = $candidate
            return $ResolvedLogDir
        } catch {
            continue
        }
    }

    throw 'No writable log directory available for WorldRec autostart watcher.'
}

function Write-AutostartLog {
    param(
        [string]$Level,
        [string]$Message
    )

    $timestamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    $logDir = Resolve-LogDir
    $logPath = Get-WeeklyLogFilePath -BaseLogDir $logDir
    Add-Content -Path $logPath -Value "$timestamp [$Level] $Message" -Encoding UTF8
}

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
        return $false
    }

    try {
        $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'py.exe' OR Name = 'pyw.exe'" -ErrorAction Stop
        foreach ($p in $procs) {
            $cmd = [string]$p.CommandLine
            if ($cmd -match 'app\.main') {
                return $true
            }
        }
    } catch {
        Write-AutostartLog -Level 'WARN' -Message "Failed to inspect Python processes: $($_.Exception.Message)"
        return $false
    }

    return $false
}

function Start-WorldRec {
    if (Test-Path $WorldRecExe) {
        Write-AutostartLog -Level 'INFO' -Message "Starting WorldRec.exe: $WorldRecExe"
        Start-Process -FilePath $WorldRecExe -ArgumentList '--start-minimized' -WorkingDirectory $ProjectRoot -WindowStyle Hidden | Out-Null
        return
    }

    $runtime = Get-WorldRecRuntime
    Write-AutostartLog -Level 'INFO' -Message "Starting runtime: $($runtime.FilePath) $($runtime.ArgumentList -join ' ')"
    Start-Process -FilePath $runtime.FilePath -ArgumentList $runtime.ArgumentList -WorkingDirectory $ProjectRoot -WindowStyle Hidden | Out-Null
}

Write-AutostartLog -Level 'INFO' -Message "Watcher started. PollSeconds=$PollSeconds ProjectRoot=$ProjectRoot"

while ($true) {
    try {
        $vrchatRunning = Test-VRChatRunning
        $worldRecRunning = Test-WorldRecRunning

        if ($lastVrchatRunning -ne $vrchatRunning) {
            if ($vrchatRunning) {
                Write-AutostartLog -Level 'INFO' -Message 'Detected VRChat process start.'
            } else {
                Write-AutostartLog -Level 'INFO' -Message 'Detected VRChat process stop.'
            }
            $lastVrchatRunning = $vrchatRunning
        }

        if ($lastWorldRecRunning -ne $worldRecRunning) {
            if ($worldRecRunning) {
                Write-AutostartLog -Level 'INFO' -Message 'Detected WorldRec already running.'
            } else {
                Write-AutostartLog -Level 'INFO' -Message 'Detected WorldRec not running.'
            }
            $lastWorldRecRunning = $worldRecRunning
        }

        if ($vrchatRunning) {
            if (-not $worldRecRunning) {
                Write-AutostartLog -Level 'INFO' -Message 'VRChat is running and WorldRec is not. Launching WorldRec.'
                Start-WorldRec
                $lastWorldRecRunning = $true
            }
        }
    } catch {
        # Keep watcher alive; continue loop even if one iteration fails.
        Write-AutostartLog -Level 'ERROR' -Message $_.Exception.Message
    }

    Start-Sleep -Seconds $PollSeconds
}
