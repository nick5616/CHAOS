@echo off
setlocal

echo ======================================================
echo  CHAOS Project Setup Script for Windows (Robust)
echo ======================================================
echo.

REM --- Step 0: Change directory to the script's location ---
REM %~dp0 is the magic variable for the script's own directory.
echo [0/4] Setting working directory to script location...
pushd "%~dp0"
echo      Working directory is now: %cd%
echo.

REM --- Step 1: Check for Python ---
echo [1/4] Checking for Python installation...
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python is not found in your system's PATH.
    echo Please install Python from python.org and ensure "Add Python to PATH" is checked.
    goto :error
)
echo      Python found.
echo.

REM --- Step 2: Create virtual environment ---
echo [2/4] Creating virtual environment in 'venv' folder...
if exist "venv" (
    echo      Virtual environment 'venv' already exists. Skipping.
) else (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create the virtual environment.
        goto :error
    )
    echo      Virtual environment created successfully.
)
echo.

REM --- Step 3: Install packages ---
echo [3/4] Activating environment and installing required packages...
echo      This may take several minutes. Please be patient.
call "venv\Scripts\activate.bat"
pip install -r "requirements.txt"
if %errorlevel% neq 0 (
    echo ERROR: Failed to install packages. Check internet connection and requirements.txt.
    goto :error
)
echo      Packages installed successfully.
echo.

REM --- Step 4: Success ---
echo [4/4] Setup Complete!
echo ======================================================
echo.
echo To run the CHAOS system, open a new terminal in this folder
echo (you can right-click in Explorer and choose 'Open in Terminal'),
echo and then run this command to activate the environment:
echo.
echo   .\venv\Scripts\activate
echo.
echo Then you can run the main script, for example:
echo.
echo   python main.py ingest
echo.
goto :end

:error
echo.
echo ======================================================
echo  An error occurred. Please check the messages above.
echo ======================================================
pause

:end
popd
pause