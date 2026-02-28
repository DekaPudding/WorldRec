param(
    [string]$TaskName = 'WorldRec-VRChat-Autostart'
)

$ErrorActionPreference = 'Stop'

schtasks /Delete /F /TN $TaskName | Out-Null
Write-Host "Task deleted: $TaskName"
