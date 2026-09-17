# SpotImageViewer Native Build & Launch Script
# Builds the super-lightweight C# .NET 8 / WebView2 native desktop app

param(
    [switch]$Run,
    [switch]$Publish,
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$DotnetExe = "$env:LOCALAPPDATA\Microsoft\dotnet\dotnet.exe"

if (-not (Test-Path $DotnetExe)) {
    $DotnetExe = "dotnet"
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  SpotImageViewer.Native: High-Speed Native Build" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ProjectFile = Join-Path $ScriptDir "SpotImageViewer.Native\SpotImageViewer.Native.csproj"

# Detect version if not passed
if ([string]::IsNullOrWhiteSpace($Version)) {
    $ConfigCs = Join-Path $ScriptDir "SpotImageViewer.Native\Core\Config.cs"
    if (Test-Path $ConfigCs) {
        $content = Get-Content $ConfigCs -Raw
        if ($content -match 'CURRENT_VERSION\s*=\s*"([^"]+)"') {
            $Version = $matches[1]
        }
    }
}
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = "0.0.1"
}

Write-Host "Target Version: v$Version" -ForegroundColor Magenta

$PublishDir = Join-Path $ScriptDir "SpotImageViewer.Native\publish"
$ReleaseArchiveDir = Join-Path $ScriptDir "SpotImageViewer.Native\releases\v$Version"

if ($Publish) {
    Write-Host "`nPublishing single-file optimized native WPF executable..." -ForegroundColor Yellow
    Get-Process -Name "SpotImageViewer*" -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Milliseconds 300
    & $DotnetExe publish $ProjectFile -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -o $PublishDir
    
    Write-Host "`nPublished executable located at: SpotImageViewer.Native\publish\SpotImageViewer.Native.exe" -ForegroundColor Green

    # Archive this version release
    Write-Host "`nArchiving release to $ReleaseArchiveDir..." -ForegroundColor Cyan
    if (-not (Test-Path $ReleaseArchiveDir)) {
        New-Item -ItemType Directory -Path $ReleaseArchiveDir -Force | Out-Null
    }
    Copy-Item "$PublishDir\*" -Destination $ReleaseArchiveDir -Recurse -Force
    Write-Host "Release v$Version successfully archived at: SpotImageViewer.Native\releases\v$Version\" -ForegroundColor Green
} else {
    Write-Host "`nBuilding in Release configuration..." -ForegroundColor Yellow
    & $DotnetExe build $ProjectFile -c Release
    Write-Host "`nBuild complete!" -ForegroundColor Green
}

if ($Run) {
    $BinPath = Join-Path $ScriptDir "SpotImageViewer.Native\bin\Release\net8.0-windows\SpotImageViewer.Native.exe"
    if ($Publish) {
        $BinPath = Join-Path $ScriptDir "SpotImageViewer.Native\publish\SpotImageViewer.Native.exe"
    }
    Write-Host "`nLaunching SpotImageViewer.Native..." -ForegroundColor Green
    Start-Process $BinPath
}
