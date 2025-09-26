# CHAOS Project Setup Script for Windows (PowerShell)
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host " CHAOS Project Setup Script for Windows (PowerShell)" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# Set working directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptPath
Write-Host "[0/6] Setting working directory to: $(Get-Location)" -ForegroundColor Green
Write-Host ""

# Check for Python
Write-Host "[1/6] Checking for Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "     Python found: $pythonVersion" -ForegroundColor Green
    } else {
        throw "Python not found"
    }
} catch {
    Write-Host "ERROR: Python not found. Please install from python.org and add to PATH." -ForegroundColor Red
    exit 1
}
Write-Host ""

# Check for FFmpeg
Write-Host "[2/6] Checking for FFmpeg..." -ForegroundColor Yellow
try {
    $ffmpegVersion = ffmpeg -version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "     FFmpeg found." -ForegroundColor Green
    } else {
        throw "FFmpeg not found"
    }
} catch {
    Write-Host "     FFmpeg not found. Attempting to install automatically..." -ForegroundColor Yellow
    
    # Try winget first
    Write-Host "     Trying winget (Windows Package Manager)..." -ForegroundColor Yellow
    try {
        winget install "Gyan.FFmpeg" --accept-package-agreements --accept-source-agreements --silent
        if ($LASTEXITCODE -eq 0) {
            Write-Host "     FFmpeg installed successfully via winget!" -ForegroundColor Green
            # Wait for installation to complete
            Start-Sleep -Seconds 3
            # Find and add FFmpeg to PATH
            $ffmpegPath = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*" -Recurse -Name "ffmpeg.exe" | Select-Object -First 1
            if ($ffmpegPath) {
                $ffmpegDir = Split-Path (Join-Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" $ffmpegPath)
                $env:Path = "$ffmpegDir;$env:Path"
                Write-Host "     Added FFmpeg to PATH: $ffmpegDir" -ForegroundColor Green
                # Test if FFmpeg is now accessible
                $testFFmpeg = ffmpeg -version 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "     FFmpeg is now accessible!" -ForegroundColor Green
                } else {
                    Write-Host "     FFmpeg installed but not accessible. Trying alternative method..." -ForegroundColor Yellow
                    # Try to find FFmpeg in common locations
                    $commonPaths = @(
                        "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin",
                        "$env:PROGRAMFILES\ffmpeg\bin",
                        "$env:PROGRAMFILES(X86)\ffmpeg\bin"
                    )
                    foreach ($path in $commonPaths) {
                        $found = Get-ChildItem $path -Name "ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
                        if ($found) {
                            $fullPath = Join-Path $path $found
                            $env:Path = "$(Split-Path $fullPath);$env:Path"
                            Write-Host "     Found FFmpeg at: $fullPath" -ForegroundColor Green
                            break
                        }
                    }
                }
            }
        } else {
            throw "winget failed"
        }
    } catch {
        Write-Host "     winget failed, trying chocolatey..." -ForegroundColor Yellow
        try {
            choco install ffmpeg -y
            if ($LASTEXITCODE -eq 0) {
                Write-Host "     FFmpeg installed successfully via chocolatey!" -ForegroundColor Green
                # Refresh environment variables
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
                # Wait a moment for PATH to be updated
                Start-Sleep -Seconds 2
            } else {
                throw "chocolatey failed"
            }
        } catch {
            Write-Host "     Package managers failed, trying direct download..." -ForegroundColor Yellow
            try {
                & "$scriptPath\install_ffmpeg.ps1"
                if ($LASTEXITCODE -ne 0) {
                    throw "Direct download failed"
                }
            } catch {
                Write-Host "     Automatic installation failed. Please install FFmpeg manually:" -ForegroundColor Red
                Write-Host "     Download from: https://ffmpeg.org/download.html" -ForegroundColor Red
                Write-Host "     Or use chocolatey: choco install ffmpeg" -ForegroundColor Red
                Write-Host "     Or use winget: winget install ffmpeg" -ForegroundColor Red
                Write-Host "     Make sure to add FFmpeg to your system PATH." -ForegroundColor Red
                Write-Host "     After installation, run this setup script again." -ForegroundColor Red
                exit 1
            }
        }
    }
    
    # Verify installation
    Write-Host "     Verifying FFmpeg installation..." -ForegroundColor Yellow
    $ffmpegFound = $false
    
    # Try multiple times with different methods
    for ($i = 1; $i -le 3; $i++) {
        Write-Host "     Attempt $i/3 to find FFmpeg..." -ForegroundColor Yellow
        
        # Method 1: Check if FFmpeg is in PATH
        try {
            $ffmpegVersion = ffmpeg -version 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "     FFmpeg verified and ready!" -ForegroundColor Green
                $ffmpegFound = $true
                break
            }
        } catch {}
        
        # Method 2: Search for FFmpeg in common locations
        $searchPaths = @(
            "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*",
            "$env:PROGRAMFILES\ffmpeg",
            "$env:PROGRAMFILES(X86)\ffmpeg",
            "$env:USERPROFILE\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*"
        )
        
        foreach ($searchPath in $searchPaths) {
            $ffmpegExe = Get-ChildItem $searchPath -Recurse -Name "ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($ffmpegExe) {
                $ffmpegDir = Split-Path (Get-ChildItem $searchPath -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
                $env:Path = "$ffmpegDir;$env:Path"
                Write-Host "     Found FFmpeg at: $ffmpegDir" -ForegroundColor Green
                
                # Test again
                try {
                    $ffmpegVersion = ffmpeg -version 2>&1
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "     FFmpeg verified and ready!" -ForegroundColor Green
                        $ffmpegFound = $true
                        break
                    }
                } catch {}
            }
        }
        
        if ($ffmpegFound) { break }
        
        # Wait before next attempt
        if ($i -lt 3) {
            Start-Sleep -Seconds 2
        }
    }
    
    if (-not $ffmpegFound) {
        Write-Host "     FFmpeg installation completed but not found in PATH." -ForegroundColor Red
        Write-Host "     Please restart your terminal and run this script again." -ForegroundColor Red
        Write-Host "     Or manually add FFmpeg to your system PATH." -ForegroundColor Red
        Write-Host "     You can also try running: winget install Gyan.FFmpeg" -ForegroundColor Red
        exit 1
    }
}
Write-Host ""

# Create virtual environment
Write-Host "[3/6] Creating virtual environment 'venv'..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "     Virtual environment exists. Skipping." -ForegroundColor Green
} else {
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
    Write-Host "     Virtual environment created successfully." -ForegroundColor Green
}
Write-Host ""

# Install base packages
Write-Host "[4/6] Activating environment and installing base packages..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"
pip install -r "requirements.txt"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install base packages." -ForegroundColor Red
    exit 1
}
Write-Host "     Base packages installed." -ForegroundColor Green
Write-Host ""

# Install PyTorch
Write-Host "[5/6] Installing PyTorch for NVIDIA GPU (CUDA)..." -ForegroundColor Yellow
Write-Host "     This is the slowest step. Please be patient." -ForegroundColor Yellow

# First, uninstall any existing PyTorch to avoid conflicts
Write-Host "     Removing any existing PyTorch installations..." -ForegroundColor Yellow
pip uninstall torch torchvision torchaudio -y 2>$null

# Try CUDA 12.1 first (compatible with CUDA 13)
Write-Host "     Attempting to install CUDA 12.1 PyTorch..." -ForegroundColor Yellow
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
if ($LASTEXITCODE -eq 0) {
    Write-Host "     CUDA 12.1 PyTorch installed successfully!" -ForegroundColor Green
    # Verify CUDA is available
    $cudaTest = python -c "import torch; print('CUDA available:', torch.cuda.is_available())" 2>$null
    if ($cudaTest -match "True") {
        Write-Host "     CUDA support verified! You can now use --gpu flag for faster processing." -ForegroundColor Green
    } else {
        Write-Host "     WARNING: PyTorch installed but CUDA not detected. Trying CUDA 11.8..." -ForegroundColor Yellow
        pip uninstall torch torchvision torchaudio -y 2>$null
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
        if ($LASTEXITCODE -eq 0) {
            Write-Host "     CUDA 11.8 PyTorch installed successfully!" -ForegroundColor Green
        } else {
            Write-Host "     WARNING: CUDA PyTorch installation failed. Installing CPU version..." -ForegroundColor Yellow
            pip install torch torchvision torchaudio
        }
    }
} else {
    Write-Host "     CUDA 12.1 failed, trying CUDA 11.8..." -ForegroundColor Yellow
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    if ($LASTEXITCODE -eq 0) {
        Write-Host "     CUDA 11.8 PyTorch installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "     WARNING: CUDA PyTorch installation failed. Installing CPU version..." -ForegroundColor Yellow
        Write-Host "     You can manually install CUDA PyTorch later if needed." -ForegroundColor Yellow
        pip install torch torchvision torchaudio
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to install PyTorch." -ForegroundColor Red
            exit 1
        }
    }
}
Write-Host "     PyTorch installation complete." -ForegroundColor Green
Write-Host ""

# Setup complete
Write-Host "[6/6] Setup Complete!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To use CHAOS, open a terminal in this folder and run:" -ForegroundColor Cyan
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "Then run the main script:" -ForegroundColor Cyan
Write-Host "  python main.py analyze --debug" -ForegroundColor White
Write-Host "  python main.py analyze --debug --gpu  (for GPU acceleration)" -ForegroundColor White
Write-Host ""