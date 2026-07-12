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
$RequiredRuntimePackages = @("certifi", "flet", "httpx", "websockets", "chromium_reader")
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

$AppArchive = Join-Path $ProjectRoot "build\windows\data\flutter_assets\app\app.zip"
if (-not (Test-Path -LiteralPath $AppArchive)) {
    Stop-Build "Flet app archive was not found: $AppArchive"
}

$RequiredArchiveEntries = @(
    "main.py",
    "assets/icon.png",
    "src/llanfeng_code_assistant/__init__.py",
    "src/llanfeng_code_assistant/__main__.py",
    "src/llanfeng_code_assistant/app.py",
    "src/llanfeng_code_assistant/codex_config_restorer.py",
    "src/llanfeng_code_assistant/installer.py",
    "src/llanfeng_code_assistant/codex_statsig_unlocker.py",
    "src/llanfeng_code_assistant/codex_desktop_launcher.py",
    "src/llanfeng_code_assistant/codex_plugin_marketplace.py"
)
$AllowedArchiveEntries = @("main.py")
$AllowedArchivePrefixes = @(
    "assets/",
    "src/llanfeng_code_assistant/"
)
$ForbiddenArchivePrefixes = @(
    "src/llanfeng_code_assistant/__pycache__/",
    "src/llanfeng_code_assistant/config/"
)
$ForbiddenArchiveEntries = @(
    "assets/codex-plugin.vbs",
    "src/llanfeng_code_assistant/storage.py",
    "src/llanfeng_code_assistant/secrets.py",
    "src/llanfeng_code_assistant/models.py",
    "src/llanfeng_code_assistant/model_fetcher.py",
    "src/llanfeng_code_assistant/codex_model_catalog_editor.py",
    "src/llanfeng_code_assistant/deeplink.py",
    "src/llanfeng_code_assistant/protocol_document.py",
    "src/llanfeng_code_assistant/registry.py",
    "src/llanfeng_code_assistant/inject_launch.py",
    "src/llanfeng_code_assistant/file_ops.py"
)

Add-Type -AssemblyName System.IO.Compression.FileSystem
$Archive = [System.IO.Compression.ZipFile]::OpenRead($AppArchive)
try {
    $ArchiveEntryNames = @(
        $Archive.Entries |
            ForEach-Object { $_.FullName.Replace("\", "/") }
    )
}
finally {
    $Archive.Dispose()
}

$MissingArchiveEntries = @(
    $RequiredArchiveEntries |
        Where-Object { $ArchiveEntryNames -notcontains $_ }
)
if ($MissingArchiveEntries.Count -gt 0) {
    Stop-Build "Archive is missing required runtime files: $($MissingArchiveEntries -join ', ')"
}

$ForbiddenArchiveHits = @()
foreach ($EntryName in $ArchiveEntryNames) {
    $IsAllowed = $AllowedArchiveEntries -contains $EntryName
    if (-not $IsAllowed) {
        foreach ($Prefix in $AllowedArchivePrefixes) {
            if ($EntryName.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                $IsAllowed = $true
                break
            }
        }
    }

    $IsForbidden = -not $IsAllowed
    if (-not $IsForbidden) {
        $IsForbidden = ($ForbiddenArchiveEntries -contains $EntryName) -or
            $EntryName.EndsWith(".pyc", [System.StringComparison]::OrdinalIgnoreCase) -or
            $EntryName.IndexOf("/__pycache__/", [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    }
    if (-not $IsForbidden) {
        foreach ($Prefix in $ForbiddenArchivePrefixes) {
            if ($EntryName.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                $IsForbidden = $true
                break
            }
        }
    }
    if ($IsForbidden) {
        $ForbiddenArchiveHits += $EntryName
    }
}

if ($ForbiddenArchiveHits.Count -gt 0) {
    Stop-Build "Archive contains forbidden files: $($ForbiddenArchiveHits -join ', ')"
}

$WindowsPackageCertifi = Join-Path $ProjectRoot "build\windows\site-packages\certifi"
if (-not (Test-Path -LiteralPath $WindowsPackageCertifi)) {
    Stop-Build "Windows package is missing certifi. Re-run this script after confirming Python dependency installation can access PyPI."
}

exit 0
