param(
    [string]$TaskName = 'WorldRec-VRChat-Autostart',
    [int]$PollSeconds = 60
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WatcherScript = Join-Path $ScriptDir 'worldrec-vrchat-autostart.ps1'

if (-not (Test-Path $WatcherScript)) {
    throw "Watcher script not found: $WatcherScript"
}

$taskCommand = "powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -WindowStyle Hidden -File `"$WatcherScript`" -PollSeconds $PollSeconds"

schtasks /Create /F /SC ONLOGON /RL LIMITED /TN $TaskName /TR $taskCommand | Out-Null
Write-Host "Task registered: $TaskName"
