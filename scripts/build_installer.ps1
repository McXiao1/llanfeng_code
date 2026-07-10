param(
    [switch]$SkipAppBuild,
    [string]$InnoSetupCompiler
)

$ErrorActionPreference = "Stop"

function Stop-InstallerBuild {
    param([string]$Message)

    Write-Error $Message
    exit 1
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WindowsBuildDir = Join-Path $ProjectRoot "build\windows"
$ApplicationExe = Join-Path $WindowsBuildDir "llanfeng-code-assistant.exe"
$InstallerScript = Join-Path $PSScriptRoot "installer.iss"
$InstallerIcon = Join-Path $ProjectRoot "build\flutter\windows\runner\resources\app_icon.ico"
$PyprojectPath = Join-Path $ProjectRoot "pyproject.toml"
$OutputDir = Join-Path $ProjectRoot "build\installer"

if (-not $SkipAppBuild) {
    & (Join-Path $PSScriptRoot "build_windows.ps1")
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

foreach ($RequiredPath in @($ApplicationExe, $InstallerScript, $InstallerIcon, $PyprojectPath)) {
    if (-not (Test-Path -LiteralPath $RequiredPath)) {
        Stop-InstallerBuild "Required installer input was not found: $RequiredPath"
    }
}

$PyprojectContent = Get-Content -LiteralPath $PyprojectPath -Raw
$VersionMatch = [regex]::Match(
    $PyprojectContent,
    '(?m)^version\s*=\s*"(?<version>[^"]+)"\s*$'
)
if (-not $VersionMatch.Success) {
    Stop-InstallerBuild "Could not read project.version from pyproject.toml."
}
$AppVersion = $VersionMatch.Groups["version"].Value

if ([string]::IsNullOrWhiteSpace($InnoSetupCompiler)) {
    $CompilerCandidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    $InnoSetupCompiler = $CompilerCandidates |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1
}

if ([string]::IsNullOrWhiteSpace($InnoSetupCompiler) -or
    -not (Test-Path -LiteralPath $InnoSetupCompiler)) {
    Stop-InstallerBuild (
        "Inno Setup 6.7.3 compiler was not found. Install Inno Setup 6.7.3 from " +
        "https://jrsoftware.org/isdl.php, or pass -InnoSetupCompiler with the full path to ISCC.exe."
    )
}

$RequiredInnoSetupVersion = [version]"6.7.3"
$CompilerDirectory = [System.IO.Path]::GetFullPath(
    (Split-Path -Parent $InnoSetupCompiler)
).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
$InnoSetupInstall = Get-ItemProperty `
    -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*", `
    "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" `
    -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like "Inno Setup version *" } |
    Where-Object {
        $_.InstallLocation -and
        ([System.IO.Path]::GetFullPath($_.InstallLocation).TrimEnd(
            [System.IO.Path]::DirectorySeparatorChar
        ) -eq $CompilerDirectory)
    } |
    Select-Object -First 1

$CompilerVersionText = if ($InnoSetupInstall.DisplayVersion) { $InnoSetupInstall.DisplayVersion } else { "" }
$CompilerVersionMatch = [regex]::Match($CompilerVersionText, '^\d+\.\d+\.\d+')
if (-not $CompilerVersionMatch.Success -or
    [version]$CompilerVersionMatch.Value -ne $RequiredInnoSetupVersion) {
    Stop-InstallerBuild (
        "Inno Setup 6.7.3 is required, but the selected compiler installation reports " +
        "version '$CompilerVersionText': $InnoSetupCompiler"
    )
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$ExpectedInstaller = Join-Path $OutputDir "Llanfeng-Code-Assistant-Setup-$AppVersion.exe"

Write-Host "Building installer version $AppVersion with: $InnoSetupCompiler"
& $InnoSetupCompiler `
    "/DAppVersion=$AppVersion" `
    "/DSourceDir=$WindowsBuildDir" `
    "/DOutputDir=$OutputDir" `
    $InstallerScript
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if (-not (Test-Path -LiteralPath $ExpectedInstaller)) {
    Stop-InstallerBuild "Inno Setup completed without producing: $ExpectedInstaller"
}

Write-Host "Installer created: $ExpectedInstaller"

