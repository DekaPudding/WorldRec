param(
    [string]$TaskName = 'WorldRec-VRChat-Autostart',
    [int]$PollSeconds = 60
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunKeyPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$StartupDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
$StartupCmdPath = Join-Path $StartupDir "$TaskName.cmd"
$StartupVbsPath = Join-Path $StartupDir "$TaskName.vbs"

function Quote-ForCommand {
    param([string]$Value)
    return '"' + $Value.Replace('"', '""') + '"'
}

function Build-PowerShellCommand {
    param(
        [string]$ScriptPath,
        [string[]]$ArgumentList
    )

    $powershellExe = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $segments = @(
        (Quote-ForCommand -Value $powershellExe),
        '-NoProfile',
        '-WindowStyle', 'Hidden',
        '-ExecutionPolicy', 'Bypass',
        '-File', (Quote-ForCommand -Value $ScriptPath)
    )

    foreach ($arg in $ArgumentList) {
        $segments += (Quote-ForCommand -Value $arg)
    }

    return ($segments -join ' ')
}

function Remove-LegacyTask {
    param([string]$Name)

    & cmd.exe /c "schtasks /Query /TN ""$Name"" >nul 2>&1"
    if ($LASTEXITCODE -eq 0) {
        & schtasks.exe /Delete /F /TN $Name | Out-Null
    }
}

$autostartScript = Join-Path $ScriptDir 'worldrec-vrchat-autostart.ps1'
if (-not (Test-Path $autostartScript)) {
    throw "Autostart watcher script not found: $autostartScript"
}

$command = Build-PowerShellCommand -ScriptPath $autostartScript -ArgumentList @('-PollSeconds', $PollSeconds.ToString())

New-Item -ItemType Directory -Path $StartupDir -Force | Out-Null
$escapedCommand = $command.Replace('"', '""')
$startupVbs = @"
Set shell = CreateObject("WScript.Shell")
shell.Run "$escapedCommand", 0, False
"@
Set-Content -Path $StartupVbsPath -Value $startupVbs -Encoding ASCII
if (Test-Path $StartupCmdPath) {
    Remove-Item -Path $StartupCmdPath -Force -ErrorAction SilentlyContinue
}
if (Test-Path $RunKeyPath) {
    Remove-ItemProperty -Path $RunKeyPath -Name $TaskName -ErrorAction SilentlyContinue
}
Remove-LegacyTask -Name $TaskName

Write-Host "Startup launcher registered: $StartupVbsPath"
Write-Host $command
