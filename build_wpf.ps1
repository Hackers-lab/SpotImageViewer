# SpotImageViewer Pure WPF Native Build & Launch Script
# Builds the 100% pure native C# .NET 8 WPF desktop application

param(
    [switch]$Run,
    [switch]$Publish,
    [string]$Version = "0.0.1"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$DotnetExe = "$env:LOCALAPPDATA\Microsoft\dotnet\dotnet.exe"

if (-not (Test-Path $DotnetExe)) {
    $DotnetExe = "dotnet"
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  SpotImageViewer.WPF: Pure Native WPF Desktop Build" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ProjectFile = Join-Path $ScriptDir "SpotImageViewer.WPF\SpotImageViewer.WPF.csproj"
$PublishDir = Join-Path $ScriptDir "SpotImageViewer.WPF\publish"
$ReleaseArchiveDir = Join-Path $ScriptDir "SpotImageViewer.WPF\releases\v$Version"

Write-Host "Target Version: v$Version" -ForegroundColor Magenta

if ($Publish) {
    Write-Host "`nPublishing single-file ultra-fast native WPF executable..." -ForegroundColor Yellow
    Get-Process -Name "SpotImageViewer.WPF*" -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Milliseconds 300
    & $DotnetExe publish $ProjectFile -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:EnableCompressionInSingleFile=true -o $PublishDir
    
    Write-Host "`nPublished executable located at: SpotImageViewer.WPF\publish\SpotImageViewer.WPF.exe" -ForegroundColor Green

    # Archive this version release
    Write-Host "`nArchiving release to $ReleaseArchiveDir..." -ForegroundColor Cyan
    if (-not (Test-Path $ReleaseArchiveDir)) {
        New-Item -ItemType Directory -Path $ReleaseArchiveDir -Force | Out-Null
    }
    Copy-Item "$PublishDir\*" -Destination $ReleaseArchiveDir -Recurse -Force
    Write-Host "Release v$Version successfully archived at: SpotImageViewer.WPF\releases\v$Version\" -ForegroundColor Green
} else {
    Write-Host "`nBuilding in Release configuration..." -ForegroundColor Yellow
    & $DotnetExe build $ProjectFile -c Release
    Write-Host "`nBuild complete!" -ForegroundColor Green
}

if ($Run) {
    $BinPath = Join-Path $ScriptDir "SpotImageViewer.WPF\bin\Release\net8.0-windows\SpotImageViewer.WPF.exe"
    if ($Publish) {
        $BinPath = Join-Path $ScriptDir "SpotImageViewer.WPF\publish\SpotImageViewer.WPF.exe"
    }
    Write-Host "`nLaunching SpotImageViewer.WPF..." -ForegroundColor Green
    Start-Process $BinPath
}
