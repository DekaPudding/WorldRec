param(
    [string]$TaskName = 'WorldRec-VRChat-Autostart'
)

$ErrorActionPreference = 'Stop'

$RunKeyPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$StartupCmdPath = Join-Path (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup') "$TaskName.cmd"
$StartupVbsPath = Join-Path (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup') "$TaskName.vbs"

if (Test-Path $RunKeyPath) {
    Remove-ItemProperty -Path $RunKeyPath -Name $TaskName -ErrorAction SilentlyContinue
}

if (Test-Path $StartupCmdPath) {
    Remove-Item -Path $StartupCmdPath -Force -ErrorAction SilentlyContinue
}

if (Test-Path $StartupVbsPath) {
    Remove-Item -Path $StartupVbsPath -Force -ErrorAction SilentlyContinue
}

& cmd.exe /c "schtasks /Query /TN ""$TaskName"" >nul 2>&1"
if ($LASTEXITCODE -eq 0) {
    & schtasks.exe /Delete /F /TN $TaskName | Out-Null
}

Write-Host "Startup registration removed: $TaskName"
