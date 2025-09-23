@echo off
setlocal
echo ======================================================
echo  CHAOS Project Setup Script for Windows
echo ======================================================
echo.

pushd "%~dp0"
echo [0/5] Setting working directory to: %cd%
echo.

echo [1/5] Checking for Python...
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install from python.org and add to PATH.
    goto :error
)
echo      Python found.
echo.

echo [2/5] Creating virtual environment 'venv'...
if exist "venv" (
    echo      Virtual environment exists. Skipping.
) else (
    python -m venv venv
    if %errorlevel% neq 0 (goto :error)
    echo      Virtual environment created successfully.
)
echo.

echo [3/5] Activating environment and installing base packages...
call "venv\Scripts\activate.bat"
pip install -r "requirements.txt"
if %errorlevel% neq 0 (
    echo ERROR: Failed to install base packages.
    goto :error
)
echo      Base packages installed.
echo.

echo [4/5] Installing PyTorch for NVIDIA GPU (CUDA)...
echo      This is the slowest step. Please be patient.
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
if %errorlevel% neq 0 (
    echo WARNING: Failed to install PyTorch for CUDA.
    echo The script will fall back to the CPU version.
    echo To fix, check your NVIDIA drivers and get the correct command from pytorch.org.
    pip install torch torchvision torchaudio
)
echo      PyTorch installed.
echo.

echo [5/5] Setup Complete!
echo ======================================================
echo.
echo To use CHAOS, open a terminal in this folder and run:
echo   .\venv\Scripts\activate
echo Then run the main script:
echo   python main.py analyze --debug
echo.
goto :end

:error
echo.
echo ERROR: Setup failed. Please check messages above.
pause

:end
popd
pause