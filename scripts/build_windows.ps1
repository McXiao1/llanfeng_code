param(
    [string]$FlutterBin = $env:FLET_FLUTTER_BIN
)

$ErrorActionPreference = "Stop"

$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $Utf8NoBom
[Console]::InputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$null = & chcp.com 65001

function Stop-Build {
    param([string]$Message)

    Write-Error $Message
    exit 1
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path -LiteralPath "main.py")) {
    Stop-Build "main.py was not found. Run this script from the project checkout."
}

if (-not (Test-Path -LiteralPath "assets\icon.png")) {
    Stop-Build "assets\icon.png was not found. Copy LOGO.png to assets\icon.png before building."
}

if ([string]::IsNullOrWhiteSpace($FlutterBin)) {
    $DefaultFlutterBin = Join-Path $env:USERPROFILE "flutter\3.41.7\bin"
    if (Test-Path -LiteralPath (Join-Path $DefaultFlutterBin "flutter.bat")) {
        $FlutterBin = $DefaultFlutterBin
    }
}

if (-not [string]::IsNullOrWhiteSpace($FlutterBin)) {
    $FlutterExe = Join-Path $FlutterBin "flutter.bat"
    if (-not (Test-Path -LiteralPath $FlutterExe)) {
        Stop-Build "FLET_FLUTTER_BIN does not contain flutter.bat: $FlutterBin"
    }
    $env:Path = "$FlutterBin;$env:Path"
    Write-Host "Using Flutter from: $FlutterExe"
}

$VsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path -LiteralPath $VsWhere)) {
    Stop-Build "vswhere.exe was not found. Install Visual Studio 2022 Build Tools with Desktop development with C++."
}

$VcToolsComponent = "Microsoft.VisualStudio.Component.VC.Tools.x86.x64"
$VsInstallPath = & $VsWhere `
    -latest `
    -products * `
    -requires $VcToolsComponent `
    -property installationPath

if ([string]::IsNullOrWhiteSpace($VsInstallPath)) {
    Stop-Build "Visual Studio C++ toolchain was not found. Install the Microsoft.VisualStudio.Workload.VCTools workload."
}

Write-Host "Using Visual Studio toolchain from: $VsInstallPath"

$RedistRoot = Join-Path $VsInstallPath "VC\Redist\MSVC"
$RuntimeDir = Get-ChildItem -LiteralPath $RedistRoot -Directory -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending |
    ForEach-Object { Join-Path $_.FullName "x64\Microsoft.VC143.CRT" } |
    Where-Object { Test-Path -LiteralPath (Join-Path $_ "vcruntime140_1.dll") } |
    Select-Object -First 1

if ([string]::IsNullOrWhiteSpace($RuntimeDir)) {
    Stop-Build "Visual Studio x64 VC runtime redist directory was not found under $RedistRoot."
}

$env:SERIOUS_PYTHON_VC_RUNTIME_DIR = $RuntimeDir
Write-Host "Using x64 VC runtime from: $RuntimeDir"

python scripts\patch_serious_python_windows.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$WindowsBuildDir = Join-Path $ProjectRoot "build\flutter\build\windows"
if (Test-Path -LiteralPath $WindowsBuildDir) {
    Write-Host "Cleaning stale Windows build cache: $WindowsBuildDir"
    Remove-Item -LiteralPath $WindowsBuildDir -Recurse -Force
}

$BuildPythonDir = Join-Path $ProjectRoot "build\flutter\build\build_python_3.12.9"
$BuildPythonPackageDir = Join-Path $BuildPythonDir "python"
$BuildPythonExe = Join-Path $BuildPythonPackageDir "python.exe"
$DependencyHashFile = Join-Path $ProjectRoot "build\.hash\package"
$env:SERIOUS_PYTHON_BUILD_PYTHON_DIR = $BuildPythonPackageDir

if ((Test-Path -LiteralPath $BuildPythonDir) -and -not (Test-Path -LiteralPath $BuildPythonExe)) {
    Write-Host "Removing incomplete Flet build Python cache: $BuildPythonDir"
    Remove-Item -LiteralPath $BuildPythonDir -Recurse -Force
}

if (-not (Test-Path -LiteralPath $BuildPythonExe) -and (Test-Path -LiteralPath $DependencyHashFile)) {
    Write-Host "Build Python cache incomplete; forcing Python dependency reinstall."
    Remove-Item -LiteralPath $DependencyHashFile -Force
}

$DependencyCacheDir = Join-Path $ProjectRoot "build\site-packages"
$RequiredRuntimePackages = @("certifi", "flet", "httpx", "tomlkit", "pydantic", "keyring")
$MissingRuntimePackages = @()

foreach ($PackageName in $RequiredRuntimePackages) {
    $PackagePath = Join-Path $DependencyCacheDir $PackageName
    if (-not (Test-Path -LiteralPath $PackagePath)) {
        $MissingRuntimePackages += $PackageName
    }
}

if ($MissingRuntimePackages.Count -gt 0 -and (Test-Path -LiteralPath $DependencyHashFile)) {
    Write-Host "Dependency cache incomplete ($($MissingRuntimePackages -join ', ')); forcing Python dependency reinstall."
    Remove-Item -LiteralPath $DependencyHashFile -Force
}

Write-Host "Running: flet build windows -v --no-rich-output"

& flet build windows -v --no-rich-output
$BuildExitCode = $LASTEXITCODE
if ($BuildExitCode -ne 0) {
    exit $BuildExitCode
}

$WindowsPackageCertifi = Join-Path $ProjectRoot "build\windows\site-packages\certifi"
if (-not (Test-Path -LiteralPath $WindowsPackageCertifi)) {
    Stop-Build "Windows package is missing certifi. Re-run this script after confirming Python dependency installation can access PyPI."
}

exit 0
