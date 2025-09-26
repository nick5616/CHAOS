# FFmpeg Installation Script for Windows
# This script downloads and installs FFmpeg if package managers fail

Write-Host "FFmpeg Direct Installation Script" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Check if FFmpeg is already installed
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "FFmpeg is already installed and available in PATH." -ForegroundColor Green
    exit 0
}

Write-Host "FFmpeg not found. Downloading and installing FFmpeg..." -ForegroundColor Yellow

# Create temp directory
$tempDir = Join-Path $env:TEMP "ffmpeg_install"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

try {
    # Download FFmpeg
    Write-Host "Downloading FFmpeg..." -ForegroundColor Yellow
    $ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    $ffmpegZip = Join-Path $tempDir "ffmpeg.zip"
    
    Invoke-WebRequest -Uri $ffmpegUrl -OutFile $ffmpegZip -UseBasicParsing
    
    # Extract FFmpeg
    Write-Host "Extracting FFmpeg..." -ForegroundColor Yellow
    Expand-Archive -Path $ffmpegZip -DestinationPath $tempDir -Force
    
    # Find the extracted folder
    $extractedFolder = Get-ChildItem -Path $tempDir -Directory | Where-Object { $_.Name -like "ffmpeg-*" } | Select-Object -First 1
    
    if ($extractedFolder) {
        # Create a local bin directory
        $localBin = Join-Path (Get-Location) "bin"
        if (-not (Test-Path $localBin)) {
            New-Item -ItemType Directory -Path $localBin -Force | Out-Null
        }
        
        # Copy FFmpeg executables
        Copy-Item -Path "$($extractedFolder.FullName)\bin\*" -Destination $localBin -Force
        
        # Add to PATH for current session
        $env:Path = "$localBin;$env:Path"
        
        Write-Host "FFmpeg installed to: $localBin" -ForegroundColor Green
        Write-Host "Added to PATH for current session." -ForegroundColor Green
        
        # Test installation
        $ffmpegVersion = & "$localBin\ffmpeg.exe" -version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "FFmpeg installation verified successfully!" -ForegroundColor Green
            Write-Host ""
            Write-Host "Note: To make this permanent, add '$localBin' to your system PATH:" -ForegroundColor Yellow
            Write-Host "1. Open System Properties > Environment Variables" -ForegroundColor Yellow
            Write-Host "2. Add '$localBin' to the PATH variable" -ForegroundColor Yellow
        } else {
            throw "FFmpeg installation verification failed"
        }
    } else {
        throw "Could not find extracted FFmpeg folder"
    }
} catch {
    Write-Host "ERROR: Failed to install FFmpeg: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Please install FFmpeg manually from: https://ffmpeg.org/download.html" -ForegroundColor Red
    exit 1
} finally {
    # Cleanup
    if (Test-Path $tempDir) {
        Remove-Item $tempDir -Recurse -Force
    }
}

Write-Host ""
Write-Host "FFmpeg installation complete!" -ForegroundColor Green
