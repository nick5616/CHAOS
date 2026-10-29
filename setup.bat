@echo off
REM CHAOS setup for Windows. Double-click to install, or re-run any time to repair/update.
REM Pass --desktop-shortcut to also put a shortcut on the Desktop.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
set RESULT=%errorlevel%
echo.
pause
exit /b %RESULT%
