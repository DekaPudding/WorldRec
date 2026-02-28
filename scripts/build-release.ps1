param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [switch]$Clean,
    [ValidateSet('auto', 'always', 'never')]
    [string]$Signing = 'auto',
    [string]$SignCertPath = $env:WORLDREC_SIGN_CERT_PATH,
    [string]$SignCertPassword = $env:WORLDREC_SIGN_CERT_PASSWORD,
    [string]$SignTimestampUrl = $env:WORLDREC_SIGN_TIMESTAMP_URL
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DistDir = Join-Path $ProjectRoot 'dist\WorldRec'
$ArtifactsDir = Join-Path $ProjectRoot 'artifacts'
$InstallerScript = Join-Path $ProjectRoot 'installer\worldrec.iss'
$ZipPath = Join-Path $ArtifactsDir "WorldRec-v$Version-win64.zip"
$SetupPath = Join-Path $ArtifactsDir "WorldRec-Setup-v$Version.exe"
$HashPath = Join-Path $ArtifactsDir "WorldRec-v$Version-sha256.txt"

if (-not $SignTimestampUrl) {
    $SignTimestampUrl = 'http://timestamp.digicert.com'
}

function Ensure-CleanArtifacts {
    param([string]$PathToRemove)
    if (Test-Path $PathToRemove) {
        Remove-Item -Recurse -Force $PathToRemove
    }
}

function Get-IsccPath {
    $iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($iscc) {
        return $iscc.Source
    }

    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }
    throw 'ISCC.exe (Inno Setup) not found. Install Inno Setup 6 and retry.'
}

function Get-SignToolPath {
    $manual = $env:WORLDREC_SIGNTOOL_PATH
    if ($manual -and (Test-Path $manual)) {
        return $manual
    }

    $signTool = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($signTool) {
        return $signTool.Source
    }

    return $null
}

function Invoke-Sign {
    param(
        [string]$FilePath,
        [string]$ToolPath,
        [string]$CertPath,
        [string]$CertPassword,
        [string]$TimestampUrl
    )
    & $ToolPath sign `
        /f $CertPath `
        /p $CertPassword `
        /fd SHA256 `
        /tr $TimestampUrl `
        /td SHA256 `
        $FilePath
}

function Try-SignArtifacts {
    param(
        [string[]]$Targets,
        [string]$Mode,
        [string]$CertPath,
        [string]$CertPassword,
        [string]$TimestampUrl
    )

    if ($Mode -eq 'never') {
        Write-Host 'Signing disabled by parameter (-Signing never).'
        return
    }

    $signToolPath = Get-SignToolPath
    $canSign = $signToolPath -and $CertPath -and $CertPassword -and (Test-Path $CertPath)

    if (-not $canSign) {
        $message = 'Signing skipped: missing signtool or certificate settings.'
        if ($Mode -eq 'always') {
            throw $message
        }
        Write-Warning $message
        Write-Host 'Required: WORLDREC_SIGNTOOL_PATH(optional), WORLDREC_SIGN_CERT_PATH, WORLDREC_SIGN_CERT_PASSWORD'
        return
    }

    foreach ($target in $Targets) {
        Write-Host "Signing: $target"
        Invoke-Sign -FilePath $target -ToolPath $signToolPath -CertPath $CertPath -CertPassword $CertPassword -TimestampUrl $TimestampUrl
    }
}

if ($Clean) {
    Ensure-CleanArtifacts -PathToRemove (Join-Path $ProjectRoot 'build')
    Ensure-CleanArtifacts -PathToRemove (Join-Path $ProjectRoot 'dist')
    Ensure-CleanArtifacts -PathToRemove $ArtifactsDir
}

New-Item -ItemType Directory -Path $ArtifactsDir -Force | Out-Null

Write-Host 'Step 1/5: Build executable'
$buildArgs = @(
    '-ExecutionPolicy', 'RemoteSigned',
    '-File', (Join-Path $ScriptDir 'build-exe.ps1')
)
if ($Clean) {
    $buildArgs += '-Clean'
}
powershell @buildArgs

if (-not (Test-Path $DistDir)) {
    throw "Build output not found: $DistDir"
}

Write-Host 'Step 2/5: Package zip'
if (Test-Path $ZipPath) {
    Remove-Item -Force $ZipPath
}
Compress-Archive -Path (Join-Path $DistDir '*') -DestinationPath $ZipPath -CompressionLevel Optimal

Write-Host 'Step 3/5: Build installer'
if (-not (Test-Path $InstallerScript)) {
    throw "Installer script not found: $InstallerScript"
}
$iscc = Get-IsccPath
& $iscc `
    "/DMyAppVersion=$Version" `
    "/DMySourceDir=$DistDir" `
    "/DMyOutputDir=$ArtifactsDir" `
    $InstallerScript

if (-not (Test-Path $SetupPath)) {
    throw "Installer not found: $SetupPath"
}

Write-Host 'Step 4/5: Sign artifacts (optional)'
$signTargets = @(
    (Join-Path $DistDir 'WorldRec.exe'),
    $SetupPath
)
Try-SignArtifacts -Targets $signTargets -Mode $Signing -CertPath $SignCertPath -CertPassword $SignCertPassword -TimestampUrl $SignTimestampUrl

Write-Host 'Step 5/5: Write SHA256'
$hashItems = @($ZipPath, $SetupPath)
$hashLines = @()
foreach ($item in $hashItems) {
    $hash = Get-FileHash -Path $item -Algorithm SHA256
    $hashLines += "$($hash.Hash)  $([System.IO.Path]::GetFileName($item))"
}
Set-Content -Path $HashPath -Value $hashLines -Encoding UTF8

Write-Host ''
Write-Host 'Release artifacts created:'
Write-Host "  $ZipPath"
Write-Host "  $SetupPath"
Write-Host "  $HashPath"

