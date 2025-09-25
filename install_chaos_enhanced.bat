@echo off
REM Enhanced CHAOS Desktop Application Installer for Windows

setlocal enabledelayedexpansion

set APP_NAME=CHAOS
set INSTALL_DIR=%USERPROFILE%\Applications\CHAOS
set VENV_DIR=%INSTALL_DIR%\venv
set BACKUP_DIR=%USERPROFILE%\.chaos_backup

echo CHAOS Desktop Application Installer
echo ==================================
echo.

REM Check if already installed
if exist "%INSTALL_DIR%" (
    echo CHAOS is already installed at: %INSTALL_DIR%
    set /p reinstall="Do you want to reinstall? (y/N): "
    if /i not "!reinstall!"=="y" (
        echo Installation cancelled.
        pause
        exit /b 0
    )
    
    REM Backup existing installation
    echo Backing up existing installation...
    if exist "%BACKUP_DIR%" rmdir /s /q "%BACKUP_DIR%"
    move "%INSTALL_DIR%" "%BACKUP_DIR%"
)

REM Create installation directory
echo Creating installation directory: %INSTALL_DIR%
mkdir "%INSTALL_DIR%" 2>nul

REM Get the source directory (where this script is run from)
set SOURCE_DIR=%CD%

REM Copy application files
echo Copying application files...
xcopy "%SOURCE_DIR%\chaos_lib" "%INSTALL_DIR%\chaos_lib" /E /I /Q
xcopy "%SOURCE_DIR%\desktop_app" "%INSTALL_DIR%\desktop_app" /E /I /Q
copy "%SOURCE_DIR%\config.yaml" "%INSTALL_DIR%\" >nul
copy "%SOURCE_DIR%\requirements.txt" "%INSTALL_DIR%\" >nul
copy "%SOURCE_DIR%\setup.bat" "%INSTALL_DIR%\" >nul
copy "%SOURCE_DIR%\setup.sh" "%INSTALL_DIR%\" >nul

REM Create virtual environment
echo Creating virtual environment...
cd /d "%INSTALL_DIR%"
python -m venv venv

REM Activate virtual environment and install dependencies
echo Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Create launcher script
echo Creating launcher...
echo @echo off > "%INSTALL_DIR%\start_chaos.bat"
echo REM CHAOS Desktop Application Launcher >> "%INSTALL_DIR%\start_chaos.bat"
echo. >> "%INSTALL_DIR%\start_chaos.bat"
echo cd /d "%%~dp0" >> "%INSTALL_DIR%\start_chaos.bat"
echo call venv\Scripts\activate.bat >> "%INSTALL_DIR%\start_chaos.bat"
echo python desktop_app\main_gui.py >> "%INSTALL_DIR%\start_chaos.bat"

REM Create Start Menu shortcut
echo Creating Start Menu shortcut...
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%APPDATA%\Microsoft\Windows\Start Menu\Programs\CHAOS.lnk'); $Shortcut.TargetPath = '%INSTALL_DIR%\start_chaos.bat'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.Description = 'CHAOS Desktop Application'; $Shortcut.Save()" 2>nul
if %errorlevel% equ 0 (
    echo Start Menu shortcut created
) else (
    echo Warning: Could not create Start Menu shortcut
)

REM Create desktop shortcut
set /p create_shortcut="Create desktop shortcut? (y/N): "
if /i "!create_shortcut!"=="y" (
    echo Creating desktop shortcut...
    powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%USERPROFILE%\Desktop\CHAOS.lnk'); $Shortcut.TargetPath = '%INSTALL_DIR%\start_chaos.bat'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.Description = 'CHAOS Desktop Application'; $Shortcut.Save()" 2>nul
    if !errorlevel! equ 0 (
        echo Desktop shortcut created: %USERPROFILE%\Desktop\CHAOS.lnk
    ) else (
        echo Warning: Could not create desktop shortcut
    )
)

REM Create registry entries for Add/Remove Programs
echo Creating registry entries...
reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall\CHAOS" /v "DisplayName" /t REG_SZ /d "CHAOS Desktop Application" /f >nul 2>&1
reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall\CHAOS" /v "DisplayVersion" /t REG_SZ /d "1.0" /f >nul 2>&1
reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall\CHAOS" /v "Publisher" /t REG_SZ /d "CHAOS Team" /f >nul 2>&1
reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall\CHAOS" /v "InstallLocation" /t REG_SZ /d "%INSTALL_DIR%" /f >nul 2>&1
reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall\CHAOS" /v "UninstallString" /t REG_SZ /d "%INSTALL_DIR%\uninstall.bat" /f >nul 2>&1

echo.
echo Installation complete!
echo =====================
echo.
echo CHAOS has been installed to: %INSTALL_DIR%
echo.
echo To start CHAOS:
echo   - Run: %INSTALL_DIR%\start_chaos.bat
echo   - Use Start Menu shortcut
echo   - Double-click desktop shortcut (if created)
echo.
echo To uninstall, run: %INSTALL_DIR%\uninstall.bat
echo.

REM Create enhanced uninstaller
echo @echo off > "%INSTALL_DIR%\uninstall.bat"
echo REM CHAOS Desktop Application Uninstaller >> "%INSTALL_DIR%\uninstall.bat"
echo. >> "%INSTALL_DIR%\uninstall.bat"
echo setlocal enabledelayedexpansion >> "%INSTALL_DIR%\uninstall.bat"
echo set INSTALL_DIR=%%~dp0 >> "%INSTALL_DIR%\uninstall.bat"
echo set APP_NAME=CHAOS >> "%INSTALL_DIR%\uninstall.bat"
echo. >> "%INSTALL_DIR%\uninstall.bat"
echo echo CHAOS Desktop Application Uninstaller >> "%INSTALL_DIR%\uninstall.bat"
echo echo ===================================== >> "%INSTALL_DIR%\uninstall.bat"
echo echo. >> "%INSTALL_DIR%\uninstall.bat"
echo echo This will remove CHAOS from: %%INSTALL_DIR%% >> "%INSTALL_DIR%\uninstall.bat"
echo echo. >> "%INSTALL_DIR%\uninstall.bat"
echo set /p confirm="Are you sure you want to uninstall CHAOS? (y/N): " >> "%INSTALL_DIR%\uninstall.bat"
echo if /i not "%%confirm%%"=="y" ( >> "%INSTALL_DIR%\uninstall.bat"
echo     echo Uninstall cancelled. >> "%INSTALL_DIR%\uninstall.bat"
echo     pause >> "%INSTALL_DIR%\uninstall.bat"
echo     exit /b 0 >> "%INSTALL_DIR%\uninstall.bat"
echo ^) >> "%INSTALL_DIR%\uninstall.bat"
echo. >> "%INSTALL_DIR%\uninstall.bat"
echo echo Removing CHAOS installation... >> "%INSTALL_DIR%\uninstall.bat"
echo. >> "%INSTALL_DIR%\uninstall.bat"
echo REM Remove Start Menu shortcut >> "%INSTALL_DIR%\uninstall.bat"
echo if exist "%%APPDATA%%\Microsoft\Windows\Start Menu\Programs\CHAOS.lnk" del "%%APPDATA%%\Microsoft\Windows\Start Menu\Programs\CHAOS.lnk" >> "%INSTALL_DIR%\uninstall.bat"
echo echo Removed Start Menu shortcut >> "%INSTALL_DIR%\uninstall.bat"
echo. >> "%INSTALL_DIR%\uninstall.bat"
echo REM Remove desktop shortcut >> "%INSTALL_DIR%\uninstall.bat"
echo if exist "%%USERPROFILE%%\Desktop\CHAOS.lnk" del "%%USERPROFILE%%\Desktop\CHAOS.lnk" >> "%INSTALL_DIR%\uninstall.bat"
echo echo Removed desktop shortcut >> "%INSTALL_DIR%\uninstall.bat"
echo. >> "%INSTALL_DIR%\uninstall.bat"
echo REM Remove registry entries >> "%INSTALL_DIR%\uninstall.bat"
echo reg delete "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall\CHAOS" /f >nul 2>&1 >> "%INSTALL_DIR%\uninstall.bat"
echo echo Removed registry entries >> "%INSTALL_DIR%\uninstall.bat"
echo. >> "%INSTALL_DIR%\uninstall.bat"
echo REM Remove installation directory >> "%INSTALL_DIR%\uninstall.bat"
echo if exist "%%INSTALL_DIR%%" rmdir /s /q "%%INSTALL_DIR%%" >> "%INSTALL_DIR%\uninstall.bat"
echo echo Removed installation directory >> "%INSTALL_DIR%\uninstall.bat"
echo. >> "%INSTALL_DIR%\uninstall.bat"
echo echo. >> "%INSTALL_DIR%\uninstall.bat"
echo echo CHAOS has been completely uninstalled. >> "%INSTALL_DIR%\uninstall.bat"
echo echo. >> "%INSTALL_DIR%\uninstall.bat"
echo REM Restore backup if it exists >> "%INSTALL_DIR%\uninstall.bat"
echo if exist "%%USERPROFILE%%\.chaos_backup" ( >> "%INSTALL_DIR%\uninstall.bat"
echo     set /p restore="Restore previous installation from backup? (y/N): " >> "%INSTALL_DIR%\uninstall.bat"
echo     if /i "%%restore%%"=="y" ( >> "%INSTALL_DIR%\uninstall.bat"
echo         move "%%USERPROFILE%%\.chaos_backup" "%%INSTALL_DIR%%" >> "%INSTALL_DIR%\uninstall.bat"
echo         echo Previous installation restored. >> "%INSTALL_DIR%\uninstall.bat"
echo     ^) else ( >> "%INSTALL_DIR%\uninstall.bat"
echo         rmdir /s /q "%%USERPROFILE%%\.chaos_backup" >> "%INSTALL_DIR%\uninstall.bat"
echo         echo Backup removed. >> "%INSTALL_DIR%\uninstall.bat"
echo     ^) >> "%INSTALL_DIR%\uninstall.bat"
echo ^) >> "%INSTALL_DIR%\uninstall.bat"
echo pause >> "%INSTALL_DIR%\uninstall.bat"

echo Enhanced uninstaller created: %INSTALL_DIR%\uninstall.bat
pause
