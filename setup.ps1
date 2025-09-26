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
$ffmpegFound = $false

# First, check if FFmpeg is already available
try {
    $ffmpegVersion = ffmpeg -version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "     FFmpeg found and working." -ForegroundColor Green
        $ffmpegFound = $true
    }
} catch {
    Write-Host "     FFmpeg not found in PATH." -ForegroundColor Yellow
}

# If not found, try to install it
if (-not $ffmpegFound) {
    Write-Host "     Attempting to install FFmpeg..." -ForegroundColor Yellow
    
    # Try winget first
    Write-Host "     Trying winget (Windows Package Manager)..." -ForegroundColor Yellow
    try {
        winget install "Gyan.FFmpeg" --accept-package-agreements --accept-source-agreements --silent
        if ($LASTEXITCODE -eq 0) {
            Write-Host "     FFmpeg installed via winget!" -ForegroundColor Green
            Start-Sleep -Seconds 3
            
            # Find FFmpeg installation
            $ffmpegExe = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*" -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($ffmpegExe) {
                $ffmpegDir = Split-Path $ffmpegExe.FullName
                
                # Add to current session PATH
                $env:Path = "$ffmpegDir;$env:Path"
                Write-Host "     Added FFmpeg to current session PATH: $ffmpegDir" -ForegroundColor Green
                
                # Add to user PATH permanently
                try {
                    $currentUserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
                    if ($currentUserPath -notlike "*$ffmpegDir*") {
                        [System.Environment]::SetEnvironmentVariable("Path", "$currentUserPath;$ffmpegDir", "User")
                        Write-Host "     Added FFmpeg to user PATH permanently" -ForegroundColor Green
                    }
                } catch {
                    Write-Host "     WARNING: Could not add FFmpeg to permanent PATH. You may need to restart your terminal." -ForegroundColor Yellow
                }
                
                # Test if it works now
                try {
                    $testFFmpeg = ffmpeg -version 2>&1
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "     FFmpeg verified and ready!" -ForegroundColor Green
                        $ffmpegFound = $true
                    }
                } catch {
                    Write-Host "     FFmpeg installed but not accessible in current session." -ForegroundColor Yellow
                }
            }
        }
    } catch {
        Write-Host "     winget failed, trying chocolatey..." -ForegroundColor Yellow
        try {
            choco install ffmpeg -y
            if ($LASTEXITCODE -eq 0) {
                Write-Host "     FFmpeg installed via chocolatey!" -ForegroundColor Green
                # Refresh PATH
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
                Start-Sleep -Seconds 2
                
                # Test if it works now
                try {
                    $testFFmpeg = ffmpeg -version 2>&1
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "     FFmpeg verified and ready!" -ForegroundColor Green
                        $ffmpegFound = $true
                    }
                } catch {
                    Write-Host "     FFmpeg installed but not accessible in current session." -ForegroundColor Yellow
                }
            }
        } catch {
            Write-Host "     Package managers failed. Please install FFmpeg manually:" -ForegroundColor Red
            Write-Host "     Download from: https://ffmpeg.org/download.html" -ForegroundColor Red
            Write-Host "     Or use: winget install Gyan.FFmpeg" -ForegroundColor Red
            Write-Host "     Or use: choco install ffmpeg" -ForegroundColor Red
            Write-Host "     After installation, restart your terminal and run this script again." -ForegroundColor Red
            exit 1
        }
    }
}

# Final verification
if (-not $ffmpegFound) {
    Write-Host "     WARNING: FFmpeg installation may require a terminal restart." -ForegroundColor Yellow
    Write-Host "     If you encounter FFmpeg errors, please restart your terminal and run this script again." -ForegroundColor Yellow
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
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate virtual environment." -ForegroundColor Red
    exit 1
}

# Install requirements
Write-Host "     Installing Python dependencies from requirements.txt..." -ForegroundColor Yellow
pip install -r "requirements.txt"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install base packages from requirements.txt." -ForegroundColor Red
    Write-Host "     Trying to install packages individually..." -ForegroundColor Yellow
    
    # Try installing packages individually
    $packages = @("pyyaml", "pandas", "tqdm", "opencv-python", "easyocr", "librosa", "thefuzz", "PyQt6", "Pillow", "psutil")
    foreach ($package in $packages) {
        Write-Host "     Installing $package..." -ForegroundColor Yellow
        pip install $package
        if ($LASTEXITCODE -ne 0) {
            Write-Host "     WARNING: Failed to install $package" -ForegroundColor Yellow
        }
    }
    
    # Install whisper separately
    Write-Host "     Installing OpenAI Whisper..." -ForegroundColor Yellow
    pip install openai-whisper
    if ($LASTEXITCODE -ne 0) {
        Write-Host "     WARNING: Failed to install OpenAI Whisper" -ForegroundColor Yellow
    }
}

Write-Host "     Base packages installation completed." -ForegroundColor Green
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

# Final verification
Write-Host "[6/6] Verifying installation..." -ForegroundColor Yellow
Write-Host "     Testing Python environment..." -ForegroundColor Yellow
python -c "import sys; print('Python version:', sys.version)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python test failed." -ForegroundColor Red
    exit 1
}

Write-Host "     Testing key dependencies..." -ForegroundColor Yellow
python -c "import yaml, pandas, cv2, easyocr, whisper, librosa, thefuzz; print('All key dependencies imported successfully!')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Some dependencies may not be properly installed." -ForegroundColor Yellow
    Write-Host "     You may need to install missing packages manually." -ForegroundColor Yellow
}

Write-Host "     Testing FFmpeg..." -ForegroundColor Yellow
try {
    $ffmpegTest = ffmpeg -version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "     FFmpeg is working!" -ForegroundColor Green
    } else {
        Write-Host "WARNING: FFmpeg may not be accessible. You may need to restart your terminal." -ForegroundColor Yellow
    }
} catch {
    Write-Host "WARNING: FFmpeg not found. Please restart your terminal and run this script again." -ForegroundColor Yellow
}

# Setup complete
Write-Host ""
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To use CHAOS, open a NEW terminal in this folder and run:" -ForegroundColor Cyan
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "Then run the main script:" -ForegroundColor Cyan
Write-Host "  python main.py analyze --debug" -ForegroundColor White
Write-Host "  python main.py analyze --debug --gpu  (for GPU acceleration)" -ForegroundColor White
Write-Host ""
Write-Host "IMPORTANT: If you encounter FFmpeg errors, please restart your terminal" -ForegroundColor Yellow
Write-Host "and run this setup script again to ensure FFmpeg is properly configured." -ForegroundColor Yellow
Write-Host ""
Write-Host "The clipper has been updated to automatically find FFmpeg even if it's not in PATH." -ForegroundColor Green
Write-Host "This should resolve most FFmpeg-related issues." -ForegroundColor Green
Write-Host ""