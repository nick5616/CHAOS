@echo off
echo ======================================================
echo  CHAOS Project Setup Script for Windows
echo ======================================================
echo.
echo This script will run the PowerShell setup script.
echo If you prefer to run it directly, use: setup.ps1
echo.

powershell -ExecutionPolicy Bypass -File "setup.ps1"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: PowerShell setup failed.
    echo Please try running setup.ps1 directly in PowerShell.
    pause
    exit /b 1
)

echo.
echo Setup completed successfully!
pause